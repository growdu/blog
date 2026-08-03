# 内核执行 Babelfish 上下文需要考虑的问题

## 概述

SQL Server 和 PG 本身在数据库架构层面 schema 的含义就不一致：

| 维度 | SQL Server | PostgreSQL |
|------|-----------|------------|
| 命名空间 | 三级：Database → Schema → Object | 两级：Schema → Object |
| 逻辑数据库 | 有（SQL Server 数据库） | 无（PG 直接用 schema 组织） |
| 端口区分 | 无 | Babelfish 用端口区分模式 |
| 连接类型 | TDS 协议 | PG 协议 + TDS 协议 |

Babelfish 使用端口来和 PG 模式进行区分，因而 Babelfish 里面的很多逻辑都是和端口强绑定，即 `MyProcPort`。

同时根据客户端连接方式的不同：
- **PG-TSQL**：psql 连接 Babelfish 端口（5432），走 PG 协议但设置 `sql_dialect = 'tsql'`
- **TDS**：sqlcmd/SSMS 连接 Babelfish 端口（1433），走 TDS 协议

两者的内部执行路径不完全一致，这对 DDL 同步有重要影响。

---

## Schema 映射问题

### Multi-DB 和 Single-DB

Babelfish 支持两种部署模式：

**Multi-DB 模式（默认）**：
```
┌─────────────────────────────────────────────┐
│ PostgreSQL Cluster                          │
│                                             │
│  ┌─────────────┐  ┌─────────────┐          │
│  │ Database:   │  │ Database:   │          │
│  │ myapp       │  │ sales       │          │
│  │             │  │             │          │
│  │  Schema:    │  │  Schema:    │          │
│  │  dbo        │  │  dbo        │          │
│  │  sys        │  │  sys        │          │
│  └─────────────┘  └─────────────┘          │
│         │                │                 │
│         └────────────────┴──────► Babelfish│
│         映射到不同的物理 PG database        │
└─────────────────────────────────────────────┘
```
**Single-DB 模式**：
```
┌─────────────────────────────────────────────┐
│ PostgreSQL Cluster (single database)        │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │ Database: postgres                   │   │
│  │                                     │   │
│  │  Schema (logical):      Physical:   │   │
│  │  dbo                →   public      │   │
│  │  sys                →   sys         │   │
│  │  INFORMATION_SCHEMA → information_  │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```
**关键差异**：

| 特性 | Multi-DB | Single-DB |
|------|----------|-----------|
| 数据库隔离 | 强（不同物理 DB） | 弱（共用一个 DB） |
| `CREATE DATABASE` | 支持 | 不支持 |
| 跨库查询 | 不支持 | 支持（通过 schema 区分） |
| 迁移复杂度 | 高 | 低 |
| DDL 捕获时的 current db | 必需 | 可忽略 |

### 逻辑数据库和物理数据库

Babelfish 维护一套逻辑数据库名到物理数据库名的映射：

```c
// babelfishpg_tsql/src/multidb.c

typedef struct {
    const char *logical_db_name;     // 逻辑名：myapp, sales
    const char *physical_db_name;     // 物理名：myapp, sales (multi-db) 或 postgres (single-db)
    Oid         db_id;               // 数据库 OID
    bool        is_plpgsql Trusted;   // 是否有 plpgsql 扩展
} LogicalDBEntry;

// 查询逻辑数据库
LogicalDBEntry *
get_logical_db_entry(const char *logical_name)
{
    // 在系统表中查找映射
}

// 获取当前逻辑数据库
const char *
get_current_logical_database_name(void)
{
    // 返回当前连接的逻辑数据库名
}
```
**DDL 同步时的问题**：

```sql
-- 发布端执行 (连接到 logical DB: myapp)
CREATE TABLE myapp.dbo.t1 (id INT);

-- 捕获的 DDL SQL 可能是：
-- 1. 包含数据库名：CREATE TABLE myapp.dbo.t1 ...
-- 2. 不包含数据库名：CREATE TABLE dbo.t1 ...
-- 3. 使用物理名：CREATE TABLE public.t1 ...
```
### Current DB Name

