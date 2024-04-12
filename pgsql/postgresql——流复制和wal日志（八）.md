## 一、什么是流复制

PostgreSQL通过wal日志来传送的方式有两种：基于文件的日志传送和流复制。  
不同于基于文件的日志传送，流复制的关键在于“流”，所谓流，就是没有界限的一串数据，类似于合理的水流，是连成一片的。因此流复制允许一台后备服务器比使用基于文件的日志传送更能保持为最新的状态。  
比如我们有一个大文件要从本地主机发送到远程主机，如果是按照“流”接收到的话，我们可以一边接收，一边将文本流存入文件系统。这样，等到“流”接收完了，硬盘写入操作也已经完成。

## **1、流复制发展历史**

pg在流复制出现之前，使用的就是基于文件的日志传送：对wal日志进行拷贝，因此从库始终落后主库一个日志文件，并且使用rsync工具同步data目录。

流复制出现是从2010年推出的pg9.0开始的，其历史大致为：

-   **起源**：pg9.0开始支持流式物理复制，用户可以通过流式复制，构建只读备库(主备物理复制，块级别一致)。流式物理复制可以做到极低的延迟(通常在1毫秒以内)。
-   **同步流复制**：pg9.1开始支持同步复制，但是当时只支持一个同步流复制备节点(例如配置了3个备，只有一个是同步模式的，其他都是异步模式)。同步流复制的出现，保证了数据的0丢失。
-   **级联流复制**：pg9.2支持级联流复制。即备库还可以再连备库。
-   **流式虚拟备库**：pg9.2还支持虚拟备库，即就是只有WAL，没有数据文件的备库。
-   **逻辑复制**：pg9.4开始可以实现逻辑复制，逻辑复制可以做到对主库的部分复制，例如表级复制，而不是整个集群的块级一致复制。
-   **增加多种同步级别**：pg9.6版本开始可以通过synchronous\_commit参数，来配置事务的同步级别。

## **二、wal日志（预写日志）**

介绍流复制首先要了解wal日志，下面将介绍什么是wal日志

## **1、wal日志是什么**

预写式日志（Write Ahead Log，WAL）是保证数据完整性的一种标准方法。

数据库在写入或者修改时，会把相应的数据读到内存中，在内存中进行修改，并记录到wal日志中，而不是直接写到磁盘中，并按照一定的规律把wal中的数据刷到磁盘中；从wal日志刷盘时时孙顺序IO，比随机IO效率高很多。

AL也使得在线备份和时间点恢复能被支持。通过归档WAL数据，我们可以支持回转到被可用WAL数据覆盖的任何时间

## 2、wal日志格式

wal日志位置在$PGDATA/pg\_wal目录中（PostgreSQL从10版本开始，将所用xlog相关的全部用wal替换了）。任何试图修改数据库数据的操作都会写一份日志到磁盘。

wal命名格式文件名称为16进制的24个字符组成，每8个字符一组，每组的意义如下：

```
00000001 00000000 00000001
-------- -------- --------
时间线    LogID     LogSeg

时间线：英文是timeline，从1开始递增的数字,如果数据库通过wal日志进行过恢复，就+1
LogID：32bit长的数字，从0开始递增的数字
LogSeg：2bit长的数字，从0开始递增的数字，16进制

LogID：当LogSeg的最后两位变成FF，在生成一个时，LogID就会+1，如下：

00000001 00000000 000000FD
00000001 00000000 000000FE
00000001 00000000 000000FF
00000001 00000001 00000001
```

### 查看当前正在用的wal日志文件

```
##################方式一##########################
postgres=# select pg_current_wal_lsn();
 pg_current_wal_lsn 
--------------------
 0/70001B0
(1 row)

postgres=# select pg_walfile_name('0/70001B0');
     pg_walfile_name      
--------------------------
 00000001000000000000000E
(1 row)

##################方式二##########################
postgres=# select pg_walfile_name(pg_current_wal_lsn());
     pg_walfile_name      
--------------------------
 00000001000000000000000E
(1 row)

```

