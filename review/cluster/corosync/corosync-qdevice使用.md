# 审校：corosync-qdevice使用

- 原文：`docs/cluster/corosync/corosync-qdevice使用.md`
- 范围：全文
- 目标读者：给数据库集群配第三方仲裁的工程师
  （知道 corosync 是什么，但没用过 qdevice/qnetd）
- 一句话定位：从编译 qdevice/qnetd 到跑起来的操作手册，
  外加双节点场景下 votequorum 与 qdevice 两条路的对比
- 核心判断：**「corosync 1.0 版本没有投票机制」是错的**（1.x 就有基于投票的
  quorum 服务，还带共享磁盘设备）；两个投票算法各自的**硬前提正好相反**
  而正文只字未提；算法落地的另一半——corosync.conf 里的
  `quorum.device.*` 配置——全篇没有
- 审校状态：建议中

## 优先修改

1. 位置：L114（corosync 版本沿革）
   - 问题：**三句话里三处都错**。原文：「corosync1.0版本没有投票机制，
     需要使用corosync-qdevice来配合投票仲裁，corosync2.0版本通过votequorum
     提供投票机制。」
     - **corosync 1.x 本来就有基于投票的 quorum 服务**。已核实 v1.4.4 的
       源码树：`exec/quorum.c`（quorum 服务）、`exec/quorum.h`、
       `lib/votequorum.c`、`include/corosync/votequorum.h`、
       `lib/libvotequorum.verso`，以及手册
       `man/votequorum_overview.8`（2009-01-26）——它开头就写着
       「the external interface to the **vote-based quorum service**.
       This service is optionally loaded into all nodes in a corosync cluster
       to avoid split-brain situations. It does this by having a **number of
       votes assigned to each system**」。
     - **corosync-qdevice 是 2.0 之后才有的独立项目**，1.0 时代根本不可能
       用它：qdevice 项目 README 的依赖写的是「**Corosync >= 2.0**、NSS」，
       并说明「Originally both qdevice and qnetd were part of the Corosync
       codebase … but because it got quite big we decided to split it into
       its own sub-project」。
     - **corosync 1.x 的 votequorum 还带共享磁盘设备**。v1.4.4 有
       `man/votequorum_qdisk_register.3`，原文：
       「A quorum device is an external way of adding votes to a small
       cluster. The quorum device is, in effect, a **pseudo node** in the
       cluster that provide votes based on some external device, usually a
       **shared disk partition** or perhaps a network router.」
       → 也就是说，1.x 的磁盘仲裁是以 votequorum 库 API
       （`votequorum_qdisk_register` / `votequorum_qdisk_poll` /
       `votequorum_qdisk_unregister`）提供的。
   - 建议：改成准确的三段——
     「corosync 1.x 就有基于投票的 quorum 服务（`exec/quorum.c`），
     并通过 votequorum 库支持外部投票设备（当时有共享磁盘 qdisk）；
     2.0 把 quorum 服务重写为 votequorum + qdevice 两块，第三方仲裁改由
     独立的 corosync-qdevice 项目提供（要求 corosync >= 2.0）；
     2.x 之后上游只保留 `net` 一种仲裁模型（qdevice 的 man page：
     「Currently only net is supported」），磁盘仲裁不再是上游能力。」
     这段沿革正好接得上同目录 `sanlock实现共享corosync共享存储仲裁.md`
     讨论的「为什么要自己移植 sanlock」。
   - 原因：涉及版本与事实，必须可回溯。这是全文唯一的版本沿革断言，
     三句都站不住，读者按它去理解 corosync 的演进会错。

