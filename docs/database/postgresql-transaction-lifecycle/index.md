# PostgreSQL 事务：一次 BEGIN 与 COMMIT 背后的双层世界

| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 初稿，结合 PostgreSQL 17 源码 | 2026-08-20 |

如果你只学过 SQL，看到事务大概是这样的：

```sql
BEGIN;
UPDATE account SET balance = balance - 100 WHERE id = 1;
UPDATE account SET balance = balance + 100 WHERE id = 2;
COMMIT;
```

三行字，简单直接。但当这条 SQL 真正跑进 PostgreSQL，它会触发**两台完全不同的状态机**——一台是给你看的（"事务块状态机"），一台是给它自己用的（"低层事务状态机"）。这两台机器之间不是简单翻译，而是层层映射、各司其职。

今天我们沿 `~/cwork/postgresql/src/backend/access/transam/xact.c`、`varsup.c`、`clog.c`，把这双层世界从头到尾拆给你看。

---

## 两层状态机：用户态与内核态

`xact.c` 在第 141 行和第 159 行定义了两个枚举，几乎一模一样的名字，相近的语义，但承担完全不同的职责：

```c
/* 内核的"低层"状态机 */
typedef enum TransState {
    TRANS_DEFAULT,       /* idle */
    TRANS_START,         /* transaction starting */
    TRANS_INPROGRESS,    /* inside a valid transaction */
    TRANS_COMMIT,        /* commit in progress */
    TRANS_ABORT,         /* abort in progress */
    TRANS_PREPARE,       /* prepare in progress */
} TransState;

/* 给客户端协议用的"高层"状态机 */
typedef enum TBlockState {
    TBLOCK_DEFAULT,            /* idle */
    TBLOCK_STARTED,            /* running single-query transaction */

    TBLOCK_BEGIN,              /* starting transaction block */
    TBLOCK_INPROGRESS,         /* live transaction */
    TBLOCK_IMPLICIT_INPROGRESS,/* live transaction after implicit BEGIN */
    TBLOCK_PARALLEL_INPROGRESS,/* live transaction inside parallel worker */
    TBLOCK_END,                /* COMMIT received */
    TBLOCK_ABORT,              /* failed xact, awaiting ROLLBACK */
    TBLOCK_ABORT_END,          /* failed xact, ROLLBACK received */
    TBLOCK_ABORT_PENDING,      /* live xact, ROLLBACK received */
    TBLOCK_PREPARE,            /* live xact, PREPARE received */

    /* 子事务 */
    TBLOCK_SUBBEGIN, TBLOCK_SUBINPROGRESS, TBLOCK_SUBRELEASE,
    TBLOCK_SUBCOMMIT, TBLOCK_SUBABORT, TBLOCK_SUBABORT_END,
    TBLOCK_SUBABORT_PENDING, TBLOCK_SUBRESTART, TBLOCK_SUBABORT_RESTART,
    ...
} TBlockState;
```

为什么需要两台机器？因为客户端协议层有它自己的"事务观"：

- 你在 psql 里发 `COMMIT` 之前，可能还会回 `ROLLBACK`；这两条命令在协议上是等价的"语句"，但内核层对它们的处理路径完全不同。
- 你可能写了 `BEGIN; ... COMMIT;` 也可能写了 `... `（没写 BEGIN）—— 后者其实**也是一个事务**。
- 你可能嵌套 `SAVEPOINT`，也可能跑两阶段提交 `PREPARE TRANSACTION`……

所有这些"用户协议上的状态"必须被内核一一映射到底层的 `TransState` 上。两台机器的关系，可以画成下面这张图：

```text
   ───── 用户视角（你敲的命令）──────               ───── 内核视角（xact.c 真正在跑）──────

   客户端敲了：                                      TransactionStateData s->state
   BEGIN          ──► TBLOCK_BEGIN          ──►     TRANS_START → TRANS_INPROGRESS
   一条 SQL       ──► TBLOCK_STARTED        ──►     TRANS_START → TRANS_INPROGRESS
   COMMIT         ──► TBLOCK_END            ──►     TRANS_COMMIT → TRANS_DEFAULT
   ROLLBACK       ──► TBLOCK_ABORT_END      ──►     TRANS_ABORT → TRANS_DEFAULT
   PREPARE        ──► TBLOCK_PREPARE        ──►     TRANS_PREPARE → TRANS_INPROGRESS

   用户协议的 TBlockState 是"语法糖"             TransState 才是真正决定代码分支的开关
```

