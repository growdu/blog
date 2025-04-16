# corosync-qdevice使用

qdevice要用途是让群集能够承受大于标准仲裁规则所允许的节点故障数量。在分布式一致性协议中，基于多数派quorum的协议解决脑裂等问题，因而当集群存活节点挂死超过一半时，集群将无法对外提供服务。qdevice提供仲裁机制，使集群在多数节点挂掉后仍然能提供服务。典型的如双节点集群发生网络分区后，qdevice可以使其中一台机器继续提供服务，进而保证高可用。

QDevice 和 QNetd 会参与仲裁决定。在仲裁方 `corosync-qnetd` 的协助下，`corosync-qdevice` 会提供一个可配置的投票数，以使群集可以承受大于标准仲裁规则所允许的节点故障数量。我们强烈建议为双节点群集部署 `corosync-qnetd` 和 `corosync-qdevice`，但对于所含节点数为偶数的群集，一般也建议使用 QNetd 和 QDevice。

## 基本组件

### corosync

corosync提供分布式一致性协议和配置。

### qnetd

qnetd提供与qdevice通信的网络服务器。

### qdevice

每个群集节点上与 Corosync 一起运行的 systemd 服务（守护程序）。这是 `corosync-qnetd` 的客户端。其主要用途是让群集能够承受大于标准仲裁规则所允许的节点故障数量。

QDevice 可以与不同的仲裁方配合工作，但目前仅支持与 QNetd 配合工作。

## 编译运行

### 编译

qdevice依赖corosync，在编译qdevice前应先编译corosync。

- 下载源码
  
  ```shell
  git clone https://github.com/corosync/corosync-qdevice.git
  ```

- 编译
  
  ```shell
  cd corosync-qdevice
  ./autogen.sh
  ./configure
  make -j 8
  sudo make install
  ```
  
  若编译时找不到libcorosync_common库，则需要导出pkgconfig文件路径到PKG_CONFIG_PATH，如：
  
  ```shell
  export PKG_CONFIG_PATH="/home/ha/code/corosync/pkgconfig"
  ```
  
  编译完成后会生成corosync-qnetd和corosync-qdevice。
  
  ```shell
  ha@ha-virtual-machine:~/code/corosync-qdevice$ ls install
  bin  etc  sbin  share  var
  ha@ha-virtual-machine:~/code/corosync-qdevice$ ls install/bin/
  corosync-qnetd  corosync-qnetd-certutil  corosync-qnetd-tool
  ha@ha-virtual-machine:~/code/corosync-qdevice$ ls install/sbin/
  corosync-qdevice  corosync-qdevice-net-certutil  corosync-qdevice-tool
  ha@ha-virtual-machine:~/code/corosync-qdevice$ ls install/etc/
  corosync  init.d
  ha@ha-virtual-machine:~/code/corosync-qdevice$ ls install/etc/corosync/
  qdevice  qnetd
  ```

### 运行

corosync-qnetd可以独立运行，同时corosync-qdevice在启动时候需要连接qnetd，因而需先启动corosync-qnetd。

一般我们使用非root用户运行，运行配置步骤如下：

1. 先创建非root用户；
   
   ```shell
   groupadd -r coroqnetd
   useradd -r -g coroqnetd -d / -s /sbin/nologin -c "User for corosync-qnetd" coroqnetd
   chown -R coroqnetd:coroqnetd /etc/corosync/qnetd /var/run/corosync-qnetd
   ```

2. 在/etc/corosync/qnetd/下创建corosync-qnetd.sysconfig写下如下内容
   
   ```shell
   # Corosync Qdevice Network daemon init script configuration file
   
   # COROSYNC_QNETD_OPTIONS specifies options passed to corosync-qnetd command
   # (default is no options).
   # See "man corosync-qnetd" for detailed descriptions of the options.
   COROSYNC_QNETD_OPTIONS=""
   
   # COROSYNC_QNETD_RUNAS specifies user under which qnetd daemon should be running
   # (not set or empty is default and means "user who executes init script")
   # Make sure to set correct owner of directories /etc/corosync/qnetd and
   # /var/run/corosync-qnetd
   # This has no effect if systemd unit is used (you have to change unit file)
   COROSYNC_QNETD_RUNAS="coroqnetd"
   ```

3. 运行qnetd
   
   ```shell
   /etc/init.d/corosync-qnetd start
   ```

## 双节点qnet与三节点corosync的区别

1. qnet主要作为第三方仲裁，配合qdevice来提供投票仲裁服务，不属于集群内节点，不承担任何集群节点功能；
2. QDevice 支持多种不同的算法，而这些算法决定着如何分配投票的行为，如：
   - FFSplit (“fifty-fifty split”) 为默认算法，用于所含节点数为偶数的群集。如果群集分裂为两个相似的部分，此算法会根据启发检查结果和其他因素为其中一个部分提供一个投票
   - LMS (“last man standing”) 允许仅剩的那个节点看到 QNetd 服务器以获取投票。因此此算法适用于只有一个活动节点应保留法定票数的群集
3. 启用qdevice加qnet后，corosync里的`last_man_standing` 选项（即动态修改quorum）与其不兼容，但qdevice如上描述可以选择LMS算法来进行投票；
4. qnet一般需要独立于主集群，不要与 corosync 环或者环位于同一个网络网段，一般不在现有集群节点中运行制裁设备；
5. 多个集群可以共用一个qnet仲裁服务，且不同的集群可以配置不同投票算法；

corosync1.0版本没有投票机制，需要使用corosync-qdevice来配合投票仲裁，corosync2.0版本通过votequorum提供投票机制。

## votequorum与corosync-qdevice

votequorum和corosync-qdevice都是投票仲裁机制。

votequorum不需要引入第三方仲裁，直接作为一个服务集成到corosync中。votequorum通过为集群中的每个系统分配一定数量的选票，并确保只有当多数票出现时，才允许进行集群操作。

corosync-qdevice需要引入第三方仲裁qnet，除运行corosync服务、corosync-qdevice服务外，还需要在一台非集群节点运行corosync-qnetd服务。在仲裁方 `corosync-qnetd` 的协助下，`corosync-qdevice` 会提供一个可配置的投票数，以使群集可以承受大于标准仲裁规则所允许的节点故障数量。这里的标准仲裁规则是指当集群节点数超过一般挂死时集群将不可用。

### 双节点场景

对于双节点场景来说，

- votequorum通过在corosync.conf中配置two_node来解决双节点场景的高可用问题，且这样配置后只能处理两个节点的情况，当有第三个节点加入时，two_node配置自动失效
- 而corosync-qdevice通过在corosync.conf的device配置模块中配置algorithm: ffsplit来解决