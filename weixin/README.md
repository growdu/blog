# weixin — 博客到公众号的转换与自动发布

把 `source/_posts/` 下的博客文章转换成公众号可直接发布的 HTML，并推送到公众号草稿箱。

## 现状

- 语料：**564 篇**文章、7689 个代码围栏（mermaid 1280）、13512 行表格、568 张图、1208 处站外链接
- 合规：标题 ≤32 字过 459 → 原始正文 ≤2 万字过 444 → 渲染后 HTML ≤2 万字符过 **357 篇（63.3%）**（其中 18 篇靠关闭代码高亮才放得下）
- 测试：**229 个**，全绿，不依赖网络
- **发布链路已用真实账号实测**：`stable_token` / `media/uploadimg` /
  `material/add_material` / `draft/add` 全部通过，草稿已进草稿箱；
  `freepublish/submit` 返回 **48001 api unauthorized**——该账号没有发表权限，
  最后「点一下发表」由人完成
- **分类与合集**：平台没有开放接口（`draft/add` 无 category 字段、`api.weixin.qq.com`
  无对应端点、合集只收已发布文章），但**分类标签、合集计划、合集导览文章、
  后台勾选清单**都能自动生成。合集导览文章已用真实账号建过草稿并回读校验
  （0 个 class、0 个外链锚点、0 个残留占位符）。见
  [docs/04-分类与合集.md](docs/04-分类与合集.md)

## 实测结论速查

| 事项 | 结论 |
| --- | --- |
| IP 白名单填哪个 IP | **以 `40164` 报错里的为准**。走分流代理时 `curl ifconfig.me` 拿到的不是微信看到的那个 |
| `stable_token` 的凭据字段名 | 用 **`secret`**，不是文档写的 `appsecret`（只发 appsecret 会被回 `41004`） |
| `media/uploadimg` 的 token 位置 | 走 **query 参数** `?access_token=`，`Authorization` header 对这两个老接口无效 |
| 外链图片 | 微信会**静默删除**非 mmbiz 的图片。工具会下载并转存，转存失败的降级为可见提示 |
| 幂等 | 同一篇跑两次复用同一个 `media_id`，不产生第二篇草稿 |
| 失败行为 | 退出码 3、`publish_id` 不写、错误不吞——不会静默成功 |
| 分类 / 合集 | **接口层面做不了**：`draft/add` 无 category 字段，`api.weixin.qq.com` 无对应端点，合集后台只收**已发布**文章。工具负责内容与清单，平台上的归属仍需人工勾选 |

## 文档

| 文档 | 内容 |
| --- | --- |
| [docs/00-文章盘点.md](docs/00-文章盘点.md) | 564 篇全量统计、三层合规闸门、超限文章的本质问题 |
| [docs/01-转换规则.md](docs/01-转换规则.md) | Markdown → 公众号 HTML 的逐条规则、链接降级、图片两段式、mermaid 降级、体积预算 |
| [docs/02-接口与发布.md](docs/02-接口与发布.md) | 6 个微信接口、字段限制、token 选型、publish_status 状态机、三层幂等、错误码 |
| [docs/03-试点记录.md](docs/03-试点记录.md) | 单篇实测数据、mermaid 成功/失败两条路径、Phase 0 接口实测清单 |
| [docs/04-分类与合集.md](docs/04-分类与合集.md) | 分类与合集的平台边界（实测探测）、分类标签、合集计划、导览文章、后台勾选清单 |
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

# 3. 复算全语料统计（docs/ 里每个数字的出处，约 4.5 秒）
cd weixin && python3 -m wechat.cli audit

# 4. 转换（不调接口，只产出 HTML）
cd weixin && python3 -m wechat.cli convert <slug>
```

## 命令

| 命令 | 作用 |
| --- | --- |
| `scan` | 逐篇盘点，输出合格/不合格清单 |
| `audit` | 复算全语料统计与 HTML 合规检查 |
| `convert <slug>` | 转换一篇，产出 HTML 到 `out/` |
| `publish <slug>` | 转换 + 上传 + 建草稿（**本号自动化能到的最远一步**） |
| `publish <slug> --publish` | 额外提交发表（该账号会返回 48001，无权限） |
| `categories [名称]` | 列出分类及文章数，或某一个分类下的文章 |
| `collections [名称] [--write]` | 列出合集；`--write` 写出导览文章与后台勾选清单 |
| `publish-collection 名称` | 把合集导览文章推进草稿箱 |
| `status` | 查看所有文章的状态 |

`<slug>` 是文章相对 `source/_posts/` 的路径去掉 `.md`，例如
`db/postgresql/postgresql-logical-replication-add-guc`。

全局选项（`--posts-dir` / `--out-dir` / `--source-url` / `--category-tag`）
写在子命令前后都行。

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `WX_APPID` | 公众号 AppID |
| `WX_APPSECRET` | 公众号 AppSecret（**不要提交到仓库**） |
| `WX_SOURCE_URL` | 站点根 URL，用于拼「阅读原文」，默认 `https://growdu.cn` |
| `WX_COVER` | 封面图路径（未指定时取文章首图） |
| `WX_NOTIFY` | 通知通道：`serverchan` / `wechat_work` / `webhook` |
| `WX_NOTIFY_KEY` | 通知凭据：SendKey / webhook key / 完整 URL |

