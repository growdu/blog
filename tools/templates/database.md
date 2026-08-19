---
title: 数据库专题
date: 2026-07-29 00:00:00
type: "database"
layout: "page"
---

# 数据库专题

> 数据库内核是计算机系统软件中最复杂的领域之一。本专题收录我在 PostgreSQL / openGauss 内核开发、分布式一致性（Raft / DCF）、逻辑解码与双向同步、存储引擎等方向的实战笔记与源码解读，希望对同样走在这条路上的同行有所启发。

作为长期在 PostgreSQL 与 openGauss 内核一线搬砖的工程师，我日常的工作内容大致涵盖：**内核源码阅读与 Bug 定位**、**新特性设计（如 DDL-Replay 双向同步）**、**分布式一致性模块开发（DCF / Raft）**、**性能调优与故障排查**。下面把博客里相关的文章按主题串成一张导览图，方便按需取用。

## PostgreSQL 源码修炼之路

本页自动汇总“数据库”与“PostgreSQL 源码修炼之路”分类下的全部文章，并按去重后的日期倒序排列。后续新增章节时，只需在目录的 `cascade.categories` 中加入“数据库”，无需再手工维护本页链接。

<!-- DATABASE_POSTS_START -->
<!-- DATABASE_POSTS_END -->

## 核心技术栈

<div class="db-skill-grid">
  <div class="db-skill-card">
    <div class="db-skill-name">PostgreSQL 内核</div>
    <div class="db-skill-bar"><div class="db-skill-fill" style="width:95%"></div></div>
    <div class="db-skill-meta">进程模型 · 存储引擎 · WAL · 复制 · 执行器 · MVCC</div>
  </div>
  <div class="db-skill-card">
    <div class="db-skill-name">openGauss / DCF</div>
    <div class="db-skill-bar"><div class="db-skill-fill" style="width:90%"></div></div>
    <div class="db-skill-meta">分布式一致性 · 日志复制 · 投票机制 · 网络模块</div>
  </div>
  <div class="db-skill-card">
    <div class="db-skill-name">分布式协议</div>
    <div class="db-skill-bar"><div class="db-skill-fill" style="width:88%"></div></div>
    <div class="db-skill-meta">Raft · 多数派 · Quorum 动态调整 · Leader 选举</div>
  </div>
  <div class="db-skill-card">
    <div class="db-skill-name">逻辑解码与双向同步</div>
    <div class="db-skill-bar"><div class="db-skill-fill" style="width:85%"></div></div>
    <div class="db-skill-meta">pgoutput · pglogical · DDL-Replay · 跨版本迁移</div>
  </div>
  <div class="db-skill-card">
    <div class="db-skill-name">多数据库架构对比</div>
    <div class="db-skill-bar"><div class="db-skill-fill" style="width:80%"></div></div>
    <div class="db-skill-meta">PostgreSQL / MySQL / SQLServer / TDengine 横向评测</div>
  </div>
  <div class="db-skill-card">
    <div class="db-skill-name">性能调优与故障排查</div>
    <div class="db-skill-bar"><div class="db-skill-fill" style="width:85%"></div></div>
    <div class="db-skill-meta">Checkpoint · WAL · 锁等待 · 慢 SQL · 崩溃恢复</div>
  </div>
</div>

## 学习路径建议

如果你刚接触数据库内核开发，建议按下面这条路线循序渐进，每一档都附上对应的站内文章入口：

