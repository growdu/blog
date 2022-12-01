# vpp

## 概述

VPP(Vector Packet Processing )(向量包处理)库。

VPP向量报文处理是与传统的标量报文处理相对而言的。传统报文处理方式，同时也是人类常用的逻辑思维方式，即：报文是按照到达先后顺序来处理，第一个报文处理完，处理第二个，依次类推；A callsB calls C….return return return，函数会频繁嵌套调用，并最终返回。

由此可见，传统标量报文处理有如下缺陷：

1. I-cache 抖动(cache时间局限性和空间局限性特点)

2. I-cache misses

3. 除了扩大cache外，没有变更方案

相比较而言，向量报文处理则是一次处理多个报文，也相当于一次处理一个报文数组。VPP把一批底层硬件队列Rx ring收到的包，组成一个Packet Vector或者是一组包，借助于报文处理图Packet  Processing graph来实现处理流程，图节点graph node把整个过程分解为一个个先后连接的服务node。这一组包（packet  vector）被第一个graph node节点的任务处理，然后依次被第二个graph node节点的任务处理，依次类推。

向量报文处理解决了标量处理的主要性能缺陷，并有具有如下优点：

1. 解决了I-cache抖动问题
2. 向量报文进行预取缓解了读时延问题，高性能并且更加稳定

## 技术特色

- 服务的易插件化

  VPP平台的图节点graph node组织方式，使用户可以根据需求，通过plugin方式插入新的图节点或者重新排列图节点，扩展非常方便，也不会影响原有核心处理流程。

- 丰富的基础功能

  - ipv4
  - ipv6

- 良好的扩展性

  VPP平台是通过graph node串联起来形成一条datapath来处理报文，类似于freebsd的netgraph。通过插件的形式引入新的graph node或者重新排列报文的graph node。将插件添加到插件目录中，运行程序的时候就会自动加载插件。另外插件也可以根据硬件情况通过某个node直接连接硬件进行加速。将插件添加到插件目录中，运行程序的时候就会自动加载插件。另外插件也可以根据硬件情况通过某个node直接连接硬件进行加速。VPP平台可以用于构建任何类型的报文处理应用。比如负载均衡、防火墙、IDS、主机栈。也可以是一个组合，比如给负载均衡添加一个vSwitch。
  
  通过创建插件，可以任意扩展如下功能：
  
  - 自定义新的graph node。
  - 重新排列graph node。
  - 添加底层API。

## 架构

### 源码架构

- 基础架构层：包括vppinfra，vlib，svm和二进制api库
- 通用网络协议栈层：vnet
- 应用程序shell：vpp

## 编译

### x86

- openssl

```shell
./Configure linux-aarch64 --prefix=/home/duanyingshou/code/openssl/build_linux_native_x86/openssl shared
make -j 8
make install
```

- dpdk

```shell
make config T=x86_64-native-linuxapp-gcc EXTRA_CFLAGS='-g -Ofast -fPIC -ftls-model=local-dynamic'
make T=x86_64-native-linuxapp-gcc  -j 8 EXTRA_CFLAGS='-g -Ofast -fPIC -ftls-model=local-dynamic' install 
```

- vpp

```shell
export DPDK_PATH=/home/duanyingshou/code/dpdk/x86_64-native-linuxapp-gcc
#export OPENSSL_PATH=/home/duanyingshou/code/openssl/build_linux_native_x86/
export PLATFORM=vpp
make wipe
make build-release
```

### arm64

- openssl

```shell
export CC=aarch64-linux-gnu-gcc
#./Configure linux-aarch64 --prefix=/opt/cross/sysroots/x86_64-fslsdk-linux/usr shared
./Configure linux-aarch64 --prefix=/home/duanyingshou/code/openssl/build_linux_aarch64/openssl shared
make -j 8
make install
```

- dpdk

```shell
export CROSS=aarch64-linux-gnu-
make config T=arm64-dpaa2-linuxapp-gcc
make T=arm64-dpaa-linuxapp-gcc install CONFIG_RTE_KNI_KMOD=n CONFIG_RTE_EAL_IGB_UIO=n -j 8
```

- vpp

### dpaa2

需要使用专门的交叉工具编译，交叉编译工具文件为fsl-qoriq-glibc-x86_64-fsl-toolchain-aarch64-toolchain-2.5.sh，使用如下命令安装：

```shell
fsl-qoriq-glibc-x86_64-fsl-toolchain-aarch64-toolchain-2.5.sh -d /opt/cross
```

