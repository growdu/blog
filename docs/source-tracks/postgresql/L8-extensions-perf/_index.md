---
title: "扩展、性能与生态"
description: "把内核之外的东西补齐：扩展怎么写、扩展生态里有哪些能打的、性能怎么观测和调，以及别的数据库长什么样。"
cascade:
  categories:
    - 扩展、性能与生态
tags:
  - 扩展、性能与生态
---

# 扩展、性能与生态

把内核之外的东西补齐：扩展怎么写、扩展生态里有哪些能打的、性能怎么观测和调，以及别的数据库长什么样。

## 本系列文章

- [BenchmarkSQL 使用教程：从配置到运行机制分析](./benchmarksql使用教程.md)
- [Citus Columnar 深度解析：从 cstore_fdw 到 Table AM 的 PG 原生列存扩展](./citus-columnar-deep-dive/index.md)
- [Citus 深度解析：从分布式 SQL 到列存扩展的 PG 集群引擎](./citus-deep-dive/index.md)
- [cstore_fdw 深度解析：从 Hydra 到 Citus Columnar 的列存 FDW 鼻祖](./cstore-fdw-deep-dive/index.md)
- [火焰图怎么看:从一张图到优化方向的完整方法论](./flame-graph-analysis/index.md)
- [10 进阶特性](./learning-path/10-advanced-topics.md)
- [14 列存与 cstore_fdw](./learning-path/14-column-store.md)
- [安装mysql](./macos安装mysql.md)
- [真希望有人早点告诉我的 Postgres 经验](./pg-challahscript-tips/index.md)
- [PostgreSQL "Don't Do This" 完整中文版](./pg-dont-do-this/index.md)
- [pg_duckdb 深度解析：从 OLTP 到 OLAP hybrid query 的 DuckDB 内嵌扩展](./pg-duckdb-deep-dive/index.md)
- [pg_stat_statements 深度解析：从 query hash 到 pg_stat_* 生态的查询统计扩展](./pg-stat-statements-deep-dive/index.md)
- [pg_io_调优](./pg_io_调优.md)
- [pgAudit 深度解析：从 log_statement 到 PG 审计标准的合规扩展](./pgaudit-deep-dive/index.md)
- [pgBackRest 深度解析：从 pg_basebackup 到企业级备份恢复的 Go 实现](./pgbackrest-deep-dive/index.md)
- [pgbench 源码全解：一个 C 文件如何撑起 PostgreSQL 官方压测工具](./pgbench-internals/index.md)
- [pgcrypto 深度解析：从 md5 到 OpenSSL 集成的 PG 加密扩展](./pgcrypto-deep-dive/index.md)
- [pg扩展开发](./pgsql扩展.md)
- [pgvector 深度解析：从 ANN 索引到 RAG 时代的向量数据库核心](./pgvector-deep-dive/index.md)
- [polardb竞争力分析](./polardb竞争力分析.md)
- [PostGIS 深度解析：从 OGC Simple Features 到 PG 18 时代的 GIS 引擎](./postgis-deep-dive/index.md)
- [PostgreSQL 社区精髓资源汇总:从官方文档到内核贡献者博客的"一键直达"清单](./postgresql-community-gems/index.md)
- [PostgreSQL 逻辑复制性能分析:火焰图实战](./postgresql-flame-graph/index.md)
- [Injection Point 与 PG 测试框架集成实战:从 Makefile 到 .spec 完整链路](./postgresql-injection-points-test-framework/index.md)
- [用 Injection Point 测试无法到达的代码路径:3 种改造模式 + 实战](./postgresql-injection-points-test-unreachable/index.md)
- [PostgreSQL 18 Injection Point 完整指南:原理、API 与实战](./postgresql-injection-points/index.md)
- [sql_test](./sql_test.md)
- [taosd基本使用](./taos基本使用.md)
- [TimescaleDB Columnstore（hypercore）深度解析：时序列存压缩的 hybrid engine](./timescaledb-columnstore-deep-dive/index.md)
- [TimescaleDB 深度解析：从时间分区到列存压缩的 PG 时序数据库扩展](./timescaledb-deep-dive/index.md)
