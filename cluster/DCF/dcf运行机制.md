# dcf运行机制

dcf通过stream的概念来运行分布式协议，每个stream是一个完整的分布式实例。
每个stream可以由多个节点组成。

## 外部应用启动接口

dcf在初次启动后，会将传入的配置文件信息写入到metadata里，也就是说dcf为了设计成一个通用的库，是不需要配置文件的。
整个运行启动都是通过传参的方式来启动，这样就可以把参数配置放在外部应用程序内。

应用通过json字符串数组传入参数，在初次传入时dcf会将元信息持久化到文件中，默认在应用执行目录下面，并按照节点id命名目录存储。
当应用再次启动时，就会直接读取持久化到文件的信息，而不会再读取传入的json字符串。
其中json字符串数组实例如下：

```json
[{
	"stream_id": 1,
	"node_id": 1,
	"ip": "x.x.x.21",
	"port": 1712,
	"role": "LEADER"
}, {
	"stream_id": 1,
	"node_id": 2,
	"ip": "x.x.x.22",
	"port": 1713,
	"role": "FOLLOWER"
}, {
	"stream_id": 1,
	"node_id": 3,
	"ip": "x.x.x.23",
	"port": 1714,
	"role": "FOLLOWER"
}]

```

## 内部启动流程


dcf内部从dcf_start开启启动，dcf_start需要每个节点都运行，并且需要传入节点id和集群配置json字符串。

```c
int dcf_start(unsigned int node_id, const char *cfg_str);
```

dcf内部采用的是多线程模型，在启动后需要初始化各个线程。具体包括如下几个方面：

- metadata（元数据，简称md）
- network（消息通信，简称mec）
- log store（日志持久化存储，简称stg）
- election（投票，简称elc）
- replication（流复制，简称rep）

### metadata

若元数据目录已存在，直接从文件中读取元数据。若元数据目录不存在，则根据传入的json字符串解析元数据信息并写入文件。
同时会将流的相关配置信息加载到内存中，后续会根据这些配置进行初始化。

### network

mec模块主要是负责网络通信的，采用自己管理内存的方式申请分配内存，因而需要先初始化内存池，并且采用伙伴算法进行内存分配。
网络模块有一个全局实例g_mec，用于保存mec相关的数据结构。

```c
typedef struct st_mec_instance {
    mec_profile_t      profile; ///< mec主要信息
    mq_context_t       send_mq; ///< 发送队列
    mq_context_t       recv_mq; ///< 接收队列
    mec_context_t      mec_ctx; ///< mec上下文
    fragment_ctx_t     fragment_ctx; ///< 分片上下文
    thread_t           daemon_thread;///< 守护线程id
    reactor_pool_t     reactor_pool[PRIV_CEIL]; ///< epoll反应堆数组
    agent_pool_t       agent_pool[PRIV_CEIL]; ///< 代理池
    ssl_ctx_t         *ssl_acceptor_fd; ///< ssl接受器
    ssl_ctx_t         *ssl_connector_fd;///< ssl连接器
} mec_instance_t;
static mec_instance_t *g_mec = NULL;
```
mec模块会初始化g_mec，首先是需要设置其配置，也就是profile，其中profile需要设置如下信息：

```c
typedef struct st_mec_profile {
    spinlock_t           lock; ///< 自旋锁
    uint16               inst_id; ///< mec实例id
    volatile uint16      inst_count; ///< mec实例个数
    mec_addr_t           inst_arr[CM_MAX_NODE_COUNT]; ///< mec地址数组
    int16                maps[CM_MAX_NODE_COUNT];     ///< 节点数组
    uint8                pipe_type; ///< 管道类型
    uint8                reserved;  ///< 预留
    uint16               channel_num; ///< 通道数
    uint64               msg_pool_size; ///< 消息池大小
    uint32               frag_size; ///< 分片大小
    uint32               batch_size; ///< 批量包大小
    uint32               agent_num; ///< 代理数量
    uint32               reactor_num; ///< 反应堆数量
    compress_algorithm_t algorithm; ///< 压缩算法
    uint32               level;  
    int32                connect_timeout;  // ms
    int32                socket_timeout;   // ms
} mec_profile_t;
```

mec通信层面使用reactor模型，并将其分为agent和reactor，agent+reactor=mec，同时mec又分为高优先级和低优先级。
而agent和reactor的个数则由上面提到的配置传入。agent和reacor都是线程池，有任务来的时候就会attach到对应的线程上去执行。


### log store

### election

### replication
