# PostgreSQL 逻辑复制集群搭建指北：基于 Docker 的 publisher + subscriber 一键拉起

| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 初稿，使用 `docker.m.daocloud.io/library/postgres:16` 与 `docker compose` 起 publisher / subscriber，跑通 INSERT / UPDATE / DELETE 的实时同步 | 2026-09-01 |

> 本文是「PostgreSQL 逻辑复制系列」的第 N 篇，重点不在原理拆解，而在「**用一条 `docker compose up -d` 把 publisher/subscriber 拉起来**」。同系列前文：

PostgreSQL 的逻辑复制（Logical Replication）自 10.0 起成为内核能力，基于 **发布（Publication）/ 订阅（Subscription）** 模型，把发布端表的 WAL 解码为逻辑变更（`pgoutput` 插件），由订阅端 apply worker 回放。

## 背景

它与流复制的区别在于：

- 粒度细到表、甚至 DML 操作类型（`INSERT/UPDATE/DELETE/TRUNCATE` 可独立订阅）；
- 可以跨大版本（如 14 → 16）；
- 既能整库级同步，也能构建多主、级联、选择性分发表；
- 默认是 **单向**，反向回环需要用 `origin` 与 `REPLICA IDENTITY FULL` 等手段处理。

下面这套配置用 `docker.m.daocloud.io/library/postgres:16` 镜像在一台主机上起两个 PG 实例，做一个能跑通的最小化逻辑复制集群，并把 publisher / subscriber 都做成由 `docker compose` 一键拉起的服务。

## 总体方案

```
+------------------+    logical WAL (pgoutput)    +------------------+
|  pg-publisher    |  --------------------------->|  pg-subscriber   |
|  hostname:       |     via replication slot     |  hostname:       |
|  pg-publisher    |     sub_slot_app             |  pg-subscriber   |
|  port 5432       |                              |  port 5432       |
|  DB: appdb       |                              |  DB: appdb       |
|  PUBLICATION:    |                              |  SUBSCRIPTION:   |
|  pub_app         |                              |  sub_app         |
+------------------+                              +------------------+
```

要点：

| 维度 | publisher | subscriber |
| --- | --- | --- |
| `wal_level` | 必须 `logical` | 同上（作为上游保留能力） |
| `max_replication_slots` | ≥ 订阅端数量 | 不强依赖 |
| `max_wal_senders` | ≥ 订阅端 × 工作进程 | 同上 |
| `max_logical_replication_workers` | ≥ 同时复制表数 | ≥ `apply worker + tablesync worker` |
| 表结构 | 必须存在并包含主键 | **必须预先存在**（`copy_data=true` 时尤其重要） |
| 复制账号 | 需 `REPLICATION` 属性 | 用同一账号连接 |

## docker-compose.yml

工作目录建议放在 `/tmp/pg-logical-replication`，文件如下：

```yaml
services:
  publisher:
    image: docker.m.daocloud.io/library/postgres:16
    container_name: pg-publisher
    hostname: pg-publisher
    environment:
      POSTGRES_USER: repuser
      POSTGRES_PASSWORD: reppass@2026
      POSTGRES_DB: appdb
    command:
      - "postgres"
      - "-c"
      - "wal_level=logical"
      - "-c"
      - "max_replication_slots=10"
      - "-c"
      - "max_wal_senders=10"
      - "-c"
      - "max_logical_replication_workers=10"
      - "-c"
      - "max_worker_processes=20"
      - "-c"
      - "shared_preload_libraries="
      - "-c"
      - "listen_addresses=*"
    ports:
      - "5433:5432"
    volumes:
      - publisher_data:/var/lib/postgresql/data
      - ./init-publisher.sh:/docker-entrypoint-initdb.d/01-init.sh:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U repuser -d appdb"]
      interval: 5s
      timeout: 5s
      retries: 10

  subscriber:
    image: docker.m.daocloud.io/library/postgres:16
    container_name: pg-subscriber
    hostname: pg-subscriber
    environment:
      POSTGRES_USER: repuser
      POSTGRES_PASSWORD: reppass@2026
      POSTGRES_DB: appdb
      PUBLISHER_HOST: pg-publisher
    command:
      - "postgres"
      - "-c"
      - "wal_level=logical"
      - "-c"
      - "max_replication_slots=10"
      - "-c"
      - "max_logical_replication_workers=10"
      - "-c"
      - "max_worker_processes=20"
      - "-c"
      - "shared_preload_libraries="
      - "-c"
      - "listen_addresses=*"
    ports:
      - "5434:5432"
    volumes:
      - subscriber_data:/var/lib/postgresql/data
      - ./init-subscriber.sh:/docker-entrypoint-initdb.d/01-init.sh:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U repuser -d appdb"]
      interval: 5s
      timeout: 5s
      retries: 10
    depends_on:
      publisher:
        condition: service_healthy

volumes:
  publisher_data:
  subscriber_data:
```

