# 审校：raft重要概念

- 原文：`docs/cluster/raft/raft重要概念.md`
- 范围：全文
- 目标读者：想做分布式共识 / 数据库高可用选型的工程师
  （知道 Paxos、Raft 这些名字，但没读过论文也没实现过）
- 一句话定位：Raft 概念的入门摘抄——把选举、任期、日志复制的名词和流程
  串了一遍，但止步于名词，没讲 Raft 真正难的那三件事
- 核心判断：**开篇那句「分解成两个独立的问题」与论文原文不符**（论文是
  三个：leader election / log replication / safety，而 safety 恰好是
  本文完全没讲的那部分）；复制流程的最后一个条目**句子截断且方向写反**；
  「投票限制」一句主客体颠倒；此外通篇没提 Raft 里唯一必须持久化的东西
  和最容易实现错的提交规则
- 审校状态：建议中

## 优先修改

1. 位置：L5
   - 问题：**「raft将分布式一致性问题分解成两个独立的问题」与论文原文
     不符**。Raft 论文（Ongaro & Ousterhout, *In Search of an Understandable
     Consensus Algorithm (Extended Version)*）§5 开头写的是
     「Raft decomposes the consensus problem into **three** relatively
     independent subproblems」——**三个**：Leader election、Log replication、
     **Safety**。论文摘要里也是三样：「Raft separates the key elements of
     consensus, such as leader election, log replication, and safety」。
     这不是吹毛求疵：本文恰好**完全没讲 safety**，
     「两个问题」的说法等于把 Raft 里最难、也最能体现其设计意图的那部分
     从定义里删掉了。
   - 建议：改成「分解成三个相对独立的子问题」，并补一节 Safety——
     至少讲清论文 Figure 3 的三条性质（Election Safety、Leader Completeness、
     State Machine Safety）各自保证了什么，以及 Leader Completeness
     是靠 election restriction 撑起来的。篇幅有限时，
     宁可把「两个」改成「两个主要步骤（选主 + 复制），安全性由第三条性质
     保证」，也不要写成论文没这么说的话。
   - 原因：涉及事实与引用，必须可回溯；这是全文的定调句，定调错了
     后面全歪。

2. 位置：L77（并牵连 L75）
   - 问题：**这句话在句中截断，而且写反了**。原文是
     「若`local term==leader term，则需要比较local index和leader index；
     若local index\<leader index，则append log；若local index\>leader index`,」
     ——结尾一个反引号、句子没写完，读者根本不知道最后那半句是什么。
     而写出来的半句方向是反的：论文 §5.3 的一致性检查是
     「If the follower does not find an entry in its log with the same index
     and term, then it **refuses** the new entries」——
     **对不上就拒绝**，不是 append；leader 收到拒绝后要回退 `nextIndex`
     重试。原文既没说清「leader index」指 `prevLogIndex` 还是 `nextIndex`，
     又把「拒绝」写成了「append」。
     L75 同样不准确：「若`local term<leader term，更新local term，并append log`」
     ——更新 term 与 append 日志是两回事，更新完 term 还得先过一致性检查
     才谈得上 append。
   - 建议：按论文 Figure 2 的 AppendEntries 接收方五条判据重写这一段：
     1. term 小于当前 term → 回复 false；
     2. 日志里没有与 `prevLogIndex` 同 term 的条目 → 回复 false；
     3. 有冲突条目（index 相同、term 不同）→ 删掉它及其后所有条目；
     4. 追加新条目；
     5. 若 `leaderCommit > commitIndex` → `commitIndex = min(leaderCommit,
        新条目的最后 index)`。
     顺带说明 leader 侧收到 false 时的动作：`nextIndex` 回退重试。
   - 原因：这是全文最后、也是最实操的一段，却是断的；方向反了读者照着
     实现会写出「不检查一致性就覆盖日志」的代码。README 的「机制解释」
     「踩坑与校验」。

3. 位置：L41-L43（投票的处理）
   - 问题：**只写了投票的一半**。原文「收到投票请求的节点比较请求的term
     和自己的term，如果请求的term比自己的大，则更新自己的term」——
     这只是论文 Figure 2 里 RequestVote 接收方的第 0 步。论文的完整判据是：
     「1. Reply false if term < currentTerm；
       2. If votedFor is null or candidateId, **and** candidate's log is at
       least as up-to-date as receiver's log, grant vote」。
     也就是说，除了比 term，还要看**本任期有没有已经投过票**（`votedFor`）、
     以及**候选人的日志够不够新**。缺了后两条，读者照原文实现会投出第二票。
   - 建议：把三条判据写成编号，并说明 `votedFor` 是持久化状态
     （见第 6 条）。
   - 原因：同上，这是实现 Raft 最容易漏的两条判据。