凭据也可以放进 `weixin/secrets.json`（已在 `.gitignore` 里），避免 secret 落到
shell 历史里。格式见 `secrets.example.json`：

```json
{
  "appid": "wx1234567890abcdef",
  "appsecret": "你的 AppSecret"
}
```

优先级：**命令行参数 > 环境变量 > `secrets.json`**。用 `--secrets-file` 指定别的路径。

合集的手工配置放在 `weixin/collections.json`（同样是本地文件，已 gitignore），
格式见 `weixin/collections.example.json`。文件不存在时，合集按分类自动生成。

### 草稿就绪通知

这个账号发不了表（个人主体被回收了发表接口权限），最后那次点击必须由人做。
所以草稿建好时推一条通知到手机，省得你回后台看。

```bash
export WX_NOTIFY=serverchan
export WX_NOTIFY_KEY=SCTxxxxxxxx     # https://sct.ftqq.com 扫码登录即可生成
```

| 通道 | 凭据 | 说明 |
| --- | --- | --- |
| `serverchan` | SendKey | 直推微信，免费额度每天 5 条（够日更一篇） |
| `wechat_work` | 群机器人 webhook key | 企业微信群机器人 |
| `webhook` | 完整 URL | 任何接受 `{"title","body"}` 的 endpoint（Bark、Discord 等） |

- 新建草稿时通知一次；**复用已有草稿不重复打扰**
- 通知失败只打印警告，**不影响发布结果**
- 不配置就完全安静——没通知不是错误

### 凭据从哪来

登录 [微信公众平台](https://mp.weixin.qq.com/) → 左侧「**设置与开发**」→「**基本配置**」：

| 要的东西 | 在哪 | 注意 |
| --- | --- | --- |
| 开发者 ID (AppID) | 页面右侧「开发者ID」 | 直接可见，`wx` 开头 |
| 开发者密码 (AppSecret) | AppID 下方，点「重置」（首次是「启用」） | 管理员扫码确认，**只显示这一次**，当场复制 |
| IP 白名单 | **在 AppSecret 下方** | 必须先启用 AppSecret，白名单入口才会出现 |

白名单里填的是**调用接口这台机器的公网出口 IP**（不是微信的服务器 IP）。
本机出口 IP：`curl ifconfig.me`。填错会报 `40164 invalid ip not in whitelist`，
报错信息里会带上微信实际看到的那个 IP，直接把它加进去即可。

> ⚠️ **机器上走了代理的话，`curl ifconfig.me` 查到的未必是微信看到的那个**。
> 分流代理对不同目标会用不同出口。实测本机 `curl` 是 `43.166.8.75`，微信看到的
> 是 `171.213.162.214`——照抄报错里的 IP，别照抄 `curl` 的。
> 详见 [docs/02-接口与发布.md](docs/02-接口与发布.md)。

## 实现现状

| 段 | 模块 | 状态 |
| --- | --- | --- |
| 发现 / 校验 | `posts.py` | ✅ 硬限制、permalink、摘要 |
| 解析 | `mdparse.py` | ✅ 纯函数 |
| 渲染 | `render.py` | ✅ inline style，0 个 `class`，原始 HTML 会清洗 |
| 高亮 | `highlight.py` | ✅ Pygments，nowrap + noclasses |
| mermaid | `mermaid.py` | ✅ 失败显式降级为源码块 |
| 资产 | `assets.py` | ✅ 压缩到 ≤ 1 MB、封面裁剪框、外链图下载 |
| 接口 | `publish.py` | ✅ 6 个接口，错误不吞 |
| 幂等 | `state.py` | ✅ 三层键 |
| 通知 | `notify.py` | ✅ Server酱 / 企业微信 / 通用 webhook |
| 分类 / 合集 | `collection.py` | ✅ 分类标签、合集计划、导览文章、勾选清单（**平台上的归属仍是人工**） |
| 站点复用 | `hexo.py` | ✅ 复用 `sync-hexo.py` 的 slugize，分类归档路径与站点一致 |
| 审计 | `audit.py` | ✅ 复算全语料统计与 HTML 合规检查 |
| CLI | `cli.py` | ✅ scan / audit / convert / publish / categories / collections / publish-collection / status |

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
- **分类与合集只能自动化到内容层**：公众号没有开放的分类 / 合集接口，合集还只收已发布文章。工具生成分类标签、合集计划、导览文章和后台勾选清单；**把文章挂到平台上的合集对象上，仍需在后台人工勾选**。
