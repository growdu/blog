# linux巨页内存指北

巨页的实现，涉及到两个模块：hugetlb和hugetlbfs。

- hugetlb

  >struct  hstate  hstates[HUGE_MAX_HSTATE];
  >上面定义了一个hstate数组，每个元素是一个巨页池。不同的巨页池，其巨页尺寸是不一样的，例如2M的，4M的，1G的等等。
  >系统中可能会有多个巨页池，每一个池的巨页尺寸都是不一样的。
  >max_hstate标识当前有多少个hstate，即数组的前多少个元素是有效的。默认的话，hugetlb_init中会创建一个hstate，其page size是默认大小，此hstate也就成了默认的hstate。如果hugetlb.c被编译进内核，并且内核启动的时候，命令行参数中有hugepagesz=选项。那么就会调setup_hugepagesz进行处理，setup_hugepagesz应该会在hugetlb_init之前执行。setup_hugepagesz中会调用hugetlb_add_hstate添加一个hstate，其pagesize大小为命令行参数中指定的大小。每一个hstate，在/sys/kernel/mm/hugepages下面会有一个目录与之对应。通过读写此目录下的文件，即可实现对此hstate的各种属性的查看与修改。例如，可以查看或修改此hstate的页面数量。
  >例如，下面的命令将2M巨页池的页面数设置为N
  >echo  N  > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages
  >如果N小于当前池中的页面数量，则会归还相应的页面给内核。如果N为0，就全还给内核了。但是，必须等程序释放了内存，这些内存才会真正还给内核。
  >如果程序还没释放，则这种需要释放还没释放的页面数，可以通过如下文件得知。
  >/sys/kernel/mm/hugepages/hugepages-2048kB/surplus_hugepages 

  > 当前系统具体是什么参数，可以在host上查看：cat /proc/cmdline

- hugetlbfs

  >hugetlbfs在加载时，会向内核注册hugetlbfs文件系统，并mount hugetlbfs文件系统到内核中，结果保存到hugetlbfs_vfsmount中。这个mount，没有使用什么参数，因此对应到默认的hstate。

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

## 巨页的使用

有两种方式，mmap方式和共享内存方式(shmget/shmat)。
但是，无论是通过哪种方式，最终都是通过对一个hugetlbfs类型的文件做内存映射而实现的(通过file->f_op->mmap完成)。

### mmap

> 这种方式，需要先通过如下命令mount一个hugetlbfs文件系统，通过pagesize指定页面大小。
>
> ```shell
> mount -t hugetlbfs none /mnt/path/to/hugetlbfs -o pagesize=2048K
> ```
>
> 这样的话，新挂载的文件系统，与页面大小为2048K的hstate相关联。接下来，在/mnt/path/to/hugetlbfs下面创建文件，然后打开文件并通过mmap进行内存映射即可

在编程时通过mmap来映射巨页，在这之前需保证有空闲的巨页可以使用。

```shell
# 查看时否有空闲巨页
grep Huge /proc/meminfo
# 此时没有巨页，需要进行配置
[root@localhost ~]# grep Huge /proc/meminfo
AnonHugePages:     14336 kB
HugePages_Total:       0
HugePages_Free:        0
HugePages_Rsvd:        0
HugePages_Surp:        0
Hugepagesize:       2048 kB
# 配置巨页，这里设置可用的巨页数为16（此处为虚拟机设置）
echo 16 > /proc/sys/vm/nr_hugepages
# 物理机
echo 16 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages
```

使用如下方式将巨页映射到本进程:

```c
#include <sys/mman.h>
#include <stdio.h>
#include <memory.h>
 
int main(int argc, char *argv[]) {
  char *m;
  size_t s = (8UL * 1024 * 1024);
 
  m = mmap(NULL, s, PROT_READ | PROT_WRITE,
                    MAP_PRIVATE | MAP_ANONYMOUS | 0x40000 /*MAP_HUGETLB*/, -1, 0);
  if (m == MAP_FAILED) {
    perror("map mem");
    m = NULL;
    return 1;
  }
 
  memset(m, 0, s);
 
  printf("map_hugetlb ok, press ENTER to quit!\n");
  getchar();
 
  munmap(m, s);
  return 0;
}
```

其测试demo.c如下:

