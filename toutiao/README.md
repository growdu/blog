# toutiao — 博客到头条号的切片与发布

把 `source/_posts/` 下的博客文章裁成**头条版**（3K 精简稿 + 最多 3 张图，0 张也行），
产出发布包交人工上传；账号拿到 API 权限后，同一套代码改为直接调接口。

> **这个目录与 `weixin/` 平级、互不引用。** 两个平台的实现是分开做的，
> 详见 [../publish/spec/00-架构设计.md](../publish/spec/00-架构设计.md) §11.1。

## 现状

- **路线已定（2026-11-11）**：双轨并行——
  轨道 A 半自动出包（**本周就能发**），轨道 B 职业认证（并行解锁 API 权限）
- **账号现状**：未认证，粉丝 < 1000 → **开放平台 API 权限开不了**
  （2026-11-12 实测：后台**连「开放平台」入口都不渲染**，不是灰掉是菜单里没有；
  排查清单见 [docs/02-试点记录.md](docs/02-试点记录.md) §R1）
- **自动化能到的最远一步（当前）**：产出发布包 + 通知，等人工上传
- **实现状态**：切片、渲染、出包、幂等状态、通知、命令行**都已实现**
  （[docs/11-实施计划.md](docs/11-实施计划.md) 的 Task 1~10），**347 条用例**。
  其中 2 条是**语料级回归**——母稿 `source/_posts` 不入库，
  干净检出里它们是 `skipped`（345 passed / 2 skipped），
  本地有母稿时才会真跑（347 passed）。
  逐条任务见 [docs/00-设计.md](docs/00-设计.md)

## 为什么是「裁」而不是「搬」

头条版**不是母稿的搬运**。三条硬约束叠在一起：

| 约束 | 来源 | 后果 |
| --- | --- | --- |
| 标题 ≤ 30 字 | 平台限额 | 标题要重写，不能直接截断母稿标题 |
| 正文**不能用外链图片** | 平台行为 | 每张图都得在编辑器里重新上传 → **图越少越好** |
| 正文放可点击站外 URL 受限 | 外链是独立创作者权益 | 链接降级成纯文本 |

所以头条版是 **3K 精简稿 + 最多 3 张图（0 张也行）+ 纯文本提及博客全文**。
完整版链接由站点反向承担（文章页的跨平台索引区块）。

规则明细见 [../publish/spec/06-发布计划与调度.md](../publish/spec/06-发布计划与调度.md) §6.6。

## 三档自动化

能力模型 `publish/capabilities/toutiao.toml` 里的 `automation` 是数据，**换档改一行**：

| 档 | 前提 | 行为 |
| --- | --- | --- |
| `manual` | 未认证（**当前**） | 产出发布包 + 通知，人工上传 |
| `api_draft` | API 权限开通，但无直接发表权限 | 调 API 建草稿，人工点发表 |
| `api_publish` | API 权限开通且可直接发表 | 调 API 发布，轮询审核状态 |

## 文档

| 文档 | 内容 |
| --- | --- |
| [docs/00-设计.md](docs/00-设计.md) | **实现规格**：模块划分、切片规则、出包结构、幂等、CLI 契约、测试要求 |
| [docs/01-接口与发布.md](docs/01-接口与发布.md) | 开放平台接口、字段限制、OAuth2 绑定、错误码（实测后补） |
| [docs/02-试点记录.md](docs/02-试点记录.md) | Phase 0 实测清单：认证前 / 认证后两阶段，逐步填答 |
| [docs/11-实施计划.md](docs/11-实施计划.md) | **实施计划**：10 个任务，逐条带测试代码与提交命令 |

上位契约：[../publish/spec/00-架构设计.md](../publish/spec/00-架构设计.md)（整体架构）、
[../publish/spec/06-发布计划与调度.md](../publish/spec/06-发布计划与调度.md)（头条号一节）。

## 目录结构

