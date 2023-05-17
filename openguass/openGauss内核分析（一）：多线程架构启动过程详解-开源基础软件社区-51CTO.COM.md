> openGauss数据库自2020年6月30日开源以来，吸引了众多内核开发者的关注。那么openGauss的多线程是如何启动的，一条SQL语句在 SQL引擎，执行引擎和存储引擎的执行过程是怎样的，酷哥做了一些总结，第一期内容主要分析openGauss 多线程架构启动过程。

openGauss数据库是一个单进程多线程的数据库，客户端可以使用JDBC/ODBC/Libpq/Psycopg等驱动程序，向openGauss的主线程（Postmaster）发起连接请求。

![openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区](https://dl-harmonyos.51cto.com/images/202212/984df3269691a7b1262304b1bcfb78a0fefe1d.png "openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区")

### openGauss为什么要使用多线程架构

随着计算机领域多核技术的发展，如何充分有效的利用多核的并行处理能力，是每个服务器端应用程序都必须考虑的问题。由于数据库服务器的服务进程或线程间存在着大量数据共享和同步，而多线程可以充分利用多CPU来并行执行多个强相关任务，例如执行引擎可以充分的利用线程的并发执行以提供性能。在多线程的架构下，数据共享的效率更高，能提高服务器访问的效率和性能，同时维护开销和复杂度更低，这对于提高数据库系统的并行处理能力非常重要。

#### 多线程的三大主要优势：

\*\*优势一：\*\*线程启动开销远小于进程启动开销。与进程相比，它是一种非常“节俭”的多任务操作方式。在Linux系统下，启动一个新的进程必须分配给它独立的地址空间，建立众多的数据表来维护它的代码段、堆栈段和数据段，这是一种“昂贵”的多任务工作方式。而运行于一个进程中的多个线程，它们彼此之间使用相同的地址空间，共享大部分数据，启动一个线程所花费的空间远远小于启动一个进程所花费的空间。

\*\*优势二：\*\*线程间方便的通信机制：对不同进程来说，它们具有独立的数据空间，要进行数据的传递只能通过通信的方式进行，这种方式不仅费时，而且很不方便。线程则不然，由于同一进程下的线程之间共享数据空间，所以一个线程的数据可以直接为其他线程所用，这不仅快捷，而且方便。

\*\*优势三：\*\*线程切换开销小于进程切换开销，对于Linux系统来讲，进程切换分两步：1.切换页目录以使用新的地址空间；2.切换内核栈和硬件上下文。对线程切换，第1步是不需要做的，第2步是进程和线程都要做的，所以明显线程切换开销小。

### openGauss主要线程有哪些

<table data-id="t7a7e9d1-6e2JI0Si" data-width=""><colgroup data-id="c7104f7d-kYGBQJ1O"><col data-id="cd89ecb0-mJgLh4gk"><col data-id="cd89ecb0-Q14XGn4P"></colgroup><tbody data-id="t6d5e859-HZhAPach"><tr data-id="t31e458f-31JVquEG"><td data-id="t6267798-Uf7GB4WX"></td><td data-id="t6267798-ZCeHA7Vl"></td></tr><tr data-id="t31e458f-Yqc6cnlM"><td data-id="t6267798-bgkoOIlC"><p data-id="p838747a-Mt3f7gJE">后台线程<br></p></td><td data-id="t6267798-EpO5acAp"><p data-id="p838747a-0kzb7RP6">功能介绍<br></p></td></tr><tr data-id="t31e458f-B0VxuOMQ"><td data-id="t6267798-LPVml425"><p data-id="p838747a-9tUaIYZm">Postmaster<br></p><p data-id="p838747a-czLdvcpv">主线程<br></p></td><td data-id="t6267798-X7NPmL3b"><p data-id="p838747a-p3wphCEv">入口函数PostmasterMain，主要负责内存、全局信息、信号、线程池等的初始化，启动辅助线程并监控线程状态，循环监听接收新的连接<br></p></td></tr><tr data-id="t31e458f-i4z2iidq"><td data-id="t6267798-2PYhEqac"><p data-id="p838747a-veObASHj">Walwriter<br></p><p data-id="p838747a-eY5B1paF">日志写线程<br></p></td><td data-id="t6267798-npT1j8iZ"><p data-id="p838747a-N0och2hd">入口函数WalWriterMain，将内存的预写日志页数据刷新到预写日志文件中，保证已提交的事物永久记录，不会丢失<br></p></td></tr><tr data-id="t31e458f-uWPlcRps"><td data-id="t6267798-G5hIJP9T"><p data-id="p838747a-fP571LCd">Startup<br></p><p data-id="p838747a-g5j9n4bY">数据库启动线程<br></p></td><td data-id="t6267798-rXQC9qgL"><p data-id="p838747a-FhslqjZx">入口函数StartupProcessMain，数据库启动时Postmaster主线程拉起的第一个子线程，主要完成数据库的日志REDO（重做）操作，进行数据库的恢复。日志REDO操作结束，数据库完成恢复后，如果不是备机，Startup线程就退出了。如果是备机，那么Startup线程一直在运行，REDO备机接收到新的日志<br></p></td></tr><tr data-id="t31e458f-MopB8WsY"><td data-id="t6267798-iEHorW1U"><p data-id="p838747a-ZI1Xc82S">Bgwriter<br></p><p data-id="p838747a-580n1W6V">后台数据写线程<br></p></td><td data-id="t6267798-EdYJCt9U"><p data-id="p838747a-rIY44lP4">入口函数BackgroundWriterMain，对共享缓冲区的脏页数据进行下盘<br></p></td></tr><tr data-id="t31e458f-rVYgrFp6"><td data-id="t6267798-NjEey5LR"><p data-id="p838747a-ZicdSI9a">PageWriter<br></p></td><td data-id="t6267798-K6uDJHLo"><p data-id="p838747a-XmU5phB3">入口函数ckpt_pagewriter_main，将脏页数据拷贝至双写区域并落盘<br></p></td></tr><tr data-id="t31e458f-pXMWmHRQ"><td data-id="t6267798-NBmmEtlJ"><p data-id="p838747a-0si0h5zm">Checkpointer<br></p><p data-id="p838747a-9rHYKRdH">检查点线程<br></p></td><td data-id="t6267798-Rc4I9zPx"><p data-id="p838747a-WvvLUk6a">入口函数CheckpointerMain，周期性检查点，所有数据文件被更新，将数据脏页刷新到磁盘，确保数据库一致；崩溃回复后，做过checkpointer更改不需要从预写日志中恢复<br></p></td></tr><tr data-id="t31e458f-6G99inrD"><td data-id="t6267798-KCd0H8gT"><p data-id="p838747a-OfW1Sxfb">StatCollector<br></p><p data-id="p838747a-1gpY21Wc">统计线程<br></p></td><td data-id="t6267798-EFY2nXia"><p data-id="p838747a-3Cta7AWU">入口函数PgstatCollectorMain，统计信息，包括对象、sql、会话、锁等，保存到pgstat.stat文件中，用于性能、故障、状态分析<br></p></td></tr><tr data-id="t31e458f-oWhZJUt8"><td data-id="t6267798-vXU3Eadp"><p data-id="p838747a-uZNbnmUQ">WalSender<br></p><p data-id="p838747a-62YLltcL">日志发送线程<br></p></td><td data-id="t6267798-HsBnlbMh"><p data-id="p838747a-hXFAAyp8">入口函数WalSenderMain，主机发送预写日志<br></p></td></tr><tr data-id="t31e458f-qsdgkbO1"><td data-id="t6267798-Ni8yF4wu"><p data-id="p838747a-W2zi87Ql">WalReceiver<br></p><p data-id="p838747a-9pEjh3yX">日志接收线程<br></p></td><td data-id="t6267798-4h833uTw"><p data-id="p838747a-WDMpyjyd">入口函数WalReceiverMain，备机接收预写日志<br></p></td></tr><tr data-id="t31e458f-3DjYqdvB"><td data-id="t6267798-WjJK0dKt"><p data-id="p838747a-rOboUIBw">Postgres<br></p><p data-id="p838747a-MY5s40WQ">业务处理线程<br></p></td><td data-id="t6267798-fXXES2YE"><p data-id="p838747a-VVfIldaH">入口函数PostgresMain：处理客户端连接请求，执行相关SQL业务<br></p></td></tr></tbody></table>

数据库启动后，可以通过操作系统命令ps查看线程信息(进程号为17012)

![openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区](https://dl-harmonyos.51cto.com/images/202212/4812ec558537d4dd120639afc139a7a7756687.png "openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区")

### openGauss启动过程

下面主要介绍openGauss数据库的启动过程，包括主线程，辅助线程及业务处理线程的启动过程。

#### gs\_ctl启动数据库

gs\_ctl是openGauss提供的数据库服务控制工具，可以用来启停数据库服务和查询数据库状态。主要供数据库管理模块调用，启动数据库使用如下命令：

gs\_ctl的入口函数在“src/bin/pg\_ctl/pg\_ctl.cpp”，gs\_ctl进程fork一个进程来运行 gaussdb进程，通过shell命令启动。

![openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区](https://dl-harmonyos.51cto.com/images/202212/97b6d71669e06c5c662728b0f210a11ce0b166.png "openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区")

上图中的cmd为“\*\*/opt/software/openGauss/bin/gaussdb -D /opt/software/openGauss/data”，进入到数据库运行调用的第一个函数是main函数，\*\*在“src/gausskernel/process/main/main.cpp”文件中，在main.cpp文件中，主要完成实例Context（上下文）的初始化、本地化设置，根据main.cpp文件的入口参数调用BootStrapProcessMain函数、GucInfoMain函数、PostgresMain函数和PostmasterMain函数。BootStrapProcessMain函数和PostgresMain函数是在initdb场景下初始化数据库使用的。GucInfoMain函数作用是显示GUC（grand unified configuration，配置参数，在数据库中指的是运行参数）参数信息。正常的数据库启动会进入PostmasterMain函数。下面对这个函数进行更详细的介绍。

![openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区](https://dl-harmonyos.51cto.com/images/202212/66773e9470845210c440876f2d3e9cfc81d270.png "openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区")

1.MemoryContextInit：内存上下文系统初始化，主要完成对ThreadTopMemoryContext，ErrorContext，AlignContext和ProfileLogging等全局变量的初始化。

2.pg\_perm\_setlocale：设置程序语言环境相关的全局变量。

3.check\_root: 确认程序运行者无操作系统的root权限，防止的意外文件覆盖等问题。

4.如果gaussdb后的第一个参数是—boot,则进行数据库初始化，如果gaussdb后的第一个参数是--single，则调用PostgresMain()，进入（本地）单用户版服务端程序。之后，与普通服务器端线程类似，循环等待用户输入SQL语句，直至用户输入EOF（Ctrl+D），退出程序。如果没有指定额外启动选项，程序进入PostmasterMain函数，开始一系列服务器端的正常初始化工作。

### PostmasterMain 函数

#### 下面具体介绍PostmasterMain。

![openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区](https://dl-harmonyos.51cto.com/images/202212/36bf87030cdc80fbe7b1705c597938f00f10ce.png "openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区")

1.设置线程号相关的全局变量MyProcPid、PostmasterPid、MyProgName和程序运行环境相关的全局变量IsPostmasterEnvironment。

2.调用postmaster\_mem\_cxt = AllocSetContextCreate(t\_thrd.top\_mem\_cxt,...)，在目前线程的top\_mem\_cxt下创建postmaster\_mem\_cxt全局变量和相应的内存上下文。

3.MemoryContextSwitchTo(postmaster\_mem\_cxt)切换到postmaster\_mem\_cxt内存上下文。

4.调用getInstallationPaths()，设置my\_exec\_path（一般即为gaussdb可执行文件所在路径）。

5.调用InitializeGUCOptions()，根据代码中各个GUC参数的默认值生成ConfigureNamesBool、ConfigureNamesInt、ConfigureNamesReal、ConfigureNamesString、ConfigureNamesEnum等 GUC参数的全局变量数组，以及统一管理GUC参数的guc\_variables、num\_guc\_variables、size\_guc\_variables全局变量，并设置与具体操作系统环境相关的GUC参数。

6. while (opt = ...) SetConfigOption, 若在启动gaussdb时用指定了非默认的GUC参数，则在此时加载至上一步中创建的全局变量中。

7.调用checkDataDir()，确认数据库安装成功以及PGDATA目录的有效性。

8.调用CreateDataDirLockFile()，创建数据目录的锁文件。

9.调用process\_shared\_preload\_libraries()，处理预加载库。

10.为每个ListenSocket创建监听。

11. reset\_shared，设置共享内存和信号，主要包括页面缓存池、各种锁缓存池、WAL日志缓存池、事务日志缓存池、事务（号）概况缓存池、各后台线程（锁使用）概况缓存池、各后台线程等待和运行状态缓存池、两阶段状态缓存池、检查点缓存池、WAL日志复制和接收缓存池、数据页复制和接收缓存池等。在后续阶段创建出的客户端后台线程以及各个辅助线程均使用该共享内存空间，不再单独开辟。

12.将启动时手动设置的GUC参数以文件形式保存下来，以供后续后台服务端线程启动时使用。

13.为不同信号设置handler。

14.调用pgstat\_init()，初始化状态收集子系统。

15.调用load\_hba()，加载pg\_hba.conf文件，该文件记录了允许连接（指定或全部）数据库的客户端物理机的地址和端口；调用load\_ident()，加载pg\_ident.conf文件，该文件记录了操作系统用户名与数据库系统用户名的对应关系，以便后续处理客户端连接时的身份认证。

16.调用 StartupPID = initialize\_util\_thread(STARTUP)，进行数据一致性校验。对于服务端主机来说，查看pg\_control文件，若上次关闭状态为DB\_SHUTDOWNED且recovery.conf文件没有指定进行恢复，则认为数据一致性成立；否则，根据pg\_control中检查点的redo位置或者recovery.conf文件中指定的位置，读取WAL日志或归档日志进行replay（回放），直至数据达到预期的一致性状，主要函数StartupXLOG。

17. 最后进入ServerLoop()函数，循环响应客户端连接请求。

### ServerLoop函数

#### 下面来讲ServerLoop函数主流程

![openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区](https://dl-harmonyos.51cto.com/images/202212/a4d5cd302a7f12205e8773b3c7c21d82181cea.png "openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区")

1.调用gs\_signal\_setmask(&UnBlockSig, NULL)和gs\_signal\_unblock\_sigusr2()，使得线程可以响应用户或其它线程的、指定的信号集。

2.每隔PM\_POLL\_TIMEOUT\_MINUTE时间修改一次socket文件和socket锁文件的访问和修改时间，以免被操作系统淘汰。

3.判断线程状态（pmState），若为PM\_WAIT\_DEAD\_END，则休眠100毫秒，并且不接收任何连接；否则，通过系统调用poll()或select()来阻塞地读取监听端口上传入的数据，最长阻塞时间PM\_POLL\_TIMEOUT\_SECOND。

4.调用gs\_signal\_setmask(&BlockSig, NULL)和gs\_signal\_block\_sigusr2()不再接收外源信号。

5.判断poll()或select()函数的返回值，若小于零，监听出错，服务端进程退出；若大于零，则创建连接ConnCreate()，并进入后台服务线程启动流程BackendStartup()。对于父线程，即postmaster线程，在结束BackendStartup()的调用以后，会调用ConnFree()，清除连接信息；若poll()或select()的返回值为零，即没有信息传入，则不进行任何操作。

6.调用ADIO\_RUN()、ADIO\_END() ，若AioCompleters没有启动，则启动之。

7.检查各个辅助线程的线程号是否为零，若为零，则调用initialize\_util\_thread启动。

以非线程池模式为例，介绍线程的启动逻辑。BackendStartup函数是通过调用initialize\_worker\_thread(WORKE，port)创建一个后台线程处理客户请求。后台线程的启动函数initialize\_util\_thread和工作线程的启动函数initialize\_worker\_thread，最后都是调用initialize\_thread函数完成线程的启动。

![openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区](https://dl-harmonyos.51cto.com/images/202212/66d48d451480b1ff78226632a898ffc9095ef3.png "openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区")

1.initialize\_thread函数调用gs\_thread\_create函数创建线程，调用InternalThreadFunc函数处理线程。

2.InternalThreadFunc函数根据角色调用GetThreadEntry函数，GetThreadEntry函数直接以角色为下标，返回对应GaussdbThreadEntryGate数组对应的元素。数组的元素是处理具体任务的回调函数指针，指针指向的函数为GaussDbThreadMain。

3.在GaussDbThreadMain函数中，首先初始化线程基本信息，Context和信号处理函数，接着就是根据thread\_role角色的不同调用不同角色的处理函数，进入各个线程的main函数，角色为WORKER会进入PostgresMain函数,下面具体介绍PostgresMain函数。

### PostgresMain函数

![openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区](https://dl-harmonyos.51cto.com/images/202212/35028327205eb55d97e482e4ffe2a039ba368f.png "openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区")

1.process\_postgres\_switches()，加载传入的启动选项和GUC参数。

2.为不同信号设置handler。

3.调用sigdelset(&BlockSig, SIGQUIT)，允许响应SIGQUIT信号。

4.调用BaseInit()，初始化存储管理系统和页面缓存池计数。

5.调用on\_shmem\_exit()，设置线程退出前需要进行的内存清理动作。这些清理动作构成一个链表（on\_shmem\_exit\_list全局变量），每次调用该函数都向链表尾端添加一个节点，链表长度由on\_shmem\_exit\_index记录，且不可超过MAX\_ON\_EXITS宏。在线程退出时，从后往前调用各个节点中的动作（函数指针），完成清理工作。

6.调用gs\_signal\_setmask (&UnBlockSig)，设置屏蔽的信号类型。

7.调用InitBackendWorker进行统计系统初始化、syscache初始化工作。

8. BeginReportingGUCOptions如有需要则打印GUC参数。

9.调用on\_proc\_exit()，设置线程退出前需要进行的线程清理动作。设置和调用机制与on\_shmem\_exit()类似。

10.调用process\_local\_preload\_libraries()，处理GUC参数设定后的预加载库。

11. AllocSetContextCreate创建MessageContext、RowDescriptionContext、MaskPasswordCtx上下文。

12.调用sigsetjmp()，设置longjump点，若后续查询执行中出错，在某些情况下可以返回此处重新开始。

13.调用gs\_signal\_unblock\_sigusr2()，允许线程响应指定的信号集。

14.然后进入for循环，进行查询执行。

![openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区](https://dl-harmonyos.51cto.com/images/202212/4797e7b59aa5d329b741860b41ac0680e43fef.png "openGauss内核分析（一）：多线程架构启动过程详解-开源基础软件社区")

1.调用pgstat\_report\_activity()、pgstat\_report\_waitstatus()，告诉统计系统后台线程正处于idle状态。

2.设置全局变量DoingCommandRead = true。

3.调用ReadCommand(),读取客户端SQL语句。

4.设置全局变量DoingCommandRead=false。

5.若在上述过程中收到SIGHUP信号，表示线程需要重新加载修改过的postgresql.conf配置文件。

6.进入switch (firstchar)，根据接收到的信息进行分支判断。

### 思考如何新增一个辅助线程

#### 参考其他线程完成

<table data-id="t7a7e9d1-FW08n96W" data-transient-attributes="class" data-width="670px"><colgroup data-id="c7104f7d-HlSCbIBQ"><col data-id="cd89ecb0-XPcLB9bR" span="1" width="335"><col data-id="cd89ecb0-dmSXQKWV" span="1" width="335"></colgroup><tbody data-id="t6d5e859-K9a78C6Z"><tr data-id="t31e458f-VMunVlgw"><td data-id="t6267798-klpHWpWQ" data-transient-attributes="table-cell-selection"></td><td data-id="t6267798-8ByrrsFJ" data-transient-attributes="table-cell-selection"></td></tr><tr data-id="t31e458f-fUoLVBJj"><td data-id="t6267798-3EW2ZxuM" data-transient-attributes="table-cell-selection"><p data-id="p838747a-uftAscSj">涉及修改文件<br></p></td><td data-id="t6267798-ucBXaR57" data-transient-attributes="table-cell-selection"><p data-id="p838747a-FYy058x5">Postmaster.cpp<br></p></td></tr><tr data-id="t31e458f-qs7pBAML"><td data-id="t6267798-kbc7BUci" data-transient-attributes="table-cell-selection"><p data-id="p838747a-7szQCuva">涉及修改函数<br></p></td><td data-id="t6267798-DaZalxCJ" data-transient-attributes="table-cell-selection"><p data-id="p838747a-0Wi1WgFo">GaussdbThreadGate – 定义Serverloop – 启动线程Reaper – 回收线程GaussDBThreadMain – 入口函数<br></p></td></tr></tbody></table>

文章转载自公众号：  openGauss