---

## 用户视角：事务的"语法糖"

对用户来说，一个事务的生命周期就是这五个动词：

| 命令 | TBlockState | 说明 |
| --- | --- | --- |
| `BEGIN` / `START TRANSACTION` | `TBLOCK_BEGIN` → `TBLOCK_INPROGRESS` | 显式开启事务块 |
| 一条 SQL（无 BEGIN） | `TBLOCK_STARTED` | 单语句自动包装成事务 |
| `COMMIT` | `TBLOCK_END` | 进入提交处理 |
| `ROLLBACK` / `ROLLBACK TO` | `TBLOCK_ABORT_END` / `TBLOCK_ABORT_PENDING` | 回滚 |
| `SAVEPOINT s` | `TBLOCK_SUBBEGIN` → `TBLOCK_SUBINPROGRESS` | 嵌套子事务 |
| `RELEASE s` | `TBLOCK_SUBRELEASE` | 释放保存点 |
| `PREPARE TRANSACTION 'gid'` | `TBLOCK_PREPARE` | 两阶段提交第一阶段 |

注意一个细节：**用户视角里很多状态是"等候命令"的状态**，内核视角里只有六个状态。换句话说，内核不在乎你下一个命令是 COMMIT 还是 ROLLBACK——它只关心"这一刻系统处于提交/中止/正常"哪个分支里。

源码里这件事是这样协作的：

```c
/* BeginTransactionBlock 只是改 blockState，不做真正的开始工作 */
void BeginTransactionBlock(void) {
    s->blockState = TBLOCK_BEGIN;
    /* ...校验状态合法性... */
}

/* 真正的开始工作要等 StartTransactionCommand → StartTransaction */
void StartTransactionCommand(void) {
    switch (s->blockState) {
        case TBLOCK_DEFAULT:
            StartTransaction();
            s->blockState = TBLOCK_STARTED;
            break;
        case TBLOCK_BEGIN:
            StartTransaction();   /* 同样走 StartTransaction */
            /* blockState 等会儿再改成 TBLOCK_INPROGRESS */
            break;
        ...
    }
}
```

也就是说，**"BEGIN 命令本身不开事务"**，它只是把状态机拨到 `TBLOCK_BEGIN`，真正的内存分配、资源管理器创建、XID 分配都发生在下一次 `StartTransactionCommand` 被触发的瞬间。这是个很优雅的延迟——同一个 `StartTransaction` 既能服务隐式事务（无 BEGIN）也能服务显式事务（有 BEGIN），不需要写两份。

---

## 隐式事务：autocommit 的两面

PostgreSQL 没有传统意义上的"autocommit 开关"。它用一种更巧妙的方式实现：

```c
/*
 * 每条 SQL 提交时，CommitTransactionCommand 会看当前 blockState：
 *   - 如果是 TBLOCK_STARTED（无 BEGIN 的单语句），立刻进入 TBLOCK_DEFAULT
 *   - 如果是 TBLOCK_INPROGRESS（有 BEGIN），保持原状态等待下一条 SQL
 */
case TBLOCK_STARTED:
    CommitTransaction();
    s->blockState = TBLOCK_DEFAULT;
    break;
case TBLOCK_BEGIN:
    s->blockState = TBLOCK_INPROGRESS;
    break;
```

你在 psql 里的"普通模式"其实是这样的循环：

```text
  客户端                              PG 后端
  ────────                          ──────
  发一条 SELECT ───────► StartTransactionCommand → StartTransaction
                      执行 SQL
  (等下一条) ◄───────── CommitTransactionCommand → CommitTransaction
                                ↑ CommitTransaction 内部做 WAL、CLOG、清理
                                  然后 blockState 回到 TBLOCK_DEFAULT
                                  
  发 BEGIN            ───► BeginTransactionBlock → blockState=TBLOCK_BEGIN
  发 SELECT           ───► StartTransactionCommand → blockState=TBLOCK_INPROGRESS
                      执行 SQL
  发 COMMIT           ───► EndTransactionBlock → blockState=TBLOCK_END
  (后端下一次循环)      ───► CommitTransactionCommand → 提交并回到 TBLOCK_DEFAULT
```

