# 审校：PostgreSQL MVCC：一条数据是如何拥有"分身术"的

- 原文：`docs/database/postgresql-mvcc/index.md`
- 范围：全文
- 目标读者：用过 PostgreSQL、但说不清并发下「我读到的到底是哪一版数据」的开发者
- 一句话定位：沿着 PostgreSQL 17 源码，把 MVCC 从「一行数据怎么变成一串分身」讲到「你读到的那个版本是怎么被判定可见的」
- 核心判断：MVCC 的可见性判定只依赖两个数——快照里的 `xmin`/`xmax`——加上事务自己的 `xip` 名单；理解了这两个数，就理解了为什么读写互不阻塞
- 审校状态：建议中

## 优先修改

1. 位置：L264-271「快照（Snapshot）」小节
   - 问题：正文写「判定一条记录 xmin 是否可见，**三步走**」，下面却列了 4 条（第 4 条「否则 → 已提交，可见」是独立的判定分支，不是第 3 步的收尾）
   - 建议：把「三步走」改成「四步走」；或把第 4 条并进第 3 条写成「3. `xmin ∈ xip[]` → 还在跑，不可见；**否则** → 已提交，可见」
   - 原因：读者按「三步」去数会找不到第四步。这种数字对不上的细节，会让人怀疑整篇文章的严谨性——而这篇文章的卖点恰恰是严谨

2. 位置：L252-262 快照时间线 ASCII 图
   - 问题：`xmin` 的箭头画在时间线**最左端**（落在「已提交老古董」区间里），但 `xmin` 的语义是「当前仍在运行的最老 XID」，应该落在「已提交老古董」与「正在跑的事务们」的**分界**处。图上 `xmax` 反而是对的
   - 建议：把 `↑ xmin` 移到第二个 `┬`（正在跑的事务们 的起点）正下方；并在图下补一行「`xmin` = 最早仍在运行的 XID，`xmax` = 最新已分配 XID」
   - 原因：`xmin`/`xmax` 是快照判定的两根柱子。画错位置，读者会以为「已提交老古董」区间是以 `xmin` 为界，恰好把两个数的含义对调

3. 位置：L375-390「例子：两个事务的赛跑」的 SQL 块
   - 问题：两个会话的语句被排成左右两列塞进同一个 ```sql 块，注释里写死 `xmin=500, xmax=510, xip={505, 508}`。这是示意图，但放在 ```sql 围栏里，读者会当成可执行代码照抄；实际它根本跑不通（两个会话的语句交错在一段里）
   - 建议：拆成两个独立块，分别标注「会话 1」「会话 2」；把写死的快照值改成显式注释 `-- 假设此刻快照为 xmin=500, xmax=510, xip={505,508}`；块后补一句「真实值取决于你库里的并发事务，用 `SELECT pg_current_snapshot()` 现场看」
   - 原因：README 的「可复现证据」要求读者能照着跑。把示意图放在 sql 围栏里而不声明它是示意图，读者会以为自己漏了步骤

4. 位置：L419「不同隔离级别下的 MVCC 行为」首句
   - 问题：「PG 一共支持 4 种隔离级别（`src/backend/storage/ipc/procarray.c` 和 `src/backend/commands/variable.c` 决定默认值）」——两处需要修正：其一，`default_transaction_isolation` 是 GUC，定义不在 `variable.c`（那个文件处理的是 `SET`/`RESET` 语句本身）；其二，PG 实现的行为对应 SQL 标准的 4 个**级别名**，其中 Read Uncommitted 被当作 Read Committed 处理——表格下一行自己就写了「PG 里等同 RC」，所以「4 种隔离级别」这个说法与下表自相矛盾
   - 建议：改为「PG 支持 SQL 标准的 4 个隔离级别名，但 Read Uncommitted 被当作 Read Committed 处理，实际只有 3 种并发语义」；源码出处改成 GUC 定义处（核实后填，见「事实待核」）
   - 原因：出处写错，读者照着 `variable.c` 找半天找不到；级别数量说错，会让读者以为 PG 有 4 种不同的并发语义去对比

5. 位置：L505-508「关键概念」中 `OldestXmin` 的解释
   - 问题：「当前所有活跃事务里**最早开始**的那个 XID」——`OldestXmin` 是按 XID **分配顺序**取最老，不是按事务开始时间；而且它不是简单取最小值，来源是 `GetOldestNonRemovableTransactionId()`
   - 建议：改为「当前仍在运行的事务里 XID 最小的那个（按分配顺序，不是开始时间）」，并补上来源函数 `GetOldestNonRemovableTransactionId()`
   - 原因：读者在判断「多老的事务才挡住 VACUUM」时，按「开始时间」理解会算错——一个 began earlier 但 XID 更大的事务不一定是屏障

