#### 内容简介

本文主要介绍postgresql 的startup处理流程。startup发生在一个client连接server端时，server与client建立连接，并创建对应的backend process。后续就可以进行正常的消息交互了。

PostgreSQL 通信协议包括两个阶段： startup 阶段和常规 normal 阶段。

-   startup 阶段，客户端尝试创建连接并发送授权信息，如果一切正常，服务端会反馈状态信息，连接成功创建，随后进入 normal 阶段。 normal 阶段，客户端发送请求至服务端，服务端执行命令并将结果返回给客户端。客户端请求结束后，可以主动发送消息断开连接。
-   normal 阶段，客户端可以通过两种 "子协议" 来发送请求，分别是 simpel query 和 extened query。
    
    -   simple query：客户端发送字符串文本请求，后端收到后立即处理并返回结果。
    -   extened query：发送请求的过程被分为若干步骤，通常包括 Parse，Bind 和 Execute。Extended Query 协议将以上 Simple Query 的处理流程分为若干步骤，每一步都由单独的服务端消息进行确认。该协议可以使用服务端的 perpared-statement 功能，即先发送一条参数化 SQL，服务端收到 SQL（Statement）之后对其进行解析、重写并保存，这里保存的 Statement 也就是所谓 Prepared-statement，可以被复用；执行 SQL 时，直接获取事先保存的 Prepared-statement 生成计划并执行，避免对同类型 SQL 重复解析和重写。

