"""通用绘图原语。"""
from __future__ import annotations

import math

import cairo

from pyv.palette import FONT_FAMILY, hex_to_rgb


def _set_source(ctx: cairo.Context, color: str, alpha: float = 1.0) -> None:
    r, g, b = hex_to_rgb(color)
    ctx.set_source_rgba(r, g, b, alpha)


def rounded_rect(ctx: cairo.Context, x: float, y: float, w: float, h: float,
                 r: float, color: str, alpha: float = 1.0) -> None:
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()
    _set_source(ctx, color, alpha)
    ctx.fill()


def stroke_rect(ctx: cairo.Context, x: float, y: float, w: float, h: float,
                r: float, color: str, width: float = 4.0, alpha: float = 1.0) -> None:
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()
    _set_source(ctx, color, alpha)
    ctx.set_line_width(width)
    ctx.stroke()


def arrow(ctx: cairo.Context, x1: float, y1: float, x2: float, y2: float,
          color: str, width: float = 6.0, head: float = 22.0,
          alpha: float = 1.0) -> None:
    _set_source(ctx, color, alpha)
    ctx.set_line_width(width)
    ctx.move_to(x1, y1)
    ctx.line_to(x2, y2)
    ctx.stroke()
    angle = math.atan2(y2 - y1, x2 - x1)
    for sign in (1, -1):
        a = angle + sign * math.radians(150)
        ctx.move_to(x2, y2)
        ctx.line_to(x2 + head * math.cos(a), y2 + head * math.sin(a))
    ctx.stroke()


def text(ctx: cairo.Context, s: str, x: float, y: float, size: float,
         color: str, anchor: str = "left", bold: bool = False,
         alpha: float = 1.0) -> None:
    """绘制一行文字，anchor 取 left / center / right。"""
    _set_source(ctx, color, alpha)
    ctx.select_font_face(
        FONT_FAMILY,
        cairo.FONT_SLANT_NORMAL,
        cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL,
    )
    ctx.set_font_size(size)
    width = ctx.text_extents(s).width
    if anchor == "center":
        x -= width / 2
    elif anchor == "right":
        x -= width
    ctx.move_to(x, y)
    ctx.show_text(s)


def text_width(ctx: cairo.Context, s: str, size: float) -> float:
    ctx.set_font_size(size)
    return ctx.text_extents(s).width