在 DDL 执行时，Babelfish 需要知道"当前是哪个逻辑数据库"：

```c
// 获取当前数据库上下文
static char *
get_current_db_name(void)
{
    // 优先从 session 变量获取
    const char *val = get_config_option("babelfishpg_tsql.database_name", false, true);
    if (val)
        return pstrdup(val);

    // 回退到 catalog 查询
    Oid db_oid = MyDatabaseId;
    return get_logical_database_name(db_oid);
}
```
**对于 apply worker 的挑战**：

apply worker 连接的是物理 PG 数据库，但 DDL SQL 可能是逻辑数据库名：
```sql
-- 发布端在 myapp.dbo 创建表
CREATE TABLE dbo.t1 (id INT);

-- 订阅端 apply worker 连接的是物理 DB
-- 需要知道这个 dbo 对应哪个物理 schema
```
### Schema Mapping

Babelfish 维护逻辑 schema 到物理 schema 的映射：

**Multi-DB 模式**：
| 逻辑 Schema | 物理 Schema |
|------------|-------------|
| dbo | public |
| sys | sys |
| INFORMATION_SCHEMA | information_schema |

**Single-DB 模式**：
| 逻辑 Schema | 物理 Schema |
|------------|-------------|
| dbo | dbo |
| sys | sys |
| INFORMATION_SCHEMA | INFORMATION_SCHEMA |

**映射查询函数**：

```c
// babelfishpg_tsql/src/multidb.c

// 将逻辑 schema 名转换为物理 schema 名
char *
get_physical_schema_name(const char *logical_schema)
{
    // 查询 sys.babelfish_namespace 表
    // 返回物理 schema 名
}

// 将物理 schema 名转换为逻辑 schema 名
char *
get_logical_schema_name(const char *physical_schema)
{
    // 反向查询
}

// 完全解析表引用（database.schema.table）
void
rewrite_object_name(ObjectName *name)
{
    // 如果没有指定 database，使用当前逻辑数据库
    // 如果没有指定 schema，使用 dbo
    // 然后查找物理映射
}
```
**DDL 同步时的 schema 处理**：

```sql
-- 发布端 DDL
CREATE TABLE dbo.t1 (
    id INT PRIMARY KEY,
    name NVARCHAR(100)
);

-- 捕获时需要保存的信息：
{
    "ddl_sql": "CREATE TABLE dbo.t1 ...",
    "search_path": "dbo,pg_catalog",  -- 发布端的 search_path
    "current_db": "myapp",            -- 当前逻辑数据库
    "target_schema": "public"          -- 物理 schema（multi-db）
}
```
---

## PG-TSQL 和 TDS

### PG-TSQL

PG-TSQL 是通过 PostgreSQL 协议连接 Babelfish，但设置 `sql_dialect = 'tsql'`：

```
客户端 (psql)
     │
     │ PG 协议
     ▼
Babelfish 端口 (5432)
     │
     ├──► 解析 PG 协议数据
     │
     ├──► 设置 sql_dialect = 'tsql'（session 变量）
     │
     ▼
PG-TSQL 执行路径
     │
     ├──► PG parser (使用 T-SQL 语法规则)
     ├──► bbf_ProcessUtility() hook
     └──► T-SQL 兼容函数
```
**PG-TSQL 的特点**：
- 仍然是 PG 连接，`MyProcPort->proc` 是 PG 的
- `Is_TSQL_CLIENT()` 可能返回 false（取决于实现）
- 适合：已存在 PG 工具/脚本，渐进式迁移

**代码判断**：
```c
// babelfishpg_tsql/src/pl_handler.c

bool
IsTDSSprotocol(void)
{
    // 检查是否是 TDS 协议连接
    // 实际上是检查 MyProcPort->hints 中是否有 TDS 相关标记
}

bool
isTDSConnection(void)
{
    // 更直接的检查方式
    // 检查连接是否是 Babelfish TDS 端口 (1433)
}
```
### TDS

