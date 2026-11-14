# 审校：corosync down网卡仍处于多数派问题分析（-1 版）

- 原文：`docs/cluster/corosync/corosync-down网卡仍处于多数派-1/index.md`
- 范围：全文
- 目标读者：做同城双中心数据库集群的运维与开发工程师（知道 corosync、
  fence 这些词，但未必读过 corosync 源码）
- 一句话定位：同目录 `corosync-down网卡仍处于多数派/index.md` 的**超集版**——
  多出了 knet 的取舍说明、可执行的绕行方案和内部待办，本篇记录这些增量
  内容的问题
- 核心判断：增量内容的**方向是对的，但那条被当作「POC 紧急方案」写进结论的
  应急做法在 corosync 2.x 上会静默失效**（2.x 没有 knet，写进去会被解析成
  组播 UDP）；同时全文的 PR 链接在站点上**渲染成坏链**——裸 URL 后面的整段
  中文被 marked 吞进了 href
- 审校状态：建议中

> 本篇与 `review/cluster/corosync/corosync-down网卡仍处于多数派.md` 是同一篇
> 文章的两个版本。**正文问题**（PR 685 从未合入、「问题原因」一节写的是
> 期望、缺版本边界、缺复现命令等）以那篇记录为准，本篇只写 `-1` 版**多出来
> 的部分**以及两版都有的**渲染层面问题**。合并口径见「优先修改」第 1 条。

## 优先修改

1. 位置：L48-L58「## 结论」第 2 条（应急方案）
   - 问题：**这条方案在 corosync 2.x 上不生效，而且不报错**。
     corosync 2.x 根本没有 knet——`exec/totemknet.c` 在 v2.4.6 tag 下
     HTTP 404，v2.4.6 的 `man/corosync.conf.5` 里 "knet" 出现 **0 次**，
     它写的是「The default is udp. The transport type can also be set to
     udpu or iba.」；knet 是 **corosync 3 才引入的**（上游 man page：
     「KNET. This is a default and recommended transport introduced in
     Corosync 3」）。
     更糟的是解析行为：v2.4.6 的 `exec/totemconfig.c` 里
     `totem_config->transport_number = TOTEM_TRANSPORT_UDP;` 之后**只对
     `"udpu"` 和 `"iba"` 覆盖**，没有第三分支、也没有任何报错。
     所以在 2.x 上把 `transport: knet` 写进配置，corosync 会**静默落回
     组播 UDP**——集群从单播 UDPU 变成组播 UDP，既不生效、也没人收到告警。
     对比 v3.0.0 的同一段：默认值就是 `TOTEM_TRANSPORT_KNET`，并显式识别
     `udpu` / `udp` / `knet` 三个取值。
   - 建议：把这条改成有前置条件的版本——「**前提是 corosync 3.x**（2.x 无
     knet，写了也不生效且会静默退化成组播 UDP）」，并补上三条切换前提：
     1. 先确认二进制带 knet：`corosync -v` 看 Built-in features
        （上游 man page：「Legacy unencrypted transports are available only
        for udpu builds; run `corosync -v` and check for "udpu" under
        "Built-in features"」）；
     2. `nodelist` 里**每个节点都要有 `nodeid`**——上游 man page：
        「nodeid … This configuration option is required for each node for
        Kronosnet mode … If KNET is set, this field must be set.」；
     3. knet 才支持加密，`secauth` 默认开启、密钥在
        `/etc/corosync/authkey`，从 udpu 切过来要一并准备。
     真正适用于 2.x 的应急做法是**合入上游修复**（`8b638e98`，见
     「事实待核」），而不是换传输层。
   - 原因：这是全文唯一一条读者会照着做的操作指引，写错的后果是
     「以为绕过了问题，实际把集群换成了另一种传输层」。README 的
     「用证据建立技术感」「工程取舍」都要求给依据和适用边界。

