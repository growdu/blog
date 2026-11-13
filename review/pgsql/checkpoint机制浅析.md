# 审校：checkpoint 机制浅析

- 原文：`docs/pgsql/checkpoint机制浅析.md`
- 范围：全文
- 目标读者：读过《WAL 机制浅析》、想知道 checkpoint 到底做了什么、什么时候触发的开发者
- 一句话定位：把 checkpoint 从「参数与触发条件」讲到「一次 checkpoint 依次刷了哪些缓存」，并解释它为什么决定了崩溃恢复要重放多少 WAL
- 核心判断：checkpoint 的成本不在「刷脏页」本身，而在它要同时照顾 clog/subtrans/multixact/predicate 这几类 SLRU 缓存——这决定了 checkpoint 不能想多久做多久
- 审校状态：建议中

## 优先修改

1. 位置：全文（L44-53「与检查点相关参数」整节）
   - 问题：整节参数表描述的是 **PostgreSQL 9.4 及更早**的行为，却没有任何版本标注。`checkpoint_segments` 在 **9.5 已被删除**，由 `max_wal_size`（默认 1GB）/ `min_wal_size`（默认 80MB）取代；`checkpoint_completion_target` 的默认值在 9.5 是 0.5、**9.6 起是 0.9**。读者现在去调 `checkpoint_segments` 会直接报参数不存在
   - 建议：在参数节开头加一行版本声明，并在每个参数后标注适用版本，例如：
     - `max_wal_size`（9.5+，默认 1GB）—— 替代旧的 `checkpoint_segments`
     - `min_wal_size`（9.5+，默认 80MB）
     - `checkpoint_timeout`（默认 5min）—— 版本间未变
     - `checkpoint_completion_target`（默认 0.5 → **9.6+ 起 0.9**）
     - `checkpoint_warning`（默认 30s）—— 版本间未变
   - 原因：这是全文最硬的问题——参数名在当前版本里不存在，读者照着做一定失败。README 原则 1 要求保真，但保真的前提是**说清楚这个结论针对哪个版本**

2. 位置：L61「遍历所有的数据buffer，将脏页块状态从BM_DIRTY改为BM_CHECKPOINT_NEEDED」
   - 问题：`BM_CHECKPOINT_NEEDED` 这个标志在 **PG 9.5 就被移除了**（随 `BufferSetCheckpointNeeded()` 一起删掉）。9.4 之后 `CreateCheckPoint()` 走的是 `CheckPointBuffers()` → `BufferSync()` 直接刷脏页，不再有「先改标志位」这一步。L79-80 的 `prevCheckPoint` 注释（「最后一个完全检查点位置写在 prevCheckPoint 上」）也是 9.4 之前的设计——现代 PG 的 `ControlFileData` 里 `prevCheckPoint` 已被 `checkPointCopy` 取代
   - 建议：把第 1 步改成 PG 9.5+ 的真实流程，并注明「9.4 及更早是 BM_DIRTY → BM_CHECKPOINT_NEEDED 两段式」作为对照
   - 原因：读者拿着这段去看 PG 17 源码会找不到 `BM_CHECKPOINT_NEEDED`，会以为自己在看一个废弃的实现——这正是「技术密度」反噬的地方：细节越具体，版本不对的伤害越大

3. 位置：L102「需要在recovery.conf配置文件中设置目标时间线」
   - 问题：`recovery.conf` 在 **PG 12 已被移除**，改成 `recovery.signal` 标记文件 + `postgresql.conf` 里的 `restore_command` / `recovery_target_timeline` / `recovery_target_time`。现在的 PG 会直接报 `recovery.conf` 不存在
   - 建议：改成 `recovery.signal` + `postgresql.conf` 的写法，并标注「12 之前是 recovery.conf」
   - 原因：同上——这是「照着做就失败」的级别

4. 位置：L11-32（`xlog.h` 代码块）与 L68-89（`ControlFileData` 代码块）
   - 问题：代码块里的空格被吃掉了，`#define CHECKPOINT_IS_SHUTDOWN0x0001/* Checkpoint is for shutdown */` 这种宏名、值、注释全黏在一起，完全不可读；两个代码块都没有标语言（应标 `c`）
   - 建议：按原样恢复对齐（宏名、值、注释分列），并给围栏加 ```c
   - 原因：贴源码是这篇文章的主要证据来源，贴坏了等于没有证据。README 原则 6 说技术感来自源码——但排版坏掉的源码只会传递「作者没核对过」

5. 位置：L1（文件开头）
   - 问题：文章从 `## 背景` 开始，**没有 H1 标题**（MET-02），标题只能靠文件名；也没有「编写人 / 编写内容 / 编写时间」信息表（MET-01），读者不知道这文章对应哪个 PG 版本、什么时候写的
   - 建议：补 H1 标题（建议 `# PostgreSQL Checkpoint 机制浅析`），并按仓库惯例补上编写人信息表，编写时间一栏写清**本文对应的 PG 版本**
   - 原因：文章开头已经在讲版本相关的事，版本就该写在最显眼的地方

