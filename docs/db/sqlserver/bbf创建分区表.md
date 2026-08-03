# 逻辑复制适配sqlserver模式分区表问题分析

问题原因：逻辑复制同步DDL在sqlserver模式下不支持分区表同步，根本原因为分区表创建依赖于Partition Function 、Partition Scheme，但这两个语句不走PG标准的执行流程（ProcessUtility），无法被捕获。

解决方案：需要对分区表的ddl语句进行特殊处理和适配。

## sqlserver创建分区表的流程

1. 创建 Partition Function
2. 创建 Partition Scheme
3. 创建分区表

### 1. 创建 Partition Function

```sql
CREATE PARTITION FUNCTION pf_range(INT)
AS RANGE LEFT FOR VALUES (100, 200, 300);
```text
- `RANGE LEFT`：边界值归属左侧分区
- `RANGE RIGHT`：边界值归属右侧分区
- 定义的是**逻辑分区规则**，不涉及存储

### 2. 创建 Partition Scheme

```sql
CREATE PARTITION SCHEME ps_range
AS PARTITION pf_range ALL TO ([PRIMARY]);
```text
- 将 Partition Function 映射到具体的文件组（filegroup）
- `ALL TO ([PRIMARY])` 表示所有分区都在同一个文件组
- 也可以指定不同的文件组实现物理隔离

### 3. 创建分区表

```sql
CREATE TABLE dbo.orders (
    order_id INT NOT NULL,
    order_date DATE NOT NULL,
    amount DECIMAL(10, 2)
) ON ps_range(order_id);
```text
- `ON ps_range(order_id)` 指定分区方案和分区键
- 表的物理存储由 Partition Scheme 决定

## SQL Server 与 PostgreSQL 分区表对比

| 维度 | SQL Server | PostgreSQL |
|------|-----------|------------|
| 分区定义方式 | Partition Function + Partition Scheme + 表 ON scheme | 声明式分区（PARTITION BY） |
| 分区函数 | 独立的数据库对象 | 无独立对象，内嵌在表定义中 |
| 分区方案 | 独立的数据库对象，映射到 filegroup | 无独立对象，分区直接绑定到表 |
| 分区键 | 在表定义时通过 `ON scheme(key)` 指定 | 在 `CREATE TABLE` 时通过 `PARTITION BY RANGE/LIST/HASH(key)` 指定 |
| 分区维护 | `ALTER TABLE ... ADD/DROP/SPLIT/MERGE PARTITION` | `CREATE TABLE ... PARTITION OF` / `ALTER TABLE ... DETACH PARTITION` |
| 存储映射 | filegroup | tablespace |

### SQL Server 分区模型

```text
Partition Function (逻辑规则)
    ↓
Partition Scheme (映射到 filegroup)
    ↓
Table ON scheme(key) (物理表)
```text
### PostgreSQL 分区模型

```text
Parent Table PARTITION BY RANGE/LIST/HASH (key)
    ↓
Child Table PARTITION OF parent FOR VALUES FROM ... TO ...
```text
## babelfish插件如何创建分区表

Babelfish 对 SQL Server 分区语法的支持通过**三层架构**实现：

### 第一层：ANTLR 语法解析（`TSqlParser.g4`）

T-SQL 的分区语法在 ANTLR 语法文件中定义为独立的语法规则：

```text
create_partition_function
    : CREATE PARTITION FUNCTION name(data_type) AS RANGE (LEFT|RIGHT) FOR VALUES(expr_list)

create_partition_scheme
    : CREATE PARTITION SCHEME name AS PARTITION func_name ALL? TO(filegroup_list)

drop_partition_function  /  drop_partition_scheme
alter_partition_function /  alter_partition_scheme
```text
这些规则在 `ddl_statement` 中注册，是 T-SQL 特有的语法，**不对应 PostgreSQL 的任何标准 DDL 节点类型**。

### 第二层：AST 构建（`tsqlIface.cpp`）

ANTLR 解析后，`tsqlIface.cpp` 将这些语法节点转换为 Babelfish 自定义的语句类型：

```cpp
// tsqlIface.cpp:2183-2197
if (ctx->create_partition_function())
    stmt = makeCreatePartitionFunction(ctx->create_partition_function());
else if (ctx->create_partition_scheme())
    stmt = makeCreatePartitionScheme(ctx->create_partition_scheme());
```text
这些语句的类型是 `PLTSQL_STMT_PARTITION_FUNCTION` 和 `PLTSQL_STMT_PARTITION_SCHEME`（定义在 `pltsql.h:210-211`），**不是 PostgreSQL 标准的 `PlannedStmt` 节点**。

