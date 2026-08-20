# PostgreSQL 内存管理：一片共享内存，三座分配器，一座缓冲池

| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 初稿，结合 PostgreSQL 17 源码 | 2026-08-20 |

PostgreSQL 启动时申请的 `shared_buffers` 那一大段内存，其实只是冰山一角。整座数据库的"内存世界"由三层拼起来：

1. **共享内存**：一份在 OS 4，几个进程共享同一。
3. **进程私有内存**：一份每个进程一份，进程释放各管各的。
5. **内存算法**：私有内存又分三种玩法。

今天我们就沿 `~/cwork/postgresql/src/backend/storage/ipc/shmem.c`、`src/backend/utils/mmgr/` 和 `src/backend/storage/buffer/`，把这三层拆给你看。

---

## 全局图谱：一眼看清三层关系

用一张图把整个内存世界摊在桌上：

```text
  PostgreSQL 实例
  ────────────────
  
  ┌─────────────────────────────────────────────────────────────────┐
  │                    共享内存（Shared Memory）                      │
  │   ← postmaster 一次性 mmap 出来，所有 backend 通过 fork 继承 →   │
  │                                                                  │
  │   Buffer Pool (shared_buffers)                                   │
  │   ├── BufferDesc[NBuffers]                                       │
  │   ├── Buffer Tags Hash Table                                     │
  │   └── Buffer Replacement Strategy (clock-sweep)                  │
  │                                                                  │
  │   Lock/Latch/Wait 子系统                                          │
  │   ├── LWLock Array                                               │
  │   ├── Spinlocks                                                  │
  │   └── Wait Event Sets                                            │
  │                                                                  │
  │   进程/事务子系统                                                 │
  │   ├── PGPROC / PGXACT array                                       │
  │   ├── ProcArray                                                  │
  │   ├── CLOG (pg_xact) SLRU                                        │
  │   ├── MultiXact SLRU                                             │
  │   ├── Subtrans SLRU                                              │
  │   └── CommitTs SLRU                                              │
  │                                                                  │
  │   其他共享结构                                                    │
  │   ├── ShmemIndex (syscache 注册表)                                │
  │   ├── DSM segments (动态扩展)                                     │
  │   └── DSA areas (动态共享堆)                                      │
  └─────────────────────────────────────────────────────────────────┘
  
  ┌────────────────────────┐  ┌────────────────────────┐
  │ Backend #1 私有内存    │  │ Backend #2 私有内存    │  ……
  │ ──────────────────    │  │ ──────────────────    │
  │ TopMemoryContext       │  │ TopMemoryContext       │
  │  ├─ PostmasterContext │  │  ├─ CacheMemoryContext │
  │  ├─ ErrorContext       │  │  ├─ MessageContext     │
  │  ├─ CacheMemoryContext │  │  ├─ TopTransaction...  │
  │  ├─ MessageContext     │  │  │   ├─ CurTrans...    │
  │  ├─ TopTransaction...  │  │  └─ PortalContext      │
  │  │   ├─ CurTrans...    │  │                        │
  │  ├─ PortalContext      │  │                        │
  │  └─ per-query contexts │  │                        │
  │       (AllocSet / Gen / │  │                        │
  │        Slab 实例)        │  │                        │
  └────────────────────────┘  └────────────────────────┘
           │                            │
           ▼                            ▼
       malloc/free                  malloc/free
       (进程本地堆)                  (进程本地堆)
```

记住这三条原则，等下读源码就不会迷路：

- **共享内存永远不能 free**——一旦分配就跟随进程生命周期，回收靠进程退出。
- **私有内存按"上下文"管理**——一组寿命相近的对象共享一个上下文，整组释放。
- **私有内存算法不止一种**——AllocSet 是默认，Generation 适合队列，Slab 适合定长对象。

---

## 一、共享内存：PostgreSQL 的"中央广场"

### 1.1 创建流程：postmaster 一锤定音

共享内存由 postmaster 在启动时一次性创建。Linux 上用 `mmap(MAP_SHARED)`，System V 上用 `shmget`。代码入口在 `src/backend/storage/ipc/shmem.c`：

