## 1 **引言**

看下官网的解释，复制槽提供了一种办法确保主库不会“删除”还未发送到备库的WAL日志，也不会删除备库需要的多版本，即使备库掉线。

2 **相关参数**

wal\_keep\_segments：设置为较大值，保证pg\_wal目录下保留较多的wal日志，主库上wal日志留存越多，允许备库宕机的时间越长，设置此参数需要注意不要将pg\_wal目录撑满。或者在主库上开启归档，如果没有足够的硬盘空间保留wal归档，至少在备库停机维护时临时开启主库归档。如果备库落后主库wal\_keep\_segments数量的wal，则主库可能会删除备用服务器仍需要的wal，这种情况下，流复制就会中断。

hot\_standby\_feedback：备库定时将最小活跃事务ID(xmin)告诉master，使得 master在执行vacuum 时对备库还需要的tuple手下留情，但这样可能会导致主库膨胀，在每个wal\_receiver\_status\_interval定义的周期内发送的频率不超过一次，并且此设置不会覆盖在主数据库上的old\_snapshot\_threshold行为。

max\_standby\_streaming\_delay：通常会将一些执行时间较长的分析任务、统计SQL跑在备库上。在备库上执行长时间的查询，由于涉及的记录有可能在主库上被更新或删除，主库上对更新或删除数据的老版本进行vacuum后，从库上也会执行这个操作，从而与从库上的当前查询产生冲突。此参数默认为30s，当备库执行SQL时，有可能与正在应用的WAL发生冲突，此查询如果30s没有执行完就被中止，注意30s不是备库上单个查询允许的最大执行时间，是指当备库上应用WAL时允许的最大WAL延迟应用时间，因此备库上查询的执行时间有可能不到这个值就被中止了，此参数可以设置为\-1，表示当从库上的WAL应用进程与从库上执行的查询冲突时，WAL应用进程一直等待直到从库查询执行完成。

