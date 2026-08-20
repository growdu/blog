# PostgreSQL MVCC：一条数据是如何拥有"分身术"的

| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 初稿，结合 PostgreSQL 17 源码 | 2026-08-20 |

想象一下，你正坐在一家 24 小时营业的自助图书馆里。顾客们进进出出，有人想改书里的一段话，有人想删掉某一页。如果每改一次都要把整本书收回柜台、贴上封条、再发出去，那这家图书馆基本就瘫痪了。

PostgreSQL 选择了一种更"魔法"的思路：**书从来不被收回**。你看到的永远是当时那个时刻的版本，**不管后来谁改了它**。改的人只是在旁边塞了一本"修订版"，还悄悄在新书封面上记了一笔："这本是被 X 先生改过的旧版"。直到确认没有人还在看旧版本时，旧书才会被回收站悄悄收走。

这就是 **MVCC（Multi-Version Concurrency Control，多版本并发控制）** 的全部核心。本文会沿着 `~/cwork/postgresql/src/backend/access/heap/` 的源码，把这条魔法一步步拆给你看。

---

## 为什么我们需要 MVCC

在 MVCC 出现之前，主流的并发控制思路是**两阶段锁（2PL）**。读加共享锁（S），写加排他锁（X），读写互斥。它的逻辑非常符合直觉：

```text
事务 A 读数据 ──┐
                  ├──> 冲突！A 必须等 B 释放锁
事务 B 写数据 ──┘
```

问题也出在这里：**只要有人"握笔"，其他人连"看"都不被允许**。一个长时间运行的报表查询，会把整张表锁住，让所有写入排队等到天荒地老。这在高并发系统里几乎是灾难。

MVCC 的解法是**让读和写走两条独立的路**：

- 写的人造一个**新版本**，不碰旧版本。
- 读的人拿到一个**快照**（snapshot），照着快照读，不受别人干扰。

读不阻塞写，写也不阻塞读。大家井水不犯河水。

下面这张图可以让你一眼看清两者区别：

```text
   ────── 两阶段锁 2PL ──────               ────── MVCC ──────
       T1    T2    T3                          T1    T2    T3
  r1   ████                                     ████
  r2        ████                                       ████
  w1                                            ↑ 创建 v2
  w2                  ████                              ↑ 创建 v3

  写者阻塞所有读者                          读者永远不会被写阻塞
```

---

## MVCC 的核心思想：版本而非锁

把刚才图书馆的比喻再具体一点。一行数据 `users(id, name)`，假设 `id=1` 的名字叫 `Alice`，它可能会经历这些变更：

```text
时刻 t1：Alice 提交了 INSERT
        id=1, name='Alice'    （版本 v1）

时刻 t2：Bob 把名字改成 Bob
        id=1, name='Alice'    （版本 v1，被废弃但仍存在）
        id=1, name='Bob'      （版本 v2，新写入）

时刻 t3：Carol 把名字删了
        id=1, name='Alice'    （版本 v1，死）
        id=1, name='Bob'      （版本 v2，死）
        ─────────────────    （id=1 不再存在）
```

注意：**v1、v2 都还在磁盘上**！它们并没有被删除，只是被打上了"已废弃"的标记。这就是"多版本"三个字的字面意思。

那么问题来了：

1. 一行数据怎么记下"我是谁生的、谁把我干掉的"？
2. 一个事务怎么决定哪个版本对它"可见"？

答案都在元组头里。

---

## 元组的"身份证"：HeapTupleHeaderData

每一条堆表（heap）记录的最前面，都有一小段元数据，叫做 **tuple header**。它不存用户数据，只用来回答"这条记录的来龙去脉"。

源码定义在 `src/include/access/htup_details.h`：

```c
typedef struct HeapTupleFields
{
    TransactionId t_xmin;       /* inserting xact ID */
    TransactionId t_xmax;       /* deleting or locking xact ID */

    union
    {
        CommandId    t_cid;     /* inserting or deleting command ID, or both */
        TransactionId t_xvac;   /* old-style VACUUM FULL xact ID */
    }            t_field3;
} HeapTupleFields;
```