6. 位置：全文（DEP-05 仅命中 2 处）——尤其「一个元组的一生」与「死元组清理：VACUUM」两节
   - 问题：全篇没有一处告诉读者「怎么亲眼看到版本链」。没有 `pageinspect`、没有 `heap_page_items`、没有 `pg_visibility`。前面讲的 `t_infomask`、`t_xmax`、提示位全是看不见的符号
   - 建议：在「死元组清理：VACUUM」节末补一段可执行观测，例如
     `CREATE EXTENSION pageinspect;` 后
     `SELECT lp, lp_off, t_xmin, t_xmax, t_infomask FROM heap_page_items(get_raw_page('account', 0)) WHERE lp_off > 0;`
     并说明 `t_infomask` 里的 `HEAP_XMAX_COMMITTED` 等位如何对应前面画的 tuple 结构
   - 原因：这是全文最能兑现「读者因此能做什么」的一处补强。给一条真能跑的观测命令，读者才能把前面所有符号和真实字节对上——否则「提示位」「版本链」永远只是图上的框

7. 位置：L1-13 开头
   - 问题：图书馆比喻很贴切，但没有一句话说清「读完能回答什么」，也没有像同系列《pgAudit 深度解析》那样列出「本文回答 N 个问题」的路线；版本边界（PostgreSQL 17）只出现在编写人表里，正文没提
   - 建议：在 L11 之后补 4 条路线——① 快照是什么、从哪来；② 可见性怎么判；③ UPDATE/DELETE 之后磁盘上留下了什么；④ VACUUM / HOT / 提示位各解决什么问题；并在开头补一句「本文基于 PostgreSQL 17 源码」
   - 原因：README 要求「一句话定位 + 一个可记住的判断」。这篇的比喻读者会记住，但**判断**（两个数决定可见性）才是能带走的那个；路线能让 18600 字有落点

## 事实待核

- L419 隔离级别默认值的源码出处：文中写 `src/backend/commands/variable.c`，但 `default_transaction_isolation` 是 GUC，更可能定义在 `src/backend/utils/misc/guc_tables.c`。需对照 `~/cwork/postgresql` 确认后再改，不能凭印象改
- L273-295 `GetSnapshotData()` 代码片段：文中摘录的片段省略了不少分支（真实实现里还有 `xip` 数组的 `maxProcs` 上限处理、以及 `serializable` 快照的特殊路径）。需确认这段是删减示意还是原文摘录；若是前者，应明确标注「已删减」
- L505-508 `OldestXmin` 的来源：文中未标 `HeapTupleSatisfiesVacuum` 的 `OldestXmin` 参数由谁算出。需补 `src/backend/commands/vacuum.c` 里的 `GetOldestNonRemovableTransactionId()` 作为出处
- L473 「PG 的 RR 已经能防住脏读、不可重复读、幻读」：结论在 PG 成立（靠的是整事务不换的快照，而不是锁），但同一句又说「代价是没有像 ANSI SQL 那样加间隙锁」，因果容易被读反。改写时要把「防住幻读靠快照、因此并发 INSERT 不会被阻塞只会看不见」摆正
- L11 与 L640 的 `~/cwork/postgresql/...` 是作者本机绝对路径，发布出去读者点不开。需确认是否统一改成 upstream 路径或仓库内相对路径

## 可补的技术证据或产物

- 机制 / 源码入口：已有 `heapam_visibility.c`、`procarray.c`、`snapshot.h` 三处。缺两个关键点——`src/backend/access/heap/heapam.c` 的 `heap_update()`（版本链真正的写入点，文章只讲了 UPDATE 之后的结果，没讲怎么写进去的）和 `src/backend/utils/time/snapmgr.c` 的 `GetTransactionSnapshot()`（「RC 下每条语句拍一次快照」这个结论的真正出处，现在只引了 `GetSnapshotData()`）
- 实验或观测：`pageinspect` 的 `heap_page_items()` 展示真实页上的 `lp`/`t_infomask`/`t_xmax`；`pg_current_snapshot()` 现场看 xmin/xmax/xip。两者能把第 2、6 条建议的收益变成实感
- 工程取舍：文中有「UPDATE/DELETE 不真正删除 → 表膨胀 → 依赖 VACUUM」这条因果，但没有讲**取舍**——什么时候该 UPDATE 而不是 DELETE（改几列决定版本链有多长）、autovacuum 参数在这条链上起什么作用、长事务如何卡住回收。这正是 README 说的「不只给唯一最佳实践」
- 结尾清单或下一篇链接：结尾的「参考资料」是延伸阅读，不是**可带走的产物**。可补一页排查清单——「怀疑 MVCC 有问题时先看这三张视图：`pg_stat_activity`（有没有长事务）、`pg_locks`（谁在等）、`pg_stat_user_tables.n_dead_tup`（回收有没有跟上）」——并链到同系列的《PostgreSQL 内存管理》《PostgreSQL 事务生命周期》《PostgreSQL 读取一行数据》

## 已确认的改动

- 无（阶段 A 只出记录，未改动 `docs/`）
