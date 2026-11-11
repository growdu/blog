# 并行解码讲解片 · 代码驱动动画 + MiniMax Design 协作设计

> **历史存档（2026-11-09 的设计稿）。** 其中描述的 2D 形象与 `elephant.py` 部件动画
> 已于 2026-11-11 整体移除，形象改走 3D 静帧 + 位移/缩放/淡入，
> 见《形象与音色规范》§1.6。同日整个目录从 `docs/life/aiv/` 迁到仓库根的 `aiv/`
> （与 `weixin/` 同级），本文里的 `docs/life/aiv/` 路径按当时的位置保留。
> 本文保留当时的方案记录，不再是现行设计。

- 日期：2026-11-09
- 目标成片：`docs/life/aiv/` 下的 34.488 秒「海量数据库 · 逻辑复制并行解码」讲解片
- 分工模式：**代码渲染分镜 → 写回 canvas.json → MiniMax Design 画布完成最终合并与多平台导出**
- 画面来源：**B 混合档**（技术图示全代码 + 3–5 秒 768P 质感片头/转场 + 封面锚图），目标积分 290–430（原全 H3 方案 4200）

---

## 1. 背景与目标

原方案用 H3 逐段生成全部画面：2 段 13 秒（各 1560 积分）+ 1 段 9 秒（1080 积分）= 35 秒 / 4200 积分。
经核算，H3 2K 单价为 **120 积分/秒**（1560÷13 = 1080÷9 = 120），成本由单价决定，不是分段策略失误。

本片以技术图示为主（reader→worker 数据流、32 核、2–5 倍、commit 顺序一致性），
这类内容由规则描述、由代码绘制最准确，且**不消耗任何积分**。

**目标**

| 项 | 指标 |
| --- | --- |
| 积分消耗 | ≤ 450（原 4200，降 ≥ 89%） |
| 画面准确性 | 文字、数字、机制图示零模型生成，改一处只需重渲一个场景 |
| 旁白完整性 | 原音频 `pa_decode.mp3` 完整保留，34.488 秒不重录 |
| 可回溯 | 每个场景一个模块、一次提交；契约 `storyboard.json` 入库 |
| 交付 | 2560×1440 / 24fps 成片（对齐既有 `parallel-apply-subtitles-synced.mp4`） |

**非目标（YAGNI）**：不做 9:16 竖版自动化（由 Design 多平台导出承担）；不做本地 H3 自托管；
不让模型二次修改已渲染画面；不重录配音；不做背景音乐智能混音（固定增益）。

---

## 2. 已核验的事实基线

### 2.1 素材现状（`docs/life/aiv/`）

| 资产 | 规格 | 用途 |
| --- | --- | --- |
| `pa_decode.mp3` | 34.488s / mp3 / 32kHz / 单声道 | 本片旁白（唯一音轨基准） |
| `字幕-并行解码.md` | 11 句口播稿 | 分场依据（注意：为 9/20 版本，需按今日旁白重新对齐） |
| `growdu-elephant-presenter.png` | 1376×768 | 小象形象源，2D 动画与 H3 参考图共用 |
| `科技广告背景音乐.mp3` | 44.9MB | BGM |
| `ddl-title-top.ass` | ASS 样式 | 字幕样式参考（颜色规则见 2.3） |
| `parallel-apply-subtitles-synced.mp4` | 2560×1440 / 24fps / 39.5s | 上一条成片，规格对齐基准 |
| `.hilo/canvas.json` | 12 节点 | 本地画布节点图（Design 项目根即此目录） |

### 2.2 工具链（本机已装）

`ffmpeg/ffprobe 8.1`、`python3 3.11`（`cairo` `PIL` `numpy` `matplotlib` 可用，`manim` 未装且**不打算装**）、
`node 25.7`。技术图示与 2D 部件动画用 cairo + PIL 足够，无需引入渲染框架。

**字体**：固定 `PingFang SC`（macOS 自带）。`palette.py` 在启动时校验字体可加载，缺失即报错退出，
不静默降级到默认字体（避免跨机渲染结果不一致）。

### 2.3 沿用的视觉规则（来自 `字幕-并行apply.md`）

