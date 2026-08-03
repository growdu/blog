# 支持逻辑复制同步 DDL 适配 SQL Server 方案

## 背景

### Babelfish 架构概述

Babelfish 是 PostgreSQL 的一个扩展，通过双端口设计支持 SQL Server 协议：

| 端口 | 协议 | 用途 |
|------|------|------|
| 1433 | TDS (Tabular Data Stream) | SQL Server 客户端连接 |
| 5432 | PostgreSQL 协议 | PostgreSQL 客户端连接 |

当 `sql_dialect = 'tsql'` 时，解析器使用 T-SQL 语法；`sql_dialect = 'pg'` 时使用标准 PostgreSQL 语法。

当前采用捕获客户端原始sql，并写入系统表同步到订阅端的方式，在订阅端apply worker对ddl进行repaly。
这就要求apply worker需要拥有和TDS建立后端连接后相同的bbf上下文。
或者换句话说，在pg内核已经加载bbf插件后，提供一种标准的机制：
使pg的worker进程执行ddl sql能够达到像客户端连接tds端口执行ddl sql等价，并且最大程度的利用已有机制，减少内bbf的修改。

### 逻辑复制 DDL 同步流程

```text
发布端                          订阅端
   │                               │
   │  1. DDL 在 ProcessUtility()   │
   │     被 CapturePublicationSyncDDL() 捕获
   │                               │
   │  2. DDL SQL 存入              │
   │     pg_publication_sync 表    │
   │                               │
   │  3. 逻辑解码读取               │
   │     pg_publication_sync 变化   │
   │                               │
   │  4. 通过 pgoutput 插件         │
   │     发送 DDL 消息              │──────────► 5. apply_handle_ddl()
   │                               │              接收 DDL 消息
   │                               │
   │                               │  6. execute_publication_sync_sql_command()
   │                               │     执行 DDL SQL
```text
### 核心问题

订阅端 `apply worker` 执行 DDL SQL 时面临的问题：

1. **apply worker 使用 PG 连接**：默认使用 PostgreSQL 协议连接，无法自动获得 T-SQL 上下文
2. **DDL SQL 是 T-SQL 语法**：捕获的 DDL 是用户通过 TDS 端口输入的 T-SQL 语法
3. **PostgreSQL 无法解析 T-SQL DDL**：如 `CREATE TABLE` 的 T-SQL 语法与 PG 有差异
4. **Babelfish 限制**：部分 DDL 语句在 PG 连接上下文中无法执行（如 `ALTER VIEW`）

---

## 三种方案详细分析

### 方案一：发布端将 DDL SQL 转换为 PG SQL

#### 核心思路

在发布端捕获 DDL 后、存入 `pg_publication_sync` 之前，将 T-SQL DDL 转换为等效的 PG DDL，然后发送转换后的 PG SQL 到订阅端。

#### 技术实现

```text
发布端捕获 DDL (T-SQL 语法)
         │
         ▼
┌─────────────────────────┐
│  T-SQL to PG 转换层      │
│  (基于 AST 重写)         │
└─────────────────────────┘
         │
         ▼
存储转换后的 PG SQL 到 pg_publication_sync
         │
         ▼
订阅端收到并执行 PG SQL (无需 dialect 切换)
```text
**转换类型**：

| T-SQL 语法 | PostgreSQL 等价 |
|-----------|----------------|
| `CREATE TABLE t1 (id INT PRIMARY KEY)` | `CREATE TABLE t1 (id INT PRIMARY KEY)` |
| `CREATE TABLE t1 (id INT IDENTITY(1,1))` | `CREATE TABLE t1 (id SERIAL)` |
| `NVARCHAR(MAX)` | `TEXT` |
| `DATETIME2` | `TIMESTAMP` |
| `BIT` | `BOOLEAN` |
| `DROP TABLE [dbo].[t1]` | `DROP TABLE IF EXISTS t1` |
| `SELECT INTO t1 FROM t2` | `CREATE TABLE t1 AS SELECT ...` |

#### 类型映射转换

Babelfish 已有的类型映射定义（来源：`babelfishpg_common/src/typecode.c`）：

**T-SQL 到 PG 的类型映射表**：

| T-SQL 类型 | PG 映射类型 | 备注 |
|-----------|------------|------|
| `BIGINT` | `int8` | 8字节整数 |
| `INT` | `int4` | 4字节整数 |
| `SMALLINT` | `int2` | 2字节整数 |
| `TINYINT` | `tinyint` | Babelfish特有类型 |
| `BIT` | `bit` | 位类型 |
| `DECIMAL(p,s)` / `NUMERIC(p,s)` | `numeric` | 高精度数值 |
| `MONEY` | `money` | 货币类型 |
| `SMALLMONEY` | `smallmoney` | 小货币类型 |
| `FLOAT` / `REAL` | `float8` / `float4` | 浮点数 |
| `DATETIME` | `datetime` | 日期时间 |
| `DATETIME2(n)` | `datetime2` | 扩展日期时间 |
| `SMALLDATETIME` | `smalldatetime` | 小日期时间 |
| `DATE` | `date` | 日期 |
| `TIME(n)` | `time` | 时间 |
| `DATETIMEOFFSET(n)` | `datetimeoffset` | 带时区偏移 |
| `CHAR(n)` | `bpchar` | 定长字符 |
| `VARCHAR(n)` | `varchar` | 变长字符 |
| `VARCHAR(MAX)` | `text` | 大文本 |
| `NCHAR(n)` | `nchar` | Unicode定长 |
| `NVARCHAR(n)` | `nvarchar` | Unicode变长 |
| `NVARCHAR(MAX)` | `text` | Unicode大文本 |
| `TEXT` | `text` | 文本 |
| `NTEXT` | `ntext` | Unicode文本 |
| `BINARY(n)` | `binary` | 定长二进制 |
| `VARBINARY(n)` | `varbinary` | 变长二进制 |
| `VARBINARY(MAX)` | `bytea` | 大二进制 |
| `IMAGE` | `image` | 图像类型 |
| `UNIQUEIDENTIFIER` | `uniqueidentifier` | GUID |
| `ROWVERSION` / `TIMESTAMP` | `timestamp` | 行版本号 |
| `XML` | `xml` | XML文档 |
| `SQL_VARIANT` | `sql_variant` | 混合类型 |
| `SYSNAME` | `sysname` | 系统名称类型 |

**特殊类型转换规则**：

```c
// IDENTITY 列转换
T-SQL:  CREATE TABLE t1 (id INT IDENTITY(1,1) PRIMARY KEY)
PG:     CREATE TABLE t1 (id SERIAL PRIMARY KEY)

// 或者显式序列
T-SQL:  CREATE TABLE t1 (id INT IDENTITY(1,1) PRIMARY KEY)
PG:     CREATE TABLE t1 (
          id INT PRIMARY KEY DEFAULT nextval('t1_id_seq')
        );
        CREATE SEQUENCE t1_id_seq START WITH 1 INCREMENT BY 1;

// NVARCHAR(MAX) 转换
T-SQL:  CREATE TABLE t1 (name NVARCHAR(MAX))
PG:     CREATE TABLE t1 (name TEXT)

// VARBINARY(MAX) 转换
T-SQL:  CREATE TABLE t1 (data VARBINARY(MAX))
PG:     CREATE TABLE t1 (data BYTEA)

// DATETIME2 精度处理
T-SQL:  CREATE TABLE t1 (dt DATETIME2(7))
PG:     CREATE TABLE t1 (dt TIMESTAMP(7))
```text
#### Schema 和对象名转换

**Schema 映射**：

| T-SQL Schema | Multi-DB 物理 Schema | Single-DB 物理 Schema |
|-------------|---------------------|---------------------|
| `dbo` | `public` | `dbo` |
| `sys` | `sys` | `sys` |
| `INFORMATION_SCHEMA` | `information_schema` | `INFORMATION_SCHEMA` |

**表名 bracket 处理**：

```sql
-- T-SQL 允许用 [] 包裹标识符
T-SQL:  CREATE TABLE [dbo].[t1] ([id] INT, [name] NVARCHAR(100))
PG:     CREATE TABLE public.t1 (id INT, name TEXT)

-- PG 标识符使用双引号
T-SQL:  CREATE TABLE "My Table" (id INT)
PG:     CREATE TABLE "My Table" (id INT)  -- 保持原样

-- 删除时的 schema 处理
T-SQL:  DROP TABLE [dbo].[t1]
PG:     DROP TABLE IF EXISTS public.t1
```text
#### DDL 语句转换规则

**CREATE TABLE**：

```sql
-- 基本类型映射（见类型映射表）
T-SQL:
  CREATE TABLE dbo.t1 (
      id INT PRIMARY KEY,
      name NVARCHAR(50) NOT NULL,
      price DECIMAL(10,2),
      created_at DATETIME2
  )

PG:
  CREATE TABLE public.t1 (
      id INT PRIMARY KEY,
      name VARCHAR(50) NOT NULL,  -- NVARCHAR -> VARCHAR
      price NUMERIC(10,2),        -- DECIMAL -> NUMERIC
      created_at TIMESTAMP         -- DATETIME2 -> TIMESTAMP
  )
```text
**ALTER TABLE**：

```sql
-- ADD COLUMN
T-SQL:  ALTER TABLE t1 ADD col1 INT
PG:     ALTER TABLE t1 ADD COLUMN col1 INT

-- DROP COLUMN
T-SQL:  ALTER TABLE t1 DROP COLUMN col1
PG:     ALTER TABLE t1 DROP COLUMN col1

-- ALTER COLUMN (类型修改)
T-SQL:  ALTER TABLE t1 ALTER COLUMN col1 VARCHAR(100)
PG:     ALTER TABLE t1 ALTER COLUMN col1 TYPE VARCHAR(100)

-- ADD CONSTRAINT
T-SQL:  ALTER TABLE t1 ADD CONSTRAINT pk_t1 PRIMARY KEY (id)
PG:     ALTER TABLE t1 ADD CONSTRAINT pk_t1 PRIMARY KEY (id)
```text
**DROP TABLE / INDEX**：

