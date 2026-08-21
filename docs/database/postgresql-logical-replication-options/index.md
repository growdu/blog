# PostgreSQL 逻辑复制订阅参数全解：从 run_as_owner 到 disable_on_error

| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 初稿，结合 PostgreSQL 18 dev 源码 | 2026-08-21 |

`CREATE SUBSCRIPTION` 那一长串 `WITH (...)` 参数，每个都对应 `pg_subscription` 系统表里的一列，背后是 apply worker 一段真实的代码分支。

今天我们沿 `~/cwork/postgresql/src/include/catalog/pg_subscription.h`、`src/backend/replication/logical/worker.c`、`src/backend/commands/subscriptioncmds.c`，把每个参数讲透。重点是：

- **`run_as_owner`**——安全模型的核心开关
- **`disable_on_error`**——错误处理的兜底机制
- 顺带把 `binary` / `streaming` / `two_phase` / `failover` / `origin` / `password_required` / `synchronous_commit` / `copy_data` 都讲清楚

---

## 一、先看 pg_subscription 的全貌

`pg_subscription` 是订阅的"身份证"，每个订阅对应一行。所有 `WITH (...)` 参数都映射到这表的列：

源码 `src/include/catalog/pg_subscription.h:42`：

```c
CATALOG(pg_subscription, 6100, SubscriptionRelationId) BKI_SHARED_RELATION
{
    Oid         oid;
    Oid         subdbid BKI_LOOKUP(pg_database);     /* 订阅所属数据库 */

    XLogRecPtr  subskiplsn;                          /* 跳过初始同步的 LSN */
    NameData    subname;                             /* 订阅名 */
    Oid         subowner BKI_LOOKUP(pg_authid);      /* 谁是订阅的主人 */

    bool        subenabled;                          /* 是否启用 */
    bool        subbinary;                           /* 二进制传输 */
    char        substream;                            /* 流式事务模式 */
    char        subtwophasestate;                     /* 两阶段状态机 */
    bool        subdisableonerr;                     /* 错就停？ */
    bool        subpasswordrequired;                 /* 强制密码 */
    bool        subrunasowner;                        /* 用订阅 owner 身份执行？ */
    bool        subfailover;                          /* slot 同步给备机？ */

#ifdef CATALOG_VARLEN
    text        subconninfo;                          /* 连接串 */
    NameData    subslotname;                          /* 复制槽名 */
    text        subsynccommit;                        /* synchronous_commit 覆盖 */
    text        subpublications[1];                   /* 订阅的 publication 列表 */
    text        suborigin;                            /* 只接受指定 origin 的变更 */
#endif
}
```

对应的内存结构 `Subscription`：

```c
/* src/include/catalog/pg_subscription.h:108 */
typedef struct Subscription {
    Oid       oid;
    Oid       dbid;
    XLogRecPtr skiplsn;
    char     *name;
    Oid       owner;
    bool      ownersuperuser;
    bool      enabled;
    bool      binary;
    char      stream;
    char      twophasestate;
    bool      disableonerr;     /* ← disable_on_error */
    bool      passwordrequired; /* ← password_required */
    bool      runasowner;       /* ← run_as_owner */
    bool      failover;         /* ← failover */
    char     *conninfo;
    char     *slotname;
    char     *synccommit;       /* ← synchronous_commit */
    List     *publications;
    char     *origin;           /* ← origin */
} Subscription;
```

这样所有参数 → 系统表列 → apply worker 内存对象 → 内核代码分支的链路一目了然。

```text
  CREATE SUBSCRIPTION foo WITH (run_as_owner=true, disable_on_error=false)
        │
        ▼
  src/backend/commands/subscriptioncmds.c:275
        │
        ├─ opts->disableonerr = true
        └─ opts->runasowner = true
        │
        ▼
  pg_subscription.subdisableonerr = true
  pg_subscription.subrunasowner = true
        │
        ▼
  apply worker 启动时通过 syscache 读到 MySubscription
        │
        ▼
  worker.c:2427  run_as_owner = MySubscription->runasowner
  worker.c:4523  if (MySubscription->disableonerr) DisableSubscriptionAndExit()
```

接下来我们逐个参数深入。

---