```c
/*
 * ShmemAlloc -- allocate max-aligned chunk from shared memory
 */
void *ShmemAlloc(Size size)
{
    void *newSpace;
    Size allocated_size;

    newSpace = ShmemAllocRaw(size, &allocated_size);
    if (!newSpace)
        ereport(ERROR, "out of shared memory (%zu bytes requested)", size);
    return newSpace;
}

static void *ShmemAllocRaw(Size size, Size *allocated_size)
{
    /* 关键：cache line 对齐 */
    size = CACHELINEALIGN(size);
    *allocated_size = size;

    SpinLockAcquire(ShmemLock);

    newStart = ShmemSegHdr->freeoffset;
    newFree  = newStart + size;
    if (newFree <= ShmemSegHdr->totalsize) {
        newSpace = (char *) ShmemBase + newStart;
        ShmemSegHdr->freeoffset = newFree;
    } else
        newSpace = NULL;
    ...
}
```

工作方式很像一个**带自旋锁的 bump allocator**：

```text
  ShmemBase                                                    进程退出
  │◄────────────── totalsize = shared_buffers + 其他 ──────────►│
  │                                                              │
  │  ShmemSegHdr │  Buffer Pool  │  ProcArray  │  CLOG  │ ...    │
  │  (header)    │  (8K 一份)    │             │        │       │
  │                                                              │
  │◄── freeoffset 一路向后推进，从不回收 ──►│
```

注意三点：
1. **`freeoffset` 是个高水位线**，分配完就往前走，**永不后退**。这意味着共享内存只能涨、不能缩。
2. **`CACHELINEALIGN`** 把每块对齐到 CPU cache line（一般 64 字节），防止一个数据结构跨两个 cache line 导致 false sharing。
3. **`ShmemLock`** 是个 `SpinLock`，因为共享内存分配只在 postmaster 启动时执行一次（创建 backend 走的是 fork 继承），所以简单 spin lock 就够了。

### 1.2 命名机制：ShmemIndex

每个共享结构都通过 `ShmemInitStruct` 注册到一个字符串名字的索引表里：

```c
void *ShmemInitStruct(const char *name, Size size, bool *foundPtr);
```

调用方式：

```c
/* 例：Clog 模块 */
size = sizeof(SlruCtlData) * NUM_CLOG_BUFFERS;
ShmemInitStruct("CLOG Ctl", size, &found);
```

```text
  ShmemIndex（一张 hash 表）
  ┌─────────────┬─────────────────┐
  │ "BufferDesc"│ → ptr + size   │
  │ "CLOG Ctl"  │ → ptr + size   │
  │ "ProcArray" │ → ptr + size   │
  │ "PGPROC"    │ → ptr + size   │
  │ ...         │                 │
  └─────────────┴─────────────────┘
```

这套机制的好处是：
- 后端启动时按名字"找"自己需要的结构，找不到才创建——`foundPtr` 参数就是给"已存在"返回的。
- 不需要写死的固定地址。
- 不同模块互不干扰。

### 1.3 Buffer Pool：共享内存里最大的住户

`shared_buffers`（默认 128MB）是共享内存里最大的住户。它由 `BufferDesc[NBuffers]` + 一张 hash 表 + 一套置换策略组成。

`src/backend/storage/buffer/buf_internals.h`：

```c
typedef struct BufferDesc {
    BufferTag   tag;             /* 这页是哪张表哪个 block */
    int         buf_id;          /* 在数组里的下标 */
    ...
    pg_atomic_uint32 state;      /* refcount + lock bits */
    int         wait_backend_pid;
    ...
} BufferDesc;

typedef struct BufferTag {
    RelFileNumber rnode;
    ForkNumber    forkNum;
    BlockNumber   blockNum;
} BufferTag;
```

访问一个页要"两步走"：

```text
  想访问 (relfilenode=16384, block=42) 这页
  │
  ├─► 第 1 步：查 buf_hash 表（共享内存里的 HTAB）
  │     buf_id = hash_search(buf_hash, tag, HASH_FIND, NULL)
  │
  └─► 第 2 步：根据 buf_id 在 BufferDesc[] 里定位
        desc = BufferDescriptor[buf_id]
        pin = pg_atomic_read(&desc->state)  ← refcount 自增
```

整个流程涉及两类锁：

