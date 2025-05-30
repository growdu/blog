## WAL机制简介

WAL即 Write-Ahead Logging，是一种实现事务日志的标准方法。WAL 的中心思想是先写日志，再写数据，数据文件的修改必须发生在这些修改已经记录在日志文件中之后。采用WAL日志的数据库系统在事务提交时，WAL机制可以从两个方面来提高性能：

- 多个client写日志文件可以通过一次 fsync()来完成
- 日志文件是顺序写的，同步日志的开销要远比同步数据页的开销要小

总体来说，使用了WAL机制之后，磁盘写操作只有传统的回滚日志的一半左右，大大提高了数据库磁盘I/O操作的效率，从而提高了数据库的性能。

采用了WAL机制，就不需要在每次事务提交的时候都把数据页冲刷到磁盘，如果出现数据库崩溃， 我们可以用日志来恢复数据库，任何尚未附加到数据页的记录都将先从日志记录中重做（这叫向前滚动恢复，也叫做 REDO）。对于PostgreSQL来说，未采用WAL机制之前，如果数据库崩溃，可能存在数据页不完整的风险，而WAL 在日志里保存整个数据页的内容，完美地解决了这个问题。

## WAL机制实现

实现WAL机制，需要保证脏页在刷新到磁盘前，该数据页相对应的日志记录已经刷新到磁盘中。为了实现WAL机制，当PostgreSQL进行事务提交（脏数据页需要刷新到磁盘）时，需要进行如下操作：

- 生成该事务提交的日志记录（唯一标示为LSN–Log sequence number）
- 将该LSN之前的xlog日志刷入到磁盘中

### LSN标记

为了标记每个数据页最后修改它的日志记录号，在每个数据页的PageHeaderData结构中引入了一个LSN标记，如下：

```
typedef struct PageHeaderData
{
PageXLogRecPtr pd_lsn; //指向最后修改页面的日志记录
uint16pd_checksum;
uint16    pd_flags;
LocationIndex  pd_lower;
LocationIndex  pd_upper;
LocationIndex  pd_special;
uint16   pd_pagesize_version;
TransactionId     pd_prune_xid; 
ItemIdData       pd_linp[1];
} PageHeaderData;
```

其中PageXLogRecPtr结构是一个无符号的64位整数，它的含义如下：

| 32位     | 8位  | 13位 | 11位  |
| ------- | --- | --- | ---- |
| 逻辑日志文件号 | 段号  | 块号  | 块内偏移 |

PageXLogRecPtr结构和每个日志记录一一对应，同时LSN是全局统一管理，顺序增加的。

当缓冲区管理器(Bufmgr)写出脏数据页时，必须确保小于页面PageHeaderData中pd\_lsn指向的Xlog日志已经刷写到磁盘上了。这里的LSN检查只用于共享缓冲区，用于临时表的local缓冲区不需要，因此临时表是没有WAL日志的，不受WAL机制的保护。

### WAL共享缓存区

为了进一步的减少xlog日志文件的I/O操作，PostgreSQL中引入了WAL共享缓存区，对产生的xlog日志进行缓存，合并I/O操作。

WAL共享缓存区的大小可以通过设置postgresql.conf文件参数wal\_buffers来设置，官方解释如下：

- 表示WAL共享缓存区的大小，和oracle中的log buffer类似，单位可以是kB, MB
- 默认值为-1，表示大小占shared\_buffers大小的1/32，但是大于64kB，小于16MB
- 用户可以自己设置，小于32kB的值会被转化为32kB
- 只能在服务启动之前设置

可以看出，当多个client同时进行事务提交时，如果这个缓存区比较大，相应地会更大程度地合并I/O，提高性能，但是如果过大，同时也存在断电后，这部分数据丢失的风险。所以，这里比较推荐使用默认值，即shared\_buffers的1/32。

为了标示当前WAL共享缓存区的状态，引入了XLogCtlData结构如下：

```
typedef struct XLogCtlData
{
XLogwrtRqst LogwrtRqst;/* 表示当前请求写入系统缓冲区或同步写入磁盘的日志位置*/
XLogRecPtrasyncXactLSN;/*最近需要异步提交的日志位置*/
XLogwrtResult LogwrtResult;/*当前已经写入系统缓冲区或者同步写入磁盘的日志位置*/
XLogRecPtr   *xlblocks;/* LSN数组*/
intXLogCacheBlck;/* WAL缓存区的大小，单位为页 */
        char              *pages;      /* 指向WAL缓存Buffer的首地址 */
......
}
```

