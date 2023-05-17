# libqb源码详解

> libqb 是一个提供高性能客户端服务器可重用功能的库。 它提供高性能日志记录、跟踪、IPC 和轮询的功能。
> libqb 的初始功能来自 corosync 的功能，专门针对客户端/服务器应用程序实现的高性能 API。

libqb分为客户端和服务端，除了网络通信外，如udp/tcp，libqb还支持本地ipc通信。

## ipc

libqb支持如下几种ipc通信方式：

```c
enum qb_ipc_type {
	QB_IPC_SOCKET,
	QB_IPC_SHM,
	QB_IPC_POSIX_MQ,
	QB_IPC_SYSV_MQ,
	QB_IPC_NATIVE,
};
```

ipc同样分为客户端和服务端，服务端接口以ipcs为前缀，客户端接口以ipcc为前缀。

- 创建ipc

  ```c
  qb_ipcs_service_t *
  qb_ipcs_create(const char *name, // ipc名称，客户端以这个名称来连接
  	       int32_t service_id,   // 服务id
  	       enum qb_ipc_type type, // ipc类型
             struct qb_ipcs_service_handlers *handlers // ipc函数句柄
               );
  ```

  在创建时需要将ipc行为传递给libqb，函数句柄定义如下：

  ```c
  struct qb_ipcs_service_handlers {
  	qb_ipcs_connection_accept_fn connection_accept; /// 接受连接回调
  	qb_ipcs_connection_created_fn connection_created; /// 连接创建回调
  	qb_ipcs_msg_process_fn msg_process; /// 消息处理回调
  	qb_ipcs_connection_closed_fn connection_closed; /// 连接关闭回调
  	qb_ipcs_connection_destroyed_fn connection_destroyed; /// 连接销毁回调
  };
  ```

  