| 锁 | 保护对象 | 数量级 |
| --- | --- | --- |
| `BufMappingLock`（分区 LWLock） | `buf_hash` 表本身 | 高并发争用 |
| `BufferDesc.state`（atomic 32-bit） | refcount + content lock | 自旋在 cache 上 |

### 1.5 CLOG / 子事务 / 多事务：SLRU 共享缓存

`pg_xact`（旧名 `pg_clog`）、`pg_subtrans`、`pg_multixact`、`pg_commit_ts` 这些"事务状态页"都是 SLRU（Simple LRU）结构。每个 XID 占 2 bit 表示提交状态：

```c
/* src/backend/access/transam/clog.c */
#define CLOG_BITS_PER_XACT      2
#define CLOG_XACTS_PER_BYTE     4
#define CLOG_XACTS_PER_PAGE     (BLCKSZ * CLOG_XACTS_PER_BYTE)
```

每页 8K × 4 = **32K 个 XID** 用 2 bit 编码。SLRU 把这些页也放在共享内存里，满了再 evict 到磁盘：

```text
  SLRU 总览（共享内存里）
  ─────────────────────
  ┌──────────────────────────────────────┐
  │ SLRU Bank 0 (32K XID 状态)            │ ← 最近访问
  ├──────────────────────────────────────┤
  │ SLRU Bank 1 (32K XID 状态)            │
  ├──────────────────────────────────────┤
  │ ...                                   │
  └──────────────────────────────────────┘
     LRU 替换，写满后异步刷到 $PGDATA/pg_xact/
```

### 1.6 DSM / DSA：动态扩展的共享内存

传统的 `ShmemAlloc` 必须**在启动时就知道总大小**。但很多场景下，我们要的内存大小是动态变化的（比如并行查询、逻辑复制、扩展）。这时候用 **DSM（Dynamic Shared Memory）**：

```c
/* src/backend/storage/ipc/dsm.c */
typedef struct dsm_segment {
    void   *mapped_address;   /* 当前进程看到的地址 */
    Size    mapped_size;
    dsm_handle handle;        /* 全局唯一 ID，用于跨进程传递 */
    ...
} dsm_segment;

dsm_segment *dsm_create(Size size, int tranche_id);
void        *dsm_attach(dsm_handle h);
void         dsm_detach(dsm_segment *seg);
```

DSM 是一个**按需创建的 mmap 段**，可以脱离 postmaster 的 `ShmemBase` 独立存在。然后在 DSM 之上，PG 又搭了一层 **DSA（Dynamic Shared Area）**——一个共享内存里的"堆分配器"：

```c
/* src/backend/utils/mmgr/dsa.c */
dsa_area *dsa_create(int tranche_id, size_t init_segment_size,
                     size_t max_segment_size);
dsa_pointer dsa_allocate(dsa_area *area, size_t size);
void       *dsa_get_address(dsa_area *area, dsa_pointer p);
void        dsa_free(dsa_area *area, dsa_pointer p);
```

```text
  DSA 的设计（来自源码注释）
  ──────────────────────────
  请求 ≤ 8KB：走"对象池"，每个 size class 一个 superblock
  请求 > 8KB：直接在 DSM 段里分配连续页
  整个 segment 全空时归还 OS
```

并行哈希、并行 BTree、并行 SeqScan 都在用 DSA。

---

## 二、进程私有内存：MemoryContext 的艺术

### 2.1 为什么不用 malloc/free？

理论上，`malloc`/`free` 就能搞定一切，PG 为什么要造一个 **MemoryContext** 的轮子？

原因有三：

1. **事务结束要"一键清空"**——一次事务里可能分配了上百万个对象，逐个 `free` 不现实也不可靠（漏一个就漏）。
2. **错误处理要"一键回滚"**——查询中途报错，已经分配了一堆临时对象，靠 `goto cleanup` 一处处释放是噩梦。
3. **生命周期分层**——有些对象活"一次查询"，有些活"一个事务"，有些活"整个进程"。分层后可以分级清理。

`src/backend/utils/mmgr/README` 里的原话：

> The main advantage of memory contexts over plain use of malloc/free is that the entire contents of a memory context can be freed easily, without having to request freeing of each individual chunk within it.

### 2.2 全局上下文：进程一启动就有的 7 个

`memutils.h` 顶端定义了 7 个全局可见的上下文（`extern PGDLLIMPORT MemoryContext ...`）：

