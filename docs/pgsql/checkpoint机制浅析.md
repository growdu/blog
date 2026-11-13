# PostgreSQL Checkpoint 机制浅析

| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 修订：核对源码与各发布版本，补版本边界与失效参数，修正控制文件字段与恢复配置写法 | 2026-11-14 |

> **版本声明**：本文的代码与字段讲解基于 **PostgreSQL 9.x**（`CheckPointGuts` 的调用顺序、
> 控制文件字段、PITR 配置写法都是那个年代的）。涉及当前版本（PG 17）差异的地方会单独标出，
> 不标的地方请以你自己的 `src/` 为准。

## 背景

上一篇《[WAL 机制浅析](./wal机制浅析.md)》简单介绍了 PostgreSQL 中的 WAL 机制，其中讲到创建
checkpoint 会触发刷新 xlog 日志页到磁盘。本文接着讲 checkpoint 机制本身。

checkpoint 又名检查点，一般 checkpoint 会将某个时间点之前的脏数据全部刷新到磁盘，以实现数据的一致性与完整性。

目前各个流行的关系型数据库都具备 checkpoint 功能，其主要目的是为了缩短崩溃恢复时间。以 Oracle 为例，在进行数据恢复时，会以最近的 checkpoint 为参考点执行事务前滚。而在 WAL 机制的浅析中也提过，PostgreSQL 在崩溃恢复时会以最近的 checkpoint 为基础，不断应用这之后的 WAL 日志。

本文回答三个问题：checkpoint 什么时候被触发、一次 checkpoint 到底做了哪些事、它的代价落在哪里。

## 检查点发生时机

在xlog.h文件中，有如下代码对checkpoint进行了相应的分类：

```c
/*
 * OR-able request flag bits for checkpoints.  The "cause" bits are used only
 * for logging purposes.  Note: the flags must be defined so that it's
 * sensible to OR together request flags arising from different requestors.
 */

/* These directly affect the behavior of CreateCheckPoint and subsidiaries */
#define CHECKPOINT_IS_SHUTDOWN  0x0001  /* Checkpoint is for shutdown */
#define CHECKPOINT_END_OF_RECOVERY 0x0002  /* Like shutdown checkpoint,
                                             * but issued at end of WAL
                                             * recovery */
#define CHECKPOINT_IMMEDIATE   0x0004  /* Do it without delays */
#define CHECKPOINT_FORCE       0x0008  /* Force even if no activity */
/* These are important to RequestCheckpoint */
#define CHECKPOINT_WAIT        0x0010  /* Wait for completion */
/* These indicate the cause of a checkpoint request */
#define CHECKPOINT_CAUSE_XLOG  0x0020  /* XLOG consumption */
#define CHECKPOINT_CAUSE_TIME  0x0040  /* Elapsed time */
#define CHECKPOINT_FLUSH_ALL   0x0080  /* Flush all pages, including those
                                         * belonging to unlogged tables */
```
也就是说，以下几种情况会触发数据库操作系统做检查点操作：

1. 超级用户（其他用户不可）执行CHECKPOINT命令
2. 数据库shutdown
3. 数据库recovery完成
4. XLOG日志量达到了触发checkpoint阈值
5. 周期性地进行checkpoint
6. 需要刷新所有脏页

为了能够周期性的创建检查点，减少崩溃恢复时间，同时合并I/O，PostgreSQL提供了辅助进程checkpointer。它会对不断检测周期时间以及上面的XLOG日志量阈值是否达到，而周期时间以及XLOG日志量阈值可以通过参数来设置大小，接下来介绍下与checkpoints相关的参数。

### 与检查点相关参数

下面四个参数里有两个的**名字在当前版本已经不存在了**，抄之前先看清版本：

| 参数 | 当前（PG 17）默认值 | 版本说明 |
| --- | --- | --- |
| `max_wal_size` | 1GB | **PG 10 引入**，取代旧的 `checkpoint_segments` |
| `min_wal_size` | 80MB | **PG 10 引入**，与 `max_wal_size` 一起取代 `checkpoint_segments` |
| `checkpoint_timeout` | 5min | 版本间未变 |
| `checkpoint_completion_target` | **0.9** | PG 10~13 默认 **0.5**，**PG 14 起改为 0.9** |
| `checkpoint_warning` | 30s | 版本间未变；设成 0 可禁用 |

> **旧参数 `checkpoint_segments`（默认 3）**：控制「WAL 超过多少个段就触发 checkpoint」。
> 它在 **PostgreSQL 10** 被 `min_wal_size` / `max_wal_size` 取代，现在设置它会直接报
> `unrecognized configuration parameter`。

各个参数的含义：

- `max_wal_size`
  - WAL 允许增长到的上限（默认 1GB）。超过这个量，系统会**请求**一次 checkpoint
    （是「请求」，不是「强制立刻做」，实际是否立刻做取决于 `checkpoint_completion_target`）。
- `min_wal_size`
  - WAL 段文件的回收下限（默认 80MB）。checkpoint 之后多余的 WAL 段会被回收复用，
    留在这个量以下是为了避免频繁创建/删除文件。
