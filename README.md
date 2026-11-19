# growdu · 博客与内容生产线

> 一个仓库，三条产线：**技术站点**（growdu.cn）、**品牌视频**（AIV）、**多平台分发**（公众号 / 头条号 / 视频号 / B 站）。
> 共同的底座是 `docs/` —— 那里是所有内容的唯一真相。

本文件是**仓库级总览**：讲清楚整体架构与模块划分。
想改文章、改样式，看 [`docs/blog/架构.md`](docs/blog/架构.md)（站点构建链路，更细）。
想改视频、看契约，看 [`aiv/README.md`](aiv/README.md)。
想改发布逻辑，看 [`publish/spec/00-架构设计.md`](publish/spec/00-架构设计.md) 与
[`publish/spec/06-发布计划与调度.md`](publish/spec/06-发布计划与调度.md)、
[`publish/spec/07-视频发布契约.md`](publish/spec/07-视频发布契约.md)。

---

## 一、整体架构

```text
                        ┌───────────────────────────────────────────┐
                        │              docs/  (唯一真相)           │
                        │   技术文章 · 专题页 · 图片 · 分类 _index.md │
                        └───────────────────┬───────────────────────┘
                                            │
                    ┌───────────────────────┴────────────────────────┐
                    │ tools/sync-hexo.py（内容编译层，纯标准库）        │
                    │  · 剥首个 H1、重写图片与相对链接                │
                    │  · 重建 front matter（推导字段 + 透传白名单）    │
                    │  · 路径排除：什么不是文章                        │
                    └───────────┬───────────────────────┬────────────┘
                                │                       │
                     source/_posts/**          aiv/contracts/*.json
                     （内容单元 content_id）    （视觉分镜契约）
                                │                       │
              ┌─────────────────┴────────┐              │ pyv 渲染引擎
              │ hexo generate            │              │ (cairo + ffmpeg)
              │ + themes/matery          │              ▼
              ▼                          │        storyboard_<EP>.json（产物，不入库）
        public/  →  CI 部署              │              │
        growdu.cn / GH Pages             │        build/<EP>/*.mp4（片段，不入库）
                                         │              │
                                         │              ▼
                                         │        out/<EP>.mp4（成片，不入库）
                                         │              │
                                         └──────┬───────┘
                                                │ publish/publishkit（契约层，平台无关）
                                    ┌───────────┴────────────┐
                                    ▼                        ▼
                     publish/capabilities/*.toml    publish/outbox/*.json
                     （平台能力 = 数据）              （发布结果快照 = 幂等键）
                                    │                        │
                     ┌──────────────┼────────────────────────┘
                     ▼              ▼            ▼            ▼
                  weixin/        toutiao/    channels/    bilibili/
                  （公众号）      （头条号）   （视频号）     （B 站）
                  各自一套 adapter：切片 → 清单 → 出包/API → 人工/自动发布
```

### 三条产线的分工

| 产线 | 输入 | 产物 | 事实来源 |
| --- | --- | --- | --- |
| 技术站点 | `docs/` | 静态站 `public/` | `docs/` |
| 品牌视频 AIV | `aiv/contracts/*.json` + 口播稿 + 旁白 | 1920×1080 成片 | 契约 + 规范文档 |
| 多平台分发 | `source/_posts/` 内容单元 + 能力声明 | 草稿 / 出包 / 已发链接 | `docs/`（内容）+ `publish/outbox/`（状态） |

---

## 二、模块划分

### 2.1 全局分层

| 层 | 位置 | 职责 | 允许依赖 |
| --- | --- | --- | --- |
| **内容层** | `docs/` | 母稿、图片、分类元数据 | 无（纯内容） |
| **内容编译层** | `tools/` + `scripts/` | `docs/` → Hexo 源、主题补丁、校验 | 只读 `docs/`，只写 `source/` |
| **展示层** | `themes/matery/` | EJS 模板、CSS/JS、静态资源 | Hexo 运行时 |
| **视频生产层** | `aiv/` | 契约 → 时间轴 → 片段 → 成片 | 只读自己的契约与素材 |
| **审核层** | `review/`、`aiv/review/` | 审校规则、一期一条记录、抽帧清单 | 只读 `docs/`、`aiv/` 的契约与产物 |
| **发布契约层** | `publish/publishkit/` | 内容契约 / 能力模型 / manifest / 调度 | **不认识任何平台** |
| **平台适配层** | `weixin/` `toutiao/` `channels/` `bilibili/` | 平台切片、渲染、出包、发布、状态 | 只认 TOML 与 manifest JSON |

