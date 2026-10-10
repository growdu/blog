# PostgreSQL 逻辑复制里 `RUNNING_XACTS` 写入机制与快照 `xmin / xmax / xip` 的演化：源码级深度拆解

| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 初稿 + 第十二节增补：补充 ReorderBuffer 视角——从 `SnapBuild → ReorderBufferSetBaseSnapshot` 把 `builder->snapshot` 挂到 `txn->base_snapshot`，到 `txns_by_base_snapshot_lsn` dlist 与 `ReorderBufferGetOldestXmin` 反控 slot.xmin，再到 `ReorderBufferReplay` 用 `txn->base_snapshot == NULL` 判定"是否要发送"，`ReorderBufferCopySnap` 把 `base_snapshot` + subxact 拼成 `snapshot_now` 喂给 output plugin，streaming 模式如何复用 `txn->snapshot_now`。源码级别 + 30+ 张架构图。配套源码版本：PostgreSQL 18 dev（`~/cwork/postgresql`）。 | 2026-09-29 |

> 本文是「PostgreSQL 逻辑复制源码系列」。同系列前文：
>
> - [PostgreSQL MVCC：从一行 UPDATE 到 5 个 HeapTuple 的演化](./postgresql-mvcc/index.html)
> - [PostgreSQL 事务生命周期：从 BEGIN/COMMIT 到 CLOG 一条链路](./postgresql-transaction-lifecycle/index.html)
> - [PostgreSQL 逻辑复制表的生命周期：从 `pg_replication_slots` 到 `pg_subscription_rel`](./postgresql-logical-replication-tables-lifecycle/index.html)
> - [PostgreSQL 逻辑复制 spill 深度拆解：ReorderBuffer 如何把 100GB 事务拆成小块](./postgresql-logical-replication-spill-deep-dive/index.html)
> - [PostgreSQL 逻辑复制的 ReorderBuffer 与事务机制](./postgresql-logical-replication-reorderbuffer-transaction/index.html)
> - [PostgreSQL 逻辑复制全链路：以一个真实事务为例，从 `INSERT` 到 `apply` 的源码级旅程](./postgresql-logical-replication-end-to-end-flow/index.html)
> - [PostgreSQL 元数据存储机制：从磁盘文件到内存缓存，`pg_class` 撑起的整个系统表体系](./postgresql-catalog-storage/index.html)

逻辑复制里最容易出 bug 的事不是 decode（`pgoutput` 已经写得相当稳定），也不是 apply（无脑 INSERT/UPDATE/DELETE），而是 **snapshot 怎么从 WAL 里"长"出来**——也就是 `RUNNING_XACTS` + `SnapBuild` 状态机 + `xmin / xmax / xip` 三个字段的更新规则。

很多 PG DBA 在用 `SELECT * FROM pg_replication_slots;` 看到 `restart_lsn` 不动时，第一反应是"复制停了"；**但其实 90% 的 case 是 `SnapBuild` 在等 `running->oldestRunningXid` 推进**，或者 `xmax` 被某个长 catalog DDL 卡住。

本文回答 5 个问题：

1. **`xl_running_xacts` 这条 WAL 记录到底写的是什么？谁触发？频率多少**？
2. **`SnapBuild` 状态机有 4 个状态**，它怎么从 WAL 里"长"出一个能 decode catalog 的 snapshot？
3. **`xmin` / `xmax` 在 `SnapBuild` 里和 `SnapshotData` 里语义完全不一样**——到底怎么演化？
4. **`xip` 数组在 `SnapBuild` 里被"重新定义"为"catalog-modifying xid 列表"**，这是怎么做到的？
5. **apply 端（worker）怎么消费这个 snapshot 决定"一条 tuple 对我可见吗"**？
6. **ReorderBuffer 怎么用 snapshot 决定一条事务"能不能发出去"——`txn->base_snapshot == NULL` 的判定、`txns_by_base_snapshot_lsn` dlist、`ReorderBufferGetOldestXmin` 反控 slot.xmin 的完整链路**？

全文 12 节，**30+ 张架构图 / 状态机 / 时序图**，**90+ 个源码引用**。

---

## 一、为什么 `RUNNING_XACTS` 是逻辑复制的"枢纽"

### 1.1 一条逻辑复制 SQL 走到后台，要经过 6 道关卡

```mermaid
flowchart LR
    A["INSERT INTO t VALUES (1)"] --> B["PG backend<br/>heap_insert"]
    B --> C["XLogInsert<br/>WAL: XLOG_HEAP_INSERT"]
    C --> D["WAL segment<br/>pg_wal/0000..."]
    D -->|"reorderbuffer 读"| E["ReorderBuffer 内存"]
    E -->|"SnapBuild 解码"| F["pgoutput plugin"]
    F -->|"subscriber 端 apply worker"| G["subscriber INSERT"]
    G --> H["订阅侧 heap_insert"]

    style D fill:#fee2e2,stroke:#b91c1c
    style E fill:#fef3c7,stroke:#d97706
    style F fill:#dcfce7,stroke:#15803d
    style H fill:#dbeafe,stroke:#1d4ed8
```

**6 道关卡里，`SnapBuild` 是最容易被忽略但最难调的一环**——它需要从 WAL 里**反推出"在某个时间点，哪些 xact 已经提交、哪些还在跑"**。这个反推的"原材料"就是 `xl_running_xacts` 记录。

### 1.2 没有 `RUNNING_XACTS` 的世界会怎样

```mermaid
flowchart TB
    A["无 RUNNING_XACTS"] -->|"subscriber 看到 INSERT"| B["这条 INSERT 是 xid 12345 写的"]
    B -->|"xid 12345 提交了吗？"| C["subscriber 不知道"]
    C -->|"看 CLOG？"| D["CLOG 还没有这条记录<br/>(未 commit)"]
    D -->|"等 commit"| E["死锁：subscriber 等 commit<br/>commit 永远不来<br/>(无 snapshot)"]
    style E fill:#fee2e2,stroke:#b91c1c
```

> **核心问题**：subscriber / decoder 需要一个 **catalog snapshot** 来判断"我能不能看见 tuple X"，但 PG 没有"future CLOG"——所以必须有一个"在某个 LSN 时刻，已经完成提交的所有 catalog-modifying xid 的列表"。这个列表**就是 `SnapBuild` 用 `RUNNING_XACTS` 攒出来的**。

---

## 二、`SnapshotData` 基础：xmin / xmax / xip 到底存什么

### 2.1 `SnapshotData` 数据结构

源码 `src/include/utils/snapshot.h`：

```c
typedef struct SnapshotData
{
    SnapshotType snapshot_type;   /* SNAPSHOT_MVCC / TOAST / SELF / ANY */
    TransactionId xmin;           /* 还在跑的最早 xid */
    TransactionId xmax;           /* 下一个即将分配 xid */
    TransactionId *xip;           /* [xmin, xmax) 范围内已提交 xid */
    TransactionId *subxip;        /* subxid 数组 */
    uint32        xcnt;           /* xip 数量 */
    uint32        subxcnt;        /* subxip 数量 */
    bool          suboverflowed;  /* subxid 是否溢出 */
    ...
} SnapshotData;
```

### 2.2 `xmin` / `xmax` / `xip` 的语义

```mermaid
flowchart LR
    A["xmin = 100<br/>xmax = 200"] --> B["[100, 200) 范围内"]
    B --> C["xip = [105, 110, 150]"]
    C --> D["已提交 xid"]
    B --> E["其他 xid"]
    E --> F["要么还没开始<br/>要么 abort 了"]
    style A fill:#dbeafe,stroke:#1d4ed8
    style C fill:#dcfce7,stroke:#15803d
```

**判定规则**（`heapam_visibility.c:HeapTupleSatisfiesMVCC`）：

```text
tuple_xid  ∈ [xmin, xmax):
  ├─ in xip？  → 可见（已提交）
  └─ not in xip？  → 不可见（运行中 / 中止）

tuple_xid < xmin：
  → 可见（已 commit 或 abort，事务早已结束）

tuple_xid ≥ xmax：
  → 不可见（"未来"的 xid）
```

### 2.3 `xip` 是 sparse array，不是 dense array

```c
/* xip 中的 xid 必须满足: */
/* 1. xmin <= xip[i] < xmax */
/* 2. 已经 commit / 即将被判断 */
/* 不一定连续 */
```

> **重点**：`xip` 不是"[xmin, xmax) 范围内所有 xid"，而是"其中**已 commit** 的 xid 的稀疏集合"。`HeapTupleSatisfiesMVCC` 通过 `bsearch(xip, ...)` 来 O(log n) 查找。

---

## 三、`xl_running_xacts` 数据结构：WAL 写什么

### 3.1 `xl_running_xacts` 定义

源码 `src/include/storage/standbydefs.h:47`：

```c
typedef struct xl_running_xacts
{
    int            xcnt;             /* xid 数量 */
    int            subxcnt;          /* subxid 数量 */
    bool           subxid_overflow;  /* subxid 是否溢出 */
    TransactionId  nextXid;          /* 下一个即将分配 xid */
    TransactionId  oldestRunningXid; /* 当前跑着的最早 xid */
    TransactionId  latestCompletedXid; /* 已完成的最晚 xid */
    TransactionId  xids[FLEXIBLE_ARRAY_MEMBER]; /* xcnt + subxcnt 个 xid */
} xl_running_xacts;
```