其中，LogwrtRqst表示当前请求写入系统缓冲区或同步写入磁盘的日志位置，由info\_lck轻量锁保护，结构如下：

```
typedef struct XLogwrtRqst
{
XLogRecPtr     Write;
XLogRecPtr  Flush;
} XLogwrtRqst;
```

这里需要**注意**的是，因为很多操作系统会维护一个操作系统缓存，用来对磁盘的I/O操作进行合并，这就可能造成操作系统返回给内核写文件成功的地址和真实文件写到磁盘的地址是有差异的。为了区分这个差异，这里引入了2个变量，其中：

- Write表示在此位置之前的日志记录已经写出Wal缓冲区，可能在操作系统缓存区
- Flush表示的是在此位置之前的日志已经写入到磁盘

asyncXactLSN是一个XLogRecPtr类型的成员变量，表示最近需要异步提交的日志位置，并且也是由info\_lck锁来保护。

在PostgreSQL中，日志记录刷写到磁盘有两种提交方式：同步和异步。其区别如下：

- synchronous\_commit参数（默认值为ON）为ON，则为同步方式。事务提交时，对应的Xlog日志必须马上刷新回磁盘事务才能返回成功
- synchronous\_commit参数为OFF，则为异步方式。事务提交时，立刻返回用户成功，同时更新asyncXactLSN

异步提交的提出主要是为了很多短事务（本身执行时间非常短）能立即提交。但是同时，也会打破WAL机制，造成数据库崩溃后数据丢失的危险。在PostgreSQL中，这个参数用户可以在连接中使用SET语句直接设置，实现异步日志提交和同步日志提交的切换，既减少数据丢失风险又能兼顾效率。

LogwrtResult表示当前已经写入系统缓冲区或者同步写入磁盘的日志位置，由info\_lck 和 WALWriteLock 锁保护，结构如下：

```
typedef struct XLogwrtResult
{
XLogRecPtr   Write;
XLogRecPtr  Flush;
} XLogwrtResult;
```

可以看出，XLogwrtResult和XLogwrtRqst的结构相同，其原因也是为了区分是否真正写入到磁盘。

Xlblocks是一个XLogRecPtr \*类型的成员变量，表示指向每个WAL缓存开始的LSN数组的首地址，可以根据这个变量加上日志缓存的偏移量就可以得到具体的对应LSN。

XLogCacheBlck是一个int类型的成员变量，表示缓冲区的大小，单位为块，系统会根据此块进行日志缓存Buffer的具体分配。

pages是一个char \*类型的成员变量，表示指向日志缓存Buffer的首地址的指针，通过偏移量直接定位到哪块日志缓存Buffer，不过需要注意的是，内存日志缓存中存放的日志块，大小不固定，所以2个Buffer的大小可以不一致。

WAL缓存区可以理解为一个环形的共享缓存，每次缓存空间满后，会将头部的页面刷新到磁盘，同时写入新的页面，并将头部往后移动一位。具体来说，需要写入新的日志记录时:

- 当WAL缓存区中有足够的空间，顺序写入到缓存区中。
- 当WAL缓存区写到尾部且空间不足时，从头部刷出信息后重复利用。

因为WAL缓存区是顺序刷出的，这样日志文件中的信息必然是连续的。

为了更好的维护和管理WAL的刷盘，PostgreSQL提供辅助进程Walwriter 预发式日志写进程，Walwriter会周期性地将xlog日志块写入到磁盘。此时，刷新xlog日志页到磁盘的时机有以下几个：

- 事务提交
- Walwriter进程到达间歇时间
- 创建checkpoint
- WAL缓存区满

其中，checkpoint会强制将所有数据缓存中的脏页刷新到磁盘，所以对应的xlog日志页必须在这之前刷新到磁盘。

### Walwriter 预发式日志写进程

数据库启动时，通过调用main()->PostmasterMain()->StartupDataBase()->WalWriterMain()启动Walwriter 辅助进程，Walwriter进程从Postmaster进程中startup子进程一结束就启动，一直保留到Postmaster进程命令其结束。

