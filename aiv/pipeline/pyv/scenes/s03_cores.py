"""段 C：核阵列模板。

画一片核，只点亮其中一个；右侧两组方块表达压力。
版式在代码里，**这一期的文字与核数在契约里**（`Scene.params`）。

**竖版（1080×1920）**：横版是「左核阵列 + 右压力」左右分栏，
竖版改成上下堆叠——核阵列铺满宽度放在上面，两组方块（上面一块大色块、
下面一排小色块）依次排在下面（见 `pyv/scene_layout.py` 的三条规矩）。
"""
from __future__ import annotations

from pyv import easing
from pyv import scene_layout
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
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return

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


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：核阵列在上，两组方块在下。

    横版是左右分栏，竖版改成上下堆叠。这个场景没有画面内的说明，
    所以内容一直排到内容区下沿。
    """
    core_count = int(p["core_count"])
    cols = int(p["core_cols"])
    highlighted = int(p["highlighted_core"])

    left = scene_layout.content_left(w)
    full_w = scene_layout.content_width(w)

    scene_layout.title(ctx, p["title"], w, h)

    # ---- 核阵列 ----
    cell_w, cell_h = 92, 80
    gap_x, gap_y = 24, 18
    grid_w = cols * cell_w + (cols - 1) * gap_x
    x0 = left + (full_w - grid_w) / 2
    y0 = scene_layout.content_top(h)
    pulse = easing.ease_out_cubic(max(0.0, (t - 0.20) / 0.55))
    lit = set(highlighted_cores(p.as_dict()))

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
    ctx.arc(cx, cy, cell_w * (0.70 + 0.06 * pulse), 0, 6.2832)
    ctx.stroke()

    # ---- 只用到一核 ----
    scene_layout.line(ctx, p["stat"], left, 685, full_w, 44,
                      COLORS["accent"], bold=True)

    # ---- 大事务：一整块 ----
    scene_layout.line(ctx, p["big_label"], left, 770, full_w, 44,
                      COLORS["problem"], bold=True)
    rounded_rect(ctx, left, 800, full_w, 90, 12, COLORS["problem"])

    # ---- 小事务高并发：许多小块 ----
    scene_layout.line(ctx, p["small_label"], left, 960, full_w, 44,
                      COLORS["problem"], bold=True)
    for i in range(SMALL_BLOCKS):
        rounded_rect(ctx, left + i * 136, 995, 118, 88, 8,
                     COLORS["problem"] if i % 2 == 0 else "#F8C489")

    # ---- 结论 ----
    scene_layout.line(ctx, p["conclusion"], left, 1165, full_w, 52,
                      COLORS["primary"], bold=True)
