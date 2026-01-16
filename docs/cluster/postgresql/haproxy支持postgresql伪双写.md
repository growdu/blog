# haproxy支持postgresql伪双写

要达到双写，其实就是把备库收到的请求都转发或者路由到主库，这又分为两种方式:

1.在备库的TCP五元组上将数据转发到主库；（这种方式客户端连接方式无需更改，但需要侵入修改数据库内核）
2.在备库或者其他节点加一层代理，使用不同的TCP五元组，并将数据转发到主库；（这种方式需要修改客户端连接方式，增加客户端连接串）

由于不能侵入修改数据库内核，因而采用增加代理的方式，而代理的主要作用就是将收到的TCP数据原样转发给主库。

这就意味着代理需要能访问所有节点，并判断谁是主节点。

- haproxy本身就是一个代理组件，支持代理。

- 要实现主库判断，可以通过健康检查来实现。

健康检查又分为多种方式：
  - tcp检查（发送tcp请求检查，可以构造postgresql协议的数据，可读性差，对postgresql协议需要有一定的理解）
  - http检查（发送http请求，需要有http检查服务）
  - pgsql-check（haproxy提供的数据库检查，但只能发送startup消息，需要做二次开发）
  - 外部脚本（在外部写一个脚本用于判断，耦合性最小，实现最简单，但是延迟可能较高）

## 代理

haproxy本身就用于代理和故障切换或者负载均衡。只需要使用其基本功能就行。示例配置文件如下：

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

    server pg1 127.0.0.1:5433 check
    server pg2 127.0.0.1:5432 check backup
```

上面的haproxy配置对应如下内容：

---

# **1️⃣ 大模块结构**

HAProxy 配置通常分为三个大块：

1. **global** → 全局设置，影响整个 HAProxy 进程
2. **defaults** → 默认行为设置，可以被 frontend/backend 继承
3. **frontend/backend** → 实际网络流量处理和负载分发逻辑

你的配置大概是：

```cfg
global
defaults
frontend pg_front
backend pg_primary
```

* **global**：控制 HAProxy 本身运行的资源、日志、最大连接等
* **defaults**：设置 frontend/backend 的默认 TCP 模式、超时和日志
* **frontend pg_front**：监听客户端请求端口 5000，把请求送到 pg_primary 后端
* **backend pg_primary**：定义 PostgreSQL 节点，健康检查、负载均衡策略、主备关系

---

# **2️⃣ global 模块**

```cfg
global
    maxconn 5000
    log stdout format raw local0
```

| 配置项                            | 作用                                                     |
| ------------------------------ | ------------------------------------------------------ |
| `maxconn 5000`                 | HAProxy 最大同时处理的连接数是 5000，超过会排队                         |
| `log stdout format raw local0` | 日志输出到 stdout（常用于容器），日志格式是 raw，local0 是 syslog facility |

**说明**：

* 这里没有启用 `daemon` 或 `pidfile`，通常在容器里会直接在前台运行
* `maxconn` 控制全局并发能力，不影响单个 backend/server 配置

---

# **3️⃣ defaults 模块**

```cfg
defaults
    mode tcp
    timeout connect 5s
    timeout client  1m
    timeout server  1m
    log global
```

| 配置项                  | 作用                                |
| -------------------- | --------------------------------- |
| `mode tcp`           | 默认使用 TCP 层转发（第 4 层），而不是 HTTP 层    |
| `timeout connect 5s` | 客户端连接 HAProxy 时，如果连接到后端超时 5 秒就断开  |
| `timeout client 1m`  | 客户端空闲时间超过 1 分钟就断开                 |
| `timeout server 1m`  | HAProxy 与后端 server 之间空闲超过 1 分钟就断开 |
| `log global`         | 继承 global 定义的日志设置                 |

**说明**：

* `mode tcp` 是关键，因为 PostgreSQL 是 TCP 协议，不是 HTTP
* 超时设置保证 HAProxy 不会无限等待，避免资源占用

---

# **4️⃣ frontend pg_front**

```cfg
frontend pg_front
    bind *:5000
    default_backend pg_primary