其中WalWriterMain()的具体步骤如下：

1. 变量初始化

2. 注册信号函数

3. 运行环境初始化
   
   a. 通过ResourceOwnerCreate函数创建一个名为”Wal Writer”的资源跟踪器 b. 为WalWriter创建运行内存上下文，并将运行环境切换到新创建的内存上下文中

4. 注册异常处理

5. 进入服务循环
   
   a. 处理信号分支 b. 调用XLogBackgroundFlush() c. 完成写Xlog后进入休眠，休眠时间可以根据对应的Xlog日志写出频率进行调节

6. Walwriter进程退出。

接下来，具体讲下核心函数XLogBackgroundFlush()。它主要是定位需要刷回磁盘的Xlog日志的开始位置和结束位置传递给XLogWrite()函数进行写日志操作，具体步骤如下：

1. 初始化局部变量

2. 判断数据库是否在恢复过程中，如果是，则返回false，无需写回磁盘。

3. 在锁的保护下访问日志控制信息xlogctl
   
   a. 初始化已经写入系统缓冲区和磁盘的日志位置LogwrtResult = xlogctl->LogwrtResult b. 初始化当前请求写入系统缓冲区的日志位置 WriteRqstPtr = xlogctl->LogwrtRqst.Write c. 为了保证WalWriter以页为单位进行写日志操作，这里会把请求写入系统缓冲区的日志位置WriteRqstPtr调整为页尾

4. 比较WriteRqstPtr 和LogwrtResult.Flush，确定刷新到磁盘的头尾地址
   
   a. 如果前者大于后者，表示当前请求有需要刷回磁盘的日志，转到6 b. 如果前者小于等于后者，即当前请求写入系统缓冲区的日志位置已经刷新至磁盘，没有需要刷回磁盘的日志，则考虑异步提交的日志情况，将WriteRqstPtr 赋值为xlogctl->asyncXactLSN c. 再一次比较现在的WriteRqstPtr 和LogwrtResult.Flush，如果依然是前者小于等于后者，则关闭当前的日志文件，并返回false，否则转到6

5. 调用XLogWrite刷写页面到磁盘
   
   a. 等待日志写锁WALWriteLock，获得该锁之后，重新把LogwrtResult 赋值为XLogCtl->LogwrtResult b. 比较WriteRqstPtr 和LogwrtResult.Flush，如果前者大于后者，调用XLogWrite，并释放锁。否则，释放锁，返回false。

XLogWrite函数的具体步骤如下：

1. 初始化局部变量

2. 进入循环：
   
   a. 初始化需要刷新到磁盘的最后位置，并且打开相应的日志文件openLogFile，如果不存在该日志文件，则创建一个对应的日志文件
   
   b. 判断当前是否满足以下三个条件之一，转入c，否则转入d： - 当前位置满一段 - 缓冲区全部刷新到磁盘 - 请求之前的日志记录全部刷新到磁盘
   
   c. 刷新缓存到磁盘 - 执行系统函数\_write，将标记位置的日志记录刷新到磁盘（可能是缓冲区） - 其中如果满一段，为了减少切换日志段文件带来的开销，应立即执行系统函数\_commit强制将日志记录刷新到磁盘（真正的磁盘） - 唤醒WalSender进程和XlogArch日志归档进程，判断是否需要创建检查点。
   
   d. 判断这次写是否不足页，如果不足页则更新已经写出的日志位置为当前请求写日志的位置，不足页仅发生在这次写日志写最后一页的时候，因此请求写日志之前的日志已经全部写出，跳出循环。
   
   e. 更新需要刷新到磁盘的最后位置为下一页

3. 更新全局变量XLogCtl；释放锁

除了Walwriter 预发式日志写进程之外，其他的进程如果满足刷新xlog日志页到磁盘的时机，也可以直接调用XLogWrite函数。

至此，我们已经完成对PostgreSQL WAL机制原理和实现的大体介绍。WAL机制的思想比较简单，先日志落盘，后数据落盘，但是在实现过程中会有很多细节的考量，至于涉及到的checkpoint机制以及数据库崩溃的处理，这些将在后续逐步分享。