关键细节：在 `exitDdl_statement()` 中（`tsqlIface.cpp:2228-2232`），分区函数/方案被特殊处理：

```cpp
if (ctx->create_partition_function() || ctx->drop_partition_function()
     || ctx->create_partition_scheme() || ctx->drop_partition_scheme())
{
    return;  // 不设置 stmt->is_ddl = true，提前返回
}
```text
这意味着它们不会被标记为 DDL，也不会走标准的 DDL 处理路径。

### 第三层：PL/TSQL 执行器（`iterative_exec.c` → `pl_exec-2.c`）

语句被交给 PL/TSQL 执行器执行，而非 `ProcessUtility()`：

```c
// iterative_exec.c:830-847
case PLTSQL_STMT_PARTITION_FUNCTION:
    exec_stmt_partition_function(estate, (PLtsql_stmt_partition_function *) stmt);
    break;
case PLTSQL_STMT_PARTITION_SCHEME:
    exec_stmt_partition_scheme(estate, (PLtsql_stmt_partition_scheme *) stmt);
    break;
```text
#### CREATE PARTITION FUNCTION 执行流程（`pl_exec-2.c:4349`）

1. 检查用户权限（`check_create_or_drop_permission_for_partition_specifier`）
2. 验证分区函数名不重复（`partition_function_exists`）
3. 解析数据类型、排序规则
4. 将边界值转换为 `sql_variant` 数组
5. **写入系统表 `sys.babelfish_partition_function`**（`add_entry_to_bbf_partition_function`）

#### CREATE PARTITION SCHEME 执行流程（`pl_exec-2.c:4626`）

1. 检查分区方案名不重复
2. 验证关联的 Partition Function 存在
3. **写入系统表 `sys.babelfish_partition_scheme`**（`add_entry_to_bbf_partition_scheme`）

#### 创建分区表时的实际分区构建（`pltsql_partition.c`）

当执行 `CREATE TABLE ... ON scheme(key)` 时，Babelfish 调用 `bbf_create_partition_tables()` 函数：

```text
CREATE TABLE ... ON scheme(key)
    → bbf_ProcessUtility() 识别到 CREATE TABLE 带 partitionspec
        → bbf_create_partition_tables(stmt)
            → 从 sys.babelfish_partition_function 读取分区元数据
            → 从 sys.babelfish_partition_scheme 读取映射关系
            → 临时切换 sql_dialect = 'postgres'
            → 构造 PG 的 "CREATE TABLE ... PARTITION OF ..." 语句
            → standard_ProcessUtility() 执行
            → 循环创建每个分区（分区名: {hash}_partition_N）
            → 写入 sys.babelfish_partition_depend 跟踪依赖
```text
关键实现细节：
- 分区名自动生成：基于表名的 MD5 hash + 分区序号（`{hash}_partition_0`, `{hash}_partition_1`, ...）
- 第一个分区使用 `DEFAULT` 边界容纳 NULL 值
- 最后一个分区使用 `MAXVALUE` 作为上界
- 数据类型验证：分区列类型必须与 Partition Function 定义的参数类型一致

### 当前支持情况汇总

| 语法 | 支持情况 | 说明 |
|------|---------|------|
| `CREATE PARTITION FUNCTION` | 支持 | 元数据存储在 `sys.babelfish_partition_function` |
| `CREATE PARTITION SCHEME` | 支持 | 元数据存储在 `sys.babelfish_partition_scheme` |
| `DROP PARTITION FUNCTION` | 支持 | 需要无依赖（无关联的 scheme）才能删除 |
| `DROP PARTITION SCHEME` | 支持 | 需要无依赖（无关联的表）才能删除 |
| `CREATE TABLE ... ON scheme(key)` | 支持 | 自动创建 PG 分区表，分区名自动生成 |
| `ALTER TABLE ... SPLIT PARTITION` | 不支持 | PG 无直接等价操作，需 DETACH + 重建 |
| `ALTER TABLE ... MERGE PARTITION` | 不支持 | PG 无直接等价操作 |
| 直接重命名/修改分区 | 限制 | 非超级用户禁止直接操作子分区 |

## ddl捕获分区表