```sql
-- DROP TABLE
T-SQL:  DROP TABLE [dbo].[t1], [dbo].[t2]
PG:     DROP TABLE IF EXISTS public.t1, public.t2

-- CREATE INDEX
T-SQL:  CREATE INDEX idx1 ON dbo.t1 (name)
PG:     CREATE INDEX idx1 ON public.t1 (name)

-- DROP INDEX
T-SQL:  DROP INDEX idx1 ON dbo.t1
PG:     DROP INDEX IF EXISTS public.idx1 ON public.t1
```text
**CREATE / DROP / ALTER VIEW**（限制同步）：

```sql
-- CREATE VIEW
T-SQL:  CREATE VIEW dbo.v1 AS SELECT id, name FROM t1
PG:     CREATE VIEW public.v1 AS SELECT id, name FROM t1

-- 注意：VIEW DDL 同步受限，见"转换限制"章节
```text
#### 无法转换的 DDL 类型（限制）

以下 DDL 类型**无法通过方案一转换同步**，需要人工处理或使用方案三：

| DDL 类型 | 原因 | 影响等级 | 建议 |
|---------|------|---------|------|
| `ALTER VIEW` | PG 端 `Is_TSQL_CLIENT()` 返回 false | **高** | 人工双端执行 |
| `CREATE TRIGGER` | 生成 `CreateFunctionStmt` 而非 `CreateTrigStmt` | **高** | 人工双端执行 |
| `SELECT INTO` | 触发 hook 生成不支持的 ALTER COLUMN NOT NULL | **中** | 人工双端执行 |
| `CREATE MATERIALIZED VIEW` | 同上 | **中** | 人工双端执行 |
| `ALTER INDEX ... REBUILD` | Babelfish 不支持该语法 | **中** | 人工双端执行 |
| `ALTER TABLE ... REPLICA IDENTITY` | PG 专有语法，T-SQL 端不应出现 | **高** | 禁止同步 |
| `CREATE DATABASE` | Multi-DB 模式下语义不同 | **高** | 不支持 |
| `DROP DATABASE` | 同上 | **高** | 不支持 |
| `CREATE SCHEMA` | 需要同步 schema 创建 | **中** | 需人工确认 |
| `ALTER TABLE ... ADD` 多列 | T-SQL 解析器不支持 | **低** | 拆分为多条 |

#### SQL Server DDL 完整支持表格

##### 表对象 DDL

| T-SQL 语法 | 转换支持 | PG 结果 | 限制与风险 | 建议 |
|-----------|---------|---------|-----------|------|
| `CREATE TABLE dbo.t1 (col1 INT PRIMARY KEY)` | ✅ 完全支持 | `CREATE TABLE public.t1 (col1 INT PRIMARY KEY)` | 类型映射可能需调整 | 直接同步 |
| `CREATE TABLE dbo.t1 (col1 INT IDENTITY(1,1))` | ✅ 完全支持 | `CREATE TABLE public.t1 (col1 SERIAL)` | 序列命名需确认 | 直接同步 |
| `CREATE TABLE dbo.t1 (col1 NVARCHAR(50))` | ✅ 支持 | `CREATE TABLE public.t1 (col1 VARCHAR(50))` | UTF-8 语义差异 | 验证长度 |
| `CREATE TABLE dbo.t1 (col1 NVARCHAR(MAX))` | ✅ 支持 | `CREATE TABLE public.t1 (col1 TEXT)` | TEXT 类型无长度限制 | 直接同步 |
| `CREATE TABLE dbo.t1 (col1 DATETIME2(7))` | ✅ 支持 | `CREATE TABLE public.t1 (col1 TIMESTAMP(7))` | 精度可能略有差异 | 直接同步 |
| `CREATE TABLE dbo.t1 (col1 DECIMAL(18,2))` | ✅ 支持 | `CREATE TABLE public.t1 (col1 NUMERIC(18,2))` | - | 直接同步 |
| `DROP TABLE dbo.t1` | ✅ 完全支持 | `DROP TABLE IF EXISTS public.t1` | - | 直接同步 |
| `DROP TABLE dbo.t1, dbo.t2` | ✅ 支持 | `DROP TABLE IF EXISTS public.t1, public.t2` | 多表删除 | 直接同步 |
| `ALTER TABLE dbo.t1 ADD col1 INT` | ✅ 完全支持 | `ALTER TABLE public.t1 ADD COLUMN col1 INT` | - | 直接同步 |
| `ALTER TABLE dbo.t1 ADD col1 INT, col2 VARCHAR(50)` | ⚠️ 部分支持 | 需拆分为两条 | T-SQL 不支持多列 ADD | **拆分为多条** |
| `ALTER TABLE dbo.t1 DROP COLUMN col1` | ✅ 完全支持 | `ALTER TABLE public.t1 DROP COLUMN col1` | - | 直接同步 |
| `ALTER TABLE dbo.t1 ALTER COLUMN col1 VARCHAR(100)` | ✅ 支持 | `ALTER TABLE public.t1 ALTER COLUMN col1 TYPE VARCHAR(100)` | - | 直接同步 |
| `ALTER TABLE dbo.t1 ALTER COLUMN col1 INT NOT NULL` | ✅ 支持 | `ALTER TABLE public.t1 ALTER COLUMN col1 SET NOT NULL` | - | 直接同步 |
| `ALTER TABLE dbo.t1 ADD CONSTRAINT pk PRIMARY KEY (col1)` | ✅ 完全支持 | 同左 | - | 直接同步 |
| `ALTER TABLE dbo.t1 ADD CONSTRAINT uq UNIQUE (col1)` | ✅ 完全支持 | 同左 | - | 直接同步 |
| `ALTER TABLE dbo.t1 ADD CONSTRAINT fk FOREIGN KEY (col1) REFERENCES t2(col2)` | ✅ 完全支持 | 同左 | - | 直接同步 |
| `ALTER TABLE dbo.t1 ADD CONSTRAINT chk CHECK (col1 > 0)` | ✅ 完全支持 | 同左 | - | 直接同步 |
| `ALTER TABLE dbo.t1 DROP CONSTRAINT pk` | ✅ 完全支持 | `ALTER TABLE public.t1 DROP CONSTRAINT pk` | - | 直接同步 |
| `ALTER TABLE dbo.t1 ADD col1 INT DEFAULT 0` | ✅ 支持 | `ALTER TABLE public.t1 ADD COLUMN col1 INT DEFAULT 0` | - | 直接同步 |
| `ALTER TABLE dbo.t1 DROP DEFAULT FOR col1` | ✅ 支持 | `ALTER TABLE public.t1 ALTER COLUMN col1 DROP DEFAULT` | - | 直接同步 |
| `sp_rename 'dbo.t1.col1', 'col1_new'` | ❌ 不支持 | - | 系统存储过程，无等价 PG | 人工处理 |
| `ALTER TABLE dbo.t1 DROP PRIMARY KEY` | ✅ 支持 | `ALTER TABLE public.t1 DROP PRIMARY KEY` | - | 直接同步 |
| `ALTER TABLE dbo.t1 NOCHECK CONSTRAINT fk` | ⚠️ 部分支持 | PG 无完全等价语法 | 约束检查差异 | 人工确认 |
| `ALTER TABLE dbo.t1 WITH CHECK CHECK CONSTRAINT fk` | ⚠️ 部分支持 | PG 无完全等价语法 | 约束检查差异 | 人工确认 |

##### 索引 DDL

| T-SQL 语法 | 转换支持 | PG 结果 | 限制与风险 | 建议 |
|-----------|---------|---------|-----------|------|
| `CREATE INDEX idx1 ON dbo.t1 (col1)` | ✅ 完全支持 | `CREATE INDEX idx1 ON public.t1 (col1)` | - | 直接同步 |
| `CREATE UNIQUE INDEX idx1 ON dbo.t1 (col1)` | ✅ 完全支持 | `CREATE UNIQUE INDEX idx1 ON public.t1 (col1)` | - | 直接同步 |
| `CREATE INDEX idx1 ON dbo.t1 (col1) INCLUDE (col2)` | ⚠️ 部分支持 | `CREATE INDEX idx1 ON public.t1 (col1)` | INCLUDE 列丢失 | **评估影响** |
| `CREATE INDEX idx1 ON dbo.t1 (col1) WHERE col1 > 0` | ⚠️ 部分支持 | `CREATE INDEX idx1 ON public.t1 (col1) WHERE col1 > 0` | 部分支持 | 直接同步 |
| `DROP INDEX idx1 ON dbo.t1` | ✅ 完全支持 | `DROP INDEX IF EXISTS public.idx1 ON public.t1` | - | 直接同步 |
| `DROP INDEX idx1 ON dbo.t1, idx2 ON dbo.t2` | ✅ 支持 | 需逐条处理 | - | 直接同步 |
| `ALTER INDEX idx1 ON dbo.t1 REBUILD` | ❌ 不支持 | - | Babelfish 不支持 | **人工处理** |
| `ALTER INDEX idx1 ON dbo.t1 REORGANIZE` | ❌ 不支持 | - | Babelfish 不支持 | **人工处理** |
| `ALTER INDEX ALL ON dbo.t1 REBUILD` | ❌ 不支持 | - | Babelfish 不支持 | **人工处理** |
| `CREATE CLUSTERED INDEX idx1 ON dbo.t1 (col1)` | ⚠️ 部分支持 | `CREATE INDEX idx1 ON public.t1 (col1)` | PG 无 CLUSTERED 概念 | **评估影响** |
| `CREATE XML INDEX idx1 ON dbo.t1 (col1)` | ❌ 不支持 | - | XML 索引不支持 | 人工处理 |
| `CREATE FULLTEXT INDEX ON dbo.t1 (col1)` | ❌ 不支持 | - | 全文索引不支持 | 人工处理 |
| `sp_helpindex 'dbo.t1'` | ❌ 不支持 | - | 系统存储过程 | 无需同步 |