TDS (Tabular Data Stream) 是 SQL Server 的原生协议：

```
客户端 (sqlcmd, SSMS)
     │
     │ TDS 协议
     ▼
Babelfish TDS 端口 (1433)
     │
     ├──► TDS 协议解析
     ├──► 设置 sql_dialect = 'tsql'
     └──► 完全 T-SQL 兼容层
```
**TDS 的特点**：
- 完全 T-SQL 兼容
- 支持 SQL Server 特有语法
- `Is_TSQL_CLIENT()` 返回 true
- 支持 `sp_` 存储过程

### PG-TSQL 和 TDS 的执行差异

| 操作 | PG-TSQL | TDS |
|------|---------|-----|
| `ALTER VIEW` | ❌ 报错 | ✅ 支持 |
| `CREATE TRIGGER` | ⚠️ 有限支持 | ✅ 支持 |
| `SELECT INTO` | ⚠️ 有限支持 | ✅ 支持 |
| `IDENTITY` | ✅ 支持 | ✅ 支持 |
| `NVARCHAR(MAX)` | ✅ 支持 | ✅ 支持 |
| `SET NOCOUNT ON` | ❌ 不识别 | ✅ 支持 |

---

## Apply Worker Replay DDL

### 发布端转换 TSQL 为 PG SQL 发送

发布端捕获 DDL 时，DDL SQL 是用户输入的 T-SQL 语法。方案一是将 T-SQL DDL 转换为 PG DDL 再发送：

**转换类型**：

| T-SQL 类型 | 转换规则 | PG 结果 |
|-----------|---------|---------|
| `INT IDENTITY(1,1)` | → `SERIAL` | 自增序列 |
| `NVARCHAR(MAX)` | → `TEXT` | 文本类型 |
| `DATETIME2` | → `TIMESTAMP` | 时间戳 |
| `BIT` | → `BOOLEAN` | 布尔类型 |
| `[dbo].[t1]` | → `public.t1` | Schema 映射 |
| `DROP TABLE t1` | → `DROP TABLE IF EXISTS t1` | 安全删除 |

**转换代码结构**：

```c
// postgresql-3/src/backend/tcop/utility.c

typedef struct {
    const char *tsql_type;      // T-SQL 类型名
    const char *pg_type;         // PG 等价类型
    bool        need_rewrite;    // 是否需要 rewrite
} TSQLtoPGMapping;

// 核心转换函数
static char *
rewrite_tsql_ddl(const char *tsql_ddl, const RewriteContext *ctx)
{
    // 1. 解析 T-SQL DDL AST
    List       *stmts = babelfishpg_tsql_raw_parser(tsql_ddl);

    // 2. 遍历节点，转换类型引用
    for (each node in stmts) {
        rewrite_node(node, ctx);
    }

    // 3. 生成 PG SQL
    return deparse_stmt(stmts);
}
```
### Apply Worker 获取 Babelfish 上下文

Apply worker 是 PG 连接，要执行 Babelfish DDL 需要获取正确的上下文：

**需要的上下文信息**：

```c
typedef struct {
    char       *current_database;      // 当前逻辑数据库名
    char       *current_schema;       // 当前 schema (通常是 dbo)
    char       *search_path;          // 发布端捕获时的 search_path
    Oid         current_db_oid;       // 物理数据库 OID
    Oid         target_schema_oid;     // 目标物理 schema OID
} BabelfishContext;
```
**获取方式**：

```c
// 1. 从捕获的 DDL 消息中获取
static BabelfishContext *
extract_bbf_context(const DDLMessage *msg)
{
    BabelfishContext *ctx = palloc0(sizeof(BabelfishContext));

    // 从 pg_publication_sync 消息中解析
    ctx->current_database = msg->database_name;  // 捕获时保存
    ctx->search_path = msg->search_path;         // 捕获时保存

    // 查询物理映射
    ctx->target_schema_oid =
        get_physical_schema_oid(ctx->current_database, "dbo");

    return ctx;
}

// 2. 在 apply worker 中设置上下文
static void
setup_bbf_context(BabelfishContext *ctx)
{
    // 设置当前逻辑数据库
    set_config_option("babelfishpg_tsql.database_name",
                     ctx->current_database,
                     PGC_SUSET, PGC_S_SESSION);

    // 设置 search_path
    set_config_option("search_path",
                     ctx->search_path,
                     PGC_SUSET, PGC_S_SESSION);

    // 设置 dialect
    set_config_option("babelfishpg_tsql.sql_dialect", "tsql",
                     PGC_SUSET, PGC_S_SESSION);
}
```
#### Schema Mapping

