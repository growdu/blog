---
title: "WAL 与恢复"
description: "WAL、checkpoint 与恢复：写前日志怎么保证崩溃后能redo出来。"
cascade:
  categories:
    - WAL 与恢复
tags:
  - WAL 与恢复
---

# WAL 与恢复

WAL、checkpoint 与恢复：写前日志怎么保证崩溃后能redo出来。

## 本系列文章

- [PostgreSQL WAL 记录类型完全指南：21 个 RMGR × 80+ 种记录的源码级拆解](./postgresql-wal-record-types/index.md)
- [09 WAL 与恢复](./learning-path/09-wal-and-recovery.md)
- [11 崩溃恢复深入](./learning-path/11-crash-recovery.md)
- [PostgreSQL 时间线解析](./PostgreSQL%20时间线解析.md)
- [PostgreSQL Checkpoint 机制浅析](./checkpoint机制浅析.md)
- [BgWriter](./BgWriter.md)
- [checkpoint](./Checkpoint.md)
- [WalWriter](./WalWriter.md)
- [数据库数据完整性问题（块折断）](./full_page_writes/index.md)
- [pg_checksum](./pg_checksum.md)
- [xlog](./xlog.md)
- [wal机制浅析](./wal机制浅析.md)
- [数据库崩溃恢复](./数据库崩溃恢复.md)
