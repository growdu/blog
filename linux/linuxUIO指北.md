# linux UIO指北

在基于kernel的IO模型中，所有的设备IO都要经过内核处理，在高并发的网络数据包收发的情况下，大量硬件中断会降低内核数据包处理能力，内核和用户空间的数据拷贝也会造成大量的计算资源浪费。所以，作为高并发大流量网络开发框架的DPDK，必须要找到一个能够避免内核中断爆炸和大量数据拷贝的方法，在用户空间能够直接和硬件进行交互。

Linux的UIO就是这样一个将硬件操作映射到用户空间的kernel bypass方案。

# reference

1. https://blog.csdn.net/cloudvtech/article/details/80359834