2. 位置：L108-L109（两个投票算法）
   - 问题：**两个算法各自有一条硬前提，而且正好相反，正文一个字都没提**。
     已核实 qdevice man page「MODEL NET ALGORITHMS」：
     - **ffsplit**：「To use this algorithm it's required to set the number of
       votes per node to 1 (default) and the qdevice number of votes has to be
       also 1. This is achieved by setting **`quorum.device.votes` key in
       corosync.conf file to 1**.」
     - **lms**：「For LMS to work, the number of qdevice votes has to be set
       to **default (so just delete `quorum.device.votes` key from
       corosync.conf)**.」
     → 选 ffsplit 就必须显式写 `quorum.device.votes: 1`；
     选 lms 就必须**把这个键删掉**（走默认值，默认值是
     `number_of_nodes - 1`，即「节点数减一」）。照原文搭，
     很容易两边都配错——而配错的后果是投票数不对，
     要到分区时才发现少一票或多一票。
     此外，ffsplit 的判定规则原文也没给全，官方原话是：
     「It provides exactly one vote to the partition with the highest number
     of active nodes. If there are two exactly similar partitions, it provides
     its vote to the partition with higher score. The score is computed as
     (**number_of_connected_nodes + number_of_connected_nodes_with_passed_
     heuristics − number_of_connected_nodes_with_failed_heuristics**). If the
     scores are equal, the vote is provided to partition with the most clients
     connected to the qnetd server. If this number is also equal, then the
     **tie_breaker** is used.」
   - 建议：把两个算法的「score 公式 + 票数前提 + 平手时的判定顺序」写成
     两张小表，并给出对应的 corosync.conf 片段。
   - 原因：README 的「机制解释」与「踩坑与校验」——
     这是读者配 quorum 时唯一会踩的坑。

3. 位置：L108-L109（漏掉的两个关键参数）
   - 问题：**漏了 `tie_breaker` 与 `keep_active_partition`**，
     而这两个直接决定「平手时把票给谁」。
     qdevice man page：
     - `tie_breaker`：「can be one of `lowest`, `highest` or `valid_node_id`
       (number) values. It's used as a **fallback if qdevice has to decide
       between two or more equal partitions**. … Default is `lowest`.」
     - `keep_active_partition`：「Can be one of `on` or `off` and specifies if
       **keep active partition tie breaker** should be used. When this option
       is enabled and tie happens QNetd will prefer partition with members of
       previously active (quorate) partition. This is hard-coded behavior of
       LMS algorithm so this setting affects only FFSplit algorithm.
       Default is `on`.」
   - 建议：补上这两个参数，并说明它们与 ffsplit / lms 的适用关系
     （`keep_active_partition` 只影响 ffsplit）。
     顺带补一句：官方 `algorithm` 其实有四个取值——
     `ffsplit`、`lms`，以及 `test`、`2nodelms`，后两个
     「mainly for developers and shouldn't be used for production clusters」。
   - 原因：README 的「技术深度检查」——参数是读者真正要带走的东西。

4. 位置：L129（配置键名）
   - 问题：**键名写错了层级**。原文「通过在corosync.conf的**device配置模块**中
     配置`algorithm: ffsplit`」。上游的完整键名是
     **`quorum.device.net.algorithm`**（`algorithm` 在 `quorum.device.net`
     子键下），同级还有 `quorum.device.net.tls`（默认 **on**）、
     `quorum.device.net.host`（**必填**，qnetd 的地址）、
     `quorum.device.net.port`（默认 5403）、`tie_breaker`、
     `connect_timeout`、`keep_active_partition`；
     `quorum.device` 这一层则是 `model`、`votes`、`timeout`、`sync_timeout`、
     `interval`。
   - 建议：改成完整键名，并给一段**完整可用的 corosync.conf 片段**
     （`quorum { provider: corosync_votequorum; device { model: net;
     votes: 1; net { host: …; tls: on; algorithm: ffsplit; } } }`）。
     顺带说明 `quorum.device.net.tls` 默认 on，意味着 qdevice 与 qnetd
     之间默认尝试 TLS，需要 NSS 数据库；`off` 是「唯一不需要正确初始化
     NSS 数据库」的模式（官方原话）。
   - 原因：README 的「可复现证据」——读者照原文搭会写错键。

