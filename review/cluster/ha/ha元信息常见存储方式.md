# 审校：ha元信息常见存储方式

- 原文：`docs/cluster/ha/ha元信息常见存储方式/index.md`
- 范围：全文
- 目标读者：做数据库高可用方案选型的工程师
  （知道 corosync、qdevice 这些词，想搞清楚各家把「元信息」放在哪）
- 一句话定位：横向对比四套 HA 方案（MySQL MHA、Oracle Site Guard、
  openGauss、OceanBase）把元信息存在哪里，以及存的地方会不会成为单点
- 核心判断：**四个案例里的「元信息」根本不是同一种东西，而文章把它们
  放在同一张表里比较**；此外结论的口径与表格不一致、Oracle 一节引用
  的文档里查不到文中用的术语、有一张图「如下图所示」但根本没有图、
  一条参考链接已经打不开
- 审校状态：建议中

## 优先修改

1. 位置：L3-L8（总表）与 L35-L36、L60、L81、L112（四条结论）
   - 问题：**表格和结论说的不是同一件事，口径不一致**。
     - 表格说「mysql mha → 第三方存储（zookeeper）」，
       但 L35 的结论说「在**不考虑 mha manager 单点问题**的场景下，
       mysql mha **不需要**持久化存储元信息」——表格把「引入 ZK」写成了
       MHA 的固有属性，而正文说它是可选的；
     - 表格说「oracle site guard → 第三方存储（oracle数据）」，
       L60 的结论说「在**不考虑 EMHOST 单点问题**的场景下，
       EMHOST 将数据保存在 EMDB 数据库中」——EMDB 就是那个第三方存储，
       所以「不考虑单点问题」这个前提在这个案例里**没有对应的部署形态**
       （见第 3 条）；
     - 表格说 openGauss / OceanBase → 节点自己存储，正文一致 ✅。
     → 读者看表会以为「MHA 一定用 ZK」，看正文才知道不是。
   - 建议：表格加一列「**是否引入第三方存储 / 前提条件**」，
     或者在表格下方加一句说明：「MHA 一列的第三方存储是**为解决
     manager 单点而可选引入**的，不是 MHA 的必需组件」。
   - 原因：README 的「信息重复」与「按读者的阅读路径组织」——
     表格是读者的第一印象，它和正文对不上，整篇的结论就立不住。

2. 位置：全文（「元信息」这个中心概念）
   - 问题：**四个案例里的「元信息」不是同一种东西，文章没有说清楚，
     却把它们并列比较**。按文章自己的描述：
     - **MHA**：其实**不存**元信息——L35 明说「不需要持久化存储元信息，
       通过 mha node 主动向 mha manager 注册和上报数据库状态信息」；
     - **Site Guard**：存的是 Site Guard 的部署配置与切换状态，
       落在 EM Repository（一个 Oracle 数据库）里；
     - **openGauss**：存的是**集群元信息**（CMS 维护的节点状态与集群配置），
       每个节点一份；
     - **OceanBase**：存的是**集群/租户元信息**，分布式保存，每节点一份。
     前两个是「集中式存储的元信息」，后两个是「分布式复制的元信息」；
     而 MHA 根本是「无状态上报」。把它们放进同一列比较，
     读者会以为它们是同类问题的不同答案。
   - 建议：在表格前加一段定义，把维度拆开——
     **元信息存不存在 / 存在哪 / 谁维护一致性 / 它挂了会怎样**。
     这四个问题才是各家真正可比的地方。表格也按这四列重排，
     「元信息存储方式」一列改成「元信息形态」（无状态上报 / 集中式存储 /
     分布式复制）。
   - 原因：README 的「先保真」「让抽象话落地」。这是全文的立论点，
     现在立不住。

