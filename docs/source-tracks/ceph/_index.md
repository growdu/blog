---
title: "Ceph"
description: "Ceph 源码主线：从一次读写的完整链路，读到 MON、PG、CRUSH 与 BlueStore。"
cascade:
  categories:
    - Ceph
tags:
  - Ceph
---

# Ceph

Ceph 源码主线：从一次读写的完整链路，读到 MON、PG、CRUSH 与 BlueStore。

Ceph 是分布式存储里少见的一个「全样本」：对象存储、块存储、文件存储三种形态跑在同一套
RADOS 之上；无中心的元数据管理、一套 CRUSH 放置算法、一套自己实现的网络栈，全都摊在
同一个代码树里。读它等于读了一遍分布式存储的教科书。

这条线按「**先看全景，再看一条链路**」的顺序走：先把 Ceph 的角色分工和代码地图摸清楚，
然后跟着一次写请求从 librados 一路走到盘上，再一层层往下拆。

## 系列

- [起步与全景](./getting-started/_index.md)
- [架构与数据路径](./architecture/_index.md)

## 路线图

- [Ceph 源码学习之路：一张全景图 + 12 章路线](./getting-started/ceph源码学习之路.md)

## 版本说明

本文基于 Ceph `main` 分支（`v22.0.0`，代号 **vampire**，dev 版本）。
Ceph 每年发一个大版本，目录结构会动；引用具体文件时，请以你手上那棵树的
`git describe` 为准。
