# PostgreSQL 15 逻辑复制操作流程详解

## 概述

本文通过实际操作演示 PostgreSQL 15 逻辑复制的完整流程，重点展示：
- WAL（Write-Ahead Logging）日志的生成与解析
- LSN（Log Sequence Number）的推进机制
- 事务（Transaction）与 WAL 的关系
- 快照（Snapshot）创建流程
- DDL（数据定义语言）、DML（数据操作语言）、DQL（数据查询语言）在逻辑复制中的处理过程

通过开启 WAL 调试模式，我们可以直观地看到：
1. 执行 DDL/DML 时写入的 WAL 日志内容
2. 复制传输过程中 LSN 的推进过程
3. 快照创建的具体步骤
4. 逻辑复制过程中操作的具体文件和文件内容

## 环境准备

### 1. PostgreSQL 15 安装与配置

首先确保已安装 PostgreSQL 15。以下配置参数需在 `postgresql.conf` 中设置：

```ini
# 设置 WAL 级别为 logical，这是逻辑复制的前提
wal_level = logical

# 设置最大复制槽数量
max_replication_slots = 10

# 设置最大 WAL 发送进程数量
max_wal_senders = 10

# 设置热备模式，允许在备份时进行查询
hot_standby = on

# 设置最大连接数
max_connections = 100

# 设置共享内存大小
shared_buffers = 128MB

# 设置 WAL 日志大小
wal_buffers = 16MB

# 设置检查点间隔
checkpoint_timeout = 15min
```text
重启 PostgreSQL 服务使配置生效：

```bash
# 根据系统不同，重启命令可能不同
sudo systemctl restart postgresql-15
# 或
pg_ctl restart -D /var/lib/pgsql/15/data
```text
### 2. 创建测试数据库和用户

```sql
-- 创建测试数据库
CREATE DATABASE logical_test;

-- 切换到 logical_test 数据库
\c logical_test

-- 创建用于复制的用户
CREATE USER repl_user WITH REPLICATION LOGIN PASSWORD 'repl_password';

-- 授予必要权限
GRANT ALL PRIVILEGES ON DATABASE logical_test TO repl_user;
```text
### 3. 准备测试环境

我们将使用两个数据库来模拟发布者（Publisher）和订阅者（Subscriber）：
- 发布者：logical_test 数据库
- 订阅者：logical_sub 数据库（在同一实例或不同实例中）

创建订阅者数据库：

```sql
CREATE DATABASE logical_sub;
```text
## 第一部分：WAL 日志基础

### 1.1 查看当前 WAL 状态

```sql
-- 查看当前 WAL LSN 位置
SELECT pg_current_wal_lsn();

-- 查看 WAL 文件名和 LSN 的对应关系
SELECT pg_walfile_name(pg_current_wal_lsn());

-- 查看 WAL 目录位置
SHOW data_directory;

-- 查看 WAL 相关配置
SHOW wal_level;
SHOW max_wal_size;
SHOW min_wal_size;
```text
### 1.2 开启 WAL 调试

PostgreSQL 没有直接的 "WAL 调试模式"，但我们可以通过以下方式查看 WAL 内容：

1. **使用 pg_waldump 工具**：解析二进制 WAL 文件
2. **设置 log_statement = 'all'**：记录所有 SQL 语句
3. **使用 pg_logical 扩展**：更详细的逻辑解码信息

在 `postgresql.conf` 中添加：

```ini
# 记录所有 SQL 语句
log_statement = 'all'

# 记录连接信息
log_connections = on

# 记录断开连接信息
log_disconnections = on

# 记录复制相关活动
log_replication_commands = on
```text
重启服务后，可以在日志文件中看到详细的 SQL 执行信息。

## 第二部分：逻辑复制搭建

### 2.1 创建发布者（Publisher）

在 logical_test 数据库中：

```sql
-- 创建测试表
CREATE TABLE test_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入初始数据
INSERT INTO test_table (name) VALUES ('初始数据1'), ('初始数据2'), ('初始数据3');

-- 创建发布
CREATE PUBLICATION test_pub FOR TABLE test_table;

-- 查看发布信息
SELECT * FROM pg_publication;
SELECT * FROM pg_publication_tables;
```text
### 2.2 创建订阅者（Subscriber）

