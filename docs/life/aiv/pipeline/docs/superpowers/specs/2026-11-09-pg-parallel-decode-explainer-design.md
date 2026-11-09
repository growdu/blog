# 并行解码讲解片 · 代码驱动动画 + MiniMax Design 协作设计

- 日期：2026-11-09（v2，按 Design 项目实况与第三方口径修订）
- 目标成片：`docs/life/aiv/` 下的「逻辑复制 · 并行解码」讲解片
- 叙事口径：**独立开发者 / PostgreSQL 社区贡献者视角**，全程不出现公司名、品牌、产品、Logo、客户
- 分工模式：**本地代码渲染全部画面 → 本地 ffmpeg 合成 → 导入 MiniMax Design 做终审与多平台导出**
- 画面来源：技术图示与角色动作全代码；H3 仅用于 3 秒质感片头（768P，210 积分）

---

## 1. 背景与目标

原方案用 H3 逐段生成全部画面：2 段 13 秒（各 1560 积分）+ 1 段 9 秒（1080 积分）= 35 秒 / 4200 积分。
H3 2K 单价为 **120 积分/秒**（1560÷13 = 1080÷9 = 120），成本由单价决定，不是分段策略失误。

本片以技术图示为主（reader→worker 数据流、32 核只占 1 核、2–5 倍、提交顺序一致性），
这类内容由规则描述、由代码绘制最准确，且**不消耗任何积分**。

**目标**

| 项 | 指标 |
| --- | --- |
| 积分消耗 | ≤ 350（原 4200，降 ≥ 91%） |
| 画面准确性 | 文字、数字、机制图示零模型生成，改一处只重渲一个场景 |
| 旁白 | 第三方口径重录，音色与前系列一致，原 34.488s 音频保留归档 |
| 可回溯 | 一场景一模块、一模块一提交；契约 `storyboard.json` 入库 |
| 交付 | 1920×1080 / 24fps 成片 + Design 多平台导出 |

**非目标（YAGNI）**：不做 9:16 竖版自动化（交 Design 多平台导出）；不做本地 H3 自托管；
不让模型修改已渲染画面；不做背景音乐（本片无 BGM）；不做智能混音与 ducking。

---

## 2. 已核验的事实基线

### 2.1 素材现状

| 资产 | 规格 | 用途 |
| --- | --- | --- |
| `growdu.png` | 白底**透明底**扁平矢量小象，1220×1289，RGBA（42.8% 透明像素） | **唯一形象原图**：部件切分、2D 动作、H3 参考图都用它 |
| `pa_decode.mp3` | 34.488s / mp3 / 32kHz / 单声道 | 旧旁白（公司口径），**保留归档，不再使用** |
| `pa_decode_v2.mp3` | 29.599s / mp3 / 32kHz / 单声道 | **新旁白**（第三方口径，同音色重录） |
| `字幕-并行解码.md` | 11 句口播稿 + 字幕表 + 出处表 | 唯一文案契约 |
| `并行解码动画分镜与制作方案.md` | Design 项目内策划（15:35） | 上游策划基线：6 段分镜、视觉风格、事实边界 |
| `growdu.jpg` | 2048×2048 个人头像 | 落版用（**替代任何公司 Logo**） |

> 仓库路径已从 `docs/db/aiv/` 迁至 `docs/life/aiv/`（2026-11-09 17:11 目录重组）。本设计与 pipeline 均以新路径为准。

**明确排除**：`docs/db/logical_decode/pa_decode/` 目录下的所有图片（`image.png`、`image-1.png` 等）
不作为形象来源，避免系列内形象不一致。`growdu.png` 已复制到项目内 `docs/life/aiv/`，
pipeline 不依赖 Design 项目目录（`~/Movies/Hub/Projects/.projects/...`）的路径。

### 2.2 工具链（本机已装）

`ffmpeg/ffprobe 8.1`、`python3 3.11`（`cairo` `PIL` `numpy` `matplotlib` 可用，`manim` 未装且**不打算装**）、
`node 25.7`。技术图示与 2D 部件动画用 cairo + PIL 足够。

**字体**：固定 `PingFang SC`（macOS 自带）。`palette.py` 启动时校验字体可加载，缺失即报错退出，不静默降级。

