
# PostgreSQL `LogLogicalMessage` 

## 1. 文档目标

本文面向需要理解 PostgreSQL 逻辑复制/逻辑解码链路的开发人员，解释 `LogLogicalMessage` 的定位、内部实现、设计初衷和工程使用方式。

它不是普通 DML WAL，也不是 SQL 级逻辑复制协议里的表变更；它本质上是 PostgreSQL 为**逻辑解码插件提供的一条“通用消息通道”**：把一段任意 payload 写进 WAL，在物理恢复中几乎等价于 no-op，但在逻辑解码时可被专门识别并回调给输出插件。这个设计在最初的社区提案中就被明确表述为“generic WAL logical messages”，并说明这类记录对普通 WAL 回放基本是 no-op，而在 logical decoding 中会触发输出插件的专门 callback。([PostgreSQL][1])

---

## 2. 一句话定义

`LogLogicalMessage()` 是 PostgreSQL 内核中的一个函数，用来把**自定义逻辑消息**写入 WAL；这些消息随后可以被逻辑解码器读取，并通过输出插件的 `message_cb` / `stream_message_cb` 回调向下游输出。其对应的 SQL 接口是 `pg_logical_emit_message(...)`。([doxygen.postgresql.org][2])

---

## 3. 设计初衷

### 3.1 社区最初想解决什么问题

社区最初的提案写得很直接：希望引入一种“generic WAL logical messages”，允许用户把任意数据写入 WAL；对标准 WAL 回放来说这些记录基本是 no-op，但在逻辑解码时会被识别，并调用输出插件的专门 callback。提案同时指出，这些消息既可以是**事务型**的，也可以是**非事务型**的，还可以带一个 `prefix` 供插件快速识别。([PostgreSQL][1])

也就是说，它的设计目标不是替代表级变更复制，而是补足逻辑解码体系里“**非表行变更信息的传递能力**”。

### 3.2 为什么不做成“自定义 WAL redo”能力

社区讨论里还明确提到，如果扩展可以自定义 WAL 重放函数，那么扩展 bug 可能破坏 recovery、archive 和 physical replication；这被认为不可接受。因此才把“写 WAL 中的通用消息”和“物理恢复逻辑”分离开：**物理恢复不关心消息内容，逻辑解码才消费它**。([PostgreSQL][3])

这个点非常关键，因为它解释了 `LogLogicalMessage` 的架构边界：

* **物理层**：保证 WAL 兼容、恢复安全
* **逻辑层**：暴露自定义消息能力给解码插件

---

## 4. 对外接口

### 4.1 SQL 接口：`pg_logical_emit_message`

官方文档提供了两个 SQL 形式：

```sql
pg_logical_emit_message(transactional boolean, prefix text, content text [, flush boolean default false]) -> pg_lsn
pg_logical_emit_message(transactional boolean, prefix text, content bytea [, flush boolean default false]) -> pg_lsn
```

官方说明非常明确：该函数会“发出一个 logical decoding message”，用于“通过 WAL 向逻辑解码插件传递通用消息”；`transactional` 表示消息是否属于当前事务，`prefix` 用于让插件识别自己关心的消息，`content` 可以是 text 或 bytea，`flush` 仅控制**非事务型消息**是否立即 flush 到 WAL。([PostgreSQL][4])

### 4.2 SQL 到内核函数的映射

源码里 `pg_logical_emit_message_bytea()` 直接调用 `LogLogicalMessage(prefix, ..., transactional, flush)`；`pg_logical_emit_message_text()` 则复用 bytea 版本实现。([doxygen.postgresql.org][5])

因此以把它理解为：

```text
SQL 层 pg_logical_emit_message(...)
           ↓
内核层 LogLogicalMessage(...)
           ↓
写入一条 RM_LOGICALMSG_ID / XLOG_LOGICAL_MESSAGE WAL record
```

---

## 5. WAL 记录格式