4. 位置：L51（投票限制的第二条）
   - 问题：**主客体说反了，而且比较规则不完整**。原文「数据最新才能获取到
     投票（选举人必须知道的比自己的多，需要比较term和log index）」——
     「选举人必须知道的比自己的多」这句话按字面读不成立。
     论文 §5.4.1 的原话是**投票者拒绝投票**：
     「the voter **denies its vote** if its own log is **more up-to-date
     than that of the candidate**」——是**投票者自己的日志更新，就拒绝**。
     比较规则原文是「Raft determines which of two logs is more up-to-date by
     comparing the **index and term of the last entries** in the logs. If the
     logs have last entries with **different terms**, then the log with the
     **later term** is more up-to-date. If the logs end with the **same term**,
     then whichever log is **longer** is more up-to-date.」——
     **先比 term，term 相同再比长度**，不是笼统的「比较 term 和 log index」。
   - 建议：改成「候选人的日志必须至少和投票者的一样新，否则投票者拒绝投票；
     比较时先比最后一条日志的 term，term 相同再比长度」，并补一句
     **这是 Leader Completeness 的来源**——没有它，新 leader 可能带着
     缺失已提交条目的日志上台。
   - 原因：涉及技术结论，方向反了会写出错误实现；README 的「机制解释」。

5. 位置：L31
   - 问题：224 字一整段（检查器 AIF-03 命中），把「启动时是 follower →
     等心跳 → 心跳超时转 candidate → 拿到多数票转 leader → 收到 leader
     消息转 follower」五步状态迁移全塞在一段里。而且第一句是病句：
     「并且**每隔**follower状态的节点都会等待leader状态节点的心跳报文」——
     「每隔……都会等待」不成句，应为「每个处于 follower 状态的节点
     都会等待 leader 发来的心跳报文」。
   - 建议：改成一张状态迁移表（当前状态 → 触发事件 → 下一状态 → 动作），
     也就是论文 Figure 4 的等价物。这张表是全文最该有的「可带走的产物」。
   - 原因：README 的「让抽象话落地」「一份可带走的产物」。

6. 位置：全文（缺持久化状态）
   - 问题：**通篇没提 Raft 里唯一必须落盘的东西**。论文 Figure 2 明确列出
     「Persistent state on all servers: (**Updated on stable storage before
     responding to RPCs**)」——`currentTerm`（latest term server has seen，
     initialized to 0 on first boot, increases monotonically）、
     `votedFor`（current term 里投给的 candidateId，null 表示还没投）、
     `log[]`。也就是说这三个状态**必须在响应 RPC 之前**就写到稳定存储上。
     这是 Raft 里唯一需要 fsync 的东西，也是实现错了一定会在「节点重启
     后投出第二票」这类故障里暴露的地方。
   - 建议：补一节「必须持久化的三样东西」，并写清持久化的时机
     （响应 RPC 前）。
   - 原因：README 的「机制解释」「踩坑与校验」——这是读者照着实现时
     最需要知道的一条。

7. 位置：全文（缺提交规则）
   - 问题：**没讲 commit index，也没讲「什么才算已提交」**。论文 §5.4.2
     「Committing entries from previous terms」写得很明确：
     「a leader knows that an entry **from its current term** is committed
     once that entry is stored on a majority of the servers. However, a leader
     **cannot immediately conclude that an entry from a previous term is
     committed** once it is stored on a majority of servers.」
     也就是**只有当前任期的条目被多数派存下才算提交**；往期任期的条目
     存到多数派**不能直接判定**，得靠新 leader 提交一条当前任期的条目
     把它「带」过去。这是 Raft 最反直觉、也最常被实现错的一条规则。
   - 建议：补「提交规则」一小节，写清 commitIndex 的推进条件，
     以及「读请求要等 appliedIndex ≥ commitIndex」这类实际影响
     （线性一致读为什么不能直接读本地状态机）。
   - 原因：README 的「机制解释」与「工程取舍」；读者没有这条就没法
     理解 Raft 为什么安全。

