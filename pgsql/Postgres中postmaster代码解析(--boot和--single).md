之前我的一些文章都是在说Postgres的一些查询相关的代码。但是对于Postgres服务端是如何启动，后台进程是如何加载，服务端在哪里以及如何监听客户端的连接都没有一个清晰的逻辑。那么今天我来说说Postgres中的**postmaster**模块的代码，试着解答这些问题。

在正式讨论之前，我先说一下，代码主要涉及的是postgres源码的src/backend目录下的main，postmaster以及tcop模块。

关于postmaster这个命令，熟悉postgres的一定不会陌生。在Linux上它是postgres命令的一个软连接，而在Windows上，它直接就是postgres命令的别名。因此，话题就转换为：postgres命令的处理细节。而postgres命令，从官方手册上我们可以知道，它是启动后端服务器的命令(当然前提是你要用initdb命令先生成一个database cluster)。无论是是直接使用postgres命令启动还是用pg\_ctl命令，其本质都是调用postgres命令来启动数据库的。

下面进入代码。

___

## 1.命令的入口处理

命令的入口在src/backend/main/main.c。这个main()函数所做的工作不多：

```
做一下基本的初始化(主要是调用MemoryContextInit函数启动error和memory management子系统，还有其他的locale设置等)；
根据命令行的第一个参数分派不同的函数去处理。
```

我们用postgres命令来启动一个数据库的时候，虽然参数很多。最简单的是对于"–help, --version"这两个参数的处理。对于这两个参数我们只需要简单的返回一下帮助信息即可返回。对于剩下的参数，我们不急着处理，因为我们首先要根据第一个参数确定的是我们希望database工作在何种模式？

要回答这个问题的话，我们看一下src/backend/main/main.c，在main函数里，有以下代码：

```
if (argc > 1 && strcmp(argv[1], "--boot") == 0)
AuxiliaryProcessMain(argc, argv);/* does not return */    --->后端子进程，bootstrap
else if (argc > 1 && strcmp(argv[1], "--describe-config") == 0)
GucInfoMain();/* does not return */
else if (argc > 1 && strcmp(argv[1], "--single") == 0)
PostgresMain(argc, argv,
 NULL,/* no dbname */
 strdup(get_user_name_or_exit(progname)));/* does not return */--->backend进程
else
PostmasterMain(argc, argv);/* does not return */--->后台主进程
```

我们来一一分析。

> 首先是bootstrap("--boot"参数指定)模式。

这个模式大家可能比较陌生，在postgres的官方手册上也没有说明这个参数，这个参数目前只在postgres程序内部调用。这个模式下，数据库工作在启动模式下，此时数据库还不能接受外部的数据库连接，大概就是说此时数据库只是内核启动了，还没有对外部提供访问接口。那么这个模式的用处何在呢？

那就让我们把目光放远一点，看看initdb这个命令吧(代码在src/bin/initdb下)。initdb命令我们很熟悉，这个命令用来初始化一个数据库集群。而在这个过程中，我们知道会建立template1，template0和postgres这个三个初始的数据库。那么问题是，我们这三个数据库是怎么建立的，数据库的表，视图索引之类的是怎么创建的？

答案就是在调用工作在"bootstrap"模式下的postgres命令，启动一个"standalone bootstrap process"。也就是说，以"内核"模式启动postgres服务器，从而进行这一系列的数据库操作。证据何在？我们看看initdb.c:  
代码调用栈如下：

```
main()
    ->initialize_data_directory()
        ->bootstrap_template1()
```

在bootstrap\_template1中，有以下代码：

```
snprintf(cmd, sizeof(cmd),
 "\"%s\" --boot -x1 %s %s %s",
 backend_exec,
 data_checksums ? "-k" : "",
 boot_options, talkargs);
```

可以说是非常清晰了。

> 接下来是"--describe-config"参数。

这个参数在官方手册是有定义说明的，我直接抄下来吧：

```
这个选项会用制表符分隔的COPY格式导出服务器的内部配置变量、描述以及默认值。设计它的目的是用于管理工具。
```

所以还是打印信息，只不过是打印数据库的内部的配置参数信息的，其实还是蛮实用的。

> single("--single"参数指定)模式

这个很简单，选择数据库进入单用户模式。这个模式和正常的启动的差别是你是以单独的用户方式进入数据库的，不会做任何后台处理，例如自动检查点。一般是用来debug用。这里也不细说了。

> 不指定以上参数的话，我们进入Postmater进程。

到这里，我们终于进入正题，进入PostmasterMain()函数，进入正常启动后端的过程。这个也是我们今天讨论的重点了。

___

## 2.postmater的处理

postmaster部分的处理主函数是PostmasterMain()。这个函数的处理内容较多，我们按照步骤来解释：

> 1.memorycontext的建立与切换(切换到PostmasterContext)

我们知道在main模块里我们建立了顶层上下文TopMemoryContext和其子上下文ErrorContext。此处调用AllocSetContextCreate()函数建立内存上下文PostmasterContext，并调用函数MemoryContextSwitchTo()将当前上下文切换到PostmasterContext。这样如果在Postmaster模块如果出现内存相关的问题，不会影响到其他模块(这也是内存上下文模块引入的原因吧)。

> 2.信号处理函数(singal handler)的设置

