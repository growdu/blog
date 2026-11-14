# 审校：corosync down网卡仍处于多数派问题分析

- 原文：`docs/cluster/corosync/corosync-down网卡仍处于多数派/index.md`
- 范围：全文
- 目标读者：做同城双中心数据库集群的运维与开发工程师（知道 corosync、
  SBD、fence 这些词，但未必读过 corosync 源码）
- 一句话定位：一个 udpu 集群 down 掉网卡后 corosync 仍自报 quorate，
  连带触发跨中心脑裂双主——本文记录现象、上游缺陷与社区修复
- 核心判断：现象描述属实、上游确实有对应修复，但**引用的 PR 685 从未合入**
  （真正落地的是 PR 686 / commit `8b638e98`）；「问题原因」一节写的不是原因
  而是期望，全文没有版本边界、没有一条可复现命令
- 审校状态：已合入

> 本篇已与 `review/cluster/corosync/corosync-down网卡仍处于多数派-1.md`
> 合并（同目录的 `-1` 版是本篇的超集）。合并口径：正文留在本篇的路径
> （`docs/cluster/corosync/corosync-down网卡仍处于多数派/index.md`），
> `-1` 版独有的 knet 取舍说明与 `## 结论` 应急方案并入本篇，
> `-1` 的 docs 目录、审校记录与索引行一并删除；`-1` 记录独有的待核事实
> 与结论已搬进本篇的「事实待核」，核证工作没有丢。

## 优先修改

1. 位置：L18、L22
   - 问题：两处都写「社区在这个补丁里对这个问题进行了修复」并给出
     `https://github.com/corosync/corosync/pull/685`。**PR 685 从未合并**——
     它由 epenchev 于 2021-11-17 提交，2021-11-22 被作者自己关闭
     （`merged=false`、`merged_at=null`、`mergeable_state=dirty`）。
     作者关闭时留言说他已验证 PR 686 有效，于是关掉了 685。
     真正进入上游的是 **PR 686**（jfriesse，2021-11-22），
     以 commit `8b638e989c391860d0e0f8bcd83fed1ac0b50992` 于 2021-11-24
     直接提交进 master，并 backport 为 `5d625cefe820c71d14ec851fc6bb5fd640515d89`。
   - 建议：两处链接都换成 PR 686 与 commit `8b638e98`，并加一句
     「PR 685 是被放弃的方案，作者已撤回，按它去 cherry-pick 会白忙」。
     既然正文还要说「我们的 corosync 没合入这个补丁」，那就更不能指错补丁。
   - 原因：涉及引用与事实，必须可回溯。这是全篇最硬的一处错——
     读者照着 685 去找补丁会直接落空。

2. 位置：L14-L18「## 问题原因」整节
   - 问题：这一节写的不是原因，是**期望**。L16「在down掉网卡时，节点的quorate
     状态应改变为非quorate」——「应该怎样」不是「为什么现在不是这样」。
     全文没有回答「为什么 down 掉网卡后 corosync 还认为自己健康」。
   - 建议：按上游讨论补上真正的因果链，每一步都能落到提交上：
     - 2018-07-12 `96354fba72b7e7065610f37df0c0547b1e93ad51`
       「totemudpu: Add local loop support」——提交说明自称就是为了解决
       长期存在的 ifdown 问题，做法是网卡 down 时改用本地 socketpair 收发，
       并「继续假装旧 IP 仍然存在」；
     - 2019-05-29 `c652ee0df8c1971cf9347c69d7ff3d78505dc9e9`
       「udpu: Drop packets from unlisted IPs」——加了「丢弃来自未列出 IP 的包」，
       而 socketpair 没有 `msg_name`，这条丢弃逻辑把本地 socketpair 的包
       也丢了，ifdown 场景就此走不通（这是上游维护者 jfriesse 的归因）；
     - 修复 `8b638e98` 只有一行：只在 `BIND_STATE_REGULAR` 时才丢弃
       未列出 IP 的包。
     同时点明源码入口：`exec/totemudpu.c` 的
     `timer_function_netif_check_timeout()` 与 `BIND_STATE_UNBOUND/LOOPBACK/REGULAR`
     三态。
   - 原因：README 的「机制解释」与「用证据建立技术感」。这是本文该给读者的
     核心价值，现在这一节等于没写。

