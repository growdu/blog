---
title: "openGauss CSN 全序保证机制"
date: 2026-10-21
categories:
  - 数据库
  - openGauss
  - 逻辑复制
  - 并行解码
tags:
  - openGauss
  - CSN
  - 全序
  - 并行解码
  - 逻辑复制
---

# openGauss CSN 全序保证机制

本目录收录 openGauss 在并行解码 / 逻辑复制场景下的 **CSN(Commit Sequence Number)** 全序保证机制深度分析。

## 文章

- [openGauss CSN 全序保证机制:从源码看为什么并行解码能保证全局一致性](./index.html) — 一篇完整深度拆解

## 相关目录

- [PostgreSQL 18 并行解码源码专题](../postgresql/index.html) — 对照看 PostgreSQL 的并行解码思路
- [openGauss 并行解码设计原理](../opengauss-parallel-decoding-design/index.html) — 姐妹篇,讲架构
- [openGauss 部署 / 架构专题](../../openguass/index.html) — openGauss 全家桶
