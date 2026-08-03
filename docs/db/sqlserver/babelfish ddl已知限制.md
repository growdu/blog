# Babelfish DDL 同步已知限制与客户使用建议

本文档汇总 Babelfish 插件在 SQL Server 模式下使用逻辑复制 DDL 自动同步时的已知限制，并按客户使用影响给出分级和建议做法。

这些限制主要来自 Babelfish 对 T-SQL DDL 的解析、重写和执行路径约束，不是普通逻辑复制链路本身的问题。客户仍然可以使用 DDL 同步，但需要避开下列不适配场景，或对部分对象采用手动维护。

---

## 影响程度分级

| 影响程度 | 含义 | 客户侧处理原则 |
|----------|------|----------------|
| 高 | 客户高频场景且使用复杂，或者可能导致订阅端 apply worker 报错、反复重启，后续 DDL 无法继续回放 | 禁止在 DDL 同步链路中使用；如已触发，需要先恢复订阅端 apply 状态，再采用规避写法。初期手动执行，后续持续优化完善 |
| 中 | 不会破坏整条复制链路，但该类对象或操作不能自动同步，发布端和订阅端可能出现结构差异 | 可以继续使用 DDL 同步，但该类对象需要在订阅端手动创建或手动变更 |
| 低 | 主要是语法写法约束或初始化流程约束，按推荐方式使用后不影响后续同步 | 按规范写法或初始化流程执行即可 |

---

## 总体使用建议

客户在 Babelfish SQL Server 模式下使用 DDL 同步时，建议遵循以下原则：

1. DDL 同步适合用于表、列、约束、普通索引等 Babelfish 已稳定支持的 T-SQL DDL。
2. 订阅创建时使用 `copy_data=false`，历史数据由客户自行导入，逻辑复制只负责后续增量 DML 和可支持 DDL。
3. 不要把 PostgreSQL 专有语法混入 SQL Server 模式 DDL 同步链路，例如 `ALTER TABLE ... REPLICA IDENTITY`。
4. 对视图、物化视图、触发器、索引维护类操作，应建立明确的人工变更流程，确保发布端和订阅端对象一致。
5. 对存在高影响风险的 DDL，应在测试环境验证后再进入生产变更窗口。

推荐的客户使用流程：

```
1. 在订阅端预建基础对象，或确认基础对象可由 DDL 同步创建。
2. 创建订阅时指定 copy_data=false。
3. 手动导入发布端已有历史数据。
4. 启动订阅，开始同步后续 DML。
5. 后续 DDL 只执行本文档允许的写法。
6. 对不支持自动同步的对象，在发布端和订阅端按同一变更单分别执行。
```
---

## 1. 物化视图不支持自动同步

**影响程度**：中。

**限制描述**：在 T-SQL 方言下，`SELECT INTO` / `CREATE MATERIALIZED VIEW` 的执行会经过 Babelfish 的 `bbf_select_into_utility_hook`。该 hook 调用 `transformSelectIntoStmt` 时会检查源表的 `NOT NULL` 列并生成 `ALTER TABLE SET NOT NULL` 命令。但 PostgreSQL 内核不允许对物化视图执行 `ALTER COLUMN SET NOT NULL`，导致订阅端 apply worker 执行失败。

**触发场景**：

- 发布端在 SQL Server 模式下创建物化视图。
- DDL 同步尝试在订阅端回放该物化视图 DDL。

**对客户的影响**：

- 物化视图不能依赖 DDL 同步自动创建。
- 发布端和订阅端的物化视图定义、刷新策略可能不一致。
- 不影响普通表 DDL 和 DML 的同步，只影响物化视图对象本身。

**客户应该如何使用 DDL 同步**：

- DDL 同步继续用于普通表结构变更。
- 物化视图不纳入自动 DDL 同步范围。
- 客户如需要订阅端也存在同名物化视图，应在订阅端手动创建。
- 物化视图刷新策略也需要由客户在订阅端单独维护。

**规避方案**：

- SQL Server 模式下不捕获或不同步物化视图相关 DDL。
- 将物化视图创建动作纳入发布端、订阅端双端人工变更流程。

---

## 2. VIEW 相关 DDL 不支持自动同步

**影响程度**：中。

