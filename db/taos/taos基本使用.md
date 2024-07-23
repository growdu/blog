# taosd基本使用

taos是一个开源的时序数据库，目前发展势头较好，走的开源路线。

## 二进制包下载安装

### server

需要到taos官网下载，但是无法直接获取下载链接，要输入邮箱（能获取到联系你的方式，便于统计下载量），会将下载链接发送到的你的邮箱。

```shell
wget https://www.taosdata.com/assets-download/3.0/TDengine-server-3.3.2.0-Linux-x64.rpm
rpm -i TDengine-server-3.3.2.0-Linux-x64.rpm
systemctl start taosd
```
需要使用root用户安装。

taosd的默认数据库目录在/var/lib/taos下面，他的配置文件在/etc/taos/taos.cfg。

taos的数据库目录结构大致如下：

```shell
/var/lib/taos
├── dnode
│   ├── dnode.info
│   └── dnode.json
├── mnode
│   ├── data
│   ├── mnode.json
│   ├── sync
│   └── wal
└── vnode
```
taos默认以root用户运行：(已常规数据库有所区别，一般数据库都是以普通用户运行的，比如postgres、mysql)。

```shell
(base) ➜  ~ ps -ef | grep taosd
root     3744260       1  0 11:07 ?        00:00:00 /usr/bin/taosd
```

如果没有明确指定，taos默认监听127.0.0.1的6300端口，只能本机访问。同时还会监听一个unix domain socket。

```shell
(base) ➜  ~ sudo netstat -anp | grep taos
tcp        0      0 0.0.0.0:6030            0.0.0.0:*               LISTEN      3744260/taosd       
tcp        0      0 127.0.0.1:6030          127.0.0.1:54630         ESTABLISHED 3744260/taosd       
tcp        0      0 127.0.0.1:54630         127.0.0.1:6030          ESTABLISHED 3744260/taosd       
unix  2      [ ACC ]     STREAM     LISTENING     293894282 3744286/udfd         /var/lib/taos//.udfd.sock.1
```

taos默认的运行日志放在/var/log/taos/目录下面，其目录结构如下：

```shell
/var/log/taos
├── taosdlog.0
├── taosSlowLog
├── tdengine_install.log
└── udfdlog.0
```

我们要使taosd能对外服务，就不能使用127.0.0.1这个ip，而是要使用对外的ip，这里需要修改配置文件。

```shell
vim /etc/taos/taos.cfg
(base) ➜  ~ cat /etc/taos/taos.cfg | grep fqdn
fqdn                      taosdb
```
将fqdn那行后面的域名换成自己的ip或者域名，如果使用的是域名的话，可以在/etc/hosts里添加域名和ip的映射关系。

修改完成后需要重启taosd，需要特别注意的是因为taosd会默认写一些数据到/var/lib/taos的数据目录下，目前直接修改配置文件重启会失败。（当前采用的措施是删除数据库目录重新启动）

```shell
07/22 11:19:24.065295 03779249 C DND start to init dnode env
07/22 11:19:24.065674 03779249 C DND succceed to read dnode file /var/lib/taos//dnode/dnode.json
07/22 11:19:24.065694 03779249 C DND ERROR dnode:1, localEp taosdb:6030 different from node1:6030
07/22 11:19:24.065698 03779249 C DND ERROR localEp taosdb:6030 different with /var/lib/taos//dnode/dnode.json and need to be reconfigured
07/22 11:19:24.065781 03779249 C DND ERROR failed to read file since Invalid config option
07/22 11:19:24.065791 03779249 C DND ERROR failed to create dnode since Invalid config option
07/22 11:19:24.065794 03779249 C DND ERROR failed to init dnode since Invalid config option
```

```shell
sudo rm -rf /var/lib/taos/*
sudo systemctl restart taosd 
```
重启之后配置正确的话就会监听对外的ip和端口了。

### client

#### cli

安装server时默认就安装了cli，直接使用taos命令就可以连接数据库。(没有设置密码也没有指定端口、数据库，所以我也不知道密码用户数据库是什么，缺省用户和密码似乎是root和taosdata)

```shell
(base) ➜  ~ taos
Welcome to the TDengine Command Line Interface, Client Version:3.3.2.0
Copyright (c) 2023 by TDengine, all rights reserved.


  *********************************  Tab Completion  *************************************
  *   The TDengine CLI supports tab completion for a variety of items,                   *
  *   including database names, table names, function names and keywords.                *
  *   The full list of shortcut keys is as follows:                                      *
  *    [ TAB ]        ......  complete the current word                                  *
  *                   ......  if used on a blank line, display all supported commands    *
  *    [ Ctrl + A ]   ......  move cursor to the st[A]rt of the line                     *
  *    [ Ctrl + E ]   ......  move cursor to the [E]nd of the line                       *
  *    [ Ctrl + W ]   ......  move cursor to the middle of the line                      *
  *    [ Ctrl + L ]   ......  clear the entire screen                                    *
  *    [ Ctrl + K ]   ......  clear the screen after the cursor                          *
  *    [ Ctrl + U ]   ......  clear the screen before the cursor                         *
  ****************************************************************************************

Server is TDengine Community Edition, ver:3.3.2.0 and will never expire.

taos> 
```

尝试了一下基本命令，看起来有点像是类mysql的，没有postgres的\d、\d+，倒是有show databases。

```shell
taos> \d+
    > ;

DB error: unrecognized token: "\d+ ;" (0.000059s)
taos> \d;

DB error: unrecognized token: "\d;" (0.000033s)
taos> help
    > ;

DB error: syntax error near "help ;" (0.000036s)
taos> show database;

DB error: syntax error near "database;" (0.000041s)
taos> show databases;
              name              |
=================================
 information_schema             |
 performance_schema             |
Query OK, 2 row(s) in set (0.000737s)

taos> 
```

#### windows cli

taos官网提供了客户端程序，同样需要输入邮箱地址才能下载，下载链接会发到邮箱地址。

```shell
wget https://www.taosdata.com/assets-download/3.0/TDengine-client-3.3.2.0-Windows-x64.exe
```
下载完成后可以安装到windows，可以生成桌面快捷方式，但实际上是启动了一个cmd窗口，可以使用taos命令连接服务端，还是没有界面。

```shell
 C:\TDengine 的目录

2024/07/22  14:06    <DIR>          .
2024/07/22  14:06    <DIR>          cfg
2024/07/22  14:06    <DIR>          connector
2024/07/22  14:06    <DIR>          driver
2024/07/22  14:06    <DIR>          examples
2024/07/22  14:06    <DIR>          include
2024/07/22  11:44    <DIR>          log
2024/03/26  23:17           982,296 msvcp140d.dll
2024/06/28  12:14         4,833,280 taos.exe
2024/06/28  12:14           475,136 taosBenchmark.exe
2024/06/28  12:14           654,848 taosdump.exe
2024/07/22  14:06    <DIR>          taos_odbc
2024/07/22  14:06            48,905 unins000.dat
2024/07/22  14:06         3,141,379 unins000.exe
```

```shell
C:\TDengine>taos -h taosdb
Welcome to the TDengine Command Line Interface, Client Version:3.3.2.0
Copyright (c) 2023 by TDengine, all rights reserved.


Server is TDengine Community Edition, ver:3.3.2.0 and will never expire.

taos> show databases;
              name              |
=================================
 information_schema             |
 performance_schema             |
Query OK, 2 row(s) in set (0.038056s)

taos>
```

### webui

taos还提供了一个web操作管理界面taos-explorer，不过属于付费功能，github下面也没有该仓库的开源。

## 源码编译安装

