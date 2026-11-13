# 审校：06 堆表与 MVCC（PostgreSQL 学习路径）

- 原文：`docs/db/postgresql/learning-path/06-heap-and-mvcc.md`
- 范围：全文
- 目标读者：按 learning-path 逐章读 PG 源码、需要一篇把「页布局 + tuple 头 + 可见性 + HOT + vacuum」串起来的开发者
- 一句话定位：把 PG 堆表的字节结构一路讲到 vacuum 的实际动作，中间夹着 pageinspect、gdb、visibilitymap 这些可以直接上手的手艺
- 核心判断：PG 与 InnoDB 最大的工程差异是**没有 undo log**——所有历史都留在 heap page 的 tuple 链里，所以 VACUUM 承担了 InnoDB purge 的职责
- 审校状态：建议中

## 优先修改

1. 位置：全文（**零链接**）
   - 问题：整篇**一个链接都没有**（检查器统计：链接 0）。learning-path 是一个 14 章的系列（`01-build-and-codebase` 到 `14-column-store`），第 6 篇既不链上一章《05 缓冲管理器》，也不链下一章《07 B-Tree 索引》，文末 L330 只有一句「下一章 07 进入 B-Tree 索引」——**读者点不到**。同系列的其他篇章也没有互链
   - 建议：① 开头加「系列位置」块，链到 `01`（构建与代码库）与 `05`（缓冲管理器）；② L330 那句改成真链接 `[下一章 07 B-Tree 索引](./07-btree-index.md)`；③ 文末补「相关章节」：本页与《05 缓冲管理器》《08 锁与并发》《13 逻辑复制》的关系
   - 原因：README 的内容策略里「一条自然的内容路径」是四个必做项之一。系列文不互链，读者就只能靠目录页硬找，learning-path 的价值被浪费了

2. 位置：L322（`## 6.12 小结`）与 L789（`## 6.22 小结`）
   - 问题：全文有**两个「小结」**。6.12 在 L322，6.22 在 L789，中间夹着 6.13~6.21 九个「进阶」小节（TOAST、hint bits 完整语义、lazy vacuum 完整流程、snapshot 实现细节、EPQ、visibilitymap、FSM、catalog MVCC、HIO）。从结构上看，6.13 之后像是另起炉灶追加的内容，原有编号体系没跟着重排
   - 建议：二选一——① 把 6.13~6.21 整体降为「6.13 进阶篇」的子结构，6.12 保留为全篇小结，把 6.22 改为「进阶篇小结」；② 或者把这九节拆成独立的 06b~06i 文件，在 06 里留索引。**不要保留两个同名「小结」**
   - 原因：两个「小结」意味着读者不知道该在哪停——这是 README 说的「结构跳跃」

3. 位置：L298-L304（GDB 跟踪）
   - 问题：给出了断点命令，但**没有说这些断点要生效需要什么构建条件**。PG 默认的发行版构建没有调试符号，读者照抄这几行只会得到 "No symbol table info available"
   - 建议：补一句构建要求（源码编译时加 `--enable-debug` 且 `CFLAGS="-O0 -g3"`，或发行版的 `-dbg` 包），并注明 `heap_insert` / `heap_update` 是 `heapam.c` 里的**静态函数**，需要靠「文件:函数名」形式断点
   - 原因：这是全文最硬的一处「可复现证据」缺口——读者按步骤做却一定失败，而失败原因（缺调试符号）文中只字未提

4. 位置：L281-L285（看 xmin/xmax 与 clog）
   - 问题：`pg_xact_status(t_xmin::text::xid)` 这个双重转换是 **PG 9.x 时代**的写法。`pg_xact_status` 在 PG 13 之后签名改为 `xid8`，`heap_page_items` 返回的 `t_xmin`/`t_xmax` 类型在 PG 14+ 也改成了 `xid8`。在 PG 17 上，`t_xmin::text::xid` 会把它降回 32 位 `xid`，与 `xid8` 形参之间的隐式转换是否还成立、会不会报错，需要按目标版本实测
   - 建议：给出不带转换的写法（`pg_xact_status(t_xmin)`），并在旁边注明「PG 13 之前 `pg_xact_status` 收 `xid`，写法为 `pg_xact_status(t_xmin::text::xid)`」
   - 原因：读者跑 6.10.3 时报类型错误，整节实战就断了

5. 位置：L287-L293（手动 freeze）
   - 问题：`VACUUM (FREEZE, VERBOSE) t;` 后写「VERBOSE 会输出每个 page 的 prune、dead、frozen 数量」——**VERBOSE 输出的是表级汇总**（`pages: 1, tuples: 3, …`），不是每个 page 的明细
   - 建议：改写成「VERBOSE 给出表级汇总；要逐页看 prune/dead/frozen，需要对比 `heap_page_items` 前后结果，或观察 `pg_stat_progress_vacuum`」，并把「逐页」的真实做法给一条命令
   - 原因：这是全文最容易误导实践的一处——读者以为看到了逐页明细，实际看到的是三行汇总

