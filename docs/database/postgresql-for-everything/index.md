# PostgreSQL 万能论：为什么一家公司可以用它替代 Kafka、Redis、Elastic 与 ClickHouse

| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 翻译整理，原文作者 Dr. Raphael A. Bauer | 2026-08-21 |

> **本文为 Dr. Raphael A. Bauer 所写 *PostgreSQL for Everything* 一文的中文翻译整理**。
> - 原文链接：https://www.raphaelbauer.com/posts/postgresql-everything/
> - 原文发布时间：2024-02-14
> - 译者：本文用我自己的中文技术行文重写了原文观点，并在部分章节补充了 PostgreSQL 源码定位，便于读者自行深入查阅
> - 如有错译，请以原文为准

---

## 引子

"宇宙的终极答案不是 42，而是 PostgreSQL。"

这是一句玩笑话，但里面藏着一个真实的故事：在今天的技术栈里，PostgreSQL 已经强大到可以**同时扮演多种基础组件的角色**——全文检索、文档数据库、消息队列、时序库、向量库、缓存、文件存储、图数据库，乃至一些你不该拿数据库干的活（比如俄罗斯方块）。

如果你想让产品跑得快、运营得简单，PostgreSQL 几乎可以**替代一整套周边组件**。很多成功公司正在这么做。我们今天就来盘一盘，PG 到底能顶替什么、怎么顶替。

---

## 一、PostgreSQL 为什么"够格"做这一切？

在讨论"能不能替代 X"之前，先说清楚 PostgreSQL 本身的两大特质。

### 1.1 坚如磐石

PG 的稳定性在数据库圈里近乎"另类"：

- 30+ 年活跃开发的代码库，C 为主
- **MVCC 不阻塞读不阻塞写**，并发模型本身就让简单负载非常稳
- 主版本之间的兼容性强（从 PG 9 升到 PG 18 的 API 变化极小）
- 配套生态成熟：pgBackRest、pg_stat_statements、pgaudit、pg_hint_plan……

**稳定性 = 维护成本低**。这是 PG 替代一切的第一前提。

### 1.2 装、跑、扩——样样简单

```bash
# Debian/Ubuntu
sudo apt install postgresql
sudo systemctl start postgresql
```

```bash
# 容器化
docker run --name pg -e POSTGRES_PASSWORD=xxx -d postgres:18
```

```bash
# 云上一键
# AWS RDS、阿里云 PolarDB-PG、腾讯云 TDSQL-PG……
```

扩缩容也是老套路：

- **垂直扩**：改 `shared_buffers`、加 CPU、加大盘
- **水平扩**：逻辑复制 + 读写分离；或者用 Citus 这样的扩展做分片

> 译者注：PG 17 引入了**逻辑复制槽 failover**、**增量备份**等特性，让 HA 链路进一步简化；源码见 `src/backend/replication/logical/worker.c`。

---

## 二、简化你的整套 IT 架构

每一套外部组件都意味着：

- 多一套监控
- 多一套备份
- 多一套权限管理
- 多一份跨网络流量
- 多一份故障点

如果 PostgreSQL 能干，那把它合进 PG 的收益就**远大于性能上那点微小的差距**。

下面逐一拆解 PG 可以顶替谁、怎么顶替。

---

## 三、PostgreSQL 替代 Solr / Elastic：全文检索

**典型替代场景**：站内搜索、日志检索、文档检索。

### 3.1 原生能力

PG 自带 `tsvector` / `tsquery`：

```sql
-- 一行 SQL 建索引
ALTER TABLE articles
    ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title,'')), 'A') ||
        setweight(to_tsvector('english', coalesce(body,'')), 'B')
    ) STORED;

CREATE INDEX idx_search ON articles USING GIN (search_vector);

-- 查询
SELECT title, ts_rank(search_vector, query) AS rank
FROM articles, to_tsquery('english', 'postgres & replication') query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 10;
```

### 3.2 何时够用，何时不够

- ✅ **小到中等规模**（千万级文档）、典型 web 搜索：完全够用
- ✅ **语言支持**：英语、中文（用 `simple` 或 zhparser）、日韩……
- ⚠️ **超大规模 + 复杂聚合**：Elastic 的 inverted index + 分布式更适合
- ⚠️ **复杂相关性 + 机器学习打分**：Elastic / OpenSearch 的生态更丰富

> 译者注：PG 的 GIN 索引（`src/backend/access/gin/`）对 `tsvector` 的支持已经多年迭代成熟，足够替代大多数"塞个全文检索"的项目需求。

---

