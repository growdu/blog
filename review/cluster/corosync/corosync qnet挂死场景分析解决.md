# 审校：corosync qnet挂死场景分析解决

- 原文：`docs/cluster/corosync/corosync qnet挂死场景分析解决.md`
- 范围：全文
- 目标读者：做双节点 / 同城双中心仲裁方案的工程师
  （知道 qdevice、qnetd 的角色，想搞清楚仲裁进程挂掉后的行为边界）
- 一句话定位：分析「仲裁进程 qnetd 挂死又恢复后，选出来的分区可能不是
  原来提供服务的分区」这个矛盾，并给出一个用节点数量做身份判定的办法
- 核心判断：**那个判据不成立**——节点数量相同的两个不同分区会被误判成
  「同一个分区」；而上游 qnetd 用的判据是 **ring_id + 成员集合的完整比对**，
  不是数量。另外全文有两处自相矛盾的结论、一节空骨架、以及一个没有回答
  的关键问题：那个「上一次提供服务的分区」的状态由谁记
- 审校状态：建议中

## 优先修改

1. 位置：L12-L17（核心判据：比较节点数量）
   - 问题：**这个判据不可靠，而且上游用的根本不是它**。
     原文的思路是：「记录下上一次提供服务的节点数量……因而可以使用本次投票
     时的节点数量与上一次提供服务时的节点数量进行比较来判断分区是否是上次
     提供服务的分区」，规则是「数量减少 → 不是；数量不变或增多 → 是」。
     但**数量相同的两个不同分区会被误判**。反例：三节点 {A,B,C}，
     之前 {A,B} 提供服务（A 的当前节点数 = 2）。qnet 挂死期间 C 回来与 A
     组网形成 {A,C}，B 单独。qnet 恢复后把票投给 {A,C}。
     A 的当前节点数是 2 → 2，按 L15「若节点数量不变……则是上一次提供服务的
     分区，可以提供服务」判定通过——**但上次服务的是 {A,B}，现在是 {A,C}**，
     成员完全不同。B 那一侧如果还在跑，两边都提供服务，就是脑裂。
     上游的做法比数量比对强得多，已核实：
     - qnetd 的 ffsplit 算法 `qnetd_algo_ffsplit_is_membership_stable()`
       （`qdevices/qnetd-algo-ffsplit.c`）先 **比较 ring id**
       （`if (!tlv_ring_id_eq(ring_id1, ring_id2)) return (0);`，
       注释就是「Compare ring ids」），再**逐个成员比对 membership node list**
       （注释「Now compare that membership node list equals, so walk thru all
       members」）——判定的是 (ring_id, 成员集合) 完全一致；
     - qdevice 客户端侧同样用 ring_id：`qdevices/qdevice-net-msg-received.c`
       里 `if (!tlv_ring_id_eq(&msg->ring_id, &instance->last_sent_ring_id))`
       就判定「Received node list reply with **old ring id**」。
     → 也就是说，**上游已经用「ring_id + 成员集合」精确回答了
     「是不是上次那个分区」这个问题**，而且 ring_id 天然满足
     「同一环的成员共享同一个 ring_id」这一条。
   - 建议：把判据换成 ring_id：记录上次提供服务的分区的 ring_id，
     qnet 恢复后比较新分区的 ring_id；ring_id 相同即可继续服务。
     若要做成上层（kbha）的能力，则需把「比较 ring_id」实现成
     「用 `corosync-cmaptool` 读本节点的 ring id」这一条可执行的操作，
     而不是比较节点数量。
   - 原因：涉及技术结论，必须可回溯；这是全文的核心判据，
     判据不成立，整篇推演的前提就是错的。README 的「机制解释」
     「踩坑与校验」。

2. 位置：L154（结论自相矛盾）
   - 问题：**一句话里前后打架**。原文：「此时A节点分区虽然获取到qnet投票，
     但其节点数量减少，**无法获取到投票**。」前半句说拿到了票，
     后半句说拿不到票。而且 L135 的状态变更里 A 恢复时写的是
     「1(qnet恢复获取到投票)」，与后半句直接矛盾。
   - 建议：改成「此时 A 所在分区虽然获取到 qnet 投票，但其节点数量减少，
     按上述判据无法提供服务」。
   - 原因：基础校对 + 结论准确性。