在 logical_sub 数据库中：

```sql
-- 创建相同的表结构（注意：不需要创建序列，逻辑复制会复制数据）
CREATE TABLE test_table (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100),
    created_at TIMESTAMP
);

-- 创建订阅
CREATE SUBSCRIPTION test_sub
CONNECTION 'dbname=logical_test host=localhost user=repl_user password=repl_password'
PUBLICATION test_pub
WITH (copy_data = true);

-- 查看订阅信息
SELECT * FROM pg_subscription;
SELECT * FROM pg_stat_subscription;
```text
### 2.3 验证复制状态

```sql
-- 在发布者端查看复制槽
SELECT * FROM pg_replication_slots;

-- 查看复制统计信息
SELECT * FROM pg_stat_replication;

-- 查看当前复制进度
SELECT
    application_name,
    client_addr,
    state,
    sent_lsn,
    write_lsn,
    flush_lsn,
    replay_lsn,
    write_lag,
    flush_lag,
    replay_lag
FROM pg_stat_replication;

-- 在订阅者端查看数据是否已复制
SELECT * FROM test_table;
```text
## 第三部分：DDL 操作与 WAL 日志分析

### 3.1 执行 DDL 操作

```sql
-- 在发布者端执行 DDL
ALTER TABLE test_table ADD COLUMN email VARCHAR(255);

-- 添加索引
CREATE INDEX idx_test_table_name ON test_table(name);

-- 修改列类型
ALTER TABLE test_table ALTER COLUMN name TYPE VARCHAR(200);
```text
### 3.2 查看 DDL 对应的 WAL 日志

首先找到当前的 WAL 文件：

```sql
SELECT pg_walfile_name(pg_current_wal_lsn());
```text
假设得到的 WAL 文件名为 `000000010000000000000001`，使用 pg_waldump 解析：

```bash
# 切换到 WAL 目录
cd /var/lib/pgsql/15/data/pg_wal

# 使用 pg_waldump 解析 WAL 文件
pg_waldump 000000010000000000000001 -p

# 如果要查看特定 LSN 范围的 WAL
pg_waldump 000000010000000000000001 -s 0/1000000 -e 0/2000000
```text
### 3.3 分析 DDL 的 WAL 记录

DDL 操作在 WAL 中通常记录为：
1. **XLOG_SMGR_CREATE**：创建文件
2. **XLOG_SMGR_TRUNCATE**：截断文件
3. **XLOG_DBASE_CREATE**：创建数据库
4. **XLOG_DBASE_DROP**：删除数据库

对于表结构变更，WAL 会记录系统表（pg_class、pg_attribute等）的变更。

### 3.4 查看系统表变更

```sql
-- 查看最近的事务
SELECT * FROM pg_stat_activity WHERE backend_type = 'client backend';

-- 查看当前事务ID
SELECT txid_current();

-- 查看事务快照
SELECT pg_current_snapshot();
```text
## 第四部分：DML 操作与 WAL 日志分析

### 4.1 执行 DML 操作

```sql
-- 记录当前 LSN
SELECT pg_current_wal_lsn() AS before_lsn;

-- 执行 INSERT
INSERT INTO test_table (name, email) VALUES ('新数据1', 'test1@example.com');

-- 执行 UPDATE
UPDATE test_table SET name = '更新后的数据' WHERE id = 1;

-- 执行 DELETE
DELETE FROM test_table WHERE id = 2;

-- 记录操作后的 LSN
SELECT pg_current_wal_lsn() AS after_lsn;
```text
### 4.2 查看 DML 对应的 WAL 日志

使用 pg_waldump 查看 INSERT/UPDATE/DELETE 对应的 WAL 记录：

```bash
# 解析特定 LSN 范围的 WAL
pg_waldump 000000010000000000000001 -s 0/3000000 -e 0/4000000 -r heap
```text
`-r heap` 参数只显示堆表相关的 WAL 记录。

### 4.3 WAL 记录结构分析

一个典型的 INSERT WAL 记录包含：
- **事务ID**（xid）
- **关系OID**（表的对象ID）
- **插入的数据**（tuple）
- **LSN**（该记录在WAL中的位置）