##### 视图 DDL

| T-SQL 语法 | 转换支持 | PG 结果 | 限制与风险 | 建议 |
|-----------|---------|---------|-----------|------|
| `CREATE VIEW dbo.v1 AS SELECT ...` | ⚠️ 部分支持 | `CREATE VIEW public.v1 AS SELECT ...` | 语法可转换但同步受限 | **方案三或人工** |
| `ALTER VIEW dbo.v1 AS SELECT ...` | ❌ 不支持 | - | `Is_TSQL_CLIENT()` 返回 false | **人工处理** |
| `DROP VIEW dbo.v1` | ⚠️ 部分支持 | `DROP VIEW IF EXISTS public.v1` | 语法可执行但同步受限 | **方案三或人工** |
| `CREATE OR ALTER VIEW dbo.v1 AS SELECT ...` | ❌ 不支持 | - | 组合语句不支持 | **拆分为 ALTER** |
| `CREATE VIEW dbo.v1 WITH SCHEMABINDING AS ...` | ❌ 不支持 | - | SCHEMABINDING 不支持 | 人工处理 |
| `CREATE VIEW dbo.v1 AS SELECT ... WITH CHECK OPTION` | ⚠️ 部分支持 | `CREATE VIEW public.v1 AS SELECT ... WITH CHECK OPTION` | 部分支持 | **评估** |

##### 触发器 DDL

| T-SQL 语法 | 转换支持 | PG 结果 | 限制与风险 | 建议 |
|-----------|---------|---------|-----------|------|
| `CREATE TRIGGER tr1 ON dbo.t1 FOR INSERT AS ...` | ❌ 不支持 | - | 生成 CreateFunctionStmt | **人工处理** |
| `CREATE TRIGGER tr1 ON dbo.t1 AFTER INSERT AS ...` | ❌ 不支持 | - | 生成 CreateFunctionStmt | **人工处理** |
| `CREATE TRIGGER tr1 ON dbo.t1 INSTEAD OF INSERT AS ...` | ❌ 不支持 | - | 生成 CreateFunctionStmt | **人工处理** |
| `DROP TRIGGER tr1` | ❌ 不支持 | - | 生成 CreateFunctionStmt | **人工处理** |
| `DROP TRIGGER IF EXISTS tr1 ON dbo.t1` | ❌ 不支持 | - | 生成 CreateFunctionStmt | **人工处理** |
| `ENABLE TRIGGER tr1 ON dbo.t1` | ❌ 不支持 | - | 触发器启用状态不支持 | 人工处理 |
| `DISABLE TRIGGER tr1 ON dbo.t1` | ❌ 不支持 | - | 触发器禁用状态不支持 | 人工处理 |

##### 序列 DDL

| T-SQL 语法 | 转换支持 | PG 结果 | 限制与风险 | 建议 |
|-----------|---------|---------|-----------|------|
| `CREATE SEQUENCE dbo.seq1 AS INT START WITH 1` | ✅ 完全支持 | `CREATE SEQUENCE public.seq1 START WITH 1` | - | 直接同步 |
| `CREATE SEQUENCE dbo.seq1 AS BIGINT START WITH 1 INCREMENT BY 1` | ✅ 完全支持 | `CREATE SEQUENCE public.seq1 START WITH 1 INCREMENT BY 1` | - | 直接同步 |
| `ALTER SEQUENCE dbo.seq1 RESTART WITH 100` | ✅ 完全支持 | `ALTER SEQUENCE public.seq1 RESTART WITH 100` | - | 直接同步 |
| `ALTER SEQUENCE dbo.seq1 INCREMENT BY 2` | ✅ 完全支持 | `ALTER SEQUENCE public.seq1 INCREMENT BY 2` | - | 直接同步 |
| `DROP SEQUENCE dbo.seq1` | ✅ 完全支持 | `DROP SEQUENCE IF EXISTS public.seq1` | - | 直接同步 |
| `SELECT NEXT VALUE FOR dbo.seq1` | ⚠️ 部分支持 | `SELECT nextval('public.seq1')` | 语法差异 | **评估** |
| `SELECT CURRENT VALUE FOR dbo.seq1` | ⚠️ 部分支持 | `SELECT lastval()` | 语义不完全等价 | **评估** |

##### 物化视图 DDL

| T-SQL 语法 | 转换支持 | PG 结果 | 限制与风险 | 建议 |
|-----------|---------|---------|-----------|------|
| `SELECT ... INTO dbo.t1 FROM dbo.t2` | ❌ 不支持 | - | 触发不支持的 ALTER COLUMN NOT NULL | **人工处理** |
| `CREATE MATERIALIZED VIEW dbo.mv1 AS SELECT ...` | ❌ 不支持 | - | 触发不支持的 ALTER COLUMN NOT NULL | **人工处理** |
| `ALTER MATERIALIZED VIEW dbo.mv1 REBUILD` | ❌ 不支持 | - | 不支持 | 人工处理 |
| `REFRESH MATERIALIZED VIEW dbo.mv1` | ⚠️ 部分支持 | `REFRESH MATERIALIZED VIEW public.mv1` | 语法可转换但物化视图可能不存在 | **确认存在** |

##### 存储过程和函数 DDL

| T-SQL 语法 | 转换支持 | PG 结果 | 限制与风险 | 建议 |
|-----------|---------|---------|-----------|------|
| `CREATE PROC dbo.sp1 AS BEGIN ... END` | ⚠️ 部分支持 | 需转换为 PG 函数 | 参数处理差异 | **方案三** |
| `ALTER PROC dbo.sp1 AS BEGIN ... END` | ⚠️ 部分支持 | 需转换为 PG 函数 | 参数处理差异 | **方案三** |
| `DROP PROCEDURE dbo.sp1` | ⚠️ 部分支持 | `DROP PROCEDURE IF EXISTS public.sp1` | 函数 vs 过程差异 | **评估** |
| `CREATE FUNCTION dbo.fn1(@p1 INT) RETURNS INT AS ...` | ⚠️ 部分支持 | 需转换为 PG 函数 | 语法差异较大 | **方案三** |
| `ALTER FUNCTION dbo.fn1(...)` | ⚠️ 部分支持 | 需转换为 PG 函数 | 语法差异较大 | **方案三** |
| `DROP FUNCTION dbo.fn1` | ⚠️ 部分支持 | `DROP FUNCTION IF EXISTS public.fn1` | 函数 vs 过程差异 | **评估** |
| `CREATE OR ALTER FUNCTION dbo.fn1(...)` | ❌ 不支持 | - | 组合语句不支持 | **拆分为 ALTER** |

##### Schema DDL

| T-SQL 语法 | 转换支持 | PG 结果 | 限制与风险 | 建议 |
|-----------|---------|---------|-----------|------|
| `CREATE SCHEMA dbo` | ⚠️ 部分支持 | `CREATE SCHEMA IF NOT EXISTS public` | Multi-DB 映射复杂 | **人工确认** |
| `CREATE SCHEMA foo AUTHORIZATION dbo` | ⚠️ 部分支持 | `CREATE SCHEMA IF NOT EXISTS foo` | AUTHORIZATION 差异 | **人工确认** |
| `DROP SCHEMA dbo` | ⚠️ 部分支持 | `DROP SCHEMA IF EXISTS public` | Multi-DB 映射复杂 | **人工确认** |
| `DROP SCHEMA IF EXISTS foo, bar` | ⚠️ 部分支持 | 需逐条处理 | - | **人工确认** |

##### 数据库 DDL

| T-SQL 语法 | 转换支持 | PG 结果 | 限制与风险 | 建议 |
|-----------|---------|---------|-----------|------|
| `CREATE DATABASE db1` | ❌ 不支持 | - | Multi-DB 语义差异太大 | **禁止同步** |
| `ALTER DATABASE db1 SET SINGLE_USER` | ❌ 不支持 | - | PG 无等价语法 | 人工处理 |
| `ALTER DATABASE db1 SET MULTI_USER` | ❌ 不支持 | - | PG 无等价语法 | 人工处理 |
| `DROP DATABASE db1` | ❌ 不支持 | - | Multi-DB 语义差异太大 | **禁止同步** |
| `ALTER DATABASE db1 MODIFY FILE (...)` | ❌ 不支持 | - | 存储参数差异 | 人工处理 |

##### 约束和默认值 DDL

| T-SQL 语法 | 转换支持 | PG 结果 | 限制与风险 | 建议 |
|-----------|---------|---------|-----------|------|
| `CREATE DEFAULT def1 AS 0` | ⚠️ 部分支持 | PG 无同名 DEFAULT 对象 | 需转换为列默认值 | **转换语法** |
| `DROP DEFAULT def1` | ⚠️ 部分支持 | 需查找使用处 | - | **人工确认** |
| `CREATE RULE rule1 AS @value > 0` | ⚠️ 部分支持 | PG 有 RULE 但不推荐 | 语义差异 | 人工确认 |
| `DROP RULE rule1` | ⚠️ 部分支持 | 需确认对象存在 | - | 人工确认 |
| `sp_bindefault 'def1', 'dbo.t1.col1'` | ❌ 不支持 | - | 系统存储过程 | 人工处理 |
| `sp_unbindefault 'dbo.t1.col1'` | ❌ 不支持 | - | 系统存储过程 | 人工处理 |
| `sp_bindrule 'rule1', 'dbo.t1.col1'` | ❌ 不支持 | - | 系统存储过程 | 人工处理 |
| `sp_unbindrule 'dbo.t1.col1'` | ❌ 不支持 | - | 系统存储过程 | 人工处理 |

##### 同义词 DDL