```mermaid
flowchart TB
    A["xl_running_xacts (WAL record)"] --> B["xcnt = 3<br/>subxcnt = 1"]
    A --> C["nextXid = 200"]
    A --> D["oldestRunningXid = 105"]
    A --> E["latestCompletedXid = 199"]
    A --> F["xids = [105, 110, 150, 105-1]"]

    style A fill:#dbeafe,stroke:#1d4ed8
    style C fill:#dcfce7,stroke:#15803d
    style D fill:#fce7f3,stroke:#be185d
    style F fill:#fef3c7,stroke:#d97706
```

### 3.2 `nextXid` / `oldestRunningXid` 的语义

| 字段 | 含义 |
|---|---|
| `nextXid` | TransamVariables->nextXid（未来分配的 xid） |
| `oldestRunningXid` | procArray 里最小的 xid（正在跑的最早 xid）|
| `latestCompletedXid` | 已完成的最晚 xid（用于设置 xmax） |

### 3.3 `xids` 数组的组成

```c
/* xids[0 .. xcnt-1]                    = toplevel xids */
/* xids[xcnt .. xcnt+subxcnt-1]         = subxids */
```

源码 `LogCurrentRunningXacts`：

```c
recptr = XLogInsert(RM_STANDBY_ID, XLOG_RUNNING_XACTS);
```

`xids` 数组前 `xcnt` 个元素是 toplevel running xid，后 `subxcnt` 个是 subxid。decoder 端会按这个顺序重建。

---

## 四、`LogStandbySnapshot`：谁触发 `RUNNING_XACTS` 写入

### 4.1 `LogStandbySnapshot` 触发点

源码 `src/backend/storage/ipc/standby.c:1282`：

```c
XLogRecPtr LogStandbySnapshot(void)
{
    RunningTransactions running;
    xl_standby_lock *locks;
    int nlocks;

    Assert(XLogStandbyInfoActive());

    /* 1. 取所有 AccessExclusiveLock */
    locks = GetRunningTransactionLocks(&nlocks);
    if (nlocks > 0)
        LogAccessExclusiveLocks(nlocks, locks);

    /* 2. 取所有 running xact 状态 */
    running = GetRunningTransactionData();

    /* 3. 不同 wal_level 不同处理 */
    if (wal_level < WAL_LEVEL_LOGICAL)
        LWLockRelease(ProcArrayLock);

    /* 4. 写 RUNNING_XACTS WAL */
    recptr = LogCurrentRunningXacts(running);

    /* 5. logical 模式下保留 lock 到写完 */
    if (wal_level >= WAL_LEVEL_LOGICAL)
        LWLockRelease(ProcArrayLock);

    LWLockRelease(XidGenLock);
    return recptr;
}
```

### 4.2 触发场景

`LogStandbySnapshot` 由 4 类调用方触发：

```mermaid
mindmap
  root((LogStandbySnapshot 触发点))
  Checkpointer
    每个 checkpoint
  BgWriter
    bgwriter_delay 周期
  Logical decode
    SnapBuildWaitSnapshot
    SnapBuildExportSnapshot
  Replication slot
    推进 xmin horizon
```

源码中实际调用点（`grep LogStandbySnapshot`）：

| 调用方 | 路径 | 频率 |
|---|---|---|
| **Checkpointer** | `CheckpointerMain → LogStandbySnapshot` | 每次 checkpoint（默认 5 min）|
| **BgWriter** | `BackgroundWriterMain → LogStandbySnapshot` | bgwriter_delay（默认 100 ms）|
| **SnapBuild** | `SnapBuildWaitSnapshot → LogStandbySnapshot` | 等到目标 cutoff 强制写 |
| **SnapBuildSerialize** | `SnapBuildSerialize → LogStandbySnapshot` | 进入 CONSISTENT 状态后 |
| **SnapBuildExport** | `SnapBuildExportSnapshot → LogStandbySnapshot` | 导出 snapshot 时 |

### 4.3 `wal_level` 与 lock 释放顺序

```c
if (wal_level < WAL_LEVEL_LOGICAL)
    LWLockRelease(ProcArrayLock);   /* 物理复制可立即释放 */
...
recptr = LogCurrentRunningXacts(running);
if (wal_level >= WAL_LEVEL_LOGICAL)
    LWLockRelease(ProcArrayLock);   /* logical 复制必须保留到 WAL 写完 */
```

**为什么 logical 模式要保留 `ProcArrayLock`？**

```mermaid
flowchart TB
    A["GetRunningTransactionData 返回"] -->|"physical 模式"| B["立即释放 ProcArrayLock"]
    B --> C["可能 procArray 改变<br/>clog 中有 commit"]
    C --> D["standby 通过 clog 重检"]

    A -->|"logical 模式"| E["保留 ProcArrayLock 到 WAL 写完"]
    E --> F["确保 xl_running_xacts 中的 xid 仍然有效"]
    F --> G["否则 clog 出现 “未来” commit<br/>但 decoder 看不见"]
    style F fill:#dcfce7,stroke:#15803d
```

源码注释很关键：

```c
/*
 * For logical decoding, the lock can't be released early because the clog
 * might be "in the future" from the POV of the historic snapshot. This would
 * allow for situations where we're waiting for the end of a transaction
 * listed in the xl_running_xacts record which, according to the WAL, has
 * committed before the xl_running_xacts record.
 */
```

---

## 五、`GetRunningTransactionData`：扫 ProcArray 收 running xact

### 5.1 函数入口

源码 `src/backend/storage/ipc/procarray.c:2689`：

```c
RunningTransactions GetRunningTransactionData(void)
{
    static RunningTransactionsData CurrentRunningXactsData;
    ProcArrayStruct *arrayP = procArray;
    TransactionId *other_xids = ProcGlobal->xids;
    RunningTransactions CurrentRunningXacts = &CurrentRunningXactsData;
    TransactionId latestCompletedXid;
    TransactionId oldestRunningXid;
    TransactionId oldestDatabaseRunningXid;
    TransactionId *xids;
    int index, count, subcount;
    bool suboverflowed;
    ...
}
```

### 5.2 全流程图

```mermaid
flowchart TB
    A["GetRunningTransactionData()"] --> B["malloc xids 数组<br/>(maxProcs * sizeof(TransactionId))"]
    B --> C["LWLockAcquire(ProcArrayLock, SHARED)"]
    C --> D["LWLockAcquire(XidGenLock, SHARED)"]
    D --> E["读 TransamVariables"]
    E --> F["latestCompletedXid = TransamVars->latestCompletedXid"]
    E --> G["oldestRunningXid = TransamVars->nextXid"]
    E --> H["oldestDatabaseRunningXid = same"]

    F --> I["for index in 0 .. numProcs"]
    I --> J["读 other_xids[index]"]
    J --> K{"is valid xid?"}
    K -->|"no"| I
    K -->|"yes"| L["oldestRunningXid = min(oldestRunningXid, xid)"]
    L --> M{"proc.databaseId == MyDatabaseId?"}
    M -->|"yes"| N["oldestDatabaseRunningXid = min(...)"]
    M -->|"no"| O["keep current"]
    N --> P["count++"]
    P --> Q["xids[count] = xid"]
    Q --> R["suboverflowed check"]
    R --> I

    I -->|"done"| S["sort xids"]
    S --> T["fill result struct"]
    T --> U["LWLockRelease(XidGenLock)<br/>(保留 ProcArrayLock)"]
    style U fill:#fef3c7,stroke:#d97706

    style A fill:#dbeafe,stroke:#1d4ed8
    style S fill:#dcfce7,stroke:#15803d
```

### 5.3 三种 oldestXid

```mermaid
flowchart TB
    A["三个 oldestXid"] --> B["oldestRunningXid<br/>(全集群最小)"]
    A --> C["oldestDatabaseRunningXid<br/>(当前 DB 最小)"]
    A --> D["nextXid (TransamVars)"]
    style A fill:#dbeafe,stroke:#1d4ed8
    style B fill:#dcfce7,stroke:#15803d
    style C fill:#fce7f3,stroke:#be185d
    style D fill:#fef3c7,stroke:#d97706
```

**关键代码**（procarray.c:2780+）：

```c
/* 1. 初始化 */
oldestDatabaseRunningXid = oldestRunningXid = 
    XidFromFullTransactionId(TransamVariables->nextXid);

/* 2. 扫 procArray */
for (index = 0; index < arrayP->numProcs; index++)
{
    int pgprocno = arrayP->pgprocnos[index];
    PGPROC *proc = &allProcs[pgprocno];
    TransactionId xid = UINT32_ACCESS_ONCE(other_xids[index]);
    
    if (!TransactionIdIsValid(xid))
        continue;
    
    if (TransactionIdPrecedes(xid, oldestRunningXid))
        oldestRunningXid = xid;
    
    if (proc->databaseId == MyDatabaseId &&
        TransactionIdPrecedes(xid, oldestDatabaseRunningXid))
        oldestDatabaseRunningXid = xid;
    
    /* 3. 记录 subxid 溢出 */
    if (ProcGlobal->subxidStates[index].overflowed)
        suboverflowed = true;
}
```

### 5.4 `oldestDatabaseRunningXid` 没用？

> **在 `xl_running_xacts` 里**只用 `oldestRunningXid`，**不用** `oldestDatabaseRunningXid`。后者在 `GetOldestXmin` / `ProcArrayApplyXidAssignment` 等地方使用。

### 5.5 结果填到 `xl_running_xacts`

源码 `LogCurrentRunningXacts`（standby.c:1353）：

