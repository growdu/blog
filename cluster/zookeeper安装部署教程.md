# zookeeper使用说明文档

## 安装部署

需对每一台zookeeper集群节点做如下操作：

- 安装openjdk并设置JAVA_HOME

  ```shell
  sudo apt-get install openjdk-8-jdk
  export JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64
  ```

- 下载zookeeper

  ```shell
  wget https://mirrors.tuna.tsinghua.edu.cn/apache/zookeeper/stable/apache-zookeeper-3.6.3-bin.tar.gz
  ```

  <font color="red">注意：下载时需下载带bin的包，否则会在启动时报找不到主类的错。</font>

- 安装zookeeper

  ```shell
  cd /opt
  tar -xvf apache-zookeeper-3.6.3-bin.tar.gz
  export ZOOKEEPER_HOME=/opt/apache-zookeeper-3.6.3-bin
  export PATH=$PATH:$ZOOKEEPER_HOME/bin
  ```

- 配置zookeeper

  ```shell
  cd /opt
  mkdir data
  mkdir logs
  cd /opt/apache-zookeeper-3.6.3-bin/conf
  vim zoo.cfg
  ```

  zoo.cfg的文件内容如下：

  ```shell
  tickTime=2000
  initLimit=10
  syncLimit=5
  dataDir=/opt/data
  dataLogDir=/opt/logs
  clientPort=2181
  server.1=ip1:2888:3888
  server.2=ip2:2888:3888
  server.3=ip3:2888:3888
  ```

  对每个节点分别执行如下命令：

  ```shell
  # 对2,3节点分别换成2和3
  echo "1" >> /opt/data/myid
  ```

- 启动

  ```shell
  cd /opt/apache-zookeeper-3.6.3-bin/bin
  ./zkServer.sh start
  ```

- 查看状态

  ```shell
  cd /opt/apache-zookeeper-3.6.3-bin/bin
  ./zkServer.sh status
  ```

- 连接服务端

  ```shell
  cd /opt/apache-zookeeper-3.6.3-bin/bin
  ./zkCli.sh -server ip1:2181
  ```

## zookeeper基础概念

> ZooKeeper 是一个开源的分布式协调服务，由雅虎创建，是 Google Chubby 的开源实现。
>
> 分布式应用程序可以基于 ZooKeeper 实现诸如数据发布/订阅、负载均衡、命名服务、分布式协调/通知、集群管理、Master 选举、配置维护，名字服务、分布式同步、分布式锁和分布式队列等功能。
>
> 它是一个为分布式应用提供一致性服务的软件，提供的功能包括：配置维护、域名服务、分布式同步、组服务等。

> ZooKeeper使用共享存储实现对分布式系统的协调。其实共享存储，分布式应用也需要和存储进行网络通信。网络通信是分布式系统并发设计的基础。

- znode

在ZooKeeper中，任务的分配、完成情况，等共享信息被保存在一个个数据节点上，这些节点被称为znode。它采用了类似文件系统的层级树状结构进行管理。znode节点存储的数据为字节数组。存储数据的格式zookeeper不做限制，也不提供解析，需要应用自己实现。

znode支持如下操作：

```shell
create /path data

    创建一个名为/path的znode，数据为data。

delete /path

    删除名为/path的znode。

exists /path

    检查是否存在名为/path的znode

set /path data

    设置名为/path的znode的数据为data

get /path

    返回名为/path的znode的数据
```

- 观察与通知

> zookeeper采用了通知的机制。客户端向zookeeper请求，在特定的znode设置观察点（watch）。当该znode发生变化时，会触发zookeeper的通知，客户端收到通知后进行业务处理。观察点触发后立即失效。所以一旦观察点触发，需要再次设置新的观察点。

- 版本

> 每个znode都有版本号，随着每次数据变化自增。setData和delete，以版本号作为参数，当传入的版本号和服务器上不一致时，调用失败。当多个zookeeper客户端同时对一个znode操作时，版本将会起到作用，假设c1，c2同时往一个znode写数据，c1先写完后版本从1升为2，但是c2写的时候携带版本号1，c2会写入失败。

- 法定人数