| T-SQL 语法 | 转换支持 | PG 结果 | 限制与风险 | 建议 |
|-----------|---------|---------|-----------|------|
| `CREATE SYNONYM syn1 FOR dbo.t1` | ❌ 不支持 | - | PG 无 SYNONYM | **人工处理** |
| `DROP SYNONYM dbo.syn1` | ❌ 不支持 | - | PG 无 SYNONYM | **人工处理** |

##### 统计信息 DDL

| T-SQL 语法 | 转换支持 | PG 结果 | 限制与风险 | 建议 |
|-----------|---------|---------|-----------|------|
| `CREATE STATISTICS stat1 ON dbo.t1 (col1)` | ⚠️ 部分支持 | `ANALYZE public.t1 (col1)` | 语义差异 | **转换语法** |
| `DROP STATISTICS dbo.t1.stat1` | ⚠️ 部分支持 | 需查找统计信息 | - | **转换语法** |
| `UPDATE STATISTICS dbo.t1` | ⚠️ 部分支持 | `ANALYZE public.t1` | - | **转换语法** |
| `UPDATE STATISTICS dbo.t1 (col1)` | ⚠️ 部分支持 | `ANALYZE public.t1 (col1)` | - | **转换语法** |
| `sp_autostats 'dbo.t1'` | ❌ 不支持 | - | 系统存储过程 | 人工处理 |
| `DBCC SHOW_STATISTICS ('dbo.t1', 'stat1')` | ❌ 不支持 | - | DBCC 命令 | 人工处理 |

##### 排序规则和字符集 DDL

| T-SQL 语法 | 转换支持 | PG 结果 | 限制与风险 | 建议 |
|-----------|---------|---------|-----------|------|
| `CREATE TABLE t1 (c1 NVARCHAR(50) COLLATE Chinese_PRC_CI_AS)` | ⚠️ 部分支持 | 需检查 PG 是否有对应 collation | 排序规则映射复杂 | **人工确认** |
| `ALTER TABLE t1 ALTER COLUMN c1 VARCHAR(50) COLLATE ...` | ⚠️ 部分支持 | 需检查 PG 是否有对应 collation | 排序规则映射复杂 | **人工确认** |

##### 分区表 DDL

| T-SQL 语法 | 转换支持 | PG 结果 | 限制与风险 | 建议 |
|-----------|---------|---------|-----------|------|
| `CREATE PARTITION FUNCTION pf1 (INT) AS RANGE LEFT FOR VALUES (1, 100)` | ⚠️ 部分支持 | 需转换为 PG 分区表 | 语法差异较大 | **人工确认** |
| `CREATE PARTITION SCHEME ps1 AS PARTITION pf1 ALL ON [PRIMARY]` | ⚠️ 部分支持 | 需转换为 PG tablespace | 语义差异 | **人工确认** |
| `ALTER TABLE t1 ADD PARTITION ...` | ⚠️ 部分支持 | `ALTER TABLE t1 ADD PARTITION ...` | 语法差异 | **人工确认** |
| `ALTER TABLE t1 DROP PARTITION ...` | ⚠️ 部分支持 | `ALTER TABLE t1 DROP PARTITION ...` | 语法差异 | **人工确认** |
| `ALTER TABLE t1 SPLIT PARTITION ...` | ⚠️ 部分支持 | 需转换为 PG 语法 | 语义差异 | **人工确认** |
| `ALTER TABLE t1 MERGE PARTITIONS ...` | ⚠️ 部分支持 | 需转换为 PG 语法 | 语义差异 | **人工确认** |

##### 其他维护 DDL

| T-SQL 语法 | 转换支持 | PG 结果 | 限制与风险 | 建议 |
|-----------|---------|---------|-----------|------|
| `TRUNCATE TABLE dbo.t1` | ✅ 完全支持 | `TRUNCATE TABLE public.t1` | - | 直接同步 |
| `TRUNCATE TABLE t1 WITH (PARTITIONS (1, 2))` | ⚠️ 部分支持 | 需转换为具体分区 | - | **评估** |
| `DBCC CHECKDB ('db1')` | ❌ 不支持 | - | DBCC 命令 | 人工处理 |
| `DBCC CHECKTABLE ('dbo.t1')` | ❌ 不支持 | - | DBCC 命令 | 人工处理 |
| `DBCC SHRINKDATABASE (db1, 10)` | ❌ 不支持 | - | DBCC 命令 | 人工处理 |
| `DBCC SHRINKFILE (1, 10)` | ❌ 不支持 | - | DBCC 命令 | 人工处理 |
| `BACKUP DATABASE db1 TO DISK = '...'` | ❌ 不支持 | - | 备份命令 | 无需同步 |
| `RESTORE DATABASE db1 FROM DISK = '...'` | ❌ 不支持 | - | 恢复命令 | 无需同步 |
| `SET IDENTITY_INSERT dbo.t1 ON` | ❌ 不支持 | - | 会话级设置无法同步 | 人工处理 |
| `SET IDENTITY_INSERT dbo.t1 OFF` | ❌ 不支持 | - | 会话级设置无法同步 | 人工处理 |

##### 类型别名 DDL

| T-SQL 语法 | 转换支持 | PG 结果 | 限制与风险 | 建议 |
|-----------|---------|---------|-----------|------|
| `CREATE TYPE dbo.MyType FROM INT` | ⚠️ 部分支持 | 需转换为 PG DOMAIN | - | **评估** |
| `DROP TYPE dbo.MyType` | ⚠️ 部分支持 | `DROP DOMAIN IF EXISTS public.mytype` | - | **评估** |
| `sp_addtype 'MyType', 'INT'` | ❌ 不支持 | - | 系统存储过程 | 人工处理 |
| `sp_droptype 'MyType'` | ❌ 不支持 | - | 系统存储过程 | 人工处理 |

#### DDL 支持汇总表

| DDL 类别 | 可直接同步 | 需转换后同步 | 部分支持 | 不支持 | 总计 |
|---------|----------|-------------|---------|-------|------|
| 表对象 (Table) | 12 | 6 | 1 | 0 | 19 |
| 索引 (Index) | 4 | 1 | 2 | 5 | 12 |
| 视图 (View) | 0 | 0 | 2 | 3 | 5 |
| 触发器 (Trigger) | 0 | 0 | 0 | 5 | 5 |
| 序列 (Sequence) | 4 | 1 | 1 | 0 | 6 |
| 物化视图 | 0 | 0 | 1 | 2 | 3 |
| 存储过程/函数 | 0 | 0 | 4 | 2 | 6 |
| Schema | 0 | 0 | 4 | 0 | 4 |
| 数据库 | 0 | 0 | 0 | 5 | 5 |
| 约束/默认值 | 0 | 0 | 4 | 4 | 8 |
| 同义词 | 0 | 0 | 0 | 2 | 2 |
| 统计信息 | 0 | 0 | 4 | 1 | 5 |
| 排序规则 | 0 | 0 | 2 | 0 | 2 |
| 分区表 | 0 | 0 | 6 | 0 | 6 |
| 维护命令 | 0 | 0 | 1 | 6 | 7 |
| 类型别名 | 0 | 0 | 2 | 2 | 4 |
| **总计** | **20** | **8** | **34** | **37** | **99** |

#### 限制说明

| 限制级别 | 含义 | DDL 数量 | 处理方式 |
|---------|------|---------|---------|
| ✅ 完全支持 | 语法等价，可直接同步 | 20 | 直接同步 |
| ✅ 支持 | 语法略有差异但可转换 | 8 | 转换后同步 |
| ⚠️ 部分支持 | 可转换但有语义差异或限制 | 34 | 评估后同步 |
| ❌ 不支持 | 无法转换或禁止同步 | 37 | 人工处理 |

#### 关键风险提示

1. **高风险（禁止同步）**：
   - `CREATE/DROP DATABASE`
   - `ALTER TABLE ... REPLICA IDENTITY`
   - 视图 DDL (`ALTER VIEW`)
   - 触发器 DDL

2. **中风险（需评估）**：
   - 带 `INCLUDE` 的索引
   - `CLUSTERED` 索引
   - 排序规则指定
   - 分区表

3. **低风险（可直接同步）**：
   - 普通表创建/修改/删除
   - 简单索引创建/删除
   - 序列创建/修改/删除
   - `TRUNCATE TABLE`

#### 转换执行位置和方式

**在发布端捕获时转换**：

```c
// src/backend/tcop/utility.c 修改

// 在 CapturePublicationSyncDDL() 中调用转换
static void
CapturePublicationSyncDDL(...)
{
    // ... 原有捕获逻辑 ...

    // 1. 检测是否需要转换
    if (sql_dialect == SQL_DIALECT_TSQL)
    {
        // 2. 进行 T-SQL 到 PG 的转换
        char *pg_ddl = rewrite_tsql_ddl_to_pg(ddl_sql, &ctx);

        if (pg_ddl != NULL) {
            // 3. 使用转换后的 SQL
            ddl_sql_to_store = pg_ddl;
        } else {
            // 4. 无法转换，标记为不可同步
            mark_ddl_as_unsupported(ddl_type);
            return;
        }
    }

    // ... 后续存储逻辑 ...
}
```text
**核心转换函数结构**：

```c
typedef struct {
    const char *tsql_type;      // T-SQL 类型名
    const char *pg_type;         // PG 等价类型
    bool        need_cast;        // 是否需要显式 CAST
} TSQLtoPGTypeMapping;

// 核心转换函数
static char *
rewrite_tsql_ddl_to_pg(const char *tsql_ddl, const RewriteContext *ctx)
{
    char *result;
    List *stmts;

    // 1. 使用 T-SQL 解析器解析（Babelfish 已安装）
    stmts = babelfishpg_tsql_raw_parser(tsql_ddl, RAW_PARSE_DEFAULT);

    // 2. 遍历 AST 节点，转换类型引用
    stmts = transform_ddl_statements(stmts, ctx);

    // 3. 转换为 PG SQL 字符串
    result = deparse_ddl_statements(stmts);

    return result;
}

// 类型转换
static Node *
transform_type_reference(Node *typeNode, const RewriteContext *ctx)
{
    if (IsA(typeNode, TypeName)) {
        TypeName *tn = (TypeName *) typeNode;
        const char *tsql_typename = tn->names->tail->data.ptr_value;
        const TSQLtoPGTypeMapping *mapping = find_type_mapping(tsql_typename);

        if (mapping) {
            // 替换类型名
            tn->names = makeString(mapping->pg_type);
        }
    }
    return typeNode;
}
```text
#### 语义差异风险