```c
xl_running_xacts xlrec;
xlrec.xcnt = CurrRunningXacts->xcnt;
xlrec.subxcnt = CurrRunningXacts->subxcnt;
xlrec.subxid_overflow = CurrRunningXacts->suboverflowed;
xlrec.nextXid = CurrRunningXacts->nextXid;
xlrec.oldestRunningXid = CurrRunningXacts->oldestRunningXid;
xlrec.latestCompletedXid = CurrRunningXacts->latestCompletedXid;
/* 然后 memcpy xids[0..xcnt-1] + subxids */

recptr = XLogInsert(RM_STANDBY_ID, XLOG_RUNNING_XACTS);
```

---

## 六、`SnapBuild` 状态机：4 个状态怎么演

### 6.1 4 个状态

```c
typedef enum
{
    SNAPBUILD_START,              /* 起始 */
    SNAPBUILD_BUILDING_SNAPSHOT,  /* 攒 catalog snapshot */
    SNAPBUILD_FULL_SNAPSHOT,      /* 完整 catalog snapshot */
    SNAPBUILD_CONSISTENT          /* 全局一致 + 能用 */
} SnapBuildState;
```

### 6.2 状态机全景

```mermaid
stateDiagram-v2
    [*] --> START
    START --> BUILDING_SNAPSHOT : xl_running_xacts 出现
    BUILDING_SNAPSHOT --> FULL_SNAPSHOT : 旧 xact 都跑完
    FULL_SNAPSHOT --> CONSISTENT : xl_running_xacts 且无新 running
    CONSISTENT --> CONSISTENT : 持续维护
    CONSISTENT --> START : 重启 / slot 重建
```

### 6.3 `SnapBuild` 主结构

源码 `src/backend/replication/logical/snapbuild.h`：

```c
typedef struct SnapBuild
{
    SnapBuildState state;            /* 状态 */
    
    /* 重建的 snapshot */
    TransactionId xmin;              /* catalog 视角的 xmin */
    TransactionId xmax;              /* catalog 视角的 xmax */
    
    /* 已知 catalog-modifying xid */
    TransactionId *xip;              /* 动态分配 */
    int xcnt;
    int xcnt_allocated;              /* 预分配容量 */
    
    /* full snapshot 时也要记 in-progress 的 xid */
    TransactionId *subxip;
    int subxcnt;
    int subxcnt_allocated;
    
    /* catchange tracking */
    ReorderBufferTXN by_txn[...];
    ...
    
    ReorderBuffer *reorder;
    bool building_full_snapshot;
    bool in_slot_creation;
    TransactionId next_phase_at;
    XLogRecPtr start_decoding_at;
    ...
} SnapBuild;
```

---

## 七、`SnapBuildProcessRunningXacts`：snapbuild 怎么消费 RUNNING_XACTS

### 7.1 函数入口

源码 `src/backend/replication/logical/snapbuild.c:1136`：

```c
void
SnapBuildProcessRunningXacts(SnapBuild *builder, XLogRecPtr lsn,
                              xl_running_xacts *running)
{
    ReorderBufferTXN *txn;
    TransactionId xmin;

    /* 1. 还不是 CONSISTENT？尝试找 snapshot */
    if (builder->state < SNAPBUILD_CONSISTENT)
    {
        if (!SnapBuildFindSnapshot(builder, lsn, running))
            return;
    }
    else
        SnapBuildSerialize(builder, lsn);  /* 序列化当前 snapshot */

    /* 2. 更新 xmin = oldestRunningXid（重要！）*/
    builder->xmin = running->oldestRunningXid;

    /* 3. 清理不需要的 xid */
    SnapBuildPurgeOlderTxn(builder);

    /* 4. 推进 slot 的 xmin horizon（让 vacuum 回收 tuple）*/
    xmin = ReorderBufferGetOldestXmin(builder->reorder);
    if (xmin == InvalidTransactionId)
        xmin = running->oldestRunningXid;

    LogicalIncreaseXminForSlot(lsn, xmin);

    /* 5. 推进 slot 的 restart_lsn */
    ...
}
```

### 7.2 `SnapBuildFindSnapshot` 的 3 个分支

源码 `snapbuild.c:1238-1430` 是 4 个 `if/else if` 分支，对应状态机：

```mermaid
flowchart TB
    A["SnapBuildProcessRunningXacts"] --> B{"builder->state < CONSISTENT?"}
    B -->|"yes"| C["SnapBuildFindSnapshot"]
    B -->|"no"| D["SnapBuildSerialize"]

    C --> E{"oldestRunningXid < initial_xmin_horizon?"}
    E -->|"yes"| F["SnapBuildWaitSnapshot<br/>(等更老 snapshot)"]
    E -->|"no"| G{"oldestRunningXid == nextXid?"}
    G -->|"yes (空)"| H["jump to CONSISTENT"]
    G -->|"no"| I{"磁盘上有可用 snapshot?"}
    I -->|"yes"| J["SnapBuildRestore"]
    I -->|"no"| K{"state == START?"}
    K -->|"yes"| L["→ BUILDING_SNAPSHOT"]
    K -->|"no"| M{"state == BUILDING_SNAPSHOT?"}
    M -->|"yes + next_phase_at <= oldestRunningXid"| N["→ FULL_SNAPSHOT"]
    M -->|"no"| O{"state == FULL_SNAPSHOT?"}
    O -->|"yes + oldestRunningXid == nextXid"| P["→ CONSISTENT"]
    style H fill:#dcfce7,stroke:#15803d
    style L fill:#fef3c7,stroke:#d97706
    style N fill:#fce7f3,stroke:#be185d
    style P fill:#dbeafe,stroke:#1d4ed8
```

### 7.3 case a: 无 running xact（oldestRunningXid == nextXid）

```c
if (running->oldestRunningXid == running->nextXid)
{
    /* 此时没有任何 running xact */
    if (builder->start_decoding_at == InvalidXLogRecPtr ||
        builder->start_decoding_at <= lsn)
        builder->start_decoding_at = lsn + 1;

    /* xmin = xmax = nextXid */
    builder->xmin = running->nextXid;
    builder->xmax = running->nextXid;

    builder->state = SNAPBUILD_CONSISTENT;
    builder->next_phase_at = InvalidTransactionId;

    ereport(LOG, (errmsg("logical decoding found consistent point at %X/%X",
                          LSN_FORMAT_ARGS(lsn))));
    return false;
}
```

> **瞬间到 CONSISTENT**——如果系统在某个时间点完全没有 running xact，就不用 BUILDING_SNAPSHOT 阶段。

### 7.4 case c: START → BUILDING_SNAPSHOT

```c
else if (builder->state == SNAPBUILD_START)
{
    builder->state = SNAPBUILD_BUILDING_SNAPSHOT;
    builder->next_phase_at = running->nextXid;  /* 关键：记录切换点 */

    builder->xmin = running->nextXid;   /* < 都已经结束 */
    builder->xmax = running->nextXid;   /* >= 都还在跑 */

    SnapBuildWaitSnapshot(running, running->nextXid);
}
```

### 7.5 推进 xmin 后的 `xip` 处理

```c
/* xmin 更新后，需要把 xip 中比 xmin 小的 xid 删除 */
builder->xmin = running->oldestRunningXid;
SnapBuildPurgeOlderTxn(builder);
```

`SnapBuildPurgeOlderTxn` 干了什么？

```c
static void
SnapBuildPurgeOlderTxn(SnapBuild *builder)
{
    int off;
    TransactionId *newxip;
    int newxcnt = 0;
    
    /* 1. 计算新 xip 数组大小 */
    newxip = palloc(builder->xcnt * sizeof(TransactionId));
    
    /* 2. 保留 >= xmin 的 xid */
    for (off = 0; off < builder->xcnt; off++)
    {
        if (TransactionIdPrecedes(builder->xip[off], builder->xmin))
            continue;
        newxip[newxcnt++] = builder->xip[off];
    }
    
    /* 3. 替换 */
    memcpy(builder->xip, newxip, newxcnt * sizeof(TransactionId));
    builder->xcnt = newxcnt;
    pfree(newxip);
}
```

---

## 八、xip 数组的"重新定义"：catalog-modifying xid 列表

### 8.1 重要事实：`SnapBuild.xip` 不是 running xid，是**已提交的 catalog-modifying xid**

源码 `snapbuild.c:31` 的注释明确说：

```c
/*
 * In the 'xip' array we store transactions that have to be treated as
 * committed for the purpose of decoding (i.e. catalog-modifying transactions
 * that we have seen commits for).  We don't store running xacts in xip
 * because they can abort.
 */
```

```mermaid
flowchart TB
    A["SnapBuild.xip"] --> B["已 COMMIT 的 catalog-modifying xid"]
    A -->|"不是"| C["running xid (在 CLOG 可能 abort)"]
    A -->|"不是"| D["所有提交 xid (太大)"]
    style A fill:#dcfce7,stroke:#15803d
    style C fill:#fee2e2,stroke:#b91c1c
    style D fill:#fee2e2,stroke:#b91c1c
```

### 8.2 `xip` 何时被加入：`SnapBuildCommitTxn`

源码 `snapbuild.c:940`：

```c
void SnapBuildCommitTxn(SnapBuild *builder, XLogRecPtr lsn, TransactionId xid,
                        int nsubxacts, TransactionId *subxacts, uint32 xinfo)
{
    /* 1. 如果不是 catalog-modifying，跳过 */
    if (!SnapBuildXidHasCatalogChanges(builder, xid, xinfo))
        return;
    
    /* 2. 加到 committed.xip（SnapBuild 的 xip）*/
    SnapBuildAddCommittedTxn(builder, xid);
    
    /* 3. 更新 xmax = max(committed.xmax, xid) + 1 */
    if (TransactionIdFollowsOrEquals(xid, builder->xmax))
    {
        builder->xmax = xid;
        TransactionIdAdvance(builder->xmax);  /* xmax 永远 > 任何 commit xid */
    }
}
```

