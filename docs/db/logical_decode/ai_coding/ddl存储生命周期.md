可以，下面我直接给你一版**接近 PostgreSQL patch 风格**的 `LogLogicalDDLMessage()` 实现草稿。它的设计核心是：**复用 PostgreSQL 现有 generic logical decoding message 的 WAL 记录格式与写入路径**。现有源码里，`xl_logical_message` 记录了 `dbId`、`transactional`、`prefix_size`、`message_size` 和 payload；`LogLogicalMessage()` 会走 `XLogBeginInsert()` / `XLogRegisterData()` / `XLogInsert(RM_LOGICALMSG_ID, XLOG_LOGICAL_MESSAGE)`，并带上 `XLOG_INCLUDE_ORIGIN` 标记。([doxygen.postgresql.org][1])

先说一句定位：

> `LogicalDDLCommand` 本身只是**后端内存里的瞬时结构**；真正持久化和被 logical decoding 看到的，是它**序列化后的 payload**，并且它会被写成一条 **transactional logical decoding message** 进入 WAL。`pg_logical_emit_message(transactional => true, ...)` 的官方文档也是这个语义：把 generic message 通过 WAL 提供给 logical decoding plugin。([PostgreSQL][2])

---

# 1. 设计选择

我建议不要重新发明一套新的 rmgr record，而是先在一期里直接封装现有 `LogLogicalMessage()`：

```c
XLogRecPtr LogLogicalMessage(const char *prefix,
                            const char *message,
                            size_t size,
                            bool transactional,
                            bool flush);
```

这个函数在当前 PostgreSQL 源码里已经存在，且底层就是往 `RM_LOGICALMSG_ID / XLOG_LOGICAL_MESSAGE` 写 WAL。`logicalmsg_redo()` 还是 no-op，因为这类记录主要是给 logical decoding 用的。([doxygen.postgresql.org][1])

所以你的 `LogLogicalDDLMessage()` 最合理的实现，是：

1. 把 `LogicalDDLCommand` 序列化成紧凑二进制 payload
2. 以固定 prefix，例如 `"pg_ddl"`
3. 调用 `LogLogicalMessage("pg_ddl", payload, len, true, false)`

其中 `transactional = true` 很关键，因为官方文档明确区分了 transactional 和 non-transactional logical messages。([PostgreSQL][2])

---

# 2. 推荐的数据结构

先定义一个内部版本化格式。不要直接把 C struct 原样 memcpy 到 WAL，因为对齐、字节序、版本演进都会出问题。

## 头文件：`src/include/replication/logicalddl.h`

```c
#ifndef PG_LOGICAL_DDL_H
#define PG_LOGICAL_DDL_H

#include "nodes/parsenodes.h"
#include "nodes/pg_list.h"
#include "postgres.h"
#include "utils/rel.h"

#define LOGICAL_DDL_PREFIX "pg_ddl"
#define LOGICAL_DDL_VERSION_1 1

typedef enum ReplicableDDLKind
{
	REPL_DDL_TABLE = 1,
	REPL_DDL_INDEX = 2,
	REPL_DDL_TRIGGER = 3,
	REPL_DDL_VIEW = 4,
	REPL_DDL_RULE = 5,
	REPL_DDL_SCHEMA = 6,
	REPL_DDL_FUNCTION = 7,
	REPL_DDL_TYPE = 8,
	REPL_DDL_DOMAIN = 9,
	REPL_DDL_EXTENSION = 10
} ReplicableDDLKind;

typedef struct LogicalDDLCommand
{
	ReplicableDDLKind kind;

	Oid			classid;
	Oid			objid;
	int32		objsubid;

	Oid			relid;		/* InvalidOid if not table-related */
	Oid			nspid;		/* InvalidOid if not namespace-related */

	char	   *command_tag;
	char	   *object_identity;
	char	   *query_string;    /* debug/log only */
	char	   *normalized_sql;  /* subscriber executes this */

	List	   *pubids;          /* List of Oid */
	uint32		flags;
	uint32		ddl_seqno;       /* sequence number within current xact */
} LogicalDDLCommand;

extern XLogRecPtr LogLogicalDDLMessage(const LogicalDDLCommand *cmd);
extern void SerializeLogicalDDLMessage(StringInfo out,
									   const LogicalDDLCommand *cmd);
extern LogicalDDLCommand *DeserializeLogicalDDLMessage(StringInfo in);

#endif
```

---

# 3. payload 序列化格式

我建议 message payload 自己再分成两层：

* **固定头**
* **变长字段**

格式建议：

```text
uint8   version
uint8   kind
uint16  reserved
uint32  flags
uint32  ddl_seqno

Oid     classid
Oid     objid
int32   objsubid
Oid     relid
Oid     nspid

uint32  npubids
Oid[]   pubids

cstring command_tag
cstring object_identity
cstring normalized_sql
cstring query_string
```

这样做的好处：

* 以后你加字段可以升 `version`
* apply 端和 pgoutput 端都能稳定反序列化
* 不依赖编译器布局

---

