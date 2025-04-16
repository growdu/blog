# pg_io_调优

## 检查点

检查点是数据库的关键行为，同时也是IO敏感的；其保证了数据库的一致性状态，定期执行检查点是很重要的，确保数据变化持久保存到磁盘中并且数据库的状态是一致的。不当的检查点配置会导致IO性能问题。我们需要关注检查点的配置，确保没有任何IO的尖刺(这同样也取决于磁盘性能的好坏，以及数据文件的组织)。

- checkpoint_timeout

  统自动执行checkpoint之间的最大时间间隔。系统默认值是5分钟，这个值可以在压测过程中调大，尽量避免执行checkpoint争抢IO。

- max_wal_size

  写满多少个WAL时执行checkpoint，也是同理，这个值可以在压测过程中调大，尽量避免执行checkpoint争抢IO

- min_wal_size

  只要wal日志目录使用空间小于该值，那么旧的wal日志就会循环使用而不是进行删除。这个参数是为了确保足够的wal空间预留给突发情况，比如大的跑批操作。

- 843-789-644

  分散检查点，默认为0.5，即表示每个checkpoint需要在checkpoints间隔时间的50%内完成，然后立马进行fsync，fsync执行是很快的。checkpoint_completion_target设置的越高的情况下，写入速度越低，对客户而言，体验越好，性能越高。反之，较低的值可能会引起I/O峰值，导致“卡死”的现象，可以设置0.9 +。

- full_page_writes

  服务器在检查点之后对页面的第一次写入时将整个页面写到WAL里面。如果checkpoint发生太频繁，会导致写放大，默认为on，假如调为off，需要确保数据库在压测期间不要崩溃，不然重启后可能发生数据块部分写，导致重启失败。full_page_writes就是为了确保数据页一致性，不发生块折断

## BgWriter

- bgwriter_delay

  background writer每次扫描之间的时间间隔，也就是刷shared buffer脏页的进程调度间隔，尽量高频调度，减少用户进程申请不到内存而需要主动刷脏页的可能(导致RT升高

- bgwriter_lru_maxpage

   一次最多刷多少脏页

- bgwriter_lru_multiplier

  写出至多bgwriter_lru_multiplier * N个脏页，并且不超过bgwriter_lru_maxpages值的限制。其中N是最近一段时间在两次BgWriter运行期间系统新申请的缓冲区页数。后台写进程根据最近服务进程需要的buffer数量乘上这个比率估算出下次服务进程需要的buffer数量，再使用后台写进程刷脏页面，使缓冲区能使用的干净页面达到这个估计值

- bgwriter_flush_after

  每当bgwriter写入的字节数超过bgwriter_flush_after时，就会强制OS从page cache中写出。这样做将限制page cache中脏数据量，从而减少在检查点末尾发出fsync或操作系统在后台大批量写回数据时出现停顿的可能性

## vacuum

- autovacuum

  自动清理进程，在压测期间，可以关闭，减少IO争抢

# reference

1. https://www.modb.pro/db/28822