3. 位置：L45-L60（Oracle Site Guard 一节）
   - 问题：**引用与术语对不上**。文章 L64 引的是 Oracle 11gR2 的
     MAA 手册「Understanding Oracle Site Guard Concepts」
     （`docs.oracle.com/cd/E24628_01/server.121/e52894/concepts.htm#GUARD126`，
     实测仍可访问），但那一页里：
     - **「EMHOST」出现 0 次**、**「EMAGENT」出现 0 次**
       （它写的是 **Oracle Management Agent (EM Agent)**）、
       **「EM Repository」出现 0 次**（只有 1 次普通的 "repository"）；
     - 该页的术语表用的是 Target、Site、Primary Site、Standby Site、
       Role、Switchover、Failover、Operation Plan、Prechecks、
       Health Checks、EM Agent、Enterprise Manager Cloud Control。
     → 文中用的 **EMHOST** 和 **EM Repository Database** 这两个名字，
     在自己引用的那一页里查不到出处。
     更要紧的是那一页明确写着 Site Guard 的成立前提：
     「Oracle Site Guard only supports Enterprise Manager deployments where
     **both primary and standby sites are managed by the same Enterprise
     Manager Cloud Control deployment**」——
     也就是说主备两站点必须由**同一个** EM 部署管理，
     而 EM 的元信息库本身就是单点。**「不考虑 EMHOST 单点问题」这个
     前提在 Site Guard 的架构里并不存在一种真的可以不考虑的部署形态**，
     它与 MHA「可以不要 ZK」的情况不是一回事，不能套同一个句式。
   - 建议：把 EMHOST / EMAGENT / EM Repository 三个名字换成引文里的
     官方术语，或者补上它们真正的出处；L60 的结论按上面对 Site Guard
     架构前提的说明重写——Site Guard 这一行应当直接写
     「元信息落在 EM Repository，**且 Site Guard 要求主备由同一个 EM 管理，
     该单点无法通过配置绕开**」，而不是套「不考虑单点问题」的句式。
   - 原因：涉及引用与术语，必须可回溯；结论的适用条件写错，
     读者按它做选型会误判 Site Guard 的单点风险。

4. 位置：L56-L58（Oracle Site Guard 的架构图）
   - 问题：**说了「如下图所示」，但下面没有图**。L56 是
     「oracle site Guard的详细架构如下图所示：」，L57 空行，
     L58 直接是「### 结论」。已核实 `img/` 目录下只有 4 张图
     （mha_arch.png、openguass_same_city.png、openguass_three_center.png、
     oceanbase_arch.png），**没有 Site Guard 的架构图**。
   - 建议：要么补一张（Site Guard 的 primary site / standby site /
     EM Cloud Control / EM Agent 的关系图，官方文档里有现成的
     Figure 2-1 可以参照），要么把这句话删掉。
   - 原因：README 的「信息重复」与基础校对——说了「下图」而没有下图，
     是读者一眼能看到的问题。

5. 位置：L10-L43（MySQL MHA 一节）
   - 问题：**没有说 MHA 的维护状态，而这个状态直接影响选型**。
     已核实：`github.com/yoshinorim/mha4mysql-manager` 的 master 分支
     **最后一次提交是 2018-03-22（"Release v0.58 (#102)"）**，
     仓库只有一个 tag `v0.58`，Wiki 的 Release Notes 里最新的 Manager
     版本也是 0.57（2015-05-31）。仓库本身**没有**标记为 archived，
     但主分支上已近 8 年没有开发活动。
     也就是说，这篇文章拿一个多年未更新的开源项目当第一个案例，
     读者容易误以为它是现役方案。
   - 建议：加一句状态说明（「MHA 的上游自 2018 年起已无正式发布，
     社区里更常被提的是 orchestrator / MGR」），或者在标题/开头就说明
     本文是**历史方案的横向对照**，不是现行方案推荐。
     另外顺带一提，MHA 的 Wiki 明确给出故障转移的时间构成
     ——「9-12 seconds to detect master failure, optionally 7-10 seconds
     to power off the master machine to avoid split brain, and a few seconds
     to apply differential relay logs to the new master. Total downtime is
     normally 10-30 seconds.」原文 L20 只说「整个故障转移过程对应用程序
     完全透明」，**「完全透明」是 Wiki 没有的说法**，而且 Wiki 明明写了
     有 10–30 秒的停写窗口；建议改成「对应用透明（不需要应用感知或改配置），
     停写窗口通常 10–30 秒」。
   - 原因：涉及版本与事实，必须可回溯；README 的「问题边界」与
     「工程取舍」。

