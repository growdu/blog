# ha元信息常见存储方式

## mysql mha

[源码地址](https://github.com/yoshinorim/mha4mysql-manager)

mysql MHA(Master High Availability)是mysql高可用一套相对成熟的解决方案。MHA 由 MHA 管理器和 MHA 节点组成。

- MHA Manager 是包含监控 MySQL 主站、控制主站故障转移等功能的管理器程序。

MHA Manager 可以单独部署在一台独立的机器上，管理多个 master-slave 集群；也可以部署在一台 slave 节点上。
MHA Manager 会定时探测集群中的 master 节点。当 master 出现故障时，
它可以自动将最新数据的 slave提升为新的 master， 然后将所有其他的 slave 重新指向新的 master。整个故障转移过程对应用程序完全透明。

- MHA node包含解析 MySQL 二进制/中继日志、识别中继日志位置、将中继日志应用于其他从站、将事件应用于目标从站等功能的故障转移程序脚本，MHA 节点在每个 MySQL 服务器上运行。

mha node和数据库运行在一起，作为mha的代理，负责监控数据库，并且连接MHA manager注册并上报信息。
当 MHA 管理器执行故障转移时，MHA 管理器通过 SSH 连接 MHA node，并在需要时执行 MHA 节点命令。

在标准的方案中，mha manager是一个节点，当mha manager故障后，将无法进行自动故障转移。（即mha存在单点问题）



### 结论

- <font color="red">在不考虑mha manager单点问题的场景下，mysql mha不需要持久化存储元信息，通过mha node主动向mha manager注册和上报数据库状态信息来进行数据库故障转移。</font>
- <font color="red">在考虑mha manager单点问题的场景下，一般引入zookeeper来保存mha manager节点的信息，以及通过zookeeper来判断那个mha manager提供服务。并在当前服务的mha manager故障时，切换到另一个mha manager.</font>

### reference

1. https://github.com/yoshinorim/mha4mysql-manager/wiki/Architecture
2. https://github.com/yoshinorim/mha4mysql-manager/wiki/Advantages
3. https://github.com/yoshinorim/mha4mysql-manager/wiki
4. https://www.cnblogs.com/keme/p/9707755.html

## oracle site guard

## OpenGauss 多地高可用架构

## OceanBase 两地三中心



### reference

1. https://www.oceanbase.com/docs/community-observer-cn-0000000000161661