8. 位置：L45-L69「## leader election」整节
   - 问题：**选举超时为什么要随机，全文没提**。论文 §5.2：
     「Raft uses **randomized election timeouts** to ensure that split votes
     are rare and that they are resolved quickly. To prevent split votes in
     the first place, election timeouts are chosen **randomly from a fixed
     interval (e.g., 150–300ms)**.」原文 L69 只写「选举超时，发起新一轮
     选举」，读者会以为固定超时即可，照着实现就会遇到选票瓜分。
     同节还漏了论文里 candidate 的三种结局的准确表述：
     「(a) it wins the election, (b) another server establishes itself as
     leader, or (c) a period of time goes by with no winner」，
     以及「A candidate wins an election if it receives votes from a
     **majority of the servers in the full cluster** for the same term」
     ——「整个集群的多数派」这个限定，原文写的是「大多数节点」。
   - 建议：补上随机超时（并给出论文给的 150–300ms 量级作参考，
     注明实际要按网络 RTT 调整），以及「多数派指全体节点的多数」这一限定。
   - 原因：README 的「工程取舍」——这是 Raft 少有的「非直觉但必须这么做」
     的地方。

9. 位置：L79-L87「# reference」
   - 问题：三个问题。
     - **正文里没有任何一处引用这些参考**，读者不知道哪句话对应哪个来源；
     - **两条 SegmentFault 链接已经失效**：实测
       `https://segmentfault.com/a/1190000020962361` 与
       `https://segmentfault.com/a/1190000038170806` 均返回 **HTTP 410 Gone**
       （另两条 `cnblogs.com/xybaby/p/10124083.html` 与
       `sofastack.tech/projects/sofa-jraft/raft-introduction/` 返回 200）；
     - **最该引的一手源没引**：Raft 论文本身
       （https://raft.github.io/raft.pdf）与官方站点 raft.github.io 都没出现。
       这篇讲的是概念，概念的标准答案就在论文里。
   - 建议：正文里给关键论断加出处（如「论文 §5.4.1」），把失效链接
     换成可用的替代或直接删掉；参考列表第一位放论文与官方站点。
     顺带：L87 的裸 URL 会渲染成「文字就是 URL」的裸链接，和上面三条
     markdown 链接风格不一致，可一并改成 markdown 链接。
   - 原因：涉及引用与链接，必须可回溯；失效链接是读者看得见的坏体验。

10. 位置：L1 开头 / L77 结尾
    - 问题：开头没有一句话定位（检查器 STR-02 命中）；结尾停在半句话上，
      既没有产物也没有指向同目录的相关文章（检查器 STR-03 命中）。
      另外缺本仓库其它文章都有的「编写人／编写内容／编写时间」表
      （检查器 MET-01 命中）。
    - 建议：开头补定位与编写信息；结尾给「状态迁移表 + 两种 RPC 的接收方
      判据 + 持久化三件套」这三张表的索引，再链到同目录的
      `raft协议动态调整quorum.md`、`c-raft分布式存储方案.md`，
      以及已合入的 `docs/cluster/分布式一致性协议.md`（那篇讲的是
      「哪些问题 Raft 解决不了」，正好是本文的下一步）。
    - 原因：README 的「一句话定位」「一份可带走的产物」「一条自然的内容路径」。

11. 位置：全文（技术深度）
    - 问题：检查器 DEP-00 命中——五要素只命中 1 个。原文没有版本边界、
      没有源码入口、没有可复现证据、没有工程取舍、没有校验方法，
      是一篇纯名词摘抄。
    - 建议：至少补两样，让它从「名词表」变成「能照着实现」的指南：
      - **源码入口**：etcd 的 raft 库（`go.etcd.io/raft/v3`）的
        `raft.go` / `log.go`，或 hashicorp/raft 的 `raft.go`；
        论文 Figure 2 的每条判据都能在这两个实现里找到对应的函数
        （`stepFollower` / `stepCandidate` / `stepLeader`、
        `RequestVote` / `AppendEntries` 的处理入口）；
      - **可复现证据**：用上面的可视化
        （https://raft.github.io/ 上的 RaftScope 浏览器里直接跑一遍
        选主与日志复制）当实验入口——这是 Raft 少有的能零成本复现的场合，
        很配「用证据建立技术感」这条原则。
    - 原因：README 的「技术深度检查」；也正好对上博客「数据库内核与
      分布式系统」这条支柱该有的密度。

12. 位置：与 `docs/cluster/raft协议动态调整quorum.md` 的关系
    - 问题：仓库里有**两份逐字节相同**的文件——
      `docs/cluster/raft协议动态调整quorum.md` 与
      `docs/cluster/raft/raft协议动态调整quorum.md`（`diff` 无输出，
      两份都是 36 行，H1 都是「raft协议动态调整quorum」）。
      站点上会出现两篇完全一样的文章。
    - 建议：留一份、删一份（保留 `raft/` 目录下的那份，与本篇同目录，
      便于形成 raft 系列）。那篇本身不在本轮审校范围（信号 1 条），
      但重复这件事该一并处理。
    - 原因：README 的「信息重复」；两篇同名同文的文章是读者负担，
      也是内容资产的浪费。