6. 位置：L96-L118（OceanBase 一节）
   - 问题：**内容是 OceanBase 官方文档的逐字照抄，但没有标注**。
     已核实：L104 的「为了支持地区级无损容灾，通过 Paxos 协议的原理可以证明，
     至少需要 3 个地区。OceanBase 数据库采用的是两地三中心的变种方案：
     三地三中心五副本。该方案包含三个城市，每个城市一个机房，
     前两个城市的机房各有两个副本，第三个城市的机房只有一个副本。
     和两地三中心的不同点在于，每次执行事务至少需要同步到两个城市，
     需要业务容忍异地复制的延时。」与 OceanBase 官方
     「容灾部署方案」文档**逐字一致**；L98-L100 的「两地两中心物理备库」
     一段同样如此。
     → 这本身不是错（架构描述就该照官方说），但**照抄了却没说是照抄**，
     而且检查器 AIF-02 命中的 L100「更加高效利用资源」正是官方文档的原话
     ——按「消信号不是目的」，这一条**不必改**，只建议在段末标注出处。
     真正的问题是 **L118 的参考链接已经打不开**：
     `http://www.oceanbase.wiki/concept/...` 实测连接失败（curl 返回 000）。
   - 建议：L96-L118 整段标注为「以下依据 OceanBase 官方《容灾部署方案》」，
     并把参考链接换成当前可用的
     `https://www.oceanbase.com/docs/community-observer-cn-10000000000901136`
     （社区版《容灾部署方案》）或
     `https://www.oceanbase.com/docs/common-oceanbase-database-cn-1000000000818990`。
     顺便可以补上官方给的**容灾指标**——官方表格里
     「三地三中心五副本 = 地域级无损容灾，RTO 8s 内，RPO 0」，
     这比原文的定性描述有用得多。
   - 原因：涉及引用与链接，必须可回溯。

7. 位置：L35-L36、L60、L81、L112（结论的句式与 AIF-05）
   - 问题：**四条结论的句式不统一**：MHA 有两条、Site Guard 一条、
     openGauss 一条、OceanBase 一条，而且前两条都套了
     「在不考虑 X 单点问题的场景下……在考虑 X 单点问题的场景下……」，
     后两条却是「XX 集群元信息采用分布式方式保存，每个节点都会保存
     一份元信息」。
     检查器 AIF-05 命中的 L81~L112（相似度 0.93）正是 openGauss 与
     OceanBase 两条结论——**这是有意的平行结论**（两个产品同一结论），
     与已合入那篇的 L185/L209 属同类，按「消信号不是目的」**不必改**；
     更好的做法是**把这两条并进总表的最后一列**，正文就不必再重复一遍。
   - 建议：统一成「本节结论」一行，直接对应总表里那一行；
     L81、L112 合并进表格后，这两条正文可以删掉。
   - 原因：README 的「按读者的阅读路径组织」与「信息重复」。

8. 位置：L35、L36、L60、L81、L112（`<font color="red">`）
   - 问题：结论全部用 `<font color="red">` 包住。和同目录
     `corosync-down网卡仍处于多数派` 里同一个坑：`<font>` 出现在
     列表项开头会**让行首不再是列表标记**，marked 就不生成 `<ol>`；
     这里的 L35、L36 是两个以 `-` 开头的列表项，各自被 `<font>` 包住，
     渲染出来是两个普通段落而不是一个列表。
   - 建议：去掉 `<font>`，用 `**加粗**` 或直接用列表。
   - 原因：README 的「保留人的声音」不反对强调，但强调不该以破坏列表
     结构为代价；同仓库已有实测先例。

9. 位置：L73
   - 问题：**「机构」应为「架构」**——「openguass两地三中心的**机构**如下：」。
   - 建议：改字。
   - 原因：基础校对。

