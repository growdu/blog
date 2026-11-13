"""颜色、字体与画布尺寸常量。

字体族名不在这里定死——跨平台由 `pyv.fonts` 解析（macOS 用 PingFang SC，
Linux 退到 Noto Sans CJK SC）。要拿族名就调 `fonts.font_family()`。
"""
from __future__ import annotations

from pyv import fonts

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

def assert_font_available() -> None:
    """字体不可用时立即失败，避免跨机渲染出豆腐块。

    真正的判定在 `pyv.fonts`：那里负责跨平台挑字体族，并按平台给出
    安装提示（PingFang 是 Apple 授权字体，Linux 上必须退到开源字体）。
    """
    fonts.assert_font_available()


def hex_to_rgb(value: str) -> tuple[float, float, float]:
    """'#RRGGBB' → (r, g, b)，分量范围 0..1。"""
    value = value.lstrip("#")
    return (
        int(value[0:2], 16) / 255.0,
        int(value[2:4], 16) / 255.0,
        int(value[4:6], 16) / 255.0,
    )