也就是说，**每一条 SQL 外面都包了一层"StartTransaction + CommitTransaction"**。只是 BEGIN 把 `TBLOCK_END` 留给了下一轮循环，于是两条 SQL 之间的那次 CommitTransactionCommand 就只是更新命令计数 `CommandCounterIncrement`，不会真的提交。

---

## 内存上下文：事务的"沙盒"

每个事务自带一个"内存沙盒"，叫 **MemoryContext**，这是 PostgreSQL 自己实现的内存池。这套机制让事务回滚时能"一键丢弃所有改动过的内存"。

```c
typedef struct TransactionStateData {
    ...
    MemoryContext   curTransactionContext;   /* 当前 SQL 用的 */
    ResourceOwner   curTransactionOwner;     /* 当前 SQL 用的资源 */
    ...
} TransactionStateData;
```

层级关系：

```text
  TopMemoryContext
    └── TopTransactionContext      ← 整个事务的生命周期
            └── CurTransactionContext  ← 每条 SQL 重置
                    └── 执行 SQL 时临时分配的 palloc 都在这
```

`AtCommit_Memory()` 会把整个 `TopTransactionContext` 删掉重建，`AtAbort_Memory()` 则切到 `TransactionAbortContext` 完成清理。所有改动过的缓存、临时表、内存对象都跟着消失。

这相当于 JVM 里的"年轻代"——事务结束就整个清空，省心。

---

## 事务的生命周期（一个完整 COMMIT 的内部旅程）

现在让我们把视角切到内核，**跟随一个事务走完一生**。下面这段伪代码串起了 `xact.c` 里真正的函数调用顺序：

```text
客户端发送 BEGIN
  │
  ├─► exec_simple_query("BEGIN")
  │     └─► BeginTransactionBlock()        ← 只改 blockState
  │
客户端发送 UPDATE ...
  │
  ├─► StartTransactionCommand()
  │     └─► StartTransaction()             ← 见 §"事务开始"
  │           ├─► 创建 TopTransactionContext
  │           ├─► 创建 ResourceOwner
  │           ├─► AssignTransactionId()    ← 申请 XID（可能）
  │           ├─► ProcArrayAddTransaction()
  │           └─► state = TRANS_INPROGRESS
  │
  ├─► 执行 UPDATE
  │     ├─► heap_update()                 ← 写 WAL、写 heap page、改 t_ctid
  │     ├─► XLogInsert(RM_HEAP, ...)
  │     └─► CommandCounterIncrement()     ← currentCommandId++
  │
客户端发送 COMMIT
  │
  ├─► EndTransactionBlock(false)          ← 只改 blockState=TBLOCK_END
  │
  └─► CommitTransactionCommand()
        └─► CommitTransaction()           ← 见 §"事务提交"
              ├─► RecordTransactionCommit()  ← 写 XLOG_XACT_COMMIT
              │     ├─► TransactionIdCommitTree()  ← 写 pg_xact（CLOG）
              │     └─► XLogInsert(RM_XACT_ID, XLOG_XACT_COMMIT)
              ├─► ProcArrayEndTransaction()       ← 从 MyProc->xid 清掉
              ├─► ReleaseLockIfHeld ...
              └─► AtCommit_Memory()  ← 释放 TopTransactionContext
```

这张图里最值得细看的，是 **StartTransaction** 和 **CommitTransaction** 两个函数。我们一个一个来。

### 起点：StartTransaction

`xact.c:2064` 处的 `StartTransaction` 干这几件事：

```c
static void StartTransaction(void) {
    TransactionState s = &TopTransactionStateData;

    s->state = TRANS_START;
    s->fullTransactionId = InvalidFullTransactionId;   /* 还没拿到 XID */
    s->nestingLevel = 1;
    s->gucNestLevel = 1;
    s->childXids = NULL;

    /* 创建 TopTransactionContext */
    s->curTransactionContext = AllocSetContextCreate(...);

    /* 创建 ResourceOwner，用于追踪锁、buffer pin、文件描述符 */
    s->curTransactionOwner = ResourceOwnerCreate(...);

    /* 如果还没 XID，就调用 AssignTransactionId() 申请 */
    ...
}
```

注意 `fullTransactionId` 一开始是 `Invalid` 的——**事务开始时并不一定立即获得 XID**。只有当第一条真正写数据的 SQL 进来时才会通过 `AssignTransactionId` 申请。这是个重要优化：只读事务不需要 XID，省掉一个 XID 就是省掉一次 CLOG 页初始化。