### 8.3 `SnapBuildAddCommittedTxn` 实现

```c
static void
SnapBuildAddCommittedTxn(SnapBuild *builder, TransactionId xid)
{
    /* 满了就 realloc */
    if (builder->xcnt == builder->xcnt_allocated)
    {
        builder->xcnt_allocated = builder->xcnt_allocated ? 
            builder->xcnt_allocated * 2 : 128;
        builder->xip = repalloc(builder->xip,
                                builder->xcnt_allocated * sizeof(TransactionId));
    }
    
    builder->xip[builder->xcnt++] = xid;
}
```

> **重要**：`SnapBuild.xip` 数组**只增不减**（除了 `SnapBuildPurgeOlderTxn` 剔除 < xmin 的）。这是为什么说"xmax > xmin"是允许的——`xip` 数组里可能有 `>= xmin` 的 xid。

### 8.4 全景图：`xip` 演化

```mermaid
sequenceDiagram
    participant W as WAL
    participant B as SnapBuild
    participant R as 序列化 snapshot

    Note over W,B: START 状态，xmin/xmax 初始化
    W->>B: xid 100 commit (catalog)
    B->>B: xip = [100], xmax = 101
    W->>B: xid 105 commit (catalog)
    B->>B: xip = [100, 105], xmax = 106
    W->>B: xid 110 commit (data only)
    Note over B: 不在 xip
    W->>B: xid 200 commit (catalog)
    B->>B: xip = [100, 105, 200], xmax = 201
    Note over B,R: xmin = oldestRunningXid (从 RUNNING_XACTS 来)
    R->>B: 序列化 snapshot
    B->>R: xmin=100, xmax=201, xip=[100, 105, 200]
```

---

## 九、`xmax` 的双轨更新：RUNNING_XACTS 之外还有 SnapBuildCommitTxn

### 9.1 `xmax` 由谁更新？

```mermaid
flowchart TB
    A["SnapBuild.xmax 更新来源"] -->|"路径 1"| B["SnapBuildCommitTxn<br/>(catalog commit 时)"]
    A -->|"路径 2"| C["SnapBuildFindSnapshot 状态机转移"]
    style A fill:#dbeafe,stroke:#1d4ed8
    style B fill:#dcfce7,stroke:#15803d
    style C fill:#fce7f3,stroke:#be185d
```

**路径 1: SnapBuildCommitTxn**（snapbuild.c:1055-1059）：

```c
if (needs_timetravel &&
    (!TransactionIdIsValid(builder->xmax) ||
     TransactionIdFollowsOrEquals(xmax, builder->xmax)))
{
    builder->xmax = xmax;
    TransactionIdAdvance(builder->xmax);
}
```

> 关键：**`xmax` 只在 catalog-modifying xact commit 时推进**，其他 commit 不会动它。

**路径 2: 状态机转移**（snapbuild.c:1301, 1405 等）：

```c
/* START → BUILDING_SNAPSHOT */
builder->xmin = running->nextXid;
builder->xmax = running->nextXid;

/* BUILDING_SNAPSHOT → FULL_SNAPSHOT */
builder->next_phase_at = running->nextXid;

/* FULL_SNAPSHOT → CONSISTENT */
... xmax 不再被重置
```

### 9.2 注释里的"奇怪"事实

源码 `snapbuild.c:1163`：

```c
/*
 * NB: We only increase xmax when a catalog modifying transaction commits
 * (see SnapBuildCommitTxn).  Because of this, xmax can be lower than
 * xmin, which looks odd but is correct and actually more efficient, since
 * we hit fast paths in heapam_visibility.c.
 */
```

```mermaid
flowchart LR
    A["xmin = 100"] --> C["xmax = 99?"]
    C -->|"看似矛盾"| D["但 fast path<br/>heapam_visibility.c 命中"]
    style A fill:#fee2e2,stroke:#b91c1c
    style C fill:#fef3c7,stroke:#d97706
    style D fill:#dcfce7,stroke:#15803d
```

> **xmax < xmin 是合法的**！这是因为 `xip` 数组里都是"已 commit 的 catalog xid"，`xmax` 只看 commit 的最新一个 catalog xid。如果中间有 data-only xid commit，`xmax` 不动。

### 9.3 `xmax` 的双轨

```mermaid
gantt
    title xmax 双轨演化
    dateFormat X
    axisFormat %s
    section 时间线
    xmax=99 (START)        :milestone, m1, 0, 1
    xmax=99 (BUILDING)     :milestone, m2, 2, 3
    xmax=99 (FULL_SNAPSHOT):milestone, m3, 5, 6
    xmax=110 (catalog commit):crit, m4, 7, 8
    xmax=110 (持久化)        :milestone, m5, 9, 10
```

---

## 十、`SnapBuildSerialize`：snapshot 持久化

### 10.1 序列化入口

源码 `snapbuild.c:1470`：

```c
static void
SnapBuildSerialize(SnapBuild *builder, XLogRecPtr lsn)
{
    Snapshot snap;
    
    /* 1. 分配 SnapshotData */
    snap = palloc0(sizeof(SnapshotData));
    snap->xmin = builder->xmin;
    snap->xmax = builder->xmax;
    snap->xcnt = builder->xcnt;
    
    /* 2. 复制 xip 数组 */
    snap->xip = palloc(builder->xcnt * sizeof(TransactionId));
    memcpy(snap->xip, builder->xip, builder->xcnt * sizeof(TransactionId));
    
    /* 3. 排序（fast path 优化）*/
    qsort(snap->xip, snap->xcnt, sizeof(TransactionId), xidComparator);
    
    /* 4. 写文件 */
    SnapBuildRestoreSnapshot(builder, snap);
}
```

### 10.2 持久化格式

```c
/* SnapBuildOnDisk */
typedef struct SnapBuildOnDisk
{
    SnapBuildOnDiskConstantSize;
    int magic;          /* 魔数 */
    TransactionId xmin;
    TransactionId xmax;
    int xcnt;
    int subxcnt;
    TransactionId xip[FLEXIBLE_ARRAY_MEMBER];
} SnapBuildOnDisk;
```

### 10.3 序列化时机

```c
void SnapBuildProcessRunningXacts(...)
{
    if (builder->state < SNAPBUILD_CONSISTENT)
        SnapBuildFindSnapshot(builder, lsn, running);
    else
        SnapBuildSerialize(builder, lsn);  /* ← CONSISTENT 状态每次 RUNNING_XACTS 都序列化 */
}
```

> **CONSISTENT 状态后，每次 RUNNING_XACTS 都会序列化**。这是为什么 `restart_lsn` 能快速回放。

---

## 十一、apply 端怎么用这个 snapshot

### 11.1 apply worker 端 decode

源码 `src/backend/replication/logical/worker.c`：

```mermaid
sequenceDiagram
    participant W as Apply Worker
    participant R as ReorderBuffer
    participant S as SnapBuild
    participant X as pgoutput

    W->>R: ReorderBufferCommit<br/>(received commit)
    R->>S: SnapBuildCommitTxn(xid)
    S->>S: xip[] += xid (if catalog)
    S->>S: xmax = max(xmax, xid+1)
    
    W->>R: ReorderBufferProcessTXN
    R->>S: build historic snapshot
    S->>S: xmin=oldestRunningXid<br/>xip=committed catalog xids
    S->>X: SnapBuildGetSnapshot → SnapshotData
    X->>X: decode tuple with snapshot
```

### 11.2 `SnapBuildGetSnapshot` 返回给 decoder

源码 `snapbuild.c:380`：

```c
Snapshot SnapBuildGetSnapshot(SnapBuild *builder)
{
    Snapshot snap = palloc(sizeof(SnapshotData));
    
    snap->xmin = builder->xmin;
    snap->xmax = builder->xmax;
    snap->xcnt = builder->xcnt;
    
    snap->xip = palloc(builder->xcnt * sizeof(TransactionId));
    memcpy(snap->xip, builder->xip, builder->xcnt * sizeof(TransactionId));
    qsort(snap->xip, snap->xcnt, sizeof(TransactionId), xidComparator);
    
    /* subxip 初始为空 */
    snap->subxip = NULL;
    snap->subxcnt = 0;
    
    return snap;
}
```

### 11.3 `GetTupleVisibility`：用 snapshot 判断 tuple 可见

源码 `decode.c:GetTupleVisibility`：

```c
XLogRecPtr GetTupleVisibility(LogicalDecodingContext *ctx, ...,
                                Snapshot *snapshot)
{
    ...
    /* 关键：systable_endscan 中要传 snapshot */
    if (RelationGetRelid(relation) == RelationRelationId)
    {
        /* pg_class */
        *snapshot = SnapBuildGetSnapshot(ctx->snapshot_builder);
    }
    else if (...)
        ...
}
```

```mermaid
flowchart LR
    A["WAL: tuple insert"] --> B["tuple xid 12345"]
    B --> C["decode: 调 visibility"]
    C --> D{"snapshot.xmin=100, xmax=200, xip=[100,105,150]"}
    D -->|"12345 in xip?"| E["catalog 变更可见"]
    D -->|"12345 not in xip"| F["不可见 (在跑)"]
    D -->|"12345 < xmin"| G["可见 (早已结束)"]
    style E fill:#dcfce7,stroke:#15803d
    style F fill:#fee2e2,stroke:#b91c1c
```

