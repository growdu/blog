# 审校：Postgresql存储、索引及系统优化、主备切换

- 原文：`docs/pgsql/replication/Postgresql存储、索引及系统优化、主备切换/index.md`
- 范围：全文
- 目标读者：需要读懂 PostgreSQL 存储结构、做索引选型、调系统参数、
  搭主备集群的 DBA 与运维
- 一句话定位：把 PostgreSQL 的存储结构、索引类型、系统优化和主备切换
  串成一份从「数据页长什么样」到「备库怎么切」的参考手册
- 核心判断：技术密度是站得住的——88 个代码块、大量源码级细节，
  几处跨版本边界说得比大多数中文材料准确；但**这份手册的骨架是坏的**：
  标题编号有 6 处冲突或层级错乱，唯一的版本声明埋在 L3 的一行红字里，
  而正文自己没守住这个基线；结尾停在两个参数说明上，没有产物
- 审校状态：建议中

## 优先修改

1. 位置：L1、L3
   - 问题：两个问题叠在一起。
     - H1 是「**0** Postgresql存储、索引及系统优化、主备切换」——
       开头那个「0 」像是从别的文档复制来的编号残留。
     - L3 有一行 `<font color="red">基于pg12描述。</font>`——
       **这是全文唯一的版本边界声明**，却是红字小字，还夹在一级标题和
       正文之间。读者多半会滑过去。
     - 开头没有定位句（STR-02），也没有「编写人 / 编写内容 / 编写时间」
       信息表（MET-01）——本仓库其它文章都有这一张表。
   - 建议：去掉「0 」；把版本基线提到正文开头做成一个显眼的说明块
     （例如「本文以 PostgreSQL 12 为基线；PG 13 / 15 / 16 起的几处变化
     就地标注」）；补一句话定位和编写信息表。
   - 原因：README 的「问题边界」「一句话定位」。版本边界是这类参考手册
     最要命的东西，它藏在红字里等于没有。

2. 位置：L611、L672、L687、L735、L764、L813
   - 问题：**章节编号全面撞号**。L215 是「1.2 数据（表）物理存储结构」，
     L611 又来一个「**1.2** 控制文件」；后者的小节又是
     `#### 1.2.1 数据库唯一标识` / `#### 1.2.2 checkpoint信息` /
     `#### 1.2.3 备库相关信息`——与前面的 `#### 1.2.1 关键概念` /
     `#### 1.2.2 数据块结构` / `#### 1.2.3 tuple结构` **逐个撞号**。
     后面 WAL 文件写成 1.3、clog 写成 1.4，也是跟着错的。
   - 建议：控制文件改成 1.3（WAL 1.4、clog 1.5），其小节顺延为
     1.3.1 / 1.3.2 / 1.3.3。
   - 原因：编号是读者唯一的定位手段；撞号之后「见 1.2.2」这种话没法用。

3. 位置：L1110、L1122、L1167、L1198
   - 问题：文件系统一节同样撞号。L1110 是「3.3.2.1 文件系统的崩溃恢复」，
     L1122 又是「**3.3.2.1** Ext2文件系统」；L1167「3.3.2.5 Barriers I/O」
     与 L1198「**3.3.2.5** I/O调优方法」也重号。
   - 建议：从 Ext2 起整体顺延一位（Ext2→3.3.2.2、Ext3→…3、
     Ext4→…4、XFS→…5、Barriers I/O→…6、I/O调优方法→…7），
     其下的 3.3.2.5.1~3.3.2.5.5 一并跟着改。
   - 原因：同上。

4. 位置：L1584、L1606、L1616、L760、L601
   - 问题：**标题层级与编号对不上**。
     - L1584「## 4.3.4 启动Standby数据库」用的是 **H2**，
       比它的同级（4.3.1 / 4.3.2 / 4.3.3 都是 H4）高了两级。
     - L1606「### 4.3.5 switchover」用 **H3**，而它的同级
       L1616「#### 4.3.6 failover」用 H4。
     - L760「#### reference」没有编号，和 L601「#### 1.2.6 reference」
       一样——「reference」当标题，读者不知道里面是什么
       （参考出处？还是本节小结？）。
   - 建议：4.3.4 / 4.3.5 改成 H4；两个「reference」改成有内容指向的
     标题（如「参考资料」「本节小结」），或者干脆去掉这层标题，
     内容直接跟在所属小节下面。
   - 原因：README 的「标题层级是读者唯一的导航」。

