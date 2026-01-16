# postgresql “伪双写”

## 结论

选择haproxy来实现。

要达到双写，其实就是把备库收到的请求都转发或者路由到主库，这又分为两种方式:

1.在备库的TCP五元组上将数据转发到主库；（这种方式客户端连接方式无需更改，但需要侵入修改数据库内核）
2.在备库或者其他节点加一层代理，使用不同的TCP五元组，并将数据转发到主库；（这种方式需要修改客户端连接方式，增加客户端连接串）

由于不能侵入修改数据库内核，因而采用增加代理的方式，而代理的主要作用就是将收到的TCP数据原样转发给主库。

这就意味着代理需要能访问所有节点，并判断谁是主节点。

```shell
           +-----------------+
           |     Client      |
           +-----------------+
                    |
                    v
          +---------------------+
          |  TCP 代理节点       |
          | (HAProxy / Envoy)  |
          +---------------------+
            |          |
            v          v
   +---------------+  +---------------+
   | PostgreSQL    |  | PostgreSQL    |
   | Primary       |  | Standby1      |
   +---------------+  +---------------+
                          ...

```

具体功能实现分为：

- 角色识别（role-agent）
- 流量转发（haproxy或者envoy）

通过轻量级 role-agent 将 pg_is_in_recovery() 状态转换为 HTTP 健康检查接口，由 HAProxy或者envoy 在四层进行主库优先转发。

## HAProxy转发

```shell
global
    maxconn 5000
    log stdout format raw local0

defaults
    mode tcp
    timeout connect 5s
    timeout client  1m
    timeout server  1m
    log global

frontend pg_front
    bind *:5000
    default_backend pg_primary

backend pg_primary
    mode tcp
    balance first
    option tcp-check

    #option pgsql-check user repl

    server pg1 127.0.0.1:5433 check
    server pg2 127.0.0.1:5432 check backup
```

## envoy

```yaml
static_resources:
  listeners:
    - name: listener_pg
      address:
        socket_address:
          address: 0.0.0.0
          port_value: 5000
      filter_chains:
        - filters:
            - name: envoy.filters.network.tcp_proxy
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.tcp_proxy.v3.TcpProxy
                stat_prefix: pg_tcp
                cluster: pg_primary

  clusters:
    - name: pg_primary
      connect_timeout: 5s
      type: strict_dns
      lb_policy: round_robin
      health_checks:
        - timeout: 2s
          interval: 5s
          tcp_health_check: {}
          unhealthy_threshold: 3
          healthy_threshold: 2
      load_assignment:
        cluster_name: pg_primary
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address:
                      address: 127.0.0.1
                      port_value: 5433
                # 主节点 priority=0
                load_balancing_weight:
                  value: 100
                priority: 0
              - endpoint:
                  address:
                    socket_address:
                      address: 127.0.0.1
                      port_value: 5432
                # 备节点 priority=1，相当于 HAProxy backup
                load_balancing_weight:
                  value: 100
                priority: 1
```

## haproxy和envoy对比

**HAProxy** 和 **Envoy** PostgreSQL 主备 L4 TCP 代理下，**性能、可用性、并发能力、稳定性、开源风险** 这五个维度系统性对比结果如下：

---

## 1️⃣ 性能

| 维度       | HAProxy                           | Envoy                                                  |
| -------- | --------------------------------- | ------------------------------------------------------ |
| TCP 转发吞吐 | 非常高，C语言实现，单进程即可支撑几十万连接            | 高，多线程异步，略高资源消耗                                         |
| 延迟       | 极低，几乎无附加延迟                        | 较低，但比 HAProxy 高一点（解析健康检查内容略增加 CPU）                     |
| 资源占用     | 极低，单进程 + epoll/kqueue，内存占用少       | 中等，多线程 + 异步调度，内存占用略高                                   |
| 健康检查     | tcp-check + send/expect，可自定义字符串匹配 | tcp_health_check，可匹配 TCP/HTTP 内容，Envoy PLUS 可解析完整 HTTP |

**结论**：

* HAProxy 性能略优，轻量、低延迟
* Envoy 功能更多，健康检查灵活，但略占用更多 CPU/内存

---

## 2️⃣ 可用性