### 2.3 视觉规则（以 Design 策划 + 新小象取色为准）

| 用途 | 色值 | 来源 |
| --- | --- | --- |
| 背景 | `#FFFFFF` 明亮白底 | Design 策划 |
| 主色（结构线、标题、图表） | `#2B4C7E` 深蓝 | 小象背心与描边 |
| 强调（数字、高亮、结论） | `#F5A623` 橙黄 | 小象数据库图标 |
| 次强调（解决段、正确性） | `#4FD1C5` 青 | 既有系列配色 |
| 点缀（面颊、亲和力） | `#F8BBD0` 粉 | 小象面颊 |
| 问题段 | `#F6AD55` 橙 | 既有系列配色 |

**字幕**：底部居中，**深蓝字 `#1B2A47` + 白色描边**，底部加极淡渐变蒙版保证可读。
⚠️ 与 Design 策划里"白字黑描边"冲突：白底视频上白字不可读，此处以可读性为准（需向用户确认）。

### 2.4 MiniMax Design 的能力边界（已核验）

- 「本地优先」仅指画布素材存本机，生成算力全在云端；第三方模型不可本地跑。
- **语义编辑不稳**（调色几乎无效、换背景主体变形）；分镜、剪辑、字幕、裁切、转场可用。
  → 分工原则：**模型只生成，不修图；像素级确定的操作走 ffmpeg/ASS**。
- H3 2K = 120 积分/秒（实测）；768P ≈ 70 积分/秒（公开换算口径）。
- **套餐积分只在 Design 客户端内消耗**；直接调用开放平台 H3 V2 API 走 API 余额，不扣套餐积分。
- 本地跑 H3 权重需 NVIDIA CUDA，Apple Silicon 不成立。

### 2.5 画布架构 v3（已核验，**推翻了 v1 写回配方**）

新项目 `Movies/Hub/Projects/.projects/grow du/decode/` 的画布不是 v1 的扁平 asset 节点，而是 **composition 图**：

```
resources(res_*)                → 导入的文件（音频/图片/文档）
  └─ compositions(cmp_*)        → 合成体，type 取自 composition_types（视频/图片…）
       └─ composition_members    → composition ↔ member ↔ resource_id（按 position 排序）
canvas-v3/state.sqlite
  ├─ document(id=1)             → {schemaVersion, revision, nodes:{id:{kind:"composition",compositionId,…}}, edges:{}}
  └─ receipts                   → {command_id → request_hash, applied_revision, effects_json}
index.sqlite                    → resources / compositions / project_composition_commands / canvas_command_journal …
```

结论与影响：

- v1 那种「插一行 assets + 加一个带 `data.path` 的 video 节点」**不适用于 v3**：v3 节点是 composition 引用，
  要新增一个视频节点必须同时写 `resources` → `compositions` → `composition_members` → canvas 节点 →
  `revision` → `receipts`/`canvas_command_journal`，是跨表事务协议，且随版本变动。
- 应用**正在运行**（`index.sqlite-wal` 1.5MB 持续增长），并发写库有损坏风险。
- 因此**放弃直接改 Design 数据库**。改用官方通道：本地合成成片 → 导入 Design（拖拽或 IM 派活给 Design 的 agent）。

### 2.6 叙事口径（硬性约束）

以**独立开发者 / PostgreSQL 社区贡献者**身份讲述上游特性。

- 可出现：PostgreSQL 18、reader / worker、逻辑复制、WAL、commit 顺序等公开技术概念；
  上游设计稿与补丁中已公开的机制；作者本人压测结论（须标注为个人实测）。
- 不可出现：公司名、品牌、产品名、Logo、客户名、内部项目代号、内部人员、未公开数据。
- 落版用个人头像 `growdu.jpg`，不用任何公司 Logo；角色仅用 `growdu.png`（胸牌为个人标识）。

### 2.7 已确认决策（用户裁定）

