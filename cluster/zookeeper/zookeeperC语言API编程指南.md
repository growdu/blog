# zookeeperC语言API编程指南

zookeeper是用java语言编写的分布式集群，我们可以基于zookeeper搭建分布式应用。通常zookeeper作为服务器运行，分布式应用需要使用客户端API与zookeeper进行通信。

zookeeper官方主要提供了java语言版本的API以及C语言API。下面基于C语言API进行编程说明。

## 下载编译

对于zookeeper执行程序和C语言API需分开下载，因为官方打包的zookeeper二进制程序默认不包含zokeeper-client-c。

若只是下载zookeeper二进制程序，直接使用如下连接下载：

```shell
https://dlcdn.apache.org/zookeeper/zookeeper-3.8.0/apache-zookeeper-3.8.0-bin.tar.gz
```

下载该文件后直接解压即可运行。

若要使用C语言API则需要下载zookeeper的源码，如下：

```shell
https://dlcdn.apache.org/zookeeper/zookeeper-3.8.0/apache-zookeeper-3.8.0.tar.gz
```

编译C语言API需要依赖java生成zookeeper.jute.c，用于序列化信息，因而编译zookeeper-c-client有两种方式：

1. 先用maven编译zookeeper，编译完成后会在zookeeper-client-c目录自动生成generated目录，里面含有zookeeper-c-client依赖的zookeeper.jute.c和zookeeper.jute.h；然后再编译zookeeper-client-c，大致流程步骤如下：

   ```shell
   tar -xvf apache-zookeeper-3.8.0.tar.gz
   cd apache-zookeeper
   mvn clean compile -Dmaven.test.skip=true
   cd zookeeper-client/zookeeper-client-c
   autoreconf -if
   ./configure
   make
   make install
   ```

2. 从其他地方拷贝generated目录到zookeeper-c-client下面，然后再进行编译，这一般适用于目标机器无法联网；

   ```shell
   cd zookeeper-client/zookeeper-c-client
   autoreconf -if
   ./configure
   make
   make install
   ```

编译下载完成后就可以使用C语言来编写基于zookeeper的分布式应用。

## 应用开发