Apply worker 需要正确解析 schema 引用：

```c
// 解析 DDL SQL 中的 schema 引用
static void
resolve_schema_references(BabelfishContext *ctx, Node *stmt)
{
    if (IsA(stmt, CreateStmt)) {
        CreateStmt *create = (CreateStmt *)stmt;

        // 处理表名
        resolve_rangevar(create->relation, ctx);

        // 处理列类型
        foreach(col, create->tableElts) {
            if (IsA(l, ColumnDef)) {
                ColumnDef *col = (ColumnDef *)l;
                col->typeName = rewrite_type_name(col->typeName, ctx);
            }
        }
    }
}
```
#### PG-TSQL Parse

使用 PG 解析器配合 T-SQL dialect：

```c
// 在 PG-TSQL 模式下解析 DDL
static List *
parse_ddl_as_pgtsql(const char *ddl_sql)
{
    // 设置 dialect
    set_config_option("babelfishpg_tsql.sql_dialect", "tsql", ...);

    // 使用 PG parser 解析 T-SQL 语法
    List *stmts = pg_parse_query(ddl_sql);

    // 恢复
    set_config_option("babelfishpg_tsql.sql_dialect", "postgres", ...);

    return stmts;
}
```
**问题**：PG parser 只能解析 PG 语法，不能解析纯 T-SQL 语法。对于复杂的 T-SQL DDL 可能会解析失败。

#### TDS Parse

使用 Babelfish 的 T-SQL 解析器：

```c
// 使用 T-SQL 原生解析器
static List *
parse_ddl_as_tsql(const char *ddl_sql)
{
    // T-SQL parser
    List *stmts = babelfishpg_tsql_raw_parser(ddl_sql, RAW_PARSE_DEFAULT);
    return stmts;
}
```
**问题**：T-SQL 解析器输出的 AST 是 PG 节点，但某些 T-SQL 特有的语义信息可能丢失。

### Worker 创建 TDS 连接来执行 TSQL

这是方案三的核心，通过 libpq 建立 TDS 连接执行 DDL：

#### 核心实现

```c
// worker.c 中添加 TDS 连接执行路径

static void
execute_ddl_via_tsql_connection(const char *ddl_sql, BabelfishContext *ctx)
{
    PGconn *tsql_conn;

    // 1. 建立 TDS 连接
    tsql_conn = establish_tsql_connection(ctx->current_database);
    if (!tsql_conn) {
        ereport(ERROR, "Failed to establish TDS connection");
    }

    // 2. 设置 session 选项（与发布端一致）
    set_session_config(tsql_conn, ctx);

    // 3. 执行 DDL
    PGresult *res = PQexec(tsql_conn, ddl_sql);

    if (PQresultStatus(res) != PGRES_COMMAND_OK) {
        // 记录错误
        ereport(ERROR,
            errmsg("DDL execution failed on subscriber"),
            errdetail("%s", PQerrorMessage(tsql_conn)));
    }

    PQclear(res);
    PQfinish(tsql_conn);
}

static PGconn *
establish_tsql_connection(const char *database)
{
    char        conninfo[256];
    PGconn     *conn;

    // 连接到本地 Babelfish TDS 端口
    snprintf(conninfo, sizeof(conninfo),
             "host=localhost port=1433 dbname=%s "
             "user=%s password=%s",
             database,
             babelfish_user,    // 订阅端配置的 Babelfish 用户
             babelfish_pass);

    conn = PQconnectdb(conninfo);

    if (PQstatus(conn) != CONNECTION_OK) {
        PQfinish(conn);
        return NULL;
    }

    return conn;
}
```
#### 数据一致性

