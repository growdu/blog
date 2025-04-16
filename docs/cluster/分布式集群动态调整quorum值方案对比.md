# 数据库分布式集群动态调整quorum值方案对比

## 背景

**在数据库分布式集群中，在半数以上节点宕机后，期望剩下的节点机器仍然能提供服务**。

举例来说，一个包含5个节点的数据库集群，当集群挂掉3个节点后，因为不符合半数以上节点正常原则，数据库集群将无法对外提供服务，需要人为介入。但在数据库的实际使用场景中，我们期望即使只剩下一个节点也能对外提供服务。实际上，当5个集群节点挂掉2个节点后，应将剩下3个节点看成一个3节点的集群，动态调整对应的quorum值，并允许再挂掉一个节点。基于该中情况对分布式集群选举算法提出了动态调整quorum值的要求。

当前业界主流的分布式协议主要有raft协议和totem协议，并且业界均有相关协议成熟的开源实现，如jraft是raft协议的开源实现，corosync是totem协议的开源实现。我们将对照这两种协议的特点及相关开源实现，来选择动态调整quorum值的方案。

备注：需要特别说明的raft协议和totem协议是算法和通信协议，是分布式集群实现的理论基础，jraft和corosync是框架实现，pacemaker+corosync是其中一种解决方案。

## 实现方案

要达到动态调整quorum值，当前有两种实现方式：

1. 修改quorum；
2. 修改集群节点

### 修改quorum

使用修改quorum动态调整quorum的算法如下（假设集群节点总数为n，采用quorum机制投票半数原则进行选举）：

1. 初始化时expect_vote为n，选举leader时需要的quorum为（expect_vote/2）+ 1；
2. 当在线节点数与quorum相等时，需启动动态quorum定时器；
3. 当quorum定时器超时时，此时需要将expect_vote修改为quorum，quorum值修改为（expect_vote/2）+ 1；
4. 当leader节点挂掉时，根据quorum机制选举新的leader，选举leader时需要的quorum为（expect_vote/2）+ 1；；
5. 当有节点新加入时，计算在线节点数，则更新expect_vote为当前节点数；此时需要将expect_vote修改为quorum，quorum值修改为（expect_vote/2）+ 1；
6. 当集群在线节点数为2时，若再有集群挂掉，则集群将不提供服务；

**corosync当前版本已支持该方式。**

### 修改集群节点

修改集群节点的算法与修改quorum流程相似，与其不同的是修改集群节点通过移除或者添加节点的方式来触发expect_vote和quorum值改变，而不是在定时器超时后直接修改quorum。

**corosync和raft相关开源实现均未支持该方式。但raft的开源实现jraft提供了从集群中动态添加/移除节点的接口，可基于此进行二次开发。**

总结起来，当前有两种实现方式：

1. 基于corosync直接修改quorum实现，不需要修改开源代码；
2. 基于jraft动态添加删除节点实现，需修改开源代码；

## 方案对比

### [jraft](https://github.com/sofastack/sofa-jraft)

- jraft基于faft协议实现，其底层通信采用rpc机制，节点之间采用多播通信，且节点之间多播通信不会阻塞
- jraft仅仅实现了协议框架，要将其运用在项目中需要项目集成，其使用java语言编写，与java生态兼容性好。
- jraft参考自百度使用c++编写的[braft](https://github.com/baidu/braft)，braft功能与jraft基本一致，对C++兼容性好，但c语言不兼容
- 其底层rpc框架使用[sofa-bolt](https://github.com/sofastack/sofa-bolt)，当其仅有java、js、c++版本，对C语言兼容性不好。
- jraft开源实现仅提供动态添加/删除节点的接口，要实现动态修改quorum值需要修改开源代码，添加多数节点挂掉后修改节点或quorum的机制
- jraft提供了开发框架，需将框架集成到数据库系统中，定制化程度高，但未提供可直接搭配数据库的解决方案

### [corosync](https://github.com/corosync/corosync)

- corosync基于totem协议实现，其底层通信采用基于udp的令牌环机制实现，在节点间多播通信时需要等待token，节点之间多播通信会阻塞
- corosync使用c语言编写，对c语言兼容性好
- corosync当前版本通过LSM特性支持动态调整quorum，无需修改代码，通过配置即可实现
- corosync是一个开发框架，可作为第三方库引入，定制化程度高
- 开源社区围绕corosync已形成pacemaker+corosync+服务的解决方案，数据库可作为一种服务直接使用该解决方案而无需任何开发，仅需修改相关配置文件即可