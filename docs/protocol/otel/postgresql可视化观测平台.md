# postgresql 可视化观测平台

使用 `OpenTelemetry` 实现 `Trace + Metrics + Logs → Tempo + Prometheus + Loki → Grafana`的全链路可观测平台。

采用如下技术架构来采集观测：

```shell
          +----------------+
          |  PostgreSQL /  |
          |  Rust App      |
          +----------------+
                   |
        OpenTelemetry SDK / Collector
                   |
    -----------------------------------------
    |                  |                   |
Metrics → Prometheus   Trace → Tempo     Logs → Loki
    |                  |                   |
   Grafana ---------- Dashboard / Explore / Alerts
```
- Trace 可以展示 SQL 执行时间线
- Metrics 可以展示系统实时状态和趋势
- Logs 可以追溯慢 SQL 原文、错误、内存/IO峰值

基于rust可以使用如下方式实现：

```shell
          +-------------------+
          | PostgreSQL Server |
          +-------------------+
                    |
               eBPF probes
                    |
       +---------------------------+
       | Rust eBPF Collector (Aya) |
       +---------------------------+
                    |
   --------------------------------------
   |                 |                  |
Metrics → Prometheus  Trace → Tempo    Logs → Loki
                    |                  |
                    +------------------+
                           Grafana
```
## 核心逻辑

1. PostgreSQL：数据库执行 SQL 查询、产生内部调用。

2. eBPF (Aya)：在内核或 PostgreSQL 用户态 attach probe，采集：

- SQL 执行开始/结束事件
- 内存分配/释放
- CPU/锁/IO事件
- 关键函数调用路径

3.Rust Collector：将 eBPF 收集的数据进行处理：

- 构造 Trace Span（SQL 执行调用链）
- 生成 Metrics（执行时间、CPU、内存、IO）
- 生成结构化日志（慢 SQL、异常）
- 输出到 OpenTelemetry Collector（OTLP/gRPC）

4.OpenTelemetry Collector：

- Metrics → Prometheus
- Trace → Tempo
- Logs → Loki

5.Grafana：

- Metrics Dashboard（查询耗时、CPU/IO/内存使用）
- Trace View（SQL 执行路径）
- Logs Explore（慢 SQL 原文、异常日志）
- Trace ↔ Logs 联动（通过 trace_id）

## 开源实现coroot

Coroot 是“分析层 + 采集层”的组合。

```shell
                ┌──────────────┐
                │    Coroot     │   ←—— 分析 & UI
                │  (Server/UI)  │
                └──────┬───────┘
                       │ Prometheus API / HTTP scrape
        ┌──────────────┼───────────────┐
        │              │               │
  node-agent       pg-agent        其他 exporters
(eBPF + 主机监控) (Postgres)       (Redis / Nginx / JVM …)
```
- Agent 负责采集
- Coroot 负责聚合 → 关联拓扑 → 根因分析（RCA） → 展示

### coroot组件

#### coroot server

- 拓扑构建（自动识别服务依赖）
- RCA（根因分析）
- SLO 与可用性分析
- 警报推理（避免“告警风暴”）
- UI 仪表盘

coroot的数据来源：

- 直接抓取 Agents
- 读取现有 Prometheus
- 读取 tracing / logging 后端（可选）

#### Node Agent（coroot-agent / node-agent）

- CPU / 内存 / 磁盘 / IO
- 宿主机进程关系
- Kubernetes pod → 容器 → 进程 映射
- eBPF：网络、依赖调用、延迟、丢包、重传

通信方式：

- 本地 HTTP /metrics（Prometheus 格式）
- 被 Coroot 或 Prometheus 拉取（pull）

#### PostgreSQL Agent（coroot-pg-agent）

- pg_stat_statements
- 锁等待
- 慢查询
- WAL / 复制延迟
- autovacuum
- checkpoint 行为

```shell
客户端 → 应用 → PostgreSQL
             │
             ▼
      pg-agent采集内部指标
             │
             ▼
      node-agent观察系统+网络(eBPF)
             │
             ▼
         Coroot 拉取数据
             │
             ▼
    1. 自动识别拓扑
    2. 相关性分析
    3. 判断链路瓶颈
    4. 输出 RCA（根因）

```