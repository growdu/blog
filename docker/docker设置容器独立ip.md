# docker设置容器独立ip（linux下虚拟机设置独立ip）

在linux要设置容器或者其他虚拟机独立ip，需要如下步骤：

- 准备好ip和网关
- 创建好网桥，并把物理网卡连接到网桥上
- 对于docker容器来说，需要使用pipework配置容器ip，对于kvm等虚拟化工具则使用虚拟化界面选择对应的网桥即可

## 创建网桥

在linux中，网桥就是虚拟交换机的意思，通过建立一个网桥，并将物理网卡连接到网桥上，在该机器上的虚拟机包括容器就可以通过网桥访问与物理机所在的网络，同时可以给虚拟机或者容器分配独立的大网ip。

这里以eth0和br0为例创建网桥和对外连接。

在没有创建网桥之前，我们通过物理网卡eth0对外提供这台机器的网络访问服务，比如它的ip是192.168.0.100/24，网关是192.168.0.1。
在我们创建网桥br0后，我们将eth0连接到br0上，后续物理将通过br0对外提供网络服务，为了保证我们的物理机对外提供服务的ip不变，我们会将eth0的ip配置到br0上。
<font color="red">需要特别注意的是，与我们的直觉不一致的地方，物理网卡eth0连接到br0后，需要把eth0 down掉，否则网络无法访问。</font>

### 创建网桥br0

```shell
nmcli conn add type bridge con-name br0 ifname br0
```

上面的命令创建了一个连接名称为br0，网桥名称也为br0的网桥。

### 设置网桥静态ip

```shell
nmcli connection modify br0 ipv4.addresses '192.168.0.100/24' ipv4.gateway '192.168.0.1' ipv4.method manual
```

将eth0的ip设置到网桥br0上，这样可以保证物理机器的访问ip不变。

### 将物理网卡连接到网桥br0上

```shell
nmcli conn add type ethernet slave-type bridge con-name br0-eth0 ifname eth0 master br0
```

这个就是把eth0连接到br0上。

### 打开网桥并关闭网卡

```shell
nmcli conn up br0; nmcli conn down eth0
```

这两个命令最好合在一条命令里执行，因为执行完后会短暂的断网，需要隔几秒才能恢复。

等网络恢复后，如果ping 192.168.0.100能ping通，说明网桥配置成功。

## 使用pipework配置容器独立ip

对于容器独立ip来说，需要下载pipework。

```shell
git clone https://github.com/jpetazzo/pipework
cp pipework/pipework /usr/local/bin/
```
然后创建一个容器，比如创建的容器名为update，则使用如下命令创建容器独立ip：

```shell
pipework br0 update 192.168.0.101/24@192.168.0.1
```
上面的命令将192.168.0.101分配给了容器update，其中@前面的是ip地址，@后面的是网关。

最后在物理机上ping 192.168.0.101验证是否可以ping通。