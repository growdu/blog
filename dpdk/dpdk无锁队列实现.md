# dpdk无锁队列实现

rte_ring是dpdk内部提供的一种无锁队列实现。

## vpp线程模型

- Main Thread做管理。常常使用协程驱动实现单线程多任务（VPP内部实现了一套类似于协程的调度机制，以此来实现单线程多任务的调度）
- fwd Thread做纯转发。通常为了性能考虑，在转发路径上严禁有内存拷贝和系统调用（但是凡事都有例外）。

## dpdk ring使用

```c
// dpdk19.11
void rte_ring_free(struct rte_ring *r) //释放已经创建的dpdk的rte_ring
    
struct rte_ring * rte_ring_lookup(const char *name) //去寻找一个已经创建好的dpdk的rte_ring
    
static __rte_always_inline unsigned int __rte_ring_do_enqueue(struct rte_ring *r, void * const *obj_table, unsigned int n, enum rte_ring_queue_behavior behavior, unsigned int is_sp, unsigned int *free_space) //此函数为内部方法，所有入队函数都是此函数的上层封装
    
static __rte_always_inline unsigned int __rte_ring_do_dequeue(struct rte_ring *r, void **obj_table, unsigned int n, enum rte_ring_queue_behavior behavior, unsigned int is_sc, unsigned int *available) //此函数为内部方法，所有出队函数都是此函数的上层封装
    
static __rte_always_inline unsigned int rte_ring_mp_enqueue_bulk(struct rte_ring *r, void * const *obj_table, unsigned int n, unsigned int *free_space) //此函数为批量入队函数，为多生产者安全(multi producer)
    
static __rte_always_inline unsigned int
rte_ring_sp_enqueue_bulk(struct rte_ring *r, void * const *obj_table, unsigned int n, unsigned int *free_space) //此函数为批量入队函数，为单生产者安全(single producer)
    
static __rte_always_inline unsigned int rte_ring_enqueue_bulk(struct rte_ring *r, void * const *obj_table, unsigned int n, unsigned int *free_space) //此函数为批量入队函数，具体安全性质取决于创建队列时的标志(flags)
    
static __rte_always_inline unsigned int rte_ring_mc_dequeue_bulk(struct rte_ring *r, void **obj_table, unsigned int n, unsigned int *available) //此函数为批量出队函数，为多消费者安全(multi consumer)
    
static __rte_always_inline unsigned int rte_ring_sc_dequeue_bulk(struct rte_ring *r, void **obj_table, unsigned int n, unsigned int *available) //此函数为批量出队函数，为单消费者安全(single consumer)
    
static __rte_always_inline unsigned int rte_ring_dequeue_bulk(struct rte_ring *r, void **obj_table, unsigned int n, unsigned int *available) //此函数为批量出队函数，具体安全性质取决于创建队列时的标志(flags)
    
static inline unsigned rte_ring_count(const struct rte_ring *r) //此函数用于查看队列中元素的数量
```

## 无锁队列实现

> ```
> 无锁的实现依赖于一个汇编指令: cmpxchg
> 翻译过来就是compare and change
> ```

### 生产者消费者问题

1. 多个生产者，生产位置有冲突，比如生产者A要push 3个元素，生产者B要push 3个元素，如何做到不冲突不覆盖？
2. 生产者和消费者，生产了之后要让消费者可以消费，消费了之后要让生产者进行生产。
3. 多消费者，和多生产者的问题类似，消费位置冲突，比如消费者A要消费3个元素，消费者B要消费3个元素，如何做到消费不冲突让每一个消费者都能有元素可以消费？

