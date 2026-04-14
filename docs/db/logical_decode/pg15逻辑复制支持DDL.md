# pg15逻辑复制支持DDL

如果你的目标是：

> **在 PostgreSQL 15 的原生逻辑复制框架（CREATE PUBLICATION / CREATE SUBSCRIPTION）基础上，扩展支持 DDL 复制，并在 SQL 接口层增加 ddl 选项，同时把整个复制链路打通。**

那么可以设计一套 **“最小侵入内核”的实现方案**。我按 **接口层 → catalog → WAL → decoding → apply worker → 执行DDL** 的完整链路讲清楚。

---

# 一、SQL接口扩展设计

PG15 的接口：

```sql
CREATE PUBLICATION pub1
FOR TABLE t1
WITH (publish = 'insert, update, delete');
```

可以扩展为：

```sql
CREATE PUBLICATION pub1
FOR TABLE t1
WITH (publish = 'insert, update, delete, ddl');
```

或者更清晰：

```sql
CREATE PUBLICATION pub1
FOR ALL TABLES
WITH (
    publish = 'insert, update, delete',
    publish_ddl = true
);
```

推荐第二种，因为：

* 不破坏原 publish 参数解析
* 兼容旧版本逻辑复制

对应订阅端：

```sql
CREATE SUBSCRIPTION sub1
CONNECTION 'host=... dbname=...'
PUBLICATION pub1
WITH (
    copy_data = true,
    enable_ddl = true
);
```

---

# 二、系统表扩展（Catalog）

需要在 publication catalog 中增加字段。

系统表：

```
pg_publication
```

新增字段：

```
pubddl bool
```

修改：

```
src/include/catalog/pg_publication.h
```

示例：

```c
bool pubddl;   /* publish DDL */
```

同时更新：

```
pg_publication_rel
pg_publication_namespace
```

读取函数：

```
GetPublication()
GetPublicationByName()
```

要把 `pubddl` 返回给 replication 逻辑。

---

# 三、DDL 捕获

DDL执行入口：

```
standard_ProcessUtility()
```

位置：

```
src/backend/tcop/utility.c
```

逻辑：

```c
if (IsA(parsetree, CreateStmt) ||
    IsA(parsetree, AlterTableStmt) ||
    IsA(parsetree, DropStmt) ||
    IsA(parsetree, IndexStmt))
{
    if (PublicationHasDDL())
        LogDDLLogicalMessage(queryString);
}
```

关键函数：

```c
LogDDLLogicalMessage(queryString)
```

---

# 四、写入 WAL

PostgreSQL 已经支持 **logical message WAL record**：

```
LogLogicalMessage()
```

文件：

```
src/backend/replication/logical/logicalfuncs.c
```

实现：

```c
LogLogicalMessage(
    "pg_ddl_replication",
    queryString,
    strlen(queryString),
    false);
```

写入 WAL：

```
RM_LOGICALMSG_ID
```

WAL结构：

```
LogicalMessage
   prefix = "pg_ddl_replication"
   message = "CREATE TABLE t1..."
```

这样 WAL 中就包含 DDL。

---

# 五、Logical Decoding 扩展

逻辑复制发送 WAL 时在：

```
pgoutput plugin
```

文件：

```
src/backend/replication/pgoutput/pgoutput.c
```

需要扩展：

```
pgoutput_decode_message()
```

当前逻辑：

```
prefix == "pgoutput"
```

新增：

```
prefix == "pg_ddl_replication"
```

处理：

```c
OutputPluginPrepareWrite(ctx, true);

pq_sendbyte(ctx->out, REPLICATION_MSG_DDL);
pq_sendstring(ctx->out, message);

OutputPluginWrite(ctx, true);
```

发送到 replication stream。

---

# 六、Replication Protocol 扩展

logical replication protocol 目前消息：

```
BEGIN
COMMIT
INSERT
UPDATE
DELETE
RELATION
```

新增：

```
DDL
```

定义：

```
#define LOGICAL_REP_MSG_DDL 'D'
```

数据结构：

```
[D][length][ddl_sql]
```

---

# 七、Subscriber Apply Worker

apply worker 代码：

```
src/backend/replication/logical/worker.c
```

主循环：

```
LogicalRepApplyLoop()
```

接收消息：

```
apply_dispatch()
```

新增处理：

```c
case LOGICAL_REP_MSG_DDL:
    apply_handle_ddl(msg);
```

---

# 八、执行DDL

实现函数：

```
apply_handle_ddl()
```

流程：

```c
StartTransactionCommand();

ProcessUtility(
    parse_analyze(query),
    query,
    PROCESS_UTILITY_TOPLEVEL,
    NULL,
    NULL,
    None_Receiver,
    NULL);

CommitTransactionCommand();
```