`src/include/replication/message.h` 中定义了它的 WAL 载荷结构 `xl_logical_message`：

* `dbId`：消息发出时所在数据库 OID
* `transactional`：是否事务型
* `prefix_size`
* `message_size`
* 后续跟随 `message[]`，其中先放以 `\0` 结尾的 prefix，再放真正 payload。([doxygen.postgresql.org][2])

这意味着它在 WAL 中不是 SQL 文本结构，也不是 tuple 结构，而是一个**专门的消息 record**。

---

## 6. 写入流程：`LogLogicalMessage` 如何写 WAL

下面按源码流程解释。

### 6.1 事务型消息先强制拿到 XID

如果 `transactional=true`，函数会先断言当前在事务状态中，然后调用 `GetCurrentTransactionId()`，确保该消息绑定到当前事务。([doxygen.postgresql.org][6])

这一步的含义是：

* 事务型消息要跟事务提交/回滚语义绑定
* 它必须属于某个 xid 的变更流

### 6.2 组装 `xl_logical_message`

然后填充：

* `dbId = MyDatabaseId`
* `transactional`
* `prefix_size = strlen(prefix) + 1`
* `message_size = size`

源码特别写了注释：`prefix` 尾部的零字节是关键。([doxygen.postgresql.org][6])

### 6.3 使用标准 XLog 插入接口写 WAL

接着走标准 WAL 插入套路：

* `XLogBeginInsert()`
* `XLogRegisterData(&xlrec, SizeOfLogicalMessage)`
* `XLogRegisterData(prefix, xlrec.prefix_size)`
* `XLogRegisterData(message, size)`
* `XLogSetRecordFlags(XLOG_INCLUDE_ORIGIN)`
* `XLogInsert(RM_LOGICALMSG_ID, XLOG_LOGICAL_MESSAGE)` ([doxygen.postgresql.org][6])

这里有两个点需要注意：

#### 1）它是标准 WAL record

不是插件私有文件，也不是共享内存旁路，而是进入 WAL 主链路，所以天然带有 LSN、归档、复制、slot 保留等特征。([doxygen.postgresql.org][6])

#### 2）它允许携带 replication origin

源码调用了 `XLogSetRecordFlags(XLOG_INCLUDE_ORIGIN)`，注释写明“allow origin filtering”，也就是后续逻辑解码阶段可以按 origin 做过滤。([doxygen.postgresql.org][6])

### 6.4 `flush` 的真实语义

源码中只有在 **非事务型** 且 `flush=true` 时才调用 `XLogFlush(lsn)`。官方文档也说明：`flush` 对事务型消息没有效果，因为事务型消息会随着事务一起 flush。([doxygen.postgresql.org][6])

所以要记住：

* `transactional=true`：是否持久化由事务提交控制
* `transactional=false`：可通过 `flush=true` 立即确保 WAL 落盘

---

## 7. 物理恢复中的行为：为什么说它几乎是 no-op

`logicalmsg_redo()` 的源码几乎什么都不做，只检查 op code 是否正确，然后注释写明：

> “This is only interesting for logical decoding, see decode.c.” ([doxygen.postgresql.org][6])

社区原始提案也明确说，对标准 WAL replay 来说这些消息“basically noop”。([PostgreSQL][1])

这说明：

* 它**不会**像 heap insert/update 那样改数据页
* 它**不会**在 crash recovery 时重放成实际表变更
* 它的意义主要在逻辑解码侧

这正是它安全地集成进 PostgreSQL WAL 体系的关键原因。

---

## 8. 解码流程：`LogLogicalMessage` 如何被 logical decoding 看到

### 8.1 入口：`logicalmsg_decode()`

在 `decode.c` 中，`logicalmsg_decode()` 是这类 WAL record 的解码函数。它会：