3. 位置：L18、L22
   - 问题：两段**一字不差**（检查器 AIF-05 相似度 1.00）。「问题原因」和
     「问题解决」两个 H2 下面装的是同一段话。
   - 建议：合并成一节「问题原因与上游修复」，或者让两节各司其职——
     「问题原因」讲成因链（见第 2 条），「问题解决」只讲自己怎么落地
     （合入哪个补丁、为什么不直接上 knet）。
   - 原因：重复不是「讲清楚」，是「没讲」；重复段还会让读者误以为是两处
     独立的佐证。

4. 位置：L9
   - 问题：写了「使用如下命令down掉网卡」，**但全文没有任何命令**。
     L9 的「如下命令」后面直接接的是 L11 的 fence 描述，读者找不到命令；
     紧接着的「格一段时间后查看节点的quorate状态」也没说是多久。
   - 建议：补上实际执行的注入命令与观测命令，例如注入用
     `ip link set eth0 down`（或现场实际用的 `ifdown eth0`），
     观测用 `corosync-quorumtool -s`（看 Quorum information）与
     `corosync-cfgtool -s`（看 Ring ID / membership）；
     「隔一段时间」换成具体的收敛时间，并说明它由 `corosync.conf` 里的
     totem 超时参数决定。
   - 原因：README 的「可复现证据」。上游 PR 685 的评论里已经给出了完整
     复现步骤（`ip link set eth0 down` 与 iptables REJECT 两种注入），
     直接引用即可。

5. 位置：L5
   - 问题：没有版本边界。原文只说「corosync三节点集群，未启用vote_quorum，
     没有qdevice进程」，没写 corosync 版本、分支和传输层以外的关键配置，
     读者无法判断自己的环境是否受影响。
   - 建议：补上「本文针对 corosync 2.4.x + udpu」这类边界，并注明
     修复 commit `8b638e98` 覆盖到的版本线（v2.4.6、v3.1.7、v3.1.10、v3.2.0
     都已包含），以及 corosync 3 起默认走 knet 可规避该问题。
   - 原因：README 的「问题边界」。核不到具体版本时至少写清楚「哪条版本线
     上有这个问题」。

6. 位置：L9
   - 问题：「实际上网络不通应处于非quorate状态」缺主体限定。三节点集群
     down 掉一张网卡后，**剩下两个节点仍然满足多数派，仍应是 quorate**；
     该变成非 quorate 的是**被 down 的那台自己**。原文这么写，读者容易
     读成「集群应该失去 quorum」——而那恰恰是错的方向，照着做反而会误停库。
   - 建议：把主体写清楚：「被隔离的这台应当转为非 quorate，集群其余节点
     仍保有多数派、仍为 quorate，但应把该节点视为 offline」。
   - 原因：涉及技术结论，且方向反了会导致误操作。这是全文风险最高的一处
     表述含糊。

7. 位置：L11-L12（fence 与脑裂双主）
   - 问题：220 字一整段（检查器 AIF-03），把整条脑裂成因链塞在一段里：
     fence 依赖 quorate → 20 秒阈值 → 本中心失联但未停库 → observer 触发
     跨中心切换 → 网络恢复 → 双主。读者分不清哪一步发生在本中心、哪一步
     发生在灾备中心。另外「非quorate 状态超过20秒才停库」这个关键参数
     没解释来由。
   - 建议：拆成三段或改成时序列表，并补一句这 20 秒的来由——它必须**慢于**
     corosync 判定自己失联所需的时间，否则会把正常的网络抖动误判成故障；
     再补上「本中心失联为什么会导致灾备中心切主」这一环（observer 的
     跨中心切换条件），这是读者最想弄明白的地方。
   - 原因：README 的「踩坑与校验」；检查器 AIF-03 与 DEP-04 都命中这一段。