**限制描述**：Babelfish 重写了 `ViewStmt` 的处理逻辑，内部通过先 `DROP` 再 `CREATE` 来模拟 `ALTER VIEW`。该路径仅在 TDS 连接或标记了 T-SQL 会话的 PG 连接下可用。逻辑复制 apply worker 既不是 TDS 客户端，也不是 PG-T-SQL 标记连接，因此如果直接在订阅端回放 `ALTER VIEW`，`Is_TSQL_CLIENT()` 会返回 false，并触发防护性报错：

```
ERROR: TSQL ALTER VIEW is not supported from PostgreSQL endpoint.
```
当前 DDL 同步实现已经对 view 相关 DDL 做了限制：SQL Server 模式下不自动同步 `CREATE VIEW`、`ALTER VIEW`、`DROP VIEW` 等 view 相关 DDL，因此这类语句不会进入订阅端自动回放链路。

**触发场景**：

- 发布端执行 `CREATE VIEW`、`ALTER VIEW`、`DROP VIEW` 等 view 相关 DDL。
- DDL 同步实现识别到 view 相关 DDL 后不进行自动同步。

**对客户的影响**：

- view 的创建、修改、删除都不会自动同步到订阅端。
- 订阅端 view 定义可能与发布端不一致，需要客户手动维护。
- 由于实现层已限制同步该类 DDL，正常情况下不会因为 view 相关 DDL 阻塞后续 DDL 回放。

**客户应该如何使用 DDL 同步**：

- DDL 同步继续用于普通表结构变更。
- view 相关 DDL 不依赖自动同步。
- `CREATE VIEW`、`ALTER VIEW`、`DROP VIEW` 均需要客户在订阅端手动执行。
- 建议 view 类对象不纳入自动 DDL 同步范围，由客户在发布端和订阅端按同一脚本分别执行。

**人工同步示例**：

```sql
-- 发布端和订阅端分别执行
DROP VIEW dbo.v1;
CREATE VIEW dbo.v1 AS
SELECT ...
```
**规避方案**：

- SQL Server 模式下已限制捕获或同步 view 相关 DDL。
- 客户在订阅端手动创建、修改或删除 view。
- 将视图创建、修改、删除纳入发布端、订阅端双端人工变更流程。

---

## 3. CREATE TRIGGER 不支持自动同步

**影响程度**：中。

**限制描述**：T-SQL 的 `CREATE TRIGGER` 在 Babelfish 语法解析时生成的是 `CreateFunctionStmt` 节点，而不是标准 PostgreSQL 的 `CreateTrigStmt` 节点。因此 DDL 捕获逻辑无法按标准 trigger 节点匹配该语句。此外，即使匹配到，`CreateFunctionStmt` 也会被 Babelfish 的 `bbf_custom_process_utility_hook` 直接返回，无法进入 DDL 捕获逻辑。

**触发场景**：

- 发布端在 SQL Server 模式下执行 `CREATE TRIGGER`。

**对客户的影响**：

- 触发器不会自动同步到订阅端。
- 如果业务依赖订阅端触发器执行审计、校验、派生数据写入等逻辑，订阅端行为会与发布端不同。
- 不影响普通表 DDL 和 DML 的同步。

**客户应该如何使用 DDL 同步**：

- DDL 同步继续用于触发器依赖的基础表结构。
- 触发器本身由客户在订阅端手动创建。
- 如果触发器会影响复制写入的数据，需评估是否应在订阅端启用，避免重复写入或与复制数据冲突。

**规避方案**：

- SQL Server 模式下不捕获 trigger 相关 DDL。
- 将触发器创建、修改、删除纳入双端人工变更流程。

---

## 4. ALTER INDEX 不支持

**影响程度**：中。

**限制描述**：Babelfish 当前不支持 T-SQL `ALTER INDEX` 语句，需要等待 Babelfish 上游适配支持。

**触发场景**：

- 发布端执行 `ALTER INDEX ... REBUILD`、`ALTER INDEX ... REORGANIZE` 或其他索引维护类语句。

**对客户的影响**：

- 索引维护操作不会自动同步到订阅端。
- 发布端和订阅端的索引维护状态可能不同。
- 通常不影响数据正确性，但可能造成订阅端查询性能、索引膨胀、维护状态与发布端不一致。

**客户应该如何使用 DDL 同步**：

- 表结构和普通索引创建可继续按支持范围使用 DDL 同步。
- 索引维护类操作不要依赖 DDL 同步。
- 如订阅端也需要执行同样维护，应在订阅端手动执行等价操作。

**规避方案**：

- 禁止将 `ALTER INDEX` 放入自动 DDL 同步链路。
- 对生产环境索引维护建立发布端、订阅端分别执行的维护计划。

