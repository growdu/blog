# 逻辑复制系统表支持DDL实现问题

1. 逻辑解码会过滤掉系统表，不支持系统表进行逻辑解码；
2. pglogical使用的是用户表，并使用user_catalog_table=true;

黎哥，
目前apply的流程基本跑通了。但是在做的过程中发现使用新增系统表这种方式总感觉比较奇怪，侵入性修改很严重。
然后后面我又查了下资料和社区的讨论，发现社区之前就预留了写逻辑日志的接口LogLogicalMessage，可以直接利用LogLogicalMessage来写入自定义的wal日志，并且天生就集成到了逻辑复制的流程里。有时间你可以看看。
内网我提交了两版代码，分支分别是ddl_with_wal和ddl_with_catalog,你有时间可以看看。
按目前的实现和修改来看，我觉得写wal日志这种方式更好一点，与pg更契合，侵入性修改更小一些。

1.看一下v3的逻辑复制实现和相关的问题处理；
2.babelfish是否支持spi；

## 社区推进的方向

### 结构化DDL

“结构化 DDL”本质上不是把

```sql
ALTER TABLE t ADD COLUMN c int;
```text
当成一段字符串发出去，而是把它拆成**带语义的结构化对象**，让订阅端按“对象类型 + 操作类型 + 参数”去理解和执行。社区这些年讨论的方向，整体上就是：

> **捕获 DDL → 规范化/去解析成结构化表示 → 写入专用逻辑日志/WAL → 解码发送 → 订阅端按结构化语义 apply**

而不是单纯把原始 SQL 用 `LogLogicalMessage` 直接透传。([wiki.postgresql.org][1])

---

## 1. 为什么要“结构化”

社区讨论里反复提到两个目标：

第一，**订阅端可以对命令做再处理**，例如 schema/name mapping、过滤未发布对象、拆分混合命令。邮件里明确提到，可以生成一种 command representation，让订阅端按通用规则任意处理；也提到通过 deparser 可以把 `DROP TABLE table_pub, table_unpub` 拆成更细粒度命令，只复制发布对象相关部分。([PostgreSQL][2])

第二，**适配异构复制或版本差异**。AWS/Fujitsu 的 DDL 复制设计材料里直接写到，structured representation facilitates heterogeneous replication，也把 “schema/name mapping” 和 “auto-fix DDL syntax incompatibility” 列为目标场景。

所以结构化 DDL 的核心动机不是“更好看”，而是为了让复制链路理解 DDL 的**语义**，而不是只看到一段 SQL 文本。([PostgreSQL][2])

---

## 2. 典型实现方式是什么样

社区讨论里没有一个已经合入主线的最终版本，但从 wiki、设计 PDF 和邮件看，比较清晰的实现方式可以分成 5 步。

### 第一步：捕获 DDL

社区讨论过两条路：

* **Inline 捕获**，即在 `ProcessUtilitySlow` 这类执行路径里直接抓 DDL
* **Event Trigger 捕获**，复用现有 event trigger 机制

设计材料里把这两种方案都列出来了；其中也明确指出 event trigger 目前只覆盖 DDL 的一个子集，如果走这条路还需要扩展支持面。

这意味着如果要做“完整结构化 DDL”，更稳的办法通常还是**内核 utility 执行路径内联捕获**；event trigger 更像是实现原型或覆盖部分场景的手段。这个判断是基于社区材料里对两条路线优缺点的描述做出的工程推断。

### 第二步：把 DDL 变成“结构化命令”

这一步是关键。不是保留原始 SQL，而是生成一个“命令对象”，至少带上：

* 命令类型，如 `CREATE TABLE`、`ALTER TABLE`
* 目标对象类型，如 table/index/function/type
* 目标对象标识，如 schema、name、可能还有 relid
* 参数列表，如列定义、约束、默认值、是否重命名等

社区的设计材料里展示过一个拟议的 WAL 记录结构 `xl_logical_ddl_message`，字段包括 `dbId`、`relid`、`DeparsedCommandType cmdtype`、`message_size` 和 payload；这说明当时的方向已经不是“只有一段 SQL”，而是至少要把**命令类型**和**目标对象**显式放进消息头里。