```c
#include <sys/mman.h>
#include <stdio.h>
#include <memory.h>

#define MB_1 (1024*1024)
#define MB_8 (8*MB_1)

char *a;

void init_hugetlb_seg()
{
  size_t s = MB_8;
 
  a = mmap(NULL, s, PROT_READ | PROT_WRITE,
                    MAP_PRIVATE | MAP_ANONYMOUS | 0x40000 /*MAP_HUGETLB*/, -1, 0);
  if (a == MAP_FAILED) {
    printf("map mem failed\n");
    a = NULL;
    exit(-1);
  }
}

void wr_to_array()
{
  int i;
  memset(a, 0, s);
  for( i=0 ; i<MB_8 ; i++) {
    a[i] = 'A';
  }
}

// 按字节读取8M的内存，并统计‘A’和写入的个数是否相等
// 相等则读取成功，不相等则读取失败
void rd_from_array()
{
  int i, count = 0;
  for( i=0 ; i<MB_8 ; i++)
    if (a[i] == 'A') count++;
  if (count==i)
    printf("HugeTLB read success :-)\n");
  else
    printf("HugeTLB read failed :-(\n");
}

int main(int argc, char *argv[])
{
  // 申请内存
  init_hugetlb_seg();
  printf("HugeTLB memory segment initialized !\n");
  printf("Press any key to write to memory area\n");
  getchar();
  // 写入测试数据
  wr_to_array();
  printf("Press any key to rd from memory area\n");
  getchar();
  // 读取测试数据
  rd_from_array();
  printf("Press any key to free memory area\n");
  getchar();
  // 释放内存
  munmap(a, MB_8);
  return 0;
}
```

针对以上四步分别查看大页内存的使用情况：

- 申请内存

  ```shell
  [root@localhost ~]# grep Huge /proc/meminfo
  AnonHugePages:     16384 kB
  HugePages_Total:      16
  HugePages_Free:       16
  HugePages_Rsvd:        4
  HugePages_Surp:        0
  Hugepagesize:       2048 kB
  ```

  申请内存后会阻塞等待输入字符，此时另起一个终端查看巨页情况。可以看到系统保留了4个2048kb的巨页，刚好对应申请的8M内存。

- 写入测试数据

  随意按下一个字符后开始写入测试数据，写入完成后会再次阻塞等待输入字符。此时巨页情况如下所示：

  ```shell
  [root@localhost ~]# grep Huge /proc/meminfo
  AnonHugePages:     16384 kB
  HugePages_Total:      16
  HugePages_Free:       12
  HugePages_Rsvd:        0
  HugePages_Surp:        0
  Hugepagesize:       2048 kB
  ```

  可以看到4个2048kb的巨页已经被使用，free的仅剩下12个。

- 读取测试数据

  随意按下一个字符后开始读取测试数据，读取完成后会再次阻塞等待输入字符。此时巨页情况如下所示：

  ```shell
  [root@localhost ~]# grep Huge /proc/meminfo
  AnonHugePages:     16384 kB
  HugePages_Total:      16
  HugePages_Free:       12
  HugePages_Rsvd:        0
  HugePages_Surp:        0
  Hugepagesize:       2048 kB
  ```

  此时巨页为发生变化，且读取数据均为写入数据。

- 释放内存

  随意按下一个字符后开始释放内存，释放完成后进程退出。此时巨页情况如下所示：

  ```shell
  [root@localhost ~]# grep Huge /proc/meminfo
  AnonHugePages:     16384 kB
  HugePages_Total:      16
  HugePages_Free:       16
  HugePages_Rsvd:        0
  HugePages_Surp:        0
  Hugepagesize:       2048 kB
  ```

  可以发现巨页个数又恢复到了最开始配置的16个。

### shmget

shmget属于**XSI共享内存**，是X/Open组织对UNIX定义的一套接口标准（X/Open System Interface）。其底层实现与mmap一致。

在编程时通过shmget来访问巨业，在这之前需保证有空闲的巨页可以使用。

```shell
# 查看时否有空闲巨页
grep Huge /proc/meminfo
# 此时没有巨页，需要进行配置
[root@localhost ~]# grep Huge /proc/meminfo
AnonHugePages:     14336 kB
HugePages_Total:       0
HugePages_Free:        0
HugePages_Rsvd:        0
HugePages_Surp:        0
Hugepagesize:       2048 kB
# 配置巨页，这里设置可用的巨页数为16（此处为虚拟机设置）
echo 16 > /proc/sys/vm/nr_hugepages
# 物理机
echo 16 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages
```

按照如下命令设置巨页后，因为我们的巨页页面大小为2048kb（2M），设置了16个页面后，我们可以使用32M内存。

要使用巨页，需要把巨页内存attach到当前进程内。实现代码如下：

```c
#define MB_1 (1024*1024)
#define MB_8 (8*MB_1)

char *a;
int shmid1;

void init_hugetlb_seg()
{
  // 2是共享内存key，用于标识内存，可随意设置
  // SHM_HUGETLB是基于大页内存创建共享内存的标志
  shmid1 = shmget(2, MB_8, SHM_HUGETLB 
         | IPC_CREAT | SHM_R /* 创建并具有读写权限*/
         | SHM_W);
  if ( shmid1 < 0 ) {
    perror("shmget");
    exit(1);
  }
  printf("HugeTLB shmid: 0x%x\n", shmid1);
  // 将内存attach到进程，后面基于地址a进行大页内存操作
  a = shmat(shmid1, 0, 0);
  if (a == (char *)-1) {
    perror("Shared memory attach failure");
    shmctl(shmid1, IPC_RMID, NULL);
    exit(2);
  }
}
```

上面即获取到了大页内存的起始地址，可以根据该地址和内存长度实现内存池。

下面是具体的巨页内存使用demo.c：