![图片](https://mmbiz.qpic.cn/mmbiz_png/lniadOK6Dzb4Js6Vbw6iaPTWIAUEnmOF4r1RCgMqbobL8nskaNo1Ox1lh3IKZeialGrNjdKdwicG9vkEJQryl9f5Cg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

old\_snapshot\_threshold：单位为min，最大可以设置为60天，当vacuum回收垃圾时，遇到垃圾记录的xmax大于数据库中现存的最早未提交事务xmin时，不会对其进行回收。因此当数据库中存在很久为结束的事务时，可能会导致数据库膨胀。此参数代表强制删除为过老的事务快照保留的死元组。这会导致长事务读取已被删除的tuple时出错。

vacuum\_defer\_cleanup\_age：指定vacuum延迟清理死亡元组的事务数，vacuum会延迟清除无效的记录，延迟的事务个数通过vacuum\_defer\_cleanup\_age进行设置。默认为0，在主库上设置一个稍大的值也可以减少冲突的发生，但是并不太好计量。

max\_standby\_archive\_delay：备机因为处理归档的wal日志产生查询冲突而取消查询之前的等待时间，和上面的参数类似。

recovery\_min\_apply\_delay：延迟备库设置备库延迟重做WAL的时间，而备库依然及时接收主库发送的WAL日志流，只是不是一接收到WAL后就立即应用，而是等待此参数设置的值再应用。使用此功能将延迟hot\_standby\_feedback，当synchronous\_commit设置为remote\_apply时，同步复制也会受此设置的影响，每个commit都需要等待。

## 3 **为啥要设复制槽**

前面所说的那么多参数，只有在主备关系正常时才能起到作用，而replication slot能够确保在主备断连后主库的wal仍不被清理，因为replication slot的状态信息是持久化保存的，即便从库断掉或主库重启，这些信息仍然不会丢掉或失效。

replication slots 是从postgresql 9.4引入的，主要是提供了一种自动化的方法来确保主库在所有的备库收到wal之前不会移除它们，并且主库也不会移除可能导致恢复冲突的行(需要配合hot\_standby\_feedback)，即使备库断开也是如此。

在没有启用replication slots的环境中，如果碰到 ERROR: requested WAL segment xxxx has already been removed 的错误，解决办法是要么提前开启了归档，要么重做slave，另外还可以在主库上设置 wal\_keep\_segments 为更大的值。当然，如果备库停机时间太长，可能主库的WAL日志目录会被撑满，如果设置了复制槽，建议将WAL日志目录放在大容量硬盘上。

## 4 **实战演示**

## 4.1 hot\_standby\_feedback

流复制搭建就不演示了，此处基于PostgreSQL12搭建的，在此就不再赘述，只是要注意原有的recovery.conf没有了，合到了postgresql.conf里面。

postgres=# select usename,client\_addr,backend\_xmin,sync\_state from pg\_stat\_replication ;

 usename  |   client\_addr   | backend\_xmin | sync\_state

\----------+-----------------+--------------+------------

 postgres | 192.168.211.166 |              | sync

(1 row)

我把hot\_standby\_feedback主从都设为了off，查询pg\_replication\_slots可以看到xmin为空

postgres=# select \* from pg\_replication\_slots ;

 slot\_name | plugin | slot\_type | datoid | database | temporary | active | active\_pid | xmin | catalog\_xmin | restart\_lsn | confirmed\_flush\_lsn

\-----------+--------+-----------+--------+----------+-----------+--------+------------+------+--------------+-------------+---------------------

 slot1     |        | physical  |        |          | f         | t      |       3743 |      |              | 4/38A410E0  |

(1 row)

模拟一下冲突的发生，先创建一张测试表test，插入4千万数据：

postgres=# insert into test values(generate\_series(1,40000000));

INSERT 0 40000000

postgres=# analyze test;

ANALYZE

备库上执行一下查询：

postgres=# show hot\_standby\_feedback ;

 hot\_standby\_feedback

\----------------------

 off

(1 row)

postgres=# select count(\*) from test where id = 6666666;

此处夯住...

主库上删除id为6666666的数据，然后做一下vacuum：

postgres=# delete from test where id = 6666666;

DELETE 2

postgres=# vacuum test;

VACUUM

这个时候再去备库上，查询会报错：

postgres=# select count(\*) from test where id = 6666666;

FATAL:  terminating connection due to conflict with recovery

DETAIL:  User query might have needed to see row versions that must be removed.

HINT:  In a moment you should be able to reconnect to the database and repeat your command.

ERROR:  canceling statement due to conflict with recovery

DETAIL:  User query might have needed to see row versions that must be removed.

看下vacuum里的逻辑，

/\*

 \* Deleter committed, but perhaps it was recent enough that some open

 \* transactions could still see the tuple.

 \*/

if (!TransactionIdPrecedes(HeapTupleHeaderGetRawXmax(tuple), OldestXmin))

return HEAPTUPLE\_RECENTLY\_DEAD;

/\* Otherwise, it's dead and removable \*/

return HEAPTUPLE\_DEAD;

}

该函数计算当前tuple的xmax是否大于或等于OldestXmin。xmax是删除这个tuple的事务ID，而OldestXmin由GetOldestXmin函数计算，是所有活跃事务的ID，以及所有事务的xmin 组成的集合中最小的事务ID。所有ID大于这个OldestXmin的事务，都是“新近”开启的事务，其他事务可能需要读取这个旧版本用于查询，所以不能物理删除，则返回HEAPTUPLE\_RECENTLY\_DEAD，保留此tuple。换句话说，就是产生垃圾tuple的事务号，通常在为垃圾tuple的头信息中的xmax版本号大于或等于vacuum开启时数据库中最小的(backend\_xmin, backend\_xid)，这条垃圾tuple就不能被回收，我们可以在pg\_stat\_activity视图中看到这两列，

postgres=# \\d pg\_stat\_activity

                      View "pg\_catalog.pg\_stat\_activity"

      Column      |           Type           | Collation | Nullable | Default

\------------------+--------------------------+-----------+----------+---------

 backend\_xid      | xid                      |           |          |

 backend\_xmin     | xid                      |           |          |

