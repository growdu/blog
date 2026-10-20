---
title: "PostgreSQL 源码修炼之路:内核深度拆解专题"
date: 2026-10-23 09:00:00
categories:
  - 数据库
  - PostgreSQL
tags:
  - PostgreSQL
  - 源码分析
  - 内核
  - 逻辑复制
---

# PostgreSQL 源码修炼之路:内核深度拆解专题

> 本目录是 [PostgreSQL 源码修炼之路 — 存储引擎内核开发者的进阶地图](./learning-path/index.html) 的**专题补充**。
> 配套源码全部基于 PostgreSQL 18 仓库 `~/cwork/postgresql`(`src/backend/{replication/logical,utils/cache,access/heap,access/transam}`)。
> 每篇都带 **文件:行号** 标注,**多张 mermaid 图(架构 / 时序 / 流程 / 状态机)**,以及可直接复现的 GDB 路径 / 输出示例。

## 一、本目录文章总览(按主题分组)

### 1. 逻辑复制 — 入口与全链路(6 篇)

| 文章 | 切入点 |
|---|---|
| [PostgreSQL 18 CREATE_REPLICATION_SLOT 全链路分析](./postgresql-create-replication-slot-deep-dive/index.html) | `CREATE_REPLICATION_SLOT` SQL → `SnapBuild` 状态机的完整路径 |
| [PostgreSQL 逻辑复制端到端深度拆解](./postgresql-logical-replication-end-to-end/index.html) | WAL 字节 → 订阅者落盘的 9 段链路全景 |
| [PostgreSQL 逻辑复制 LSN 推进全景](./postgresql-logical-replication-lsn-flow/index.html) | LSN 在 copy/snapshot/apply 三处的轮转 |
| [PostgreSQL 逻辑复制:catalog 改动、可见性判定与 xmin/xmax 推进全景](./postgresql-logical-replication-catalog-visibility/index.html) | **catalog 改动如何透传到 HVMCC 可见性判决**(NEW_CID 全链路) |
| [PostgreSQL 18 流式逻辑复制发布端深度解析](./postgresql-logical-replication-stream-publisher/index.html) | `logical_decoding_work_mem` → `stream_commit` 完整链路 |
| [PostgreSQL 逻辑复制性能分析:火焰图实战](./postgresql-flame-graph/index.html) | perf + 火焰图对解码路径的性能定位 |

### 2. 逻辑复制 — SnapBuild / ReorderBuffer 子系统源码拆解(6 篇)

| 文章 | 切入点 |
|---|---|
| [PostgreSQL snapbuild.c 深度解析](./postgresql-snapbuild-deep-dive/index.html) | snapbuild.c 2076 行全栈拆解,状态机 + 函数集 |
| [PostgreSQL SnapBuildFindSnapshot 深度拆解](./postgresql-snapbuild-find-snapshot-deep-dive/index.html) | 6 状态机的每条状态转换路径,带具体 WAL 与前提条件 |
| [reorderbuffer.c 源码深度解析](./postgresql-reorder-buffer-code-analysis/index.html) | reorderbuffer.c 5615 行架构综述(生命周期 / 内存管理 / streaming) |
| [PostgreSQL reorderbuffer.c 函数级源码全集](./postgresql-reorderbuffer-c-function-reference/index.html) | **95 个函数逐函数源码级拆解**(5615 行 / 2494 行解读) |
| [PostgreSQL 逻辑复制 spill 与 streaming 实战](./postgresql-logical-replication-streaming-spill/index.html) | spill 文件 `/pg_replication_slot/<slot>/xid-*.txn` 真实分析 |
| [PostgreSQL 逻辑复制 spill 文件深度剖析:TPC-C 100WH](./postgresql-logical-replication-spill-deep-dive/index.html) | 大量生成 spill 的根因与治理建议 |

### 4. 逻辑复制 — Apply / 并行 Apply(5 篇)

| 文章 | 切入点 |
|---|---|
| [PostgreSQL 逻辑复制 Apply Parallel Worker 运行机制](./postgresql-apply-parallel-worker/index.html) | 进程拓扑 / leader-worker 协议 |
| [applyparallelworker.c 源码深度解析](./postgresql-apply-parallel-worker-code-analysis/index.html) | 1646 行 applyparallelworker.c 全栈 |
| [applyparallelworker.c 之 LA 端源码深度解析](./postgresql-apply-leader-worker-code-analysis/index.html) | Leader Apply Worker 的指挥中枢 |
| [Apply Parallel Worker 的 lock_stream 与 unlock_stream](./postgresql-apply-parallel-lock-stream/index.html) | "获得就释放"的死锁防护机制 |
| [PostgreSQL 逻辑复制 Apply Parallel Worker 参数调优实战](./postgresql-logical-replication-apply-parallel-tuning/index.html) | GUC 与 apply 性能关系 |

