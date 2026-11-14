"""段 B：并发提交乱序模板。

上面一条 commit 时间轴，三个事务的提交点按真实先后落在轴上；
下面按事务编号列出，每个事务用一条引线连回轴上自己的提交点——
引线交叉，「谁先谁后不由编号决定」一眼可见。

版式在代码里，**这一期的事务编号、提交顺序与文案在契约里**（`Scene.params`）。

**竖版（1080×1920）**：横版是「轴在上、编号列表在下」的上下两层，
竖版沿用这个上下关系，但轴只占右边一段——左边那一列留给按编号排的
列表，引线才不会从别的行穿过去。
"""
from __future__ import annotations

from pyv import easing
from pyv import scene_layout
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
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return

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


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：commit 时间轴在上，按事务编号排的列表在下。

    **左边一列是列表，右边是轴**：轴只占右边一段，最靠左的提交点
    也在列表列右边，引线往下拉时不会从别的行的色块上穿过去。
    """
    ids = [str(x) for x in p["txn_ids"]]
    ranks = commit_ranks(p.as_dict())
    count = len(ids)

    left = w * scene_layout.MARGIN_X
    content_w = w * scene_layout.CONTENT_W

    scene_layout.title(ctx, p["title"], w, h, color=COLORS["problem"])

    # ---- commit 时间轴 ----
    lead = 150.0                       # 左边那一列留给列表
    axis_x0 = left + lead
    step = (content_w - lead) / count
    axis_y = 340.0
    scene_layout.line(ctx, p["axis_label"], left, 248, content_w, 30,
                      COLORS["primary"])
    rounded_rect(ctx, left, axis_y - 3, content_w, 6, 3, "#DCE1E8")

    # 每个事务在轴上的落点
    for index, (txn_id, rank) in enumerate(zip(ids, ranks)):
        color = MARKER_COLORS[index % len(MARKER_COLORS)]
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.08 * rank) * 3.0)))
        cx = axis_x0 + (rank + 0.5) * step
        rounded_rect(ctx, cx - 16, axis_y - 16, 32, 32, 9, color, alpha=appear)
        scene_layout.line(ctx, txn_id, cx, axis_y - 40, 160, 36,
                          COLORS["primary"], anchor="center", bold=True,
                          alpha=appear)

    # ---- 下面按事务编号列出，引线连回轴上自己的落点 ----
    row_h = 180.0
    for index, (txn_id, rank) in enumerate(zip(ids, ranks)):
        y = 470.0 + index * 250.0
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.14 * index) * 2.4)))
        color = MARKER_COLORS[index % len(MARKER_COLORS)]
        cx = axis_x0 + (rank + 0.5) * step
        # 引线：从轴上的落点垂直拉到这一行的上沿
        rounded_rect(ctx, cx - 2, axis_y + 18, 4, y - axis_y - 18, 2,
                     color, alpha=0.5 * appear)
        rounded_rect(ctx, left, y, content_w, row_h, 14, color, alpha=0.16)
        rounded_rect(ctx, left + 18, y + 42, 120, 96, 12, color, alpha=appear)
        scene_layout.line(ctx, txn_id, left + 78, y + 104, 110, 40, "#FFFFFF",
                          anchor="center", bold=True, alpha=appear)

    scene_layout.caption(ctx, p["caption"], w, h)
