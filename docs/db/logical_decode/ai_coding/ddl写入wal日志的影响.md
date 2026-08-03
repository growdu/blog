这个问题非常关键，而且是**内核方案必须回答清楚的两个核心风险**：

> 1️⃣ 会不会导致 WAL 暴增
> 2️⃣ 会不会破坏 WAL 兼容性

我分别给你**结论 + 原理 + 定量判断 + 风险控制方案**。

---

# 一、结论（先说清楚）

## ✅ 1. WAL 不会“失控暴增”，但会**可控增加**

* 增量主要来自 **DDL SQL 文本 / payload**
* 对 OLTP 场景影响 **非常小**
* 对 DDL-heavy 场景需要优化（可控）

---

### ✅ 2. 不会破坏 WAL 兼容性（前提：用现有机制）

如果你用的是：

```c
LogLogicalMessage(..., RM_LOGICALMSG_ID)
```text
👉 那么：

> ✔ WAL 格式完全兼容
> ✔ crash recovery 不受影响
> ✔ 旧版本不会崩（只是忽略 message）

---

# 二、WAL 是否会暴增（深入分析）

---

## 1️⃣ 你到底往 WAL 里多写了什么？

你新增的是：

```text
XLOG_LOGICAL_MESSAGE
  prefix = "pg_ddl"
  payload = LogicalDDLCommand（二进制）
```text
👉 本质：

> **每个 DDL 多一条 WAL record**

---

## 2️⃣ 单条 DDL 大小估算

假设：

```sql
CREATE TABLE t1 (
  id int,
  name text
);
```text
payload 大致：

| 项               | 大小       |
| --------------- | -------- |
| header          | ~40B     |
| pubids          | ~8B      |
| command_tag     | ~16B     |
| normalized_sql  | ~80~200B |
| object_identity | ~32B     |

👉 合计：

```text
≈ 150B ~ 400B
```text
---

## 3️⃣ 对比 WAL 本身大小

一个普通 INSERT：

```text
heap_insert WAL ≈ 50B ~ 200B
```text
一个 UPDATE：

```text
≈ 100B ~ 300B
```text
---

👉 结论：

> 一条 DDL ≈ 几条 DML WAL 的量级

---

## 4️⃣ 关键点：DDL 频率极低

现实生产：

| 类型            | QPS           |
| ------------- | ------------- |
| INSERT/UPDATE | 1000 ~ 100万/s |
| DDL           | 0 ~ 1/s（甚至更低） |

---

👉 所以：

```text
WAL 增量 ≈ 忽略不计（绝大多数场景）
```text
---

## 5️⃣ 真正可能膨胀的场景

只有两种情况需要警惕：

---

### ❗场景1：自动化系统疯狂 DDL

例如：

```text
每秒 CREATE TABLE / DROP TABLE
```text
👉 会产生：

```text
DDL WAL ≈ 300B * N
```text
---

### ❗场景2：超长 SQL

```sql
CREATE TABLE t (... 500列 ...)
```text
👉 SQL 本身可能：

```text
10KB+
```text
---

👉 但注意：

这本来就已经存在：

```text
log_statement = ddl
```text
也会记录类似大小

---

# 三、如何控制 WAL 增长（优化建议）

---

## ✅ 优化1：不要无脑存原 SQL

你现在设计：

```text
query_string
normalized_sql
```text
👉 建议：

| 字段             | 是否必须         |
| -------------- | ------------ |
| normalized_sql | ✅ 必须         |
| query_string   | ❌ 可选（debug用） |

---

👉 可以加参数：

```text
ddl_include_query = off
```text
---

## ✅ 优化2：压缩 payload（可选）

可以：

```c
pglz_compress(payload)
```text
👉 对长 SQL 效果很好：

```text
10KB → 2KB
```text
---

## ✅ 优化3：结构化替代 SQL（高级优化）

未来可以：

```json
{
  "type": "CREATE_TABLE",
  "columns": [...]
}
```text
👉 比 SQL 小很多

---

# 四、WAL 兼容性问题（重点）

---

## 1️⃣ 你有没有改变 WAL 格式？

👉 没有 ❗（关键）

你使用：

```c
RM_LOGICALMSG_ID
XLOG_LOGICAL_MESSAGE
```text
这是 PostgreSQL 已存在的 WAL record 类型：

```c
PG_RMGR(RM_LOGICALMSG_ID, "LogicalMessage", ...)
```text
---

👉 意味着：

| 项          | 结果     |
| ---------- | ------ |
| WAL 格式     | ✅ 不变   |
| redo       | ✅ 不受影响 |
| pg_waldump | ✅ 可识别  |
| 旧版本        | ✅ 可跳过  |

---

## 2️⃣ crash recovery 是否受影响？

不会。

因为：

```c
logicalmsg_redo(...) { /* no-op */ }
```text
👉 说明：

> 这种 WAL record **不参与物理恢复**

---

## 3️⃣ 旧版本兼容性

假设：

* 主库：你改过（支持DDL复制）
* 备库：旧版本

---

👉 行为：

```text
WAL → 备库
遇到 XLOG_LOGICAL_MESSAGE
→ 忽略
```text
---

✔ 不会崩
✔ 不会错误恢复
✔ 只是丢失DDL复制能力

---

## 4️⃣ replication protocol 兼容性

你新增：

```text
'D' message
```text
---

👉 必须做：

```text
proto_version >= N
```text
否则：

👉 老 subscriber 收到未知 message 会报错

---

👉 正确做法：

```text
START_REPLICATION ... (proto_version=5, ddl=on)
```text
---

# 五、真正的风险点（你必须注意）

---

## ❗1. WAL 膨胀不是最大问题

真正风险是：

```text
logical slot retention
```text
---

### 场景：

* subscriber 挂了
* slot 卡住
* WAL 无法 recycle

---

👉 现在：

```text
WAL = DML + DDL
```text
---

👉 你的 DDL 会：

* 延长 WAL 生命周期
* 但不是主要因素（DML 才是）

---

## ❗2. 超大 DDL 导致 WAL segment 膨胀

极端：

```sql
CREATE TABLE t (... 10000 columns ...)
```text
👉 payload = 100KB+

---

👉 会导致：

* WAL segment 快速切换
* replication lag

---

👉 解决：

```text
max_ddl_message_size
```text
---

## ❗3. 逻辑复制 replay 风险（比 WAL 更重要）

不是 WAL 问题，而是：

```text
DDL replay 失败 → 停订阅
```text
---

# 六、总结一句话

👉 你的方案在 WAL 层面的影响是：

```text
✔ 增加 WAL（但很小）
✔ 不改变 WAL 格式
✔ 不影响 crash recovery
✔ 不影响物理复制
✔ 对 logical slot 有轻微压力（但可控）
```text
---

# 七、最终建议（非常关键）

如果你要上线这个功能，我建议你必须加这 4 个保护：

---

## ✅ 1. WAL 控制参数

```text
max_ddl_message_size
ddl_include_query = off
```text
---

## ✅ 2. payload 压缩（建议）

---

## ✅ 3. proto_version gating

---

## ✅ 4. publication 限制

一期只允许：

```text
table + index
```text
---

# 八、如果你要更深入（下一步）

我可以帮你继续做两个非常关键的点：

---

## 👉 1. pgoutput 如何发送 DDL（完整实现）

包括：

* prefix 匹配
* 转成 'D' message
* proto negotiation

---

## 👉 2. apply worker 如何执行DDL（最复杂部分）

包括：

* 事务顺序
* 幂等处理
* 错误恢复
* search_path 问题
