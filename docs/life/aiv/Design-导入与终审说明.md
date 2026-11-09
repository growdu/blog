# MiniMax Design 导入与终审说明

> 本片的技术画面全部由本地代码精确绘制完成，Design 只承担**终审 + 多平台导出**，
> 不再生成任何技术画面。本次协作**不写入 Design 的任何数据库或画布文件**，
> 只走官方导入通道（拖拽 / 客户端内导入）。

---

## 1. 成片与副产物

| 文件 | 路径 | 用途 |
| --- | --- | --- |
| 成片 | `docs/life/aiv/out/pg-parallel-decode.mp4` | 导入 Design 的主文件 |
| 字幕副产物 | `docs/life/aiv/build/subtitles.ass` | 需要在 Design 内改字幕时复用 |
| 片段源 | `docs/life/aiv/build/s01.mp4` … `s06.mp4` | 单段返修、换节奏时用 |
| 契约 | `docs/life/aiv/storyboard.json` | 时间码、字幕、场景的唯一事实来源 |
| 口播/字幕文案 | `docs/life/aiv/字幕-并行解码.md` | 文案与禁止项 |

成片规格：1920×1080 / 24fps / H.264 (yuv420p) / AAC 48kHz / 29.625 秒
（旁白 29.599 秒；视频按整帧对齐到 711 帧 = 29.625 秒）。

---

## 2. 导入步骤

1. **先关掉正在运行的 Design**，避免目标工程文件被占用。
2. 打开 Design 客户端，进入 `grow du / decode` 工程。
3. 把 `docs/life/aiv/out/pg-parallel-decode.mp4` 拖入画布。
   - 若画布已有旧的示意版时间线，先删掉旧片段再拖入，避免两层叠在一起。
4. 确认视频在画布上完整可播放（29.6 秒，末尾停在落版帧）。

---

## 3. 终审清单

逐项过一遍，任何一项不过就回本地 `pipeline/` 改代码重出，不要在 Design 里修图。

- [ ] **字幕时间轴**：10 条字幕与旁白逐句对齐，无抢拍、无抢字；
      字幕样式为深蓝字 `#1B2A47` + 白描边、底部居中。
- [ ] **术语口径**：全片只用 `reader`（画面标注为 `Reader (WALSender)`），
      不出现 leader / 主机 / 备机等说法。
- [ ] **禁止项**：全片无公司名、品牌名、产品名、Logo、客户名；
      不出现「海量数据库」「海量智库」「原生集成」「内核原生」「Mass Elephant」。
- [ ] **归属语**：开头是「关注数据库内核的独立开发者」，
      结尾落版是「独立开发者 · growdu」，全程没有雇员身份暗示。
- [ ] **形象来源**：小象形象只有 `growdu.png` 一个来源，
      没有出现 `docs/db/logical_decode/pa_decode/` 下的任何图片。
- [ ] **数字准确**：32 核只占 1 核、性能提升 2–5 倍、订阅端顺序与发布端一致，
      三处数字与图形必须对得上。
- [ ] **落版**：最后 2.65 秒停在「并行解码 · 有序同步」+ 个人头像 + 署名，
      没有半句话断掉。

---

## 4. 多平台导出

在 Design 内导出：

- **16:9 主版**：1920×1080，即成片原尺寸。
- **9:16 竖版**：用 Design 的裁切铺满功能裁一版；
  字幕是随画面烧进去的，裁切时会一起被裁，需要在 Design 内**重新加一遍字幕**
  （用 `build/subtitles.ass` 的时间码，或直接在 Design 的字幕轨上手填）。
  注意：本地渲染的字幕字号按画布高度等比缩放，竖版重排后建议重新走一遍
  `make render compose` 并加一条 `video.width/height` 契约，而不是靠 Design 端缩放。

---

## 5. H3 质感片头（可选，210 积分）

默认成片**不含** H3 片头。想加的话：

1. 在 Design 内用 `docs/life/aiv/growdu.png` 作参考图，生成一段 **768P / 3 秒**的质感镜头
   （≈ 70 积分/秒 × 3 秒 ≈ 210 积分）。不要用 2K，2K 是 120 积分/秒。
2. 把它导出成 mp4，放到 `docs/life/aiv/build/h3_intro.mp4`。
3. 在 `storyboard.json` 里加一段 `type: "h3"` 的场景：

   ```json
   {
     "id": "h3a",
     "start": 0.0,
     "end": 3.0,
     "type": "h3",
     "clip": "h3_intro.mp4",
     "subtitle": "关注数据库内核的独立开发者",
     "h3": {"resolution": "768P", "duration": 3.0, "est_credits": 210}
   }
   ```

   并把后面所有场景的 `start`/`end` 整体后移 3 秒、`video.duration` 改成 `32.599`。

4. 回到 `pipeline/` 跑 `make render compose`。
   `compose.py` 会按场景顺序把 h3 片段和代码片段拼在一起。

> H3 只做质感镜头，不承担任何需要"画对"的图形。

---

## 6. 回归方式

```bash
cd docs/life/aiv/pipeline
make test       # 全部单测 + 集成测试
make validate   # 契约校验：时间码连续、字幕行宽、禁止词、字体可解析
make render     # 增量渲染（未过期的片段直接复用）
make compose    # 拼接 + 混音 + 出片
make probe      # 打印成片规格
```

改了场景代码后重跑 `make render compose` 即可；只有改 `storyboard.json` 或
`pyv/` 下的绘图模块才会触发全部重渲。
