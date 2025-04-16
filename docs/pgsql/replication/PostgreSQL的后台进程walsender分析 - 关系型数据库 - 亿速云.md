这篇文章主要介绍“PostgreSQL的后台进程walsender分析”，在日常操作中，相信很多人在PostgreSQL的后台进程walsender分析问题上存在疑惑，小编查阅了各式资料，整理出简单好用的操作方法，希望对大家解答”PostgreSQL的后台进程walsender分析”的疑惑有所帮助！接下来，请跟着小编一起来学习吧！

该进程实质上是streaming replication环境中master节点上普通的backend进程,在standby节点启动时,standby节点向master发送连接请求,master节点的postmaster进程接收到请求后,启动该进程与standby节点的walreceiver进程建立通讯连接,用于传输WAL Record.  
walsender启动后,使用gdb跟踪此进程,其调用栈如下:

```
(gdb) bt
#0  0x00007fb6e6390903 in __epoll_wait_nocancel () from /lib64/libc.so.6
#1  0x000000000088e668 in WaitEventSetWaitBlock (set=0x10ac808, cur_timeout=29999, occurred_events=0x7ffd634441b0, 
    nevents=1) at latch.c:1048
#2  0x000000000088e543 in WaitEventSetWait (set=0x10ac808, timeout=29999, occurred_events=0x7ffd634441b0, nevents=1, 
    wait_event_info=83886092) at latch.c:1000
#3  0x000000000088dcec in WaitLatchOrSocket (latch=0x7fb6dcbfc4d4, wakeEvents=27, sock=10, timeout=29999, 
    wait_event_info=83886092) at latch.c:385
#4  0x000000000085405b in WalSndLoop (send_data=0x8547fe <XLogSendPhysical>) at walsender.c:2229
#5  0x0000000000851c93 in StartReplication (cmd=0x10ab750) at walsender.c:684
#6  0x00000000008532f0 in exec_replication_command (cmd_string=0x101dd78 "START_REPLICATION 0/5D000000 TIMELINE 16")
    at walsender.c:1539
#7  0x00000000008c0170 in PostgresMain (argc=1, argv=0x1049cb8, dbname=0x1049ba8 "", username=0x1049b80 "replicator")
    at postgres.c:4178
#8  0x000000000081e06c in BackendRun (port=0x103fb50) at postmaster.c:4361
#9  0x000000000081d7df in BackendStartup (port=0x103fb50) at postmaster.c:4033
#10 0x0000000000819bd9 in ServerLoop () at postmaster.c:1706
#11 0x000000000081948f in PostmasterMain (argc=1, argv=0x1018a50) at postmaster.c:1379
#12 0x0000000000742931 in main (argc=1, argv=0x1018a50) at main.c:228
```

本节首先介绍调用栈中PostgresMain函数.

#### 一、数据结构

**StringInfo**  
StringInfoData结构体保存关于扩展字符串的相关信息.

```
/*-------------------------
 * StringInfoData holds information about an extensible string.
 * StringInfoData结构体保存关于扩展字符串的相关信息.
 *      data    is the current buffer for the string (allocated with palloc).
 *      data    通过palloc分配的字符串缓存
 *      len     is the current string length.  There is guaranteed to be
 *              a terminating '\0' at data[len], although this is not very
 *              useful when the string holds binary data rather than text.
 *      len     是当前字符串的长度.保证以ASCII 0(\0)结束(data[len] = '\0').
 *              虽然如果存储的是二进制数据而不是文本时不太好使.
 *      maxlen  is the allocated size in bytes of 'data', i.e. the maximum
 *              string size (including the terminating '\0' char) that we can
 *              currently store in 'data' without having to reallocate
 *              more space.  We must always have maxlen > len.
 *      maxlen  以字节为单位已分配的'data'的大小,限定了最大的字符串大小(包括结尾的ASCII 0)
 *              小于此尺寸的数据可以直接存储而无需重新分配.
 *      cursor  is initialized to zero by makeStringInfo or initStringInfo,
 *              but is not otherwise touched by the stringinfo.c routines.
 *              Some routines use it to scan through a StringInfo.
 *      cursor  通过makeStringInfo或initStringInfo初始化为0,但不受stringinfo.c例程的影响.
 *              某些例程使用该字段扫描StringInfo
 *-------------------------
 */
typedef struct StringInfoData
{
    char       *data;
    int         len;
    int         maxlen;
    int         cursor;
} StringInfoData;
typedef StringInfoData *StringInfo;
```

#### 二、源码解读

**PostgresMain**  
后台进程postgres的主循环入口 — 所有的交互式或其他形式的后台进程在这里启动.  
其主要逻辑如下:  
1.初始化相关变量  
2.初始化进程信息,设置进程状态,初始化GUC参数  
3.解析命令行参数并作相关校验  
4.如为walsender进程,则调用WalSndSignals初始化,否则执行其他信号初始化  
5.初始化BlockSig/UnBlockSig/StartupBlockSig  
6.非Postmaster,则检查数据库路径/切换路径/创建锁定文件等操作  
7.调用BaseInit执行基本的初始化  
8.调用InitProcess/InitPostgres初始化进程  
9.重置内存上下文,处理加载库和前后台消息交互等  
10.初始化内存上下文  
11.进入主循环  
11.1切换至MessageContext上下文  
11.2初始化输入的消息  
11.3给客户端发送可以执行查询等消息  
11.4读取命令  
11.5根据命令类型执行相关操作