```c
extern PGDLLIMPORT MemoryContext TopMemoryContext;
extern PGDLLIMPORT MemoryContext ErrorContext;
extern PGDLLIMPORT MemoryContext PostmasterContext;
extern PGDLLIMPORT MemoryContext CacheMemoryContext;
extern PGDLLIMPORT MemoryContext MessageContext;
extern PGDLLIMPORT MemoryContext TopTransactionContext;
extern PGDLLIMPORT MemoryContext CurTransactionContext;
extern PGDLLIMPORT MemoryContext PortalContext;
```

它们的寿命层次可以画成这样：

```text
  TopMemoryContext                      ← 进程级，永远不释放
    │
    ├── ErrorContext                    ← 专门给 elog(ERROR) 用，不会递归
    │
    ├── PostmasterContext               ← postmaster 用；backend fork 后可以删掉
    │
    ├── CacheMemoryContext              ← relcache / catcache 永久缓存
    │     ├── <每个 cache entry 的子 context>
    │     └── ...
    │
    ├── MessageContext                  ← 一条客户端消息的生命
    │     └── parse/plan tree
    │
    ├── TopTransactionContext           ← 一个顶层事务
    │     └── CurTransactionContext     ← 每个子事务各自的子 context
    │           ├── portal memory
    │           ├── per-statement context
    │           └── ...
    │
    └── PortalContext                   ← 当前执行的 portal
          └── executor state, exprcontext...
```

README 里把每个 context 的用途都解释了一遍。最关键的两条：

- **`TopMemoryContext` 永远不释放**，等于"无限 malloc"。
- **`CurTransactionContext` 子事务回滚时会被销毁**，所以子事务不要把指针留在父事务里（会产生悬空指针）。

### 2.3 palloc vs malloc：API 差异

`palloc` 是 PG 自己的"分配器入口"，对标 `malloc`，但有几个故意为之的差别：

```c
/* 出错时不返回 NULL，直接 elog(ERROR) */
extern void *palloc(Size size);

/* 大块优先走 malloc()，不走上下文 */
extern void *MemoryContextAllocHuge(MemoryContext context, Size size);
```

```text
  palloc / pfree  vs  malloc / free
  ──────────────────────────────────
  • 出错时：palloc → ERROR（不会返回 NULL）
  • palloc(0)：合法（malloc 行为依实现）
  • pfree(NULL：非法（malloc 接受 NULL）
  • pfree / repalloc 不依赖 CurrentMemoryContext
    —— chunk 自带"所属上下文"信息
  • reset/delete context：批量释放，无需逐个 free
```

### 2.4 父子树：递归释放的优雅

context 之间不是孤岛，是**一棵树**：

```text
  TopMemoryContext
    ├── A
    │   ├── A1
    │   └── A2
    └── B
```

调用 `MemoryContextDelete(A)` 会把 A1、A2 一起删掉。这条规则让"忘记释放某个子 context" 变得**安全**：只要根没忘，叶子随便漏。

```c
/* src/backend/utils/mmgr/mcxt.c */
void MemoryContextDelete(MemoryContext context)
{
    /* 递归删除所有 child */
    MemoryContextDeleteChildren(context);
    /* 调用具体实现的 delete 钩子 */
    context->methods->free_context(context);
}
```

`MemoryContextReset()` 类似，但保留 context 本身——适合"每条 SQL 重置一次"的场景。

### 2.5 CurrentMemoryContext：全局"当前上下文"

代码里到处都是 `palloc(...)`，没有传 context 参数。这是因为有 `CurrentMemoryContext` 这个全局变量。`MemoryContextSwitchTo()` 切换当前 context：

```c
extern MemoryContext CurrentMemoryContext;     /* 全局 */
extern MemoryContext MemoryContextSwitchTo(MemoryContext context);

void do_query(...) {
    MemoryContext old = MemoryContextSwitchTo(MessageContext);
    /* 这里所有 palloc() 都在 MessageContext 里 */
    MemoryContextSwitchTo(old);
}
```

`README` 里特意警告：

> Only in *very* circumscribed code should it ever point at a context having greater than transaction lifespan, since doing so risks permanent memory leaks.

