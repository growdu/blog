# c-raft分布式存储方案

## raft协议详解

RAFT中将节点状态分为：

- Leader：接收Client的请求，并进行复制，任何时刻只有一个Leader
- Follower：被动接收各种RPC请求
- Candidate：用于选举出一个新的Leader

RAFT中Follower长时间没有接受到心跳就会转为Candidate状态，收到多数投票应答之后可以转为Leader，Leader会定期向其他节点发送心跳。当Leader和Candidate接收到更高版本的消息后，转为Follower。

### leader选举

系统中只会存在一个 leader, 如果一段时间内没有 leader, 那么大家通过选举的方式选出 leader. leader 不停的向 follower 发出心跳，表明 leader 的存活状态， 如果l leader 故障，follower 会切换成 candidate 选举出新 leader。

1. 所有节点启动时都是 follower  状态， 在 一段时间如果没有收到来自 leader 的心跳，follower 切换为 candidate , 并发起选举。
2. 如果收到了 majority 的选举票（包含自己的一票），那么切换为 leader 状态。
3. 如果发现其他节点比自己更新，则主动切换为 follower

RAFT中将时间划分到Term，用于选举，标示某个Leader下的Normal Case，每个Term最多只有一个Leader，某些term可能会选主失败而没有leader（未达到多数投票应答而超时）。选举过程中，每个Candidate节点先将本地的Current Term加一，然后向其他节点发送RequestVote请求，其他节点根据本地数据版本、长度和之前选主的结果判断应答成功与否。具体处理规则如下：

1. 如果now – lastLeaderUpdateTimestamp < elect_timeout，忽略请求
2. 如果req.term < currentTerm，忽略请求。
3. 如果req.term > currentTerm，设置req.term到currentTerm中，如果是Leader和Candidate转为Follower。
4. 如果req.term == currentTerm，并且本地voteFor记录为空或者是与vote请求中term和CandidateId一致，req.lastLogIndex > lastLogIndex，即Candidate数据新于本地则同意选主请求。
5. 如果req.term == currentTerm，如果本地voteFor记录非空并且是与vote请求中term一致CandidateId不一致，则拒绝选主请求。
6. 如果lastLogTerm > req.lastLogTerm，本地最后一条Log的Term大于请求中的lastLogTerm，说明candidate上数据比本地旧，拒绝选主请求。

上面的选主请求处理，符合Paxos的"少数服从多数，后者认同前者"的原则。按照上面的规则，选举出来的Leader，一定是多数节点中Log数据最新的节点。

### 选举过程

follower 在 timeout 时间内，没有收到来自 leader 的心跳，则会发起选举：

- 增加节点本地的 current term, 切换为 candidate 状态
- 投自己一票
- 并行的发送给其他节点 RequestVotes RPCs
- 等待其他节点的回复
  1. 收到了 大多数选票（majority ),那么赢得选举，切换状态为 leader
  2. 被告知别人已经当选，则切换为 follower
  3. 一段时间还是没有收到 majority 的投票结果，保持 candidate 状态，重新发出选举。
- 每个任期，一个节点只能投票一次
- 候选人知道的信息不能比自己少
- fisrtcome- first-serverd 先到先得

### 流复制

一旦选举出了一个leader，它就开始负责服务客户端的请求。每个客户端的请求都包含一个要被复制状态机执行的指令。leader首先要把这个指令追加到log中形成一个新的entry，然后通过AppendEntries RPCs并行的把该entry发给其他servers，其他server如果发现没问题，复制成功后会给leader一个表示成功的ACK，leader收到大多数ACK后应用该日志，返回客户端执行结果。

当系统有了leader, 系统应用进入了工作区， 客户端的一切请求会发送到 leader, leader 来调度这些并发请求到顺序，并且保证 leader 和 follower 状态的一致性。

raft 的做法就是，将这些请求的顺序告诉 follower, leader 和 follwer 以相同的顺序来执行这些请求， 保持状态一致。所谓强一致性， 并不是指集群中任意时刻状态都一致。而是指一个目标， 让一个分布式系统看起来只有一个数据副本， 并且读写都是原子的， 这样应用层可以忽略系统多个数据间的同步问题。

共识算法，就是来保证一致性的。共识算法保证在小部分节点故障的 <=(N-1)/2 节点故障的情况下，系统仍然可以对外提供服务。

> 共识算法，是通过复制状态机来实现。所有节点从同一个状态 state 出发，经过相同的 log, 最终达到一致的状态 state.

**相同的初始状态+相同的输入 = 相同的结束状态。**

Raft 负责保证集群所有节点 log 一致性。leader 具有较强的领导力， 所有 log 都必须交给 leader 节点处理，并由 leader 复制给其他节点。这个过程叫做日志复制。

日志复制机的流程：

leader 选举出来后，就承担了领导整个集群的责任，开始接受客户端请求，并将操作包装成日志，发送给其他节点。

- leader 为客户端提供服务， 客户端的每个请求都包含一条被状态复制机执行的指令。
- leader 把该指令作为一个新的日志附加到自身的日志集合。然后向其他节点发起附加请求条目（AppendEntries RPC)。来要求其他节点将日志附加到自己的本地日志集合中。
- 当这条日志确保被安全复制，即 （N/2 +1) 节点有复制后，leader 将该日志 apply 到他本地的状态机中，然后把操作成功的结果返回给客户端。

### 安全性

#### 对选举的限制

**每个 candidate 必须在 RequestVote RPC 中携带自己的最新日志，如果 follower 发现candidate 日志还没有自己的新， 那么就拒绝投给该 candidate**

也就是说 candidate 想要赢得选举，必须得到大多数节点的投票，那么它的日志一定不能落后大多数节点。又因为一条日志只有被复制到大多数节点才能被 COMMIT, 也就是说 赢的选举的 candidate 一定拥有所有 commited 节点的日志。

#### 对提交的限制

除了对选举限制外，还需要对 commit 增加一些限制。

> 当 leader 得知某条日志被集群过半的节点复制成功时，就可以进行 commit，committed 日志一定最终会被状态机 apply。

leader 并不能随时随地 commit 旧任期的留下的日志，即便旧任期已经复制到大部分节点。

Leader 只允许 commit 包含当前 term 的日志。

## raft协议优化

当某个节点a长时间没有回复leader的心跳报文时，leader会向其他节点发送移除该节点的报文，当半数以上节点确认移除该节点时，各节点均移除该节点，达到动态调整节点的目的。

# reference

1. https://cloud.tencent.com/developer/article/1826594