10. 位置：全文（术语与大小写）
    - 问题：同一个产品有多种写法：`openguass`（L67、L69、L73、L77、
      L81、L85、L86）/ `OpenGauss`（L67 标题）/ `openGauss`（L85 链接文字）；
      `oracle site Guard`（L45）/ `Oracle site Guard`（L56）/
      `oracle Site Guard`（L54）/ `site guard`（L3 表格）；
      `EMAGENT` / `EMHOST`（L48-L54）与官方文档的
      **EM Agent** 不一致。全文还有中英文之间缺空格的问题
      （「EMAGENT和数据库运行在同一个节点上」「查看备中心伪主库hamgr.log」）。
    - 建议：统一成各产品的官方写法：openGauss、Oracle Site Guard、
      EM Agent、EM Repository；中英文之间补空格。
    - 原因：README 的「术语一致」——README 把「术语不一致」明确列进了
      要查的问题。

11. 位置：L1 开头 / L118 结尾
    - 问题：开头没有一句话定位（检查器 STR-02 命中）——读者不知道
      这篇文章是「选型参考」还是「内部调研笔记」；结尾停在参考链接，
      没有可带走的产物（检查器 STR-03 命中）。
      另外缺本仓库其它文章都有的「编写人／编写内容／编写时间」表
      （检查器 MET-01 命中）。
    - 建议：开头补定位与编写信息；结尾把「四家元信息怎么存」这件事
      变成一张**可带走的对照表**（产品 / 元信息形态 / 一致性由谁保证 /
      单点在哪 / 挂了会怎样 / 该形态适合什么场景），这张表本身就能复用；
      再链到同目录 `中移动数据库停库问题分析/index.md`、
      `调整corosync网络波动时间操作文档/index.md`，
      以及 `docs/cluster/kingbase/tptc.md`（伪主节点与 observer
      那一套）。
    - 原因：README 的「一句话定位」「一份可带走的产物」「一条自然的内容路径」。

12. 位置：L27-L28（MHA 的单点问题）
    - 问题：**这一句是全文最有价值的一句，但被埋在一段里**：
      「在标准的方案中，mha manager是一个节点，当mha manager故障后，
      将无法进行自动故障转移。（即mha存在单点问题）」。
      它其实是整篇文章的核心命题——「元信息存哪，决定了哪个环节会成单点」。
      而 MHA 的答案恰恰是「不存元信息，靠 node 主动上报」，
      所以它的单点在 manager 进程本身。
    - 建议：把这句话提到开头，作为全文的主线：
      「元信息放在哪儿，决定了哪个环节会成为单点。MHA 的答案是
      不存；Site Guard 的答案是存在 EM Repository；openGauss 和
      OceanBase 的答案是每个节点各存一份、由协议保证一致。」
      然后每节按这条线写。
    - 原因：README 的「一个可记住的判断」——这篇文章缺一个能被记住的
      判断，而它其实已经有了，只是没说出来。

13. 位置：L67-L86（openGauss 一节）
    - 问题：**参考链接指向的是 `docs-opengauss.osinfra.cn` 这个镜像站**
      （实测可访问），而不是 openGauss 官方文档站；且引的是
      **5.0.0** 版本（L85-L86），正文没说结论对应哪个版本。
      L77 说「每个节点上的CMS就负责了节点之间的通信和集群状态维护」——
      CMS 是 openGauss 的集群管理组件，但正文没解释它是什么，
      也没给源码/文档入口。
    - 建议：换成官方文档站并标明版本；
      L77 补一句 CMS 是什么（以及 DCF 与 CMS 的分工——CMS 管集群状态，
      DCF 管数据复制），并链到本仓库的
      `docs/cluster/DCF/一文读懂openguass dcf网络模块.md`。
    - 原因：涉及版本与引用；README 的「问题边界」与「一条自然的内容路径」。

## 事实待核

- [x] OceanBase 三地三中心五副本的描述与官方文档逐字一致 —— OceanBase
  官方《容灾部署方案》（`https://www.oceanbase.com/docs/community-observer-cn-10000000000901136`）
  原文：「为了支持地区级无损容灾，通过 Paxos 协议的原理可以证明，至少需要
  3 个地区。OceanBase 数据库采用的是两地三中心的变种方案：三地三中心五副本。
  该方案包含三个城市，每个城市一个机房，前两个城市的机房各有两个副本，
  第三个城市的机房只有一个副本。和两地三中心的不同点在于，每次执行事务
  至少需要同步到两个城市，需要业务容忍异地复制的延时。」
  原文 L104 与之逐字相同。两地两中心物理备库一段（L98-L100）同样逐字一致。