```c
#include <stdio.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <stdlib.h>

#define MB_1 (1024*1024)
#define MB_8 (8*MB_1)

char  *a;
int shmid1;

void init_hugetlb_seg()
{
  // 2是共享内存key，用于标识内存，可随意设置
  // SHM_HUGETLB是基于大页内存创建共享内存的标志
  shmid1 = shmget(2, MB_8, SHM_HUGETLB 
         | IPC_CREAT | SHM_R /* 创建并具有读写权限*/
         | SHM_W);
  if ( shmid1 < 0 ) {
    perror("shmget");
    exit(1);
  }
  printf("HugeTLB shmid: 0x%x\n", shmid1);
  // 将内存attach到进程，后面基于地址a进行大页内存操作
  a = shmat(shmid1, 0, 0);
  if (a == (char *)-1) {
    perror("Shared memory attach failure");
    shmctl(shmid1, IPC_RMID, NULL);
    exit(2);
  }
}

// 对申请的8M大页内存按字节每字节都写入字符‘A’：
void wr_to_array()
{
  int i;
  for( i=0 ; i<MB_8 ; i++) {
    a[i] = 'A';
  }
}

// 按字节读取8M的内存，并统计‘A’和写入的个数是否相等
// 相等则读取成功，不相等则读取失败
void rd_from_array()
{
  int i, count = 0;
  for( i=0 ; i<MB_8 ; i++)
    if (a[i] == 'A') count++;
  if (count==i)
    printf("HugeTLB read success :-)\n");
  else
    printf("HugeTLB read failed :-(\n");
}

int main(int argc, char *argv[])
{
  // 申请内存
  init_hugetlb_seg();
  printf("HugeTLB memory segment initialized !\n");
  printf("Press any key to write to memory area\n");
  getchar();
  // 写入测试数据
  wr_to_array();
  printf("Press any key to rd from memory area\n");
  getchar();
  // 读取测试数据
  rd_from_array();
  printf("Press any key to free memory area\n");
  getchar();
  // 释放内存
  shmctl(shmid1, IPC_RMID, NULL);
  return 0;
}
```

```makefile
gcc demo.c -o demo
```

针对以上四步分别查看大页内存的使用情况：

- 申请内存

  ```shell
  [root@localhost ~]# grep Huge /proc/meminfo
  AnonHugePages:     16384 kB
  HugePages_Total:      16
  HugePages_Free:       16
  HugePages_Rsvd:        4
  HugePages_Surp:        0
  Hugepagesize:       2048 kB
  ```

  申请内存后会阻塞等待输入字符，此时另起一个终端查看巨页情况。可以看到系统保留了4个2048kb的巨页，刚好对应申请的8M内存。

- 写入测试数据

  随意按下一个字符后开始写入测试数据，写入完成后会再次阻塞等待输入字符。此时巨页情况如下所示：

  ```shell
  [root@localhost ~]# grep Huge /proc/meminfo
  AnonHugePages:     16384 kB
  HugePages_Total:      16
  HugePages_Free:       12
  HugePages_Rsvd:        0
  HugePages_Surp:        0
  Hugepagesize:       2048 kB
  ```

  可以看到4个2048kb的巨页已经被使用，free的仅剩下12个。

- 读取测试数据

  随意按下一个字符后开始读取测试数据，读取完成后会再次阻塞等待输入字符。此时巨页情况如下所示：

  ```shell
  [root@localhost ~]# grep Huge /proc/meminfo
  AnonHugePages:     16384 kB
  HugePages_Total:      16
  HugePages_Free:       12
  HugePages_Rsvd:        0
  HugePages_Surp:        0
  Hugepagesize:       2048 kB
  ```

  此时巨页为发生变化，且读取数据均为写入数据。

- 释放内存

  随意按下一个字符后开始释放内存，释放完成后进程退出。此时巨页情况如下所示：

  ```shell
  [root@localhost ~]# grep Huge /proc/meminfo
  AnonHugePages:     16384 kB
  HugePages_Total:      16
  HugePages_Free:       16
  HugePages_Rsvd:        0
  HugePages_Surp:        0
  Hugepagesize:       2048 kB
  ```

  可以发现巨页个数又恢复到了最开始配置的16个。

通过对比可以发现，mmap的接口比shmget要更加简洁。

# reference

1. https://blog.csdn.net/zhang123456456/article/details/77853345
2. https://blog.csdn.net/weixin_35664258/article/details/83348133
3. https://www.cnblogs.com/zfox2017/p/6794617.html
3. https://blog.csdn.net/crazycoder8848/article/details/44983265
3. https://blog.csdn.net/weixin_30363509/article/details/96763008?spm=1001.2101.3001.6661.1&utm_medium=distribute.pc_relevant_t0.none-task-blog-2%7Edefault%7ECTRLIST%7Edefault-1.pc_relevant_default&depth_1-utm_source=distribute.pc_relevant_t0.none-task-blog-2%7Edefault%7ECTRLIST%7Edefault-1.pc_relevant_default&utm_relevant_index=1
3. https://www.cnblogs.com/xianzhedeyu/p/5784105.html