```c
struct rte_ring {
    char name[RTE_MEMZONE_NAMESIZE] __rte_cache_aligned; // ring的名称，lookup的时候就是根据名称进行查找对应的ring

    int flags;                                           // 标记，用来描述队列是单/多生产者还是单/多消费者安全

    const struct rte_memzone *memzone;                     // 所属的memzone，memzone是dpdk内存管理底层的数据结构

    uint32_t size;                                        // 队列长，为2^n。如果flags为RING_F_EXACT_SZ
                                                         // 队列size为初始化时队列长度的向上取2的n次幂，例如如果为
                                                         // 7，那么向上取最近的2^n幂的数为8.如果flags不为
                                                         // RING_F_EXACT_SZ，那么初始化队列的时候队列长必须为2^n幂                                                         

    uint32_t mask;                                         // 掩码，为队列长 - 1，用来计算位置的时候取余用
    uint32_t capacity;                                    // 队列容量，一般不等于队列长度，把队列容量理解为实际可以
                                                         // 使用的元素个数即可。例如初始化时count为7并且指定标志为
                                                         // RING_F_EXACT_SZ，那么count最后为8，但是capacity为7，因为
                                                         // 8是向上取2^n幂取出来的，实际上仍然是创建时所需的个数，8.

    char pad0 __rte_cache_aligned;                          // 填充，考虑到性能，要使用填充法保证cache line

    struct rte_ring_headtail prod __rte_cache_aligned;   // 生产者位置，里面有一个生产者头，即prod.head，还有一个生
                                                         // 产者尾，即prod.tail。prod.head代表着下一次生产时的起始
                                                         // 生产位置。prod.tail代表消费者可以消费的位置界限，到达
                                                         // prod.tail后就无法继续消费，通常情况下生产完成后，
                                                         // prod.tail = prod.head，意味着刚生产的元素皆可以被消费

    char pad1 __rte_cache_aligned;  
    struct rte_ring_headtail cons __rte_cache_aligned;   // 消费者位置，里面有一个消费者头，即cons.head，还有一个消
                                                         // 费者尾，即cons.tail。cons.head代表着下一次消费时的起始
                                                         // 消费位置。cons.tail代表生产者可以生产的位置界限，到达
                                                         // cons.tail后就无法继续生产，通常情况下消费完成后，
                                                         // cons.tail = cons.head，意味着刚消费的位置皆可以被生产
                                                         
    char pad2 __rte_cache_aligned; /**< empty cache line */
};
```

- 生产者：先抢占，再写入，再更新指针

  1. 先偏移头指针，说白了就是抢位置。这步主要是为了对付多生产者的情况。

  2. 抢到位置后写数据。

  3. 更新尾指针，让消费者可以消费刚塞入的数据

  ```c
  static __rte_always_inline unsigned int
  __rte_ring_move_prod_head(struct rte_ring *r, unsigned int is_sp,
          unsigned int n, enum rte_ring_queue_behavior behavior,
          uint32_t *old_head, uint32_t *new_head,
          uint32_t *free_entries)
  {
      const uint32_t capacity = r->capacity;
      unsigned int max = n;
      int success;
  
      do {
          //1.先确定生产者要生产多少个元素
          n = max;
          //2.拿到现在生产者的head位置，也就是即将生产的位置
          *old_head = r->prod.head;
  
          //内存屏障
          rte_smp_rmb();
  
          //3.计算剩余的空间
          *free_entries = (capacity + r->cons.tail - *old_head);
  
          //4.比较生产的元素个数和剩余空间
          if (unlikely(n > *free_entries))
              n = (behavior == RTE_RING_QUEUE_FIXED) ?
                      0 : *free_entries;
  
          if (n == 0)
              return 0;
          //5.计算生产后的新位置
          *new_head = *old_head + n;
          if (is_sp)
              r->prod.head = *new_head, success = 1;
          else //6.如果是多生产者的话调用cpmset函数实现生产位置抢占
              success = rte_atomic32_cmpset(&r->prod.head,
                      *old_head, *new_head);
      } while (unlikely(success == 0));
      return n;
  }
  ```

  ```c
  static inline int
  rte_atomic32_cmpset(volatile uint32_t *dst, uint32_t exp, uint32_t src)
  {
      uint8_t res;
  
      asm volatile(
              MPLOCKED
              "cmpxchgl %[src], %[dst];"
              "sete %[res];"
              : [res] "=a" (res),     /* output */
                [dst] "=m" (*dst)
              : [src] "r" (src),      /* input */
                "a" (exp),
                "m" (*dst)
              : "memory");            /* no-clobber list */
      return res;
  }
  ```

  >
  >
  >```
  >cmpxchg指令的意思就是“compare and change”，即“比较并交换”。
  >举个例子，如果A等于B，则将C赋值给A；如果A不等于B，则拒绝将C赋值给A。
  >```
  >
  >```
  >如果生产位置没有变化（A等于B），那么就将最新的生产位置（计算偏移后的生产位置）赋值给生产者指针；如果生产位置发生了变化（有其他生产者也在生产），那么就取消更新生产者指针
  >```

  ```c
  static __rte_always_inline void
  update_tail(struct rte_ring_headtail *ht, uint32_t old_val, uint32_t new_val,
          uint32_t single, uint32_t enqueue)
  {
      //1.内存屏障
      if (enqueue)
          rte_smp_wmb();
      else
          rte_smp_rmb();
      //2.如果有其他生产者生产数据，那么需要等待其将数据生产完更新tail指针后，本生产者才能更新tail指针
      if (!single)
          while (unlikely(ht->tail != old_val))
              rte_pause();
      //3.更新tail指针，更新的位置为最新的生产位置，意味着刚刚生产的数据已经全部可以被消费者消费
      ht->tail = new_val;
  }
  ```

  

- 消费者：先标记，再回收



# reference

1. https://www.cnblogs.com/jungle1996/p/12194243.html