### 11.4 `RelationBuildTupleDesc` 用 snapshot 读 catalog

源码 `relcache.c:RelationBuildTupleDesc`：

```c
/* 1. 打开 pg_attribute */
attrdesc = table_open(AttributeRelationId, AccessShareLock);

/* 2. 传 snapshot（由 logical context 提供）*/
scan = systable_beginscan(attrdesc, AttributeRelidNameIndexId, true,
                          snapshot, 1, skey);

/* 3. 逐条读 */
while (HeapTupleIsValid(tup = systable_getnext(scan)))
    ...
```

**这就是 `rd_rel` 和 `rd_att` 怎么从 WAL 中"长"出来**。

---

## 十二、ReorderBuffer 视角：快照如何决定事务"能不能发送出去"

第十一节讲了 apply worker 怎么用 snapshot 解码 catalog tuple——但**在 apply worker 拿到变更之前，ReorderBuffer 这一层已经把"哪些事务可以发、哪些不能发、发的 snapshot 长啥样"全部决定了**。本节把这一段补全。

核心三问：

1. **事务的 `base_snapshot` 是怎么被挂上去的**？答：`SnapBuild → ReorderBufferSetBaseSnapshot` 在事务的"第一条变更到达"时把 `builder->snapshot` 挂到 `txn->base_snapshot`。
2. **"能不能发"的最关键判定是什么**？答：`txn->base_snapshot == NULL` 决定"这个事务从未产生过任何变更"——没变更就没东西可发，commit 时直接 `ReorderBufferCleanupTXN` 走人；有变更就以 `base_snapshot` 为模板拼出 `snapshot_now` 喂给 output plugin。
3. **所有 base_snapshot 中最老的那个**（`dlist_head`）的 `xmin` 怎么反向控制 slot 的 catalog_xmin？答：`ReorderBufferGetOldestXmin` → `LogicalIncreaseXminForSlot`，让 publisher 不去 vacuum 这部分 catalog tuple。

### 12.1 桥接点：`ReorderBufferSetBaseSnapshot` 挂载 base_snapshot

源码 `reorderbuffer.c:3310`：

```c
void
ReorderBufferSetBaseSnapshot(ReorderBuffer *rb, TransactionId xid,
                             XLogRecPtr lsn, Snapshot snap)
{
    ReorderBufferTXN *txn;
    bool        is_new;

    Assert(snap != NULL);

    /*
     * Fetch the transaction to operate on.  If we know it's a subtransaction,
     * operate on its top-level transaction instead.
     */
    txn = ReorderBufferTXNByXid(rb, xid, true, &is_new, lsn, true);
    if (rbtxn_is_known_subxact(txn))
        txn = ReorderBufferTXNByXid(rb, txn->toplevel_xid, false,
                                    NULL, InvalidXLogRecPtr, false);
    Assert(txn->base_snapshot == NULL);

    txn->base_snapshot = snap;
    txn->base_snapshot_lsn = lsn;
    dlist_push_tail(&rb->txns_by_base_snapshot_lsn, &txn->base_snapshot_node);

    AssertTXNLsnOrder(rb);
}
```

**三个关键事实**：

- `base_snapshot` 是**强引用**到 `snap`，refcount 由 `SnapBuildSnapIncRefcount` 在调用前手动加 1，事务释放时 `SnapBuildSnapDecRefcount` 减回去。
- **只在事务"第一条变更"那一次挂**——后续变更**不会**重新挂载。
- 挂载时**把这个事务插入 `txns_by_base_snapshot_lsn` dlist 尾部**——`AssertTXNLsnOrder` 强制保证 dlist 严格按 `base_snapshot_lsn` 升序，所以"最早的"事务永远在头部。

调用方有两处，源码 `snapbuild.c:676` / `snapbuild.c:1086`：

```c
/* snapbuild.c:676 — 事务的第一条变更 (HEAP_INSERT/UPDATE/DELETE/COMMIT 等) */
if (!ReorderBufferXidHasBaseSnapshot(builder->reorder, xid))
{
    if (builder->snapshot == NULL)
    {
        builder->snapshot = SnapBuildBuildSnapshot(builder);
        SnapBuildSnapIncRefcount(builder->snapshot);    /* 给 SnapBuild 自己留一份 */
    }
    SnapBuildSnapIncRefcount(builder->snapshot);        /* 给 ReorderBuffer 留一份 */
    ReorderBufferSetBaseSnapshot(builder->reorder, xid, lsn, builder->snapshot);
}
```

```mermaid
sequenceDiagram
    participant W as WAL
    participant SB as SnapBuild
    participant RB as ReorderBuffer
    participant D as dlist

    Note over SB: state = CONSISTENT<br/>builder->snapshot 已构建
    W->>SB: xid 500 的 HEAP_INSERT @ LSN 0/16ABCDE
    SB->>SB: ReorderBufferXidHasBaseSnapshot?<br/>false (没挂过)
    SB->>SB: SnapBuildSnapIncRefcount
    SB->>RB: ReorderBufferSetBaseSnapshot(500, 0/16ABCDE, snap)
    RB->>RB: txn = ReorderBufferTXNByXid(500, create=true)
    RB->>RB: txn->base_snapshot = snap
    RB->>RB: txn->base_snapshot_lsn = 0/16ABCDE
    RB->>D: dlist_push_tail(txn->base_snapshot_node)
    Note over D: 500 节点挂到 dlist 尾部
    SB-->>W: 处理完,等下一条变更
    W->>SB: xid 500 的 HEAP_UPDATE @ LSN 0/16ABCF0
    SB->>SB: ReorderBufferXidHasBaseSnapshot?<br/>true (已挂过,跳过)
    Note over RB: base_snapshot 不变
    W->>RB: xid 600 的 HEAP_INSERT @ LSN 0/16BD000
    SB->>RB: ReorderBufferSetBaseSnapshot(600, 0x16BD000, snap')
    RB->>D: 600 节点挂到 500 之后
```

### 12.2 base_snapshot 是"事务第一条变更到达那一刻"的 catalog 视图

为什么是"第一条变更"那个 LSN？**因为 output plugin 在解码 tuple 时要做 catalog lookup，而 catalog 在 `xmin`/`xmax` 之间是稳定的**。事务的 N 条变更 LSN 全部落在 `xmin ≤ LSN_i < xmax` 这个区间里，**任何一个 LSN 看到的 catalog 都一样**——所以挂哪个 LSN 都行，但选最早最自然。

源码 `SnapBuildBuildSnapshot`（snapbuild.c:360-432）在 `ReorderBufferSetBaseSnapshot` 之前被调过一次，把 `builder->xmin / xmax / xip` 打包成 `SnapshotData`：

```c
snapshot->xmin = builder->xmin;
snapshot->xmax = builder->xmax;
snapshot->xip  = ... (从 builder->xip 拷贝);
```

随后这个 `SnapshotData` 跟着事务走完一生——**直到事务 commit/abort 才被 free**。

```mermaid
flowchart LR
    A["WAL 流入"] --> B["xid 500 HEAP_INSERT @ 0/16A"]
    B --> C["base_snapshot 挂载<br/>lsn=0/16A"]
    C --> D["xid 500 累积变更:<br/>HEAP_UPDATE @ 0/17A<br/>HEAP_UPDATE @ 0/18A"]
    D --> E["xid 500 COMMIT @ 0/19A"]
    E --> F["ReorderBufferReplay<br/>snapshot_now = base_snapshot 拷贝<br/>(+subxact → subxip[])"]
    F --> G["output plugin<br/>用 snapshot_now 解码所有变更"]
    G --> H["pgoutput BEGIN/INSERT/UPDATE/COMMIT"]
    H --> I["SnapBuildSnapDecRefcount<br/>dlist 移除 500 节点"]
    style C fill:#fef3c7,stroke:#d97706
    style F fill:#dcfce7,stroke:#15803d
    style I fill:#dbeafe,stroke:#1d4ed8
```

### 12.3 `txn->base_snapshot == NULL`：决定"能不能发"的最关键判定

**发送路径** `reorderbuffer.c:2848`：

```c
if (txn->base_snapshot == NULL)
{
    Assert(txn->ninvalidations == 0);
    /* 事务从未产生变更,nothing to decode */
    if (!rbtxn_is_prepared(txn))
        ReorderBufferCleanupTXN(rb, txn);
    return;
}

snapshot_now = ReorderBufferCopySnap(rb, txn->base_snapshot, txn, command_id);
ReorderBufferProcessTXN(rb, txn, commit_lsn, snapshot_now, command_id, false);
```

**这个 `if` 就是"事务能不能发送"的全部判定**：

- `base_snapshot == NULL` → **不发送**，直接清理掉。
- `base_snapshot != NULL` → **发送**，以 `base_snapshot` 为模板构造 `snapshot_now`。

什么时候 `base_snapshot` 是 NULL？**只有"事务只做了 BEGIN + COMMIT / ROLLBACK，没动任何表"的情况**——比如一个只 `SELECT` 的事务，或者一个只设 GUC 的事务。`SnapBuildChange` 这条 hook 只在变更类 WAL（`HEAP_INSERT/UPDATE/DELETE`、`XLOG_HEAP2_NEW_CID` 等）到来时触发，所以纯只读事务不会走到 `ReorderBufferSetBaseSnapshot`。

