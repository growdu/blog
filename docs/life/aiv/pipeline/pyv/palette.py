"""颜色、字体与画布尺寸常量。"""
from __future__ import annotations

import glob
import os

import cairo

WIDTH = 1920
HEIGHT = 1080
FPS = 24

COLORS = {
    "bg": "#FFFFFF",
    "primary": "#2B4C7E",
    "accent": "#F5A623",
    "secondary": "#4FD1C5",
    "cheek": "#F8BBD0",
    "problem": "#F6AD55",
    "subtitle_text": "#1B2A47",
    "subtitle_outline": "#FFFFFF",
}

FONT_FAMILY = "PingFang SC"

PINGFANG_CANDIDATES = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/PingFang SC.ttc",
)

# macOS 新版把 PingFang 放在可下载资产目录里，文件名带哈希，需 glob
PINGFANG_ASSET_GLOB = (
    "/System/Library/AssetsV2/com_apple_MobileAsset_Font8/*/AssetData/PingFang.ttc"
)


def _font_paths() -> list[str]:
    paths = list(PINGFANG_CANDIDATES)
    paths.extend(sorted(glob.glob(PINGFANG_ASSET_GLOB)))
    return paths


def _resolved_width(family: str, sample: str = "并行解码") -> float:
    """cairo 实际解析该字体族后的文本宽度。"""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    ctx = cairo.Context(surface)
    ctx.select_font_face(family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(40)
    return ctx.text_extents(sample).width


def assert_font_available() -> None:
    """字体不可用时立即失败，避免跨机渲染出豆腐块。

    判定方式：先看字体文件是否存在；文件不在（macOS 可下载资产）时，
    改用 cairo 实测——真字体族与不存在字体的文本宽度必然不同。
    """
    if any(os.path.exists(p) for p in _font_paths()):
        return
    fallback = _resolved_width("__NoSuchFontFamily__")
    if abs(_resolved_width(FONT_FAMILY) - fallback) > 0.5:
        return
    raise RuntimeError(
        f"字体族 {FONT_FAMILY} 无法解析，拒绝渲染（避免输出豆腐块）"
    )


def hex_to_rgb(value: str) -> tuple[float, float, float]:
    """'#RRGGBB' → (r, g, b)，分量范围 0..1。"""
    value = value.lstrip("#")
    return (
        int(value[0:2], 16) / 255.0,
        int(value[2:4], 16) / 255.0,
        int(value[4:6], 16) / 255.0,
    )