### 6. 逻辑复制 — 性能 / 调优(2 篇)

| 文章 | 切入点 |
|---|---|
| [PostgreSQL 逻辑复制性能与速率测试](./postgresql-logical-replication-throughput-benchmark/index.html) | 测量模型 + 11 个 SQL/Shell 脚本 |
| [PostgreSQL 逻辑复制性能测试总结](./%E9%80%BB%E8%BE%91%E5%A4%8D%E5%88%B6%E6%80%A7%E8%83%BD%E6%B5%8B%E8%AF%95/index.html) | 公开数据的对比 |

### 7. 内核子系统 — 缓存 / 锁 / 共享内存(3 篇)

| 文章 | 切入点 |
|---|---|
| [PostgreSQL syscache 模块源码深度拆解](./postgresql-syscache-deep-dive/index.html) | CatCache / LRU 哈希 / cache invalidation 全链路 |
| [PostgreSQL 行锁机制深度解析](./postgresql-row-lock/index.html) | MVCC → 多级锁 → 多事务 |
| [PostgreSQL 共享内存机制](./postgresql-shared-memory/index.html) | DSM/DSA、固定 MemoryContext 用法 |

### 8. 内核开发实战 — Injection Point / GUC / 调试(4 篇)

| 文章 | 切入点 |
|---|---|
| [PostgreSQL 18 Injection Point 完整指南](./postgresql-injection-points/index.html) | 原理 / API / 实战 |
| [Injection Point 与 PG 测试框架集成](./postgresql-injection-points-test-framework/index.html) | Makefile → .spec 完整链路 |
| [用 Injection Point 测试无法到达的代码路径](./postgresql-injection-points-test-unreachable/index.html) | 3 种改造模式 |
| [PostgreSQL 18 新增一个 GUC 参数](./postgresql-logical-replication-add-guc/index.html) | 内核开发者视角的完整流程 |

### 9. 社区资源与社区精华(2 篇)

| 文章 | 切入点 |
|---|---|
| [PostgreSQL 社区精髓资源汇总](./postgresql-community-gems/index.html) | 官方文档 → 内核贡献者博客的"一键直达"清单 |
| [pgsql-hackers 并行 apply 讨论集](./pgsql-hackers-parallel-apply-discussion/index.html) | 邮件列表核心讨论整理 |

### 11. 学习路径

- [PostgreSQL 源码修炼之路 — 存储引擎内核开发者的进阶地图](./learning-path/index.html) — 主线 14 章框架,与本文档互补

### 12. 杂项 / 工具

| 文章 | 切入点 |
|---|---|
| [使用 meson 编译 PostgreSQL](./%E4%BD%BF%E7%94%A8meson%E7%BC%96%E8%AF%91pg/index.html) | meson build 实战 |
| [PostgreSQL 常用函数速查](./pg%E5%B8%B8%E7%94%A8%E5%87%BD%E6%95%B0/index.html) | 系统表 / 函数 / 视图 |
| [PostgreSQL 部分专题(Part 1)](./part1/index.html) | 早期草稿合集 |

## 二、阅读顺序建议

```
入门  → [01 PostgreSQL 源码修炼之路](./learning-path/index.html)
         ↓
主线  → 逻辑复制端到端(end-to-end)
         ↓
拆解  → CREATE_REPLICATION_SLOT → snapbuild.c → reorderbuffer.c
         ↓
深入  → catalog 可见性 / NewCID / HVMCC
         ↓
延伸  → apply worker / parallel apply / streaming / spill
         ↓
旁支  → syscache / row-lock / 共享内存
         ↓
实战  → Injection Point / GUC 添加 / 火焰图
```

## 三、与 `docs/database/` 的关系

- **本目录(`docs/db/postgresql/`)**:聚焦 PostgreSQL 18 源码级深拆,**逐函数 / 逐行号**
- **`docs/database/postgresql-*`**([入口](/database/)):覆盖 PostgreSQL 主题更广(历史、MVCC、模块架构、对比、扩展、监控等)

二者互补:
- 想了解 *某个子系统怎么实现* → 看本目录
- 想了解 *PostgreSQL 整体生态 / 主题入门 / 监控* → 看 `docs/database/`

## 四、与其他数据库专题的连接

| 主题 | 路径 |
|---|---|
| openGauss CSN 全序保证 | [docs/db/opengauss-csn-total-ordering](../opengauss-csn-total-ordering/index.html) |
| openGauss 并行解码 | [docs/db/opengauss-parallel-decoding-design](../opengauss-parallel-decoding-design/index.html) |
| 逻辑解码完整目录 | [docs/db/logical_decode](../logical_decode/index.html) |
| openGauss 部署 / 架构 | [docs/openguass](../../openguass/index.html) |