UPDATE 和 DELETE 记录类似，但包含旧元组和新元组的信息。

### 4.4 查看逻辑解码输出

PostgreSQL 提供了逻辑解码的测试接口：

```sql
-- 创建逻辑复制槽（用于测试）
SELECT * FROM pg_create_logical_replication_slot('test_slot', 'test_decoding');

-- 执行一些 DML 操作
INSERT INTO test_table (name, email) VALUES ('解码测试', 'decode@example.com');

-- 查看逻辑解码输出
SELECT * FROM pg_logical_slot_get_changes('test_slot', NULL, NULL);

-- 删除测试槽
SELECT pg_drop_replication_slot('test_slot');
```text
## 第五部分：DQL 操作与快照分析

### 5.1 执行 DQL 操作

```sql
-- 创建快照
SELECT pg_export_snapshot();

-- 在快照中查询
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SET TRANSACTION SNAPSHOT '刚才导出的快照ID';
SELECT * FROM test_table;
COMMIT;

-- 查看当前活跃快照
SELECT * FROM pg_stat_activity WHERE state = 'active';
```text
### 5.2 快照与 LSN 的关系

快照实际上是一个事务ID的集合，表示在该快照创建时哪些事务已经提交、哪些正在运行、哪些还未开始。

```sql
-- 查看快照内容
SELECT pg_current_snapshot();

-- 快照格式：xmin:xmax:xip_list
-- xmin: 最早仍活跃的事务ID
-- xmax: 下一个将要分配的事务ID
-- xip_list: 当前活跃的事务ID列表
```text
### 5.3 快照在逻辑复制中的应用

逻辑复制中的初始数据拷贝（copy_data = true）使用一致性快照来确保数据的一致性：

1. **创建快照**：在复制开始时创建一个一致性快照
2. **基于快照拷贝数据**：使用该快照读取数据，确保看到一致的数据视图
3. **从快照LSN开始复制**：复制快照之后的所有WAL变化

## 第六部分：LSN 推进流程追踪

### 6.1 LSN 基本概念

LSN（Log Sequence Number）是WAL日志中的位置标识，是一个64位整数，通常表示为两个32位十六进制数（如 0/152B8A0）。

```sql
-- 查看各种LSN
SELECT
    pg_current_wal_lsn() AS current_lsn,
    pg_last_wal_receive_lsn() AS receive_lsn,
    pg_last_wal_replay_lsn() AS replay_lsn,
    pg_current_wal_insert_lsn() AS insert_lsn,
    pg_current_wal_flush_lsn() AS flush_lsn;
```text
### 6.2 复制过程中的 LSN 推进

在逻辑复制中，有多个LSN概念：
1. **sent_lsn**：发送者已发送的LSN
2. **write_lsn**：接收者已写入的LSN
3. **flush_lsn**：接收者已刷盘的LSN
4. **replay_lsn**：接收者已应用的LSN
5. **confirmed_flush_lsn**：确认已刷盘的LSN（复制槽中记录）

```sql
-- 查看复制进度
SELECT
    slot_name,
    plugin,
    slot_type,
    datoid,
    database,
    active,
    xmin,
    catalog_xmin,
    restart_lsn,
    confirmed_flush_lsn
FROM pg_replication_slots;

-- 查看复制延迟
SELECT
    application_name,
    pg_wal_lsn_diff(pg_current_wal_lsn(), sent_lsn) AS send_lag_bytes,
    pg_wal_lsn_diff(sent_lsn, write_lsn) AS write_lag_bytes,
    pg_wal_lsn_diff(write_lsn, flush_lsn) AS flush_lag_bytes,
    pg_wal_lsn_diff(flush_lsn, replay_lsn) AS replay_lag_bytes,
    pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS total_lag_bytes
FROM pg_stat_replication;
```text
### 6.3 LSN 与事务的关系

每个事务提交时都会记录一个LSN，表示该事务的WAL记录结束位置。

