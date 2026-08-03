# protobuf实现rpc

Protocol Buffers (protobuf) 是Google开发的一种高效的数据序列化格式，常被用于RPC（远程过程调用）系统中。

protobuf用来定义网络数据交互的数据结构。

在C语言中使用protobuf需要使用到protobuf和protobuf-c两个项目，其安装步骤如下：

```shell
yum install protobuf-devel.x86_64 protobuf-c-devel.x86_64 protobuf-c.x86_64
```
## 示例

示例说明：使用c语言，需要存储两张表，一张是节点信息表，包含id、名字、角色、优先级等字段，另外一张表是事件表，包含故障、关机、重启等事件，需要实现这两张表的插入更新和删除。

### 消息定义

定义.proto

```proto
syntax = "proto3";

package cluster;

// ==================== 节点信息 ====================
message NodeInfo {
  int32 id = 1;
  string name = 2;
  string role = 3;
  int32 priority = 4;

  // 新增字段，向前兼容
  string description = 5;    // optional，新版本可用，旧版本忽略
}

// ==================== 事件类型 ====================
enum EventType {
  UNKNOWN = 0;
  FAILURE = 1;
  SHUTDOWN = 2;
  RESTART = 3;

  // 新增值，不影响旧版本
  MAINTENANCE = 4;
}

// ==================== 事件表 ====================
message Event {
  int32 event_id = 1;
  int32 node_id = 2;
  EventType type = 3;
  int64 timestamp = 4;

  string details = 5;        // 新增字段，旧版本忽略
}

// ==================== 操作类型 ====================
enum OpType {
  OP_INSERT = 0;
  OP_UPDATE = 1;
  OP_DELETE = 2;
}

// ==================== 通用请求 ====================
message Request {
  int32 version = 1;         // 消息版本号
  OpType op = 2;

  oneof payload {
    NodeInfo node = 3;
    Event event = 4;
  }
}

// ==================== 通用响应 ====================
message Response {
  int32 version = 1;         // 响应版本号
  bool success = 2;
  string message = 3;
}

```
### 生成C代码

```shell
protoc-c --c_out=. cluster.proto
```
```shell
# ls -al
总用量 29
drwxrwxrwx. 1 root root     0 9月   3 08:56 .
drwxrwxrwx. 1 root root  4096 9月   3 08:47 ..
-rwxrwxrwx. 1 root root 15440 9月   3 08:56 cluster.pb-c.c
-rwxrwxrwx. 1 root root  7459 9月   3 08:56 cluster.pb-c.h
-rwxrwxrwx. 1 root root   640 9月   3 08:48 cluster.proto
```