8. 位置：L24-L30「### 对于开发来说」
   - 问题：内部待办清单混进了对外文章。第 2 条「输出分析文档，给出选择
     那种通信方式」是**还没做的决定**（连「哪种」都写错了），第 3、4 条是
     常规流程跟踪，第 4 条末尾还留了个分号。第 1 条「合入社区相关补丁代码」
     与上一节的结论重复。
   - 建议：把已经定的写成结论（合入 `8b638e98`、为什么选 knet），
     把还没定的移出正文——待办属于内部文档，读者看到「待办」只会怀疑
     这套方案还没想清楚。
   - 原因：README 的「按读者的阅读路径组织」：先说明问题、背景和结论。

9. 位置：L31-L40「### 对于测试来说」
   - 问题：同样是对内的工作安排。而且 L39-L40 列的「开防火墙 / 停网卡服务 /
     ifdown网卡 / 拔网线」其实是**四种不同的故障注入方式**，原文既没说这是
     四种方式，也没写每种方式的期望结果是什么（停网卡服务与 ifdown 的
     语义差别很大，前者 corosync 未必感知得到）。
   - 建议：改成一张表：注入方式 → 期望的 quorum 状态 → 判定命令 → 备注。
     这张表既能当测试用例，也是文章结尾最该给的「可带走的产物」。
   - 原因：README 的「一份可带走的产物」；检查器 STR-03 命中（结尾没有产物）。

10. 位置：L12、L9、L27
    - 问题：三处错别字：「生成中心」应为「**本**中心」（讲脑裂双主的那一段，
      「生成中心的主库未停止」语义不通）；L9「格一段时间」应为「**隔**一段时间」；
      L27「给出选择那种通信方式」应为「哪**种**」。
    - 建议：逐处改正。
    - 原因：基础校对；「本中心」这处还是关键信息，写错会误导读者。

11. 位置：L1 开头 / 全文结尾
    - 问题：开头没有一句话定位，也没有说明本文替读者解决什么（检查器 STR-02）；
      结尾停在「4. 拔网线；」，没有可带走的产物，也没有指向同目录的相关文章
      （检查器 STR-03）。
    - 建议：开头补定位与编写信息；结尾给「故障注入方式 → 期望 quorum 状态 →
      判定命令」清单，再链到同目录的 `totem协议详解.md`、
      `corosync qnet挂死场景分析解决.md`、`corosync-qdevice使用.md`。
    - 原因：README 的「一句话定位」「一份可带走的产物」「一条自然的内容路径」。

12. 位置：与 `docs/cluster/corosync/corosync-down网卡仍处于多数派-1/index.md` 的关系
    - 问题：同目录下 `-1` 版是本篇的**超集**——它多了 knet 的取舍说明
      （「knet 目前传输层默认用 udp 单播，也支持 sctp」、测试环境观察到广播
      实为虚拟机抓包环境问题）、`## 结论` 一节，以及可执行的绕行方案
      （把 `V8R6_cluster_install.sh` 里的 `transport: udpu` 改成
      `transport: knet`）。两篇标题完全相同、内容高度重叠，站点上会出现
      两篇几乎一样的文章。
    - 建议：合并成一篇——以 `-1` 版的结构为骨架，把本篇独有的内容
      （现象链条、fence 与脑裂双主的因果）并进去，删除 `-1` 目录。
      具体怎么处理由站长定，但两篇同标题并存是必须解决的。
    - 原因：README 的「结构跳跃」与「重复」；站点上重复内容对读者是负担。
    - 本轮处置：按本条执行——正文留在本篇路径，`-1` 的增量并入，
      `-1` 的 docs 目录、审校记录与索引行删除。`-1` 记录独有的待核事实
      已搬到本篇的「事实待核」。

13. 位置：L18、L22（结论「建议使用knet」的依据）
    - 问题：只说「建议使用knet」，没给依据，也没给限定。
    - 建议：补上上游维护者 jfriesse 的原话依据——corosync 3 里 knet 是
      「default, recommended and only supported transport（udpu/udp 只保留
      给调试用）」；2021-11-22 他又说「only real solution is to use knet,
      because udpu ifdown handling is not perfect (**but usually works**)」。
      这句限定要一并写进去，别把结论写成「udpu 一律不可用」。
    - 原因：README 的「工程取舍」——结论要给依据，也要给适用边界。

