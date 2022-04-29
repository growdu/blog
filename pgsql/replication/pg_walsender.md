# pg_walsender

## 交互接口

### 全局变量

```c
/* global state */
extern PGDLLIMPORT bool am_walsender; // 是否是walsender进程
extern PGDLLIMPORT bool am_cascading_walsender; // 是否是级联walsender
extern PGDLLIMPORT bool am_db_walsender; // 是否连接到数据库
extern PGDLLIMPORT bool wake_wal_senders; 

/* user-settable parameters */
extern PGDLLIMPORT int max_wal_senders; // 最大walsender进程数
extern PGDLLIMPORT int wal_sender_timeout; // wal消息发送超时时间
extern PGDLLIMPORT bool log_replication_commands;
```

- am_walsender和am_db_walsender

  解析启动参数replication的值进行赋值，如果replication的值是database或者true就设置这两个值为true。

  ```c
  				if (strcmp(valptr, "database") == 0)
  				{
  					am_walsender = true;
  					am_db_walsender = true;
  				}
  				else if (!parse_bool(valptr, &am_walsender)) {
                      
                  }
  ```

- am_cascading_walsender

  am_cascading_walsender在初始化walSnd的时候赋值。

  ```c
  am_cascading_walsender = RecoveryInProgress();
  ```

  值呢主要来自于全局的LocalRecoveryInProgress，LocalRecoveryInProgress=false时就是false，否则的话就从xlogctl->SharedRecoveryState取值。

  ```c
  LocalRecoveryInProgress = (xlogctl->SharedRecoveryState != RECOVERY_STATE_DONE);
  ```

  

### 对外接口

```c
extern void InitWalSender(void);
extern bool exec_replication_command(const char *query_string);
extern void WalSndErrorCleanup(void);
extern void WalSndResourceCleanup(bool isCommit);
extern void WalSndSignals(void);
extern Size WalSndShmemSize(void);
extern void WalSndShmemInit(void);
extern void WalSndWakeup(void);
extern void WalSndInitStopping(void);
extern void WalSndWaitStopping(void);
extern void HandleWalSndInitStopping(void);
extern void WalSndRqstFileReload(void);
```

- InitWalSender

  初始化一个walSnd。当am_walsender为true的时候，porstgres启动的时候就会初始化一个walSnd。

  ```mermaid
  graph TB
  InitWalSender-->|初始化walSnd|InitWalSenderSlot-->MarkPostmasterChildWalSender-->SendPostmasterSignal-->MemoryContextAllocZero
  ```

  

  初始化slot的时候会将全局的WalSndCtl的walsnds初始化，walsnds是一个变长数组，会根据max_wal_senders进行内存分配和初始化。每个创建的walSnd都会保存到全局的WalSndCtl的数组中。
  
  根据walSnd的pid是否为0来判断是否需要初始化，每个初始化的walSnd的状态为WALSNDSTATE_STARTUP。

### 对内接口

```c
extern void WalSndSetState(WalSndState state);

/*
 * Internal functions for parsing the replication grammar, in repl_gram.y and
 * repl_scanner.l
 */
extern int	replication_yyparse(void);
extern int	replication_yylex(void);
extern void replication_yyerror(const char *str) pg_attribute_noreturn();
extern void replication_scanner_init(const char *query_string);
extern void replication_scanner_finish(void);
extern bool replication_scanner_is_replication_command(void);
```

- WalSndSetState

  用来更改walSnd的状态。

### 数据模型

- walsender状态

```c
typedef enum WalSndState
{
	WALSNDSTATE_STARTUP = 0,
	WALSNDSTATE_BACKUP,
	WALSNDSTATE_CATCHUP,
	WALSNDSTATE_STREAMING,
	WALSNDSTATE_STOPPING
} WalSndState;
```

- walsender 结构

一个进程对应一个walSnd结构。

```c
typedef struct WalSnd
{
	pid_t		pid;			/* this walsender's PID, or 0 if not active */

	WalSndState state;			/* this walsender's state */
	XLogRecPtr	sentPtr;		/* WAL has been sent up to this point */
	bool		needreload;		/* does currently-open file need to be
								 * reloaded? */

	/*
	 * The xlog locations that have been written, flushed, and applied by
	 * standby-side. These may be invalid if the standby-side has not offered
	 * values yet.
	 */
	XLogRecPtr	write;
	XLogRecPtr	flush;
	XLogRecPtr	apply;

	/* Measured lag times, or -1 for unknown/none. */
	TimeOffset	writeLag;
	TimeOffset	flushLag;
	TimeOffset	applyLag;

	/*
	 * The priority order of the standby managed by this WALSender, as listed
	 * in synchronous_standby_names, or 0 if not-listed.
	 */
	int			sync_standby_priority;

	/* Protects shared variables shown above. */
	slock_t		mutex;

	/*
	 * Pointer to the walsender's latch. Used by backends to wake up this
	 * walsender when it has work to do. NULL if the walsender isn't active.
	 */
	Latch	   *latch;

	/*
	 * Timestamp of the last message received from standby.
	 */
	TimestampTz replyTime;
} WalSnd;
```
- WalSndCtlData