```

| 配置项                          | 作用                                |
| ---------------------------- | --------------------------------- |
| `frontend pg_front`          | 定义一个入口（前端）处理客户端连接                 |
| `bind *:5000`                | HAProxy 在本地 5000 端口监听所有网卡的 TCP 连接 |
| `default_backend pg_primary` | 所有流量默认发送到 pg_primary 后端           |

**说明**：

* 这里没有定义高级路由或 ACL，所以**所有连接都走 pg_primary**
* 前端只是 TCP 隧道，把流量直接送到 backend

---

# **5️⃣ backend pg_primary**

```cfg
backend pg_primary
    mode tcp
    balance first
    option tcp-check

    server pg1 127.0.0.1:5433 check
    server pg2 127.0.0.1:5432 check backup
```

---

## **5.1 backend 基础配置**

| 配置项                | 作用                                      |
| ------------------ | --------------------------------------- |
| `mode tcp`         | backend 使用 TCP 转发                       |
| `balance first`    | **负载均衡策略**：总是选择第一个健康节点，只有它 DOWN 才用第二个节点 |
| `option tcp-check` | 启用 TCP 层健康检查（简单建立 TCP 连接，不发任何数据）        |

**说明**：

* `balance first` 是关键，因为 HAProxy 会永远把流量发送到 pg1（127.0.0.1:5433），除非它 DOWN
* `option tcp-check` 让 HAProxy 自动检测 pg1/pg2 是否可以 TCP 连接

balance除了有first模式外，还有如下模式：

| 模式             | 适用       | 特点          | 场景         |
| -------------- | -------- | ----------- | ---------- |
| roundrobin     | TCP/HTTP | 轮询分发        | 节点均衡、简单场景  |
| leastconn      | TCP/HTTP | 最少连接        | 长连接负载均衡    |
| source         | TCP/HTTP | 根据客户端 IP 哈希 | 会话固定分配     |
| first          | TCP/HTTP | 总是选择第一个可用   | 主备切换、数据库主备 |
| static-rr      | TCP/HTTP | 静态轮询        | 少用         |
| random         | TCP/HTTP | 随机          | 高并发、均匀分布   |
| uri/hdr/cookie | HTTP     | HTTP 内容哈希   | HTTP 会话保持  |


---

## **5.2 server 定义**

| server 配置                                | 解释                                           |
| ---------------------------------------- | -------------------------------------------- |
| `server pg1 127.0.0.1:5433 check`        | 主库节点，启用健康检查 (`check`)                        |
| `server pg2 127.0.0.1:5432 check backup` | 备库节点，健康检查启用，但 `backup` 表示**只有主库 DOWN 才会被使用** |

### **重点：backup 行为**

* HAProxy backup server 机制：

  1. pg1 UP → 流量全部走 pg1
  2. pg1 DOWN → 流量切换到 pg2
* 结合 `balance first` → 整体逻辑就是“一主一备”模式

---

## **6️⃣ 总结流量行为**

假设客户端连接到 `5000`：

1. HAProxy `pg_front` 接受连接
2. 默认送到 `pg_primary` backend
3. backend 检查健康状态：

   * pg1 UP → 走 pg1:5433
   * pg1 DOWN → pg2 UP → 走 pg2:5432
   * pg2 DOWN → 连接失败
4. TCP-check 确保节点可以建立连接

**结果**：

* **平时** → 所有流量走主库
* **主库挂掉** → 自动切到备库
* **备库正常**，主库恢复 → 自动切回主库

---

## **7️⃣ 图解（文字版）**

```
Client
  |
  | TCP:5000
  v
HAProxy Frontend pg_front
  |
  |--> Backend pg_primary
        |
        |--> pg1 127.0.0.1:5433 (主库, first)
        |
        |--> pg2 127.0.0.1:5432 (备库, backup)