——别把 `CurrentMemoryContext` 长期指向 `TopMemoryContext`，否则事务结束都清理不掉。

---

## 三、内存算法：三种 MemoryContext 实现

PG 自带三种 MemoryContext 实现，各有适用场景。它们的入口都在 `src/backend/utils/mmgr/`：

```text
  MemoryContext（抽象基类）
    │
    ├── AllocSet         （aset.c）   ← 默认，通用
    ├── Generation       （generation.c）← 队列、FIFO 场景
    ├── Slab             （slab.c）    ← 定长对象
    ├── Bump              （bump.c）    ← 单调增长、整体释放
    └── [测试用 dummy]
```

### 3.1 AllocSet：通用主力

**所有"通用"的 context（TopMemoryContext、CacheMemoryContext、MessageContext...）都用它。**

数据结构（`aset.c`）：

```c
typedef struct AllocSetContext {
    MemoryContextData header;          /* 公共头 */
    AllocBlock    blocks;              /* 所有 block 链表 */
    AllocSetFreeListKey freelist[ALLOCSET_NUM_FREELISTS];  /* 空闲链表 */
    Size          allocChunkLimit;     /* 走 freelist 的最大尺寸 */
} AllocSetContext;

typedef struct AllocBlockData {
    AllocSetContext *aset;            /* 所属 context */
    AllocBlock       prev, next;      /* 双向链表 */
    Size             size;            /* 整个 block 大小（含 header） */
    /* 后面就是可分配空间 */
} AllocBlockData;
```

核心思想：**"freelist + power-of-2 桶"**。

```text
  AllocSet 内存布局
  ────────────────────────────────────────────────────────
  
  block[0] (8K)         block[1] (8K)         block[2] (64K)  ...
  ├─ header ─┤├─ data ─┤ ├─ header ─┤├─ data ─┤ ├─ header ─┤├─ data ─┤
  
  freelist[0]  →  32B 空闲块链表  (1 << ALLOC_MINBITS)
  freelist[1]  →  64B 空闲块链表  (2 << ALLOC_MINBITS)
  freelist[2]  →  128B 空闲块链表
  ...
  freelist[10] →  8K  空闲块链表  (= ALLOCSET_SEPARATE_THRESHOLD)
  
  > 8K 的请求 → 直接 malloc 整块（不再 freelist 化）
```

关键参数 `aset.c:103-110`：

```c
#define ALLOC_BLOCKHDRSZ  MAXALIGN(sizeof(AllocBlockData))
#define ALLOC_CHUNKHDRSZ  MAXALIGN(sizeof(MemoryChunk))
#define ALLOCSET_NUM_FREELISTS  11
#define ALLOCSET_SEPARATE_THRESHOLD  8192   /* 8K 分界 */
```

调用 `palloc(100)` 时：

```text
  1. AllocSetFreeIndex(100) → idx=2  (freelist[2] 是 64B 还是 128B 桶？)
     其实取 ceil(log2(100)) - ALLOC_MINBITS，得到一个 2 的幂
  2. 从 freelist[idx] 找一个空闲块
     - 找到了 → 抠出来返回
     - 找不到 → 申请一个新 block，从里面切一块
  3. < 8K 走 freelist；≥ 8K 直接 malloc 整块
```

`pfree(ptr)` 时：

```text
  ptr 反向找到所属 AllocSet + block
  计算 size，把块挂回 freelist[idx]
  ← 注意：块还在 block 里，block 没还 malloc
```

`AllocSetReset()` 时：

```text
  把所有 block 都 free 掉（除了 keeper block）
  freelist 全部清空
  ← 这才是真正"还 malloc"的时候
```

为什么这么设计？因为**绝大多数对象的生命周期都和 context 一致**——context reset 时一起还，比每个 pfree 都 malloc 一次快得多。

### 3.2 Generation：FIFO 场景专用

**`Generation` 假设"先分配的先释放"（FIFO）**。典型场景：exececutor 构造一批元组、处理、扔掉。

实现核心（`generation.c`）：

```c
typedef struct GenerationContext {
    MemoryContextData header;
    GenerationBlock *blocks;       /* 所有 block 链表 */
    GenerationBlock *freeblock;    /* 复用一个全空的 block */
    Size              blockSize;   /* 每个 block 大小 */
    Size              chunkSize;   /* 单个 chunk 大小（固定） */
} GenerationContext;
```

