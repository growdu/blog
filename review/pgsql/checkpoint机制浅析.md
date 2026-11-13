# 审校：checkpoint 机制浅析

- 原文：`docs/pgsql/checkpoint机制浅析.md`
- 范围：全文
- 目标读者：读过《WAL 机制浅析》、想知道 checkpoint 到底做了什么、什么时候触发的开发者
- 一句话定位：把 checkpoint 从「参数与触发条件」讲到「一次 checkpoint 依次刷了哪些缓存」，并解释它为什么决定了崩溃恢复要重放多少 WAL
- 核心判断：checkpoint 的成本不在「刷脏页」本身，而在它要同时照顾 clog/subtrans/multixact/predicate 这几类 SLRU 缓存——这决定了 checkpoint 不能想多久做多久
- 审校状态：已合入

> **核实记录**：本篇的版本类论断全部对照 `~/cwork/postgresql`（REL_17_9-20-g99524a62871，
> 仓库含 REL_10_0 ~ REL_18_2 全部标签）逐条核实。**核实过程中发现审校初稿本身有 4 条
> 论断是错的，已在下面标注并撤回**——其中 3 条会导向错误的正文修改。

## 优先修改

1. 位置：L44-53「与检查点相关参数」整节
   - 问题：整节参数表写的是 **PG 9.x** 的参数，其中 `checkpoint_segments` 在 **PG 10** 就被
     `min_wal_size` / `max_wal_size` 取代，现在设置它直接报 `unrecognized configuration parameter`；
     `checkpoint_completion_target` 的默认值 PG 10~13 是 0.5、**PG 14 起才是 0.9**
   - 建议（已采用）：改成带版本列的表格，逐个标注「PG 10 引入」「PG 14 起默认 0.9」，
     并保留一段「旧参数 `checkpoint_segments`」的说明，讲清它被谁取代
   - 原因：这是全文最硬的问题——参数名在当前版本里不存在，读者照着做一定失败

2. 位置：L61「遍历所有的数据buffer，将脏页块状态从BM_DIRTY改为BM_CHECKPOINT_NEEDED」
   - 问题：**此条撤回**。核实结论相反：`BM_CHECKPOINT_NEEDED` 是 **PG 10 引入**的
     （commit `867e2c91a0c` "Implement distributed checkpoints"，首次含它的发布标签是
     REL_10_0），至今仍在 `src/include/storage/buf_internals.h:68`，**没有被移除**。
     PG 17 的 `BufferSync()`（`src/backend/storage/buffer/bufmgr.c:2963`）正是
     `buf_state |= BM_CHECKPOINT_NEEDED;`，文章描述的机制是对的
   - 建议（已采用）：不改机制描述，只把「改为」改成「额外打上标志」——因为 BM_DIRTY 本身
     并不会被清掉，写盘时才一起清（`bufmgr.c:5667`）
   - 原因：保留原文的机制描述，只修正措辞；顺带在参数节末尾补一段「分布式 checkpoint」
     的机制说明，把 BM_CHECKPOINT_NEEDED 讲透

3. 位置：L102 `recovery.conf`
   - 问题：`recovery.conf` 在 **PG 12 已被移除**，改成数据目录里的 `recovery.signal`
     标记文件 + `postgresql.conf` 里的恢复参数。核实依据：REL_11_22 全树有 60 个文件
     提到 `recovery.conf`、0 个提到 `recovery.signal`；REL_12_0 起出现 `recovery.signal`
     （`src/backend/access/transam/xlog.c:6424` 的 errhint）
   - 建议（已采用）：保留 `recovery.conf` 的历史说法，但明确标注版本边界，并给出 PG 12+
     的 `recovery.signal` + `postgresql.conf` 写法
   - 原因：读者现在去写 `recovery.conf` 会直接报错