1. **入门**：[PostgreSQL 基操](/categories/PostgreSQL/) → [源码编译](/2023/09/14/pgsql/postgresql源码编译/) → [启动流程](/2023/05/17/pgsql/postgresql启动流程/)。先把一份能跑、能断点的内核源码环境搭起来。
2. **存储与 WAL**：[FSM 文件解析](/2024/02/21/pgsql/storage/PosgreSQL%20FSM%E6%96%87%E4%BB%B6%E8%A7%A3%E6%9E%90%20%E2%80%93%20%E8%9B%8B%E6%8C%9E/) → [full_page_writes](/2022/06/13/pgsql/storage/full_page_writes/) → [WAL 机制浅析](/2023/05/17/pgsql/wal机制浅析/) → [崩溃恢复](/2023/05/17/pgsql/数据库崩溃恢复/)。理解"数据页 + WAL + 检查点"这一数据库的基石三角。
3. **进程与执行器**：[BgWriter](/2022/04/22/pgsql/process/BgWriter/) → [Checkpoint](/2022/04/25/pgsql/process/Checkpoint/) → [WalWriter](/2022/04/22/pgsql/process/WalWriter/) → [insert 语句执行过程](/2023/05/17/pgsql/executor/PostgreSQL%E7%9A%84insert%E8%AF%AD%E5%8F%A5%E6%89%A7%E8%A1%8C%E8%BF%87%E7%A8%8B%E5%88%86%E6%9E%90%20-%20%E5%A2%A8%E5%A4%A9%E8%BD%AE/)。把后台进程和查询执行的主干打通。
4. **复制与高可用**：[流复制与 WAL 日志](/2024/02/06/pgsql/postgresql%E2%80%94%E2%80%94%E6%B5%81%E5%A4%8D%E5%88%B6%E5%92%8Cwal%E6%97%A5%E5%BF%97%EF%BC%88%E5%85%AB%EF%BC%89/) → [同步流复制原理](/2023/05/17/pgsql/replication/PostgreSQL%20%E5%90%8C%E6%AD%A5%E6%B5%81%E5%A4%8D%E5%88%B6%E5%8E%9F%E7%90%86%E5%92%8C%E4%BB%A3%E7%A0%81%E6%B5%85%E6%9E%90-%E9%98%BF%E9%87%8C%E4%BA%91%E5%BC%80%E5%8F%91%E8%80%85%E7%A4%BE%E5%8C%BA/) → [WalReceiver / WalSender 交互](/2023/05/17/pgsql/replication/PostgreSQL%E6%95%B0%E6%8D%AE%E5%BA%93%E5%A4%8D%E5%88%B6%E2%80%94%E2%80%94%E5%90%8E%E5%8F%B0%E4%B8%80%E7%AD%89%E5%85%AC%E6%B0%91%E8%BF%9B%E7%A8%8BWalReceiver&startup%E4%BA%A4%E4%BA%92_postgressql%20walreceive%E7%BA%BF%E7%A8%8B_%E8%82%A5%E5%8F%94%E8%8F%8C%E7%9A%84%E5%8D%9A%E5%AE%A2-CSDN%E5%8D%9A%E5%AE%A2/) → [repmgr 实现原理](/2024/02/19/pgsql/ha/repmgr实现原理/) → [伪双写](/2026/01/15/cluster/postgresql/postgresql伪双写/)。
5. **事务与并发控制**：[事务管理](/2026/03/03/cluster/postgresql/事务管理/) → [并发控制](/2022/04/13/pgsql/pgsql_main_structure/) → [MVCC 源码解读](/2022/04/13/pgsql/pgsql_main_structure/) → [锁等待排查](/2022/04/13/pgsql/pgsql_main_structure/)。
6. **逻辑解码与双向同步**：[逻辑复制源码分析](/2026/04/14/db/logical_decode/逻辑复制源码分析/) → [PG15 逻辑复制支持 DDL](/2026/03/11/db/logical_decode/pg15逻辑复制支持DDL/) → [pglogical 详解](/2026/03/06/db/logical_decode/pglogical详解/) → [DDL-Replay 框架设计](/2026/07/27/db/logical_decode/逻辑解码DDL-Replay框架设计/) → [AI 逻辑解码](/2026/03/06/db/logical_decode/ai逻辑解码/)。
7. **分布式一致性**：[Raft 重要概念](/2023/05/17/cluster/raft/raft重要概念/) → [一文读懂 openGauss DCF 网络模块](/2023/05/26/cluster/DCF/一文读懂openguass%20dcf网络模块/) → [DCF 投票系统详解](/2023/05/22/cluster/DCF/dcf投票系统详解/) → [DCF 运行机制](/2023/12/23/cluster/DCF/dcf运行机制/) → [DCF 写入机制](/2023/05/22/cluster/DCF/dcf写入机制/) → [Raft 协议动态调整 quorum](/2022/10/25/cluster/raft/raft协议动态调整quorum/)。

## 专题导览

### PostgreSQL 内核

PostgreSQL 是研究数据库内核最好的教科书。本节文章覆盖源码结构、进程模型、执行器、统计信息、对象管理等。

- [PostgreSQL 主结构](/2022/04/13/pgsql/pgsql_main_structure/) — 一张图看懂内核子目录划分与启动链路。
- [postmaster 启动代码解析（--boot / --single）](/2023/06/25/pgsql/Postgres%E4%B8%ADpostmaster%E4%BB%A3%E7%A0%81%E8%A7%A3%E6%9E%90%28--boot%E5%92%8C--single%29/) — 两个特殊启动模式的差异与适用场景。
- [PostgreSQL 时间线解析](/2023/07/21/pgsql/PostgreSQL%20时间线解析/) — 时间线（Timeline）在 PITR 与复制里的关键作用。