## 二、run_as_owner：订阅 worker 以谁的身份执行？

### 2.1 默认行为：身份会"换"

这是**最容易被忽视**的参数，也是**最危险**的一个。

PG 的默认行为（`run_as_owner = false`）：

```text
  订阅 owner：alice（被授予 REPLICATION、CREATE 等权限）
  订阅 apply worker 启动后：
    1. 以 alice 身份连 publisher
    2. 拉到变更后，针对目标表 t1（owner = bob）执行 INSERT/UPDATE/DELETE 时
       → 临时切换到 bob 身份（SET ROLE bob）
       → 用 bob 的权限执行
       → 完成后切回 alice
```

源码 `src/backend/replication/logical/worker.c:2427`（apply_handle_insert）：

```c
run_as_owner = MySubscription->runasowner;
if (!run_as_owner)
    SwitchToUntrustedUser(rel->localrel->rd_rel->relowner, &ucxt);

/* ... 执行 INSERT/UPDATE/DELETE ... */

if (!run_as_owner)
    RestoreUserContext(&ucxt);
```

`SwitchToUntrustedUser` 实际就是 `SET ROLE table_owner`。意思是：

> 既然这条 INSERT 是写到 bob 的表里，那就**让 bob 的权限来检查约束、触发器、行级安全策略**——这才是合理的安全模型。

### 2.2 run_as_owner = true：不切换身份

```text
  订阅 owner：alice
  订阅 apply worker 启动后：
    1. 以 alice 身份连 publisher
    2. 拉到变更后，针对目标表 t1（owner = bob）执行 INSERT/UPDATE/DELETE 时
       → 不切换身份，仍然以 alice 身份执行
```

源码里的逻辑：`if (!run_as_owner) SwitchToUntrustedUser(...)`——`run_as_owner` 为真就**跳过这步**。

### 2.3 安全影响：差异巨大

官方文档 `doc/src/sgml/logical-replication.sgml:2320` 的话（原文）：

> If the subscription has been configured with `run_as_owner = true`, then no user switching will occur. Instead, all operations will be performed with the permissions of the subscription owner. ... However, this also means that any user who owns a table into which replication is happening can execute arbitrary code with the privileges of the subscription owner. For example, they could do this by simply attaching a trigger to one of the tables which they own.

**翻译**：开了 `run_as_owner = true` 后，**目标表的 owner 可以通过在该表上加 trigger 来以订阅 owner 身份执行任意代码**。

用一个具体例子说明风险：

```sql
-- alice 创建订阅
CREATE SUBSCRIPTION sub
    CONNECTION 'host=pub user=repl_user'
    PUBLICATION pub
    WITH (run_as_owner = true);

-- bob 是目标表 accounts 的 owner，bob 可以这样攻击：
CREATE FUNCTION f_attack() RETURNS trigger AS $$
BEGIN
    -- 这里以 alice 身份执行！alice 是订阅 owner
    EXECUTE format('GRANT ALL ON DATABASE %I TO bob', current_database());
    RETURN NULL;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER t_attack
    BEFORE INSERT ON accounts
    FOR EACH ROW EXECUTE FUNCTION f_attack();
```

下次 publisher 上有 INSERT 复制到 accounts，bob 的恶意 trigger 就被以 alice 身份执行了——alice 的权限都被 bob 拿走。

### 2.4 适用场景

| 场景 | 推荐设置 |
| --- | --- |
| 多团队共用数据库，各管各表 | `false`（默认） |
| 单租户/单 owner，所有表一个用户 | `true` |
| 表 owner 不可信（多租户 SaaS） | **永远 `false`** |
| 跨实例复制，源端表 owner 是 `postgres` | `true`（反正都是 superuser） |
| 复制到受限 schema，只想让 replication 角色写入 | `true` |

### 2.5 设置时机

```sql
-- 创建时
CREATE SUBSCRIPTION sub
    CONNECTION 'host=pub ...'
    PUBLICATION pub
    WITH (run_as_owner = false);     -- 显式写出更清晰

-- 修改（必须先 disable 订阅）
ALTER SUBSCRIPTION sub DISABLE;
ALTER SUBSCRIPTION sub SET (run_as_owner = true);
ALTER SUBSCRIPTION sub ENABLE;
```