对于repeatable read与serializable隔离级别的事务来说，每一个查询开始时需要获取一个快照，对于read committed隔离级别的事务来说，事务中每条查询开始都会重新获取一个快照，快照中将包含一个xmin值，表示当前数据库中最小的正在运行的事务号，如果没有，则为最小未分配事务号。快照xmin与事务申请的事务号有别，xid表示该事务申请的事务号。PostgreSQL9.6之后可以通过old\_snapshot\_threshold来强制删除为过老的事务快照保留的死元组。

了解了vacuum的逻辑后，我们知道假如session 1查询某行数据，session 2删除该数据，然后commit，执行一次vacuum，我们知道这次vacuum并不会删除该行数据，因为session 1的事务还需要使用该元组，所以不会清理该元组。那么如果是主从呢？主库在准备进行vacuum时怎么知道从库还在进行查询，这就是hot\_standby\_feedback的意义，设置hot\_standby\_feedback参数之后备库会定期向主库通知最小活跃事务id(xmin)，这样使得主库vacuum进程不会清理大于xmin值的事务。但是假如主备之间的网络突然中断，备库就无法向主库正常发送xmin值，如果时间够长，主库在这段时间内还是会清理无用元组，这样网络恢复后就可能发生上面的冲突ERROR：canceling statement due to confilct with recovery。

把主从的hot\_standby\_feedback都设为on，再来模拟一下，我们可以看到pg\_replication\_slots的xmin一列有值了：

postgres=# select \* from pg\_replication\_slots ;

 slot\_name | plugin | slot\_type | datoid | database | temporary | active | active\_pid | xmin | catalog\_xmin | restart\_lsn | confirmed\_flush\_lsn

\-----------+--------+-----------+--------+----------+-----------+--------+------------+------+--------------+-------------+---------------------

 slot1     |        | physical  |        |          | f         | t      |       4034 |  532 |              | 4/38A51988  |

(1 row)

恢复一下环境：

postgres=# drop table test;

DROP TABLE

postgres=# create table test(id int);

CREATE TABLE

postgres=# insert into test values(generate\_series(1,40000000));

INSERT 0 40000000

postgres=# analyze test;

ANALYZE

备库上执行一下查询：

postgres=# select count(\*) from test where id = 6666666;

此处夯住...

主库上删除id为6666666的数据，然后做一下vacuum：

postgres=# delete from test where id = 6666666;

DELETE 1

postgres=# vacuum test;

VACUUM

再去备库上等待查询完成，时间稍长，可以看到并未发生上面的冲突：

postgres=# select count(\*) from test where id = 6666666;

 count

\-------

     1

(1 row)

## 4.2 restart\_lsn

postgres=# \\d pg\_replication\_slots

             View "pg\_catalog.pg\_replication\_slots"

       Column        |  Type   | Collation | Nullable | Default

...

 restart\_lsn         | pg\_lsn  |           |          |

对于restart\_lsn的官方解释是The address (LSN) of oldest WAL which still might be required by the consumer of this slot and thus won't be automatically removed during checkpoints. NULL if the LSN of this slot has never been reserved，意思就是主库checkpoint的时候不会删除这之后的wal日志，以及过早的归档出去，为备库保留着。

postgres=# \\d pg\_replication\_slots

             View "pg\_catalog.pg\_replication\_slots"

       Column        |  Type   | Collation | Nullable | Default

...

 restart\_lsn         | pg\_lsn  |           |          |

postgres=# select pg\_walfile\_name(restart\_lsn) from pg\_replication\_slots ;

     pg\_walfile\_name      

\--------------------------

 00000001000000050000007E

(1 row)

模拟一下，没有复制槽的情况下：

postgres=# select pg\_drop\_replication\_slot('slot1');

 pg\_drop\_replication\_slot

\--------------------------

(1 row)

postgres=# select client\_addr,sync\_state from pg\_stat\_replication ;

   client\_addr   | sync\_state

\-----------------+------------

 192.168.211.166 | sync

(1 row)