5. 位置：L1424-L1432（### 4.1.5 创建standby备库的步骤）
   - 问题：**与全文自相矛盾**。这一节写「Standby数据库一直运行在恢复状态，
     如何让数据库运行在恢复状态呢？在PostgreSQL中是通过配置**recovery.conf**
     文件来实现的。在数据库启动过程中，如果发现数据目录下存在
     **recovery.conf**，就会按 recovery.conf 文件中指示的情况把数据库
     启动到恢复状态。」——这是 PostgreSQL 11 及以前的机制。
     而同一节的 L1386 已经写明「在PostgreSQL 12版本之前是通过文件
     "recovery.conf"来指示……从PostgreSQL 12版本开始把 recovery.conf
     中的配置项全部移到 postgresql.conf」，L1396、L1401、L1404 也都
     按 12 写了。
     同一节里还出现了 `pg_start_backup()`——这个函数在 **PostgreSQL 15**
     起已经被 `pg_backup_start()` 取代。
   - 建议：4.1.5 整节按 PG 12 重写——`standby.signal` + `postgresql.conf`
     里的 `primary_conninfo` / `restore_command`，并把 `pg_start_backup()`
     的说法改成 PG 15 起的 `pg_backup_start()`（或两边都写、标注版本）。
   - 原因：这是全文最硬的一处自相矛盾——**同一节里前后两段给出互斥的
     操作步骤**，读者照哪一段做都会错。

6. 位置：L1463（pg_basebackup 的 -R 选项）
   - 问题：「-R，--write-recovery-conf：是否生成 **recovery.conf** 文件。」
     ——这是 PostgreSQL 11 及以前的行为。实测源码头：
     REL_10_0 的 `pg_basebackup --help` 写的是
     「write recovery.conf for replication」，而 **REL_12_0 已经改成**
     「write configuration for replication」——即写 `standby.signal`
     和 `postgresql.auto.conf`，不再有 recovery.conf。
     所以这句**连本文自己声明的 PG 12 基线都不符合**。
   - 建议：改成「生成备库需要的恢复配置：PG 12 起是 standby.signal +
     postgresql.auto.conf，PG 11 及以前是 recovery.conf」。
   - 原因：涉及事实与版本，必须可回溯。已对源码核对（见「事实待核」）。

7. 位置：L2010-L2012（### 4.7.1 min_wal_size参数的配置）
   - 问题：三个问题。
     - 标题写的是 **min_wal_size**，正文讲的却是 **wal_keep_segments**——
       标题与内容不是一回事。
     - `wal_keep_segments` 在 **PostgreSQL 13** 改名为 `wal_keep_size`，
       单位也从「段」变成「MB」。
     - 正文里把参数名拼成了 `wal_keep_segements`（少一个 m）。
   - 建议：标题改成 `wal_keep_segments`（并注明 PG 13 起为
     `wal_keep_size`）；正文补上版本标注；参数名拼写改对；
     再补一句更稳妥的做法——**复制槽（replication slot）**，
     它是现代 PG 防止 WAL 被覆盖的标准手段，比靠 wal_keep_size 猜一个
     安全值可靠得多。
   - 原因：涉及事实与版本，必须可回溯。

8. 位置：L2014-L2016（### 4.7.2 vacuum_defer_cleanup_age参数的配置）
   - 问题：这个参数**在 PostgreSQL 16 里被删了**（上游提交
     1118cd37eb6，2023-04-24「Remove vacuum_defer_cleanup_age」，
     理由是它「难以合理使用、且让 xid horizon 的计算变复杂」）。
     实测 REL_13_0 / 14_0 / 15_0 的 `postgresql.conf.sample` 里还有它，
     REL_16_0 起就没有了。原文这一节没有任何版本提示，
     PG 16+ 的读者照着配会直接报参数不存在。
   - 建议：加版本标注（PG ≤ 15 有效，PG 16 起已移除），
     并写明替代方案（`hot_standby_feedback`、复制槽、或靠
     `max_standby_streaming_delay` 控制冲突回收）。
   - 原因：涉及事实与版本，必须可回溯。

