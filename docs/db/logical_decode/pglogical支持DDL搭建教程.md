# pglogical支持DDL搭建

## 编译数据库和pglogical插件

```shell
git clone https://git.postgresql.org/git/postgresql.git
cd postgresql
git checkout REL_15_STABLE # 以pg15为例
./configure --prefix=`pwd`/debug
make world -j16
make install-world
```text
```shell
git clone https://github.com/2ndQuadrant/pglogical.git
cd pglogical
export PG_CONFIG=/path/pg_config
make
make install
```text
## 配置启动

### 配置数据库1

使用如下命令初始化数据库：

```shell
./initdb -D data -A trust
```text
初始化data后，修改postgres.conf，添加如下内容：

```shell
wal_level = logical

max_worker_processes = 10
max_replication_slots = 10
max_wal_senders = 10

shared_preload_libraries = 'pglogical'
```text
启动数据库并配置插件：

```shell
./pg_ctl -D data start -l logfile
```text
```shell
./psql -d postgres
psql (15.12)
Type "help" for help.

postgres=# create extension pglogical;
CREATE EXTENSION
```text
### 配置数据库2

在同一台机器上再初始化一个数据库，

```shell
./initdb -D data -A trust
```text
初始化data后，修改postgres.conf，添加如下内容：(修改一下数据库运行的端口)

```shell
wal_level = logical

max_worker_processes = 10
max_replication_slots = 10
max_wal_senders = 10

shared_preload_libraries = 'pglogical'
port=5433
```text
```shell
./pg_ctl -D data1 start -l logfile1
```text
```shell
./psql -d postgres -p 5433
psql (15.12)
Type "help" for help.

postgres=# create extension pglogical;
CREATE EXTENSION
```text
## 配置pub

连接数据库，注册pub。

```sql
# 创建节点
SELECT pglogical.create_node(
    node_name := 'provider1',
    dsn := 'host=127.0.0.1 port=5432 dbname=postgres'
);
```text
```sql
./psql -d postgres
psql (15.12)
Type "help" for help.

postgres=# SELECT pglogical.create_node(
postgres(#     node_name := 'provider1',
postgres(#     dsn := 'host=127.0.0.1 port=5432 dbname=postgres'
postgres(# );
 create_node 
-------------
  2976894835
(1 row)
```text
创建复制集

将public架构中的所有表添加到default复制集中。

```sql
SELECT pglogical.replication_set_add_all_tables('default', ARRAY['public']);
```text
复制集default的表都必需要primary key。

## 配置subscribe

连接数据库，创建订阅者节点。

```sql
SELECT pglogical.create_node(
node_name := 'subscriber1',
dsn := 'host=127.0.0.1 port=5433 dbname=postgres'
);
```text
```sql
./psql -d postgres -p 5433
psql (15.12)
Type "help" for help.

postgres=# SELECT pglogical.create_node(
postgres(# node_name := 'subscriber1',
postgres(# dsn := 'host=127.0.0.1 port=5433 dbname=postgres'
postgres(# );
 create_node 
-------------
   330520249
(1 row)

```text
节点创建完成后，创建订阅者。

```sql
SELECT pglogical.create_subscription(
subscription_name := 'subscription1',
provider_dsn := 'host=127.0.0.1 port=5432 dbname=postgres'
);
```text
```sql
postgres=# SELECT pglogical.create_subscription(
postgres(# subscription_name := 'subscription1',
postgres(# provider_dsn := 'host=127.0.0.1 port=5432 dbname=postgres'
postgres(# );
 create_subscription 
---------------------
          1763399739
(1 row)
```text
此时查看机器上的进程如下：

```shell
ps -ef | grep postgres
dys      1201049       1  0 3月08 ?       00:00:00 /work/cwork/postgresql/debug/bin/postgres -D /home/dys/data
dys      1201050 1201049  0 3月08 ?       00:00:00 postgres: checkpointer 
dys      1201051 1201049  0 3月08 ?       00:00:00 postgres: background writer 
dys      1201053 1201049  0 3月08 ?       00:00:00 postgres: walwriter 
dys      1201054 1201049  0 3月08 ?       00:00:00 postgres: autovacuum launcher 
dys      1201055 1201049  0 3月08 ?       00:00:00 postgres: pglogical supervisor 
dys      1201056 1201049  0 3月08 ?       00:00:00 postgres: logical replication launcher 
dys      1202949       1  0 00:08 ?        00:00:00 /work/cwork/postgresql/debug/bin/postgres -D /home/dys/data1
dys      1202950 1202949  0 00:08 ?        00:00:00 postgres: checkpointer 
dys      1202951 1202949  0 00:08 ?        00:00:00 postgres: background writer 
dys      1202953 1202949  0 00:08 ?        00:00:00 postgres: walwriter 
dys      1202954 1202949  0 00:08 ?        00:00:00 postgres: autovacuum launcher 
dys      1202955 1202949  0 00:08 ?        00:00:00 postgres: pglogical supervisor 
dys      1202956 1202949  0 00:08 ?        00:00:00 postgres: logical replication launcher 
dys      1220248 1201049  0 02:25 ?        00:00:00 postgres: pglogical manager 5 
dys      1222134 1202949  0 02:44 ?        00:00:00 postgres: pglogical manager 5 
dys      1222717 1202949  0 02:51 ?        00:00:00 postgres: pglogical apply 5:1763399739 
dys      1222722 1201049  0 02:51 ?        00:00:00 postgres: walsender dys 127.0.0.1(57692) START_REPLICATION
dys      1222772 1218880  0 02:51 pts/1    00:00:00 grep --color=auto postgres
```text
## 验证逻辑复制