```
/* ----------------------------------------------------------------
 * PostgresMain
 *     postgres main loop -- all backends, interactive or otherwise start here
 *     postgres主循环 -- 所有的交互式或其他形式的后台进程在这里启动 
 *
 * argc/argv are the command line arguments to be used.  (When being forked
 * by the postmaster, these are not the original argv array of the process.)
 * dbname is the name of the database to connect to, or NULL if the database
 * name should be extracted from the command line arguments or defaulted.
 * username is the PostgreSQL user name to be used for the session.
 * argc/argv是命令行参数(postmaster fork进程时,不存在原有的进程argv数组).
 * dbname是连接的数据库名称,如需要从命令行参数中解析或者为默认的数据库名称,则为NULL.
 * username是PostgreSQL会话的用户名.
 * ----------------------------------------------------------------
 */
/*
输入：
    argc/argv-Main函数的输入参数
    dbname-数据库名称
    username-用户名
输出：
    无
*/
void
PostgresMain(int argc, char *argv[],
             const char *dbname,
             const char *username)
{
    int         firstchar;//临时变量，读取输入的Command
    StringInfoData input_message;//字符串增强结构体
    sigjmp_buf  local_sigjmp_buf;//系统变量
    volatile bool send_ready_for_query = true;//
    bool        disable_idle_in_transaction_timeout = false;
    /* Initialize startup process environment if necessary. */
    //如需要,初始化启动进程环境
    if (!IsUnderPostmaster//未初始化？initialized for the bootstrap/standalone case
        InitStandaloneProcess(argv[0]);//初始化进程
    SetProcessingMode(InitProcessing);//设置进程状态为InitProcessing
    /*
     * Set default values for command-line options.
     * 设置命令行选项默认值
     */
    if (!IsUnderPostmaster)
        InitializeGUCOptions();//初始化GUC参数，GUC=Grand Unified Configuration
    /*
     * Parse command-line options.
     * 解析命令行选项
     */
    process_postgres_switches(argc, argv, PGC_POSTMASTER, &dbname);//解析输入参数
    /* Must have gotten a database name, or have a default (the username) */
    //必须包含数据库名称或者存在默认值
    if (dbname == NULL)//输入的dbname为空
    {
        dbname = username;//设置为用户名
        if (dbname == NULL)//如仍为空，报错
            ereport(FATAL,
                    (errcode(ERRCODE_INVALID_PARAMETER_VALUE),
                     errmsg("%s: no database nor user name specified",
                            progname)));
    }
    /* Acquire configuration parameters, unless inherited from postmaster */
    //请求配置参数,除非从postmaster中继承
    if (!IsUnderPostmaster)
    {
        if (!SelectConfigFiles(userDoption, progname))//读取配置文件conf/hba文件&定位数据目录
            proc_exit(1);
    }
    /*
     * Set up signal handlers and masks.
     * 配置信号handlers和masks.
     *
     * Note that postmaster blocked all signals before forking child process,
     * so there is no race condition whereby we might receive a signal before
     * we have set up the handler.
     * 注意在fork子进程前postmaster已阻塞了所有信号,
     *   因此就算接收到信号,但在完成配置handler前不会存在条件争用.
     *
     * Also note: it's best not to use any signals that are SIG_IGNored in the
     * postmaster.  If such a signal arrives before we are able to change the
     * handler to non-SIG_IGN, it'll get dropped.  Instead, make a dummy
     * handler in the postmaster to reserve the signal. (Of course, this isn't
     * an issue for signals that are locally generated, such as SIGALRM and
     * SIGPIPE.)
     * 同时注意:最好不要使用在postmaster中标记为SIG_IGNored的信号.
     * 如果在改变处理器为non-SIG_IGN前,接收到这样的信号,会被清除.
     * 相反,可以在postmaster中创建dummy handler来保留这样的信号.
     * (当然,对于本地产生的信号,比如SIGALRM和SIGPIPE,这不会是问题)
     */
    if (am_walsender)//wal sender进程？
        WalSndSignals();//如果是，则调用WalSndSignals
    else//不是wal sender进程
    {
        //设置标记,读取配置文件
        pqsignal(SIGHUP, PostgresSigHupHandler);    /* set flag to read config
                                                     * file */
        //中断信号处理器(中断当前查询)
        pqsignal(SIGINT, StatementCancelHandler);   /* cancel current query */
        //终止当前查询并退出
        pqsignal(SIGTERM, die); /* cancel current query and exit */
        /*
         * In a standalone backend, SIGQUIT can be generated from the keyboard
         * easily, while SIGTERM cannot, so we make both signals do die()
         * rather than quickdie().
         * 在standalone进程,SIGQUIT可很容易的通过键盘生成,而SIGTERM则不好生成,
         *   因此让这两个信号执行die()而不是quickdie().
         */
        //bool IsUnderPostmaster = false
        if (IsUnderPostmaster)
            //悲催时刻,执行quickdie()
            pqsignal(SIGQUIT, quickdie);    /* hard crash time */
        else
            //执行die()
            pqsignal(SIGQUIT, die); /* cancel current query and exit */
        //建立SIGALRM处理器
        InitializeTimeouts();   /* establishes SIGALRM handler */
        /*
         * Ignore failure to write to frontend. Note: if frontend closes
         * connection, we will notice it and exit cleanly when control next
         * returns to outer loop.  This seems safer than forcing exit in the
         * midst of output during who-knows-what operation...
         * 忽略写入前端的错误.
         * 注意:如果前端关闭了连接,会通知并在空中下一次返回给外层循环时退出.
         * 这看起来会比在who-knows-what操作期间强制退出安全一些.
         */
        pqsignal(SIGPIPE, SIG_IGN);
        pqsignal(SIGUSR1, procsignal_sigusr1_handler);
        pqsignal(SIGUSR2, SIG_IGN);
        pqsignal(SIGFPE, FloatExceptionHandler);
        /*
         * Reset some signals that are accepted by postmaster but not by
         * backend
         * 重置一些postmaster接收而后台进程不会接收的信号
         */
        //在某些平台上,system()需要这个信号
        pqsignal(SIGCHLD, SIG_DFL); /* system() requires this on some
                                     * platforms */
    }
    //初始化BlockSig/UnBlockSig/StartupBlockSig
    pqinitmask();//Initialize BlockSig, UnBlockSig, and StartupBlockSig.
    if (IsUnderPostmaster)
    {
        /* We allow SIGQUIT (quickdie) at all times */
        //放开SIGQUIT(quickdie)
        sigdelset(&BlockSig, SIGQUIT);
    }
    //除了SIGQUIT,阻塞其他
    PG_SETMASK(&BlockSig);      /* block everything except SIGQUIT */
    if (!IsUnderPostmaster)
    {
        /*
         * Validate we have been given a reasonable-looking DataDir (if under
         * postmaster, assume postmaster did this already).
         * 验证已给出了reasonable-looking DataDir 
         * (如在postmaster下,假定postmaster已完成了这个事情)
         */
        checkDataDir();//确认数据库路径OK，使用stat命令
        /* Change into DataDir (if under postmaster, was done already) */
        //切换至数据库路径，使用chdir命令
        ChangeToDataDir();
        /*
         * Create lockfile for data directory.
         */
        //创建锁定文件，CreateLockFile(DIRECTORY_LOCK_FILE, amPostmaster, "", true, DataDir);
        CreateDataDirLockFile(false);
        /* read control file (error checking and contains config ) */
        //读取控制文件(错误检查和包含配置)
        LocalProcessControlFile(false);//Read the control file, set respective GUCs.
        /* Initialize MaxBackends (if under postmaster, was done already) */
        //从配置选项中初始化MaxBackends
        InitializeMaxBackends();//Initialize MaxBackends value from config options.
    }
    /* Early initialization */
    BaseInit();//执行基本的初始化
    /*
     * Create a per-backend PGPROC struct in shared memory, except in the
     * EXEC_BACKEND case where this was done in SubPostmasterMain. We must do
     * this before we can use LWLocks (and in the EXEC_BACKEND case we already
     * had to do some stuff with LWLocks).
     * 在共享内存中创建每个backend都有的PGPROC结构体,除了在SubPostmasterMain的EXEC_BACKEND情况.
     * 在可以使用LWLocks前必须执行该操作.
     * (在EXEC_BACKEND中,已使用了LWLocks执行这个场景)
     */
// initialize a per-process data structure for this backend
#ifdef EXEC_BACKEND
    if (!IsUnderPostmaster)
        InitProcess();
#else
    InitProcess();
#endif
    /* We need to allow SIGINT, etc during the initial transaction */
    //在初始化事务期间需要允许SIGINT等等
    PG_SETMASK(&UnBlockSig);
    /*
     * General initialization.
     * 常规的初始化.
     *
     * NOTE: if you are tempted to add code in this vicinity, consider putting
     * it inside InitPostgres() instead.  In particular, anything that
     * involves database access should be there, not here.
     * 注意:如果希望在此处添加代码,请考虑将其放入InitPostgres()中.
     * 特别的,任何涉及到数据库访问的内容都应该在InitPostgres中,而不是在这里.
     */
    InitPostgres(dbname, InvalidOid, username, InvalidOid, NULL, false);//Initialize POSTGRES
    /*
     * If the PostmasterContext is still around, recycle the space; we don't
     * need it anymore after InitPostgres completes.  Note this does not trash
     * *MyProcPort, because ConnCreate() allocated that space with malloc()
     * ... else we'd need to copy the Port data first.  Also, subsidiary data
     * such as the username isn't lost either; see ProcessStartupPacket().
     * 如果PostmasterContext仍然存在,回收空间;
     * 在InitPostgres完成后,我们不再需要这些空间.
     * 注意:这个操作不会回收*MyProcPort,因为ConnCreate()分配
     */
    if (PostmasterContext)
    {
        MemoryContextDelete(PostmasterContext);
        PostmasterContext = NULL;
    }
    //完成初始化后，设置进程模式为NormalProcessing
    SetProcessingMode(NormalProcessing);
    /*
     * Now all GUC states are fully set up.  Report them to client if
     * appropriate.
     */
    //Report GUC
    BeginReportingGUCOptions();
    /*
     * Also set up handler to log session end; we have to wait till now to be
     * sure Log_disconnections has its final value.
     */
    //设置处理器,用于记录会话结束;
    //等待直至确保Log_disconnections最终有值存在
    if (IsUnderPostmaster && Log_disconnections)
        on_proc_exit(log_disconnections, 0);//this function adds a callback function to the list of functions invoked by proc_exit()
    /* Perform initialization specific to a WAL sender process. */
    //为WAL sender进程执行特别的初始化
    if (am_walsender)
        InitWalSender();//初始化 WAL sender process
    /*
     * process any libraries that should be preloaded at backend start (this
     * likewise can't be done until GUC settings are complete)
     * 处理在后台进程启动时需要提前预装载的库(这个步骤在GUC配置完成后才能够执行)
     */
    process_session_preload_libraries();//加载LIB
    /*
     * Send this backend's cancellation info to the frontend.
     * 发送后端的取消信息到前台
     */
    if (whereToSendOutput == DestRemote)
    {
        StringInfoData buf;
        pq_beginmessage(&buf, 'K');
        pq_sendint32(&buf, (int32) MyProcPid);
        pq_sendint32(&buf, (int32) MyCancelKey);
        pq_endmessage(&buf);
        /* Need not flush since ReadyForQuery will do it. */
        //不需要flush,因为ReadyForQuery会执行该操作
    }
    /* Welcome banner for  case */
    //standalone的欢迎信息
    if (whereToSendOutput == DestDebug)
        printf("\nPostgreSQL stand-alone backend %s\n", PG_VERSION);
    /*
     * Create the memory context we will use in the main loop.
     * 创建主循环中使用的内存上下文
     *
     * MessageContext is reset once per iteration of the main loop, ie, upon
     * completion of processing of each command message from the client.
     * 主循环中,每一次迭代都会重置MessageContext,比如完成了每个命令的处理,已从客户端返回了信息
     */
    //初始化内存上下文：MessageContext
    MessageContext = AllocSetContextCreate(TopMemoryContext,
                                           "MessageContext",
                                           ALLOCSET_DEFAULT_SIZES);
    /*
     * Create memory context and buffer used for RowDescription messages. As
     * SendRowDescriptionMessage(), via exec_describe_statement_message(), is
     * frequently executed for ever single statement, we don't want to
     * allocate a separate buffer every time.
     * 创建RowDescription消息的内存上下文和缓存.
     * 每一条单独的语句执行时都会频繁的通过exec_describe_statement_message()函数
     *   调用SendRowDescriptionMessage(),不希望在每次都分配单独的缓存.
     */
    //TODO 传输RowDescription messages？
    row_description_context = AllocSetContextCreate(TopMemoryContext,
                                                    "RowDescriptionContext",
                                                    ALLOCSET_DEFAULT_SIZES);
    MemoryContextSwitchTo(row_description_context);
    initStringInfo(&row_description_buf);
    MemoryContextSwitchTo(TopMemoryContext);
    /*
     * Remember stand-alone backend startup time
     * 记录stand-alone后台进程的启动时间
     */
    if (!IsUnderPostmaster)
        PgStartTime = GetCurrentTimestamp();//记录启动时间
    /*
     * POSTGRES main processing loop begins here
     * POSTGRES的主处理循环在这里开始
     *
     * If an exception is encountered, processing resumes here so we abort the
     * current transaction and start a new one.
     * 如果出现了异常,处理过程会在这里恢复因此PG可以回滚当前事务并启动新事务
     *
     * You might wonder why this isn't coded as an infinite loop around a
     * PG_TRY construct.  The reason is that this is the bottom of the
     * exception stack, and so with PG_TRY there would be no exception handler
     * in force at all during the CATCH part.  By leaving the outermost setjmp
     * always active, we have at least some chance of recovering from an error
     * during error recovery.  (If we get into an infinite loop thereby, it
     * will soon be stopped by overflow of elog.c's internal state stack.)
     * 你可能会对这里不用PG_TRY构造一个无限循环感到困惑.
     * 理由是这是异常栈的底,因此在这里使用PG_TRY会导致在CATCH部分没有任何的异常处理器.
     * 通过让最外层的setjmp始终处于活动状态,我们起码有机会在错误恢复的错误中进行恢复.
     * (如果进入了无线循环,会很快因为elog's内部状态栈的溢出而停止)
     *
     * Note that we use sigsetjmp(..., 1), so that this function's signal mask
     * (to wit, UnBlockSig) will be restored when longjmp'ing to here.  This
     * is essential in case we longjmp'd out of a signal handler on a platform
     * where that leaves the signal blocked.  It's not redundant with the
     * unblock in AbortTransaction() because the latter is only called if we
     * were inside a transaction.
     * 注意我们使用sigsetjmp(...,1),
     *   以便该函数的信号mask(也就是说,UnBlockSig)在longjmp到这里的时候可以被还原.
     * 在某个让信号继续阻塞的平台上通过longjmp跳出信号处理器时这样的处理是需要的.
     * 这与AbortTransaction()设置unblock并不多余因为如果我们在事务中保证只执行了一次.
     */
    if (sigsetjmp(local_sigjmp_buf, 1) != 0)//
    {
        /*
         * NOTE: if you are tempted to add more code in this if-block,
         * consider the high probability that it should be in
         * AbortTransaction() instead.  The only stuff done directly here
         * should be stuff that is guaranteed to apply *only* for outer-level
         * error recovery, such as adjusting the FE/BE protocol status.
         * 注意:如果你希望在if-block中添加代码,建议在AbortTransaction()中添加.
         * 直接添加在这里的唯一理由是可以应用对高层的错误恢复,比如调整FE/BE协议状态.
         */
        /* Since not using PG_TRY, must reset error stack by hand */
        //不使用PG_TRY,必须重置错误栈
        error_context_stack = NULL;
        /* Prevent interrupts while cleaning up */
        //清理时禁止中断
        HOLD_INTERRUPTS();
        /*
         * Forget any pending QueryCancel request, since we're returning to
         * the idle loop anyway, and cancel any active timeout requests.  (In
         * future we might want to allow some timeout requests to survive, but
         * at minimum it'd be necessary to do reschedule_timeouts(), in case
         * we got here because of a query cancel interrupting the SIGALRM
         * interrupt handler.)  Note in particular that we must clear the
         * statement and lock timeout indicators, to prevent any future plain
         * query cancels from being misreported as timeouts in case we're
         * forgetting a timeout cancel.
         * 废弃正在处理中QueryCancel请求,因为进程会返回到空闲循环中,同时取消所有活动的超时请求.
         * (在未来,我们可能希望运行某些超时请求仍然存活,但最起码有需要执行reschedule_timeouts(),
         *  在这种情况下到达这里的原因是查询取消是通过SIGALRM终端处理器中断的).
         * 注意特别的,必须清理语句和锁超时提示器,已避免在取消超时后后续的普通查询出现超时时没有报告.
         */
        disable_all_timeouts(false);
        QueryCancelPending = false; /* second to avoid race condition */
        stmt_timeout_active = false;
        /* Not reading from the client anymore. */
        //不再从客户端读取信息
        DoingCommandRead = false;
        /* Make sure libpq is in a good state */
        //确保libq状态OK
        pq_comm_reset();
        /* Report the error to the client and/or server log */
        //向客户端和/或服务器日志报告错误
        EmitErrorReport();
        /*
         * Make sure debug_query_string gets reset before we possibly clobber
         * the storage it points at.
         * 确保debug_query_string在可能破坏它所指向的存储之前重置
         */
        debug_query_string = NULL;
        /*
         * Abort the current transaction in order to recover.
         * 取消当前事务
         */
        AbortCurrentTransaction();
        if (am_walsender)
            //如为walsender,则执行清理工作
            WalSndErrorCleanup();
        //错误清理
        PortalErrorCleanup();
        SPICleanup();
        /*
         * We can't release replication slots inside AbortTransaction() as we
         * need to be able to start and abort transactions while having a slot
         * acquired. But we never need to hold them across top level errors,
         * so releasing here is fine. There's another cleanup in ProcKill()
         * ensuring we'll correctly cleanup on FATAL errors as well.
         * 在AbortTransaction()中不能释放replication slots因为需要在持有slot时启动和回滚事务.
         * 但不限于在顶层出现错误时持有这些slots,因此在这里释放这些slots是OK的.
         * 这里在ProcKill()中存在另外一个清理确保我们可以在FATAL错误中正确的恢复.
         */
        if (MyReplicationSlot != NULL)
            ReplicationSlotRelease();
        /* We also want to cleanup temporary slots on error. */
        //出现错误时,清理临时slots
        ReplicationSlotCleanup();
        //重置JIT
        jit_reset_after_error();
        /*
         * Now return to normal top-level context and clear ErrorContext for
         * next time.
         * 现在可以回到正常的顶层上下文中并为下次循环清理ErrorContext
         */
        MemoryContextSwitchTo(TopMemoryContext);
        FlushErrorState();
        /*
         * If we were handling an extended-query-protocol message, initiate
         * skip till next Sync.  This also causes us not to issue
         * ReadyForQuery (until we get Sync).
         * 如果我们正在处理extended-query-protocol消息,启动跳过直至下次Sync.
         * 这同时会导致我们不会触发ReadyForQuery(直至接收到Sync)
         */
        if (doing_extended_query_message)
            ignore_till_sync = true;
        /* We don't have a transaction command open anymore */
        //不再有打开的事务命令
        xact_started = false;
        /*
         * If an error occurred while we were reading a message from the
         * client, we have potentially lost track of where the previous
         * message ends and the next one begins.  Even though we have
         * otherwise recovered from the error, we cannot safely read any more
         * messages from the client, so there isn't much we can do with the
         * connection anymore.
         * 如果在读取客户端消息时出现错误,进程可能已经丢失了上一条消息结束和下一条消息开始的位置.
         * 虽然从错误中恢复了,但我们仍然不能安全的从客户端读取消息,因此我们对该连接已无能无力.
         */
        if (pq_is_reading_msg())
            ereport(FATAL,
                    (errcode(ERRCODE_PROTOCOL_VIOLATION),
                     errmsg("terminating connection because protocol synchronization was lost")));
        /* Now we can allow interrupts again */
        //允许中断
        RESUME_INTERRUPTS();
    }
    /* We can now handle ereport(ERROR) */
    //现在可以处理ereport(ERROR)了
    PG_exception_stack = &local_sigjmp_buf;
    if (!ignore_till_sync)
        //错误恢复后重新初始化
        send_ready_for_query = true;    /* initially, or after error */
    /*
     * Non-error queries loop here.
     * 世界清净了...
     */
    for (;;)//主循环
    {
        /*
         * At top of loop, reset extended-query-message flag, so that any
         * errors encountered in "idle" state don't provoke skip.
         * 在循环的最开始处,重置extended-query-message标记,
         * 以便在"idle"状态遇到错误时不会跳过
         */
        doing_extended_query_message = false;
        /*
         * Release storage left over from prior query cycle, and create a new
         * query input buffer in the cleared MessageContext.
         * 释放上一个查询周期中残余的存储空间,并在干净的MessageContext中创建新的查询输入缓存
         */
        MemoryContextSwitchTo(MessageContext);//切换至MessageContext
        MemoryContextResetAndDeleteChildren(MessageContext);
        initStringInfo(&input_message);//初始化输入的信息
        /*
         * Also consider releasing our catalog snapshot if any, so that it's
         * not preventing advance of global xmin while we wait for the client.
         * 尝试释放catalog snapshot,以便在等待客户端返回时不会阻碍全局xmin的增加.
         */
        InvalidateCatalogSnapshotConditionally();
        /*
         * (1) If we've reached idle state, tell the frontend we're ready for
         * a new query.
         * (1) 如果是idle状态,告诉前台已准备接受新查询请求了.
         *
         * Note: this includes fflush()'ing the last of the prior output.
         * 注意:这包含了fflush()'ing前一个输出的最后一个.
         *
         * This is also a good time to send collected statistics to the
         * collector, and to update the PS stats display.  We avoid doing
         * those every time through the message loop because it'd slow down
         * processing of batched messages, and because we don't want to report
         * uncommitted updates (that confuses autovacuum).  The notification
         * processor wants a call too, if we are not in a transaction block.
         * 发送收集的统计信息到collector,正当其时!
         * 在每次消息循环时都发送统计信息是需要避免的,
         *   因为我不希望报告未提交的更新(这会让autoacuum出现混乱).
         * 如果我们不在事务块中,那么通知处理器希望调用一次.
         */
        if (send_ready_for_query)//I am ready!
        {
            if (IsAbortedTransactionBlockState())
            {
                set_ps_display("idle in transaction (aborted)", false);
                pgstat_report_activity(STATE_IDLEINTRANSACTION_ABORTED, NULL);
                /* Start the idle-in-transaction timer */
                if (IdleInTransactionSessionTimeout > 0)
                {
                    disable_idle_in_transaction_timeout = true;
                    enable_timeout_after(IDLE_IN_TRANSACTION_SESSION_TIMEOUT,
                                         IdleInTransactionSessionTimeout);
                }
            }
            else if (IsTransactionOrTransactionBlock())
            {
                set_ps_display("idle in transaction", false);
                pgstat_report_activity(STATE_IDLEINTRANSACTION, NULL);
                /* Start the idle-in-transaction timer */
                if (IdleInTransactionSessionTimeout > 0)
                {
                    disable_idle_in_transaction_timeout = true;
                    enable_timeout_after(IDLE_IN_TRANSACTION_SESSION_TIMEOUT,
                                         IdleInTransactionSessionTimeout);
                }
            }
            else
            {
                ProcessCompletedNotifies();
                pgstat_report_stat(false);
                set_ps_display("idle", false);
                pgstat_report_activity(STATE_IDLE, NULL);
            }
            ReadyForQuery(whereToSendOutput);
            send_ready_for_query = false;
        }
        /*
         * (2) Allow asynchronous signals to be executed immediately if they
         * come in while we are waiting for client input. (This must be
         * conditional since we don't want, say, reads on behalf of COPY FROM
         * STDIN doing the same thing.)
         * (2) 如果异步信号在等待客户端输入时接收到,那么允许马上执行.
         *     (这是有条件的,因为我们不希望或者说执行COPY FORM STDIN同样的动作)
         */
        DoingCommandRead = true;
        /*
         * (3) read a command (loop blocks here)
         * (3) 读取命令(循环块)
         */
        firstchar = ReadCommand(&input_message);//读取命令
        /*
         * (4) disable async signal conditions again.
         * (4) 再次禁用异步信号条件
         *
         * Query cancel is supposed to be a no-op when there is no query in
         * progress, so if a query cancel arrived while we were idle, just
         * reset QueryCancelPending. ProcessInterrupts() has that effect when
         * it's called when DoingCommandRead is set, so check for interrupts
         * before resetting DoingCommandRead.
         * 在处理过程中如无查询,那么取消查询被认为是no-op的,
         *   因此如果在空闲状态下接收到查询取消信号,那么重置QueryCancelPending.
         * ProcessInterrupts()函数在DoingCommandRead设置的时候调用会有类似的影响,
         *   因此在重置DoingCommandRead前重新检查中断.
         */
        CHECK_FOR_INTERRUPTS();
        DoingCommandRead = false;
        /*
         * (5) turn off the idle-in-transaction timeout
         * (5) 关闭idle-in-transaction超时控制
         */
        if (disable_idle_in_transaction_timeout)
        {
            disable_timeout(IDLE_IN_TRANSACTION_SESSION_TIMEOUT, false);
            disable_idle_in_transaction_timeout = false;
        }
        /*
         * (6) check for any other interesting events that happened while we
         * slept.
         * (6) 在休眠时检查感兴趣的事件
         */
        if (ConfigReloadPending)
        {
            ConfigReloadPending = false;
            ProcessConfigFile(PGC_SIGHUP);
        }
        /*
         * (7) process the command.  But ignore it if we're skipping till
         * Sync.
         * (7) 处理命令.但如果我们设置了ignore_till_sync则忽略之.
         */
        if (ignore_till_sync && firstchar != EOF)
            continue;
        switch (firstchar)
        {
            case 'Q':           /* simple query */
                {
                    //--------- 简单查询
                    const char *query_string;
                    /* Set statement_timestamp() */
                    //设置时间戳
                    SetCurrentStatementStartTimestamp();
                    //SQL语句
                    query_string = pq_getmsgstring(&input_message);
                    pq_getmsgend(&input_message);
                    if (am_walsender)
                    {
                        //如为WAL sender,执行exec_replication_command
                        if (!exec_replication_command(query_string))
                            exec_simple_query(query_string);
                    }
                    else
                        //普通的后台进程
                        exec_simple_query(query_string);//执行SQL语句
                    send_ready_for_query = true;
                }
                break;
            case 'P':           /* parse */
                {
                    //---------- 解析
                    const char *stmt_name;
                    const char *query_string;
                    int         numParams;
                    Oid        *paramTypes = NULL;
                    forbidden_in_wal_sender(firstchar);
                    /* Set statement_timestamp() */
                    SetCurrentStatementStartTimestamp();
                    stmt_name = pq_getmsgstring(&input_message);
                    query_string = pq_getmsgstring(&input_message);
                    numParams = pq_getmsgint(&input_message, 2);
                    if (numParams > 0)
                    {
                        int         i;
                        paramTypes = (Oid *) palloc(numParams * sizeof(Oid));
                        for (i = 0; i < numParams; i++)
                            paramTypes[i] = pq_getmsgint(&input_message, 4);
                    }
                    pq_getmsgend(&input_message);
                    //执行解析
                    exec_parse_message(query_string, stmt_name,
                                       paramTypes, numParams);
                }
                break;
            case 'B':           /* bind */
                //------------- 绑定
                forbidden_in_wal_sender(firstchar);
                /* Set statement_timestamp() */
                SetCurrentStatementStartTimestamp();
                /*
                 * this message is complex enough that it seems best to put
                 * the field extraction out-of-line
                 * 该消息看起来比较复杂,看起来最好的做法是提取字段
                 */
                exec_bind_message(&input_message);
                break;
            case 'E':           /* execute */
                {
                    //------------ 执行
                    const char *portal_name;
                    int         max_rows;
                    forbidden_in_wal_sender(firstchar);
                    /* Set statement_timestamp() */
                    SetCurrentStatementStartTimestamp();
                    portal_name = pq_getmsgstring(&input_message);
                    max_rows = pq_getmsgint(&input_message, 4);
                    pq_getmsgend(&input_message);
                    exec_execute_message(portal_name, max_rows);
                }
                break;
            case 'F':           /* fastpath function call */
                //----------- 函数调用
                forbidden_in_wal_sender(firstchar);
                /* Set statement_timestamp() */
                SetCurrentStatementStartTimestamp();
                /* Report query to various monitoring facilities. */
                pgstat_report_activity(STATE_FASTPATH, NULL);
                set_ps_display("<FASTPATH>", false);
                /* start an xact for this function invocation */
                start_xact_command();
                /*
                 * Note: we may at this point be inside an aborted
                 * transaction.  We can't throw error for that until we've
                 * finished reading the function-call message, so
                 * HandleFunctionRequest() must check for it after doing so.
                 * Be careful not to do anything that assumes we're inside a
                 * valid transaction here.
                 */
                /* switch back to message context */
                MemoryContextSwitchTo(MessageContext);
                HandleFunctionRequest(&input_message);
                /* commit the function-invocation transaction */
                finish_xact_command();
                send_ready_for_query = true;
                break;
            case 'C':           /* close */
                {
                    //---------- 关闭
                    int         close_type;
                    const char *close_target;
                    forbidden_in_wal_sender(firstchar);
                    close_type = pq_getmsgbyte(&input_message);
                    close_target = pq_getmsgstring(&input_message);
                    pq_getmsgend(&input_message);
                    switch (close_type)
                    {
                        case 'S':
                            if (close_target[0] != '\0')
                                DropPreparedStatement(close_target, false);
                            else
                            {
                                /* special-case the unnamed statement */
                                drop_unnamed_stmt();
                            }
                            break;
                        case 'P':
                            {
                                Portal      portal;
                                portal = GetPortalByName(close_target);
                                if (PortalIsValid(portal))
                                    PortalDrop(portal, false);
                            }
                            break;
                        default:
                            ereport(ERROR,
                                    (errcode(ERRCODE_PROTOCOL_VIOLATION),
                                     errmsg("invalid CLOSE message subtype %d",
                                            close_type)));
                            break;
                    }
                    if (whereToSendOutput == DestRemote)
                        pq_putemptymessage('3');    /* CloseComplete */
                }
                break;
            case 'D':           /* describe */
                {
                    //------------- 描述比如\d等命令
                    int         describe_type;
                    const char *describe_target;
                    forbidden_in_wal_sender(firstchar);
                    /* Set statement_timestamp() (needed for xact) */
                    SetCurrentStatementStartTimestamp();
                    describe_type = pq_getmsgbyte(&input_message);
                    describe_target = pq_getmsgstring(&input_message);
                    pq_getmsgend(&input_message);
                    switch (describe_type)
                    {
                        case 'S':
                            exec_describe_statement_message(describe_target);
                            break;
                        case 'P':
                            exec_describe_portal_message(describe_target);
                            break;
                        default:
                            ereport(ERROR,
                                    (errcode(ERRCODE_PROTOCOL_VIOLATION),
                                     errmsg("invalid DESCRIBE message subtype %d",
                                            describe_type)));
                            break;
                    }
                }
                break;
            case 'H':           /* flush */
                //--------- flush 刷新
                pq_getmsgend(&input_message);
                if (whereToSendOutput == DestRemote)
                    pq_flush();
                break;
            case 'S':           /* sync */
                //---------- Sync 同步
                pq_getmsgend(&input_message);
                finish_xact_command();
                send_ready_for_query = true;
                break;
                /*
                 * 'X' means that the frontend is closing down the socket. EOF
                 * means unexpected loss of frontend connection. Either way,
                 * perform normal shutdown.
                 */
            case 'X':
            case EOF:
                /*
                 * Reset whereToSendOutput to prevent ereport from attempting
                 * to send any more messages to client.
                 */
                if (whereToSendOutput == DestRemote)
                    whereToSendOutput = DestNone;
                /*
                 * NOTE: if you are tempted to add more code here, DON'T!
                 * Whatever you had in mind to do should be set up as an
                 * on_proc_exit or on_shmem_exit callback, instead. Otherwise
                 * it will fail to be called during other backend-shutdown
                 * scenarios.
                 */
                proc_exit(0);
            case 'd':           /* copy data */
            case 'c':           /* copy done */
            case 'f':           /* copy fail */
                /*
                 * Accept but ignore these messages, per protocol spec; we
                 * probably got here because a COPY failed, and the frontend
                 * is still sending data.
                 */
                break;
            default:
                ereport(FATAL,
                        (errcode(ERRCODE_PROTOCOL_VIOLATION),
                         errmsg("invalid frontend message type %d",
                                firstchar)));
        }
    }                           /* end of input-reading loop */
}
```