作为一个后端主进程，其拥有很多相关的子进程。我们也知道信号(singal)是进程间通信的一种比较方便的方式。这里Postmaster也利用了这一点，注册了很多信号处理函数来处理信号。有关这部分的信号以及相关的handler我列在下面了：

![](https://images2018.cnblogs.com/blog/579102/201804/579102-20180408214809188-248117352.png)

> 3.处理GUC和一些命令行参数

这部分就比较常规了。注意这里调用InitializeGUCOptions()函数**初始化**一些GUC，我们还并不能从config文件中读取，因为我们还没有处理命令行参数(命令行参数可以指定一些GUC参数以及config文件)。然后我们用getopt读取命令行参数，这样以后，我们就可以读取config文件进行GUC的设置和验证参数的合法性了。

> 4.数据库集群(database cluster)的锁定(lock)

调用CreateDataDirLockFile()函数在数据库集群所在目录创建数据库集群的lock文件postmaster.pid。这样就能保证我们不会对同一个数据库集群"启动两次"。虽然我们也会创建socket lock文件，但是我们还是觉得数据库集群所在的目录更加可信和保险一点。

> 5.共享库的预加载(process\_shared\_preload\_libraries())

我们喜欢用Postgres的一大原因就是Postgres的丰富的插件，其中很多就是通过共享库来实现的。这里就是调用process\_shared\_preload\_libraries()函数来导入你在shared\_preload\_libraries参数中指定的共享库的。

> 6.socket的初始化

这里初始化TCP/IP socket和UNIX socket。初始化UNIX socket会在/tmp下创建socket文件。默认情况下，TCP/IP socket是禁用的，我们可以通过修改配置文件来开启。

> 7.共享内存和信号量的初始化(reset\_shared(PostPortNumber))

这里调用函数reset\_shared(PostPortNumber)来处理共享内存和信号量。详细的说，它调用各模块的共享内存的使用量估计函数，计算总共所需的共享内存的量，并申请。详细的我们可以看CreateSharedMemoryAndSemaphores()函数。

> 8.初始化(并未启动)数据库相关后台进程

调用SysLogger\_Start()函数启动syslogger后台子进程；

分别调用pgstat\_init()和autovac\_init()函数初始化状态收集子进程(stats collection process)和自动清理子进程(autovacuum process)。

> 9.读取客户端认证的配置文件()

调用load\_hba()函数和load\_ident()函数读取客户端认证文件pg\_hba.conf和ident.conf。

> 10.启动数据库(StartupDataBase()函数)

做好了上面这些配置和设置，这里终于可以进行数据库的启动操作了。这里我们调用StartupDataBase()函数(其实就是一个宏)来启动数据库集群，这里主要发挥作用的是StartupProcessMain(void)函数，这个函数相当于启动数据库的Main函数。详细的调用栈如下，有兴趣的读者可以看看：

```
PostmasterMain()
    ->StartupDataBase()
        ->StartChildProcess()
            ->AuxiliaryProcessMain()
                ->StartupProcessMain(void)
                    ->StartupXLOG()
```

> 11.服务端主循环(ServerLoop())

既然数据库终于启动起来了，我们终于可以接受客户端发起的连接请求了，这里的ServerLoop()函数就是一个死循环。循环读取客户端的请求并进行相关处理。

这里有一点说明，我提个问题，是不是进入ServerLoop()之后，我们就真的可以马上接受客户端的连接了呢？或者换句话说，我们到底到什么时候才能接受客户端连接呢？标志是什么呢？

我们看PostmasterMain()函数里面关于上面的10和11的代码如下：

```
    StartupPID = StartupDataBase();
Assert(StartupPID != 0);
StartupStatus = STARTUP_RUNNING;
pmState = PM_STARTUP;

/* Some workers may be scheduled to start now */
maybe_start_bgworker();

status = ServerLoop();
```

关于上面的代码，我们发现，正是由StartupDataBase()函数启动了数据库，然后在ServerLoop()函数里面接受连接。

但是，我们看到在进入ServerLoop()函数之前，pmState的值还是PM\_STARTUP，而只有在PM\_RUN状态，数据库才是真正的启动起来了。

我们在看下函数reaper()，这个函数是postmaster函数的一个信号处理函数，当它捕获到Startup进程正常死亡(也就是说，数据库正常启动完毕了)后，会设置pmState为PM\_RUN。

因此，我们得到结论：**在进入ServerLoop()函数后，只有在reaper函数捕获到Startup的正常死亡并设置pmState为PM\_RUN之后，数据库才能真正的意义上接受连接。**

接下来，我们再看ServerLoop()里面到底做了什么。

```
　PostmasterMain()
　  |->ServerLoop()
　      |->initMasks()
　      |->for(;;)
　          |->select()         <--监听端口
　          |->ConnCreate()     <--创建connection相关的数据结构
　          |->BackendStartup() <--建立后端进程backend process
　              |->PostmasterRandom()
　              |->fork_process()
　              |->InitPostmasterChild()
　              |->ClosePostmasterPorts()
　              |->BackendInitialize()
　                  |->ProcessStartupPacket()
　              |->BackendRun()
　                  |->PostgresMain()
            |->ConnFree()       <--释放connection相关的数据结构
```

我们再看看关于ServerLoop()中的关于socket和信号处理：  
![](https://images2018.cnblogs.com/blog/579102/201804/579102-20180408221956346-1712021714.png)

___

好的，今天就到这里，剩下的会继续讨论Postmaster的其他细节。