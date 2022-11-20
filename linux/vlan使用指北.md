# vlan使用指北

vlan详细内容请参考[博客](https://blog.csdn.net/qq_38265137/article/details/80390759)。

VLAN（Virtual Local Area Network）的中文名为"虚拟局域网"。

> LAN可以是由少数几台家用计算机构成的网络，也可以是数以百计的计算机构成的企业网络。VLAN所指的LAN特指使用路由器分割的网络——也就是广播域。
>
> 简单来说，同一个VLAN中的用户间通信就和在一个局域网内一样，同一个VLAN中的广播只有VLAN中的  成员才能听到，而不会传输到其他的VLAN中去，从而控制不必要的广播风暴的产生。同时，  若没有路由，不同VLAN之间不能相互通信，从而提高了不同工作组之间的信息安全性。网络  管理员可以通过配置VLAN之间的路由来全面管理网络内部不同工作组之间的信息互访。
>
> - VLAN通过限制广播帧转发的范围分割了广播域。
> - VLAN生成的逻辑上的交换机是互不相通的。因此，在交换机上设置VLAN后，如果未做其他处理，VLAN间是无法通信的。
> - VLAN间的通信也需要路由器提供中继服务，这被称作“VLAN间路由”。转自[博客](http://www.qianjia.com/html/2019-03/19_329607.html)

## vlan的作用

>
>
>- 限制广播域：广播域被限制在一个VLAN内，节省了带宽，提高了网络处理能力。
>- 增强局域网的安全性：不同VLAN内的报文在传输时是相互隔离的，即一个VLAN内的用户不能和其它VLAN内的用户直接通信。
>- 提高了网络的健壮性：故障被限制在一个VLAN内，本VLAN内的故障不会影响其他VLAN的正常工作。
>- 灵活构建虚拟工作组：用VLAN可以划分不同的用户到不同的工作组，同一工作组的用户也不必局限于某一固定的物理范围，网络构建和维护更方便灵活。
>  ————————————————
>   版权声明：本文为CSDN博主「曹世宏的博客」的原创文章，遵循CC 4.0 BY-SA版权协议，转载请附上原文出处链接及本声明。
>   原文链接：https://blog.csdn.net/qq_38265137/article/details/80390759

### 使用vlan

### 加载8021q模块

vlan协议即IEE8021Q，在linux内核中若想使用vlan协议，需先加载8021q模块。

```shell
lsmod | grep 8021q
# 若没有需先加载
modprobe 8021q
```

### 安装vconfig

```shell
wget https://download-ib01.fedoraproject.org/pub/epel/7/x86_64/Packages/v/vconfig-1.9-16.el7.x86_64.rpm
rpm -Uvh vconfig-1.9-16.el7.x86_64.rpm
```

vconfig参数如下：

```shell
Expecting argc to be 3-5, inclusive.  Was: 2

Usage: add             [interface-name] [vlan_id]
       rem             [vlan-name]
       set_flag        [interface-name] [flag-num]       [0 | 1]
       set_egress_map  [vlan-name]      [skb_priority]   [vlan_qos]
       set_ingress_map [vlan-name]      [skb_priority]   [vlan_qos]
       set_name_type   [name-type]

* The [interface-name] is the name of the ethernet card that hosts
  the VLAN you are talking about.
* The vlan_id is the identifier (0-4095) of the VLAN you are operating on.
* skb_priority is the priority in the socket buffer (sk_buff).
* vlan_qos is the 3 bit priority in the VLAN header
* name-type:  VLAN_PLUS_VID (vlan0005), VLAN_PLUS_VID_NO_PAD (vlan5),
              DEV_PLUS_VID (eth0.0005), DEV_PLUS_VID_NO_PAD (eth0.5)
* bind-type:  PER_DEVICE  # Allows vlan 5 on eth0 and eth1 to be unique.
              PER_KERNEL  # Forces vlan 5 to be unique across all devices.
* FLAGS:  1 REORDER_HDR  When this is set, the VLAN device will move the
            ethernet header around to make it look exactly like a real
            ethernet device.  This may help programs such as DHCPd which
            read the raw ethernet packet and make assumptions about the
            location of bytes.  If you don't need it, don't turn it on, because
            there will be at least a small performance degradation.  Default
            is OFF.
```



### 配置vlan

```shell
# 在物理网口ens33上配置vlan id为100的vlan网口
vconfig add ens33 100
vconfig add ens33 200
#设置VLAN的REORDER_HDR参数
vconfig set_flag ens33.100 1 1
vconfig set_flag ens33.200 1 1
#配置ip
ifconfig ens33.100 172.168.1.100/24 up
ifconfig ens33.200 172.168.1.200/24 up
#查看配置信息
cat /proc/net/vlan/ens33.100
cat /proc/net/vlan/ens33.200
```

### 设置vlan优先级

```shell
# 将vlan出口包的优先级改为2
[root@localhost ~]# vconfig set_egress_map ens33.100 vlan_qos 2
Set egress mapping on device -:ens33.100:- Should be visible in /proc/net/vlan/ens33.100
[root@localhost ~]# cat /proc/net/vlan/ens33.100
ens33.100  VID: 100      REORDER_HDR: 1  dev->priv_flags: 1
         total frames received            0
          total bytes received            0
      Broadcast/Multicast Rcvd            0

      total frames transmitted          145
       total bytes transmitted        11140
Device: ens33
INGRESS priority mappings: 0:0  1:0  2:0  3:0  4:0  5:0  6:0 7:0
 EGRESS priority mappings: 0:2
[root@localhost ~]#
```