2. 位置：L18、L22（两处 PR 链接）
   - 问题：**这两条链接在站点上是坏链**。原文把 URL 直接裸露在句子里，
     后面紧跟中文。marked 的 GFM autolink 规则会从 `https://` 一直吃到
     下一个空白字符为止，中文没有空格，于是**整段中文被当成了链接的一部分**。
     用站点实际的渲染链实测（marked 15.0.12 + hexo-renderer-marked 7.0.1
     的 tokenizer + 站点 `_config.yml` 的 marked 选项），L18 渲染出来是：
     ```html
     <p>这个问题是corosync的已知问题，社区在这个补丁里对这个问题进行了修复，<a
     href="https://github.com/corosync/corosync/pull/685%EF%BC%8C%E6%88%91...%E3%80%82">
     https://github.com/corosync/corosync/pull/685，我们的corosync没合入这个补丁。…建议使用knet。</a></p>
     ```
     链接文字是整段话，href 是百分号编码的一长串。读者点进去是一个
     **不存在的 PR 地址**（何况 685 本身就从未合并）。
     全树共 **15 篇 / 30 处**中招（`docs/network/【网络】MTU相关网络丢包问题分析处理.md`
     7 处、`docs/tools/clash-meta-mihomo-install-guide.md` 5 处、
     `docs/tools/clash-meta-user-guide.md` 4 处最集中）。
   - 建议：把 URL 写成 markdown 链接并单独成段，或用行内代码包住：
     `[PR 686](https://github.com/corosync/corosync/pull/686)`。
     注意 URL 后面**必须跟空白或换行**，否则仍会被吞。
     这条值得同时提给站长：全树 30 处是同一个成因，适合一次性修掉，
     也可以给检查器加一条规则（但信号不该变成门禁）。
   - 原因：涉及链接与事实，必须可回溯；而且读者点不开的「证据」等于没有证据。

3. 位置：L18、L22
   - 问题：两处都写「社区在这个补丁里对这个问题进行了修复」并给出
     `https://github.com/corosync/corosync/pull/685`。**PR 685 从未合并**
     ——作者 epenchev 2021-11-22 自行关闭（`merged=false`、
     `merged_at=null`）。真正落地的是 **PR 686**，以 commit
     `8b638e989c391860d0e0f8bcd83fed1ac0b50992` 于 2021-11-24 进入上游，
     并 backport 为 `5d625cefe820c71d14ec851fc6bb5fd640515d89`。
   - 建议：两处都改成 PR 686 / commit `8b638e98`，并加一句
     「PR 685 是被放弃的方案，作者已撤回」。
   - 原因：全篇最硬的一处错，读者照着 685 去找补丁会直接落空。
     （该结论与同目录另一篇的记录一致，已逐项复核。）

4. 位置：L48-L50（`<font color="red">` 标签）
   - 问题：**`<font color="red">` 把结论的两个编号吃成了普通段落**。
     原文是 `<font color="red">1. 后续会将…；` 换行 `2. 若现场poc…，</font>找到如下内容：`
     ——开标签在列表项**之前**，所以行首不是 `1.`，marked 根本不把它当有序列表。
     实测渲染结果是：
     ```html
     <p><font color="red">1. 后续会将corosync通信方式从udpu更改为knet，并进行测试验证；<br>2. 若现场poc测试比较紧急的话，可以修改V8R6_cluster_install.sh文件，</font>找到如下内容：</p>
     ```
     两条结论变成一个段落里的裸文本编号（不是 `<ol>`），而且 `</font>`
     落在句子中间，把红色范围切在了「…文件，」后面，「找到如下内容：」
     掉出了红色。
   - 建议：去掉 `<font>`，让 Markdown 自己渲染列表；要强调就用
     `**加粗**`。顺带一提，仓库里有 38 篇用了 `<font color=...>`，
     不是孤例，但用在这里包住一个编号列表是错的。
   - 原因：README 的「保留人的声音」不反对强调，但强调不该以破坏列表结构
     为代价；读者看到的是塌成一段的「1.…2.…」。

5. 位置：L28（250 字一整段，检查器 AIF-03 命中）
   - 问题：一段里塞了四件事——knet 是默认方式、引用了 2017 年的演讲、
     「原来的通信方式只用于兼容」、「之前不用 knet 是因为测试环境发现 knet
     会广播」以及两点澄清。250 字一个自然段，读者抓不住主干。
   - 建议：拆成三段，并补上依据与限定：
     - 「knet 是 corosync 3 的默认传输层」——上游 man page 原文
       「Corosync uses KNET as the standard network transport for
       communication between nodes in the cluster」，
       且 udpu/udp 已被上游标为 deprecated / highly discouraged；
     - 「knet 的传输层默认 udp，支持 sctp」——上游 man page
       `knet_transport`：「valid values are "udp" (or "sctp" if supported by
       the installed version of kronosnet). (default: udp)」，
       但要补一句「**sctp 已弃用**，上游注明将在 kronosnet v2.0 移除」；
     - 「knet 会广播」这个观察**在配置语义上没有依据**——`link_mode`
       只有 passive / active / rr 三个取值，**没有 broadcast**；
       v3.0.0 的 `exec/totemconfig.c` 里默认值是
       `strcpy (totem_config->link_mode, "passive")`，
       man page 也写「If only one interface directive is specified,
       passive is automatically chosen」。原文自己已经说明这是虚拟机抓包
       环境造成的，把这个澄清单独写成一两句更清楚。
   - 原因：README 的「让抽象话落地」与「工程取舍」；检查器 AIF-03 命中。

