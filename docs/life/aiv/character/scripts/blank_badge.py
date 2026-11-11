#!/usr/bin/env python3
"""把胸口铭牌上的模型生成文字擦成纯白。

模型生成的中英文会乱码（见《形象与音色规范》§1.4），所以铭牌必须留空。
模型这次碰巧写对了 "growdu"，但「碰巧」不能当规范用——本脚本在生成之后、
合成之前把铭牌矩形刷成纯白，保证画面上永远只有代码用真实字体渲染的文字。

铭牌定位不硬编码坐标（重生成后依然有效）：
  1. 找「近白色」的连通块，排除与画布边缘相连的（那是背景）
  2. 候选必须是横向长方形、边长与面积都够大
  3. 铭牌是「被深藏蓝马甲围住的一小块白」，所以四周一圈马甲色占比最高

用法：
  python3 scripts/blank_badge.py                  # 处理默认素材
  python3 scripts/blank_badge.py <png> [png...]   # 处理指定文件
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
AIV = HERE.parent.parent                     # docs/life/aiv
CHAR_DIR = AIV / "character"

NEAR_WHITE = 205          # 近白阈值
VEST_MAX = (110, 140, 175)   # 深藏蓝马甲的 r/g/b 上限
VEST_BLUE_MARGIN = 20       # 马甲还要满足 b > r + 该值
MIN_SIDE = 8                # 铭牌最小边长（像素）
MIN_ASPECT = 1.5            # 铭牌是横向长方形
MAX_AREA_RATIO = 0.004      # 铭牌面积不超过画布的 0.4%
MIN_VEST_FRACTION = 0.30    # 四周一圈必须是马甲色

DEFAULT_TARGETS = (
    CHAR_DIR / "growdu_character_2k.png",
    CHAR_DIR / "growdu_character_2k_nobg.png",
)


def find_badge(image: Image.Image) -> tuple[int, int, int, int] | None:
    """返回铭牌矩形 (x0, y0, x1, y1)；找不到返回 None。"""
    arr = np.array(image.convert("RGBA"))
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    alpha = arr[..., 3]
    near_white = (r > NEAR_WHITE) & (g > NEAR_WHITE) & (b > NEAR_WHITE)
    if alpha.min() < 250:
        near_white &= alpha > 200      # 透明底版：先把背景剔掉
    labels, _ = ndimage.label(near_white)
    height, width = arr.shape[:2]
    vest = (
        (r < VEST_MAX[0]) & (g < VEST_MAX[1]) & (b < VEST_MAX[2])
        & (b > r + VEST_BLUE_MARGIN)
    )

    best: tuple[tuple[int, int, int, int], float] | None = None
    for index, sl in enumerate(ndimage.find_objects(labels), start=1):
        y0, y1 = sl[0].start, sl[0].stop
        x0, x1 = sl[1].start, sl[1].stop
        if x0 == 0 or y0 == 0 or x1 == width or y1 == height:
            continue                    # 与画布边缘相连 → 那是背景
        box_w, box_h = x1 - x0, y1 - y0
        if min(box_w, box_h) < MIN_SIDE:
            continue
        if box_w < MIN_ASPECT * box_h:
            continue                    # 铭牌是横向长方形
        if box_w * box_h > MAX_AREA_RATIO * width * height:
            continue
        ring = np.zeros_like(near_white)
        ring[max(0, y0 - 4):y1 + 4, max(0, x0 - 4):x1 + 4] = True
        ring[y0:y1, x0:x1] = False
        fraction = float(vest[ring].mean()) if ring.any() else 0.0
        if fraction < MIN_VEST_FRACTION:
            continue
        if best is None or fraction > best[1]:
            best = ((x0, y0, x1, y1), fraction)
    return best[0] if best else None


def blank_badge(path: str | Path) -> bool:
    """把铭牌刷成纯白。返回是否真的处理了。"""
    path = Path(path)
    if not path.exists():
        print(f"  - {path.name}：文件不存在，跳过", file=sys.stderr)
        return False
    image = Image.open(path).convert("RGBA")
    box = find_badge(image)
    if box is None:
        print(f"  - {path.name}：没找到铭牌，跳过")
        return False
    x0, y0, x1, y1 = box
    arr = np.array(image)
    arr[y0:y1, x0:x1, :3] = 255
    Image.fromarray(arr, "RGBA").save(path)
    print(f"  → {path.name}：铭牌 {box} 已刷白")
    return True


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    targets = [Path(a) for a in argv] if argv else list(DEFAULT_TARGETS)
    for target in targets:
        blank_badge(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