#### 三、跟踪分析

在主节点上用gdb跟踪postmaster,在PostgresMain上设置断点后启动standby节点,进入断点

```
[xdb@localhost ~]$ ps -ef|grep postgre
xdb       1263     1  0 14:20 pts/0    00:00:00 /appdb/xdb/pg11.2/bin/postgres
(gdb) b PostgresMain
Breakpoint 1 at 0x8bf9df: file postgres.c, line 3660.
(gdb) set follow-fork-mode child
(gdb) c
Continuing.
[New process 1332]
[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib64/libthread_db.so.1".
[Switching to Thread 0x7fb3885d98c0 (LWP 1332)]
Breakpoint 1, PostgresMain (argc=1, argv=0x1aa4c78, dbname=0x1aa4b68 "", username=0x1aa4b40 "replicator") at postgres.c:3660
3660        volatile bool send_ready_for_query = true;
(gdb)
```

1.初始化相关变量  
注意变量IsUnderPostmaster,如为T则表示该进程为postmaster的子进程

```
(gdb) p *argv
$1 = 0xc27715 "postgres"
(gdb) n
3661        bool        disable_idle_in_transaction_timeout = false;
(gdb) 
3664        if (!IsUnderPostmaster)
(gdb) p IsUnderPostmaster
$2 = true
```