## 事实待核

- [x] PR 685 的最终状态 —— GitHub API `pulls/685`：`state=closed`、
  `merged=false`、`merged_at=null`、`closed_at=2021-11-22T16:36:47Z`、
  `mergeable_state=dirty`、改动 `exec/totemudpu.c` +16/-57。
  作者 epenchev 关闭时留言「Closing this PR then.」，理由是 PR 686 已验证有效。
- [x] 真正合入上游的修复 —— PR 686「totemudpu: Don't block local socketpair」，
  作者 Jan Friesse (jfriesse)，2021-11-22 提交，2021-11-24 以 commit
  `8b638e989c391860d0e0f8bcd83fed1ac0b50992` 直接提交进 master
  （backport `5d625cefe820c71d14ec851fc6bb5fd640515d89`），
  改动是 `exec/totemudpu.c` **+1/-0**——只在 `BIND_STATE_REGULAR` 时才
  丢弃未列出 IP 的包。
- [x] 修复覆盖的版本 —— `compare/8b638e98...<tag>` 对 v2.4.6、v3.1.7、
  v3.1.10、v3.2.0 均返回 200（该 commit 是这些 tag 的祖先）；对 `main`
  返回 `status=ahead, behind_by=0`（是 `main` 的祖先）。v2.4.6 是 corosync 2.x
  的最后一个 release（2022-11-09），v3.2.0 是当前最新（2026-10-27）。
- [x] knet 在 corosync 3 中的地位 —— jfriesse 2021-11-18 在 PR 685 下原话：
  「udpu is known to not handle these situations well. That's the reason why
  corosync 3 added knet, and that is default, recommended and only supported
  transport (udpu/udp was left only for debugging purposes).」
  2021-11-22 补充：「only real solution is to use knet, because udpu ifdown
  handling is not perfect (but usually works)」。
- [x] knet 不复现该问题 —— epenchev 2021-11-22 评论：「I've tested this with
  knet and it's working perfectly fine so no problem there.」
- [x] 缺陷成因涉及的两个提交 —— `96354fba72b7e7065610f37df0c0547b1e93ad51`
  （2018-07-12，totemudpu: Add local loop support，提交说明自称是为解决
  「long time ifdown corosync problem」，做法是网卡 down 时改用本地 socket
  收发并继续假装旧 IP 存在）；`c652ee0df8c1971cf9347c69d7ff3d78505dc9e9`
  （2019-05-29，udpu: Drop packets from unlisted IPs）。jfriesse 归因于后者：
  该丢弃逻辑对 socketpair 也生效，而 socketpair 的 `msg_name` 未设置。
  补丁 PR 685 的提交说明是同一归因（"msg_name is unset for socketpair"）。
- [x] udpu 传输层在当前版本仍然存在 —— `exec/totemudpu.c` 在 v2.4.6、v3.2.0
  与 `main` 分支下均可取到（HTTP 200），所以「升级到新版就不会有这个问题」
  的说法不成立，问题仍然在 udpu 上；规避靠换 knet 而不是靠升级。
- [x] **knet 是 corosync 3 才有的**（`-1` 版独有）—— `exec/totemknet.c` 在
  v2.4.6 下 HTTP **404**，在 v3.0.0 / v3.2.0 / `main` 下均 HTTP 200；
  v2.4.6 的 `man/corosync.conf.5` 中 "knet" 出现 **0 次**，其 transport 段写的是
  「The default is udp. The transport type can also be set to udpu or iba.」；
  `main` 的 man page 写「KNET. This is a default and recommended transport
  introduced in Corosync 3」。