1. 从 record 里取出 xid、origin、info
2. 调用 `ReorderBufferProcessXid(...)`
3. 如果 snapshot builder 还没到可解码状态，则直接返回
4. 取出 `xl_logical_message`
5. 检查 `dbId` 是否匹配当前 slot 所属数据库
6. 按 origin 做过滤
7. 对事务型消息调用 `SnapBuildProcessChange(...)`
8. 最终调用 `ReorderBufferQueueMessage(...)` 入 reorder buffer。([doxygen.postgresql.org][7])

### 8.2 为什么非事务型消息要拿 snapshot

源码注释明确写道：对事务型消息不需要单独 snapshot，使用 ReorderBuffer 维护的常规事务 snapshot；但对**非事务型消息**，会调用 `SnapBuildGetOrBuildSnapshot()`。([doxygen.postgresql.org][7])

这说明 PostgreSQL 在设计上仍然要求逻辑解码输出维持一致的“可见性上下文”，而不是看到 WAL 就不加约束地立即吐给插件。

### 8.3 进入 ReorderBuffer

`logicalmsg_decode()` 最后调用：

```c
ReorderBufferQueueMessage(rb, xid, snapshot, lsn, transactional, prefix, message_size, message)
```

把消息作为一种 change 排入 ReorderBuffer。([doxygen.postgresql.org][7])

这一步意义非常大：

* 它说明 logical message 并不是脱离 reorder buffer 的旁路消息
* 事务型消息会和同事务的 DML 一起重组、排序、提交输出
* 因此它天然能与事务边界保持一致

---

## 9. 输出插件如何接收它

官方文档在 output plugin callbacks 一节中定义了 `message_cb`：

```c
typedef void (*LogicalDecodeMessageCB)(
    struct LogicalDecodingContext *ctx,
    ReorderBufferTXN *txn,
    XLogRecPtr message_lsn,
    bool transactional,
    const char *prefix,
    Size message_size,
    const char *message);
```

文档说明：

* 当 logical decoding message 被解码时会调用它
* 非事务型消息且尚未分配 XID 时，`txn` 可能为 `NULL`
* `prefix` 是任意的 null-terminated 前缀
* 建议用扩展名/插件名保证 prefix 唯一。([PostgreSQL][8])

如果开启大事务流式传输，还存在 `stream_message_cb`，用于在 streamed block 中发送 generic message。([PostgreSQL][8])

这也解释了为什么它适合做：

* 事务性业务事件
* DDL 元信息事件
* 审计附加信息
* Outbox/CDC 元数据

---

## 10. 它如何接入内建逻辑复制 `pgoutput`

### 10.1 `pgoutput` 已经支持消息回调

`_PG_output_plugin_init()` 中，`pgoutput` 把 `message_cb` 和 `stream_message_cb` 都绑定到了 `pgoutput_message`。([doxygen.postgresql.org][9])

### 10.2 但默认不发送，必须显式打开 `messages` 选项

官方协议文档说明：在 `START_REPLICATION ... LOGICAL` 使用 `pgoutput` 时，可以传入 `messages` 选项；该选项是一个布尔值，用于启用发送由 `pg_logical_emit_message` 写入的 messages。([PostgreSQL][10])

这点很重要：
**有能力，不代表默认生效。**

### 10.3 `pgoutput_message()` 做了什么

`pgoutput_message()` 的逻辑大致是：

1. 读取 `PGOutputData`
2. 如果 `data->messages` 没开，直接返回
3. 流式模式下记录 xid
4. 对事务型消息，如尚未发送 BEGIN，则先发送 BEGIN
5. `OutputPluginPrepareWrite(ctx, true)`
6. 调用 `logicalrep_write_message(...)`
7. `OutputPluginWrite(ctx, true)` 把消息写给下游。([doxygen.postgresql.org][9])

### 10.4 线路协议中的 `M` 消息格式

官方文档对逻辑复制协议里的 Message 格式定义如下：