2.初始化进程信息,设置进程状态,初始化GUC参数

```
(gdb) n
3667        SetProcessingMode(InitProcessing);
(gdb) 
3672        if (!IsUnderPostmaster)
(gdb) p InitProcessing
$3 = InitProcessing
```

3.解析命令行参数并作相关校验

```
(gdb) n
3678        process_postgres_switches(argc, argv, PGC_POSTMASTER, &dbname);
(gdb) 
3681        if (dbname == NULL)
(gdb) p dbname
$4 = 0x1aa4b68 ""
(gdb) p username
$5 = 0x1aa4b40 "replicator"
(gdb) n
3692        if (!IsUnderPostmaster)
(gdb)
```

4.如为walsender进程,则调用WalSndSignals初始化,否则执行其他信号初始化

```
3712        if (am_walsender)
(gdb) 
3713            WalSndSignals();
(gdb)
```

5.初始化BlockSig/UnBlockSig/StartupBlockSig

```
(gdb) 
3751        pqinitmask();
(gdb) 
3753        if (IsUnderPostmaster)
(gdb) 
3756            sigdelset(&BlockSig, SIGQUIT);
(gdb) 
(gdb) 
3759        PG_SETMASK(&BlockSig);      /* block everything except SIGQUIT */
(gdb)
```