### 终点：CommitTransaction

`xact.c:2228` 的 `CommitTransaction` 是整条故事的高潮。它的执行顺序被非常严格地安排过：

```c
static void CommitTransaction(void) {
    /* ======== 第 1 阶段：用户代码可以运行 ======== */
    AfterTriggerFireDeferred();           /* 触发器 */
    PreCommit_Portals(false);             /* 关闭游标 */
    PreCommit_on_commit_actions();        /* ON COMMIT 处理 */
    CallXactCallbacks(XACT_EVENT_PRE_COMMIT);

    /* ======== 第 2 阶段：进入临界区，不准出错 ======== */
    HOLD_INTERRUPTS();
    START_CRIT_SECTION();

    /* 写 commit 日志、写 CLOG */
    latestXid = RecordTransactionCommit();

    /* 标记 ProcArray：本事务不再 running */
    ProcArrayEndTransaction(MyProc, latestXid);

    /* ======== 第 3 阶段：清理 ======== */
    ResourceOwnerRelease(... RESOURCE_RELEASE_BEFORE_LOCKS ...);
    ResourceOwnerRelease(... RESOURCE_RELEASE_LOCKS ...);
    smgrDoPendingDeletes(true);           /* 真正删除文件 */
    AtCommit_Notify();
    AtEOXact_GUC(true, 1);                /* 重置 SET 参数 */
    AtEOXact_Memory();                    /* 删除内存沙盒 */
    s->state = TRANS_DEFAULT;
    RESUME_INTERRUPTS();
}
```

这顺序里有**两条铁律**，理解了它们就读懂了 PostgreSQL 的提交协议：

1. **RecordTransactionCommit 必须在 ProcArrayEndTransaction 之前。**  
   因为 `GetSnapshotData` 扫描 ProcArray 时要找出 "xmin < xid < xmax 且仍在跑" 的事务。如果先把自己从 ProcArray 清掉再写 commit 日志，期间另一个事务可能拍快照时看到我们"不存在"，又看不到 commit 日志，就会判我们为"未提交不可见"——**这等价于自己提交了但别人读不到，违反原子性**。

2. **资源释放顺序：先放锁外的资源 → 再放锁 → 最后放 backend 局部资源。**  
   让别的 backend 在等我们锁的时候，能看到"事务已彻底结束"再开始争抢。

### 中间：RecordTransactionCommit 的两步提交

`RecordTransactionCommit` (`xact.c:1315`) 才是真正"持久化"的地方。它做两件大事：

```c
static TransactionId RecordTransactionCommit(void) {
    ...
    START_CRIT_SECTION();

    /* ① 写 XLOG（事务提交日志） */
    XactLogCommitRecord(...);          /* → XLOG_XACT_COMMIT */

    /* ② 写 CLOG（事务提交状态位图） */
    TransactionIdCommitTree(xid, nchildren, children, ...);

    END_CRIT_SECTION();

    /* 更新 shared 最新完成 XID（影响 GetSnapshotData 的 xmax） */
    if (!isParallelWorker)
        MaintainLatestCompletedXid(latestXid);
    ...
}
```

注意**第 ② 步不写 WAL**！它只是把 `pg_xact` 这个 SLRU 的对应位设成 `COMMITTED`。这是有意为之——XLOG 里已经有 COMMIT 记录，恢复时会重放；CLOG 的写只是"运行时状态"，崩溃后可以从 XLOG 重建。

### CLOG（pg_xact）：提交状态位图

`pg_xact`（以前叫 `pg_clog`）是个 SLRU（Simple Least Recently Used）结构，每个 XID 占 2 bit，编码四种状态：

```text
  00 = TRANSACTION_STATUS_IN_PROGRESS     进行中
  01 = TRANSACTION_STATUS_COMMITTED       已提交
  10 = TRANSACTION_STATUS_ABORTED         已回滚
  11 = TRANSACTION_STATUS_SUB_COMMITTED   子事务已提交（待顶层合并）
```

源码 `clog.c:62`：

```c
#define CLOG_BITS_PER_XACT      2
#define CLOG_XACTS_PER_BYTE     4
#define CLOG_XACTS_PER_PAGE     (BLCKSZ * CLOG_XACTS_PER_BYTE)
```