**依赖方向是单向的**：平台层不 import 契约层，契约层不 import 平台层。
两边唯一的接缝是**同一份 `capabilities/*.toml`** 与**同一份 manifest JSON**。
这条规矩由 `publish/tests/test_capability_compat.py` 之类的一致性测试守住。

### 2.2 站点构建链

| 模块 | 位置 | 干什么 |
| --- | --- | --- |
| 内容编译 | `tools/sync-hexo.py` | `docs/` → `source/_posts/` + `source/images/`，重建 front matter，生成分类/标签/关于等页面与旧 URL 的重定向页 |
| 主题补丁 | `tools/patch-theme.py` | marker-based 幂等注入：SEO meta、相关文章、PV、OG 卡片等 |
| 素材搬运 | `tools/copy-vendor.py` | logo、打赏图 → 主题 `medias/` |
| 内容校验 | `tools/check-markdown.py` / `fix-markdown.py` | front matter、链接、格式校验与修复 |
| 契约闸门 | `tools/check-content-contract.py` | 按内容契约校验所有内容单元，违规退出码 1（CI 用） |
| CDN 本地化 | `tools/localize-cdn.py` | 把主题的 jsDelivr CDN 换成本地资源（国内访问） |
| 评论初始化 | `tools/init-gitalk-issues.js` | 为新文章预创建 Gitalk issue |
| Hexo 扩展 | `scripts/*.js` | filter/helper：mermaid 渲染、HTML 文章处理、智能摘要 |
| 主题 | `themes/matery/` | 站点外观；覆盖配置在根目录 `_config.matery.yml`（**不要改主题自带的 `_config.yml`**） |

配置分工：`_config.yml` 是 Hexo 自身的；`_config.matery.yml` 是对主题的覆盖。
`source/` 与 `public/` 都在 `.gitignore` 里，CI 现生成。

### 2.3 AIV 视频生产线

| 模块 | 位置 | 干什么 |
| --- | --- | --- |
| 视觉分镜契约 | `aiv/contracts/<期>.json` | 一期视频的段落划分、画面文案与数字（**每期只写这里**） |
| 发布元数据 | `aiv/publish/<期>.json` | 每期各平台的标题、简介、话题与分区（`pyv publish check` 体检） |
| 渲染引擎 | `aiv/pipeline/pyv/` | `pyv/cli.py` + `scenes/` + 28 个模块：`align`/`render`/`compose`/`timeline`/`subtitle`/`bgm`/`brand`/`persona`/`topics`/`doctor`/`preflight`/`review`/`layout`/`components`/`fingerprint`… |
| 审核 | `aiv/review/` + `pyv/review.py` | 文本层 `VT-*` 与成片层 `VV-*` 的规则、一期一条记录、抽帧清单 |
| 时间轴 | `storyboard_<EP>.json` | 由旁白对齐算出的产物，**不入库** |
| 场景模板 | `aiv/pipeline/pyv/scenes/*.py` | 位置、尺寸、配色、动效等版式常量 |
| 形象 | `aiv/character/scripts/` | 3D 小象生成、加眼镜、铭牌盖章 |
| 品牌 | `aiv/brand/scripts/` | 片头/片尾渲染与配乐 |
| 音色 | `aiv/voice/scripts/` | 旁白合成、读音验收（多音字） |
| 音乐 | `aiv/music/` | 授权台账（入库）+ 曲库文件（不入库） |
| 规范文档 | `aiv/*.md` | 人格规范、形象与音色规范、背景音乐规范、选题库 |
| 发布副本同步 | `aiv/scripts/sync_publish_docs.py` | 把面向读者的文档同步到 `docs/life/aiv/`（博客发的是副本） |

**核心规矩**：文案与数字进契约，版式常量留代码。
契约少参数 → 渲染前抛 `MissingParam`；契约里的文案不许回流成场景代码里的字面量
（`pipeline/tests/test_contract.py` 盯这条）。

流水线按期号切：`make EP=<期号> align|validate|brand|render|compose`。
`align` 是手工步骤（需要旁白音频），其余可全自动。

同一套还有几档变体与审校命令：

| 命令 | 干什么 |
| --- | --- |
| `make EP=<期号> nobrand` | 无品牌导流版（抖音那一档，去品牌片头/片尾；`NOBADGE=1` 再去铭牌） |
| `make EP=<期号> vertical` | 9:16 竖版画布（抖音那一档，本来就不套品牌片） |
| `make EP=<期号> mix-verify` | 成片级混音验收（稳态 duck 深度、电平差、真峰值） |
| `make EP=<期号> review-text` | 审校·文本层（`VT-*`）：审要讲什么 |
| `make EP=<期号> review-video` | 审校·成片层（`VV-*`）：审做出来是什么样 |
| `make EP=<期号> review-frames` | 抽帧 + 清单：每段两帧 + 关键帧，给人和 Agent 逐帧看画面 |