* `Byte1('M')`
* 可选 streamed xid
* flags：0 或 1（1 表示 transactional）
* message LSN
* prefix
* content length
* content bytes。([PostgreSQL][11])

这表明在网络上传输给订阅端时，逻辑消息已经成为协议中一个正式消息类型，而不是私有扩展字段。([PostgreSQL][11])

---

## 11. 内建订阅端为何“看得到但默认不用”

PostgreSQL 订阅端 `apply_dispatch()` 在收到 `LOGICAL_REP_MSG_MESSAGE` 时，源码里的注释直接写道：

> “Logical replication does not use generic logical messages yet. Although, it could be used by other applications that use this output plugin.” ([doxygen.postgresql.org][12])

也就是说：

* `pgoutput` 可以发 `M`
* 订阅端 apply worker 能识别消息类型
* 但**内建 logical replication 目前并不会把 generic logical message 应用成任何对象操作**

所以现状是：

### 已实现

* 写入 WAL
* 被逻辑解码
* 可由 `pgoutput` 编码发送
* 协议层有正式 `M` 消息

### 未内建完成

* 订阅端把 `M` 转换成 DDL 执行或其他语义动作

这个结论对你们的 DDL 复制设计非常关键：
**你们可以复用前半段链路，但订阅端 apply 逻辑需要自己扩展。** ([doxygen.postgresql.org][12])

---

## 12. 它一般用于什么场景

### 12.1 最原生的场景：输出插件之间传递通用消息

官方文档对 `pg_logical_emit_message` 的定义就是：通过 WAL 向逻辑解码插件传递 generic messages。([PostgreSQL][4])

### 12.2 应用级事件与 CDC 元数据

在“为 pgoutput 增加 message 支持”的社区邮件里，提案者明确提到，他们已经用 `pg_logical_emit_message` 把**应用级事件**和 CDC 一起发送了约两年，希望在 pgoutput 获得 message 支持后，把这部分能力迁到内建链路中。([PostgreSQL][13])

这说明一个典型场景是：

* 表变更之外，还要伴随发送业务语义事件
* 且希望事件与数据变更共享事务顺序

### 12.3 DDL 复制的载体

虽然内建 logical replication 目前“不使用 generic logical messages yet”，但 output plugin 文档同时指出 `receive_rewrites` 这类能力对“处理 DDL replication 的插件”是有意义的，需要特殊处理。([PostgreSQL][8])

工程上，这意味着：

* 如果你要做 DDL 复制，`LogLogicalMessage` 是一个很自然的承载机制
* 它避免你自己发明另一套 WAL 类型和解码通路
* 更接近 PostgreSQL 社区已经存在的机制和讨论方向。([PostgreSQL][1])

### 12.4 审计、日志、心跳、slot 推进

官方并没有把这些都列成标准场景，但从社区和生态实践看，逻辑消息常被用作审计附加信息、应用日志事件、以及在无表变更时推进 slot 的辅助消息。社区讨论中也有人明确提到用 `pg_logical_emit_message` 作为消息机制的实际经验；另外官方升级文档把“logical decoding messages”与普通事务一起并列为需要复制完成的对象。([PostgreSQL][13])

---

## 13. 事务型与非事务型消息的语义差异


### 13.1 事务型消息

事务型消息：

* 绑定 xid
* 进入 reorder buffer
* 与同事务 DML 一起在 commit 时输出
* 若事务回滚，消息不会被交付。([doxygen.postgresql.org][6])

### 13.2 非事务型消息

非事务型消息：

* 在 logical decoding 读到 record 时即可输出
* 可以没有 txn/XID
* 若 `flush=true`，写入后可立即 `XLogFlush(lsn)`。([doxygen.postgresql.org][6])

### 13.3 如何选

工程建议：

* **需要与事务原子性保持一致**：选事务型
* **做心跳、推进 slot、无事务即时报送**：选非事务型
* **做 DDL 同步事件**：通常更适合事务型，除非你刻意设计成 autocommit/即时生效语义