### 能捕获的内容

- **创建分区表的语句**：`CREATE TABLE ... ON scheme(key)` 可以被 DDL 捕获框架识别
  - 捕获到的是经过 Babelfish 转换后的 PG 语法树（带 `partspec` 的 `CreateStmt`）
  - 分区规则信息存在于 `partspec` 节点中
- **分区表的 ALTER TABLE ADD/DROP COLUMN** 等普通结构变更

### 无法捕获的内容

- **Partition Function**：`CREATE PARTITION FUNCTION` 无法被捕获
- **Partition Scheme**：`CREATE PARTITION SCHEME` 无法被捕获

### 为什么 Partition Function 和 Partition Scheme 无法捕获

**根本原因：分区函数和分区 scheme 完全不走 `ProcessUtility()` 执行路径。**

#### 详细分析

PostgreSQL 的 DDL 捕获机制依赖 `ProcessUtility_hook`：

```text
标准 DDL 执行流程：
  ANTLR 解析 → 转换为 PG PlannedStmt
    → ProcessUtility()
      → CapturePublicationSyncDDL()   ← DDL 捕获点
      → bbf_ProcessUtility()           ← Babelfish hook
      → standard_ProcessUtility()      ← 实际执行
```text
但 Partition Function 和 Partition Scheme 走的是完全不同的路径：

```text
CREATE PARTITION FUNCTION/Scheme 执行流程：
  ANTLR 解析 (TSqlParser.g4)
    → tsqlIface.cpp 转换为 PLTSQL_STMT_PARTITION_*
      → PL/TSQL 执行器 (iterative_exec.c)
        → exec_stmt_partition_function/scheme (pl_exec-2.c)
          → 直接写入系统表 (catalog.c)
            ← 全程不经过 ProcessUtility()
```text
**关键代码**：

1. **`tsqlIface.cpp:2228-2232`** — `exitDdl_statement()` 对分区语句提前返回，不设置 `is_ddl` 标记：
   ```cpp
   if (ctx->create_partition_function() || ctx->drop_partition_function()
        || ctx->create_partition_scheme() || ctx->drop_partition_scheme())
   {
       return;  // 不设置 stmt->is_ddl，后续流程不会将其作为 DDL 处理
   }
   ```

2. **`pltsql.h:210-211`** — 语句类型为独立的 `PLTSQL_STMT_PARTITION_FUNCTION` 和 `PLTSQL_STMT_PARTITION_SCHEME`，不属于 PG 标准的 `T_CreateStmt` 等节点类型。

3. **`iterative_exec.c:830-847`** — 由 PL/TSQL 执行器直接调用 `exec_stmt_partition_function/scheme`，不经过 `ProcessUtility()`。

4. **`pl_exec-2.c`** — `exec_stmt_partition_function()` 直接操作目录表（`add_entry_to_bbf_partition_function`），不生成 `PlannedStmt`。

#### 影响

1. **发布端创建了完整的分区表结构，但订阅端只收到表创建语句，没有分区规则**
2. 订阅端的表变成普通表，而非分区表
3. 后续的分区维护操作也无法同步

### DDL 同步对分区表的适用性

| 操作 | 能否捕获 | 能否同步 | 备注 |
|------|---------|---------|------|
| `CREATE PARTITION FUNCTION` | 不能 | 不能 | PL/TSQL 执行器直接写目录，不经过 ProcessUtility |
| `CREATE PARTITION SCHEME` | 不能 | 不能 | 同上 |
| `DROP PARTITION FUNCTION` | 不能 | 不能 | 同上 |
| `DROP PARTITION SCHEME` | 不能 | 不能 | 同上 |
| `CREATE TABLE ... ON scheme(key)` | 能 | 部分 | 捕获到建表语句，但分区规则依赖 Function/Scheme 元数据 |
| `ALTER TABLE ... ADD/DROP COLUMN` | 能 | 能 | 普通 DDL，正常捕获 |
| `ALTER TABLE ... SPLIT/MERGE PARTITION` | 不适用 | 不支持 | Babelfish 不支持此语法 |

## 结论

### 问题原因

逻辑复制同步DDL在sqlserver模式下不支持分区表同步，根本原因为分区表创建依赖于Partition Function 、Partition Scheme，但这两个语句不走PG标准的执行流程（ProcessUtility），无法被捕获。

### 解决方案

需要对分区表的ddl语句进行特殊处理和适配。

