# vpp日志系统

## vpp日志接口

在dpdk插件中可以使用vpp封装的dpdk日志打印接口：

```c
dpdk_log_info
dpdk_log_warn
dpdk_log_notice
dpdk_log_err
```

vpp本身的日志会调用syslog写到内核日志系统里面。

vppctl的日志会写到startup.conf里配置的日志路径里面。

## vpp如何处理dpdk的日志

 vpp 配置文件（/etc/vpp/startup.conf） 的 dpdk section 添加 **log-level debug** 配置项，其中 debug 是日志级别。dpdk中日志级别对应数字如下：

```c
/* Can't use 0, as it gives compiler warnings */
#define RTE_LOG_EMERG    1U  /**< System is unusable.               */
#define RTE_LOG_ALERT    2U  /**< Action must be taken immediately. */
#define RTE_LOG_CRIT     3U  /**< Critical conditions.              */
#define RTE_LOG_ERR      4U  /**< Error conditions.                 */
#define RTE_LOG_WARNING  5U  /**< Warning conditions.               */
#define RTE_LOG_NOTICE   6U  /**< Normal but significant condition. */
#define RTE_LOG_INFO     7U  /**< Informational.                    */
#define RTE_LOG_DEBUG    8U  /**< Debug-level messages.             */
```

成功启动vpp后，进入vpp的cli界面使用如下命令可以查看dpdk日志：

```shell
show log
```



#  reference

1. https://blog.csdn.net/choumin/article/details/121630307