**两阶段提交问题**：

```
Apply Worker 执行时序：

┌─────────────────────────────────────────────────────────────┐
│ PG 连接 (执行 DML)                                          │
│ BEGIN;                                                     │
│   INSERT INTO t1 VALUES (1);  ───► 已提交                  │
│ COMMIT;                                                     │
│                                                             │
│                        ┌───────────────────────────────────┤
│                        │ T-SQL 连接 (执行 DDL)              │
│                        │ BEGIN;                             │
│                        │   ALTER TABLE t1 ADD col2 INT;   │
│                        │                                    │
│                        │   ⚠️ 如果失败？                    │
│                        │   ROLLBACK;                        │
│                        └───────────────────────────────────┘
│                                                             │
│ 问题：INSERT 已提交，ALTER TABLE 回滚 → 数据不一致            │
└─────────────────────────────────────────────────────────────┘
```
**解决方案：同步屏障**

```c
// DDL 执行前的同步机制
static void
execute_ddl_with_barrier(const char *ddl_sql, BabelfishContext *ctx)
{
    // 1. 暂停 DML 处理
    pause_dml_processing();

    // 2. 等待所有 pending DML 完成
    wait_for_pending_dml();

    // 3. 确保没有活跃的事务在引用目标表
    wait_for_no_active_txns_on_table(ctx->target_relation);

    // 4. 执行 DDL
    begin_synchronized_transaction();
    execute_ddl_via_tsql_connection(ddl_sql, ctx);
    commit_synchronized_transaction();

    // 5. 恢复 DML 处理
    resume_dml_processing();
}
```
#### 连接池优化

```c
// T-SQL 连接池
typedef struct {
    PGconn         *conn;
    char           *database;
    pthread_mutex_t mutex;
    time_t          last_used;
    int             use_count;
} TSQLConnectionPool;

// 全局连接池
static TSQLConnectionPool tsql_pool = {
    .conn = NULL,
    .mutex = PTHREAD_MUTEX_INITIALIZER,
    .last_used = 0,
    .use_count = 0
};

static PGconn *
get_tsql_connection(const char *database)
{
    pthread_mutex_lock(&tsql_pool.mutex);

    // 检查现有连接
    if (tsql_pool.conn != NULL) {
        if (strcmp(tsql_pool.database, database) == 0 &&
            PQstatus(tsql_pool.conn) == CONNECTION_OK) {

            // 检查连接是否健康
            if (PQping(tsql_pool.conn) == PQPING_OK) {
                tsql_pool.last_used = time(NULL);
                tsql_pool.use_count++;
                pthread_mutex_unlock(&tsql_pool.mutex);
                return tsql_pool.conn;
            }
        }

        // 连接不健康，关闭
        PQfinish(tsql_pool.conn);
        tsql_pool.conn = NULL;
    }

    // 建立新连接
    tsql_pool.conn = establish_tsql_connection(database);
    tsql_pool.database = pstrdup(database);
    tsql_pool.last_used = time(NULL);
    tsql_pool.use_count = 1;

    pthread_mutex_unlock(&tsql_pool.mutex);

    return tsql_pool.conn;
}

// 定期清理连接池
static void
cleanup_tsql_connection_pool(void)
{
    pthread_mutex_lock(&tsql_pool.mutex);

    if (tsql_pool.conn != NULL) {
        time_t idle_time = time(NULL) - tsql_pool.last_used;

        // 超过 5 分钟空闲或使用次数过多，关闭连接
        if (idle_time > 300 || tsql_pool.use_count > 100) {
            PQfinish(tsql_pool.conn);
            tsql_pool.conn = NULL;
            pfree(tsql_pool.database);
        }
    }

    pthread_mutex_unlock(&tsql_pool.mutex);
}
```
---

## PostgreSQL Hook 机制与内核-插件关系

### PostgreSQL 的 Hook 架构原则