问题段 `#F6AD55`、解决段 `#4FD1C5`、中文每行 ≤ 14 字、数值段大字号 + 强调色、不出现具体库名/函数名/参数名。

### 2.4 MiniMax Design 的能力边界（已核验）

- 「本地优先」**仅指画布素材存本机**，生成算力全在云端；第三方模型不可本地跑。
- **语义编辑不稳**（调色几乎无效、换背景主体变形）；导演台分镜、剪辑、字幕、裁切、转场可用。
  → 由此确定分工原则：**模型只生成，不修图；像素级确定的操作走 ffmpeg/ASS**。
- H3 2K = 120 积分/秒（实测）；768P ≈ 70 积分/秒（1 万积分 ≈ 143 秒 768P 的公开换算口径）。
- **套餐积分只在 Design 客户端内消耗**；直接调用开放平台 H3 V2 API 走的是 API 余额，不扣套餐积分。
  → 需要消耗积分的镜头必须在 Design 内生成（含 IM 派活到 Design）。
- 本地跑 H3 权重需 NVIDIA CUDA（官方 ComfyUI / SGLang / vLLM-Omni 路径均是），本机为 Apple Silicon，不成立。

### 2.5 画布写回机制（已核验 schema）

`.hilo/index.sqlite` 的 `assets` 表与 `.hilo/canvas.json` 节点构成**一对一映射**：

```
canvas.json 节点.assetId  ≡  assets.id  ≡  assets.path（工作区相对路径）  →  项目目录下的同名文件
```

`assets` 表字段：`id, path, status, size, mtime_ms, dev_id, inode, birthtime_ms, quick_hash,
width, height, duration_ms, mime_type, name, metadata, created_at, updated_at, ...`
本地导入的文件其 `metadata` 为 `{"model":"user_uploaded"}`。
`canvas.json` 结构：`{version, mode:"workflow", nodes:[...], edges:[...]}`（大项目另有 `hiddenAssetIds`）。

→ 写回配方见 §7。**唯一未实机验证点**：外部写入后 Design 是否正确 reconcile（步骤 0 的尖峰任务）。

---

## 3. 方案总览

```
                    ┌──────────────── 本地（0 积分）────────────────┐
 pa_decode.mp3 ───▶ │ align.py ──▶ storyboard.json ──▶ scenes/*.py  │
 34.488s 原音频     │                     │                │        │
                    │                     │          cairo 逐帧渲染 │
 科技广告背景音乐 ──▶│                     │                ▼        │
                    │                     │         build/scene-*.mp4│
                    │                     │                │        │
                    │                     │         canvas_writer.py  │
                    │                     │                │        │
                    │                     │      ┌─────────┴────────┐ │
                    │                     │      ▼                  ▼ │
                    │                     │ .hilo/canvas.json  .hilo/index.sqlite
                    └─────────────────────┼──────────────────────────┘
                                          │  打开 MiniMax Design
                                          ▼
                    ┌──────────── MiniMax Design（消耗套餐积分）────────────┐
                    │ 画布时间线合并 → 终审 → 多平台导出 / 封面              │
                    │ H3 768P 质感镜头（3–5s，210–350 积分）+ 封面锚图（80） │
                    └──────────────────────────────────────────────────────┘
```

**职责边界**

| 环节 | MiniMax Design | 本地代码 |
| --- | --- | --- |
| 小象角色锚定、跨镜头一致性 | ✅ 资产中心 | 读 PNG 做部件切分 |
| reader→worker、32 核、2–5 倍、commit 顺序 | ❌ 模型写不对 | ✅ 精确绘制 |
| 小象挥手/点头/指示 | 少量质感镜头 | ✅ 2D 部件动画（沿用原图） |
| 文字、数字、字幕 | ❌ | ✅ ASS 烧制 |
| 旁白 | 保留原音频 | ✅ 按时间码对齐，0 成本 |
| 时间线合并、多平台导出 | ✅ 画布 | 提供分镜片段与节点 |
| 终审 | ✅ 节点级检查点 | 自动校验（时长/字幕/响度） |

---

## 4. 目录与契约