审校的规则与边界见 [`aiv/review/README.md`](aiv/review/README.md)。

### 2.4 发布契约层（`publish/publishkit/`）

平台无关，只回答「发什么、怎么切、按什么规则触发」，不管「怎么发」。

| 模块 | 职责 |
| --- | --- |
| `contract.py` | 内容契约：母稿 front matter 的字段表与格式规则（扁平 `key: value` + 单层列表） |
| `capability.py` | 能力模型：读 `publish/capabilities/<platform>.toml`，严格校验后交给 adapter |
| `manifest.py` | 发布清单：一个内容单元 × 一个平台的纯数据（可重放、无时间戳、无凭据） |
| `schedule.py` | 调度层：候选集、选题规则、ISO 周键、调度状态文件 |
| `cli.py` | 命令行入口：`schedule weekly/status/candidates`、`publish <content_id> --platform <id>` |

配套资产：

| 路径 | 内容 |
| --- | --- |
| `publish/capabilities/*.toml` | 平台限额与自动化档位（**数据不是代码**，平台规则变了改这里） |
| `publish/outbox/*.json` | 发布结果快照（幂等键 + 站点发布索引的数据源） |
| `publish/schedule.json` | 调度状态，按周键幂等 |
| `publish/spec/*.md` | 契约规格（架构设计 / 调度 / 视频发布） |
| `publish/deploy/*.template` | crontab、launchd、GitHub Action 模板 |
| `publish/tests/` | 契约、能力、清单、调度、CLI 的测试 |

### 2.5 平台适配层

四个 adapter **同构布局**，彼此独立：

| 平台 | 目录 | 形态 | 自动化档位 |
| --- | --- | --- | --- |
| 微信公众号 | `weixin/wechat/` | 图文 → 草稿箱（`draft/add`） | 自动生成 + 自动进草稿箱，**发表由人点**（账号无发表接口权限） |
| 今日头条 | `toutiao/toutiao/` | 图文 → 头条版排版包 / 半自动出包 | `manual`（能力声明）：出包 + 人工发（账号未认证，API 权限开不了） |
| 微信视频号 | `channels/channels/` | 视频 → 切片 + 人工发布清单 | `manual`：视频号无普通创作者发布接口 |
| 哔哩哔哩 | `bilibili/bilibili/` | 视频 → 投稿包 + 字幕 | `manual`（`ARC_BASE` 权限开通后可转 `api_publish`） |

每个 adapter 的典型模块：`assets.py`（素材）、`contract.py`（平台契约）、
`render.py`/`package.py`（渲染/打包）、`state.py`（状态）、`snapshot.py`（快照）、
`notify.py`（通知）、`cli.py`（命令行），外加 `docs/`（设计与实施计划）与 `tests/`。

公众号线最成熟：`weixin/wechat/` 20 个模块，覆盖 Markdown 解析、封面、标题裁剪、
超长文章拆分、SVG/代码高亮、mermaid、合集与分类、品牌图文，已跑到草稿箱。

---

## 三、关键设计原则

1. **母稿唯一**：任何平台产物都能从 `content_id` 重建；真相只在 `docs/`。
2. **可重放 vs 有状态**：切片与渲染是纯函数，随便重跑；只有「发布」有状态，
   幂等键由 `publish/outbox/` 与 `publish/schedule.json` 承载。
3. **不静默成功**：平台的「成功」必须是**被显式确认过**的成功。发重了比发慢了糟糕得多。
4. **能力即数据**：平台限额与自动化档位在 TOML 里，不在 Python 里。
5. **只有一处接缝**：契约层与 adapter 互不 import，认的是同一份 TOML 与同一份 manifest JSON。
6. **入库的是事实，产物不入库**：音视频、时间轴、成片留在本机；入库的是规范、契约、台账、代码。
7. **规范公开，工程内部产物下线**：面向读者的规范在 `docs/` 发一份，工程内部留在仓库里。

---

## 四、数据契约速查

