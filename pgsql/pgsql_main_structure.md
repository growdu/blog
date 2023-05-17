# pgsql架构

## 整体模式

pgsql采用C/S架构（客户端/服务端）模式。应用层通过INET或者Unix Socket利用既定的协议与数据库服务器进行通信。

pgsql把客户端称为前端，把服务端称为后端。前端通过调用**libpq**来与后端通信。
后端由多个进程组成，前端发送网络数据报文（查询请求）到后端，后端解析请求后回复相应的报文。

## pgsql后端进程

- postgres主进程（postmaster）

管理后端的常驻进程，也称为’postmaster’。
其默认监听UNIX Domain Socket和TCP/IP（Windows等，一部分的平台只监听tcp/ip）的5432端口，等待来自前端的的连接处理。
监听的端口号可以在PostgreSQL的设置文件postgresql.conf里面可以改。

当有前端连接过来的时候，postmaster会fork一个子进程来处理前端的连接请求。并通过共享内存进行进程间通信。

- postgres子进程

子进程根据pg_hba.conf定义的安全策略来判断是否允许进行连接，根据策略，会拒绝某些特定的IP及网络，或者也可以只允许某些特定的用户或者对某些数据库进行连接。

- 辅助进程
  
  - writer process
  - WAL wriiter process
  - archive process
  - stats collector process
  - logger process
  - autovacuum
  - wal sender/wal receiver

### 启动流程

```mermaid
graph TB
main-->PostmasterMain-->SysLogger_Start-->fork_process-->InitPostmasterChild-->SysLoggerMain
PostmasterMain-->maybe_start_bgworkers-->ServerLoop-->StartAutoVacLauncher-->MaybeStartWalReceiver
PostmasterMain-->StartCheckpointer
PostmasterMain-->StartBackgroundWriter
```

### 后端处理流程

1. 接收前端发送过来的请求报文
2. parse模块进行文本解析，得到查询树
3. analyze模块进行分析处理
4. 通过查询语句的重写实现视图和规则
5. 查询优化，优化查询树
6. executor执行处理
7. 返回执行结果给前端
8. 重复步骤1-7

## 后端运行主要逻辑

1. initdb初始化一个数据库，创建data目录、模板数据库、默认用户、默认配置文件，主要涉及内容如下：
   
   - pg_wal:存放wal日志
   
   - base：存放表数据

2. postgresql采用先写wal日志，再写数据的方式；通过保证wal数据库写入的方式来保证数据写入，并通过wal日志可以进行数据redo和undo；

3. initdb初始化数据目录后，可以通过pg_ctl启动后端服务进程；

4. 后端服务进程首先是启动了一个postgres进程，该进程会fork出startup、logger、bgwriter、walwriter、walreceiver等子进程，并通过共享内存和信号进行通信，同时该进程还会监听配置的ip和端口；

5. postgres进程启动后会先启动startup进程，startup进程会读取control文件，确认是否需要恢复，即是否还有wal日志还没有转换为数据，若有或者配置recovery，则需要根据对应的control信息和检查点信息，找到离检查点或配置的最近的lsn，再根据lsn找到对应wal日志进程redo；

6. redo完成后，若开启了流复制，则startup进程将唤醒walreceiver进程，walreceiver获取到最新的lsn后，将和主库walsender进程进行wal同步；

7. postgres启动walreceiver进程时，walreceiver会和另外一个postgres服务端建立连接，另一端将会启动一个walsender进程来进行流复制同步；
