# linux常用系统接口

## mprotect

> mprotect()函数可以修改调用进程内存页的保护属性，如果调用进程尝试以违反保护属性的方式访问该内存，则内核会发出一个SIGSEGV信号给该进程。
>
> ```c
> #include <sys/mman.h>
> int mprotect(void *addr, size_t len, int prot);
> addr：修改保护属性区域的起始地址，addr必须是一个内存页的起始地址，简而言之为页大小（一般是 4KB == 4096字节）整数倍。
> len：被修改保护属性区域的长度,最好为页大小整数倍。修改区域范围[addr, addr+len-1]。
> prot：可以取以下几个值，并可以用“|”将几个属性结合起来使用：
> 1）PROT_READ：内存段可读；
> 2）PROT_WRITE：内存段可写；
> 3）PROT_EXEC：内存段可执行；
> 4）PROT_NONE：内存段不可访问。
> 返回值：0；成功，-1；失败（并且errno被设置）
> 1）EACCES：无法设置内存段的保护属性。当通过 mmap(2) 映射一个文件为只读权限时，接着使用 mprotect() 标志为 PROT_WRITE这种情况就会发生。
> 2）EINVAL：addr不是有效指针，或者不是系统页大小的倍数。
> 3）ENOMEM：内核内部的结构体无法分配。
> ```
>
> 以上内容摘自[qiu.s.z的博客](https://blog.csdn.net/qq_15762939/article/details/104062307)。

## sysconf

>使用 sysconf() 函数确定可配置的系统变量的值。sysconf() 返回选项 (变量) 的当前值，这个值可配置的但也是受系统限制的。在成功完成的情况下，sysconf() 返回变量的当前值。该值受到的限制将少于编译时 <limits.h>， <unistd.h> 或 <time.h> 中可用的对应值。大多数这些变量的值在调用进程的生存时间内不变。
>
>```c
>#include <unistd.h>
>long sysconf ( int name); 
>```
>
>```c
>#include<stdio.h>
>#include<unistd.h>
>int main(void) {
>    long num_procs, page_size,num_pages,free_pages;
>	num_procs  =  sysconf (_SC_NPROCESSORS_CONF);
>	printf ( " CPU 个数为: %ld 个\n " , num_procs);
>
>	page_size  =  sysconf (_SC_PAGESIZE);
>    printf ( " 系统页面的大小为: %ld K\n " , page_size  /   1024  );
>
>    num_pages  =  sysconf (_SC_PHYS_PAGES);
>    printf ( " 系统中物理页数个数: %ld 个\n " , num_pages);
>}
>     
>    ```
>
>以上内容摘自[ketvin2011victory的博客](https://blog.csdn.net/ketvin2011victory/article/details/8062449)。

## syslog

>Linux C中提供一套系统日记写入接口，包括三个函数：openlog，syslog和closelog。
>
>调用openlog是可选择的。如果不调用openlog，则在第一次调用syslog时，自动调用openlog。调用closelog也是可选择的，它只是关闭被用于与syslog守护进程通信的描述符。
>
> ```c
> //#include //头文件
> 
> void openlog (char*ident, int option, int facility); 
> 
> void closelog(); 
> 
> void syslog(int priority, char*format,……);
> ```
>
>```shell
>var/log/dmesg      内核引导信息日志
>
>/var/log/message    标准系统错误信息日志
>
>/var/log/maillog    邮件系统信息日志
>
>/var/log/cron       计划任务日志
>
>/var/log/secure     安全信息日志
>
>/var/log/syslog     vpp日志
>```
>
>以上内容摘自[[bitbit](https://www.cnblogs.com/skyofbitbit/)的博客](https://www.cnblogs.com/skyofbitbit/p/3674664.html)。

## syscall

>
>
>```shell
>#include <unistd.h> 
>#include <sys/syscall.h> 
>#include <sys/types.h> 
>int main() {
>	long id = syscall(SYS_gettid);
>	printf("tid is %ld\n",id);
>}
>```
>
>

## open

open可以打开文件，读取文件内容。特别的，读取一些特别的文件可以获取一些系统信息。

### /proc/self/pagemap

>通过读取里面的内容就可以算出当前虚拟地址对应的物理页，然后加入page_offset就可以知道当前虚拟地址对应的物理地址。

> pagemap is a new (as of 2.6.25) set of interfaces in the kernel that allow
> userspace programs to examine the page tables and related information by
> reading files in /proc.
>
> There are four components to pagemap:
>
>  \* /proc/pid/pagemap. This file lets a userspace process find out which
>   physical frame each virtual page is mapped to. It contains one 64-bit
>   value for each virtual page, containing the following data (from
>   fs/proc/task_mmu.c, above pagemap_read):
>
>   \* Bits 0-54 page frame number (PFN) if present
>   \* Bits 0-4  swap type if swapped
>   \* Bits 5-54 swap offset if swapped
>   \* Bit 55  pte is soft-dirty (see Documentation/vm/soft-dirty.txt)
>   \* Bit 56  page exclusively mapped (since 4.2)
>   \* Bits 57-60 zero
>   \* Bit 61  page is file-page or shared-anon (since 3.5)
>   \* Bit 62  page swapped
>   \* Bit 63  page present
>
>   Since [Linux](https://so.csdn.net/so/search?q=Linux&spm=1001.2101.3001.7020) 4.0 only users with the CAP_SYS_ADMIN capability can get PFNs.
>   In 4.0 and 4.1 opens by unprivileged fail with -EPERM. Starting from
>   4.2 the PFN field is zeroed if the user does not have CAP_SYS_ADMIN.
>   Reason: information about PFNs helps in exploiting Rowhammer vulnerability.
>
>   If the page is not present but in swap, then the PFN contains an
>   encoding of the swap file number and the page's offset into the
>   swap. Unmapped pages return a null PFN. This allows determining
>   precisely which pages are mapped (or in swap) and comparing mapped
>   pages between processes.
>
>   Efficient users of this interface will use /proc/pid/maps to
>   determine which areas of memory are actually mapped and llseek to
>   skip over unmapped regions.

详情可查看[博客](https://blog.csdn.net/weixin_34191734/article/details/86122595).

pagemap文件为二进制文件，要查看其文件内容可以使用od命名：

```shell
od /proc/self/pagemap
```



## mmap

头文件 sys/mman.h

````c
void *mmap(void *start, size_t length, int prot, int flags, int fd, off_t offset);
int munmap(void *start, size_t length);
int msync ( void * addr , size_t len, int flags); //通过调用msync()实现磁盘上文件内容与共享内存区的内容一致
````

作用： 
 mmap将一个文件或者其他对象映射进内存，当文件映射到进程后，就可以直接操作这段虚拟地址进行文件的读写等操作。

> 参数说明：
> start：映射区的开始地址
> length：映射区的长度
> prot：期望的内存保护标志
> —-PROT_EXEC //页内容可以被执行
> —-PROT_READ //页内容可以被读取
> —-PROT_WRITE //页可以被写入
> —-PROT_NONE //页不可访问
> flags：指定映射对象的类型
> —-MAP_FIXED 如果你指定的地址和已有的线性区重叠，那么就抛弃已有的线性区映射
> —-MAP_SHARED 与其它所有映射这个对象的进程共享映射空间
> —-MAP_PRIVATE 建立一个写入时拷贝的私有映射。内存区域的写入不会影响到原文件
> —-MAP_ANONYMOUS 匿名映射，映射区不与任何文件关联;和使用/dev/zero映射一致
> fd：如果MAP_ANONYMOUS被设定，为了兼容问题，其值应为-1
> offset：被映射对象内容的起点

# reference

1. https://blog.csdn.net/luckywang1103/article/details/50619251