5. 位置：全文（缺 corosync.conf 这一半）
   - 问题：**全篇没有一段 corosync.conf 的完整配置**。
     文章讲的是「编译 qdevice/qnetd → 跑 qnetd → qdevice 连上去」，
     但 qdevice 真正干活的一半配置在 corosync.conf 的 `quorum.device.*`
     里，而这一半完全没写：`model: net` 是必须的（man page：
     「Specifies the model to be used. This parameter is required.」）；
     `quorum.device.net.host` 必填；`votes` 怎么设与算法相关；
     TLS 默认开、证书要用 `corosync-qnetd-certutil` /
     `corosync-qdevice-net-certutil` 生成——这些一个都没提。
   - 建议：把文章分成「qnetd 侧」「corosync.conf 侧」「验证」三段，
     每一段都能独立跑通。
   - 原因：README 的「按读者的阅读路径组织」——
     现在读者走完全文仍然不知道 quorum 那一侧要怎么配。

6. 位置：L110（`last_man_standing` 与 qdevice）
   - 问题：**两个 LMS 是同名不同物，而原文把它们并列，读者必然混淆**；
     而且「不兼容」这个结论在 qdevice 的文档里查不到出处。
     - **corosync 的 `last_man_standing`**（votequorum.5）：
       「Enables Last Man Standing (LMS) feature (default: 0). Tunable
       `last_man_standing_window` (default: 10 seconds, expressed in ms).」
       机制是「允许集群在特定情况下**动态重算 expected_votes 与 quorum**」，
       官方举的例子是 8 节点集群：3 个节点挂掉后仍 quorate，
       等 `last_man_standing_window`（默认 10 秒）超时后重算成
       `(expected_votes 5, quorum 3)`，再挂 2 个仍 quorate，再重算成
       `(expected_votes 3, quorum 2)`。并且官方明确写
       「It is essential to enable **WFA** when using LMS in High Availability
       clusters.」
     - **qdevice 的 `lms` 算法**：是 qnetd 在分区时按 ring_id 划分分区、
       给其中一个分区投票的仲裁算法，与上面那个毫无关系。
     - 「不兼容」这一结论：在 qdevice 的 man page 与 README 里检索
       `last_man_standing` / `incompatib` **均 0 命中**。
   - 建议：改写这一条，把两个 LMS 的区别点破，并说明为什么不该同时开
     （两者都在改「票数」这一件事：votequorum 的 LMS 动态重算
     expected_votes/quorum，qdevice 的 LMS 由 qnetd 直接给分区投票）。
     若确实有官方的「不兼容」说明，补上出处；补不出就标明这是作者判断。
     顺带补上「用 votequorum 的 LMS 必须同时开 WFA」这条官方要求。
   - 原因：涉及概念与结论，必须可回溯；同名不同物是读者最容易读错的地方。

7. 位置：L5 与 L122
   - 问题：**同一句话一字不差地出现两次**（检查器 AIF-05 报相似度 1.00）：
     「在仲裁方 `corosync-qnetd` 的协助下，`corosync-qdevice` 会提供一个
     可配置的投票数，以使群集可以承受大于标准仲裁规则所允许的节点故障数量。」
     L5 是全文第二段，L122 是「votequorum与corosync-qdevice」一节的第二段。
     另外这两段都超长（L5 202 字、L122 211 字，检查器 AIF-03 命中）。
   - 建议：L122 那句删掉，只保留 L122 独有的信息
     （「votequorum 不需要第三方仲裁，直接集成在 corosync 里」、
     「qdevice 需要一台非集群节点跑 qnetd」）；L5 拆成两句。
   - 原因：README 的「信息重复」；重复段还会让读者误以为是两处独立佐证。