> **为什么"纯只读事务不需要发送"**？因为 output plugin 拿到它也没东西可发——`pgoutput` 的 `commit` 回调收到一个空事务，连 `BEGIN` 都省了（`stream_start` 的 `nmsgs == 0`）。让空事务走完全链路只浪费 CPU/内存。

### 12.4 `txns_by_base_snapshot_lsn` dlist：所有 base_snapshot 的"xmin horizon"

源码 `reorderbuffer.h`：

```c
struct ReorderBuffer
{
    ...
    dlist_head    txns_by_base_snapshot_lsn;  /* 按 base_snapshot_lsn 升序 */
    ...
};
```

**关键性质**：

- 严格按 `base_snapshot_lsn` 升序——`ReorderBufferSetBaseSnapshot` 用 `dlist_push_tail`，加上 `AssertTXNLsnOrder` 强约束。
- dlist **只在事务 commit / abort / spill-out 时移除节点**——**事务活着期间，base_snapshot 一直被它持有**。
- dlist 头节点 = `base_snapshot_lsn` 最小的事务 = "最早开始做变更"的事务。

```mermaid
flowchart LR
    subgraph LIST["txns_by_base_snapshot_lsn (升序)"]
        N1["txn 500<br/>lsn=0x16A<br/>xmin=400<br/>(仍 in-progress)"] --> N2["txn 600<br/>lsn=0x16B<br/>xmin=410<br/>(已 commit)"] --> N3["txn 700<br/>lsn=0x16C<br/>xmin=420<br/>(仍 in-progress)"]
    end
    N1 -.->|"oldest"| HEAD["dlist_head"]
    HEAD --> XMIN["slot.catalog_xmin = 400"]
    style HEAD fill:#fef3c7,stroke:#d97706
    style XMIN fill:#dcfce7,stroke:#15803d
```

**为什么用 dlist 而不是最小堆**？因为 dlist 节点的进入/退出是 `O(1)`，且事务活跃期通常很短（ms 级），dlist 的 `O(n)` 遍历只在 `ReorderBufferGetOldestXmin` 时发生（每次 `SnapBuildProcessRunningXacts` 调一次），完全可以接受。

### 12.5 `ReorderBufferGetOldestXmin`：从 dlist 头取 xmin，反控 slot.catalog_xmin

源码 `reorderbuffer.c:1077`：

```c
TransactionId
ReorderBufferGetOldestXmin(ReorderBuffer *rb)
{
    ReorderBufferTXN *txn;

    AssertTXNLsnOrder(rb);

    if (dlist_is_empty(&rb->txns_by_base_snapshot_lsn))
        return InvalidTransactionId;

    txn = dlist_head_element(ReorderBufferTXN, base_snapshot_node,
                             &rb->txns_by_base_snapshot_lsn);
    return txn->base_snapshot->xmin;
}
```

调用方 `SnapBuildProcessRunningXacts`（snapbuild.c:1136，第七节）：

```c
xmin = ReorderBufferGetOldestXmin(builder->reorder);
if (xmin == InvalidTransactionId)
    xmin = running->oldestRunningXid;

LogicalIncreaseXminForSlot(lsn, xmin);
```

**完整链路**：

```mermaid
flowchart TB
    A["WAL: xlog_running_xacts"] --> B["SnapBuildProcessRunningXacts"]
    B --> C["xmin = ReorderBufferGetOldestXmin"]
    C --> D{"dlist 为空?"}
    D -->|"yes"| E["xmin = running->oldestRunningXid"]
    D -->|"no"| F["xmin = dlist_head->base_snapshot->xmin"]
    E --> G["LogicalIncreaseXminForSlot(lsn, xmin)"]
    F --> G
    G --> H["slot.data.catalog_xmin = xmin"]
    H --> I["ReplicationSlotsComputeRequiredXmin"]
    I --> J["ProcArray.replication_slot_xmin = max(all slots)"]
    J --> K["autovacuum 跳过 catalog tuple<br/>(xmin 之前的旧版本)"]
    style F fill:#dcfce7,stroke:#15803d
    style K fill:#fae8ff,stroke:#a21caf
```

> **为什么用 dlist 头的 xmin 而不是 `running->oldestRunningXid`**？因为 dlist 头可能是 "lsn 0x16A 的 txn 500"，但 `running` 记录里 `oldestRunningXid` 可能是 "lsn 0x300 的 txn 50"——**`running` 反映 publisher 当前活跃的 xid，而 dlist 反映 ReorderBuffer 实际"挂着 base_snapshot 还没发完"的事务**。两者谁更老用谁，dlist 通常更老（因为 dlist 上的事务可能已经 commit 但还在 PG_OUTPUT 阶段）。这就是为什么 long-running 事务会卡 slot。

### 12.6 `ReorderBufferCopySnap`：把 base_snapshot + subxact 拼成 snapshot_now

事务 commit 时，**output plugin 拿到的不是 `base_snapshot`，而是一个 "私有拷贝 + 事务自己的 subxact 拼到 subxip[]" 的版本**。源码 `reorderbuffer.c:1908`：

```c
static Snapshot
ReorderBufferCopySnap(ReorderBuffer *rb, Snapshot orig_snap,
                      ReorderBufferTXN *txn, CommandId cid)
{
    Snapshot snap;
    dlist_iter iter;
    int i = 0;
    Size size;

    /* 1. 申请 SnapshotData + xip[] + subxip[] 一整块 */
    size = sizeof(SnapshotData) +
           sizeof(TransactionId) * orig_snap->xcnt +
           sizeof(TransactionId) * (txn->nsubtxns + 1);

    snap = MemoryContextAllocZero(rb->context, size);
    memcpy(snap, orig_snap, sizeof(SnapshotData));

    snap->copied = true;
    snap->active_count = 1;       /* 标记 active,禁止别人 free */
    snap->regd_count = 0;
    snap->xip = (TransactionId *) (snap + 1);  /* 紧跟在 SnapshotData 后面 */

    /* 2. 把 base_snapshot.xip[] 拷过来 */
    memcpy(snap->xip, orig_snap->xip, sizeof(TransactionId) * snap->xcnt);

    /* 3. 关键：把本事务的 toplevel xid + 所有 subxact 塞到 subxip[] */
    snap->subxip = snap->xip + snap->xcnt;
    snap->subxip[i++] = txn->xid;            /* toplevel */
    snap->subxcnt = 1;

    /* 4. 遍历 subxact 链表,塞进 subxip[] */
    dlist_foreach(iter, &txn->subtxns)
    {
        ReorderBufferTXN *sub_txn = dlist_container(ReorderBufferTXN, node, iter.cur);
        snap->subxip[i++] = sub_txn->xid;
        snap->subxcnt++;
    }
    qsort(snap->subxip, snap->subxcnt, sizeof(TransactionId), xidComparator);

    snap->curcid = cid;
    return snap;
}
```

**两个语义变化**：

- `xip[]`：从 `base_snapshot` 原样拷贝（"哪些 catalog-modifying xid 已 commit"），**不变**。
- `subxip[]`：**新增**——"**本事务自己的所有 xid（toplevel + subxact）**"。这样 `HeapTupleSatisfiesMVCC` 在 `subxip` 命中（=本事务自己写的）时按 `curcid` 决定可见/不可见，避开 cmin/cmax 跨事务比较的坑。

```mermaid
flowchart TB
    A["base_snapshot<br/>xmin=400, xmax=500, xip=[420, 450, 480]"]
    A --> B["ReorderBufferCopySnap"]
    B --> C["snapshot_now<br/>xmin=400, xmax=500<br/>xip=[420, 450, 480]<br/>subxip=[500, 501]<br/>(本事务 toplevel=500, subxact=501)<br/>curcid=FirstCommandId"]
    C --> D["output plugin<br/>(pgoutput)"]
    D --> E["解码 tuple 时:<br/>HeapTupleSatisfiesMVCC(snap, tuple)<br/>tuple.xid == 500 → subxip 命中 → 看 curcid"]
    style A fill:#fef3c7,stroke:#d97706
    style C fill:#dcfce7,stroke:#15803d
    style E fill:#fae8ff,stroke:#a21caf
```

> **为什么必须 subxip[]**？因为本事务自己写的 tuple 用 cmin/cmax 来标识可见性，而 base_snapshot 来自另一个 LSN 那一刻，**base_snapshot 里没有本事务的 cmin/cmax 信息**。所以把本事务 xid 单独塞到 subxip，让 `HeapTupleSatisfiesMVCC` 走"自己事务 → 看 curcid"路径。

### 12.7 `ReorderBufferProcessTXN` 的 4 个入口分支

`ReorderBufferProcessTXN(rb, txn, ...)`（reorderbuffer.c:2210）是事务变更的"实际发送"函数。它有 3 个调用方：

```mermaid
flowchart TB
    A1["ReorderBufferReplay<br/>(非 stream)"] --> P1["ReorderBufferProcessTXN<br/>commit_lsn=commit, stream=false"]
    A2["ReorderBufferStreamTXN<br/>(streaming)"] --> P2["ReorderBufferProcessTXN<br/>commit_lsn=Invalid, stream=true"]
    A3["ReorderBufferStreamCommit<br/>(stream + commit)"] --> P3["ReorderBufferProcessTXN<br/>commit_lsn=Invalid, stream=true"]
    P1 --> P4["stream_finalize? = false<br/>is_commit=true"]
    P2 --> P4
    P3 --> P4
    style A1 fill:#dcfce7,stroke:#15803d
    style A2 fill:#fef3c7,stroke:#d97706
    style A3 fill:#fae8ff,stroke:#a21caf
```

**3 个入口的本质差异**：