若/opt/cross已存在该交叉编译工具无需安装。

注：暂时只能以该交叉工具编译vpp，且openssl、dpdk、vpp都需要以该工具链编译。

交叉编译工具链中包含的openssl库可以用来编译fastup，暂时先不用编译opens数量。

- openssl

```shell
#编译openssl
git checkout OpenSSL_1_1_0g
export CROSS=/opt/cross/sysroots/x86_64-fslsdk-linux/usr/bin/aarch64-fsl-linux/aarch64-fsl-linux-
export CC=aarch64-fsl-linux-gcc
#./Configure linux-aarch64 --prefix=/opt/cross/sysroots/x86_64-fslsdk-linux/usr shared
./Configure linux-aarch64 --prefix=/home/duanyingshou/code/openssl/build_linux_aarch64/ shared
make depend
make CC="/opt/cross/sysroots/x86_64-fslsdk-linux/usr/bin/aarch64-fsl-linux/aarch64-fsl-linux-gcc --sysroot=/opt/cross/sysroots/aarch64-fsl-linux -fPIC" LD="/opt/cross/sysroots/x86_64-fslsdk-linux/usr/bin/aarch64-fsl-linux/aarch64-fsl-linux-ld" AR="/opt/cross/sysroots/x86_64-fslsdk-linux/usr/bin/aarch64-fsl-linux/aarch64-fsl-linux-ar rv " EXTRA_CFLAGS='-g -Ofast -fPIC -ftls-model=local-dynamic' -j 8
make install
```

1. 编译时打包/opt/cross/sysroots/x86_64-fslsdk-linux/usr/bin/aarch64-fsl-linux/aarch64-fsl-linux-ar失败

   解决方法添加rv参数

2. 编译openssl成功，但在编译vpp时openssl报错找不到符号表

   解决方法添加LD="/opt/cross/sysroots/x86_64-fslsdk-linux/usr/bin/aarch64-fsl-linux/aarch64-fsl-linux-ld"

- dpdk

```shell
# 编译dpdk
export CROSS=/opt/cross/sysroots/x86_64-fslsdk-linux/usr/bin/aarch64-fsl-linux/aarch64-fsl-linux-
make config T=arm64-dpaa2-linuxapp-gcc CROSS=aarch64-fsl-linux- CROSS_COMPILE="aarch64-fsl-linux-" CC="/opt/cross/sysroots/x86_64-fslsdk-linux/usr/bin/aarch64-fsl-linux/aarch64-fsl-linux-gcc --sysroot=/opt/cross/sysroots/aarch64-fsl-linux -fPIC -g"  EXTRA_CFLAGS='-g -Ofast -fPIC -ftls-model=local-dynamic'
make T=arm64-dpaa2-linuxapp-gcc CC="/opt/cross/sysroots/x86_64-fslsdk-linux/usr/bin/aarch64-fsl-linux/aarch64-fsl-linux-gcc --sysroot=/opt/cross/sysroots/aarch64-fsl-linux -fPIC" EXTRA_CFLAGS='-g -Ofast -fPIC -ftls-model=local-dynamic' CONFIG_RTE_KNI_KMOD=n CONFIG_RTE_EAL_IGB_UIO=n install -j 8
```

```shell
# support kni
export CROSS=/opt/cross/sysroots/x86_64-fslsdk-linux/usr/bin/aarch64-fsl-linux/aarch64-fsl-linux-
export RTE_KERNELDIR=/home/duanyingshou/linux
make config T=arm64-dpaa2-linuxapp-gcc CROSS=aarch64-fsl-linux- CROSS_COMPILE="aarch64-fsl-linux-"
CC="/opt/cross/sysroots/x86_64-fslsdk-linux/usr/bin/aarch64-fsl-linux/aarch64-fsl-linux-gcc --sysroot=/opt/cross/sysroots/aarch64-fsl-linux -fPIC -g"  EXTRA_CFLAGS='-g -Ofast -fPIC -ftls-model=local-dynamic'
make T=arm64-dpaa2-linuxapp-gcc CC="/opt/cross/sysroots/x86_64-fslsdk-linux/usr/bin/aarch64-fsl-linux/aarch64-fsl-linux-gcc --sysroot=/opt/cross/sysroots/aarch64-fsl-linux -fPIC" EXTRA_CFLAGS='-g -Ofast -fPIC -ftls-model=local-dynamic -I/opt/cross/sysroots/aarch64-fsl-linux/usr/include' CONFIG_RTE_KNI_KMOD=y CONFIG_RTE_EAL_IGB_UIO=n install -j 32
```



