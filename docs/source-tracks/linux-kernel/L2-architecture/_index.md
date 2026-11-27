---
title: "架构与数据路径"
description: "一次系统调用在 Linux 里怎么流转：入口、VFS、块层；外加进程、调度、内存三条主线。"
cascade:
  categories:
    - 架构与数据路径
tags:
  - 架构与数据路径
---

# 架构与数据路径

一次系统调用在 Linux 里怎么流转：入口、VFS、块层；外加进程、调度、内存三条主线。

## 本系列文章

- [01 整体架构与一次系统调用的完整链路](./learning-path/01-整体架构与一次系统调用的完整链路.md)
- [02 编译与启动：从 `start_kernel` 到第一个用户态进程](./learning-path/02-编译与启动-从start_kernel到第一个用户态进程.md)