我们可以把它想象成一张"出生证明 + 死亡证明"：

```text
┌──────────────────────────────────────────────────────────┐
│                    HeapTupleHeaderData                    │
├──────────────┬──────────────┬───────────┬────────────────┤
│   t_xmin     │   t_xmax     │ t_cid/t_xvac│   t_ctid      │
│ (谁生了我)   │ (谁杀了我)   │ (命令号)    │  (我的新地址)  │
└──────────────┴──────────────┴───────────┴────────────────┘
```

每个字段的含义：

| 字段 | 含义 | 类比 |
| --- | --- | --- |
| `t_xmin` | 插入这条记录的事务 ID（XID） | 出生证明上的"父亲" |
| `t_xmax` | 删除（或锁定）这条记录的事务 ID | 死亡证明上的"凶手" |
| `t_cid` | 命令 ID（CommandId），区分同一事务里的多条语句 | 同一父亲的不同孩子序号 |
| `t_ctid` | 当前行指向的**新版本**位置 | "想找最新版请翻到第 X 页" |

除了这三个事务字段外，还有一个非常关键的 `t_infomask`（uint16 标志位），它在 `htup_details.h` 中定义：

```c
#define HEAP_XMIN_COMMITTED       0x0100   /* t_xmin 已提交 */
#define HEAP_XMIN_INVALID         0x0200   /* t_xmin 已回滚 */
#define HEAP_XMIN_FROZEN          0x0300   /* t_xmin 永远可见（已冻结） */
#define HEAP_XMAX_COMMITTED       0x0400   /* t_xmax 已提交 */
#define HEAP_XMAX_INVALID         0x0800   /* t_xmax 已回滚 */
#define HEAP_XMAX_IS_MULTI        0x1000   /* t_xmax 是 MultiXactId */
```

这些位叫做 **Hint Bits（提示位）**。它们相当于元组头上"盖的几个章"：插入者已提交、删除者已提交……这样下次有人来读这条记录时，**不用每次都去翻日志**就能立刻知道结论。

---

## 一个元组的一生：插入、删除、更新

我们用一个具体例子走完一个元组的全部生命周期。

### 准备一张表演台

```sql
CREATE TABLE account (
    id   int PRIMARY KEY,
    name text,
    balance int
);

INSERT INTO account VALUES (1, 'Alice', 100);
```

假设这条 INSERT 由事务 XID=100 完成。磁盘上的那一行长这样：

```text
┌─────────────────────────────────────────────────────────┐
│  HeapTuple (id=1, name='Alice', balance=100)            │
├─────────────┬─────────────┬────────────┬────────────────┤
│ t_xmin=100  │ t_xmax=0    │ t_cid=0    │ t_ctid=(0,1)   │
│  (自己)     │  (没被杀)   │            │  (指向自己)    │
└─────────────┴─────────────┴────────────┴────────────────┘
        ↑                       ↑
   盖个 HEAP_XMIN_COMMITTED 章   HEAP_XMAX_INVALID 已置位
```

> `t_xmax=0` 表示无效（`InvalidTransactionId`），相当于"无凶杀"。

### DELETE：给元组"盖个死亡章"

事务 XID=200 执行：

```sql
DELETE FROM account WHERE id = 1;
```

PostgreSQL 实际上并没有把这条记录抹掉，而是**原地修改 t_xmax**：

```text
┌─────────────────────────────────────────────────────────┐
│  HeapTuple (id=1, name='Alice', balance=100)            │
├─────────────┬─────────────┬────────────┬────────────────┤
│ t_xmin=100  │ t_xmax=200  │ t_cid=0    │ t_ctid=(0,1)   │
│  committed  │ (自己)      │            │  (指向自己)    │
└─────────────┴─────────────┴────────────┴────────────────┘
                                        ↑
                                此时盖 HEAP_XMAX_INVALID
                                还没决定生死
```

