# fastupkni功能测试

## x86

### 编译

- dpdk

```shell
make config T=x86_64-native-linuxapp-gcc EXTRA_CFLAGS='-g -Ofast -fPIC -ftls-model=local-dynamic'
make T=x86_64-native-linuxapp-gcc  CONFIG_RTE_KNI_KMOD=y CONFIG_RTE_EAL_IGB_UIO=y EXTRA_CFLAGS='-g -Ofast -fPIC -ftls-model=local-dynamic' install -j 8
make examples T=x86_64-native-linuxapp-gcc O=x86_64-native-linuxapp-gcc -j16
```

- vpp

```shell
export DPDK_PATH=/home/duanyingshou/code/dpdk/x86_64-native-linuxapp-gcc
export PLATFORM=vpp
make wipe
make build
```

### scl

scl保持多版本gcc兼容，并支持切换gcc版本进行编译。

将toolchain.cmake中的set(CMAKE_C_COMPILER /usr/bin/gcc)注释掉。

```shell
yum install centos-release-scl
yum install devtoolset-7-gcc*
scl enable devtoolset-7 bash
gcc -v
```

- numa

  ```shell
  yum install numactl-devel
  ```


### 编译脚本

编译时进入dpdk源码目录，执行build.sh脚本。若要交叉编译，需要提前安装好交叉编译工具，且交叉编译工具需安装在/opt/cross目录下面，若安装在其它目录需修改下面的编译脚本，且需要声明export PLATFORM=aarch64。

```shell
#!/bin/bash
make clean
if [ $PLATFORM = "aarch64" ];then
    echo "complie aarch64"
    export CROSS=/opt/cross/sysroots/x86_64-fslsdk-linux/usr/bin/aarch64-fsl-linux/aarch64-fsl-linux-
    export RTE_KERNELDIR=/home/duanyingshou/linux
    make config T=arm64-dpaa2-linuxapp-gcc CROSS=aarch64-fsl-linux- CROSS_COMPILE="aarch64-fsl-linux-" CC="/opt/cross/sysroots/x86_64-fs
    make T=arm64-dpaa2-linuxapp-gcc -j 4 CC="/opt/cross/sysroots/x86_64-fslsdk-linux/usr/bin/aarch64-fsl-linux/aarch64-fsl-linux-gcc --s
else
    echo "complie x86"
    make config T=x86_64-native-linuxapp-gcc EXTRA_CFLAGS='-g -Ofast -fPIC -ftls-model=local-dynamic'
    make T=x86_64-native-linuxapp-gcc  CONFIG_RTE_KNI_KMOD=n CONFIG_RTE_EAL_IGB_UIO=n EXTRA_CFLAGS='-g -Ofast -fPIC -ftls-model=local-dynamic' install -j 8
fi
```



### 问题

#### i40e dpdk 19.08以下版本打开网口会出问题

```shell
i40e_vlan_tpid_set(): Set switch config failed aq_err: 14
eth_i40e_dev_init(): Failed to set the default outer VLAN ether type
EAL: ethdev initialisation failedEAL: Requested device 0000:43:00.0 cannot be used
EAL: PCI device 0000:43:00.1 on NUMA socket 0
EAL:   probe driver: 8086:37d0 net_i40e
i40e_vlan_tpid_set(): Set switch config failed aq_err: 14
eth_i40e_dev_init(): Failed to set the default outer VLAN ether type
EAL: ethdev initialisation failedEAL: Requested device 0000:43:00.1 cannot be used
```

解决方法如下：

- 更换版本到19.08及其以上

也可以直接修改代码，修改drivers/net/i40e/i40e_ethdev.c,在1514行添加如下代码：

```c
/* Firmware of SFP x722 does not support 802.1ad frames ability */
    if (hw->device_id == I40E_DEV_ID_SFP_X722 ||
        hw->device_id == I40E_DEV_ID_SFP_I_X722) {
        hw->flags &= ~I40E_HW_FLAG_802_1AD_CAPABLE;
    }
```



#### dpdk18.11当前不支持NetXtreme BCM5720网卡 

使用虚拟机可利用该机器网卡进行测试。

### 测试运行

- startup.conf

  相比fastup的配置，只需添加kni的路径即可

  ```shell
  heapsize 256M
  kni_ko_path /home/platform/code/dpdk/x86_64-native-linuxapp-gcc/kmod/rte_kni.ko
  
  unix {
    interactive
    #nodaemon
    gid vpp
    log /tmp/vpp.log
    full-coredump
    cli-listen /run/vpp/cli.sock
    #startup-config /etc/vpp/interface.txt
  }
  
  api-trace {
    on
  }
  
  api-segment {
    gid vpp
  }
  
  session {
    evt_qs_memfd_seg
  }
  
  socksvr {
    socket-name /tmp/vpp-api.sock
  }
  
  cpu {
      main-core 1
  #   corelist-workers 3
  }
  
  dpdk {
      dev 0000:02:08.0 {
          name dpdk0
  	}
      #dev 0000:02:07.0 {
      #    name dpdk1
      #}
  }
  
  plugins {
          ## Adjusting the plugin path depending on where the VPP plugins are
  
          plugin default { enable }
          plugin gtpu_plugin.so { disable }
          #plugin fastgtpu_plugin.so { disable }
  
  }
  ```

