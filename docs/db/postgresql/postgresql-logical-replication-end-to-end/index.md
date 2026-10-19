---
title: PostgreSQL 逻辑复制端到端深度拆解:从 WAL 字节到订阅者 apply 的全链路源码分析
date: 2026-10-19
author: growdu
categories:
  - 数据库
  - PostgreSQL
  - 源码分析
  - 逻辑复制
tags:
  - PostgreSQL
  - 逻辑复制
  - Logical Decoding
  - snapbuild
  - reorderbuffer
  - pgoutput
  - WAL
  - walsender
  - MVCC
  - 源码分析
---

# PostgreSQL 逻辑复制端到端深度拆解:从 WAL 字节到订阅者 apply 的全链路源码分析

> 配套源码:`~/cwork/postgresql/src/backend/replication/`(PG 18 主干,30+ 文件、30K+ 行)
>
> 读完本文你会理解:
> 1. **逻辑复制的整体数据流**:`WAL 字节 → walsender → reorder buffer → output plugin → 订阅者`
> 2. **`snapbuild` 4 态状态机** 的具体 WAL 推进过程(以具体日志为例)
> 3. **每种 WAL rmgr** 在逻辑解码中的处理路径(`heap` / `heap2` / `xact` / `standby` / `xlog` / `logicalmsg`)
> 4. **reorder buffer** 的核心抽象:`ReorderBufferTXN` / `ReorderBufferChange` / `base snapshot` 注入
> 5. **完整例子**:`INSERT 1 行 → 提交` 经历的 7 个函数调用链
> 6. **用户/DBA/内核开发者** 三个视角下的观察点
> 7. **PG 18 重要特性**:streaming、parallel apply、two-phase decoding 源码入口

---

## 目录

