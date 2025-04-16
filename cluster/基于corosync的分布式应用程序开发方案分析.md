# 基于corosync的分布式应用程序开发方案分析

## 0 结论

综上所述，并结合实际使用场景中遇到的各种问题，可得出如下结论：

<font color="red">1. corosync保证的数据一致性对application没用</font>
<font color="red">2. corosync的机器独占性导致corosync无法共用仲裁，不适用于多套集群</font>
<font color="red">3. corosync-qnetd的共用仲裁解决方案会引入qnetd的单点故障问题，需考虑qnetd的高可用性</font>
<font color="red">4. corosync采用udp广播通信，会损耗一些网络带宽，不适用与节点数较多的集群</font>

## 1. 概述

当基于corosync进行应用层开发时，一般使用cpg分组来进行数据收发，这种情况下我们的程序会有两个进程：

- corosync进程
- 基于cpg的应用进程

我们将corosync进程称作process进程，基于cpg的应用进程称为application进程。数据先通过网络在process进程中传输，保证各个process进程都能收到数据，各process进程收到数据后再通过本地ipc通信将数据传递到应用层。



## 2. 数据收发及数据一致性

### 2.1 现状

数据收发分为两个步骤：

1. 数据先传输到process进程，通过totem协议（令牌环协议）保证每个存活的节点都收到数据（保证顺序，数据按顺序到达）；
2. 当所有的process进程都确认数据收到后，process通过本地ipc通信将数据传输到application，由application进行写入；

<font color="red">由上可知，corosync只保证process进程的数据一致性，无法保证application进程的数据一致性。因为process无法保证application数据一定处理成功，application进程处理失败或某条数据未处理时process进程不会将该条数据重传到application进程。</font>

process进程不保证application数据写入成功， 当某个application进程在接收数据挂死后将导致数据丢失。因而在使用corosync进行数据收发时，需要由application再次对数据进行确认，同时application同样需要对数据进行重传，以保证接收失败的application进程能收到完整数据。

### 2.2 解决方案

<font color="red">appliction实现数据确认机制：</font>

1. application需要维持一套集群状态，包括quorum（多数派），master（领导节点，读取写入权限）；
2. application进程只有master具有读取和写入权限，非master节点收到数据请求时需要先转发到master，由master进行数据操作；
3. master节点写入时，需要其他节点写入进行确认，只有超过半数节点写入成功后才认为本次写入成功；

<font color="red">第三点未实现可能会导致极端情况下造成数据丢失：</font>

如三节点集群，节点1和节点2在处理旧数据时卡住，节点3为master且收到新数据写入请求，此时节点3会直接将数据写入。若此时节点3在写入数据后挂死，节点1和节点2重新选出master继续服务，此时就导致了数据丢失。

### 2.3 由此带来的问题

application实现数据确认机制，相当于在应用层又实现了一套分布式数据确认机制。相当于我们完全没有用到corosync的数据一致性功能，因为corosync无法保证application数据的一致性，corosync在数据层面仅仅实现了网络通信功能。我们将corosync换成通用的网络通信接口同样能实现类似的功能。



## 3. 投票机制

<font color="red">corosync与机器强绑定，一台机器只能运行一个corosync节点，且一个corosync节点只能属于一个集群，不能被多个集群共用。</font>

当部署多套集群时，为了得到更高的可用性，往往会设置一些仲裁节点，这些仲裁节点仅具有投票功能。我们可以采用在集群中增重corosync节点来作为仲裁，但每增加一个仲裁corosync节点就需要多部署一台机器，多个集群需部署更多的仲裁机器，无法共用，相当于浪费了机器资源。

### 3.1 解决方案

corosync官方提供的corosync-qdevice和corosync-qnetd的公共仲裁解决方案，允许部署一个qnetd服务器进程，为多套集群提供仲裁服务。

qnetd支持两种算法：

- 五五开算法（一般适用于偶数节点集群）

  主要是在集群出现两个网络分区，且分区节点数一致时，辅助决定哪个分区胜出。

- LMS算法

  主要是实现集群只剩下一个节点时也能提供服务，此时qnetd占用更高的投票权重。

### 3.2 由此带来的问题

<font color="red">corosync官方提供的corosync-qdevice和corosync-qnetd的公共仲裁解决方案，但在集群节点上会多出一个corosync-qdevice进程，同时qnetd占据更高的投票权重，存在qnetd单点故障问题。</font>

`corosync-qdevice`和`corosync-qnetd`组合的公共仲裁解决方案，需要在corosync运行的节点上再运行corosync-qdev，同时需要一台额外的机器来部署qnetd，此时虽然会增加集群的管理复杂度，但多个集群可以共有qnetd，可以节约机器资源。

qnetd作为公共仲裁时，若要支持5节点集群，还剩下2个几点也能正常工作，此时需要选用LMS算法，但使用此算法时，qnetd会占用更高的投票权重。此时若qnetd出现故障时，5节点集群一个都不能挂死才能正常服务，qnetd存在单点故障问题。此时又会引入qnetd的高可用性问题，比如qnetd的主备冗余模式。



## 4. 性能

corosync的process进程采用udp广播通信，即一条信息发出，正常情况下所有的节点都会接收到，而不管节点是否需要该消息。我们基于cpg分组的application通过process进行数据收发，不管我们的消息发往哪个节点，都会往所有节点发送，且保证每个节点都收到为止。

对于客户端的查询请求来说，实际上我们最多只需要访问两个节点就可以获取到数据：

1. 客户端发出查询请求，集群中一个节点收到请求，若该节点是master，直接响应数据，此时只需要访问一个节点；
2. 客户端发出查询请求，集群中一个节点收到请求，若该节点不是master，将请求转发给master，master收到请求后再响应，本节点再转发给客户端，此时需要访问两个节点；

对于客户端的增删改请求来说，最终需要访问所有节点，但返回给客户端响应时，只要半数以上节点响应就可以返回给客户端，而不需要所有节点都确认。

<font color="red">因而，每次数据发送都需要所有节点收到会占用网络带宽，当网络状况极差时，客户端很容易响应超时。导致客户端访问数据延迟高。</font>

### 4.1 解决方案

按照前面的分析，对客户端查询请求进行单独处理，设计单独的查询api。当收到客户端的查询请求后，不使用process的通信机制；而是重新增加各节点之间的socket通信（TCP），这样一次查询最多只会发起两次网络请求。对于现有的使用场景来说，绝大数时候使用的是查询接口，对性能和可用性会有较大提升。

至于增删改接口，若性能满足可暂时不做修改。

### 4.2 由此带来的问题

- 需要增加一套集群间的通信机制，使各节点能够单点通信（一对一）
- 当增加了集群间节点的通信机制后，似乎corosync没有太大的作用了（有了通信就可以加心跳，有了心跳就可以计算quorum）