- [x] OceanBase 官方给出的容灾指标 —— 官方《容灾部署方案》的表格：
  同机房三副本 = 机器级/机架级无损容灾，RTO 8s 内，RPO 0；
  同城三机房 = 机房级无损容灾，8s 内，RPO 0；
  **三地三中心五副本 = 地域级无损容灾，8s 内，RPO 0**；
  官方另称「三地五中心」满足金融行业 6 级容灾标准（RPO=0，RTO < 8s）。
- [x] AIF-02 命中的「高效」是 OceanBase 官方原话 —— 官方《容灾部署方案》
  「两地两中心物理备库」段：「进一步说，用户可以利用两地两中心实现双活，
  部署两套物理备库，两个地域互为主备。这样可以更加高效利用资源，
  并且达到更高的容灾能力。」原文 L100 与之逐字相同。
  → 这条不是作者自撰的空泛评价，**不必改**。
- [x] Oracle Site Guard 官方术语 —— 文章 L64 引用的 11gR2 MAA 手册
  「Understanding Oracle Site Guard Concepts」实测可访问（200），
  该页的术语表是 Target / Site / Primary Site / Standby Site / Role /
  Switchover / Failover / Operation Plan / Prechecks / Health Checks /
  **Oracle Management Agent (EM Agent)** / Enterprise Manager Cloud Control。
  在该页正文中检索：**EMHOST 0 次、EMAGENT 0 次、EM Repository 0 次**
  （"repository" 仅 1 次且非该含义）。
  → 文中三个组件名里，只有 EM Agent 能对上；EMHOST 与
  **EM Repository Database** 在引文里查不到出处。
- [x] Site Guard 的架构前提 —— 同页原文：「Oracle Site Guard only supports
  Enterprise Manager deployments where **both primary and standby sites are
  managed by the same Enterprise Manager Cloud Control deployment**.」
  → 主备必须由同一个 EM 部署管理，EM 元信息库的单点**无法通过配置绕开**，
  L60「在不考虑 EMHOST 单点问题的场景下」这一前提不成立。
