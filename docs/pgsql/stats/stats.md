1. 
```
设置存储临时统计数据的目录。这可以是一个相对于数据目录的路径或一个绝对路径。默认值是pg_stat_tmp。在一个基于 RAM 的文件系统上指明这个参数将降低物理 I/O 需求，并且提高性能。这个参数只能在postgresql.conf文件中或在服务器命令行上设置。
对超大容量数据库很有用；stats 临时目录可以设置为 RAMdisk 或其他高速资源（以可能丢失一些统计信息为代价），因为该文件每秒更新数百次。
```

2.  

   ```
   1.pg_stat_activity 每个服务进程一行,显示与那个进程的当前活动相关的信息，例如状态和当前状态和查询
   2.pg_stat_replication 每一个WAL发送进程一行，显示有关到该发送进程连接的后备务器的复制的统计信息
   3.pg_stat_wal_receiver 只有一行，显示来自WAL接收器所连接服务器的有关该接收器的统计信息
   4.pg_stat_subscripition 每个订阅至少一行，显示有关该订阅的工作者的信息
   5. pg_stat_ssl 每个连接（常规的或者复制）一行，显示在这个连接上使用的ssl的信息
   6.pg_stat_gssapi 每个连接（常规的或者复制）一行，显示关于gassapi加密或者验证的信息
   7. pg_stat_progress_create_index 每个后台运行create index或reindex的后端都有一行，显示当前进度
   8. pg_stat_progress_vacuum 每个后台运行VACUUM的后端（或者autovacuum工作进程）一行，显示当前进度
   9. pg_stat_progress_cluster 每个后台运行CLUSTER或VACUUM FULL的后端一行，显示当前进度
   ```
2.  

   ```
   1.pg_stat_archiver 只有一行．显示有关WAL归柽进程活动的统计信息
   2. pg_stat_bgwritter 只有一行，显示有关后台写进程的活动的统计信息
   3. pg_stat_database 每个数据库一行，显示数据库范围的统计信息
   4. pg_stat_database_conflicts 每个数据库一行：由于与后备服务器的复过程发生冲突而被取消的查询
   5. pg_stat_all_tables 当前数据库中每个表一行，显示有关访问指定表的统计信息
   6.pg_stat_xact_all_tables 计数动作只在当前事务内发生（还没有被包括在pg_stat_all_tables 和相关视图
   中）
   7. pg_stat_all_indexes 当前数据库中的每个索引一行，显示与访问指定索引有关的统计信息
   8. pg_statio_all_tables 当前数据岸中的每个表一行，显示有关在指定表上I/O的统计信息
   9. pg_statio_all_indexes  当前数据库中的每个索引一行，显示与指定索引上的I/O有关的统计信息
   10. pg_statio_all_seauence 当前数据岸中的每个列一行，显示与指定序列上的I/O有关的统计信息
   11. pg_stat_user_function 一个被跟踪的函数一行，显示与执行该函数有关的统计信息 
   ```
2.  

   ```
   pg_stat_statements.save = on
   2. 查询
   select queryid, substr(query,0,30) as query, parses, plans, calls, round(total_plan_time + total_exec_time) as times,rows from pg_stat_statements order by times desc;
   3.清理
   pg_stat_statements_reset
   ```
2.  

   ```
   1. 通过pg_stat_database可以大概了解数据库的历史情况;pg_stat_statements模块提供一种跟踪执行统计服务器执行的所有SQL语句的手;
   2. pg_stat_database更多的是关注历史数据，即过去的数据库状态；而pg_stat_statements关注的是实时数据，即数据库执行过程中的实时统计数据。
   ```

6. 

```
1. 可以通过pg_stat_activity查看正在执行的SQL；
2.属于实时统计信息；
3.使用PgBackendStatus数组存储
```

7. 

```
1.修改数据库配置，打开pg_stat_statements,重启数据库
shared_preload_libraries = 'liboracle_parser, pg_stats_statements'
pg_stat_statements.track_utility = on
pg_stat_statements.track = 'top'
pg_stat_statements.max = 5000
pg_stat_statements.save = on
2. 创建pg_stat_statements扩展
CREATE EXTENSION pg_stat_statements;
3.在数据库shell中根据相关条件查询pg_stat_statements视图，获取执行次数和执行时间

```
8. 

```
1.无；
2.寻求帮助的方法有：
 a. 求助公司相关模块的同事；
 b. 上网查阅资料，包括pg官网；
 c.阅读数据库手册；
 d.阅读开发者文档和源码
```