PostgreSQL 的核心设计原则之一是**内核不依赖任何插件**，而是通过 hook 机制让插件扩展内核功能：

```
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL 内核                                │
│                                                                 │
│  src/backend/tcop/utility.c                                     │
│       │                                                         │
│       ▼                                                         │
│  ProcessUtility()                                               │
│       │                                                         │
│       ├──► if (ProcessUtility_hook)                            │
│       │         ProcessUtility_hook(pstate, pstmt, ...)        │
│       │              │                                          │
│       │              ▼                                          │
│       │         [插件注册的 hook 函数]                           │
│       │              │                                          │
│       │              ├──► Babelfish: bbf_ProcessUtility()      │
│       │              └──► 其他插件: their_custom_hook()        │
│       │                                                         │
│       ▼                                                         │
│  standard_ProcessUtility()  ◄── 内核默认实现                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

关键点：
1. 内核定义 hook 类型和调用点
2. 插件注册 hook 函数到内核
3. 内核调用 hook 时不知道具体是哪个插件
4. 插件不能直接调用内核私有函数
```
### PostgreSQL 主要 Hook 类型

| Hook 类型 | 定义位置 | 用途 |
|-----------|---------|------|
| `ProcessUtility_hook` | tcop/utility.h | DDL/DML 语句执行 |
| `ExecutorStart_hook` | executor.h | 执行器启动 |
| `ExecutorRun_hook` | executor.h | 执行器运行 |
| `planner_hook` | optimizer/planner.h | 查询规划 |
| `object_access_hook` | catalog/objectaccess.h | 对象访问控制 |
| `shmem_request_hook` | miscadmin.h | 共享内存请求 |
| `post_parse_analyze_hook` | parser/analyze.h | 解析后分析 |

### Babelfish 注册的 Hook 一览

**在 `InstallExtendedHooks()` 中注册**：

```c
// babelfishpg_tsql/src/hooks.c

static void
InstallExtendedHooks(void)
{
    // Executor hooks
    ExecutorStart_hook = pltsql_ExecutorStart;
    ExecutorRun_hook = pltsql_ExecutorRun;
    ExecutorFinish_hook = pltsql_ExecutorFinish;
    ExecutorEnd_hook = pltsql_ExecutorEnd;

    // Planner hooks
    planner_hook = pltsql_planner_hook;

    // Parser hooks
    core_yylex_hook = pgtsql_core_yylex;
    pre_transform_returning_hook = handle_returning_qualifiers;
    // ... 更多 parser hooks

    // Object access hook
    object_access_hook = bbf_object_access_hook;

    // Replication hook
    logicalrep_modify_slot_hook = logicalrep_modify_slot;

    // 其他
    GetNewObjectId_hook = pltsql_GetNewObjectId;
}
```
**在 `pl_handler.c` 中注册的 Hook**：

```c
// babelfishpg_tsql/src/pl_handler.c

ProcessUtility_hook = bbf_ProcessUtility;
relname_lookup_hook = bbf_table_var_lookup;
pre_parse_analyze_hook = ...;
post_parse_analyze_hook = ...;
// TSQL 方言特定的 hooks
```
**Babelfish 自定义 Hook 类型**：

```c
// babelfishpg_tsql/src/hooks.h

// Babelfish 特有的 hook 类型
typedef bool (*bbfCustomProcessUtility_hook_type)(ParseState *pstate,
    PlannedStmt *pstmt, const char *queryString,
    ProcessUtilityContext context, ParamListInfo params,
    QueryCompletion *qc);

// table variable 相关
typedef bool (*table_variable_satisfies_visibility_hook_type)(...);
typedef TM_Result (*table_variable_satisfies_update_hook_type)(...);

// ...
```
### 内核与插件的依赖关系图