8. 位置：L80（sysconfig 文件路径）
   - 问题：**路径与文件名与上游不符**。原文「在`/etc/corosync/qnetd/`下创建
     `corosync-qnetd.sysconfig`」。上游的实际情况：
     - 安装目录由 configure 的 `--with-initconfigdir` 决定，**默认值是
       `${sysconfdir}/sysconfig`**（即 `/etc/sysconfig`），
       不是 `/etc/corosync/qnetd/`；
     - 装出来的**文件名是 `corosync-qnetd`，不带 `.sysconfig` 后缀**——
       上游仓库里的样本文件叫 `init/corosync-qnetd.sysconfig.example`，
       而 systemd unit 写的是 `EnvironmentFile=-@INITCONFIGDIR@/corosync-qnetd`。
     → 按原文写出来的文件名，systemd 读不到。
     顺带一提：文章 L83-L95 那段 sysconfig 内容本身**抄自上游样本**
     （包括「This has no effect if systemd unit is used (you have to change
     unit file)」这句注释），只是漏了上游样本里的三个
     `COROSYNC_QNETD_CERTUTIL_*` 变量。
   - 建议：改成上游的安装路径与文件名，并说明「以 `make install` 实际
     装出来的路径为准（`make install` 后可在 `$(INITCONFIGDIR)` 下确认）」。
   - 原因：涉及可复现步骤；README 的「可复现证据」。

9. 位置：L101（启动 qnetd）
   - 问题：**用的是 sysvinit 的老路子，而上游现在同时提供 systemd unit**。
     上游 `init/` 目录里有 `corosync-qnetd.service.in`
     （`EnvironmentFile=-@INITCONFIGDIR@/corosync-qnetd`、
     `ExecStart=@QNETDDIR@/corosync-qnetd -f $COROSYNC_QNETD_OPTIONS`、
     `Type=notify`、`RuntimeDirectory=corosync-qnetd`、
     `Restart=on-abnormal`）、
     `corosync-qnetd.in`（sysvinit 脚本）、以及
     `corosync-qnetd.sysusers.conf.example`
     （内容是 `u coroqnetd - 'User for corosync-qnetd' - -`）。
   - 建议：补 systemd 的装法（`systemctl enable --now corosync-qnetd`），
     并把建用户那步改成用 sysusers 片段；同时说明 `RuntimeDirectory`
     会自动创建 `/var/run/corosync-qnetd`，不必手工建。
   - 原因：涉及可复现步骤；老路子在新发行版上不一定有 init 脚本。

10. 位置：L27（编译依赖）
    - 问题：**漏了一个必需依赖**。qdevice 项目 README 的
      「Dependencies」写的是「**Corosync >= 2.0**」「**NSS**」。
      NSS（Network Security Services）不是可选项——`quorum.device.net.tls`
      默认就是 `on`，没有 NSS 就没有可用的证书库。
      原文 L45-L49 只处理了「找不到 libcorosync_common 就导出
      PKG_CONFIG_PATH」，这解决不了 NSS 缺失。
    - 建议：在编译步骤前补一句依赖清单
      （corosync >= 2.0 的开发包、NSS 开发包、libqb 等），
      并说明 `PKG_CONFIG_PATH` 这个坑的根因是上游把 pkgconfig 装在了
      非默认前缀下。
    - 原因：涉及可复现步骤；README 的「可复现证据」。

11. 位置：L3（第一句话）
    - 问题：**「qdevice要用途是」是病句**，应为「qdevice 的主要用途是」。
      另外整句把「多数派 quorum 协议解决脑裂」与「qdevice 让集群在多数
      节点挂掉后仍能服务」并排放在一起，读者容易以为两者矛盾——
      实际上不矛盾：qdevice 提供的是**额外的仲裁票**，让集群在
      「存活节点 + 仲裁票」达到多数时仍可 quorate。
    - 建议：改成「qdevice 的主要用途是……：它由第三方仲裁方授予一票，
      让集群在存活节点不足多数时仍能满足 quorum 计算」。
    - 原因：基础校对 + 机制表述；README 的「先保真」。

