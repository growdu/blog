# 内存管理之dlmalloc

## 基础知识

### 内存分配原理

> 首先我们需要知道的是allocator与普通程序一样都工作在用户态,并且其本身也是作为system heap的一部分。当用户通过malloc之类的库函数提交分配请求后,将首先由allocator查找,如果在其内部保留的空间中找到满足需求的内存块,就将之返回给用户(一般都是相对较小的块).如果找不到合适的块,则进一步向system发起请求,将划分system heap上的一部分给allocator,再由后者划拨给用户.另一方面,在划拨heap空间后,这部分新生成的空间其实还无法直接使用,系统会在合适的时机,通过名为MMU的硬件将实际物理内存上的某些区域(以page为单位),映射到需要使用的线性地址上.这样就完成了一块内存从申请到使用的全过程。转自[dlmalloc 2.8.6 源码详解](https://blog.csdn.net/vector03/article/details/40977679)

> 从这些描述上, 你可能会感受到一点, allocator和system之间的关系就如批发和零售的关系一样. System作为批发商,手中握有大量的待批商品——线性地址.而allocator作为零售商,会不定期的从批发商手里提货,将这些一次性批来的地址再进行二次管理.当用户程序作为顾客,向零售商购买商品时, allocator的整套算法都是为了保证尽可能的将货都卖出去而不砸在手里,也就是尽量避免在尚有存货的情况下向批发商购进新的货品.同时,它还要保证能在最快的时间将这些货卖出去. Allocator的初衷就是帮助用户程序又快又好的管理system heap中的内存。转自[dlmalloc 2.8.6 源码详解](https://blog.csdn.net/vector03/article/details/40977679)

### linux进程地址空间

>
>
>进程空间从低地址到高地址依次分为：
>
>- 保留区
>- text段
>- data段
>- bss段
>- heap区
>- mmap区
>- stack
>
>应用程序的内存分配事实上是通过在中间空洞两边的heap区和mmap区相对生长来完成的.因此我们常说的动态内存在堆区分配其实是不准确的.转自[dlmalloc 2.8.6 源码详解](https://blog.csdn.net/vector03/article/details/40977679)

# reference

1. https://blog.csdn.net/vector03/article/details/40977679