"""段 B：两个事务抢同一行。

一条记录，两边都写。左边的事务写一个值，右边的事务写另一个值，
两条箭头都落到同一行。读的那一侧互不打扰，写的那一侧却会互相覆盖。

版式在代码里，**这一期的表名、行号、写入值与文案在契约里**（`Scene.params`）。

**竖版（1080×1920）**：横版是「两个事务在左右两边，箭头从两边指进同一行」；
竖版改成「两个事务在上下两头，箭头从上下指进同一行」——同一行的
争夺，从相反的方向来。
"""
from __future__ import annotations

from pyv import easing
from pyv import scene_layout
from pyv.draw import arrow, rounded_rect, stroke_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "table_label", "row_label", "txn_a", "txn_b",
            "write_a", "write_b", "conclusion", "caption")

# 两条事务的颜色：左边偏橙，右边偏青
TXN_COLORS = ("#F6AD55", "#4FD1C5")

# 版式常量
TBL_X_RATIO, TBL_Y_RATIO = 0.28, 0.42
TBL_W_RATIO, TBL_H_RATIO = 0.44, 0.22
CHIP_W_RATIO, CHIP_H_RATIO = 0.16, 0.075
CHIP_A_X_RATIO, CHIP_B_X_RATIO = 0.04, 0.80
CHIP_Y_RATIO = 0.27
CONCL_X_RATIO, CONCL_Y_RATIO = 0.22, 0.70
CONCL_W_RATIO, CONCL_H_RATIO = 0.56, 0.075


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s02")
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    # ---- 中间的表 ----
    tbl_x, tbl_y = w * TBL_X_RATIO, h * TBL_Y_RATIO
    tbl_w, tbl_h = w * TBL_W_RATIO, h * TBL_H_RATIO
    rounded_rect(ctx, tbl_x, tbl_y, tbl_w, tbl_h, 16, "#F2F5F9")
    stroke_rect(ctx, tbl_x, tbl_y, tbl_w, tbl_h, 16, "#DCE1E8", 3, 0.9)
    text(ctx, p["table_label"], tbl_x + w * 0.025, tbl_y + h * 0.075, 36,
         COLORS["primary"], bold=True)

    row_y = tbl_y + h * 0.105
    row_h = h * 0.075
    rounded_rect(ctx, tbl_x + w * 0.025, row_y, tbl_w - w * 0.05, row_h, 10,
                 "#FFFFFF")
    stroke_rect(ctx, tbl_x + w * 0.025, row_y, tbl_w - w * 0.05, row_h, 10,
                "#C8D2DE", 3, 0.9)
    text(ctx, p["row_label"], tbl_x + tbl_w / 2, row_y + row_h * 0.68, 34,
         COLORS["primary"], bold=True, anchor="center")

    # ---- 两条事务各写各的 ----
    chip_y = h * CHIP_Y_RATIO
    chip_w, chip_h = w * CHIP_W_RATIO, h * CHIP_H_RATIO
    for index, (txn_id, write, x_ratio) in enumerate(
        ((str(p["txn_a"]), str(p["write_a"]), CHIP_A_X_RATIO),
         (str(p["txn_b"]), str(p["write_b"]), CHIP_B_X_RATIO))
    ):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.10 - index * 0.16) * 3.0))
        )
        chip_x = w * x_ratio
        rounded_rect(ctx, chip_x, chip_y, chip_w, chip_h, 10,
                     TXN_COLORS[index], alpha=appear)
        text(ctx, txn_id, chip_x + chip_w / 2, chip_y + chip_h * 0.70, 36,
             "#FFFFFF", anchor="center", bold=True, alpha=appear)
        text(ctx, write, chip_x + chip_w / 2, chip_y + chip_h + h * 0.055, 28,
             COLORS["primary"], anchor="center", alpha=appear)

        # 两条箭头都指向同一行
        if index == 0:
            x1, x2 = chip_x + chip_w, tbl_x + w * 0.020
        else:
            x1, x2 = chip_x, tbl_x + tbl_w - w * 0.020
        arrow(ctx, x1, chip_y + chip_h * 0.5, x2, row_y + row_h * 0.5,
              TXN_COLORS[index], 5, 18, alpha=0.9 * appear)

    # ---- 结论 ----
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.48) * 3.0)))
    concl_x, concl_y = w * CONCL_X_RATIO, h * CONCL_Y_RATIO
    concl_w, concl_h = w * CONCL_W_RATIO, h * CONCL_H_RATIO
    rounded_rect(ctx, concl_x, concl_y, concl_w, concl_h, 12,
                 COLORS["problem"], alpha=0.95 * appear)
    text(ctx, p["conclusion"], concl_x + concl_w / 2, concl_y + concl_h * 0.66,
         34, "#FFFFFF", anchor="center", bold=True, alpha=appear)

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：两个事务一个在上、一个在下，两支箭头都扎进同一行。

    两支箭头一头从上、一头从下，指到中间那一个行框的两侧——
    「两边都写同一行」这件事，从相反的方向看更清楚。
    """
    left = w * scene_layout.MARGIN_X
    content_w = w * scene_layout.CONTENT_W

    scene_layout.title(ctx, p["title"], w, h)

    # ---- 两个事务，各写各的 ----
    bar_h = 150.0
    for index, (txn_id, write, y) in enumerate((
            (str(p["txn_a"]), str(p["write_a"]), 250.0),
            (str(p["txn_b"]), str(p["write_b"]), 810.0))):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.10 - index * 0.16) * 3.0))
        )
        rounded_rect(ctx, left, y, content_w, bar_h, 14, "#F2F5F9",
                     alpha=appear)
        rounded_rect(ctx, left + 24, y + 25, 150, 100, 12, TXN_COLORS[index],
                     alpha=appear)
        scene_layout.line(ctx, txn_id, left + 99, y + 92, 140, 38, "#FFFFFF",
                          anchor="center", bold=True, alpha=appear)
        scene_layout.line(ctx, write, left + 210, y + 90, content_w - 240, 34,
                          COLORS["primary"], alpha=appear)

    # ---- 中间那一行 ----
    scene_layout.line(ctx, p["table_label"], left, 520, 300, 36,
                      COLORS["primary"], bold=True)
    row_y, row_h = 560.0, 130.0
    rounded_rect(ctx, left, row_y, content_w, row_h, 10, "#FFFFFF")
    stroke_rect(ctx, left, row_y, content_w, row_h, 10, "#C8D2DE", 3, 0.9)
    scene_layout.line(ctx, p["row_label"], left + content_w / 2, row_y + 85,
                      content_w - 80, 36, COLORS["primary"], anchor="center",
                      bold=True)

    # 两条箭头都指向同一行：一支从上往下，一支从下往上
    arrow(ctx, left + content_w / 2, 400, left + content_w / 2, row_y,
          TXN_COLORS[0], 5, 18, alpha=0.9)
    arrow(ctx, left + content_w / 2, 810, left + content_w / 2, row_y + row_h,
          TXN_COLORS[1], 5, 18, alpha=0.9)

    # ---- 结论 ----
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.48) * 3.0)))
    concl_y, concl_h = 1030.0, 120.0
    rounded_rect(ctx, left, concl_y, content_w, concl_h, 12,
                 COLORS["problem"], alpha=0.95 * appear)
    scene_layout.line(ctx, p["conclusion"], left + content_w / 2,
                      concl_y + 78, content_w - 80, 34, COLORS["primary"],
                      anchor="center", bold=True, alpha=appear)

    scene_layout.caption(ctx, p["caption"], w, h)