- vpp

修改vpp下的toolchain.cmake的20和21行如下：

```shell
set(CMAKE_C_COMPILER ${toolchain}/usr/bin/$ENV{CROSS_PREFIX}/$ENV{CROSS_PREFIX}-gcc)
set(CMAKE_CXX_COMPILER ${toolchain}/usr/bin/$ENV{CROSS_PREFIX}/$ENV{CROSS_PREFIX}-g++)
```

```shell
#编译vpp
export PLATFORM=dpaa
export DPDK_PATH=/home/duanyingshou/code/dpdk/arm64-dpaa2-linuxapp-gcc
#export OPENSSL_PATH=/home/duanyingshou/code/openssl/build_linux_aarch64/
export CROSS_TOOLCHAIN=/opt/cross/sysroots/x86_64-fslsdk-linux
export CROSS_PREFIX=aarch64-fsl-linux
export CROSS_SYSROOT=/opt/cross/sysroots/aarch64-fsl-linux/
export PATH=$CROSS_TOOLCHAIN/bin:$CROSS_TOOLCHAIN/usr/bin/aarch64-fsl-linux:$PATH
cd build-root
make distclean
#TAG可以使用dpaa_debug，编译时不会优化，方便debug，详见 vpp/build-data/platforms/dpaa.mk
make V=0 PLATFORM=dpaa TAG=dpaa 
```

## 执行

## vpp环境准备

- 打包

```shell
# x86
cp ~/code/fastup_nxp/src/fastuplibs/libup/lib/x86/*  ~/code/fastup_nxp/build-root/install-vpp_debug-native/vpp/lib
cp ~/code/fastup_nxp/src/fastuplibs/libutils/lib/x86/* ~/code/fastup_nxp/build-root/install-vpp_debug-native/vpp/lib
cd ~/code/fastup_nxp/build-root/install-vpp_debug-native/
tar zcvf ~/package/vpp_x86.tar.gz vpp
# arm
cp ~/code/fastup_nxp/src/fastuplibs/libup/lib/arm64/*  ~/code/fastup_nxp/build-root/install-dpaa-aarch64/vpp/lib
cp ~/code/fastup_nxp/src/fastuplibs/libutils/lib/arm64/* ~/code/fastup_nxp/build-root/install-dpaa-aarch64/vpp/lib
cd ~/code/fastup_nxp/build-root/install-dpaa-aarch64/
tar zcvf ~/package/vpp_arm64.tar.gz vpp
```

- 指明lib路径

```shell
# x86
export LD_LIBRARY_PATH=../lib
# dpaa2
export LD_LIBRARY_PATH=/mnt/emmc2/vpp/lib
export PATH=/mnt/emmc2/vpp/bin:$PATH
```

vpp可以通过配置文件startup.conf进行启动，startup.conf可配置插件等参数。

- 配置

```shell
$ cat /etc/vpp/startup.conf
unix {
	interactive
}

api-trace {
  on
}
```

- 启动

startup.conf实际配置如下

```shell
heapsize 256M
plugin_path /mnt/emmc2/vpp/lib/vpp_plugins

unix {
  interactive
  #nodaemon
  gid vpp
  log /tmp/vpp.log
  full-coredump
  cli-listen /run/vpp/cli.sock
  #startup-config /mnt/vpp/interface.txt
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
}

dpdk {
        ## Change default settings for all intefaces
        huge-dir /mnt/hugepages
        no-pci
        num-mem-channels 1
         dev default {
                ## Number of receive queues, enables RSS
                ## Default is 1
                num-rx-queues 1

                # rss { ipv4 }

                ## Number of transmit queues, Default is equal
                ## to number of worker threads or 1 if no workers treads
                num-tx-queues 1
	}
	proc-type primary
        #log-level  8
}

plugins {
        ## Adjusting the plugin path depending on where the VPP plugins are
        path /mnt/emmc2/vpp/lib/vpp_plugins
        vat-path /mnt/emmc2/vpp/lib/vpp_api_test_plugins

        plugin default { enable }
        plugin gtpu_plugin.so { disable }
        plugin fastgtpu_plugin.so { disable }

}
```

```shell
./dynamic_dpl.sh dpmac.4
groupadd -f -r vpp
vpp -c startup.conf
```

- 配置