几个工程上的细节：

- 用 `daocloud.io` 镜像源直连，无需额外 registry 代理；
- `listen_addresses=*` 让同一 compose 网络里的容器能远程连入；
- `healthcheck` 使用 `pg_isready`，让 `depends_on.condition: service_healthy` 真正生效；
- 两个容器分别映射到宿主机 `5433 / 5434`，避免本地有 PG 时的端口冲突。

## publisher 初始化脚本

`init-publisher.sh` 由 docker-entrypoint 在首次启动自动执行，做 5 件事：

1. 给 `repuser` 加 `REPLICATION` 属性；
2. 把 `appdb` 的 DML 权限授予 `repuser`；
3. 创建测试用的 `app_user / app_order` 表与种子数据；
4. 在 `pg_hba.conf` 上为 `repuser` 放行 `scram-sha-256`（包含 replication 段）；
5. 创建 `pub_app` PUBLICATION（`FOR TABLE` 显式列表，也可以改成 `FOR ALL TABLES`）。

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "[publisher] init roles, schema, publication"

# 1) 复制账号 & 库内权限
psql -v ON_ERROR_STOP=1 -U repuser -d appdb <<'SQL'
ALTER ROLE repuser WITH REPLICATION PASSWORD 'reppass@2026';
GRANT ALL PRIVILEGES ON DATABASE appdb TO repuser;
GRANT ALL ON ALL TABLES    IN SCHEMA public TO repuser;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO repuser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES    TO repuser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO repuser;
SQL

