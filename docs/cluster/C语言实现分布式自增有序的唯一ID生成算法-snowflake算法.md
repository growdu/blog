之前有人问我设计一个分布式的递增的唯一id生成。想了半天不知道，偶然一个同事说起snowflake算法，我百度了一下，很简单高效。

参考

https://github.com/twitter/snowflake  

于是，我自己用c语言随便实现了一下，还没有达到工业级别，需要细化，但是基本能用了，上代码。

```
1.  /\* 
2.      snowflake 

4.      ID 生成策略 
5.      毫秒级时间41位+机器ID 10位+毫秒内序列12位。 
6.      0 41 51 64 +-----------+------+------+ |time |pc |inc | +-----------+------+------+ 
7.      前41bits是以微秒为单位的timestamp。 
8.      接着10bits是事先配置好的机器ID。 
9.      最后12bits是累加计数器。 
10.      macheine id(10bits)标明最多只能有1024台机器同时产生ID，sequence number(12bits)也标明1台机器1ms中最多产生4096个ID， \* 
11.        注意点，因为使用到位移运算，所以需要64位操作系统，不然生成的ID会有可能不正确 
12.  \*/  

14.  #include <stdio.h>  
15.  #include <pthread.h>  
16.  #include <unistd.h>  
17.  #include <stdlib.h>  
18.  #include <sched.h>  
19.  #include <linux/unistd.h>  
20.  #include <sys/syscall.h>  
21.  #include <errno.h>  
22.  #include<linux/types.h>  
23.  #include<time.h>  
24.  #include <stdint.h>  
25.  #include <sys/time.h>  

27.  struct  globle  
28.  {  
29.      int global_int:12;  
30.      uint64_t last_stamp;  
31.      int workid;  
32.      int seqid;  
33.  };  

35.  void set_workid(int workid);  
36.  pid_t gettid( void );  
37.  uint64_t get_curr_ms();  
38.  uint64_t wait_next_ms(uint64_t lastStamp);  
39.  int atomic_incr(int id);  
40.  uint64_t get_unique_id();  

  

1.  #include "snowflake.h"  

3.  struct globle g_info;  
4.  #define   sequenceMask  (-1L ^ (-1L << 12L))  
5.  void set_workid(int workid)  
6.  {  
7.   g_info.workid = workid;  
8.  }  
9.  pid_t gettid( void )  
10.  {  
11.      return syscall( \__NR_gettid );  
12.  }  
13.  uint64_t get_curr_ms()  
14.  {  
15.      struct timeval time_now;  
16.      gettimeofday(&time_now,NULL);  
17.      uint64_t ms_time =time_now.tv_sec\*1000+time_now.tv_usec/1000;  
18.      return ms_time;  
19.  }  

21.  uint64_t wait_next_ms(uint64_t lastStamp)  
22.  {  
23.      uint64_t cur = 0;  
24.      do {  
25.          cur = get_curr_ms();  
26.      } while (cur <= lastStamp);  
27.      return cur;  
28.  }  
29.  int atomic_incr(int id)  
30.  {  
31.      \__sync_add_and_fetch( &id, 1 );  
32.      return id;  
33.  }  
34.  uint64_t get_unique_id()  
35.  {  
36.      uint64_t  uniqueId=0;  
37.      uint64_t nowtime = get_curr_ms();  
38.      uniqueId = nowtime<<22;  
39.      uniqueId |=(g_info.workid&0x3ff)<<12;  

41.      if (nowtime <g_info.last_stamp)  
42.      {  
43.          perror("error");  
44.          exit(-1);  
45.      }  
46.      if (nowtime == g_info.last_stamp)  
47.      {  
48.          g_info.seqid = atomic_incr(g_info.seqid)& sequenceMask;  
49.          if (g_info.seqid ==0)  
50.          {  
51.              nowtime = wait_next_ms(g_info.last_stamp);  
52.          }  
53.      }  
54.      else  
55.      {  
56.          g_info.seqid  = 0;  
57.      }  
58.      g_info.last_stamp = nowtime;  
59.      uniqueId |=g_info.seqid;  
60.      return uniqueId;  
61.  }  
62.  int main()  
63.  {  
64.      set_workid(100);  
65.      int size;  
66.      for (;;)  
67.      {  
68.          uint64_t unquie = get_unique_id();  
69.          printf("pthread_id:%u, id \[%llu\]\\n",gettid(),unquie);  
70.      }  

72.      return;   
73.  } 
 ```

支持原子自增操作。

多线程情况下，可以将workid进行移位加上线程ID。