### 第三步：deparse / normalize

社区邮件里多次提到 **deparser**。这里的意思不是简单 pretty-print，而是：

* 把 parse tree / utility stmt 变成**规范化后的命令表示**
* 必要时补全 schema name，避免依赖 `search_path`
* 过滤掉未发布对象
* 把一个混合命令拆成多个可独立复制的命令
* 对某些不安全或不支持的表达式直接拒绝发布

邮件里举的例子很典型：
通过 deparser 可以补全 schema name，这样订阅端不需要和发布端保持相同 `search_path`；也可以把 `CREATE TABLE AS` 拆出纯建表部分，避免在订阅端重新执行查询；对于带 volatile function 的命令，可以在 deparser 阶段识别并过滤。([PostgreSQL][2])

也就是说，结构化 DDL 的“结构化”并不一定要求最后传输的是 JSON/Protobuf；更重要的是**在发布端先把 DDL 规范化成可判定、可过滤、可映射的内部表示**。([PostgreSQL][2])

### 第四步：写入专用 WAL/逻辑日志格式

社区在 DDL 复制设计里提出过“为 DDL 消息增加新的 WAL 记录类型”，而不是直接沿用泛化的 `LogLogicalMessage`。设计材料里明确写了 “A new WAL record for DDL messages / XLOG_LOGICAL_DDL_MESSAGE”，并给出包含 `cmdtype`、`relid` 等字段的结构草案。

这恰恰说明社区倾向于：

* **message 作为运输层思路可以借鉴**
* 但 DDL 最好有自己的**专用结构化 record 格式**

因为这样解码端不需要先猜 payload 是什么，也更容易做过滤、协议扩展和向后兼容。这个结论是对设计草案结构的直接推断。

### 第五步：订阅端按语义 apply

订阅端不再是“拿到 SQL 就 `SPI_execute`”，而是：

1. 读取结构化消息头
2. 根据对象类型和命令类型做合法性检查
3. 做 schema/name mapping
4. 检查依赖是否满足
5. 重建本地等价命令并执行，或直接调用更底层的对象创建/修改接口

这一步社区没有主线代码，但设计目标很清楚：支持 selective DDL replication、schema/name mapping、语法不兼容修复、异构复制。只有结构化 apply 才有可能做到这些。([PostgreSQL][2])

---

## 3. 一个更具体的“结构化 DDL”数据模型

如果你们自己实现，比较合理的内部模型大致会长这样：

```text
DDLRecord
  - dbid
  - xid
  - seqno
  - object_class      (table/index/sequence/function/type/...)
  - command_type      (create/alter/drop/rename/...)
  - target
      - schema
      - name
      - relid/object identity
  - subcommands[]     (尤其用于 ALTER TABLE)
  - options
      - if_exists
      - if_not_exists
      - cascade/restrict
  - mapping_hints
  - original_sql      (可选，仅审计/报错用)
```text
其中最关键的是 `subcommands[]`。因为很多真正麻烦的 DDL，尤其是 `ALTER TABLE`，本身就是一个“容器命令”，里面可能混着：

* add column
* alter type
* set default
* add constraint
* rename column

如果只用一条 SQL 文本，订阅端很难做细粒度过滤和重写；而结构化以后，才能按子动作逐项判断。这个部分是实现建议，不是当前 PostgreSQL 已合入的官方结构。社区草案只明确到了 `cmdtype`、`relid`、payload 这一级。

---

## 4. 它和“直接用 LogLogicalMessage 发 SQL”有什么区别

差别主要在 4 个方面。

### 4.1 过滤粒度不同

直接发 SQL：

* 很难只复制其中一部分对象
* 很难拆分混合命令

结构化 DDL：

* 可以按对象粒度过滤
* 可以拆成多条独立命令发送或应用

这正是社区邮件里 deparser 方案想解决的问题。([PostgreSQL][2])

### 4.2 mapping 能力不同

直接发 SQL：

