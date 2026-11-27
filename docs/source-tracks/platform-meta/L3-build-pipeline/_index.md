---
title: "构建流水线"
description: "docs/ → source/ → public/ 完整链路：内容编译、主题补丁、CI 门禁，以及踩过的坑。"
cascade:
  categories:
    - 构建流水线
tags:
  - 构建流水线
  - Hexo
  - CI
---

# 构建流水线

站点这条线是三条产线里最成熟的一条，也是唯一一条**每次 push 都会自动跑完**的。

它的形状很简单：`docs/` 里的 markdown 是真相，一个编译脚本把它们变成
Hexo 的源，Hexo 再渲染成静态页面。但「简单」是结果不是过程——
这条线上踩过的坑，单独写一篇都写不完。

## 本系列文章

- [从母稿到页面](./docs-to-public-pipeline.md) — 一次 push 之后到底发生了什么、
  主题补丁为什么用 marker 注入、日期是怎么来的，以及四个真实踩过的坑

## 相关

- [内容单元与内容契约](../content-model/content-unit-and-contract.md) — 编译这一步到底在「搬」什么
- [一个仓库，三条产线](../platform-overview/one-repo-three-pipelines.md) — 站点在整体架构里的位置