关键算法：

```text
  Generation 的"代际"思维
  ──────────────────────────
  
  块里有两个计数：nallocated、nfreed
  
  nfreed == nallocated 时
    → 这个块变成"全空"，挂到 freeblock 复用
    → 如果 freeblock 已被占用 → 直接 free 给 malloc
  
  下次 palloc：优先从 freeblock 切，省一次 malloc
```

```text
  Generation vs AllocSet
  ──────────────────────
  AllocSet 把空闲 chunk 挂到 freelist 复用
  Generation 把整个空 block 复用
  
  优势：
    • FIFO 工作负载下，Generation 的块复用率最高
    • 碎片最少（整块复用，不会有"半碎"的块）
  
  代价：
    • 不适合随机 pfree 的场景（块永远等不到 nfreed==nallocated）
```

`execGrouping.c`、一些队列场景会用 Generation。

### 3.3 Slab：定长对象专属

**Slab 假设所有分配都是同样大小**。这在 PG 里有真实需求——比如 TupleTableSlot、CatCtucheEntry 等等。

实现核心（`slab.c`）：

```c
typedef struct SlabContext {
    MemoryContextData header;
    dlist_head    blocklist[SLAB_BLOCKLIST_COUNT];   /* 按空闲率分桶 */
    int           chunkSize;            /* 固定 chunk 大小 */
    int           chunksPerBlock;
    int           fullChunkCount;       /* 块上总 chunk 数 */
    SlabBlock    *curBlock;             /* 当前分配用的 block */
    int           curBlockIndex;        /* 当前块在 blocklist 里的位置 */
    ...
} SlabContext;
```

块按"已用多少 chunk"分桶：

```text
  Slab 的 blocklist（按"满的程度"分 3 桶）
  ──────────────────────────────────────────
  
  blocklist[0]  全满块       ← 新 chunk 优先从这里切？不对，是反过来的
  blocklist[1]  半空块
  blocklist[2]  全空块       ← 优先从这里拿
  
  等等，再看代码注释：
  
  "We give priority to putting new allocations into the
   'fullest' block.  This help avoid having too many sparsely
   used blocks around and allows blocks to more easily become
   completely unused"
  
  反过来了！优先放最"满"的块里 →
  满的块 → 释放 → 全空 → 整体还给 malloc
```

每块内部维护一个简单 freelist（用 chunk 自身存指针）：

```c
typedef struct SlabBlock {
    SlabContext *slab;        /* 所属 context */
    int          nfree;       /* 空闲 chunk 数 */
    void        *freehead;    /* freelist 头 */
    int          unused;      /* 高水位线（还没用过的 chunk 数） */
    dlist_node   node;        /* blocklist 链 */
    char         data[];      /* chunk 实际存储 */
} SlabBlock;
```

"unused 高水位线"是个聪明设计：复用过的 chunk 优先于全新 chunk——CPU cache 局部性更好。

### 3.4 三种算法对比

| 维度 | AllocSet | Generation | Slab |
| --- | --- | --- | --- |
| 适用场景 | 通用 | FIFO 队列 | 定长对象 |
| 分配复杂度 | O(1) 均值 | O(1) | O(1) |
| 碎片 | 中（freelist 桶大小是 2 的幂） | 低（整块复用） | 极低 |
| 释放复杂度 | O(1) | O(1) + 可能 free block | O(1) |
| 复用粒度 | chunk | 整个 block | chunk |
| 触发 reset | 还所有 block | 还所有 block | 还所有 block |
| 典型用途 | 几乎所有 context | execGrouping、queue | TupleTableSlot 等 |

源码里要怎么选？

```c
AllocSetContextCreate(parent, "TopMemoryContext", ...);
GenerationContextCreate(parent, "Generation queue", ...);
SlabContextCreate(parent, "Slab cache", chunkSize, ...);
```

---

## 四、Buffer Manager：共享内存里最大的数据

虽然 Buffer Manager 算"共享内存"的一部分，但它功能完整值得单独拿出来说。

### 4.1 三大数据结构