注意：改了 `run_as_owner` **必须重启 apply worker**——worker 是把 `runasowner` 读到 `MySubscription` 缓存里的，ALTER 只是改了 catalog，重启才生效。

---

## 三、disable_on_error：错误即停

### 3.1 默认行为：错了继续跑

`disable_on_error = false`（默认）意味着 apply worker 抛错后：

```text
  apply worker 在某个事务里碰到错误
    │
    ├─► 捕获错误（PG_TRY/PG_CATCH）
    ├─► 重置 origin 进度（replorigin_reset）防止丢事务
    ├─► 上报一次订阅错误统计（pgstat_report_subscription_error）
    └─► PG_RE_THROW → 整个 apply worker 进程崩溃退出
        │
        └─► pg 调度器（launcher）会再次拉起 worker
            从上次成功的位置重放（因为 origin 进度没前进）
```

源码 `worker.c:4508`：

```c
PG_TRY();
{
    LogicalRepApplyLoop(origin_startpos);
}
PG_CATCH();
{
    /* 重置 origin 进度 */
    replorigin_reset(0, (Datum) 0);

    if (MySubscription->disableonerr)
        DisableSubscriptionAndExit();
    else
    {
        AbortOutOfAnyTransaction();
        pgstat_report_subscription_error(MySubscription->oid, !am_tablesync_worker());
        PG_RE_THROW();
    }
}
```

> ⚠️ **反复失败就会陷入"拉起-崩溃-拉起-崩溃"循环**。生产上没人希望这样。

### 3.2 disable_on_error = true：错了就停

源码 `worker.c:4838` 的 `DisableSubscriptionAndExit`：

```c
void
DisableSubscriptionAndExit(void)
{
    HOLD_INTERRUPTS();
    EmitErrorReport();
    AbortOutOfAnyTransaction();
    FlushErrorState();
    RESUME_INTERRUPTS();

    /* 上报统计 */
    pgstat_report_subscription_error(MyLogicalRepWorker->subid,
                                     !am_tablesync_worker());

    /* 在新事务里更新 pg_subscription.subenabled = false */
    StartTransactionCommand();
    PushActiveSnapshot(GetTransactionSnapshot());
    DisableSubscription(MySubscription->oid);  /* 改 subenabled = false */
    PopActiveSnapshot();
    CommitTransactionCommand();

    /* log 一条 */
    ereport(LOG,
            errmsg("subscription \"%s\" has been disabled because of an error",
                   MySubscription->name));

    proc_exit(0);  /* 干净退出 */
}
```

`DisableSubscription` 干了什么（`pg_subscription.c:200`）？

```c
void DisableSubscription(Oid subid)
{
    /* 更新 pg_subscription.subenabled = false */
    /* 留着 subslotname、subconninfo 等其他字段不动 */
    /* 不删 slot，不释放 worker，由后续 ALTER SUBSCRIPTION ... ENABLE 重新启用 */
}
```

### 3.3 一图看清流程

```text
  apply worker 撞错
       │
       ├─► 1. 错误冒泡到 PG_CATCH
       ├─► 2. replorigin_reset(...)    ← 抹掉 origin 推进
       │
       ├─► disable_on_error = false    ┌─► 抛回顶层 → 进程崩溃
       │  （默认）                       │   launcher 检测到 → 重新拉 worker
       │                                │   （错误重现 → 再崩...）
       │                                │   现象：apply worker 反复重启
       │                                └─► 多次报错累积在 stats 里
       │
       └─► disable_on_error = true     ┌─► DisableSubscriptionAndExit()
                                       │   ├─► pg_subscription.subenabled = false
                                       │   ├─► log: "subscription ... has been disabled"
                                       │   └─► proc_exit(0) 干净退出
                                       │
                                       └─► 之后：
                                           • apply worker 不再被拉起
                                           • pg_stat_subscription 里能看到错误
                                           • 需要 DBA 介入：
                                             1. 查 log 找原因
                                             2. 修数据或修 SQL
                                             3. ALTER SUBSCRIPTION ... ENABLE
                                             4.  worker 从重置后的 origin 继续
```

### 3.4 生产建议