方案一虽然技术上可行，但存在以下语义差异风险：

| 风险类型 | 描述 | 严重程度 | 缓解措施 |
|---------|------|---------|---------|
| **类型精度差异** | `DECIMAL` vs `NUMERIC` 精度处理可能不同 | 中 | 验证测试 |
| **字符串长度语义** | `NVARCHAR(50)` vs `VARCHAR(50)` - 前者是字符数，后者可能是字节 | 高 | 使用 `VARCHAR(n) CHARACTER SET UTF8` |
| **NULL 填充差异** | `CHAR(n)` 在 SQL Server 和 PG 填充行为不同 | 中 | 避免 CHAR 类型 |
| **IDENTITY 语义** | IDENTITY 的起始值和增量语义完全等价？ | 中 | 验证序列行为 |
| **时间精度** | `DATETIME2(7)` vs `TIMESTAMP(7)` 精度是否一致 | 低 | 验证 |
| **排序规则** | COLLATE 语义不同 | 高 | 避免不同 collation 混用 |

#### 转换限制的检测和过滤

**发布端应该过滤的 DDL**：

```c
// 在捕获时检测是否可转换
static bool
can_convert_tsql_ddl_to_pg(const char *ddl_sql, DDLType type)
{
    switch (type) {
        case DDL_CREATE_TABLE:
        case DDL_ALTER_TABLE_ADD_COLUMN:
        case DDL_ALTER_TABLE_DROP_COLUMN:
        case DDL_ALTER_TABLE ALTER_COLUMN_TYPE:
        case DDL_CREATE_INDEX:
        case DDL_DROP_INDEX:
        case DDL_CREATE_SEQUENCE:
        case DDL_DROP_SEQUENCE:
            return true;  // 可转换

        case DDL_ALTER_VIEW:
        case DDL_CREATE_VIEW:
        case DDL_DROP_VIEW:
        case DDL_CREATE_TRIGGER:
        case DDL_DROP_TRIGGER:
        case DDL_CREATE_MATERIALIZED_VIEW:
        case DDL_ALTER_INDEX:
            return false;  // 不可转换

        default:
            return false;  // 默认不可转换
    }
}
```text
#### 优点

1. **订阅端实现简单**：订阅端收到的直接是 PG SQL，可以直接执行，无需额外适配
2. **不改 apply worker**：无需修改订阅端逻辑，保持与原生 PG 逻辑复制兼容
3. **性能好**：不需要在订阅端进行语法切换或建立新连接
4. **对现有流程影响小**：只在发布端捕获时转换，不影响 DDL 同步的其他环节

#### 缺点

1. **转换覆盖度有限**：复杂的 T-SQL DDL 可能无法精确转换或无法转换
2. **需要维护转换映射**：随着 Babelfish 支持更多 T-SQL 语法，转换规则需要同步维护
3. **语义差异风险**：转换后的 SQL 可能与原始 T-SQL 语义不完全等价
4. **不支持的 DDL 无法同步**：如果某些 T-SQL DDL 无法转换为 PG，该 DDL 就无法同步

#### 支持的数据库模式

| 模式 | 支持情况 | 说明 |
|------|----------|------|
| SQL Server 模式 (Babelfish) | 支持 | 需要转换 T-SQL 到 PG |
| PostgreSQL 模式 | 原生支持 | 无需转换，DDL 直接就是 PG 语法 |
| 混合模式 | 部分支持 | 需要在捕获时判断 DDL 来源模式 |

#### 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 转换不完全导致语义差异 | 中 | 限制同步范围，不转换的 DDL 手动执行 |
| 转换规则维护成本 | 中 | 建立转换规则测试用例，自动回归 |
| 部分 DDL 无法转换 | 高 | 明确同步边界，不支持的 DDL 人工处理 |

---

### 方案二：订阅端适配 T-SQL，采用 T-SQL parse query

#### 核心思路

在 Babelfish 层面设计一种机制，使 PostgreSQL 内核的 worker（如逻辑复制 apply worker）能够通过一套标准流程初始化完整的 Babelfish 上下文，用于执行原始的 DDL 和 DML 语句。

使pg的worker进程执行ddl sql能够达到像客户端连接tds端口执行ddl sql等价，并且最大程度的利用已有机制，减少内bbf的修改。

#### 技术实现

```text
订阅端收到 DDL 消息
         │
         ▼
┌─────────────────────────┐
│  设置 bbf执行上下文    │
└─────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│  使用 Babelfish T-SQL    │
│  解析器解析 DDL          │
│  (babelfishpg_tsql_raw_parser) │
└─────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│  通过 bbf_ProcessUtility │
│  执行解析后的 DDL        │
└─────────────────────────┘
         │
         ▼
恢复 PG 执行上下文
```text
通过在bbf端增加bbf上下文初始化的hook接口，用于供非tcp连接的pg后端进程执行sql。

#### 优点

1. **语义完全一致**：使用原生 T-SQL 解析器执行，语义与发布端完全一致
2. **支持所有 T-SQL DDL**：只要 Babelfish 支持的 DDL，都可以同步
3. **不需要转换逻辑**：无需维护转换映射规则
4. **对发布端无侵入**：发布端无需修改，保持原生 PG 逻辑

#### 缺点

1. **需要修改 apply worker**：核心代码修改，引入 Babelfish 依赖
2. **Babelfish 版本耦合**：需要与 Babelfish 版本同步更新

#### 支持的数据库模式

| 模式 | 支持情况 | 说明 |
|------|----------|------|
| SQL Server 模式 (Babelfish) | 支持 | 直接使用 T-SQL 解析器执行 |
| PostgreSQL 模式 | 支持 | 需要补充上下文切换机制 |
| 混合模式 | 需判断 | 需要在执行时判断 DDL 来源并选择解析器 |

#### 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| Babelfish 内部限制导致部分 DDL 失败 | 高 | 识别并限制不可同步的 DDL 类型 |
| apply worker 代码复杂化 | 中 | 模块化设计，隔离 Babelfish 相关逻辑 |
| 版本兼容性问题 | 中 | 建立版本兼容性测试 |

#### 内核执行 Babelfish 上下文的问题分析

在 apply worker（PG 连接上下文）中通过设置 `sql_dialect = 'tsql'` 来执行 Babelfish DDL 面临诸多内核层面的问题：

**1. Hook 执行路径问题**

Babelfish 通过 `ProcessUtility_hook` 拦截 DDL 语句，hook 函数 `bbf_ProcessUtility()` 内部会调用 `bbfCustomProcessUtility_hook`：

```text
apply worker 执行 DDL 流程：

ProcessUtility()
    │
    ├──► CapturePublicationSyncDDL()      // PG 原生 DDL 捕获
    │         (如果订阅端也启用了 DDL 捕获)
    │
    ├──► bbf_ProcessUtility()              // Babelfish hook 入口
    │         │
    │         ▼
    │    检查 sql_dialect == TSQL ?
    │         │
    │         ├──► 是 ──► 调用 bbfCustomProcessUtility_hook
    │         │              │
    │         │              ▼
    │         │         pltsql_bbfCustomProcessUtility()
    │         │              │
    │         │              ├──► T_CreateStmt ──► rewrite_relation_walker()
    │         │              ├──► T_DropStmt   ──► rewrite_relation_walker()
    │         │              └──► 其他        ──► 按需处理
    │         │
    │         └──► 否 ──► 跳过 Babelfish 处理
    │
    └──► standard_ProcessUtility()        // 标准执行
```text
**关键问题**：apply worker 是 PG 连接，即使设置 `sql_dialect = 'tsql'`，但某些 Babelfish 内部检查可能仍然失败。

**2. Is_TSQL_CLIENT() 判断问题**

Babelfish 代码中多处使用 `Is_TSQL_CLIENT()` 判断是否为 T-SQL 客户端：

```c
// babelfishpg_tsql/src/pl_handler.c 或其他位置
bool
Is_TSQL_CLIENT(void)
{
    // 检查当前连接是否是 TDS 连接
    // 可能检查的是连接类型、协议、或者特定的 session 变量
}
```text
**问题**：`Is_TSQL_CLIENT()` 可能不仅检查 `sql_dialect`，还检查连接类型。即使设置了 `sql_dialect = 'tsql'`，如果连接本身不是 TDS 类型，可能返回 false。

**已知受限的 DDL**：

| DDL 类型 | 受限原因 | 错误信息 |
|---------|---------|----------|
| `ALTER VIEW` | `Is_TSQL_CLIENT()` 返回 false 时报错 | "TSQL ALTER VIEW is not supported from PostgreSQL endpoint" |
| `CREATE TRIGGER` | 生成 `CreateFunctionStmt` 而非 `CreateTrigStmt` | 被 `bbf_custom_process_utility_hook` 拦截 |
| `SELECT INTO` | 经过 `bbf_select_into_utility_hook` 处理 | 可能产生不支持的 ALTER COLUMN NOT NULL |

**3. 方言切换的全局影响**

设置 `sql_dialect` 会影响整个 session 的解析行为：

```c
set_config_option("babelfishpg_tsql.sql_dialect", "tsql", ...);

// 此时所有 SQL 解析都使用 T-SQL 语法
// 包括：
//   - DDL 解析
//   - DML 解析
//   - 甚至包括 apply worker 内部的查询
```text
**问题**：切换到 T-SQL 模式后，apply worker 内部执行的一些 PG 工具函数（如 `pg_catalog` 系列）可能受到影响。

