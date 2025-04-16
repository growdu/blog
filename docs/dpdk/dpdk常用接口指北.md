# dpdk常用接口指北

基于dpdk18.11版本，其他版本注意区别。

一般用dpdk做网口管理、网口收发包、内存管理等操作。

## dpdk环境初始化

```c
int rte_eal_init(int argc, char **argv);
```

### 通用参数配置

```shell
-b blacklist
-w whitelist
-c coremask
-l corelist
-s service coremask
-S service corelist
-m size of memory
-n force number of channels
-r force number of ranks
-d force loading of external driver
```

DPDK多进程使用的关键启动参数：

```shell
--in-memory :在这种模式下，DPDK不会在任何文件系统（hugetlbfs或其他文件系统）上创建文件
--proc-type：指定一个dpdk进程是主进程还是副进程（参数值就用上面的primary或是secondary，或者是auto）
--file-prefix：允许非合作的进程拥有不同的内存区域。主副进程默认文件路径/var/run/.rte_config，同一个处理组的主副进程使用相同的参数，
如果想运行多个主进程，这个参数就必须指定！
--socket-mem：设置从hugepages分配多大的存储空间。默认会用掉所有的hugepages，所以建议指定这个参数，不管是单cpu还是在NUMA中。
eg：单socket，--socket-mem=512；在numa中，--socket-mem=512,512；多个socket间用‘,’号隔开；
```
## 网口管理

## 内存管理

DPDK通过使用hugetlbfs，减少CPU TLB表的Miss次数，提高性能。

### 初始化

DPDK的内存初始化工作，主要是将hugetlbfs的配置的大内存页，根据其映射的物理地址是否连续、属于哪个Socket等，有效的组织起来，为后续管理提供便利。

```c
 /*
 * when we initialize the hugepage info, everything goes
 * to socket 0 by default. it will later get sorted by memory
 * initialization procedure.
 */
int
eal_hugepage_info_init(void)
```

eal_hugepage_info_init()主要是获取配置好的Hugetlbfs的相关信息，并将其保存在struct internal_config数据结构中。

1. 读取/sys/kernel/mm/hugepages目录下的各个子目录，通过判断目录名称中包含"hugepages-"字符串，获取hugetlbfs的相关子目录，并获取hugetlbfs配置的内存页大小。
2. 通过读取/proc/mounts信息，找到hugetlbfs的挂载点
3. 通过读取/sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages，获取配置的hugepages个数
4. 以打开文件的方式，打开挂载点目录，为其FD设置互斥锁
5. 将internal_config.hugepage_info[MAX_HUGEPAGES_SIZE]按内存页的大小排序。

```c
/* create memory configuration in shared/mmap memory. Take out
 * a write lock on the memsegs, so we can auto-detect primary/secondary.
  * This means we never close the file while running (auto-close on exit).
 * We also don't lock the whole file, so that in future we can use read-locks
  * on other parts, e.g. memzones, to detect if there are running secondary
 * processes. */
static void
rte_eal_config_create(void)
```

rte_eal_config_create()主要是初始化rte_config.mem_config。如果是以root用户运行dpdk程序的话，rte_config.mem_config指向/var/run/.rte_config文件mmap的一段sizeof(struct rte_mem_config)大小的内存

```c
int
rte_eal_hugepage_init(void)
```

rte_eal_hugepage_init()主要是在/mnt/huge目录下创建hugetlbfs配置的内存页数（在本文中就是64）的rtemap_xx文件，并为每个rtemap_xx文件做mmap映射，保证mmap后的虚拟地址与实际的物理地址是一样的.

1. 创建nr_hugepages个struct hugepage_file数组，即有多少个内存页，创建多少个struct hugepage_file数据结构
2. 有多少个内存页，在挂载点目录下创建多少个rtemap_xx文件，如下所示，并为每一个文件mmap一个hugepage_sz大小的内存区域
3. 通过读取/proc/self/pagemap页表文件，得到本进程中虚拟地址与物理地址的映射关系。使用上一步中，每个rtemap_xx文件mmap得到的虚拟地址，除以操作系统内存页的大小4k，得到一个偏移量。根据这个偏移量，在/prox/self/pagemap中，得到物理地址的页框，假设为page，那么，物理页框page乘以操作系统内存页的大小4K，再加上虚拟地址的页偏移，就是物理地址。每个rtemap_xx映射的物理地址保存在对应的hugepage_file->physaddr中
4. 读取/proc/self/numa_maps，得到每个rtemap_xx文件mmap得到的虚拟地址在哪个Socket上，即，哪个CPU上。其socketid保存在对应的hugepage_file->socket_id中
5. 在hugepage_file数组中，根据物理地址，按从小到大的顺序，将hugepage_file排序
6. 根据按物理地址排序后的结果，判断物理地址是否连续，重新mmap /mnt/huge/retmap_xx文件，**使得物理地址等于第二次mmap后的虚拟地址**。第二次mmap得到的虚拟地址保存在对应的hugepage_file->final_va中

```c
static int
rte_eal_memdevice_init(void)
```

