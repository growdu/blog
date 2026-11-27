---
title: "事务、MVCC 与并发"
description: "隔离级别到底靠什么实现，行锁在哪一层加上去的。"
cascade:
  categories:
    - 事务、MVCC 与并发
tags:
  - 事务、MVCC 与并发
---

# 事务、MVCC 与并发

隔离级别到底靠什么实现，行锁在哪一层加上去的。

## 本系列文章

- [06 堆表与 MVCC](./learning-path/06-heap-and-mvcc.md)
- [08 事务、锁与并发](./learning-path/08-locks-and-concurrency.md)
- [PostgreSQL Latch 机制详解：从一行 SetLatch 到 epoll 的内核之旅](./postgresql-latch-mechanism/index.md)
- [PostgreSQL MVCC：一条数据是如何拥有"分身术"的](./postgresql-mvcc/index.md)
- [PostgreSQL 18 并行 Worker 机制全解：从 `ParallelContext` 到 `ParallelQueryMain` 的全链路](./postgresql-parallel-worker/index.md)
- [PostgreSQL 行锁机制源码级深度拆解：4 种锁模式 + xmax + MultiXact 的完整链路](./postgresql-row-lock-deep-dive/index.md)
- [PostgreSQL 行锁机制深度解析:从 MVCC 到多级锁的完整链路](./postgresql-row-lock/index.md)
- [PostgreSQL 逻辑复制里 `RUNNING_XACTS` 写入机制与快照 `xmin / xmax / xip` 的演化：源码级深度拆解](./postgresql-running-xacts-snapshot/index.md)
- [PostgreSQL 事务：一次 BEGIN 与 COMMIT 背后的双层世界](./postgresql-transaction-lifecycle/index.md)
