# 真希望有人早点告诉我的 Postgres 经验

| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 翻译整理，原文作者 Hazel Bachrach | 2026-08-21 |

> **本文为 Hazel Bachrach 所著 *What I Wish Someone Told Me About Postgres* 一文的中文翻译整理**。
> - 原文链接：https://challahscript.com/what_i_wish_someone_told_me_about_postgres
> - 原文发布时间：2024-11-11（最后更新 2025-01-09）
> - 译者：本文用我自己的中文技术行文重写了原文观点；个别章节补充了 PG 源码定位便于读者深入
> - 如有错译，请以原文为准

---

## 引子

我在 Web 应用行业摸爬滚打了快十年，期间用过很多系统和工具。说实话，**官方文档**通常是最好的学习资料——除了 PostgreSQL。

不是说 PG 文档不好（实际上相当棒），而是它**太长**了。当前版本（PG 17）打印成标准 PDF 居然有 **3200 页**。这玩意不是哪个初级工程师能坐下从头啃完的。

所以今天我想整理一份"如果有人早点告诉我就好了"的清单。希望能让下一个走同样路的人轻松一点。

> 译者注：很多观点其实对其他 SQL 数据库也适用，但我没用过其他，所以这里只谈 PG。

---

## 一、数据要规范化，除非你有明确理由不去规范化

数据库规范化（normalization）是去除 schema 中重复/冗余数据的过程。

举个小例子：你做了一个网站，用户能上传文档，关注其他用户就能收到邮件通知。如果有个 `documents` 表，你**不应该**在文档表里塞 `user_email` 字段——不然用户改邮箱时，得把历史上百条他上传过的文档记录全部更新一遍。

正确做法：`documents` 表里只放 `user_id` 外键，关联到 `users` 表。用户改邮箱只改一处。

网上搜"数据库规范化"会出来一堆"第一范式第二范式"——你不必记住每个范式的定义，但**了解规范化的过程**对写出可维护的 schema 非常有用。

什么时候可以**反规范化**（denormalize）？通常是**让读取变快**。比如一个管理员工排班的系统，用户想看"今年已工作多少小时"。每次都现算所有班次时长会很慢，可以定期算一次存起来——既可以存在 PG 里，也可以存在 Redis 这样的外部缓存。

**反规范化永远有代价**：可能的不一致、写复杂度上升。所以**默认规范化，需要时再反规范化**。

---

## 二、听 PG 官方的劝——尤其是 "Don't Do This" 列表

