"""段 F：异构数据同步价值 + 落版（个人头像，不使用任何公司 Logo）。"""
from __future__ import annotations

import math

import cairo
from PIL import Image

from pyv import character, easing
from pyv.draw import rounded_rect, text
from pyv.palette import COLORS

_mascot = character.Mascot()


def _draw_avatar(ctx, path, x: float, y: float, size: int, alpha: float) -> None:
    """圆形头像。"""
    image = Image.open(path).convert("RGBA").resize((size, size))
    surface = character.pil_to_cairo(image)
    ctx.save()
    ctx.arc(x + size / 2, y + size / 2, size / 2, 0, 2 * math.pi)
    ctx.clip()
    ctx.set_source_surface(surface, x, y)
    ctx.paint_with_alpha(alpha)
    ctx.restore()


def render(ctx, t: float, w: int, h: int) -> None:
    enter = easing.ease_out_cubic(t / 0.20)
    slide = (1.0 - enter) * -w * 0.06
    bob = math.sin(t * math.pi * 1.8) * h * 0.006
    _mascot.draw(ctx, (w * 0.20, h * 0.92), h * 0.60,
                 alpha=enter, slide=slide, bob=bob)

    appear = easing.ease_out_cubic(max(0.0, min(1.0, t * 2.5)))
    text(ctx, "并行解码 · 有序同步", w * 0.40, h * 0.36, 76, COLORS["primary"],
         bold=True, alpha=appear)
    text(ctx, "异构数据同步场景，实用性很高", w * 0.40, h * 0.48, 44, COLORS["secondary"],
         alpha=appear)

    # 落版：个人头像 + 身份标签。头像素材缺失时只留标签，布局不变。
    size = int(h * 0.15)
    avatar = character.avatar_path()
    if avatar is not None:
        _draw_avatar(ctx, avatar, w * 0.40, h * 0.72, size, appear)

    label_x = w * 0.40 + (size * 1.15 if avatar is not None else 0.0)
    label_y = h * 0.72 + size * 0.22
    rounded_rect(ctx, label_x, label_y, w * 0.26, h * 0.075, 12,
                 COLORS["primary"], alpha=appear)
    text(ctx, "独立开发者 · growdu", label_x + w * 0.13, label_y + h * 0.05, 34,
         "#FFFFFF", anchor="center", alpha=appear)