## 四、PostgreSQL 替代 MongoDB：JSON 支持

**典型替代场景**：半结构化数据、配置存储、事件流水。

### 4.1 两种类型：`json` 与 `jsonb`

```sql
CREATE TABLE events (
    id        bigserial PRIMARY KEY,
    created_at timestamptz DEFAULT now(),
    payload   jsonb NOT NULL
);

-- 索引 jsonb 字段
CREATE INDEX idx_payload_user ON events USING GIN ((payload -> 'user_id'));

-- 查询：找出 user_id = 'u123' 的事件
SELECT * FROM events
WHERE payload @> '{"user_id": "u123"}'
ORDER BY created_at DESC
LIMIT 50;

-- 更新：jsonb 局部修改
UPDATE events
SET payload = payload || '{"processed": true}'
WHERE id = 12345;
```

`jsonb` 是**二进制存储 + GIN 索引**，性能可与文档库一战。

### 4.2 何时够用

- ✅ 半结构化数据 + 偶尔改 schema
- ✅ 不需要 MongoDB 的水平 sharding 那一套
- ✅ 团队希望一套 SQL 解决所有查询

> ⚠️ **强 schema 验证**：从 PG 12 起 `JSON_SCHEMA` 验证可用（PG 15 改名为 `pg_jsonschema` 扩展）。

---

## 五、PostgreSQL 替代 Kafka / RabbitMQ：作为队列

**典型替代场景**：任务队列、事件驱动、定时任务。

### 5.1 PG 16+ 原生消息队列

从 PG 16 起，**`pg_queue` 内置**（早期版本由 `pgmq` 扩展提供）：

```sql
-- 创建队列
SELECT pgmq.create('orders');

-- 入队
SELECT pgmq.send('orders', jsonb_build_object('order_id', 12345, 'amount', 99));

-- 出队（带 visibility timeout）
SELECT * FROM pgmq.read('orders', visibility_timeout := 30, qty := 10);

-- 处理完确认
SELECT pgmq.delete('orders', msg_id := 1);
```

### 5.2 用 SKIP LOCKED 自己做队列

`SKIP LOCKED` 是 PG 9.5 引入的杀手锏，让"任务表当队列"非常自然：

```sql
-- worker 抢一条未处理的任务
BEGIN;

WITH next_task AS (
    SELECT id, payload
    FROM tasks
    WHERE status = 'pending'
    ORDER BY created_at
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
UPDATE tasks t
SET status = 'processing', started_at = now()
FROM next_task n
WHERE t.id = n.id
RETURNING t.id, t.payload;

-- ... 处理任务 ...

COMMIT;  -- 自动释放锁
```

多 worker 并行抢任务，**没有 Kafka 也能飞起来**。

### 5.3 何时该用真消息队列

- ✅ 事件流规模上 GB/s
- ✅ 需要重放历史、回溯消费
- ✅ 跨语言、跨团队的解耦

> 译者注：PG 17 还引入了**逻辑复制订阅的流式事务**（`streaming = parallel`），可以把大事务边生成边 apply，延迟大幅降低。源码见 `src/backend/replication/logical/worker.c`。

---

## 六、PostgreSQL 替代 ClickHouse：高吞吐时序数据

**典型替代场景**：监控指标、IoT 数据、日志聚合。

### 6.1 TimescaleDB 扩展

```sql
CREATE EXTENSION timescaledb;

CREATE TABLE metrics (
    time    timestamptz NOT NULL,
    host    text NOT NULL,
    metric  text NOT NULL,
    value   double precision
);

SELECT create_hypertable('metrics', 'time');

-- 自动 chunk + 压缩
ALTER TABLE metrics SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'host, metric'
);

SELECT add_compression_policy('metrics', INTERVAL '7 days');
SELECT add_retention_policy('metrics', INTERVAL '90 days');
```

### 6.2 何时够用

- ✅ 中小规模时序（每天亿级以下）
- ✅ SQL 兼容性重要（不想为 ClickHouse 学新方言）
- ✅ 想直接用 `JOIN` 把时序数据和业务表关联

ClickHouse 在**列存压缩 + 极致聚合**上仍是王者，但时序场景 TimescaleDB 已经够用 90%。

---

## 七、PostgreSQL 作为向量数据库：AI 工作流

**典型场景**：RAG、相似度搜索、推荐系统。

### 7.1 pgvector 扩展

