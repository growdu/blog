"""段 C：32 核机器上解码只占 1 核；大事务与小事务都跟不上。"""
from __future__ import annotations

from pyv import easing
from pyv.draw import rounded_rect, text
from pyv.palette import COLORS, hex_to_rgb

CORE_COUNT = 32
HIGHLIGHTED = 11  # 第 12 个核被点亮


def highlighted_cores() -> list[int]:
    """返回被点亮的核心下标，必须恰好一个。"""
    return [HIGHLIGHTED]


def render(ctx, t: float, w: int, h: int) -> None:
    text(ctx, "32 核机器，解码只占 1 核", w * 0.07, h * 0.15, 60,
         COLORS["primary"], bold=True)

    cols = 8
    cell_w, cell_h = w * 0.043, h * 0.088
    gap_x, gap_y = w * 0.011, h * 0.032
    x0, y0 = w * 0.07, h * 0.25
    pulse = easing.ease_out_cubic(max(0.0, (t - 0.20) / 0.55))
    lit = set(highlighted_cores())

    for i in range(CORE_COUNT):
        col, row = i % cols, i // cols
        x = x0 + col * (cell_w + gap_x)
        y = y0 + row * (cell_h + gap_y)
        rounded_rect(ctx, x, y, cell_w, cell_h, 8,
                     COLORS["accent"] if i in lit else "#DCE1E8")

    cx = x0 + (HIGHLIGHTED % cols) * (cell_w + gap_x) + cell_w / 2
    cy = y0 + (HIGHLIGHTED // cols) * (cell_h + gap_y) + cell_h / 2
    ctx.set_source_rgb(*hex_to_rgb(COLORS["accent"]))
    ctx.set_line_width(6)
    ctx.arc(cx, cy, cell_w * (0.72 + 0.22 * pulse), 0, 6.2832)
    ctx.stroke()

    text(ctx, "只用到 1 核", w * 0.07, h * 0.83, 40, COLORS["accent"], bold=True)

    # 右侧压力：大事务 + 小事务高并发
    text(ctx, "大事务", w * 0.56, h * 0.28, 42, COLORS["problem"], bold=True)
    rounded_rect(ctx, w * 0.56, h * 0.32, w * 0.30, h * 0.09, 10, COLORS["problem"])

    text(ctx, "小事务高并发", w * 0.56, h * 0.52, 42, COLORS["problem"], bold=True)
    for i in range(7):
        rounded_rect(ctx, w * 0.56 + i * w * 0.046, h * 0.56, w * 0.036, h * 0.065, 8,
                     COLORS["problem"] if i % 2 == 0 else "#F8C489")

    text(ctx, "都跟不上", w * 0.56, h * 0.78, 52, COLORS["primary"], bold=True)
