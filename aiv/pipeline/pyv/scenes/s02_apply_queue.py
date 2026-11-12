"""段 B：订阅端排队模板。

左边那一头发出的是并行的一股流，到了另一头却只有一个执行线程，
右边四条事务排着队等着——并行的接收，不等于并行的应用。

版式在代码里，**这一期的标签与文案在契约里**（`Scene.params`）。
"""
from __future__ import annotations

from pyv import easing
from pyv.draw import arrow, rounded_rect, stroke_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "publisher_label", "publisher_sub", "apply_label", "apply_sub",
            "queue_label", "txn_ids", "active_txn", "caption")

# 队列里每条事务一个颜色
MARKER_COLORS = ("#F6AD55", "#4FD1C5", "#8FAADC", "#E9A0DC")


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s02")
    txn_ids = [str(x) for x in p["txn_ids"]]
    active = str(p["active_txn"])

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    # ---- 发布端：并行的几股流 ----
    src_x, src_y = w * 0.07, h * 0.30
    src_w, src_h = w * 0.17, h * 0.30
    rounded_rect(ctx, src_x, src_y, src_w, src_h, 16, COLORS["primary"])
    text(ctx, p["publisher_label"], src_x + src_w / 2, src_y + h * 0.10, 40,
         "#FFFFFF", anchor="center", bold=True)
    text(ctx, p["publisher_sub"], src_x + src_w / 2, src_y + h * 0.17, 32,
         COLORS["secondary"], anchor="center")

    # ---- 订阅端的执行线程 ----
    app_x, app_y = w * 0.45, h * 0.33
    app_w, app_h = w * 0.20, h * 0.24
    rounded_rect(ctx, app_x, app_y, app_w, app_h, 16, COLORS["accent"])
    text(ctx, p["apply_label"], app_x + app_w / 2, app_y + h * 0.09, 38,
         "#FFFFFF", anchor="center", bold=True)
    text(ctx, p["apply_sub"], app_x + app_w / 2, app_y + h * 0.16, 34,
         "#FFFFFF", anchor="center")

    # 发布端出来的几股流，收到一个线程里
    for index in range(3):
        y = src_y + src_h * (0.25 + index * 0.25)
        arrow(ctx, src_x + src_w + w * 0.012, y,
              app_x - w * 0.012, app_y + app_h * 0.5,
              COLORS["secondary"], 5, 16, alpha=0.9)

    # ---- 接收队列 ----
    queue_x = w * 0.72
    queue_y = h * 0.28
    queue_w = w * 0.21
    text(ctx, p["queue_label"], queue_x, queue_y - h * 0.035, 34, COLORS["secondary"])
    for index, txn_id in enumerate(txn_ids):
        chip_h = h * 0.058
        chip_y = queue_y + index * (chip_h + h * 0.022)
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.12 - index * 0.10) * 3.2))
        )
        color = MARKER_COLORS[index % len(MARKER_COLORS)]
        is_active = txn_id == active
        rounded_rect(ctx, queue_x, chip_y, queue_w, chip_h, 10,
                     color if is_active else "#F2F5F9", alpha=appear)
        text(ctx, txn_id, queue_x + queue_w / 2, chip_y + chip_h * 0.70, 32,
             "#FFFFFF" if is_active else COLORS["primary"],
             anchor="center", bold=True, alpha=appear)

    # 执行线程与队列之间
    arrow(ctx, app_x + app_w + w * 0.012, app_y + app_h * 0.5,
          queue_x - w * 0.012, queue_y + h * 0.145, COLORS["accent"], 6, 20)

    # 队列底下的框线
    stroke_rect(ctx, queue_x - w * 0.012, queue_y - h * 0.012,
                queue_w + w * 0.024, h * 0.37, 12, "#DCE1E8", 3, 0.9)

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])
