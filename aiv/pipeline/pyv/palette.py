"""颜色、字体与画布尺寸常量。

字体族名不在这里定死——跨平台由 `pyv.fonts` 解析（macOS 用 PingFang SC，
Linux 退到 Noto Sans CJK SC）。要拿族名就调 `fonts.font_family()`。
"""
from __future__ import annotations

from pyv import fonts

WIDTH = 1920
HEIGHT = 1080
FPS = 24

# 竖版画布（抖音那一档）：9:16。
#
# **为什么是 1080×1920 而不是 720×1280**：抖音官方上传接口的响应示例里
# 就是 720×1280，但那是示例不是限制。1080×1920 是主流竖版规格，
# 1080 宽正好让字幕与标题的字号跟横版保持同一档（见 `subtitle.draw_event`
# 按短边缩放）。
VERTICAL_WIDTH = 1080
VERTICAL_HEIGHT = 1920

# 支持的画布：名字 → (宽, 高)。
#
# **横版是默认值，行为一个字都不能变。** 竖版是新增的档，不是替换。
CANVASES = {
    "horizontal": (WIDTH, HEIGHT),
    "vertical": (VERTICAL_WIDTH, VERTICAL_HEIGHT),
}

# 竖版底部留给平台 UI 的高度（导航栏与文案区）。
#
# 这是**工程上的保守取值**，不是平台文档里写明的数字——抖音没有公开
# 「安全区」规格。与其等审核时才发现字幕被导航栏压住，不如自己留出
# 一条。横版不用留（这一档发的是视频号/B站，横版视频不叠 UI）。
VERTICAL_UI_BOTTOM = 420

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


def canvas(name: str) -> tuple[int, int]:
    """按名字取画布尺寸（宽, 高）。"""
    if name not in CANVASES:
        raise ValueError(
            f"未知画布：{name}（可选：{'、'.join(sorted(CANVASES))}）"
        )
    return CANVASES[name]


def is_vertical(width: int, height: int) -> bool:
    """画布是不是竖版（高 > 宽）。

    场景模块靠它选版式。**判据只看高宽比**，不认画布名字——
    这样以后加 4:5 之类的档，场景不用改。
    """
    return height > width


def short_side(width: int, height: int) -> int:
    """画布的短边。

    字号按短边缩放：横版是 1080（等于原来的基准），竖版也是 1080，
    所以同一段文字在两种画布里**绝对像素一样大**，而相对画面的占比
    竖版更大——这正是竖版视频要的（手机上看，文字要顶得住）。
    """
    return min(width, height)

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