12. 位置：L104-L129（双节点场景对比）
    - 问题：**对比维度不齐，且 votequorum 一侧漏了关键机制**。
      - L128 说「votequorum通过在corosync.conf中配置two_node来解决双节点
        场景的高可用问题」——对，但没说什么机制。官方 votequorum.5 的
        解释是：「With a standard two node cluster, each node with a single
        vote, there are 2 votes in the cluster. Using the simple majority
        calculation (50% of the votes + 1) to calculate quorum, the quorum
        would be 2. … **Enabling two_node: 1, quorum is set artificially
        to 1**.」也就是把 quorum 人工降成 1。
      - 原文也没提两个官方约束：「**NOTES: enabling two_node: 1
        automatically enables wait_for_all**」以及
        「If more than 2 nodes join the cluster, the two_node option is
        **automatically disabled**」（原文 L128 的后半句与这句一致 ✅）。
      - L129 说 qdevice 用 `algorithm: ffsplit` 解决双节点——但**双节点
        场景下 LMS 算法（`2nodelms` 是开发者用的变体）通常更合适**，
        官方对 lms 的描述是「If the node is the only one left in the
        cluster that can see the qnetd server then we return a vote」，
        这正是双节点挂掉一个的场景。原文把 ffsplit 说成双节点的默认解，
        没有给出理由，也没提另一个选择。
    - 建议：把这一节改成一张对照表——
      （手段 / 是否需要第三方节点 / 双节点怎么配 / 第三个节点加入后怎么办 /
      脑裂风险 / 票数怎么算），并把 two_node 的机制与 WFA 联动写进去。
    - 原因：README 的「工程取舍」；这一节是全文的落点。

13. 位置：全文（缺验证步骤）
    - 问题：**文章教人把服务跑起来，但没教人怎么确认它生效了**。
      qdevice 提供了工具（编译产物里就有 `corosync-qdevice-tool`、
      `corosync-qnetd-tool`），却没有一句「怎么验证」。
    - 建议：补一段验证——
      `corosync-qdevice-tool -s` 看本节点与 qnetd 的连接与票数状态、
      `corosync-qnetd-tool -l` 看 qnetd 侧登记了哪些集群；
      再补一个**可复现的实验**：双节点环境停掉一个节点，
      观察另一节点是否仍然 quorate 并继续服务——
      这就是本文该有的「可复现证据」。
    - 原因：README 的「可复现证据」「一份可带走的产物」。

14. 位置：L1 开头 / L129 结尾
    - 问题：开头没有一句话定位（检查器 STR-02 命中）；结尾停在
      「配置algorithm: ffsplit来解决」，既没有产物也没有下一站
      （检查器 STR-03 命中）；缺「编写人／编写内容／编写时间」表
      （检查器 MET-01 命中）。
    - 建议：开头补定位（本文回答「双节点集群怎么借第三方仲裁活下来」
      与「qdevice 怎么装、怎么配、怎么验证」）；结尾补一份
      「配置项速查表 + 验证命令 + 故障排查清单」，再链到同目录
      `corosync qnet挂死场景分析解决.md`、`sanlock实现共享corosync共享存储仲裁.md`，
      以及 `docs/cluster/ha/中移动数据库停库问题分析/index.md`
      （一个真实的「失去多数派 → 停库」案例）。
    - 原因：README 的「一句话定位」「一份可带走的产物」「一条自然的内容路径」。

15. 位置：L1-L5（版本边界）
    - 问题：**全文没有版本信息**。文章讲的是编译与配置，而 qdevice 的
      行为在不同版本间有变化（例如 `quorum.device.net.tls` 默认 on、
      `2nodelms` 算法的存在与否）。
    - 建议：加一行「本文基于 corosync-qdevice <版本> / corosync <版本>
      / NSS <版本>」。
    - 原因：README 的「问题边界」。

