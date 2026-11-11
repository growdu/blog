# Growdu 音色

后续视频旁白统一使用这套音色。**规范见 [`../形象与音色规范.md`](../形象与音色规范.md) §2**。

## 定稿参数

```json
{
  "voice_id": "Chinese (Mandarin)_Radio_Host",
  "voice_name": "电台男主播",
  "pitch": -1,
  "speed": 1.33,
  "emotion": "neutral"
}
```

对标参照：`docs/life/aiv/ddl-voiceover.mp3`。实测基频偏差 **+0.1 半音**、
F2 偏差 +31 Hz、动态跨度 107 Hz vs 参照 102 Hz。

## 试听样本

| 文件 | 配置 | 说明 |
| --- | --- | --- |
| `voice_sample_radio_s133_pm1.mp3` | pitch −1 / speed 1.33 | **定稿**，完整口播稿 |
| `voice_sample_radio_s135_pm2.mp3` | pitch −2 / speed 1.35 | 备选一，动态跨度最接近参照 |
| `voice_sample_southern_s150.mp3` | 南方小哥 / speed 1.5 | 备选二，F1 吻合但听感过于平直 |

## 合成

```bash
cd docs/life/aiv/voice
python3 scripts/synthesize_narration.py --text "大家好，我是growdu。"
python3 scripts/synthesize_narration.py --script 字幕.md --out narration.mp3
```

依赖 `mcode-tools` CLI（先加载 `mcode-tools-master` skill）。

## ⚠️ 换稿必须重新定标

`pitch` / `speed` 是相对参照稿标定的。口播稿换了（字数、断句不同），语速和
音高分布都会变，直接套用会偏。

重新定标方法（规范文档 §2.1）：

1. 测参照稿的基频 F0 中位、F1/F2 共振峰、频谱重心、语速
2. 用候选音色合成同一段文本，跑同样的四项测量
3. 按 `|ΔF0半音|×3 + |ΔF1|/30 + |ΔF2|/120 + |Δ重心%|/5 + |Δ语速%|/4` 排序
4. 在真实口播稿上做 speed × pitch 网格微调，收敛到时长与语速都对得上