13. 位置：L35-L43（term 一节）
    - 问题：这几段本身**没有硬伤**，但太薄：term 的作用只说「作为逻辑时钟」，
      没给论文那句关键限定——「Terms act as a logical clock in Raft, and
      they allow servers to **detect obsolete information such as stale
      leaders**」。term 的真正价值就是「让服务器能识别过时的 leader」，
      不点破这一句，读者只当它是版本号。
      L39 的「leader 工作一段时间后下台」用词偏口语（「下台」）。
    - 建议：补上「term 让服务器能识别过时信息（比如过期 leader）」这句，
      并把「下台」改成「任期结束」。
    - 原因：README 的「让抽象话落地」——这一节离「只是复述」最近，
      补一句就到位了。

## 事实待核

- [x] 论文把共识问题分解成**三个**子问题 —— *In Search of an Understandable
  Consensus Algorithm (Extended Version)* §5：「Raft decomposes the consensus
  problem into **three** relatively independent subproblems」，随后列出
  Leader election（§5.2）、Log replication（§5.3）、**Safety**（§5.4）。
  论文摘要同样是三样：「Raft separates the key elements of consensus, such as
  leader election, log replication, and safety」。原文 L5 的「两个独立的问题」
  与论文不符。
- [x] RequestVote 的接收方判据 —— 论文 Figure 2：
  「1. Reply false if term < currentTerm (§5.1)
    2. If votedFor is null or candidateId, **and** candidate's log is at least
       as up-to-date as receiver's log, grant vote (§5.2, §5.4)」。
  原文 L43 只覆盖了「term 更大就更新自己的 term」这一半。
- [x] 选举限制的方向与比较规则 —— 论文 §5.4.1：
  「the voter **denies its vote** if its own log is **more up-to-date** than
  that of the candidate」；「Raft determines which of two logs is more
  up-to-date by comparing the **index and term of the last entries** in the
  logs. If the logs have last entries with **different terms**, then the log
  with the **later term** is more up-to-date. If the logs end with the
  **same term**, then whichever log is **longer** is more up-to-date.」
  原文 L51 主客体颠倒，且把「先比 term、再比长度」压成了「比较 term 和
  log index」。
- [x] 复制的一致性检查是「对不上就拒绝」 —— 论文 §5.3：
  「the leader … includes the index and term of the entry in its log that
  immediately precedes the new entries. If the follower does not find an entry
  in its log with the same index and term, then it **refuses** the new
  entries.」Figure 2 的 AppendEntries 接收方五条判据：
  「1. Reply false if term < currentTerm；
    2. Reply false if log doesn't contain an entry at prevLogIndex whose term
       matches prevLogTerm；
    3. If an existing entry conflicts with a new one (same index but different
       terms), delete the existing entry and all that follow it；
    4. Append any new entries not already in the log；
    5. If leaderCommit > commitIndex, set commitIndex = min(leaderCommit,
       index of last new entry)」。
  原文 L77 写成了「local index < leader index 则 append」，与论文相反。
- [x] 提交规则 —— 论文 §5.4.2「Committing entries from previous terms」：
  「a leader knows that an entry **from its current term** is committed once
  that entry is stored on a majority of the servers. However, a leader
  **cannot immediately conclude** that an entry from a previous term is
  committed once it is stored on a majority of servers.」原文全文未提。
- [x] 持久化状态 —— 论文 Figure 2「Persistent state on all servers:
  (**Updated on stable storage before responding to RPCs**)」：
  `currentTerm`（latest term server has seen, initialized to 0 on first boot,
  increases monotonically）、`votedFor`（candidateId that received vote in
  current term, or null if none）、`log[]`。
- [x] 每任期一票及其作用 —— 论文 §5.2：
  「Each server will vote for **at most one candidate in a given term**, on a
  **first-come-first-served** basis (note: Section 5.4 adds an additional
  restriction on votes). The majority rule ensures that **at most one candidate
  can win the election** for a particular term (the Election Safety
  Property in Figure 3).」原文 L49 的表述与论文一致。
- [x] 候选人获胜条件与三种结局 —— 论文 §5.2：
  「A candidate wins an election if it receives votes from a **majority of the
  servers in the full cluster** for the same term」；
  「A candidate continues in this state until one of three things happens:
  (a) it wins the election, (b) another server establishes itself as leader,
  or (c) a period of time goes by with no winner.」
