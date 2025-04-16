# day1

今天重点搞清楚 

1. NXP ARM下面DPDK如何独立编译
2. ARM下面DPDK要运行，需要做些什么配置和事情
3. 了解VFIO相关
4. 了解如何运行l3fwd，以及用l3fwd测试的模型。

## DPDK编译

```c
git clone https://source.codeaurora.org/external/qoriq/qoriq-components/dpdk -b github.qoriq-os/
integration
make T=arm64-dpaa-linuxapp-gcc install CONFIG_RTE_KNI_KMOD=n CONFIG_RTE_EAL_IGB_UIO=n -j 4
export RTE_SDK=<path to DPDK source code, where compilation was done>
export RTE_TARGET=arm64-dpaa-linuxapp-gcc
make -C examples/l3fwd # for the L3 forwarding application
make -C examples/<Name of examples directory>
```

- kni
  1. 声明内核头文件路径
  2. 设置交叉编译器路径
  3. 设置openssl路径

```c
export RTE_KERNELDIR=<Path to compiled Linux kernel to compile KNI kernel module>
export CROSS=<path to cross-compile toolchain>
export OPENSSL_PATH=<path to installed OpenSSL>
```

```c
make T=arm64-dpaa-linuxapp-gcc install DESTDIR=<location to install DPDK>
make T=arm64-dpaa-linuxapp-gcc CONFIG_RTE_KNI_KMOD=n CONFIG_RTE_EAL_IGB_UIO=n CONFIG_RTE_EAL_IGB_UIO=n install
make T=arm64-dpaa-linuxapp-gcc CONFIG_RTE_LIBRTE_PMD_OPENSSL=y EXTRA_CFLAGS="-I${OPENSSL_PATH}/include/" EXTRA_LDFLAGS="-L${OPENSSL_PATH}/lib/" install

```

## dpdk配置

1. 设置大页内存
2. 加载内核驱动模块
3. 更换网卡驱动类型

## VFIO

### 概念

VFIO是一个可以安全的把设备I/O、中断、DMA等暴露到用户空间（userspace），从而可以在用户空间完成设备驱动的框架。用户空间直接设备访问，虚拟机设备分配可以获得更高的IO性能。

## IOMMU

实现用户空间设备驱动，最困难的在于如何将DMA以安全可控的方式暴露到用户空间：

- 提供DMA的设备通常可以写内存的任意页，因此使用户空间拥有创建DMA的能力就等同于用户空间拥有了root权限，恶意的设备可能利用此发动DMA攻击
- I/O memory management unit(IOMMU)的引入对设备进行了限制，设备I/O地址需要经过IOMMU重映射为内存物理地址。恶意的或存在错误的设备不能读写没有被明确映射过的内存，运行在cpu上的操作系统以互斥的方式管理MMU与IOMMU，物理设备不能绕行或污染可配置的内存管理表项。

IOMMU主要功能包括DMA Remapping和Interrupt Remapping，这里主要讲解DMA Remapping，Interrupt Remapping会独立讲解。对于DMA Remapping，IOMMU与MMU类似。IOMMU可以将一个设备访问地址转换为存储器地址。

### 实现

VFIO由平台无关的接口层与平台相关的实现层组成。接口层将服务抽象为IOCTL命令，规化操作流程，定义通用数据结构，与用户态交互。实现层完成承诺的服务。据此，可在用户态实现支持DMA操作的高性能驱动。在虚拟化场景中，亦可借此完全在用户态实现device passthrough。

### 接口

用户态通过IOCTL与VFIO交互。可作为操作对象的几种文件描述符有：

- Container文件描述符

  打开/dev/vfio字符设备可得

- IOMMU group文件描述符

  打开/dev/vfio/N文件可得 

-  Device文件描述符

  向IOMMU group文件描述符发起相关ioctl可得

用VFIO访问硬件的步骤：
- 打开设备所在IOMMU group在/dev/vfio/目录下的文件
- 使用VFIO_GROUP_GET_DEVICE_FD得到表示设备的文件描述 (参数为设备名称，一个典型的PCI设备名形如0000:03.00.01)
- 对设备进行read/write/mmap等操作

用VFIO配置IOMMU的步骤：
- 打开/dev/vfio，得到container文件描述符
- 用VFIO_SET_IOMMU绑定一种IOMMU实现层
- 打开/dev/vfio/N，得到IOMMU group文件描述符
- 用VFIO_GROUP_SET_CONTAINER将IOMMU group加入container
- 用VFIO_IOMMU_MAP_DMA将此IOMMU group的DMA地址映射至进程虚拟地址空间

## l2fwd

二层转发，即mac层转发。

## l3fwd

三层转发，即IP层转发。

### pktgen

pktgen是一个位于linux内核层的高性能网络测试工具，主要用来测试网络驱动与网卡设备，支持多线程，能够产生随机mac地址、IP地址、UDP端口号的数据包，pktgen 的作者使用多CPU处理器在不同的PCI总线（pci 、pcie等总线）上用千兆以太网卡做过测试（pktgen的表现依赖于CPU处理速率、内存延时、pci总线速率等硬件参数），发送数据速率甚至可以大于10GBit/s。

三层转发。

## reference

1. https://blog.csdn.net/wentyoon/article/details/60144824