```sql
CREATE EXTENSION vector;

CREATE TABLE docs (
    id        bigserial PRIMARY KEY,
    content   text,
    embedding vector(1536)  -- OpenAI text-embedding-3 维度
);

CREATE INDEX idx_embedding ON docs USING hnsw (embedding vector_cosine_ops);

-- 相似度搜索
SELECT id, content
FROM docs
ORDER BY embedding <=> $1::vector
LIMIT 10;
```

支持的距离：`vector_cosine_ops` / `vector_l2_ops` / `vector_ip_ops`，HNSW / IVFFlat 索引都能用。

### 7.2 实时 LLM 应用

把向量和元数据放一起：

```sql
SELECT d.id, d.content, d.metadata
FROM docs d
WHERE d.metadata->>'tenant' = current_setting('app.tenant')
ORDER BY d.embedding <=> $1::vector
LIMIT 10;
```

**不需要单独维护一套向量库**，事务一致性、权限、备份都和白名单用户表一起搞定。

---

## 八、PostgreSQL 替代 Redis：非持久化高性能缓存

**典型替代场景**：会话存储、热点数据缓存。

### 8.1 UNLOGGED 表

```sql
CREATE UNLOGGED TABLE session_cache (
    key       text PRIMARY KEY,
    value     jsonb NOT NULL,
    expires_at timestamptz NOT NULL
);

-- 自动过期触发器
CREATE OR REPLACE FUNCTION session_cache_expire() RETURNS trigger AS $$
BEGIN
    DELETE FROM session_cache WHERE expires_at < now();
    RETURN NULL;
END $$ LANGUAGE plpgsql;

CREATE EXTENSION pg_cron;  -- 配合定时清理
SELECT cron.schedule('expire-cache', '*/1 * * * *',
    $$DELETE FROM session_cache WHERE expires_at < now()$$);
```

UNLOGGED 表：

- 写不写 WAL（极快）
- 崩溃会丢数据（适合缓存）
- 性能可与 Redis 一战

> ⚠️ UNLOGGED 不能被流复制或逻辑复制，所以在读写分离架构里需要单独处理。

### 8.2 pgmemcache / 嵌入式方案

对极致延迟敏感，可以配合：

- **Redis 仍然单独用**：当 PG 的 cache 失效时回源
- **pg_redis_fdw**：把 Redis 当成外部表

---

## 九、PostgreSQL 替代文件系统：原始二进制数据

**典型场景**：图片、音视频、文件片段、IoT 数据。

### 9.1 blob + Flatbuffers

```sql
CREATE TABLE blobs (
    id      bigserial PRIMARY KEY,
    data    bytea NOT NULL
);

-- 存
INSERT INTO blobs (data) VALUES (decode('hex...', 'hex'));

-- 取
SELECT data FROM blobs WHERE id = 12345;
```

> **经验之谈**：原文作者提到，在他的项目里，PG 读 binary blob **比直接读本地文件系统还快**——因为 PG 的 buffer pool + 预读 + 大页缓存已经把这事做得很好。

### 9.2 配合 Flatbuffers / Protocol Buffers

```c
// 客户端：序列化 → bytea 存入 PG → 反序列化
flatcc_builder_t builder;
flatcc_builder_init(&builder);
flatcc_builder_create_vector(&builder, data, len);
size_t size;
void *buf = flatcc_builder_finalize_buffer(&builder, &size);

PGresult *res = PQexecParams(conn,
    "INSERT INTO blobs (data) VALUES ($1)",
    1, NULL, &buf, &size, NULL, 0);
```

> 译者注：在 Linux 上 `bytea` 的最大大小受 `pg_largeobject`（TOAST）机制支持，理论上最大 1GB / 字段。

---

## 十、PostgreSQL 替代图数据库：层级数据

**典型场景**：组织架构、标签树、评论嵌套。

### 10.1 LTREE 扩展

```sql
CREATE EXTENSION ltree;

CREATE TABLE categories (
    id        serial PRIMARY KEY,
    name      text NOT NULL,
    path      ltree  -- 例如 '1.5.12' 代表 1 → 5 → 12 的路径
);

INSERT INTO categories (name, path) VALUES
    ('Electronics', '1'),
    ('Computers',   '1.1'),
    ('Laptops',     '1.1.1'),
    ('Phones',      '1.2'),
    ('Smartphones', '1.2.1');

-- 查所有"Electronics"的后代
SELECT * FROM categories WHERE path <@ '1';

-- 查所有祖先
SELECT * FROM categories WHERE path @> '1.1.1';

-- 找兄弟节点
SELECT * FROM categories WHERE path ~ '1.1.*';
```

比 SQL 递归 CTE 简洁一万倍，性能也好很多。

