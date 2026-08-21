# PostgreSQL "Don't Do This" 完整中文版

| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 翻译整理，原文为 PostgreSQL 官方 Wiki | 2026-08-21 |

> **本文为 PostgreSQL 官方 Wiki *Don't Do This* 页面的中文翻译整理**。
> - 原文链接：https://wiki.postgresql.org/wiki/Don%27t_Do_This
> - 原文性质：PostgreSQL 官方社区维护的"反模式清单"
> - 译者：本文用我自己的中文技术行文重写，并补了一部分 PG 源码定位
> - 如有错译，请以原文为准
> - 配套工具：[schemalint](https://github.com/kaaveland/schemalint)（Kristian Dupont 提供，可自动对照本清单检查你的 schema）

---

## 关于这份清单

这是一份**常见错误**的清单——按主题分章，每条都说清楚"**为什么不要**"和"**什么时候才可以用**"。

> 译者注：很多条目对 MySQL / Oracle 用户来说是反直觉的，那是因为**各家默认值不一样**。PostgreSQL 在这些地方的设计哲学是"**合理默认值优先于历史包袱**"。

---

## 一、数据库编码

### 1.1 不要用 `SQL_ASCII`

#### 为什么不要？

`SQL_ASCII` 在所有编码转换函数里都意味着"**不做任何转换**"——原始字节直接当作新编码处理，不会校验字符是否合法。

除非极其小心，否则 `SQL_ASCII` 数据库最终会变成**一堆无标签编码的混合体**，根本无法可靠还原原始字符。

#### 什么时候可以用？

如果你的输入数据本身就是一堆**毫无头绪的混合编码**（比如 IRC 频道日志、不合规邮件），那 `SQL_ASCII` 可以作为兜底。但**先考虑 `bytea`**，或者自动检测 UTF8 把非 UTF8 数据归到某个具体编码（比如 `WIN1252`）。

> 译者注：现代系统一律 UTF8，不要再为老数据妥协。这条历史意义大于实际意义。

---

## 二、工具用法

### 2.1 不要用 `psql -W` 或 `psql --password`

#### 为什么不要？

加 `--password` / `-W` 会让 psql **连接服务器之前**就要求你输入密码——**即使服务器根本不要密码**也会弹提示。

这从来没必要用。服务器真要密码时 psql 自己会弹提示；不需要时你就别多此一举。

`-W` 特别容易让人**误以为**服务器在要密码。比如你用 peer 认证连本地库时 `-W` 会让你输密码，然后你以为"哦原来是要密码的"——其实不是。

更糟的是：如果你登录的用户**没设密码**或**输错密码**，你仍然"成功"连进去，然后**其他客户端**或**其他用户**就没法连。debug 时一头雾水。

#### 什么时候可以用？

几乎**永远不要用**。最多省一次往返握手，不值。

---

### 2.2 不要用规则（rules）

**不要用 rules。** 如果你觉得你需要，那应该用触发器（trigger）。

#### 为什么不要？

规则（`CREATE RULE`）能力很强，但**它们做的事和看起来做的事不一样**。看起来像条件判断，实际上**重写查询**——把原查询改掉或加额外查询。

也就是说**几乎所有非平凡的规则都是错的**。

详见 [Depesz 的博客](https://www.depesz.com/)。

#### 什么时候可以用？

**永远不要用**。规则机制是视图（VIEW）的实现细节，没有理由直接掀开这块盖板。

> 译者注：视图在 PG 里就是用规则实现的（`CREATE VIEW` 背后是 `CREATE RULE ... ON SELECT ... DO INSTEAD ...`），所以规则本身没问题，但**手写规则来改写 UPDATE/INSERT/DELETE** 几乎必然踩坑。

---

### 2.3 不要用表继承（table inheritance）

**不要用表继承。** 如果你觉得你需要，那应该用**外键**。

#### 为什么不要？

表继承是当年**数据库与面向对象代码紧耦合**的时髦做法。结果证明，**强耦合并不会产生想要的结果**。

#### 什么时候可以用？

**几乎永远不要用**。PG 10+ 有了**原生分区表**（`PARTITION BY RANGE/LIST/HASH`），那种用法已经被原生特性取代——分区路由、约束传播、查询裁剪都是原生的，不必自己写继承 + UNION ALL。

极少的例外：如果你**临时**用 `temporal_tables` 扩展做行版本化（PG 还没支持 SQL:2011 的 temporal），表继承能省掉一些 `UNION ALL` 拼凑历史的 SQL。即便如此，用父表时也得小心各种坑。

> 译者注：分区表的源码在 `src/backend/catalog/partition.c`、路由逻辑在 `src/backend/executor/execPartition.c`，已经非常成熟。

---

## 三、SQL 写法

### 3.1 不要用 `NOT IN`

**不要用 `NOT IN`**，或任何 `NOT` + `IN` 的组合（比如 `NOT (x IN (select…))`）。

#### 为什么不要？

两个原因：

**1. NULL 时的行为很反直觉：**

```sql
-- 这条永远返回 0 行
SELECT * FROM foo WHERE col NOT IN (1, NULL);

-- 这条如果 bar.x 里有 NULL，也永远返回 0 行
SELECT * FROM foo WHERE foo.col NOT IN (SELECT bar.x FROM bar);
```

原因：`col IN (1, NULL)` 在 `col=1` 时返回 `TRUE`，否则返回 `NULL`（永远不返回 `FALSE`）。`NOT TRUE = FALSE`，但 `NOT NULL = NULL`——所以 `col NOT IN (1, NULL)` 永远不可能是 `TRUE`。

**2. `NOT IN (SELECT ...)` 优化效果差。**

优化器**无法**把它转成 anti-join，只能用 hashed Subplan 或 plain Subplan。前者快但只对小结果集用，后者**是 O(N²)**——测试时看着快，规模一过阈值**慢 5 个数量级以上**。

**替代写法**：用 `NOT EXISTS`：

```sqlSELECT * FROM foo WHERE NOT EXISTS (
    SELECT 1 FROM bar WHERE foo.col = bar.x
);
```

#### 什么时候可以用？

`NOT IN (const, list, ...)`)**基本安全**，除非列表里可能有 NULL。所以排除特定常量值时用它挺自然的。

---

### 3.2 不要用驼峰或大写表名/列名

**不要用 `NamesLikeThis`，用 `names_like_this`。**

#### 为什么不要？

PostgreSQL 默认把所有未加双引号的标识符**折叠为小写**。

```sql
CREATE TABLE Foo();    -- 创建的表叫 foo
CREATE TABLE "Bar"();  -- 创建的表叫 Bar
```

下面这些都能跑：

```sql
SELECT * FROM Foo;
SELECT * FROM foo;
SELECT * FROM "Bar";
```

下面这些会报 "no such table"：

```sql
SELECT * FROM "Foo";   -- 错（找不到 foo 带引号的版本）
SELECT * FROM Bar;      -- 错（找不到 "Bar" 的小写版本）
SELECT * FROM bar;      -- 错（找不到 "Bar" 的小写版本）
```

也就是说——一旦表名/列名带大写，你就**必须**始终对它们加双引号，**或者**始终不加。这两种风格混着用已经够烦了，更别说不同的工具（ORM、ORM、、BI 数据库、CLI）**有的总是加引号、有的不加**——混乱加倍。

只用 `a-z`、`0-9`、下划线——永远不用关心引号。

#### 什么时候可以用？

如果"漂亮名字"对报表输出很重要，可以用别名：

```sql
SELECT character_name AS "Character Name" FROM foo;
```

列存储还是 snake_case，输出才"漂亮"。

---

### 3.3 不要用 `BETWEEN`（尤其是对时间戳）

#### 为什么不要？

`BETWEEN` 是**闭区间**比较——两端的值都包含。

这对**时间戳**特别坑：

```sql-- 这条会包含 2018-06-08 00:00:00.000000，但不会包含这天晚一点的时间
SELECT * FROM blah WHERE timestampcol BETWEEN '2018-06-01' AND '2018-06-08';
```

你可能觉得"看起来对啊"，但只要有一条记录恰好落在午夜 0 点，就会**被双重计入**。

**改用半开区间**：

```sqlSELECT * FROM blah
WHERE timestampcol >= '2018-06-01'
  AND timestampcol <  '2018-06-08';
```

#### 什么时候可以用？

`BETWEEN` 对**离散值**（整数、日期）安全，只要记得两端都包含就行。但**作为习惯要改**——不然总有一天掉坑里。

> 译者注：源码里 `BETWEEN` 实际就是 `>= AND <=` 拼出来的，`src/backend/parser/parse_expr.c`。

---

## 四、日期/时间存储

### 4.1 不要用 `timestamp`（不带时区）

**不要用 `timestamp` 存时间戳。用 `timestamptz`（即 `timestamp with time zone`）。**

#### 为什么不要？

`timestamptz` 存的是一个**确定的时刻**。虽然名字带"timestamp"，它存的其实**不是时间戳**，而是从某个固定点（PG 用 2000-01-01 UTC）起的微秒数。可以用任何时区**插入**，PG 内部统一存那个时刻；**查询时**默认显示在当前时区，可用 `AT TIME ZONE` 显示在其他时区。

`timestamptz` 存储的是一个时刻，所以**跨时区、跨夏令时的算术运算**都自然正确。

`timestamp`（不带时区）则**不是**这样——它只是存"你给它的日期和时间"。可以理解成一张**挂历加挂钟的照片**，而不是一个时刻。没有附加信息（时区）你根本不知道这代表什么时区的几点。所以**跨时区、跨夏令时的算术**会给出错误答案。

要存"时刻"就用 `timestamptz`。

#### 什么时候可以用？

如果你是**抽象地**处理时间戳，或者只是存一下再从应用读出来，**不做算术**——那 `timestamp` 凑合能用。

---

### 4.2 不要用 `timestamp`（不带时区）存 UTC 时间

把 UTC 值塞进 `timestamp without time zone` 列——这是从其他**不支持时区的数据库**带过来的坏习惯。

**用 `timestamp with time zone`。**

#### 为什么不要？

数据库**没法知道**这个列里存的就是 UTC。

这会让很多时间计算变得非常复杂。比如"用户 `u.timezone` 时区的今天 0 点"变成：

```sqldate_trunc('day', now() AT TIME ZONE u.timezone) AT TIME ZONE u.timezone AT TIME ZONE 'UTC'
```

而"给定 `x.datecol` 的前一天 0 点（在 `u.timezone`）"变成：

```sqldate_trunc('day', x.datecol AT TIME ZONE 'UTC' AT TIME ZONE u.timezone)
  AT TIME ZONE u.timezone AT TIME ZONE 'UTC'
```

#### 什么时候可以用？

如果**与不支持时区的数据库兼容**比什么都重要。

---

### 4.3 不要用 `timetz`

**不要用 `timetz`。** 你大概想要的是 `timestamptz`。

#### 为什么不要？

**官方手册自己都说了**，这个类型只是为了 SQL 标准合规而实现。

SQL 标准定义了 `time with time zone`，但其定义导致**实际用处可疑**。绝大多数情况下，`date` + `time` + `timestamp without time zone` + `timestamp with time zone` 这四种类型**够任何应用用了**。

#### 什么时候可以用？

**永远不要用**。

> 译者注：源码 `src/backend/utils/adt/date.c`/`timestamp.c` 可以看到 `timetz` 的实现残缺——只有时区信息但没有日期，所以夏令时调整没法做。

---

### 4.4 不要用 `CURRENT_TIME`

**不要用 `CURRENT_TIME`。** 用对应的：

- `CURRENT_TIMESTAMP` 或 `now()` —— `timestamp with time zone`
- `LOCALTIMESTAMP` —— `timestamp without time zone`
- `CURRENT_DATE` —— `date`
- `LOCALTIME` —— `time`

#### 为什么不要？

`CURRENT_TIME` 返回 `timetz` 类型——见上一条。

#### 什么时候可以用？

**永远不要用**。

---

### 4.5 不要用 `timestamp(0)` 或 `timestamptz(0)`

**不要给 timestamp 列（或 cast）指定精度，更不要指定 0。**

用 `date_trunc('second', blah)` 代替。

#### 为什么不要？

因为 `timestamp(0)` 会**舍入**到秒，而不是你预期的**截断**。把 `now()` 存到这种列，**可能存的是未来半秒钟**。

#### 什么时候可以用？

**永远不要用**。

> 译者注：源码 `src/backend/utils/adt/timestamp.c` 的 `timestamptz_in` 函数，确实是按精度 round 而非 truncate。

---

### 4.6 不要用 `+/-HH:mm` 作为文本时区名

#### 为什么不要？

PG **不接受**固定时区偏移作为 ISO 时区名/缩写的替代。如果你写了个固定偏移，会被当作 **POSIX 自定义时区规范**——结果**正负号方向反了**（ISO 是向东为负，POSIX 是向东为正）。

如果真要用固定偏移，**用 `INTERVAL` 类型**：

```sql-- 04:00 在 ISO 约定下就是东四区
SELECT now() AT TIME ZONE INTERVAL '04:00';
```

#### 什么时候可以用？

**ISO 格式的 timestamptz 字面量**里可以用带符号偏移，方向按 ISO 解释：

```sqlSELECT '2024-01-31 17:16:25+04'::timestamptz;  -- → 13:16:25 UTC
```

---

## 五、文本存储

### 5.1 不要用 `char(n)`

**不要用 `char(n)`。** 你大概想要 `text`。

#### 为什么不要？

任何插入 `char(n)` 的字符串都会被**空格 padding 到声明宽度**。你多半不想要这个。

PG 官方手册原文：

> Values of type character are physically padded with spaces to the specified width n, and are stored and displayed that way. However, trailing spaces are treated as semantically insignificant and disregarded when comparing two values of type character.

空格 padding 不止浪费空间，**还**让操作更慢（因为很多场景需要 strip 空格）。

在某些 collation 下，`char(n)` 的行为更诡异：

```sqlSELECT 'a '::CHAR(2) COLLATE "C" < E'a\n'::CHAR(2)
-- 返回 true，但 C locale 下空格应该 > 换行
```

> 当你看完手册这段还能面不改色说"嗯有道理"，那它就适合你。否则就跑。

另外 `char(n)` **不是**真正的定长类型——实际占的字节数会因字符编码（多字节字符）而变。

#### 什么时候可以用？

- 你在移植**非常老的**用定长字段的软件
- 你是上面那位"看完还觉得合理"的稀有品种

---

### 5.2 不要用 `char(n)` 存定长标识符

有人会问"我的值必须**正好 N 个字符**（比如国家代码、哈希、外部标识符）——那 `char(n)` 没问题了吧？"

**还是有问题。**

用 `text`，或者用 `text` 的 domain + `CHECK(length(VALUE)=3)` 或 `CHECK(VALUE ~ '^[[:alpha:]]{3}$')`。

#### 为什么不要？

`char(n)` **不会拒绝太短的值**——只会**默默用空格补足**。所以和用 `text` + 长度约束相比没有任何优势。bonus：你的 CHECK 还能**验证格式**。

记住：`char(n)` 对比 `varchar(n)` **没有任何性能优势**——反而更慢。一个具体问题：如果你拿 `char(n)` 字段和某个**驱动显式声明为 `text`/`varchar` 的参数**比较，可能意外地**用不上索引**。手动跑 SQL 时又看不出来，调试很难。

#### 什么时候可以用？

**永远不要用**。

---

### 5.3 不要默认用 `varchar(n)`

**不要默认用 `varchar(n)`。** 用 `varchar`（不带长度）或 `text`。

#### 为什么不要？

`varchar(n)` 是变长字符串，**插入超过 n 个字符（注意是字符不是字节）会报错**。

`varchar`（不带 `(n)`）或 `text` 是一样长的字段，**没有长度限制**。插入同样字符串到三种字段占的空间**完全一样**，性能**测不出差异**。

如果你确实要"文本 + 长度限制"，那 `varchar(n)` 很好。但如果你**拍脑袋选个长度**——`varchar(20)`)` 存姓氏——早晚有一天 Hubert Blaine Wolfeschlegelsteinhausenbergerdorff 注册时把你的服务炸了。

> 译者注：这个名字是网络上"最长姓名"的梗，1939 年英国出生证明上真有这么一位。

有些数据库没"任意长文本"类型，或者有但不够好用，那些 DB的用户会习惯性用 `varchar(255)`——其实**他们想要的就是 `text`**。

如果你的字段需要约束，那大概率**不只是最大长度**——可能还要最小长度、字符集、格式校验。用 CHECK 约束能搞定**所有**这些。

#### 什么时候可以用？

- 你真的想要"插入过长报错"且不想显式加 CHECK——那 `varchar(n)` 很好
- 别无脑用

另外 `varchar` 在 SQL 标准里，`text` 不在——所以**写超级可移植的应用**时 `varchar` 可能更合适。

---

## 六、其他数据类型

### 6.1 不要用 `money`

`money` 类型**不适合**存钱。用 `numeric`，或者（极少）`integer`。

#### 为什么不要？

一堆原因：

- 它是定点类型，用机器 int 实现——算术快。
- 但**它处理不了分以下的小数**（其他货币的小数位），舍入行为多半不是你想要的。
- **它不存币种**，而是用数据库 `lc_monetary` locale 设置的币种。如果你改了 `lc_monetary`，**所有 money 列的值都错了**。比如 `lc_monetary='en_US.UTF-8'` 时插入 `'$10.00'`，改成别的可能读出 `'10,00 Lei'` 或 `'¥1,000'`。

用 `numeric` + 一个**相邻列存币种**更好。

#### 什么时候可以用？

只用单一币种、不处理分以下小数、只加减——`money` 可以用。

---

### 6.2 不要用 `serial`

**新应用应该用 `IDENTITY` 列**（`GENERATED ... AS IDENTITY`）。

#### 为什么不要？

`serial` 类型（`serial` / `bigserial` / `smallserial`）有些古怪，让 schema、依赖、权限管理变得**不必要地繁琐**——它本质上是一个**自动创建序列 + 关联默认值**的语法糖，但相关的序列、约束、权限分散在三处。

#### 什么时候可以用？

- 需要支持 PG 10 之前的版本
- 某些和表继承的组合（（但看前面那段）
- 更一般地：如果你让**同一个序列服务多张表**，那种情况下**显式声明**也比 `serial` 好

> 译者注：`IDENTITY` 列在 `src/backend/parser/parse_expr.c`、`src/backend/catalog/heap.c` 里实现——本质和 `serial` 一样，但所有元数据集中在一处，权限管理更清晰。

---

## 七、认证

### 7.1 不要在 TCP/IP 上用 trust 认证（`host`、`hostssl`）

**任何生产环境都不要在 TCP/IP 上用 trust 认证。**

特别是不要在 `pg_hba.conf` 里写：

```confhost    all   all   0.0.0.0/0   trust
```

这等于把整个数据库公开给互联网——包括 PG 的 superuser。

正经的远程连接认证方式很多——至少上密码，**推荐 `scram-sha-256`**（PG 10+ 提供）。

#### 为什么不要？

PG 手册原文：

> trust authentication is only suitable for TCP/IP connections if you trust every user on every machine that is allowed to connect to the server by the pg_hba.conf lines that specify trust. It is seldom reasonable to use trust for any TCP/IP connections other than those from localhost (127.0.0.1).

用 trust 认证，**任何用户**都可以**声称自己是任何其他用户**，PG **会信任这个说法**。这意味着某人可以声称自己是 `postgres` superuser，PG 会接受并允许登录。

进一步说，**本地 UNIX socket 也不该用 trust**——能登录到运行 PG 的机器的人都能以任何用户身份登录 PG。

#### 什么时候可以用？

短答案：**永远不要用**。

长答案：少数场景可以：

- CI/CD 跑测试任务（在可信网络里）
- 本地开发机，但只允许 localhost TCP/IP

但你应该考虑**别的认证方式**。比如 UNIX 系统本地开发，**peer 认证**就挺好。

---

## 译者补充：把这些"反模式"对应到 PG 源码

| 反模式 | 源码位置 | 备注 |
| --- | --- | --- |
| `SQL_ASCII` 行为 | `src/backend/utils/adt/conv.c` | `pg_do_encoding_conversion` 对 SQL_ASCII 直接透传 |
| 表继承 | `src/backend/catalog/heap.c` + `src/backend/optimizer/path/allpaths.c` | PG 10+ 推荐用 `PARTITION BY` 取代 |
| `NOT IN` 优化器 | `src/backend/optimizer/plan/subselect.c` | 没法转 anti-join，只能 Subplan |
| 时间戳时区处理 | `src/backend/utils/adt/timestamp.c` | `timestamptz` 存的是 epoch 微秒数 |
| `char(n)` padding | `src/backend/utils/adt/varchar.c` | 字段头里有个 `tp`（typmod） |
| `BETWEEN` | `src/backend/parser/parse_expr.c` | 直接展开成 `>= AND <=` |
| `money` 行为 | `src/backend/utils/adt/cash.c` | 用 int + `lc_monetary` |
| `serial` 限制 | `src/backend/parser/parse_expr.c` + `src/backend/catalog/pg_type.h` | `IDENTITY` 在 PG 10+ 的 `src/backend/catalog/heap.c` |
| trust 认证 | `src/backend/libpq/hba.c` | `hba_authname` 等函数 |

---

## 参考资料

- 原文：*Don't Do This*, PostgreSQL Wiki, https://wiki.postgresql.org/wiki/Don%27t_Do_This
- [schemalint](https://github.com/kaaveland/schemalint) — Kristian Dupont 写的 schema 自动检查工具，能对照这份清单验证你的 schema
- [PostgreSQL 官方文档](https://www.postgresql.org/docs/current/)
- [Depesz 关于 RULES 的讨论](https://www.depesz.com/)（通过原文外链进入）