6. 位置：L3（开头目标块）
   - 问题：定位写在 `>` 引用块里（`> 目标：理解 PostgreSQL 堆表的页面布局……`），渲染出来是引用样式，视觉上被弱化；同时**没有说明本文对应的 PG 版本**（正文里有「PG 17 快照优化」等版本相关表述，但开头没交代）
   - 建议：把「目标」改成正文里的加粗段落，并补一句「本文基于 PostgreSQL 17 源码，命令在 PG 17 上实测」
   - 原因：README 原则 4 要求「保留人的声音」；而定位句是读者判断「这篇值不值得读」的唯一依据，不该藏在引用块里

7. 位置：L308-L320（6.11 与 InnoDB 对照）与 L320
   - 问题：这张对照表是全文的**核心判断**所在（没有 undo log → VACUUM ≈ purge），但它躺在 6.11 这个二级位置，读者读完前面十几页未必意识到它是全文结论。表里两处「历史回溯」的表述也可以更准：PG 侧写「不支持（除非 logical decoding）」，InnoDB 侧写「支持（MVCC 链 + undo）」——InnoDB 的 undo 链默认只保留旧版本供并发读，历史版本回溯（类似 flashback）需要额外机制
   - 建议：把「没有 undo log，VACUUM ≈ purge」这句提炼成文章开头的一句话定位（L6 之后），并在对照表下加一行「代价：长事务会挡住 purge，PG 侧表现为 VACUUM 回收不掉、表膨胀」
   - 原因：README 说的「一个可记住的判断」——这句判断现在埋在第 320 行，读者带不走

## 事实待核

- L281-L285 的 `pg_xact_status` 参数类型：需在目标版本（PG 17）实测确认 `pg_xact_status(t_xmin)` 是否可直接编译，以及 `heap_page_items` 返回的 `t_xmin` 类型在 PG 17 中是 `xid` 还是 `xid8`
- L300 `b heapam.c:heap_insert`：需确认 GDB 的「文件:函数名」断点语法在当前 GDB 版本下能否命中 `heapam.c` 中的**静态**函数 `heap_insert`（该函数在 `heapam.c` 中为 `static`，普通 `b heap_insert` 不可用）
- L306「`p tup->t_data->t_xmin/xmax/cmin/cmax` 看 hint bit 变化」：`cmin`/`cmax` 存在于 tuple header，但**不参与 hint bit**，且在 PG 中早已不常用（`HeapTupleHeaderGetCmin` 已弃用）。需确认这句指的是 `t_infomask` 的哪些位，避免把 cmin/cmax 与 hint bit 混为一谈
- L320「PG 的 VACUUM 实际上是 InnoDB 的 purge」：这个类比在「回收老版本」这一层成立，但 VACUUM 还额外承担 anti-wraparound freeze、visibilitymap 维护、索引清理等职责，与 purge 不完全等价。改写时是否要加限定，需按系列的口径定
- L563 起「6.16.2 PG 17 快照优化」：需核对 PG 17 相对 PG 16 在快照路径上的具体变化点，避免把尚未进入 PG 17 的优化写进去

## 可补的技术证据或产物

- 机制 / 源码入口：文章已在末尾列出 9 个源码文件，覆盖度很好。缺的是**入口与调用链的顺序**：读者拿到文件清单后仍不知道从哪个函数读起。可在 6.2 开头给一条阅读路径：「先 `heapam.c` 的 `heap_insert` 看写入 → 再 `heapam_visibility.c` 的 `HeapTupleSatisfiesMVCC` 看读取 → 再 `vacuumlazy.c` 看回收」
- 实验或观测：6.10 实战已经是全文最强的部分（pageinspect / HOT 链 / clog / freeze / gdb 五件事）。建议把每一条的**预期输出**贴出来——现在只给了命令没给结果，读者无法自查「我看到的是不是对的」
- 工程取舍：L310-L320 的对照表只讲「有什么」，没讲「代价」。可以补一段：PG 因为没有 undo log，所以长事务会同时拖住 VACUUM 回收与表膨胀；InnoDB 的 undo 有独立上限（`innodb_max_undo_log_size`）可以截断——两种设计的代价完全不同，而这正是「读 PG 源码时时刻记住没有 undo log」的**下半句**
- 结尾清单或下一篇链接：结尾是 mermaid 图示（6.23），没有「可带走的产物」。可补一页排查清单——「怀疑 MVCC 有问题时先看：① `heap_page_items` 对比 xmin/xmax；② `pg_stat_user_tables.n_dead_tup` 与 `pg_stat_activity` 里的长事务；③ `pg_visibility_map` 的 all-visible/all-frozen 状态」，并链到同系列的《08 锁与并发》《13 逻辑复制》

## 已确认的改动

- 无（阶段 A 只出记录，未改动 `docs/`）