每页 8K * 4 = 32K 个 XID。每两个 bit 的语义，就是 MVCC 的"门牌号查询表"——任何一次 `HeapTupleSatisfiesMVCC` 都要问它"这个 xmin 提交了吗？"

---

## 回滚时发生了什么？

回滚比提交简单，因为**回滚的 WAL 可以不刷盘**——崩溃恢复默认按"未提交"处理即可。`xact.c:1754` 的 `RecordTransactionAbort`：

```c
static TransactionId RecordTransactionAbort(bool isSubXact) {
    TransactionId xid = GetCurrentTransactionIdIfAny();

    /* 没拿到 XID 就不写任何日志（只读事务嘛） */
    if (!TransactionIdIsValid(xid))
        return InvalidTransactionId;

    /* 已经 commit 过了？致命错误 */
    if (TransactionIdDidCommit(xid))
        elog(PANIC, "cannot abort transaction %u, it was already committed", xid);

    START_CRIT_SECTION();
    /* 写 XLOG_XACT_ABORT，但不要求 fsync */
    XactLogAbortRecord(...);
    /* 把 CLOG 标记为 ABORTED */
    TransactionIdAbortTree(xid, nchildren, children);
    END_CRIT_SECTION();
    ...
}
```

回滚后还要做的"扫尾"在 `AbortTransaction` (`xact.c:2809`) 和 `CleanupTransaction` (`xact.c:3009`)：

```c
static void AbortTransaction(void) {
    ...
    AtAbort_Memory();                      /* 切到 TransactionAbortContext */
    AtEOXact_Buffers(false);               /* 释放所有 buffer pin */
    AtEOXact_RelationCache(false);         /* 失效 relcache */
    AtEOXact_Inval(false);                 /* 失效 catcache */
    ResourceOwnerRelease(... LOCKS ...);   /* 释放所有锁 */
    smgrDoPendingDeletes(false);           /* 删除临时文件 */
}

static void CleanupTransaction(void) {
    AtEOXact_Snapshot(false, true);        /* 释放 snapshot */
    AtEOXact_PgStat(true, ...);
    /* ...清理 GUC、ComboCid、Memory、ApplyLauncher... */
    s->state = TRANS_DEFAULT;
}
```

回滚的核心是**不信任任何用户级改动**：所有 buffer pin 一律释放，所有 catalog cache 一律失效，所有锁全部丢弃。这是 PG 长期不变的设计原则。

---

## 子事务（SAVEPOINT）：嵌套的迷你事务

子事务的代码在 `xact.c:5067` 起。一个 `SAVEPOINT s1` 会做这些事：

```c
void DefineSavepoint(const char *name) {
    /* 创建一个新的 TransactionStateData，压栈到 parent 上 */
    TransactionState s = palloc0(sizeof(TransactionStateData));
    s->name = pstrdup(name);
    s->savepointLevel = ...;
    s->parent = CurrentTransactionState;
    CurrentTransactionState = s;
    s->blockState = TBLOCK_SUBBEGIN;

    /* 真正工作等到 CommitTransactionCommand → StartSubTransaction */
}

static void StartSubTransaction(void) {
    s->state = TRANS_START;

    AtSubStart_Memory();                   /* 创建子上下文 */
    AtSubStart_ResourceOwner();            /* 创建子 ResourceOwner */
    AfterTriggerBeginSubXact();

    s->state = TRANS_INPROGRESS;

    /* 调用 SUBXACT_EVENT_START_SUB 回调 */
    CallSubXactCallbacks(SUBXACT_EVENT_START_SUB, s->subTransactionId,
                         s->parent->subTransactionId);
}
```

子事务的关键特征：

- **栈式内存上下文**：每个子事务有自己的 `MemoryContext` 和 `ResourceOwner`，回滚时一层层释放。
- **共享 XID 子树**：子事务自己也会分配 XID（`AssignTransactionId` 在子事务路径同样被调用），但顶层提交时才把整个 XID 树一起在 CLOG 里标记为 COMMITTED（`TransactionIdCommitTree` 处理）。
- **嵌套回滚**：`ROLLBACK TO s1` 只回滚 s1 之后的部分，s1 之前的仍然保留。

可以用一张图看清子事务的"树状 XID"：