| 入口 | 何时调 | snapshot 来源 | 是否 stream |
| --- | --- | --- | --- |
| `ReorderBufferReplay` | 非 stream 模式事务 commit | `txn->base_snapshot` 拷贝 | false |
| `ReorderBufferStreamTXN` | streaming 模式，每批变更后 | 首次 `base_snapshot` 拷贝 / 后续 `txn->snapshot_now` 复用 | true |
| `ReorderBufferStreamCommit` | streaming 模式 commit 时 | `txn->snapshot_now` 复用 | true |

### 12.8 streaming 模式：txn->snapshot_now 的复用与刷新

streaming 模式（`reorderbuffer.c:4350+`）下，事务不会等 commit 才发，而是**按 `reorderbuffer.c:stream_changes` 阈值分批发**。**关键**：每批发的 snapshot 不能重新构造，而是**复用上一批的 `txn->snapshot_now`**，仅在"出现了新 subxact"时调 `ReorderBufferCopySnap` 增量更新。

源码 `reorderbuffer.c:4350`：

```c
if (!rbtxn_is_streamed(txn))
{
    /* 1. 第一批 / 非 stream 模式:从 base_snapshot 开始 */
    if (txn->base_snapshot == NULL)
    {
        Assert(txn->ninvalidations == 0);
        return;
    }
    command_id = FirstCommandId;
    snapshot_now = ReorderBufferCopySnap(rb, txn->base_snapshot,
                                         txn, command_id);
}
else
{
    /* 2. 后续批:复用上一批的 snapshot_now */
    Assert(rbtxn_is_streamed(txn));

    /* 必须重新 copy,因为可能新增了 subxact */
    command_id = txn->command_id;
    snapshot_now = ReorderBufferCopySnap(rb, txn->snapshot_now,
                                         txn, command_id);

    /* 释放上一批的 snapshot */
    Assert(txn->snapshot_now->copied);
    ReorderBufferFreeSnap(rb, txn->snapshot_now);
    txn->snapshot_now = NULL;
}
```

**为什么必须 `ReorderBufferCopySnap` 而不能直接复用 `txn->snapshot_now`**？因为 `txn->subxns` 可能在两批之间新增了 subxact——`subxip[]` 必须包含最新的 subxact 集合。所以**复用 base_snapshot 的内容 + 重新遍历 `txn->subxns` 拼出新的 subxip**。

```mermaid
sequenceDiagram
    participant W as WAL
    participant RB as ReorderBuffer
    participant OP as output plugin

    W->>RB: xid 500 HEAP_INSERT (subxact 501 begin)
    RB->>RB: base_snapshot 挂载
    Note over RB: 第 1 批触发 (达到 stream_changes 阈值)
    RB->>RB: snapshot_now = CopySnap(base_snapshot, subxip=[500, 501])
    RB->>OP: stream_change
    RB->>RB: txn->snapshot_now = snapshot_now (保留)
    W->>RB: xid 500 HEAP_UPDATE
    W->>RB: xid 502 HEAP_INSERT (subxact 502 begin)
    Note over RB: 第 2 批触发
    RB->>RB: snapshot_now = CopySnap(txn->snapshot_now, subxip=[500, 501, 502])
    RB->>RB: ReorderBufferFreeSnap(txn->snapshot_now) (释放旧的)
    RB->>RB: txn->snapshot_now = snapshot_now (新的)
    RB->>OP: stream_change
    W->>RB: xid 500 COMMIT
    RB->>RB: snapshot_now = CopySnap(txn->snapshot_now, ...) (commit 阶段)
    RB->>OP: stream_commit
    RB->>RB: 释放 snapshot_now, dlist 移除
```

> **坑**：streaming 模式下 `txn->snapshot_now` 的生命周期横跨"事务 commit 之前"——如果此时 `reorderbuffer.c:ReorderBufferResetTXN` 触发 streaming 中止重置，`txn->snapshot_now` 也会被释放（`ReorderBufferFreeSnap`），下一批必须重新从 `base_snapshot` 拷贝。

### 12.9 abort 路径：只清变更，不动 snapshot 太久

`ReorderBufferAbort`（reorderbuffer.c:1825 起）不会走 `ReorderBufferReplay`——它只做两件事：

```c
txn->txn_flags |= RBTXN_IS_ABORTED;
...
ReorderBufferCleanupTXN(rb, txn);
```

`ReorderBufferCleanupTXN`（reorderbuffer.c:1594+）会：

- 把 txn 从 `txns_by_base_snapshot_lsn` dlist 移除。
- `SnapBuildSnapDecRefcount(txn->base_snapshot)` 减 refcount。
- `pfree(txn->base_snapshot)` / `pfree(txn->snapshot_now)`（如果 streaming 模式）。
- `dlist_delete(&txn->node)` 移出 `toplevel_by_lsn`。

**abort 不发**——这是为什么 `base_snapshot` 的判定只在 commit 路径做：abort 路径上无论 `base_snapshot` 是不是 NULL，都会 `CleanupTXN`，没有 "发" 的可能。

### 12.10 完整时序：commit 路径下的 snapshot 全生命周期

把第十二节所有内容串成一张图：

```mermaid
sequenceDiagram
    participant W as WAL
    participant SB as SnapBuild
    participant RB as ReorderBuffer
    participant D as txns_by_base_snapshot_lsn
    participant OP as output plugin

    Note over SB: 状态 CONSISTENT, builder->snapshot 已就绪
    W->>SB: xid 500 HEAP_INSERT @ LSN 0x16A
    SB->>SB: SnapBuildSnapIncRefcount
    SB->>RB: ReorderBufferSetBaseSnapshot(500, 0x16A, snap)
    RB->>RB: txn->base_snapshot = snap
    RB->>D: dlist_push_tail
    W->>RB: xid 500 HEAP_UPDATE
    Note over RB: base_snapshot 不变, 继续累积变更

    W->>SB: xlog_running_xacts @ LSN 0x16B
    SB->>RB: SnapBuildProcessRunningXacts
    RB->>D: 取 dlist_head (xid 500)
    RB->>RB: xmin = dlist_head->base_snapshot->xmin
    RB->>SB: LogicalIncreaseXminForSlot(0x16B, xmin)

    W->>RB: xid 500 COMMIT
    RB->>RB: ReorderBufferCommit
    RB->>RB: ReorderBufferReplay
    alt base_snapshot == NULL
        RB->>RB: ReorderBufferCleanupTXN (不发)
    else base_snapshot != NULL
        RB->>RB: snapshot_now = CopySnap(base_snapshot, subxip)
        RB->>OP: ReorderBufferProcessTXN (BEGIN + INSERT + UPDATE + COMMIT)
        OP-->>RB: callback 返回
        RB->>RB: ReorderBufferFreeSnap(snapshot_now)
        RB->>D: dlist_delete (移除 500 节点)
        RB->>SB: SnapBuildSnapDecRefcount
    end
```

### 12.11 总结：`base_snapshot` 的三个作用

```mermaid
mindmap
  root((txn->base_snapshot))
    作用1
      "判定能不能发"
        base_snapshot == NULL
        → 不发
    作用2
      "发送时的 catalog 视图"
        snapshot_now = CopySnap + subxip
        output plugin 用它解码
    作用3
      "反控 slot.catalog_xmin"
        dlist_head->base_snapshot->xmin
        → publisher 不 vacuum
```

---

## 十三、5 个最常见坑 + 排查

### 13.1 坑 1: `restart_lsn` 长时间不动

```sql
-- 现象
SELECT slot_name, restart_lsn, confirmed_flush_lsn 
FROM pg_replication_slots;

-- slot_name | restart_lsn | confirmed_flush_lsn
-- s1        | 0/1A4D0000 | 0/1A4D0000
-- restart_lsn 一直不动
```

**原因**：`SnapBuildFindSnapshot` 卡在 `oldestRunningXid` 上。可能是：

- 旧 xact 没 commit（应用层长事务）
- 旧 xact 已 commit 但 commit 记录没被 decoder 看到（reorderbuffer spill）
- `wal_level = replica` 而不是 `logical`

**排查**：

```sql
-- 找长 xact
SELECT pid, age(now(), xact_start), query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY xact_start LIMIT 5;
```

### 13.2 坑 2: xmax < xmin 导致 decode 失败

**现象**：

```text
ERROR: snapshot xmin 100 > xmax 99
```

**原因**：状态机转移时，`xmin = running->nextXid`，`xmax = running->nextXid`，`xmax` 暂时落后于 `xmin`。后续 commit 推进 `xmax`。

**修复**：等 commit 推进 `xmax`。

### 13.3 坑 3: 磁盘上 `snapbuild` 文件被锁

```sql
ERROR: could not open file "pg_replslot/s1/snapbuild": Resource busy
```

**原因**：另一个 worker 在用 slot。

### 13.4 坑 4: `committed.includes_all_transactions = false`

源码里 `builder->committed.includes_all_transactions` 在 `!needs_timetravel` 时设为 `false`：

```c
if (!needs_timetravel)
    builder->committed.includes_all_transactions = false;
```

**含义**：如果某个 xact 不是 catalog-modifying，**不会被记录在 xip**，所以导出的 snapshot 不能用于 export（pg_export_snapshot）。

### 13.5 坑 5: `subxid_overflow`

源码里 `subxid_overflow=true` 时，subxid 数组可能丢失：

```c
typedef struct xl_running_xacts {
    ...
    bool subxid_overflow;  /* subxids 丢失了 */
    ...
} xl_running_xacts;
```