```
docs/life/aiv/
├── assets/                     # 输入素材（不入库）
├── pa_decode.mp3               # 旁白（唯一音轨基准）
├── 字幕-并行解码.md             # 口播稿
├── storyboard.json             # ★ 唯一契约（入库）
├── pipeline/
│   ├── pyv/                    # 引擎包
│   │   ├── canvas.py           # cairo 绘制封装（文字/矩形/箭头/图片/缓动）
│   │   ├── palette.py          # 配色常量（§2.3）+ 字体名
│   │   ├── easing.py           # 缓动函数
│   │   ├── timeline.py         # 场景装载、时间码校验
│   │   ├── subtitle.py         # ASS 生成
│   │   ├── align.py            # 旁白静音切分 → 时间码草稿
│   │   ├── render.py           # 逐帧渲染 + ffmpeg 编码
│   │   ├── compose.py          # 分镜 concat + 混音 + ASS 烧制
│   │   ├── canvas_writer.py    # 写回 canvas.json + assets 索引
│   │   ├── elephant.py         # 小象部件切分与 2D 动画
│   │   └── scenes/             # 一个场景一个模块 s01_hook.py …
│   │       ├── __init__.py
│   │       ├── s01_intro.py
│   │       ├── s05_core_32cores.py
│   │       └── …
│   ├── tests/                  # pytest：单测 + 集成
│   ├── Makefile                # make align / render / compose / publish
│   └── docs/superpowers/specs/ # 本设计文档
├── build/                      # 渲染产物（不入库）
└── .hilo/                      # Design 项目状态
```

### `storyboard.json`（契约）

```json
{
  "version": 1,
  "video": { "width": 2560, "height": 1440, "fps": 24, "duration": 34.488 },
  "audio": { "narration": "pa_decode.mp3", "bgm": "科技广告背景音乐.mp3", "bgm_gain_db": -20 },
  "scenes": [
    {
      "id": "s05",
      "start": 10.82, "end": 13.44,
      "type": "code",
      "renderer": "pyv.scenes.s05_core_32cores",
      "subtitle": "32 核机器上解码只占 1 核",
      "params": { "highlight": "#4FD1C5" }
    },
    {
      "id": "s01",
      "start": 0.0, "end": 3.0,
      "type": "h3",
      "h3": { "resolution": "768p", "duration": 3.0, "reference": "growdu-elephant-presenter.png",
              "prompt": "科技感深色背景中的拟人化小象形象，缓缓转头看向镜头并轻微抬爪，光线柔和有层次，画面稳定不晃动，无文字",
              "est_credits": 210 },
      "clip": "build/h3/s01_intro_768p.mp4"
    }
  ]
}
```

规则：

- `type` ∈ `code` | `h3` | `image`。`h3` 场景是**占位规格**：本地不调用任何生成 API，只登记镜头参数与预估积分；
  镜头在 Design 内生成后落到 `build/h3/`，流水线只负责把它接入时间线。
- 场景按 `start` 升序、**首尾相接无缝无重叠**，总时长 = 旁白时长。
- 每个场景覆盖 1 句旁白；边界取静音点。
- `subtitle` 为该场景的字幕文本，≤ 14 字/行。

---

## 5. 场景清单

| # | 旁白句 | 画面 | 来源 | 核心度 |
| --- | --- | --- | --- | --- |
| s01 | 大家好，我是海量数据库内核研发 growdu | 小象入场 + 身份条 | **H3 768P 3s** + code 叠加 | 质感 |
| s02 | 今天我们聊一聊海量数据库逻辑复制的并行解码 | 标题卡 | code | |
| s03 | 常规的逻辑复制场景数据同步效率低下 | 痛点：单线程流水线 | code | |
| s04 | 默认发布端只有一个解码线程串行处理 | 发布端单线程 | code | |
| s05 | 32 核机器上解码只占 1 核 | 32 核 vs 1 核 | code | ★核心 |
| s06 | 大事务小事务高并发场景解码都跟不上 | 双场景对比 | code | |
| s07 | 海量数据库逻辑复制发布端支持并行解码 | 架构切换转折 | code | |
| s08 | reader 解析加多 worker 并行解码，速度显著提升 | reader→worker 分发 | code | ★核心 |
| s09 | 订阅端收到的顺序和发布端一致 | 顺序编号一致性 | code | ★核心 |
| s10 | 整体性能提升 2 到 5 倍 | 数字大字 | code | |
| s11 | 逻辑复制数据同步性能显著提升，满足金融等重要业务场景的实时性要求 | 收束 + 落版 | code | |

