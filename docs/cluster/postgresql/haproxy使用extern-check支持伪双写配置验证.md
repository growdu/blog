# haproxy使用extern-check支持伪双写配置验证

## 部署数据库

### 初始化主库

```shell
initdb -D data -A trust -Upostgres
```
将如下配置文件添加到postgresql.conf,

```shell
listen_addresses = '*'
port = 5432

# 复制设置
wal_level = replica
max_wal_senders = 10
wal_keep_size = 1GB
hot_standby = on
```
启动数据库：（如果是跨机器部署机器还需要修改pg_hba.conf）

```shell
pg_ctl -D data -l logfile start
```
## cloen备库

```shell
pg_basebackup -h localhost -p 5432 -D data1 -U repl -P -v -R -X stream -C -S standby1_slot
```
将如下配置文件添加到postgresql.conf,

```shell
port = 5433
hot_standby = on
hot_standby_feedback = on
max_standby_streaming_delay = 30s

# 禁止在备库上进行写操作
default_transaction_read_only = on

# 可选：报告为主库（用于监控）
hot_standby_feedback = on
```
拷贝过来的原来的主库配置要把它删除掉。

启动备库。

```shell
pg_ctl -D data1 -l logfile start
```
可以看到主库运行在5432端口，备库运行在5433端口，然后连接主库查看流复制关系。

```shell
psql -h 127.0.0.1 -p 5432 -U postgres
psql (15.12)
Type "help" for help.

postgres=# select pg_is_in_recovery();
 pg_is_in_recovery
-------------------
 f
(1 row)

postgres=# select * from pg_stat_replication;
   pid   | usesysid | usename | application_name | client_addr | client_hostname | client_port |         backend_start         | backend_xmin |   state   | sent_lsn  | write_lsn | flush_lsn |
replay_lsn | write_lag | flush_lag | replay_lag | sync_priority | sync_state |          reply_time
---------+----------+---------+------------------+-------------+-----------------+-------------+-------------------------------+--------------+-----------+-----------+-----------+-----------+-
-----------+-----------+-----------+------------+---------------+------------+-------------------------------
 1203834 |    16384 | repl    | walreceiver      | 127.0.0.1   |                 |       48076 | 2026-01-15 08:05:52.885746+00 |              | streaming | 0/7000290 | 0/7000290 | 0/7000290 |
0/7000290  |           |           |            |             0 | async      | 2026-01-15 11:53:44.016787+00
(1 row)

postgres=# \q
root@linux-kernel-test:~# psql -h 127.0.0.1 -p 5433 -U postgres
psql (15.12)
Type "help" for help.

postgres=# select pg_is_in_recovery();
 pg_is_in_recovery
-------------------
 t
(1 row)

postgres=#
```
到这里主备集群就搭建好了。

## haproxy

```shell
apt install haproxy
```
或者从源码下载编译。https://github.com/haproxy/haproxy

采用extern-check方式来探测主库，探测脚本check_pg_master.sh的内容如下：

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
DB="postgres"
export LD_LIBRARY_PATH=/var/postgres/lib

# 查询 PostgreSQL 节点角色
STATUS=$(PGPASSWORD="$PASS" /var/postgres/bin/psql -qtAX -h "$HOST" -p "$PORT" -U "$USER" -d${DB} \
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
haproxy的配置如下：

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
使用如下命令启动haproxy，

```shell
systemctl start haproxy
```
## 验证代理是否生效

- 代理运行在5000端口，将流量转发到主库
- 127.0.0.1:5432是主库
- 127.0.0.1:5432是备库

```shell
psql -h 127.0.0.1 -p 5000 -U postgres
psql (15.12)
Type "help" for help.

postgres=# select pg_is_in_recovery();
 pg_is_in_recovery
-------------------
 f
(1 row)
```
修改haproxy的配置，变更pg1和pg2的位置，继续使用上面的连接串连接数据库，依然能连接到主库。