6.非子进程(仍为postmaster进程),则检查数据库路径/切换路径/创建锁定文件等操作

```
N/A
```

7.调用BaseInit执行基本的初始化

```
3785        BaseInit();
(gdb)
```

8.调用InitProcess/InitPostgres初始化进程

```
3797        InitProcess();
(gdb) 
3801        PG_SETMASK(&UnBlockSig);
(gdb) 
3810        InitPostgres(dbname, InvalidOid, username, InvalidOid, NULL, false);
(gdb)
```

9.重置内存上下文,处理加载库和前后台消息交互等

```
(gdb) 
3819        if (PostmasterContext)
(gdb) 
3821            MemoryContextDelete(PostmasterContext);
(gdb) P PostmasterContext
$6 = (MemoryContext) 0x1a78c60
(gdb) P *PostmasterContext
$7 = {type = T_AllocSetContext, isReset = false, allowInCritSection = false, methods = 0xc93260 <AllocSetMethods>, 
  parent = 0x1a73aa0, firstchild = 0x1a9a700, prevchild = 0x1a7ac70, nextchild = 0x1a75ab0, name = 0xc2622a "Postmaster", 
  ident = 0x0, reset_cbs = 0x0}
(gdb) n
3822            PostmasterContext = NULL;
(gdb) 
3825        SetProcessingMode(NormalProcessing);
(gdb) 
3831        BeginReportingGUCOptions();
(gdb) 
3837        if (IsUnderPostmaster && Log_disconnections)
(gdb) p Log_disconnections
$8 = false
(gdb) p
$9 = false
(gdb) n
3841        if (am_walsender)
(gdb) 
3842            InitWalSender();
(gdb) 
3848        process_session_preload_libraries();
(gdb) 
3853        if (whereToSendOutput == DestRemote)
(gdb) 
3857            pq_beginmessage(&buf, 'K');
(gdb) 
3858            pq_sendint32(&buf, (int32) MyProcPid);
(gdb) 
3859            pq_sendint32(&buf, (int32) MyCancelKey);
(gdb) 
3860            pq_endmessage(&buf);
(gdb) 
3865        if (whereToSendOutput == DestDebug)
(gdb)
```