4. 位置：L109-129（`ControlFileData` 代码块）
   - 问题：代码块里空格被吃掉（`typedefstruct`、`XLogRecPtrcheckPoint`），不可读；
     字段里还留着 **`prevCheckPoint`**——该字段在 **PG 10** 的 "Remove secondary checkpoint"
     （commit `4b0d28de06b`）中被移除，PG 17 的 `src/include/catalog/pg_control.h`
     里只有 `checkPoint` / `checkPointCopy` / `minRecoveryPoint` / `minRecoveryPointTLI` /
     `backupStartPoint`，**没有 `prevCheckPoint`**
   - 建议（已采用）：恢复对齐 + 标 ```c；删掉 `prevCheckPoint` 字段，加一段版本差异说明
     讲清它当年是干什么的（记「上一个完全写完的 checkpoint」）以及为什么被移除
   - 原因：贴源码是这篇文章的主要证据来源，贴坏了等于没有证据

5. 位置：L1（文件开头）
   - 问题：文章从 `## 背景` 开始，**没有 H1 标题**（MET-02），标题只能靠文件名；也没有
     「编写人 / 编写内容 / 编写时间」信息表（MET-01）
   - 建议（已采用）：补 H1 标题与编写人信息表；并在开头加一段**版本声明**——本文代码与
     字段基于 PG 9.x，当前版本差异单独标出
   - 原因：这篇文章讲的就是版本相关的行为，版本不写出来，后面每一条都得重复解释

