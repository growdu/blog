# weixin — 博客到公众号的转换与自动发布

把 `source/_posts/` 下的博客文章转换成公众号可直接发布的 HTML，并推送到公众号草稿箱。

## 现状

- 语料：560 篇文章、6533 个代码围栏（mermaid 1272）、13512 行表格、568 张图、1208 处站外链接
- 合规率：正文超 20000 字 23 篇、标题超 64 字符 16 篇，其余全部可用
- 设计规格：[docs/10-设计.md](docs/10-设计.md)
- 实施计划：[docs/11-实施计划.md](docs/11-实施计划.md)

## 依赖

| 依赖 | 用途 |
| --- | --- |
| Python 3.11+ | 运行时 |
| pygments | 代码服务端高亮（已装） |
| pillow | 图片压缩与尺寸（已装） |
| pytest | 测试（已装） |
| node + `@mermaid-js/mermaid-cli` | mermaid → PNG（唯一需额外安装的） |

除上面这些外只用标准库：front-matter 是手写解析器，HTTP 用 `urllib`，multipart 编码自己拼。

## 快速开始

```bash
# 1. 生成 source/_posts/（首次或改动 docs/ 后，约 3 分钟）
python3 tools/sync-hexo.py

# 2. 盘点：哪些文章能发，哪些不能，为什么
cd weixin && python3 -m wechat.cli scan

# 3. 转换（不调接口，只产出 HTML）
cd weixin && python3 -m wechat.cli convert <slug>
```

## 命令

| 命令 | 作用 |
| --- | --- |
| `scan` | 盘点全部文章，输出合格/不合格清单 |
| `convert <slug>` | 转换一篇，产出 HTML 到 `out/` |
| `publish <slug>` | 转换 + 上传 + 建草稿 |
| `publish <slug> --publish` | 额外提交发表（默认只到草稿箱） |
| `status` | 查看所有文章的状态 |

`<slug>` 是文章相对 `source/_posts/` 的路径去掉 `.md`，例如
`db/postgresql/postgresql-logical-replication-add-guc`。

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `WX_APPID` | 公众号 AppID |
| `WX_APPSECRET` | 公众号 AppSecret（**不要提交到仓库**） |
| `WX_SOURCE_URL` | 站点根 URL，用于拼「阅读原文」，默认 `https://growdu.cn` |
| `WX_COVER` | 封面图路径（未指定时取文章首图） |

## 测试

```bash
cd /Users/growduduan/code/blog && python3 -m pytest weixin/tests -q
```

测试不依赖网络：微信接口用本地假 HTTP server 模拟。

## 边界

- **发布在本地执行**：微信后台要求调用机出口 IP 加白名单，GitHub 托管 runner 的 IP 是动态的。
- **默认只到草稿箱**：2025-07 起部分账号类型的发表接口返回 `48001`，草稿箱天然是人工审批点。
- **超限文章跳过**：正文 > 20000 字、标题 > 64 字符的文章会被记录但不发，不做截断。
- **mermaid 渲染失败会显式降级**为源码块并记入报告，不会静默丢图。
- **全流程幂等**：正文指纹 / `media_id` / `publish_id` 三层键，重复执行不会发两遍。