---

## 14. 在逻辑复制全流程中的位置

可以把它放到如下总链路里理解：

```text
上层 SQL / 内核模块
    ↓
pg_logical_emit_message() / LogLogicalMessage()
    ↓
生成 RM_LOGICALMSG_ID / XLOG_LOGICAL_MESSAGE WAL record
    ↓
walsender / logical decoding 读取 WAL
    ↓
decode.c::logicalmsg_decode()
    ↓
ReorderBufferQueueMessage()
    ↓
输出插件 message_cb / stream_message_cb
    ↓
pgoutput_message()
    ↓
logicalrep_write_message()
    ↓
复制协议 'M' 消息
    ↓
订阅端 apply_dispatch()
    ↓
当前内建实现：识别但不处理
```

其中：

* “逻辑流复制协议使用 `pgoutput`，并且 `messages` 参数控制是否把 `pg_logical_emit_message` 写入的消息发送出去”是官方文档定义的。([PostgreSQL][10])
* `logicalmsg_decode()` 被 `XLogSendLogical()`、`pg_logical_slot_get_changes_guts()` 等调用路径引用，说明无论是流复制接口还是 SQL 读 slot 接口，都会经过这条解码逻辑。([doxygen.postgresql.org][7])

---

## 15. 对 DDL 复制方案的意义

### 15.1 为什么它很适合作为 DDL 复制的“消息载体”

如果你们的目标是：

* 自动捕获 DDL
* 保留事务顺序
* 走现有 slot / WAL / logical decoding / pgoutput 通路
* 避免自己扩展一套新的物理恢复语义

那么 `LogLogicalMessage` 非常合适，因为它正是为“**在 WAL 中写入只供逻辑层消费的通用消息**”设计的。([PostgreSQL][1])

### 15.2 但它本身不等于“DDL 复制已经完成”

必须注意两点：

#### 1）`LogLogicalMessage` 只解决“发送”

它解决的是：

* 如何进入 WAL
* 如何被逻辑解码
* 如何通过协议传出去

#### 2）它不解决“订阅端执行”

内建 apply worker 当前对 `LOGICAL_REP_MSG_MESSAGE` 直接跳过。要做 DDL 复制，你仍需自定义：

* 消息 payload 格式
* 过滤与路由规则
* apply 端执行器
* 错误恢复与幂等策略。([doxygen.postgresql.org][12])

所以更准确地说：

> `LogLogicalMessage` 是 DDL 复制方案中的**传输底座**，不是完整方案本身。

---

## 16. 使用它时的边界与注意事项

### 16.1 prefix 要求唯一

源码注释和输出插件文档都建议 prefix 需要足够唯一，最好用扩展名或插件名，避免多个模块消息冲突。([doxygen.postgresql.org][6])

### 16.2 它会写 WAL，因此不是“零成本”

它既然进入 WAL，就会占用：

* WAL 空间
* slot 保留空间
* 复制带宽
* 解码/发送 CPU

社区里也有人明确提到，`pg_logical_emit_message` 会“pollute the wal files”，本质上就是会增大 WAL。([PostgreSQL][14])

所以它适合承载**关键控制消息、元信息、事件**，不适合替代大批量普通数据复制。

### 16.3 不要误解为“物理恢复可重放业务语义”

它在物理恢复中基本 no-op，不会自动把消息内容执行成表修改、DDL 或其他对象操作。([doxygen.postgresql.org][6])

### 16.4 与内建 publication/subscription 的关系

内建 pgoutput 能发送消息，但只有在 `messages` 选项打开时才会输出；而内建 subscriber 目前不消费这些 generic logical messages。([PostgreSQL][10])

因此若你们要把它纳入产品级 DDL 复制，通常需要：