详细可参考：[postgresql通信协议](https://link.segmentfault.com/?enc=xLetT3WRikiuheWm%2BuZaDg%3D%3D.IyrytzplhW6gE1SzPUvwVdSO%2BckLC5vp%2FDStYD8wfesbj03PSnJgYnjgjFzA2ZCA)  
[pg docs - protocol](https://link.segmentfault.com/?enc=tkozWEVYzHaZmlzuhAPbdA%3D%3D.RBAIAR5%2FEcLJk9SfgvyZ8huSFrE%2B8wpsuQ7M8OucFTNOkLWrcaFGy%2FY5lN8DBqzlEDsevRKatW6dR7V6dTsxYA%3D%3D)

##### pg版本

12.4

##### startup流程

![image.png](https://segmentfault.com/img/bVcOCyL "image.png")

##### startup消息类型

startup阶段server端发送给client端的消息类型如下。详细可参照[postgresql通信协议](https://link.segmentfault.com/?enc=A7vhau%2Bo0l5JpZm5XXoAmA%3D%3D.ouT5vfeo4sFDVQIjiRAu257Lm3qQgBV54LAuIGPvN%2F5kptZQxeF7QiRDeV68ukhi)

```
case 'R':        
case 'S':        
case 'K':        
case 'Z':        
```

client发给server端的消息类型

```
case 'p':        
```

#### 函数调用关系图

![image](https://segmentfault.com/img/bVcODHy "image")

#### startup简要分析

参照上面的"startup流程图"，client端首先向server端发送startup package。在server端postgres server process处理并创建对应的backend process。详细参考"[postgresql启动分析](https://segmentfault.com/a/1190000039193129)"

##### startup package结构

![image.png](https://segmentfault.com/img/bVcOC12 "image.png")

##### 本文线索

本文会结合一个线索来梳理流程。在startup package中client端可以包含一个application\_name，我们会分析这个参数如何在server端生效。

##### BackendStartup分析

BackendStartup是postmaster accept client端后的入口函数，负责fork backend process。为啥是入口呢，参考"[postgresql启动分析](https://segmentfault.com/a/1190000039193129)"

```
static int BackendStartup(Port *port)
  
  Backend    *bn = (Backend *) malloc(sizeof(Backend));
  pid = fork_process();
  if (pid == 0)    
  {
      free(bn);
  
      
      InitPostmasterChild();
  
      
      ClosePostmasterPorts(false);
  
      
      BackendInitialize(port);
  
      
      BackendRun(port);
  }
```

##### BackendInitialize分析

BackendInitialize负责backend中进一步的初始化，并处理startup package。  
注意全局变量MyProcPort赋值为port，后面会使用。

```
static void BackendInitialize(Port *port)
  
  MyProcPort = port;
  
  
  pq_init();
  
  
  whereToSendOutput = DestRemote; 
  
  
  InitializeTimeouts
  
  
  
  
  pg_getnameinfo_all(&port->raddr.addr,remote_host,remote_port)
  
  
  
  RegisterTimeout(STARTUP_PACKET_TIMEOUT, StartupPacketTimeoutHandler);
  enable_timeout_after(STARTUP_PACKET_TIMEOUT, AuthenticationTimeout * 1000);
  
  
  
  ProcessStartupPacket(port, false, false)
  
  
  disable_timeout(STARTUP_PACKET_TIMEOUT, false);
  
  
  check_on_shmem_exit_lists_are_empty
  
  
  initStringInfo(&ps_data)
  appendStringInfo(&ps_data, "%s", port->remote_host);
  appendStringInfo(&ps_data, "(%s)", port->remote_port);
  
  
  init_ps_display(ps_data.data);
```

##### ProcessStartupPacket分析

下面单独分析BackendInitialize中的ProcessStartupPacket。  
最终application\_name被保存到port->guc\_options和port->application\_name中。

```
static int ProcessStartupPacket(Port *port, bool ssl_done, bool gss_done)
{
  
  pq_getbytes((char *) &len, 1)
  pq_getbytes(((char *) &len) + 1, 3) 
  
  len = pg_ntoh32(len);
  len -= 4;
  
  
  pq_getbytes(buf, len)
  
  
  port->proto = proto = pg_ntoh32(*((ProtocolVersion *) buf));
  
  
  if (proto == CANCEL_REQUEST_CODE)
  {
      processCancelRequest(port, buf);
      
      return STATUS_ERROR;
  }
  
  
  
  
  
  
  
  
  if (proto == NEGOTIATE_SSL_CODE && !ssl_done)
    
    
    if (send(port->sock, &SSLok, 1, 0) != 1)
    return ProcessStartupPacket(port, true, SSLok == 'S');
  ......
  
  else if (proto == NEGOTIATE_GSS_CODE && !gss_done)
  ...
  
  
  
  
  oldcontext = MemoryContextSwitchTo(TopMemoryContext);
  
  port->guc_options = NIL;
  while (offset < len)
  {
    if (strcmp(nameptr, "database") == 0)
        port->database_name = pstrdup(valptr);
    else if (strcmp(nameptr, "user") == 0)
        port->user_name = pstrdup(valptr);
    ......
    else
    {
      port->guc_options = lappend(port->guc_options,pstrdup(nameptr));
      port->guc_options = lappend(port->guc_options,pstrdup(valptr));
      
      
      
      if (strcmp(nameptr, "application_name") == 0)
      {
        char       *tmp_app_name = pstrdup(valptr);
        port->application_name = tmp_app_name;
      }
  
  ......
  
  MemoryContextSwitchTo(oldcontext);
  
```

##### BackendRun分析

```
static void BackendRun(Port *port)
  // 为PostgresMain准备参数，是从postmaster中的-o选项获取option(保存于ExtraOptions)
  // 具体可以参考https://segmentfault.com/a/1190000039193129
  char      **av;
  int    ac = 0;
  av = (char **) MemoryContextAlloc(TopMemoryContext,
                                      maxac * sizeof(char *));
  av[ac++] = "postgres";
  pg_split_opts(av, &ac, ExtraOptions);
  
  MemoryContextSwitchTo(TopMemoryContext);
  
  PostgresMain(ac, av, port->database_name, port->user_name);
```

##### PostgresMain分析

PostgresMain是所有backend process的主入口函数。

```
void PostgresMain(int argc, char *argv[],
             const char *dbname,
             const char *username)
  // 有一种standalone的模式，以及作为wal sender。我们只分析作为client的backend process的情况。
  
  // 是否向client发送ready for query消息， 默认true，表示startup阶段结束会发送。其它阶段比如每次simple query结束也会发送。
  // 详见"startup消息类型"
  // case 'Z':        /* backend is ready for new query */
  volatile bool send_ready_for_query = true;
  
  // 参数解析，会通过SetConfigOption设置GUC，这里是第一次调用，模式为PGC_POSTMASTER，是从postmaster中的-o选项获取option(保存于ExtraOptions)。后面还会有第二次调用，对应从client端获取的option，模式为PGC_BACKEND，PGC_SU_BACKEND。
  // "TODO": SetConfigOption 设置GUC解析(特别是ctx区别)
  process_postgres_switches(argc, argv, PGC_POSTMASTER, &dbname);
  
  // signal重新注册
  pqsignal(SIGHUP, SignalHandlerForConfigReload);
  pqsignal(SIGINT, StatementCancelHandler);    /* cancel current query */
  pqsignal(SIGTERM, die); 
  pqsignal(SIGQUIT, quickdie);
  pqsignal(SIGPIPE, SIG_IGN);
  pqsignal(SIGUSR1, procsignal_sigusr1_handler);
  pqsignal(SIGUSR2, SIG_IGN);
  pqsignal(SIGFPE, FloatExceptionHandler);
  pqsignal(SIGCHLD, SIG_DFL);
  
  // per process的一些init，Semaphore...
  // !!! TODO: detailed parse
  InitProcess();
  
  // 基本的初始化，bufferpool，timer, portal manager, GUC, process setting...
  // 特别的，application_name设置到GUC也在这里
  // 下面会单独介绍
  InitPostgres(dbname, InvalidOid, username, InvalidOid, NULL, false);
  
  // 删除PostmasterContext，backend不再需要访问postmaster的context了
  if (PostmasterContext)
  {
      MemoryContextDelete(PostmasterContext);
      PostmasterContext = NULL;
  }
  
  // 向client report parameter status
  // 只发送GUC中GUC_REPORT类型的参数(auto-report changes to client)
  // 参照"startup消息类型"
  // case 'S':        /* parameter status */
  // !!!TODO：参数举例
  // 这里没有调用pq_flush()，直到ready for query才会一起发送
  BeginReportingGUCOptions();
    // -- parse BeginReportingGUCOptions
    for (i = 0; i < num_guc_variables; i++)
    {
        struct config_generic *conf = guc_variables[i];
    
        if (conf->flags & GUC_REPORT)
            ReportGUCOption(conf);
            // -- parse ReportGUCOption
            if (reporting_enabled && (record->flags & GUC_REPORT))
              pq_beginmessage(&msgbuf, 'S');
              pq_sendstring(&msgbuf, record->name);
              pq_sendstring(&msgbuf, val);
              pq_endmessage(&msgbuf);
    }
  
  process_session_preload_libraries();
  
  // 向client发送 secret key数据
  // 参照"startup消息类型"
  // case 'K':        /* secret key data from the backend */
  // 这里没有调用pq_flush()，直到ready for query才会一起发送
  if (whereToSendOutput == DestRemote)
  {
      StringInfoData buf;
  
      pq_beginmessage(&buf, 'K');
      pq_sendint32(&buf, (int32) MyProcPid);
      pq_sendint32(&buf, (int32) MyCancelKey);
      pq_endmessage(&buf);
  }
  
  // 创建MessageContext，这是给消息处理用，每一轮循环会重置
  MessageContext = AllocSetContextCreate(TopMemoryContext, "MessageContext");
  
  // 创建RowDescriptionContext，用于RowDescription messages
  row_description_context = AllocSetContextCreate(TopMemoryContext, "RowDescriptionContext",
  
  MemoryContextSwitchTo(row_description_context);
  initStringInfo(&row_description_buf);
  MemoryContextSwitchTo(TopMemoryContext);
  
  // 异常恢复的入口
  if (sigsetjmp(local_sigjmp_buf, 1) != 0)
  {
    ......
  }
  
  // 主循环
  for (;;)
  {
    // 初始化
      doing_extended_query_message = false;
    
    // 上面提到的MessageContext重置
      MemoryContextSwitchTo(MessageContext);
      MemoryContextResetAndDeleteChildren(MessageContext);
  
      initStringInfo(&input_message);
      InvalidateCatalogSnapshotConditionally();
  
    if (send_ready_for_query)
    {
      if (IsAbortedTransactionBlockState())
      else if (IsTransactionOrTransactionBlock())
      else {
        ProcessCompletedNotifies();
        pgstat_report_stat(false);
        set_ps_display("idle");
        pgstat_report_activity(STATE_IDLE, NULL);
      }
      
      // 详见"startup消息类型"
      // case 'Z':   /* backend is ready for new query */
      ReadyForQuery(whereToSendOutput);
      send_ready_for_query = false;
    }
    
    // 到这里startup阶段就结束了，接下来是normal阶段的消息处理
    // 下面以simple query为例
    
    // 读取command
    firstchar = ReadCommand(&input_message);
    
    // 分情况处理command
    switch (firstchar)
    {
        // 'Q':            /* simple query */
        case 'Q':            /* simple query */
            {
                const char *query_string;
    
                /* Set statement_timestamp() */
                SetCurrentStatementStartTimestamp();
    
                query_string = pq_getmsgstring(&input_message);
                pq_getmsgend(&input_message);
    
                if (am_walsender)
                {
                    if (!exec_replication_command(query_string))
                        exec_simple_query(query_string);
                }
                else
                    // 执行simple query
                    exec_simple_query(query_string);
    
                send_ready_for_query = true;
            }
            break;
            
        // 其它类型消息处理, bind, parse......
```

##### InitPostgres介绍

InitPostgres在PostgresMain中调用，进行基本的初始化，bufferpool，timer, portal manager, GUC, process setting...。

特别的，application\_name设置到GUC也在这里。authentication也发生在这里。

```
void
InitPostgres(const char *in_dbname, Oid dboid, const char *username,
             Oid useroid, char *out_dbname, bool override_allow_connections)
{
  bool        bootstrap = IsBootstrapProcessingMode();
  
  // InitProcess中初始化的process信息在这里用到了
  InitProcessPhase2();
  
  // shared-invalidation manager相关
  // !!! TODO： detailed parse
  MyBackendId = InvalidBackendId;
  SharedInvalBackendInit(false);
  ProcSignalInit(MyBackendId);
  
  // timer 注册
  if (!bootstrap)
  {
      RegisterTimeout(DEADLOCK_TIMEOUT, CheckDeadLockAlert);
      RegisterTimeout(STATEMENT_TIMEOUT, StatementTimeoutHandler);
      RegisterTimeout(LOCK_TIMEOUT, LockTimeoutHandler);
      RegisterTimeout(IDLE_IN_TRANSACTION_SESSION_TIMEOUT,
                      IdleInTransactionSessionTimeoutHandler);
  }
  
  // init buffer pool
  InitBufferPoolBackend();
  
  // xlog recovery检查
  // !!!TODO: detailed parse
  (void) RecoveryInProgress();
  
  //初始化relation cache和system catalog caches
  RelationCacheInitialize();
  InitCatalogCache();
  InitPlanCache();
  
  // 初始化portal manager
  // !!!TODO: detailed parse
  EnablePortalManager();
  
  // stats collection初始化
  pgstat_initialize();
  
  RelationCacheInitializePhase2();
  
  // 注册process-exit callback，用来进行pre-shutdown cleanup
  before_shmem_exit(ShutdownPostgres, 0);
  
  // start 一个transaction，获取snapshot
  // 只用于后面的各种表的访问，会在本函数结尾end
  // !!! TODO: detailed parse
  if (!bootstrap){
    SetCurrentStatementStartTimestamp();
    StartTransactionCommand();
    XactIsoLevel = XACT_READ_COMMITTED;
    (void) GetTransactionSnapshot();
   }
  
  // authentication
  // !!!! TODO: detailed parse
  else
  {
      /* normal multiuser case */
      Assert(MyProcPort != NULL);
      PerformAuthentication(MyProcPort);
      InitializeSessionUserId(username, useroid);
      am_superuser = superuser();
  }
  
  // 从pg_database表中获取client指定连接的database的oid，table space oid，存到MyDatabaseId， MyDatabaseTableSpace。
  else if (in_dbname != NULL)
  {
      HeapTuple    tuple;
      Form_pg_database dbform;
  
      tuple = GetDatabaseTuple(in_dbname);
      if (!HeapTupleIsValid(tuple))
          ereport(FATAL,
                  (errcode(ERRCODE_UNDEFINED_DATABASE),
                   errmsg("database \"%s\" does not exist", in_dbname)));
      dbform = (Form_pg_database) GETSTRUCT(tuple);
      MyDatabaseId = dbform->oid;
      MyDatabaseTableSpace = dbform->dattablespace;
      /* take database name from the caller, just for paranoia */
      strlcpy(dbname, in_dbname, sizeof(dbname));
  }
  
  // 获得client连接database的读写锁
  LockSharedObject(DatabaseRelationId, MyDatabaseId, 0, RowExclusiveLock);
  
  // 
  MyProc->databaseId = MyDatabaseId;
  
  // 设置当前catalog snapshot为invalid
  // !!!TODO:detailed parse
  InvalidateCatalogSnapshot();
  
  // 获取database path
  // 每个数据库都有对应的存储目录，例如下面base为table space，123000为这个db的oid，可以通过pg_database查询 - select oid, datname from pg_database;
  // /usr/local/pgsql/data4/base/123000/
  fullpath = GetDatabasePath(MyDatabaseId, MyDatabaseTableSpace);
  
  // 检查数据库目录
  if (access(fullpath, F_OK) == -1)
  ValidatePgVersion(fullpath);
  
  // 记录数据库目录到全局变量DatabasePath
  SetDatabasePath(fullpath);
  
  RelationCacheInitializePhase3();
  initialize_acl();
  
  // 读取pg_database，并设置GUC: server_encoding， client_encoding, lc_collate, lc_ctype
  CheckMyDatabase(dbname, am_superuser, override_allow_connections);
  
  // 会把port->guc_options中的option设置到GUC中
  // client发送的application_name也被设置到GUC中了
  // 我们的线索也到此为止了，回忆一下：
  // MyProcPort是在BackendInitialize中被设置为port
  // 而client发送的application_name是在BackendInitialize调用的ProcessStartupPacket中被记录到port->guc_options。
  if (MyProcPort != NULL)
    process_startup_options(MyProcPort, am_superuser);
  
  // pg_db_role_setting中load setting并且设置到数据库
  // !!!!TODO: detailed parse
  process_settings(MyDatabaseId, GetSessionUserId());
  
  // search path设置
  InitializeSearchPath();
  
  // client encoding设置
  InitializeClientEncoding();
  
  // session 设置
  InitializeSession();
  
  // pgstat start
  pgstat_bestart();
  
  // 关闭上面开始的transaction
  CommitTransactionCommand();
}

```

##### PerformAuthentication分析

InitPostgres中调用了PerformAuthentication进行authentication。此操作对应"startup流程"部分的authentication request/authentication ok。

```
static void
PerformAuthentication(Port *port)
{
  ClientAuthInProgress = true;
  
  enable_timeout_after(STATEMENT_TIMEOUT, AuthenticationTimeout * 1000);
  
  
  set_ps_display("authentication");
  
  
  ClientAuthentication(port);
  
  disable_timeout(STATEMENT_TIMEOUT, false);
  
  set_ps_display("startup");
  ClientAuthInProgress = false;
}

```

##### ClientAuthentication分析

ClientAuthentication是authentication主函数。

postgresql支持下面的authentication方法。

```
typedef enum UserAuth
{
    uaReject,
    uaImplicitReject,            
    uaTrust,
    uaIdent,
    uaPassword,
    uaMD5,
    uaSCRAM,
    uaGSS,
    uaSSPI,
    uaPAM,
    uaBSD,
    uaLDAP,
    uaCert,
    uaRADIUS,
    uaPeer
} UserAuth
```

postgresql向client发送的authentication code。

```

#define AUTH_REQ_OK            0    
#define AUTH_REQ_KRB4        1    
#define AUTH_REQ_KRB5        2    
#define AUTH_REQ_PASSWORD    3    
#define AUTH_REQ_CRYPT        4    
#define AUTH_REQ_MD5        5    
#define AUTH_REQ_SCM_CREDS    6    
#define AUTH_REQ_GSS        7    
#define AUTH_REQ_GSS_CONT    8    
#define AUTH_REQ_SSPI        9    
#define AUTH_REQ_SASL       10    
#define AUTH_REQ_SASL_CONT 11    
#define AUTH_REQ_SASL_FIN  12    

typedef uint32 AuthRequest;
```

```
void
ClientAuthentication(Port *port)
{
  // 读取pg_hba.conf，查找与本client符合的rule
  // 记录到port->hba
  hba_getauthmethod(port);
    // -- parse hba_getauthmethod
    check_hba(port);
      roleid = get_role_oid(port->user_name, true);
      
      // parsed_hba_lines是在load_hba中解析过的，详见
      // https://segmentfault.com/a/1190000039193129
      foreach(line, parsed_hba_lines){
        check_hostname
        check_ip
        check_same_host_or_net
        check_db
        check_role
        ... 
        
  CHECK_FOR_INTERRUPTS();
  
  // 针对不同搞的authentication method进行处理，下面只列举常见的password方式, 以及trust方式
  switch (port->hba->auth_method)
  { 
    // password方式，会要求client发送password
    case uaPassword:
      status = CheckPasswordAuth(port, &logdetail);
        // -- parse CheckPasswordAuth
        // 向client发送authentication request，code 为AUTH_REQ_PASSWORD
        sendAuthRequest(port, AUTH_REQ_PASSWORD, NULL, 0);
          // -- parse sendAuthRequest
          // 参照"startup消息类型"
          // case 'R':        /* Authentication Request */
          pq_beginmessage(&buf, 'R');
          pq_sendint32(&buf, (int32) areq);
          pq_endmessage(&buf);
        passwd = recv_password_packet(port);
          // -- parse recv_password_packet
          // 参照"startup消息类型"
          // case 'p':        /* password */
          pq_startmsgread();
          mtype = pq_getbyte();
          if (mtype != 'p')
          
          initStringInfo(&buf);
          if (pq_getmessage(&buf, 0))
        
        // 获取role对应的password
        // 本地存储的是shadow_pass(password的hash)
        shadow_pass = get_role_password(port->user_name, logdetail);
        
        // client发送的password进行比较
        result = plain_crypt_verify(port->user_name, shadow_pass, passwd, logdetail);
      break;
    
    // trust类型，则不需要authentication
    // 例如，pg_hba.conf中配置
    // TYPE  DATABASE        USER            ADDRESS          METHOD
    // host    all             all             0.0.0.0/0      trust
    case uaTrust:
      status = STATUS_OK;
      break;
    }
    
    
    // 根据authentication的结果
    // 向client发送结果，消息类型为'R'。 如成功，则为authenticon ok(0)
    // case 'R':        /* Authentication Request */
    if (status == STATUS_OK)
        sendAuthRequest(port, AUTH_REQ_OK, NULL, 0);
        // -- parse sendAuthRequest
        // 类似上面分析的，此处发送的消息类型为authentication request, 但是quthentication request code为AUTH_REQ_OK
        // case 'R':        /* Authentication Request */
        // 但是这里没有立刻发送，而是等到ready for queries时发送
        // 没有调用pq_flush()
        if (areq != AUTH_REQ_OK && areq != AUTH_REQ_SASL_FIN)
          pq_flush();
        
    else
        auth_failed(port, status, logdetail);
}
```

##### 抓包分析

pg\_hba.conf中配置trust模式

```
host    all             all             0.0.0.0/0               trust
```

###### 测试步骤

```
1. server端开始tcpdump

# tcpdump -i eth1 -s0 -nnX -w startup_trust.cap

2. psql连接server
# psql  -p 5436 -U postgres -h 172.28.128.18

3. server端停止tcpdump
 ctrl-c

4. 用wireshark查看cap包
```

![image.png](https://segmentfault.com/img/bVcOEee "image.png")  
类型为PSH，方向为client到server的为startup package。data中可以看到对应的消息体，其中包含如下options

```
database postgres, application_name psql, client_encoding UTF8
```

![image.png](https://segmentfault.com/img/bVcOEew "image.png")  
类型为PSH，方向为client到server的是一个大消息。查看data中对应的消息体内容。我们上面分析过在R，S，K消息后没有进行pg\_flush，而是直到Z一起flush后发送给client。

```
'R' : authentication ok
'S' : parameter status(application_name 
...
      client_encoding 
      is_superuser 
      IntervalStyle 
      server_encoding 
      session_autherization 
      server_version 
      TimeZone 
'K' : secret 
'Z' : ready 
```

##### 结语

本文分析了startup的主要流程，并且以application\_name为线索，帮助更连贯的理解整体流程。在这个过程中，对backend process有了更深入理解，其process管理，signal，semaphore，GUC，与client间的通信模型，消息结构等等。

##### Q&A

暂无

##### 遗留问题

还有很多地方没有进行详细分析(特别是mark TODO的)，后续再做进一步分析。