**4. 事务处理冲突**

Babelfish 在 T-SQL 模式下对事务的处理方式与 PG 原生不同：

```c
// PG 原生事务语义
BEGIN;
  DDL;  -- 自动提交
  DML;
COMMIT;

// T-SQL 事务语义 (Babelfish)
BEGIN;
  DDL;  -- 不会自动提交
  DML;
COMMIT; -- 显式提交
```text
apply worker 在子事务中执行 DDL，如果 DDL 触发了 Babelfish 的特殊处理，可能导致事务状态不一致。

**5. Search Path 与 Schema 解析**

Babelfish 维护自己的 schema 映射规则：

```c
// 发布端捕获 DDL 时保存的 search_path
saved_search_path = "dbo,pg_catalog"

// 但订阅端的 schema 映射可能不同
// Babelfish 的物理 schema 映射：
//   T-SQL: dbo      → physical: public
//   T-SQL: sys      → physical: sys
//   T-SQL: INFORMATION_SCHEMA → physical: information_schema
```text
**问题**：如果发布端和订阅端的 schema 映射不一致，同样的 DDL SQL 可能在订阅端解析到错误的 schema。

**6. 内部 Hook 拦截问题**

Babelfish 的 `bbfCustomProcessUtility_hook` 可能会拦截某些 DDL 语句：

```c
// hooks.c 中的处理逻辑
static bool
pltsql_bbfCustomProcessUtility(...)
{
    Node *stmt = pstmt->utilityStmt;

    switch (nodeTag(stmt)) {
        case T_CreateFunctionStmt:
            // 直接返回，DDL 不会继续执行
            return pltsql_createFunction(...);

        case T_CreateStmt:
            // 进入 rewrite 流程
            break;

        // ... 其他情况
    }
    return false;  // 继续 standard_ProcessUtility
}
```text
**问题**：某些 DDL 语句被 hook 直接处理而不会继续执行，或者被拦截后返回错误。

**7. 错误处理与回滚**

Babelfish 在执行 DDL 时可能抛出特定类型的错误：

```c
// 可能遇到的错误类型
typedef enum {
    ERRCODE_TSQL_SYNTAX_ERROR,           // T-SQL 语法错误
    ERRCODE_TSQL_FEATURE_NOT_SUPPORTED,   // T-SQL 功能不支持
    ERRCODE_TSQL_OBJECT_NOT_FOUND,        // 对象不存在
    ERRCODE_TSQL_DUPLICATE_OBJECT,        // 对象已存在
    // ...
} TSQL_ErrorCode;
```text
apply worker 需要正确处理这些 T-SQL 特有的错误码，并转换为 PG 能理解的错误。

**8. 内存上下文问题**

Babelfish 可能使用独立的内存上下文：

```c
// T-SQL 解析器可能使用独立内存池
MemoryContext tsql_parser_context;

// apply worker 的内存上下文切换
if (sql_dialect == SQL_DIALECT_TSQL)
{
    // 切换到 Babelfish 的内存上下文？
    // 还是使用 apply worker 自己的？
}
```text
**问题**：内存上下文不匹配可能导致内存泄漏或访问违例。

**9. Catalog 访问权限问题**

Babelfish 在 T-SQL 模式下访问系统 catalog 时可能走不同的路径：

```c
// PG 模式
syscache = SearchSysCache(RELOID, ...);

// T-SQL 模式
// 可能访问 babelfishpg_tsql 扩展维护的 catalog
```text
apply worker 在 PG 连接中访问 Babelfish catalog 可能遇到权限或可见性问题。

**10. 多数据库/多 Tenant 上下文**

Babelfish 支持多数据库，每个数据库有独立的配置：

```c
// 订阅端有多个 Babelfish 数据库
//   - mydb1 (SQL Server 模式)
//   - mydb2 (SQL Server 模式)
//   - postgres (PG 模式)

// DDL 执行时需要知道是哪个数据库
// 但 apply worker 是按订阅连接的
```text
**问题**：DDL SQL 中可能不包含数据库名，需要根据订阅配置确定目标数据库。

**11. 核心问题汇总**

| 问题类型 | 严重程度 | 说明 |
|---------|---------|------|
| `Is_TSQL_CLIENT()` 返回 false | **高** | 导致 ALTER VIEW 等 DDL 直接失败 |
| Hook 拦截导致 DDL 不执行 | **高** | 某些 DDL 被 hook 直接返回 |
| 方言切换影响 apply worker 内部操作 | **中** | 内部查询可能解析失败 |
| Search path 不一致 | **中** | Schema 解析到错误的对象 |
| 事务语义差异 | **中** | DDL 不会自动提交导致死锁 |
| 内存上下文问题 | **中** | 潜在内存泄漏或崩溃 |
| 多数据库上下文 | **中** | DDL 无法确定目标数据库 |

**12. 结论**

方案二在 apply worker PG 连接上下文中执行 Babelfish DDL 存在根本性的架构障碍：

1. **不是真正的 TDS 连接**：`Is_TSQL_CLIENT()` 等检查会失败
2. **Hook 执行路径不完整**：某些 DDL 被拦截或走不同路径
3. **全局状态污染**：方言切换影响整个 session

这些问题表明方案二不是一个可行的方案，方案三（独立 T-SQL 连接）反而能绕过这些限制。

---

### 方案三：订阅端新建一个 T-SQL 连接，连接本机执行 DDL SQL

#### 核心思路

订阅端 apply worker 在接收到 DDL 消息后，通过 libpq 建立起一个到本地 TDS 端口的连接，在这个 T-SQL 连接中执行 DDL SQL。

#### 技术实现

```text
订阅端 apply worker
         │
         │ 收到 DDL 消息
         │
         ▼
┌─────────────────────────┐
│  通过 libpq 连接         │
│  localhost:1433 (TDS)   │
└─────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│  在 T-SQL 连接中         │
│  执行 DDL SQL            │
└─────────────────────────┘
         │
         ▼
关闭 T-SQL 连接，返回结果
```text
**关键代码位置**：
- 修改 `src/backend/replication/logical/worker.c` 中的 `execute_publication_sync_sql_command()`
- 使用 libpq 建立 TDS 连接，执行 DDL 后关闭连接

**代码示例**：

```c
// worker.c execute_publication_sync_sql_command() 修改
static void
execute_publication_sync_sql_command(...)
{
    PGconn *tsql_conn;
    PGresult *res;

    // 建立 T-SQL 连接
    tsql_conn = PQconnectdb("host=localhost port=1433 dbname=... user=... password=...");

    if (PQstatus(tsql_conn) != CONNECTION_OK)
    {
        // 处理连接失败
        ereport(ERROR, ...);
    }

    // 执行 DDL
    res = PQexec(tsql_conn, ddl_sql);
    if (PQresultStatus(res) != PGRES_COMMAND_OK)
    {
        // 处理执行失败
        ereport(ERROR, ...);
    }

    PQclear(res);
    PQfinish(tsql_conn);
}
```text
**连接池优化**（避免每次 DDL 都建立新连接）：

```c
// 维护一个 T-SQL 连接池
static PGconn *tsql_connection_pool = NULL;

static PGconn* get_tsql_connection(void)
{
    if (tsql_connection_pool == NULL ||
        PQstatus(tsql_connection_pool) != CONNECTION_OK)
    {
        if (tsql_connection_pool)
            PQfinish(tsql_connection_pool);
        tsql_connection_pool = PQconnectdb("host=localhost port=1433 ...");
    }
    return tsql_connection_pool;
}
```text
#### 优点

1. **完全兼容 T-SQL**：使用原生 TDS 协议执行，绕过 Babelfish 在 PG 连接上的限制
2. **不受 apply worker 上下文限制**：所有 T-SQL DDL 都可以执行
3. **发布端完全不用改**：保持与原生 PG 逻辑复制完全兼容
4. **Babelfish 内部限制不影响**：如 `ALTER VIEW` 等在 PG 连接受限的操作可以正常执行

#### 缺点

1. **性能开销大**：每次执行 DDL 都需要建立/使用 T-SQL 连接，额外网络开销
2. **连接管理复杂**：需要维护长连接或连接池，增加复杂度
3. **安全风险**：需要配置 TDS 端口访问权限
4. **单点故障**：T-SQL 连接出问题会影响 DDL 同步
5. **额外资源消耗**：T-SQL 连接占用服务器资源

#### 支持的数据库模式

| 模式 | 支持情况 | 说明 |
|------|----------|------|
| SQL Server 模式 (Babelfish) | 完全支持 | 通过 TDS 端口执行所有 T-SQL DDL |
| PostgreSQL 模式 | 不适用 | PG 模式没有 TDS 端口，无法使用此方案 |
| 混合模式 | 仅 T-SQL 模式 | 只能用于 Babelfish 管理的数据库 |

#### 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| T-SQL 连接失败导致 DDL 同步中断 | 高 | 实现连接重试机制和连接池 |
| 性能开销影响复制延迟 | 中 | 使用连接池复用连接，减少连接建立开销 |
| TDS 端口安全配置 | 中 | 限制本地访问，配合认证机制 |
| 连接资源泄漏 | 中 | 严格管理连接生命周期，建立超时机制 |

#### 数据一致性分析

方案三通过建立独立的 T-SQL 连接执行 DDL，与 apply worker 的 PG 连接形成两个独立的执行上下文。这种架构在数据一致性方面面临以下挑战：

**1. 跨连接事务一致性问题**

