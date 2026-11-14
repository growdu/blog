#!/usr/bin/env python3
"""把胸口铭牌抹掉，产出一份「无标牌」形象素材。

**为什么要这一份。** 抖音禁「过度营销信息」与站外引流（规格 §6.6.4）。
片头字标与片尾的 `growdu.cn` 胶囊已经去掉了，剩下的是胸口这枚铭牌——
画面占比极小，但确实是品牌标识。先按「保留」投一条，被判了再换
（规格 §十四 第 16 条）。

**能抹掉，是因为铭牌是脚本印上去的。** `stamp_badge.py` 自动定位铭牌
（不硬编码坐标），所以这里也能自动找到它、把它抹掉。

**抹法**：刷成**马甲色**。铭牌四周一圈都是深藏蓝的马甲，取那一圈里
马甲色像素的中值填进铭牌框——视觉上就是「这块儿本来就没有铭牌」。
比刷成纯白好：白色一块反而更显眼（像贴了张便条）。

用法：
    python3 scripts/clear_badge.py                      # 产出默认素材
    python3 scripts/clear_badge.py <png> [png...]       # 处理指定文件
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
AIV = HERE.parent.parent                     # aiv
CHAR_DIR = AIV / "character"

sys.path.insert(0, str(HERE))
from stamp_badge import find_badge            # noqa: E402

# 输出文件名：与 `character.STATIC_IMAGE` 同目录，名字带 nobadge。
OUTPUT_NAME = "growdu_character_2k_nobg_nobadge.png"

# 取色时往外扩多少像素找马甲色。太小会被铭牌自己的白边干扰，
# 太大会取到马甲外面的背景。
RING_WIDTH = 14

# 铭牌的塑料牌有一圈白色描边，往外扩这么多个像素一起盖掉。
# 不盖的话会留一道白边——原图上很明显，缩小到视频尺寸后看不见，
# 但素材本身看着不干净。
EXPAND = 3

# 羽化宽度：最外圈这么多像素按比例渐隐，跟马甲接得上。
FEATHER = 3


def _vest_pixels(image: Image.Image) -> np.ndarray:
    """马甲色（深藏蓝）的像素。"""
    arr = np.array(image.convert("RGBA"))
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    return (r < 110) & (g < 140) & (b < 175) & (b > r + 20)


def _column_medians(band: np.ndarray, mask: np.ndarray) -> list:
    """每一列里马甲色的中值。没有马甲色的列给 None。"""
    out: list = []
    for index in range(band.shape[1]):
        column = mask[:, index]
        if column.any():
            out.append(np.median(band[column, index], axis=0))
        else:
            out.append(None)
    return out


def _fill_gaps(values: list) -> list:
    """None 的位置用最近的非 None 值补上（先左后右）。

    麦克风与象的手臂压住了几列，那几列上下两圈都取不到马甲色。
    拿整块的中值去补会在马甲上留下一条条竖纹——**兜底色必须是马甲色**。
    """
    known = [index for index, value in enumerate(values) if value is not None]
    if not known:
        return values
    filled = list(values)
    for index, value in enumerate(filled):
        if value is not None:
            continue
        left = max((k for k in known if k < index), default=None)
        right = min((k for k in known if k > index), default=None)
        pick = left if left is not None else right
        if pick is not None:
            filled[index] = values[pick]
    return filled


def _fill_map(arr: np.ndarray, vest_mask: np.ndarray, box: tuple[int, int, int, int],
              expanded: tuple[int, int, int, int]) -> np.ndarray:
    """算出要填进铭牌区域的颜色（每个像素一个 RGB）。

    **按列取色，不整块取一个色。** 铭牌四周并不干净：左边是麦克风
    （黑）、右边是象的手臂（浅灰）。整块取一个中值会在马甲上留下
    一块明显偏平的矩形——按成片尺度算，那块有 58×25 px看得出来。
    按列取马甲色、再按上下两圈竖向插值，能把横向的光照渐变带进来。

    取不到马甲色的列用邻近列补（`_fill_gaps`）；一圈马甲色都没有时，
    兜底用**整张图里马甲色的中值**——不能用整块区域的中值，那个区域
    大半是铭牌本身的白，中值会被拉白，抹完留下一条条白色竖纹。
    """
    x0, y0, x1, y1 = box
    fx0, fy0, fx1, fy1 = expanded
    height = arr.shape[0]

    vest_all = arr[..., :3][vest_mask]
    fallback = (np.median(vest_all, axis=0) if vest_all.size
                else np.array([0.0, 0.0, 0.0]))

    top_band = arr[fy0:y0, fx0:fx1, :3]
    top_mask = vest_mask[fy0:y0, fx0:fx1]
    bottom_band = arr[y1:min(height, fy1), fx0:fx1, :3]
    bottom_mask = vest_mask[y1:min(height, fy1), fx0:fx1]

    tops = _fill_gaps(_column_medians(top_band, top_mask))
    bottoms = _fill_gaps(_column_medians(bottom_band, bottom_mask))
    # 上下两圈互相补：某一圈整个取不到色时用另一圈顶上
    tops = [t if t is not None else b for t, b in zip(tops, bottoms)]
    bottoms = [b if b is not None else t for t, b in zip(tops, bottoms)]
    tops = [t if t is not None else fallback for t in tops]
    bottoms = [b if b is not None else fallback for b in bottoms]

    fill = np.zeros((fy1 - fy0, fx1 - fx0, 3), dtype=np.float64)
    inner_rows = max(1, y1 - y0 - 1)
    for index in range(fx1 - fx0):
        top = tops[index]
        bottom = bottoms[index]
        for row in range(fy0, fy1):
            if row < y0:
                color = top
            elif row >= y1:
                color = bottom
            else:
                t = (row - y0) / inner_rows
                color = top * (1 - t) + bottom * t
            fill[row - fy0, index, :] = color
    return fill


def clear_badge(source: str | Path, output: str | Path | None = None) -> Path | None:
    """抹掉铭牌，产出无标牌素材。找不到铭牌返回 None。"""
    source = Path(source)
    if not source.exists():
        print(f"  - {source.name}：文件不存在，跳过", file=sys.stderr)
        return None

    image = Image.open(source).convert("RGBA")
    box = find_badge(image)
    if box is None:
        print(f"  - {source.name}：没找到铭牌，跳过")
        return None

    x0, y0, x1, y1 = box
    arr = np.array(image)

    # 铭牌四周一圈的马甲色像素——用它来取填充色
    height, width = arr.shape[:2]
    ring_box = (max(0, x0 - RING_WIDTH), max(0, y0 - RING_WIDTH),
                min(width, x1 + RING_WIDTH), min(height, y1 + RING_WIDTH))
    full_vest = _vest_pixels(image)
    vest_mask = full_vest[ring_box[1]:ring_box[3], ring_box[0]:ring_box[2]]
    if not vest_mask.any():
        print(f"  - {source.name}：铭牌四周没找到马甲色，不敢抹，跳过")
        return None

    # 填进铭牌框，并往外扩 EXPAND 个像素盖掉塑料牌的白边。
    # 最外圈 FEATHER 个像素渐隐——硬边会在马甲上留下一道可见的接缝。
    fx0 = max(0, x0 - EXPAND)
    fy0 = max(0, y0 - EXPAND)
    fx1 = min(width, x1 + EXPAND)
    fy1 = min(height, y1 + EXPAND)

    # 填充色按列算（见 `_fill_map` 的说明）：整块一个色会在马甲上留下
    # 一块明显偏平的矩形。
    fill = _fill_map(arr, full_vest, box, (fx0, fy0, fx1, fy1))

    region = arr[fy0:fy1, fx0:fx1, :3].astype(np.float64)

    # 到铭牌框的边缘距离：框内是 0，框外往外挂。
    #
    # **框的坐标必须是绝对坐标**：下面 ys/xs 走的是整张图的绝对坐标，
    # 一旦这里写成相对偏移（`y0 - fy0`），distance 会算成几千，
    # alpha 全被 clip 成 0，脚本就成了空操作——产出跟原图逐字节相同，
    # 却打印「已抹成马甲色」。空操作比报错更难发现，所以钉死在注释里。
    inner_y0, inner_y1 = y0, y1
    inner_x0, inner_x1 = x0, x1

    def _distance_to_inner(y, x):
        dy = np.maximum(np.maximum(inner_y0 - y, y - inner_y1), 0)
        dx = np.maximum(np.maximum(inner_x0 - x, x - inner_x1), 0)
        return np.maximum(dy, dx)

    ys = np.arange(fy0, fy1)[:, None]
    xs = np.arange(fx0, fx1)[None, :]
    distance = _distance_to_inner(ys, xs)
    alpha = np.clip(1.0 - distance / float(FEATHER), 0.0, 1.0)

    blended = region * (1 - alpha[..., None]) + fill * alpha[..., None]
    arr[fy0:fy1, fx0:fx1, :3] = np.clip(blended, 0, 255).astype(np.uint8)

    out = Path(output) if output else source.with_name(OUTPUT_NAME)
    Image.fromarray(arr, "RGBA").save(out)
    print(f"  → {out.name}：铭牌 {box} 已抹成马甲色")
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    targets = [Path(a) for a in argv] if argv else [
        CHAR_DIR / "growdu_character_2k_nobg.png"]
    for target in targets:
        clear_badge(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