## 3、wal日志内部布局

一个wal日志默认16M，大约能记录几十万个事务日志

### 事务日志的格式

[![](https://learnforfuture.top/attachment/20230831/ab2762d3c57543729510f3fdda0d6a27.jpg)](https://learnforfuture.top/attachment/20230831/ab2762d3c57543729510f3fdda0d6a27.jpg)

**一个事务由Header+data组成，wal共记录了3种类型，除了事务，还有检查点和数据库：**

1.  Backup block,把数据块放在wal日志文件中
2.  XLOG record of INSERT statement：记录插入的数据
3.  Check Point:记录检查点的信息

## 4、wal的写处理

pg数据库有一个专门的写进程：walwriter

```
[postgres@pg1 ~]$ ps -ef|grep postgre
postgres   1323   1318  0 03:25 ?        00:00:00 postgres: walwriter
```

**wal日志中的内容：**

pg数据库会把事务做一个格式化，形成一个pg能够读懂的格式

## 5、wal切换和归档

单个wal日志写满(默认大小16MB，编译数据库时指定)继续写下一个wal日志，直到磁盘剩余空间不足min\_wal\_size时才会将旧的 WAL文件回收以便继续使用。

wal日志文件默认为 16MB，这个值可以在编译 PostgreSQL 时通过参数 "--with-wal-segsize" 更改，编译则后不能修改。

### 3.1、wal日志切换

1.  一个日志文件写满后会切换
2.  人为切换，手动切换WAL日志
3.  主备复制时，archive\_mode和archive\_timeout参数，强制主从切换，避免主库和异步库数据差异太大

手动切换命令：

```
--PG10之前切换WAL log
select pg_switch_xlog();
--PG10之后切换WAL log
select pg_switch_wal();
```

### 3.2、wal日志归档

wal日志写满后会自动归档，在postgresql.conf 文件中的参数archive\_timeout，如果设置archive\_timeout=60s，意思是，wal日志60s切换一次，同时会触发日志归档。

尽量不要把archive\_timeout设置的很小，如果设置的很小，会很消耗归档存储，因为强制归档的日志，即使没有写满，也会是默认的16M（假设wal日志写满的大小为16M）

```
archive_mode = on # 当启用archive_mode时，可以通过设置 archive_command命令将完成的 WAL 段发送到 归档存储。
archive_command = 'cp %p /pgarch/pg_arch/%p' 

archive_command：表示归档的命令%p:wal日志文件名 %f:归档文件名
```

## 4、wal日志的清理

在没有开启归档的情况下：9.5以后，如果超过了max\_wal\_size，那么就会删除不需要的wal。

如果开启了归档，那么归档成功了，才会被清除，所以这里注意一下，如果你开启了归档，但是归档命令是失效的，那么wal目录会一直增长，不会自动删除WAL，会使得此目录被撑爆。

### 4.1、什么情况下系统自动清理wal

1.  做检查点的时候
2.  数据库启动的时候，或者修改了相关参数后重启数据库。

### 4.2、手动清理wal日志

```
pg_controldata
Latest checkpoint location:           0/1000098
Latest checkpoint's REDO location:    0/1000060
Latest checkpoint's REDO WAL file:    000000010000000000000002

这里表示0/1000060检查点已经执行，已经包含在000000010000000000000002日志文件中，那么这个日志之前的日志是可以清理的。可以使用系统命令rm清理或者pg_archivecleanup清理

--保留000000010000000000000002之后的日志
pg_archivecleanup /pgdb/pgdata/pg_wal/  000000010000000000000002
```

注意：pg\_wal日志没有设置保留周期的参数，即没有类似mysql的参数expire\_logs\_days，pg\_wal日志永久保留，除非shell脚步删除几天前或pg-rman备份时候设置保留策略。

## 5、数据落盘

### Checkpoints 检查点，checkpoint发生时：将所有data buffer刷新的磁盘。

### 5.1、哪些情况会触发数据库的checkpoing

1.  手动执行CHECKPOINT命令；
2.  执行需要检查点的命令（例如pg\_start\_backup 或pg\_ctl stop|restart等等）；
3.  达到检查点配置时间(checkpoint\_timeout)；
4.  max\_wal\_size已满。

### 5.2、Checkpoints相关参数

```
checkpoint_timeout： 自动 WAL 检查点之间的最长时间，以秒计。合理的范围在 30 秒到 1 天之间。默认是 5 分钟(5min)。
max_wal_size：在自动WAL检查点使得WAL增长到最大尺寸。这是软限制；特殊情况下WAL大小可以超过 max_wal_size，如重负载下，错误archive_command，或者 较大wal_keep_segments的设置。缺省是1GB。
min_wal_size ：  # 只要WAL磁盘使用率低于这个设置，旧的WAL文件总数被回收，以供将来检查点使用。
checkpoint_timeout = 5min       # range 30s-1d 自动 WAL 检查点之间的最长时间。如果指定值时没有单位，则以秒为单位。 合理的范围在 30 秒到 1 天之间。默认是 5 分钟（5min）。增加这个参数的值会增加崩溃恢复所需的时间。
```

## 二、流复制的配置

## 1、主节点的配置参数

```
[postgres@pg1 ~]$ vim /pgdb/pgdata/postgresql.conf

# - 连接设置 Connection Settings -
listen_addresses = '0.0.0.0'            # what IP address(es) to listen on;
port = 5432
max_connections = 3000                  # (change requires restart)
tcp_keepalives_idle = 60             #指定不活动多少秒之后通过 TCP 向客户端发送一个 keepalive 消息。
tcp_keepalives_interval = 10         #指定在多少秒之后重发一个还没有被客户端告知已收到的 TCP keepalive 消息
tcp_keepalives_count = 10            #指定与客户端的服务器连接被认为死掉之前允许丢失的 TCP keepalive 数量

# - 内存 -
shared_buffers = 1GB                    # min 128kB,一个合理的shared_buffers开始值是系统内存的 25%
huge_pages = off                        #启用/禁用巨型内存页面的使用。
temp_buffers = 8MB                      #设置每个数据库会话使用的临时缓冲区的最大数目。这些都是会话的本地缓冲区
work_mem = 4MB                         # 指定在写到临时磁盘文件之前被内部排序操作和哈希表使用的内存量
maintenance_work_mem = 512MB            # 指定在维护性操作（例如VACUUM、CREATE INDEX和ALTER TABLE ADD FOREIGN KEY）中使用的 最大的内存量。
dynamic_shared_memory_type = posix      # 指定服务器应该使用的动态共享内存实现。默认posix

# - 基于代价的清理延迟 -
vacuum_cost_delay = 10                   # 进程超过代价限制后将休眠的时间长度，以毫秒计。其默认值为0，
vacuum_cost_limit = 1000                # 将导致清理进程休眠的累计代价。默认值为200

# - 后台写入器 -
bgwriter_delay = 10ms                   # 指定后台写入器活动轮次之间的延迟。
bgwriter_lru_maxpages = 1000            # 在每个轮次中，不超过这么多个缓冲区将被后台写入器写出。
bgwriter_lru_multiplier = 10.0          # 每一轮次要写的脏缓冲区的数目基于最近几个轮次中服务器进程需要的新缓冲区的数目。
bgwriter_flush_after = 256              # 不管何时 bgwriter 写入了超过bgwriter_flush_after字节， 尝试强制 OS 把这些写发送到底层存储上。
# 注：较小的bgwriter_lru_maxpages和bgwriter_lru_multiplier可以降低由后台写入器造成的额外 I/O 开销。但更可能的是，服务器进程将必须自己发出写入操作，这会延迟交互式查询。


# - 异步行为 -
max_worker_processes = 128             # 设置系统能够支持的后台进程的最大数量。这个参数只能在服务器启动时设置。
max_parallel_workers_per_gather = 0    # 设置单个Gather节点能够开始的工作者的最大数量。
old_snapshot_threshold = -1             设置在使用快照时，一个快照可以被使用而没有发生snapshot too old 错误风险的最小时间。 # 值为-1会禁用这个特性，并且这个值是默认值。                                
backend_flush_after = 0               # 只要一个后端写入了超过backend_flush_after字节， 就会尝试强制 OS 把这些写发送到底层存储。# 合法的范围位于0 （禁用受控写回）和2MB之间。默认是0（即没有刷写控制）
                                
-----------------------------
# 预写式日志 
-----------------------------
wal_level = replica                   # minimal, replica, or logical
                                      # wal_level决定多少信息写入到 WAL 中。默认值是minimal， 只写入从崩溃或立即关机恢复所需要的信息。
                                      # archive添加 WAL 归档所需要的日志。 hot_standby则进一步增加在一个后备服务器上运行只读查询所需的信息。 最后，logical会增加支持逻辑解码所需的信息。
                                      # 为了在一个后备服务器上启用只读查询，主服务器上的wal_level必须设置为hot_standby或更高级别， 并且后备服务器上必须启用hot_standby。
fsync = on                             # 如果打开这个参数，PostgreSQL服务器将尝试确保更新被物理地写入到磁盘，做法是发出fsync()系统调用或者使用多种等价的方法
synchronous_commit = on                # 指定在命令返回“success”指示给客户端之前，一个事务是否需要等待 WAL 记录被写入磁盘。
full_page_writes = on                  # 当这个参数为打开时，PostgreSQL服务器在一个检查点之后的页面的第一次修改期间将每个页面的全部内容写到 WAL 中。默认值是on
wal_log_hints = on                      # 当这个参数为on时，PostgreSQL服务器一个检查点之后页面被第一次修改期间把该磁盘页面的整个内容都写入 WAL，即使对所谓的提示位做非关键修改也会这样做。
wal_buffers = -1                       # 默认值 -1 选择等于shared_buffers的 1/32 的尺寸（大约3%）
wal_writer_delay = 10ms               # 指定 WAL 写入器的活动轮次之间的延迟。在每个轮次中写入器会将 WAL 刷到磁盘。
wal_writer_flush_after = 4MB           # 刷新wal数据，默认为1m（脏数据超过阈值，将被刷新到磁盘）
commit_delay = 0                       # 在一次 WAL 刷写被发起之前，commit_delay增加一个时间延迟，以微妙计。

# - Checkpoints 检查点 -
checkpoint_timeout = 10min              #自动 WAL 检查点之间的最长时间。如果指定值时没有单位，则以秒为单位
max_wal_size = 1GB                      # 在自动WAL检查点使得WAL增长到最大尺寸。这是软限制
min_wal_size = 200MB                    # 只要WAL磁盘使用率低于这个设置，旧的WAL文件总数被回收，以供将来检查点使用。
checkpoint_completion_target = 0.8     # 指定检查点完成的目标，作为检查点之间总时间的一部分。
checkpoint_flush_after = 1MB         # 在执行检查点时，只要有checkpoint_flush_after字节被写入， 就尝试强制 OS 把这些写发送到底层存储。

# - Archiving -
archive_mode = on              # 当启用archive_mode时，可以通过设置 archive_command命令将完成的 WAL 段发送到 归档存储。
archive_command = 'cp %p /pgarch/pg_arch/%f'              # command to use to archive a logfile segment

#------------------------------------------------------------------------------
# 复制
#------------------------------------------------------------------------------
# - 发送服务器(s) -
max_wal_senders = 6           # 指定来自后备服务器或流式基础备份客户端的并发连接的最大数量（即同时运行 WAL 发送进程 的最大数）
wal_keep_segments = 1024       # 指定在后备服务器需要为流复制获取日志段文件的情况下，pg_xlog目录下所能保留的过去日志文件段的最小数目。每个段通常是 16 兆字节。
wal_sender_timeout = 60s       # 中断那些停止活动超过指定毫秒数的复制连接。
max_replication_slots = 10     # 指定服务器可以支持的复制槽最大数量。默认值为零。

# - 主服务器 -
synchronous_standby_names = 'pg2' #  这个参数指定一个支持同步复制的后备服务器的列表。'*' = all
# - 后备服务器 -
hot_standby = on                       # 指定在恢复期间，你是否能够连接并运行查询
max_standby_archive_delay = 30s        # 当热后备机处于活动状态时，这个参数决定取消那些与即将应用的 WAL 项冲突的后备机查询之前，后备服务器应该等待多久
max_standby_streaming_delay = 30s      # 当热后备机处于活动状态时，这个参数决定取消那些与即将应用的 WAL 项冲突的后备机查询之前，后备服务器应该等待多久
wal_receiver_status_interval = 2s       # 指定在后备机上的 WAL 接收者进程向主服务器或上游后备机发送有关复制进度的信息的最小频度
hot_standby_feedback = on               # 指定一个热后备机是否将会向主服务器或上游后备机发送有关于后备机上当前正被执行的查询的反馈。

#------------------------------------------------------------------------------
# QUERY TUNING
#------------------------------------------------------------------------------
random_page_cost = 2.0                 # 设置规划器对一次非顺序获取磁盘页面的代价估计。默认值是 4.0。
effective_cache_size = 1GB            # 设置规划器对一个单一查询可用的有效磁盘缓冲区尺寸的假设。
constraint_exclusion = partition       # 通常被用于继承和分区表来提高性能

#------------------------------------------------------------------------------
# 错误报告和日志
#------------------------------------------------------------------------------
log_destination = 'csvlog'             # PostgreSQL支持多种方法来记录服务器消息，要产生 CSV 格式的日志输出，必须启用logging_collector。
logging_collector = on          # 这个参数启用日志收集器，它是一个捕捉被发送到stderr的日志消息的后台进程，并且它会将这些消息重定向到日志文件中。
                    # into log files. Required to be on for
log_directory = '/pglog'                  # directory where log files are written,
log_filename = 'postgresql-%Y-%m-%d.log'        # log file name pattern,
log_file_mode = 0644                    # creation mode for log files,
log_truncate_on_rotation = on           # 当logging_collector被启用时，这个参数将导致PostgreSQL截断（覆盖而不是追加）任何已有的同名日志文件。
log_rotation_age = 1d                  # 当logging_collector被启用时，这个参数决定一个个体日志文件的最长生命期。
log_rotation_size = 0                  # 当logging_collector被启用时，这个参数决定一个个体日志文件的最大尺寸。
log_min_duration_statement = 1000        # 如果语句运行至少指定的毫秒数，将导致记录每一个这种完成的语句的持续时间。
# - What to Log -
log_checkpoints = on                 # 开启时检查点和重启点被记录在服务器日志中。
log_connections = on                 # 导致每一次尝试对服务器的连接被记录，客户端认证的成功完成也会被记录。
log_disconnections = on              # 记录会话终止原因。
log_error_verbosity = verbose        # 控制为每一个被记录的消息要写入到服务器日志的细节量。
                                     # 有效值是TERSE、DEFAULT和VERBOSE，每一个都为显示的消息增加更多域。
                                    # TERSE排除记录DETAIL、HINT、QUERY和CONTEXT错误信息。
                                    # VERBOSE输出包括SQLSTATE错误码以及产生错误的源代码文件名、函数名和行号。
log_line_prefix = '%t %p %r '           # 这是一个printf风格的字符串，它在每个日志行的开头输出。%字符开始"转义序列"，
log_lock_waits = 1                      # 控制当一个会话为获得一个锁等到超过deadlock_timeout时，是否要产生一个日志消息。
log_timezone = 'PRC'                    # 设置在服务器日志中写入的时间戳的时区

#------------------------------------------------------------------------------
# 自动清理
#------------------------------------------------------------------------------
autovacuum = on                 # 控制服务器是否运行自动清理启动器后台进程。默认为开启
log_autovacuum_min_duration = 0   # 如果自动清理运行至少该值所指定的毫秒数，被自动清理执行的每一个动作都会被日志记录。
autovacuum_max_workers = 8             # max number of autovacuum subprocesses
autovacuum_naptime = 5min              # 指定自动清理在任意给定数据库上运行的最小延迟。
autovacuum_vacuum_cost_delay = 10         # 指定用于自动VACUUM操作中的代价延迟值。
autovacuum_vacuum_cost_limit = 1000       # 指定用于自动VACUUM操作中的代价限制值。

#------------------------------------------------------------------------------
# 客户端连接默认值
#------------------------------------------------------------------------------
# - 语句行为 -
idle_in_transaction_session_timeout = 3600000    # 终止任何已经闲置超过这个参数所指定的时间（以毫秒计）的打开事务的会话。
# - 区域和格式化 -
datestyle = 'iso, ymd'                          # 设置日期和时间值的显示格式，以及解释有歧义的日期输入值的规则
timezone = 'PRC'                                 # 设置用于显示和解释时间戳的时区。内建默认值是GMT
lc_messages = 'zh_CN.UTF-8'                     # 设置消息显示的语言。可接受的值是系统相关的；
lc_monetary = 'zh_CN.UTF-8'                     # 设置用于格式化货币量的区域，例如用to_char函数族。
lc_numeric = 'zh_CN.UTF-8'                      # 设置用于格式化数字的区域，例如用to_char函数族。
lc_time = 'zh_CN.UTF-8'                         # 设置用于格式化日期和时间的区域，例如用to_char函数族。
default_text_search_config = 'pg_catalog.simple'   选择被那些没有显式参数指定配置的文本搜索函数变体使用的文本搜索配置
shared_preload_libraries = 'pg_stat_statements,auto_explain,pg_pathman'  # 这个变量指定一个或者多个要在服务器启动时预载入的共享库。

#------------------------------------------------------------------------------
# 运行时统计数据
#------------------------------------------------------------------------------
track_io_timing = on                     # 启用对每个会话的当前执行命令的信息收集，还有命令开始执行的时间。
track_activity_query_size = 2048          # 启用对每个会话的当前执行命令的信息收集，还有命令开始执行的时间。

# pg_stat_statements 监控SQL模块
pg_stat_statements.max = 10000            # 在pg_stat_statements中最多保留多少条统计信息，通过LRU算法，覆盖老的记录
pg_stat_statements.track = all         # all - (所有SQL包括函数内嵌套的SQL), top - 直接执行的SQL(函数内的sql不被跟踪), none - (不跟踪)
pg_stat_statements.track_utility = off  # 是否跟踪非DML语句 (例如DDL，DCL)，on表示跟踪, off表示不跟踪 
pg_stat_statements.save = on

#------------------------------------------------------------------------------
# 锁管理
#------------------------------------------------------------------------------
deadlock_timeout = 1s                   # 这是进行死锁检测之前在一个锁上等待的总时间（以毫秒计）。
                            # 死锁检测相对昂贵，因此服务器不会在每次等待锁时都运行这个它。

#------------------------------------------------------------------------------
# 错误处理
#------------------------------------------------------------------------------
restart_after_crash = off               # 当被设置为真（默认值）时，PostgreSQL将在一次后端崩溃后自动重新初始化。
# CUSTOMIZED OPTIONS
include '/var/lib/pgsql/tmp/rep_mode.conf' # added by pgsql RA
```

创建用于复制的用户

```
create user repl  REPLICATION  LOGIN ENCRYPTED  PASSWORD 'repl';
```

修改pg.hab.conf

```
host    replication     repl             192.168.56.33/24            md5
host    replication     repl             192.168.56.32/24            md5
```

## 2、同步节点的配置参数

备份数据

```
pg_basebackup -h 192.168.56.32 -U repl -p 5432 -F p   -X s  -v -P -R -D /pgdb/pgdata/ -l postgres32


pg_basebackup命令中的参数说明：

-h 指定连接的数据库的主机名或IP地址，这里就是主库的ip。
-U 指定连接的用户名，此处是我们刚才创建的专门负责流复制的repl用户。
-F 指定生成备份的数据格式，支持p（plain原样输出）或者t（tar格式输出）。
-X 表示备份开始后，启动另一个流复制连接从主库接收WAL日志，有 f(fetch)和s (stream）两种方式，建议使用s方式。
-P 表示显示数据文件、表空间传输的近似百分比 允许在备份过程中实时的打印备份的进度。
-v 表示启用verbose模式，命令执行过程中会打印各阶段日志，建议启用。
-R 表示会在备份结束后自动生成recovery.conf文件，这样也就避免了手动创建。
-D 指定把备份写到哪个目录，这里尤其要注意一点就是做基础备份之前从库的数据目录（/data/postgresql/data）目录需要手动清空。
-l 表示指定个备份的标识，运行命令后可以看到进度提示。
```

#### 修改recovery.conf,以上备份命令中生成了recovery.conf 文件,因此简单修改即可。

```
standby_mode = 'on'
primary_conninfo = 'application_name=pg2 user=repl password=repl123 host=192.168.56.32 port=5432 sslmode=disable sslcompression=0 target_session_attrs=any'
## 添加如下信息
recovery_target_timeline = 'latest'


standby_mode：设置是否启用数据库为备库，如果设置成on，备库会不停地从主库上获取WAL日志流，直到获取主库上最新的WAL日志流
primary_conninfo：设置主库的连接信息，这里设置了主库IP、端口、用户名信息等，此处是明文密码，生产环境建议配置非明文密码，而是将密码配置在另一个隐藏文件中
covery_target_timeline：设置恢复的时间线（timeline），默认情况下是恢复到基准备份生成时的时间线，设置成latest表示从备份中恢复到最近的时间线，通常流复制环境设置此参数为latest，复杂的恢复场景可将此参数设置成其他值
```

## 3、异步节点的

备份数据

```
pg_basebackup -h 192.168.56.32 -U repl -p 5432 -F p   -X s  -v -P -R -D /data/postgresql/data/ -l postgres32


pg_basebackup命令中的参数说明：

-h 指定连接的数据库的主机名或IP地址，这里就是主库的ip。
-U 指定连接的用户名，此处是我们刚才创建的专门负责流复制的repl用户。
-F 指定生成备份的数据格式，支持p（plain原样输出）或者t（tar格式输出）。
-X 表示备份开始后，启动另一个流复制连接从主库接收WAL日志，有 f(fetch)和s (stream）两种方式，建议使用s方式。
-P 表示显示数据文件、表空间传输的近似百分比 允许在备份过程中实时的打印备份的进度。
-v 表示启用verbose模式，命令执行过程中会打印各阶段日志，建议启用。
-R 表示会在备份结束后自动生成recovery.conf文件，这样也就避免了手动创建。
-D 指定把备份写到哪个目录，这里尤其要注意一点就是做基础备份之前从库的数据目录（/data/postgresql/data）目录需要手动清空。
-l 表示指定个备份的标识，运行命令后可以看到进度提示。
```

#### 修改recovery.conf,以上备份命令中生成了recovery.conf 文件,因此简单修改即可。

```
standby_mode = 'on'
primary_conninfo = 'application_name=pg3 user=repl password=repl123 host=192.168.56.32 port=5432 sslmode=disable sslcompression=0 target_session_attrs=any'
## 添加如下信息
recovery_target_timeline = 'latest'


standby_mode：设置是否启用数据库为备库，如果设置成on，备库会不停地从主库上获取WAL日志流，直到获取主库上最新的WAL日志流
primary_conninfo：设置主库的连接信息，这里设置了主库IP、端口、用户名信息等，此处是明文密码，生产环境建议配置非明文密码，而是将密码配置在另一个隐藏文件中
covery_target_timeline：设置恢复的时间线（timeline），默认情况下是恢复到基准备份生成时的时间线，设置成latest表示从备份中恢复到最近的时间线，通常流复制环境设置此参数为latest，复杂的恢复场景可将此参数设置成其他值
```

## 查看流复制

查看流复制

```
select pid,state,client_addr,sync_priority,sync_state from pg_stat_replication;
```