```text
apply worker 执行流程：

┌─────────────────────────────────────────────────────────────────┐
│ 时间线                                                          │
│ ─────────────────────────────────────────────────────────────── │
│                                                                  │
│  T1: PG 连接 BEGIN (开启事务)                                   │
│  T2: PG 连接 执行 DML (INSERT/UPDATE/DELETE)                   │
│  T3: PG 连接 COMMIT                                             │
│                                                                  │
│  T4: T-SQL 连接 BEGIN (新事务)                                  │
│  T5: T-SQL 连接 执行 DDL (ALTER TABLE ...)                     │
│  T6: T-SQL 连接 COMMIT                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

问题：T2 和 T5 不在同一事务中，如果 T6 失败，T2 已经提交无法回滚
```text
**具体场景分析**：

| 场景 | 问题描述 | 影响 |
|------|----------|------|
| DDL 执行失败 | DML 已提交，DDL 失败回滚 | 发布端和订阅端结构不一致，后续 DML 可能报错 |
| DDL 执行超时 | DML 已提交，DDL 超时 | 同上 |
| 连接异常断开 | DML 已提交，DDL 未执行 | 需要人工干预 |

**2. DDL 与 DML 时序问题**

```text
发布端事务：
  BEGIN
    ALTER TABLE t1 ADD col_new INT;  -- 捕获到 pg_publication_sync
    INSERT INTO t1 (col_new) VALUES (1);  -- 普通 DML
  COMMIT

订阅端接收顺序：
  情况A：先收到 DDL 消息，再收到 DML 消息
    → T-SQL 连接执行 DDL
    → PG 连接执行 DML
    → 正常 ✓

  情况B：先收到 DML 消息，再收到 DDL 消息
    → PG 连接执行 DML (col_new 还不存在!)
    → DML 执行失败 ✗
```text
**3. 表结构变更与存量数据同步**

| 阶段 | 发布端状态 | 订阅端状态 | 一致性风险 |
|------|-----------|-----------|-----------|
| DDL 捕获后 | 新结构 | 旧结构 | DML 可能在新旧结构间不一致 |
| DDL 同步中 | 新结构 | 切换中 | 短暂不一致窗口 |
| DDL 执行后 | 新结构 | 新结构 | 恢复一致 |

**4. 连接会话状态差异**

T-SQL 连接和 PG 连接的 session 配置可能不同：

| 配置项 | PG 连接 (apply worker) | T-SQL 连接 | 差异影响 |
|--------|------------------------|------------|----------|
| `search_path` | 发布端捕获时保存 | 默认值 | DDL 执行的表引用可能解析到不同 schema |
| `sql_dialect` | PG | TSQL | 不影响执行 |
| `client_encoding` | 可能不同 | 可能不同 | 字符集转换问题 |
| 事务隔离级别 | 默认 READ COMMITTED | 默认 READ COMMITTED | 需保持一致 |

**5. 错误处理与恢复**

```text
DDL 执行失败时的处理流程：

┌─────────────────────────────────────────┐
│ DDL 在 T-SQL 连接执行失败                │
├─────────────────────────────────────────┤
│ 1. 记录错误到 apply worker 日志         │
│ 2. DDL 消息是否重试？                   │
│    ├─ 可重试 (网络闪断)：重试 N 次       │
│    └─ 不可重试 (语法错误)：暂停订阅      │
│ 3. 已执行的 DML 如何处理？              │
│    └─ 无法回滚，需人工介入              │
└─────────────────────────────────────────┘
```text
**6. 数据一致性保障措施**

针对上述问题，需要以下保障措施：

**a) DDL 执行时机控制**

```c
// 在 apply worker 中实现 DDL 屏障
typedef enum {
    DDL_BARRIER_WAIT,    // 等待前面的 DML 全部完成
    DDL_BARRIER_NONE     // 不等待，直接执行
} DDLBarrierMode;

// DDL 消息到达时
static void
apply_handle_ddl(...)
{
    // 确保没有正在进行的 DML 操作
    WaitForPendingDML();

    // 开启同步事务
    BeginSynchronizedTransaction();

    // 先执行 DDL
    execute_ddl_via_tsql_connection(ddl_sql);

    // 等待 DDL 在订阅端生效
    WaitForDDLReplication();

    // 提交同步事务
    CommitSynchronizedTransaction();
}
```text
**b) DDL 重试机制**

```c
typedef struct {
    int max_retries;           // 最大重试次数
    int retry_interval_ms;      // 重试间隔
    int total_timeout_ms;       // 总超时时间
} DDLRetryConfig;

static DDLRetryConfig default_ddl_retry_config = {
    .max_retries = 3,
    .retry_interval_ms = 1000,
    .total_timeout_ms = 30000,
};

// 带重试的 DDL 执行
static bool
execute_ddl_with_retry(const char *ddl_sql, DDLRetryConfig *config)
{
    for (int attempt = 0; attempt < config->max_retries; attempt++) {
        PGconn *tsql_conn = get_tsql_connection();

        if (PQsendQuery(tsql_conn, ddl_sql)) {
            // 同步等待结果
            PGresult *res = PQgetResult(tsql_conn);
            if (PQresultStatus(res) == PGRES_COMMAND_OK) {
                PQclear(res);
                return true;
            }
            PQclear(res);
        }

        // 检查是否是可重试的错误
        if (!is_retryable_error(PQerrorMessage(tsql_conn))) {
            return false;  // 不可重试的错误，直接返回
        }

        // 重试前等待
        pg_usleep(config->retry_interval_ms * 1000);
    }
    return false;
}
```text
**c) 订阅暂停与告警**

```c
// DDL 执行失败处理
static void
handle_ddl_failure(const char *ddl_sql, const char *error_msg)
{
    // 1. 记录详细错误信息
    ereport(ERROR,
        errmsg("DDL sync failed: %s", error_msg),
        errdetail("DDL: %s", ddl_sql));

    // 2. 暂停订阅
    subscription_sync_disable(subid);

    // 3. 发送告警
    send_alert(ALERT_LEVEL_HIGH, "DDL sync failure", ddl_sql, error_msg);

    // 4. 等待人工介入
    wait_for_manual_intervention();
}
```text
**d) 发布端事务顺序保证**

```text
发布端改造方案：

1. 在事务提交前，确保 DDL 已经写入 pg_publication_sync
2. DDL 和 DML 在同一个事务中捕获
3. 逻辑解码时保持事务顺序

具体实现：
- 在 CapturePublicationSyncDDL() 中检查是否在事务上下文中
- 如果 DDL 和 DML 在同一事务，确保它们一起被解码
- 订阅端按事务顺序应用
```text
**7. 一致性风险等级汇总**

| 一致性风险 | 发生概率 | 影响程度 | 风险等级 | 缓解措施 |
|-----------|---------|---------|---------|----------|
| DDL 失败导致 DML 已提交 | 低 | 高 | **中高** | DDL 屏障 + 事务顺序保证 |
| DML 先于 DDL 执行 | 中 | 高 | **高** | DDL 屏障机制 |
| 连接状态差异导致 DDL 语义不同 | 低 | 中 | **中** | 会话状态同步 |
| DDL 执行超时/中断 | 低 | 中 | **中** | 重试机制 + 订阅暂停 |
| 多表 DDL 部分成功 | 低 | 高 | **中高** | 分布式事务或人工干预 |

**8. 最佳实践建议**

1. **使用 `copy_data=false` 初始化订阅**：避免 initial data sync 和 DDL 同步交织
2. **DDL 同步单独建订阅**：表结构同步和数据同步分离，减少交叉干扰
3. **高峰期避免 DDL 操作**：减少对在线业务的影响
4. **建立 DDL 同步监控**：实时监控 DDL 执行状态，及时发现不一致
5. **准备回滚方案**：当 DDL 同步失败时，准备好订阅端手动执行 DDL 的方案

---

## 三种方案对比

### 综合对比表

| 评估维度 | 方案一 (发布端转换) | 方案二 (订阅端 T-SQL 解析) | 方案三 (T-SQL 连接) |
|----------|---------------------|---------------------------|---------------------|
| **实现复杂度** | 中 | 中 | 高 |
| **发布端改动** | 需要 | 不需要 | 不需要 |
| **订阅端改动** | 不需要 | 需要 | 需要 |
| **语义一致性** | 依赖转换质量 | 一致 | 一致 |
| **性能影响** | 小 | 小 | 中 |
| **Babelfish 限制** | 无影响 | 部分限制 | 无影响 |
| **维护成本** | 高 (转换规则) | 中 (版本适配) | 中 (连接管理) |
| **PG 原生兼容** | 完全兼容 | 部分破坏 | 完全兼容 |

### 场景适用性分析

#### 场景 1：仅使用 SQL Server 模式 (Babelfish)

**推荐方案：方案三 (T-SQL 连接)**

理由：
- 方案三可以处理所有 T-SQL DDL，不受 Babelfish 内部限制
- 发布端无需改动，保持与原生 PG 逻辑复制兼容
- 虽然有连接开销，但 DDL 执行频率远低于 DML，性能影响可接受

#### 场景 2：混合使用 SQL Server 模式和 PostgreSQL 模式

**推荐方案：方案一 (发布端转换) + 方案三 (T-SQL 连接) 组合**

实施策略：
- PostgreSQL 模式：使用原生 DDL 同步逻辑（无需转换）
- SQL Server 模式：根据 DDL 类型选择：
  - 可转换的 DDL：方案一（发布端转换）
  - 不可转换的 DDL：方案三（T-SQL 连接）

#### 场景 3：对性能要求高，DDL 同步频率低

**推荐方案：方案一 (发布端转换)**

理由：
- DDL 执行频率低，语义差异风险大于性能影响
- 转换规则可测试、可控
- 订阅端实现简单，出了问题容易排查

#### 场景 4：需要支持所有 T-SQL DDL，包括视图、触发器等

**推荐方案：方案三 (T-SQL 连接)**

理由：
- 方案二需要初始化bbf上下文，并且需要bbf内部提供hook
- 方案三使用原生 TDS 协议，无额外限制
- 只要 Babelfish TDS 端口能执行的 DDL，都可以同步

### 决策矩阵

