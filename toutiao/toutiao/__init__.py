"""头条号 adapter —— 把博客文章裁成头条版并发布。

本包实现 [publish/spec/00-架构设计.md](../../publish/spec/00-架构设计.md) 定义的
平台 adapter 契约，与 `weixin/wechat/` 平级、互不引用。

接缝只有两处：
  1. `publish/capabilities/toutiao.toml` —— 平台限额与自动化档位（数据）
  2. 一份发布清单 manifest JSON —— 调度层交给本包的内容单元与目标平台

权威文档：
  - 整体架构：publish/spec/00-架构设计.md
  - 头条号一节：publish/spec/06-发布计划与调度.md §6
  - 实现规格：toutiao/docs/00-设计.md
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