postgres=# select \* from pg\_replication\_slots ;

 slot\_name | plugin | slot\_type | datoid | database | temporary | active | active\_pid | xmin | catalog\_xmin | restart\_lsn | confirmed\_flush\_lsn

\-----------+--------+-----------+--------+----------+-----------+--------+------------+------+--------------+-------------+---------------------

(0 rows)

关掉备库：

postgres=# select client\_addr,sync\_state from pg\_stat\_replication ;

 client\_addr | sync\_state

\-------------+------------

(0 rows)

然后主库上频繁的创建表，以及切换WAL日志：

postgres=# create table test2(id int);

^CCancel request sent

WARNING:  canceling wait for synchronous replication due to user request

DETAIL:  The transaction has already committed locally, but might not have been replicated to the standby.

CREATE TABLE

postgres=# select pg\_switch\_wal();

 pg\_switch\_wal

\---------------

 0/3016168

(1 row)

postgres=# create table test3(id int);

^CCancel request sent

WARNING:  canceling wait for synchronous replication due to user request

DETAIL:  The transaction has already committed locally, but might not have been replicated to the standby.

CREATE TABLE

postgres=# select pg\_switch\_wal();

 pg\_switch\_wal

\---------------

 0/4003A50

(1 row)

postgres=# create table test4(id int);

^CCancel request sent

WARNING:  canceling wait for synchronous replication due to user request

DETAIL:  The transaction has already committed locally, but might not have been replicated to the standby.

CREATE TABLE

postgres=# select pg\_switch\_wal();

 pg\_switch\_wal

\---------------

 0/50011A0

(1 row)

postgres=# checkpoint ;

CHECKPOINT

再启动备机，可以看到流复制关系断了，看下日志：

postgres=# select client\_addr,sync\_state from pg\_stat\_replication ;

 client\_addr | sync\_state

\-------------+------------

(0 rows)

2020-03-24 08:32:30.044 PDT \[4178\] FATAL:  could not receive data from WAL stream: ERROR:  requested WAL segment 000000010000000000000003 has already been removed

2020-03-24 08:32:30.132 PDT \[4179\] LOG:  started streaming WAL from primary at 0/3000000 on timeline 1

2020-03-24 08:32:30.132 PDT \[4179\] FATAL:  could not receive data from WAL stream: ERROR:  requested WAL segment 000000010000000000000003 has already been removed

2020-03-24 08:32:35.077 PDT \[4180\] LOG:  started streaming WAL from primary at 0/3000000 on timeline 1

2020-03-24 08:32:35.078 PDT \[4180\] FATAL:  could not receive data from WAL stream: ERROR:  requested WAL segment 000000010000000000000003 has already been removed

2020-03-24 08:32:40.095 PDT \[4181\] LOG:  started streaming WAL from primary at 0/3000000 on timeline 1

2020-03-24 08:32:40.096 PDT \[4181\] FATAL:  could not receive data from WAL stream: ERROR:  requested WAL segment 000000010000000000000003 has already been removed

2020-03-24 08:32:45.089 PDT \[4182\] LOG:  started streaming WAL from primary at 0/3000000 on timeline 1

2020-03-24 08:32:45.089 PDT \[4182\] FATAL:  could not receive data from WAL stream: ERROR:  requested WAL segment 000000010000000000000003 has already been removed

恢复下环境，使用复制槽，看下情况：

postgres=# select client\_addr,sync\_state from pg\_stat\_replication ;

   client\_addr   | sync\_state

\-----------------+------------

 192.168.211.166 | sync

(1 row)

postgres=# select \* from pg\_replication\_slots ;

 slot\_name | plugin | slot\_type | datoid | database | temporary | active | active\_pid | xmin | catalog\_xmin | restart\_lsn | confirmed\_flush\_lsn

\-----------+--------+-----------+--------+----------+-----------+--------+------------+------+--------------+-------------+---------------------

 slot1     |        | physical  |        |          | f         | t      |       4496 |  486 |              | 0/3000060   |

(1 row)

同样的操作，关掉备库：

postgres=# select client\_addr,sync\_state from pg\_stat\_replication ;

 client\_addr | sync\_state

