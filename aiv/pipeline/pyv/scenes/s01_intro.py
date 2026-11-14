"""段 A：标题卡模板。

左边小象入场，右边三行文字（标题 / 副标题 / 标语）。
版式在代码里，**这一期的文字在契约里**（`Scene.params`）。

**竖版（1080×1920）**：横版是「左形象 + 右文字」，竖版改成
「上文字 + 下形象」——竖版只有 1080 宽，左右分栏会把每栏压到一半宽，
字全得缩。竖版里形象居中、文字左对齐在同一条竖轴上
（见 `pyv/scene_layout.py` 的三条规矩）。
"""
from __future__ import annotations

import math

from pyv import character, easing
from pyv import scene_layout
from pyv.draw import text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "subtitle", "tagline")

_mascot = character.Mascot()


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    """t ∈ [0,1] 为场景内进度。"""
    p = Params(params, "s01")
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return

    # 形象：滑入 + 淡入 + 轻微浮动。静帧形象做不了挥手，用浮动补一点生气。
    enter = easing.ease_out_cubic(t / 0.25)
    slide = (1.0 - enter) * -w * 0.08
    bob = math.sin(t * math.pi * 2.2) * h * 0.008
    _mascot.draw(ctx, (w * 0.27, h * 0.90), h * 0.66,
                 alpha=enter, slide=slide, bob=bob)

    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.30) / 0.45)))
    text(ctx, p["title"], w * 0.50, h * 0.40, 104, COLORS["primary"], alpha=appear)
    text(ctx, p["subtitle"], w * 0.50, h * 0.56, 72, COLORS["accent"], bold=True,
         alpha=appear)
    text(ctx, p["tagline"], w * 0.50, h * 0.68, 38, COLORS["primary"], alpha=appear)


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：标题 / 副标题 / 标语在上，形象在下。

    **字号不缩、框变宽**：竖版只有 1080 宽，但手机上看字要顶得住，
    所以字号跟横版同档甚至更大，靠「每行字都过一遍 fit_size」来保证
    放得下。
    """
    enter = easing.ease_out_cubic(t / 0.25)
    slide = (1.0 - enter) * -w * 0.08
    bob = math.sin(t * math.pi * 2.2) * h * 0.008
    # 形象居中：脚下落在内容区下沿，头上留出文字的位置
    _mascot.draw(ctx, (w * 0.5, h * 0.64), h * 0.40,
                 alpha=enter, slide=slide, bob=bob)

    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.30) / 0.45)))
    left = w * scene_layout.MARGIN_X
    max_width = w * scene_layout.CONTENT_W
    scene_layout.line(ctx, p["title"], left, h * scene_layout.TITLE_Y,
                      max_width, 64, COLORS["primary"], alpha=appear)
    scene_layout.line(ctx, p["subtitle"], left, h * 0.138, max_width,
                      46, COLORS["accent"], bold=True, alpha=appear)
    scene_layout.line(ctx, p["tagline"], left, h * 0.188, max_width,
                      32, COLORS["primary"], alpha=appear)
