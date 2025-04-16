# zookeeper主备集群demo

使用zookeeper搭建主备集群，要求实现如下功能：

- 有且只有一个节点作为master，履行master的职责，在例子中是注册调度器；
- 其他实例作为slave，不提供调度功能，但是在master节点挂掉之后，可以重新进行选主调度。

## kazoo

搭建好zookeeper后，需要使用zookeeper 客户端来连接zookeeper，并在zookeeper中写入相关信息。本次测试demo使用python编写，因而使用zookeeper的python客户端来kazoo来与zookeeper进行通信。

kazoo的安装流程如下：

```shell
pip install kazoo
```

也可以从github上下载源码进行安装，

```shell
git clone https://github.com/python-zk/kazoo.git
cd kazoo
python3 setup.py install
```

## zookeeper部署

使用两台机器部署zookeeper，部署过程如下：

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
  ```

  给每台zookeeper分配id：

  ```shell
  # 对节点1执行
  echo "1" >> /opt/data/myid
  # 对节点2执行
  echo "2" >> /opt/data/myid
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

## demo执行

demo代码run.py如下：

```python
# -*- coding:utf-8 -*-

import socket
import traceback
import time
from kazoo.client import KazooClient
from kazoo.client import KazooState

# 调度器注册和关闭
# 模拟主节点的职责
class MyScheduler(object):

    # 注册调度器
    def init_scheduler(self):
        print('########## 开启调度器成功 ############')

    # 关闭调度器
    def stop_scheduler(self):
        print('########## 关闭调度器成功 ############')

class HAMaster(object):

    def __init__(self):
        self.path = '/dmonitor/master'
        self.scheduler = MyScheduler()
        #self.zk = KazooClient('localhost:2181,10.93.18.34:2181,10.93.18.35:2181', timeout=10)
        self.zk = KazooClient('localhost:2181', timeout=10)
        self.zk.start()
        self.zk.add_listener(self.my_listener)
        self.is_leader = False

    def create_instance(self):
        instance = self.path + '/' + socket.gethostbyname(socket.gethostname()) + '-'
        self.zk.create(path=instance, value=b"test", ephemeral=True, sequence=True, makepath=True)

    # 选主逻辑: master节点下, 所有ephemeral+sequence类型的节点中, 编号最大的获得领导权.
    def choose_master(self):
        print("########## 选主开始 ############")
        instance_list = self.zk.get_children(path=self.path, watch=self.my_watcher)
        instance = max(instance_list).split('-')[0]
        # 本实例获得领导权
        if instance == socket.gethostbyname(socket.gethostname()):
            if not self.is_leader:
                self.scheduler.init_scheduler()
                self.is_leader = True
                print("######### 我被选为master, 我以前不是master, 注册调度 ##########")
            else:
                print("######### 我被选为master, 我以前是master, 不再注册调度 ##########")
        # 本实例没有获得领导权
        else:
            if self.is_leader:
                self.scheduler.stop_scheduler()
                self.is_leader = False
                print("######### 我被选为slave, 我以前不是slave, 关闭调度 ##########")
            else:
                print("######### 我被选为slave, 我以前是slave, 不再关闭调度 ##########")
        print("########## 选主完成 ############")

    def my_listener(self, state):
        if state == KazooState.LOST:
            print("########## 会话超时:KazooState.LOST ############")
            while True:
                try:
                    self.create_instance()
                    self.zk.get_children(path=self.path, watch=self.my_watcher)
                    print("########## 会话超时:重建会话完成! ############")
                    break
                except (Exception, _):
                    traceback.print_exc()
        elif state == KazooState.SUSPENDED:
            print("########## 会话超时:KazooState.SUSPENDED ############")
        elif state == KazooState.CONNECTED:
            print("########## 会话超时:KazooState.CONNECTED ############")
        else:
            print("########## 会话超时:非法状态 ############")

    def my_watcher(self, event):
        if event.state == "CONNECTED" and event.type == "CREATED" or event.type == "DELETED" or event.type == "CHANGED" or event.type == "CHILD":
            print("########## 监听到子节点变化事件 ############")
            self.choose_master()
        else:
            print("########## 监听到未识别的事件 ############")

def run():
    ha = HAMaster()
    # 向zk注册自己
    ha.create_instance()
    # 进行选主
    ha.choose_master()

    while 1:
        time.sleep(10)

if __name__ == "__main__":
    run()
```

demo模拟一个调度器的服务，且同一时刻仅有一个master节点在提供调度服务。

- 当有新节点加入时，自动成为备节点，仅作为备份，不提供服务
- 当master节点挂掉时，选择一个备节点，提升为主节点

在部署好zookeeper后，分别在各节点上执行如下命令模拟主备集群启动：

```shell
python3 run.py
```

注册服务的大致流程如下：

