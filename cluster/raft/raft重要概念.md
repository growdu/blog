# raft重要概念

## 执行流程

raft将分布式一致性问题分解成两个独立的问题，分成两个大的步骤来进行数据处理。

两个独立问题分别为：

- leader election

- log replication

对应的两个步骤分别为：

- 先投票选出leader

- leader存在后，由leader负责协调数据写入，当leader离开时，回到选leader步骤

## 节点与角色

在raft中每一个进程是一个节点，节点用节点id区分。节点有角色状态，并且在通信流程中，节点角色会不断发生变化。

节点角色状态分为如下三种：

- follower

- candidate

- leader

节点启动时处于follower状态，并且每隔follower状态的节点都会等待leader状态节点的心跳报文，若有leader的话会定时收到心跳报文；若在一段时间内没有收到leader心跳报文，此时将会发生状态变更，follower切换到candidate状态，发起选举投票。投票过程中，若某节点获得大多数节点的投票，则该节点将从candidate转变为leader，而其他节点收到leader的消息后则从candidate转变为follower。

## term

term在raft中作为逻辑时钟存在，Raft 把时间分割成任意长度的任期，用term来标识每一届leader的任期，这样可以保证在一个任期内只有一个Leader。

term是一个递增的数值，从选举开始，若在规定时间内选出leader，则term就是leader的工作期；若在规定时间未选出leader，将会开始新一轮选举，此时term将会增加。

当leader工作一段时间后下台，其他follower节点因心跳超时将会进入新一轮选举，此时term也会增加。

Candidate发起选举时就将自己的term加1，然后发起投票请求；

收到投票请求的节点比较请求的term和自己的term，如果请求的term比自己的大，则更新自己的term；

## leader election

选举的限制条件如下：

- 同一任期内每个节点最多只能投一票，先来先得

- 数据最新才能获取到投票（选举人必须知道的比自己的多，需要比较term和log index）

当follower与leader的心跳超时时，就会触发选举，流程如下：

1. 增加本地的current term,切换到candidate状态

2. 投自己一票

3. 并行给其他节点发送*RequestVote*

4. 等待其他节点回复

5. 根据回复结果进行状态变更
   
   1. 收到大多数节点的投票（包含自己的一票），则赢得选举，成为leader，并广播所有节点本节点已当选leader
   
   2. 被告知别人已当选，切换到follower
   
   3. 选举超时，发起新一轮选举

leader发送的第一个`AppendEntries`RPC往往是一个空的包（不包含日志数据的心跳包，大部分时候是空的，如果当选leader和发送`AppendEntries`之间leader接收了新的数据，那么这部分新数据也会发送）。

当节点收到leader的第一条消息时：

1. 比较local term与leader term，若local term>leader term，拒绝接受日志；若local term<leader term，更新local term，并append log；

2. 如果local term==leader term，则需要比较local index和leader index；若local index\<leader index，则append log；若local index\>leader index,

# reference

1. [一文搞懂Raft算法 - xybaby - 博客园](https://www.cnblogs.com/xybaby/p/10124083.html)

2. [Raft算法同步过程 - 个人文章 - SegmentFault 思否](https://segmentfault.com/a/1190000020962361)

3. [分布式 - Raft算法之选举篇 - 个人文章 - SegmentFault 思否](https://segmentfault.com/a/1190000038170806?utm_source=sf-similar-article)

4. https://www.sofastack.tech/projects/sofa-jraft/raft-introduction/
