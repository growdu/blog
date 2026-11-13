# 审校：PostgreSQL 逻辑复制的 Worker 模型

- 原文：`docs/database/postgresql-logical-replication-worker-model/index.md`
- 范围：全文
- 目标读者：正在给分区表做逻辑复制、需要搞清楚要起多少 worker 的 DBA 与开发者
- 一句话答案（文章自己的）：**一个 subscription 永远只有一个 apply worker**，分区表加多少叶子都不增加；能并行的是初始同步阶段的 tablesync worker
- 核心判断：分区表的并行化被 PG 交给了内核的 partition routing，而不是靠堆 apply worker——所以 worker 数与分区数无关
- 审校状态：建议中

## 优先修改

1. 位置：L30（`## 二、三种 worker 类型`）与 L63-L70（表头写「四种 worker 的分工」）
   - 问题：标题说「**三种** worker 类型」，紧接着的表说「**四种** worker 的分工」，而代码里 `LogicalRepWorkerType` 枚举确实只有三种（TABLESYNC / APPLY / PARALLEL_APPLY），**Launcher 不在枚举里**。读者对着枚举看表，会以为漏了一个枚举值，或者以为 Launcher 也是一种 worker 类型
   - 建议：把小节标题改成「二、三类 apply 类 worker + 一个 Launcher」，并把表格拆成两张或加一列「是否 `LogicalRepWorkerType` 枚举成员」；在 Launcher 那一行注明「Launcher 不是 worker 类型，它常驻监控 `pg_subscription` 并按需拉起 apply worker」
   - 原因：这是全文第一处自相矛盾，而出现在**第二节**——读者在这里建立的心智模型会一路带偏

2. 位置：L22-L24（「一、一句话答案」的引用块）
   - 问题：最该被看到的答案被放在 `>` 引用块里，渲染成引用样式，视觉权重低于正文；同时这一节和 L26 的过渡句之间被 `---` 分隔线切开
   - 建议：把这两段改成普通正文加粗（或用引用块的样式但去掉 `>`），让「不需要 / 一个 subscription 永远只有一个 apply worker」成为页面第一眼看到的内容
   - 原因：README 要求「开头讲清楚文章替读者解决什么难题」。这篇文章的答案质量很高，不该被排版埋掉

3. 位置：L3-L18（开头引用块列出的 5 个源码路径）与全文链接统计（**只有 1 条链接**）
   - 问题：开头的姊妹篇链接（L5）是全文唯一的链接，而「PostgreSQL 逻辑复制」这个系列在 `docs/database/` 下有 **16 篇**（`postgresql-logical-replication-*`）。读者读完这篇想知道「分区表 INSERT 的完整路径」得自己去找
   - 建议：在开头或文末加一个**系列目录**，把 16 篇按主题分组列出并全部链上（如「机制：end-to-end-flow / worker-model / options」「分区表：partitioned-insert-flow / with-partitioned-tables / publish-via-partition-root」「工程化：monitoring / throughput-benchmark / docker-setup」）
   - 原因：README 把「一条自然的内容路径」列为必做项。系列已经成规模（16 篇），互链却只有 1 条——这是整个逻辑复制系列共同的缺口，应该在系列层面一次性补齐，而不是每篇各补

4. 位置：L564-L635（九、调优建议）到 L680（十一、结语）之间的第十节
   - 问题：「十、修改指南：要加新 worker 类型 / 改变 worker 关系时碰哪些文件」是全文**最有价值、最可带走**的部分（README 说的「一份可带走的产物」），但它被放在**倒数第二节**，且结语（十一）用一张结论表把读者注意力引走了——结果是「修改指南」这个最实用的产物被埋了
   - 建议：把第十节「修改指南」上移到结语之后作为**最后一节**（读者带着「我要改代码」的意图来，最该最后看到）；或在结语表后加一句「要改代码？直接看第十节：碰哪些文件、哪几个函数」
   - 原因：文章结构应该服务于读者的意图。这篇有三种读者意图——**搞懂**（看一二三节）、**排障**（看九、结语表）、**改代码**（看第十节）。现在的顺序把「改代码」放在中间，最强的意图反而最难找

5. 位置：L680-L700（十一、结语）
   - 问题：结语只有一张结论表 + 一个「黄金公式」，**没有串起全文的因果**。表格是「是什么」的汇总，读者拿不走「为什么」
   - 建议：表格前补一段三句话的收束——「apply worker 唯一常驻 → 所以 worker 数与分区数无关 → 所以分区表的并行化由内核 routing 承担，扩展性问题转移给了 partition routing」。文末那个「黄金公式」其实已经写对了因果（"这就是 PG 逻辑复制能在线性扩展的根本原因——它把分区表的并行化问题留给了内核的 partition routing"），把它提到表格前面当引子，结论表当证据
   - 原因：README 要「一个可记住的判断」。结论表是六行答案，判断只有那最后一段——顺序反了