### 存储引擎与 WAL

数据页、WAL、检查点是数据库可靠性的三角。

- [PostgreSQL 存储、索引及系统优化、主备切换](/2024/02/23/pgsql/replication/Postgresql存储、索引及系统优化、主备切换/) — 系统性梳理物理存储与优化。
- [WAL 机制浅析](/2023/05/17/pgsql/wal机制浅析/) — 写前日志的写入路径与刷盘策略。
- [full_page_writes](/2022/06/13/pgsql/storage/full_page_writes/) — 部分写保护为何是数据一致性的最后一道防线。
- [崩溃恢复](/2023/05/17/pgsql/数据库崩溃恢复/) — 从 REDO / UNDO 到多版本可见性的恢复链路。
- [Checkpoint 源码](/2022/04/25/pgsql/process/Checkpoint/) — 检查点触发的代码路径。
- [bgwriter 与 walwriter](/2022/04/22/pgsql/process/BgWriter/) — 后台刷盘进程协同。

### 复制与高可用

复制是数据库走向生产的关键能力。

- [流复制与 WAL 日志](/2024/02/06/pgsql/postgresql%E2%80%94%E2%80%94%E6%B5%81%E5%A4%8D%E5%88%B6%E5%92%8Cwal%E6%97%A5%E5%BF%97%EF%BC%88%E5%85%AB%EF%BC%89/) — 物理复制的原理与配置。
- [同步流复制原理](/2023/05/17/pgsql/replication/PostgreSQL%20%E5%90%8C%E6%AD%A5%E6%B5%81%E5%A4%8D%E5%88%B6%E5%8E%9F%E7%90%86%E5%92%8C%E4%BB%A3%E7%A0%81%E6%B5%85%E6%9E%90-%E9%98%BF%E9%87%8C%E4%BA%91%E5%BC%80%E5%8F%91%E8%80%85%E7%A4%BE%E5%8C%BA/) — 同步复制的等待与反馈机制。
- [WalReceiver / WalSender 交互](/2023/05/17/pgsql/replication/PostgreSQL%E6%95%B0%E6%8D%AE%E5%BA%93%E5%A4%8D%E5%88%B6%E2%80%94%E2%80%94%E5%90%8E%E5%8F%B0%E4%B8%80%E7%AD%89%E5%85%AC%E6%B0%91%E8%BF%9B%E7%A8%8BWalReceiver&startup%E4%BA%A4%E4%BA%92_postgressql%20walreceive%E7%BA%BF%E7%A8%8B_%E8%82%A5%E5%8F%94%E8%8F%8C%E7%9A%84%E5%8D%9A%E5%AE%A2-CSDN%E5%8D%9A%E5%AE%A2/) — 备库回放链路。
- [逻辑复制源码分析](/2026/04/14/db/logical_decode/逻辑复制源码分析/) — publisher / subscriber 模型。
- [repmgr 实现原理](/2024/02/19/pgsql/ha/repmgr实现原理/) — 复制管理与自动 failover。
- [HAProxy + PGBouncer](/2026/01/15/cluster/postgresql/haproxy支持postgresql伪双写/) — 连接池与负载均衡。

### 逻辑解码与双向同步

这是近几年 PostgreSQL 社区最活跃的方向。

- [逻辑解码 DDL-Replay 框架设计](/2026/07/27/db/logical_decode/逻辑解码DDL-Replay框架设计/) — 自研框架支持 DDL 复制。
- [PG15 逻辑复制支持 DDL](/2026/03/11/db/logical_decode/pg15逻辑复制支持DDL/) — 上游方案。
- [pglogical 详解](/2026/03/06/db/logical_decode/pglogical详解/) — 二进制协议扩展。
- [逻辑复制支持系统表同步概要设计](/2026/04/14/db/logical_decode/逻辑复制源码分析/) — 自研系统的总体思路。
- [pglogical 支持 DDL 搭建教程](/2026/03/11/db/logical_decode/pglogical支持DDL搭建教程/) — 实战步骤。
- [AI 逻辑解码](/2026/03/06/db/logical_decode/ai逻辑解码/) — AI 辅助的逻辑解码工具。
- [Babelfish 内核执行上下文](/2026/07/03/db/logical_decode/%E9%80%BB%E8%BE%91%E8%A7%A3%E7%A0%81ddl%20replay%E6%94%AF%E6%8C%81sqlserver%E6%A8%A1%E5%BC%8F/) — SQL Server 兼容层。