XID=200 提交后，这条记录就被盖上 **HEAP_XMAX_COMMITTED** 章——**正式死亡**。但磁盘上的字节一个都没动，它就这么"挂着"等着被 VACUUM 回收。

### UPDATE：版本链的诞生

事务 XID=300 执行：

```sql
UPDATE account SET name='Alice_v2' WHERE id = 1;
```

PostgreSQL 不会"在原地改"。它做两件事：

1. **在旧版本上写 t_xmax，标记被自己"杀"了**。
2. **插一条新版本到表中（可能是同一页，也可能不同页）**，新版本的 t_xmin 写自己。

如果新版本被插入到同一页的另一位置，旧版本的 `t_ctid` 就指向新版本。这就是**版本链**：

```text
┌────────────────────────┐    t_ctid     ┌────────────────────────┐
│ v1 (page 0, item 1)    │ ────────────► │ v2 (page 0, item 4)    │
│ xmin=100, xmax=300     │               │ xmin=300, xmax=0       │
│ name='Alice'           │               │ name='Alice_v2'        │
│ (已死，盖 XMAX_COMMIT) │               │ (活着)                  │
└────────────────────────┘               └────────────────────────┘
```

源码里这条链子的写法在 `src/backend/access/heap/heapam.c` 的 `heap_update` 中：

```c
/* 1) 把新版本插进去 */
newtup = heap_form_tuple(tupdesc, values, nulls);
newtup->t_data->t_choice.t_heap.t_xmin = xid;        /* 自己的 XID */
newtup->t_data->t_choice.t_heap.t_xmax = InvalidTransactionId;

/* 2) 修改旧版本，让它指向新版本 */
oldtup.t_data->t_choice.t_heap.t_xmax = xid;
oldtup.t_data->t_ctid = newtup->t_self;
MarkBufferDirty(buffer);
```

把这两步合并起来，就是 PG 里"UPDATE 等于 DELETE+INSERT"这句老话的真实含义：**它物理上真的就是 DELETE+INSERT**，只是在用户看来像原地改。

---

## 快照（Snapshot）：每个事务眼中的世界

有了版本链，下一个问题：**一个事务怎么决定"对我来说，哪一版可见"？**

PG 给每个事务发一张"通行证"，叫 **Snapshot**。结构定义在 `src/include/utils/snapshot.h`：

```c
typedef struct SnapshotData
{
    TransactionId xmin;     /* 所有 < xmin 的事务，对我都已"完成" */
    TransactionId xmax;     /* 所有 >= xmax 的事务，对我都"未发生" */
    TransactionId *xip;     /* [xmin, xmax) 之间正在进行的事务们 */
    uint32        xcnt;     /* xip 数组长度 */
    TransactionId *subxip;  /* 子事务们 */
    int32         subxcnt;
    CommandId     curcid;   /* 当前命令 ID */
    ...
} SnapshotData;
```

把它翻译成时间线上的窗口：

```text
          ◀──── 这个事务能看到的世界 ────►

──┬──────────┬─────────────────┬───────────┬──────► 时间
   已提交老古董   正在跑的事务们      最新已分配
                (在 xip[] 里)        但未提交
                                  ↑
                                 xmax
   ↑                              ↑
  xmin                  xmax 是 latestCompletedXid + 1
```

判定一条记录 xmin 是否可见，三步走：

```text
1. xmin < snapshot.xmin    ──> 老古董，一定可见
2. xmin >= snapshot.xmax   ──> 未来人，不可见
3. xmin ∈ snapshot.xip[]   ──> 还在跑，不可见（快照拍摄时尚未提交）
4. 否则                     ──> 已提交，可见
```

源码 `src/backend/storage/ipc/procarray.c` 的 `GetSnapshotData()` 干的就是这件事——它扫描所有 PG 进程，把正在运行的事务 XID 收进 `xip` 数组：