- [x] 选举超时必须随机 —— 论文 §5.2：
  「Raft uses **randomized election timeouts** to ensure that split votes are
  rare and that they are resolved quickly. To prevent split votes in the first
  place, election timeouts are chosen **randomly from a fixed interval
  (e.g., 150–300ms)**.」论文正文亦称
  「In some situations an election will result in a **split vote**. In this
  case the term will end with no leader」。
- [x] 新 leader 先发空 AppendEntries —— 论文 §5.2 的 Leaders 规则：
  「Upon election: send **initial empty AppendEntries RPCs** (heartbeat) to
  each server; repeat during idle periods to prevent election timeouts」。
  原文 L71 的说法方向正确。
- [x] term 作为逻辑时钟的作用 —— 论文 §5.1：
  「Terms act as a **logical clock** in Raft, and they allow servers to
  **detect obsolete information such as stale leaders**. Each server stores a
  current term number, which **increases monotonically** over time.」
  另 §5.1：「Raft divides time into terms of arbitrary length… Terms are
  numbered with consecutive integers. Each term begins with an election…
  If a candidate wins the election, then it serves as leader for the rest of
  the term.」原文 L35-L39 与此一致。
- [x] 参考链接的可达性 —— 实测（2026-11）：`cnblogs.com/xybaby/p/10124083.html`
  返回 200；`sofastack.tech/projects/sofa-jraft/raft-introduction/` 返回 200；
  `segmentfault.com/a/1190000020962361` 与
  `segmentfault.com/a/1190000038170806` 均返回 **410 Gone**。
- [x] raft 目录里的重复文件 —— `docs/cluster/raft协议动态调整quorum.md` 与
  `docs/cluster/raft/raft协议动态调整quorum.md` **逐字节相同**
  （`diff` 无输出，均 36 行，H1 同为「raft协议动态调整quorum」）。
- 原文 L77 里的「leader index」到底指 `prevLogIndex` 还是 `nextIndex` ——
  论文里两个概念都存在（`prevLogIndex` 是新条目之前那条的 index，
  `nextIndex` 是 leader 侧待发的下一条 index），原文没定义，读者无从判断；
  需作者确认原意后再改写。
- 原文 L51「选举人必须知道的比自己的多」的原始意图 —— 按字面不成立，
  推测作者想说的是「候选人的日志必须至少和投票者的一样新」；
  需作者确认后再定稿措辞。
- 本文是否要补 Safety 一节 —— 按现状是一篇概念摘抄；补不补 safety、
  补到什么程度，决定了它是「名词表」还是「实现指南」；
  需作者确认本篇定位后再决定。
- 参考 4（SOFAStack 的 sofa-jraft raft-introduction）与本文各段的对应关系 ——
  原文没在正文里引用它，需作者说明，否则这条参考只是列了个链接。

## 可补的技术证据或产物

- 机制 / 源码入口：论文 Figure 2 是全文的骨架，把它逐条翻译成中文并配上
  实现位置即可：etcd 的 `go.etcd.io/raft/v3`（`raft.go` 里的
  `stepFollower` / `stepCandidate` / `stepLeader`，`log.go` 里的
  `maybeAppend`）或 hashicorp/raft 的 `raft.go`（`RequestVote` /
  `AppendEntries` 的处理入口、`raftLog` 的 `matchTerm` / `maybeAppend`）。
  三条 RPC 的判据都能在代码里找到一一对应的分支。
- 实验或观测：https://raft.github.io/ 上的 RaftScope 浏览器里直接跑一遍
  选主与日志复制（可注入网络分区、看日志冲突如何被修复），
  再配上「换一个实现跑同一场景」的对照——这是零成本可复现的实验，
  也正好补上 DEP-00 缺的「可复现证据」。
- 工程取舍：把 Raft 与 Paxos 的差别落到具体机制上（论文摘要里那句
  「Strong leader: log entries only flow from the leader to other servers」，
  以及 Raft 的 joint consensus 成员变更 vs Paxos 的其它做法）；
  再写清 Raft 不解决什么——**读一致性的线性化、拜占庭故障、外部一致性
  与时钟假设**，把这些交给读者做选型。
- 结尾清单或下一篇链接：三张表（状态迁移表 / 两种 RPC 的接收方判据 /
  持久化三件套）+ 一份「实现前必须想清楚的十个问题」清单；
  再链到同目录 `raft协议动态调整quorum.md`、`c-raft分布式存储方案.md`，
  以及已合入的 `docs/cluster/分布式一致性协议.md`。

## 已确认的改动

- （本轮只出审校记录，正文改动待确认后执行。）
