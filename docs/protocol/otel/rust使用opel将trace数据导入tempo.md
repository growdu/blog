# rust使用opel将trace数据导入tempo

## 新建项目

```shell
cargo new otlp_test
```text
## 修改项目依赖

修改Cargo.toml,将其内容修改如下：

```toml
[package]
name = "otlp_test"
version = "0.1.0"
edition = "2024"

[dependencies]
opentelemetry = "0.23"
opentelemetry-otlp = "0.16"
tokio = { version = "1", features = ["full"] }
opentelemetry_sdk = { version = "0.23", features = ["rt-tokio"] }
```text
## 添加导入逻辑

将main.rs替换为如下内容：

```rs
use opentelemetry::{global, Context, KeyValue};
use opentelemetry::trace::{Span, SpanKind, TraceContextExt, Tracer};
use opentelemetry_sdk::trace::{self, Sampler};
use opentelemetry_sdk::Resource;
use opentelemetry_otlp::WithExportConfig;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // ===== 构建 OTLP SpanExporter（注意：build！）=====
    let exporter = opentelemetry_otlp::new_exporter()
        .tonic()
        .with_endpoint("http://192.168.3.99:4317")
        .build_span_exporter()?;

    // ===== TracerProvider =====
    let tracer_provider = trace::TracerProvider::builder()
        .with_config(
            trace::Config::default()
                .with_sampler(Sampler::AlwaysOn)
                .with_resource(Resource::new(vec![
                    KeyValue::new("service.name", "rust-tempo-demo"),
                    KeyValue::new("service.version", "0.1.0"),
                ])),
        )
        .with_batch_exporter(exporter, opentelemetry_sdk::runtime::Tokio)
        .build();

    global::set_tracer_provider(tracer_provider);

    let tracer = global::tracer("demo");

    // ===== Root span =====
    // let cx = opentelemetry::Context::current();
    // let mut root = tracer.start_with_context("http_request", &cx);
    let mut root = tracer.start("http_request");
    root.set_attribute(KeyValue::new("http.method", "GET"));
    root.set_attribute(KeyValue::new("http.route", "/demo"));
    let cx = Context::current_with_span(root);

    // ===== Child span =====
    {
        let mut child = tracer
            .span_builder("db_query")
            .with_kind(SpanKind::Internal)
            .start_with_context(&tracer, &cx);

        child.set_attribute(KeyValue::new("db.system", "postgresql"));
        child.set_attribute(KeyValue::new(
            "db.statement",
            "SELECT * FROM test",
        ));

        std::thread::sleep(std::time::Duration::from_millis(120));
        child.end();
    }

    cx.span().end();

    // ===== 非常重要：flush =====
    global::shutdown_tracer_provider();

    Ok(())
}
```text
## 基本概念详解

- exporter：出口
- provider：入口与生命周期管理
- pipeline：处理流水线

```shell
Instrumentation (Span / Metric)
        ↓
   Provider (TracerProvider / MeterProvider)
        ↓
      Pipeline
  (Sampler / Processor / Aggregation)
        ↓
     Exporter
        ↓
 Tempo / Jaeger / Prometheus / OTLP Collector
```text
trace/span/metric是底层数据模型：

span有如下特点：

- 一次操作
- 开始/结束时间
- 有属性
- 有事件
- 有父子关系

```shell
HTTP request
 └─ SQL query
     └─ index scan
```text
trace是一棵span树，使用traceID标识。span是最小单位，trace是span的集合。

metric是数值型时间序列，主要是统计信息。

### provider

provider是入口+全局管理者。

1. TraceProvider

```rust
let provider = TracerProvider::builder()
    .with_span_processor(...)
    .build();
```text
- 创建Tracer
- 管理生命周期
- 持有pipeline
- flush/shutdown

2. pipeline

trace pipeline典型组成：

- Sampler：采样器
- SpanProcessor：处理器
- Exporter：发送到后端

常见的trace exporter：

- opentelemetry_otlp	OTLP gRPC / HTTP
- opentelemetry_jaeger	Jaeger
- opentelemetry_zipkin	Zipkin
- stdout	打印

```rust
let exporter = opentelemetry_otlp::new_exporter().tonic();
```text
trace的完整生命周期如下：

```shell
你调用 tracer.start()
   ↓
Tracer（来自 TracerProvider）
   ↓
Sampler 决定是否记录
   ↓
Span 生命周期交给 SpanProcessor
   ↓
Span 结束
   ↓
Exporter 发出去
```text
对应sdk结构关系：

```shell
TracerProvider
 ├── Resource
 ├── Sampler
 └── SpanProcessor
      └── Exporter
```text
- trace / metric	“记录什么数据”
- provider	“谁来创建 & 管理”
- pipeline	“数据如何处理”
- exporter	“数据发到哪”