9. 位置：L385、L387
   - 问题：检查器报的「近似重复句」在这里是**真 bug**，不是文风问题。
     - L385：「插入该元组的命令在**插入事务**中的命令标识（从0开始累加）」
     - L387：「删除该元组的命令在**插入事务**中的命令标识（从0开始累加）」
     第二句说的是删除，命令标识却写成了「插入事务」——删除发生在
     **删除方的事务**里。两句长得像，是为了让读者对照着看，
     平行结构本身是对的，**错的是第二个事务的归属**。
   - 建议：第二句改成「删除该元组的命令在**删除方事务**中的命令标识
     （从0开始累加）」。
   - 原因：涉及事实。检查器的重复句信号在这里指向了一个真错误——
     这正是机械信号值得看的地方。

10. 位置：L185、L209
    - 问题：检查器也把这一对判成近似重复（0.89），但**这是合理的平行示例**
    ——「表」和「索引」两段刻意用了同样的句式，读者对照着看正合适。
    - 建议：**不要为了消信号去改**。知道检查器会命中即可。
    - 原因：README 的「保留人的声音」；消信号不等于消问题。

11. 位置：L287、L542、L2012
    - 问题：三个错字。
      - L287「行指针中表示行内容在**业内**（块中）的偏移量」——
        「业内」应为「**块内**」，括号里自己都写对了。
      - L542「VACCUM」应为「**VACUUM**」。
      - L2012「wal_keep_**segements**」少一个 m。
    - 建议：逐处改正。
    - 原因：基础校对。

12. 位置：全文 14 处「Postgresql」
    - 问题：官方写法是 **PostgreSQL**（大写 PG）。全文混用
    「PostgreSQL」和「Postgresql」，标题、H1、章节名都是后者
    （检查器 STR-05 命中 14 行）。
    - 建议：统一成 PostgreSQL。
    - 原因：术语一致性；README 把「术语不一致」列进了要查的问题。

13. 位置：L542、L557、L939、L1144、L1344
    - 问题：检查器 AIF-02 报了 5 处空泛评价（高效 ×3、全面、完美），
      但**不是每一处都要改**：
      - L557「提高了效率」前面已经给出了机制（FSM 用大根堆组织，
        取堆顶就能拿到最大空余空间）——有机制支撑，可以保留。
      - L1144「journal 模式提供了更全面的完整性保证」、L1344「不再需要
        一个**完美的一致性**备份」——是技术表述（perfectly consistent
        backup），不必动。
      - L542「如何将这些可用空间管理起来，并在需要的时候能够**高效**地
        分配出去」和 L939「数据的查找会非常**高效**」——这两处是真的
        没有任何依据。
    - 建议：只改 L542 与 L939——L542 补上堆顶 O(1) 取值的说法，
      L939 补上「N 个块才对应一条索引记录」这类可数的量。
    - 原因：README 的「让抽象话落地」；也提醒：消信号不是目的，
      分辨哪条信号背后是真问题才是。

14. 位置：全文 32 段超过 200 字
    - 问题：检查器 AIF-03 命中 32 段。长的多半是**好内容**
      （比如 L100 那种带完整算例的段落、L132 讲 PMTUD 的那段），
      不该为了字数拆散。
    - 建议：只拆那些**塞了多个结论又没有因果关系**的段落
      （L17、L270、L450、L597、L720、L790、L795、L870 等）；
      带算例、带时序的段落保留。
    - 原因：README 的「AI 味信号」第三条是「一段塞进多个结论」，
      不是「一段超过 200 字」。

15. 位置：L2008-L2017（### 4.7 流复制的注意事项）
    - 问题：文章以两个参数的说明结束（STR-03 命中：结尾没有可带走的产物）。
      而且标题说「注意事项」，实际只讲了两个 GUC——主备切换里真正的坑
      （备库连接断了怎么办、复制槽没释放会撑爆磁盘、
      `synchronous_standby_names` 配错会导致主库阻塞、切换演练怎么做）
      一个都没写。
    - 建议：结尾补一张「主备搭建 → 验证 → 切换 → 日常巡检」的清单，
      再链到本仓库讲主备切换与故障演练的相关文章。
    - 原因：README 的「一份可带走的产物」「一条自然的内容路径」。