| 项 | 决定 | 说明 |
| --- | --- | --- |
| 角色术语 | **reader** | 不用 leader；字幕固定写 `reader`，图示标注 `Reader (WALSender)` |
| 形象原图 | **仅 `growdu.png`** | 部件切分、2D 动作、H3 参考图统一用它 |
| pa_decode 目录图片 | **一律不用** | `docs/db/logical_decode/pa_decode/image*.png` 全部排除 |
| 字幕样式 | 深蓝字 `#1B2A47` + 白描边 + 底部淡渐变蒙版 | ⚠️ 暂定值：Design 策划原文为"白字黑描边"，白底上不可读，用户尚未明确回复 |
| 成片时长 | 29.599 秒（新旁白实测） | ⚠️ 暂定值：用户尚未回复是否补一句恢复 34.5 秒节奏 |
| 画面风格 | 明亮白底、蓝色主色、橙黄强调 | 沿用 Design 策划，与新小象取色一致 |

> 两项暂定值（字幕样式、成片时长）已写入 `storyboard.json` 的 `subtitle_style` 与 `video.duration`，
> 改动只需改这两个字段并重跑 `make render compose`，无需改代码。

---

## 3. 方案总览

```
                    ┌──────────── 本地（0 积分）────────────┐
 pa_decode_v2.mp3 ─▶│ align.py ─▶ storyboard.json ─▶ pyv/scenes/*.py
 29.599s 新旁白     │                    │                │  cairo 逐帧渲染
                    │                    │                ▼
                    │                    │        build/scene-*.mp4
                    │                    │                │  ffmpeg concat + ASS 烧字幕
                    │                    │                ▼
                    │                    │        out/pg-parallel-decode.mp4
                    │                    │                │
                    │                    │        导入 Design（官方通道）
                    └────────────────────┼────────────────┘
                                         ▼
                    ┌──────── MiniMax Design（消耗套餐积分）────────┐
                    │ 终审 → 多平台导出 / 封面                        │
                    │ H3 768P 质感片头 3s（210 积分）                 │
                    └────────────────────────────────────────────────┘
```

**职责边界**

| 环节 | MiniMax Design | 本地代码 |
| --- | --- | --- |
| 角色一致性、跨镜头形象 | ✅ 资产中心（参考图） | 读 `growdu.png` 做部件切分 |
| reader→worker、32 核、2–5 倍、提交顺序 | ❌ 模型写不对 | ✅ 精确绘制 |
| 小象挥手/点头/指示 | 少量质感镜头 | ✅ 2D 部件动画 |
| 文字、数字、字幕 | ❌ | ✅ ASS 烧制 |
| 旁白 | 保留音频 | ✅ 按时间码对齐，0 成本 |
| 时间线合并、成片输出 | 导入后终审 + 多平台导出 | ✅ ffmpeg 主合成 |
| 逐项检查 | ✅ 节点级检查点 | 自动校验（时长/字幕/响度） |

---

## 4. 目录与契约

```
docs/life/aiv/
├── growdu.png                  # 角色源（白底矢量小象）
├── growdu.jpg                  # 个人头像（落版）
├── pa_decode.mp3               # 旧旁白（归档，不用）
├── pa_decode_v2.mp3            # 新旁白（第三方口径，29.599s）
├── 字幕-并行解码.md             # ★ 文案契约（口播稿 + 字幕表 + 出处 + 禁止项）
├── storyboard.json             # ★ 时间轴契约
├── pipeline/
│   ├── pyv/                    # 引擎包
│   │   ├── canvas.py           # cairo 绘制封装
│   │   ├── palette.py          # 配色与字体常量（§2.3）
│   │   ├── easing.py           # 缓动函数
│   │   ├── timeline.py         # 场景装载与时间码校验
│   │   ├── subtitle.py         # ASS 生成
│   │   ├── align.py            # 旁白静音切分 → 时间码草稿
│   │   ├── render.py           # 逐帧渲染 + ffmpeg 编码
│   │   ├── compose.py          # concat + 混音 + ASS 烧制
│   │   ├── elephant.py         # 小象部件切分与 2D 动作
│   │   └── scenes/             # 一场景一模块（s01_hook.py …）
│   ├── tests/                  # pytest：单测 + 集成
│   ├── Makefile                # make align / render / compose
│   └── docs/superpowers/specs/ # 本设计文档
├── build/                      # 渲染产物（不入库）
└── out/                        # 成片（不入库）
```

### `storyboard.json`