```sql
-- 查看事务与LSN的关系
BEGIN;
INSERT INTO test_table (name, email) VALUES ('LSN测试', 'lsn@example.com');
-- 记录事务提交前的LSN
SELECT pg_current_wal_lsn() AS before_commit_lsn;
COMMIT;
-- 记录事务提交后的LSN
SELECT pg_current_wal_lsn() AS after_commit_lsn;

-- 计算事务占用的WAL大小
SELECT pg_wal_lsn_diff('0/152B8B0', '0/152B8A0') AS wal_size_bytes;
```text
## 第七部分：文件级操作追踪

### 7.1 WAL 文件管理

WAL 文件位于 `pg_wal` 目录中，每个文件默认16MB。

```bash
# 查看WAL文件
ls -la /var/lib/pgsql/15/data/pg_wal/

# 查看WAL文件大小
du -sh /var/lib/pgsql/15/data/pg_wal/

# 查看当前正在使用的WAL文件
psql -c "SELECT pg_walfile_name(pg_current_wal_lsn());"
```text
### 7.2 数据文件追踪

每个表对应一个或多个数据文件（在 `base` 目录中）。

```sql
-- 查看表的文件节点信息
SELECT
    pg_relation_filepath('test_table'),
    pg_relation_size('test_table'),
    pg_total_relation_size('test_table');

-- 查看表的物理位置
SELECT
    relname,
    relfilenode,
    reltablespace,
    relpages,
    reltuples
FROM pg_class
WHERE relname = 'test_table';
```text
### 7.3 逻辑复制相关的文件

1. **复制槽状态文件**：`pg_replslot/<slot_name>/state`
2. **逻辑解码插件**：`lib/pgoutput.so` 或 `lib/decoder.so`
3. **订阅状态文件**：`pg_subscription/<sub_oid>/state`

```bash
# 查看复制槽文件
ls -la /var/lib/pgsql/15/data/pg_replslot/

# 查看逻辑解码插件
ls -la /usr/pgsql-15/lib/ | grep -E '(pgoutput|decoder)'
```text
## 第八部分：完整实验演示

### 8.1 实验目标

通过一个完整的实验演示：
1. DDL、DML、DQL 操作的执行
2. 对应 WAL 日志的生成
3. LSN 的推进过程
4. 快照的创建和使用
5. 逻辑复制的完整流程

### 8.2 实验步骤

#### 步骤1：环境准备
```bash
# 停止 PostgreSQL 服务
sudo systemctl stop postgresql-15

# 备份配置文件
cp /var/lib/pgsql/15/data/postgresql.conf /var/lib/pgsql/15/data/postgresql.conf.backup

# 修改配置文件（添加调试参数）
echo "
log_statement = 'all'
log_connections = on
log_disconnections = on
log_replication_commands = on
log_line_prefix = '%m [%p] %q%u@%d '
log_timezone = 'UTC'
" >> /var/lib/pgsql/15/data/postgresql.conf

# 启动 PostgreSQL 服务
sudo systemctl start postgresql-15
```text
#### 步骤2：初始化测试环境
```sql
-- 创建测试数据库
DROP DATABASE IF EXISTS logical_test;
DROP DATABASE IF EXISTS logical_sub;
CREATE DATABASE logical_test;
CREATE DATABASE logical_sub;

-- 创建测试表
\c logical_test
CREATE TABLE experiment_table (
    id SERIAL PRIMARY KEY,
    operation_type VARCHAR(50),
    operation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data JSONB
);

-- 创建发布
CREATE PUBLICATION experiment_pub FOR TABLE experiment_table;
```text
#### 步骤3：监控脚本准备
创建一个监控脚本 `monitor_replication.sh`：

