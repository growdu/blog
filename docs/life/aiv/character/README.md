# Growdu 模型形象（3D 卡通小象）

后续视频统一使用的讲解者形象。**规范见 [`../形象与音色规范.md`](../形象与音色规范.md)**。

## 内容

| 文件 | 尺寸 | 说明 |
| --- | --- | --- |
| `growdu_character_2k.png` | 2048×2048 | 主形象，白底。通用素材源 |
| `growdu_character_2k_nobg.png` | 2048×2048 RGBA | 透明底版。**合成进视频用这个** |
| `growdu_pose_sheet.png` | 2720×1536 | 6 姿态设定表：中性 / 指示 / 思考 / 数字 2 / 低头 / 收束 |
| `scripts/generate_character.py` | — | 生成脚本（prompt + 参数都在里面，可复现） |
| `scripts/blank_badge.py` | — | 把铭牌刷成纯白（生成后自动跑，也可单独跑） |

媒体文件不入库，保留本机即可；需要时跑脚本重新生成。

## 形象原型

唯一来源：`docs/life/aiv/growdu2.jpeg`。**不要**引用仓库其它目录下的任何形象图。

## 重新生成

```bash
cd docs/life/aiv/character
python3 scripts/generate_character.py   # 生成 → 抠透明底 → 姿态表 → 擦铭牌
```

依赖 `mcode-tools` CLI（先加载 `mcode-tools-master` skill）。
每次运行都会消耗生成额度，重复执行前先确认是否真的需要重做。

铭牌擦白也可以单独跑（不消耗额度）：

```bash
python3 scripts/blank_badge.py            # 处理默认素材
python3 scripts/blank_badge.py <png> ...  # 处理指定文件
```

## 两条硬规矩

1. **铭牌必须留空。** 模型生成的中英文文字会乱码（`growdu` 可能变成 `giowdu`、
   `grawdu`）。文字一律由代码用真实字体（`PingFang SC`）在 cairo 阶段渲染。
   这与 `brand/scripts/fix_plates.py` 是同一类问题的同一套解法。

   主形象这次模型碰巧写对了 `growdu`，但「碰巧」不能当规范用——生成后仍会跑
   `blank_badge.py`，按「被深藏蓝马甲围住的那块白」自动定位铭牌并刷成纯白。
   定位不硬编码坐标，重生成后依然有效。

2. **3D 形象不能喂进 `pipeline/pyv/elephant.py`。** 那个模块的部件切分按颜色
   连通块做，阈值和绝对坐标都是为 2D 扁平形象 `growdu.png` 硬编码的；3D 渲染的
   渐变与高光会直接破坏阈值分割。新形象按「静帧素材 + 位移/缩放/淡入」做动效，
   由 `pipeline/pyv/character.py` 统一接入。
