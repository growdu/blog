“时间线”（Timeline）是PG一个很有特色的概念，在备份恢复方面的文档里面时有出现。但针对这个概念的详细解释却很少，也让人不太好理解。我们在此仔细解析一下。

## 时间线的引入

为了理解引入时间线的背景，我们来分析一下，如果没有时间线，会有什么问题？先举个将数据库恢复到以前时间点的例子。假设在一个数据库的运行过程中，DBA在周三12:00AM删掉了一个关键的表，但是直到周五中午才发现这个问题。这个时候DBA拿出最初的数据库备份，加上存在归档目录的日志文件，将数据库恢复到周三11:00AM的时间点，这样就能正常启动和运行。但是，DBA后来意识到这样恢复是不对的，想恢复到周四8:00AM的数据。这时会发现无法做到：因为在数据库不断运行中，会产生与旧的WAL文件重名的文件，这些文件进入归档目录时，会覆盖原来的旧日志，导致恢复数据库需要的WAL文件丢失。为了避免这种情况，需要区分原始数据库历史生成的WAL文件和完成恢复之后继续运行产生的（重名的）新WAL文件。整个过程如图1所示：  
![recover_without_timeline](http://img1.tbcdn.cn/L1/461/1/c89bf19d70683aed6254224c0696f0f71eaf38b9 "recover_without_timeline")

为了解决这个问题，PostgreSQL引入了时间线的概念。每当归档文件恢复完成后，创建一个新的时间线用来区别新生成的WAL记录。WAL文件名由时间线和日志序号组成，源码实现如下：

```
#define XLogFileName(fname, tli, log, seg)    \
    snprintf(fname, XLOG_DATA_FNAME_LEN + 1, "%08X%08X%08X", tli, log, seg)                    
```

例如：

```
$ ls -1
00000002.history
00000003.history
00000003000000000000001A
00000003000000000000001B
```

时间线ID号是WAL文件名组成之一，因此一个新的时间线不会覆盖由以前的时间线生成的WAL。 如图2所示，每个时间线类似一个分支，在当前时间线的操作不会对其他时间线WAL造成影响。有了时间线，我们就可以恢复到之前的任何时间点。  
![recover_with_timeline](http://img3.tbcdn.cn/L1/461/1/325c612ca9d1a5b8c0e9a8e3473888849223d38e "recover_with_timeline")

## 新时间线的出现场景

新的时间线会在什么情况下出现呢？  
**1\. 即时恢复(PITR)**  
配置recovery.conf文件：

```
restore_command = 'cp /mnt/server/archivedir/%f %p' //从归档目录恢复日志 
recovery_target_time = '2015-7-16 12:00:00 ' //指定归档时间点，如没指定恢复到故障前的最后一完成的事务 
recovery_target_timeline = 'latest' //指定归档时间线，’latest’代表最新的时间线分支，如没指定恢复到故障前的pg_control里面的时间线 
standby_mode = ‘off’ //打开后将会以备库身份启动，而不是即时恢复
```

设置好recovery.conf文件后，启动数据库，将会产生新的timeline，而且会生成一个新的history文件。恢复的默认行为是沿着与当前基本备份相同的时间线恢复。如果你想恢复到某些时间线，你需要指定的recovery.conf目标时间线recovery\_target\_timeline，不能恢复到早于基本备份分支的时间点。  
**2\. standby promote**  
搭建一个PG主备，然后停止主库，在备库机器执行：

```
$ pg_ctl promote –D $PGDATA 
```

这时候备库将会升为主备，同时产生一个新的timeline，同样生成一个新的history文件。

## history文件

每次创建一个新的时间线，PostgreSQL都会创建一个“时间线历史”文件，文件名类似.history，它里面的内容是由原时间线history文件的内容再追加一条当前时间线切换记录。假设数据库恢复启动后，切换到新的时间线ID＝5，那么文件名就是00000005.history ，该文件记录了自己从什么时间哪个时间线什么原因分出来的，该文件可能含有多行记录，每个记录的内容格式如下：

```
 * <parentTLI> <switchpoint> <reason>
 *
 *      parentTLI       ID of the parent timeline
 *      switchpoint     XLogRecPtr of the WAL position where the switch happened
 *      reason          human-readable explanation of why the timeline was changed
```

例如：

```
$ cat 00000004.history
1    0/140000C8    no recovery target specified
2    0/19000060    no recovery target specified
3    0/1F000090    no recovery target specified
```

当数据库在从包含多个时间线的归档中恢复时，这些history文件允许系统选取正确的WAL文件。当然，它也能像WAL文件一样被归档到WAL归档目录里。历史文件只是很小的文本文件，所以保存它们的代价很小。  
当我们在recovery.conf指定目标时间线tli进行恢复时，程序首先寻找.history文件，根据.history文件里面记录的时间线分支关系，找到从pg\_control里面的startTLI到tli之间的所有时间线对应的日志文件，再进行恢复。

## 总结

PG中通过timeline机制能够方便地实现数据库恢复到任意时间点，这对我们数据库备份有重要的作用。我们可以在数据库的使用中合理地备份和归档我们的数据，一旦数据出现丢失或损坏，我们都能有条不紊的使用timeline机制恢复出来我们需要的数据。