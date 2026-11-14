"""段 F：价值收束 + 落版（个人头像，不使用任何公司 Logo）。

版式在代码里，**这一期的标题、副标题与落版标签在契约里**（`Scene.params`）。
"""
from __future__ import annotations

import math

import cairo
from PIL import Image

from pyv import character, easing
from pyv import scene_layout
from pyv.draw import rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "subtitle", "badge")

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


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s06")
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return
    enter = easing.ease_out_cubic(t / 0.20)
    slide = (1.0 - enter) * -w * 0.06
    bob = math.sin(t * math.pi * 1.8) * h * 0.006
    _mascot.draw(ctx, (w * 0.20, h * 0.92), h * 0.60,
                 alpha=enter, slide=slide, bob=bob)

    appear = easing.ease_out_cubic(max(0.0, min(1.0, t * 2.5)))
    text(ctx, p["title"], w * 0.40, h * 0.36, 76, COLORS["primary"],
         bold=True, alpha=appear)
    text(ctx, p["subtitle"], w * 0.40, h * 0.48, 44, COLORS["secondary"],
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
    text(ctx, p["badge"], label_x + w * 0.13, label_y + h * 0.05, 34,
         "#FFFFFF", anchor="center", alpha=appear)


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：标题 / 副标题在上，形象居中，落版在最下面。

    落版整块要留在字幕带（y=1393）之上——横版它落在 h*0.72，
    竖版换成绝对位置，不然按比例算会掉到字幕底下。
    """
    enter = easing.ease_out_cubic(t / 0.20)
    slide = (1.0 - enter) * -w * 0.06
    bob = math.sin(t * math.pi * 1.8) * h * 0.006
    _mascot.draw(ctx, (w * 0.5, h * 0.58), h * 0.32,
                 alpha=enter, slide=slide, bob=bob)

    appear = easing.ease_out_cubic(max(0.0, min(1.0, t * 2.5)))
    left = w * scene_layout.MARGIN_X
    max_width = w * scene_layout.CONTENT_W
    scene_layout.line(ctx, p["title"], left, h * scene_layout.TITLE_Y,
                      max_width, 60, COLORS["primary"], bold=True, alpha=appear)
    scene_layout.line(ctx, p["subtitle"], left, h * 0.135, max_width,
                      42, COLORS["secondary"], alpha=appear)

    # 落版：个人头像 + 身份标签。头像素材缺失时只留标签，布局不变。
    size = int(h * 0.078)
    avatar = character.avatar_path()
    badge_y = 1190
    if avatar is not None:
        _draw_avatar(ctx, avatar, left, badge_y, size, appear)

    label_x = left + (size * 1.15 if avatar is not None else 0.0)
    label_w = max(w * 0.26, size * 1.2)
    rounded_rect(ctx, label_x, badge_y, label_w, size * 0.78, 12,
                 COLORS["primary"], alpha=appear)
    scene_layout.line(ctx, p["badge"], label_x + label_w / 2,
                      badge_y + size * 0.54, label_w * 0.9, 34, "#FFFFFF",
                      alpha=appear, anchor="center")
