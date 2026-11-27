---
title: "Linux 源码"
description: "Linux 源码 赛道：3 个阶段，由浅入深。"
cascade:
  categories:
    - Linux 源码
tags:
  - Linux 源码
---

# Linux 源码

Linux 源码 赛道：3 个阶段，由浅入深。

Linux 内核是所有「系统级」知识的交汇点：进程怎么被调度、内存怎么被管住、
文件怎么落到盘上、系统调用怎么进内核 —— 这四件事在同一个代码树里，
而且这棵树是**全宇宙最被阅读过的 C 代码**。

这条线按「**先看全景，再跟一条链路**」的顺序走：先把内核的分层和代码地图摸清楚，
然后跟着一次 `write` 从用户态一路走到盘上，再一层层往下拆。

> 站里另有一条「[Linux 与网络](/categories/PostgreSQL%20%E6%BA%90%E7%A0%81%E5%86%85%E6%A0%B8/)」专题线，讲的是**怎么用**
> （命令、内存工具、网络协议、抓包、内核模块怎么写）。
> 那条线是「用」，这条线是「读懂它为什么这样表现」—— 两条互补，不重复。

## 路线图

- [Linux 源码学习之路：一张全景图 + 12 章路线](L1-getting-started/linux源码学习之路.md)

## 版本说明

本文基于 Linux `v7.4.0-rc3`（`git describe` 为 `v7.4-rc3-149-g666539eecdf4`）。
内核半年一个大版本，目录结构和内部 API 都会动；引用具体文件时，
请以你手上那棵树的 `git describe` 为准 —— 本文末尾有一张
「老文章会踩空的地方」对照表。

## 阶段

- [起步与全景](./L1-getting-started/_index.md)
- [架构与数据路径](./L2-architecture/_index.md)
- [进程与内存](./L3-process-memory/_index.md)