```
toutiao/
├── toutiao/               # Python 包（顶层目录不是包，同名子目录才是）
│   ├── __init__.py
│   ├── cli.py             # 命令行入口
│   ├── contract.py        # 头条版切片规则
│   ├── render.py          # Markdown → 头条 HTML
│   ├── assets.py          # 图片转 webp、封面 3:4 裁切
│   ├── publish.py         # 调 API 或产出发布包
│   ├── state.py           # 幂等状态
│   └── notify.py          # 通知
├── docs/                  # 设计与实测记录
├── tests/                 # 单元 + 集成测试
├── out/                   # 发布包等本地产物（gitignore）
├── secrets.json           # 凭据（gitignore，永不入库）
└── secrets.example.json  # 凭据模板（入库）
```

## 命令

```bash
# 盘点：哪些文章能发到头条号，为什么
cd "$(git rev-parse --show-toplevel)"/toutiao && python3 -m toutiao.cli scan

# 切片 + 出包（不调接口）
cd "$(git rev-parse --show-toplevel)"/toutiao && python3 -m toutiao.cli convert <slug>

# 出包 + 通知（API 权限开通后才是真正的「发布」）
cd "$(git rev-parse --show-toplevel)"/toutiao && python3 -m toutiao.cli publish <slug>

# 查看状态
cd "$(git rev-parse --show-toplevel)"/toutiao && python3 -m toutiao.cli status
```

退出码：`0` 成功 / `1` 参数或配置错误 / `2` 该篇不合格 / `3` 接口或写盘错误。

`<slug>` 是文章相对 `source/_posts/` 的路径去掉 `.md`，
例如 `db/postgresql/postgresql-logical-replication-add-guc`。

每个命令都能把落盘位置指到别处，**但要把每一处都指走**，否则还是会写进仓库：
`--posts-dir` / `--out-dir` / `--outbox-dir` / `--state-file` / `--capability`。
另外三个选项管内容与通知：`--source-url`（正文末尾署名的站点地址）、
`--notify`（通知通道：serverchan / wechat_work / webhook）、`--notify-key`（通知凭据）。
选项写在命令名前后都行。

⚠️ **只指 `--out-dir` 是不够的**：`convert` 会把状态快照写进仓库里的
`publish/outbox/<slug>__toutiao.json`——**那个文件是被 git 跟踪的**，
而快照里的 `package_dir` 会变成相对你那个 `--out-dir` 的路径。
结果就是仓库里多出一处改动，它指向的包却根本不在仓库里。
只在仓库里试跑，就**别传** `--out-dir`；要让仓库完全不动，
`--outbox-dir` 和 `--state-file` 也要一起指走。

**两件事它不会悄悄做**：状态文件损坏会打到 stderr 并让退出码变成 `3`
（空状态读起来就是「什么都没发过」= 再发一遍的起点）；一篇文章切不出来
会退出 `2` 并说明原因，不会「成功地什么都没做」。

## 依赖

| 依赖 | 用途 |
| --- | --- |
| Python 3.11+ | 运行时 |
| pillow | 图片转 webp、封面裁剪（已装） |
| pytest | 测试（已装） |

除上面这些外只用标准库：front-matter 是手写解析器，HTTP 用 `urllib`。
**能力模型的限额用 `tomllib` 读**（3.11 标准库，零依赖）。

## 测试

```bash
cd "$(git rev-parse --show-toplevel)" && python3 -m pytest toutiao/tests -q
```

测试不依赖网络：头条接口用本地假 HTTP server 模拟（绑定 `127.0.0.1`），
手法照抄 `weixin/tests/test_publish.py`。

## 边界

- **发布在本地执行**：与公众号同理，平台侧有 IP / 凭据约束
- **不做静默成功**：每个「成功」都必须显式确认过。发重了比发慢了糟糕得多
- **超限跳过并记录原因**，不做静默截断
- **通知措辞必须区分三种状态**：「待上传」/「待你点发表」/「已发布」——
  含糊说「已发布」是发布场景里最贵的 bug
- **不 import `weixin/`**，也不 import `publish/` 的包——契约只通过
  `capabilities/toutiao.toml` 与 manifest JSON 传递
