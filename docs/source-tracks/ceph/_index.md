---
title: "Ceph 源码"
description: "Ceph 源码 赛道：2 个阶段，由浅入深。"
cascade:
  categories:
    - Ceph 源码
tags:
  - Ceph 源码
---

# Ceph 源码

Ceph 源码 赛道：2 个阶段，由浅入深。

Ceph 是分布式存储里少见的一个「全样本」：对象存储、块存储、文件存储三种形态跑在同一套
RADOS 之上；无中心的元数据管理、一套 CRUSH 放置算法、一套自己实现的网络栈，全都摊在
同一个代码树里。读它等于读了一遍分布式存储的教科书。

这条线按「**先看全景，再看一条链路**」的顺序走：先把 Ceph 的角色分工和代码地图摸清楚，
然后跟着一次写请求从 librados 一路走到盘上，再一层层往下拆。

## 已写章节

| # | 章节 | 回答什么问题 |
| --- | --- | --- |
| 01 | [整体架构与一次写请求的完整链路](L2-architecture/learning-path/01-整体架构与一次写请求的完整链路.md) | 一次写从 librados 到盘上再回到客户端，经过了哪些函数？ |
| 02 | [环境、编译与代码地图](L1-getting-started/learning-path/02-环境编译与代码地图.md) | 怎么把 Ceph 编译起来、跑起来、在 30 万行里定位一个函数？ |
| 03 | [MON：集群状态是怎么产生和分发的](L2-architecture/learning-path/03-MON集群状态的产生与分发.md) | OSDMap 从哪儿来，怎么在 MON 之间表决、怎么发给客户端？ |
| 04 | [PG 状态机：从 peering 到 active](L2-architecture/learning-path/04-PG状态机与恢复.md) | PG 的每个状态意味着什么，恢复是怎么一步步推进的？ |
| 05 | [CRUSH：数据怎么落到这些盘上](L2-architecture/learning-path/05-CRUSH数据放置.md) | 一个 PG 怎么变成一组 OSD，权重和故障域怎么参与计算？ |
| 06 | [BlueStore：对象怎么变成 extent](L2-architecture/learning-path/06-BlueStore对象与extent.md) | 对象在盘上长什么样，allocator 怎么分配空间，一次写什么时候算落盘？ |
| 07 | [事务与 journal：一次写什么时候算「落盘」](L2-architecture/learning-path/07-事务与journal写什么时候算落盘.md) | journal 这个词在 v22 还剩什么含义？写成功回包的那一刻，数据到底在哪儿？ |
| 08 | [RADOS 对象语义：omap、快照、xattr、watch/notify](L2-architecture/learning-path/08-RADOS对象语义.md) | omap、快照、xattr、watch/notify 分别由谁实现、落在哪一层？ |

## 路线图

- [Ceph 源码学习之路：一张全景图 + 12 章路线](L1-getting-started/ceph源码学习之路.md)

## 版本说明

本文基于 Ceph `main` 分支（`v22.0.0`，代号 **vampire**，dev 版本）。
Ceph 每年发一个大版本，目录结构会动；引用具体文件时，请以你手上那棵树的
`git describe` 为准。

## 阶段

- [起步与全景](./L1-getting-started/_index.md)
- [架构与数据路径](./L2-architecture/_index.md)
