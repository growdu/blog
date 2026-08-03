# pglogical.so详解

pglogical.so是pglogical中的数据库扩展（extension），负责管理复制拓扑、节点、replication set、apply worker 等控制逻辑。

pglogical.so是控制层，用于管理逻辑复制。

它和普通的postgresql插件没什么区别，其机制和运行原理都与普通插件机制。

## 加载插件

编译安装后初始化一个data。

```shell
./initdb -D data -A trust
```
修改postgres.conf，添加如下内容：

```shell
shared_preload_libraries = 'pglogical'
```
修改完配置后启动：

```shell
./pg_ctl -D data -l logfile start
```
启动后连接数据库加载插件：

```sql
./psql -d postgres
psql (15.12)
Type "help" for help.

postgres=# create extension pglogical;
CREATE EXTENSION
postgres=# \q
```
## 源码分析

核心代码如下：

```c
void
_PG_init(void)
{
    #if PG_VERSION_NUM >= 150000
	prev_shmem_request_hook = shmem_request_hook;
	shmem_request_hook = pglogical_worker_shmem_init;
#else
	pglogical_worker_shmem_init();
#endif

	/* Init executor module */
	pglogical_executor_init();

	/* Run the supervisor. */
	memset(&bgw, 0, sizeof(bgw));
	bgw.bgw_flags =	BGWORKER_SHMEM_ACCESS |
		BGWORKER_BACKEND_DATABASE_CONNECTION;
	bgw.bgw_start_time = BgWorkerStart_RecoveryFinished;
	snprintf(bgw.bgw_library_name, BGW_MAXLEN,
			 EXTENSION_NAME);
	snprintf(bgw.bgw_function_name, BGW_MAXLEN,
			 "pglogical_supervisor_main");
	snprintf(bgw.bgw_name, BGW_MAXLEN,
			 "pglogical supervisor");
	bgw.bgw_restart_time = 5;

	RegisterBackgroundWorker(&bgw);
}
```
主要作用：
1. 申请共享内存
2. 注册BackgroundWorker