\-------------+------------

(0 rows)

然后主库上频繁的创建表，以及切换WAL日志：

postgres=# create table test1(id int);

^CCancel request sent

WARNING:  canceling wait for synchronous replication due to user request

DETAIL:  The transaction has already committed locally, but might not have been replicated to the standby.

CREATE TABLE

postgres=# select pg\_switch\_wal();

 pg\_switch\_wal

\---------------

 0/3014FF0

(1 row)

postgres=# create table test2(id int);

^CCancel request sent

WARNING:  canceling wait for synchronous replication due to user request

DETAIL:  The transaction has already committed locally, but might not have been replicated to the standby.

CREATE TABLE

postgres=# select pg\_switch\_wal();

 pg\_switch\_wal

\---------------

 0/40011A0

(1 row)

postgres=# create table test3(id int);

^CCancel request sent

WARNING:  canceling wait for synchronous replication due to user request

DETAIL:  The transaction has already committed locally, but might not have been replicated to the standby.

CREATE TABLE

postgres=# select pg\_switch\_wal();

 pg\_switch\_wal

\---------------

 0/5003A50

(1 row)

postgres=# checkpoint ;

CHECKPOINT

postgres=# select client\_addr,sync\_state from pg\_stat\_replication ;

   client\_addr   | sync\_state

\-----------------+------------

 192.168.211.166 | sync

(1 row)

在备库上查一下是否有这些表，可以看到，流复制正常：

postgres=# \\d

         List of relations

 Schema | Name  | Type  |  Owner   

\--------+-------+-------+----------

 public | test1 | table | postgres

 public | test2 | table | postgres

 public | test3 | table | postgres

(3 rows)

## 5 **结论**

1．复制槽防止备库需要的wal日志在主库被删除，主库会根据备库返回的信息确认哪些wal日志已不再需要，才能进行清理。

2．当允许应用连接从库做只读查询时，复制槽可以与参数hot\_standby\_feedback配合使用，使主库的vacuum操作不会过早的清掉从库查询需要的记录，而出现如下错误：ERROR: canceling statement due to conflict with recovery

但是也要注意几点：

1．如果收不到从库的reply，复制槽的状态restart lsn会保持不变，造成主库会一直保留本地日志，可能导致日志磁盘满。所以应该实时监控日志磁盘使用情况，并设置较小的wal\_sender\_timeout，默认为60s，及早发现从库断掉的情况。

2．将hot\_standby\_feedback设为on时，如果从库长时间有慢查询发生，可能导致发回到主库的xmin变化较慢，主库的vaccum操作停滞，造成主库被频繁更新的表大小暴增，导致严重的表膨胀。

针对措施：

1．可以增加wal日志个数的监控，当wal日志数量超过正常值告警。

2．做好对每个复制槽同步状态的监控，出现某个槽同步状态异常要及时处理，同步异常会造成lsn不向前推进，导致wal堆积。

3．对于业务很空闲但是数据需要同步的库，可以自定义脚本，定期更新无用表，手工推进lsn。

4．如果wal日志已经堆积很多磁盘马上要爆炸的情况下，在考虑应急删掉复制槽之前要评估剩余空间是否还有足够富余，因为即使删掉复制槽，wal日志也不是马上就会清理，删掉后主库vacuum也会产生较多xlog日志，一定要做好评估。

5．增加pg\_replication\_slot()视图中restart\_lsn的监控，对于落后较大和长期不推进的lsn进行告警。

最后引用一下微信群分享的PostgreSQL流复制图片：

![图片](https://mmbiz.qpic.cn/mmbiz_png/lniadOK6Dzb4Js6Vbw6iaPTWIAUEnmOF4rAIepia5Uaj6yeMWF42SIpsEB5KODTdFefnjZ11raicVnib8r7CEentscQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/lniadOK6Dzb4Js6Vbw6iaPTWIAUEnmOF4rNmw1TMDwlpxuxGrS40TCLWHUsKTSYaUUCa82d454iaoBRDEIxfAujqg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)