* 发布端扩展 message payload
* 订阅端扩展 apply_dispatch 或外围消费器
* 或者使用自定义 output plugin / 自定义消费者

---

## 17. 几个常见误区

### 误区 1：`LogLogicalMessage` 就是写一条 SQL 到 WAL

它写的是专门的 `xl_logical_message` 结构，而不是 SQL 语句对象。payload 可以是任意字节。([doxygen.postgresql.org][2])

### 误区 2：写了消息，订阅端就会自动执行

内建逻辑复制协议里虽然有 `M` 消息，但当前 apply worker 明确不使用 generic logical messages。([PostgreSQL][11])

### 误区 3：它会影响崩溃恢复逻辑

它被设计成物理恢复几乎 no-op，只在 logical decoding 中有意义。([doxygen.postgresql.org][6])

### 误区 4：非事务型消息也一定属于事务

文档明确说非事务型消息场景下 `txn` 甚至可能为 `NULL`。([PostgreSQL][8])

---

## 18. 总结

`LogLogicalMessage` 的本质可以概括为一句话：

> **它是 PostgreSQL 核心提供的一种“把自定义逻辑事件写入 WAL，并交给逻辑解码插件消费”的机制。**

它的关键价值在于：

* 使用标准 WAL 插入链路
* 对物理恢复安全
* 对逻辑解码可见
* 支持事务型/非事务型两种语义
* 能经由 `pgoutput` 转成协议层 `M` 消息发送出去
* 非常适合作为 DDL 元信息、业务事件、审计元数据等“非表行变更”的传输底座。([doxygen.postgresql.org][6])

但同时也必须明确：

* 它不是完整的 DDL 复制方案
* PostgreSQL 内建 subscriber 目前不会消费 generic logical message
* 真正要做 DDL 复制，还需要你们自己定义 apply 侧执行语义。([doxygen.postgresql.org][12])

---

# 19. 官方与社区参考资料

## 官方文档

1. `pg_logical_emit_message` 官方说明
   PostgreSQL 18 文档，System Administration Functions。([PostgreSQL][4])

2. Logical Decoding Concepts
   解释 logical decoding 的整体定位。([PostgreSQL][15])

3. Logical Decoding Output Plugins
   包含 `message_cb` / `stream_message_cb` 的官方回调定义。([PostgreSQL][8])

4. Logical Streaming Replication Protocol
   说明 `pgoutput` 的 `messages` 选项。([PostgreSQL][10])

5. Logical Replication Message Formats
   说明协议层 `M` 消息格式。([PostgreSQL][11])

## 官方源码说明

1. `src/include/replication/message.h`
   `xl_logical_message` 结构与 `LogLogicalMessage` 声明。([doxygen.postgresql.org][2])

2. `src/backend/replication/logical/message.c`
   WAL 写入与 redo no-op。([doxygen.postgresql.org][6])

3. `src/backend/replication/logical/decode.c`
   `logicalmsg_decode()` 解码路径。([doxygen.postgresql.org][7])

4. `src/backend/replication/logical/reorderbuffer.c`
   `ReorderBufferQueueMessage()` 入队。([doxygen.postgresql.org][16])

5. `src/backend/replication/pgoutput/pgoutput.c`
   `pgoutput_message()` 把消息写入复制协议。([doxygen.postgresql.org][9])

6. `src/backend/replication/logical/worker.c`
   内建订阅端当前忽略 `LOGICAL_REP_MSG_MESSAGE`。([doxygen.postgresql.org][12])

7. `src/backend/replication/logical/logicalfuncs.c`
   SQL 接口到 `LogLogicalMessage` 的映射。([doxygen.postgresql.org][5])

## 社区邮件与讨论

1. 最初设计提案：**Proposal: Generic WAL logical messages**
   最清楚地说明了设计初衷。([PostgreSQL][1])

2. 设计讨论：为什么不允许扩展自定义 WAL replay 破坏恢复
   解释为何设计成“物理 no-op、逻辑消费”。([PostgreSQL][3])

