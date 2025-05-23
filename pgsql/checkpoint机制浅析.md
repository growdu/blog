## 背景

上期月报[PgSQL · 特性分析 · Write-Ahead Logging机制浅析](http://mysql.taobao.org/monthly/2017/03/02/)中简单介绍了PostgreSQL中WAL机制，其中讲到如果是创建checkpoint会触发刷新xlog日志页到磁盘，本文主要分析下PostgreSQL中checkpoint机制。

checkpoint又名检查点，一般checkpoint会将某个时间点之前的脏数据全部刷新到磁盘，以实现数据的一致性与完整性。目前各个流行的关系型数据库都具备checkpoint功能，其主要目的是为了缩短崩溃恢复时间，以Oracle为例，在进行数据恢复时，会以最近的checkpoint为参考点执行事务前滚。而在WAL机制的浅析中，也提过PostgreSQL在崩溃恢复时会以最近的checkpoint为基础，不断应用这之后的WAL日志。

## 检查点发生时机

在xlog.h文件中，有如下代码对checkpoint进行了相应的分类：

```
/*
 * OR-able request flag bits for checkpoints.  The "cause" bits are used only
 * for logging purposes.  Note: the flags must be defined so that it's
 * sensible to OR together request flags arising from different requestors.
 */

/* These directly affect the behavior of CreateCheckPoint and subsidiaries */
#define CHECKPOINT_IS_SHUTDOWN0x0001/* Checkpoint is for shutdown */
#define CHECKPOINT_END_OF_RECOVERY0x0002/* Like shutdown checkpoint,
 * but issued at end of WAL
 * recovery */
#define CHECKPOINT_IMMEDIATE0x0004/* Do it without delays */
#define CHECKPOINT_FORCE0x0008/* Force even if no activity */
/* These are important to RequestCheckpoint */
#define CHECKPOINT_WAIT0x0010/* Wait for completion */
/* These indicate the cause of a checkpoint request */
#define CHECKPOINT_CAUSE_XLOG0x0020/* XLOG consumption */
#define CHECKPOINT_CAUSE_TIME0x0040/* Elapsed time */
#define CHECKPOINT_FLUSH_ALL0x0080/* Flush all pages, including those
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

- checkpoint\_segments
  - WAL log的最大数量，系统默认值是3。超过该数量的WAL日志，会自动触发checkpoint。
- checkpoint\_timeout
  - 系统自动执行checkpoint之间的最大时间间隔。系统默认值是5分钟。
- checkpoint\_completion\_target
  - 该参数表示checkpoint的完成时间占两次checkpoint时间间隔的比例，系统默认值是0.5,也就是说每个checkpoint需要在checkpoints间隔时间的50%内完成。
- checkpoint\_warning
  - 系统默认值是30秒，如果checkpoints的实际发生间隔小于该参数，将会在server log中写入写入一条相关信息。可以通过设置为0禁用。

## 创建检查点具体过程

### CreateCheckPoint具体过程

当PostgreSQL触发checkpoint发生的条件后，会调用CreateCheckPoint函数创建具体的检查点，具体过程如下：

1. 遍历所有的数据buffer，将脏页块状态从BM\_DIRTY改为BM\_CHECKPOINT\_NEEDED，表示这些脏页将要被checkpoint刷新到磁盘
2. 调用CheckPointGuts函数将共享内存中的脏页刷出到磁盘
3. 生成新的Checkpoint 记录写入到XLOG中
4. 更新控制文件、共享内存里XlogCtl的检查点相关成员、检查点的统计信息结构

PostgreSQL 控制文件pg\_control里存储的数据是一个ControlFileData结构，具体如下：

```
typedefstruct ControlFileData
{
    uint64    system_identifier;
    uint32    pg_control_version;     /*PG_CONTROL_VERSION */
    uint32    catalog_version_no;     /* seecatversion.h */
    DBState      state;       /* see enum above */
    pg_time_t time;        /* time stamp of last pg_control update */

        XLogRecPtrcheckPoint;/* 最近一次创建checkpoint的LSN*/
        XLogRecPtrprevCheckPoint; /* 最近一次之前创建checkpoint的LSN */
        /*由于一个检查点的时间比较长，所以有可能系统在所有页面写完之前崩溃，这样磁盘上的检查点可能是不完全的，因此将最后一个完全检查点位置写在prevCheckPoint上*/

CheckPointcheckPointCopy; /* 最近一次checkpoint对应的CheckPoint对象 */

XLogRecPtrminRecoveryPoint;
TimeLineIDminRecoveryPointTLI;
XLogRecPtrbackupStartPoint;
XLogRecPtrbackupEndPoint;
boolbackupEndRequired;
   ......
```

其中，minRecoveryPoint和minRecoveryPointTLI确定数据库启动前，如果做归档恢复，我们必须恢复到的最小检查点。其中minRecoveryPoint指向该检查点对应的LSN位置，minRecoveryPointTLI指向该检查点对应的时间线。其具体的用法，我们将在之后的PostgreSQL崩溃恢复中分析，这里我们主要分析下PostgreSQL中的时间线概念。

PostgreSQL中WAL日志段名称，由时间线ID、日志ID、段ID的八位16进制数依次构成。例如：

| 00000001      | 00000001 | 0000008F |
| ------------- | -------- | -------- |
| 时间线TimeLineID | 逻辑日志ID   | 段ID      |

其中时间线是作为日志段名称的一部分，用来标识数据库归档恢复后产生的一系列新的WAL记录。在每次归档恢复完成后，都会产生一个新的时间线和新的WAL日志段。时间线可以理解为平行时空中的各个平行宇宙，我们完全可以恢复到某个时间点，重开一条时间线，继续进行数据操作，这样就可以实现完全的PTIR。

在PostgreSQL中，一个新的时间线产生，系统伴随它会建立一个以“新TimeLineID+.history”命名的“时间线历史”文件(timeline history)，它是一个类似于txt的文件，其中包含所有在当前时间线以前的时间线，同时记录了每个时间线开始时的第一个WAL段，这样数据库恢复时，通过读取时间线历史文件文件，根据目标时间点可以快速找到正确的日志段文件。如果上一次恢复是恢复到具体某时刻，在时间线历史文件中还会记录该时间线对应的具体时刻。

在PITR恢复时，无需扫描所有WAL日志文件，而是通过时间线直接定位某个WAL段，再从该WAL段中找到符合该时间点的日志记录，这样就大大提高了效率。同时数据库恢复时，默认是沿着基备份开始时的时间点进行，即利用从基备份完成后产生的第一个日志段文件做恢复，如果想恢复到指定时间点(时间线)，需要在recovery.conf配置文件中设置目标时间线(target timeline ID)，但是target timeline ID不能指定为基备份以前的时间线。

### CheckPointGuts函数

CheckPointGuts函数将共享内存里的数据刷出并文件同步到磁盘，具体定义如下：

```
staticvoid
CheckPointGuts(XLogRecPtrcheckPointRedo,int flags)
{
   CheckPointCLOG();
   CheckPointSUBTRANS();
   CheckPointMultiXact();
   CheckPointPredicate();
   CheckPointRelationMap();
   CheckPointBuffers(flags);   /* performs all required fsyncs */
   /* We deliberately delay 2PC checkpointingas long as possible */
   CheckPointTwoPhase(checkPointRedo);
}
```

可以看出，CheckPointGuts根据不同的缓存类型，把clog、subtrans、multixact、predicate、relationmap、buffer（数据文件）和twophase相应缓存分别调用不同的方法，将缓存刷到磁盘中：

- 提交事务日志管理器的方法CheckPointClog
- 子事务日志管理器的方法CheckPointSUBTRANS
- 多事务日志管理器的方法CheckPointMultiXact
- 支持序列化事务隔离级别的谓词锁模块的方法CheckPointPredicate
- 目录/系统表到文件节点映射模块的方法CheckPointRelationMap
- 缓存管理器的方法CheckPointBuffers
- 两阶段提交模块的方法CheckPointTwoPhase

其中，前四个函数最后都调用了SLRU模块的SimpleLruFlush（简单最近最少使用）方法，把相应的共享内存数据写到磁盘，并通过调用pg\_fsync方法把相应文件刷到磁盘上对应文件。

后二个函数没有使用SLRU算法，直接调用pg\_fsync方法把相应文件刷到磁盘上对应文件。

而目录/系统表到文件节点映射模块的方法CheckPointRelationMap，会将共享内存里系统表和对应物理文件映射的map文件刷到磁盘。

## 总结

至此，我们大体了解了checkpoint的用法和整个实现过程，但是还需要对一些特别的地方做出说明。

- 每个检查点后，第一次数据页的变化会导致整个页面会被记录在XLOG日志中
- 检查点的开销比较高，可以用checkpoint\_warning自检，相应调大checkpoint\_segments
- 检查点的位置保存在文件 pg\_control，pg\_control文件被损坏可能会导致数据库不可用

其中，如果pg\_control文件损坏，在数据库崩溃恢复时可能出现一些问题，这些问题我们将在分析PostgreSQL数据库崩溃恢复时具体分析。