```

* `balance first + backup` → HAProxy 优先 pg1
* TCP-check → 确保节点可以建立连接

---

总结：

* **global** → HAProxy 全局资源和日志
* **defaults** → 默认 TCP 模式、超时
* **frontend** → 客户端入口，监听端口，流量指向 backend
* **backend** → 定义节点、健康检查、负载策略
* **server + check + backup** → 一主一备自动故障切换

---

## 健康检查


---

# **1️⃣ HAProxy 健康检查概念**

HAProxy 的健康检查（Health Check / `check`）用于 **判断后端 server 是否可用**，主要作用：

1. **保证流量只走健康节点**
2. **自动剔除宕机节点**，避免请求失败
3. **支持主备节点切换**（backup）、负载均衡策略选择

**健康检查核心点**：

* **类型**：TCP 层或 HTTP 层
* **频率**：检查间隔 (`inter`)
* **阈值**：标记 UP/DOWN 所需的连续成功/失败次数 (`rise`, `fall`)
* **动作**：标记节点 DOWN/UP，影响负载均衡

HAProxy 在 **TCP/HTTP 或 external 脚本层面**都有实现机制。

---

# **2️⃣ TCP 健康检查**

### **原理**

* HAProxy 只在 **TCP 层**建立连接
* 检查 server **端口是否可达**
* 不发送任何数据包，不关心服务内容

**工作流程**：

1. HAProxy 尝试 TCP 连接到 server 的 IP:port
2. 连接成功 → 计数器增加
3. 连接失败 → 计数器增加失败
4. 达到 `rise` → server 标记 UP
5. 达到 `fall` → server 标记 DOWN

### **配置示例**

```cfg
backend pg_primary
    mode tcp
    option tcp-check
    default-server inter 3s rise 2 fall 3
    server pg1 127.0.0.1:5433 check
    server pg2 127.0.0.1:5432 check backup
```

| 参数                 | 说明                  |
| ------------------ | ------------------- |
| `option tcp-check` | 启用 TCP 健康检查         |
| `inter 3s`         | 每 3 秒执行一次检查         |
| `rise 2`           | 连续 2 次成功才标记 UP      |
| `fall 3`           | 连续 3 次失败才标记 DOWN    |
| `backup`           | 备份节点，只在主节点 DOWN 时使用 |

**特点**：

* 简单，性能开销小
* 只能判断端口可达性，无法判断业务逻辑

---

# **3️⃣ HTTP 健康检查**

### **原理**

* 在 **HTTP 层**发起请求（GET/HEAD/POST 等）
* 根据返回状态码判断 server 健康：

  * 2xx / 3xx → 健康
  * 4xx / 5xx → 不健康
* 支持检查特定 URI 或自定义头

**工作流程**：

1. HAProxy 发起 HTTP 请求到后端节点
2. 根据返回码判断成功/失败
3. 持续计数，根据 `rise/fall` 标记 UP/DOWN

### **配置示例**

```cfg
backend web_app
    mode http
    option httpchk GET /health
    default-server inter 5s rise 2 fall 3
    server s1 10.0.0.1:80 check
    server s2 10.0.0.2:80 check
```

| 参数                           | 说明                          |
| ---------------------------- | --------------------------- |
| `option httpchk GET /health` | 向 `/health` 发起 GET 请求作为健康检查 |
| `inter 5s`                   | 每 5 秒检查一次                   |
| `rise/fall`                  | 连续成功/失败次数判定节点状态             |
| `check`                      | 表示开启健康检查                    |

**特点**：

* 可以检查服务业务逻辑
* 可配置返回码、HTTP 方法、请求头
* 对微服务、HTTP API 很适用

---

# **4️⃣ External-check 健康检查**

### **原理**

* `external-check` 允许 HAProxy **调用外部脚本**判断节点健康
* 脚本返回 **exit code** 控制节点状态：

  * `0` → UP
  * 非 `0` → DOWN
* 可以实现 **复杂逻辑**，如数据库主备检测、应用健康检查

**工作流程**：

1. HAProxy 调用 `external-check command /path/to/script`
2. 脚本执行任意逻辑（TCP/HTTP/SQL/etc）
3. 脚本通过 `exit code` 返回结果
4. HAProxy 根据 `rise/fall/inter` 更新节点健康状态

### **配置示例**

```cfg
backend pg_primary
    mode tcp
    option external-check
    external-check command /etc/haproxy/check_pg_master.sh
    default-server inter 3s rise 2 fall 3
    server pg1 127.0.0.1:5433 check
    server pg2 127.0.0.1:5432 check backup
```

* `check_pg_master.sh` 脚本示例：

```bash
#!/bin/bash
HOST="${HAPROXY_SERVER_ADDR}"
PORT="${HAPROXY_SERVER_PORT}"
USER="monitor"
PASS="password"

STATUS=$(PGPASSWORD="$PASS" psql -qtAX -h "$HOST" -p "$PORT" -U "$USER" -d postgres \
        -c "SELECT pg_is_in_recovery();" 2>/dev/null)

