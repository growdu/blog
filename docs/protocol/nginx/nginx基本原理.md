# nginx 基本原理

nginx由内核和模块组成，nginx接收到请求时，通过查找配置文件将此次请求映射到一个location block。

location 会涉及一个handler模块或多个filter模块。

- handler模块负责处理请求，完成响应内容的生成
- filter模块负责对响应内容进行处理

nginx采用多进程模型，分为master进程和worker进程，master进程负责监听端口、管理分配请求，worker进程负责处理具体的连接。

## nginx模块划分

结构上划分为：

- 核心模块：http模块、stream模块、event模块、mail模块
- 基础模块： http access、http fastcgi、http proxy、http rewrite
- 第三方模块： http upstream request hash、notice、http access key

功能上划分为：

- 核心模块
- 处理器模块
- 过滤器模块
- 代理类模块

核心模块主要负责建立nginx服务模型、管理网络层和应用协议层，以及自定义候选模块。

## nginx负载均衡

nginx启动后，会读取配置文件，载入对应的模块，确认监听的端口，以及对应的处理模块。最常见的比如：stream模块（4层转发，负载均衡）、http模块（反向代理，7层转发）。

负载均衡模块有两种工作方式：

- 轮转法：按顺序依次分配
- IP哈希法：同一个请求分配到相同的后端
- 权重法
- 最少连接