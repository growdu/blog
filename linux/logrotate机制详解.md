
logrotate 是一个 linux 系统日志的管理工具。可以对单个日志文件或者某个目录下的文件按时间 / 大小进行切割，压缩操作；指定日志保存数量；还可以在切割之后运行自定义命令。

logrotate 是基于 crontab 运行的，所以这个时间点是由 crontab 控制的，具体可以查询 crontab 的配置文件 /etc/anacrontab。 系统会按照计划的频率运行 logrotate，通常是每天。在大多数的 Linux 发行版本上，计划每天运行的脚本位于 /etc/cron.daily/logrotate。

主流 Linux 发行版上都默认安装有 logrotate 包，如果你的 linux 系统中找不到 logrotate, 可以使用 apt-get 或 yum 命令来安装。

## 运行机制

logrotate 在很多 Linux 发行版上都是默认安装的。系统会定时运行 logrotate，一般是每天一次。系统是这么实现按天执行的。crontab 会每天定时执行 /etc/cron.daily 目录下的脚本，而这个目录下有个文件叫 logrotate。在 centos 上脚本内容是这样的：

系统自带 cron task：`/etc/cron.daily/logrotate`，每天运行一次。

```shell
(base) ➜  ~ sudo cat /etc/cron.daily/logrotate                                    
#!/bin/sh                                                                          
/usr/sbin/logrotate -s /var/lib/logrotate/logrotate.status /etc/logrotate.conf     
EXITVALUE=$?                                                                       
if [ $EXITVALUE != 0 ]; then                                                       
    /usr/bin/logger -t logrotate "ALERT exited abnormally with [$EXITVALUE]"       
fi                                                                                 
exit 0
```
可以看到这个脚本主要做的事就是以 `/etc/logrotate.conf` 为配置文件执行了 logrotate。就是这样实现了每天执行一次 logrotate。



# reference

1. https://wsgzao.github.io/post/logrotate/