3. 位置：L54 与 L77（两节结论互斥）
   - 问题：**L54 说可以服务，L77 说不能服务**。
     L54：「挂死过程中发生网络分区，数据无法写入，qnet恢复后识别分区，
     **可以根据选举规则提供服务**。」
     L77：「无论哪个分区获得投票，节点数都变少，**无法提供服务**。」
     同一个场景（挂死前未分区、挂死过程中分区），两处结论相反。
   - 建议：明确取一个。按 L12-L17 的判据，这里应该是「无法提供服务」，
     L54 应改成「qnet 恢复后能识别分区，但按判据不能恢复服务」。
   - 原因：README 的「按读者的阅读路径组织」——
     同一篇里前后两个相反的结论，读者无法判断该信哪个。

4. 位置：L12（判据的前提）
   - 问题：**前提「未继续服务的分区节点数量不会改变」不成立**。
     原文：「当网络分区时，继续提供服务的分区节点数量会发生改变，
     而**未继续服务的分区节点数量不会改变**」。
     这只在「没有节点真的宕机、只是网络分区」时成立。一旦有节点宕机，
     上次提供服务的分区自己就会缩小（少了那个宕机的节点），
     数量同样会变——而节点宕机恰恰是仲裁进程挂死场景的常见伴随现象。
     → 前提不成立时，整套判据失效。
   - 建议：把「节点数量」明确为「**分区成员集合的大小**」并说明前提
     （本判据只区分「分区变大/变小/不变」，不区分「成员换了但个数一样」）；
     更好的做法是直接换成第 1 条的 ring_id 判据，它对节点宕机是免疫的。
   - 原因：README 的「问题边界」——判据的适用条件必须写出来。

5. 位置：L181-L186 与 L12（方案的关键缺口）
   - 问题：**这一节提出的问题，正好击中了方案的软肋，但全文没有回答**。
     L183-L186 说得很对：「节点本身无法判断qnet是否挂死，只能感知到是否
     获取qnet投票……则无法获取到投票，则有两种情况：网络分区 / qnet挂死」。
     那么 L12 要求的「记录上一次提供服务的节点数量」**存在哪里**？
     - 记在每个节点本地：各节点看到的成员列表不同、观测时刻也不同，
       记出来的值会分歧，判定结果也会分歧；
     - 记在 qnetd：**上游 qnetd 的设计目标恰恰是不保存状态**——
       README 原文「corosync-qnetd … is designed to support multiple clusters
       and be **almost configuration and state free**. New clusters are handled
       dynamically and **no configuration file exists**.」
       真正被记下来的只有每个 client 侧的 `last_ring_id` 与
       `last_membership_node_list`（`qdevices/qnetd-client-msg-received.c`），
       那是**易失的运行期状态**，不是「上次提供服务的分区」这种跨挂死的持久记录；
     - 记在别处（数据库、文件）：那就**引入了第三方存储**——
       而这恰恰是同目录 `sanlock实现共享corosync共享存储仲裁.md` 讨论的
       那个问题。
     → 原文提出问题、给出判据，却没有回答「状态存哪、谁来保证一致」。
   - 建议：补一段「状态放在哪」，把三个选项各自的代价写出来。
     如果最终结论是「必须引入第三方存储」，那这篇和
     `sanlock实现共享corosync共享存储仲裁.md` 就应该合成一篇，
     或者互相链接——两篇讲的是同一个问题的两面。
   - 原因：这是方案能不能落地的关键。README 的「工程取舍」
     「可复现证据」。

