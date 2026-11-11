"""段 C：核阵列模板。

画一片核，只点亮其中一个；右侧两组方块表达压力。
版式在代码里，**这一期的文字与核数在契约里**（`Scene.params`）。
"""
from __future__ import annotations

from pyv import easing
from pyv.draw import rounded_rect, text
from pyv.palette import COLORS, hex_to_rgb
from pyv.params import Params

REQUIRED = ("title", "core_count", "core_cols", "highlighted_core", "stat",
            "big_label", "small_label", "conclusion")

SMALL_BLOCKS = 7


def highlighted_cores(params=None) -> list[int]:
    """返回被点亮的核心下标，必须恰好一个。"""
    p = Params(params, "s03")
    return [int(p["highlighted_core"])]


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s03")
    core_count = int(p["core_count"])
    cols = int(p["core_cols"])
    highlighted = int(p["highlighted_core"])

    text(ctx, p["title"], w * 0.07, h * 0.15, 60,
         COLORS["primary"], bold=True)

    cell_w, cell_h = w * 0.043, h * 0.088
    gap_x, gap_y = w * 0.011, h * 0.032
    x0, y0 = w * 0.07, h * 0.25
    pulse = easing.ease_out_cubic(max(0.0, (t - 0.20) / 0.55))
    lit = set(highlighted_cores(params))

    for i in range(core_count):
        col, row = i % cols, i // cols
        x = x0 + col * (cell_w + gap_x)
        y = y0 + row * (cell_h + gap_y)
        rounded_rect(ctx, x, y, cell_w, cell_h, 8,
                     COLORS["accent"] if i in lit else "#DCE1E8")

    cx = x0 + (highlighted % cols) * (cell_w + gap_x) + cell_w / 2
    cy = y0 + (highlighted // cols) * (cell_h + gap_y) + cell_h / 2
    ctx.set_source_rgb(*hex_to_rgb(COLORS["accent"]))
    ctx.set_line_width(6)
    ctx.arc(cx, cy, cell_w * (0.72 + 0.22 * pulse), 0, 6.2832)
    ctx.stroke()

    text(ctx, p["stat"], w * 0.07, h * 0.83, 40, COLORS["accent"], bold=True)

    # 右侧压力：大块 + 小块
    text(ctx, p["big_label"], w * 0.56, h * 0.28, 42, COLORS["problem"], bold=True)
    rounded_rect(ctx, w * 0.56, h * 0.32, w * 0.30, h * 0.09, 10, COLORS["problem"])

    text(ctx, p["small_label"], w * 0.56, h * 0.52, 42, COLORS["problem"], bold=True)
    for i in range(SMALL_BLOCKS):
        rounded_rect(ctx, w * 0.56 + i * w * 0.046, h * 0.56, w * 0.036, h * 0.065, 8,
                     COLORS["problem"] if i % 2 == 0 else "#F8C489")

    text(ctx, p["conclusion"], w * 0.56, h * 0.78, 52, COLORS["primary"], bold=True)