3. `pgoutput` 增加 message 支持的讨论
   说明真实使用场景：把应用级事件与 CDC 一起发送。([PostgreSQL][13])

4. 协议文档修订讨论
   说明 `Message` 格式后来还补充过文档。([PostgreSQL][17])

---

如果你需要，我下一步可以把这份内容继续整理成**“面向你们 DDL 复制方案的定制版培训文档”**，专门补一章：`ProcessUtility hook -> LogLogicalMessage -> pgoutput -> 订阅端 apply 扩展` 的完整实现路径。

[1]: https://www.postgresql.org/message-id/5685F999.6010202%402ndquadrant.com "PostgreSQL: Proposal: Generic WAL logical messages"
[2]: https://doxygen.postgresql.org/message_8h_source.html "PostgreSQL Source Code: src/include/replication/message.h Source File"
[3]: https://www.postgresql.org/message-id/CANP8%2BjLftMGHSMTTKsJBcXvR%3DZv7kNGaE0HVHcbJ-XzFaQs0Vw%40mail.gmail.com "PostgreSQL: Re: Proposal: Generic WAL logical messages"
[4]: https://www.postgresql.org/docs/current/functions-admin.html?utm_source=chatgpt.com "Documentation: 18: 9.28. System Administration Functions"
[5]: https://doxygen.postgresql.org/logicalfuncs_8c_source.html "PostgreSQL Source Code: src/backend/replication/logical/logicalfuncs.c Source File"
[6]: https://doxygen.postgresql.org/message_8c_source.html "PostgreSQL Source Code: src/backend/replication/logical/message.c Source File"
[7]: https://doxygen.postgresql.org/decode_8c.html "PostgreSQL Source Code: src/backend/replication/logical/decode.c File Reference"
[8]: https://www.postgresql.org/docs/current/logicaldecoding-output-plugin.html "PostgreSQL: Documentation: 18: 47.6. Logical Decoding Output Plugins"
[9]: https://doxygen.postgresql.org/pgoutput_8c.html "PostgreSQL Source Code: src/backend/replication/pgoutput/pgoutput.c File Reference"
[10]: https://www.postgresql.org/docs/current/protocol-logical-replication.html "PostgreSQL: Documentation: 18: 54.5. Logical Streaming Replication Protocol"
[11]: https://www.postgresql.org/docs/current/protocol-logicalrep-message-formats.html "PostgreSQL: Documentation: 18: 54.9. Logical Replication Message Formats"
[12]: https://doxygen.postgresql.org/backend_2replication_2logical_2worker_8c_source.html "PostgreSQL Source Code: src/backend/replication/logical/worker.c Source File"
[13]: https://www.postgresql.org/message-id/CAOXUAcKDddXVVMqW%2BfQUCYoskS_LX14fdf7RvySw3f7bTTV6NQ%40mail.gmail.com "PostgreSQL: Re: Any objections to implementing LogicalDecodeMessageCB for pgoutput?"
[14]: https://www.postgresql.org/message-id/CAGSzHa0BLiGQ_xb5en%2BSNJk4cV9DqUUY7VvK-Uef0QhC%3DZKcqQ%40mail.gmail.com?utm_source=chatgpt.com "Re: pg_notify contention"
[15]: https://www.postgresql.org/docs/current/logicaldecoding-explanation.html?utm_source=chatgpt.com "Documentation: 18: 47.2. Logical Decoding Concepts"
[16]: https://doxygen.postgresql.org/reorderbuffer_8c_source.html "PostgreSQL Source Code: src/backend/replication/logical/reorderbuffer.c Source File"
[17]: https://www.postgresql.org/message-id/cc70956c-e578-e54f-49e6-b5d68c89576f%40gmx.de "PostgreSQL: Doc patch for Logical Replication Message Formats (PG14)"
