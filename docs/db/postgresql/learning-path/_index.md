---
title: "PostgreSQL 源码修炼之路"
cascade:
  categories:
    - 数据库
    - PostgreSQL 源码修炼之路
  tags:
    - 数据库
    - PostgreSQL 源码修炼之路
---

# PostgreSQL 源码修炼之路——存储引擎内核开发者的进阶地图

> 适用对象：希望成长为 **资深 PostgreSQL 存储引擎 / 内核开发工程师** 的人。
> 配套源码：`~/cwork/postgresql`（PostgreSQL 18.3，含 AIO、WAL summarizer 等新设施）。
> 阅读约定：文中所有 `文件路径:行号` 形式都对应上述源码树。

## 为什么是这条路线

PostgreSQL 的内核不是"一个"模块，而是由 **进程模型 → 查询管线 → 存储抽象 → 缓冲管理 → 访问方法 → 事务/锁 → WAL/恢复** 七层正交子系统叠起来的"洋葱"。任何一个看似简单的 SQL 行为（比如 `UPDATE ... WHERE`），其执行轨迹都会穿过 7–8 层代码。如果按 SQL 用法去学，永远停在表面；**只有按子系统纵切，才能真正掌握内核**。

本系列刻意 **避开**：
- "SQL 教程"层面的内容（`SELECT/INSERT` 怎么用）
- PG 周边生态工具（pgAdmin、psycopg2、逻辑复制槽）
- contrib 模块的逐个 API 罗列

**专注**：
- 一个子系统内部的数据结构、关键函数、调用链
- "为什么这么设计" 与 "其它数据库（InnoDB、RocksDB、TiKV）怎么做" 的对照
- 用 GDB 实测验证假设的练习

## 能力分层

把"资深存储引擎内核开发"拆成 4 阶。每阶对应本系列中的一批章节：

| 阶段 | 能力关键词 | 对应章节 | 验收标准 |
| --- | --- | --- | --- |
| **L1 入门** | 能编译、能 GDB、能跟踪一条 SQL | 01, 02, 03 | 能在 GDB 里打断点，跟踪 `SELECT * FROM t WHERE id=1` 的完整调用栈 |
| **L2 存储基线** | 理解页面、缓冲、可见性 | 04, 05, 06 | 能解释一条 `UPDATE` 后页面与 WAL 的字节级变化 |
| **L3 索引与并发** | 能读 / 改 B-Tree、懂锁与隔离 | 07, 08 | 能解释 `READ COMMITTED` 下 `UPDATE` 与 `SELECT FOR UPDATE` 的死锁路径 |
| **L4 恢复与进阶** | 能 redo、能分析 checkpoint、设计特性 | 09, 10, 11, 12, 13, 14 | 能分析 PITR 流程、设计 replication slot、写一个 mini FDW |

## 阅读顺序建议

```
01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11 → 12 → 13 → 14
```

但如果你已是其它 DBMS（InnoDB / RocksDB / LevelDB）的内核熟手，可跳读：
- 熟悉 InnoDB → 直接看 **06, 08, 09, 11, 12**（重点对照 redo/undo/binlog 差异）
- 熟悉 LSM → 看 **04, 09, 11**（重点对照"覆盖写 vs 追加写"与 checkpoint 模型）
- 写过 Linux 内核 / 文件系统 → 直接看 **05**（重点看 AIO 与 buffer 替换策略）
- 搞过大数据 / 数仓 → 直接看 **14**（重点看 cstore_fdw / parquet_fdw 设计与 FDW 框架）

## 章节索引

### 第一部分：环境与全景

- [01 编译调试与代码布局](./01-build-and-codebase.md)
- [02 进程架构与生命周期](./02-process-architecture.md)
- [03 查询管线全景](./03-query-pipeline.md)

### 第二部分：存储引擎基线（L2 存储基线）

- [04 存储抽象层 SMGR](./04-storage-abstraction.md)
- [05 缓冲区管理](./05-buffer-manager.md)
- [06 堆表与 MVCC](./06-heap-and-mvcc.md)

### 第三部分：索引与并发（L3）

- [07 B-Tree 索引](./07-btree-index.md)
- [08 事务、锁与并发](./08-locks-and-concurrency.md)

### 第四部分：恢复、复制与扩展（L4）

- [09 WAL 与恢复](./09-wal-and-recovery.md)
- [10 进阶特性](./10-advanced-topics.md)
- [11 崩溃恢复深入](./11-crash-recovery.md)
- [12 物理复制深入](./12-physical-replication.md)
- [13 逻辑复制深入](./13-logical-replication.md)
- [14 列存与 cstore_fdw](./14-column-store.md)

## 章节速查表（按主题）