6. 位置：全文（上游已有对应机制）
   - 问题：**文章在解决一个上游已经部分考虑过的问题，而完全没提到上游**。
     已核实 qdevice 的 `quorum.device.net.keep_active_partition`
     （默认 **on**）：「specifies if **keep active partition tie breaker**
     should be used. When this option is enabled and tie happens QNetd will
     prefer partition with members of **previously active (quorate)
     partition**. This is hard-coded behavior of LMS algorithm so this setting
     affects only FFSplit algorithm. Default is `on`.」
     ffsplit 本身的描述也相关：「It is able to transition its vote if the
     currently active partition becomes partitioned and a non-active partition
     still has at least 50% of the active nodes.」
     → 「qnet 恢复后选出的分区可能不是上次服务的分区」这个问题，
     上游用 keep_active_partition + ffsplit 的投票转移能力做了**部分**处理
     （注意：keep_active_partition 是**平手时的**兜底，
     ffsplit 的投票转移也有前提条件，不是无条件满足）。
   - 建议：先写清楚「上游做了什么、覆盖到什么程度、剩下的是什么」，
     再决定要不要自研。这是 README 的「先保真」与「用证据建立技术感」——
     读者最想知道的是「这活儿上游做了没有、做了多少」。
   - 原因：涉及事实，必须可回溯；也避免重复造轮子。

7. 位置：全文（「qnet」这个词）
   - 问题：**「qnet」同时指代两样东西，读者会混**。
     上游术语是：**qnetd**（仲裁进程，`corosync-qnetd`）与
     **model net**（仲裁模型，corosync.conf 里 `quorum.device.model: net`）。
     原文从 L3 起就一直用「qnet」，且**从未定义「qnet 挂死」到底指什么**——
     是 qnetd 进程挂了？是 qdevice 到 qnetd 的网络断了？还是 qnetd 所在
     机器宕了？三种情况的处理完全不同（第三种 qnetd 重启后是全新状态）。
   - 建议：统一成「qnetd」，并在开头一句话定义「本文说的挂死指
     qnetd 进程不可用」。若三种情况结论不同，就分开写。
   - 原因：README 的「术语一致」。

8. 位置：L188-L201（「## n节点集群」一节）
   - 问题：**这一节是空骨架**——只有两级 bullet，没有任何内容。
     而且 L190 有一个错字：「n个节点集群，**分死种**情况讨论」
     ——「死」应为「**四**」。
   - 建议：要么把这节写完（n 的一般推导），要么删掉——
     一节只有标题和空 bullet 的「分析」，读者只会困惑。
   - 原因：README 的「结构跳跃」「信息重复」——L192-L201 的四组空 bullet
     与 L25-L27、L52、L79、L131 四个小节是同一套组合的另一种列法，
     读者会以为是新内容，其实什么都没说。

9. 位置：L235-L241（「## qnet恢复后节点数量减少情况分析」）
   - 问题：**标题说「分析」，正文只有三行**，而且最后一句
     「此时B获得qnet的投票，B无法提供服务」与 L129
     「qnet恢复后1节点分区获取到投票，但其节点数量减少，无法提供服务」
     是同一类结论（拿到票但节点数量减少 → 无法提供服务）。
     三行里没有一句给出**规则**，只有一次具体场景。
   - 建议：这一节要么补完（把「节点数量减少」的各种组合枚举清楚，
     并把 L12 的判据写成可判断的条件），要么并入前面三节点的分析里。
   - 原因：README 的「信息重复」。

10. 位置：L223 与 L233（复制粘贴留下的重复）
    - 问题：**两处近乎逐字相同，而且各自指错了小节**。
      L223：「qnet挂死前发生网络分区时可以继续提供服务，其场景与qnet挂死前
      未发生网络分区，挂死过程中也未发生网络分区一致。」
      L233：「qnet挂死前发生网络分区时可以继续提供服务，其场景与qnet挂死前
      未发生网络分区，挂死过程中发生网络分区一致。」
      两句只差「未发生/发生网络分区」几个字（检查器 AIF-05 报相似度 0.98）。
      而且 L233 说的「与…挂死过程中发生网络分区一致」指向的正是
      L213-L217 那一节——那一节的结论是「集群**不可以**提供服务」，
      与本句「可以继续提供服务」正好相反。
    - 建议：改写 L233（它真正想说的是「挂死前已分区时，上次服务的分区
      在挂死中未再分区，则仍可服务」），并把 L223、L233 合成一处。
    - 原因：README 的「信息重复」与「结构跳跃」；自相矛盾的结论
      比没有结论更糟。

