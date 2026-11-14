# Growdu 模型形象（3D 卡通小象）

后续视频统一使用的讲解者形象。**规范见 [`../形象与音色规范.md`](../形象与音色规范.md)**。

## 内容

| 文件 | 尺寸 | 说明 |
| --- | --- | --- |
| `growdu_character_2k.png` | 2048×2048 | 主形象，白底。通用素材源 |
| `growdu_character_2k_nobg.png` | 2048×2048 RGBA | 透明底版。**合成进视频用这个** |
| `growdu_character_2k_nobg_nobadge.png` | 2048×2048 RGBA | 透明底**无铭牌**版。抖音这一档备用 |
| `growdu_pose_sheet.png` | 2720×1536 | 6 姿态设定表：中性 / 指示 / 思考 / 数字 2 / 低头 / 收束 |
| `scripts/generate_character.py` | — | 生成脚本（prompt + 参数都在里面，可复现） |
| `scripts/add_glasses.py` | — | 戴眼镜化：图生图加眼镜 + 擦镜框杂物 + 抠底 + 盖章 |
| `scripts/stamp_badge.py` | — | 铭牌盖章：刷白铭牌 + 用真实字体印上 growdu |
| `scripts/clear_badge.py` | — | 抹掉胸口铭牌：产出无标牌素材（抖音这档备用） |
| `scripts/_mcode.py` | — | mcode-tools CLI 封装（上传 / 调用 / 下载 / 临时故障重试） |

透明底主形象与无标牌版**入库**（出片必需 / 抖音这档备用）；
白底原图与姿态表不入库，保留本机即可，需要时跑脚本重新生成。

## 形象原型

唯一来源：`aiv/growdu2.jpeg`。**不要**引用仓库其它目录下的任何形象图。

## 形象设定速记

- 3D 卡通小象，浅蓝灰皮肤、圆大眼、粉色面颊、小巧象牙、头顶呆毛
- 深藏蓝 `#2B4C7E` 工装马甲，胸口琥珀黄 `#F5A623` 圆柱数据库图标
- 黑色头戴式耳机 + 麦克风臂
- **深藏蓝 `#2B4C7E` 方形细边框眼镜，镜片透明**（§1.5）
- 胸口白色铭牌，必须显示 `growdu`

## 重新生成

```bash
cd aiv/character
python3 scripts/generate_character.py   # 生成 → 抠透明底 → 姿态表 → 铭牌盖章
```

### 给已有素材戴上眼镜

眼镜不能贴图贴上去（3D 渲染的眼镜要有厚度、高光、镜腿遮挡关系），
只能以素材为参考图做图生图：

```bash
cd aiv/character
python3 scripts/add_glasses.py                        # 批次：4 个素材 → _staging/
python3 scripts/add_glasses.py --resume              # 断点续跑（跳过已生成的）
python3 scripts/add_glasses.py --promote              # 目视验收后覆盖正式素材
python3 scripts/add_glasses.py <src.png> <dst.png>    # 单张：给任意素材戴眼镜
```

批次流程是 生成 → 目视验收 → promote：参考图取自 `_staging/_base/` 的留底，
promote 之后再跑一次不会「眼镜叠眼镜」。

依赖 `mcode-tools` CLI（先加载 `mcode-tools-master` skill）。
每次运行都会消耗生成额度，重复执行前先确认是否真的需要重做。

铭牌盖章也可以单独跑（不消耗额度）：

```bash
python3 scripts/stamp_badge.py            # 处理默认素材
python3 scripts/stamp_badge.py <png> ...  # 处理指定文件
```

### 换成无铭牌形象（抖音这一档备用）

胸口那枚 `growdu` 铭牌也是品牌标识。抖音判「过度营销信息」时要换成
无铭牌那份：

```bash
cd aiv/character
python3 scripts/clear_badge.py            # 产出 growdu_character_2k_nobg_nobadge.png
cd ../pipeline
make EP=row-lock nobrand NOBADGE=1        # 用无铭牌素材重出片
```

抹法是刷成**马甲色**：铭牌四周一圈取马甲色像素的中值，按列竖向插值填
回去（整块一个色会在马甲上留下一块偏平的矩形）。铭牌是脚本印上去的，
所以定位也是自动的，不硬编码坐标。

默认**保留**铭牌：它占画面 0.4%，机器审核未必看得见，
先按保留投一条看结果（发布契约 §十四 第 16 条）。

## 三条硬规矩

1. **铭牌必须显示 `growdu`，但文字不能由模型生成。** 模型生成的中英文会乱码
   （`growdu` 可能变成 `giowdu`、`grawdu`），所以生成后统一跑一遍
   `stamp_badge.py`：自动定位铭牌（按「被深藏蓝马甲围住的那块白」，
   不硬编码坐标）→ 刷成纯白 → 用当前字体写上 `growdu`（字体族名由
   `pipeline/pyv/fonts.py` 跨平台解析：macOS `PingFang SC`，Linux `Noto Sans CJK SC`）。
   文字来源从「模型碰运气」变成「代码确定」。

   这与 `brand/scripts/fix_plates.py` 是同一类问题的同一套解法：所有文字都用
   真实字体渲染。

2. **眼镜只能靠图生图加，不能贴图贴。** 贴上去是平色块，一眼假。
   而且模型戴上方形眼镜后有个固定毛病：会在镜框或镜腿上贴一小块白色铭牌
   （实测写着 `growdu`）——所以 `add_glasses.py` 额外走一次局部修补把它擦掉。
   这块白牌还会被铭牌检测当成真铭牌（它四周全是镜框色），所以铭牌检测
   同时加了尺寸下限，见 `scripts/stamp_badge.py` 里的
   `MIN_WIDTH_RATIO` / `MIN_HEIGHT_RATIO`。

3. **3D 形象不做部件切分动画。** 仓库早期版本试过按颜色连通块把形象切成
   部件再驱动动作，阈值和绝对坐标都是为 2D 扁平图硬编码的，3D 渲染的
   渐变与高光会直接破坏阈值分割。新形象按「静帧素材 + 位移/缩放/淡入」做动效，
   由 `pipeline/pyv/character.py` 统一接入。