```text
  顶层事务 XID=100
  │
  ├── SAVEPOINT a (子事务 XID=101)
  │     ├── UPDATE ... ← xmin=101
  │     └── INSERT ... ← xmin=101
  │
  ├── SAVEPOINT b (子事务 XID=102)
  │     └── UPDATE ... ← xmin=102
  │
  ROLLBACK TO a
  │
  └── SAVEPOINT c (子事务 XID=103，复用 b 释放的 XID 槽位)
        └── UPDATE ... ← xmin=103

  COMMIT
    ├─► TransactionIdCommitTree(xid=100, children=[101, 103])
    │     ↑ 一次原子地把整棵子树在 CLOG 里标记为 COMMITTED
    └─► XLOG_XACT_COMMIT（带 XINFO_HAS_SUBXACTS flag）
```

注意 ROLLBACK TO 后我们又新开了子事务 c，但 c 的 XID=103 是新的——之前 b 用的 102 被 PG "复用了"。PG 的 XID 分配是简单的 `nextXid++`，永远向前走，不会复用。

---

## 两阶段提交：跨库事务的桥梁

两阶段提交（2PC）是 PG 留给分布式事务的"逃生口"。`PREPARE TRANSACTION 'gid'` 的工作流：

```text
  协调者（应用）                PostgreSQL                    其他 PG / 其他 DB
  ──────────                   ──────────                    ──────
  BEGIN
  UPDATE pg1.t ...
  PREPARE TRANSACTION 'g1'
    │                          EndTransactionBlock + PrepareTransactionBlock
    │                              blockState = TBLOCK_PREPARE
    │                          PrepareTransaction:
    │                            ├─► GXactCreate('g1', xid)    ← 写 pg_twophase
    │                            ├─► XactLogPrepareRecord      ← XLOG_XACT_PREPARE
    │                            └─► ProcArrayEndTransaction    ← 进程退出，但 xid 还活着
    │
  UPDATE pg2.t ...                                            (其他 DB 的事)
  PREPARE TRANSACTION 'g2'                                     ...
  
  收到所有 PREPARE 成功
  │
  ├─► COMMIT PREPARED 'g1'                                     (发到 PG1)
    │                       RecordTransactionCommitPrepared
    │                         ├─► CLOG: COMMITTED
    │                         ├─► XLOG_XACT_COMMIT_PREPARED
    │                         └─► RemoveTwoPhaseFile('g1')
  │
  └─► COMMIT PREPARED 'g2'                                     ...
```

关键差异：

- `PREPARE` 之后，**当前后端进程完全可以退出**——事务状态已被序列化到 `pg_twophase` 目录下（文件名形如 `xact_<xid>`）。
- 重启后 `StandbyRecoverPreparedTransactions` 会恢复所有 prepared xact，等协调者发 `COMMIT PREPARED` / `ROLLBACK PREPARED`。
- 如果协调者宕机，这些 prepared 事务会一直占着锁直到手动干预——这是 2PC 的固有问题。

`twophase.c` 的 `PrepareTransaction` (`xact.c:2515`) 干的就是这套：

```c
static void PrepareTransaction(void) {
    TransactionId xid = GetCurrentTransactionId();
    ...
    gxact = MarkAsPreparing(xid, &prepareGID, ...);   /* 写 pg_twophase */
    ...
    /* 写 XLOG_XACT_PREPARE */
    XactLogPrepareRecord(gxact->prepare_end_lsn, ...);
    ...
}
```

---

## XID 回卷：32 位的代价

XID 是 32 位的，从 3 开始递增（1 是 Bootstrap，2 是 Frozen）。PG 用一个 64 位的 `FullTransactionId` 来扛 epoch，但 `t_xmin`/`t_xmax` 字段还是 32 位。

这就带来一个隐患：**当新 XID 追上老 XID 时，比较会反转**。PostgreSQL 用 `TransactionIdPrecedes`（基于 2^31 半圆比较）处理，但前提是 **"没有人还在用回卷边界附近的 XID"**。

保护机制在 `varsup.c` 的 `GetNewTransactionId`：

```c
TransactionId xid = XidFromFullTransactionId(full_xid);

/* 过了 xidVacLimit：触发 autovacuum */
if (TransactionIdFollowsOrEquals(xid, TransamVariables->xidVacLimit))
    SendPostmasterSignal(PMSIGNAL_START_AUTOVAC_LAUNCHER);

/* 过了 xidWarnLimit：WARNING */
if (TransactionIdFollowsOrEquals(xid, xidWarnLimit))
    ereport(WARNING, "database ... must be vacuumed within %u transactions", ...);

/* 过了 xidStopLimit：拒绝分配新 XID */
if (TransactionIdFollowsOrEquals(xid, xidStopLimit))
    ereport(ERROR, "database is not accepting commands that assign new "
                   "transaction IDs to avoid wraparound data loss", ...);
```