```bash
#!/bin/bash
# monitor_replication.sh

while true; do
    clear
    echo "=== PostgreSQL 逻辑复制监控 ==="
    echo "时间: $(date)"
    echo ""

    echo "1. 当前 WAL LSN:"
    psql -d logical_test -c "SELECT pg_current_wal_lsn();"

    echo ""
    echo "2. 复制槽状态:"
    psql -d logical_test -c "SELECT slot_name, active, restart_lsn, confirmed_flush_lsn FROM pg_replication_slots;"

    echo ""
    echo "3. 复制连接状态:"
    psql -d logical_test -c "SELECT application_name, state, sent_lsn, write_lsn, flush_lsn, replay_lsn FROM pg_stat_replication;"

    echo ""
    echo "4. 表数据量:"
    psql -d logical_test -c "SELECT COUNT(*) FROM experiment_table;"
    psql -d logical_sub -c "SELECT COUNT(*) FROM experiment_table;" 2>/dev/null || echo "订阅者表不存在"

    echo ""
    echo "5. 最近WAL文件:"
    ls -la /var/lib/pgsql/15/data/pg_wal/ | tail -5

    sleep 2
done
```text
#### 步骤4：执行 DDL 操作并观察
```sql
-- 记录开始LSN
SELECT pg_current_wal_lsn() AS start_lsn \gset

-- 执行DDL
ALTER TABLE experiment_table ADD COLUMN ddl_marker BOOLEAN DEFAULT FALSE;

-- 记录结束LSN
SELECT pg_current_wal_lsn() AS end_lsn \gset

-- 计算DDL产生的WAL大小
SELECT pg_wal_lsn_diff(:'end_lsn', :'start_lsn') AS ddl_wal_size;
```text
#### 步骤5：执行 DML 操作并观察
```sql
-- 批量插入数据
INSERT INTO experiment_table (operation_type, data, ddl_marker)
SELECT
    'INSERT',
    jsonb_build_object('value', i, 'timestamp', now()),
    true
FROM generate_series(1, 100) AS i;

-- 更新数据
UPDATE experiment_table SET operation_type = 'UPDATE' WHERE id % 10 = 0;

-- 删除数据
DELETE FROM experiment_table WHERE id % 20 = 0;

-- 查看WAL生成量
SELECT pg_current_wal_lsn() AS current_lsn \gset
SELECT pg_wal_lsn_diff(:'current_lsn', :'end_lsn') AS dml_wal_size;
```text
#### 步骤6：创建订阅并观察复制过程
```sql
-- 在订阅者数据库创建表结构
\c logical_sub
CREATE TABLE experiment_table (
    id INTEGER PRIMARY KEY,
    operation_type VARCHAR(50),
    operation_time TIMESTAMP,
    data JSONB,
    ddl_marker BOOLEAN
);

-- 创建订阅
CREATE SUBSCRIPTION experiment_sub
CONNECTION 'dbname=logical_test host=localhost user=repl_user password=repl_password'
PUBLICATION experiment_pub
WITH (copy_data = true, create_slot = true);

-- 监控复制进度
\c logical_test
SELECT
    slot_name,
    confirmed_flush_lsn,
    pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn) AS lag_bytes
FROM pg_replication_slots;
```text
#### 步骤7：分析 WAL 日志
```bash
# 找到包含实验操作的WAL文件
WAL_FILE=$(psql -d logical_test -t -c "SELECT pg_walfile_name(:'start_lsn');")

# 解析WAL文件
pg_waldump /var/lib/pgsql/15/data/pg_wal/$WAL_FILE -s :'start_lsn' -e :'current_lsn' -p > experiment_wal_dump.txt

# 查看解析结果
head -100 experiment_wal_dump.txt
```text
#### 步骤8：验证数据一致性
```sql
-- 在发布者和订阅者比较数据
\c logical_test
SELECT 'Publisher' as source, COUNT(*) as row_count FROM experiment_table
UNION ALL
\c logical_sub
SELECT 'Subscriber' as source, COUNT(*) as row_count FROM experiment_table;

-- 比较具体数据
\c logical_test
SELECT id, operation_type, ddl_marker FROM experiment_table ORDER BY id LIMIT 10;
\c logical_sub
SELECT id, operation_type, ddl_marker FROM experiment_table ORDER BY id LIMIT 10;
```text
### 8.3 实验结果分析

通过上述实验，我们可以观察到：

1. **DDL 操作**：会产生系统表变更的WAL记录，但不会通过逻辑复制自动传播到订阅者（除非使用pglogical等扩展）。
2. **DML 操作**：每个INSERT/UPDATE/DELETE都会产生对应的WAL记录，并通过逻辑复制传播到订阅者。
3. **LSN 推进**：每次事务提交都会推进LSN，复制槽的confirmed_flush_lsn会逐渐向前移动。
4. **快照使用**：初始数据拷贝使用一致性快照，确保数据一致性。
5. **文件变化**：WAL文件会不断生成，复制槽状态文件会记录复制进度。

