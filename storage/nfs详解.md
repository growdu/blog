# nfs详解

## nfs简介

NFS是Network File System的缩写，即网络文件系统，是一种使用于分散式文件系统的协定。功能是通过网络让不同的机器、不同的操作系统能够彼此分享个别的数据，让应用程序在客户端通过网络访问位于服务器磁盘中的数据，是在类Unix系统间实现磁盘文件共享的一种方法。

这个NFS服务器可以让你的PC来将网络远程的NFS服务器分享的目录，挂载到本地端的机器当中， 在本地端的机器看起来，那个远程主机的目录就好像是自己的一个磁盘分区槽一样。

除了可以在unix系统间文件共享外，windows也可以使用nfs客户端挂载网络磁盘。windows默认关闭了nfs功能，若要开启需要在程序功能里开启，开启后windows会运行对应的nfs服务，此时就可以把nfs server共享的文件挂载到windows本地。

## nfs工作原理

nfs使用客户端和服务器模式，服务端会监听多个服务端口（主要是2049和111（nfs4之前需要监听）），客户端连接监听的端口进行文件共享。中间的通信采用RPC（远程过程调用）的方式。

因为 NFS 支持的功能相当的多，而不同的功能都会使用不同的程序来启动， 每启动一个功能就会启用一些端口来传输数据，因此， NFS 的功能所对应的端口才没有固定住， 而是随机取用一些未被使用的小于 1024 的端口来作为传输之用。

因为服务端使用随机的端口，需要有一种机制告诉客户端连接哪几个端口。因而nfs在服务端会使用固定的端口来运行rpcbind（或者是portmap）， 最主要的功能就是在指定每个 NFS 功能所对应的端口号，并且回报给客户端，让客户端可以连接到正确的端口上去。NFS本身是没有提供信息传输的协议和功能的，但NFS却能让我们通过网络进行资料的分享，这是因为NFS使用了一些其它的传输协议。而这些传输协议用到这个RPC功能的。可以说NFS本身就是使用RPC的一个程序，或者说NFS也是一个RPC SERVER。所以只要用到NFS的地方都要启动RPC服务，不论是NFS SERVER或者NFS CLIENT。可以这么理解RPC和NFS的关系：NFS是一个文件系统，而RPC是负责负责信息的传输。事实上，有很多这样的服务器都是向 RPC 注册的，举例来说，NIS (Network Information Service) 也是 RPC server 的一种。

### rpcbind如何知道每个nfs的端口

- 当服务器在启动 NFS 时会随机取用数个端口，并主动的向 RPC 注册，因此 RPC 可以知道每个埠口对应的 NFS 功能，然后 RPC 又是固定使用 111 端口来监听客户端的需求并报客户端正确的埠口， 所以当然可以让 NFS 的启动更为轻松愉快了。

- 要启动 NFS 之前，RPC 就要先启动了，否则 NFS 会无法向 RPC 注册。另外，RPC 若重新启动时，原本注册的数据会不见，因此 RPC 重新启动后，它管理的所有服务都要重新启动来重新向 RPC 注册。

### 客户端如何向NFS服务端交换数据数据

1. 客户端会向服务器端的 RPC 的111端口发出 NFS 档案存取功能的询问要求
2. 服务器端找到对应的已注册的 NFS 守护进程端口后，会回报给客户端
3. 客户端了解正确的端口后，就可以直接与 NFS 守护进程来联机

## nfs主要进程

- rpcbind（portmap）
主要负责RPC端口和守护进程的映射关系，在启动nfs之前需要先启动这个进程。
- rpc.nfsd
管理客户端是否能够登入主机的权限，其中还包含这个登入者的 ID 的判别。
- rpc.mountd
这个守护进程主要的功能，则是在管理 NFS 的档案系统，用于给用户提供访问令牌

## nfs版本

nfs共发布了3个版本：NFSv2、NFSv3、NFSv4，NFSv4包含两个次版本NFSv4.0和NFSv4.1。

不同的nfs版本所需要开发的端口不同：

| 协议版本|开发端口  |
|------|------|
|nfs3|111,445|
|nfs4|445|

## 服务端安装

1. 安装server

```shell
yum install rpcbind nfs-utils
```

2. 配置共享文件

```shell
echo "/data *(rw,sync,root_squash)" >> /etc/exports
```

其中*表示不限制ip，任何ip均可访问。括号中的rw是对权限或者其他选项的控制，具体如下：

-  ro 该主机对该共享目录有只读权限

- rw 该主机对该共享目录有读写权限

- root_squash 客户机用root用户访问该共享文件夹时，将root用户映射成匿名用户

- no_root_squash 客户机用root访问该共享文件夹时，不映射root用户

- all_squash 客户机上的任何用户访问该共享目录时都映射成匿名用户

- anonuid 将客户机上的用户映射成指定的本地用户ID的用户

- anongid 将客户机上的用户映射成属于指定的本地用户组ID

- sync 资料同步写入到内存与硬盘中

- async 资料会先暂存于内存中，而非直接写入硬盘

- insecure 允许从这台机器过来的非授权访问
　
- subtree_check 如果共享/usr/bin之类的子目录时，强制NFS检查父目录的权限（默认）

- no_subtree_check 和上面相对，不检查父目录权限

- wdelay 如果多个用户要写入NFS目录，则归组写入（默认）

- no_wdelay 如果多个用户要写入NFS目录，则立即写入，当使用async时，无需此设置。

- hide 在NFS共享目录中不共享其子目录

- no_hide 共享NFS目录的子目录

- secure NFS通过1024以下的安全TCP/IP端口发送

- insecure NFS通过1024以上的端口发送

3. 使共享目录生效

```shell
exportfs -rv
```

4. 启动nfs

```shell
systemctl start nfs
```

5. 查看共享

```shell
showmount -e localhost
```

## 客户端连接

### linux

```shell
mount localhost:/data /mnt
```

### windows

需要在程序与功能中开启nfs相关功能。

开启后打开命令行就可以正常使用mount命令。

```shell
mount \\ip\data H:
```

# reference

1. https://www.cnblogs.com/ludongguoa/p/15313140.html
2. https://blog.csdn.net/qq_36357820/article/details/78488077