```text
  Buffer Manager 三大组件
  ──────────────────────────
  
  ┌─ BufferDescriptor[] (数组) ─┐
  │  BufferDesc[0]               │ ← NBuffers 个
  │  BufferDesc[1]              │
  │  ...                        │
  │  BufferDesc[NBuffers-1]     │
  └─────────────────────────────┘
            │
            │ 通过 buf_id 索引
            ▼
  ┌─ buf_hash (HTAB) ─────────┐
  │  key: BufferTag            │
  │  value: buf_id             │
  └────────────────────────────┘
            │
            │ 通过 BufferTag 查找
            ▼
  ┌─ Strategy (置换策略) ─────┐
  │  clock-sweep hands         │
  │  freelist（未使用页）     │
  └────────────────────────────┘
```

### 4.2 访问一个 Buffer 的全过程

```text
  想读 (relfilenode=16384, blockNum=42)
  │
  ├─► ReadBuffer(relation, blockNum)
  │     │
  │     ├─► BufferAlloc(smgr, ...)
  │     │     │
  │     │     ├─► hash_search(buf_hash, tag, HASH_FIND, &found)
  │     │     │     │  找到：返回 buf_id
  │     │     │     │  没找到：从 Strategy 拿一个 victim buf_id
  │     │     │     │
  │     │     ├─► Pin/Lock BufferDesc[buf_id]
  │     │     │     pg_atomic_fetch_or_uint32(&state, BM_LOCKED)
  │     │     │
  │     │     └─► 如果是 dirty，先刷盘
  │     │
  │     └─► 返回 Buffer（其实就是 buf_id）
  │
  └─► 用户拿到 buf_id，读 BufferDescriptor[buf_id].data
```

### 4.3 锁的层次

```text
  读路径锁链（典型）
  ──────────────────
  1. partitionlock for BufMappingLock  (LWLock, share)
  2. buffer content lock (BM_LOCKED in state)
  3. pin refcount (atomic increment)

  写路径锁链（典型）
  ──────────────────
  1. partitionlock for BufMappingLock  (LWLock, exclusive)
  2. buffer content lock (BM_LOCKED in state, exclusive)
  3. pin refcount

  ← 关键设计：先拿映射锁定位，再拿内容锁修改
  ← 映射锁按 blockNum 哈希分桶（默认 16 个分区）减少争用
```

---

## 五、三者协作：一张全景图

把三层放在一起，看一次 SQL 查询到底用了哪些分配器：

```text
  客户端发送 SELECT * FROM t WHERE id = 1
  │
  ▼
  ┌──────────────────────────────────────────────────────────┐
  │ 共享内存（本进程 fork 继承得到）                          │
  │                                                          │
  │  Buffer Pool: 命中就直接读；不命中从 disk 读进来           │
  │  CLOG: 查可见性                                          │
  │  ProcArray: 看看有谁在跑（GetSnapshotData）              │
  │                                                          │
  │  这一段没有任何 malloc，全是预先 mmap 的共享内存          │
  └──────────────────────────────────────────────────────────┘
  │
  ▼
  ┌──────────────────────────────────────────────────────────┐
  │ 进程私有内存（本进程 palloc）                          │
  │                                                          │
  │  MessageContext        解析 SQL 文本                     │
  │    └─ parsetree                                              │
  │  PortalContext         执行 portal                                       │
  │    ├─ ExecutorState                                              │
  │    ├─ TupleTable (SlabContext!)                              │
  │    ├─ ExprContext                                              │
  │    └─ per-tuple AllocSet (每行迭代 reset 一次)             │
  └──────────────────────────────────────────────────────────┘
  │
  ▼
  ┌──────────────────────────────────────────────────────────┐
  │ 共享内存里的"动态部分"（可选）                       │
  │                                                          │
  │  Parallel Query: 用 DSM + DSA 给 worker 们分配共享内存     │
  │  Logical Decoding: 用 DSM 存 changeset                    │
  └──────────────────────────────────────────────────────────┘
```

---

## 六、运维与调试：怎么观察内存？

几条最常用的诊断姿势：

### 6.1 看私有内存

```sql
-- 看每个 context 的占用
SELECT name, setting FROM pg_settings WHERE name LIKE '%context%';
-- 或通过 contrib/pg_buffercache 类似工具查

-- PG 14+ 提供内存上下文统计输出：
SET log_statement_stats = on;
SET log_parser_stats = on;
SET log_planner_stats = on;
SET log_executor_stats = on;
-- 然后查日志，会输出每个 context 的 peak usage
```