- [x] MHA 的维护状态 —— GitHub API：`github.com/yoshinorim/mha4mysql-manager`
  `archived=false`，master 分支最近 5 次提交为
  2018-03-22「Release v0.58 (#102)」、2018-02-05、2018-01-19、2018-01-18 ×3；
  仓库 tags 只有一个 `v0.58`；Wiki 的 ReleaseNotes 页列出的最新 Manager
  版本是 0.57（2015-05-31）。
  → 主分支开发活动停在 2018-03-22，文章未提这一点。
- [x] MHA 故障转移的时间构成 —— MHA Wiki《Overview》：「9-12 seconds to
  detect master failure, optionally 7-10 seconds to power off the master
  machine to avoid split brain, and a few seconds to apply differential relay
  logs to the new master. **Total downtime is normally 10-30 seconds.**」
  原文 L20 的「整个故障转移过程对应用程序完全透明」不是 Wiki 的说法，
  且掩盖了 10–30 秒的停写窗口。
- [x] MHA 与 pacemaker 的组合用法 —— MHA Wiki《Overview》明确列出：
  「For example, you can use [Pacemaker(Heartbeat)] for detecting master
  failure and virtual IP address takeover, while using MHA for master failover
  and slave promotion.」这是与本仓库 corosync/pacemaker 内容天然接得上的
  组合，原文没提。
- [x] 参考链接可达性 —— 实测（2026-11）：
  `github.com/yoshinorim/mha4mysql-manager` 200、
  `github.com/yoshinorim/mha4mysql-manager/wiki/Architecture` 200、
  `github.com/yoshinorim/mha4mysql-manager/wiki/Advantages` 200、
  `github.com/yoshinorim/mha4mysql-manager/wiki` 200、
  `cnblogs.com/keme/p/9707755.html` 200、
  `docs.oracle.com/cd/E24628_01/server.121/e52894/concepts.htm` 200、
  `oracle.com/a/tech/docs/siteguard-app-dr-pca.pdf` 200、
  `oceanbase.com/docs/community-observer-cn-0000000000161661` 200、
  `docs-opengauss.osinfra.cn/zh/docs/5.0.0/...` 200；
  **只有 `http://www.oceanbase.wiki/concept/...` 连接失败（curl 返回 000）**。
- [x] 缺图 —— L56 说「oracle site Guard的详细架构如下图所示：」，但
  L58 紧接「### 结论」；`docs/cluster/ha/ha元信息常见存储方式/img/` 下
  只有 4 张图（mha_arch、openguass_same_city、openguass_three_center、
  oceanbase_arch），**没有 Site Guard 的图**。其余 3 处引用与图一一对应。
- [x] AIF-05 命中的 L81~L112 是平行结论 —— openGauss 与 OceanBase 两条
  结论句式相同（相似度 0.93），属有意的平行结构，**不必改**。
- 「元信息」在四个案例里分别指什么 —— MHA 是「不存，靠 node 上报」、
  Site Guard 是「EM Repository 里的部署配置与切换状态」、
  openGauss 是「CMS 维护的集群元信息」、
  OceanBase 是「分布式保存的集群/租户元信息」。
  四者不同类，文章需要给出一个统一口径（或明说「不严格同类」）。
- MHA 在本文里的定位 —— 是历史方案回顾，还是仍在用的方案？
  若仍在用，需说明用的是哪个 fork / 发行版补丁。
- 「EMHOST」具体指哪个组件、出处在哪 —— 需作者给出；它与
  Enterprise Manager Cloud Control 是什么关系。
- 各方案对应的**版本** —— Site Guard 引用的是 11gR2 的 MAA 手册，
  openGauss 引用的是 5.0.0，OceanBase 引用的是 community-observer 文档，
  MHA 是 0.58；正文没有统一说明这些结论对应哪个版本的产品。
- 现场实际用的是其中哪几套 —— 这决定了本文是「选型参考」还是
  「我们用过的方案回顾」，定位不同，写法也不同。

## 可补的技术证据或产物

- 机制 / 源码入口：MHA 的 manager / node 两侧代码在
  `github.com/yoshinorim/mha4mysql-manager` 与 `mha4mysql-node`
  （Perl），「mha node 主动上报、manager 无状态」这个结论可以直接从
  `MHA::Manager` 与 `masterha_check_status` 的代码路径看出来；
  openGauss 侧对应 DCF（`docs/cluster/DCF/一文读懂openguass dcf网络模块.md`
  已在本仓库）与 CMS 的集群元信息维护；
  OceanBase 侧对应 Paxos 组与租户元信息（官方《容灾部署方案》已给全图）。
- 实验或观测：给一个**可复现的对照实验**——把同一个「元信息单点」
  场景在两套方案上各演一遍，例如：
  (a) MHA：kill 掉 manager，看是否还能自动切换（预期不能，对应 L27）；
  (b) openGauss / OceanBase：kill 掉一个节点，看元信息是否仍在其它节点上
  可用（预期可以，对应 L81/L112）。
  这组实验能把「元信息放哪 → 谁是单点」这个判断变成读者能自己验证的结论。
- 工程取舍：把四套方案按同一组维度摆开——
  元信息形态 / 一致性由谁保证（元信息自身走 Paxos？还是靠单一存储？/
  还是无状态上报）/ 元信息丢失的后果（脑裂？误切换？只是不能切？）
  / 依赖的外部组件（ZK / EM / 无）/ 运维成本 / 适用场景。
  这张表是本文最该交付的东西。
- 结尾清单或下一篇链接：一页「元信息单点排查清单」
  （这套 HA 方案的元信息存在哪 → 它挂了会怎样 → 谁来兜底 →
  兜底本身是不是新的单点）；再链到同目录
  `中移动数据库停库问题分析/index.md`（一个真实的「quorum 判定 + 单点」
  案例）与 `docs/cluster/kingbase/tptc.md`。

## 已确认的改动

- （本轮只出审校记录，正文改动待确认后执行。）