6. 位置：L3
   - 问题：开头引用「上期月报[PgSQL · 特性分析 · Write-Ahead Logging机制浅析](http://mysql.taobao.org/monthly/2017/03/02/)」——这个域名是阿里内网旧站，**现在外部打不开**；而且文章说「上期」，读者接不上
   - 建议：换成本仓库里的《WAL 机制浅析》（`docs/pgsql/wal机制浅析.md`），改成「上一篇《WAL 机制浅析》讲的是……本文讲 checkpoint」；顺带把「上期月报」这种时间指代改成可点的前文链接
   - 原因：这正是 README 要的「一条自然的内容路径」。仓库里明明有同系列的 WAL 文章，链接却指到一个死链

7. 位置：L5、L100、L102（三段超长）
   - 问题：AIF-03 命中——L5（218 字）、L100（229 字）、L102（227 字）连续三段各超过 200 字，其中 L100 讲时间线历史文件、L102 讲 PITR 定位，两段内容其实可以拆成「时间线机制」和「PITR 怎么用」两节
   - 建议：L5 拆成「checkpoint 是什么」+「它和崩溃恢复的关系」两段；L100/L102 提升为独立小节 `### 时间线历史文件` 与 `### PITR 怎么定位目标时间线`
   - 原因：README 的修改方法之一是「把大段概述拆为短段」；而且时间线/PITR 这块本可以独立成篇，拆出来还能多一篇内容

8. 位置：L140-L146「总结」
   - 问题：结尾三条结论都没说清**「什么时候该动 checkpoint 参数」**——只说「开销比较高，可以用 checkpoint_warning 自检，相应调大 checkpoint_segments」，而调大 checkpoint_segments 这个建议在 9.5+ 已经无效
   - 建议：把第三条改成 PG 9.5+ 的口径：「用 `checkpoint_warning` 观察实际间隔是否超过 `checkpoint_timeout`，需要拉长就用 `max_wal_size` 而不是 `checkpoint_segments`」
   - 原因：结尾是读者唯一会带走的部分，不能给一个在当前版本失效的操作建议

## 事实待核

- L61 的 `BM_CHECKPOINT_NEEDED` 移除版本：文中按 9.4 及更早描述。需对照 `~/cwork/postgresql` 与 PG 9.4/9.5 的 `bufmgr.c` 确认移除版本号与替代流程后再改写，不能凭印象写「9.5」
- L77-78 的 `ControlFileData` 字段：文中同时给出 `checkPoint` / `prevCheckPoint` / `minRecoveryPoint` / `minRecoveryPointTLI`。`minRecoveryPoint` 与 `minRecoveryPointTLI` 在新版 PG 里是否还存在、是否已挪到 `XLogCtl`，需按目标版本核对 `src/include/catalog/pg_control.h`
- L90 的说法「minRecoveryPoint 和 minRecoveryPointTLI 确定数据库启动前……必须恢复到的最小检查点」与 L100-102 的时间线历史文件机制是同一件事的两面，两处的表述需要统一，不能一处讲「最小恢复点」一处讲「时间线定位」
- L132「前四个函数最后都调用了 SLRU 模块的 SimpleLruFlush」：按 L122-130 的列举顺序，CLOG/SUBTRANS/MULTIXACT/PREDICATE 走 SLRU、RELATIONMAP 不用 SLRU。需确认「前四个」的指代与列举顺序一致（现在的顺序里 RelationMap 排在第五，文字却另起一段解释它，读者容易误以为它在「前四个」里）
- L134「后二个函数没有使用 SLRU 算法，直接调用 pg_fsync」：需确认 `CheckPointTwoPhase` 是否也走 `pg_fsync` 直刷，还是与 RelationMap 一样有专门路径

## 可补的技术证据或产物

- 机制 / 源码入口：文章给了 `xlog.h`、`CheckPointGuts`、`ControlFileData` 三处。缺最关键的两处——`src/backend/postmaster/checkpointer.c`（checkpointer 这个辅助进程怎么按 `checkpoint_timeout` / `max_wal_size` 决定何时触发，文中的第 4、5 条触发条件就出自这里）和 `src/backend/access/transam/xlog.c` 的 `CreateCheckPoint()`（文中的「具体过程」四步就是它的主干）
- 实验或观测：给一条真能跑的观测——checkpoint 期间用 `SELECT * FROM pg_stat_progress_checkpoint;` 看 `buffers_written` / `write_time`，或用 `pg_waldump` 对比两次 checkpoint 之间的 WAL 量。现在文章讲的全是「代码里写了什么」，没有一条「我怎么看见它」
- 工程取舍：文章提到「checkpoint 的开销比较高」，但没讲**取舍**：checkpoint 间隔调长 → 崩溃恢复要重放的 WAL 变多（恢复变慢）；调短 → 写放大和 I/O 尖峰变多。这正是 README 说的「不只给唯一最佳实践」。可以补一段「什么时候该调 max_wal_size，什么时候该调 checkpoint_timeout」
- 结尾清单或下一篇链接：结尾只有三条结论。可补一页排查清单——「checkpoint 相关告警该先看哪三张视图：`pg_stat_bgwriter`（checkpoint 频率与耗时）、`pg_stat_wal_receiver`/`pg_stat_wal_sender`（复制场景的 WAL 保留量）、`pg_stat_progress_checkpoint`」，并链到同目录的《WAL 机制浅析》与《PostgreSQL 崩溃恢复》（`docs/pgsql/` 下）

## 已确认的改动

- 无（阶段 A 只出记录，未改动 `docs/`）