10.初始化内存上下文

```
(gdb) 
3874        MessageContext = AllocSetContextCreate(TopMemoryContext,
(gdb) 
3884        row_description_context = AllocSetContextCreate(TopMemoryContext,
(gdb) 
3887        MemoryContextSwitchTo(row_description_context);
(gdb) 
3888        initStringInfo(&row_description_buf);
(gdb) 
3889        MemoryContextSwitchTo(TopMemoryContext);
(gdb) 
3894        if (!IsUnderPostmaster)
(gdb) 
3919        if (sigsetjmp(local_sigjmp_buf, 1) != 0)
(gdb) 
4027        PG_exception_stack = &local_sigjmp_buf;
(gdb) 
4029        if (!ignore_till_sync)
(gdb) 
4030            send_ready_for_query = true;    /* initially, or after error */
(gdb)
```

11.进入主循环  
11.1切换至MessageContext上下文

```
(gdb) 
4042            doing_extended_query_message = false;
(gdb) 
4048            MemoryContextSwitchTo(MessageContext);
(gdb) 
4049            MemoryContextResetAndDeleteChildren(MessageContext);
```

11.2初始化输入的消息

```
(gdb) 
4051            initStringInfo(&input_message);
(gdb) 
4057            InvalidateCatalogSnapshotConditionally();
(gdb) p input_message
$10 = {data = 0x1a78d78 "", len = 0, maxlen = 1024, cursor = 0}
(gdb)
```

