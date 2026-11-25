# 审校进度索引

审校范围：`docs/` 全树（649 篇）里**面向读者的技术文章**（426 篇）。
非内容（站点目录页、代码仓库说明、内部工作文档、外链指北、只有标题的未成稿）、
速查/清单/操作类、非技术内容与**转载稿**共 223 篇已排除——分类与逐篇清单见
[`scope/2026-11-14-scope-classification.md`](scope/2026-11-14-scope-classification.md)。

> 转载稿（正文顶部有 `> 来源:`，署名他人）不按原创稿审改——改写等于改别人的东西。
> 怎么处理（保留标注 / 删除 / 重写）是站长的决定。

规范见 [`README.md`](README.md)，落地机制见
[`specs/2026-11-13-content-review-design.md`](specs/2026-11-13-content-review-design.md)，
实现计划见 [`plans/2026-11-13-content-review.md`](plans/2026-11-13-content-review.md)。

## 怎么读这张表

| 列 | 含义 |
| --- | --- |
| 记录 | 审校记录；点进去是逐条建议 |
| 支柱 | `docs/` 下的一级目录 |
| 状态 | 待审 → 审校中 → 建议中 → 已确认 → 已合入 |
| 信号 | 检查器给出的 warn 级信号条数（warn 规则共 8 条，所以是 0~8；全树实测最高 3 条） |
| 待确认 | 「事实待核」里还没销掉的条目数——状态为「已合入」时必须是 0 |
| 不阻塞 | 标了「不适用」的条目数：事实本身还没核实，但本次改动没碰它，不卡合并 |
| 批次 | 试点 / 1 / 2 … |

**信号为 0 不等于文章没问题**——检查器只出机械信号，技术深度、定位、语气这类
判断是人工做的，机械信号干净的文章照样可能需要改。

## 进度

已审 18 篇（首批试点：数据库内核四支柱 5 篇），批次 1 按信号密度新增 5 篇，
批次 2 按信号密度清完 cluster 支柱的 2 信号队列（8 篇，已核空）。
同标题的两对文章已各自合并为一篇：`corosync-down网卡仍处于多数派`（并掉 `-1` 版）
与 `两地三中心`（并掉 `tptc_improve`）——站点上不再保留重复的第二篇。
范围扩到全树后按信号密度排序继续——排序依据见范围分类文档的「逐支柱分布」。

图示可读性规则（`FIG-01` 图太长该拆 / `FIG-02`「下图」离图太远）加入后，
全树 639 篇里 84 篇命中 `FIG-01`、5 篇命中 `FIG-02`。已审文章中
`一文读懂openguass dcf网络模块`（6 张超长链式流程图）与 `06-heap-and-mvcc`
（HeapTuple 结构图 + UPDATE 流程图）的信号数因此各 +1。
**已合入的文章不保证信号为 0**——规则是后加的，之前的稿子没按新规则重审。

> `FIG-01` 的判定原先会抖：算「一条流程多长」时由 `set` 的迭代顺序决定
> DFS 从哪个框出发，而字符串哈希每进程随机 —— 同一棵树连跑四次，
> warn 在 509 / 510 之间来回跳（`tools/review-check.py` 的 `_longest_path`）。
> 2026-11-17 改成「先做一次确定性 DFS 找回边、切成 DAG 再算最长路径」，
> 现在连跑四次结果逐条相同，全树 warn 稳定在 **515**
> （分布式这一块搬完之后：新目录页多了 5 个，warn 跟着多 4 条）。

站内链接另有一把尺子：`tools/check-internal-links.py`（2026-11-17 新增）。
母稿侧查相对链接能不能解析到目标，产物侧查 `public/` 里的站内 href 有没有落到
不存在的页面上。首跑抓出 **11 条产物侧死链**（线上的死链，多在
`db/opengauss-*` 两篇文章里，指向 `db/postgresql/` 下少了一级的路径），
母稿侧 **62 条**相对链接解析不到（多在 `database/_index.md` —— 分类页本身
不发，读者看不见，但迁移时会咬人）。这两组数字是**迁移前**的基线，
搬家后必须回到 0（死链）/ 不增加（母稿侧）。

**PostgreSQL 试点搬完后的实测（2026-11-17）**：产物侧 **11 → 0**
（132457 条站内 href 全通）；母稿侧 **62 → 5**，剩下的 5 条逐条核对过，
都是迁移前就在的误报（`{image_url}` 模板占位符、`life/shehui/_index.md` × 2、
两个代码块里的 `DatumGetPointer(...)` / `order_date`），在 master 上逐字相同。

**Linux 块搬完后的实测（2026-11-17）**：`docs/linux/` 38 篇 + `docs/network/` 9 篇
（47 篇）收进 `docs/source-tracks/linux/`，分成 5 个系列：日常操作与工具 12、
存储与文件系统 1、内核机制与驱动 14、内存与动态链接 9、网络协议与抓包 11。
母稿侧死链 5 → 5（没动，逐条核对过）；**产物侧死链 0**（144689 条站内 href 全通）；
日期漂移 0（`capture-dates.py --check` 逐篇比 572 篇）；
47 篇正文逐字节相同（合并 master 后重比：全树 1721 个文件，
只有 63 个改了路径，内容逐字节相同，另 6 个是新建的目录页）；
学习路径分类 572 篇逐篇比对，0 处变化；
`publish/outbox/` 46 份快照按新路径改名，全部 567 份快照逐个核过，
文件名与 `content_id` **0 处不一致**；
mermaid 渲染失败 **109 张，与搬家前持平**（源码侧能说死：master 的树与合并后的树，
1309 张唯一 mermaid 源码的集合完全相同，0 张新增、0 张消失）。