# 4. 序列化函数实现

## `src/backend/replication/logical/logicalddl.c`

```c
#include "postgres.h"

#include "access/xact.h"
#include "lib/stringinfo.h"
#include "nodes/pg_list.h"
#include "replication/logicalddl.h"
#include "replication/message.h"
#include "utils/builtins.h"

static void
append_string0(StringInfo out, const char *str)
{
	if (str == NULL)
		appendStringInfoChar(out, '\0');
	else
		appendBinaryStringInfo(out, str, strlen(str) + 1);
}

static char *
read_string0(StringInfo in)
{
	char   *start;
	int		len;

	if (in->cursor >= in->len)
		elog(ERROR, "invalid logical DDL message: unexpected end of message");

	start = in->data + in->cursor;
	len = strlen(start);

	if (in->cursor + len >= in->len)
		elog(ERROR, "invalid logical DDL message: unterminated string");

	in->cursor += len + 1;

	return pstrdup(start);
}

void
SerializeLogicalDDLMessage(StringInfo out, const LogicalDDLCommand *cmd)
{
	ListCell   *lc;
	uint32		npubids = list_length(cmd->pubids);

	resetStringInfo(out);

	pq_sendbyte(out, LOGICAL_DDL_VERSION_1);
	pq_sendbyte(out, (uint8) cmd->kind);
	pq_sendint16(out, 0); /* reserved */
	pq_sendint32(out, cmd->flags);
	pq_sendint32(out, cmd->ddl_seqno);

	pq_sendint32(out, cmd->classid);
	pq_sendint32(out, cmd->objid);
	pq_sendint32(out, cmd->objsubid);
	pq_sendint32(out, cmd->relid);
	pq_sendint32(out, cmd->nspid);

	pq_sendint32(out, npubids);
	foreach(lc, cmd->pubids)
	{
		Oid pubid = lfirst_oid(lc);
		pq_sendint32(out, pubid);
	}

	append_string0(out, cmd->command_tag);
	append_string0(out, cmd->object_identity);
	append_string0(out, cmd->normalized_sql);
	append_string0(out, cmd->query_string);
}
```

这里用 `StringInfo` 做 buffer，是因为它本来就是 PostgreSQL 内部最常用的变长缓冲区容器，后续 `pgoutput` 侧也方便复用同一格式。

---

# 5. 反序列化函数实现

```c
LogicalDDLCommand *
DeserializeLogicalDDLMessage(StringInfo in)
{
	LogicalDDLCommand *cmd;
	uint8		version;
	uint8		kind;
	uint32		flags;
	uint32		ddl_seqno;
	uint32		npubids;
	uint32		i;

	cmd = palloc0(sizeof(LogicalDDLCommand));

	version = pq_getmsgbyte(in);
	if (version != LOGICAL_DDL_VERSION_1)
		elog(ERROR, "unsupported logical DDL message version: %u", version);

	kind = pq_getmsgbyte(in);
	(void) pq_getmsgint(in, 2); /* reserved */

	flags = pq_getmsgint(in, 4);
	ddl_seqno = pq_getmsgint(in, 4);

	cmd->kind = (ReplicableDDLKind) kind;
	cmd->flags = flags;
	cmd->ddl_seqno = ddl_seqno;

	cmd->classid = (Oid) pq_getmsgint(in, 4);
	cmd->objid = (Oid) pq_getmsgint(in, 4);
	cmd->objsubid = pq_getmsgint(in, 4);
	cmd->relid = (Oid) pq_getmsgint(in, 4);
	cmd->nspid = (Oid) pq_getmsgint(in, 4);

	npubids = pq_getmsgint(in, 4);
	for (i = 0; i < npubids; i++)
	{
		Oid pubid = (Oid) pq_getmsgint(in, 4);
		cmd->pubids = lappend_oid(cmd->pubids, pubid);
	}

	cmd->command_tag = read_string0(in);
	cmd->object_identity = read_string0(in);
	cmd->normalized_sql = read_string0(in);
	cmd->query_string = read_string0(in);

	return cmd;
}
```

---

# 6. `LogLogicalDDLMessage()` 实现

这部分最核心。既然 PostgreSQL 现成的 `LogLogicalMessage()` 已经会把 message 写成 `XLOG_LOGICAL_MESSAGE` 记录，那我们就包一层，专门给 DDL 用。当前源码里这条路径最终会调用 `XLogInsert(RM_LOGICALMSG_ID, XLOG_LOGICAL_MESSAGE)`，并且对非事务型消息可按需 `XLogFlush(lsn)`；logical message 的 WAL 记录结构就是 `xl_logical_message`。([doxygen.postgresql.org][1])