## 第九部分：原理与实操结合

### 9.1 LSN、事务、WAL 之间的关系

1. **LSN 是 WAL 的地址**：每个WAL记录都有一个唯一的LSN。
2. **事务包含多个 WAL 记录**：一个事务可能包含多个DML操作，每个操作对应一个WAL记录。
3. **事务提交记录最终的 LSN**：事务提交时，会写入一个提交记录，该记录的LSN代表事务的结束位置。
4. **逻辑复制按 LSN 顺序读取**：逻辑解码器按LSN顺序读取WAL记录，重组事务。

```sql
-- 演示事务与LSN的关系
BEGIN;
SELECT pg_current_wal_lsn() AS lsn_before_insert \gset
INSERT INTO test_table (name) VALUES ('事务测试1');
SELECT pg_current_wal_lsn() AS lsn_after_insert \gset
INSERT INTO test_table (name) VALUES ('事务测试2');
SELECT pg_current_wal_lsn() AS lsn_before_commit \gset
COMMIT;
SELECT pg_current_wal_lsn() AS lsn_after_commit \gset

-- 计算各个阶段之间的WAL增量
SELECT
    pg_wal_lsn_diff(:'lsn_after_insert', :'lsn_before_insert') AS insert1_wal,
    pg_wal_lsn_diff(:'lsn_before_commit', :'lsn_after_insert') AS insert2_wal,
    pg_wal_lsn_diff(:'lsn_after_commit', :'lsn_before_commit') AS commit_wal;
```text
### 9.2 快照与事务隔离

逻辑复制使用快照来确保数据一致性：

1. **快照创建时机**：在创建订阅或初始数据拷贝时创建。
2. **快照内容**：包含创建时所有已提交的事务。
3. **快照与 LSN**：每个快照都对应一个LSN，表示快照创建时的WAL位置。

```sql
-- 演示快照与LSN的关系
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT pg_export_snapshot() AS snapshot_id \gset
SELECT pg_current_wal_lsn() AS snapshot_lsn \gset

-- 在另一个会话中修改数据
-- 然后回到这个会话查询，应该看不到新修改的数据
SELECT * FROM test_table;

COMMIT;

-- 快照对应的LSN可以用于确定复制起点
SELECT :'snapshot_lsn' AS snapshot_lsn_position;
```text
### 9.3 逻辑复制的工作流程

1. **捕获变更**：通过WAL日志捕获DDL/DML变更。
2. **逻辑解码**：使用输出插件（如pgoutput）将WAL记录解码为逻辑变更。
3. **事务重组**：使用ReorderBuffer将同一事务的变更重组。
4. **传输变更**：通过复制协议将变更发送到订阅者。
5. **应用变更**：订阅者应用变更，保持数据同步。

## 第十部分：故障排查与性能优化

### 10.1 常见问题排查

#### 问题1：复制延迟大
```sql
-- 查看复制延迟
SELECT
    application_name,
    pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS delay_bytes,
    pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)) AS delay_pretty
FROM pg_stat_replication;

-- 可能原因及解决方案：
-- 1. 网络带宽不足：检查网络连接
-- 2. 订阅者应用慢：检查订阅者负载
-- 3. 大事务：避免长时间运行的大事务
-- 4. WAL文件过多：定期清理旧复制槽
```text
#### 问题2：WAL磁盘空间不足
```sql
-- 查看WAL磁盘使用
SELECT
    slot_name,
    pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS wal_retained
FROM pg_replication_slots;

-- 解决方案：
-- 1. 删除不需要的复制槽：SELECT pg_drop_replication_slot('slot_name');
-- 2. 监控复制进度，确保订阅者及时确认
-- 3. 增加WAL磁盘空间
```text
#### 问题3：复制中断
```sql
-- 查看复制状态
SELECT * FROM pg_stat_replication WHERE state != 'streaming';

-- 查看错误日志
SELECT pg_read_file('log/postgresql-' || to_char(current_date, 'YYYY-MM-DD') || '.log')
FROM generate_series(1,1)
WHERE length(pg_read_file('log/postgresql-' || to_char(current_date, 'YYYY-MM-DD') || '.log')) > 0;

-- 常见原因：
-- 1. 网络中断：检查网络连接
-- 2. 权限问题：检查复制用户权限
-- 3. 表结构不一致：确保发布者和订阅者表结构一致
```text
### 10.2 性能优化建议