```json
{
  "version": 1,
  "video": { "width": 1920, "height": 1080, "fps": 24, "duration": 29.599 },
  "audio": { "narration": "pa_decode_v2.mp3", "bgm": null },
  "subtitle_style": { "primary": "#1B2A47", "outline": "#FFFFFF", "position": "bottom-center" },
  "scenes": [
    { "id": "s05", "start": 10.82, "end": 13.02, "type": "code",
      "renderer": "pyv.scenes.s05_core_32cores",
      "subtitle": "32 核机器 解码只占 1 核",
      "params": { "highlight": "#F5A623" } }
  ]
}
```

规则：

- `type` ∈ `code` | `h3`。`h3` 场景只登记镜头参数与预估积分，**本地不调用任何生成 API**；
  镜头在 Design 内生成后落到 `build/h3/` 再接入。
- 场景按 `start` 升序、首尾相接无缝无重叠，总时长 = 旁白时长。
- 每场景覆盖 1 句旁白，边界取静音点。

---

## 5. 分镜结构

沿用 Design 策划的 **6 段主结构**，把 11 句口播分配进去；时间码按新旁白重算。

| 段 | 旁白句 | 画面 | 来源 |
| --- | --- | --- | --- |
| A | 我是关注数据库内核的独立开发者 / 今天聊聊 PostgreSQL 18 的并行逻辑解码 | 小象左侧轻挥手，右侧出现发布端→订阅端概览 + 标题 | H3 768P 3s + code 叠加 |
| B | 常规逻辑复制效率不高 / 发布端只有一个解码线程串行处理 | 聚焦发布端，多个事务块排队依次通过一个 decoder，队列积压 | code |
| C | 32 核机器 解码只占 1 核 / 大事务小事务高并发都跟不上 | 32 个核心方格只亮一个；大小事务数据块分别排队 | code ★ |
| D | reader 读取协调 多 worker 并行解码 | 单通道扩展为 reader→多 worker 并行路径，数据块分发后汇入统一输出节点 | code ★ |
| E | 订阅端顺序与发布端保持一致 / 整体性能提升 2 到 5 倍 | 数据块汇聚后按 1、2、3、4 编号顺序输出；「2–5 倍」数字大字 | code ★ |
| F | 异构数据同步场景实用性很高 | 输出节点连接多种数据库图标；小象点头，定格「并行解码 · 有序同步」+ 个人头像落版 | code |

**时长变化说明**：旧旁白 34.488s → 新旁白 29.599s（改口径后语料更紧凑）。
Design 策划里的时间点（0–6.5 / 6.5–13 / 13–19 / 19–26 / 26–31 / 31–34.488）随之作废，由 `align.py` 重算。
若需保持原节奏，可补一句收尾语并重录（TTS 一次调用即可）。

---

## 6. 渲染引擎

- 技术选型：cairo 逐帧绘制 → rawvideo 管道喂 ffmpeg → 单场景无声 mp4（1920×1080 / 24fps / H.264 yuv420p）
  → concat → 混旁白 → ASS 烧字幕。
- 场景是纯函数式 `render(ctx, t_local)`，`t_local ∈ [0,1]`，无全局状态 → 可单测、可重放、可单场景重渲。
- 小象 2D 动画：`elephant.py` 从 `growdu.png` 切出部件（头/双耳/双臂/鼻/胸牌/数据库图标），
  用旋转 + 位移 + 缓动驱动；动作限于挥手、点头、轻微转动、指向。**不做口型**（无模型视频即无口型需求）。
  白底矢量图便于按几何与颜色分离部件，无需抠图模型。
- 旁白：`pa_decode_v2.mp3` 原样保留，不变速、不重录、无 BGM。
- 字幕：`pyv/subtitle.py` 生成 ASS，样式按 §2.3，时间码直接来自 `storyboard.json`。

---

## 7. 与 MiniMax Design 的协作

### 7.1 主路径（可靠，走官方通道）

1. 本地渲染 6 段（或 11 句细分）分镜片段 → `build/`
2. 本地 ffmpeg 合成成片 → `out/pg-parallel-decode.mp4`（含旁白与字幕）
3. 把成片**导入 Design**：拖入画布，或 IM 派活给 Design 的 agent 执行导入
4. Design 内做终审、封面、多平台导出

