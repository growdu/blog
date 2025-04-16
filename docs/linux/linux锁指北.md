# linux锁指北

锁一般用于解决资源竞争，比如多进程或者多线程场景下。锁主要是为了保证同一个资源在同一时间只能被一名修改者修改。

## 互斥锁（mutex）

对于竞争资源来说，只要有一方获取了资源的锁，另一方就无法修改竞争资源，需要等待锁释放并获取到锁之后才能进行修改。

有两种方式创建互斥锁：

- 静态创建

  >
  >
  >POSIX定义了一个宏PTHREAD_MUTEX_INITIALIZER 来静态初始化互斥锁，方法如下：
  >
  >```c
  >pthread_mutex_t mutex=PTHREAD_MUTEX_INITIALIZER;
  >```
  >
  >在LinuxThreads实现中，pthread_mutex_t是一个结构，而PTHREAD_MUTEX_INITIALIZER则是一个结构常量。
  >————————————————
  >版权声明：本文为CSDN博主「佰慕哒Chow」的原创文章，遵循CC 4.0 BY-SA版权协议，转载请附上原文出处链接及本声明。
  >原文链接：https://blog.csdn.net/qq_18144747/article/details/86671284

- 动态创建

  >
  >
  >动态方式是采用pthread_mutex_init()函数来初始化互斥锁，API定义如下：
  >
  >```c
  > int pthread_mutex_init(pthread_mutex_t  *mutex, const pthread_mutexattr_t*mutexattr)
  >```
  >
  >其中mutexattr用于指定互斥锁属性（见下），如果为NULL则使用缺省属性。 pthread_mutex_destroy ()用于注销一个互斥锁，API定义如下：
  >
  >```c
  > int pthread_mutex_destroy(pthread_mutex_t *mutex)
  >```
  >
  >锁操作主要包括加锁pthread_mutex_lock()、解锁pthread_mutex_unlock()和测试加锁 pthread_mutex_trylock()三个，不论哪种类型的锁，都不可能被两个不同的线程同时得到， 而必须等待解锁。对于普通锁和适应锁类型，解锁者可以是同进程内任何线程； 而检错锁则必须由加锁者解锁才有效，否则返回EPERM；对于嵌套锁，文档和实现要求必须由 加锁者解锁，但实验结果表明并没有这种限制，这个不同目前还没有得到解释。在同一进程中 的线程，如果加锁后没有解锁，则任何其他线程都无法再获得锁。
  >
  >————————————————
  >版权声明：本文为CSDN博主「佰慕哒Chow」的原创文章，遵循CC 4.0 BY-SA版权协议，转载请附上原文出处链接及本声明。
  >原文链接：https://blog.csdn.net/qq_18144747/article/details/86671284

  pthread_mutex_unlock和pthread_mutex_trylock的区别在于前者会阻塞等待直到要获取的锁释放，而后者则不会等待锁释放，若锁被占用则直接返回EBUSY。

### 互斥锁的优点

>
>
>优点：由一块能够被多个进程共享的内存空间（一个对齐后的整型变量）组成；这个整型变量的值能够通过汇编语言调用CPU提供的原子操作指令来增加或减少，并且一个进程可以等待直到那个值变成正数。 的操作几乎全部在应用程序空间完成；只有当操作结果不一致从而需要仲裁时，才需要进入操作系统内核空间执行。这种机制允许使用的锁定原语有非常高的执行效率：由于绝大多数的操作并不需要在多个进程之间进行仲裁，所以绝大多数操作都可以在应用程序空间执行，而不需要使用（相对高代价的）内核系统调用。
>————————————————
>版权声明：本文为CSDN博主「佰慕哒Chow」的原创文章，遵循CC 4.0 BY-SA版权协议，转载请附上原文出处链接及本声明。
>原文链接：https://blog.csdn.net/qq_18144747/article/details/86671284

## 读写锁

特点：读写锁适合于对数据结构的读次数比写次数多得多的情况.因为,读模式锁定时可以共享,以写 模式锁住时意味着独占,所以读写锁又叫共享-独占锁.

```c
// 成功则返回0,出错则返回错误编号. 同互斥量以上,在释放读写锁占用的内存之前,需要先通过 pthread_rwlock_destroy对读写锁进行清理工作, 释放由init分配的资源.
int pthread_rwlock_init(pthread_rwlock_t *restrict rwlock, const
    pthread_rwlockattr_t *restrict attr);
int pthread_rwlock_destroy(pthread_rwlock_t *rwlock);
```

```c
// 成功则返回0,出错则返回错误编号.这3个函数分别实现获取读锁,获取写锁和释放锁的操作
int pthread_rwlock_rdlock(pthread_rwlock_t *rwlock);
int pthread_rwlock_wrlock(pthread_rwlock_t *rwlock);
int pthread_rwlock_unlock(pthread_rwlock_t *rwlock);
// 非阻塞接口
int pthread_rwlock_tryrdlock(pthread_rwlock_t *rwlock);
int pthread_rwlock_trywrlock(pthread_rwlock_t *rwlock);
```

## 自旋锁（spin_lock）