```text
                    ┌─────────────────────────────────────────────────────┐
                    │              场景特征                                │
                    ├─────────────┬─────────────┬─────────────┬───────────┤
                    │ 仅 Babelfish│   混合模式   │  追求性能   │ 完整支持  │
                    │    模式     │             │             │  所有DDL  │
─────┬──────────────┼─────────────┼─────────────┼─────────────┼───────────┤
     │  方案一      │    △        │     ○       │     ◎       │     ✗     │
     │ (发布端转换) │             │   (组合)    │             │           │
方案 ├──────────────┼─────────────┼─────────────┼─────────────┼───────────┤
选择 │  方案二      │    △        │     △       │     ○       │     △     │
     │ (T-SQL解析) │             │             │             │           │
     ├──────────────┼─────────────┼─────────────┼─────────────┼───────────┤
     │  方案三      │    ◎        │     ○       │     △       │     ◎     │
     │ (T-SQL连接) │             │   (仅BBF)   │             │           │
     └──────────────┴─────────────┴─────────────┴─────────────┴───────────┘

图例：◎ 推荐  ○ 可用  △ 勉强可用  ✗ 不适用
```text
---

## 多数据库模式支持分析

### 模式识别与路由

在混合模式环境下，需要在 DDL 捕获时判断 DDL 来源，并在订阅端选择合适的执行策略。

#### 模式识别机制

```c
typedef enum {
    DB_MODE_PG,        // PostgreSQL 模式
    DB_MODE_TSQL,      // SQL Server 模式 (Babelfish)
    DB_MODE_UNKNOWN    // 未知模式
} DatabaseMode;

// 在捕获时判断模式
static DatabaseMode
get_ddl_source_mode(const char *sql)
{
    // 检查 sql_dialect GUC
    const char *dialect = get_config_option("babelfishpg_tsql.sql_dialect", true, true);
    if (dialect && strcmp(dialect, "tsql") == 0)
        return DB_MODE_TSQL;
    return DB_MODE_PG;
}
```text
#### 订阅端执行路由

```c
static void
execute_publication_sync_sql_command(const char *ddl_sql, DatabaseMode mode)
{
    switch (mode) {
        case DB_MODE_PG:
            // 直接执行，PG 模式无需转换
            pg_parse_query(ddl_sql);
            break;

        case DB_MODE_TSQL:
            // 方案三：使用 T-SQL 连接执行
            execute_via_tsql_connection(ddl_sql);
            break;

        default:
            ereport(ERROR, "Unknown database mode");
    }
}
```text
### 多模式支持矩阵

| 功能 | PG 模式 | SQL Server 模式 | 混合模式 |
|------|---------|-----------------|----------|
| DDL 捕获 | 原生支持 | 原生支持 | 原生支持 |
| DDL 存储 | 原生格式 | 原生格式 | 原生格式 |
| DDL 发送到订阅端 | 原生协议 | 原生协议 | 原生协议 |
| **订阅端 DDL 执行** | | | |
| ├─ 方案一 (转换) | N/A | 部分支持 | 部分支持 |
| ├─ 方案二 (T-SQL解析) | 不支持 | 部分支持 | 部分支持 |
| └─ 方案三 (T-SQL连接) | 不适用 | 完全支持 | 仅BBF部分 |

---

## 推荐方案

### 短期方案：方案三 (T-SQL 连接)

理由：
1. **实现相对简单**：不需要理解复杂的 T-SQL 到 PG 的转换规则
2. **覆盖度最广**：不受 Babelfish 内部限制
3. **发布端不改**：保持与原生 PG 逻辑复制兼容
4. **风险可控**：T-SQL 连接可以独立管理，出问题不影响 DML 同步

### 长期方案：方案一 + 方案三 组合

理由：
1. **性能优化**：频繁执行的简单 DDL（表创建、列增删）使用方案一
2. **完整性保障**：复杂 DDL 或方案一无法转换的使用方案三
3. **可演进**：随着 Babelfish 能力提升，方案一覆盖度会增加

### 不推荐方案二

理由：
1. **Babelfish 内部限制**：部分 DDL（如 ALTER VIEW）在 PG 连接上下文无法执行
2. **版本耦合**：与 Babelfish 实现细节强耦合
3. **维护困难**：一旦 Babelfish 内部实现变化，需要同步修改

---

## 实施建议

### 第一阶段：基础能力

1. 实现方案三（T-SQL 连接）作为基础
2. 支持基本的表 DDL 同步（CREATE/ALTER/DROP TABLE）
3. 建立 DDL 同步监控和告警

### 第二阶段：能力扩展

1. 实现方案一（发布端转换）处理简单可转换的 DDL
2. 建立 DDL 转换规则库
3. 对不可转换的 DDL 使用方案三

### 第三阶段：优化完善

1. 实现连接池优化，减少 T-SQL 连接开销
2. 建立 DDL 同步质量检测
3. 支持更多 DDL 类型

---

## 附录

### 架构对比图

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           方案一：发布端转换                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   发布端                           订阅端                                    │
│   ┌─────────┐                      ┌─────────┐                              │
│   │ TDS端口  │                      │ PG端口   │                              │
│   │(SQL执行) │                      │(应用DDL) │                              │
│   └────┬────┘                      └────┬────┘                              │
│        │                                │                                   │
│        ▼                                │                                   │
│   ┌─────────────┐                       │                                   │
│   │ 捕获DDL     │                       │                                   │
│   │(T-SQL语法)  │                       │                                   │
│   └──────┬──────┘                       │                                   │
│          │                              │                                   │
│          ▼                              │                                   │
│   ┌─────────────┐                       │                                   │
│   │ T-SQL → PG  │ ─────────────────────►│ 直接执行 PG SQL                   │
│   │ 转换层      │   (转换后PG语法)       │                                   │
│   └─────────────┘                       │                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           方案二：订阅端T-SQL解析                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   发布端                           订阅端                                    │
│   ┌─────────┐                      ┌─────────┐                              │
│   │ TDS端口  │                      │ PG端口   │                              │
│   │(SQL执行) │                      │(应用DDL) │                              │
│   └────┬────┘                      └────┬────┘                              │
│        │                                │                                   │
│        ▼                                │                                   │
│   ┌─────────────┐                       │                                   │
│   │ 捕获DDL     │                       │                                   │
│   │(T-SQL语法)  │                       │                                   │
│   └──────┬──────┘                       │                                   │
│          │                              │                                   │
│          │  原样发送 T-SQL DDL          │                                   │
│          │ ───────────────────────────►│                                   │
│          │                              ▼                                   │
│          │                     ┌─────────────────┐                          │
│          │                     │ 设置 dialect=TSQL │                        │
│          │                     └────────┬────────┘                          │
│          │                              │                                   │
│          │                              ▼                                   │
│          │                     ┌─────────────────┐                          │
│          │                     │ T-SQL 解析器    │                          │
│          │                     │ 解析 DDL        │                          │
│          │                     └────────┬────────┘                          │
│          │                              │                                   │
│          │                              ▼                                   │
│          │                     ┌─────────────────┐                          │
│          │                     │ 执行 DDL        │                          │
│          │                     │ (仍有BBF限制)   │                          │
│          │                     └─────────────────┘                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           方案三：订阅端T-SQL连接                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   发布端                           订阅端                                    │
│   ┌─────────┐                      ┌─────────┐     ┌─────────┐              │
│   │ TDS端口  │                      │ PG端口   │     │ TDS端口  │              │
│   │(SQL执行) │                      │(应用DDL) │     │(执行DDL) │              │
│   └────┬────┘                      └────┬────┘     └────┬────┘              │
│        │                                │              │                    │
│        ▼                                │              │                    │
│   ┌─────────────┐                       │              │                    │
│   │ 捕获DDL     │                       │              │                    │
│   │(T-SQL语法)  │                       │              │                    │
│   └──────┬──────┘                       │              │                    │
│          │                              │              │                    │
│          │  原样发送 T-SQL DDL          │              │                    │
│          │ ───────────────────────────►│              │                    │
│          │                              ▼              │                    │
│          │                     ┌─────────────────┐     │                    │
│          │                     │ 建立T-SQL连接   │◄────┘                    │
│          │                     │ (localhost:1433)│                          │
│          │                     └────────┬────────┘                          │
│          │                              │                                   │
│          │                              ▼                                   │
│          │                     ┌─────────────────┐                          │
│          │                     │ 通过TDS协议     │                          │
│          │                     │ 执行DDL(无限制) │                          │
│          │                     └─────────────────┘                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```text
### 关键代码文件索引

| 组件 | 文件路径 | 说明 |
|------|----------|------|
| DDL 捕获 | `postgresql-3/src/backend/tcop/utility.c` | `CapturePublicationSyncDDL()` |
| DDL 存储 | `postgresql-3/src/include/catalog/pg_publication_sync.h` | `pg_publication_sync` 表定义 |
| pgoutput 插件 | `postgresql-3/src/backend/replication/pgoutput/pgoutput.c` | DDL 消息发送 |
| Apply worker | `postgresql-3/src/backend/replication/logical/worker.c` | DDL 消息接收与执行 |
| 协议消息 | `postgresql-3/src/backend/replication/logical/proto.c` | `logicalrep_write_ddl()` |
| Babelfish Hook | `babelfish_extensions/contrib/babelfishpg_tsql/src/hooks.c` | `pltsql_bbfCustomProcessUtility()` |
| 方言切换 | `babelfish_extensions/contrib/babelfishpg_tsql/src/pl_handler.c` | `bbf_ProcessUtility()` |

### 相关文档

- [逻辑复制同步 DDL 适配 Babelfish 面临的挑战](./逻辑复制同步ddl适配bbf面临的挑战.md)
- [Babelfish DDL 已知限制](./babelfish ddl已知限制.md)
- [SQL Server 模式逻辑复制支持 DDL](./sqlserver模式逻辑复制支持ddl.md)