6. 位置：L31（`clusterware MDE应关注…`）
   - 问题：这是**内部待办**，而且三个词对读者都是黑话——「clusterware MDE」
     是什么、「ES」指什么、「产出加入产品规划流程」是哪个流程，读者一样都
     不知道。这句话还挂在第 4 条「后续持续跟踪corosync社区的代码，并及时
     跟进更新；」后面（上一条以分号结尾），句子结构是断的。
   - 建议：移出正文。已经定下来的写成结论（「我们把 corosync 3.x + knet
     作为目标版本，并持续跟踪上游社区版本」），还没定的留在内部文档。
   - 原因：README 的「按读者的阅读路径组织」：对外文章不该出现待办；
     读者看到「待办」只会怀疑这套方案还没想清楚。

7. 位置：L44（`相关测试MDE也需要确认下…`）
   - 问题：同样是内部待办，而且和 L35-L42 那张「应增加如下测试场景」的
     清单重复——清单本身已经是结论，后面这句是又一句「要去确认」。
   - 建议：删掉，或改成清单的一句话总结（例如「这四种注入方式的期望
     结果各不相同，验收时逐条对照」）。
   - 原因：README 的「小步可审」「信息重复」。

8. 位置：L18、L22（内容完全重复）
   - 问题：两段**一字不差**（检查器 AIF-05 相似度 1.00，报了 2 对）。
     「问题原因」和「问题解决」两个 H2 下面装的是同一段话。
   - 建议：合并成一节「问题原因与上游修复」；或者让两节各司其职——
     「问题原因」讲成因链（`96354fb` → `c652ee0` → `8b638e98`），
     「问题解决」只讲自己怎么落地。
   - 原因：重复段会让读者误以为是两处独立的佐证。

9. 位置：L9
   - 问题：写了「使用如下命令down掉网卡」，**但全文没有任何命令**；
     紧接着的「格一段时间后查看节点的quorate状态」也没说是多久。
   - 建议：补上注入与观测命令——注入用 `ip link set eth0 down`
     （或现场实际的 `ifdown eth0`），观测用 `corosync-quorumtool -s`
     与 `corosync-cfgtool -s`；「隔一段时间」换成具体秒数，并说明它由
     `corosync.conf` 的 totem 超时参数决定。
   - 原因：README 的「可复现证据」。

10. 位置：L5、L28
    - 问题：没有版本边界。原文只说「corosync三节点集群，未启用vote_quorum，
      没有qdevice进程」「通信方式为udpu」，没写 corosync 版本。
      而这一版恰恰**特别需要版本**——knet 存不存在、结论那条应急方案能不能用，
      全部取决于版本线。
    - 建议：补上「本文针对 corosync 2.4.x + udpu」这类边界，
      并注明上游修复 commit `8b638e98` 覆盖到 v2.4.6 / v3.1.7 / v3.1.10 /
      v3.2.0，corosync 3 起默认 knet。
    - 原因：README 的「问题边界」。

11. 位置：L9
    - 问题：「实际上网络不通应处于非quorate状态」缺主体限定。三节点集群
      down 掉一张网卡后，**剩下两个节点仍然满足多数派、仍应是 quorate**；
      该变成非 quorate 的是**被 down 的那台自己**。读者容易读反方向。
    - 建议：把主体写清楚：「被隔离的这台应当转为非 quorate，集群其余节点
      仍保有多数派、仍为 quorate，但应把该节点视为 offline」。
    - 原因：涉及技术结论，方向反了会导致误操作。

12. 位置：L12（fence 与脑裂双主）
    - 问题：220 字一整段（检查器 AIF-03），把 fence 依赖 quorate → 20 秒
      阈值 → 本中心失联但未停库 → observer 触发跨中心切换 → 网络恢复 →
      双主整条链塞在一段里；另外「会触发observer执行跨中心切换」缺主语
      （是「本中心失联」触发，不是「网卡 down」触发），「网路恢复」是错字。
    - 建议：拆成时序列表，每步写清发生在哪一侧；补一句这 20 秒的来由——
      它必须**慢于** corosync 判定自己失联所需的时间（上游默认值：
      token 3000ms，且 `token_coefficient` 默认 650ms、在 nodelist 有 3 个
      以上节点时真实 token 超时 = token + (节点数-2) × coefficient，
      三节点约 3650ms；现场配置不同，需以自己的 `corosync.conf` 为准）。
    - 原因：README 的「机制解释」与「踩坑与校验」。