6. 位置：L76-L120（三、worker 的全局资源限制）与 L680（十、修改指南）
   - 问题：全文 DEP-04（工程取舍）只命中 3 处——三个协议/机制都讲得清楚，但**「为什么 PG 要这么设计」和「代价是什么」没展开**
   - 建议：补一小节「设计取舍」：① 为什么 apply worker 不并行——并行 apply 要处理事务内 change 的依赖顺序，PG 16 的 parallel apply 是**按事务拆分**（大事务才拆），代价是 worker 生命周期与协调开销；② tablesync worker 为什么按 `pg_subscription_rel` 分行而不是按分区表分——避免分区表被拆成 N 个 COPY 任务导致恢复点漂移；③ `max_logical_replication_workers` 是共享池（结语表已指出）带来的排障陷阱：tablesync 吃满配额会导致 apply worker 起不来
   - 原因：这是全文从「机制说明」升级为「工程判断」的关键一步，也是 cluster/database 支柱定位里「写出自己的工程判断」那条要求的落点

## 事实待核

- L32 `src/include/replication/worker_internal.h:31` 与 L78 `src/backend/replication/logical/launcher.c:50`：行号是针对特定 PG 版本（文中写 PG 17）。需确认这两个行号在 PG 17 源码上是否仍指向所述内容——行号会随版本漂移，建议改成「符号名 + 文件路径」并在括号里注明版本
- L36-L41 的枚举注释「PG 16+」：`WORKERTYPE_PARALLEL_APPLY` 是 PG 16 引入的，需确认枚举值与注释在 PG 17 源码中的实际写法（后续版本可能新增了成员，如 `WORKERTYPE_STREAMING`）
- L38 `WORKERTYPE_TABLESYNC` 与 L50 `PARALLEL_APPLY`：文中同时提到「streaming」相关能力（Babelfish 模式、streaming spill 系列文章），需确认这三类枚举是否覆盖 streaming 场景；若有独立的 streaming worker 类型，第三节的「三种」和结语表的 worker 清单都要补
- L81「`max_logical_replication_workers` 是 apply 还是 tablesync 还是 sum？→ **sum**」：这是结语表里的断言，需按 PG 17 的 `logical.c` 实际取值逻辑核对（不同版本对 `max_logical_replication_workers` 与 `max_worker_processes` 的关系、以及 logical worker 配额是否受 `max_sync_workers_per_subscription` 二次约束，处理方式有差异）
- L564 起关于 Babelfish T-SQL 模式的差异（第八节）：Babelfish 是 PG 的商业分支，其 worker 模型与社区版可能不同。文中第八节说「没有不同——完全复用 PG 原生 worker 模型」，这个断言需要对照 Babelfish 分支源码确认；结论写进结语表之前尤其要核实

## 可补的技术证据或产物

- 机制 / 源码入口：文章已给出 5 个路径（含 `launcher.c` / `worker.c` / `tablesync.c` / `applyparallelworker.c` / `worker_internal.h`），覆盖很全。缺 `src/backend/replication/logical/applyparallelworker.c` 之外的**协调侧**：`src/backend/replication/logical/worker.c` 里 apply worker 拉起 parallel worker 的入口函数（第五节讲「worker 之间的依赖关系」的关键）
- 实验或观测：全文 27 个代码块，但没有一条「我怎么看见 worker 在跑」的观测命令。可补：`pg_stat_subscription`（看每个 subscription 的 worker 状态与 lag）、`pg_stat_replication`（看 apply 进度）、`pg_stat_progress_subscription`（看 tablesync 的 COPY 进度）——尤其 tablesync 阶段最需要「现在到哪了」的可见性
- 工程取舍：见优先修改第 6 条，这是本篇最值得补的一块
- 结尾清单或下一篇链接：结语表是「答案表」，不是「产物」。可补一页运维清单——「逻辑复制起不来 / 变慢，按这个顺序查：① `pg_stat_subscription` 看 apply worker 状态 → ② `max_logical_replication_workers` 是否被 tablesync 占满 → ③ `pg_stat_progress_subscription` 看是否卡在初始 COPY → ④ 大事务场景确认是否需要调 `max_parallel_apply_workers_per_subscription`」，并链到本系列的《逻辑复制端到端全链路》《逻辑复制监控》《逻辑复制吞吐量基准》

## 已确认的改动

- 无（阶段 A 只出记录，未改动 `docs/`）