```
正确的关系：内核定义 hook，插件注册

┌────────────────────────────────────────────────────────────────┐
│                     PostgreSQL 内核                             │
│                                                                │
│  定义 hook 类型 (例如 ProcessUtility_hook_type)                 │
│  定义 hook 调用点 (例如 ProcessUtility() 中的 if (hook) 调用)  │
│  提供公共 API (set_config_option, get_config_option 等)        │
│                                                                │
└────────────────────────┬───────────────────────────────────────┘
                       │ 定义 + 调用
                       ▼
┌────────────────────────────────────────────────────────────────┐
│                     Babelfish 插件                              │
│                                                                │
│  实现 hook 函数 (bbf_ProcessUtility, bbf_custom_process_...)   │
│  注册到内核 (ExecutorStart_hook = pltsql_ExecutorStart)        │
│  使用内核公共 API (不能调用内核内部函数)                         │
│                                                                │
└────────────────────────────────────────────────────────────────┘

错误的关系：内核直接调用插件函数

┌────────────────────────────────────────────────────────────────┐
│                     PostgreSQL 内核                             │
│  ✗ 直接调用 babelfishpg_tsql 的某个 extern 函数                │
│  ✗ #include "babelfishpg_tsql.h"                              │
│  ✗ 依赖 Babelfish 特定的数据结构                               │
└────────────────────────────────────────────────────────────────┘
```
### 方案二为何违反了这个原则

方案二试图在 apply worker 中直接调用 Babelfish 的接口：

```c
// 方案二的问题代码 - worker.c

// 问题 1：直接调用 Babelfish 的 extern 函数
parsetree_list = babelfishpg_tsql_raw_parser(ddl_sql, RAW_PARSE_DEFAULT);

// 问题 2：假设 Babelfish 存在，内核编译时需要 Babelfish
// 这意味着：如果没有 Babelfish，PG 内核无法编译

// 问题 3：假设特定的 hook 函数存在并可用
set_config_option("babelfishpg_tsql.sql_dialect", "tsql", ...);
```
**这违反了以下原则**：

| 原则 | 违反原因 |
|------|---------|
| 内核不依赖插件 | 内核代码中直接调用 `babelfishpg_tsql_raw_parser()` |
| 插件化架构 | apply worker 逻辑中硬编码了 Babelfish 判断 |
| 可插拔 | PG 编译需要 Babelfish 代码存在 |

### 内核能否调用 Babelfish 暴露的接口？

**Babelfish 暴露的公共接口**（在 `hooks.h` 中用 `extern` 声明）：

```c
// babelfishpg_tsql/src/hooks.h

// 安装/卸载 hooks
extern void InstallExtendedHooks(void);
extern void UninstallExtendedHooks(void);

// 函数参数列表
extern char *gen_func_arg_list(Oid objectId);

// 类型转换
extern Datum pltsql_exec_tsql_cast_value(Datum value, bool *isnull, ...);

// 视图绑定
extern bool handle_bbf_view_binding_on_object_drop(...);
```
**问题是**：即使这些是 `extern` 函数，内核代码也不应该直接调用它们，因为：

1. **运行时绑定**：hook 函数通过函数指针调用，内核不需要知道具体函数
2. **可选插件**：如果没有安装 Babelfish，这些函数不存在
3. **版本兼容**：不同版本的 Babelfish 可能提供不同的接口

### 正确的做法：通过 Hook 机制

**正确的架构应该是**：

```
Apply Worker 执行 DDL
         │
         ▼
┌─────────────────────────┐
│  ProcessUtility()        │
│  (内核公共入口)           │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  ProcessUtility_hook    │
│  (如果有插件注册)        │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  bbf_ProcessUtility()   │
│  (Babelfish hook 函数)   │
└─────────────────────────┘
```
**对于 apply worker，需要考虑的是**：

1. **apply worker 执行 DDL 时，`ProcessUtility_hook` 会被调用吗？**
   - 答案：**会**。apply worker 执行 DDL 就是调用 `ProcessUtility()`
   - 如果 Babelfish 安装并注册了 `ProcessUtility_hook`，hook 会被触发

2. **apply worker 能否获得正确的 Babelfish 上下文？**
   - 答案：**可以**，但需要正确设置 session 变量
   - 设置 `sql_dialect = 'tsql'`
   - 设置 `babelfishpg_tsql.database_name`
   - 设置 `search_path`

