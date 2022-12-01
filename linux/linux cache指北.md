# linux cache指北

## cache是什么

计算机中数据存取满足“二八定律”(局部性原理)，为了以较低的成本大幅提高性能，现代cpu都有cache。cpu cache已经发展到了三级缓存结构，基本上现在买的个人电脑都是L3结构。其中L1和L2cache为每个核独有，L3则所有核共享。

本文内容大量摘抄自[飘舞的雪的博客](https://www.cnblogs.com/snow826520/p/8574824.html)，详情请参阅原文。

### cache bouncing

> 为了保证所有的核看到正确的内存数据，一个核在写入自己的L1 cache后，CPU会执行[Cache一致性](https://en.wikipedia.org/wiki/Cache_coherence)算法把对应的[cacheline](https://en.wikipedia.org/wiki/CPU_cache#Cache_entries)(一般是64字节)同步到其他核。这个过程并不很快，是微秒级的，相比之下写入L1  cache只需要若干纳秒。当很多线程在频繁修改某个字段时，这个字段所在的cacheline被不停地同步到不同的核上，就像在核间弹来弹去，这个现象就叫做cache bouncing。由于实现cache一致性往往有硬件锁，cache bouncing是一种隐式的的全局竞争。
>
> cache bouncing使访问频繁修改的变量的开销陡增，甚至还会使访问同一个cacheline中不常修改的变量也变慢，这个现象是[false sharing](https://en.wikipedia.org/wiki/False_sharing)。按cacheline对齐能避免false  sharing，但在某些情况下，我们甚至还能避免修改“必须”修改的变量。当很多线程都在累加一个计数器时，我们让每个线程累加私有的变量而不参与全局竞争，在读取时我们累加所有线程的私有变量。虽然读比之前慢多了，但由于这类计数器的读多为低频展现，慢点无所谓。而写就快多了，从微秒到纳秒，几百倍的差距。

## cache的意义

> 为什么需要CPU  cache？因为CPU的频率太快了，快到主存跟不上，这样在处理器时钟周期内，CPU常常需要等待主存，浪费资源。所以cache的出现，是为了缓解CPU和内存之间速度的不匹配问题（结构：cpu -> cache -> memory）。
>
> 　　CPU cache有什么意义？cache的容量远远小于主存，因此出现cache miss在所难免，既然cache不能包含CPU所需要的所有数据，那么cache的存在真的有意义吗？当然是有意义的——局部性原理。
>
>   A. 时间局部性：如果某个数据被访问，那么在不久的将来它很可能被再次访问；
>
>   B. 空间局部性：如果某个数据被访问，那么与它相邻的数据很快也可能被访问；

### cache和寄存器

> 存储器的三个性能指标——速度、容量和每位价格——导致了计算机组成中存储器的多级层次结构，其中主要是缓存和主存、主存和磁盘的结构。

一般情况下，速度越快，容量越小，价格越高。按照速率从高到低各级存储介质排序如下：

- 寄存器
- cache
- 内存
- 磁盘

## cpu cache结构

### 单核CPU cache

单核cpu为二级缓存，因为不存在核之间共享，因为没有三级缓存。

> 在单核CPU结构中，为了缓解CPU指令流水中cycle冲突，L1分成了指令（L1P）和数据（L1D）两部分，而L2则是指令和数据共存。

### 多核CPU cache

多核cpu为三级缓存，L3为各个核心共享。

> 多核CPU的结构与单核相似，但是多了所有CPU共享的L3三级缓存。在多核CPU的结构中，L1和L2是CPU私有的，L3则是所有CPU核心共享的。

## cache 一致性

> 缓存一致性：用于保证多个CPU cache之间缓存共享数据的一致。

### cache 的写方式

> -  write through（写通）：每次CPU修改了cache中的内容，立即更新到内存，也就意味着每次CPU写共享数据，都会导致总线事务，因此这种方式常常会引起总线事务的竞争，高一致性，但是效率非常低；
> - write back（写回）：每次CPU修改了cache中的数据，不会立即更新到内存，而是等到cache line在某一个必须或合适的时机才会更新到内存中；
>
> 　　无论是写通还是写回，在多线程环境下都需要处理缓存cache一致性问题。为了保证缓存一致性，处理器又提供了写失效（write invalidate）和写更新（write update）两个操作来保证cache一致性。
>
> - 写失效：当一个CPU修改了数据，如果其他CPU有该数据，则通知其为无效；
> - 写更新：当一个CPU修改了数据，如果其他CPU有该数据，则通知其更新数据；
>
> 　　写更新会导致大量的更新操作，因此在MESI协议中，采取的是写失效（即MESI中的I：invalid，如果采用的是写更新，那么就不是MESI协议了，而是MESU协议）

### cache line

缓存的换入换出是以cacheline为单位的，一般的cacheline为64byte。因而在一些性能要求较高的程序中，我们会看到大量的内存对齐，比如vpp，目的就是为了尽量将数据装在cacheline里面。减少换入换出的次数。

> cache line是cache与内存数据交换的最小单位，根据操作系统一般是32byte或64byte。在MESI协议中，状态可以是M、E、S、I，地址则是cache line中映射的内存地址，数据则是从内存中读取的数据。
>
> - 工作方式：当CPU从cache中读取数据的时候，会比较地址是否相同，如果相同则检查cache line的状态，再决定该数据是否有效，无效则从主存中获取数据，发起一次RR（remote read）；
> - 工作效率：当CPU能够从cache中拿到有效数据的时候，消耗几个CPU cycle，如果发生cache miss，则会消耗几十上百个CPU cycle

### MESI协议

#### cache状态

> MESI协议将cache line的状态分成modify、exclusive、shared、invalid，分别是修改、独占、共享和失效。
>
> - modify：当前CPU cache拥有最新数据（最新的cache line），其他CPU拥有失效数据（cache line的状态是invalid），虽然当前CPU中的数据和主存是不一致的，但是以当前CPU的数据为准；
> - exclusive：只有当前CPU中有数据，其他CPU中没有改数据，当前CPU的数据和主存中的数据是一致的
> - shared：当前CPU和其他CPU中都有共同数据，并且和主存中的数据一致
> - invalid：当前CPU中的数据失效，数据应该从主存中获取，其他CPU中可能有数据也可能无数据，当前CPU中的数据和主存被认为是不一致的；

#### cache操作

> MESI协议中，每个cache的控制器不仅知道自己的操作（local read和local  write），通过监听也知道其他CPU中cache的操作（remote read和remote  write）。对于自己本地缓存有的数据，CPU仅需要发起local操作，否则发起remote操作，从主存中读取数据，cache控制器通过总线监听，仅能够知道其他CPU发起的remote操作，但是如果local操作会导致数据不一致性，cache控制器会通知其他CPU的cache控制器修改状态。
>
> - local read（LR）：读本地cache中的数据；
> - local write（LW）：将数据写到本地cache；
> - remote read（RR）：读取内存中的数据；
> - remote write（RW）：将数据写通到主存

#### cache状态转换和cache操作

cache状态转换的重点是，当有某一个cpu核心操作主存（读取和写入）时，其他核心能感知到并进行状态修改和数据更新。

> MESI协议中cache line数据状态有4种，引起数据状态转换的CPU cache操作也有4种，因此要理解MESI协议，就要将这16种状态转换的情况讨论清楚。
>
> 初始场景：在最初的时候，所有CPU中都没有数据，某一个CPU发生读操作，此时发生RR，数据从主存中读取到当前CPU的cache，状态为E（独占，只有当前CPU有数据，且和主存一致），此时如果有其他CPU也读取数据，则状态修改为S（共享，多个CPU之间拥有相同数据，并且和主存保持一致），如果其中某一个CPU发生数据修改，那么该CPU中数据状态修改为M（拥有最新数据，和主存不一致，但是以当前CPU中的为准），并通知其他拥有该数据的CPU数据失效，其他CPU中的cache line状态修改为I（失效，和主存中的数据被认为不一致，数据不可用应该重新获取）
>
> - modify
>
>   场景：当前CPU中数据的状态是modify，表示当前CPU中拥有最新数据，虽然主存中的数据和当前CPU中的数据不一致，但是以当前CPU中的数据为准；
>
>   - LR：此时如果发生local read，即当前CPU读数据，直接从cache中获取数据，拥有最新数据，因此状态不变；
>   - LW：直接修改本地cache数据，修改后也是当前CPU拥有最新数据，因此状态不变；
>   - RR：因为本地内存中有最新数据，因此当前CPU不会发生RR和RW，当本地cache控制器监听到总线上有RR发生的时，必然是其他CPU发生了读主存的操作，此时为了保证一致性，当前CPU应该将数据写回主存，而随后的RR将会使得其他CPU和当前CPU拥有共同的数据，因此状态修改为S；
>   - RW：同RR，当cache控制器监听到总线发生RW，当前CPU会将数据写回主存，因为随后的RW将会导致主存的数据修改，因此状态修改成I；
>
> - exclusive
>
>   场景：当前CPU中的数据状态是exclusive，表示当前CPU独占数据（其他CPU没有数据），并且和主存的数据一致；
>
>   - LR：从本地cache中直接获取数据，状态不变；
>   - LW：修改本地cache中的数据，状态修改成M（因为其他CPU中并没有该数据，因此不存在共享问题，不需要通知其他CPU修改cache line的状态为I）；
>   - RR：因为本地cache中有最新数据，因此当前CPU  cache操作不会发生RR和RW，当cache控制器监听到总线上发生RR的时候，必然是其他CPU发生了读取主存的操作，而RR操作不会导致数据修改，因此两个CPU中的数据和主存中的数据一致，此时cache line状态修改为S；
>   - RW：同RR，当cache控制器监听到总线发生RW，发生其他CPU将最新数据写回到主存，此时为了保证缓存一致性，当前CPU的数据状态修改为I；
>
> - shared
>
>   场景：当前CPU中的数据状态是shared，表示当前CPU和其他CPU共享数据，且数据在多个CPU之间一致、多个CPU之间的数据和主存一致；
>
>   - LR：直接从cache中读取数据，状态不变；
>   - LW：发生本地写，并不会将数据立即写回主存，而是在稍后的一个时间再写回主存，因此为了保证缓存一致性，当前CPU的cache line状态修改为M，并通知其他拥有该数据的CPU该数据失效，其他CPU将cache line状态修改为I；
>   - RR：状态不变，因为多个CPU中的数据和主存一致；
>   - RW：当监听到总线发生了RW，意味着其他CPU发生了写主存操作，此时本地cache中的数据既不是最新数据，和主存也不再一致，因此当前CPU的cache line状态修改为I；
>
> - invalid
>
>   场景：当前CPU中的数据状态是invalid，表示当前CPU中是脏数据，不可用，其他CPU可能有数据、也可能没有数据；
>
>   - LR：因为当前CPU的cache line数据不可用，因此会发生RR操作，此时的情形如下。
>
>   ​           A. 如果其他CPU中无数据则状态修改为E；
>
>      　　B. 如果其他CPU中有数据且状态为S或E则状态修改为S；
>
>      　　C. 如果其他CPU中有数据且状态为M，那么其他CPU首先发生RW将M状态的数据写回主存并修改状态为S，随后当前CPU读取主存数据，也将状态修改为S；
>
>   - LW：因为当前CPU的cache line数据无效，因此发生LW会直接操作本地cache，此时的情形如下。
>
>      　　A. 如果其他CPU中无数据，则将本地cache line的状态修改为M；
>
>      　　B. 如果其他CPU中有数据且状态为S或E，则修改本地cache，通知其他CPU将数据修改为I，当前CPU中的cache line状态修改为M；
>
>      　　C. 如果其他CPU中有数据且状态为M，则其他CPU首先将数据写回主存，并将状态修改为I，当前CPU中的cache line转台修改为M；
>
>   - RR：监听到总线发生RR操作，表示有其他CPU读取内存，和本地cache无关，状态不变；
>
>   - RW：监听到总线发生RW操作，表示有其他CPU写主存，和本地cache无关，状态不变；

# reference

1. https://www.cnblogs.com/snow826520/p/8574824.html