13. 位置：L12、L9、L27
    - 问题：三处错别字：「生成中心」应为「**本**中心」；L9「格一段时间」
      应为「**隔**一段时间」；L27「给出选择那种通信方式」应为「哪**种**」。
      另 L12「网路恢复」应为「网络恢复」。
    - 建议：逐处改正。
    - 原因：基础校对；「本中心」这处还是关键信息。

14. 位置：L14-L18「## 问题原因」整节
    - 问题：这一节写的不是原因，是**期望**——L16「在down掉网卡时，节点的
      quorate状态应改变为非quorate」是「应该怎样」，不是「为什么现在不是
      这样」。`-1` 版也没有补上成因链。
    - 建议：按上游讨论补上真正的因果链，每一步都能落到提交上：
      `96354fba72b7e7065610f37df0c0547b1e93ad51`（2018-07-12，
      totemudpu: Add local loop support，自称是为解决长期存在的 ifdown 问题）
      → `c652ee0df8c1971cf9347c69d7ff3d78505dc9e9`（2019-05-29，
      udpu: Drop packets from unlisted IPs）→ 修复 `8b638e98`（+1/-0，
      只在 `BIND_STATE_REGULAR` 时才丢弃未列出 IP 的包）。
      配置面还有一个现成的开关：`block_unlisted_ips`（默认 yes）——
      上游 man page：「Allow UDPU and KNET to drop packets from IP addresses
      that are not known … The default value is yes.」
    - 原因：README 的「机制解释」——这是本文该给读者的核心价值。

15. 位置：L1 开头 / L58 结尾
    - 问题：开头没有一句话定位（检查器 STR-02 命中）；结尾停在
      「这样部署的集群可以规避该问题。」——**这句话本身也是错的**
      （在 2.x 上规避不了，见第 1 条），且没有可带走的产物、没有指向
      同目录的相关文章。
    - 建议：开头补定位与编写信息（检查器 MET-01 命中）；结尾改成
      「故障注入方式 → 期望 quorum 状态 → 判定命令」的一张表，
      再链到同目录的 `totem协议详解.md`、`corosync qnet挂死场景分析解决.md`、
      `corosync-qdevice使用.md`。
    - 原因：README 的「一句话定位」「一份可带走的产物」「一条自然的内容路径」。

16. 位置：与 `docs/cluster/corosync/corosync-down网卡仍处于多数派/index.md` 的关系
    - 问题：`-1` 版是那一篇的**超集**——多了 knet 的取舍说明、
      `## 结论` 一节和可执行的绕行方案，以及 L31 / L44 两句内部待办。
      两篇 H1 标题完全相同，站点上会出现两篇几乎一样的文章。
    - 建议：合并成一篇——以 `-1` 版的结构为骨架（它多出来的结论节是全文
      唯一有「产物」的部分），把原版独有的内容（现象链条、fence 与脑裂双主
      的因果）并进去，删除 `-1` 目录。具体怎么处理由站长定，但两篇同标题
      并存是必须解决的。**注意合并时要一起修掉第 1 条的 transport 误用**——
      那是 `-1` 版独有的内容，也是更危险的一半。
    - 原因：README 的「结构跳跃」与「信息重复」。

## 事实待核

- [x] PR 685 的最终状态 —— GitHub API `pulls/685`：`state=closed`、
  `merged=false`、`merged_at=null`、`closed_at=2021-11-22T16:36:47Z`。
  作者 epenchev 关闭时留言「Closing this PR then.」，理由是 PR 686 已验证有效。
- [x] 真正合入上游的修复 —— PR 686「totemudpu: Don't block local socketpair」，
  作者 Jan Friesse (jfriesse)，2021-11-22 提交，2021-11-24 以 commit
  `8b638e989c391860d0e0f8bcd83fed1ac0b50992` 直接提交进上游
  （backport `5d625cefe820c71d14ec851fc6bb5fd640515d89`），
  改动是 `exec/totemudpu.c` **+1/-0**。