```c
xmax = XidFromFullTransactionId(latest_completed);
TransactionIdAdvance(xmax);                  /* xmax = 最新已完成 + 1 */

xmin = xmax;
if (TransactionIdIsNormal(myxid) && NormalTransactionIdPrecedes(myxid, xmin))
    xmin = myxid;                            /* 包括自己 */

/* 把所有正在跑的事务 XID 收进 xip[] */
for (int pgxactoff = 0; pgxactoff < numProcs; pgxactoff++)
{
    TransactionId xid = UINT32_ACCESS_ONCE(other_xids[pgxactoff]);
    ...
    if (xid != InvalidTransactionId && pgxactoff != mypgxactoff)
        xip[count++] = xid;
}

snapshot->xmin = xmin;
snapshot->xmax = xmax;
snapshot->xcnt = count;
```

---

## 可见性判定：HeapTupleSatisfiesMVCC 全流程

快照拿到之后，每次扫描一行都要走一遍 `HeapTupleSatisfiesMVCC`。它在 `src/backend/access/heap/heapam_visibility.c`：

```c
static bool
HeapTupleSatisfiesMVCC(HeapTuple htup, Snapshot snapshot, Buffer buffer)
{
    HeapTupleHeader tuple = htup->t_data;
    ...
    if (!HeapTupleHeaderXminCommitted(tuple))     /* xmin 没提交？ */
    {
        if (HeapTupleHeaderXminInvalid(tuple))    /* xmin 已回滚？ */
            return false;
        ...
        else if (XidInMVCCSnapshot(t_xmin, snapshot))   /* 还在跑？ */
            return false;
        else if (TransactionIdDidCommit(t_xmin))  /* 已提交？ */
            SetHintBits(... HEAP_XMIN_COMMITTED ...);
        else                                       /* 崩溃了？ */
            return false;
    }

    /* 到这里，插入事务已经提交 */

    if (tuple->t_infomask & HEAP_XMAX_INVALID)     /* 没被杀？ */
        return true;
    if (HEAP_XMAX_IS_LOCKED_ONLY(...))             /* 只被锁没被杀？ */
        return true;
    ...
    if (XidInMVCCSnapshot(t_xmax, snapshot))      /* 杀我的人还在跑？ */
        return true;                               /* 我暂时还活着 */
    if (TransactionIdDidCommit(t_xmax))            /* 杀我的人已提交？ */
        return false;                              /* 我真的死了 */
    /* 杀我的人回滚/崩溃 */
    return true;
}
```

把它整理成流程图：

```text
                  ┌──────────────────────────┐
                  │ 扫描到一条 tuple，        │
                  │ 准备判断它对我可见吗？    │
                  └─────────────┬────────────┘
                                ▼
               ┌────────────────────────────┐
        ─────► │ 插入者 xmin 是否已提交？    │
               └───────┬────────────┬───────┘
                  否   │            │  是
                       ▼            ▼
                 ┌─────────┐    ┌──────────────┐
                 │ 还在跑？ │    │ 杀我的人       │
                 │ → 不可见 │    │ t_xmax = ?     │
                 └─────────┘    └──┬──────┬─────┘
                                    │      │
                            无效/被锁 │      │ 有效
                                    ▼      ▼
                              ┌────────┐ ┌──────────────┐
                              │ 可见 ✓ │ │ 杀我的人      │
                              └────────┘ │ 还在跑？      │
                                         │ → 还可见 ✓    │
                                         │ 已提交？      │
                                         │ → 死了 ✗     │
                                         │ 回滚/崩溃？   │
                                         │ → 还可见 ✓    │
                                         └──────────────┘
```

---

## 例子：两个事务的赛跑

光说不练假把式。我们让两个事务对一行数据同时动刀，看快照如何保护彼此。

```sql
-- 会话 1                                 -- 会话 2
BEGIN;
SELECT pg_snapshot_xmin(pg_current_snapshot());
-- 假设此时 xmin=500, xmax=510,
-- xip={505, 508}
                                           BEGIN;
                                           UPDATE account
                                             SET balance = 200
                                             WHERE id = 1;
                                           -- XID=508，写入了 v2
                                           -- 但还没提交
SELECT balance FROM account
  WHERE id = 1;
COMMIT;
```