| 契约 | 文件 | 生产者 | 消费者 |
| --- | --- | --- | --- |
| 内容契约（front matter） | `docs/**` 的 front matter | 作者 | sync-hexo → Hexo → 各 adapter |
| 平台能力 | `publish/capabilities/<id>.toml` | 手写（对着平台文档复核） | publishkit + adapter |
| 发布清单 manifest | JSON（内存/落盘） | publishkit | adapter |
| 视觉分镜契约 | `aiv/contracts/<EP>.json` | 作者 | pyv 渲染引擎 |
| 发布元数据 | `aiv/publish/<EP>.json` | 手写 | `pyv publish check` + 各平台 adapter |
| 抽帧清单 | `aiv/review/frames/<EP>/frames.md` | 审核工具 | 审核记录（逐帧复核） |
| 发布结果快照 | `publish/outbox/<content>__<platform>.json` | adapter | 幂等判定 + 站点发布索引 |
| 调度状态 | `publish/schedule.json` | 调度层 | 调度层（周键幂等） |

---

## 五、目录速查

| 路径 | 内容 | 是否入库 |
| --- | --- | --- |
| `docs/` | 内容母稿（唯一真相） | ✅ |
| `source/` | Hexo 源（CI 生成） | ❌ 仅 `all/`、`recommended/` |
| `public/` | 构建产物 | ❌ |
| `themes/matery/` | 主题 | ✅ |
| `tools/`、`scripts/` | 构建与校验脚本 | ✅ |
| `aiv/` | 视频生产线（规范 + 契约 + 代码） | ✅ 产物除外 |
| `aiv/build/`、`aiv/out/` | 片段与成片 | ❌ |
| `review/`、`aiv/review/` | 审校规则、一期一条记录、抽帧清单 | ✅ 帧除外 |
| `publish/` | 契约层、调度、能力声明、outbox | ✅ |
| `weixin/` `toutiao/` `channels/` `bilibili/` | 平台 adapter | ✅ |
| `requirements/` | 依赖清单（按模块分文件） | ✅ |
| `.github/workflows/` | `hexo.yml`（构建部署）、`contracts.yml`（契约闸门） | ✅ |

---

## 六、常用命令

```bash
# 站点
npm run sync          # docs → source（等价 tools/sync-hexo.py）
npm run build         # hexo generate
npm run server        # 本地预览

# AIV 视频（cd aiv/pipeline）
make test             # 全量测试
make topics           # 选题库规则检查
make persona          # 人格规范检查
make EP=<期号> all    # validate → brand → render → compose
make EP=<期号> mix-verify     # 成片级混音验收
make EP=<期号> review-text    # 审校·文本层（VT-*）
make EP=<期号> review-video   # 审校·成片层（VV-*）
make EP=<期号> review-frames  # 抽帧 + 清单（帧不入库，清单入库）

# 发布调度
cd publish && python3 -m publishkit.cli schedule candidates
cd publish && python3 -m publishkit.cli schedule weekly --dry-run
cd publish && python3 -m publishkit.cli schedule status

# 契约闸门
python3 tools/sync-hexo.py                 # 先产出内容单元
python3 tools/check-content-contract.py   # 校验 568 个内容单元，违规退出码 1
```

---

## 七、开发环境