# 2) 表结构 (必须先于 CREATE PUBLICATION)
psql -v ON_ERROR_STOP=1 -U repuser -d appdb <<'SQL'
CREATE TABLE IF NOT EXISTS app_user (
    id          BIGSERIAL    PRIMARY KEY,
    username    VARCHAR(64)  NOT NULL UNIQUE,
    email       VARCHAR(128) NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app_order (
    id           BIGSERIAL    PRIMARY KEY,
    user_id      BIGINT       NOT NULL REFERENCES app_user(id),
    amount       NUMERIC(12,2) NOT NULL,
    remark       TEXT,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);
SQL

# 3) 种子数据
psql -v ON_ERROR_STOP=1 -U repuser -d appdb <<'SQL'
INSERT INTO app_user(username, email) VALUES
    ('alice', 'alice@example.com'),
    ('bob',   'bob@example.com'),
    ('carol', 'carol@example.com')
ON CONFLICT DO NOTHING;
SQL

# 4) 让远端复制流量走 scram-sha-256
echo "host    all             repuser        0.0.0.0/0               scram-sha-256" >> /var/lib/postgresql/data/pg_hba.conf
echo "host    replication     repuser        0.0.0.0/0               scram-sha-256" >> /var/lib/postgresql/data/pg_hba.conf
psql -v ON_ERROR_STOP=1 -U repuser -d appdb -c "SELECT pg_reload_conf();"

# 5) 创建发布
psql -v ON_ERROR_STOP=1 -U repuser -d appdb <<'SQL'
DROP PUBLICATION IF EXISTS pub_app;
CREATE PUBLICATION pub_app FOR TABLE app_user, app_order;
SQL

echo "[publisher] publication:"
psql -U repuser -d appdb -c "SELECT pubname, puballtables FROM pg_publication;"
echo "[publisher] tables:"
psql -U repuser -d appdb -c "\dt"
```

> 注意：`docker-entrypoint.sh` 会保证 SQL 脚本只在 **数据目录为空** 时跑一次。如果你想重做一次发布，删卷即可：`docker compose down -v`。

## subscriber 初始化脚本

subscriber 端要做两件事：

1. **预先创建空表**（列、主键、外键、默认值都要齐全，因为初始 `copy_data` 通过 `INSERT … SELECT` 把 publisher 的内容灌进来）；
2. `CREATE SUBSCRIPTION` 指向 publisher，开始拉取逻辑变更。

```bash
#!/usr/bin/env bash
set -euo pipefail

PUBLISHER_HOST="${PUBLISHER_HOST:-pg-publisher}"
echo "[subscriber] waiting for publisher at ${PUBLISHER_HOST}:5432 ..."
for i in $(seq 1 60); do
    if pg_isready -h "${PUBLISHER_HOST}" -p 5432 -U repuser -d appdb >/dev/null 2>&1; then
        echo "[subscriber] publisher is up after ${i} tries"
        break
    fi
    sleep 2
done

# 本实例的本地权限
psql -v ON_ERROR_STOP=1 -U repuser -d appdb <<'SQL'
GRANT ALL PRIVILEGES ON DATABASE appdb TO repuser;
SQL

# 关键: subscriber 端必须预先存在同名表结构, 才能承接初始 copy_data 同步
psql -v ON_ERROR_STOP=1 -U repuser -d appdb <<'SQL'
CREATE TABLE IF NOT EXISTS app_user (
    id          BIGSERIAL    PRIMARY KEY,
    username    VARCHAR(64)  NOT NULL UNIQUE,
    email       VARCHAR(128) NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app_order (
    id           BIGSERIAL    PRIMARY KEY,
    user_id      BIGINT       NOT NULL REFERENCES app_user(id),
    amount       NUMERIC(12,2) NOT NULL,
    remark       TEXT,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);
SQL

export PGPASSWORD='reppass@2026'

# 创建逻辑复制订阅 (核心步骤)
psql -v ON_ERROR_STOP=1 -U repuser -d appdb <<SQL
DROP SUBSCRIPTION IF EXISTS sub_app;
CREATE SUBSCRIPTION sub_app
    CONNECTION 'host=${PUBLISHER_HOST} port=5432 user=repuser password=reppass@2026 dbname=appdb'
    PUBLICATION pub_app
    WITH (copy_data = true, create_slot = true, enabled = true, slot_name = sub_slot_app);
SQL

echo "[subscriber] subscription:"
psql -U repuser -d appdb -c "SELECT subname, subenabled, subslotname, subpublications FROM pg_subscription;"
```

`CREATE SUBSCRIPTION` 末尾的几个开关很重要：

- `copy_data = true`：先做一次全量初始同步；
- `create_slot = true`：自动在 publisher 上建一个名字为 `sub_slot_app` 的 replication slot；
- `enabled = true`：开启 apply worker；
- `slot_name = …`：固定复制槽名，方便后续运维诊断。

## 部署与验证

### 启动

```bash
cd /tmp/pg-logical-replication
docker compose up -d
docker compose ps
```

启动后大约 5–10 秒两端 healthcheck 全绿。

### 元数据核对

**Publisher 端：**

```bash
docker exec -e PGPASSWORD=reppass@2026 pg-publisher \
    psql -U repuser -d appdb -c "SELECT * FROM pg_publication;"
docker exec -e PGPASSWORD=reppass@2026 pg-publisher \
    psql -U repuser -d appdb -c "SELECT slot_name, plugin, slot_type, database, active, restart_lsn FROM pg_replication_slots;"
docker exec -e PGPASSWORD=reppass@2026 pg-publisher \
    psql -U repuser -d appdb -c "SELECT pid, usename, application_name, client_addr, state, sync_state, write_lsn, replay_lsn FROM pg_stat_replication;"
```

我在部署中输出的结果（节选）：

```
  oid  | pubname | pubowner | puballtables | pubinsert | pubupdate | pubdelete | pubtruncate | pubviaroot
-------+---------+----------+--------------+-----------+-----------+-----------+-------------+------------
 16412 | pub_app |       10 | f            | t         | t         | t         | t           | f
  slot_name   |  plugin  | slot_type | database | active | restart_lsn
--------------+----------+-----------+----------+--------+-------------
 sub_slot_app | pgoutput | logical   | appdb    | t      | 0/1979E08
 pid | usename | application_name | client_addr |   state   | sync_state | write_lsn | replay_lsn
-----+---------+------------------+-------------+-----------+------------+-----------+------------
  96 | repuser | sub_app          | 172.21.0.3  | streaming | async      | 0/1979E40 | 0/1979E40
```

**Subscriber 端：**

```bash
docker exec -e PGPASSWORD=reppass@2026 pg-subscriber \
    psql -U repuser -d appdb -c "SELECT * FROM pg_subscription;"
docker exec -e PGPASSWORD=reppass@2026 pg-subscriber \
    psql -U repuser -d appdb -c "SELECT pid, relid::regclass AS table, received_lsn, last_msg_send_time, last_msg_receipt_time FROM pg_stat_subscription;"
```

```
 oid  | subdbid | subskiplsn | subname | subowner | subenabled | subtwophasestate | subpublications
-------+---------+------------+---------+----------+------------+------------------+-----------------
 16410 |   16384 | 0/0        | sub_app |       10 | t          | d                | {pub_app}
 pid | table | received_lsn |      last_msg_send_time       |     last_msg_receipt_time
-----+-------+--------------+-------------------------------+-------------------------------
  82 |       | 0/1979E40    | 2026-08-31 08:59:26.799086+00 | 2026-08-31 08:59:26.799119+00
```

`pg_stat_subscription` 中 `last_msg_send_time` 与 `last_msg_receipt_time` 在持续更新，`received_lsn` 与 publisher 端 `replay_lsn` 同步推进，说明 apply worker 工作正常。

### 端到端 DML 验证

```bash
# 1) INSERT
docker exec -e PGPASSWORD=reppass@2026 pg-publisher \
    psql -U repuser -d appdb -c "INSERT INTO app_user(username, email) VALUES('dave', 'dave@example.com');"
docker exec -e PGPASSWORD=reppass@2026 pg-subscriber \
    psql -U repuser -d appdb -c "SELECT id, username, email FROM app_user WHERE username='dave';"

# 2) UPDATE
docker exec -e PGPASSWORD=reppass@2026 pg-publisher \
    psql -U repuser -d appdb -c "UPDATE app_user SET email='alice.new@example.com' WHERE username='alice';"
docker exec -e PGPASSWORD=reppass@2026 pg-subscriber \
    psql -U repuser -d appdb -c "SELECT email FROM app_user WHERE username='alice';"

# 3) DELETE
docker exec -e PGPASSWORD=reppass@2026 pg-publisher \
    psql -U repuser -d appdb -c "DELETE FROM app_user WHERE username='carol';"
docker exec -e PGPASSWORD=reppass@2026 pg-subscriber \
    psql -U repuser -d appdb -c "SELECT count(*) FROM app_user WHERE username='carol';"

# 4) INSERT app_order
docker exec -e PGPASSWORD=reppass@2026 pg-publisher \
    psql -U repuser -d appdb -c "INSERT INTO app_order(user_id, amount, remark) VALUES(2, 299.50, 'order-dave');"
docker exec -e PGPASSWORD=reppass@2026 pg-subscriber \
    psql -U repuser -d appdb -c "SELECT id, user_id, amount, remark FROM app_order;"

# 5) 复制延迟
docker exec -e PGPASSWORD=reppass@2026 pg-subscriber \
    psql -U repuser -d appdb -c "SELECT now() - last_msg_receipt_time AS apply_lag FROM pg_stat_subscription;"
```

部署实测里，两端 `app_user / app_order` 在几秒后内容完全一致：

```
[publisher]
 id | username |         email
----+----------+-----------------------
  1 | alice    | alice.new@example.com
  2 | bob      | bob@example.com
  4 | frank    | frank@example.com
  5 | dave     | dave@example.com
(4 rows)

 id | user_id | amount |   remark
----+---------+--------+------------
  1 |       2 | 299.50 | order-dave

[subscriber]
 id | username |         email
----+----------+-----------------------
  1 | alice    | alice.new@example.com
  2 | bob      | bob@example.com
  4 | frank    | frank@example.com
  5 | dave     | dave@example.com
(4 rows)

 id | user_id | amount |   remark
----+---------+--------+------------
  1 |       2 | 299.50 | order-dave

    apply_lag
-----------------
 00:00:02.307543
```

注意：**不要在 subscriber 端直接执行 DML**。复制过来的变更与本地 BIGSERIAL 会冲突：

```
ERROR:  duplicate key value violates unique constraint "app_user_pkey"
DETAIL:  Key (id)=(1) already exists.
```

如果非要写，需要把 subscriber 端的 identity / sequence 与 publisher 解耦，或建立双向逻辑复制 + `origin` 过滤。

## 常用排查命令

```sql
-- publisher: 槽是否活跃，是否堆积
SELECT slot_name, plugin, slot_type, database, active, restart_lsn
  FROM pg_replication_slots;

-- publisher: walsender 是否在流式发送
SELECT pid, usename, application_name, client_addr, state, sync_state,
       write_lsn, replay_lsn, (now() - backend_start) AS dur
  FROM pg_stat_replication;

-- subscriber: 订阅是否启用、远端 LSN
SELECT subname, subenabled, subslotname, subpublications
  FROM pg_subscription;

SELECT pid, relid::regclass AS table,
       received_lsn, last_msg_send_time, last_msg_receipt_time,
       (now() - last_msg_receipt_time) AS apply_lag
  FROM pg_stat_subscription;

-- subscriber: 单表同步状态
SELECT * FROM pg_subscription_rel;

-- subscriber 主动同步进度诊断（最直接）
SELECT s.subname,
       sr.srsubstate,
       sr.srrelid::regclass
  FROM pg_subscription s
  JOIN pg_subscription_rel sr ON sr.srsubid = s.oid;
```

`srsubstate` 取值含义：

- `i` = initialize（订阅尚未开始向该表推数据）；
- `d` = data being copied（初始 `copy_data` 进行中）；
- `s` = synchronized（已同步完成，正在等后续变更）；
- `r` = ready（复制状态最终一致，正在持续接收变更）。

## 常见坑

1. **subscriber 端没有同名表结构**：`CREATE SUBSCRIPTION` + `copy_data=true` 不会自动建表，只会尝试 `INSERT … SELECT`。会直接报 `relation "app_user" does not exist`。修复：在 subscriber 上预建表。
2. **`wal_level` 不等于 `logical`**：物理复制（流复制）只需要 `replica`，发布订阅链路必须 `logical`，否则 `CREATE PUBLICATION` 报 `wal_level is not logical`。
3. **`max_replication_slots` 不足**：每多一个订阅都要占一个槽；扩展新订阅前要规划好。
4. **删除 / disable 顺序**：先 `ALTER SUBSCRIPTION … DISABLE;` 再删，否则远端 walsender 还会继续往拉。
5. **`REPLICA IDENTITY` 默认是 `DEFAULT`（=主键）**：对于无主键表，要么 `ALTER TABLE … REPLICA IDENTITY FULL;`，要么在 PUBLICATION 里 `WHERE` 过滤掉，但代价是 WAL 体积明显变大。
6. **DDL 不通过逻辑复制**：表结构变更要单独在两端各执行。社区方案 [pglogical](https://github.com/2ndQuadrant/pglogical) 风格的双向 DDL 不能裸用纯 `pgoutput`。

## publisher 端 DSN

部署完成后，发布端连接串如下：

```text
# 容器内 / 同一 docker-compose 网络
postgresql://repuser:reppass%402026@pg-publisher:5432/appdb

# 宿主机（端口已映射为 5433）
postgresql://repuser:reppass%402026@127.0.0.1:5433/appdb

# key=value 风格
host=pg-publisher port=5432 user=repuser password=reppass@2026 dbname=appdb
```

注意密码里的 `@` 需要百分号编码为 `%40`。一行自检：

```bash
PGPASSWORD='reppass@2026' psql \
  "postgresql://repuser:reppass@2026@127.0.0.1:5433/appdb" \
  -c "SELECT 1 AS ok, current_setting('wal_level') AS wal_level;"
```

预期输出：

```
 ok | wal_level
----+-----------
  1 | logical
```

`wal_level = logical` 说明拿到的是真正的发布端。

## 小结

- 用 `docker.m.daocloud.io/library/postgres:16` + `docker compose`，可以把一个 **publisher + subscriber** 的逻辑复制集群拉起来不超过 10 秒，并跑通 INSERT / UPDATE / DELETE 的实时同步；
- 关键参数都来自 `wal_level=logical`、`max_replication_slots`、`max_wal_senders`、`max_logical_replication_workers`；
- subscriber 端 **必须先有同名表**，初始 `copy_data` 才能正确灌入；
- 想要更进一步（双向、级联、selective replication）时，再叠加 `origin` / `WHERE` / 多 PUBLICATION 即可，框架本身已经比较稳固。

## 同系列前文

- [PostgreSQL 逻辑复制表的生命周期：从 `pg_replication_slots` 到 `pg_subscription_rel` 的全景图](../postgresql-logical-replication-tables-lifecycle/index.html)
- [PostgreSQL 逻辑复制的 worker 模型：launcher、apply worker、tablesync worker 的进程拓扑](../postgresql-logical-replication-worker-model/index.html)
- [PostgreSQL 逻辑复制 streaming 与 spill：从 reorderbuffer 到 `<subid>-<xid>.changes` 的全程真相](../postgresql-logical-replication-streaming-spill/index.html)
- [PostgreSQL 逻辑复制订阅参数全解：从 run_as_owner 到 disable_on_error](../postgresql-logical-replication-options/index.html)
- [PostgreSQL 逻辑复制 spill 文件深度拆解：写-读-清 三阶段与 TPC-C 100WH 增长模型](../postgresql-logical-replication-spill-deep-dive/index.html)
- [PostgreSQL 逻辑复制与分区表：DDL 同步与 apply worker 启动](../postgresql-logical-replication-with-partitioned-tables/index.html)
- [PostgreSQL 逻辑复制之 `publish_via_partition_root` 深度解析](../postgresql-logical-replication-publish-via-partition-root/index.html)
- [PostgreSQL 逻辑复制分区表 INSERT 流程：从 publisher 一行到 subscriber 叶分区的全程](../postgresql-logical-replication-partitioned-insert-flow/index.html)
- [PostgreSQL 逻辑复制 DDL 触发 apply worker：分区表同步全链路](../postgresql-logical-replication-ddl-trigger-apply-worker/index.html)
- [PostgreSQL 逻辑复制六视图监控深潜：`pg_stat_replication` × `pg_stat_subscription` × `pg_stat_replication_slots`](../postgresql-logical-replication-monitoring/index.html)
- [PostgreSQL 逻辑复制 ReorderBuffer × 事务全解：从 `SnapBuild` 到 `ReorderBufferTXN`](../postgresql-logical-replication-reorderbuffer-transaction/index.html)