关键点：

* 在 subscriber 上执行 SQL
* 必须在事务内执行
* 保证与 DML 顺序一致

---

# 九、完整流程

完整链路如下：

```
Publisher
--------------------------------

CREATE TABLE t1

↓
ProcessUtility()

↓
判断 publication 是否启用 ddl

↓
LogLogicalMessage()

↓
WAL (RM_LOGICALMSG_ID)

↓
logical decoding

↓
pgoutput plugin

↓
send DDL replication message

--------------------------------

Network

--------------------------------

Subscriber

↓
walreceiver

↓
logical replication worker

↓
apply_dispatch()

↓
apply_handle_ddl()

↓
ProcessUtility()

↓
CREATE TABLE t1
```

---

# 十、流程图

```
             Publisher
 ┌──────────────────────────────┐
 │ CREATE TABLE t1              │
 │ ProcessUtility()             │
 │   ↓                          │
 │ LogLogicalMessage()          │
 └───────────────┬──────────────┘
                 │
                 ▼
           WAL LogicalMsg
                 │
                 ▼
         Logical Decoding
                 │
                 ▼
            pgoutput
                 │
                 ▼
        Replication Stream
                 │
                 ▼
             Subscriber
 ┌──────────────────────────────┐
 │ apply worker                 │
 │   ↓                          │
 │ receive DDL message          │
 │   ↓                          │
 │ ProcessUtility()             │
 │   ↓                          │
 │ CREATE TABLE t1              │
 └──────────────────────────────┘
```

---

# 十一、需要修改的核心文件

主要涉及以下模块：

### SQL接口

```
publicationcmds.c
subscriptioncmds.c
```

### catalog

```
pg_publication.h
pg_publication.c
```

### DDL捕获

```
utility.c
```

### WAL写入

```
logical.c
```

### decoding

```
pgoutput.c
```

### subscriber执行

```
worker.c
```

---

# 十二、实现复杂度评估

代码改动规模大约：

```
新增代码      ~1500 行
修改代码      ~500 行
新增 catalog   1 列
新增 replication message 1 种
```

开发量：

```
约 2-3 周
```

---

# 十三、和 pglogical 方案的区别

| 功能                  | pglogical | 内核DDL复制 |
| ------------------- | --------- | ------- |
| DML复制               | 有         | 有       |
| DDL复制               | 有         | 有       |
| multi-master        | 有         | 无       |
| conflict resolution | 有         | 无       |
| sequence复制          | 有         | 无       |
| 实现方式                | extension | core    |

你的方案：

**更简单、更稳定、适合生产。**

---

# 逻辑复制并不要求两张表的结构一致，而且要求必须要有主键

这是一个**非常关键的问题**，也是很多人在设计 **DDL replication + PostgreSQL logical replication** 时容易忽略的地方。你的观察是正确的：

* PostgreSQL **逻辑复制并不要求 publisher / subscriber 表结构完全一致**
* 但 **UPDATE / DELETE 需要 replica identity（通常是主键）**

因此如果直接把 **DDL 自动复制**，确实可能和现有逻辑复制机制产生冲突。下面我们把问题拆开分析，并给出一套 **合理的内核设计策略**。

---

# 一、PostgreSQL 逻辑复制的设计原则

在 PostgreSQL 的逻辑复制中：

### 1 表结构不要求完全一致

例如：

Publisher

```sql
CREATE TABLE t(
    id int primary key,
    a int
);
```

Subscriber

```sql
CREATE TABLE t(
    id int primary key,
    a int,
    b int
);
```

仍然可以复制：

```sql
INSERT INTO t VALUES(1,10);
```

原因：

复制是 **按列名映射**。

---

### 2 UPDATE / DELETE 必须能定位行

要求：

```text
replica identity
```

通常是：

```
PRIMARY KEY
```

或者：

```
REPLICA IDENTITY FULL
```

否则会报错：

```
cannot update table because it does not have a replica identity
```

---

# 二、DDL复制可能导致的冲突

如果简单复制DDL，会出现几类问题。

---

# 1 主键不一致

示例：

Publisher

```sql
CREATE TABLE t(
  id int primary key
);
```

Subscriber

```sql
CREATE TABLE t(
  id int
);
```

如果DDL复制：

```sql
ALTER TABLE t ADD PRIMARY KEY(id);
```

可能失败：

* subscriber 已有重复数据
* index 已存在

结果：

```
ERROR
apply worker crash
```

---

# 2 列顺序 / 列差异

Publisher

```sql
ALTER TABLE t ADD COLUMN c int;
```