| 主题 | 主章节 | 进阶深度章节 |
| --- | --- | --- |
| 编译 / GDB | 01 | — |
| 进程架构 | 02 | — |
| 查询管线 | 03 | — |
| 存储抽象 SMGR | 04 | 4.11–4.17（checksum / segment / tablespace / fd pool） |
| 缓冲管理 | 05 | 5.12–5.21（hash / pin / content_lock / clock-sweep / AIO / bgwriter） |
| 堆表 / MVCC | 06 | 6.13–6.22（TOAST / hint bit / lazy vacuum / snapshot / EPQ / FSM / VM） |
| B-Tree 索引 | 07 | 7.16–7.24（page delete / dedup / split / WAL / GiST/GIN/SP-GiST/BRIN） |
| 事务 / 锁 / 并发 | 08 | 8.12–8.22（LWLock / HLock / multixact / 死锁 / SSI / 2PC / subxact） |
| WAL 与恢复 | 09 | 9.16–9.28（XLogRecord / FPW / rmgr / checkpoint / GUC / 监控） |
| 崩溃恢复 | 11 | — |
| 物理复制 | 12 | — |
| 逻辑复制 | 13 | — |
| 列存 / cstore | 14 | — |
| 综合（其他 AM / 并行 / 分区 / FDW / JIT） | 10 | — |

## 学习方法约定

每章都按下面四块写：

1. **全景** —— 子系统位置、与上下游的接口
2. **关键数据结构** —— 内存对象、磁盘页面布局、关键常量
3. **关键函数调用链** —— 用伪调用栈 + 真实函数名
4. **动手实验** —— GDB 命令、`pg_xlogdump`、人造故障

## 配套环境

```bash
# 编译（PG 18.3 推荐 meson）
cd ~/cwork/postgresql
meson setup build --prefix=$(pwd)/install --buildtype=debugoptimized
meson compile -C build -j$(nproc)
meson install -C build

# 初始化一个 debug 实例
./install/bin/initdb -D /tmp/pgdata --enable-debug
./install/bin/pg_ctl -D /tmp/pgdata -l /tmp/pg.log start

# GDB 跟踪一条 SQL
gdb --args ./install/bin/postgres -D /tmp/pgdata
(gdb) b ExecutorRun
(gdb) b heap_getnext
(gdb) c
# 在另一个 psql 窗口执行 SELECT ...
```

## 关键认知：PG 没有 undo log

整个系列的最核心洞察：**PostgreSQL 没有 undo log**。

- **历史版本全在 heap 里**：MVCC 通过 `t_xmin / t_xmax` + clog + Snapshot 实现
- **崩溃恢复只 redo 不 undo**：未提交事务的修改靠 clog 标 ABORTED + vacuum 清理
- **没有 doublewrite buffer**：用 full page image（FPW）+ checksum 防护 torn write
- **没有 in-place update**：UPDATE 总是写新 tuple，老 tuple 标 dead

这一条原则能解释前面 14 章里的多数"为什么"。能讲清楚以下 5 问就是资深内核：
1. 一条 `UPDATE` 在 PG 里经过哪些层？
2. crash 后 redo 为什么不需要 undo？
3. 物理复制与逻辑复制的 trade-offs？
4. `READ COMMITTED` 下 `UPDATE` 与 `SELECT FOR UPDATE` 的死锁路径？
5. cstore_fdw 是怎么"拼接"成 tuple 的？

## 后续

完成 L4 后，推荐进一步阅读：

### 源码自带文档

- `src/backend/executor/README` —— 执行器总器
- `src/backend/storage/buffer/README` —— 缓冲池策略
- `src/backend/access/heap/README.HOT` —— HOT 机制
- `src/backend/access/transam/README` —— 事务子系统
- `src/backend/storage/lmgr/README`、`README-SSI` —— 锁与 SSI

### 论文

- Michael Stonebraker, "The Design of the Postgres Rules System"
- Hellerstein et al., "Architecture of a Database System"（Berkeley）
- Pavlo et al., "Skew-Aware Automatic Database Partitioning"

### 邮件列表与社区

- `pgsql-hackers@lists.postgresql.org`
- `commitfest.postgresql.org`
- Slack: postgresql.slack.com

### 博客

- Hironobu SUZUKI（Pg internals）
- Bruce Momjian 的 PPT
- depesz（explain.depesz.com）
- pgPine（国内 PG 高手博客）
- RDS 内部 PG 系列（阿里 / 腾讯云）

### 工具

- `explain.dalibo.com` —— EXPLAIN 解释器
- `pg_plan_guarantee` —— 计划不变性检测
- `pgsentinel` —— 实时指标采集
- `pgspot` —— 计划差异分析

## 贡献 PG

完成整个系列后，如果你想从使用者变成贡献者：

1. **熟悉 cfbot**（自动跑 patch 的 CI）
2. **选一个未处理的 patch**（commitfest）
3. **写自己的 patch**
4. **回复社区 review**
6. **长期参与**：邮件列表活跃讨论 / PGCon / 北京 PG 大会

常见贡献方向：
- Bug 修复（相对简单）
- 性能优化（需要对内核深入理解）
- 新特性（与 PG 18/19 路线图匹配）
- 文档改进（README、注释）
- 测试用例（regression / isolation）

## 系列维护

- 配套源码：`~/cwork/postgresql` (PG 18.3)
- 文档版本：v1.0 (2026-08)
- 维护者：本博客作者
- 反馈：通过博客留言 / 邮件

欢迎 PR 新章节、纠错、补充实战练习。
