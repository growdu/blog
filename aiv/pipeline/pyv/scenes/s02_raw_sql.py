"""段 B：原样发一段文本的模板。

左边写进日志，右边收到同一段文本——中间什么结构都没有。
这条最省事的路子，先把它画出来，后面的问题才好说。

版式在代码里，**这一期的文本、标签与文案在契约里**（`Scene.params`）。
"""
from __future__ import annotations

from pyv import easing
from pyv.draw import arrow, rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "ddl_text", "source_label", "wal_label", "target_label",
            "caption")


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s02")
    ddl = str(p["ddl_text"])

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    box_y = h * 0.30
    box_h = h * 0.30
    box_w = w * 0.31

    # ---- 两端 ----
    for index, (label, x) in enumerate((
            (str(p["source_label"]), w * 0.07),
            (str(p["target_label"]), w * 0.62))):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.08 - index * 0.18) * 3.0))
        )
        rounded_rect(ctx, x, box_y, box_w, box_h, 16, COLORS["primary"],
                     alpha=appear)
        text(ctx, label, x + box_w / 2, box_y + h * 0.075, 38, "#FFFFFF",
             anchor="center", bold=True, alpha=appear)
        # 里面就是那一段文本
        chip_y = box_y + h * 0.12
        chip_h = h * 0.11
        rounded_rect(ctx, x + w * 0.025, chip_y, box_w - w * 0.05, chip_h, 10,
                     "#FFFFFF", alpha=0.92 * appear)
        text(ctx, ddl, x + box_w / 2, chip_y + chip_h * 0.68, 28,
             COLORS["primary"], anchor="center", alpha=appear)

    # ---- 中间：写进日志，原样发过去 ----
    lane_y = box_y + box_h * 0.5
    arrow(ctx, w * 0.39, lane_y, w * 0.61, lane_y, COLORS["accent"], 7, 24)
    text(ctx, p["wal_label"], w * 0.50, lane_y - h * 0.045, 38, COLORS["accent"],
         anchor="center", bold=True)

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])