**会话 1 看到的元组状态**：

```text
  时刻 T1（会话 1 拿快照）
  ┌────────────────────────────────────────┐
  │  v1: xmin=100, xmax=508,  xctid→v2     │  ← 在 page 上
  │      hint: XMIN_COMMITTED 已盖         │
  │            XMAX_INVALID  还没盖        │
  └────────────────────────────────────────┘

  会话 1 的 snapshot: {xmin=500, xmax=510, xip=[505,508]}

  HeapTupleSatisfiesMVCC 跑一遍：
    xmin=100 < xmin=500          ✓ 老古董，跳过提交判断
    xmax=508  ≥ snapshot.xmin=500
    xmax=508 ∈ snapshot.xip     ✓ 还在跑 → 当作"没杀"
    → 返回 true：v1 对我可见，balance=100
```

**关键来了**：尽管会话 2 已经写了 v2（balance=200），但会话 1 眼里 v1 仍然"活着"。这就是 MVCC 的精髓——**读不会被写阻塞，看到的是快照时刻的一致状态**。

然后会话 1 提交，会话 2 也提交。再过一会儿，VACUUM 发现 v1 已经被所有正在运行的事务抛弃，把它物理回收。

---

## 不同隔离级别下的 MVCC 行为

PG 一共支持 4 种隔离级别（`src/backend/storage/ipc/procarray.c` 和 `src/backend/commands/variable.c` 决定默认值）：

| 隔离级别 | 何时拍快照 | 看到的版本 |
| --- | --- | --- |
| Read Uncommitted | （PG 里等同 RC） | 已提交 |
| **Read Committed（默认）** | **每条语句开头拍一次** | 那一刻已提交 |
| Repeatable Read | 事务第一条语句拍一次 | 全程不变 |
| Serializable | 同 RR + SSI 校验 | 全程不变 |

PG 默认是 **Read Committed**。这意味着**每个 SELECT 都会重新拿一张快照**。

### 经典的可重复读 vs 读已提交对比

```sql
-- 会话 1                                  -- 会话 2
SET TRANSACTION ISOLATION LEVEL
  REPEATABLE READ;
BEGIN;
                                            BEGIN;
                                            UPDATE account
                                              SET balance=200
                                              WHERE id=1;
                                            COMMIT;
SELECT balance FROM account
  WHERE id=1;
-- 100  ← 看到的是事务开始时的版本
SELECT balance FROM account
  WHERE id=1;
-- 100  ← 还是 100，RR 的承诺
COMMIT;
```

如果把会话 1 改成 Read Committed：

```text
第 1 个 SELECT：会话 2 已 commit → 看到 200
第 2 个 SELECT：依然 200

但是！如果第 1 个 SELECT 时会话 2 还没 commit，你看到 100；
  会话 2 commit 之后再 SELECT，又会变成 200。
```

RC 下"每次语句一个快照"的设计，会带来一个经典的副作用——**同一条 SELECT 在 RC 下可能两次返回不同行数**：

```sql
-- 会话 1
BEGIN;
SELECT count(*) FROM big_table;       -- 返回 1000
-- 此时会话 2 INSERT 了 500 行并 commit
SELECT count(*) FROM big_table;       -- 返回 1500！
```

这一点在 RR 下绝不会发生——RR 下两次 `count(*)` 永远相同。

> PG 的 RR 已经能防住**脏读、不可重复读、幻读**，代价是没有像 ANSI SQL 那样加间隙锁；它就是靠"一张永不换的快照"实现的。Serializable 在 RR 的基础上加了 SSI（Serializable Snapshot Isolation），通过跟踪"读写依赖图"检测会不会出现"危险结构"，违规则 abort。

---

## 死元组清理：VACUUM

