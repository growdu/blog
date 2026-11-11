# DBMedia · Growdu 品牌片头 / 片尾

**规范见 [`../形象与音色规范.md`](../形象与音色规范.md)。**

Growdu 专属的两支品牌片：**片头 `Growdu` 字标 + 数据库标语；片尾 `感谢观看` + 落版三胶囊。**
两支都是 **2.833 秒（68 帧 @ 24fps）**，都在 3 秒上限内，都带 growdu 小象形象。

## 目录

```
brand/
├── clips/
│   ├── growdu_intro_3s_1080p.mp4    片头（2.833s / 68 帧 / 24fps / 时间基 1/24000）
│   └── growdu_outro_3s_1080p.mp4    片尾（同上）
├── assets/
│   ├── bg_intro.png                 AI 背景：深蓝数据中心（2720×1536）
│   ├── bg_outro.png                 AI 背景：蓝调城市天际线（2720×1536）
│   ├── growdu_pose_thumbsup_nobg.png  小象 · 点赞姿态（2048²，透明底）
│   └── growdu_pose_wave_nobg.png      小象 · 挥手姿态（2048²，透明底）
├── audio/
│   ├── voice_intro.mp3 / voice_outro.mp3   旁白（定稿音色）
│   ├── bgm_intro.wav / bgm_outro.wav       配乐原曲（60~75 秒）
│   └── intro_mix.wav / outro_mix.wav       成品音轨（旁白 + 配乐，2.833s）
└── scripts/
    ├── render_brand.py              渲染两支片（当前唯一入口）
    ├── make_audio_brand.py          混音成品音轨
    ├── fix_plates.py                【旧版 8 秒片】底板文字修复
    ├── make_audio.sh                【旧版 8 秒片】macOS say 旁白 + 配乐
    └── render.sh                    【旧版 8 秒片】Ken Burns 渲染
```

媒体产物（`clips/`、`assets/`、`audio/`）**不入库**，本机保留；脚本与说明入库。

## 技术路线

```
AI 生成的纯环境背景（无角色、无文字、无 Logo）
  + canonical 小象姿态图（透明底 PNG，代码合成）
  + 真实字体绘制的文字（cairo + PingFang SC）
  → rawvideo 管道 → ffmpeg 编码 → 混入成品音轨
```

三条不能违反的规矩：

1. **文字一律用真实字体在 cairo 阶段渲染。** 模型生成的中英文会乱码
   （见 `scripts/fix_plates.py` 记录的同一类问题）。背景可以交给模型，文字不行。
2. **背景与形象分开生成。** AI 只画环境；小象用 canonical 参考图生成并保持空白铭牌；
   文字与版式由代码确定。
3. **技术图示绝不交给模型生成。**

### 为什么不用 H3 视频生成

H3 视频生成最短 4 秒，做不出 3 秒以内的片头，所以整条链路改成
「AI 出背景底板 + 代码合成角色与文字」。

## 重新生成

```bash
cd docs/life/aiv/brand
python3 scripts/make_audio_brand.py   # 从 bgm_*.wav 里挑 3 秒窗口并混音
python3 scripts/render_brand.py       # 渲染片头 + 片尾（--intro / --outro 可单渲）
```

渲染完会自动核对帧数（`verify_frames`）：帧数不对直接报错，不让问题流到成片。
片头/片尾时长改 `scripts/render_brand.py` 顶部的 `DURATION` 与 `FRAMES`。

### 踩过的坑

- **混音阶段不能用 `-shortest`。** AAC 编码器会引入延迟，`-shortest` 会按音频的
  结束点反过来把视频截短（实测 68 帧被截成 64 帧），concat 后总时长就漂。
  现在改成按帧数精确 `-t` 截断 + 音频 `apad` 补静音。
- **接地阴影要按真实脚底算，不能按画布底边。** 透明底素材四周有留白
  （点赞姿态脚底在 0.927 高度、挥手姿态在 0.946），画布底边 ≠ 脚底。
  `render_brand.py` 会自动探测主体包围盒再推导脚底比例。
- **AI 宽幅背景可能有贯穿全图的拼接缝。** `bg_outro.png` 初版就是左右两场景硬拼。
  羽化只会把缝糊掉，正确做法是用「单一连续空间」的 prompt 重新生成。

## 在 aiv 流水线里的用法

品牌片是流水线的一等公民，`pipeline/pyv/brand.py` 负责接入：

```bash
cd pipeline
make brand     # 把 brand_intro / brand_outro 插进契约首尾，正文整体后移
make render    # 渲染正文片段
make compose   # 拼接 + 混音（品牌片音轨自动对位）出片
```

要点：

- `brand.py` 优先用定稿的 3 秒片（`growdu_intro_3s_1080p.mp4` /
  `growdu_outro_3s_1080p.mp4`）；缺失时才回退旧的 8 秒片并打印告警。
- 素材会被转码成 1920×1080 @24fps、时间基 1/24000，与 cairo 渲染出的正文片段
  完全一致，concat 才不会漂时长。
- 品牌片自带人声 + 配乐，`compose` 会把每段品牌音轨按场景起点 `adelay` 对位后
  与正文旁白 `amix`；正文旁白自动推迟到第一个 `code` 场景的起点。
- `make brand` 可重复执行：旧的 `brand_*` 场景会被移除、正文位移会被撤销后重算。
- 媒体文件不入库，所以新克隆的机器上**一张品牌片都没有**——`brand.py` 会安静跳过，
  流水线照常出片，只是不带片头片尾。

## 快速合并

```bash
ffmpeg -i growdu_intro_3s_1080p.mp4 -i main.mp4 -i growdu_outro_3s_1080p.mp4 \
  -filter_complex "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]" \
  -map "[v]" -c:v h264 -pix_fmt yuv420p -movflags +faststart final.mp4
```

如果正文含音频，请在最终混音阶段统一加入旁白和背景音乐。