11.3给客户端发送可以执行查询等消息

```
(gdb) n
4072            if (send_ready_for_query)
(gdb) p send_ready_for_query
$12 = true
(gdb) n
4074                if (IsAbortedTransactionBlockState())
(gdb) 
4087                else if (IsTransactionOrTransactionBlock())
(gdb) 
4102                    ProcessCompletedNotifies();
(gdb) 
4103                    pgstat_report_stat(false);
(gdb) 
4105                    set_ps_display("idle", false);
(gdb) 
4106                    pgstat_report_activity(STATE_IDLE, NULL);
(gdb) 
4109                ReadyForQuery(whereToSendOutput);
(gdb) 
4110                send_ready_for_query = false;
(gdb)
```

11.4读取命令  
命令是IDENTIFY\_SYSTEM,判断系统标识是否OK  
firstchar -> ASCII 81 —> 字母’Q’

```
(gdb) 
4119            DoingCommandRead = true;
(gdb) 
4124            firstchar = ReadCommand(&input_message);
(gdb) 
4135            CHECK_FOR_INTERRUPTS();
(gdb) p input_message
$13 = {data = 0x1a78d78 "IDENTIFY_SYSTEM", len = 16, maxlen = 1024, cursor = 0}
(gdb) p firstchar
$14 = 81
(gdb) 
$15 = 81
(gdb) n
4136            DoingCommandRead = false;
(gdb) 
4141            if (disable_idle_in_transaction_timeout)
(gdb) 
4151            if (ConfigReloadPending)
(gdb) 
4161            if (ignore_till_sync && firstchar != EOF)
(gdb)
```

