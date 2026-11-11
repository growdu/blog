"""段 A：标题卡模板。

左边小象入场，右边三行文字（标题 / 副标题 / 标语）。
版式在代码里，**这一期的文字在契约里**（`Scene.params`）。
"""
from __future__ import annotations

import math

from pyv import character, easing
from pyv.draw import text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "subtitle", "tagline")

_mascot = character.Mascot()


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    """t ∈ [0,1] 为场景内进度。"""
    p = Params(params, "s01")
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