**分布式块搬完后的实测（2026-11-17）**：`docs/cluster/` 61 篇 + `docs/openguass/` 4 篇
（65 篇 + 26 个资源）收进 `docs/distributed/`，分成 6 个系列：分布式基础 7、
一致性协议 28、高可用与容灾 9、分布式存储 5、选型与对比 4、实战与故障现场 11
（合并了一对**逐字节相同**的 raft 副本，实际落地 64 篇）。
母稿侧死链 5 → 5（没动）；**产物侧死链 0**（152963 条站内 href 全通）；
日期漂移 0（`capture-dates.py --check` 逐篇比 574 篇）；
65 篇正文逐字节相同（62 篇一字不差，3 篇只差跟着新位置重算的相对链接），
26 个资源一字不差；
学习路径分类 581 篇逐篇比对「赛道 + 阶段」，**0 处变化**
（少的那篇是合并掉的重复副本，`distributed` 赛道 65 → 64）；
`publish/outbox/` 60 份快照按新路径改名，全部 566 份快照逐个核过，
文件名与 `content_id` **0 处不一致**；
mermaid 渲染失败 **109 张，与搬家前持平**（产物侧唯一源码 1308 张；源码侧：唯一 mermaid 源码的集合完全相同）。
顺带修掉四处：重复副本合并后两个旧 URL 都在（重定向表的键现在可以带一段日期）、
带空格的文件名在模板里的链接原来改不掉（「只编码空格」那一种写法补上了）、
落地页的白名单改成逐篇列出（`DISTRIBUTED_DB_KERNEL`）、
落地页里那条指向被合并副本的链接也改成了幸存那篇的真实地址（产物侧查出的 1 条死链）。

**部署链路顺带修掉一处断点（2026-11-17）**：连续两个 push 的 Deploy Hexo
都断在 "Upload build artifact" —— 旧分类「PostgreSQL 源码修炼之路:内核深度拆解专题」
的跳转页目录名带冒号，GitHub 的 upload-artifact 拒绝 `:*?"<>|`，
一个带冒号的目录就让整个产物传不上去。那个分类线上从来没出现过，
所以那一页不再生成（`tools/sync-hexo.py` 对文章重定向和分类重定向都加了这道检查），
`tests/test_sync_hexo_redirects.py` 守着。

| 记录 | 支柱 | 状态 | 信号 | 待确认 | 不阻塞 | 批次 |
| --- | --- | --- | --- | --- | --- | --- |
| [postgresql-mvcc](source-tracks/postgresql/transaction-mvcc/postgresql-mvcc.md) | source-tracks | 已合入 | 0 | 0 | 1 | 试点 |
| [postgresql-logical-replication-worker-model](source-tracks/postgresql/logical-replication/postgresql-logical-replication-worker-model.md) | source-tracks | 已合入 | 0 | 0 | 1 | 试点 |
| [06-heap-and-mvcc](source-tracks/postgresql/transaction-mvcc/learning-path/06-heap-and-mvcc.md) | source-tracks | 已合入 | 1 | 0 | 2 | 试点 |
| [checkpoint机制浅析](source-tracks/postgresql/wal-and-recovery/checkpoint机制浅析.md) | source-tracks | 已合入 | 0 | 0 | 0 | 试点 |
| [分布式一致性协议](distributed/foundations/分布式一致性协议.md) | distributed | 已合入 | 0 | 0 | 2 | 试点 |
| [file](base/file.md) | base | 已合入 | 0 | 0 | 3 | 1 |
| [corosync-down网卡仍处于多数派](distributed/field-notes/corosync-down网卡仍处于多数派.md) | distributed | 已合入 | 0 | 0 | 6 | 1 |
| [tptc](distributed/ha-and-dr/tptc.md) | distributed | 已合入 | 0 | 0 | 8 | 1 |
| [从原理到实践，彻底告别 IPv6 上网不稳定的问题](source-tracks/linux/networking/从原理到实践，彻底告别 IPv6 上网不稳定的问题.md) | source-tracks | 已合入 | 0 | 0 | 6 | 1 |
| [Postgresql存储、索引及系统优化、主备切换](source-tracks/postgresql/replication-ha/Postgresql存储、索引及系统优化、主备切换.md) | source-tracks | 已合入 | 1 | 0 | 2 | 1 |
| [raft重要概念](distributed/consensus/raft重要概念.md) | distributed | 建议中 | 2 | 4 | 0 | 2 |
| [sanlock实现共享corosync共享存储仲裁](distributed/field-notes/sanlock实现共享corosync共享存储仲裁.md) | distributed | 建议中 | 2 | 6 | 0 | 2 |
| [中移动数据库停库问题分析](distributed/ha-and-dr/中移动数据库停库问题分析.md) | distributed | 建议中 | 2 | 8 | 0 | 2 |
| [ha元信息常见存储方式](distributed/ha-and-dr/ha元信息常见存储方式.md) | distributed | 建议中 | 2 | 5 | 0 | 2 |
| [corosync-qdevice使用](distributed/field-notes/corosync-qdevice使用.md) | distributed | 建议中 | 2 | 5 | 0 | 2 |
| [corosync qnet挂死场景分析解决](distributed/field-notes/corosync qnet挂死场景分析解决.md) | distributed | 建议中 | 2 | 7 | 0 | 2 |
| [从两地三中心到OceanBase的多地多中心 - 墨天轮](distributed/distributed-storage/从两地三中心到OceanBase的多地多中心 - 墨天轮.md) | distributed | 建议中 | 2 | 8 | 0 | 2 |
| [一文读懂openguass dcf网络模块](distributed/consensus/一文读懂openguass dcf网络模块.md) | distributed | 建议中 | 3 | 7 | 0 | 2 |