1. **调整WAL参数**：
   ```ini
   wal_buffers = 16MB
   wal_writer_delay = 200ms
   max_wal_size = 2GB
   min_wal_size = 1GB
   ```

2. **优化复制参数**：
   ```sql
   -- 创建订阅时调整参数
   CREATE SUBSCRIPTION ... WITH (
       copy_data = true,
       create_slot = true,
       enabled = true,
       slot_name = 'custom_slot',
       synchronous_commit = 'off'
   );
   ```

3. **监控与告警**：
   ```sql
   -- 创建监控视图
   CREATE VIEW replication_monitor AS
   SELECT
       application_name,
       state,
       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS replication_lag_bytes,
       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) / 1024 / 1024 AS replication_lag_mb,
       CASE
           WHEN pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) > 100 * 1024 * 1024 THEN 'CRITICAL'
           WHEN pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) > 10 * 1024 * 1024 THEN 'WARNING'
           ELSE 'OK'
       END AS lag_status
   FROM pg_stat_replication;
   ```

## 第十一部分：总结

通过本文的实践操作，我们深入了解了：

1. **WAL 日志机制**：DDL/DML操作如何记录到WAL中。
2. **LSN 推进原理**：事务如何推动LSN前进，以及LSN在复制中的作用。
3. **快照创建流程**：逻辑复制如何使用快照确保数据一致性。
4. **逻辑复制全流程**：从变更捕获到数据同步的完整过程。
5. **监控与调优**：如何监控复制状态，优化复制性能。

关键点总结：
- **LSN是复制的核心**：所有复制进度都以LSN为基准。
- **事务是逻辑单位**：逻辑复制以事务为单位保证一致性。
- **WAL是物理基础**：所有变更都通过WAL记录和传输。
- **快照确保一致性**：初始数据拷贝使用快照保证数据一致性。

## 附录

### A. 常用命令速查

```sql
-- WAL相关
SELECT pg_current_wal_lsn();
SELECT pg_walfile_name(pg_current_wal_lsn());
SELECT pg_wal_lsn_diff('0/152B8B0', '0/152B8A0');

-- 复制相关
SELECT * FROM pg_replication_slots;
SELECT * FROM pg_stat_replication;
SELECT * FROM pg_publication;
SELECT * FROM pg_subscription;

-- 快照相关
SELECT pg_current_snapshot();
SELECT pg_export_snapshot();

-- 表信息
SELECT pg_relation_filepath('table_name');
SELECT pg_relation_size('table_name');
```text
### B. 配置文件示例

`postgresql.conf` 关键配置：
```ini
# 复制相关
wal_level = logical
max_replication_slots = 10
max_wal_senders = 10
hot_standby = on

# 性能相关
shared_buffers = 128MB
wal_buffers = 16MB
max_wal_size = 2GB
min_wal_size = 1GB

# 日志相关
log_statement = 'all'
log_connections = on
log_disconnections = on
log_replication_commands = on
```text
### C. WAL 日志实际示例分析

以下是使用 `pg_waldump` 工具解析的实际 WAL 日志示例，展示了不同操作对应的 WAL 记录。

#### 示例1：INSERT 操作的 WAL 记录

```plaintext
rmgr: Heap        len (rec/tot):     70/   114, tx:       1234, lsn: 0/1512345, prev 0/1512000, desc: INSERT+INIT
  blkref #0: rel 1663/16384/24576 blk 0
  tuple data: 2 columns
    col 1: [1] 49  (integer 1)
    col 2: [7] 74 65 73 74 31  (text "test1")
```text
**字段解释**：
- `rmgr: Heap`：资源管理器为堆表（数据表）
- `tx: 1234`：事务ID
- `lsn: 0/1512345`：该记录的LSN位置
- `prev 0/1512000`：前一个记录的LSN
- `desc: INSERT+INIT`：操作类型为INSERT，INIT表示这是事务中的第一个操作
- `rel 1663/16384/24576`：表OID（数据库OID/模式OID/表OID）
- `blk 0`：块号
- `tuple data`：插入的元组数据