rte_eal_memdevice_init()初始化rte_config.mem_config->nchannel和rte_config.mem_config->nrank。

　　rte_config.mem_config->nchannel = 启动参数中“-n”指定的值，不能为0，不能大于4。

　　rte_config.mem_config->nrank = 启动参数中“-r”指定的值。不能为0，不能大于16。

```c
/*
 * Init the memzone subsystem
 */
int
rte_eal_memzone_init(void)
```

rte_eal_memzone_init()主要负责初始化rte_config.mem_config->free_memseg[]及rte_config.mem_config->memzone[]。其中,rte_config.mem_config->free_memseg[]记录空闲的rte_config.mem_config->memseg[]。

### rte_mempool内存管理

DPDK以两种方式对外提供内存管理方法，一个是rte_mempool，主要用于网卡数据包的收发；一个是rte_malloc，主要为应用程序提供内存使用接口。

rte_mempool由函数rte_mempool_create()负责创建，从rte_config.mem_config->free_memseg[]中取出合适大小的内存，放到rte_config.mem_config->memzone[]中。

```c
struct rte_mempool *
rte_mempool_create(const char *name, unsigned n, unsigned elt_size,
		   unsigned cache_size, unsigned private_data_size,
           rte_mempool_ctor_t *mp_init, void *mp_init_arg,
		   rte_mempool_obj_cb_t *obj_init, void *obj_init_arg,
		   int socket_id, unsigned flags);

struct rte_mempool *
rte_mempool_create_empty(const char *name, unsigned n, unsigned elt_size,
	unsigned cache_size, unsigned private_data_size,
	int socket_id, unsigned flags);
```

rte_mempool由函数rte_mempool_create()负责创建。首先创建rte_ring，再创建rte_mempool，并建立两者之间的关联。

1. rte_ring_create()创建rte_ring无锁队列
2. 创建并初始化rte_mempool

### rte_malloc内存管理

rte_malloc()为程序运行过程中分配内存，模拟从堆中动态分配内存空间。

rte_malloc_socket()：指定从哪个socket上分配内存空间，默认是指定SOCKET_ID_ANY，即，程序在哪个socket上运行，就从哪个socket上分配内存。如果指定的socket上没有合适的内存空间，就再从其它socket上分配。

malloc_heap_alloc()：从rte_config.mem_config->malloc_heaps[]数组中找到指定socket对应的堆（使用struct  malloc_heap描述堆），即，从这个堆中分配空间。如果该堆是第一次使用，还没有被初始化过，则调用malloc_heap_init()初始化；首先，调用find_suitable_element()在堆中查找是否有合适内存可以分配，如果没有，则调用malloc_heap_add_memzone()在rte_config.mem_config->memzone[]中给堆分配一块内存。最后，调用malloc_elem_alloc()在堆中，将需要分配的内存划分出去。

## 收发包

### 队列设置

```c
// 创建收发包队列使用的内存
struct rte_mempool *
rte_pktmbuf_pool_create(const char *name, unsigned n,
	unsigned cache_size, uint16_t priv_size, uint16_t data_room_size,
	int socket_id);

// 检查Rx和Tx描述符（mbuf）的数量是否满足网卡的描述符限制，不满足将其调整为边界（改变其值）
// nb_rx_desc和nb_tx_desc默认值为1024
int rte_eth_dev_adjust_nb_rx_tx_desc(uint16_t port_id,
				     uint16_t *nb_rx_desc,
				     uint16_t *nb_tx_desc);

int rte_eth_rx_queue_setup(uint16_t port_id, uint16_t rx_queue_id,
		uint16_t nb_rx_desc, unsigned int socket_id,
		const struct rte_eth_rxconf *rx_conf,
		struct rte_mempool *mb_pool);

int rte_eth_tx_queue_setup(uint16_t port_id, uint16_t tx_queue_id,
		uint16_t nb_tx_desc, unsigned int socket_id,
		const struct rte_eth_txconf *tx_conf);
```

- 配置下发 rte_eth_dev_configure

   rte_eth_dev_configure接口使得应用层可以对网卡进行配置下发操作，将应用层提供的网卡信息保存到网卡数据空间struct  rte_eth_dev_data中，这样pmd用户态驱动就可以根据应用层提供的配置对网卡进行设置操作。另外这个接口还会为网卡的发送队列，接收队列开辟二级指针空间；

- 网卡接收队列设置 rte_eth_rx_queue_setup

  网卡接收队列设置，主要是为网卡开辟接收队列空间，也就是一级指针。上面的rte_eth_dev_configure接口只是开辟一个二级指针空间，这里是为网卡接收队列开辟一级指针空间。

### 收发包接口

- 收包

```c
rte_eth_rx_burst
```

- 发包

```c
rte_eth_tx_burst
```

## 样例

```c
int main(int argc, char **argv)
{
    int ret = rte_eal_init(argc, argv);
}
```

# reference

1. https://www.sdnlab.com/24519.html
2. https://blog.csdn.net/shaoyunzhe/article/details/7887096
2. https://blog.csdn.net/hejin_some/article/details/72146794
2. https://blog.csdn.net/wangquan1992/article/details/104061618