| 维度          | HAProxy                                  | Envoy                                                   |
| ----------- | ---------------------------------------- | ------------------------------------------------------- |
| 主备识别        | tcp-check + expect，可直接判断 primary/replica | tcp_health_check + string match，Envoy PLUS 支持 HTTP 内容检查 |
| 动态 failover | 基于健康检查和 server 状态，自动路由                   | 同样基于健康检查，多线程异步，PLUS 支持 xDS 热更新，无需 reload                |
| 多备库支持       | 支持，backend 配置多个 server                   | 支持，cluster 配置多个 endpoint                                |
| 自动切换延迟      | 健康检查间隔 × fail/rise 阈值（通常 1~5s）           | 健康检查间隔 × fail/rise 阈值（通常 2~5s）                          |

**结论**：

* 两者可用性都高
* Envoy 在动态配置更新、xDS 热更新方面更灵活
* HAProxy 配置简单，生产环境验证充分

---

## 3️⃣ 并发能力

| 维度      | HAProxy                            | Envoy                       |
| ------- | ---------------------------------- | --------------------------- |
| 并发连接数   | 高，单进程 + epoll/kqueue，可支撑几十万 TCP 连接 | 高，多线程 + 异步，负载在多核 CPU 上更均衡   |
| CPU 利用率 | 单进程高负载时可能成为瓶颈，需要增加进程或线程            | 多线程，CPU 利用率更均衡              |
| I/O 模型  | epoll/kqueue                       | epoll/kqueue + 异步事件循环 + 线程池 |

**结论**：

* 两者并发能力都足够
* HAProxy 在单机轻量场景更省资源
* Envoy 多线程设计在多核服务器上更容易扩展

---

## 4️⃣ 稳定性

| 维度    | HAProxy      | Envoy                   |
| ----- | ------------ | ----------------------- |
| 代码成熟度 | 非常成熟，十多年生产经验 | 较成熟，社区活跃，但功能更新频繁        |
| 长期运行  | 极少出现内存泄漏或崩溃  | 稳定，但长时间高负载需监控内存/线程      |
| 配置容错  | 高，简单配置易维护    | 中等，复杂配置容易出错             |
| 社区支持  | 广泛生产案例、成熟文档  | 活跃社区，企业版 PLUS 提供额外稳定性保障 |

**结论**：

* HAProxy 更稳定、简单
* Envoy 功能丰富，但生产环境需注意版本升级和配置正确性

---

## 5️⃣ 开源风险

| 维度    | HAProxy        | Envoy                                                |
| ----- | -------------- | ---------------------------------------------------- |
| 许可    | GPLv2          | Apache 2.0                                           |
| 企业依赖  | 开源版即可满足大部分生产需求 | 开源版功能丰富，但高级功能（动态 xDS、HTTP 健康检查、控制面板）企业可能需 Envoy PLUS |
| 社区成熟度 | 大量生产案例，长期稳定    | 社区活跃，功能更新快，需注意版本兼容性                                  |
|主要编程语言|C|C++|

**结论**：

* HAProxy 开源风险低，稳定可靠
* Envoy 开源版足够大部分功能，高级企业功能需授权

---

## 6️⃣ 综合对比

| 维度   | HAProxy     | Envoy        | 适用场景建议                     |
| ---- | ----------- | ------------ | -------------------------- |
| 性能   | 极高，轻量       | 高，功能多        | 单机高性能 TCP 代理               |
| 可用性  | 高，可用性依赖配置简单 | 高，更灵活，动态更新可用 | 多节点、动态 failover、xDS 动态更新场景 |
| 并发能力 | 高           | 高，多线程更均衡     | 高并发 TCP 流量场景               |
| 稳定性  | 极高，长期生产验证   | 高，需监控和版本控制   | HAProxy 更稳定，Envoy 功能更强     |
| 开源风险 | 低           | 中等，高级功能需授权   | HAProxy 易部署，Envoy 可扩展性更强   |

---

### 🔹 实战建议

1. **小型 / 单集群 / 高性能场景**

   * HAProxy 足够
   * 配置简单、稳定可靠

2. **多备库 / 多入口 / 动态切换 / 企业环境**

   * Envoy 更合适
   * 支持多备库代理、多入口、xDS 动态更新、健康检查灵活

---

# reference

1.https://dincosman.com/2024/08/10/haproxy-external-sqlcheck/
2.https://gist.github.com/jpuris/4c8e837c17415eb8d96c6385c12a7fc6
3.https://gist.github.com/gplv2/e124a26295b17316d89e9bb3e6249dd2
4.https://github.com/haproxy/haproxy
5.https://www.haproxy.com/documentation/haproxy-configuration-tutorials/reliability/health-checks/