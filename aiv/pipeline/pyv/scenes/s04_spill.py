"""段 D：攒不下就落盘的模板。

左边是内存里的那块缓冲，攒得太多时从右边溢出去，落到磁盘上。
芯片一块块搬过去——搬的是变更本身，事务的边界不丢。

版式在代码里，**这一期的标签与文案在契约里**（`Scene.params`）。
"""
from __future__ import annotations

from pyv import easing
from pyv.draw import arrow, rounded_rect, stroke_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "memory_label", "disk_label", "spill_label", "chips",
            "spill_count", "caption")

# 搬动一块芯片的间隔（场景进度）
MOVE_STEP = 0.055
MOVE_DELAY = 0.30

# 内存区里芯片的排布
COLS = 3
CHIP_W_RATIO = 0.095
CHIP_H_RATIO = 0.052


def chip_slots(count: int, left: float, top: float, width: float,
               height: float, w: int, h: int) -> list[tuple[float, float]]:
    """内存区里每块芯片的初始位置。"""
    chip_w = w * CHIP_W_RATIO
    chip_h = h * CHIP_H_RATIO
    rows = max(1, (count + COLS - 1) // COLS)
    gap_x = (width - COLS * chip_w) / (COLS + 1)
    gap_y = (height - rows * chip_h) / (rows + 1)
    out: list[tuple[float, float]] = []
    for index in range(count):
        row, col = divmod(index, COLS)
        x = left + gap_x + col * (chip_w + gap_x)
        y = top + gap_y + row * (chip_h + gap_y)
        out.append((x, y))
    return out


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s04")
    chips = [str(x) for x in p["chips"]]

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    # ---- 内存区 ----
    mem_x, mem_y = w * 0.07, h * 0.28
    mem_w, mem_h = w * 0.40, h * 0.48
    rounded_rect(ctx, mem_x, mem_y, mem_w, mem_h, 16, "#F2F5F9")
    stroke_rect(ctx, mem_x, mem_y, mem_w, mem_h, 16, "#DCE1E8", 3, 0.9)
    text(ctx, p["memory_label"], mem_x + w * 0.02, mem_y + h * 0.075, 40,
         COLORS["primary"], bold=True)

    # ---- 磁盘区 ----
    disk_x, disk_y = w * 0.66, h * 0.30
    disk_w, disk_h = w * 0.28, h * 0.44
    rounded_rect(ctx, disk_x, disk_y, disk_w, disk_h, 16, COLORS["primary"])
    text(ctx, p["disk_label"], disk_x + disk_w / 2, disk_y + h * 0.085, 40,
         "#FFFFFF", anchor="center", bold=True)
    for index in range(3):
        line_y = disk_y + disk_h - h * 0.035 - index * h * 0.028
        rounded_rect(ctx, disk_x + disk_w * 0.12, line_y, disk_w * 0.76, 5, 2,
                     "#FFFFFF", alpha=0.30)

    # ---- 溢出的箭头 ----
    arrow(ctx, mem_x + mem_w + w * 0.015, mem_y + mem_h * 0.52,
          disk_x - w * 0.015, disk_y + disk_h * 0.52,
          COLORS["accent"], 7, 24)
    text(ctx, p["spill_label"], (mem_x + mem_w + disk_x) / 2, mem_y + mem_h * 0.44,
         40, COLORS["accent"], anchor="center", bold=True)

    # ---- 芯片一块块搬进磁盘 ----
    chip_w = w * CHIP_W_RATIO
    chip_h = h * CHIP_H_RATIO
    area_top = mem_y + h * 0.11
    area_h = mem_h - h * 0.15
    starts = chip_slots(len(chips), mem_x, area_top, mem_w, area_h, w, h)
    # 落到磁盘里的位置：两列三行
    land_cols = 2
    land_gap = w * 0.012
    land_row_h = chip_h + h * 0.014
    land_x0 = disk_x + (disk_w - (land_cols * chip_w + (land_cols - 1) * land_gap)) / 2
    land_y = disk_y + h * 0.135
    for index, (label, (sx, sy)) in enumerate(zip(chips, starts)):
        if index >= int(p["spill_count"]):
            # 还留在内存里的：不动
            rounded_rect(ctx, sx, sy, chip_w, chip_h, 9, COLORS["secondary"])
            text(ctx, label, sx + chip_w / 2, sy + chip_h * 0.70, 28, "#FFFFFF",
                 anchor="center", bold=True)
            continue
        move = easing.ease_in_out(
            max(0.0, min(1.0, (t - MOVE_DELAY - MOVE_STEP * index) * 3.2))
        )
        row, col = divmod(index, land_cols)
        land_x = land_x0 + col * (chip_w + land_gap)
        x = sx + (land_x - sx) * move
        y = sy + (land_y + row * land_row_h - sy) * move
        alpha = 1.0 - 0.30 * move
        rounded_rect(ctx, x, y, chip_w, chip_h, 9, COLORS["secondary"], alpha=alpha)
        text(ctx, label, x + chip_w / 2, y + chip_h * 0.70, 28, "#FFFFFF",
             anchor="center", bold=True, alpha=alpha)

    text(ctx, p["caption"], w * 0.07, h * 0.90, 44, COLORS["primary"])
