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
│   ├── growdu_pose_thumbsup_nobg.png  小象 · 点赞姿态（2048²，透明底，戴方框眼镜）
│   └── growdu_pose_wave_nobg.png      小象 · 挥手姿态（2048²，透明底，戴方框眼镜）
├── audio/
│   ├── voice_intro.mp3 / voice_outro.mp3   旁白（定稿音色）
│   └── intro_mix.wav / outro_mix.wav       成品音轨（旁白 + 配乐，2.833s）
├── brand_windows.json                      片头片尾的配乐窗口决定（**入库**）
└── scripts/
    ├── render_brand.py              渲染两支片（当前唯一入口）
    ├── generate_poses.py            生成点赞 / 挥手姿态素材（可复现）
    ├── make_audio_brand.py          混音成品音轨
    ├── fix_plates.py                【旧版 8 秒片】底板文字修复
    ├── make_audio.sh                【旧版 8 秒片】macOS say 旁白 + 配乐
    └── render.sh                    【旧版 8 秒片】Ken Burns 渲染
```

媒体产物（`clips/`、`assets/`、`audio/`）**不入库**，本机保留；脚本与说明入库。

`brand_windows.json` 是**入库**的：它记的是「片头片尾取曲子的哪一段」这个决定
（决策入库，音频不入库）。换曲子时重挑一次即可，不用改任何脚本。

## 片头片尾的配乐：片尾接回片头

两段配乐取自同一条 `motif`，而且**在原曲里紧挨着**：片头取 `s` 到 `s+D`
这一段，片尾取 `s-D` 到 `s` 这一段，于是 `outro_start + D == intro_start`，
片尾结束时正好落在
片头的起音点上——两段拼起来是同一段连续音乐，形成闭环。

口径与判据见《背景音乐规范》§6 末条与 §7 的 `bgm.brand-*` 三条规则。
挑窗口：

```bash
cd aiv/pipeline
python -m pyv.cli bgm windows       # 重挑并写进 brand/brand_windows.json
python -m pyv.cli bgm brand-check   # 校验：首尾相接 / 曲子指纹 / 能量
```

**别用相关系数判断两段是否相接**——有瞬态的音乐上这个指标没有意义
（旧口径 +0.0543、新口径 -0.0655，两个数都说明不了问题）。
真判据是「两段在原曲里紧挨着」：逐样本验证原曲里从 `outro_start`
到 `intro_start+D` 这一段，前半等于片尾窗口、后半等于片头窗口。

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
2. **背景与形象分开生成。** AI 只画环境；小象用 canonical 参考图生成，
   铭牌由代码盖章；文字与版式由代码确定。
3. **技术图示绝不交给模型生成。**

铭牌的 `growdu` 也不是模型写的：`render_brand.py` 渲染前会自动调
`character/scripts/stamp_badge.py` 给姿态素材盖一次章——刷白铭牌，再用
`PingFang SC` 写上 `growdu`。幂等，重复渲染结果一致。

### 为什么不用 H3 视频生成

H3 视频生成最短 4 秒，做不出 3 秒以内的片头，所以整条链路改成
「AI 出背景底板 + 代码合成角色与文字」。

## 文案

文案全部由 `scripts/render_brand.py` 顶部的常量给出，文字用真实字体在 cairo 阶段渲染：

| | 画面文字 | 旁白 |
| --- | --- | --- |
| 片头 | `Growdu` / `Database · Knowledge · Growth` / 胶囊「深入数据库 · 分享技术之美」 | 欢迎来到 growdu，深入数据库。 |
| 片尾 | `感谢观看` / `Growdu · 把踩过的坑写成方法` / 三胶囊「growdu.cn」「订阅关注」「点赞支持」 | 下次卡住的时候，记得回来。 |

片尾的副标题与旁白按《人格规范》§8 改写过：原来那句「与你一起探索数据库的无边世界」
是营销腔，换成命中「现场验证者（踩坑）」与「方法论者（写成方法）」的说法；
旁白「下次卡住的时候，记得回来。」直接呼应人格的动机句。
片头保持不变——「Database · Knowledge · Growth」已经承担了「技术能力集成」的品牌表达。

改旁白要重新合成，音色与参数见《形象与音色规范》§2.2：

```bash
cd aiv
python3 voice/scripts/synthesize_narration.py \
  --text "下次卡住的时候，记得回来。" --out brand/audio/voice_outro.mp3
```

## 重新生成

```bash
cd aiv/pipeline
python -m pyv.cli bgm windows          # 挑片头片尾的配乐窗口（写进 brand/brand_windows.json）
cd ../brand
python3 scripts/make_audio_brand.py    # 按窗口从曲库取 motif，混出成品音轨
python3 scripts/render_brand.py        # 铭牌盖章 + 渲染片头 + 片尾（--intro / --outro 可单渲）
```

`make_audio_brand.py` 会核对 `brand_windows.json` 里的曲子 id 与 sha256，
并检查两段窗口首尾相接——不相接就拒产，不让错口径流到成片。

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
- **姿态素材戴眼镜要走两步。** 模型给镜框贴白色小铭牌是固定毛病，
  `character/scripts/add_glasses.py` 因此在图生图之后额外做一次局部修补。
  姿态素材本身的生成入口是 `scripts/generate_poses.py`。
- **成品音轨必须接进成片，不能只做好放在那儿。** 2026-11-12 踩过：
  motif 的成品音轨（`intro_mix.wav`）做出来了，却没接进成片——
  `brand.py` 当时从品牌片 mp4 里抽音轨，嵌进去的还是切换前的旧 AI 配乐。
  现在 `pyv/brand.py` 的 `_resolve_audio_source()` 优先取
  `brand/audio/*_mix.wav`，mp4 音轨只作兜底，换配乐不必重渲 3D 形象。
- **淡出要短。** 片尾的音乐是片头那段的前一截，末尾淡出 0.3 秒会把刚接上的
  闭环淡没。现在片头淡入 0.08 秒、淡出 0.08 秒，片尾不淡入（它的窗口是曲子
  中段的接缝，淡入像另起一段），成品混音再收 0.05 秒。

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
- 品牌音轨取的是 `brand/audio/*_mix.wav`（成品音轨），不是品牌片 mp4 里烘焙的那条；
  详见上面的「踩过的坑」。
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