- `checkpoint_timeout`
  - 系统自动执行 checkpoint 之间的最大时间间隔（默认 5 分钟）。
- `checkpoint_completion_target`
  - checkpoint 的**刷盘阶段**允许占两次 checkpoint 间隔的比例（默认 0.9）。
    也就是说 checkpoint 有 90% 的时间预算用来慢慢刷脏页，把 I/O 摊平到整个间隔里，
    而不是集中在一瞬间——这正是 PG 10 引入的「分布式 checkpoint」想解决的问题。
- `checkpoint_warning`
  - 默认 30 秒。如果实际 checkpoint 间隔小于这个值，就在 server log 里写一条告警。
    设为 0 可禁用。

关于「分布式 checkpoint」：PG 10 引入了 `BM_CHECKPOINT_NEEDED` 标志位。

checkpoint 开始时，`BufferSync()` 扫描一遍所有 buffer，把当时是脏的页面**额外**打上这个标志；之后写盘时（无论由 checkpoint 自己还是后台 writer 写），这个标志被清掉。

这样只有「checkpoint 开始那一刻是脏的」页面会被写入，而 checkpoint 期间新变脏的页面留给下一轮——避免了 checkpoint 把所有脏页挤在一个时间点写出。

## 创建检查点具体过程

### CreateCheckPoint具体过程

当PostgreSQL触发checkpoint发生的条件后，会调用CreateCheckPoint函数创建具体的检查点，具体过程如下：

1. 遍历所有的数据buffer，把当时是脏的页面**额外**打上 BM_CHECKPOINT_NEEDED 标志（脏页本身仍是 BM_DIRTY），表示这些脏页将要被checkpoint刷新到磁盘
2. 调用CheckPointGuts函数将共享内存中的脏页刷出到磁盘
3. 生成新的Checkpoint 记录写入到XLOG中
4. 更新控制文件、共享内存里XlogCtl的检查点相关成员、检查点的统计信息结构

PostgreSQL 控制文件pg_control里存储的数据是一个ControlFileData结构，具体如下：

```c
typedef struct ControlFileData
{
    uint64    system_identifier;
    uint32    pg_control_version;     /*PG_CONTROL_VERSION */
    uint32    catalog_version_no;     /* seecatversion.h */
    DBState      state;       /* see enum above */
    pg_time_t time;        /* time stamp of last pg_control update */

    XLogRecPtr checkPoint;     /* 最近一次创建 checkpoint 的 LSN */
    CheckPoint checkPointCopy; /* 最近一次 checkpoint 对应的 CheckPoint 对象 */
    ...
    XLogRecPtr minRecoveryPoint;
    TimeLineID minRecoveryPointTLI;
    XLogRecPtr backupStartPoint;
    XLogRecPtr backupEndPoint;
    bool       backupEndRequired;
    ...
}
```

> **版本差异**：早期版本还有一个 `prevCheckPoint` 字段，用来记「上一个**完全**写完的
> checkpoint 的位置」——因为 checkpoint 写盘期间崩溃，磁盘上的 checkpoint 可能不完整。
> PostgreSQL 10 的 "Remove secondary checkpoint" 改动把这个字段移除了，改由
> `checkPointCopy` + redo 指针来表达同样的语义。现在（PG 17）的 `ControlFileData`
> 里**没有** `prevCheckPoint`。

其中，minRecoveryPoint和minRecoveryPointTLI确定数据库启动前，如果做归档恢复，我们必须恢复到的最小检查点。其中minRecoveryPoint指向该检查点对应的LSN位置，minRecoveryPointTLI指向该检查点对应的时间线。其具体的用法，我们将在之后的PostgreSQL崩溃恢复中分析，这里我们主要分析下PostgreSQL中的时间线概念。

PostgreSQL中WAL日志段名称，由时间线ID、日志ID、段ID的八位16进制数依次构成。例如：

| 00000001      | 00000001 | 0000008F |
| ------------- | -------- | -------- |
| 时间线TimeLineID | 逻辑日志ID   | 段ID      |

其中时间线是作为日志段名称的一部分，用来标识数据库归档恢复后产生的一系列新的WAL记录。在每次归档恢复完成后，都会产生一个新的时间线和新的WAL日志段。时间线可以理解为平行时空中的各个平行宇宙，我们完全可以恢复到某个时间点，重开一条时间线，继续进行数据操作，这样就可以实现完全的 PITR（Point-In-Time Recovery，时间点恢复）。

### 时间线历史文件

在PostgreSQL中，一个新的时间线产生，系统伴随它会建立一个以“新TimeLineID+.history”命名的“时间线历史”文件(timeline history)。它是一个类似于txt的文件，其中包含所有在当前时间线以前的时间线，同时记录了每个时间线开始时的第一个WAL段。

这样数据库恢复时，通过读取时间线历史文件，根据目标时间点可以快速找到正确的日志段文件。如果上一次恢复是恢复到具体某时刻，在时间线历史文件中还会记录该时间线对应的具体时刻。