时间码由 `align.py` 从 `pa_decode.mp3` 的静音点产出草稿，**人工确认后**写入 `storyboard.json`。
静音检测参数固定为 `ffmpeg -af silencedetect=noise=-32dB:d=0.25`，保证可重复；
检测到的静音段数与口播稿句数不一致时（允许 ±1 的容差）直接报错并列出候选切点，不自动猜测。
注意：现存的 `字幕-并行解码.md` 是 9/20 版本稿，必须以今日 `pa_decode.mp3` 为准重新对齐。

---

## 6. 渲染引擎

**技术选型**：cairo 逐帧绘制 → rawvideo 管道喂给 ffmpeg 编码为无声片段 → concat → 一次性混入旁白与 BGM → ASS 烧字幕。

- 单场景渲染为独立 mp4（`build/scene-XX.mp4`，H.264、yuv420p、24fps、2560×1440），便于单场景重渲与并行。
- `render.py` 提供 `render_scene(scene, out)`；通过 `ffmpeg -f rawvideo -pix_fmt rgb24` 管道输出，内存占用恒定。
- 文字用 cairo 的 toy API + 系统中文字体（需在 `palette.py` 固定字体名，保证跨机一致）。
- 小象 2D 动画：`elephant.py` 负责从 PNG 切出部件（头/身/耳/臂/鼻），用旋转+位移+缓动驱动，
  动作限于挥手、点头、轻微转动、指向；不做口型（无模型生成视频即无口型需求）。
- 每个场景是**纯函数式**：`render(ctx, t_local)`，`t_local ∈ [0,1]`，无全局状态 → 可单测、可重放。

**音频与字幕**

- 旁白：`pa_decode.mp3` 原样保留，不做变速、不做重录。
- BGM：`科技广告背景音乐.mp3` 固定增益（默认 -20 dB）后与旁白混合，旁白不做 ducking（保持确定性）。
- 字幕：`pyv/subtitle.py` 生成 ASS，沿用 `ddl-title-top.ass` 的样式与 §2.3 配色，时间码直接来自 `storyboard.json`。

---

## 7. 写回 MiniMax Design（核心机制）

### 7.1 写入配方

1. 分镜片段渲染到项目目录，文件名即工作区相对路径（如 `pd-s05-cores.mp4`）。
2. 在 `.hilo/index.sqlite` 的 `assets` 表插入一行：
   `id=uuid4`、`path=<相对路径>`、`status='active'`、`size`、`mtime_ms`、`dev_id`、`inode`、`birthtime_ms`、
   `width/height`、`duration_ms`（取自 ffprobe）、`mime_type='video/mp4'`、`name`、
   `metadata='{"model":"user_uploaded"}'`、`created_at/updated_at`；`quick_hash` 留 NULL 交由 reconcile 重算。
3. 在 `.hilo/canvas.json` 的 `nodes` 追加节点（保留既有 `nodes` 与 `edges` 不动）：
   ```json
   { "id": "<node-uuid>", "type": "video",
     "positions": { "workflow": { "x": 0, "y": 0 } },
     "size": { "width": 350, "height": 197 },
     "assetId": "<第2步的 uuid>",
     "data": { "name": "pd-s05-cores.mp4", "path": "pd-s05-cores.mp4", "duration": 2.62 } }
   ```
4. 打开 MiniMax Design → reconcile 按路径重绑 → 节点出现在画布。

### 7.2 约束与回退

- **写回前必须关闭 Design**：避免与 `reconcile_lock` 竞争；sqlite 写入使用事务，写后立即校验。
- **回退方案 B**：写回不被识别时，人工把 11 个片段拖入画布（约 2 分钟），流程其余部分不变。
- **回退方案 C**：放弃画布合并，改为本地 ffmpeg 直接出片，Design 仅用于生成镜头与终审。
- 步骤 0 必须先做一次单片段尖峰验证（§10 M0），验证通过再投入后续。

---

## 8. 积分预算与生成清单

