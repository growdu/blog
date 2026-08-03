# pg常用函数

## DefineCustom*Variable

在 PostgreSQL 扩展开发中，DefineCustom*Variable 系列函数用于 注册自定义 GUC（Grand Unified Configuration）参数。

```c
DefineCustomBoolVariable(...)
DefineCustomIntVariable(...)
DefineCustomStringVariable(...)
DefineCustomEnumVariable(...)
DefineCustomRealVariable(...)
```
注册之后就可以像原生的guc参数一样修改。

```sql
ALTER SYSTEM
SET
SHOW
```
```c
DefineCustomEnumVariable("pglogical.conflict_log_level",
							 gettext_noop("Sets log level used for logging resolved conflicts."),
							 NULL,
							 &pglogical_conflict_log_level,
							 LOG,
							 server_message_level_options,
							 PGC_SUSET, 0,
							 NULL, NULL, NULL);
```
```sql
postgres=# show pglogical.conflict_log_level;
 pglogical.conflict_log_level 
------------------------------
 log
(1 row)
```
采用hook函数机制实现：

- check_hook 检查参数是否合法
- assign_hook 参数改变时执行
- show_hook 自定义show输出

## RegisterBackgroundWorker

RegisterBackgroundWorker() 是 PostgreSQL Background Worker Framework 的核心注册函数，用来在 postmaster 启动阶段注册后台进程。很多扩展（例如 pglogical）都会使用它创建自己的 worker。