if [[ "$STATUS" == "f" ]]; then
    exit 0   # 主库 UP
else
    exit 1   # 备库 DOWN
fi
```

**特点**：

* 灵活，可以检测数据库、应用、业务逻辑
* 支持复杂条件判断（如一主多备）
* 可通过环境变量获取 HAProxy server IP/端口

---

# **5️⃣ 健康检查参数汇总**

| 参数                      | 作用                   |
| ----------------------- | -------------------- |
| `check`                 | 启用健康检查               |
| `inter`                 | 检查间隔                 |
| `rise`                  | 连续成功次数判定 UP          |
| `fall`                  | 连续失败次数判定 DOWN        |
| `option tcp-check`      | TCP 健康检查             |
| `option httpchk`        | HTTP 健康检查            |
| `option external-check` | 外部脚本健康检查             |
| `backup`                | 备份节点，主节点 DOWN 才使用    |
| `port`                  | 覆盖 server 健康检查端口（可选） |

---

# **6️⃣ 健康检查流程总结**

## **TCP/HTTP 流程**

```
HAProxy ---> TCP/HTTP connect/request ---> server
       <--- TCP ACK / HTTP 2xx
         |
     判断成功/失败
         |
      rise/fall计数
         |
      更新server状态 UP/DOWN
```

## **External-check 流程**

```
HAProxy ---> execute script ---> 脚本逻辑
       <--- exit code (0=UP, !=0=DOWN)
         |
     rise/fall计数
         |
      更新server状态 UP/DOWN
```

---

# **7️⃣ 使用场景对比**

| 健康检查类型         | 场景             | 优缺点                 |
| -------------- | -------------- | ------------------- |
| TCP            | 数据库、Redis、简单服务 | 轻量、只检测端口连通性         |
| HTTP           | Web 服务、API     | 可检测业务逻辑，支持返回码、请求头   |
| external-check | 数据库主备、复杂逻辑     | 最灵活，可执行 SQL、命令或任意逻辑 |

---

✅ **总结**

* HAProxy 健康检查核心目标是 **保证流量只走健康节点**
* **TCP** → 端口可达性
* **HTTP** → 业务逻辑健康
* **external-check** → 自定义脚本逻辑（最灵活）
* `rise/fall/inter` + `backup` → 控制切换、主备流量分发

---

对于我们需要数据库双写来说，其实就是所有走到非主数据库的流量都要转到主库。
在健康检查里就是，只有主库才是up，备库都是down。

使用extern-check的配置示例如下：

```shell
global
    log stdout format raw local0
    maxconn 5000
    external-check  # 启用 external-check

defaults
    mode tcp
    timeout connect 5s
    timeout client  30s
    timeout server  30s

listen pg_write
    bind *:5000
    mode tcp
    option external-check
    external-check command /etc/haproxy/check_pg_master.sh

    # 定义默认 server 健康检查策略
    default-server inter 3s fall 3 rise 2 on-marked-down shutdown-sessions

    # PostgreSQL 节点
    server pg01 127.0.0.1:5432 check
    server pg02 127.0.0.1:5433 check

```

check_pg_master.sh的内容如下：

```shell
#!/bin/bash
# 检查当前节点是否为 PostgreSQL 主库
# 返回：
# 0 -> 主库 (UP)
# 1 -> 备库 (DOWN)

# 支持两种方式获取 server 地址：
# HAProxy >=2.4 可用参数传递 %s %p
HOST="${HAPROXY_SERVER_ADDR:-$1}"
PORT="${HAPROXY_SERVER_PORT:-$2}"
USER="repl"
PASS=""
export LD_LIBRARY_PATH=/var/postgres/lib

# 查询 PostgreSQL 节点角色
STATUS=$(PGPASSWORD="$PASS" /var/postgres/bin/psql -qtAX -h "$HOST" -p "$PORT" -U "$USER" -dpostgres \
        -c "SELECT pg_is_in_recovery();" 2>/tmp/connect.log)

echo "result is $?"
if [[ "$STATUS" == "f" ]]; then
    echo " - $HOST:$PORT is PRIMARY"
    exit 0   # 主库 -> HAProxy UP
else
    echo " - $HOST:$PORT is REPLICA"
    exit 1   # 备库 -> HAProxy DOWN
fi
```