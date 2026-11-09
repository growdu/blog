---
title: "逻辑复制并行 apply · 口播稿与字幕"
date: 2026-11-09
---

# 视频字幕（口播稿 · 逻辑复制并行 apply · 问题-解决版）

> 时长：约 32 秒（落版 3 秒另算）
> 配音员标准播报速度约 4 字/秒
> 主钩子：**海量数据库 · 逻辑复制内核原生集成 Apply Parallel Worker**
> 结构：**提出问题 → 解决问题** 双循环
> 场景覆盖：**大事务 + 海量小事务高并发**

---

## 问题-解决 一览

| 循环 | 问题 | 解决 |
| --- | --- | --- |
| P1 → S1 | 逻辑复制 apply 跟不上 publisher，大事务/小事务高并发都延迟 | Apply Parallel Worker 多 worker 并行回放 |
| P2 → S2 | 多 worker 并行如何保证事务一致性 | leader 按 publisher commit LSN 顺序协调 |

---

## 口播稿（按 P1→S1→P2→S2→Value 节奏组织）

大家好，我是海量数据库内核研发 growdu

今天我们聊一聊海量数据库逻辑复制的并行 apply

【问题 1】逻辑复制 apply 跟不上 publisher，怎么办？

默认订阅端只有一个 apply worker 串行回放

大事务 10 万条 INSERT 要等 30 分钟

小事务高并发场景同样延迟严重

【解决 1】海量数据库原生集成 Apply Parallel Worker

大事务自动切分为多 stream

多 worker 并行回放，订阅端延迟从 30 分钟降到 3 分钟

【问题 2】多 worker 并行，事务一致性怎么保证？

【解决 2】leader 按 publisher commit LSN 顺序协调

commit 顺序与 publisher 保持一致

【价值】整体性能提升 4 到 5 倍

大事务小事务都适用

满足金融、政务、电信强监管实时同步要求

---

## 主钩子（双行）

> **海量数据库**
> **逻辑复制内核原生集成 Apply Parallel Worker**
> **多 worker 并行回放 · 性能 4 到 5 倍 · commit 顺序一致**

---

## 分段时间轴（32s 主轴 + 3s 落版）

| 时间 | 段落 | P/S | 字幕 |
| --- | --- | --- | --- |
| 0–4s | 钩子 | 问题预告 | 逻辑复制 apply 跟不上 publisher，怎么办？ |
| 4–8s | P1 | 问题 1 | 默认订阅端只有一个 apply worker 串行回放 |
| 8–11s | P1 | 数据 1 | 大事务 10 万条 INSERT 要等 30 分钟 |
| 11–14s | P1 | 数据 2 | 小事务高并发场景同样延迟严重 |
| 14–20s | S1 | 解决 1 | 海量数据库原生集成 Apply Parallel Worker，大事务自动切分为多 stream |
| 20–23s | S1 | 数据 | 多 worker 并行回放，订阅端延迟从 30 分钟降到 3 分钟 |
| 23–26s | P2 | 问题 2 | 多 worker 并行，事务一致性怎么保证？ |
| 26–29s | S2 | 解决 2 | leader 按 publisher commit LSN 顺序协调，与 publisher 保持一致 |
| 29–32s | Value | 价值 | 整体性能提升 4 到 5 倍，大事务小事务都适用 |
| 32–35s | 落版 | — | 海量数据库 · 逻辑复制 Apply Parallel Worker 多 worker 并行回放 |

---

## 数据出处（来自现有文档）

| 数据 | 出处 |
| --- | --- |
| 10 万条 INSERT 串行 30 分钟 / 并行 3 分钟 | `postgresql-apply-parallel-worker/index.md` § 1.2 解决什么问题 |
| 性能提升 4 到 5 倍 | 当前字幕（用户更新版） |
| 1 leader + N PA worker 进程模型 | `postgresql-apply-parallel-worker/index.md` § 二 整体架构 |
| 必须按 publisher commit LSN 顺序提交 | `postgresql-apply-parallel-worker/index.md` § 1.3 重要的边界 |
| shm_mq 数据通道 + 错误通道 | `postgresql-apply-parallel-worker/index.md` § 2.1 三个角色架构图 |

---

## 制作说明（与 DDL 字幕一致）

- 中文每行 ≤ 14 字，便于竖版 9:16 字幕不溢出。
- 主钩子双行展示，第二行青色 #4FD1C5。
- 问题段字幕用红色 #F6AD55 高亮，解决段用青色 #4FD1C5 高亮。
- 数值段「30 分钟 → 3 分钟」「4 到 5 倍」用大字号 + 数字强调色。
- 「大事务」「小事务」用对比色块强化两个场景并行感。
- 「逻辑复制」用青色高亮 + 加大字号，与"apply"绑定为专属术语。
- 不出现具体数据库名 / 函数名 / 类名 / 源码符号 / 订阅选项参数名。
- 表达克制，不堆砌形容词。
