# AI Video Orchestrator 技术选型文档

版本：V1.0

作者：架构组

---

# 1. 技术选型原则

## 目标

支持：

* Web端
* 桌面端
* 移动端

统一开发。

---

支持：

* AI Agent
* Workflow
* Provider插件
* 视频任务编排
* 企业级扩展

---

原则：

### 原则1

跨平台优先

避免多套代码。

---

### 原则2

Agent优先

天然支持LLM。

---

### 原则3

插件化优先

支持第三方扩展。

---

### 原则4

云原生优先

方便私有化部署。

---

# 2. 总体技术架构

Client Layer

↓

API Layer

↓

Application Layer

↓

Workflow Layer

↓

Agent Layer

↓

Provider Layer

↓

Infrastructure Layer

---

# 3. 客户端技术选型

## 方案比较

### React Native

优点：

移动端成熟

缺点：

桌面端支持较弱

---

### Flutter

优点：

移动端体验最好

缺点：

桌面生态一般

---

### Tauri + React

优点：

桌面端优秀

缺点：

移动端支持较弱

---

### React + Tauri + React Native

优点：

生态成熟

缺点：

维护两套UI

---

### Flutter + Flutter Desktop + Flutter Web

优点：

真正一套代码

支持：

Windows

Mac

Linux

Android

iOS

Web

---

推荐：

Flutter

---

# 4. 前端技术栈

Framework

Flutter 3.x

---

状态管理

Riverpod

---

路由

GoRouter

---

本地存储

Hive

---

网络

Dio

---

国际化

easy_localization

---

图表

fl_chart

---

工作流编辑器

自研节点编辑器

类似：

ComfyUI

LangFlow

Dify Workflow

---

# 5. 桌面端技术选型

采用：

Flutter Desktop

---

支持：

Windows

MacOS

Linux

---

优势：

统一UI

统一代码

统一维护

---

未来支持：

本地模型部署

本地渲染

GPU调用

---

# 6. Web端技术选型

Flutter Web

---

优点：

与桌面共用代码。

---

企业版管理后台

采用：

React

Ant Design

单独开发。

---

原因：

管理后台开发效率更高。

---

# 7. 后端技术选型

## 方案比较

### Java

优点：

企业级成熟

缺点：

Agent生态差

---

### Python

优点：

AI生态最好

缺点：

高并发一般

---

### Go

优点：

高性能

缺点：

Agent生态较弱

---

推荐：

Go + Python

---

职责划分：

Go：

业务系统

API

任务调度

Workflow

---

Python：

Agent

LLM

Prompt

AI推理

---

# 8. API层

框架：

Go

---

推荐：

[Gin](https://gin-gonic.com?utm_source=chatgpt.com)

或者

[Fiber](https://gofiber.io?utm_source=chatgpt.com)

---

统一：

REST

*

WebSocket

---

# 9. Workflow引擎

## 候选

LangGraph

Temporal

Airflow

Camunda

---

推荐：

Temporal

*

LangGraph

组合

---

Temporal负责：

任务编排

重试

恢复

状态管理

---

LangGraph负责：

Agent流程

---

# 10. Agent框架

推荐：

[LangGraph](https://langchain-ai.github.io/langgraph/?utm_source=chatgpt.com)

---

原因：

天然支持：

* 多Agent
* 状态机
* Memory
* Tool Calling

---

# 11. 数据库选型

主数据库：

PostgreSQL

---

原因：

JSON

向量

全文检索

事务

统一支持

---

# 12. 向量数据库

推荐：

[Qdrant](https://qdrant.tech?utm_source=chatgpt.com)

---

存储：

角色Embedding

导演知识库

Prompt知识库

---

# 13. 缓存

Redis

---

用途：

Session

Workflow状态

任务缓存

---

# 14. 消息队列

推荐：

[Apache Kafka](https://kafka.apache.org?utm_source=chatgpt.com)

---

用途：

视频任务

Agent任务

Provider回调

---

# 15. 文件存储

开发阶段：

MinIO

---

生产阶段：

S3兼容存储

---

保存：

视频

图片

音频

项目文件

---

# 16. Provider架构

统一接口：

Provider SDK

---

支持：

Kling

Veo

Runway

PixVerse

Hailuo

Vidu

Luma

---

配置中心：

Provider Center

---

用户可配置：

API Key

Endpoint

Region

Model

Quota

---

# 17. 视频处理

推荐：

FFmpeg

---

用途：

拼接

转码

字幕

音频混合

封面生成

---

# 18. 实时通信

WebSocket

---

支持：

任务状态

Agent日志

视频生成进度

Workflow执行过程

---

# 19. 部署架构

容器化：

Docker

---

编排：

Kubernetes

---

GPU管理：

NVIDIA GPU Operator

---

任务调度：

Volcano

---

# 20. 可观测性

日志：

Loki

---

监控：

Prometheus

Grafana

---

链路追踪：

OpenTelemetry

---

# 21. 开发团队配置

前端

2人

Flutter

---

后端

3人

Go

---

AI工程师

2人

LangGraph

Prompt

---

DevOps

1人

---

产品

1人

---

总计：

9人

---

# 22. 最终技术栈

客户端：

Flutter

---

管理后台：

React

---

后端：

Go

---

Agent：

Python

LangGraph

---

数据库：

PostgreSQL

---

向量库：

Qdrant

---

缓存：

Redis

---

消息队列：

Kafka

---

存储：

MinIO

---

编排：

Temporal

---

部署：

Kubernetes

---

视频处理：

FFmpeg

---

这是当前阶段最适合 AI Video Orchestrator 的技术方案。