---

## 5. ALTER TABLE ADD 多列语法不支持

**影响程度**：低。

**限制描述**：Babelfish T-SQL 解析器不支持单条 `ALTER TABLE ... ADD` 同时添加多列的语法，例如：

```sql
ALTER TABLE t1 ADD col1 INT, col2 VARCHAR(50);
```
该写法可能报语法错误，例如 `syntax error at or near "col2"`。

**触发场景**：

- 发布端使用单条 `ALTER TABLE ... ADD` 添加多个列。

**对客户的影响**：

- 该 DDL 在发布端或订阅端可能执行失败。
- 按推荐写法拆分后，表结构可以正常同步。
- 不影响 DML 同步。

**客户应该如何使用 DDL 同步**：

- 添加多列时，拆分为多条单列 `ADD` 语句。
- 每条语句成功执行后，DDL 同步可以正常回放。

**推荐写法**：

```sql
ALTER TABLE t1 ADD col1 INT;
ALTER TABLE t1 ADD col2 VARCHAR(50);
ALTER TABLE t1 ADD col3 BIT;
```
**规避方案**：

- 变更脚本生成工具应将多列 `ADD` 自动拆分为多条单列语句。
- 客户上线前检查 DDL 脚本，避免单条多列 `ADD`。

---

## 6. ALTER TABLE REPLICA IDENTITY 不支持

**影响程度**：高。

**限制描述**：`ALTER TABLE ... REPLICA IDENTITY` 是 PostgreSQL 专有语法，用于控制逻辑复制中旧值的传输策略。T-SQL / Babelfish 不支持该语法。发布端如果通过 PG 端口执行该语句，DDL 同步机制可能捕获并发送到订阅端，但订阅端 apply worker 在 T-SQL 兼容模式下无法解析或执行。

**触发场景**：

- 客户通过 PG 端口对 SQL Server 模式对象执行 `ALTER TABLE ... REPLICA IDENTITY`。
- 该语句被 DDL 同步捕获并在订阅端回放。

**对客户的影响**：

- 订阅端 DDL 回放可能失败。
- 后续 DDL 同步可能被阻塞。
- 该语法属于 PostgreSQL 语义，与 T-SQL 客户业务 DDL 无关。

**客户应该如何使用 DDL 同步**：

- SQL Server 模式下不要使用 `REPLICA IDENTITY` 语法。
- 客户如需配置逻辑复制旧值策略，应由 DBA 在 PostgreSQL 管理侧单独评估，不应作为 SQL Server 模式业务 DDL 自动同步。
- DDL 同步链路只同步 T-SQL 业务 DDL，不混入 PostgreSQL 专有 DDL。

**规避方案**：

- SQL Server 模式 DDL 捕获时排除 `REPLICA IDENTITY`。
- 客户变更规范中明确禁止通过 PG 端口对 Babelfish 业务对象提交该类 DDL。

---

## 7. copy_data=true 不支持

**影响程度**：高。

**限制描述**：在 T-SQL / SQL Server 模式下创建逻辑复制订阅时，`copy_data=true` 选项不可用。订阅表的 initial data sync 会持续失败，日志可能循环报错：

```
ERROR: table copy could not start transaction on publisher:
ERROR: syntax error at or near "READ" at character 7
STATEMENT: BEGIN READ ONLY ISOLATION LEVEL REPEATABLE READ
```
**原因**：`copy_data=true` 会触发 table sync worker 通过 libpq 向发布端发送：

```sql
BEGIN READ ONLY ISOLATION LEVEL REPEATABLE READ
```
由于 `sql-dialect='tsql'` 是全局配置，libpq 复制连接也会走 T-SQL 语法解析路径，而 T-SQL 的 `BEGIN` 语法不支持 `READ ONLY` / `ISOLATION LEVEL` 修饰符，导致 initial data sync 失败。

**触发场景**：

- 创建订阅时使用默认 `copy_data=true`。
- 或显式指定 `WITH (copy_data = true)`。

**对客户的影响**：

- 无法自动拷贝发布端已有历史数据。
- 订阅初始化阶段可能失败。
- 使用 `copy_data=false` 后，不影响后续增量 DML 和可支持 DDL 同步。

**修复方案**：

- **修改文件**：`src/backend/replication/libpqwalreceiver/libpqwalreceiver.c`
- **修改位置**：`libpqrcv_connect` 函数，`ALWAYS_SECURE_SEARCH_PATH_SQL` 执行之后（约第 291 行）