到这一步你可能已经意识到一个严重问题：**UPDATE/DELETE 越多，磁盘上的"尸体"就越多**。

```text
  一行记录经历 5 次 UPDATE 后的版本链：
  v1 ←─t_ctid─ v2 ←─t_ctid─ v3 ←─t_ctid─ v4 ←─t_ctid─ v5
   💀          💀          💀          💀          🟢 活

  如果没有清理，最终一张表 99% 都是尸体。
```

VACUUM 就是负责"打扫房间"的后台工人。它的判断逻辑在 `src/backend/access/heap/heapam_visibility.c` 的 `HeapTupleSatisfiesVacuum`：

```c
TM_Result
HeapTupleSatisfiesVacuum(HeapTuple htup, TransactionId OldestXmin, Buffer buffer)
{
    res = HeapTupleSatisfiesVacuumHorizon(htup, buffer, &dead_after);
    if (res == HEAPTUPLE_RECENTLY_DEAD)
    {
        if (TransactionIdPrecedes(dead_after, OldestXmin))
            res = HEAPTUPLE_DEAD;          /* 老尸体，可回收 */
    }
    ...
}
```

关键概念：

- **`OldestXmin`**：当前所有活跃事务里**最早开始**的那个 XID。比它更老的 xmax，就意味着**没有人在看这个版本了**，可以放心回收。
- **dead_after**：被 xmax 干掉之后，要等到 xmax ≥ OldestXmin 才算"真的死透了"。

回到我们的图书馆比喻：借书卡上写的是"最后归还日"。只要还有人说"我还没还书"，旧版本就不能动。等到所有人都还完了，再清理。

### HOT（Heap-Only Tuples）：让 UPDATE 更便宜

如果每次 UPDATE 都把整行复制一遍，索引会全部失效（指向旧 TID）。PG 用 HOT 优化：**同页内的 UPDATE 不更新索引**，只在页面内建立 `t_ctid` 链。这要求新版本不能有任何被修改的索引键，否则降级回普通 UPDATE。

```text
  普通 UPDATE：
  ┌────────────┐    ┌────────────┐
  │ index entry│──► │ v2  新页    │      ← 索引全部失效要更新
  └────────────┘    └────────────┘

  HOT UPDATE（无索引列变化）：
  ┌────────────┐    ┌────────────┐
  │ index entry│──► │ v1 旧行    │──ctid──► v2 同页新行
  └────────────┘    └────────────┘
                                 ↑ 新行有 HOT 元组头标记
```

HOT 由 `src/backend/access/heap/heapam.c` 的 `heap_update` 配合 `rewrite_heap_dead_tuple` 处理。

---

## 提示位（Hint Bits）：让下一次判更快

回到 `HeapTupleSatisfiesMVCC` 的代码，你会发现这一行反复出现：

```c
SetHintBits(tuple, buffer, HEAP_XMIN_COMMITTED,
            HeapTupleHeaderGetRawXmin(tuple));
```

为什么每判一次就要"盖章"？因为 `pg_xact`（事务提交日志 CLOG）查起来是**有锁竞争的全局操作**。如果能盖个章在元组头里，下次再扫到它时，直接看 `t_infomask & HEAP_XMIN_COMMITTED` 就行，连 CLOG 都不用查：

```text
  没盖 Hint 时每次扫描要：
    ┌─────────┐  ┌────────────┐  ┌─────────┐
    │ 元组头   │─►│ 查 pg_xact │─►│ 决定结果 │
    └─────────┘  └────────────┘  └─────────┘

  盖了 Hint 之后：
    ┌─────────┐  ┌──────────────┐
    │ 元组头   │─►│ 看 t_infomask │─► 走人
    └─────────┘  └──────────────┘
```

但 Hint Bits 是**写操作**：要在 buffer 上设脏页。所以 PG 故意把盖章推迟到**不得不查 CLOG 的时候**才盖（见 `heapam_visibility.c` 顶部的注释）。这条策略既减小了热点页的写放大，又避免了不必要的锁竞争。