16. 位置：L111
    - 问题：**「制裁设备」应为「仲裁设备」**——原文「一般不在现有集群节点中
      运行制裁设备」。这是全文唯一的错别字，但它出现在一条关键的部署建议里。
    - 建议：改字。
    - 原因：基础校对。

## 事实待核

- [x] corosync 1.x 就有基于投票的 quorum 服务 —— v1.4.4 源码树含
  `exec/quorum.c`、`exec/quorum.h`、`lib/votequorum.c`、
  `include/corosync/votequorum.h`、`lib/libvotequorum.verso`；
  `man/votequorum_overview.8`（2009-01-26）：「the external interface to the
  **vote-based quorum service**. This service is optionally loaded into all
  nodes in a corosync cluster to avoid split-brain situations. It does this by
  having a **number of votes assigned to each system**」。
- [x] corosync 1.x 的 votequorum 支持共享磁盘投票设备 —— v1.4.4 有
  `man/votequorum_qdisk_register.3` / `votequorum_qdisk_poll.3` /
  `votequorum_qdisk_unregister.3` / `votequorum_qdisk_getinfo.3`；
  `votequorum_qdisk_register(3)` 原文：「A quorum device is an external way
  of adding votes to a small cluster. The quorum device is, in effect, a
  **pseudo node** in the cluster that provide votes based on some external
  device, usually a **shared disk partition** or perhaps a network router.」
- [x] corosync-qdevice 要求 corosync >= 2.0 且依赖 NSS —— qdevice 项目
  README「Dependencies: * Corosync >= 2.0  * NSS」；同 README 说明
  「Originally both qdevice and qnetd were part of the Corosync codebase …
  we decided to split it into its own sub-project.」
- [x] 上游 qdevice 只有 net 一种仲裁模型 —— corosync v2.4.6 的
  `qdevices/Makefile.am` 只列 `qdevice-model-net.c`，
  `man/corosync-qdevice.8`：「The model basically defines what type of
  arbitrator is used. **Currently only net is supported.**」
  corosync-qdevice 上游 master 同样。
- [x] 两个算法的票数前提相反 —— qdevice man page「MODEL NET ALGORITHMS」：
  ffsplit「To use this algorithm it's required to set the number of votes per
  node to 1 (default) and the qdevice number of votes has to be also 1. This
  is achieved by setting **`quorum.device.votes` key in corosync.conf file to
  1**.」；lms「For LMS to work, the number of qdevice votes has to be set to
  **default (so just delete `quorum.device.votes` key from corosync.conf)**.」
- [x] ffsplit 的判定规则与 score 公式 —— 同上节：
  「It provides exactly one vote to the partition with the highest number of
  active nodes. If there are two exactly similar partitions, it provides its
  vote to the partition with higher score. The score is computed as
  (**number_of_connected_nodes + number_of_connected_nodes_with_passed_
  heuristics − number_of_connected_nodes_with_failed_heuristics**). If the
  scores are equal, the vote is provided to partition with the most clients
  connected to the qnetd server. If this number is also equal, then the
  **tie_breaker** is used.」
  lms：「If more than one node can see the qnetd server but some nodes can't
  see each other then the cluster is divided up into 'partitions' based on
  their **ring_id** …」
- [x] `tie_breaker` 与 `keep_active_partition` —— qdevice man page：
  `tie_breaker`「can be one of `lowest`, `highest` or `valid_node_id` (number)
  values. It's used as a fallback if qdevice has to decide between two or
  more equal partitions. … Default is `lowest`.」；
  `keep_active_partition`「… When this option is enabled and tie happens QNetd
  will prefer partition with members of previously active (quorate) partition.
  This is hard-coded behavior of LMS algorithm so this setting affects only
  FFSplit algorithm. Default is `on`.」