11.5根据命令类型执行相关操作  
walsender —> 执行exec\_replication\_command命令

```
(gdb) 
4164            switch (firstchar)
(gdb) 
4171                        SetCurrentStatementStartTimestamp();
(gdb) 
4173                        query_string = pq_getmsgstring(&input_message);
(gdb) 
4174                        pq_getmsgend(&input_message);
(gdb) p query_string
$16 = 0x1a78d78 "IDENTIFY_SYSTEM"
(gdb) n
4176                        if (am_walsender)
(gdb) 
4178                            if (!exec_replication_command(query_string))
(gdb) 
4184                        send_ready_for_query = true;
(gdb) 
4186                    break;
(gdb) 
4411        }                           /* end of input-reading loop */
(gdb)
```

继续循环,接收命令,第二个命令是START\_REPLICATION

```
...
(gdb) 
4124            firstchar = ReadCommand(&input_message);
(gdb) 
4135            CHECK_FOR_INTERRUPTS();
(gdb) p input_message
$18 = {data = 0x1a78d78 "START_REPLICATION 0/5D000000 TIMELINE 16", len = 41, maxlen = 1024, cursor = 0}
(gdb) p firstchar
$19 = 81
...
4164            switch (firstchar)
(gdb) n
4171                        SetCurrentStatementStartTimestamp();
(gdb) 
4173                        query_string = pq_getmsgstring(&input_message);
(gdb) 
4174                        pq_getmsgend(&input_message);
(gdb) 
4176                        if (am_walsender)
(gdb) p query_string
$20 = 0x1a78d78 "START_REPLICATION 0/5D000000 TIMELINE 16"
(gdb) p input_message
$21 = {data = 0x1a78d78 "START_REPLICATION 0/5D000000 TIMELINE 16", len = 41, maxlen = 1024, cursor = 41}
(gdb) n
4178                            if (!exec_replication_command(query_string))
(gdb)
```

开始执行复制,master节点使用psql连接数据库,执行sql语句,子进程会接收到相关信号,执行相关处理  
执行脚本

```
[xdb@localhost ~]$ psql -d testdb
psql (11.2)
Type "help" for help.
testdb=# drop table t1;
```

子进程输出

```
(gdb) 
Program received signal SIGUSR1, User defined signal 1.
0x00007fb38696c903 in __epoll_wait_nocancel () from /lib64/libc.so.6
(gdb) 
Single stepping until exit from function __epoll_wait_nocancel,
which has no line number information.
procsignal_sigusr1_handler (postgres_signal_arg=32766) at procsignal.c:262
262 {
(gdb) n
263     int         save_errno = errno;
(gdb) 
Program received signal SIGTRAP, Trace/breakpoint trap.
0x00007fb3881eecd0 in __errno_location () from /lib64/libpthread.so.0
(gdb) 
Single stepping until exit from function __errno_location,
which has no line number information.
procsignal_sigusr1_handler (postgres_signal_arg=10) at procsignal.c:265
265     if (CheckProcSignal(PROCSIG_CATCHUP_INTERRUPT))
(gdb)
```

DONE!

DEBUG退出gdb后,psql会话crash:(

```
[xdb@localhost ~]$ psql -d testdb
psql (11.2)
Type "help" for help.
testdb=# drop table t1;
WARNING:  terminating connection because of crash of another server process
DETAIL:  The postmaster has commanded this server process to roll back the current transaction and exit, because another server process exited abnormally and possibly corrupted shared memory.
HINT:  In a moment you should be able to reconnect to the database and repeat your command.
server closed the connection unexpectedly
    This probably means the server terminated abnormally
    before or while processing the request.
The connection to the server was lost. Attempting reset: Failed.
!>
```

到此，关于“PostgreSQL的后台进程walsender分析”的学习就结束了，希望能够解决大家的疑惑。理论与实践的搭配能更好的帮助大家学习，快去试试吧！若想继续学习更多相关知识，请继续关注亿速云网站，小编会继续努力为大家带来更多实用的文章！