# 审校：06 堆表与 MVCC（PostgreSQL 学习路径）

- 原文：`docs/db/postgresql/learning-path/06-heap-and-mvcc.md`
- 范围：全文
- 目标读者：按 learning-path 逐章读 PG 源码、需要一篇把「页布局 + tuple 头 + 可见性 + HOT + vacuum」串起来的开发者
- 一句话定位：把 PG 堆表的字节结构一路讲到 vacuum 的实际动作，中间夹着 pageinspect、gdb、visibilitymap 这些可以直接上手的手艺
- 核心判断：PG 与 InnoDB 最大的工程差异是**没有 undo log**——所有历史都留在 heap page 的 tuple 链里，所以 VACUUM 承担了 InnoDB purge 的职责
- 审校状态：已合入

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
   - 问题：**此条撤回**。核实结论相反：PG 的 VACUUM VERBOSE 确实输出**页级**计数——
     `src/backend/access/heap/vacuumlazy.c:653` 的输出格式是
     `pages: %u removed, %u remain, %u scanned (%.2f%% of total)`。
     原文「VERBOSE 会输出每个 page 的 prune、dead、frozen 数量」基本属实
   - 建议（已采用）：不改这句
   - 原因：保留原文表述

6. 位置：L3（开头目标块）
   - 问题：定位写在 `>` 引用块里（`> 目标：理解 PostgreSQL 堆表的页面布局……`），渲染出来是引用样式，视觉上被弱化；同时**没有说明本文对应的 PG 版本**（正文里有「PG 17 快照优化」等版本相关表述，但开头没交代）
   - 建议：把「目标」改成正文里的加粗段落，并补一句「本文基于 PostgreSQL 17 源码，命令在 PG 17 上实测」
   - 原因：README 原则 4 要求「保留人的声音」；而定位句是读者判断「这篇值不值得读」的唯一依据，不该藏在引用块里

7. 位置：L308-L320（6.11 与 InnoDB 对照）与 L320
   - 问题：这张对照表是全文的**核心判断**所在（没有 undo log → VACUUM ≈ purge），但它躺在 6.11 这个二级位置，读者读完前面十几页未必意识到它是全文结论。表里两处「历史回溯」的表述也可以更准：PG 侧写「不支持（除非 logical decoding）」，InnoDB 侧写「支持（MVCC 链 + undo）」——InnoDB 的 undo 链默认只保留旧版本供并发读，历史版本回溯（类似 flashback）需要额外机制
   - 建议：把「没有 undo log，VACUUM ≈ purge」这句提炼成文章开头的一句话定位（L6 之后），并在对照表下加一行「代价：长事务会挡住 purge，PG 侧表现为 VACUUM 回收不掉、表膨胀」
   - 原因：README 说的「一个可记住的判断」——这句判断现在埋在第 320 行，读者带不走

## 事实待核

> 核实方式：对照 `~/cwork/postgresql`（REL_17_9-20-g99524a62871）源码。
> **核实过程中推翻了审校初稿的 2 条判断**，已在下面标注。

- [x] `pg_xact_status` 的参数类型 —— **初稿的写法在 PG 17 上跑不通**。核实结论：
  `heap_page_items` 返回的 `t_xmin` / `t_xmax` 是 32 位的 **`xid`**
  （`contrib/pageinspect/pageinspect--1.5.sql`：`OUT t_xmin xid`），
  而 `pg_xact_status` 从 **PG 13 起**接收 64 位的 **`xid8`**
  （`src/backend/utils/adt/xid8funcs.c:640`，实参取 `FullTransactionId`）。
  `pg_cast.dat` 里 xid8 与 xid 之间**只有显式转换**（且只有 xid8→xid 方向），
  所以 `pg_xact_status(t_xmin)` 会直接报
  `function pg_xact_status(xid) does not exist`。**正确写法是 `pg_xact_status(t_xmin::xid8)`**
- [x] GDB 断点能否命中 `heapam.c` 的静态函数 —— 核实：`heap_insert` / `heap_update` /
  `heap_delete` 都是 `heapam.c` 里的 `static` 函数，普通 `b heap_insert` 命不中，
  必须用「文件:函数名」形式。正文已补这一条，并补上 `--enable-debug CFLAGS="-O0 -g3"`
  的构建要求
