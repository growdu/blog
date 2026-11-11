# weixin — 博客到公众号的转换与自动发布

把 `source/_posts/` 下的博客文章转换成公众号可直接发布的 HTML，并推送到公众号草稿箱。

## 现状

- 语料：**564 篇**文章、7689 个代码围栏（mermaid 1280）、13512 行表格、568 张图、1208 处站外链接
- 合规：标题 ≤ 32 字（官方上限）过 459 篇、渲染后 HTML ≤ 20000 字符过 349 篇，**最终可发布 357 篇（63.3%）**
- 测试：132 个，全绿，不依赖网络
- 试点：`dpdk/vpp与dpdk的关系` 转换链路已跑通；**发布链路待用自己的号实测接口**

## 文档

| 文档 | 内容 |
| --- | --- |
| [docs/00-文章盘点.md](docs/00-文章盘点.md) | 564 篇全量统计、三层合规闸门、超限文章的本质问题 |
| [docs/01-转换规则.md](docs/01-转换规则.md) | Markdown → 公众号 HTML 的逐条规则、链接降级、图片两段式、mermaid 降级、体积预算 |
| [docs/02-接口与发布.md](docs/02-接口与发布.md) | 6 个微信接口、字段限制、token 选型、publish_status 状态机、三层幂等、错误码 |
| [docs/03-试点记录.md](docs/03-试点记录.md) | 单篇实测数据、mermaid 成功/失败两条路径、Phase 0 接口实测清单 |
| [docs/10-设计.md](docs/10-设计.md) | 设计规格（语料盘点 → 模块规格 → 风险） |
| [docs/11-实施计划.md](docs/11-实施计划.md) | 实施计划 + **试点后的修订记录**（哪些假设被推翻） |

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

全局选项（`--posts-dir` / `--out-dir` / `--source-url`）写在子命令前后都行。

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `WX_APPID` | 公众号 AppID |
| `WX_APPSECRET` | 公众号 AppSecret（**不要提交到仓库**） |
| `WX_SOURCE_URL` | 站点根 URL，用于拼「阅读原文」，默认 `https://growdu.cn` |
| `WX_COVER` | 封面图路径（未指定时取文章首图） |

## 实现现状

| 段 | 模块 | 状态 |
| --- | --- | --- |
| 发现 / 校验 | `posts.py` | ✅ 硬限制、permalink、摘要 |
| 解析 | `mdparse.py` | ✅ 纯函数 |
| 渲染 | `render.py` | ✅ inline style，0 个 `class` |
| 高亮 | `highlight.py` | ✅ Pygments，nowrap + noclasses |
| mermaid | `mermaid.py` | ✅ 失败显式降级为源码块 |
| 资产 | `assets.py` | ✅ 压缩到 ≤ 1 MB、封面裁剪框 |
| 接口 | `publish.py` | ✅ 6 个接口，错误不吞 |
| 幂等 | `state.py` | ✅ 三层键 |
| CLI | `cli.py` | ✅ scan / convert / publish / status |

## 测试

```bash
cd /Users/growduduan/code/blog && python3 -m pytest weixin/tests -q
```

测试不依赖网络：微信接口用本地假 HTTP server 模拟（绑定 `127.0.0.1`）。

## 边界

- **发布在本地执行**：微信后台要求调用机出口 IP 加白名单，GitHub 托管 runner 的 IP 是动态的。
- **默认只到草稿箱**：2025-07 起部分账号类型的发表接口返回 `48001`，草稿箱天然是人工审批点。
- **超限文章跳过**：标题 > 32 字、原始正文 > 20000 字、**渲染后 HTML > 20000 字符**的文章会被记录但不发，不做截断。
- **mermaid 渲染失败会显式降级**为源码块并记入报告，不会静默丢图。
- **全流程幂等**：正文指纹 / `media_id` / `publish_id` 三层键，重复执行不会发两遍。
- **38% 的文章渲染后超限**：这是平台的结构性约束（HTML 标签和样式都计入 2 万字符），不是实现缺陷。出路是拆篇，或发摘要版 + 全文放「阅读原文」。