11. 位置：L156
    - 问题：**句子不成句**——「特别的，C分区后，B再分区，并且C重新回来，
      可以提供服务。」缺主语（「哪个分区可以提供服务」？），也没有说明
      是哪个分区。
    - 建议：补全主语与结论对象。
    - 原因：基础校对。

12. 位置：全文（没有可复现的验证）
    - 问题：**全篇是纸面推演，一个实验都没有**（检查器 DEP-00：五个技术
      深度要素**一个都没命中**）。而这类「挂死-恢复」的时序问题，
      恰恰是最适合用实验钉死的。
    - 建议：给一个可复现的实验清单——
      (1) 双节点 + qnetd，停掉 qnetd，看集群失去仲裁票后的行为；
      (2) 停掉 qnetd 的同时做一次网络分区，恢复后看票投给了谁、
      `corosync-cfgtool -s` 里的 ring id 变成多少；
      (3) 复现第 1 条里那个反例（{A,B} 服务 → {A,C} 拿到票），
      验证按数量判据会误判、按 ring_id 判据不会。
      第 (3) 步做完，第 1 条的结论就从「推理」变成「实测」。
    - 原因：README 的「可复现证据」「踩坑与校验」。

13. 位置：L1 开头 / L241 结尾
    - 问题：开头没有一句话定位（检查器 STR-02 命中）——读者不知道
      这是一篇「问题分析」还是「方案设计」；结尾停在一句没头没尾的
      描述上，没有产物（检查器 STR-03 命中）；
      缺「编写人／编写内容／编写时间」表（检查器 MET-01 命中）。
    - 建议：开头补定位与编写信息；结尾补一张「场景 × 判定 × 结论」的
      汇总表（把三节点的四种组合和 n 节点的一般情形并成一张），
      再链到同目录 `corosync-qdevice使用.md`、
      `sanlock实现共享corosync共享存储仲裁.md`、
      `docs/cluster/ha/中移动数据库停库问题分析/index.md`
      （一个真实的「失去多数派 → 停库」案例）。
    - 原因：README 的「一句话定位」「一份可带走的产物」「一条自然的内容路径」。

14. 位置：全文（版本边界）
    - 问题：**没有版本信息**。本文讨论的行为依赖 qdevice 的具体实现
      （ring_id 比对、keep_active_partition 默认值），随版本会变。
    - 建议：加一行「本文基于 corosync-qdevice <版本> / corosync <版本>」。
    - 原因：README 的「问题边界」。

## 事实待核

- [x] 上游判定「是不是同一个分区」用的是 ring_id + 成员集合，不是节点数 ——
  `qdevices/qnetd-algo-ffsplit.c` 的 `qnetd_algo_ffsplit_is_membership_stable()`：
  先 `if (!tlv_ring_id_eq(ring_id1, ring_id2)) { return (0); }`（注释
  「Compare ring ids」），再逐成员比对 membership node list（注释
  「Now compare that membership node list equals, so walk thru all members」）。
  qdevice 客户端侧同理：`qdevices/qdevice-net-msg-received.c`
  `if (!tlv_ring_id_eq(&msg->ring_id, &instance->last_sent_ring_id))` →
  记日志「Received node list reply with old ring id.」。
- [x] qnetd 侧保存的是每个 client 的运行期状态，不是跨挂死的持久记录 ——
  `qdevices/qnetd-client-msg-received.c` 里
  `memcpy(&client->last_ring_id, &msg->ring_id, sizeof(struct tlv_ring_id))`
  与 `last_membership_node_list`；qnetd README：「corosync-qnetd … is
  designed to support multiple clusters and be **almost configuration and state
  free**. New clusters are handled dynamically and **no configuration file
  exists**.」
- [x] 上游已有「优先保留此前活跃分区」的机制 —— qdevice man page
  `quorum.device.net.keep_active_partition`：「Can be one of `on` or `off` and
  specifies if **keep active partition tie breaker** should be used. When this
  option is enabled and tie happens QNetd will prefer partition with members of
  **previously active (quorate) partition**. This is hard-coded behavior of LMS
  algorithm so this setting affects only FFSplit algorithm. **Default is
  `on`.**」