距离 `xidWrapLimit` 大约 **2.31 亿（2^31）** 个事务就是硬上限。所以运维上**永远不能让 autovacuum 失效**——一旦跨过这条线，PG 会主动停摆，要求做 anti-wraparound VACUUM。

```text
   ─────────► 时间
   │
   │   21 亿事务的"安全窗口"
   │
   │   ┌──── xidWarnLimit ────────────────► 触发 WARNING
   │   │
   │   │   ┌──── xidVacLimit ─────────────► 触发 autovacuum
   │   │   │
   │   │   │   ┌──── xidStopLimit ────────► 拒绝新 XID
   │   │   │   │
   ▼   ▼   ▼   ▼
  nextXid 不断推进
```

这就是为什么冻结（Freezing）在《MVCC》一文里那么重要——把老 XID 标记为 FrozenTransactionId 是回卷保护的实际执行人。

---

## 总结：两台机器，两层世界

回到一开始那张图。PostgreSQL 的事务不是一句话的事，它是**两台状态机协同**的精密仪器：

```text
                          用户视角
                          ────────
   BEGIN → SQL → SQL → ... → COMMIT
   │        │      │          │
   ▼        ▼      ▼          ▼
  TBLOCK_BEGIN  TBLOCK_INPROGRESS  TBLOCK_END
                          │
                          ▼
                         内核视角
                         ────────
   TRANS_START → TRANS_INPROGRESS → TRANS_COMMIT → TRANS_DEFAULT
        │              │                  │
        │              │                  ├─► RecordTransactionCommit
        │              │                  │     ├─► XLOG_XACT_COMMIT
        │              │                  │     └─► CLOG: COMMITTED
        │              │                  ├─► ProcArrayEndTransaction
        │              │                  └─► AtCommit_Memory / Lock
        │              │
        │              ├─► 每次写数据：
        │              │     ├─► heap_update → heap_insert
        │              │     ├─► XLogInsert
        │              │     └─► CommandCounterIncrement
        │              │
        │              └─► 每次拍快照：
        │                    └─► GetSnapshotData → xip[]
        │
        └─► 只读事务可以一辈子不申请 XID
```

记住这几条经验法则，下次排查事务问题时能少走很多弯路：

1. **BEGIN 不开事务**——它只是设置 blockState，真正的 `StartTransaction` 在下一条 SQL 才发生。这对排查"为什么 BEGIN 之后立刻报错事务没回滚"特别有用。
2. **CommitTransaction 里的顺序是铁律**——`RecordTransactionCommit` 必须在 `ProcArrayEndTransaction` 之前，否则违反原子性。
3. **回滚不写日志刷盘**——除非有 `synchronous_commit = on` 的强制要求。
4. **SAVEPOINT 用栈式状态**——每个子事务有自己的 XID，COMMIT 时一次性把整棵子树标记。
5. **PREPARE 后进程退出没关系**——事务已被序列化到 `pg_twophase`。
6. **永远不要关掉 autovacuum**——否则 XID 回卷会让数据库主动停摆。

事务是数据库最基础的"原子单位"，但 PostgreSQL 用两台状态机把它实现得相当优雅。下一次当你执行 `BEGIN`，想想这个 5 个字符的命令背后，那两台机器正在悄悄开机，等着为你服务。

---

## 参考资料

- PostgreSQL 17 源码：
  - `src/backend/access/transam/xact.c` — `BeginTransaction`、`CommitTransaction`、`AbortTransaction`
  - `src/include/access/xact.h` — `TransState`、`TBlockState`、`xl_xact_commit`
  - `src/backend/access/transam/varsup.c` — `GetNewTransactionId`（XID 分配）
  - `src/backend/access/transam/clog.c` — `pg_xact`（CLOG）
  - `src/backend/access/transam/twophase.c` — 两阶段提交
  - `src/backend/storage/ipc/procarray.c` — `ProcArrayEndTransaction`
- 《PostgreSQL 15 内部原理》, Egor Rogov
- [PostgreSQL Documentation — Transaction Processing](https://www.postgresql.org/docs/current/transaction-iso.html)