### 分布式协议（Raft / 一致性）

分布式一致性是数据库从单机走向分布式的灵魂。

- [Raft 重要概念](/2023/05/17/cluster/raft/raft重要概念/) — Leader / Follower / Candidate 与 Term。
- [Raft 协议动态调整 quorum](/2022/10/25/cluster/raft/raft协议动态调整quorum/) — 业务驱动的多数派动态变更方案。
- [C-Raft 分布式存储方案](/2022/10/25/cluster/raft/c-raft分布式存储方案/) — 用 C 语言实现的轻量 Raft 库。

### 多数据库对比与选型

- [PostgreSQL](/categories/PostgreSQL/) — 强事务、丰富生态、可扩展性极强的"瑞士军刀"。
- [MySQL](/categories/MySQL/) — 互联网时代的事实标准，分库分表套路成熟。
- [SQLServer](/categories/SQLServer/) — 企业级特性的集大成者，与 .NET 生态深度绑定。
- [TDengine](/categories/TDengine/) — 面向 IoT 的时序数据库，存储压缩比惊人。
- [PolarDB 竞争力分析](/categories/数据库深入/) — 云原生分布式数据库的工程亮点。

### 性能调优与故障排查

- [Checkpointer 机制浅析](/2022/04/25/pgsql/process/Checkpoint/) — 检查点触发时机与刷盘策略。
- [WAL Writer](/2022/04/22/pgsql/process/WalWriter/) — 异步刷盘的延迟与吞吐平衡。
- [统计信息采样](/2022/10/25/pgsql/stats/stats/) — ANALYZE 频率与规划器稳定性的关系。
- [PG 复制 keepalive](/2022/05/23/pgsql/replication/pg_replication_keepalive/) — 跨地域复制的网络参数调优。
- [PG IO 调优](/2022/04/25/pgsql/pg_io_调优/) — shared_buffers / wal_buffers / effective_cache_size 的取舍。
- [HA 元信息常见存储方式](/2026/07/03/db/logical_decode/%E9%80%BB%E8%BE%91%E8%A7%A3%E7%A0%81ddl%20replay%E6%94%AF%E6%8C%81sqlserver%E6%A8%A1%E5%BC%8F/) — etcd / 自建表 / 文件系统的权衡。
- [code-server 调试 PostgreSQL](/2024/07/04/pgsql/debug/code-server调试postgresql/) — 云端断点调试 PostgreSQL 的工程实践。

## 实战经验沉淀

- **内核 Bug 定位**：熟悉 gdb / perf / bpftrace 的组合用法，能从 panic 日志反推到具体的代码行。
- **性能优化**：在 openGauss 内核侧主导过 WAL 写入路径优化、复制槽回收策略改造等专项，单节点写入吞吐有数倍提升。
- **架构设计**：完整设计过一套基于 DCF 的两地三中心高可用方案，覆盖网络分区、脑裂、自动切换、降级运行等场景。

## 推荐阅读顺序

如果你只想读 5 篇文章理解数据库内核的脉络，我会推荐：

1. [PostgreSQL 主结构](/2022/04/13/pgsql/pgsql_main_structure/)
2. [WAL 机制浅析](/2023/05/17/pgsql/wal机制浅析/)
3. [PostgreSQL 流复制与 WAL 日志](/2024/02/06/pgsql/postgresql%E2%80%94%E2%80%94%E6%B5%81%E5%A4%8D%E5%88%B6%E5%92%8Cwal%E6%97%A5%E5%BF%97%EF%BC%88%E5%85%AB%EF%BC%89/)
4. [一文读懂 openGauss DCF 网络模块](/2023/05/26/cluster/DCF/一文读懂openguass%20dcf网络模块/)
5. [逻辑解码 DDL-Replay 框架设计](/2026/07/27/db/logical_decode/逻辑解码DDL-Replay框架设计/)

这五篇涵盖了存储、复制、分布式一致性与逻辑同步四条主线，足以勾勒出数据库内核的整体图景。

## 写在最后

数据库内核开发是一个"慢就是快"的领域：每一次对一行代码的深入理解，最终都会在某个深夜的故障排查里兑现回报。本专题会持续更新，把每一段新的源码阅读笔记、每一次新的故障复盘都沉淀下来。也欢迎通过 [GitHub](https://github.com/growdu) 与我交流。