> zookeeper服务器运行于两种模式：独立模式和仲裁模式（集群）。仲裁模式下，会复制所有服务器的数据树。但如果让客户端等待所有复制完成，延迟太高。这里引入法定人数概念，指为了使zookeeper集群正常工作，必须有效运行的服务器数量。同时也是服务器通知客户端保存成功前，必须保存数据的服务器最小数。例如我们有一个5台服务器的zookeeper集群，法定人数为3，只要任何3个服务器保存了数据，客户端就会收到确认。只要有3台服务器存活，整个zookeeper集群就是可用的。

- 会话

> 客户端对zookeeper集群发送任何请求前，需要和zookeeper集群建立会话。客户端提交给zookeeper的所有操作均关联在一个会话上。当一个会话因某种原因终止时，会话期间创建的临时节点将会消失。而当当前服务器的问题，无法继续通信时，会话将被透明的转移到另外一台zookeeper集群的服务器上。

## ZAB协议

ZooKeeper 保证 **分布式系统数据一致性的核心算法就是 ZAB 协议**（ZooKeeper Atomic Broadcast，原子消息广播协议）。其主要依赖于 ZAB 协议的 **消息广播，崩溃恢复和数据同步** 三个过程。

### 消息广播

1. 一个事务请求（Write）进来之后，Leader 节点会将写请求包装成 Proposal 事务，并添加一个全局唯一的 64 位递增事务 ID，也就是 Zxid（消息的先后顺序就是通过比较 Zxid）；
2. Leader 节点向集群中其他节点广播 Proposal 事务，Leader 节点和 Follower 节点是解耦的，通信都会经过一个 FIFO 的消息队列，Leader 会为每一个 Follower 节点分配一个单独的 FIFO 队列，然后把 Proposal 发送到队列中；
3. Follower 节点收到对应的 Proposal 之后会把它持久到磁盘上，当完全写入之后，发一个 ACK 给 Leader；
4. 当 Leader 节点收到超过半数 Follower 节点的 ACK 之后（Quorum 机制），会提交本地机器上的事务，同时开始广播 commit， Follower 节点收到 commit 之后，完成各自的事务提交。

### 崩溃恢复

如果在同步过程中出现 Leader 节点宕机，会进入崩溃恢复阶段，重新进行 Leader 选举，崩溃恢复阶段还包含数据同步操作，同步集群中最新的数据，保持集群的数据一致性。

整个 ZooKeeper 集群的一致性保证就是在上面两个状态之前切换，当 Leader 服务正常时，就是正常的消息广播模式；当 Leader 不可用时，则进入崩溃恢复模式，崩溃恢复阶段会进行数据同步，完成以后，重新进入消息广播阶段。

### 数据同步

崩溃恢复完成选举以后，接下来的工作就是数据同步，在选举过程中，通过投票已经确认 Leader 节点是最大 Zxid 的节点，同步阶段就是利用 Leader 前一阶段获得的最新 Proposal 历史同步集群中所有的副本。

### zxid

> Zxid 是 Zab 协议的一个事务编号，Zxid 是一个 64 位的数字，其中低 32 位是一个简单的单调递增计数器，针对客户端每一个事务请求，计数器加 1；而高 32 位则代表 Leader 周期年代的编号。
>
> 每当有一个新的 Leader 选举出现时，就会从这个 Leader 服务器上取出其本地日志中最大事务的 Zxid，并从中读取 epoch 值，然后加 1，以此作为新的周期 ID。总结一下，高 32 位代表了每代 Leader 的唯一性，低 32 位则代表了每代 Leader 中事务的唯一性。

### ZAB节点选举算法

Zab 中的节点有三种状态，伴随着的 Zab 不同阶段的转换，节点状态也在变化：

- following

  当前节点是follower，遵从leader的命令

- looking/eletion

  当前节点处于选举投票状态

- leading

  当前节点是leader，负责协调和分配工作

