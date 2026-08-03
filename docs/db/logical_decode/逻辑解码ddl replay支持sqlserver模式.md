# 逻辑解码ddl replay支持sqlserver模式

# 1. 设计背景

当前 PostgreSQL Logical Replication 仅支持 DML 同步。

对于 Babelfish 场景：

```sql
CREATE TABLE dbo.t1
(
    id INT IDENTITY(1,1)
)
```
DDL 不仅修改 PostgreSQL Catalog：

```
pg_class
pg_attribute
pg_namespace
```
同时还维护：

```
sys.objects
sys.tables
sys.columns
object_id
schema mapping
```
等 SQL Server 兼容元数据。

如果订阅端直接执行 PostgreSQL DDL：

```c
ProcessUtility()
```
则无法保持 TSQL 语义。

因此需要在逻辑复制框架中引入：

```
Babelfish DDL Replay Adapter
```
实现 TSQL DDL 回放。

# 2. 设计目标

## 2.1 功能目标

支持：

```
CREATE TABLE
ALTER TABLE
DROP TABLE

CREATE INDEX
DROP INDEX

CREATE VIEW
DROP VIEW

CREATE FUNCTION
DROP FUNCTION

CREATE PROCEDURE
DROP PROCEDURE
```
同步。

## 2.2 非目标

不处理：

```
INSERT
UPDATE
DELETE
COPY
MERGE
```
DML继续使用 PostgreSQL Logical Replication。

## 2.3 核心目标

保证订阅端：

```
sys.objects

sys.tables

sys.columns

object_id

schema mapping
```
与发布端保持一致。

# 3. 总体架构

## 3.1 DDL同步架构

```
Publisher
     │
     ▼

DDL Capture

     │
     ▼

DDL Message

     │
     ▼

Replay Framework

     │
     ▼

Babelfish Adapter

     │
     ▼

Babelfish Context

     │
     ▼

Babelfish Parser

     │
     ▼

TSQL Parse Tree

     │
     ▼

Babelfish Utility

     │
     ▼

PostgreSQL Utility
```
# 4. DDL消息设计

## 4.1 消息类型

新增：

```c
LOGICAL_REP_MSG_DDL
```
## 4.2 消息结构

```c
typedef struct LogicalRepDDL
{
    char       *ddl_sql;

    char       *dbname;

    char       *schema_name;

    char       *owner_name;

    XLogRecPtr commit_lsn;
} LogicalRepDDL;
```
# 5. Replay Framework

## 5.1 Adapter接口

```c
typedef struct DDLReplayAdapter
{
    const char *name;

    bool (*replay_ddl)
    (
        ReplayExecContext *ctx,
        LogicalRepDDL *ddlmsg
    );

} DDLReplayAdapter;
```
## 5.2 DDL分发

```c
switch(msgtype)
{
    case LOGICAL_REP_MSG_DDL:

        ddl_adapter->replay_ddl(
                ctx,
                ddlmsg);

        break;
}
```
# 6. Babelfish Adapter设计

## 6.1 Adapter注册

```c
RegisterDDLReplayAdapter(
        REPLAY_DIALECT_TSQL,
        &babelfish_adapter);
```
## 6.2 Replay入口

```c
bool
bbf_replay_ddl(
        ReplayExecContext *ctx,
        LogicalRepDDL *ddlmsg);
```
## 6.3 执行流程

```
bbf_replay_ddl()
       ↓
bbf_context_init()
       ↓
bbf_context_activate()
       ↓
bbf_parse_and_replay()
       ↓
bbf_context_deactivate()
```
# 7. Babelfish Context设计

## 7.1 Context结构

```c
typedef struct BabelfishExecContext
{
    bool        is_bbf_context;

    char       *database_name;

    char       *schema_name;

    Oid         user_oid;

    bool        tsql_mode;
} BabelfishExecContext;
```
## 7.2 初始化

恢复：

```
Current Database

Current User

Search Path

Database Mapping
```
## 7.3 激活

```c
bbf_context_activate();
```
进入：

```
TSQL Semantic Context
```
# 8. Parser Replay设计

## 8.1 设计原则

禁止：

```c
SPI_execute(sql);
```
禁止：

```c
ProcessUtility(sql);
```
禁止：

```c
raw_parser(sql);
```
直接进入 PostgreSQL Parser。

## 8.2 Replay入口

新增：

```c
bool
bbf_parse_and_replay(
        LogicalRepDDL *ddlmsg);
```
## 8.3 Parse流程

```
DDL SQL
      ↓
babelfishpg_tsql_raw_parser()
      ↓
TSQL Parse Tree
```
生成：

```
tsql_parse_tree
```
## 8.4 Analyze流程

```
TSQL Parse Tree
        ↓
Babelfish Analyzer
        ↓
TSQL Utility Node
```
## 8.5 Utility执行

```
TSQL Utility Node
        ↓
Babelfish Utility Hook
        ↓
standard_ProcessUtility()
```
# 9. DDL Replay执行路径

## CREATE TABLE

```
DDL Message
      ↓
Babelfish Adapter
      ↓
babelfishpg_tsql_raw_parser
      ↓
CreateStmt(TSQL)
      ↓
Babelfish Catalog Update
      ↓
PG Catalog Update
```
## ALTER TABLE

```
DDL Message
      ↓
Babelfish Parser
      ↓
AlterTableStmt
      ↓
Babelfish Utility
      ↓
PG Utility
```
## DROP TABLE

```
DDL Message
      ↓
Babelfish Parser
      ↓
DropStmt
      ↓
Babelfish Utility
      ↓
PG Utility
```
# 10. Catalog一致性维护

Replay过程中自动维护：

```
sys.objects

sys.tables

sys.columns

sys.indexes
```
以及：

```
object_id

database mapping

schema mapping
```
无需额外同步逻辑。

# 11. 事务一致性

发布端：

```sql
BEGIN TRAN

CREATE TABLE t1

ALTER TABLE t1 ADD c1

COMMIT
```
订阅端：

```
BEGIN

Replay CREATE

Replay ALTER

COMMIT
```
保持事务边界一致。

# 12. 错误处理

分类：

```
Context Error

Parse Error

Analyze Error

Utility Error

Catalog Error
```
返回：

```c
REPLAY_SUCCESS

REPLAY_RETRYABLE_ERROR

REPLAY_FATAL_ERROR
```
由 Replay Framework 统一处理。

# 13. 涉及模块

## PostgreSQL Core

新增：

```
logicalddl.c

logicalddl.h

replay_framework.c

replay_framework.h

replay_adapter.c

replay_adapter.h
```
## Babelfish

新增：

```
bbf_context.c

bbf_context.h

bbf_adapter.c

bbf_adapter.h

bbf_replay.c

bbf_replay.h
```
修改：

```
hooks.c

session.c

pl_handler.c

parser_entry.c
```
# 15. 预期收益

1. 完整复用Babelfish Parser。
2. 完整保持TSQL语义。
3. 自动维护sys Catalog。
4. 不依赖TDS连接。
5. 不修改现有DML复制路径。
6. PostgreSQL Core不依赖Babelfish。
7. 为未来Oracle/MySQL Adapter提供统一Replay Framework。