Subscriber

```sql
table t already has column c
```

DDL复制会失败。

---

# 3 删除列

Publisher

```sql
ALTER TABLE t DROP COLUMN a;
```

Subscriber

```
column a still used by application
```

复制会破坏 subscriber。

---

# 4 REPLICA IDENTITY 冲突

Publisher

```
PRIMARY KEY(id)
```

Subscriber

```
REPLICA IDENTITY FULL
```

如果DDL复制：

```
DROP PRIMARY KEY
```

DML复制可能失效。

---

# 三、PostgreSQL 社区为什么没有做DDL复制

核心原因就是：

```
logical replication
    ≠ schema replication
```

逻辑复制的设计目标：

```
允许 schema 演进
允许 schema 差异
```

DDL replication 会破坏这一点。

---

# 四、正确的设计策略（关键）

如果你要在 **内核实现DDL replication**，必须限制作用范围。

推荐策略：

```
DDL replication
只在 publisher / subscriber schema 完全一致时使用
```

也就是说：

```
DDL replication = strict schema mode
```

---

# 五、具体实现策略

可以在 **CREATE SUBSCRIPTION** 中增加模式。

### 新参数

```sql
CREATE SUBSCRIPTION sub1
CONNECTION '...'
PUBLICATION pub1
WITH (
  enable_ddl = true,
  schema_mode = strict
);
```

模式：

| 模式       | 行为         |
| -------- | ---------- |
| strict   | schema必须一致 |
| relaxed  | 允许差异       |
| disabled | 不复制DDL     |

默认：

```
disabled
```

---

# 六、strict schema mode 的规则

在 strict 模式下：

### 1 publisher / subscriber schema 必须一致

在 subscription 建立时检查：

```text
table name
column name
column type
primary key
```

检查位置：

```
initial table sync
```

如果不一致：

```
ERROR
```

---

### 2 禁止 subscriber 手动DDL

可以增加保护：

```
DDL guard
```

如果 subscription active：

```
subscriber 禁止本地DDL
```

否则：

```
schema drift
```

---

### 3 自动同步 schema

订阅创建时：

```
copy_data
```

可以增加：

```
copy_schema
```

例如：

```sql
CREATE SUBSCRIPTION sub1
WITH (
  copy_schema = true
);
```

实现：

```
pg_dump schema
```

或者：

```
send CREATE TABLE via replication
```

---

# 七、DDL复制只允许安全DDL

强烈建议限制DDL类型。

支持：

```
CREATE TABLE
ALTER TABLE ADD COLUMN
CREATE INDEX
DROP INDEX
```

不支持：

```
DROP COLUMN
ALTER COLUMN TYPE
DROP TABLE
```

原因：

这些DDL会破坏复制。

---

# 八、DDL冲突处理策略

建议增加策略参数：

```sql
ddl_conflict = error | skip
```

行为：

| 冲突            | error | skip |
| ------------- | ----- | ---- |
| DDL已存在        | 停止复制  | 忽略   |
| column exists | 停止复制  | 忽略   |

默认：

```
error
```

---

# 九、推荐最终架构

最终逻辑：

```
Publisher
   |
   |  DDL
   v
ProcessUtility
   |
   v
LogLogicalMessage
   |
   v
WAL
   |
   v
logical decoding
   |
   v
pgoutput
   |
   v
replication stream
   |
   v
Subscriber
   |
   v
apply worker
   |
   v
schema validation
   |
   v
ProcessUtility
```

---

# 十、最佳实践建议

如果目标是 **生产级DDL复制**，建议：

实现两种模式：

### 1 标准模式（默认）

```
DML replication only
```

### 2 schema replication mode

```
schema_strict = true
enable_ddl = true
```

这个模式类似：

* MySQL binlog schema replication
* Oracle logical standby

---

# 十一、现实数据库的做法

不同数据库策略：

| 数据库             | DDL复制                |
| --------------- | -------------------- |
| MySQL           | 默认复制DDL              |
| Oracle Database | logical standby复制DDL |
| PostgreSQL      | 默认不复制DDL             |
| PolarDB         | WAL logical message  |

PostgreSQL 是最保守的。

---

# 十二、结论

你的问题的核心答案：

**是的，会冲突。**

原因：

```
logical replication 允许 schema 差异
DDL replication 会强制 schema 一致
```

正确解决方案：

1️⃣ 增加 **schema_strict 模式**
2️⃣ subscription 创建时做 **schema validation**
3️⃣ 限制 **可复制DDL类型**
4️⃣ 增加 **ddl_conflict 策略**

这样才能保证：

```
DDL replication
不会破坏 logical replication
```

---