* 订阅端往往要模拟发布端 `search_path`
* schema 改名、对象重映射都难

结构化 DDL：

* 可以先做 schema/name mapping，再生成本地命令

这也是社区明确列出的目标。([PostgreSQL][2])

### 4.3 异构兼容性不同

直接发 SQL：

* 跨版本、异构目标更难处理

结构化 DDL：

* 可以在订阅端按目标系统规则重新翻译

设计材料里直接把 heterogeneous replication 作为 structured representation 的受益场景。

### 4.4 安全性和可控性不同

直接发 SQL 更像“远端执行任意命令”。
结构化 DDL 更像“接收一个受约束的 schema-change 事件”，订阅端可以只允许部分动作类型。这个点是工程推断，但与社区强调 filtering、mapping、publishability check 的方向一致。([PostgreSQL][2])

---

## 5. 社区讨论里，结构化 DDL最难的地方是什么

不是“怎么传”，而是“怎么定义可复制语义”。

从现有讨论能看到几个难点：

* **table rewrite**：有些 `ALTER TABLE` 会触发表重写，处理不当会让主备数据不一致；评审邮件里专门讨论了 rewrite insert 无法简单转成 update 的问题。([PostgreSQL][3])
* **volatile / non-immutable expressions**：这类表达式在订阅端重新执行可能得出不同结果，因此社区讨论里明确倾向于限制或过滤。([PostgreSQL][2])
* **event trigger 覆盖面不足**：如果捕获面不完整，就做不成普适方案。
* **initial schema sync 与增量 DDL 的衔接**：wiki 上把 initial schema sync 和 incremental sync 并列为两个主要部分，说明社区认为这两个问题必须一起考虑。([wiki.postgresql.org][1])

所以结构化 DDL 不是“把 SQL 换个格式发”这么简单，而是要给每类 DDL 定义：

* 能不能复制
* 复制粒度到哪里
* 什么前提下允许
* 订阅端如何等价应用

---

## 6. 如果你们自己做，推荐的实现路线

如果目标是**尽量贴近社区方向**，我建议是：

### 路线 A：轻量版

* 在 `ProcessUtility` 路径捕获 DDL
* 生成内部 `DeparsedCommand` / `DDLRecord`
* 先把 payload 编成 JSON 或二进制 TLV
* 仍然走 `LogLogicalMessage` 当运输层
* 订阅端自己扩展 apply

这个方案工程成本低，但“消息壳子”还是 generic message。

### 路线 B：社区风格版

* 内联捕获 DDL
* 做可发布性检查
* 用 deparser 生成规范化结构
* 定义专用 `XLOG_LOGICAL_DDL_MESSAGE`
* 解码阶段专门处理 DDL record
* 复制协议里增加 DDL message 类型
* apply 端做结构化执行

这更接近 wiki/PDF 里展示的方向，尤其是“专用 WAL 记录 + 结构化字段 + apply DDL”。

---

## 7. 一句话总结

结构化 DDL 的实现方式可以概括成：

> **不是复制原始 SQL，而是在发布端把 DDL 解析/去解析成可过滤、可映射、可重建的结构化命令，再通过专用 DDL 逻辑日志/WAL 发送给订阅端，由订阅端按语义重建并执行。**

[1]: https://wiki.postgresql.org/wiki/Logical_replication_of_DDLs "Logical replication of DDLs - PostgreSQL wiki"
[2]: https://www.postgresql.org/message-id/OS0PR01MB571684CBF660D05B63B4412C94AB9%40OS0PR01MB5716.jpnprd01.prod.outlook.com "PostgreSQL: RE: Support logical replication of DDLs"
[3]: https://www.postgresql.org/message-id/CAHut%2BPv9vPbUQc0fzrKmDkKOsS_bj-hup_E%2BsLHNEX%2B6F%2BSY5Q%40mail.gmail.com "PostgreSQL: Re: Support logical replication of DDLs"

### catalog-based replication

直接复制：

pg_class
pg_attribute
pg_type

检查apply worker中`apply_publication_sync_message_q`的实现逻辑来定位DDL未执行的原因