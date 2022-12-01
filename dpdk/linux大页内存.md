# linux大页内存

 HugePages是通过使用大页内存来取代传统的4kb内存页面，使得管理虚拟地址数变少，加快了从虚拟地址到物理地址的映射以及通过摒弃内存页面的换入换出以提高内存的整体性能。

## 概念

-  Page Table: page table也就是一种用于内存管理的实现方式，用于物理地址到虚拟之间的映射。因此对于内存的访问，先是访问Page Table，然后根据Page Table 中的映射关系，隐式的转移到物理地址来存取数据。
- TLB: Translation Lookaside Buffer (TLB) ，CPU中的一块固定大小的cache，包含了部分page table的映射关系，用于快速实现虚拟地址到物理地址的转换。
- hugetlb: hugetlb 是TLB中指向HugePage的一个entry(通常大于4k或预定义页面大小)。 HugePage 通过hugetlb entries来实现，也可以理解为HugePage 是hugetlb page entry的一个句柄
- hugetlbfs: 一个类似于tmpfs的新的in-memory filesystem，在2.6内核被提出

## 基本操作

```shell
[root@develop ~]# grep Huge /proc/meminfo    
AnonHugePages:     14336 kB
HugePages_Total:       0
HugePages_Free:        0
HugePages_Rsvd:        0
HugePages_Surp:        0
Hugepagesize:       2048 kB
~# ls /sys/kernel/mm/hugepages/
hugepages-1048576kB  hugepages-2048kB  hugepages-32768kB  hugepages-64kB
```

## 大页内存free为0

使用如下方式重新挂载：

```shell
# Build DPDK target.
cd dpdk_folder

# Get the hugepage size.
awk '/Hugepagesize/ {print $2}' /proc/meminfo

# Get the total huge page numbers.
awk '/HugePages_Total/ {print $2} ' /proc/meminfo

# Unmount the hugepages.
umount `awk '/hugetlbfs/ {print $2}' /proc/mounts`

# Create the hugepage mount folder.
mkdir -p /mnt/huge

# Mount to the specific folder.
mount -t hugetlbfs nodev /mnt/huge
```

## 命令行设置大页内存

```shell
$ sysctl -w vm.nr_hugepages=512
$ sysctl -p 
```





# reference

1. https://blog.csdn.net/zhang123456456/article/details/77853345
2. https://blog.csdn.net/weixin_35664258/article/details/83348133

3. https://www.cnblogs.com/zfox2017/p/6794617.html