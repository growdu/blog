# corosync-qdevice详解

corosync-qdevice是corosync集群工具的一个组件，用于提供第三方仲裁服务。corosync-qdevice需与corosync-qnetd和corosync一起使用，无法单独运行。

- 允许corosync在偶数节点分裂为两个相似的部分后仲裁选择出一方继续提供服务

- 允许corosync在运行到剩下最后一个节点仍能够提供服务

## corosync-qdevice架构

### corosync节点

部署运行corosync和corosync-qdevice服务的节点。属于集群节点，提供集群通信服务，参与集群的各项决策任务。

corosync需先运行，再运行corosync-qdevice，corosync和corosync-qdevice共用一份配置。corosync运行的时候会将指定路径的corosync.conf的配置读取到cmap中，corosync-qdevice运行时通过连接corosync的cmap来获取qdevice相关的配置。

### corosync-qnetd节点

部署运行corosync-qnetd服务的节点。不属于集群节点，只负责在集群中有节点挂掉时参与投票，辅助选择quorate一方的集群。

corosync-qnetd需要在corosync和corosync-qdevice时运行之前部署好，一般选择与corosync节点在不同的物理机器上。为了高可用性，可选择两台机器部署两个corosync-qnetd的服务。

corosync-qnetd可以给多个集群提供投票服务，根据集群的名字进行区分不同的集群。

### 整体运行状态

- corosync-qnetd作为corosync-qdevice的服务端运行

- corosync-qdevice和corosync一起运行，corosync-device作为客户端会在启动时连接corosync-qnetd

- 当有集群节点变动时，corosync-qdevice会和corosync-qnetd通信，并根据设定的投票规则参与投票

## corosync-qdevice配置

corosyn-qdevice的配置在corosync.conf的quorum模块中，通过配置quorum.device相关项来配置。

```shell
quorum {
         provider: corosync_votequorum
         device {
           votes: 1
           model: net
           net {
             tls: on
             host: qnetd.example.org
             algorithm: ffsplit
           }
           heuristics {
             mode: sync
             exec_ping: /bin/ping -q -c 1 "www.example.org"
             exec_test_txt_exists: /usr/bin/test -f /tmp/test.txt
           }
       }
```

- votes
  
  qnetd的票数。

- host
  
  qnetd运行的ip。

- port
  
  qnetd运行的端口。

- algorithm
  
  选择的启发式算法，可选ffsplit和lsm。
  
  - ffsplit 一般用偶数节点会分割为相似的两部分的情况
  
  - lsm 一般用于只剩下一个节点也能提供服务

- heuristic
  
  启发式算法

## corosync-qnetd配置

corosync-qnetd不需要配置文件，直接以命令行参数指定相关配置运行。

```shell
# -l 指定监听地址，默认全地址
# -p 指定监听端口，默认5403
# -s 是否开启tls，默认开启
# -f 后台运行
corosync-qnetd -l host -p port -s on/off -f
```
