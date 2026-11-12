"""段 D：攒不下就落盘的模板。

左边是内存里的那块缓冲，攒得太多时从右边溢出去，落到磁盘上。
芯片一块块搬过去——搬的是变更本身，事务的边界不丢。

版式在代码里，**这一期的标签与文案在契约里**（`Scene.params`）。

芯片的位置由 `chip_layout()` 一处算出：渲染与测试共用同一份算法，
这样「任何时刻两块芯片都不重叠」这条约束才能被测试盯住，
而不是靠肉眼看渲染图。
"""
from __future__ import annotations

from typing import NamedTuple

from pyv import easing
from pyv.draw import arrow, rounded_rect, stroke_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "memory_label", "disk_label", "spill_label", "chips",
            "spill_count", "caption")


class Chip(NamedTuple):
    """一块芯片在某一时刻的位置。progress 是搬运进度（0 还在内存，1 已落盘）。"""

    index: int
    x: float
    y: float
    progress: float


# 搬动一块芯片的间隔（场景进度）
# 一块搬完再搬下一块：几块同时在半空里飞，路径会交叉，
# 后一块把前一块的字压掉（画面上会读成半个单词）。
MOVE_STEP = 0.185
MOVE_DELAY = 0.15
MOVE_SPEED = 6.0

# 内存区里芯片的排布
COLS = 3
CHIP_W_RATIO = 0.095
CHIP_H_RATIO = 0.052

# 两块版式：内存区与磁盘区
MEM_X_RATIO, MEM_Y_RATIO, MEM_W_RATIO, MEM_H_RATIO = 0.07, 0.28, 0.40, 0.48
DISK_X_RATIO, DISK_Y_RATIO, DISK_W_RATIO, DISK_H_RATIO = 0.66, 0.30, 0.28, 0.44

# 磁盘里芯片落点的排布
# 行距要够大：落点第一行必须在搬运走廊下方，
# 否则后面一块沿走廊横穿时，会从已经落好的那一块身上压过去。
LAND_COLS = 2
LAND_GAP_RATIO = 0.012
LAND_ROW_GAP_RATIO = 0.088
LAND_TOP_RATIO = 0.135


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


def chip_layout(chips: list[str], spill_count: int, t: float,
                w: int = 1920, h: int = 1080) -> list["Chip"]:
    """每一块芯片在 t 时刻的位置。

    **槽位怎么分**：留在内存的占左边，搬走的占右边；同一排里从右往左搬——
    右边那块先飞走腾出位置，左边那块再横着飞过去时，路过的地方已经空了。
    **落点怎么排**：按飞行顺序反着排，先飞的那块落到最里侧，
    后飞的从它外侧飞过去，不会从已经落好的芯片身上压过去。
    """
    chip_w = w * CHIP_W_RATIO
    chip_h = h * CHIP_H_RATIO
    mem_x, mem_y = w * MEM_X_RATIO, h * MEM_Y_RATIO
    mem_w, mem_h = w * MEM_W_RATIO, h * MEM_H_RATIO
    disk_x, disk_y = w * DISK_X_RATIO, h * DISK_Y_RATIO
    disk_w = w * DISK_W_RATIO

    slots = chip_slots(len(chips), mem_x, mem_y + h * 0.08, mem_w,
                        mem_h - h * 0.26, w, h)
    stay_idx = list(range(spill_count, len(chips)))
    move_idx = list(range(spill_count))

    slot_of: dict[int, tuple[float, float]] = {}
    for n, index in enumerate(stay_idx):
        slot_of[index] = slots[n]
    for n, index in enumerate(move_idx):
        slot_of[index] = slots[len(slots) - 1 - n]

    land_gap = w * LAND_GAP_RATIO
    land_row_h = chip_h + h * LAND_ROW_GAP_RATIO
    land_x0 = disk_x + (disk_w - (LAND_COLS * chip_w + (LAND_COLS - 1) * land_gap)) / 2
    land_top = disk_y + h * LAND_TOP_RATIO
    # 搬运走廊就是箭头所在的那条线：芯片先落到这条线上，
    # 沿箭头横穿过去，再落进盘里的格子。
    corridor_y = mem_y + mem_h * 0.52 - chip_h * 0.5

    out: list[Chip] = []
    for index in stay_idx:
        sx, sy = slot_of[index]
        out.append(Chip(index, sx, sy, 0.0))

    for order, index in enumerate(move_idx):
        sx, sy = slot_of[index]
        move = easing.ease_in_out(
            max(0.0, min(1.0, (t - MOVE_DELAY - MOVE_STEP * order) * MOVE_SPEED))
        )
        row, col = divmod(order, LAND_COLS)
        land_x = land_x0 + col * (chip_w + land_gap)
        land_y = land_top + row * land_row_h

        if move < 0.25:
            # 第一段：落到走廊上
            u = move / 0.25
            x, y = sx, sy + (corridor_y - sy) * u
        elif move < 0.75:
            # 第二段：沿走廊横穿
            u = (move - 0.25) / 0.5
            x = sx + (land_x - sx) * u
            y = corridor_y
        else:
            # 第三段：落进格子
            u = (move - 0.75) / 0.25
            x = land_x
            y = corridor_y + (land_y - corridor_y) * u
        out.append(Chip(index, x, y, move))
    return out


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s04")
    chips = [str(x) for x in p["chips"]]

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    # ---- 内存区 ----
    mem_x, mem_y = w * MEM_X_RATIO, h * MEM_Y_RATIO
    mem_w, mem_h = w * MEM_W_RATIO, h * MEM_H_RATIO
    rounded_rect(ctx, mem_x, mem_y, mem_w, mem_h, 16, "#F2F5F9")
    stroke_rect(ctx, mem_x, mem_y, mem_w, mem_h, 16, "#DCE1E8", 3, 0.9)
    text(ctx, p["memory_label"], mem_x + w * 0.02, mem_y + h * 0.055, 40,
         COLORS["primary"], bold=True)

    # ---- 磁盘区 ----
    disk_x, disk_y = w * DISK_X_RATIO, h * DISK_Y_RATIO
    disk_w, disk_h = w * DISK_W_RATIO, h * DISK_H_RATIO
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
    # 标签压在搬运走廊的上方：在飞的芯片从这条走廊上经过，
    # 标签跟箭头挨太近就会被芯片盖住。
    text(ctx, p["spill_label"], (mem_x + mem_w + disk_x) / 2, mem_y + mem_h * 0.27,
         40, COLORS["accent"], anchor="center", bold=True)

    # ---- 芯片一块块搬进磁盘 ----
    chip_w = w * CHIP_W_RATIO
    chip_h = h * CHIP_H_RATIO
    for chip in chip_layout(chips, int(p["spill_count"]), t, w, h):
        alpha = 1.0 - 0.30 * chip.progress
        rounded_rect(ctx, chip.x, chip.y, chip_w, chip_h, 9, COLORS["secondary"],
                     alpha=alpha)
        text(ctx, chips[chip.index], chip.x + chip_w / 2, chip.y + chip_h * 0.70, 28,
             "#FFFFFF", anchor="center", bold=True, alpha=alpha)

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])