```sql
-- 1) 创建时就开
CREATE SUBSCRIPTION sub
    CONNECTION 'host=pub ...'
    PUBLICATION pub
    WITH (disable_on_error = true);   -- 强烈建议

-- 2) 配合监控：订阅状态变 disabled 时告警
SELECT subname, subenabled, suberr
FROM pg_stat_subscription
WHERE subenabled = false;
```

`pg_stat_subscription` 的字段：

| 字段 | 含义 |
| --- | --- |
| `subid` | 订阅 OID |
| `subname` | 订阅名 |
| `worker_type` | `apply` / `parallel apply` / `table synchronization` |
| `subenabled` | 是否启用 |
| `suberr` | 最近一次错误消息 |
| `sublasterror` | 错误时间 |

### 3.5 与 disable_on_error 联动的两个开关

```sql
ALTER SUBSCRIPTION sub SET (slot_name = NONE);    -- 不让 launcher 自动重建 slot
ALTER SUBSCRIPTION sub SET (disable_on_error = false);
ALTER SUBSCRIPTION sub ENABLE;
```

---

## 四、其他重要参数

### 4.1 binary：数据格式

源码 `pg_subscription.h:60`：`bool subbinary`，默认 `false`。

```text
  binary = false（默认）
    publisher 端 pgoutput 把每个值走 outfunc（文本格式）序列化
    subscriber 端 typio_in 解析

  binary = true
    publisher 端走 typsend（binary format）
    subscriber 端走 typreceive
```

**优势**：
- 类型不丢失（比如 timestamp 精度、numeric scale）
- 网络包更小（特别是 text/json 这种）

**限制**：
- **每个数据类型必须有 binary send/receive 函数**。
- 如果有类型只有文本传输能力，初始 COPY 会失败。
- 文档原文："the `binary` option cannot be used" if mismatch。

```sql
-- 检查一个类型是否支持 binary I/O
SELECT typname, typcategory, typsend, typreceive
FROM pg_type
WHERE typname IN ('point', 'interval', 'jsonb', 'uuid');
```

### 4.2 streaming：流式未提交事务

源码 `pg_subscription.h:163`：
```c
#define LOGICALREP_STREAM_OFF       'f'   /* 完全解码后再发送 */
#define LOGICALREP_STREAM_ON        't'   /* 流式，写临时文件，COMMIT 后 apply */
#define LOGICALREP_STREAM_PARALLEL  'p'   /* 并行 apply worker 边收边应用 */
```

默认值：`parallel`（PG 16+）。

```text
  streaming = off (f)
    publisher 等到事务 COMMIT 后才发送完整事务
    → 大事务延迟高，wal2json 风格
    → subscriber 看不到未提交事务的中间状态

  streaming = on (t)
    publisher 边生成边发送
    subscriber 写到临时文件，收到 COMMIT 才应用
    → 大事务延迟低
    → subscriber 写盘压力大（pg_replslot/workdir）

  streaming = parallel (p, 默认)
    publisher 边生成边发送
    subscriber 的 parallel apply worker 边收边 apply
    → 延迟最低
    → 但并行 apply worker 异常时，事务的 finish LSN 可能不报告
```

> ⚠️ **死锁风险**：当 publisher 和 subscriber 的表结构不一致时，apply worker 会自动重试，但极少情况可能死锁。文档有警告。

### 4.3 two_phase：两阶段提交

源码 `pg_subscription.h:62`：`char subtwophasestate`，三态：

```c
#define LOGICALREP_TWOPHASE_STATE_DISABLED  'd'
#define LOGICALREP_TWOPHASE_STATE_PENDING   'p'
#define LOGICALREP_TWOPHASE_STATE_ENABLED   'e'
```

`two_phase = true` 的语义：

```text
  publisher 执行 PREPARE TRANSACTION
    → 立即发送到 subscriber
    → subscriber 收到后 PREPARE 本地事务（不立刻 COMMIT）

  publisher 执行 COMMIT PREPARED
    → 发送 COMMIT 到 subscriber
    → subscriber COMMIT PREPARED 本地事务

  好处：
    • failover 时，subscriber 可以拿 prepared 状态接管
    • 配合 synchronous_commit 可实现"严格同步复制"
```

