"""段 A：身份 + 标题。小象挥手入场。"""
from __future__ import annotations

import math

from pyv import character, easing
from pyv.draw import text
from pyv.elephant import Pose
from pyv.palette import COLORS

_mascot = character.Mascot()


def render(ctx, t: float, w: int, h: int) -> None:
    """t ∈ [0,1] 为场景内进度。"""
    # 形象：滑入 + 淡入 + 轻微浮动。
    # 静帧形象做不了挥手，用浮动补一点生气；旧 2D 形象走部件动画。
    enter = easing.ease_out_cubic(t / 0.25)
    slide = (1.0 - enter) * -w * 0.08
    bob = math.sin(t * math.pi * 2.2) * h * 0.008
    _mascot.draw(ctx, (w * 0.27, h * 0.90), h * 0.66,
                 alpha=enter, pose=Pose(wave=easing.clamp01((t - 0.18) * 2.4)),
                 slide=slide, bob=bob)

    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.30) / 0.45)))
    text(ctx, "PostgreSQL 18", w * 0.50, h * 0.40, 104, COLORS["primary"], alpha=appear)
    text(ctx, "并行逻辑解码", w * 0.50, h * 0.56, 72, COLORS["accent"], bold=True,
         alpha=appear)
    text(ctx, "reader 协调 · 多 worker 并行 · 顺序一致",
         w * 0.50, h * 0.68, 38, COLORS["primary"], alpha=appear)