输出长这样：

```
  Memory context used: ... bytes in ... blocks.
  ...
  ExecutorState: 8192 total in 2 blocks; 5640 used (69%)
  TupleTable: 16384 total in 4 blocks; 12000 used (73%)
  ExprContext: 1024 total in 1 block; 768 used (75%)
  ...
```

### 6.2 看共享内存

```sql
-- 实时看 shared_buffers 中每个 page 的状态
SELECT * FROM pg_buffercache_pages() LIMIT 10;  -- 需要 pg_buffercache 扩展

-- 看 CLOG 的占用
SELECT count(*), relname FROM pg_locks GROUP BY relname;
```

### 6.3 配置项速查

```ini
# postgresql.conf
shared_buffers = 128MB           # 共享内存里最大的住户
wal_buffers = 16MB               # WAL buffer（也是共享内存）
temp_buffers = 8MB               # 临时表缓冲（私有内存）
work_mem = 4MB                   # hash join / sort 的私有内存
maintenance_work_mem = 64MB      # VACUUM / CREATE INDEX 的私有内存
hash_mem_multiplier = 2.0        # PG 13+ hash 表容量倍数
```

---

## 七、总结：三套分配器，各司其职

PostgreSQL 的内存世界不是"一个 malloc 走天下"，而是**按生命周期、按可见性、按数据结构形状分了层**：

```text
                       PostgreSQL 内存世界
                       ──────────────────
       ┌──────────────────────┐  ┌──────────────────────┐
       │    共享内存           │  │    进程私有内存       │
       │  ─────────────       │  │  ─────────────       │
       │  • 一次 mmap 永久    │  │  • 按 context 分配    │
       │  • 跨进程可见        │  │  • 按 context 释放    │
       │  • 永不 free         │  │  • 三种算法可选       │
       │                      │  │                      │
       │  ├─ Buffer Pool      │  │  ├─ AllocSet（默认） │
       │  ├─ Proc/CLOG array  │  │  ├─ Generation      │
       │  ├─ LWLock array     │  │  └─ Slab            │
       │  └─ DSM / DSA (动态)  │  │                      │
       └──────────────────────┘  └──────────────────────┘
                    │                       │
                    └──────────┬────────────┘
                               ▼
                       ┌──────────────────────┐
                       │    操作系统           │
                       │  ─────────────       │
                       │  Linux: mmap / shmget│
                       │  SysV: shmget/ shmat │
                       │  Windows: CreateFileMapping │
                       └──────────────────────┘
```

记住这三条经验法则，排查内存问题能少走弯路：

1. **共享内存涨上去就降不下来**——规划 `shared_buffers` 时必须一次给够。事后想缩？只能重启。
2. **私有内存按 context 分层**——`CurrentMemoryContext` 别乱指，长寿命 context 里别塞临时数据。
3. **三种 allocator 各有最佳场景**——通用 AllocSet、队列 Generation、定长 Slab。

内存不是越多越好，也不是越少越好。理解 PostgreSQL 的三层内存结构，才能在容量、性能、可观测性之间找到平衡。

---

## 参考资料

- PostgreSQL 17 源码：
  - `src/backend/storage/ipc/shmem.c` — `ShmemAlloc`、`ShmemInitStruct`
  - `src/backend/utils/mmgr/README` — MemoryContext 设计哲学
  - `src/backend/utils/mmgr/aset.c` — AllocSet 实现
  - `src/backend/utils/mmgr/generation.c` — Generation 实现
  - `src/backend/utils/mmgr/slab.c` — Slab 实现
  - `src/backend/utils/mmgr/dsa.c` — Dynamic Shared Area
  - `src/backend/storage/ipc/dsm.c` — Dynamic Shared Memory segments
  - `src/backend/storage/buffer/bufmgr.c` — Buffer Manager
  - `src/include/storage/buf_internals.h` — BufferDesc、Buffer state
  - `src/include/utils/memutils.h` — 7 个全局 context 声明
- 《PostgreSQL 15 内部原理》, Egor Rogov
- [PostgreSQL Documentation — Resource Consumption](https://www.postgresql.org/docs/current/runtime-config-resource.html)