---

## 十一、PostgreSQL 替代微服务：JSON 输出

**典型观察**：很多"微服务"本质上就是"取数据 → 转 JSON → 返回"。PostgreSQL **天生就能干这事**：

```sql
SELECT json_build_object(
    'id', u.id,
    'name', u.name,
    'orders', (
        SELECT json_agg(row_to_json(o))
        FROM orders o
        WHERE o.user_id = u.id
    )
) AS user_json
FROM users u
WHERE u.id = $1;
```

一行 SQL 输出完整嵌套 JSON，无需中间层。

### 11.1 利与弊

| 维度 | 用 PG 直接出 JSON | 用中间层 |
| --- | --- | --- |
| 性能 | ✅ 跳过网络 + 序列化开销 | ⚠️ 多一跳 |
| 灵活性 | ⚠️ 复杂业务逻辑难表达 | ✅ 任意逻辑 |
| 缓存 | ⚠️ PG 没专用 HTTP 缓存 | ✅ Redis/Cloudflare |
| 鉴权 | ✅ PG RLS 一致性 | ✅ 各管各的 |

**结论**：简单 CRUD + 列表/详情页 → PG 直接出 JSON 完胜；复杂业务流 → 中间层仍不可替代。

> 推荐阅读：[Lukas Eder 的 "Stop Mapping Stuff in Your Middleware"](https://blog.jooq.org/stop-mapping-stuff-in-your-middleware-use-sqls-xml-or-json-operators-instead/)（SQL/XML/JSON 优先，原文不特指 PG 但 PG 完全适用）

---

## 十二、彩蛋：PostgreSQL 替代你的 PlayStation 5

有人用 PG 的**公用表表达式（CTE）** 写了俄罗斯方块：

```sql
-- 摘自 https://github.com/nuno-faria/tetris-sql/blob/main/game.sql
WITH ... AS (...)
SELECT ... FROM ...
WHERE ...
```

不推荐家用，但证明 PG 的图灵完备性 + 表达力。

---

## 十三、结论：少即是多

上面列的并不完整。PG 是个**极其灵活**的软件，并且可以通过插件（extension）不断扩展新能力。

> **You need simplicity if you want to move fast.**

每当你遇到一个新需求，先问自己：

> *"PG 能干吗？我们真的需要那门新技术吗？"*

PostgreSQL 可能不是**一切**的答案——但它能顶的事**比你想象的要多得多**。

---

## 译者补充：源码级视角的 PG 扩展能力

下面这张表把上面提到的能力对应到 PG 源码位置，方便你按图索骥：

| 能力 | 扩展 / 模块 | 源码路径 |
| --- | --- | --- |
| 全文检索 | 内置 | `src/backend/utils/adt/tsvector.c`、`tsquery.c` |
| GIN 索引 | 内置 | `src/backend/access/gin/` |
| JSON / JSONB | 内置 | `src/backend/utils/adt/jsonb.c` |
| 消息队列 (`pgmq`) | 扩展 | https://github.com/tembo-io/pgmq |
| SKIP LOCKED | 内置 | `src/backend/executor/nodeLockRows.c` |
| 时序 (`timescaledb`) | 扩展 | https://github.com/timescale/timescaledb |
| 向量 (`pgvector`) | 扩展 | https://github.com/pgvector/pgvector |
| HNSW 索引 | 扩展 | https://github.com/pgvector/pgvector |
| LTREE | 内置 | `src/backend/utils/adt/ltree*.c` |
| UNLOGGED 表 | 内置 | `src/backend/access/heap/heapam.c` |
| 字节流 (`bytea`) | 内置 | `src/backend/utils/adt/varlena.c` |
| JSON 输出 | 内置 | `src/backend/utils/adt/json.c` |

---

## 参考资料

- 原文：Dr. Raphael A. Bauer, *PostgreSQL for Everything*, https://www.raphaelbauer.com/posts/postgresql-everything/, 2024-02-14
- [PostgreSQL 官方文档](https://www.postgresql.org/docs/current/)
- [pgmq: PostgreSQL as a queue](https://github.com/tembo-io/pgmq)
- [TimescaleDB 文档](https://docs.timescale.com/)
- [pgvector 文档](https://github.com/pgvector/pgvector)
- [Lukas Eder: Stop Mapping Stuff in Your Middleware](https://blog.jooq.org/stop-mapping-stuff-in-your-middleware-use-sqls-xml-or-json-operators-instead/)
- [Tetris in pure SQL](https://github.com/nuno-faria/tetris-sql/blob/main/game.sql)