> 选举算法流程如下：
>
> **1.各个节点变更状态，变更为 Looking**
>
> - ZooKeeper 中除了 Leader 和 Follower，还有 Observer 节点，Observer 不参与选举， Leader 挂后，余下的 Follower 节点都会将自己的状态变更为 Looking，然后开始进入 Leader 选举过程。
>
> **2.各个 Server 节点都会发出一个投票，参与选举**
>
> - 在第一次投票中，所有的 Server 都会投自己，然后各自将投票发送给集群中所有机器，在运行期间，每个服务器上的 Zxid 大概率不同。
>
> **3.集群接收来自各个服务器的投票，开始处理投票和选举**
>
> - 处理投票的过程就是对比 Zxid 的过程，假定 Server3 的 Zxid 最大，Server1判断Server3可以成为 Leader，那么Server1就投票给Server3，判断的依据如下：首先选举 epoch 最大的，如果 epoch 相等，则选 zxid 最大的，若 epoch 和 zxid 都相等，则选择 server id 最大的，就是配置 zoo.cfg 中的 myid；在选举过程中，如果有节点获得超过半数的投票数，则会成为 Leader 节点，反之则重新投票选举。

## zookeeper的读写操作

> - quorum 是zookeeper的一种投票方式，当发起proposal时，只要多数派同意，即可生效。多数派指的是，意思是至少过半的节点响应，才可以进行下面的操作。quorum数 = 节点数/2 +1
> - 为了保证事务的顺序一致性，ZooKeeper采用了递增的事务id号（zxid）来标识事务，所有提议（proposal）都有zxid
> - 每次事务的提交，必须符合quorum多数派
> - leader选举投票vote的信息结构为(sid，zxid)，sid是节点的id，zxid是事务id。选举leader的规则是zxid大的server胜出，若zxid相等，sid大的胜出。zxid数值大，说明是最新更新。

### zookeeper读操作

> 读操作比较简单，客户端与某个zookeeper服务建立session，从这个服务器读取数据，返回给客户端，最后关闭session。

### zookeeper写操作

> 1. 客户端向zookeeper集群写入数据，与一个follower建立Session连接，假设为follower01
>
> 2. follower01将写请求转发给leader
>
> 3. leader收到消息后，把本次写入操作，转化为事务proposal提案发送给每个follower，每个follower先记录下要本次写入操作
>
> 4. 超过半数quorum（包括leader自己）发回反馈，则leader提交commit提案，leader执行写入操作
>
> 5. leader通知所有follower，也commit提案，follower各自在本地写入
>
> 6. follower01响应客户端

## zookeeper如何处理“脑裂”

> 1. 首先我们搞清楚，脑裂是什么？
>
> 脑裂简单来说，就是集群中出现了两个leader
>
> 2. 是如何出现的？
>
> 网络通信故障，集群被分为了两部分。
>
> 假设我们有五个节点，其中三台可以正常通信，而另外两台因为网络原因，无法与别的机器通信，所以，整个集群被分割成了两部分。两部分同时进行leader选取，自然出现了两个leader。
>
> 3. zookeeper是如何解决的？
>
> 前面有提到过，zookeeper提交的每次proposal，都至少需要过半的节点响应，操作才会进行下去。
>
> 当发生网络分区后，三台节点的leader，我们称之为leader1。而因为网络原因分割出去的两个节点，选举出来的leader，我们称之为leader2。
>
> 这时有两个客户端，c1和c2，c1请求leader1写入一个znode为1。c2请求leader2写入一个znode为2。
>
> c1的请求，leader1向另外两个节点发出proposal，两个节点响应加上leader本身，quorum = 3，符合多数派原则，则操作生效，同步到另外两个节点。
>
> c2的请求，leader2往另一个节点发出proposal，quorum = 2，不符合多数派原则，操作则不生效。
>
> 所以，因为网络原因导致的两个leader，只有一个操作会生效。
>
> 当网络修复后，leader1的zxid肯定比leader2大，leader2变为follower状态，leader1同步操作。
> ————————————————
> 转载自CSDN博主「甜_tian」的原创文章。
> 原文链接：https://blog.csdn.net/weixin_39033058/article/details/118222322

# reference

1. https://cloud.tencent.com/developer/article/1333864
2. https://blog.csdn.net/liyiming2017/article/details/83035157
3. https://segmentfault.com/a/1190000022683594
4. https://www.cnblogs.com/zz-ksw/p/12786067.html
4. https://blog.csdn.net/weixin_39033058/article/details/118222322
4. https://cloud.tencent.com/developer/article/1050471