**关键限制**：PG 必须等到 initial table sync 完成才能真正启用两阶段。在那之前 state 是 `pending`，即使你 `two_phase = true`：

源码 `worker.c:84-105` 注释：

```
 * To avoid this, and similar prepare confusions the subscription's two_phase
 * commit is enabled only after the initial sync is over. The two_phase option
 * starts in PENDING state and is automatically upgraded to ENABLED once all
 * tables have completed the initial sync.
```

```sql
-- 查看实际两阶段状态
SELECT subname, subtwophasestate
FROM pg_subscription;

-- state:
--   d = disabled（关闭）
--   p = pending（等待 init sync 完成）
--   e = enabled（已启用）
```

### 4.4 failover：HA 同步 slot

源码 `pg_subscription.h:76, 132`：和订阅一起，关联 slot 也设置 `failover = true`，让 slot 的状态可以被同步到物理备机。

```text
  failover = false（默认）
    subscription 的 slot 是普通 slot
    publisher 主备切换后，新主不知道这个 slot，订阅中断

  failover = true
    subscription 的 slot 是 failover-enabled slot
    publisher 主备切换时，slot 的 confirmed_flush_lsn 同步到新主
    订阅可以无中断地继续在新主上工作
```

`CREATE SUBSCRIPTION` 时 `failover = true` 会让 PG 自动在 publisher 端把 slot 也创建成 failover-enabled。源码 `subscriptioncmds.c` 处理 `failover` 字段时会调 `ReplicationSlotCreate` 带 `failover = true`。

### 4.5 origin：多源复制

源码 `pg_subscription.h:95`：默认 `LOGICALREP_ORIGIN_ANY = "any"`。

```text
  origin = any（默认）
    subscriber 接受所有变更，无论是否带 origin（即使是它自己产生的变更）

  origin = none
    只接受没有 origin 标记的变更（即来自"源 publisher"的"）
    适用：把两个集群互相同步时防止回环
```

**双活复制**的典型配置：

```sql
-- 集群 A 上：
CREATE SUBSCRIPTION sub_b
    CONNECTION 'host=clusterB ...'
    PUBLICATION pub_for_a
    WITH (origin = 'cluster_a');  -- 拒收来自 cluster_a 的变更

-- 集群 B 上：
CREATE SUBSCRIPTION sub_a
    CONNECTION 'host=clusterA ...'
    PUBLICATION pub_for_b
    WITH (origin = 'cluster_b');  -- 拒收来自 cluster_b 的变更
```

`pgoutput` 插件在发送时给每条 change 打上 origin 标签，subscriber 端 `logical/relation.c` 根据 `origin` 参数过滤。

### 4.6 password_required：安全护栏

源码 `pg_subscription.h:69`：`bool subpasswordrequired`，默认 `true`。

```text
  password_required = true（默认）
    连接 publisher 必须用密码认证（md5/scram-sha-256/...）
    pg_hba.conf 不允许 trust / peer 等免密方式

  password_required = false（仅 superuser 可设）
    允许 trust 连接（极不安全，仅限 dev 环境）
```

文档原文：

> If set to `true`, connections to the publisher made as a result of this subscription must use password authentication. This setting is ignored when the subscription is owned by a superuser.

```sql
-- 必须带密码的连接串示例
CREATE SUBSCRIPTION sub
    CONNECTION 'host=pub user=repl_user password=xxx sslmode=require'
    PUBLICATION pub
    WITH (password_required = true);
```

### 4.7 synchronous_commit：apply 端的刷盘策略

源码 `pg_subscription.h:108`：`char *subsynccommit`，默认 `off`。

```text
  synchronous_commit = off（默认）
    apply worker 写完 WAL 后不等刷盘就返回
    → 复制延迟低，publisher 不被 subscriber 阻塞
    → 崩溃可能丢已 COMMIT 但未刷盘的变更
       （但 publisher 会重发，无数据丢失）

  synchronous_commit = local
    apply worker 等本地刷盘
    → 复制延迟增加
    → publisher 端被拖慢

  synchronous_commit = remote_write / remote_apply
    配合同步复制使用
    → 严格保证"publisher commit 即 subscriber 落盘"
```

### 4.8 copy_data：初始同步是否拷数据

源码在 `subscriptioncmds.c`，行为：

