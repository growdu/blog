# raft协议动态调整quorum

## raft协议基础

## jraft实现

## raft协议动态调整quorum

按照当前raft协议实现，当n个节点的集群超过n/2个节点宕机时，集群将无法提供服务。如5个节点的集群，当有3个节点宕机时，集群将无法提供服务。

假设当前集群5个节点，先挂掉2个节点，剩余3个因为quorum机制继续提供服务；此时当节点再挂掉1个时，剩余2个节点，小于（5/2+1）,因而无法提供服务。而实际场景要求该情况仍然正常提供服务。因而针对该场景对动态动态调整quorum提出了需求。

### 动态调整quorum

### 调整expect_vote和quorum

动态调整quorum的算法如下（假设集群节点总数为n（n为基数），采用quorum机制投票半数原则进行选举）：

1. 初始化时expect_vote为n，选举leader时需要的quorum为（expect_vote/2）+ 1；
2. 当在线节点数与quorum相等时，需启动动态quorum定时器；
3. 当quorum定时器超时时，此时需要将expect_vote修改为quorum，quorum值修改为（expect_vote/2）+ 1；
4. 当leader节点挂掉时，根据quorum机制选举新的leader，选举leader时需要的quorum为（expect_vote/2）+ 1；；
5. 当有节点新加入时，计算在线节点数，则更新expect_vote为当前节点数；此时需要将expect_vote修改为quorum，quorum值修改为（expect_vote/2）+ 1；
6. 当集群在线节点数为2时，若再有集群挂掉，则集群将不提供服务；

### 动态添加/移除节点

- addPeer
- removePeer

### 待解决问题

1. 剩余2节点时如何处理；

2. 有仲裁设备时如何处理；

   仲裁设备优先级高。