```c
XLogRecPtr
LogLogicalDDLMessage(const LogicalDDLCommand *cmd)
{
	StringInfoData	buf;
	XLogRecPtr		lsn;

	/*
	 * DDL replication message must be transactional, otherwise
	 * it can be decoded outside commit order and break DDL/DML ordering.
	 */
	if (!IsTransactionState())
		elog(ERROR, "cannot emit logical DDL message outside transaction");

	/*
	 * Ensure the current top-level transaction has an XID assigned,
	 * so the logical message is tied to this transaction in decoding.
	 */
	(void) GetCurrentTransactionId();

	initStringInfo(&buf);
	SerializeLogicalDDLMessage(&buf, cmd);

	/*
	 * Reuse PostgreSQL's generic logical decoding message WAL record:
	 *   RM_LOGICALMSG_ID / XLOG_LOGICAL_MESSAGE
	 */
	lsn = LogLogicalMessage(LOGICAL_DDL_PREFIX,
							buf.data,
							buf.len,
							true,   /* transactional */
							false); /* no immediate flush needed */

	pfree(buf.data);

	return lsn;
}
```

这版实现的关键点有三个：

1. **必须在事务内调用**，否则报错。
2. **主动取一次 XID**，确保这个消息和当前事务绑定。
3. **transactional=true**，保证它按事务顺序被 logical decoding 看见。

这些做法和官方对 `pg_logical_emit_message(transactional, ...)` 的说明是一致的：transactional message 属于当前事务，而 non-transactional message 会被立即写出并尽快解码。([PostgreSQL][2])

---

# 7. 为什么这版实现靠谱

因为它完全踩在 PostgreSQL 已有机制上：

* generic logical decoding message 本来就是“通过 WAL 传给 logical decoding plugin 的消息”。([PostgreSQL][2])
* `LogLogicalMessage()` 底层已经把这类消息作为 `RM_LOGICALMSG_ID / XLOG_LOGICAL_MESSAGE` 写进 WAL。([doxygen.postgresql.org][3])
* `logicalmsg_redo()` 是 no-op，说明这类记录的主要消费者就是解码链路，而不是 crash redo 本身。([doxygen.postgresql.org][3])
* `pgoutput` 从 2021 年起已经支持把 logical decoding messages 发到复制流里，只是 built-in logical replication 还没有把这条能力用于通用 DDL 复制。([PostgreSQL][4])

所以你的 `LogLogicalDDLMessage()` 不是“另起炉灶”，而是把 DDL 嵌入现有的 logical message 通路。

---

# 8. 推荐调用位置

在 `ProcessUtility` 路径里，不是“刚看到 parse tree 就发”，而是：

1. 先识别出这是可复制 DDL
2. 构造 `LogicalDDLCommand`
3. 在 utility 执行成功后再调用 `LogLogicalDDLMessage(&cmd)`

伪代码：

```c
bool should_emit = false;
LogicalDDLCommand cmd;

memset(&cmd, 0, sizeof(cmd));

should_emit = GetLogicalDDLInfo(pstmt, queryString, context, &cmd);

standard_ProcessUtility(...);  /* 先真正执行 DDL */

if (should_emit)
	LogLogicalDDLMessage(&cmd);
```

这样可以避免“DDL 实际执行失败，但你已经写了复制消息”。

---

# 9. 一些实现细节建议

## 9.1 不要把 `query_string` 当唯一执行文本

`normalized_sql` 才是给 subscriber 真正执行的；`query_string` 更像调试字段。

## 9.2 `ddl_seqno` 很重要

一个事务里可能有多条 DDL。你后续做去重和 apply 顺序控制时，`ddl_seqno` 很有用。

## 9.3 `pubids` 建议直接带 Oid

比 publication name 更紧凑，也更接近发布端内部过滤逻辑。

## 9.4 prefix 固定

建议统一用：

```c
#define LOGICAL_DDL_PREFIX "pg_ddl"
```

这样 decode / pgoutput / apply 都容易识别。

---

# 10. 这段实现还缺什么

这只是“写 WAL”这一层。完整链路还差三块：

1. **`GetLogicalDDLInfo()`**
   从 parse tree 提取 `kind / relid / nspid / normalized_sql / pubids`

2. **pgoutput 侧识别并转发**
   在 message 路径里识别 prefix=`pg_ddl`，然后写成你定义的 `D` 协议消息

3. **apply worker 侧解析并执行**
   读回 payload，构造 `LogicalDDLCommand`，按事务顺序执行

---

# 11. 我建议你下一步直接做的文件

如果你现在真要开始 patch，我建议先落地这 3 个文件：

* `src/include/replication/logicalddl.h`
* `src/backend/replication/logical/logicalddl.c`
* `src/backend/tcop/utility.c` 里接入 `LogLogicalDDLMessage()`

然后再接 pgoutput / worker。

[1]: https://doxygen.postgresql.org/message_8h_source.html "PostgreSQL Source Code: src/include/replication/message.h Source File"
[2]: https://www.postgresql.org/docs/9.6/functions-admin.html "PostgreSQL: Documentation: 9.6: System Administration Functions"
[3]: https://doxygen.postgresql.org/message_8c_source.html "PostgreSQL Source Code: src/backend/replication/logical/message.c Source File"
[4]: https://www.postgresql.org/about/news/postgresql-weekly-news-april-11-2021-2195/ "PostgreSQL: PostgreSQL Weekly News - April 11, 2021"