- [x] 修复覆盖的版本 —— `compare/8b638e98...<tag>` 对 v2.4.6、v3.1.7、
  v3.1.10、v3.2.0 均返回 200（该 commit 是这些 tag 的祖先）；
  v2.4.6 是 corosync 2.x 最后一个 release（2022-11-09），
  v3.2.0 是当前最新（2026-10-27）。
- [x] **knet 是 corosync 3 才有的** —— `exec/totemknet.c` 在 v2.4.6 下
  HTTP **404**，在 v3.0.0 / v3.2.0 / `main` 下均 HTTP 200；v2.4.6 的
  `man/corosync.conf.5` 中 "knet" 出现 **0 次**，其 transport 段写的是
  「The default is udp. The transport type can also be set to udpu or iba.」；
  `main` 的 man page 写「KNET. This is a default and recommended transport
  introduced in Corosync 3」。
- [x] **在 corosync 2.4.6 上写 `transport: knet` 会静默退化成组播 UDP** ——
  `exec/totemconfig.c`（v2.4.6）：`totem_config->transport_number =
  TOTEM_TRANSPORT_UDP;` 之后只对 `strcmp(str,"udpu")==0` 与
  `strcmp(str,"iba")==0` 覆盖，没有第三个分支、不报错；
  v3.0.0 同一段默认 `TOTEM_TRANSPORT_KNET` 并显式识别 `udpu`/`udp`/`knet`。
- [x] 上游对 udpu / udp 的定性 —— `main` 的 `man/corosync.conf.5`：
  「UDPU. This is for unicast communication. This transport is deprecated.」
  「UDP. This is for multicast communication. This transport is deprecated
  and highly discouraged to use.」；同页说明 legacy 非加密传输层
  「available only for udpu builds; run `corosync -v` and check for "udpu"
  under "Built-in features"」。
- [x] knet 的传输层与 link_mode —— 同页 `knet_transport`：
  「valid values are "udp" (or "sctp" if supported by the installed version of
  kronosnet). (default: udp)」，并注明
  「NOTE: even if currently included, sctp is deprecated and will be removed
  in kronoset v2.0」；`link_mode` 只有 passive / active / rr 三个取值，
  v3.0.0 `exec/totemconfig.c` 里默认值为 `strcpy(totem_config->link_mode,
  "passive")`，man page 另写「If only one interface directive is specified,
  passive is automatically chosen」——**没有 broadcast 模式**。
- [x] 切到 knet 的配置前提 —— `main` man page：`nodeid`「This configuration
  option is required for each node for Kronosnet mode … If KNET is set,
  this field must be set.」；「Only KNET allows crypto or multiple interfaces
  per node.」；加密相关项 `secauth`（默认 on）、`crypto_cipher`（默认 aes256）、
  `crypto_hash`（默认 sha256）、`keyfile`（默认 `/etc/corosync/authkey`），
  且「Encrypted transmission is only supported for the KNET transport」。
- [x] 《2017-Kronosnet-The-new-face-of-corosync-communications》确有出处 ——
  是 **Christine Caulfield** 在 Clusterlabs Summit 2017 的演讲
  （corosync 官方 wiki 的 Presentations 页收录为「Kronosnet - The new face
  of corosync communications」）；原始 PDF 地址
  `http://build.clusterlabs.org/corosync/presentations/2017-Kronosnet-The-new-face-of-corosync-communications.pdf`
  在 corosync 3.0.0 的发布邮件里被引用。演讲 slides 里列的是
  「UDP (unicast) / SCTP / Loopback」「No multicast, but could be added if
  really wanted」「**No broadcast**」——与「knet 会广播」的观察矛盾。
- [x] 上游对 ifdown 这种测法的定性 —— corosync 3.0.0 发布说明：
  「many people beloved way to test node split - ifdown - now finally works
  with Knet transport. UDPU transport was also partly fixed. Please keep in
  mind this method of testing is still **not supported nor recommended**.」
  原文「knet 方式不会」只说对了一半，限定条件要一并写进去。