16. 位置：全文（前置条件散在各处）
    - 问题：真正动手时会卡住的前提条件散落在正文里，没有集中：
      `wal_level` 至少要 `replica`、备份账号要 REPLICATION 权限、
      备库要 `hot_standby = on`、`max_wal_senders` 要够、
      表空间要额外指定 `-T`……
    - 建议：在「## 4 Postgresql主备切换」开头加一节「前置条件清单」，
      把这些列成一张表（要求 / 在哪配 / 漏了会怎样）。
    - 原因：README 的「一份可带走的产物」——读者真正需要的就是这张表。

## 事实待核

- [x] `pg_xlog` → `pg_wal`、`pg_clog` → `pg_xact` 的改名版本 —— 上游提交
  f82ec32ac30「Rename "pg_xlog" directory to "pg_wal"」（2016-10-20）；
  `git tag --contains` 显示**没有任何 REL_9_x 包含它**，第一个 REL_x_0 是
  **REL_10_0**；REL_10_0 的 `XLOGDIR` 宏已是 `"pg_wal"`。
  原文 L73-74、L817、L1340 说的「PostgreSQL 10 版本之前是 pg_xlog /
  pg_clog」**正确**。
- [x] `recovery.conf` → `postgresql.conf` + `standby.signal` 的版本 ——
  PostgreSQL **12**。原文 L1386、L1396、L1401、L1404、L2005（promote_trigger_file
  与 trigger_file 的分界）**都正确**；L1424-1432 的 4.1.5 **没跟上**（见
  「优先修改」第 5 条）。
- [x] `pg_basebackup -R` 的行为在 PG 12 就变了 —— 实测 `pg_basebackup.c` 的
  帮助文本：REL_10_0 是「write recovery.conf for replication」，
  **REL_12_0 已经是「write configuration for replication」**
  （即写 standby.signal + postgresql.auto.conf）。
  原文 L1463 描述的是 PG ≤ 11 的行为。
- [x] `pg_start_backup()` / `pg_stop_backup()` 的替代版本 —— 实测
  `src/include/catalog/pg_proc.dat`：REL_14_0 里是 `pg_start_backup` /
  `pg_stop_backup` / `pg_stop_backup_v`，**REL_15_0 起只剩
  `pg_backup_start` / `pg_backup_stop`**。即 **PostgreSQL 15** 改名。
- [x] `wal_keep_segments` → `wal_keep_size` 的改名版本 —— 上游提交
  f5dff45962e「Rename wal_keep_segments to wal_keep_size」（2020-07-20）；
  实测 `postgresql.conf.sample`：REL_12_0 及以前是 `wal_keep_segments`，
  **REL_13_0 起是 `wal_keep_size`**。单位同时从「段」变成「MB」。
- [x] `vacuum_defer_cleanup_age` 的移除版本 —— 上游提交 1118cd37eb6
  「Remove vacuum_defer_cleanup_age」（2023-04-24），提交说明写明它
  「难以合理使用」且让 xid horizon 计算复杂。实测
  `postgresql.conf.sample`：REL_13_0 / REL_14_0 / REL_15_0 里都有，
  **REL_16_0 起没有**。即 **PostgreSQL 16 移除**。
- [x] `promote_trigger_file` / `trigger_file`、`recovery_min_apply_delay`、
  `postgresql.auto.conf` 的版本 —— 原文 L2005、L2006、L24 说的
  「PG 12 / PG 11 及以前」「PG 9.4 之后增加」「PG 9.4 及更高版本」
  **都正确**。
- [x] FSM 用三层二叉树 —— 上游 `src/backend/storage/freespace/README` 原文：
  「maximum relation size of 2^32-1 blocks, three levels is enough with the
  default ...」。原文 L576「每张表最多有2^32-1个数据页，因而三层二叉树
  即可满足」**正确**。
- [x] `XLogCtl->Insert.forcePageWrites` 这个字段确实存在 —— REL_14_0 的
  `src/backend/access/transam/xlog.c:572` 有
  `bool forcePageWrites; /* forcing full-page writes for PITR? */`，
  同文件 379 行注明「doPageWrites is this backend's local copy of
  (forcePageWrites || fullPageWrites)」。原文 4.1.5 对该字段的描述方向正确。