#### 示例2：UPDATE 操作的 WAL 记录

```plaintext
rmgr: Heap        len (rec/tot):    104/   148, tx:       1235, lsn: 0/1512500, prev 0/1512345, desc: UPDATE
  blkref #0: rel 1663/16384/24576 blk 0
  old tuple: 2 columns
    col 1: [1] 49  (integer 1)
    col 2: [7] 74 65 73 74 31  (text "test1")
  new tuple: 2 columns
    col 1: [1] 49  (integer 1)
    col 2: [8] 74 65 73 74 31 55  (text "test17")
```text
**字段解释**：
- `desc: UPDATE`：操作类型为UPDATE
- `old tuple`：更新前的元组数据
- `new tuple`：更新后的元组数据

#### 示例3：DELETE 操作的 WAL 记录

```plaintext
rmgr: Heap        len (rec/tot):     66/   110, tx:       1236, lsn: 0/1512700, prev 0/1512500, desc: DELETE
  blkref #0: rel 1663/16384/24576 blk 0
  old tuple: 2 columns
    col 1: [1] 49  (integer 1)
    col 2: [8] 74 65 73 74 31 55  (text "test17")
```text
#### 示例4：事务提交记录

```plaintext
rmgr: Transaction len (rec/tot):     34/    34, tx:       1234, lsn: 0/1512800, prev 0/1512700, desc: COMMIT 2026-03-16 10:30:00.123456 UTC
  commit_ts: 2026-03-16 10:30:00.123456 UTC
```text
**字段解释**：
- `rmgr: Transaction`：资源管理器为事务
- `desc: COMMIT`：事务提交
- `commit_ts`：提交时间戳

#### 示例5：检查点记录

```plaintext
rmgr: XLOG        len (rec/tot):    106/   106, tx:          0, lsn: 0/1513000, prev 0/1512800, desc: CHECKPOINT_ONLINE
  redo 0/1513000; undo 0/0; tli 1; prev tli 1; fpw true; xid 0:1236; oid 24576; multi 1; offset 0; oldest xid 562 in DB 1; oldest multi 1; oldest/newest commit timestamp xid: 0/0; oldest running xid 0; shutdown false
```text
#### 示例6：DDL 操作（创建表）的 WAL 记录

DDL操作通常涉及多个系统表变更：

```plaintext
rmgr: Storage    len (rec/tot):     42/    42, tx:       1237, lsn: 0/1513200, prev 0/1513000, desc: SMGR_CREATE
  rel 1663/16384/24577 fork main size 0

rmgr: Heap        len (rec/tot):     92/    92, tx:       1237, lsn: 0/1513250, prev 0/1513200, desc: INSERT
  blkref #0: rel 1663/1262/1259 blk 0  # pg_class 系统表
  tuple data: ...  # 新表的元数据

rmgr: Heap        len (rec/tot):     85/    85, tx:       1237, lsn: 0/1513300, prev 0/1513250, desc: INSERT
  blkref #0: rel 1663/1262/1249 blk 0  # pg_attribute 系统表
  tuple data: ...  # 表列的元数据
```text
**说明**：DDL操作不会直接记录SQL语句，而是记录系统表（pg_class、pg_attribute等）的变更。逻辑复制需要额外的机制（如pglogical）来捕获和复制DDL。

#### 示例7：逻辑解码消息（Logical Message）

```plaintext
rmgr: LogicalMessage len (rec/tot):     58/    58, tx:          0, lsn: 0/1513400, prev 0/1513300, desc: MESSAGE
  prefix "pgoutput"; content "BEGIN 1234"
```text
这是逻辑复制专用的消息，用于传输事务边界等信息。

### D. 参考资源

1. PostgreSQL官方文档：逻辑复制章节
2. pg_waldump工具手册
3. PostgreSQL源码：src/backend/replication/
4. 逻辑复制扩展：pglogical、wal2json等

---

*文档最后更新日期：2026年3月16日*
*适用于 PostgreSQL 15 及以上版本*
