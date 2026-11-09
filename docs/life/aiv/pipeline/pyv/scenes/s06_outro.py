"""段 F：异构数据同步价值 + 落版（个人头像，不使用任何公司 Logo）。"""
from __future__ import annotations

import os

import cairo
from PIL import Image

from pyv import easing
from pyv.draw import rounded_rect, text
from pyv.elephant import Pose, draw_elephant, load_parts
from pyv.palette import COLORS

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_IMAGE = os.path.join(_ROOT, "growdu.png")
_AVATAR = os.path.join(_ROOT, "growdu.jpg")
_parts = None


def _get_parts():
    global _parts
    if _parts is None:
        _parts = load_parts(_IMAGE)
    return _parts


def render(ctx, t: float, w: int, h: int) -> None:
    scale = h * 0.60 / 1289.0
    pose = Pose(nod=easing.clamp01(t * 2.0))
    draw_elephant(ctx, _get_parts(), pose, (w * 0.20, h * 0.92), scale)

    appear = easing.ease_out_cubic(max(0.0, min(1.0, t * 2.5)))
    text(ctx, "并行解码 · 有序同步", w * 0.40, h * 0.36, 76, COLORS["primary"],
         bold=True, alpha=appear)
    text(ctx, "异构数据同步场景，实用性很高", w * 0.40, h * 0.48, 44, COLORS["secondary"],
         alpha=appear)

    if os.path.exists(_AVATAR):
        size = int(h * 0.15)
        avatar = Image.open(_AVATAR).convert("RGBA").resize((size, size))
        arr = avatar.getdata()
        surface = cairo.ImageSurface.create_for_data(
            bytearray(avatar.tobytes()), cairo.FORMAT_ARGB32,
            avatar.width, avatar.height, avatar.width * 4)
        ctx.save()
        ctx.arc(w * 0.40 + size / 2, h * 0.72 + size / 2, size / 2, 0, 6.2832)
        ctx.clip()
        ctx.set_source_surface(surface, w * 0.40, h * 0.72)
        ctx.paint()
        ctx.restore()

    rounded_rect(ctx, w * 0.40 + size * 1.15, h * 0.72 + size * 0.22,
                 w * 0.26, h * 0.075, 12, COLORS["primary"], alpha=appear)
    text(ctx, "独立开发者 · growdu", w * 0.40 + size * 1.15 + w * 0.13,
         h * 0.72 + size * 0.22 + h * 0.05, 34, "#FFFFFF", anchor="center", alpha=appear)