PG 官方 Wiki 上有个极其实用的列表叫 [Don't Do This](https://wiki.postgresql.org/wiki/Don%27t_Do_This)。有些条目你看不懂，没关系——**看不懂就不会踩**。

几个值得反复提及的：

- **所有文本都用 `text` 类型**——别用 `varchar(n)`、`char(n)`，容量都给你省在数据库里。
- **所有时间戳都用 `timestamptz`**（带时区）——别用 `timestamp`（不带时区）。时区相关的 bug 调试起来能让你掉光头发。
- **表名用 snake_case**——别用驼峰式或大小写混用。PG 默认会把没引号的标识符折叠成小写，引号包裹才会保留原大小写。

> 译者注：这三条的"反直觉"程度从高到低：第一条 `text` vs `varchar` 是性能误区，第二条时区问题是**全世界 PG 用户的血泪史**，第三条是历史包袱（标准 SQL 默认大小写不敏感）。`src/backend/utils/adt/varchar.c` 可以看到 `varchar` 内部其实就是 `text` + 长度检查。

---

## 三、SQL 的一些"古怪"之处

### 3.1 SQL 关键字不用全大写——保护你的小指

文档里 SQL 通常这样写：

```sql
SELECT * FROM my_table WHERE x = 1 AND y > 2 LIMIT 10;
```

其实**大小写无所谓**。下面这俩和上面等价：

```sql
select * from my_table where x = 1 and y > 2 limit 10;

SELECT * from my_table WHERE x = 1 and y > 2 LIMIT 10;
```

> 这不是 PG 特有的行为，整个 SQL 标准如此。你的小指会感谢你。

### 3.2 NULL 不是"空"——是"未知"

你可能从别的语言里接触过 `null`/`nil`——SQL 的 `NULL` 不是那个意思。`NULL` 更准确地说是**"未知"**：

```sql
NULL = NULL  -- 结果是 NULL（不是 true！两个未知是否相等？未知）
```

这条规则几乎对**所有运算符**都成立：如果比较运算符一边是 `NULL`，结果就是 `NULL`。

要"安全地"和 `NULL` 比较，用这几个运算符：

| 表达式 | 含义 |
| --- | --- |
| `x IS NULL` | x 是 NULL 吗？ |
| `x IS NOT NULL` | x 不是 NULL 吗？ |
| `x IS NOT DISTINCT FROM y` | 等价 `x = y`，但 NULL 当作正常值 |
| `x IS DISTINCT FROM y` | 等价 `x <> y`，但 NULL 当作正常值 |

⚠️ **`WHERE` 子句只在条件为 `true` 时才命中**。所以：

```sql
SELECT * FROM users WHERE title != 'manager';
```

这条**不会返回 `title` 为 NULL 的行**——因为 `NULL != 'manager'` 是 `NULL`，不是 `true`。

另一个工具：`COALESCE(a, b, c, ...)`——返回第一个不是 `NULL` 的参数：

```sql
COALESCE(NULL, 5, 10) = 5
COALESCE(2, NULL, 9) = 2
COALESCE(NULL, NULL) IS NULL
```

---

## 四、把 psql 玩明白

### 4.1 修一下那该死的输出

表太宽导致输出乱成一锅？多半是你**没启用分页器（pager）**。

`less` 是 Linux/macOS 标配的分页器：

```bash
# 在 ~/.zshrc 或 ~/.bashrc 里
export PAGER='less -S'   # -S 表示长行截断不换行
```

光有分页还不够——宽表用表格打印仍然看不清。这时候切到 **expanded display**：

```sql
\pset expanded   -- 或快捷 \x
```

想让它变成 psql 启动默认行为？建一个 `~/.psqlrc` 文件，写一行：

```
\x
```

每次启动 psql 会自动执行里面的命令。

### 4.2 让 NULL 更显眼

默认的 NULL 在 psql 输出里就是个**空字符串**——分不清是 NULL 还是空串。给它一个明显的标记：

```sql
\pset null '[NULL]'
```

任何 Unicode 字符串都行，原文作者的朋友 Steven Harman 用 👻（"幽灵"代替 NULL）——很 spooky season 的选择。

同样可以写进 `~/.psqlrc`：

```
\pset null '[NULL]'
```

### 4.3 用 Tab 自动补全

psql 像大多数交互式 shell 一样支持 Tab 补全。SQL 关键字和表名都能补全：

```sql
-- 敲 SEL 然后按 Tab
SEL<Tab>
-- 变 SELECT
```

### 4.4 背几个反斜杠命令

psql 有大量 `\xxx` 快捷命令，下面是最常用的几个：

| 命令 | 作用 |
| --- | --- |
| `\?` | 列出**所有**反斜杠命令 |
| `\d` | 列出所有表/序列及其 owner |
| `\d+` | 同 `\d`，加上大小等元信息 |
| `\d table_name` | 看某张表的 schema（列、类型、可空、默认值、索引、外键） |
| `\e` | 打开 `$EDITOR` 编辑当前 SQL |
| `\h SQL_KEYWORD` | 查看某关键字的语法和文档链接 |

这只是冰山一角。

### 4.5 一键导出 CSV

想把查询结果导成 CSV 喂给 Excel？一行命令：

```sql
\copy (select * from some_table) to 'my_file.csv' CSV
```

加表头：

```sql
\copy (select * from some_table) to 'my_file.csv' CSV HEADER
```

反向操作（从 CSV 导入）也可以，详见 [psql 文档](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-META-COMMANDS-COPY)。

> `\copy` 是个**客户端**命令（不是服务器端的 `COPY`），所以**不需要服务器 superuser 权限**——这是它在大多数实际场景下比 `COPY` 更好用的原因。

### 4.6 列别名与位置引用

`SELECT` 里可以用 `AS` 给输出列重命名：

```sql
SELECT vendor, COUNT(*) AS number_of_backpacks
FROM backpacks
GROUP BY vendor
ORDER BY number_of_backpacks DESC;
```

更妙的是：**`GROUP BY` 和 `ORDER BY` 可以用列在 SELECT 里的位置**（1-based）：

```sql
SELECT vendor, COUNT(*) AS number_of_backpacks
FROM backpacks
GROUP BY 1     -- = GROUP BY vendor
ORDER BY 2 DESC;  -- = ORDER BY number_of_backpacks DESC
```

> ⚠️ 别把这种写法推到生产代码里——加列、改顺序都会破坏含义。自己调试时可以偷懒。

---

## 五、加索引可能完全没用（特别是没配对的时候）

### 5.1 什么是索引？

索引是帮助查找数据的数据结构——给 PG 一个"快捷目录"。最常见的是 [B-tree](https://www.baeldung.com/cs/b-tree-data-structure) 索引，既支持等值查询（`WHERE a = 3`）也支持范围查询（`WHERE a > 5`）。

但 PG **不会**听你"用某个索引"。它会用统计信息**预测**走索引是否比顺序扫描（seq. scan）更快。

加 `EXPLAIN` 看 PG 准备怎么执行你的查询：

```sql
EXPLAIN SELECT * FROM users WHERE email = 'alice@x.com';
```

输出是"查询计划"——PG 打算怎么找数据、每步预估的成本。

读 EXPLAIN 的资料推荐：

- [thoughtbot 的指南](https://thoughtbot.com/blog/reading-an-explain-analyze-query-plan)
- [pganalyze 文档](https://pganalyze.com/docs/explain)
- [explain.depesz.com](https://explain.depesz.com/)——可视化分析工具，调试神器

### 5.2 行数太少时索引没用

开发环境里的本地数据库通常没几行数据。PG 可能觉得"100 行直接扫一遍更快"，**根本不用你的索引**。这是正常现象，不是 bug。

### 5.3 多列索引的顺序很重要

```sql
CREATE INDEX CONCURRENTLY ON tbl (a, b);
```

会**同时加速**这两个查询：

```sql
SELECT * FROM tbl WHERE a = 1;                  -- 走索引
SELECT * FROM tbl WHERE a = 1 AND b = 2;        -- 走索引
```

但这个查询**快不到哪去**：

```sql
SELECT * FROM tbl WHERE b = 5;                  -- 不能直接走 (a,b) 索引
```

原因：B-tree 先按 `a` 排，再在每个 `a` 内按 `b` 排。要查 `b = 5`，得扫所有 `a` 才能找全。所以**如果业务上经常按 `b` 单独查，需要单独给 `b` 加索引**。

> 译者注：PG 14+ 引入了"index skip scan"，可以让某些场景下的单列查询利用多列索引，但**不通用**。核心优化点仍然是按查询模式设计索引。

### 5.4 前缀匹配用 `text_pattern_ops`

假设你在存目录结构（materialized path 风格），每行存所有祖先的 id 拼接。要找某个目录的所有子目录：

```sql
-- % 是通配符：找 path 以 '/1/2/3/' 开头的所有目录
SELECT * FROM directories WHERE path LIKE '/1/2/3/%';
```

加个索引加速：

```sql
CREATE INDEX CONCURRENTLY ON directories (path);
```

**可惜 PG 可能不用**。默认 B-tree 依赖值的**排序**来工作，但 PG 默认 collation 是按 locale 排的，对 `LIKE 'xxx%'` 前缀匹配没用需要**显式指定 operator class**：

```sql
CREATE INDEX CONCURRENTLY ON directories (path text_pattern_ops);
```

> 译者注：详见 PG 文档 [Operator Classes and Operator Families](https://www.postgresql.org/docs/current/indexes-opclass.html)。

---

## 六、长持有的锁会搞挂你的应用（包括 `ACCESS SHARE`）

### 6.1 什么是锁？

锁（或 mutex，互斥锁）保证同一时刻只有一个客户端在做"危险的事"。PG 这样的数据库里，**单条记录的更新必须全部成功或全部失败**——不能让两个客户端同时改同一行各改一半。

### 6.2 PG 的锁等级（从弱到强）

| 锁模式 | 示例语句 |
| --- | --- |
| `ACCESS SHARE` | `SELECT` |
| `ROW SHARE` | `SELECT ... FOR UPDATE` |
| `ROW EXCLUSIVE` | `UPDATE` / / `DELETE` / / `INSERT` |
| `SHARE UPDATE EXCLUSIVE` | `CREATE INDEX CONCURRENTLY` |
| `SHARE` | `CREATE INDEX`（非 CONCURRENTLY） |
| `ACCESS EXCLUSIVE` | 各种 `ALTER TABLE` / `ALTER INDEX` |

锁冲突矩阵（X 表示冲突）：

```text
       现有锁模式
请   │ACC SHR│ROW SHR│ROW EXCL│SH UP EX│SHARE │ACC EX│
求 ──┼───────┼───────┼────────┼────────┼──────┼──────┤
ACC SH│       │       │        │        │      │  X   │
ROW SH│       │       │        │        │  X   │  X   │
ROW EX│       │       │        │  X     │  X   │  X   │
SH UP │       │       │  X     │  X     │  X   │  X   │
SHARE │       │  X    │  X     │  X     │      │  X   │
ACC EX│  X    │  X    │  X     │  X     │  X   │  X   │
```

几个关键场景：

| 客户端 1 在做 | 客户端 2 想做 | 能不能立即跑？ |
| --- | --- | --- |
| `UPDATE` | `SELECT` | ✅ 可以 |
| `UPDATE` | `CREATE INDEX CONCURRENTLY` | ✅ 可以 |
| `SELECT` | `CREATE INDEX`（非 CONCURRENTLY） | ✅ 可以 |
| `SELECT` | `ALTER TABLE` | 🚫 **必须等** |
| `ALTER TABLE` | `SELECT` | 🚫 **必须等** |

详见 [PG 官方文档](https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-TABLES) 和 [postgres-locks.husseinnasser.com](https://postgres-locks.husseinnasser.com/)（这个工具能告诉你某个具体操作会冲突哪些锁）。

### 6.3 怎么会出问题？

ALTER TABLE 是最容易踩的坑：

```sql
-- 客户端 1：运行 ALTER TABLE
ALTER TABLE users ADD COLUMN last_login timestamptz;

-- 客户端 2：必须等
SELECT * FROM users WHERE id = 123;  -- 阻塞
```

如果 ALTER TABLE 几秒钟就完成，影响不大。但：

- 加带非常量默认值的列（PG 11 之前！）
- 改列类型
- 加 UNIQUE 约束

都可能让 ALTER TABLE 慢到分钟级。`SELECT` 都堵在后面排队，等到超时 → 你的应用 503。

**最阴险的场景**：你的 ALTER TABLE 本身很快（只要拿到锁），但有个**多年前写的内部 dashboard**，跑了一条很慢的 `SELECT`。`ALTER TABLE` 必须等那条 `SELECT` 完成才能跑——而后续所有 `SELECT` 都会在这条 `ALTER TABLE` 后面排队。**PG 的锁是 FIFO 队列**！

> 详见 xata.io 的文章 [Migrations and Exclusive Locks](https://xata.io/blog/migrations-and-exclusive-locks)。

### 6.4 长事务同样危险

事务和锁有点类似——都是为了"避免别人插手你正在做的事"。经典场景：转账。

```sql
BEGIN;
SELECT * FROM backpacks WHERE id = 2;
UPDATE backpacks SET content_count = 3 WHERE id = 2;
SELECT count(*) FROM backpacks;
-- ... 程序员去拿纸杯蛋糕 ...
-- ... 同事在写 DELETE
DELETE FROM backpacks WHERE id = 2;  -- 阻塞！等待事务提交
COMMIT;
```

> ⚠️ 客户端 1 实际只改了 `id = 2` 一行，但**整条事务不提交，所有 row-level 锁都不释放**。同事的 DELETE 会被无限阻塞直到 Client 1 回来。

这个例子改自原文，作者加了非常生动的注释：`-- ... `。生产上一旦发生，PG 会越积越多 idle in transaction 的连接，最后整个应用崩盘。

---

## 七、JSONB 是一把锋利的刀

PG 有一个相当强的能力：**把 JSON 数据当一行的某个字段存**，还能查询、索引。在很多场景下，这让 PG 同时具备**文档数据库**（如 MongoDB）的优势，不必又不用引入新服务。

但用错地方会反咬你一口。

### 7.1 JSONB 可能比普通列慢

PG **不为 JSONB 列维护统计**，所以同样语义的查询，写到普通列里通常更快。极端情况能差**几千倍**！

详见 Heap 博客 [When to avoid JSONB in a PostgreSQL schema](https://www.heap.io/blog/when-to-avoid-jsonb-in-a-postgresql-schema)。

### 7.2 JSONB 不像普通表那么"自我解释"

JSONB 列里可以塞**任何结构**——这是它的力量。但也意味着你没法保证它的形状：

- 键名是 camelCase 还是 snake_case？
- 状态用 boolean 还是 yes/maybe/no 字符串？
- 时间是 ISO8601 还是 epoch？

普通表的 schema 是静态的，jsonb 没有这种"契约"。

### 7.3 JSONB 的语法有点别扭

假设有张表：

```sql
CREATE TABLE backpacks (
    id     serial PRIMARY KEY,
    data   jsonb
);
```

想找品牌为 JanSport 的：

```sql
-- 错误写法！会报 invalid input syntax for type json
SELECT * FROM backpacks WHERE data['brand'] = 'JanSport';
```

报错：

```text
ERROR: invalid input syntax for type json
DETAIL: Token "JanSport" is invalid.
CONTEXT: JSON data, line 1: JanSport
```

为啥？PG 期望右边是**合法的 JSON 值**（对象、数组、字符串、数字、布尔、null）——`JanSport` 本身不是合法 JSON（要带引号才合法）。

正确写法：

```sql
-- 把右边也变成 jsonb 字面量
SELECT * FROM backpacks WHERE data['brand'] = '"JanSport"';
-- 或者显式 cast
SELECT * FROM backpacks WHERE data['brand'] = '"JanSport"'::jsonb;
-- 或者把左边转成 text（用 ->> 而不是 ->）
SELECT * FROM backpacks WHERE data->>'brand' = 'JanSport';
```

⚠️ **`jsonb` 里的 `null` 和 SQL 的 `NULL` 不是一个东西**：

```sql
SELECT 'null'::jsonb = 'null'::jsonb;  -- true
SELECT NULL = NULL;                      -- NULL
```

> 译者注：PG 14+ 引入的 `data['brand']` 这种 subscripting 语法比 `data->'brand'` 更直观，但**容易踩类型坑**——左操作数是 jsonb，右操作数也必须是 jsonb。

完整的 JSONB 运算符和函数看 [官方文档](https://www.postgresql.org/docs/current/functions-json.html)——多背几个常用的。

---

## 八、收尾

希望这份清单对你有用。

如果你发现错译、想补充的，或有反馈意见，可以在原文评论区留言。

> 译者注：原文作者 Hazel Bachrach 在文末感谢了多位早期读者。如果你想看英文原汁原味的版本（毕竟"出错以原文为准"），请直接访问：https://challahscript.com/what_i_wish_someone_told_me_about_postgres

---

## 译者补充：把这份清单对应到 PG 源码

| 主题 | 源码位置 |
| --- | --- |
| `text` / `varchar` 内部实现 | `src/backend/utils/adt/varchar.c`、`text.c` |
| 时区处理 (`timestamptz`) | `src/backend/utils/adt/timestamp.c` |
| 大小写折叠（snake_case 约定） | `src/backend/parser/scan.l` |
| `NULL` 三值逻辑 | `src/backend/executor/execQual.c` |
| 锁模式 | `src/backend/storage/lmgr/lock.c` |
| 锁队列 (FIFO) | `src/backend/storage/lmgr/proc.c` |
| `CREATE INDEX CONCURRENTLY` | `src/backend/catalog/index.c` |
| `text_pattern_ops` operator class | `src/backend/utils/adt/like.c` |
| MVCC 与事务可见性 | `src/backend/access/heap/heapam_visibility.c` |
| JSONB 处理 | `src/backend/utils/adt/jsonb.c` |
| 索引 skip scan（PG 14+） | `src/backend/optimizer/path/indxpath.c` |

---

## 参考资料

- 原文：Hazel Bachrach, *What I Wish Someone Told Me About Postgres*, https://challahscript.com/what_i_wish_someone_told_me_about_postgres, 2024-11-11
- [PostgreSQL 官方文档](https://www.postgresql.org/docs/current/)
- [PostgreSQL Wiki - Don't Do This](https://wiki.postgresql.org/wiki/Don%27t_Do_This)
- [Heap.io: When to avoid JSONB](https://www.heap.io/blog/when-to-avoid-jsonb-in-a-postgresql-schema)
- [explain.depesz.com](https://explain.depesz.com/)
- [xata.io: Migrations and Exclusive Locks](https://xata.io/blog/migrations-and-exclusive-locks)
- [postgres-locks.husseinnasser.com](https://postgres-locks.husseinnasser.com/)