```c
typedef struct
{
	/*
	 * Synchronous replication queue with one queue per request type.
	 * Protected by SyncRepLock.
	 */
	SHM_QUEUE	SyncRepQueue[NUM_SYNC_REP_WAIT_MODE];

	/*
	 * Current location of the head of the queue. All waiters should have a
	 * waitLSN that follows this value. Protected by SyncRepLock.
	 */
	XLogRecPtr	lsn[NUM_SYNC_REP_WAIT_MODE];
	
	/*
	 * Are any sync standbys defined?  Waiting backends can't reload the
	 * config file safely, so checkpointer updates this value as needed.
	 * Protected by SyncRepLock.
	 */
	bool		sync_standbys_defined;
	
	WalSnd		walsnds[FLEXIBLE_ARRAY_MEMBER];
} WalSndCtlData;
```

- NodeTag

```c
typedef enum NodeTag {
   .....
       /*
	 * TAGS FOR REPLICATION GRAMMAR PARSE NODES (replnodes.h)
	 */
	T_IdentifySystemCmd,
	T_BaseBackupCmd,
	T_CreateReplicationSlotCmd,
	T_DropReplicationSlotCmd,
	T_ReadReplicationSlotCmd,
	T_StartReplicationCmd,
	T_TimeLineHistoryCmd,
    ......
} NodeTag;
```

- XLogReaderState

  ```c
  typedef uint64 XLogRecPtr;
  struct XLogReaderState
  {
      XLogReaderRoutine routine;
      XLogRecPtr	ReadRecPtr;		/* start of last record read */
  	XLogRecPtr	EndRecPtr;		/* end+1 of last record read */
  }
  ```

  - XLogReaderRoutine

    ```c
    typedef int (*XLogPageReadCB) (XLogReaderState *xlogreader,
    							   XLogRecPtr targetPagePtr,
    							   int reqLen,
    							   XLogRecPtr targetRecPtr,
    							   char *readBuf);
    typedef void (*WALSegmentOpenCB) (XLogReaderState *xlogreader,
    								  XLogSegNo nextSegNo,
    								  TimeLineID *tli_p);
    typedef void (*WALSegmentCloseCB) (XLogReaderState *xlogreader);
    typedef struct XLogReaderRoutine
    {
    	XLogPageReadCB page_read;
    	WALSegmentOpenCB segment_open;
    	WALSegmentCloseCB segment_close;
    } XLogReaderRoutine;
    ```

- XLogRecoveryCtlData

  ```c
  typedef struct XLogRecoveryCtlData
  {
  	/*
  	 * SharedHotStandbyActive indicates if we allow hot standby queries to be
  	 * run.  Protected by info_lck.
  	 */
  	bool		SharedHotStandbyActive;
  
  	/*
  	 * SharedPromoteIsTriggered indicates if a standby promotion has been
  	 * triggered.  Protected by info_lck.
  	 */
  	bool		SharedPromoteIsTriggered;
  
  	Latch		recoveryWakeupLatch;
  
  	/*
  	 * Last record successfully replayed.
  	 */
  	XLogRecPtr	lastReplayedReadRecPtr; /* start position */
  	XLogRecPtr	lastReplayedEndRecPtr;	/* end+1 position */
  	TimeLineID	lastReplayedTLI;	/* timeline */
  
  	/*
  	 * When we're currently replaying a record, ie. in a redo function,
  	 * replayEndRecPtr points to the end+1 of the record being replayed,
  	 * otherwise it's equal to lastReplayedEndRecPtr.
  	 */
  	XLogRecPtr	replayEndRecPtr;
  	TimeLineID	replayEndTLI;
  	/* timestamp of last COMMIT/ABORT record replayed (or being replayed) */
  	TimestampTz recoveryLastXTime;
  
  	/*
  	 * timestamp of when we started replaying the current chunk of WAL data,
  	 * only relevant for replication or archive recovery
  	 */
  	TimestampTz currentChunkStartTime;
  	/* Recovery pause state */
  	RecoveryPauseState recoveryPauseState;
  	ConditionVariable recoveryNotPausedCV;
  
  	slock_t		info_lck;		/* locks shared variables shown above */
  } XLogRecoveryCtlData;
  ```

  

## 执行逻辑