```shell
set int state TenGigabitEthernet0 up
set int ip address TenGigabitEthernet0 192.168.8.24/24
set int ip address TenGigabitEthernet0 192.168.9.24/24
set interface mac address TenGigabitEthernet0 42:4b:54:ae:6e:05
set int mtu 1500 TenGigabitEthernet0
set ip arp static TenGigabitEthernet0 192.168.8.25 90:e2:ba:8d:02:f0
```



```shell
vpp# show interface
              Name               Idx    State  MTU (L3/IP4/IP6/MPLS)     Counter          Count
TenGigabitEthernet0               1     down         9000/0/0/0
local0                            0     down          0/0/0/0
vpp#set int state TenGigabitEthernet0 up

```



### 配置详解

- unix
- api-trace
- api-segment
- socksvr
- cpu
- buffer
- dpdk
- plugins
- statseg
- heapsize

## vpp插件机制

vpp通过插件机制来开发自定义node，进而实现用户定义的行为。一般情况下会在插件中加入一些node节点去实现相关功能

## vpp node详解

vpp 把一个包的处理流程划分成多个阶段，每个阶段只做一部分处理工作，报文经过所有的阶段处理后完成报文的处理。一个阶段称为 node（中文叫做节点），即一个报文从某个口收上来后会经过一系列的 node 处理，然后从某个口发送出去。

### node结构

### node之间的关系

报文在节点之间转移方式：

- 报文类型

  mac层将报文转到ipv4、ipv6

- 预定义规则

各node组合成了一张图。

### node类型

- INTERNAl

  为 node 图中的 node

- INPUT

  为 node 图提供报文输入的 node，这类 node 在收包线程中每次循环都被调用，比如收包node，每次循环都被调用以从网卡收包；

- PRE_INPUT

  为在 INPUT 类型的 node 之前需要被调用的 node；

- PORCESS

  为可以被挂起和重新被执行的 node。

  process 和一般的 node 相比具有以下特点：

  -  只能在 thread0 上执行，即在 main 核上执行，不能在 worker 线程上执行，多个 process 共享main 的时钟
  - 能被挂起和恢复执行，恢复执行的时候要从被挂起的地方接着执行，因此需要给 process 创建单独的栈用来在被挂起时保存现场，被恢复执行时恢复现场

### node注册

node 的注册，即在 node 图中添加一个新的 node，vpp 提供宏 VLIB_REGISTER_NODE 用来注册node。

### node调度

由于 process 本身的特点，process 和其他类型的 node 的调度方式不一样，实现上为两个不同的函数，分别为：dispatch_process 和 dispatch_node，但 node 使用统一的状态，只是各自有独立的 flags。

node有如下几种状态：

- POLLING：轮询方式，每次循环都会被调度
- INTERRUPT：中断方式，只有收到中断信号之后才会被调度
- DISABLED：只有非 INTERNAL 类型的 node 才会设置该状态，如果设置了 DISABLE 状态表示不再会被调度

## vpp与dpdk的关系

dpdk是vpp的一个插件，是vpp中的一个输入节点。负责从网卡接收包到vpp。

- DPDK 的定位是基础组件, 提供的是基于X86平台的高效L2包转发方案. 这个方案包含一些最重要的底层组件,PMD/内存管理/初始化/etc.这些组件大多是为了使能硬件,优化硬件的用例. 
- VPP 的定位是解决方案. VPP 并不依赖特定的包转发框架, 当然在X86平台下, VPP集成DPDK的L2 包转发组件是一个明智选择.但VPP 更接近面向最终产品化的解决方案,尤其是对各类协议的支持更为完善. 调试框架,控制平面的接口都更加完备
- DPDK支持 Run To Completation/Pipe Line 两种模型, 当然取决于开发者怎么使用
- VPP 只支持 Run To Completation,  在IPSEC一些用例中会有比较难以处理的情况(e.g esn processing), 更加依赖网卡的 RSS功能
- VPP 有Honeycomb这样的控制平面接口, 支持netconf/yang. 这个对于产品化是非常重要的.DPDK 没有对应的组件

# reference

1. https://www.sohu.com/a/134745174_468741
2. https://www.cnblogs.com/mysky007/p/12348129.html
3. https://turbock79.cn/?p=855
4. https://blog.csdn.net/turbock/article/details/105076800
5. https://zhuanlan.zhihu.com/p/28324999
6. https://segmentfault.com/a/1190000019613730
7. https://fd.io/docs/vpp/v2009/gettingstarted/users/configuring/startup.html
8. https://www.cnblogs.com/sunnypoem/p/11368500.html
9. http://www.manongjc.com/detail/10-hpsehamtgobvwtz.html