在逻辑复制连接建立后，新增条件性 SQL 将 `sql_dialect` 设为 `pg`：

```c
/*
 * For logical replication connections, ensure PG dialect so that
 * standard SQL commands (e.g. BEGIN READ ONLY ISOLATION LEVEL
 * REPEATABLE READ) can be parsed correctly even when the publisher
 * has sql_dialect = 'tsql' globally. On non-Babelfish publishers
 * current_setting() returns NULL for unknown GUCs and set_config()
 * is not called, so this is a no-op.
 */
if (logical)
{
    res = libpqrcv_PQexec(conn->streamconn,
        "SELECT CASE WHEN current_setting('babelfishpg_tsql.sql_dialect', true) IS NOT NULL "
        "THEN set_config('babelfishpg_tsql.sql_dialect', 'pg', false) "
        "ELSE NULL END;");
    PQclear(res);
}
```
**方案要点**：

1. `current_setting(..., true)` 条件检测：`missing_ok=true` 使 GUC 不存在时返回 `NULL` 而非报错。非 Babelfish 发布端（vanilla PG）不会出错，`set_config` 不被调用。
2. 仅在 `logical` 连接上执行：物理复制连接不发送 SQL 命令，无需设置。
3. 无需错误处理：CASE 条件保证 SQL 本身不报错。Babelfish 端执行 `set_config` 成功；PG 端 CASE 返回 `NULL`，均为 `PGRES_TUPLES_OK`。
4. `is_local=false`：Session 级别设置，连接期间持续生效，后续 `BEGIN READ ONLY ...`、`COPY` 等命令均使用 PG 方言解析。
5. 不影响 apply worker DDL 回放：`apply worker` 在 `execute_publication_sync_sql_command`（worker.c:3071）中显式切换 `sql_dialect = TSQL`，覆盖此设置。

**影响**：修复后 `copy_data=true` 在 T-SQL 模式下可用，订阅端可自动拷贝发布端已有数据。同时保持与 PG 发布端的兼容性。

---

## 客户使用约束汇总

| 限制项 | 影响程度 | 是否可继续使用 DDL 同步 | 客户侧建议 |
|--------|----------|--------------------------|------------|
| 物化视图 | 中 | 可以继续用于其他 DDL | 物化视图手动在订阅端创建和维护 |
| view 相关 DDL | 中 | 已由实现限制，不自动同步该类 DDL | `CREATE VIEW`、`ALTER VIEW`、`DROP VIEW` 均由客户在订阅端手动维护 |
| `CREATE TRIGGER` | 中 | 可以继续用于其他 DDL | 触发器手动在订阅端创建，注意是否会影响复制写入 |
| `ALTER INDEX` | 中 | 可以继续用于其他 DDL | 索引维护操作在订阅端手动执行 |
| `ALTER TABLE ADD` 多列 | 低 | 可以 | 拆分为多条单列 `ADD` 语句 |
| `ALTER TABLE ... REPLICA IDENTITY` | 高 | 不应进入 SQL Server 模式 DDL 同步 | 禁止作为业务 DDL 使用；由 DBA 在 PG 管理侧单独处理 |
| `copy_data=true` | 高 | 可以，但订阅初始化需调整 | 创建订阅使用 `copy_data=false`，历史数据手动导入 |

---

## 建议给客户的 DDL 同步使用边界

客户可以把 Babelfish SQL Server 模式下的 DDL 同步定位为：

> 用于同步 Babelfish 已支持的 T-SQL 表结构类变更；不用于替代完整的数据库对象发布系统。

具体建议如下：

1. **推荐自动同步**：普通表创建、删除、字段新增、字段类型调整、普通约束和 Babelfish 已支持的普通索引创建。
2. **需要改写后同步**：单条多列 `ALTER TABLE ADD` 改写为多条单列 `ADD`。
3. **需要人工双端执行**：视图、物化视图、触发器、索引维护类操作。
4. **实现层已排除或禁止进入同步链路**：view 相关 DDL、`ALTER TABLE ... REPLICA IDENTITY`、`copy_data=true` 初始化。
5. **生产上线前检查**：客户 DDL 变更脚本应先通过限制清单检查，确认没有高影响语句后再执行。

当这些限制存在时，客户仍然可以使用 DDL 同步功能，但应将其作为“表结构自动同步能力”使用，而不是把所有数据库对象、所有 SQL Server DDL 和 PostgreSQL 管理语句都交给该功能自动处理。
