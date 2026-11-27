---
title: "构建流水线"
description: "从 `docs/` 到 `public/`：同步、分类链、重定向、静态资源各走哪一步。"
cascade:
  categories:
    - 构建流水线
tags:
  - 构建流水线
---

# 构建流水线

从 `docs/` 到 `public/`：同步、分类链、重定向、静态资源各走哪一步。

站点这条线是三条产线里最成熟的一条，也是唯一一条**每次 push 都会自动跑完**的。

它的形状很简单：`docs/` 里的 markdown 是真相，一个编译脚本把它们变成
Hexo 的源，Hexo 再渲染成静态页面。但「简单」是结果不是过程——
这条线上踩过的坑，单独写一篇都写不完。

## 本系列文章

- [从母稿到页面](./docs-to-public-pipeline.md)

## 相关

- [内容单元与内容契约](../L2-content-model/content-unit-and-contract.md) — 编译这一步到底在「搬」什么
- [一个仓库，三条产线](../L1-platform-overview/one-repo-three-pipelines.md) — 站点在整体架构里的位置