```text
  copy_data = true（默认）
    创建订阅后立即从 publisher COPY 全量数据
    然后开始 incremental replication

  copy_data = false
    订阅只接受 incremental 变更
    要求 subscriber 端已经手动准备好数据（schema + 初始内容）
    → 用于跨大版本升级 / 异构迁移
```

---

## 五、所有参数全景速查

源码 `pg_subscription.h` 给出的字段，对应到 `CREATE SUBSCRIPTION WITH (...)` 里的参数：

| 参数 | 类型 | 默认 | 含义 |
| --- | --- | --- | --- |
| `binary` | bool | false | publisher 用 binary 格式发 |
| `streaming` | enum | parallel | 流式 apply 模式 |
| `two_phase` | bool | false | 启用两阶段提交 |
| `disable_on_error` | bool | false | 错误即停 |
| `password_required` | bool | true | 必须密码认证 |
| `run_as_owner` | bool | false | 用订阅 owner 身份执行 |
| `failover` | bool | false | slot 可同步给备机 |
| `origin` | string | any | 接受变更的 origin 过滤 |
| `synchronous_commit` | enum | off | apply worker 刷盘策略 |
| `copy_data` | bool | true | 是否做初始全量复制 |
| `connect` | bool | true | ALTER SUBSCRIPTION ... ENABLE 时立即连 |
| `slot_name` | name | 自动生成 | publisher 端 slot 名 |
| `publications` | list | 必填 | 订阅哪些 publication |
| `create_slot` | bool | true | 自动在 publisher 端建 slot |
| `enabled` | bool | true | 创建后是否立即启用 |

---

## 六、调试与排查

### 6.1 看订阅状态

```sql
SELECT subname,
       subenabled,
       subslotname,
       subtwophasestate,
       substream,
       subbinary,
       subdisableonerr,
       subrunasowner
FROM pg_subscription;
```

### 6.2 看运行中的 worker 状态

```sql
-- 看 apply worker 的统计
SELECT pid, application_name, state, query, wait_event_type, wait_event
FROM pg_stat_activity
WHERE application_name LIKE 'sub_%' OR application_name LIKE '%logical%';

-- 看错误
SELECT * FROM pg_stat_subscription;
```

### 6.3 看 slot 状态

```sql
-- publisher 端
SELECT slot_name, plugin, database, active, restart_lsn,
       confirmed_flush_lsn, failover
FROM pg_replication_slots;

-- subscriber 端确认 slot 在 publisher 上存在
SELECT slot_name, plugin, slot_type, database
FROM pg_replication_slots
WHERE slot_type = 'logical';
```

### 6.4 监控订阅延迟

```sql
-- subscription 视角（PG 13+）
SELECT subname,
       received_lsn,
       latest_end_lsn,
       latest_end_time,
       pg_size_pretty(pg_wal_lsn_diff(latest_end_lsn, received_lsn)) AS apply_lag_bytes,
       EXTRACT(EPOCH FROM (now() - latest_end_time)) AS apply_lag_seconds
FROM pg_stat_subscription;
```

### 6.5 当 disable_on_error 触发后怎么恢复

```sql
-- 1) 看错误
SELECT subname, suberr FROM pg_stat_subscription WHERE subenabled = false;

-- 2) 看 worker log
-- postgresql.log 里搜：subscription "..." has been disabled because of an error

-- 3) 修复数据/schema（必要时）

-- 4) 重新启用
ALTER SUBSCRIPTION sub ENABLE;

-- 5) 验证进度继续推进
SELECT subname, received_lsn, latest_end_lsn, latest_end_time
FROM pg_stat_subscription;
```

---

## 七、常见组合与陷阱

### 7.1 高安全 + 高容错的"生产稳态"

```sql
CREATE SUBSCRIPTION sub
    CONNECTION 'host=pub.prod user=repl_user password=xxx sslmode=require'
    PUBLICATION pub
    WITH (
        run_as_owner = false,         -- 默认，但显式写出
        disable_on_error = true,      -- 错就停，别陷入重启循环
        password_required = true,     -- 默认
        binary = true,                -- 减少类型转换
        streaming = parallel,         -- 默认
        origin = 'none',              -- 防回环
        synchronous_commit = off      -- 默认，避免拖慢 publisher
    );
```

