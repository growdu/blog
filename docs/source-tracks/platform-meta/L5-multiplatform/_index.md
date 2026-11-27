---
title: "多平台分发"
description: "同一份内容怎么发到公众号、知乎、视频号，各平台各有什么规矩。"
cascade:
  categories:
    - 多平台分发
tags:
  - 多平台分发
---

# 多平台分发

同一份内容怎么发到公众号、知乎、视频号，各平台各有什么规矩。

同一个内容单元，发到公众号、头条号、抖音、视频号、B 站，
每个平台的形态、限额、自动化程度都不一样。

这一系列要讲的是：怎么把这些差异**从代码里抽出来变成数据**，
怎么保证「重复跑一遍不会发两遍」，以及为什么这套系统的自动化
**故意停在半路**。

## 本系列文章

- [一份声明顶掉五套 if-else](./capability-model-and-publishing-pipeline.md)

## 相关

- [内容单元与内容契约](../L2-content-model/content-unit-and-contract.md) — 分发链路的输入长什么样
- [一个仓库，三条产线](../L1-platform-overview/one-repo-three-pipelines.md) — 三条产线里最年轻的一条