**后果**：snapshot 不准，可能 decode 漏。**修复**：扩大 `subxid` cache（调 PG `PROC_MAX_CACHED_SUBXIDS`）。

---

## 十四、源码引用索引

**xl_running_xacts 定义**：
- `src/include/storage/standbydefs.h:47` — `xl_running_xacts` struct
- `src/include/storage/standbydefs.h:39` — `xl_standby_lock`

**LogStandbySnapshot**：
- `src/backend/storage/ipc/standby.c:1282` — `LogStandbySnapshot`
- `src/backend/storage/ipc/standby.c:1353` — `LogCurrentRunningXacts`
- `src/backend/storage/ipc/standby.c:1455` — `LogAccessExclusiveLocks`
- `src/backend/storage/ipc/procarray.c:2689` — `GetRunningTransactionData`
- `src/backend/storage/ipc/procarray.c:2658` — `GetOldestXmin` (相关)
- `src/backend/storage/ipc/procarray.c:1547` — `GetRunningTransactionLocks`

**SnapBuild 主逻辑**：
- `src/backend/replication/logical/snapbuild.c:1136` — `SnapBuildProcessRunningXacts`
- `src/backend/replication/logical/snapbuild.c:1238` — `SnapBuildFindSnapshot`
- `src/backend/replication/logical/snapbuild.c:1435` — `SnapBuildWaitSnapshot`
- `src/backend/replication/logical/snapbuild.c:940` — `SnapBuildCommitTxn`
- `src/backend/replication/logical/snapbuild.c:1470` — `SnapBuildSerialize`
- `src/backend/replication/logical/snapbuild.c:380` — `SnapBuildGetSnapshot`
- `src/backend/replication/logical/snapbuild.c:282` — `SnapBuildRestore`
- `src/backend/replication/logical/snapbuild.c:177` — `SnapBuildAddCommittedTxn`
- `src/backend/replication/logical/snapbuild.c:267` — `SnapBuildPurgeOlderTxn`

**Snapshot 内部**：
- `src/include/utils/snapshot.h` — `SnapshotData`
- `src/backend/utils/time/snapmgr.c` — snapshot manager
- `src/backend/access/heap/heapam_visibility.c` — `HeapTupleSatisfiesMVCC`

**ReorderBuffer 视角**（第十二节新增）：
- `src/backend/replication/logical/reorderbuffer.c:1077` — `ReorderBufferGetOldestXmin`（dlist 头取 xmin）
- `src/backend/replication/logical/reorderbuffer.c:1082` — `txn->base_snapshot->xmin` 取值
- `src/backend/replication/logical/reorderbuffer.c:1908` — `ReorderBufferCopySnap`（base_snapshot + subxact 拼 snapshot_now）
- `src/backend/replication/logical/reorderbuffer.c:2813` — `ReorderBufferReplay`（commit 路径入口）
- `src/backend/replication/logical/reorderbuffer.c:2848` — `txn->base_snapshot == NULL` 判定
- `src/backend/replication/logical/reorderbuffer.c:3310` — `ReorderBufferSetBaseSnapshot`（挂 base_snapshot 到 txn）
- `src/backend/replication/logical/reorderbuffer.c:4350` — streaming 模式 snapshot_now 复用与刷新
- `src/backend/replication/logical/snapbuild.c:676` — `SnapBuildChange` 内首次挂 base_snapshot
- `src/backend/replication/logical/snapbuild.c:1086` — `SnapBuildProcessNewCid` 内挂 base_snapshot

**apply 端**：
- `src/backend/replication/logical/worker.c` — apply worker
- `src/backend/replication/logical/decode.c` — `GetTupleVisibility`
- `src/backend/replication/logical/relation.c` — relation map
- `src/backend/utils/cache/relcache.c:RelationBuildTupleDesc` — 用 snapshot 读 catalog

---

## 十五、总结：7 个核心心智模型

```mermaid
flowchart TB
    A["1. RUNNING_XACTS 是逻辑复制的枢纽<br/>(snapshot of snapshots)"]
    B["2. xip 是 catalog xid 不是 running xid"]
    C["3. xmax 只能被 catalog commit 推进"]
    D["4. xmax 可以小于 xmin (合法)"]
    E["5. 状态机 4 步: START → BUILDING → FULL → CONSISTENT"]
    F["6. CONSISTENT 之后每次 RUNNING_XACTS 都序列化"]
    G["7. txn->base_snapshot 是 ReorderBuffer 视角的"事务能否发送"开关<br/>(NULL → 不发;非 NULL → 以 base_snapshot 为模板拼 snapshot_now)"]

    A --> B --> C --> D --> E --> F --> G
    style A fill:#dbeafe,stroke:#1d4ed8
    style B fill:#dcfce7,stroke:#15803d
    style C fill:#fce7f3,stroke:#be185d
    style D fill:#fef3c7,stroke:#d97706
    style E fill:#fae8ff,stroke:#a21caf
    style F fill:#fee2e2,stroke:#b91c1c
    style G fill:#dbeafe,stroke:#1d4ed8
```

### 15.1 7 个心智模型详解

| # | 原则 | 实际体现 |
|---|---|---|
| 1 | **RUNNING_XACTS 是"快照的快照"** | 写 WAL 才能在 decoder 重放 |
| 2 | **`xip` 是 catalog-modifying xid 列表** | 不在 `xip` 里的 xid = 不可见 |
| 3 | **`xmax` 只被 catalog commit 推进** | data-only commit 不会动 xmax |
| 4 | **`xmax < xmin` 是合法的** | 状态机初始化期间可出现 |
| 5 | **状态机 4 步** | `START → BUILDING_SNAPSHOT → FULL_SNAPSHOT → CONSISTENT` |
| 6 | **CONSISTENT 后持续序列化** | `restart_lsn` 才能快速回放 |
| 7 | **`txn->base_snapshot == NULL` 决定 ReorderBuffer 是否发送事务** | 没变更 → 不发;有变更 → `ReorderBufferCopySnap` 拼 `snapshot_now`;dlist 头 `base_snapshot->xmin` 反控 `slot.catalog_xmin` |

### 15.2 一图总览：`xl_running_xacts` → `SnapBuild` → snapshot

```mermaid
flowchart TB
    A["LogStandbySnapshot"] -->|"GetRunningTransactionData"| B["xl_running_xacts WAL"]
    B -->|"SnapBuildProcessRunningXacts"| C{"state < CONSISTENT?"}
    C -->|"yes"| D["SnapBuildFindSnapshot<br/>4 状态转移"]
    C -->|"no"| E["SnapBuildSerialize<br/>持久化 snapshot"]

    D --> F["builder->xmin = oldestRunningXid"]
    D --> G["builder->xmax = running->nextXid (init)"]
    D --> H["builder->xip = catalog committed xid (in SnapBuildCommitTxn)"]

    E --> I["写 pg_replslot/s1/snapbuild"]

    F --> J["SnapBuildGetSnapshot"]
    G --> J
    H --> J
    I --> J
    J --> K["apply worker<br/>HeapTupleSatisfiesMVCC"]
    style B fill:#fee2e2,stroke:#b91c1c
    style J fill:#dcfce7,stroke:#15803d
    style K fill:#fae8ff,stroke:#a21caf
```

### 15.3 apply worker 端时序图

```mermaid
sequenceDiagram
    participant P as Primary
    participant W as WAL
    participant D as Decoder (subscriber)
    participant SB as SnapBuild
    participant A as Apply Worker

    P->>W: xid 100 commit (catalog)
    W->>D: 收到 XLOG_XACT_COMMIT
    D->>SB: SnapBuildCommitTxn(xid=100)
    SB->>SB: xip[] += 100
    SB->>SB: xmax = 101
    Note over SB: 此刻 xmin=90, xmax=101, xip=[100]

    P->>W: 后台写 RUNNING_XACTS
    W->>D: 收到 XLOG_RUNNING_XACTS
    D->>SB: SnapBuildProcessRunningXacts
    SB->>SB: xmin = oldestRunningXid
    SB->>SB: SnapBuildSerialize

    Note over D,A: 一条 catalog tuple WAL 记录到
    D->>SB: SnapBuildGetSnapshot
    SB->>D: Snapshot{xmin=90, xmax=101, xip=[100]}
    D->>D: HeapTupleSatisfiesMVCC(tuple, snapshot)
    D->>A: pgoutput INSERT
    A->>A: subscriber INSERT
```

## 同系列前文

- [PostgreSQL MVCC：从一行 UPDATE 到 5 个 HeapTuple 的演化](./postgresql-mvcc/index.html)
- [PostgreSQL 事务生命周期：从 BEGIN/COMMIT 到 CLOG 一条链路](./postgresql-transaction-lifecycle/index.html)
- [PostgreSQL 逻辑复制表的生命周期：从 `pg_replication_slots` 到 `pg_subscription_rel`](./postgresql-logical-replication-tables-lifecycle/index.html)
- [PostgreSQL 逻辑复制 spill 深度拆解：ReorderBuffer 如何把 100GB 事务拆成小块](./postgresql-logical-replication-spill-deep-dive/index.html)
- [PostgreSQL 逻辑复制的 ReorderBuffer 与事务机制](./postgresql-logical-replication-reorderbuffer-transaction/index.html)
> - [PostgreSQL 逻辑复制全链路：以一个真实事务为例，从 `INSERT` 到 `apply` 的源码级旅程](./postgresql-logical-replication-end-to-end-flow/index.html)
- [PostgreSQL 元数据存储机制](./postgresql-catalog-storage/index.html)