6. 位置：L3
   - 问题：开头引用「上期月报[PgSQL · 特性分析 · Write-Ahead Logging机制浅析](http://mysql.taobao.org/monthly/2017/03/02/)」——
     这个域名是阿里内网旧站，**现在外部打不开**；而且「上期」这种时间指代读者接不上
   - 建议（已采用）：换成本仓库里的《[WAL 机制浅析](./wal机制浅析.md)》
   - 原因：README 要的「一条自然的内容路径」。仓库里明明有同系列的 WAL 文章

7. 位置：L5、L100、L102（三段超长，AIF-03）
   - 问题：三段各超过 200 字，L100/L102 讲的是时间线历史文件与 PITR 定位，本可以独立成节
   - 建议（已采用）：L5 拆两段；把时间线历史文件提成 `### 时间线历史文件` 小节；PITR
     定位拆成三段并把版本差异做成引用块
   - 原因：README 的修改方法之一是「把大段概述拆为短段」

8. 位置：L104-138「CheckPointGuts 函数」
   - 问题：代码块里的调用顺序是 **PG 9.x** 的（`RelationMap` 排在 `Predicate` 之后），
     PG 17 的顺序已经变了，而且**多了 5 个模块**（ReplicationSlots / SnapBuild /
     LogicalRewriteHeap / ReplicationOrigin / CommitTs）
   - 建议（已采用）：保留 9.x 的代码块并标注版本，紧跟一段 PG 17 的实际顺序
   - 原因：读者照着 PG 17 源码找会以为少了东西

9. 位置：L140-L146「总结」
   - 问题：结论第 2 条让读者「相应调大 checkpoint_segments」——这个参数名在 PG 10 就没了
   - 建议（已采用）：改成调 `max_wal_size`；并补一段「代价落在哪里」——间隔调长则恢复要
     重放的 WAL 变多，调短则写放大和 I/O 尖峰变多，先分清瓶颈是「恢复慢」还是「写入抖」
   - 原因：结尾是读者唯一会带走的部分，不能给一个失效的操作建议

## 事实待核

> 以下 5 条已全部核实完毕，核实依据写在每条后面。**其中第 1、2 条推翻了审校初稿的判断**。

- [x] `BM_CHECKPOINT_NEEDED` 的移除版本 —— **初稿判断有误**。该标志由 commit
  `867e2c91a0c`（"Implement distributed checkpoints"）引入，首次发布的版本是 **REL_10_0**，
  且**至今仍在** PG 17 的 `buf_internals.h:68`。它从未被移除
- [x] `checkpoint_segments` 被哪个版本取代 —— **初稿写的「9.5」不对**，实际是 **PG 10.0**
  （commit `88e98230268` "Replace checkpoint_segments with min_wal_size and max_wal_size"；
  REL_10_0 的 `postgresql.conf.sample` 里首次出现 `max_wal_size`，`checkpoint_segments` 从此消失）
- [x] `checkpoint_completion_target` 默认值 —— **初稿写的「9.6 起 0.9」不对**。实测
  REL_10_0 / 11 / 12 / 13 默认均为 **0.5**，**REL_14_0 起才是 0.9**
  （PG 17 源码 `guc_tables.c:3934` 可见 `0.9, 0.0, 1.0`）
- [x] `ControlFileData` 的字段 —— PG 17 `src/include/catalog/pg_control.h` 实测：有
  `checkPoint`、`checkPointCopy`、`minRecoveryPoint`、`minRecoveryPointTLI`、
  `backupStartPoint`；**没有 `prevCheckPoint`**（该字段随 PG 10 的 "Remove secondary
  checkpoint" 一并移除）
- [x] 「前四个函数调用 SLRU」与列举顺序是否一致 —— 一致。`CheckPointCLOG` /
  `CheckPointSUBTRANS` / `CheckPointMultiXact` / `CheckPointPredicate` 走 SLRU 的
  `SimpleLruFlush`；`CheckPointRelationMap` 单独刷 map 文件；`CheckPointBuffers` 与
  `CheckPointTwoPhase` 直接 `pg_fsync`

## 可补的技术证据或产物

- 机制 / 源码入口：文章给了 `xlog.h`、`CheckPointGuts`、`ControlFileData` 三处。缺两处
  最关键的——`src/backend/postmaster/checkpointer.c`（checkpointer 辅助进程怎么按
  `checkpoint_timeout` / `max_wal_size` 决定何时触发；文中第 4、5 条触发条件就出自这里）
  和 `src/backend/access/transam/xlog.c` 的 `CreateCheckPoint()`（文中「具体过程」四步的主干）
- 实验或观测：全文讲的是「代码里写了什么」，没有一条「我怎么看见它」。可补：
  checkpoint 期间用 `SELECT * FROM pg_stat_progress_checkpoint;` 看 `buffers_written` /
  `write_time`，或用 `pg_waldump` 对比两次 checkpoint 之间的 WAL 量
- 工程取舍：见优先修改第 9 条（已补入正文）。原文只说「开销比较高」，没说代价往哪边走
- 结尾清单或下一篇链接：结尾有三条结论 + 代价说明，但仍缺一页排查清单——「checkpoint
  相关告警该先看哪三张视图：`pg_stat_bgwriter`（频率与耗时）、`pg_stat_progress_checkpoint`
  （当前这一次）、`pg_stat_wal_sender`（复制场景的 WAL 保留量）」

## 已确认的改动

- 开头补 H1 标题「PostgreSQL Checkpoint 机制浅析」+ 编写人信息表 + **版本声明**（本文基于
  PG 9.x，版本差异单独标出）
- 开头死链（`mysql.taobao.org` 旧月报）换成本仓库《[WAL 机制浅析](./wal机制浅析.md)》，
  并补一句「本文回答三个问题」
- `xlog.h` 代码块恢复对齐、标 ```c
- 参数节改成带版本列的表格：`max_wal_size` / `min_wal_size`（PG 10 引入）、
  `checkpoint_timeout`、`checkpoint_completion_target`（PG 14 起默认 0.9）、
  `checkpoint_warning`；旧参数 `checkpoint_segments` 单独一段说明它被谁取代
- 参数节末补「分布式 checkpoint」机制说明（`BM_CHECKPOINT_NEEDED` 的引入版本与作用）
- `CreateCheckPoint` 第 1 步的措辞由「将脏页块状态从 BM_DIRTY 改为 BM_CHECKPOINT_NEEDED」
  改为「把当时是脏的页面**额外**打上 BM_CHECKPOINT_NEEDED 标志」
- `ControlFileData` 代码块恢复对齐、标 ```c、删掉 PG 10 已移除的 `prevCheckPoint`，
  补版本差异说明
- 时间线历史文件提成独立小节；PITR 段落拆开，并补 **PG 12+ 的 `recovery.signal` 写法**
  与「`recovery.conf` 已移除」的版本说明
- 修正错字：`PTIR` → `PITR`
- `CheckPointGuts` 代码块恢复对齐、标 ```c，补 PG 17 的实际调用顺序（含 5 个新增模块）
- 「前四个函数走 SLRU」的说法改为点明具体四个函数名，RelationMap 单独说明
- 总结第 2 条改为调 `max_wal_size`；新增「代价落在哪里」一段