### 冻结（Freezing）：让老事务 ID 重生

PG 的 XID 是 32 位循环使用的。当一个事务距离当前 XID 超过 **2.31 亿（2^31）** 时，它在比较时就会被当成"未来"事务，**MVCC 直接乱套**。

所以 PG 在 VACUUM 时做 **anti-wraparound vacuum**：把那些老到不会有人再看的元组的 `t_xmin` 直接置为 `FrozenTransactionId`（2），并在 `t_infomask` 里盖上 `HEAP_XMIN_FROZEN` 章，相当于"这位父亲永远存在，谁看都可见"。

源码定义：

```c
#define FrozenTransactionId  ((TransactionId) 2)
```

触发条件在 `src/backend/storage/ipc/procarray.c` 的 `GetOldestNonRemovableTransactionId`：

```text
  datfrozenxid < (latestCompletedXid - 200_000_000)
                       ↓
       autovacuum 强制做 anti-wraparound 扫描
```

否则数据库会主动停摆，报错：

```text
  ERROR: database is not accepting commands to avoid wraparound
         data loss in database with OID ...
```

---

## 总结：MVCC 是一把双刃剑

把整篇文章的脉络浓缩在一张图里：

```text
                       ┌────────────────────────┐
                       │      PostgreSQL        │
                       │        MVCC            │
                       └──────────┬─────────────┘
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
   │  元组头字段  │         │   快照机制   │         │  垃圾回收    │
   │ t_xmin      │         │ snapshot.xmin│         │ VACUUM      │
   │ t_xmax      │         │ snapshot.xmax│         │ HOT         │
   │ t_ctid      │         │ xip[]        │         │ 冻结        │
   │ t_infomask  │         │ curcid       │         │             │
   └──────┬──────┘         └──────┬──────┘         └──────┬──────┘
          │ 版本链               │ 可见性窗口            │ 老尸体回收
          └───────────────────────┴───────────────────────┘
                                  │
                                  ▼
                       ┌────────────────────────┐
                       │   HeapTupleSatisfiesMVCC│
                       │  每次访问元组的"守门员"  │
                       └────────────────────────┘
```

MVCC 带来的好处非常实在：

- 读不阻塞写，写不阻塞读，**高并发下吞吐极高**。
- 每个事务看到一致快照，**RR 隔离级无需复杂加锁即可防幻读**。
- 历史版本天然存在，**逻辑解码、时间旅行查询、审计** 都成了可能。

但代价同样真实：

- **UPDATE/DELETE 不真正删除**，导致"表膨胀"，必须依赖 VACUUM。
- **版本链** 在极端 UPDATE 频繁时可能很长，索引扫描时需要 follow ctid。
- **XID 32 位循环使用**，必须定期 freeze 否则停库。
- **长事务会拖死 VACUUM**：因为 OldestXmin 被钉住，老尸体回收不掉。

理解 MVCC 的关键，**不是记住每个字段**，而是建立这三种视角：

1. **元组的视角**：我是被谁生的，被谁杀的，我的下一代在哪？
2. **快照的视角**：在我拍照那一刻，谁已经完成，谁还在跑？
3. **回收的视角**：是不是真的没人再看这个旧版本了？

当你能同时站在这三个视角看同一行数据时，PostgreSQL 的 MVCC 对你来说就不再是魔法，而是一台**井然有序的多版本时钟**。

---

## 参考资料

- PostgreSQL 17 源码：`~/cwork/postgresql/src/backend/access/heap/heapam_visibility.c`
- `src/include/access/htup_details.h` — `HeapTupleHeaderData`
- `src/include/utils/snapshot.h` — `SnapshotData`
- `src/backend/storage/ipc/procarray.c` — `GetSnapshotData`
- `src/backend/access/heap/heapam.c` — `heap_update`
- 《PostgreSQL 15 内部原理》,  Egor Rogov
- [PostgreSQL Documentation — Concurrency Control](https://www.postgresql.org/docs/current/mvcc.html)