> 特点：轮询忙等待。
> 在单核cpu下不起作用：被自旋锁保护的临界区代码执行时不能进行挂起状态。会造成死锁
>自旋锁的初衷就是：在短期间内进行轻量级的锁定。一个被争用的自旋锁使得请求它的线程在等待锁重新可用的期间进行自旋（特别浪费处理器时间），所以自旋锁不应该被持有时间过长。如果需要长时间锁定的话, 最好使用信号量。
>————————————————
>版权声明：本文为CSDN博主「佰慕哒Chow」的原创文章，遵循CC 4.0 BY-SA版权协议，转载请附上原文出处链接及本声明。
>原文链接：https://blog.csdn.net/qq_18144747/article/details/86671284

## 条件变量

>与互斥锁不同，条件变量是用来等待而不是用来上锁的。条件变量用来自动阻塞一个线程，直到某特殊情况发生为止。通常条件变量和互斥锁同时使用。条件变量使我们可以睡眠等待某种条件出现。条件变量是利用线程间共享的全局变量进行同步的一种机制，主要包括两个动作：一个线程等待"条件变量的条件成立"而挂起；另一个线程使 "条件成立"（给出条件成立信号）。
>
>条件的检测是在互斥锁的保护下进行的。如果一个条件为假，一个线程自动阻塞，并释放等待状态改变的互斥锁。如果另一个线程改变了条件，它发信号给关联的条件变量，唤醒一个或多 个等待它的线程，重新获得互斥锁，重新评价条件。如果两进程共享可读写的内存，条件变量 可以被用来实现这两进程间的线程同步。
>————————————————
>版权声明：本文为CSDN博主「佰慕哒Chow」的原创文章，遵循CC 4.0 BY-SA版权协议，转载请附上原文出处链接及本声明。
>原文链接：https://blog.csdn.net/qq_18144747/article/details/86671284

```c
int pthread_cond_init(pthread_cond_t *cond,pthread_condattr_t *cond_attr);
int pthread_cond_wait(pthread_cond_t *cond,pthread_mutex_t *mutex);
int pthread_cond_timewait(pthread_cond_t *cond,pthread_mutex *mutex,const
      timespec *abstime);
int pthread_cond_destroy(pthread_cond_t *cond);
int pthread_cond_signal(pthread_cond_t *cond);
int pthread_cond_broadcast(pthread_cond_t *cond);  //解除所有线程的阻塞
```

## 信号量

信号量、共享内存，以及消息队列等System V IPC三剑客主要关注进程间通信；

而条件变量、互斥锁，主要关注线程间通信。

## 互斥锁、自旋锁、信号量的区别

>- 自旋锁是指没有获取到锁的线程就一直循环等待判断该资源是否已经释放锁，它不需要将线程阻塞起来，适合于线程不会长时间占用锁的场景。
>
>- 互斥锁是指没有获取到锁的线程就把自己阻塞起来，等待重新调度请求，适合于线程占用锁的时间较长的场景。
>
>通常来说，自旋锁的效率比互斥锁要高，损耗要小。

>信号量、互斥锁和自旋锁的区别
>
>信号量、互斥锁允许进程sleep属于睡眠锁，自旋锁不允许调用者sleep，而是让其循环等待，所以有以下区别应用：
>
>- 信号量和读写信号量适合于保持时间较长的情况，它们会导致调用者睡眠，因而自旋锁适合于保持时间非常短的情况；
>- 自旋锁可以用于中断，不能用于进程上下文(会引起死锁)，而信号量不允许使用在中断中，而可以用于进程上下文；
>- 自旋锁保持期间是抢占失效的，自旋锁被持有时，内核不能被抢占，而信号量和读写信号量保持期间是可以被抢占的。
>
>另外需要注意的是：
>
>信号量锁保护的临界区可包含可能引起阻塞的代码，而自旋锁则绝对要避免用来保护包含这样代码的临界区，因为阻塞意味着要进行进程的切换，如果进程被切换出去后，另一进程企图获取本自旋锁，死锁就会发生；
>占用信号量的同时不能占用自旋锁，因为在等待信号量时可能会睡眠，而在持有自旋锁时是不允许睡眠的。
>
>信号量和互斥锁的区别
>
>1、概念上的区别：     
>
>信号量：是进程间（线程间）同步用的，一个进程（线程）完成了某一个动作就通过信号量告诉别的进程（线程），别的进程（线程）再进行某些动作。有二值和多值信号量之分；
>
>互斥锁：是线程间互斥用的，一个线程占用了某一个共享资源，那么别的线程就无法访问，直到这个线程离开，其他的线程才开始可以使用这个共享资源。可以把互斥锁看成二值信号量。  
>
>2、上锁时：
>
>信号量: 只要信号量的value大于0，其他线程就可以sem_wait成功，成功后信号量的value减一。若value值不大于0，则sem_wait阻塞，直到sem_post释放后value值加一。一句话，信号量的value>=0。
>
>互斥锁: 只要被锁住，其他任何线程都不可以访问被保护的资源。如果没有锁，获得资源成功，否则进行阻塞等待资源可用。一句话，线程互斥锁的vlaue可以为负数。  
>
>3、使用场所：
>
>信号量主要适用于进程间通信，当然，也可用于线程间通信。而互斥锁只能用于线程间通信。
>————————————————
>版权声明：本文为CSDN博主「佰慕哒Chow」的原创文章，遵循CC 4.0 BY-SA版权协议，转载请附上原文出处链接及本声明。
>原文链接：https://blog.csdn.net/qq_18144747/article/details/86671284



# reference

1. https://blog.csdn.net/qq_18144747/article/details/86671284