- [x] ffsplit 的投票转移能力 —— 同 man page：ffsplit「It is able to transition
  its vote if the currently active partition becomes partitioned and a non-active
  partition still has at least 50% of the active nodes. Because of this, a vote
  is not provided if the qnetd connection is not active.」
- [x] lms 算法按 ring_id 划分分区 —— 同 man page：lms「If more than one node
  can see the qnetd server but some nodes can't see each other then the cluster
  is divided up into 'partitions' based on their **ring_id** …」
- [x] 三处结论自相矛盾 —— L54「可以根据选举规则提供服务」vs L77「无论哪个
  分区获得投票，节点数都变少，无法提供服务」；
  L154「虽然获取到qnet投票……无法获取到投票」；
  L223 与 L233 近乎逐字重复且 L233 所指小节的结论与本句相反
  （L213-L217 那一节写的是「集群不可以提供服务」）。
- [x] 检查器信号 —— AIF-05 报 L215~L221（0.94）与 L223~L233（0.98）
  两对近似重复；DEP-00「只命中 **0/5** 个技术深度要素」；
  STR-02 / STR-03 / MET-01 三条结构提示。
- 「上一次提供服务的分区」这个状态**具体存在哪里** —— 是每个节点本地记、
  qnetd 记、还是外部存储？这决定方案能否落地，需作者给出。
  （按上游设计 qnetd 是无状态的，见上。）
- 现场是否会出现**节点宕机与网络分区同时发生** —— 若会，则 L12 的
  「未继续服务的分区节点数量不会改变」这个前提不成立，数量判据整体失效。
- L154「无法获取到投票」的**原意** —— 按上下文推测应为「无法提供服务」，
  需作者确认。
- L54 与 L77 到底取哪个结论 —— 需作者确认。
- L233 想表达的**原意** —— 按上下文推测应为「挂死前已分区、且挂死过程中
  未再分区时，上次服务的分区仍可服务」，需作者确认。
- 现场 qdevice / qnetd / corosync 的**版本**与 `quorum.device.net.algorithm`、
  `keep_active_partition` 的实际取值 —— 正文完全没有。
- 是否有 qnetd 挂死的**现场日志**（qnetd 日志、qdevice 日志）——
  有的话可以把推演换成实测。

## 可补的技术证据或产物

- 机制 / 源码入口：qnetd 侧 `qdevices/qnetd-algo-ffsplit.c` 与
  `qnetd-algo-lms.c`（分区划分与打分）、`qnetd-client-msg-received.c`
  （`last_ring_id` / `last_membership_node_list` 的维护）、
  `qdevice-net-msg-received.c`（客户端侧的 ring_id 校验）；
  客户端侧 `qdevice-net-algo-ffsplit.c` / `qdevice-net-algo-lms.c`。
  本文的三节点状态推演，其实可以对照这些文件里
  「分区怎么划、票怎么算、回复怎么校验」三段代码逐句展开。
- 实验或观测：见「优先修改」第 12 条的三步实验；
  观测命令用 `corosync-cfgtool -s`（看 Ring ID 与成员）、
  `corosync-quorumtool -s`（看 Quorum information）、
  `corosync-qdevice-tool -s`（看与 qnetd 的连接和票状态）。
  **ring_id 就是分区身份**，把它读出来对照，就能量化「是不是同一个分区」。
- 工程取舍：把三种「状态存哪」的方案摆开比——
  节点本地记（无额外依赖，但各节点可能分歧）/ qnetd 记（违背上游无状态
  设计，且 qnetd 重启即丢）/ 外部存储（一致，但引入新的单点与依赖，
  正是 `sanlock实现共享corosync共享存储仲裁.md` 那篇讨论的难题）。
  再补上「干脆不自己判，交给上游 keep_active_partition + ffsplit 投票
  转移」这个选项的代价与边界。
- 结尾清单或下一篇链接：一页「qnetd 挂死 / 恢复」处置清单
  （现象 → 可能原因（进程挂 / 网络断 / 机器宕）→ 集群此时的行为 →
  恢复后要确认什么 → 脑裂风险在哪）；再链到同目录
  `corosync-qdevice使用.md`、`sanlock实现共享corosync共享存储仲裁.md`。

## 已确认的改动

- （本轮只出审校记录，正文改动待确认后执行。）