- [x] `algorithm` 的全部取值 —— qdevice man page：「Can be one of `ffsplit` or
  `lms`. (actually there are also `test` and `2nodelms`, both of which are
  mainly for developers and shouldn't be used for production clusters).
  **Default value is `ffsplit`.**」→ 原文 L108 的「默认算法」正确 ✅。
- [x] `quorum.device.votes` 的默认值 —— qdevice man page：「The number of
  votes provided to the cluster by qdevice. Default is
  **(number_of_nodes - 1)** or generally sum(votes_per_node) - 1.」
- [x] 配置键的完整路径 —— qdevice man page 里出现的键：
  `quorum.device`（`model`、`timeout`、`sync_timeout`、`votes`、
  `interval`）、`quorum.device.heuristics`（`timeout`、`sync_timeout`、
  `interval`、`mode`）、**`quorum.device.net`**（`tls`、`host`、`port`、
  `algorithm`、`tie_breaker`、`connect_timeout`、`keep_active_partition`）、
  `quorum.device.net.tls`。
  其中 `quorum.device.net.host`「Specifies the IP address or host name of the
  qnetd server to be used. **This parameter is required.**」、
  `quorum.device.net.port` 默认 5403、
  `quorum.device.net.tls` 默认 `on`（`off` 是「the only one which doesn't need
  a properly initialized NSS database」）。
  → 原文 L129 的「device 配置模块」不是上游键名。
- [x] votequorum 的 `two_node` 机制与约束 —— votequorum.5：
  「Enabling two_node: 1, **quorum is set artificially to 1**.」
  「**NOTES: enabling two_node: 1 automatically enables wait_for_all.** It is
  still possible to override wait_for_all by explicitly setting it to 0.
  **If more than 2 nodes join the cluster, the two_node option is
  automatically disabled.**」→ 原文 L128 的后半句与官方一致 ✅。
- [x] votequorum 的 `last_man_standing` 机制 —— votequorum.5：
  「Enables Last Man Standing (LMS) feature (default: 0). Tunable
  `last_man_standing_window` (default: 10 seconds, expressed in ms).」
  「Enabling LMS allows the cluster to **dynamically recalculate
  expected_votes and quorum** under specific circumstances. **It is essential
  to enable WFA when using LMS in High Availability clusters.**」
  官方示例：8 节点 → 3 死 → (expected_votes 8, quorum 5) 仍 quorate →
  窗口超时后重算为 (5, 3) → 再死 2 个 → 再重算为 (3, 2)。
  → 与 qdevice 的 `lms` 算法是**同名不同物**。
- [x] 「qdevice 与 last_man_standing 不兼容」在 qdevice 文档里查不到出处 ——
  在 `man/corosync-qdevice.8` 与 qdevice 的 README 中检索
  `last_man_standing` / `incompatib` **均 0 命中**。
- [x] sysconfig 的安装路径与文件名 —— qdevice `configure.ac`：
  `AC_ARG_WITH([initconfigdir], … [INITCONFIGDIR='${sysconfdir}/sysconfig'])`，
  即默认 `/etc/sysconfig`；
  `init/corosync-qnetd.service.in` 写的是
  `EnvironmentFile=-@INITCONFIGDIR@/corosync-qnetd`——**文件名不带
  `.sysconfig` 后缀**；仓库里的样本文件名为
  `init/corosync-qnetd.sysconfig.example`。
  → 原文 L80 的 `/etc/corosync/qnetd/corosync-qnetd.sysconfig` 与上游不符。
- [x] systemd 单元与 sysusers 片段 —— qdevice `init/` 目录含
  `corosync-qnetd.service.in`（`ExecStart=@QNETDDIR@/corosync-qnetd -f
  $COROSYNC_QNETD_OPTIONS`、`Type=notify`、
  `RuntimeDirectory=corosync-qnetd`、`Restart=on-abnormal`）、
  `corosync-qdevice.service.in`、`corosync-qnetd.in`（sysvinit）、
  `corosync-qnetd.sysusers.conf.example`（内容为
  `u coroqnetd - 'User for corosync-qnetd' - -`）。
- [x] 编译产物清单 —— 与原文 L54-L63 一致 ✅：bin 目录下
  `corosync-qnetd`、`corosync-qnetd-certutil`、`corosync-qnetd-tool`；
  sbin 目录下 `corosync-qdevice`、`corosync-qdevice-net-certutil`、
  `corosync-qdevice-tool`。
- 现场实际使用的 qdevice / corosync / NSS 版本 —— 正文完全空白，
  而 `quorum.device.net.tls` 默认 on、`2nodelms` 等特性与版本相关，需补。
- 现场是否启用了 TLS —— 决定要不要做 NSS 初始化与证书签发，
  正文只字未提，需补。
- 「qdevice 与 votequorum 的 last_man_standing 不兼容」这一判断的依据 ——
  方向上合理（两者都在改票数），但 qdevice 文档里没有这句话；
  若有内部验证或 issue 链接，请补上出处。
- 双节点场景为什么选 ffsplit 而不是 lms —— 原文 L129 直接给了 ffsplit，
  没有给理由；按官方描述，lms 恰好就是「只剩一个节点能看到 qnetd 时给它
  一票」的场景。这条需要作者说明。
- 现场 qnetd 是否与 corosync 环同网段 —— 原文 L111 给了这条建议，
  但没说依据是什么（是 qnetd 的连接对时延敏感？还是别的）。

## 可补的技术证据或产物

- 机制 / 源码入口：qdevice 的仲裁路径在
  `qdevices/qdevice-model-net.c`（model net 的主逻辑）、
  `qdevice-net-algo-ffsplit.c` / `qdevice-net-algo-lms.c`
  （两个算法的打分与投票决策）、`qdevice-net-algo-2nodelms.c`、
  `qnetd-client-msg-received.c`（qnetd 侧收 qdevice 请求并打分）、
  `qdevice-net-cast-vote-timer.c`（投票定时器）。
  文章讲的「谁给谁投票」这套机制，逐条都能对应到这几个文件里的分支。
- 实验或观测：一个**最小可复现实验**——
  (1) 双节点 + qnetd，跑通后停掉一个节点，观察另一个节点是否仍 quorate
  （`corosync-quorumtool -s` 看 Quorum information、
  `corosync-qdevice-tool -s` 看仲裁票）；
  (2) 拔掉仲裁链路（把 qnetd 停掉），观察集群的行为——
  这正好暴露「没有仲裁票时双节点集群立刻失去 quorum」这条边界；
  (3) 把 `quorum.device.votes` 分别设成 1 和默认值各跑一次 ffsplit，
  就能实测出第 2 条里那两个相反的前提。
- 工程取舍：把「双节点集群要不要 qdevice」这件事摊开讲——
  代价：多一个必须高可用的仲裁节点（它自己挂了集群就失去仲裁票）、
  多一套要运维的进程、跨网络的一次往返；
  收益：双节点在挂掉一个之后仍能服务，且**不依赖 two_node 这种
  「人为把 quorum 设成 1」的降级做法**。
  再补上 `two_node` 与 qdevice 的对比：前者把 quorum 人工降成 1，
  脑裂风险由此而来；后者靠独立仲裁方投票，仲裁方本身才是那个单点。
- 结尾清单或下一篇链接：一页「qdevice 部署与排障 checklist」——
  依赖与版本 / qnetd 侧（用户、systemd、TLS、端口）/ corosync.conf 侧
  （model、host、votes、algorithm、tie_breaker）/ 验证命令 /
  典型故障（qnetd 连不上、TLS 失败、票数不对、算法选错）；
  再链到同目录 `corosync qnet挂死场景分析解决.md`、
  `sanlock实现共享corosync共享存储仲裁.md`。

## 已确认的改动

- （本轮只出审校记录，正文改动待确认后执行。）
