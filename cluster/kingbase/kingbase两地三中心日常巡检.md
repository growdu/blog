# kingbase两地三中心日常巡检

两地三中心运行一段时间后，需要定期巡检，观察集群状态是否正常，若有异常，需确认异常原因并及时处理。
## 确认集群是否正常

在observer节点的二进制安装目录下，使用如下命令查看集群的状态：

```shell
./bin/repmgr cluster show
```

应确保集群只有一个主库。

## 确认数据库是否正常

进入数据库节点二进制安装目录下，使用如下命令查看数据库的运行状态：

```shell
./bin/repmgr cluster show
```

- 若无法查询集群信息，需要进一步确认高可用组件是否正常。

- 若能正常查询信息，则需要确认数据库的状态是否正常

## 确认高可用组件是否正常

- 确认kbha服务状态

```shell
./bin/repmgr service status
```

- 确认corosync通信是否正常

```shell
./corosync/sbin/corosync-quorumtool
```

需确认Quorate是不是Yes。

## 查看日志是否有相关故障操作发生

- 查看hamgr.log,查看是否有ERROR或者切换操作

```shell
cat log/hamgr.log | grep -E "ERROR|promote"
```

- 查看kbha.log，查看是否有ERROR或者stop操作

```shell
cat log/kbha.log | grep -E "ERROR|stop"
```

若存在异常，需要取各个节点上的如下日志进行分析：

- log下的所有日志文件（hamgr.log、kbha.log）
- corosync/log下的日志文件（corosync.log）