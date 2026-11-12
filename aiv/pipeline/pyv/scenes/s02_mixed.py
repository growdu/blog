"""段 B：并发提交乱序模板。

上面一条 commit 时间轴，三个事务的提交点按真实先后落在轴上；
下面按事务编号列出，每个事务用一条引线连回轴上自己的提交点——
引线交叉，「谁先谁后不由编号决定」一眼可见。

版式在代码里，**这一期的事务编号、提交顺序与文案在契约里**（`Scene.params`）。
"""
from __future__ import annotations

from pyv import easing
from pyv.draw import rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "axis_label", "txn_ids", "commit_order", "caption")

# 每个事务一个颜色：轴上的提交点与下面列表里的方块用的是同一个颜色。
MARKER_COLORS = ("#F6AD55", "#4FD1C5", "#8FAADC")


def commit_ranks(params=None) -> list[int]:
    """每个事务在时间轴上的名次。

    返回值与 `txn_ids` 一一对应：第 i 个事务是第几个 commit 的。
    名次由契约里的提交顺序算出来，代码不写死。
    """
    p = Params(params, "s02")
    ids = [str(x) for x in p["txn_ids"]]
    order = [str(x) for x in p["commit_order"]]
    return [order.index(txn_id) for txn_id in ids]


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s02")
    ids = [str(x) for x in p["txn_ids"]]
    ranks = commit_ranks(params)
    count = len(ids)

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["problem"], bold=True)

    # ---- 时间轴 ----
    axis_y = h * 0.315
    x0, x1 = w * 0.10, w * 0.90
    step = (x1 - x0) / count
    rounded_rect(ctx, x0, axis_y - 3, x1 - x0, 6, 3, "#DCE1E8")
    text(ctx, p["axis_label"], x0, h * 0.245, 32, COLORS["primary"])

    # 每个事务在轴上的落点
    for index, (txn_id, rank) in enumerate(zip(ids, ranks)):
        color = MARKER_COLORS[index % len(MARKER_COLORS)]
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.08 * rank) * 3.0)))
        cx = x0 + (rank + 0.5) * step
        rounded_rect(ctx, cx - 16, axis_y - 16, 32, 32, 9, color, alpha=appear)
        text(ctx, txn_id, cx, axis_y - 40, 38, COLORS["primary"],
             anchor="center", bold=True, alpha=appear)

    # ---- 下面按事务编号列出，引线连回轴上自己的落点 ----
    for index, (txn_id, rank) in enumerate(zip(ids, ranks)):
        y = h * (0.47 + index * 0.105)
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.14 * index) * 2.4)))
        color = MARKER_COLORS[index % len(MARKER_COLORS)]
        cx = x0 + (rank + 0.5) * step
        # 引线：从轴上的落点垂直拉到这一行
        rounded_rect(ctx, cx - 2, axis_y + 18, 4, y - axis_y - 18, 2,
                     color, alpha=0.45 * appear)
        rounded_rect(ctx, w * 0.07, y, w * 0.105, h * 0.062, 10,
                     color, alpha=appear)
        text(ctx, txn_id, w * 0.1225, y + h * 0.043, 36, "#FFFFFF",
             anchor="center", bold=True, alpha=appear)

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])