3. **Babelfish hook 函数能否正确处理 DDL？**
   - 答案：**部分可以**，但 `Is_TSQL_CLIENT()` 等检查可能失败
   - 这是方案二的根本问题

### 关键发现：Babelfish 是否有用于 Replication 的 Hook？

```c
// Babelfish 注册的唯一专门用于 replication 的 hook
logicalrep_modify_slot_hook = logicalrep_modify_slot;
```
**这个 hook 的用途**：在 logical replication 时修改 tuple slot 中的数据类型（例如 T-SQL 类型到 PG 类型的转换）。

**但这个 hook 不能用于 DDL 同步**，因为：
- 它只处理 DML 数据的类型转换
- 不处理 DDL 语句的执行

### 新增 Hook 的可能性

如果需要在内核和 Babelfish 之间建立更规范的接口，有两个选择：

**选择 1：新增 PG 内核 Hook**

```c
// 在 PG 内核中定义新的 hook
typedef void (*DDLPreExecute_hook_type)(const char *ddl_sql, void *context);
static PGDLLIMPORT DDLPreExecute_hook_type DDLPreExecute_hook;

// 在 apply worker 中调用
if (DDLPreExecute_hook)
    DDLPreExecute_hook(ddl_sql, context);
```
**选择 2：通过 `object_access_hook` 扩展**

```c
// object_access_hook 已经可以拦截对象创建/删除
// 可以扩展它来处理 DDL 同步场景

typedef void (*object_access_hook_type)(
    ObjectAccessType access,
    Oid classId,
    Oid objectId,
    int subId,
    void *arg);

// 拦截 CREATE, DROP, ALTER 操作
```
**选择 3：Babelfish 主动注册处理函数**

```c
// 通过 common_utility_plugin_ptr 暴露接口
// 这是 Babelfish 已经使用的机制

typedef struct Common_Utility_Plugin {
    const char *(*translate_pg_type_to_tsql)(const char *pg_type);
    // ... 其他接口
} Common_Utility_Plugin;
```
### 总结：内核与插件的正确关系

| 问题 | 答案 |
|------|------|
| PG 内核能否直接调用 Babelfish 函数？ | **不能**，违反插件化原则 |
| apply worker 执行 DDL 时 Babelfish hook 会触发吗？ | **会**，如果 `ProcessUtility_hook` 已注册 |
| 方案二的问题在哪里？ | 假设 `sql_dialect = 'tsql'` 足以让 Babelfish 正确处理 DDL |
| 方案三为何可行？ | 建立独立的 TDS 连接，绕过了 hook 调用的上下文问题 |
| 能否新增 Hook 让方案二可行？ | 可以，但需要修改 PG 内核定义新 hook |

---

## 总结

### 各方案上下文获取能力

| 上下文需求 | 方案一 (发布端转换) | 方案二 (PG-TSQL) | 方案三 (TDS 连接) |
|-----------|-------------------|-----------------|-----------------|
| Schema 映射 | 发布端处理 ✅ | PG 连接上下文 ⚠️ | 完整 TDS 上下文 ✅ |
| 逻辑数据库 | 发布端处理 ✅ | 需要额外获取 ⚠️ | 通过连接指定 ✅ |
| T-SQL 兼容 | 无需 | 部分支持 ❌ | 完全支持 ✅ |
| Search path | 发布端保存 ✅ | 可能不一致 ⚠️ | 显式设置 ✅ |
| 事务隔离 | PG 事务 ✅ | PG 事务 ✅ | 独立 T-SQL 事务 ⚠️ |

### 方案选择建议

**对于 Multi-DB 模式**：
- 优先选择方案三（TDS 连接）
- 每个逻辑数据库有独立的物理 DB，需要正确的数据库上下文

**对于 Single-DB 模式**：
- 方案一（发布端转换）可行，schema 映射简单
- 方案三也可选，但连接管理复杂度增加

**对于需要完整 T-SQL 兼容**（如 ALTER VIEW）：
- 只能选择方案三（TDS 连接）
