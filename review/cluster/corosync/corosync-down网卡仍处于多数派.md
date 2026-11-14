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
- 审校状态：建议中

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
- 本文现场所用的 corosync 版本与发行版打包版本 —— 仓库里查不到，
  需作者补充；正文「问题现象」一节必须补上，否则读者无法判断自己是否受影响。
- 未启用 vote_quorum 与本现象的因果关系 —— 三节点集群下被 down 的那台在
  未启用 votequorum 时，quorum 由 totem 环的形成员关系判定，因而察觉不到
  自身失联；启用 votequorum 后是否必然转为非 quorate，需查 `exec/votequorum.c`
  与 votequorum(5) 后再写进正文，暂不下结论。
- fence 的 20 秒阈值与 corosync 收敛时间的关系 —— 需该集群的
  `corosync.conf`（totem token 超时、downcheck 等）与 fence 脚本才能判定
  20 秒是否留了足够余量。
- 《2017-Kronosnet-The-new-face-of-corosync-communications》的出处 ——
  `-1` 版以书名号引用，未给链接；需补链接或改为普通描述。
- `V8R6_cluster_install.sh` —— 仓库里没有这个脚本，`-1` 版给出的改法
  （`transport: udpu` → `transport: knet`）需作者确认脚本路径与内容。

## 可补的技术证据或产物

- 机制 / 源码入口：`exec/totemudpu.c` 的 `timer_function_netif_check_timeout()`、
  `totemudpu_build_sockets()`，以及 `BIND_STATE_UNBOUND / LOOPBACK / REGULAR`
  三态如何决定「网卡 down 时继续假装旧 IP 存在」；配合 `exec/totemip.c` 的
  `totemip_get_interface_address()`。knet 侧对应 `exec/totemknet.c`，
  它在链路 down 时走的是另一套检测路径——两者的差别就是本文最该讲清的一点。
- 实验或观测：注入用 `ip link set eth0 down` 或现场实际的 `ifdown eth0`；
  观测用 `corosync-quorumtool -s`（Quorum information）与 `-m`（持续监视）、
  `corosync-cfgtool -s`（Ring ID 与 membership）。判定标准要写清楚：
  被隔离的那台应为非 quorate，集群其余节点应把它视为 offline。
  上游 PR 685 评论里给了完整的四步复现，可以直接引用。
- 工程取舍：udpu → knet 的迁移成本与风险——配置项 `transport:` 的切换、
  knet 的链路参数（`link_mode`、`knet_pmtud` 等）、`knet` 是否会引入广播
  （`-1` 版记录的「测试环境发现 knet 会广播」实为虚拟机抓包环境问题，
  物理机验证无异常，这条澄清本身值得写进正文）；以及 udpu 所在 corosync 2.x
  已 EOL（最后一版 v2.4.6）这个背景。
- 结尾清单或下一篇链接：结尾给一张「故障注入方式 → 期望 quorum 状态 →
  判定命令」的表——这张表同时是测试用例和读者排查时能直接用的清单；
  再链到同目录 `totem协议详解.md`、`corosync qnet挂死场景分析解决.md`、
  `corosync-qdevice使用.md`。

## 已确认的改动

- （本轮只出审校记录，正文改动待确认后执行。）