- [一、整体架构:6 层流水线](#一整体架构6-层流水线)
- [二、状态机原理:snapbuild 的 4 态推进](#二状态机原理snapbuild-的-4-态推进)
- [三、WAL 记录处理矩阵:每种 rmgr 的解码路径](#三wal-记录处理矩阵每种-rmgr-的解码路径)
- [四、reorder buffer 核心抽象](#四reorder-buffer-核心抽象)
- [五、完整启动到稳态流程(具体日志举例)](#五完整启动到稳态流程具体日志举例)
- [六、完整事务生命周期(具体例子)](#六完整事务生命周期具体例子)
- [七、用户 / DBA / 内核开发者 三个视角](#七用户--dba--内核开发者-三个视角)
- [八、PG 18 重要特性源码入口](#八pg-18-重要特性源码入口)
- [九、源码速查表](#九源码速查表)
- [十、参考](#十参考)

---

## 一、整体架构:6 层流水线

逻辑复制的本质是:**把 publisher 的 WAL 字节流,通过一系列"翻译",变成订阅者能直接 apply 的 SQL 操作流**。翻译过程涉及 6 层协作。

### 1.1 端到端架构图

```mermaid
flowchart TB
    subgraph P["Publisher 侧"]
        WAL[(WAL 文件<br/>pg_wal/)]
        BG["bgwriter / checkpointer<br/>生成 running_xacts"]
        WTX["写入事务<br/>Heap/Heap2/Xact/Btree..."]
    end

    subgraph WALREADER["1. WAL Reader 层"]
        XR["XLogReaderAllocate<br/>XLogReadRecord<br/>(walsender.c)"]
    end

    subgraph DECODE["2. Decode 层"]
        LDP["LogicalDecodingProcessRecord<br/>(decode.c)"]
        RMD["rm_decode[rmid]<br/>xact_decode / heap_decode<br/>heap2_decode / standby_decode"]
    end

    subgraph SNAP["3. SnapBuild 层"]
        SB["SnapBuild 状态机<br/>(snapbuild.c)<br/>START→BUILDING→FULL→CONSISTENT"]
        SD["快照构造/分发<br/>committed.xip / catchange.xip"]
    end

    subgraph REORDER["4. ReorderBuffer 层"]
        RB["ReorderBuffer<br/>(reorderbuffer.c)"]
        TXN["ReorderBufferTXN<br/>toplevel_by_lsn<br/>by_txn 哈希"]
        CHG["ReorderBufferChange<br/>INSERT/UPDATE/DELETE/TRUNCATE"]
        SNAP2["Base Snapshot<br/>注入到 in-progress 事务"]
        SPILL["磁盘溢出<br/>logical/decoding/"]
    end

    subgraph PLUGIN["5. Output Plugin 层"]
        OP["Output Plugin 回调<br/>begin/change/commit<br/>stream_*/prepare/*"]
        PGO["pgoutput.c<br/>(内置)"]
        TD["test_decoding<br/>(内置示例)"]
    end

    subgraph WIRE["6. Wire Protocol 层"]
        PW["WalSndPrepareWrite<br/>WalSndWriteData<br/>(walsender.c)"]
        P3["COPY 协议 (3)"]
    end

    subgraph S["Subscriber 侧"]
        W["worker.c<br/>apply worker"]
        AP["LogicalRepApplyLoop<br/>SQL: INSERT/UPDATE/DELETE"]
    end

    WTX --> WAL
    BG --> WAL
    WAL --> XR
    XR --> LDP
    LDP --> RMD
    RMD --> SB
    SB --> SD
    SD --> RB
    RB --> TXN
    RB --> CHG
    RB --> SNAP2
    RB -.溢出.-> SPILL
    TXN --> OP
    CHG --> OP
    SNAP2 --> OP
    OP --> PGO
    OP --> TD
    PGO --> PW
    TD --> PW
    PW --> P3
    P3 -->|网络| W
    W --> AP

    style P fill:#dcfce7,stroke:#15803d,color:#000
    style SNAP fill:#dbeafe,stroke:#1d4ed8,color:#000
    style REORDER fill:#fce7f3,stroke:#be185d,color:#000
    style PLUGIN fill:#f3e8ff,stroke:#7e22ce,color:#000
    style WIRE fill:#fef9c3,stroke:#a16207,color:#000
    style S fill:#dcfce7,stroke:#15803d,color:#000
```

### 1.2 模块清单与代码量

| 模块 | 文件 | 行数 | 职责 |
|------|------|------|------|
| **WAL 读取** | `replication/walsender.c` | 4000+ | `XLogSendLogical`、`WalSndLoop` 主循环 |
| **解码框架** | `replication/logical/logical.c` | 2198 | `StartupDecodingContext`、`CreateDecodingContext` |
| **WAL 解码** | `replication/logical/decode.c` | 1316 | `LogicalDecodingProcessRecord`、各 rmgr 的 `*_decode` |
| **状态机** | `replication/logical/snapbuild.c` | 2076 | 4 态状态机、committed/catchange 数组 |
| **重组缓冲** | `replication/logical/reorderbuffer.c` | 5615 | `ReorderBufferTXN` / `ReorderBufferChange` 抽象、磁盘溢出 |
| **Output 框架** | `replication/logical/logical.c` | — | 回调包装(error context) |
| **pgoutput 插件** | `replication/pgoutput/pgoutput.c` | 2484 | 内置逻辑复制输出插件,真实订阅者协议 |
| **协议** | `replication/logical/proto.c` | 1301 | 二进制流协议编码 |
| **apply worker** | `replication/logical/worker.c` | 5239 | 订阅者端 apply 主循环 |
| **冲突处理** | `replication/logical/conflict.c` | 505 | PG 16+ 冲突检测 |
| **并行 apply** | `replication/logical/applyparallelworker.c` | 1646 | PG 17+ 并行 apply 框架 |
| **slot 同步** | `replication/logical/slotsync.c` | 1862 | failover 时 slot 同步 |

**总代码量**:`src/backend/replication/logical/` + `pgoutput/` + `walsender.c` 共 ~30K 行。

### 1.3 核心数据流(单条 WAL 记录)

```mermaid
sequenceDiagram
    autonumber
    participant TXN as 写入事务
    participant WAL as WAL Buffer
    participant WS as walsender<br/>(XLogSendLogical)
    participant XR as XLogReader
    participant LDP as LogicalDecoding<br/>ProcessRecord
    participant RMD as rm_decode
    participant SB as SnapBuild
    participant RB as ReorderBuffer
    participant OP as Output Plugin
    participant SUB as 订阅者

    TXN->>WAL: 写 INSERT/HEAP2/COMMIT 等
    Note over WAL: 落盘后由 walsender 读
    WS->>XR: XLogReadRecord
    XR-->>WS: 返回 XLogRecord
    WS->>LDP: LogicalDecodingProcessRecord(ctx, record)
    LDP->>LDP: ReorderBufferAssignChild<br/>(子事务挂到 top xid)
    LDP->>RMD: rm_decode(ctx, buf)
    alt xact_decode (COMMIT/ABORT)
        RMD->>SB: SnapBuildCommitTxn
        SB->>SB: 更新 committed.xip
        SB->>RB: SnapBuildDistributeSnapshotAndInval
    else heap_decode (INSERT/UPDATE/DELETE)
        RMD->>SB: SnapBuildProcessChange
        SB->>RB: ReorderBufferSetBaseSnapshot
        RMD->>RB: ReorderBufferQueueChange
    else heap2_decode (NEW_CID/MULTI_INSERT)
        RMD->>SB: SnapBuildProcessNewCid
        RMD->>RB: ReorderBufferAddNewTupleCids
    else standby_decode (XLOG_RUNNING_XACTS)
        RMD->>SB: SnapBuildProcessRunningXacts
        SB->>SB: 状态机推进
    end
    RB->>OP: change/commit callback
    OP->>OP: pgoutput_change 编码协议
    OP->>SUB: WalSndWriteData → 网络
    SUB->>SUB: LogicalRepApplyLoop → apply
```

**关键观察**:**snapbuild 与 reorder buffer 紧密耦合**。snapbuild 决定哪些 WAL 记录"可以解码",reorder buffer 负责把"可解码"的内容暂存、排序、最终交给 output plugin。

---

## 二、状态机原理:snapbuild 的 4 态推进

> snapbuild.c 已经在 <../postgresql-snapbuild-deep-dive/> 详细拆解 32 个函数。本文重点讲状态机的"WAL 推进视角"——**看到哪条 WAL 记录,状态会怎么变**。

### 2.1 状态机回顾

```mermaid
stateDiagram-v2
    [*] --> START: 启动
    START --> BUILDING_SNAPSHOT: 看到 running_xacts<br/>(有 xid 在跑)
    START --> CONSISTENT: 看到 running_xacts<br/>(无人在跑)
    BUILDING_SNAPSHOT --> FULL_SNAPSHOT: #1 的 xid 都跑完
    FULL_SNAPSHOT --> CONSISTENT: #2 的 xid 都跑完
    CONSISTENT --> CONSISTENT: 持续读 WAL + Serialize
```

**状态值**(`snapbuild.h:23-49`):
- `SNAPBUILD_START = -1`
- `SNAPBUILD_BUILDING_SNAPSHOT = 0`
- `SNAPBUILD_FULL_SNAPSHOT = 1`
- `SNAPBUILD_CONSISTENT = 2`

### 2.2 推进矩阵:每种 WAL 记录如何影响状态

| WAL 记录类型 | rm_decode | 推进的状态机调用 | 状态变化 |
|--------------|-----------|------------------|----------|
| `XLOG_RUNNING_XACTS` | `standby_decode` | `SnapBuildProcessRunningXacts` | START→BUILDING / BUILDING→FULL / FULL→CONSISTENT |
| `XLOG_HEAP_INSERT/UPDATE/DELETE/TRUNCATE` | `heap_decode` | `SnapBuildProcessChange` | 仅在 ≥ FULL_SNAPSHOT 时返回 true |
| `XLOG_HEAP2_NEW_CID` | `heap2_decode` | `SnapBuildProcessNewCid` | 标记事务改了 catalog,加 cmin/cmax |
| `XLOG_HEAP2_MULTI_INSERT` | `heap2_decode` | `SnapBuildProcessChange` | 同 INSERT |
| `XLOG_XACT_COMMIT/ABORT` | `xact_decode` | `SnapBuildCommitTxn` | 决定是否需要重建 snapshot |
| `XLOG_XACT_ASSIGNMENT` | `xact_decode` | (跳过) | 子事务分配到 top xid |
| `XLOG_XACT_INVALIDATIONS` | `xact_decode` | (加 invalidation 队列) | 缓存 invalidation |
| `XLOG_CHECKPOINT_SHUTDOWN` | `xlog_decode` | `SnapBuildSerialize` | serialize 快照到磁盘 |
| `XLOG_CHECKPOINT_ONLINE` | `xlog_decode` | `SnapBuildSerialize` | 同上 |

**核心规律**:**只有 `XLOG_RUNNING_XACTS` 能改变 state 字段**。其他记录只修改 builder 内部的 `xmin`/`xmax`/`committed.xip`/`snapshot`。

### 2.3 4 态的"业务含义"

| 状态 | 业务含义 | 可解码性 | 可分发 snapshot | 可 export |
|------|----------|----------|-----------------|-----------|
| **START** | 刚启动,什么都没收集 | ❌ | ❌ | ❌ |
| **BUILDING_SNAPSHOT** | 在等 #1 老 xid 结束 | ❌ | ❌ | ❌ |
| **FULL_SNAPSHOT** | 已有 catalog 快照,新 xid 可解码 | ✅(新 xid) | ✅(限 catalog) | ❌ |
| **CONSISTENT** | 一切就绪,持久化快照已存在磁盘 | ✅(所有 xid) | ✅(user data) | ✅ |

**关键不变量**:
- `state >= SNAPBUILD_FULL_SNAPSHOT` 是 `SnapBuildBuildSnapshot` 的 `Assert`(见 snapbuild.c:365)
- `state == SNAPBUILD_CONSISTENT` 是 `SnapBuildInitialSnapshot` 的 `Assert`(见 snapbuild.c:461)
- 这意味着 **不在稳态,不可能导出 snapshot 给 user data 读**

---

## 三、WAL 记录处理矩阵:每种 rmgr 的解码路径

每条 WAL 记录进入 `LogicalDecodingProcessRecord`(`decode.c:88`)后,根据 `rmid` 走不同分支:

```mermaid
flowchart TD
    A[LogicalDecodingProcessRecord] --> B{txid 有效?}
    B -->|是| C1[ReorderBufferAssignChild<br/>挂子事务到 top]
    B -->|否| D
    C1 --> D
    D --> E[GetRmgr rmid]
    E --> F{rm_decode != NULL?}
    F -->|否| G1[ReorderBufferProcessXid]
    F -->|是| G2[rm_decode ctx, buf]
    G2 --> H[各 rmgr 的 decode 函数]
    H --> H1[xlog_decode]
    H --> H2[xact_decode]
    H --> H3[standby_decode]
    H --> H4[heap_decode]
    H --> H5[heap2_decode]
    H --> H6[logicalmsg_decode]
    style A fill:#dcfce7,stroke:#15803d,color:#000
    style C1 fill:#dbeafe,stroke:#1d4ed8,color:#000
    style G1 fill:#fef9c3,stroke:#a16207,color:#000
```

### 3.1 `xlog_decode`(`decode.c:129-198`)

**职责**:处理 `RM_XLOG_ID`(CHECKPOINT 记录)。

**关键分支**:
- `XLOG_CHECKPOINT_SHUTDOWN` / `XLOG_CHECKPOINT_ONLINE`:触发 `SnapBuildSerialize` 写快照
- `XLOG_END_OF_RECOVERY`:同 shutdown
- 其他(`FPI` / `SWITCH` / `BACKUP_END`):不处理(只调 `ReorderBufferProcessXid`)

**为什么 checkpoint 触发 serialize**? 因为 slot 需要"重启点",而 shutdown checkpoint 是"无 in-progress 事务"的最佳时机。online checkpoint 则作为常规推进点。

### 3.2 `xact_decode`(`decode.c:201-356`)

**职责**:处理 `RM_XACT_ID`(事务提交/回滚/prepare/assignment/invalidation)。

**4 个子分支**:

```mermaid
flowchart TD
    A[xact_decode] --> B{state &lt; FULL_SNAPSHOT?}
    B -->|是| RETURN[return<br/>快照未就绪]
    B -->|否| C{info 类型?}
    C -->|COMMIT / COMMIT_PREPARED| D1[ParseCommitRecord]
    C -->|ABORT / ABORT_PREPARED| D2[ParseAbortRecord]
    C -->|ASSIGNMENT| D3[skip]
    C -->|INVALIDATIONS| D4[ReorderBufferAddInvalidations]
    C -->|PREPARE| D5[FilterPrepare → DecodePrepare]
    D1 --> E1[SnapBuildCommitTxn]
    D1 --> E2[DecodeTXNNeedSkip?]
    E2 -->|是| E3[ReorderBufferForget]
    E2 -->|否| E4[ReorderBufferCommitChild]
    E4 --> E5{two_phase?}
    E5 -->|是| E6[ReorderBufferFinishPrepared]
    E5 -->|否| E7[ReorderBufferCommit]
    D2 --> F1[SnapBuildCommitTxn]
    F1 --> F2[DecodeAbort]
    style A fill:#dcfce7,stroke:#15803d,color:#000
    style RETURN fill:#fef9c3,stroke:#a16207,color:#000
```

**关键调用链**:`xact_decode → SnapBuildCommitTxn → SnapBuildDistributeSnapshotAndInval → ReorderBufferAddSnapshot`

### 3.3 `standby_decode`(`decode.c:359-403`)

**职责**:处理 `RM_STANDBY_ID`(`XLOG_RUNNING_XACTS`、`XLOG_STANDBY_LOCK`、`XLOG_INVALIDATIONS`)。

**核心调用**(`decode.c:362-388`):
```c
case XLOG_RUNNING_XACTS:
    running = (xl_running_xacts *) XLogRecGetData(r);
    SnapBuildProcessRunningXacts(builder, buf->origptr, running);
    ReorderBufferAbortOld(ctx->reorder, running->oldestRunningXid);
```

**两个关键调用**:
1. `SnapBuildProcessRunningXacts`:**状态机的总驱动**。每条 `XLOG_RUNNING_XACTS` 都会推进。
2. `ReorderBufferAbortOld`:**裁剪 reorder buffer**。把 < `oldestRunningXid` 的事务强制 abort(因为它们理论上不可能"还活着"了)。

**`XLOG_STANDBY_LOCK` 和 `XLOG_INVALIDATIONS`**:不做事(由 `xact_decode` 的 `XLOG_XACT_INVALIDATIONS` 处理)。

### 3.4 `heap_decode`(`decode.c:469-550`)

**职责**:处理 `RM_HEAP_ID`(`INSERT` / `UPDATE` / `DELETE` / `TRUNCATE` / `INPLACE` / `CONFIRM` / `LOCK`)。

**核心模式**(以 `XLOG_HEAP_INSERT` 为例,`decode.c:494-498`):
```c
case XLOG_HEAP_INSERT:
    if (SnapBuildProcessChange(builder, xid, buf->origptr) &&
        !ctx->fast_forward)
        DecodeInsert(ctx, buf);
    break;
```

**两层过滤**:
1. `SnapBuildProcessChange`:**关键过滤器**。返回 false 时,直接跳过(连 `ReorderBufferProcessXid` 都不调,decode.c:475 已经在前面调过)。

> **重要**:`ReorderBufferProcessXid` 是在 rm_decode 入口处无条件调的(`decode.c:475`),它**先于** snapbuild 的状态检查。这意味着即便 snapbuild 拒绝,reorder buffer 仍然**会知道这个 xid 存在**(只是不装 base snapshot)。

2. `!ctx->fast_forward`:**快进模式**。`STARTUP` 时只跑 snapbuild 不发数据,`streaming` 时才发。

**每个分支的 `DecodeXxx`**:
- `DecodeInsert` / `DecodeUpdate` / `DecodeDelete` / `DecodeTruncate` / `DecodeSpecConfirm`:解析 WAL 数据,转 `ReorderBufferQueueChange`
- `XLOG_HEAP_INPLACE`:跳过(catalog 表的 inplace update,不影响 user)
- `XLOG_HEAP_LOCK`:跳过(行锁与逻辑复制无关)

### 3.5 `heap2_decode`(`decode.c:405-467`)

**职责**:处理 `RM_HEAP2_ID`(`NEW_CID` / `MULTI_INSERT` / `REWRITE` / 各种 `PRUNE_*` / `VISIBLE` / `LOCK_UPDATED`)。

**最关键分支**(`decode.c:425-432`):
```c
case XLOG_HEAP2_NEW_CID:
    if (!ctx->fast_forward)
    {
        xlrec = (xl_heap_new_cid *) XLogRecGetData(buf->record);
        SnapBuildProcessNewCid(builder, xid, buf->origptr, xlrec);
        break;
    }
    // 注意:这里没有 break!如果没有 fast_forward,fall through 到 default
```

**注意**:`if (!ctx->fast_forward)` **没有 break**,会 fall through 到 default。fast_forward 模式直接跳过 NEW_CID 处理。

**`XLOG_HEAP2_MULTI_INSERT`**:一次插入多行(CTAS 场景),走 `DecodeMultiInsert`(`decode.c:421-424`)。

**`XLOG_HEAP2_REWRITE`**:只在 crash recovery 时生效,逻辑解码中不做事。

### 3.6 `logicalmsg_decode`(`decode.c:586-666`)

**职责**:处理 `RM_LOGICALMSG_ID`(逻辑消息,用于插件间通信)。

**两种消息**:
- **transactional message**(`xlrec->transactional == true`):进 reorder buffer,事务提交时才发
- **non-transactional message**:立即发,不入 buffer

---

## 四、reorder buffer 核心抽象

`reorderbuffer.c` 是逻辑复制的**真正核心**(5615 行,占 logical 子目录 1/4)。它负责解决一个核心问题:**WAL 里的事务是按 LSN 顺序写入的,但发布给订阅者时需要按"事务提交顺序"**。

### 4.1 核心数据结构

```mermaid
flowchart LR
    subgraph RB["ReorderBuffer"]
        CTX[MemoryContext]
        SLOT[ReplicationSlot]
        PRIVATE[private_data<br/>= LogicalDecodingContext]
        OUTPUT[output_rewrites]
        CALLBACKS[callbacks:<br/>begin/change/commit<br/>stream_*/prepare/...]
        subgraph DECKS[核心容器]
            TOP[txns by xid<br/>hash table]
            TOP_LSN[toplevel_by_lsn<br/>pairing heap]
            CATCH[catchange_txns<br/>dclist]
            SERIALIZED[serialized_txns<br/>dlist]
        end
        subgraph BSTATE[Buffer 状态]
            CUR_RESTART[current_restart_decoding_lsn]
            CB[cleanup_callbacks]
            TXNS[txns array]
            NXID[next_txn]
        end
    end
    style RB fill:#fce7f3,stroke:#be185d,color:#000
    style DECKS fill:#dbeafe,stroke:#1d4ed8,color:#000
    style BSTATE fill:#fef9c3,stroke:#a16207,color:#000
```

### 4.2 `ReorderBufferTXN` —— 事务抽象

```c
/* reorderbuffer.c / reorderbuffer.h 关键字段 */
struct ReorderBufferTXN {
    TransactionId xid;            /* 事务 id */
    XLogRecPtr first_lsn;         /* 第一个 LSN */
    XLogRecPtr restart_decoding_lsn; /* 何时可以重启 */
    dlist_node node;              /* toplevel_by_lsn 的节点 */
    Snapshot base_snapshot;       /* 从 snapbuild 注入的快照 */
    bool is_catalog_change;       /* 是否改了 catalog */
    ReorderBufferTupleCids *tuple_cids; /* cmin/cmax 映射 */
    dlist_head changes;           /* ReorderBufferChange 列表 */
    Size total_size;              /* 内存占用(触发 spill) */
    ReorderBufferTXN *toplevel_xid; /* 父事务(子事务) */
    /* ... */
};
```

**`base_snapshot` 是关键**:这是从 snapbuild 注入的"目录快照",决定了这个事务解码时能"看到"哪些 catalog 行。

### 4.3 `ReorderBufferChange` —— 变更抽象

```c
typedef enum {
    REORDER_BUFFER_CHANGE_INSERT,
    REORDER_BUFFER_CHANGE_UPDATE,
    REORDER_BUFFER_CHANGE_DELETE,
    REORDER_BUFFER_CHANGE_TRUNCATE,
    REORDER_BUFFER_CHANGE_MESSAGE,
    REORDER_BUFFER_CHANGE_INTERNAL_SPECINSERT,  /* speculative insert for ON CONFLICT */
    REORDER_BUFFER_CHANGE_INTERNAL_SPECCONFIRM, /* confirm speculative */
    REORDER_BUFFER_CHANGE_STREAMING,            /* 标记 streaming 起点 */
} ReorderBufferChangeType;
```

### 4.4 关键函数:事务生命周期

| 函数 | 行号 | 职责 |
|------|------|------|
| `ReorderBufferAllocate` | 324 | 创建 reorder buffer |
| `ReorderBufferProcessXid` | 759 | 看到 xid 时调,创建 `ReorderBufferTXN` |
| `ReorderBufferAssignChild` | 731 | 把子 xid 挂到 top xid |
| `ReorderBufferCommitChild` | 733 | 子事务 commit 记录,合并到 top |
| `ReorderBufferQueueChange` | 715 | 入队一条 change(INSERT/UPDATE/DELETE) |
| `ReorderBufferCommit` | 722 | top xid commit,触发 output 回调 |
| `ReorderBufferAbort` | 736 | top xid abort,丢弃 |
| `ReorderBufferAbortOld` | 738 | 强制 abort < oldestRunningXid 的 xid |
| `ReorderBufferForget` | 739 | 跳过这个事务(不发送) |
| `ReorderBufferSetBaseSnapshot` | 742 | snapbuild 注入 snapshot 给事务 |
| `ReorderBufferAddSnapshot` | 744 | 后续 snapshot 更新(commit 后触发) |

### 4.5 base snapshot 注入机制

**这是 snapbuild 与 reorder buffer 的"接口"**。

```mermaid
sequenceDiagram
    participant DEC as heap_decode
    participant SB as SnapBuild
    participant RB as ReorderBuffer

    DEC->>SB: SnapBuildProcessChange(xid, lsn)
    SB->>SB: 必要检查(state >= FULL)
    SB->>RB: ReorderBufferXidHasBaseSnapshot(rb, xid)
    alt xid 没有 base snapshot
        SB->>SB: builder->snapshot = SnapBuildBuildSnapshot
        SB->>SB: IncRefcount
        SB->>RB: ReorderBufferSetBaseSnapshot(rb, xid, lsn, snapshot)
        Note over RB: 后续这个 xid 的 change 用这个<br/>snapshot 解码
    end
    SB-->>DEC: return true
```

**第二次注入**(`commit` 之后):
```mermaid
sequenceDiagram
    participant XACT as xact_decode
    participant SB as SnapBuild
    participant RB as ReorderBuffer

    XACT->>SB: SnapBuildCommitTxn
    Note over SB: 主事务改了 catalog<br/>needs_snapshot = true
    SB->>SB: 重建 builder->snapshot
    SB->>SB: DistributeSnapshotAndInval
    Note over SB: 遍历 reorder->toplevel_by_lsn
    loop 所有 in-progress 事务
        alt 没有 base snapshot
            Note over SB,RB: 跳过(后续第一次 change 时再装)
        else 是 prepared
            Note over SB,RB: 跳过(prepared 不应见新 catalog)
        else 是 commit 自己的事务
            Note over SB,RB: 跳过自己(已发过)
        else 其他 in-progress 事务
            SB->>RB: ReorderBufferAddSnapshot<br/>(新 snapshot)
            SB->>RB: ReorderBufferAddDistributedInvalidations<br/>(新 inval 消息)
        end
    end
```

**关键约束**:`base_snapshot` 在事务**第一条 change** 时注入,在事务**commit 时**如果 catalog 改过则更新并分发给**其他 in-progress 事务**。

### 4.6 磁盘溢出(spill)

`ReorderBufferCheckMemoryLimit`(`reorderbuffer.c:265`)周期性检查 `rb->txns[REORDER_BUFFER_CHANGE_SIZE]` 是否超过 `logical_decoding_work_mem`。超过则:
1. 找**最老的非 streamed** 事务
2. `ReorderBufferSerializeTXN` → 写到 `pg_replslot/<slot>/decoding/<xid>_<lsn>.td` 文件
3. 释放内存

**重启时**:`ReorderBufferRestoreContents` 读回。

---

## 五、完整启动到稳态流程(具体日志举例)

> 这是 snapbuild.c 状态机的"WAL 视角"展示。**所有 LSN 都是虚构示例**,实际位置由初始 `restart_lsn` 决定。

### 5.1 假设场景

- publisher 跑了 N 天,有 100 个 long-running 事务
- slot 初始 `restart_lsn = 0/1500000`
- bgwriter 周期 15s(checkpoint)

### 5.2 WAL 序列与状态推进

```mermaid
sequenceDiagram
    autonumber
    participant WS as walsender
    participant LDP as LogicalDecoding<br/>ProcessRecord
    participant SB as SnapBuild
    participant RB as ReorderBuffer

    Note over WS,RB: === T0:启动 walsender ===
    WS->>LDP: CreateDecodingContext<br/>(ctx->reader 分配 + snapbuild 启动)
    Note over SB: state = START<br/>xmin = Invalid, xmax = Invalid

    Note over WS,RB: === T1:读 slot.restart_lsn 处 ===
    WS->>LDP: XLogReadRecord → 0/1500060 (RM_XLOG, XLOG_CHECKPOINT_ONLINE)
    LDP->>LDP: xlog_decode → SnapBuildSerialize?
    Note over SB: state < CONSISTENT<br/>SnapBuildSerialize 直接 return
    LDP-->>WS: 0 records emitted

    Note over WS,RB: === T2:读 0/16A0F80 (RM_STANDBY, XLOG_RUNNING_XACTS) ===
    WS->>LDP: XLogReadRecord → 0/16A0F80
    LDP->>LDP: standby_decode
    LDP->>SB: SnapBuildProcessRunningXacts(0/16A0F80, running)
    Note over SB: state=START, running.xcnt=100
    SB->>SB: SnapBuildFindSnapshot
    Note over SB: 走路径 c-1:<br/>state=START → BUILDING_SNAPSHOT<br/>next_phase_at = running.nextXid = 501
    SB->>SB: SnapBuildWaitSnapshot(running, 501)
    Note over SB: XactLockTableWait xid 401..500<br/>(等 #1 的 xid)
    LDP->>RB: ReorderBufferAbortOld(401)
    LDP-->>WS: 0 records

    Note over WS,RB: === T3:...继续读 WAL,跳过所有非关键 record ===
    loop 大量 HEAP/XACT/BTREE 记录
        WS->>LDP: 读 record
        LDP->>SB: state < FULL_SNAPSHOT
        Note over SB: SnapBuildCommitTxn 直接 return
        LDP-->>WS: 跳过
    end

    Note over WS,RB: === T4:看到下一条 XLOG_RUNNING_XACTS ===
    WS->>LDP: 0/1A00100 (RM_STANDBY, XLOG_RUNNING_XACTS)
    LDP->>LDP: standby_decode
    LDP->>SB: SnapBuildProcessRunningXacts
    Note over SB: state=BUILDING_SNAPSHOT<br/>running.oldestRunningXid = 502
    SB->>SB: SnapBuildFindSnapshot
    Note over SB: next_phase_at(501) <= oldestRunningXid(502)<br/>走 c-2:<br/>state = FULL_SNAPSHOT<br/>next_phase_at = running.nextXid = 520
    SB->>SB: SnapBuildWaitSnapshot(running, 520)
    LDP->>RB: ReorderBufferAbortOld(502)
    LDP-->>WS: 0 records

    Note over WS,RB: === T5:看到第三条 XLOG_RUNNING_XACTS ===
    WS->>LDP: 0/1C00200 (RM_STANDBY, XLOG_RUNNING_XACTS)
    LDP->>LDP: standby_decode
    LDP->>SB: SnapBuildProcessRunningXacts
    Note over SB: state=FULL_SNAPSHOT<br/>running.oldestRunningXid = 521
    SB->>SB: SnapBuildFindSnapshot
    Note over SB: next_phase_at(520) <= oldestRunningXid(521)<br/>走 c-3:<br/>state = CONSISTENT<br/>next_phase_at = InvalidTransactionId
    LDP->>RB: ReorderBufferAbortOld(521)
    LDP-->>WS: 0 records

    Note over WS,RB: === T6:consistency 后的第一次 commit 触发 serialize ===
    WS->>LDP: 0/1C0A000 (RM_XACT, XLOG_XACT_COMMIT for xid=505)
    LDP->>LDP: xact_decode
    LDP->>SB: SnapBuildCommitTxn(xid=505, ...)
    Note over SB: state=CONSISTENT, builder.snapshot 已就绪
    SB->>SB: SnapBuildDistributeSnapshotAndInval
    SB->>SB: SnapBuildSerialize?<br/>(由后续 XLOG_CHECKPOINT 触发)
    LDP->>RB: ReorderBufferCommit
    RB->>RB: 触发 change_cb → begin_cb → commit_cb
    Note over RB: pgoutput_change 编码并发送
    LDP-->>WS: 1 record emitted (CHANGE/BEGIN/COMMIT)

    Note over WS,RB: === T7:第一次 SHUTDOWN checkpoint 触发 serialize ===
    WS->>LDP: 0/1D00000 (RM_XLOG, XLOG_CHECKPOINT_SHUTDOWN)
    LDP->>LDP: xlog_decode
    LDP->>SB: SnapBuildSerialize(0/1D00000)
    Note over SB: 写 0-1D00000.snap 到磁盘<br/>last_serialized_snapshot = 0/1D00000

    Note over WS,RB: === T8:稳态,持续读 WAL ===
    loop 持续
        WS->>LDP: 读 record
        LDP->>SB: 视类型处理
        LDP->>RB: ReorderBufferCommit/QueueChange
        RB->>WS: 编码 + 发送
    end
```

### 5.3 关键观察

1. **从 T0 到 T4(state=FULL_SNAPSHOT),不发送任何数据**。这一段时间,所有 `DecodeCommit` 都直接 return,只有 `SnapBuild` 在静默收集。
2. **从 T4 起,可以发"新 xid"**。但 T4 之前启动的事务(< next_phase_at=520)仍然**不发送**,因为它们的提交信息不全。
3. **从 T5(state=CONSISTENT)起,所有 xid 都可发**。此时也才允许 `pg_dump` 用这个 slot。
4. **T7 之后**:重启 slot 时可以直接从 `0/1D00000.snap` 恢复,**跳过 T0-T6 全部过程**。

### 5.4 "如果看到的是空 running_xacts"

```mermaid
sequenceDiagram
    participant WS as walsender
    participant LDP as LogicalDecoding
    participant SB as SnapBuild

    Note over WS,SB: 假设启动时第一条 running_xacts 就是空
    WS->>LDP: 0/1500060 (XLOG_RUNNING_XACTS)<br/>oldestRunningXid == nextXid
    LDP->>SB: SnapBuildProcessRunningXacts
    Note over SB: 路径 a:<br/>直接 state = CONSISTENT<br/>next_phase_at = Invalid
    SB-->>LDP: SnapBuildFindSnapshot 返回 false
    Note over LDP: 0 records emitted
    LDP-->>WS: 立即进入稳态
```

**这是最快路径** —— startup 几乎瞬间完成。

---

## 六、完整事务生命周期(具体例子)

> 用一个具体的 **UPDATE** 事务,从客户端 `UPDATE` 到订阅者 apply,**逐函数**跟踪。

### 6.1 假设场景

- publisher 客户端执行:`UPDATE t SET val = 100 WHERE id = 1;`
- t 表 schema:`(id int, val int)`,id 为主键
- xid = 600
- LSN 序列(虚构)

### 6.2 publisher 端:walsender 读到这条事务的 WAL

```mermaid
sequenceDiagram
    autonumber
    participant Client as 客户端
    participant BE as backend
    participant WAL as WAL Buffer
    participant WS as walsender<br/>XLogSendLogical
    participant XR as XLogReader
    participant LDP as LogicalDecoding
    participant RMD as rm_decode
    participant SB as SnapBuild
    participant RB as ReorderBuffer
    participant OP as pgoutput
    participant SUB as 订阅者

    Note over Client: 客户端连接
    Client->>BE: BEGIN
    Client->>BE: UPDATE t SET val=100 WHERE id=1
    BE->>WAL: 写 XLOG:<br/>HEAP_UPDATE @ 0/1F00000<br/>(replaces tid, new tuple, cmin=1)
    Note over WAL: rmgr=RM_HEAP_ID(0), info=XLOG_HEAP_UPDATE
    Client->>BE: COMMIT
    BE->>WAL: 写 XLOG:<br/>XLOG_XACT_COMMIT @ 0/1F00200<br/>(xid=600, subxacts=0, xinfo=0)

    Note over WS,SUB: === walsender 端(异步推进) ===
    WS->>XR: XLogReadRecord → 0/1F00000 (HEAP_UPDATE)
    XR-->>WS: 成功
    WS->>LDP: LogicalDecodingProcessRecord(record)
    LDP->>RB: ReorderBufferProcessXid(600)<br/>(创建 ReorderBufferTXN, if not exists)
    LDP->>RMD: heap_decode(rm=RM_HEAP)
    RMD->>SB: SnapBuildProcessChange(600, 0/1F00000)
    Note over SB: state=CONSISTENT<br/>xid 没有 base snapshot
    SB->>SB: builder->snapshot = SnapBuildBuildSnapshot
    SB->>SB: IncRefcount(1) builder
    SB->>RB: ReorderBufferSetBaseSnapshot(600, snap)
    SB->>SB: IncRefcount(2) 给 xid
    RMD->>RMD: DecodeUpdate(ctx, buf)
    Note over RMD: 解析 WAL:<br/>读到 relation=16384, tid=(0,1)<br/>new tuple=(1, 100)
    RMD->>RB: ReorderBufferQueueChange(600, UPDATE, change)
    Note over RB: 排入 tx->changes 列表
    LDP-->>WS: 0 records sent<br/>(xid 还没 commit)

    WS->>XR: XLogReadRecord → 0/1F00200 (XLOG_XACT_COMMIT)
    XR-->>WS: 成功
    WS->>LDP: LogicalDecodingProcessRecord(record)
    LDP->>RB: ReorderBufferProcessXid(600)
    LDP->>RMD: xact_decode(rm=RM_XACT)
    RMD->>SB: SnapBuildCommitTxn(0/1F00200, 600, 0 subxact, xinfo=0)
    Note over SB: state=CONSISTENT<br/>xinfo 无 HAS_INVALS
    SB->>SB: SnapBuildXidHasCatalogChanges(600)? false
    Note over SB: needs_snapshot=false<br/>needs_timetravel=false<br/>committed.includes_all_transactions=false
    SB-->>RMD: 返回
    RMD->>RMD: DecodeTXNNeedSkip? false
    RMD->>RB: ReorderBufferCommit(600, 0/1F00200, endptr, ...)
    RB->>RB: ReorderBufferCommit → 触发回调
    RB->>OP: begin_cb(ctx, txn)
    Note over OP: pgoutput_begin_txn<br/>编码: 'B' + xid
    RB->>OP: change_cb(ctx, txn, relation, change)
    Note over OP: pgoutput_change<br/>编码: 'R' (Relation) + 'U' (Update)<br/>+ tuple old/new
    RB->>OP: commit_cb(ctx, txn, commit_lsn)
    Note over OP: pgoutput_commit_txn<br/>编码: 'C' + commit_lsn
    OP->>OP: OutputPluginPrepareWrite + Write
    OP->>WS: callback 调 WalSndWriteData
    WS->>SUB: COPY 协议数据流:<br/>'B' 600<br/>'R' t<br/>'U' (1, 100)<br/>'C' 0/1F00200
```

### 6.3 订阅者端:apply 流程

```mermaid
sequenceDiagram
    autonumber
    participant NET as TCP/COPY 协议
    participant W as worker.c
    participant AP as LogicalRepApplyLoop
    participant R as apply 状态机
    participant TXN as apply 事务
    participant DB as subscriber DB

    NET->>W: 收到 'B' message
    W->>AP: apply_dispatch
    AP->>R: handle_begin
    R->>TXN: StartTransaction
    TXN->>DB: SET LOCAL statement_timeout = 0

    NET->>W: 收到 'R' message (rel 16384)
    W->>AP: apply_dispatch
    AP->>R: handle_relation
    Note over R: 缓存 relation 信息<br/>(relname, attrs, types)

    NET->>W: 收到 'U' message (UPDATE)
    W->>AP: apply_dispatch
    AP->>R: handle_update
    R->>TXN: 当前 apply 事务中
    R->>DB: UPDATE t SET val=100 WHERE id=1<br/>(或:<br/> DELETE WHERE id=1;<br/> INSERT (1, 100);<br/>如果表无主键)

    NET->>W: 收到 'C' message
    W->>AP: apply_dispatch
    AP->>R: handle_commit
    R->>DB: COMMIT
    R->>TXN: 提交

    Note over W: 流式继续下一批
```

### 6.4 函数调用栈总结(一次 UPDATE)

| 步骤 | 文件:函数 | 关键操作 |
|------|-----------|----------|
| 1 | `walsender.c:XLogSendLogical` | `XLogReadRecord` |
| 2 | `decode.c:LogicalDecodingProcessRecord` | `ReorderBufferAssignChild` + `rm_decode` |
| 3 | `decode.c:heap_decode` | `SnapBuildProcessChange` |
| 4 | `snapbuild.c:SnapBuildProcessChange` | `SnapBuildBuildSnapshot` + `ReorderBufferSetBaseSnapshot` |
| 5 | `decode.c:DecodeUpdate` | 解析 WAL → `ReorderBufferQueueChange` |
| 6 | `decode.c:xact_decode` | 收到 COMMIT 调 `SnapBuildCommitTxn` |
| 7 | `snapbuild.c:SnapBuildCommitTxn` | 判断 needs_snapshot / 重建 snapshot |
| 8 | `decode.c:DecodeCommit` | `ReorderBufferCommit` |
| 9 | `reorderbuffer.c:ReorderBufferCommit` | 触发 output 回调 |
| 10 | `logical.c:begin_cb_wrapper` → `pgoutput.c:pgoutput_begin_txn` | 编码 'B' |
| 11 | `logical.c:change_cb_wrapper` → `pgoutput.c:pgoutput_change` | 编码 'R' + 'U' |
| 12 | `logical.c:commit_cb_wrapper` → `pgoutput.c:pgoutput_commit_txn` | 编码 'C' |
| 13 | `walsender.c:WalSndWriteData` | 写网络 |
| 14 | `proto.c` (订阅者) | 解析消息 |
| 15 | `worker.c:LogicalRepApplyLoop` | apply |
| 16 | `worker.c:handle_update` | `UPDATE` SQL |

**16 个函数调用,贯穿 publisher / subscriber**。

---

## 七、用户 / DBA / 内核开发者 三个视角

### 7.1 用户视角:看得见的现象

```sql
-- 创建 slot
SELECT pg_create_logical_replication_slot('my_slot', 'pgoutput');

-- 启动订阅
CREATE SUBSCRIPTION my_sub CONNECTION '...' PUBLICATION my_pub
  WITH (slot_name = 'my_slot', create_slot = false);

-- 现象 1:启动后前几秒,订阅者不接收数据
--   → 内部:状态机在 BUILDING_SNAPSHOT
-- 现象 2:订阅者累积 lag,数分钟后才追上
--   → 内部:REORDER_BUFFER_TXN 在 reorder buffer 等待提交
-- 现象 3:slot 占用大量磁盘
--   → 内部:ReorderBufferCheckMemoryLimit 触发 spill 到 pg_replslot
```

### 7.2 DBA 视角:监控点

```mermaid
flowchart LR
    subgraph PG_STAT["pg_stat_replication"]
        A1["sent_lsn<br/>(已发送)"]
        A2["write_lsn<br/>(已落盘)"]
        A3["flush_lsn<br/>(已 fsync)"]
        A4["replay_lsn<br/>(已 apply)"]
    end

    subgraph PG_REPLSLOTS["pg_replication_slots"]
        B1["restart_lsn<br/>(下次启动点)"]
        B2["confirmed_flush_lsn<br/>(订阅者已确认)"]
        B3["active_pid<br/>(sender 进程)"]
    end

    subgraph FILES["文件系统"]
        C1["pg_wal/<br/>WAL 段文件"]
        C2["pg_replslot/<slot>/<br/>decoding/*.td<br/>(reorder buffer 溢出)"]
        C3["pg_logical/snapshots/<br/>*.snap (snapbuild 快照)"]
    end

    style PG_STAT fill:#dcfce7,stroke:#15803d,color:#000
    style PG_REPLSLOTS fill:#dbeafe,stroke:#1d4ed8,color:#000
    style FILES fill:#fef9c3,stroke:#a16207,color:#000
```

**DBA 关注的核心指标**:
- `pg_replication_slots.restart_lsn` 决定 slot 占多少 WAL
- `pg_replication_slots.confirmed_flush_lsn` vs `sent_lsn` 差值 = 发送缓冲
- `pg_replslot/<slot>/decoding/` 大小 = reorder buffer 内存压力
- `pg_logical/snapshots/` 大小 = snapbuild 快照文件

**关键 SQL**:
```sql
-- 监控所有 slot 状态
SELECT slot_name, plugin, slot_type, database, active,
       restart_lsn, confirmed_flush_lsn, wal_status
FROM pg_replication_slots;

-- 监控 reorder buffer 占用
SELECT slot_name, spill_txns, spill_count, spill_bytes
FROM pg_stat_replication_slots;

-- 看 snapbuild 状态(扩展:pg_logicalinspect)
SELECT (pg_get_snapbuild_state(slot_name)).state
FROM pg_replication_slots
WHERE plugin = 'pgoutput';
```

### 7.3 内核开发者视角:扩展点

```mermaid
flowchart TD
    A[逻辑复制开发扩展点] --> B[新 Output Plugin]
    A --> C[新 rmgr 支持]
    A --> D[snapbuild 优化]
    A --> E[reorder buffer 优化]

    B --> B1[实现 _PG_output_plugin_init 入口]
    B --> B2[注册回调: startup/begin/change/commit...]
    B --> B3[可选: stream_* / begin_prepare/prepare/...]
    B --> B4[示例: pgoutput.c / test_decoding.c]

    C --> C1[在 rmgrlist.c 加新 rmgr]
    C --> C2[实现 rm_decode 回调]
    C --> C3[在 decode.c 加新 *_decode 函数]

    D --> D1[SnapBuild 状态转换逻辑]
    D --> D2[committed.xip / catchange.xip 算法]
    D --> D3[序列化/恢复机制]

    E --> E1[ReorderBufferTXN 抽象]
    E --> E2[spill/replay 机制]
    E --> E3[streaming + parallel apply]
    style A fill:#dcfce7,stroke:#15803d,color:#000
```

**几个具体扩展点**:

1. **新输出插件**:`src/backend/replication/pgoutput/pgoutput.c` 是范本,所有回调如何实现一目了然。
2. **新的事务类型支持**(比如 GTID):修改 `decode.c` 的 `xact_decode`,加新 case。
3. **snapbuild 优化**:`snapbuild.c` 的 `committed.xip` 排序 / purge 算法可改。
4. **parallel apply**:`applyparallelworker.c` 完整展示了 PG 17+ 的并行 apply 框架。

---

## 八、PG 18 重要特性源码入口

PG 18 在 logical replication 方向有重大升级,以下是源码入口:

| 特性 | 文件 | 关键函数/位置 |
|------|------|--------------|
| **Streaming 模式** | `reorderbuffer.c` | `ReorderBufferStreamTXN`、`ReorderBufferCanStream` |
| **Parallel apply** | `applyparallelworker.c` | `ApplyParallelWorkerMain` 等 |
| **两阶段解码(2PC)** | `decode.c` | `DecodePrepare`、`DecodeCommit` 的 two_phase 分支 |
| **冲突检测** | `conflict.c` | 完整 505 行文件 |
| **Slot failover** | `slotsync.c` | `update_local_synced_slot` |
| **logical message** | `decode.c:logicalmsg_decode` | RM_LOGICALMSG_ID 处理 |
| **origin filter** | `decode.c:FilterByOrigin` | 双源复制场景 |
| **wal2json 风格协议** | `pgoutput.c` | proto.c 编码协议 |

### 8.1 Streaming 模式 (PG 16+)

**核心思想**:事务**还没 commit** 就开始发给订阅者(配合 logical_decoding_work_mem 决定 streaming vs spilling)。

**关键参数**:
- `logical_replication_mode = 'streaming'|'spill'|'immediate'`

**源码入口**(`reorderbuffer.c`):
```c
static inline bool ReorderBufferCanStream(ReorderBuffer *rb);   // line 292
static inline bool ReorderBufferCanStartStreaming(ReorderBuffer *rb);  // line 293
static void ReorderBufferStreamTXN(ReorderBuffer *rb, ReorderBufferTXN *txn);  // line 294
static void ReorderBufferStreamCommit(ReorderBuffer *rb, ReorderBufferTXN *txn);  // line 295
```

### 8.2 Parallel apply (PG 17+)

**核心思想**:大事务可以由多个 apply worker 并行 apply(只对 streaming 模式有效)。

**源码入口**(`applyparallelworker.c`):
- `ApplyParallelWorkerMain`:并行 worker 主入口
- `applyparallelworker.c` 全 1646 行

### 8.3 两阶段解码(2PC) (PG 15+)

**核心思想**:`PREPARE` 记录立即发给订阅者,`COMMIT PREPARED` 触发最终提交。

**源码入口**(`decode.c:763-836`):
- `DecodePrepare` 处理 XLOG_XACT_PREPARE
- `DecodeCommit` 处理 XLOG_XACT_COMMIT_PREPARED
- 调 `ReorderBufferRememberPrepareInfo` 缓存 prepare 信息

### 8.4 冲突检测 (PG 16+)

**核心思想**:订阅者 apply 时检测主键冲突、update 行不存在、delete 行不存在。

**源码入口**:`src/backend/replication/logical/conflict.c`

---

## 九、源码速查表

### 9.1 主入口调用链

```
START_REPLICATION 命令
  → StartLogicalReplication (walsender.c:1228)
    → CreateDecodingContext (logical.c:500)
      → StartupDecodingContext (logical.c:152)
        → LoadOutputPlugin (logical.c:104)
        → AllocateSnapshotBuilder (snapbuild.c:185)
        → ReorderBufferAllocate (reorderbuffer.c:324)
    → DecodingContextFindStartpoint (logical.c:635)
      → 循环读 WAL 直到 SnapBuildCurrentState == CONSISTENT
    → WalSndLoop (walsender.c:1516)
      → XLogSendLogical (walsender.c:3428)
        → XLogReadRecord
        → LogicalDecodingProcessRecord (decode.c:88)
          → ReorderBufferAssignChild
          → rm_decode[rmid] (heap_decode / heap2_decode / xact_decode / standby_decode)
            → SnapBuild* (snapbuild.c)
            → ReorderBuffer* (reorderbuffer.c)
              → output plugin callback (pgoutput.c)
                → WalSndWriteData (walsender.c:1567)
                  → pq_putmessage (libpq)
```

### 9.2 snapbuild.c 关键函数

| 函数 | 行号 | 何时调用 |
|------|------|----------|
| `AllocateSnapshotBuilder` | 185 | 启动时 |
| `SnapBuildProcessChange` | 639 | 每条 HEAP 变更 |
| `SnapBuildProcessNewCid` | 689 | 每条 HEAP2_NEW_CID |
| `SnapBuildCommitTxn` | 940 | 每条 XACT commit/abort |
| `SnapBuildProcessRunningXacts` | 1136 | 每条 RUNNING_XACTS |
| `SnapBuildFindSnapshot` | 1238 | 状态机总驱动 |
| `SnapBuildSerialize` | 1497 | CHECKPOINT 或稳态后 |
| `SnapBuildRestore` | 1841 | 启动时尝试恢复 |
| `CheckPointSnapBuild` | 1970 | checkpoint 时清理 |

### 9.3 decode.c 关键函数

| 函数 | 行号 | 何时调用 |
|------|------|----------|
| `LogicalDecodingProcessRecord` | 88 | 每条 WAL 记录 |
| `xlog_decode` | 129 | RM_XLOG |
| `xact_decode` | 201 | RM_XACT |
| `standby_decode` | 359 | RM_STANDBY |
| `heap_decode` | 469 | RM_HEAP |
| `heap2_decode` | 405 | RM_HEAP2 |
| `logicalmsg_decode` | 586 | RM_LOGICALMSG |
| `DecodeCommit` | 667 | 解析 xact COMMIT |
| `DecodePrepare` | 763 | 解析 xact PREPARE |
| `DecodeAbort` | 838 | 解析 xact ABORT |
| `DecodeInsert` | 894 | 解析 HEAP INSERT |
| `DecodeUpdate` | 953 | 解析 HEAP UPDATE |
| `DecodeDelete` | 1020 | 解析 HEAP DELETE |
| `DecodeTruncate` | 1074 | 解析 HEAP TRUNCATE |
| `DecodeMultiInsert` | 1112 | 解析 HEAP2 MULTI_INSERT |
| `DecodeSpecConfirm` | 1216 | 解析 HEAP CONFIRM |

### 9.4 reorderbuffer.c 关键函数

| 函数 | 行号 | 何时调用 |
|------|------|----------|
| `ReorderBufferAllocate` | 324 | 启动时 |
| `ReorderBufferProcessXid` | 759 | 看到新 xid |
| `ReorderBufferQueueChange` | 715 | 收到 DML change |
| `ReorderBufferCommit` | 722 | top xid commit |
| `ReorderBufferFinishPrepared` | 725 | 2PC commit |
| `ReorderBufferAssignChild` | 731 | 子 xid 挂 top |
| `ReorderBufferCommitChild` | 733 | 子 xid commit |
| `ReorderBufferAbort` | 736 | top xid abort |
| `ReorderBufferAbortOld` | 738 | 强制 abort 老 xid |
| `ReorderBufferSetBaseSnapshot` | 742 | snapbuild 注入 snapshot |
| `ReorderBufferAddSnapshot` | 744 | 后续 snapshot 更新 |

### 9.5 关键宏 / 常量

| 名称 | 值/位置 | 作用 |
|------|---------|------|
| `SNAPBUILD_START` | -1 | 状态机初始 |
| `SNAPBUILD_BUILDING_SNAPSHOT` | 0 | 等 #1 老 xid |
| `SNAPBUILD_FULL_SNAPSHOT` | 1 | 已有 catalog 快照 |
| `SNAPBUILD_CONSISTENT` | 2 | 完全一致 |
| `SNAPBUILD_MAGIC` | 0x51A1E001 | snap 文件魔数 |
| `SNAPBUILD_VERSION` | 6 | snap 文件版本 |
| `PG_LOGICAL_SNAPSHOTS_DIR` | `pg_logical/snapshots` | snap 文件目录 |
| `LOGICAL_REP_MSG_*` | proto.c | 协议消息类型 ('B' / 'R' / 'U' / 'C' / 'D' / 'T' / 'M' / 'O' / 'Y' / 'K' / 'G') |

---

## 十、参考

### 10.1 源码

- 主入口:`src/backend/replication/walsender.c`(~4000 行)
- 解码框架:`src/backend/replication/logical/logical.c`(2198 行)
- 解码器:`src/backend/replication/logical/decode.c`(1316 行)
- 状态机:`src/backend/replication/logical/snapbuild.c`(2076 行)
- 重组缓冲:`src/backend/replication/logical/reorderbuffer.c`(5615 行)
- 输出插件:`src/backend/replication/pgoutput/pgoutput.c`(2484 行)
- 协议:`src/backend/replication/logical/proto.c`(1301 行)
- 订阅端 apply:`src/backend/replication/logical/worker.c`(5239 行)
- 并行 apply:`src/backend/replication/logical/applyparallelworker.c`(1646 行)
- 冲突处理:`src/backend/replication/logical/conflict.c`(505 行)

### 10.2 站内文章

- snapbuild.c 深度解析(32 个函数逐个源码分析): <../postgresql-snapbuild-deep-dive/>
- PostgreSQL 逻辑复制 Stream Publisher: <../postgresql-logical-replication-stream-publisher/>
- PostgreSQL Reorder Buffer 源码分析: <../postgresql-reorder-buffer-code-analysis/>
- PostgreSQL 行锁机制深度解析: <../postgresql-row-lock/>
- PostgreSQL 共享内存机制: <../postgresql-shared-memory/>

### 10.3 官方文档

- [Logical Decoding Overview](https://www.postgresql.org/docs/current/logicaldecoding-explanation.html)
- [Streaming Replication Protocol](https://www.postgresql.org/docs/current/protocol-replication.html)
- [pgoutput 文档](https://www.postgresql.org/docs/current/logicaldecoding-output-plugin.html)
- [WAL Internals](https://www.postgresql.org/docs/current/wal-internals.html)
- [pg_replication_slots 视图](https://www.postgresql.org/docs/current/view-pg-replication-slots.html)

### 10.4 关键术语

- **`xl_running_xacts`**:WAL 中记录当前运行 xid 的结构(`access/xact.h`)
- **`xl_heap_new_cid`**:catalog 改动时记录的 cmin/cmax 组合
- **`xl_xact_parsed_commit`**:commit 记录解析后的结构
- **`XLogReaderState`**:WAL 读取器状态
- **`LogicalDecodingContext`**:逻辑解码上下文,贯穿整个生命周期
- **`ReorderBufferTXN`**:`pg_replication_slots` 视图级别的 in-memory 事务
- **`ReorderBufferChange`**:单条 change(INSERT/UPDATE/DELETE/TRUNCATE/MESSAGE)
- **`base_snapshot`**:snapbuild 注入给事务的 catalog 快照
- **`SNAPSHOT_HISTORIC_MVCC`**:snapbuild 专用快照类型

---

> **更新日志**
>
> - 2026-10-19:初版发布。整合 snapbuild + reorderbuffer + decode + output plugin 完整链路,12 张架构/时序/流程图,完整状态机 WAL 推进举例,一个 UPDATE 事务的 16 步全函数调用链。