- 配置kni ip

  ```shell
  platform@ubuntu:~/code/dpdk/usertools$ifconfig
  vEth0_0: flags=4098<BROADCAST,MULTICAST>  mtu 1500
          ether 00:0c:29:f2:49:34  txqueuelen 1000  (Ethernet)
          RX packets 0  bytes 0 (0.0 B)
          RX errors 0  dropped 0  overruns 0  frame 0
          TX packets 0  bytes 0 (0.0 B)
          TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0
  platform@ubuntu:~/code/dpdk/usertools$ sudo ifconfig vEth0_0 192.168.140.129 up
  # 使用直连口ping ip
  platform@ubuntu:~/code/dpdk/usertools$ ping 192.168.140.129
  PING 192.168.140.129 (192.168.140.129) 56(84) bytes of data.
  64 bytes from 192.168.140.129: icmp_seq=1 ttl=64 time=0.009 ms
  64 bytes from 192.168.140.129: icmp_seq=2 ttl=64 time=0.023 ms
  64 bytes from 192.168.140.129: icmp_seq=3 ttl=64 time=0.021 ms
  ```

- 配置fastup ip

  ```shell
  set int state TenGigabitEthernetb5/0/0 up
  set int ip address TenGigabitEthernetb5/0/0 192.168.8.25/16
  set interface mac address TenGigabitEthernetb5/0/0 42:4b:54:ae:6e:05
  set int mtu 1500 TenGigabitEthernetb5/0/0
  ```
  
  需配置kni虚拟出的ip和mac地址与vpp的一致。
  
  ```shell
  ifconfig vEth0_0 192.168.8.25/16
  ifconfig vEth0_0 hw ether 42:4b:54:ae:6e:05
  ```

### 测试流程

在主测端使用1个网口用pktgen回放gtpu报文，使用另外一个网口发送ping报文。

- 配置发送ping报文的网口ip

```shell
ifconfig eno2 192.168.8.26/16
```



### 测试结果

- kni虚拟出的vEth和vpp需配置相同的ip和mac地址
- 当前测试GTPU报文走vpp，非GTPU报文走kni

# NXP

### 编译

```shell
export CROSS=/opt/cross/sysroots/x86_64-fslsdk-linux/usr/bin/aarch64-fsl-linux/aarch64-fsl-linux-
export RTE_KERNELDIR=/home/duanyingshou/linux
make config T=arm64-dpaa2-linuxapp-gcc CROSS=aarch64-fsl-linux- CROSS_COMPILE="aarch64-fsl-linux-" CC="/opt/cross/sysroots/x86_64-fslsdk-linux/usr/bin/aarch64-fsl-linux/aarch64-fsl-linux-gcc --sysroot=/opt/cross/sysroots/aarch64-fsl-linux -fPIC -g"  EXTRA_CFLAGS='-g -Ofast -fPIC -ftls-model=local-dynamic'
make T=arm64-dpaa2-linuxapp-gcc CC="/opt/cross/sysroots/x86_64-fslsdk-linux/usr/bin/aarch64-fsl-linux/aarch64-fsl-linux-gcc --sysroot=/opt/cross/sysroots/aarch64-fsl-linux -fPIC" EXTRA_CFLAGS='-g -Ofast -fPIC -ftls-model=local-dynamic -I/opt/cross/sysroots/aarch64-fsl-linux/usr/include' CONFIG_RTE_KNI_KMOD=y CONFIG_RTE_EAL_IGB_UIO=n install -j 32
```

```shell
export CROSSE=aarch64-linux-gnu-
export RTE_KERNELDIR=/home/duanyingshou/linux
make config T=arm64-dpaa2-linuxapp-gcc
make T=arm64-dpaa2-linuxapp-gcc CONFIG_RTE_KNI_KMOD=y CONFIG_RTE_EAL_IGB_UIO=n install -j 32
export RTE_TARGET=arm64-dpaa2-linuxapp-gcc
export RTE_SDK= /home/duanyingshou/cod/dpdk
make -C examples/kni
```

两个网口直连，一端为NXP10G网口；

1. 配置vpp ip 121.168.1.12/24，另一端配置121.168.1.11无法ping通；
2. 配置kni虚拟网口 ip 121.168.1.12/24，另一端配置121.168.1.11无法ping通；
3. 配置vpp ip 121.168.1.12/24，同时配置kni虚拟网口 ip 121.168.1.12/24，另一端配置121.168.1.11无法ping通；

### kni无法ping通

1. 加载rte_kni模块时，需添加carrier=on参数

   ```shell
   insmod rte_kni.ko carrier=on
   ```

2. 需要修改dpdk插件代码，使用rte_pktmbuf_pool_create接口创建收发包队列内存

3. 需要在kni网口打开后设置对应的打开标志位

   ```c
   xd->flags |=  DPDK_DEVICE_FLAG_ADMIN_UP;
   ```

### 测试

使用NXP板cpu A往cpu B打流：

- CPU A使用pktgen回放gtpu报文
- CPU B使用fastup_kni接收报文

fastup 配置ip：

```shell
set int ip address TenGigabitEthernet0 192.168.8.25/16
set int mtu 1500 TenGigabitEthernet0
```

kni 配置ip：

```shell
ifconfig vEth0_0 192.168.8.25/16
```

## fastup kni测试问题

1. kni网口无法接收报文回放冲击，1Mbps速率回放报文仍存在丢包；
2. fastup kni网口kni不收发数据时，对fastup几乎没有影响

### 抓包

```shell
pcap rx trace status
pcap tx trace on max 1000 intfc dpdk0 file vppTest.pcap
pcap rx trace status
pcap rx trace off
```