### 7.2 大版本升级/迁移

```sql
-- 老集群做 publication，新集群：
CREATE SUBSCRIPTION sub
    CONNECTION 'host=old_db user=repl'
    PUBLICATION pub_for_migration
    WITH (
        copy_data = true,             -- 全量同步
        binary = false,               -- 老版本可能不支持
        streaming = off               -- 防止大表并行问题
    );

-- 验证完毕，切流量：
-- 1) 老库停写入
-- 2) 新库等 apply 完
-- 3) 应用切到新库

-- 4) 删订阅
DROP SUBSCRIPTION sub;
```

### 7.3 双向复制（双活）

```sql
-- A 上：
CREATE SUBSCRIPTION sub_b
    CONNECTION 'host=B user=repl ...'
    PUBLICATION pub_for_a
    WITH (origin = 'B');    -- 拒收 B 的变更，避免回环

-- B 上：
CREATE SUBSCRIPTION sub_a
    CONNECTION 'host=A user=repl ...'
    PUBLICATION pub_for_b
    WITH (origin = 'A');
```

### 7.4 改参数后要 disable/enable

```sql
-- 这些参数改了必须重启 worker（disable → set → enable）
ALTER SUBSCRIPTION sub DISABLE;
ALTER SUBSCRIPTION sub SET (run_as_owner = true, disable_on_error = true);
ALTER SUBSCRIPTION sub ENABLE;

-- 这些参数可以热改（不需要 disable）
ALTER SUBSCRIPTION sub SET (slot_name = 'new_slot');
ALTER SUBSCRIPTION sub SET (synchronous_commit = 'local');
```

---

## 八、总结

逻辑复制的每个订阅参数都不是孤立的，它们形成一个**安全 × 容错 × 性能 × 一致性**的拉杆矩阵：

```text
                    安全
                    ──
       password_required (是否要密码认证)
       run_as_owner      (身份切换)
              │
              │
              ▼
       ┌─────────────┐
       │  apply       │
       │  worker      │
       │              │
       └──────┬──────┘
              │
              ├───► 容错：disable_on_error
              ├───► 一致性：two_phase, origin, synchronous_commit
              ├───► 性能：streaming, binary
              └───► 可用性：failover, copy_data
```

记住这几条经验法则：

1. **`run_as_owner = false`（默认）才安全**——除非你完全信任所有目标表的 owner。
2. **`disable_on_error = true` 生产必备**——否则错误会陷入重启循环。
3. **`password_required` 别改 false**——除非 dev 环境。
4. **改 `run_as_owner` 等"硬参数"必须 disable→set→enable**。
5. **`origin` 双向复制时是关键**——防止环回。
6. **`streaming = parallel`**（默认）是最优解——除非有特殊大表场景。
7. **`binary = true` 类型兼容时建议开**——更小、更快、更准。

理解这些参数的源码位置（`pg_subscription.h` 列定义、`worker.c` 应用逻辑、`subscriptioncmds.c` 参数解析），下次遇到逻辑复制问题，能直接定位到正确的那一行。

---

## 参考资料

- PostgreSQL 18 dev 源码：
  - `src/include/catalog/pg_subscription.h` — `pg_subscription` 系统表 + `Subscription` 内存结构
  - `src/backend/replication/logical/worker.c` — `run_as_owner` (L2427)、`disable_on_error` (L4508)、`DisableSubscriptionAndExit` (L4838)
  - `src/backend/commands/subscriptioncmds.c` — 参数解析（L275 `disable_on_error`、L290 `run_as_owner`）
  - `src/backend/catalog/pg_subscription.c` — `DisableSubscription` 实现（L200）
  - `src/include/catalog/pg_subscription.h` — `LOGICALREP_STREAM_*` 常量（L163-165）、`LOGICALREP_TWOPHASE_STATE_*`（L145-147）
- 官方文档：
  - `doc/src/sgml/ref/create_subscription.sgml` — 所有参数语义
  - `doc/src/sgml/logical-replication.sgml:2259` — Security 章节（`run_as_owner` 风险）
- [PostgreSQL Documentation — Logical Replication](https://www.postgresql.org/docs/current/logical-replication.html)
