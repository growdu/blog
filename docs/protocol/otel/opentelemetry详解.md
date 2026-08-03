# opentelemetry详解

OpenTelemetry（简称 OTel） 是一个开源的可观测性（Observability）标准与工具集，用于统一采集、传输和导出应用的 Trace（链路追踪）、Metric（指标）、Log（日志） 数据。

otel不提供ui，不保存数据，只定义如何采集和如何发送。

## 核心组成

- trace：请求链路

- metric：数值指标

- log：上下文

```shell
┌────────────┐
│ Application│  ← 你写的业务代码
└─────┬──────┘
      │ SDK
┌─────▼──────┐
│ OpenTelemetry SDK │ ← 生成 Span / Metric / Log
└─────┬──────┘
      │ OTLP
┌─────▼──────┐
│ OTel Collector │ ← 采集 / 处理 / 转发（核心）
└─────┬──────┘
      │ Exporter
┌─────▼──────┐
│ Backend │ ← Jaeger / Prometheus / Tempo / SkyWalking
└────────────┘
```text
## 核心概念

### trace/span

- trace：一次完整请求，有一个唯一的TraceID
- span： trace中的一个操作

   - SpanID
   - ParentSpanID
   - 起止时间
   - Attributes

### context传递

- traceID/SpanID

## OTLP

otlp用于在 SDK / Agent / 自定义采集器 与 OTel Collector 之间传输 Trace / Metric / Log 的统一协议。

otlp定义三件事：

- 数据模型
- 序列化方式
- 传输方式

otlp支持如下三种数据类型：

- trace
- metric
- log

## collector

## reference

1.https://www.cnblogs.com/hacker-linner/p/17613281.html
2.https://opentelemetry.io/zh/docs/concepts/observability-primer/