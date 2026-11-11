#!/usr/bin/env python3
"""给胸口铭牌印上 growdu（真实字体渲染）。

规范：铭牌**必须**显示 growdu——那是品牌标识，不能空着。但文字**不能**交给
模型生成：模型的中英文会乱码（growdu 可能变成 giowdu / grawdu）。

所以生成之后统一做一次后处理：

  1. 自动定位胸口那块白铭牌（不硬编码坐标，重生成后依然有效）
  2. 把铭牌刷成纯白，抹掉模型写的任何字
  3. 用 PingFang SC 写上 growdu

文字来源于是从「模型碰运气」变成「代码确定」：模型这次碰巧写对了也不算数，
下次重新生成时铭牌照样是对的。

铭牌定位：
  1. 铭牌在马甲上，所以先取最大一块马甲色连通块的包围盒，只在这块区域里找
     「近白色」的连通块——这一条约束同时挡掉了白底图里的大片背景
  2. 候选必须是横向长方形、边长与面积都够大
  3. 铭牌是「被深藏蓝马甲围住的一小块白」，所以四周一圈马甲色占比最高的那个
     就是它

用法：
  python3 scripts/stamp_badge.py                  # 处理默认素材
  python3 scripts/stamp_badge.py <png> [png...]   # 处理指定文件
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import cairo
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
AIV = HERE.parent.parent                     # docs/life/aiv
CHAR_DIR = AIV / "character"
BRAND_ASSETS = AIV / "brand" / "assets"

FONT = "PingFang SC"
TEXT = "growdu"
TEXT_COLOR = (0x1B, 0x2A, 0x47)          # 深藏蓝，跟字幕主色一致
TEXT_WIDTH_RATIO = 0.76                  # 文字宽度占铭牌宽度的比例
TEXT_HEIGHT_RATIO = 0.52                 # 文字高度占铭牌高度的比例

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
    BRAND_ASSETS / "growdu_pose_thumbsup_nobg.png",
    BRAND_ASSETS / "growdu_pose_wave_nobg.png",
)


@dataclass(frozen=True)
class Badge:
    """铭牌的几何信息。origin 是文字基线起点（相对铭牌左上角）。"""
    box: tuple[int, int, int, int]
    size: int
    origin: tuple[float, float]


def find_badge(image: Image.Image) -> tuple[int, int, int, int] | None:
    """返回铭牌矩形 (x0, y0, x1, y1)；找不到返回 None。

    铭牌在马甲上，所以只在**马甲区域内**找白块——这一条约束同时挡掉了
    白底图里的大片背景，避免白色连通块被误当成铭牌。
    """
    arr = np.array(image.convert("RGBA"))
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    alpha = arr[..., 3]
    near_white = (r > NEAR_WHITE) & (g > NEAR_WHITE) & (b > NEAR_WHITE)
    if alpha.min() < 250:
        near_white &= alpha > 200      # 透明底版：先把背景剔掉
    vest = (
        (r < VEST_MAX[0]) & (g < VEST_MAX[1]) & (b < VEST_MAX[2])
        & (b > r + VEST_BLUE_MARGIN)
    )

    # 马甲区域 = 所有马甲色像素的包围盒。
    # 不能用「最大连通块」：马甲被渐变阴影切碎了，最大那块未必包住铭牌。
    ys, xs = np.nonzero(vest)
    if len(xs) == 0:
        return None
    vx0, vx1 = int(xs.min()), int(xs.max()) + 1
    vy0, vy1 = int(ys.min()), int(ys.max()) + 1

    labels, _ = ndimage.label(near_white)
    height, width = arr.shape[:2]
    best: tuple[tuple[int, int, int, int], float] | None = None
    for index, sl in enumerate(ndimage.find_objects(labels), start=1):
        y0, y1 = sl[0].start, sl[0].stop
        x0, x1 = sl[1].start, sl[1].stop
        if x0 == 0 or y0 == 0 or x1 == width or y1 == height:
            continue                    # 与画布边缘相连 → 那是背景
        if x0 < vx0 or x1 > vx1 or y0 < vy0 or y1 > vy1:
            continue                    # 不在马甲上 → 不是铭牌
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


def _measure(ctx: cairo.Context, text: str, size: float):
    ctx.set_font_size(size)
    return ctx.text_extents(text)


def _fit_text(ctx: cairo.Context, text: str, box_w: int, box_h: int) -> int:
    """挑一个既放得下、又尽量大的字号。

    cairo 的 text_extents 依次是
    (x_bearing, y_bearing, width, height, x_advance, y_advance)，
    其中 height 就是墨迹高度。
    """
    max_w = box_w * TEXT_WIDTH_RATIO
    max_h = box_h * TEXT_HEIGHT_RATIO
    ext = _measure(ctx, text, 100.0)
    width, height = ext[2], ext[3]
    # 两个方向的缩放都从基准字号 100 算，否则会连乘、字号被压到极小
    size = 100.0
    if width > 0:
        size = min(size, 100.0 * max_w / width)
    if height > 0:
        size = min(size, 100.0 * max_h / height)
    size = int(max(6, round(size)))
    while size > 6:
        ext = _measure(ctx, text, float(size))
        if ext[2] <= max_w and ext[3] <= max_h:
            break
        size -= 1
    return size


def render_text_mask(text: str, size: int, origin: tuple[float, float],
                     width: int, height: int) -> np.ndarray:
    """把一段文字渲染成 alpha 掩膜（供合成与测试比对）。"""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(float(size))
    ctx.set_source_rgba(0.0, 0.0, 0.0, 1.0)
    ctx.move_to(origin[0], origin[1])
    ctx.show_text(text)
    surface.flush()
    stride = surface.get_stride()
    data = bytes(surface.get_data())
    arr = np.frombuffer(data, dtype=np.uint8).reshape(height, stride // 4, 4)
    return arr[:, :width, 3].copy()


def plan_badge(image: Image.Image) -> Badge | None:
    """算出铭牌矩形、字号与文字基线起点。"""
    box = find_badge(image)
    if box is None:
        return None
    x0, y0, x1, y1 = box
    box_w, box_h = x1 - x0, y1 - y0
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    ctx = cairo.Context(surface)
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    size = _fit_text(ctx, TEXT, box_w, box_h)
    ext = _measure(ctx, TEXT, float(size))
    x_bearing, y_bearing = ext[0], ext[1]
    width, ink_height = ext[2], ext[3]
    x = (box_w - width) / 2 - x_bearing
    baseline = (box_h - ink_height) / 2 - y_bearing
    return Badge(box=box, size=size, origin=(x, baseline))


def stamp_badge(path: str | Path) -> Badge | None:
    """把铭牌刷白并印上 growdu。返回铭牌信息；没找到铭牌返回 None。"""
    path = Path(path)
    if not path.exists():
        print(f"  - {path.name}：文件不存在，跳过", file=sys.stderr)
        return None
    image = Image.open(path).convert("RGBA")
    badge = plan_badge(image)
    if badge is None:
        print(f"  - {path.name}：没找到铭牌，跳过")
        return None
    x0, y0, x1, y1 = badge.box
    box_w, box_h = x1 - x0, y1 - y0

    arr = np.array(image)
    # 1. 抹掉模型写的任何字，整块刷成纯白
    arr[y0:y1, x0:x1, :3] = 255
    # 2. 用真实字体写上 growdu
    mask = render_text_mask(TEXT, badge.size, badge.origin, box_w, box_h)
    alpha = (mask.astype(np.uint16) / 255.0)[..., None]
    color = np.array(TEXT_COLOR, dtype=np.float64)[None, None, :]
    region = arr[y0:y1, x0:x1, :3].astype(np.float64)
    arr[y0:y1, x0:x1, :3] = np.clip(
        region * (1 - alpha) + color * alpha, 0, 255
    ).astype(np.uint8)

    Image.fromarray(arr, "RGBA").save(path)
    print(f"  → {path.name}：铭牌 {badge.box} 已印上 {TEXT}（{badge.size}px）")
    return badge


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    targets = [Path(a) for a in argv] if argv else list(DEFAULT_TARGETS)
    for target in targets:
        stamp_badge(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