- [x] **在 corosync 2.4.6 上写 `transport: knet` 会静默退化成组播 UDP**
  （`-1` 版独有，本轮据此改写了结论）—— `exec/totemconfig.c`（v2.4.6）：
  `totem_config->transport_number = TOTEM_TRANSPORT_UDP;` 之后只对
  `strcmp(str,"udpu")==0` 与 `strcmp(str,"iba")==0` 覆盖，没有第三个分支、
  不报错；v3.0.0 同一段默认 `TOTEM_TRANSPORT_KNET` 并显式识别
  `udpu`/`udp`/`knet`。
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
- [x] `block_unlisted_ips` 就是这次缺陷的配置面开关 —— `main` man page：
  「Allow UDPU and KNET to drop packets from IP addresses that are not known
  (nodes which don't exist in the nodelist) to corosync. … The default value
  is yes.」；对应 `c652ee0`（udpu: Drop packets from unlisted IPs），
  而修复 `8b638e98` 就是让这条丢弃逻辑在本地 socketpair 场景下不生效。
- [x] totem token 超时的默认值与算法 —— `main` man page：`token`「The default
  is 3000 milliseconds.」；`token_coefficient`「This value is used only when
  nodelist section is specified and contains at least 3 nodes. If so, real
  token timeout is then computed as token + (number_of_nodes - 2) *
  token_coefficient.」，「The default is 650 milliseconds.」三节点即
  3000 + 650 = 3650 ms。
- [x] 上游对 ifdown 这种测法的定性 —— corosync 3.0.0 发布说明：
  「many people beloved way to test node split - ifdown - now finally works
  with Knet transport. UDPU transport was also partly fixed. Please keep in
  mind this method of testing is still **not supported nor recommended**.」
  原文「knet 方式不会」只说对了一半，限定条件要一并写进去。
- [x] 《2017-Kronosnet-The-new-face-of-corosync-communications》确有出处 ——
  是 **Christine Caulfield** 在 Clusterlabs Summit 2017 的演讲
  （corosync 官方 wiki 的 Presentations 页收录为「Kronosnet - The new face
  of corosync communications」）；原始 PDF 地址
  `http://build.clusterlabs.org/corosync/presentations/2017-Kronosnet-The-new-face-of-corosync-communications.pdf`
  在 corosync 3.0.0 的发布邮件里被引用。演讲 slides 里列的是
  「UDP (unicast) / SCTP / Loopback」「No multicast, but could be added if
  really wanted」「**No broadcast**」——与「knet 会广播」的观察矛盾。
  本轮复查：该 PDF 链接当前仍可访问（HTTP 200）。
- [x] `transport:` 指令的位置 —— `main` 的 `man/corosync.conf.5` 里 `transport`
  是 `totem { }` 段下的子指令：「This directive controls the transport mechanism
  used. The default is knet (for KNET). The transport type can also be set to
  udpu (for UDPU) or udp (for UDP).」本轮正文据此把应急做法的落点写成
  `corosync.conf` 的 `totem { }` 段，而不是某个本仓库里不存在的部署脚本。
- [x] 站点渲染链下裸 URL 吞中文 —— 实测（marked 15.0.12、
  hexo-renderer-marked 7.0.1 的 tokenizer、`_config.yml` 的 marked 选项：
  `gfm/breaks/smartLists/smartypants/headerIds` 全开、`autolink` 默认 true、
  `dompurify` 未开）：以 `https://` 开头的裸 URL 会吃掉直到下一个空白为止的
  所有字符。原文 L18、L22 渲染出的 href 里含
  `%EF%BC%8C%E6%88%91%E4%BB%AC%E7%9A%84corosync…%E3%80%82`，
  即整段中文。
- [x] 全树同类问题的规模 —— 按上述规则逐行扫描 `docs/`（排除代码块、
  行内代码与 markdown 链接）：**15 篇 / 30 处**，分布为
  `docs/network/【网络】MTU相关网络丢包问题分析处理.md` 7 处、
  `docs/tools/clash-meta-mihomo-install-guide.md` 5 处、
  `docs/tools/clash-meta-user-guide.md` 4 处、
  `docs/cluster/corosync/corosync-down网卡仍处于多数派/index.md` 与
  `-1/index.md` 各 2 处，其余 9 篇各 1 处。本轮只改本篇与 `-1` 那两处，
  其余 26 处留给后续批次。
- [x] `## 结论` 段不是有序列表 —— 实测渲染结果为
  `<p><font color="red">1. …；<br>2. …，</font>找到如下内容：</p>`，
  行首因 `<font>` 开标签而不再是 `1.`，marked 不生成 `<ol>`。
- [不适用] 本文现场所用的 corosync 版本与发行版打包版本 —— 本轮正文
  **没有写死版本号**：改写成「以 `corosync -v` 的输出为准」，并说明本文的
  判断只依赖传输层、不依赖小版本；同时给出 udpu 所在的版本线（2.4.6 与 3.x
  都还在）。现场具体版本需作者补充。
- [不适用] 未启用 vote_quorum 与本现象的因果关系 —— 本轮正文只陈述
  「现场未启用 votequorum、无 qdevice」这一环境事实，**没有断言**它与本现象
  的因果关系；启用 votequorum 后是否必然转为非 quorate 仍需查
  `exec/votequorum.c` 与 votequorum(5)，那是另一轮的事。
- [不适用] fence 的 20 秒阈值与现场 corosync 收敛时间的关系 —— 本轮正文
  给出的是**上游默认配置下的算法与判据**（真实 token 超时 =
  `token + (节点数 - 2) × token_coefficient`，默认 3000 ms + 650 ms，
  三节点约 3650 ms；fence 阈值必须慢于它），并写明现场参数要以自己的
  `corosync.conf` 为准。**没有断言**现场的 20 秒够不够——那要现场那份
  `corosync.conf` 与 fence 脚本才能判。
- [不适用] 「clusterware MDE」「ES」这两个词的确切所指 —— 本轮正文把这两句
  内部待办整段移出，没有解释也没有保留。
- [不适用] 「knet 会做广播」这个观察的原始记录 —— 正文保留了原文「这是虚拟机
  抓包环境造成的」这一澄清，并补上了可核实的配置面理由（`link_mode` 只有
  passive / active / rr，没有 broadcast）。抓包位置与过滤条件属作者现场
  细节，本轮**没有写进正文**；要写需作者补验证方法。
- [不适用] `V8R6_cluster_install.sh` —— 全树检索确认仓库里没有这个脚本
  （这个名字只出现在这两份审校记录里）。本轮正文把应急做法的落点改成
  `corosync.conf` 的 `totem { }` 段 `transport:` 一行（位置由上游手册页给出），
  **不再依赖那个脚本的内容**；脚本的具体路径与内容需作者补充。

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

按「优先修改」的 13 条 + `-1` 记录独有的问题逐条落地，正文改动如下：

1. 开头补「编写人 / 编写内容 / 编写时间」表与定位导语：先说现象（网卡
   down 后 corosync 仍自报 quorate → fence 不动作 → observer 跨中心切换 →
   双主），再点明本文要回答的三个问题。
2. 新增「## 环境与边界」一节，用表格交代集群规模、传输层、votequorum、
   qdevice 与集群形态；并写清结论只对 udpu 传输层成立、udpu 在 2.4.6 与
   3.x 里都还在（对应第 5 条）。
3. 「## 问题现象」补上可复现命令：`ip link set eth0 down` 注入，
   `corosync-quorumtool -s` / `-m`、`corosync-cfgtool -s` 观测（第 4 条）。
4. 同节补上主体限定：剩下两个节点仍满足多数派、仍应是 quorate，该转非
   quorate 的是被 down 的那台自己；并说明缺主语会让读者误停库（第 6 条）。
5. 新增「## 脑裂双主是怎么发生的」一节，把原来的 220 字长段拆成五步
   时序列表（失联 → 不停库 → observer 切换 → 网络恢复 → 双主），并点明
   第 3 步触发的是「本中心失联」而非「网卡 down」这个动作（第 7 条）。
6. 同节补 20 秒阈值的来由与判据（必须慢于 corosync 判定自己失联的时间），
   并给出上游默认配置下的真实 token 超时算法与三节点约 3650 ms 的量级，
   注明现场参数以自己的 `corosync.conf` 为准（第 7 条）。
7. 「## 问题原因」重写为「## 为什么会这样」：补上 `96354fb` → `c652ee0` →
   `8b638e98` 三次提交的成因链（配一张 mermaid 流程图）、jfriesse 的归因、
   `exec/totemudpu.c` 的源码入口与三态，以及配置面开关 `block_unlisted_ips`
   （第 2 条）。
8. 新增「## 上游的修复」一节：修复是 **PR 686** / commit `8b638e98`
   （+1/-0 一行），**PR 685 从未合入**并给出关闭时的状态字段；写清该 commit
   已覆盖 v2.4.6 / v3.1.7 / v3.1.10 / v3.2.0，所以留在 udpu 也有出路
   （第 1、13 条）。
9. 原文两段一字不差的「问题原因」「问题解决」整段删掉，替换为第 7、8 条
   的两节——重复段消失（第 3 条）。
10. 原文两处裸 URL 改写成 markdown 链接（PR 686 的 commit、PR 685），
    并按「URL 单独成段」处理，避免 marked 把后面的中文吞进 href。
11. 新增「## 为什么换到 knet」一节：补 jfriesse 的原话依据与
    「but usually works」这句限定；写清 knet 的 IP 传输层默认 udp、
    sctp 已弃用；并写明「knet 会广播」这个担心在配置层面没有依据
    （`link_mode` 只有 passive / active / rr）；`2017-Kronosnet…` 的出处
    给出可点击的演讲 PDF 链接（第 13 条 + `-1` 第 5 条）。
12. 新增「## 结论与落地」一节（替掉 `-1` 版那节被 `<font>` 破坏的结论）：
    长期迁到 corosync 3.x + knet；紧急 POC **必须先确认是 3.x**——在 2.x 上
    写 `transport: knet` 会静默退化成组播 UDP，2.x 的紧急做法是合入
    `8b638e98`；再补持续跟踪上游。切 knet 的三条前提（`corosync -v` 看
    Built-in features、每个节点补 `nodeid`、准备 `authkey` 加密）单列。
13. 应急做法的落点从 `V8R6_cluster_install.sh` 改成 `corosync.conf` 的
    `totem { }` 段 `transport:` 一行（`-1` 第 1 条）。
14. 新增「## 故障注入对照表」一节：把「开防火墙 / 停网卡服务 / ifdown /
    拔网线」四种注入方式做成表，逐条写期望的 quorum 状态、判定命令与
    需要现场确认的点；并写明判定标准始终是「被隔离的那台应为非 quorate，
    其余节点应把它视为 offline」（第 9、11 条）。
15. 「### 对于开发来说」「### 对于测试来说」两节内部待办删掉：已定的写成
    结论（目标版本 corosync 3.x + knet、持续跟踪上游），还没定的移出正文；
    测试方法论那句「不能只以关机重启或者 chaos-blade 模拟」保留，作为
    对照表的引子（第 8 条 + `-1` 第 6、7 条）。
16. 错别字逐处改正：「生成中心」→「本中心」、「格一段时间」→「隔一段时间」、
    「给出选择那种通信方式」→「哪种」、「网路恢复」→「网络恢复」（第 10 条
    + `-1` 第 13 条）。
17. 结尾新增「## 延伸阅读」，链到同目录的 `totem协议详解.md`、
    `corosync qnet挂死场景分析解决.md`、`corosync-qdevice使用.md`
    （第 11 条）。带空格的路径按 `sync-hexo.py` 的解析规则写成字面空格
    （实测 `_resolve_link_target` 能解出真 permalink；写成 `%20` 反而解不出）。
18. 合并处置：删除 `docs/cluster/corosync/corosync-down网卡仍处于多数派-1/`
    目录、其审校记录与索引行；`-1` 记录独有的待核事实与结论已搬进本记录。

正文改动后检查器信号：本篇由 **3 条 warn**（AIF-03 / AIF-05 / STR-04 之外的
AIF-03、AIF-05、DEP-04）降到 **0 条**；STR-02、MET-01 也一并通过
（开头有了定位导语与编写信息表）。`-1` 版原来的 2 条 warn
（AIF-03、AIF-05）随目录删除一并消失。