- [x] 标题编号与层级的实测冲突 —— 逐个列出代码块外的 103 个标题核对后确认：
  `### 1.2` 出现两次（L215、L611）、`#### 1.2.1/1.2.2/1.2.3` 各出现两次、
  `##### 3.3.2.1` 出现两次（L1110、L1122）、`##### 3.3.2.5` 出现两次
  （L1167、L1198）、L1584 用 H2 而其编号是 4.3.4、L1606 用 H3 而编号是
  4.3.5（同级的 4.3.6 用 H4）。另外全文**没有**「编写人 / 编写内容 /
  编写时间」信息表。
- [x] 错字与拼写实测 —— L287「业内」应为「块内」、L542「VACCUM」应为
  「VACUUM」、L2012「wal_keep_segements」少一个 m；「Postgresql」与
  「PostgreSQL」混用共 14 行写成后者。
- 4.1.5 对 `pg_start_backup()` 内部行为的两条描述（置
  `XLogCtl->Insert.forcePageWrites = true`、强制发生一次 Checkpoint）——
  字段本身已核实存在，但这两步动作的准确表述需与 PG 12 的
  `do_pg_start_backup()` 实现逐行核对后再写进正文。
- 本文的读者基线到底是哪个版本 —— L3 写「基于 pg12 描述」，但 4.1.5 整节
  用的是 PG ≤ 11 的 recovery.conf 与 `pg_start_backup()`。需作者确认：
  是「以 PG 12 为主、顺带讲老版本的做法」，还是「原本以 PG 11 为主、
  后来只改了开头那一行」。这决定了 4.1.5 该重写还是该加版本标注。
- 4.3（异步流复制）与 4.4（同步流复制）两节的配置是否都在真实环境验证过 ——
  文中给的是 `primary_conninfo` / `synchronous_standby_names` 等参数，
  但没有说明验证步骤；需作者补充。
- L1344「备份数据库不再需要一个完美的一致性备份」——
  这句对应的是 `pg_start_backup()` 的非 exclusive 备份模式，
  与 PG 文档的说法需对齐后再定稿。
- BRIN 索引一节（L933-L941）「块级索引的空间占用会很小」——
  没有实验数据支撑，需补一次实测（插入 N 行后对比索引大小）或者删掉断言。
- 系统优化一章的调优建议（预读、虚拟内存参数、IO 调度器）——
  缺适用边界与实测数据，这些参数在不同内核与设备上差别很大，
  补写之前需先说明在什么环境测过。

## 可补的技术证据或产物

- 机制 / 源码入口：全文已经在引源码了，可以再往前一步——
  给出每节对应的**源码位置**（文件 + 函数），让读者能自己顺着看：
  块头 → `src/backend/storage/page/bufpage.h` 与 `bufpage.c` 的
  `PageHeaderData`；行指针 → `ItemIdData`；行头 → `HeapTupleHeader`；
  FSM → `src/backend/storage/freespace/`（连它自带的 README 都很好）；
  控制文件 → `src/backend/access/transam/pg_control.c`；
  WAL → `src/backend/access/transam/xlog.c`；
  clog → `src/backend/access/transam/clog.c`。
  有了这张「章节 → 源码文件」的对照表，读者查任何一个结构都知道去哪看。
- 实验或观测：补一组可复现的验证——用 `pageinspect` 扩展直接看真实的
  块头与行指针（`page_header(get_raw_page('t', 0))`、
  `heap_page_items(get_raw_page('t',0))`），把 L234-L310 讲的
  「块头 24 字节 + 行指针」在真实数据上打印出来；用
  `pg_filedump` 或 `pgstattuple` 看页的使用率；
  用 `pg_waldump` 看一条 WAL 记录长什么样。
- 工程取舍：索引那一节可以补一张选型表——索引类型 / 适合的数据分布 /
  写入代价 / 相对 PG 12 之后新增的选项（如 BRIN 的 `pages_per_range`、
  GIN 的 `fastupdate`、SP-GiST 的 `fillfactor`），把「索引的分类」那节
  升级成能直接用的选型依据。
- 结尾清单或下一篇链接：结尾给「搭建 → 验证 → 切换 → 巡检」四段清单；
  再链到本仓库的 `docs/pgsql/` 下讲复制、故障切换、巡检的文章，
  以及 `docs/cluster/` 下讲 quorum / fence 的文章（备库为什么会被
  fence，和本文的 quorate 状态是同一件事）。

## 已确认的改动

- （本轮只出审校记录，正文改动待确认后执行。）
