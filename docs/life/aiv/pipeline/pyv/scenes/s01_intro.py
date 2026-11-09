"""段 A：身份 + 标题。小象挥手入场。"""
from __future__ import annotations

import os

from pyv import easing
from pyv.draw import text
from pyv.elephant import Pose, draw_elephant, load_parts
from pyv.palette import COLORS

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_IMAGE = os.path.join(_ROOT, "growdu.png")
_parts = None


def _get_parts():
    global _parts
    if _parts is None:
        _parts = load_parts(_IMAGE)
    return _parts


def render(ctx, t: float, w: int, h: int) -> None:
    """t ∈ [0,1] 为场景内进度。"""
    scale = h * 0.66 / 1289.0
    pose = Pose(wave=easing.clamp01((t - 0.18) * 2.4))
    draw_elephant(ctx, _get_parts(), pose, (w * 0.27, h * 0.90), scale)

    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.30) / 0.45)))
    text(ctx, "PostgreSQL 18", w * 0.50, h * 0.40, 104, COLORS["primary"], alpha=appear)
    text(ctx, "并行逻辑解码", w * 0.50, h * 0.56, 72, COLORS["accent"], bold=True,
         alpha=appear)
    text(ctx, "reader 协调 · 多 worker 并行 · 顺序一致",
         w * 0.50, h * 0.68, 38, COLORS["primary"], alpha=appear)