- [x] `block_unlisted_ips` 就是这次缺陷的配置面开关 —— `main` man page：
  「Allow UDPU and KNET to drop packets from IP addresses that are not known
  (nodes which don't exist in the nodelist) to corosync. … The default value
  is yes.」；对应 `c652ee0`（udpu: Drop packets from unlisted IPs），
  而修复 `8b638e98` 就是让这条丢弃逻辑在本地 socketpair 场景下不生效。
- [x] 站点渲染链下裸 URL 吞中文 —— 实测（marked 15.0.12、
  hexo-renderer-marked 7.0.1 的 tokenizer、`_config.yml` 的 marked 选项：
  `gfm/breaks/smartLists/smartypants/headerIds` 全开、`autolink` 默认 true、
  `dompurify` 未开）：以 `https://` 开头的裸 URL 会吃掉直到下一个空白为止的
  所有字符。L18、L22 渲染出的 href 里含
  `%EF%BC%8C%E6%88%91%E4%BB%AC%E7%9A%84corosync…%E3%80%82`，
  即整段中文；L49 的 `</font>` 也因此落在句中。
- [x] 全树同类问题的规模 —— 按上述规则逐行扫描 `docs/`（排除代码块、
  行内代码与 markdown 链接）：**15 篇 / 30 处**，分布为
  `docs/network/【网络】MTU相关网络丢包问题分析处理.md` 7 处、
  `docs/tools/clash-meta-mihomo-install-guide.md` 5 处、
  `docs/tools/clash-meta-user-guide.md` 4 处、
  `docs/cluster/corosync/corosync-down网卡仍处于多数派/index.md` 与
  `-1/index.md` 各 2 处，其余 9 篇各 1 处。
- [x] `## 结论` 段不是有序列表 —— 实测渲染结果为
  `<p><font color="red">1. …；<br>2. …，</font>找到如下内容：</p>`，
  行首因 `<font>` 开标签而不再是 `1.`，marked 不生成 `<ol>`。
- 本次现场所用的 corosync 版本与发行版打包版本 —— 仓库里查不到，
  需作者补充；这一条尤其要紧，因为第 1 条的判断完全取决于版本线。
- `V8R6_cluster_install.sh` —— 仓库里没有这个脚本，L49 给出的改法
  （`transport: udpu` → `transport: knet`）需作者确认脚本路径与内容。
- 未启用 vote_quorum 与本现象的因果关系 —— 三节点集群下被 down 的那台在
  未启用 votequorum 时，quorum 由 totem 环的形成员关系判定，因而察觉不到
  自身失联；启用 votequorum 后是否必然转为非 quorate，需查 `exec/votequorum.c`
  与 votequorum(5) 后再写进正文，暂不下结论。
- fence 的 20 秒阈值与现场 corosync 收敛时间的关系 —— 需该集群的
  `corosync.conf`（token、token_coefficient、downcheck、consensus）
  与 fence 脚本才能判定 20 秒是否留了足够余量。上游默认值已记录在
  「事实待核」的对应条目里，但不能替代现场配置。
- 「clusterware MDE」「ES」这两个词的确切所指 —— 正文未解释，
  需作者确认后再决定是补一句说明还是整句删掉。
- 「knet 会做广播」这个观察的原始记录 —— 正文说已验证为虚拟机抓包环境
  所致，但没给验证方式（抓包位置、过滤条件）；若要保留这段澄清，
  建议补上验证方法，否则读者只能当结论看。

## 可补的技术证据或产物

- 机制 / 源码入口：`exec/totemudpu.c` 的 `timer_function_netif_check_timeout()`、
  `totemudpu_build_sockets()`，以及 `BIND_STATE_UNBOUND / LOOPBACK / REGULAR`
  三态如何决定「网卡 down 时继续假装旧 IP 存在」；配合 `exec/totemip.c` 的
  `totemip_get_interface_address()`。knet 侧对应 `exec/totemknet.c`
  （corosync 3 才有），它走的是另一套链路检测路径——两者的差别
  就是本文最该讲清的一点。
- 实验或观测：注入用 `ip link set eth0 down` 或现场实际的 `ifdown eth0`；
  观测用 `corosync-quorumtool -s` 与 `-m`、`corosync-cfgtool -s`。
  判定标准要写清楚：被隔离的那台应为非 quorate，集群其余节点应把它
  视为 offline。
- 工程取舍：udpu → knet 的迁移成本与风险要写全——`transport:` 切换、
  `nodelist` 补 `nodeid`（knet 必填）、加密与 `authkey`、
  `link_mode` 的默认值是 passive、`knet_mtu` 自动发现、
  以及 udpu 所在 corosync 2.x 已 EOL（最后一版 v2.4.6）这个背景。
- 结尾清单或下一篇链接：结尾给一张「故障注入方式 → 期望 quorum 状态 →
  判定命令」的表——这张表同时是测试用例和读者排查时能直接用的清单；
  再链到同目录 `totem协议详解.md`、`corosync qnet挂死场景分析解决.md`、
  `corosync-qdevice使用.md`。

## 已确认的改动

- （本轮只出审校记录，正文改动待确认后执行。）