1. 首先服务启动时会先向zookeeper注册，注册会在/dmonitor/master/下创建节点，命名方式为本机ip和zookeeper生成的sequence，并用“-”连接，如127.0.1.1-0000000001；
1. 在/dmonitor/master/下创建的节点为临时节点，当与zookeeper相连的客户端断开时，其对应的节点也会被删除，其他调度服务通过watch感知节点变化；
2. 每个加入的服务注册好节点后就会进行选master选择，然后根据名称中sequence大的选为master；
2. 同时，每个调度服务都会对/dmonitor/master/下面的节点设置watch，当其下的节点发生变化时，会重新进入选master的阶段；

## 模拟主备集群

未启动调度服务时zookeeper的znode信息如下：

```shell
[zk: localhost:2181(CONNECTED) 1] ls /
[my, zookeeper]
```

### 启动主节点调度服务

首先启动节点1的调度服务，其执行结果如下：

```shell
ha@machine1:~/code/kazoo_test$ python3 run.py
########## 选主开始 ############
########## 开启调度器成功 ############
######### 我被选为master, 我以前不是master, 注册调度 ##########
########## 选主完成 ############
```

当只有一个节点有调度服务时，节点1的调度服务被选为主节点。此时再来查看zookeeper的znode信息，可以看到znode多了存储master信息的节点：

```shell
[zk: localhost:2181(CONNECTED) 0] ls /
[dmonitor, my, zookeeper]
[zk: localhost:2181(CONNECTED) 1] ls /dmonitor/master
[192.168.145.131-0000000000]
[zk: localhost:2181(CONNECTED) 2] get /dmonitor/master/192.168.145.131-0000000000
test
```

可以看到/dmonitor/master节点下面存储了成为主服务的ip信息，此时master为192.168.145.131。

### 启动备节点调度服务

接着我们在节点2上启动调度服务，同样执行：

```shell
python3 run.py
```

其执行结果如下，因为已经存在master了，所以成为slaver服务。

```shell
ha@machine2:~/code/kazoo_test$ python3 run.py
########## 选主开始 ############
######### 我被选为slave, 我以前是slave, 不再关闭调度 ##########
########## 选主完成 ############
```

同时因为master设置对/dmonitor/maste的watch，因而当新节点插入时，也会进入选master的阶段。

```shell
ha@machine1:~/code/kazoo_test$ python3 run.py
########## 选主开始 ############
########## 开启调度器成功 ############
######### 我被选为master, 我以前不是master, 注册调度 ##########
########## 选主完成 ############
########## 监听到子节点变化事件 ############
########## 选主开始 ############
######### 我被选为master, 我以前是master, 不再注册调度 ##########
########## 选主完成 ############
```

但此时master不变，仍然为192.168.145.131。

此时查看zookeeper的znode，结果如下所示：

```shell
[zk: localhost:2181(CONNECTED) 2] ls /dmonitor/master
[192.168.145.130-0000000001, 192.168.145.131-0000000000]
```

可以看到/dmonitor/master当前有两个ip信息。

### 主备切换

### 模拟master服务器挂掉

主备调度服务起来后，我们模拟主备切换的过程。当前的master为192.168.145.131，停掉该机器上的调度服务，查看192.168.145.130是否能升master。

可以看到，成功升级成为master，日志如下：

```shell
ha@machine2:~/code/kazoo_test$ python3 run.py
########## 选主开始 ############
######### 我被选为slave, 我以前是slave, 不再关闭调度 ##########
########## 选主完成 ############
########## 监听到子节点变化事件 ############
########## 选主开始 ############
########## 开启调度器成功 ############
######### 我被选为master, 我以前不是master, 注册调度 ##########
########## 选主完成 ############
```

在查看zookeeper的znode信息，

```shell
[zk: localhost:2181(CONNECTED) 10] ls /dmonitor/master
[192.168.145.130-0000000001]
```

可以看到192.168.145.131的信息已经从zookeeper中删除了，此时192.168.145.130机器的调度服务升级为master。

### 重启master服务器

master从192.168.145.131切换为192.168.145.130后，我们再重启192.168.145.131的调度服务。

在192.168.145.130机器可以看到192.168.145.130从master重新切换为slaver。

```shell
ha@machine2:~/code/kazoo_test$ python3 run.py
########## 选主开始 ############
######### 我被选为slave, 我以前是slave, 不再关闭调度 ##########
########## 选主完成 ############
########## 监听到子节点变化事件 ############
########## 选主开始 ############
########## 开启调度器成功 ############
######### 我被选为master, 我以前不是master, 注册调度 ##########
########## 选主完成 ############
########## 监听到子节点变化事件 ############
########## 选主开始 ############
########## 关闭调度器成功 ############
######### 我被选为slave, 我以前不是slave, 关闭调度 ##########
########## 选主完成 ############
```

而新启动的192.168.145.131则直接成为master。

```shell
ha@machine1:~/code/kazoo_test$ python3 run.py
########## 选主开始 ############
########## 开启调度器成功 ############
######### 我被选为master, 我以前不是master, 注册调度 ##########
########## 选主完成 ###########
```

查看zookeeper的znode信息，可以看到ip信息已更新。

```shell
[zk: localhost:2181(CONNECTED) 11] ls /dmonitor/master
[192.168.145.130-0000000001, 192.168.145.131-0000000002]
```

# reference

1. https://cloud.tencent.com/developer/article/1050471