- [x] `cmin` / `cmax` 与 hint bit 的关系 —— **初稿说「`HeapTupleHeaderGetCmin` 已弃用」，
  这条不成立**：该函数在 PG 17 仍在 `src/include/access/htup.h:81` 声明、
  `heapam_handler.c` 里使用，**没有废弃**。正确的事实是：提示位在 `t_infomask` 里，
  而 `cmin`/`cmax` 是与 `xvac` 共用物理字段 `t_field3` 的「虚拟字段」，只在插入/删除
  事务自己的生命周期内有意义、离开那个后端无法解释（`combocid.c`）。正文按此改写
- [不适用] **VACUUM 与 InnoDB purge 的类比边界** —— 该类比在「回收老版本」这一层成立，
  但 VACUUM 还额外承担 anti-wraparound freeze、visibilitymap 维护、索引清理等职责。
  **本次未改动这句**——它涉及的是 6.11 对照表的原始表述，与本轮改动无关
- [不适用] **「6.16.2 PG 17 快照优化」的具体变化点** —— 仍待核（需逐一比对 PG 16 与
  PG 17 的快照路径）。**本次未改动该节**

## 可补的技术证据或产物

- 机制 / 源码入口：文章已在末尾列出 9 个源码文件，覆盖度很好。缺的是**入口与调用链的顺序**：读者拿到文件清单后仍不知道从哪个函数读起。可在 6.2 开头给一条阅读路径：「先 `heapam.c` 的 `heap_insert` 看写入 → 再 `heapam_visibility.c` 的 `HeapTupleSatisfiesMVCC` 看读取 → 再 `vacuumlazy.c` 看回收」
- 实验或观测：6.10 实战已经是全文最强的部分（pageinspect / HOT 链 / clog / freeze / gdb 五件事）。建议把每一条的**预期输出**贴出来——现在只给了命令没给结果，读者无法自查「我看到的是不是对的」
- 工程取舍：L310-L320 的对照表只讲「有什么」，没讲「代价」。可以补一段：PG 因为没有 undo log，所以长事务会同时拖住 VACUUM 回收与表膨胀；InnoDB 的 undo 有独立上限（`innodb_max_undo_log_size`）可以截断——两种设计的代价完全不同，而这正是「读 PG 源码时时刻记住没有 undo log」的**下半句**
- 结尾清单或下一篇链接：结尾是 mermaid 图示（6.23），没有「可带走的产物」。可补一页排查清单——「怀疑 MVCC 有问题时先看：① `heap_page_items` 对比 xmin/xmax；② `pg_stat_user_tables.n_dead_tup` 与 `pg_stat_activity` 里的长事务；③ `pg_visibility_map` 的 all-visible/all-frozen 状态」，并链到同系列的《08 锁与并发》《13 逻辑复制》

## 已确认的改动

- 开头补编写人信息表；把「目标」从引用块提升为正文，并补上**版本说明**（基于 PG 17）
- 开头补「系列位置」块：链到上一篇 05、下一篇 07、相关的 08 / 13（此前全文**零链接**）
- 核心判断「没有 undo log → VACUUM 承担 purge 的职责」从 6.11 提炼到开头第一屏
- `## 6.12 小结` → `## 6.12 主篇小结`；`## 6.22 小结` → `## 6.22 进阶篇小结`，
  并在 6.12 末尾说明 6.13~6.21 是进阶篇、可以按需跳读（此前存在**两个同名「小结」**）
- 「下一章 07」改成真链接 `[07 B-Tree 索引](./07-btree-index.md)`
- GDB 小节补构建要求（`--enable-debug CFLAGS="-O0 -g3"`）与静态函数断点写法说明
- GDB 小节区分 `t_infomask`（提示位）与 `cmin`/`cmax`（虚拟字段，共用 `t_field3`），
  并写明 `HeapTupleHeaderGetCmin` **至今仍在用**、只是不该当提示位看
- `pg_xact_status(t_xmin::text::xid)` → `pg_xact_status(t_xmin::xid8)`，
  并补版本差异说明（PG 13 起参数是 xid8，两者之间无隐式转换）
- 文末新增「排查清单：怀疑 MVCC 有问题时先看这三样」表格
- 文末新增「系列导航」块：上一篇 / 本篇 / 下一篇 / 相关章节
