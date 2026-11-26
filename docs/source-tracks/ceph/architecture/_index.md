---
title: "架构与数据路径"
description: "一次读写请求在 Ceph 里怎么流转：客户端、Messenger、OSD、PG、BlueStore。"
cascade:
  categories:
    - 架构与数据路径
tags:
  - 架构与数据路径
---

# 架构与数据路径

一次读写请求在 Ceph 里怎么流转：客户端、Messenger、OSD、PG、BlueStore。

## 本系列文章

- [01 整体架构与一次写请求的完整链路](./learning-path/01-整体架构与一次写请求的完整链路.md)
- [03 MON：集群状态是怎么产生和分发的](./learning-path/03-MON集群状态的产生与分发.md)
- [04 PG 状态机：从 peering 到 active](./learning-path/04-PG状态机与恢复.md)
- [05 CRUSH：数据怎么落到这些盘上](./learning-path/05-CRUSH数据放置.md)
- [06 BlueStore：对象怎么变成 extent](./learning-path/06-BlueStore对象与extent.md)
- [07 事务与 journal：一次写什么时候算「落盘」](./learning-path/07-事务与journal写什么时候算落盘.md)
- [08 RADOS 对象语义：omap、快照、xattr、watch/notify](./learning-path/08-RADOS对象语义.md)