依赖清单在 [`requirements/`](requirements/README.md)，**按模块装**：

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/publish.txt    # 契约层与调度层（零运行时依赖）
pip install -r requirements/weixin.txt     # 公众号 adapter
pip install -r requirements/aiv.txt        # AIV 视频生产线
```

pip 装不了的系统依赖：`ffmpeg` / `ffprobe`（出片与切片）、中文字体（封面与字幕）、
cairo 的头文件（`pycairo`）。

### CI 闸门

| 工作流 | 干什么 | 触发 |
| --- | --- | --- |
| `hexo.yml` | 构建与部署 | push 到 master |
| `contracts.yml` | 内容契约 + 契约层 / 头条 / 公众号测试 | push 或 PR 到 master |
| `aiv-pipeline.yml` | 在 Ubuntu 上真跑一遍 AIV：装系统依赖与内置字体，跑全部测试（含真的合成出一段成片） | push / PR 到 master 且动了 `aiv/**` |
| `site-guard.yml` | 根级站点契约测试：部署工作流的形状、文档死链与页内锚点、站点根路径前缀 | push 或 PR 到 master |

`contracts.yml` 里的四步：产出内容单元 → 内容契约闸门（违规即失败）→
契约层测试 → 两个 adapter 的测试。视频线（aiv）不在里面：它要 cairo 与
ffmpeg 这套系统依赖，失败模式是「渲染不出片」而不是「契约被破」；
它有自己的 `aiv-pipeline.yml`——在 Linux 上装依赖、装内置字体，跑全部测试，
测试里**真的会合成出一段成片**并按规格核对（逐像素基准那条在 Linux 上会
跳过并说明原因，不是红，也不是假装绿）。

`site-guard.yml` 跑的是根级 `tests/`：这些测试以前只在本机跑，CI 里没有任何
地方执行它们，于是「测试全绿」和「CI 绿」是两件事。它**不阻塞部署**
（独立工作流、独立并发组），挂了只报注解。

### 给一篇文章声明发布平台

发布候选集的**唯一依据**是母稿 front matter 里的 `platforms`：

```yaml
---
platforms:
  - toutiao
  - wechat
---
```

不写 `platforms` 的文章不进任何平台的候选集——这是内容契约 §4.1 的规定，
不是调度器的默认行为。声明之后：

```bash
cd publish && python3 -m publishkit.cli schedule candidates   # 看候选集
cd publish && python3 -m publishkit.cli schedule weekly --dry-run
```

---

## 八、当前状态

| 模块 | 状态 |
| --- | --- |
| 站点构建 | 成熟，CI 全自动（2~3 分钟） |
| 内容契约 | 闸门已进 CI（`contracts.yml`）；568 个内容单元 0 违规 |
| 公众号 | 已实现到**草稿箱**；发表接口无权限（`48001`），自动化边界 = 自动进草稿箱；**已进契约层**（能力声明 + outbox 幂等键） |
| 头条号 | 出包可用；账号未认证，API 权限开不了，走「出包 + 人工发」 |
| 视频号 / B 站 | 出包 + 人工发布清单；B 站 `ARC_BASE` 未开通 |
| AIV | 六期已出片（EP01~EP06）；契约化流程稳定；抖音那两档（无品牌 / 竖版）已就位 |
| 审校 | 文档侧（`review/`）与视频侧（`aiv/review/`）两套机制都落地了；视频侧六期文本层跑完，成片层只有本机有成片的 EP06 跑过 |
| 发布调度 | 契约层与 CLI 已落地，周键幂等已接上；候选集由母稿 `platforms` 决定 |

**平台与契约层的关系**（四个平台，两个档位）：

| 平台 | 能力声明 | 幂等键写在哪 | 自动化停在哪 |
| --- | --- | --- | --- |
| 公众号 | `wechat.toml` | `publish/outbox/`（入库） | 草稿箱（人工发表） |
| 头条号 | `toutiao.toml` | `publish/outbox/`（入库） | 出包（人工上传） |
| 视频号 | `channels.toml` | `publish/outbox/`（入库） | 出包 + 人工发布清单 |
| B 站 | `bilibili.toml` | `publish/outbox/`（入库） | 投稿包（`ARC_BASE` 未开通） |

**还没就绪的三处**（详见各 spec 的「待验证项」）：

1. 站点**看不到视频**：video widget 关着、菜单无视频入口、outbox 也没汇总成
   `publish_index`。
2. 调度器**从未真正跑过**：`publish/deploy/` 里的 cron / launchd 模板还没安装，
   `publish/schedule.json` 仍是空的。
3. **视频审校还没闭环**：六期的文本层信号已出，成片层只有本机有成片的 EP06 跑过；
   「改稿 → 重出片 → 复审成片层」这一圈还没走完（见 `aiv/review/INDEX.md` 的批次表）。

---

## 九、延伸阅读

| 文档 | 内容 |
| --- | --- |
| [`docs/blog/架构.md`](docs/blog/架构.md) | 站点构建链路的操作手册（改文章、改样式、CI 步骤） |
| [`publish/spec/00-架构设计.md`](publish/spec/00-架构设计.md) | 多平台发布架构：内容契约 · 能力模型 · 清单 · 幂等 · 展示扩展点 |
| [`publish/spec/06-发布计划与调度.md`](publish/spec/06-发布计划与调度.md) | 调度层：候选集、选题规则、周键、触发器、失败与重试 |
| [`publish/spec/07-视频发布契约.md`](publish/spec/07-视频发布契约.md) | 视频发布：视频单元、成片预检、切片规则、状态机 |
| [`aiv/README.md`](aiv/README.md) | 视频生产线说明与换期流程 |
| [`aiv/review/README.md`](aiv/review/README.md) | 视频审校：文本层 `VT-*` 与成片层 `VV-*`、抽帧方法、一期一条记录 |
| [`review/README.md`](review/README.md) | 博客内容审校：文档侧的同构机制（`tools/review-check.py`） |
| [`aiv/人格规范.md`](aiv/%E4%BA%BA%E6%A0%BC%E8%A7%84%E8%8C%83.md) | 小象是谁、怎么想、怎么讲（9 条可机检规则） |
| `weixin/docs/`、`toutiao/docs/`、`channels/docs/`、`bilibili/docs/` | 各平台 adapter 的设计与实施计划 |
