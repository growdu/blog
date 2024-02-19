# repmgr实现原理

repmgr分为三部分，其主要功能如下：

- repmgr插件，这是repmgr与Postgresql数据库交互的接口，在数据库运行起来的时候需要把这个插件加载进来
- repmgrd守护程序，这是负责监控流复制状态、自动故障转移的服务程序
- repmgr客户端，这是一个命令行工具，主要负责


## repmgr插件

## repmgrd守护程序