创建表：

```sql
create table test_lo(id int primary key, name text, reg_time timestamp);
```text
```sql
./psql -d postgres
psql (15.12)
Type "help" for help.

postgres=# create table test_lo(id int primary key, name text, reg_time timestamp);
CREATE TABLE
postgres=# \d
        List of relations
 Schema |  Name   | Type  | Owner 
--------+---------+-------+-------
 public | test_lo | table | dys
(1 row)
```text
可以看到已经在源库（pub）创建了表，可以看下目的库有没有同步该表。

```shell
./psql -d postgres -p 5433
psql (15.12)
Type "help" for help.

postgres=# \d
Did not find any relations.
```text
可以看到目标库并没有自动同步该表。

### 生成测试数据

在pub端执行：

```sql
insert into test_lo select generate_series(1,1000),'postgres',now();
```text
```sql
postgres=# insert into test_lo select generate_series(1,1000),'postgres',now();
INSERT 0 1000
postgres=# \d+
                                  List of relations
 Schema |  Name   | Type  | Owner | Persistence | Access method | Size  | Description 
--------+---------+-------+-------+-------------+---------------+-------+-------------
 public | test_lo | table | dys   | permanent   | heap          | 88 kB | 
(1 row)
postgres=# select * from test_lo limit 10;
 id |   name   |          reg_time          
----+----------+----------------------------
  1 | postgres | 2026-03-09 03:00:15.304868
  2 | postgres | 2026-03-09 03:00:15.304868
  3 | postgres | 2026-03-09 03:00:15.304868
  4 | postgres | 2026-03-09 03:00:15.304868
  5 | postgres | 2026-03-09 03:00:15.304868
  6 | postgres | 2026-03-09 03:00:15.304868
  7 | postgres | 2026-03-09 03:00:15.304868
  8 | postgres | 2026-03-09 03:00:15.304868
  9 | postgres | 2026-03-09 03:00:15.304868
 10 | postgres | 2026-03-09 03:00:15.304868
(10 rows)
```text
### 将新建的表添加到对应的复制集

对新建的表；并没有为其分配对应的复制集；需要手动添加。（也可以使用触发器添加）

```sql
postgres=# select * from pglogical.replication_set_table ;
 set_id | set_reloid | set_att_list | set_row_filter 
--------+------------+--------------+----------------
(0 rows)
```text
```sql
select pglogical.replication_set_add_table( set_name := 'default', relation := 'test_lo',synchronize_data := true);
```text
```sql
postgres=# select * from pglogical.replication_set_table ;
 set_id | set_reloid | set_att_list | set_row_filter 
--------+------------+--------------+----------------
(0 rows)

postgres=# select pglogical.replication_set_add_table( set_name := 'default', relation := 'test_lo',synchronize_data := true);
 replication_set_add_table 
---------------------------
 t
(1 row)

postgres=# select * from pglogical.replication_set_table ;
  set_id   | set_reloid | set_att_list | set_row_filter 
-----------+------------+--------------+----------------
 290045701 | test_lo    |              | 
(1 row)
```text
```sql
select * from pglogical.show_subscription_table('subscription1','test_lo');
```text
### 同步DDL

逻辑复制不会自动同步DDL，需要在创建表时使用pglogical指定的语句才会同步。

在创建表时同步DDL。

```sql
SELECT pglogical.replicate_ddl_command(
$$
SET search_path = public;
create table test_lo(id int primary key, name text, reg_time timestamp);
$$
);
```text
```sql
./psql -d postgres
psql (15.12)
Type "help" for help.

postgres=# SELECT pglogical.replicate_ddl_command(
postgres(# $$
postgres$# SET search_path = public;
postgres$# create table test_lo(id int primary key, name text, reg_time timestamp);
postgres$# $$
postgres(# );
 replicate_ddl_command 
-----------------------
 t
(1 row)

postgres=# \d
        List of relations
 Schema |  Name   | Type  | Owner 
--------+---------+-------+-------
 public | test_lo | table | dys
(1 row)

postgres=# \q
[dys@localhost bin]$ ./psql -d postgres -p 5433
psql (15.12)
Type "help" for help.

postgres=# \d
        List of relations
 Schema |  Name   | Type  | Owner 
--------+---------+-------+-------
 public | test_lo | table | dys
```text
可以看到源库和目标库都有了test_lo表。

重新生成测试数据。

```sql
[dys@localhost bin]$ ./psql -d postgres
psql (15.12)
Type "help" for help.

postgres=# INSERT INTO public.test_lo VALUES (1001,'check',now());
INSERT 0 1
postgres=# \q
[dys@localhost bin]$ ./psql -d postgres -p 5433
psql (15.12)
Type "help" for help.

postgres=# \d+
                                  List of relations
 Schema |  Name   | Type  | Owner | Persistence | Access method | Size  | Description 
--------+---------+-------+-------+-------------+---------------+-------+-------------
 public | test_lo | table | dys   | permanent   | heap          | 16 kB | 
(1 row)

postgres=# SELECT * FROM pglogical.subscription;^C
postgres=# select * from test_lo;
  id  | name  |          reg_time          
------+-------+----------------------------
 1001 | check | 2026-03-09 03:28:47.696612
(1 row)
```text
可以看到新插入的数据已经同步。
```text
# reference

1.https://www.cnblogs.com/lottu/p/10972773.html
2.https://www.modb.pro/db/376539