[首页](https://www.modb.pro/) / PostgreSQL的insert语句执行过程分析

在数据库的使用中，增删改查这种操作每天都在进行，本文通过gdb工具演示了一个insert语句的执行流程。

## 一、gdb增加断点

开启一个session，获取pid  
![1647521753323.png](https://oss-emcsprod-public.modb.pro/image/editor/20220317-8c15d175-355d-4961-bc32-f1d5f083d61b.png)

另开一个窗口，用gdb进入调试状态

![1647521868566.png](https://oss-emcsprod-public.modb.pro/image/editor/20220317-a2dd72ae-eb96-4992-b039-ad7b23a62243.png)

数据库端执行插入操作，因为gdb绑定了pid，会卡住，直到随着gdb的调试过程，执行到真正插入动作的函数

![1647521904969.png](https://oss-emcsprod-public.modb.pro/image/editor/20220317-36fa239e-33e1-4322-9540-16d7ec7768d6.png)

我在gdb端加了总共四个断点  
![1647524623688.png](https://oss-emcsprod-public.modb.pro/image/editor/20220317-c71bd980-53b2-4453-98c2-4f86f12576aa.png)

## 二、执行到exec\_simple\_query()

先从当前位置开始连续运行程序，到第一个断点，从下往上看运行的堆栈：

![1647524767084.png](https://oss-emcsprod-public.modb.pro/image/editor/20220317-cd366e22-d0f3-403c-9a8c-dc7a308832cc.png)

可以看到，insert动作从main()函数开始，首先到了postmaster进程入口 PostmasterMain() ，通过ServerLoop() 监听session连接并fork postgres子进程 ，然后用BackendStartup()启动backend进程 ，之后到PostgresMain() 即backend的入口，通过子进程backend获取sql语句 ，并最终到了exec\_simple\_query() 即SQL引擎的入口。

可以在此时查看传入这里的参数  
![1647526102468.png](https://oss-emcsprod-public.modb.pro/image/editor/20220317-ed55b892-ea44-4dd7-9853-9627b118d312.png)

单步执行，查看执行过程中相关变量的值。  
![1647526543774.png](https://oss-emcsprod-public.modb.pro/image/editor/20220317-cf59732e-7469-410c-9634-9e9dd60e384f.png)

## 三、执行到ProcessQuery()

c继续执行，在下一个断点，即ProcessQuery()这里停下，查看堆栈，可以看到这一部分跑到了PortalRun()的入口，Portal是查询执行器的四个主要子模块之一，也通常被叫做策略选择模块，在这选择执行策略后，会将控制流程交给相应的处理部件，即Executer或者ProcessUtility。这里根据策略调用了PortalRunMulti() ，最后到达了ProcessQuery()。  
![1647527251161.png](https://oss-emcsprod-public.modb.pro/image/editor/20220317-5a13168a-cb85-4034-99c5-5c6a95b35586.png)

我们继续单步执行，ProcessQuery()在这一部分创建QueryDesc，它封装了执行器执行查询所需的所有内容 ，调用ExecutorStart函数初始化结构体EState ，ExecutorStart函数调用InitPlan初始化计划状态树 。  
![1647529515600.png](https://oss-emcsprod-public.modb.pro/image/editor/20220317-886be156-2136-4e05-bfc9-d91b732e65f5.png)

这一部分执行流程过程如黄色所示：  
![1647528024796.png](https://oss-emcsprod-public.modb.pro/image/editor/20220317-177acdd1-9ba8-4f8f-a274-81fbe4406123.png)

## 四、执行到standard\_ExecutorRun()

继续c执行，到了standard\_ExecutorRun(),这里是先通过ExecutorRun ()这里进行判断，如果有hook函数，就执行hook函数，没有的话，执行标准函数standard\_ExecutorRun()。（比较典型的使用hook的是pg\_show\_plans插件）  
![1647530334528.png](https://oss-emcsprod-public.modb.pro/image/editor/20220317-e2392436-152d-401b-b244-cb477ab9b826.png)

继续执行，最后通过standard\_ExecutorRun()的ExecutePlan()执行insert并通过MemoryContextSwitchTo()切换回原内存上下文。  
![1647530791018.png](https://oss-emcsprod-public.modb.pro/image/editor/20220317-01d70778-e2f6-4f0d-92aa-0358ed876a85.png)

c继续执行一直到结束

![1647531040313.png](https://oss-emcsprod-public.modb.pro/image/editor/20220317-42fd5fa9-cc6f-403e-b0d5-b8cad70a011f.png)

可以在数据库端看到数据成功插入  
![1647531072246.png](https://oss-emcsprod-public.modb.pro/image/editor/20220317-4b8aec1a-3234-4b73-b88e-0132fd709a51.png)

整个插入动作的堆栈如下：  
![1647531572570.png](https://oss-emcsprod-public.modb.pro/image/editor/20220317-e445f37b-3c07-4d91-97c1-773fdf54942f.png)

最后修改时间：2022-03-17 23:57:09

【版权声明】本文为墨天轮用户原创内容，转载时必须标注文章的来源（墨天轮），文章链接，文章作者等基本信息，否则作者和墨天轮有权追究责任。如果您发现墨天轮中有涉嫌抄袭或者侵权的内容，欢迎发送邮件至：contact@modb.pro进行举报，并提供相关证据，一经查实，墨天轮将立刻删除相关内容。

![](https://js-cdn.modb.cc/image/svgs/likes.png)

获得了217次点赞

![](https://js-cdn.modb.cc/image/svgs/comment.png)

内容获得58次评论

![](https://js-cdn.modb.cc/image/svgs/star.png)

获得了212次收藏