在PITR恢复时，无需扫描所有WAL日志文件，而是通过时间线直接定位某个WAL段，再从该WAL段中找到符合该时间点的日志记录，这样就大大提高了效率。同时数据库恢复时，默认是沿着基备份开始时的时间点进行，即利用从基备份完成后产生的第一个日志段文件做恢复。

如果想恢复到指定时间点(时间线)，需要在恢复配置里设置目标时间线（target timeline ID），但 target timeline ID 不能指定为基备份以前的时间线。

> **版本差异**：上面这段在 **PostgreSQL 12 之前**是要写进 `recovery.conf` 的；
> **PG 12 起 `recovery.conf` 已被移除**，改成在数据目录里放一个 `recovery.signal`
> 标记文件，恢复参数直接写进 `postgresql.conf`：
>
> ```
> # PG 12+ 的做法
> touch $PGDATA/recovery.signal
> # postgresql.conf 里写：
> #   restore_command = 'cp /backup/archive/%f %p'
> #   recovery_target_time = '2026-11-14 10:00:00'
> #   recovery_target_timeline = 'latest'
> ```
>
> 老版本里仍然可以用 `recovery.conf` 的写法，但现在设置它会直接报错——
> PG 12 的提示语就是「recovery.conf 文件名已被 recovery.signal 取代」。

### CheckPointGuts函数

CheckPointGuts函数将共享内存里的数据刷出并文件同步到磁盘，具体定义如下：

```c
static void
CheckPointGuts(XLogRecPtr checkPointRedo, int flags)
{
   CheckPointCLOG();
   CheckPointSUBTRANS();
   CheckPointMultiXact();
   CheckPointPredicate();
   CheckPointRelationMap();
   CheckPointBuffers(flags);   /* performs all required fsyncs */
   /* We deliberately delay 2PC checkpointing as long as possible */
   CheckPointTwoPhase(checkPointRedo);
}
```

> **版本差异**：这是 PG 9.x 的调用顺序。**PG 17** 的同一个函数里还多了几个模块，
> 且顺序变了——先处理「元数据类」缓存（relationmap / replication slots / snapbuild /
> logical rewrite heap / replication origin），再处理「事务状态类」缓存：
>
> ```c
> CheckPointRelationMap();
> CheckPointReplicationSlots(flags & CHECKPOINT_IS_SHUTDOWN);
> CheckPointSnapBuild();
> CheckPointLogicalRewriteHeap();
> CheckPointReplicationOrigin();
> CheckPointCLOG();
> CheckPointCommitTs();
> CheckPointSUBTRANS();
> CheckPointMultiXact();
> CheckPointPredicate();
> CheckPointBuffers(flags);
> CheckPointTwoPhase(checkPointRedo);
> ```

可以看出，CheckPointGuts根据不同的缓存类型，把clog、subtrans、multixact、predicate、relationmap、buffer（数据文件）和twophase相应缓存分别调用不同的方法，将缓存刷到磁盘中：

- 提交事务日志管理器的方法CheckPointClog
- 子事务日志管理器的方法CheckPointSUBTRANS
- 多事务日志管理器的方法CheckPointMultiXact
- 支持序列化事务隔离级别的谓词锁模块的方法CheckPointPredicate
- 目录/系统表到文件节点映射模块的方法CheckPointRelationMap
- 缓存管理器的方法CheckPointBuffers
- 两阶段提交模块的方法CheckPointTwoPhase

其中，CLOG、SUBTRANS、MULTIXACT、PREDICATE 这四个函数最后都调用了SLRU模块的SimpleLruFlush（简单最近最少使用）方法，把相应的共享内存数据写到磁盘，并通过调用pg_fsync方法把相应文件刷到磁盘上对应文件。

而 CheckPointBuffers 与 CheckPointTwoPhase 没有使用SLRU算法，直接调用pg_fsync方法把相应文件刷到磁盘上对应文件。

目录/系统表到文件节点映射模块的方法CheckPointRelationMap，则是将共享内存里系统表和对应物理文件映射的map文件刷到磁盘。

## 总结

至此，我们大体了解了checkpoint的用法和整个实现过程，但是还需要对一些特别的地方做出说明。

- 每个检查点后，第一次数据页的变化会导致整个页面会被记录在XLOG日志中
- 检查点的开销比较高，可以用 `checkpoint_warning` 自检；需要拉长间隔时，调大的是
  `max_wal_size`（PG 10 起取代了 `checkpoint_segments`），而不是已经失效的旧参数名
- 检查点的位置保存在文件 pg_control，pg_control文件被损坏可能会导致数据库不可用

**代价落在哪里？** checkpoint 间隔调长，崩溃恢复要重放的 WAL 就变多（恢复更慢）；
间隔调短，写放大和 I/O 尖峰就变多。所以调参前先分清你现在的瓶颈是「恢复慢」还是「写入抖」——
前者调大 `max_wal_size`，后者反而要调小它、让 checkpoint 更频繁地把脏页摊平出去。

其中，如果pg_control文件损坏，在数据库崩溃恢复时可能出现一些问题，这些问题我们将在分析PostgreSQL数据库崩溃恢复时具体分析。