| 项 | 规格 | 积分 | 执行位置 |
| --- | --- | --- | --- |
| H3-01 片头质感（小象入场） | 768P / 3s / I2V（参考 `growdu-elephant-presenter.png`） | 210 | Design（IM 派活或客户端） |
| H3-02 转场：数据流穿梭（可选） | 768P / 2s | 140 | Design |
| 封面锚图 / 小象部件拆解表 | GPT Image 2 × 1 | 80 | Design |
| **合计** | 3–5 秒模型画面 | **290–430** | |

规则：**768P 预演，2K 只留给最终选中的镜头**；预算按镜头数而非片长规划——最烧积分的不是生成，是重试。
若 H3 镜头质量不达标，退化为纯 code 版本（0 积分），成片仍然成立。

---

## 9. 提交节奏与测试策略

遵守既定偏好：**每个子模块完成立即提交；每次提交配套单元测试 + 集成测试，且测试通过。**

| 里程碑 | 内容 | 提交 | 配套测试 |
| --- | --- | --- | --- |
| M0 | 项目骨架 + `.gitignore` + 契约校验器 + **画布写回尖峰验证** | `chore` | 契约校验单测；尖峰为人工验证项 |
| M1 | `align.py` 旁白对齐 → `storyboard.json` | `feat` | 单测：静音切分边界、句数匹配、时间码单调 |
| M2 | 渲染引擎 core（cairo→ffmpeg）+ `render.py` | `feat` | 单测：easing/调色/时间码换算；集成：渲染 1 场景并 ffprobe 断言 |
| M3 | 字幕 ASS 生成器 | `feat` | 单测：ASS 时间码格式、样式映射、行宽 |
| M4 | s01–s03（片头/标题/痛点） | `feat` | 集成：3 场景拼接时长断言 |
| M5 | s04–s06（串行瓶颈 / 32 核 / 场景对比） | `feat` | 集成：逐场景帧数 = 契约时长×fps |
| M6 | s07–s09（reader→worker / 顺序一致性） | `feat` | 集成：同上 + 顺序编号图示的元素断言 |
| M7 | s10–s11（性能数字 / 收束落版） | `feat` | 集成：同上 |
| M8 | 小象 2D 动画模块 | `feat` | 单测：部件切分尺寸、缓动边界；集成：动作帧不越界 |
| M9 | `canvas_writer.py` 写回 | `feat` | 单测：节点/资产字段完整性、id 一致性；集成：写回后 sqlite 可查且 canvas.json 合法 |
| M10 | `compose.py` 端到端合成 | `feat` | 集成：成片时长 = 34.488±0.1s、音轨存在、字幕条数 = 场景数 |
| M11 | Design 终审与多平台导出 | 人工 | 人工检查点 |

测试运行方式：`cd docs/life/aiv/pipeline && python -m pytest tests/ -q`。

---

## 10. 风险与回退

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| R1 外部写回的 canvas 节点不被 reconcile 识别 | Design 侧看不到分镜 | M0 尖峰先验；回退 B（人工拖入）/ C（本地直接出片） |
| R2 写 sqlite 时 Design 正在运行 | 索引损坏 / 锁冲突 | 写回前强制关闭 Design；事务 + 写后校验；失败即回退 B |
| R3 小象部件分离质量不足，2D 动作僵硬 | s01/s11 观感差 | 降级为整体变换（呼吸/倾斜/缩放）+ 指示箭头覆盖 |
| R4 今日旁白与 9/20 口播稿不一致 | 分场错位 | M1 产出草稿后**人工逐句确认**再冻结契约 |
| R5 H3 镜头与代码画面风格不统一 | 观感割裂 | 统一色板与构图；H3 镜头仅 3–5 秒并做转场遮罩；必要时退化为纯 code（0 积分） |
| R6 字体在渲染机缺失 | 文字错位/豆腐块 | `palette.py` 固定字体名并在启动时校验，缺失即报错而非静默降级 |

---

## 11. 不做的事

- 不重录配音、不做 TTS（保留 `pa_decode.mp3`）
- 不让模型修改已渲染画面（Design 语义编辑不稳）
- 不做本地 H3 自托管（Apple Silicon 不在官方支持矩阵）
- 不做 9:16 竖版自动化流水线（交给 Design 多平台导出）
- 不做背景音乐智能 ducking（固定增益，保持确定性）