### 7.2 H3 镜头登记（积分只在这里花）

| 项 | 规格 | 积分 | 位置 |
| --- | --- | --- | --- |
| H3-01 片头质感（小象入场） | 768P / 3s / I2V，参考 `growdu.png` | 210 | Design 内生成 |
| 封面图 | 复用 `growdu.png`，**不额外生成** | 0 | — |
| **合计** | 3 秒模型画面 | **210** | |

规则：768P 预演，2K 只留给最终选中的镜头；预算按镜头数而非片长规划。

### 7.3 明确不做

- ❌ 不直接写 `.hilo/index.sqlite` 或 `canvas-v3/state.sqlite`（composition 协议跨表且随版本变动；应用运行中）
- ❌ 不靠 Design 的语义编辑修图
- ❌ 不在 Design 里做逐帧合成（像素级确定的操作一律本地做）

---

## 8. 提交节奏与测试策略

遵守既定偏好：**每个子模块完成立即提交；每次提交配套单元测试 + 集成测试，且测试通过。**

| 里程碑 | 内容 | 提交 | 配套测试 |
| --- | --- | --- | --- |
| M0 | 骨架 + 契约校验器 + **导入通道验证**（成片能否被 Design 正常接收与导出） | `chore` | 契约校验单测；导入为人工验证项 |
| M1 | `align.py` 对齐新旁白 → `storyboard.json` | `feat` | 单测：静音切分边界、句数匹配、时间码单调 |
| M2 | 渲染引擎 core（cairo→ffmpeg）+ `render.py` | `feat` | 单测：easing/调色/时间码换算；集成：渲 1 场景并 ffprobe 断言 |
| M3 | 字幕 ASS 生成器 | `feat` | 单测：ASS 时间码格式、样式映射、行宽 |
| M4 | 段 A–B（片头/标题/串行瓶颈） | `feat` | 集成：拼接时长断言 |
| M5 | 段 C（32 核图示 + 场景对比）★ | `feat` | 集成：帧数 = 契约时长×fps；元素断言 |
| M6 | 段 D–E（reader→worker + 顺序一致性 + 数字）★ | `feat` | 集成：同上 |
| M7 | 段 F（收束 + 落版） | `feat` | 集成：同上 |
| M8 | 小象 2D 动画模块 | `feat` | 单测：部件切分尺寸、缓动边界；集成：动作帧不越界 |
| M9 | `compose.py` 端到端合成 | `feat` | 集成：成片时长 = 29.599±0.1s、音轨存在、字幕条数 = 场景数 |
| M10 | Design 终审与多平台导出 | 人工 | 人工检查点 |

测试：`cd docs/life/aiv/pipeline && python -m pytest tests/ -q`。

---

## 9. 风险与回退

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| R1 白底 + 白字字幕不可读 | 字幕看不清 | 已定：深蓝字 + 白描边 + 底部渐变蒙版；需用户确认是否推翻 Design 策划的白字方案 |
| R2 新旧旁白时长差 5 秒 | 原分镜时间点失效 | 已按新音频重算；需要原节奏可补一句重录 |
| R3 小象部件分离质量不足 | 动作僵硬 | 降级为整体变换（呼吸/倾斜/缩放）+ 指示箭头覆盖 |
| R4 「2–5 倍」缺公开出处 | 第三方口径下的可信度 | 文案已限定为「经过我自己本地压测」，并在字幕稿出处表中标注为作者个人实测；不得说成官方数据 |
| R5 Design 导入通道不接受本地成片 | 无法在 Design 内终审/导出 | 回退：完全本地出片 + 用户自行分发；Design 仅用于生成 H3 片头 |
| R6 字体缺失 | 跨机渲染不一致 | `palette.py` 启动校验，缺失即报错 |
| R7 仓库目录再次迁移 | 路径失效 | 路径集中在 `storyboard.json` 与 Makefile 顶部变量，不散落硬编码 |

---

## 10. 不做的事

- 不重录第三次配音（除非用户要求恢复 34.5s 节奏）
- 不让模型修改已渲染画面
- 不做本地 H3 自托管
- 不做 9:16 竖版自动化流水线
- 不做 BGM 与音效
- 不写 Design 的 sqlite 数据库
