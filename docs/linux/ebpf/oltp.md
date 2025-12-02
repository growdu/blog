# otlp

otlp，全称是opentelemetry protocol，主要用于可观测性领域。（trace、metrics、logs）

## 使用rust

引入依赖：

```toml
name = "otlp_tempo_demo"
version = "0.1.0"
edition = "2021"

[dependencies]
opentelemetry = "0.23"
opentelemetry-otlp = { version = "0.17", features = ["grpc-tonic"] }
opentelemetry_sdk = { version = "0.23", features = ["trace"] }
tonic = "0.11"
tokio = { version = "1", features = ["full"] }

[[bin]]
name = "otlp-test"
path = "main.rs"

```

## 使用python

```shell
apt install python3-pip
apt install python3.12-venv
python3 -m venv otlp-demo-env
source otlp-demo-env/bin/activate
pip install --upgrade pip
pip install opentelemetry-sdk opentelemetry-exporter-otlp grpcio
```

```python
import time
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# -------------------- 1. 配置 TracerProvider --------------------
resource = Resource.create(attributes={
    "service.name": "python-otlp-demo"
})
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)

# -------------------- 2. 配置 OTLP Exporter --------------------
otlp_exporter = OTLPSpanExporter(
    endpoint="http://192.168.3.99:4317",  # Tempo OTLP gRPC endpoint
    insecure=True
)

# -------------------- 3. 配置 BatchSpanProcessor --------------------
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# -------------------- 4. 发送示例 spans --------------------
for i in range(5):
    span_name = f"example_span_{i}"
    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute("example.index", i)
        print(f"➡️  Started span '{span_name}'")
        time.sleep(0.2)  # 模拟处理时间
        print(f"⬅️  Ended span '{span_name}'")

# -------------------- 5. Flush spans --------------------
print("💡 Flushing all spans to Tempo...")
span_processor.shutdown()
print("✅ Flush complete")

```

打包环境依赖：

```shell
# 激活你的 venv
source otlp-demo-env/bin/activate

# 导出所有依赖到 requirements.txt
pip freeze > requirements.txt

# 创建一个目录存放 wheel 文件
mkdir -p /tmp/wheels

# 下载所有依赖（不安装）到 wheel 文件
pip download -r requirements.txt -d /tmp/wheels
```

在离线环境安装:

```shell
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install --no-index --find-links=/path/to/wheels -r requirements.txt
```