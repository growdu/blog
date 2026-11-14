"""段 B：WAL 记录交错模板。

一条 WAL 位置轴，六条记录按位置排开，每条一个颜色——颜色代表它属于哪个事务。
轴下方按事务画三道括号：同一事务的记录被别的隔开，交错这件事一眼可见。

版式在代码里，**这一期的记录、事务编号与文案在契约里**（`Scene.params`）。

**竖版（1080×1920）**：横版是「横着的 WAL 位置轴 + 上下的记录块与括号」；
竖版把位置轴立起来——LSN 一路往下排在轴左，记录块在轴右一路往下，
轴右边那三道竖括号框住同一事务的记录，交错照样一眼可见。
"""
from __future__ import annotations

from pyv import easing
from pyv import scene_layout
from pyv.draw import rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "axis_label", "txn_ids", "records", "legend_label", "caption")

# 每个事务一个颜色：轴上的记录、括号与图例用的是同一个颜色。
MARKER_COLORS = ("#F6AD55", "#4FD1C5", "#8FAADC")

# 第 i 条记录在场景进度上的出现时刻
RECORD_STEP = 0.10
RECORD_DELAY = 0.08

# 括号的最短跨度（像素）：只有一条记录的事务也要看得见
MIN_SPAN = 90


def txn_colors(txn_ids: list[str]) -> dict[str, str]:
    """事务编号 → 颜色。"""
    return {
        txn_id: MARKER_COLORS[index % len(MARKER_COLORS)]
        for index, txn_id in enumerate(txn_ids)
    }


def group_indices(records: list[tuple[str, str, str]]) -> dict[str, list[int]]:
    """每个事务占用了第几条记录（按出现顺序）。"""
    groups: dict[str, list[int]] = {}
    for index, (_, txn_id, _) in enumerate(records):
        groups.setdefault(txn_id, []).append(index)
    return groups


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s02")
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return

    txn_ids = [str(x) for x in p["txn_ids"]]
    # 每条记录是 [位置, 事务, 操作]
    records = [(str(row[0]), str(row[1]), str(row[2])) for row in p["records"]]
    colors = txn_colors(txn_ids)

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    # ---- WAL 位置轴 ----
    axis_y = h * 0.46
    x0, x1 = w * 0.10, w * 0.90
    rounded_rect(ctx, x0, axis_y - 3, x1 - x0, 6, 3, "#DCE1E8")
    text(ctx, p["axis_label"], x0, h * 0.285, 32, COLORS["primary"])

    step = (x1 - x0) / len(records)
    centers: list[float] = []
    for index, (position, txn_id, op) in enumerate(records):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - RECORD_DELAY - RECORD_STEP * index) * 5.0))
        )
        color = colors.get(txn_id, COLORS["secondary"])
        cx = x0 + (index + 0.5) * step
        centers.append(cx)

        # 记录块：写的是什么操作
        chip_w, chip_h = w * 0.093, h * 0.065
        rounded_rect(ctx, cx - chip_w / 2, axis_y - h * 0.135, chip_w, chip_h,
                     12, color, alpha=appear)
        text(ctx, op, cx, axis_y - h * 0.135 + chip_h * 0.72, 32, "#FFFFFF",
             anchor="center", bold=True, alpha=appear)

        # 从记录块拉到轴上的引线
        rounded_rect(ctx, cx - 2, axis_y - h * 0.070, 4, h * 0.064, 2,
                     color, alpha=0.55 * appear)

        # 轴下的位置编号
        text(ctx, position, cx, axis_y + h * 0.062, 34, COLORS["primary"],
             anchor="center", alpha=appear)

    # ---- 轴下方的括号：同一事务的记录框在一起 ----
    bracket_y = h * 0.60
    bracket_h = h * 0.038
    for level, (txn_id, indices) in enumerate(group_indices(records).items()):
        color = colors.get(txn_id, COLORS["secondary"])
        xs = [centers[i] for i in indices]
        lo, hi = min(xs), max(xs)
        if hi - lo < MIN_SPAN:
            lo -= MIN_SPAN / 2
            hi += MIN_SPAN / 2
        y = bracket_y + level * h * 0.075
        # 两端的竖钩
        rounded_rect(ctx, lo - 3, y, 6, bracket_h, 3, color, alpha=0.95)
        rounded_rect(ctx, hi - 3, y, 6, bracket_h, 3, color, alpha=0.95)
        # 横线
        rounded_rect(ctx, lo, y + bracket_h - 5, hi - lo, 5, 2, color, alpha=0.95)
        # 事务名
        text(ctx, txn_id, lo - 14, y + bracket_h, 34, color,
             anchor="right", bold=True)

    # ---- 图例：颜色代表哪个事务 ----
    legend_x = w * 0.70
    legend_y = h * 0.845
    box_w, box_h = w * 0.045, h * 0.042
    gap = w * 0.085
    for index, txn_id in enumerate(txn_ids):
        bx = legend_x + index * gap
        rounded_rect(ctx, bx, legend_y, box_w, box_h, 8,
                     colors.get(txn_id, COLORS["secondary"]))
        text(ctx, txn_id, bx + box_w + w * 0.008, legend_y + box_h * 0.72, 32,
             COLORS["primary"], bold=True)
    text(ctx, p["legend_label"], legend_x, legend_y - h * 0.035, 30,
         COLORS["secondary"])

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：WAL 位置轴立起来，LSN 在轴左，记录块在轴右。

    轴右边三道竖括号框住同一事务的那些记录——竖着框，跨过的记录
    一样多，交错这件事照样一眼可见。
    """
    txn_ids = [str(x) for x in p["txn_ids"]]
    # 每条记录是 [位置, 事务, 操作]
    records = [(str(row[0]), str(row[1]), str(row[2])) for row in p["records"]]
    colors = txn_colors(txn_ids)

    left = w * scene_layout.MARGIN_X
    content_w = w * scene_layout.CONTENT_W

    scene_layout.title(ctx, p["title"], w, h)

    # ---- WAL 位置轴（竖着） ----
    axis_x = left + 130
    axis_top, axis_bottom = 250.0, 1060.0
    scene_layout.line(ctx, p["axis_label"], left, 240, content_w, 30,
                      COLORS["primary"])
    rounded_rect(ctx, axis_x - 3, axis_top, 6, axis_bottom - axis_top, 3,
                 "#DCE1E8")

    chip_x = axis_x + 44
    chip_w = 540.0
    chip_h = 92.0
    centers: list[float] = []
    for index, (position, txn_id, op) in enumerate(records):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - RECORD_DELAY - RECORD_STEP * index) * 5.0))
        )
        color = colors.get(txn_id, COLORS["secondary"])
        y = 270.0 + index * 135.0
        centers.append(y + chip_h / 2)

        # 记录块：写的是什么操作
        rounded_rect(ctx, chip_x, y, chip_w, chip_h, 12, color, alpha=appear)
        scene_layout.line(ctx, op, chip_x + chip_w / 2, y + chip_h * 0.70,
                          chip_w - 60, 32, "#FFFFFF", anchor="center", bold=True,
                          alpha=appear)

        # 从记录块拉到轴上的引线
        rounded_rect(ctx, axis_x, y + chip_h / 2 - 2, chip_x - axis_x, 4, 2,
                     color, alpha=0.55 * appear)

        # 轴左的位置编号
        scene_layout.line(ctx, position, axis_x - 22, y + chip_h * 0.70, 200,
                          32, COLORS["primary"], anchor="right", alpha=appear)

    # ---- 轴右的竖括号：同一事务的记录框在一起 ----
    # **每层往右错开**：三道括号画在同一个 x 上会叠在一起，短的那道
    # 被长的盖住，就看不出哪个框住了哪些记录了（横版是按层往下错开的）。
    span_x = chip_x + chip_w + 34
    for level, (txn_id, indices) in enumerate(group_indices(records).items()):
        color = colors.get(txn_id, COLORS["secondary"])
        ys = [centers[i] for i in indices]
        lo, hi = min(ys), max(ys)
        if hi - lo < MIN_SPAN:
            lo -= MIN_SPAN / 2
            hi += MIN_SPAN / 2
        x = span_x + level * 28
        # 竖线
        rounded_rect(ctx, x - 3, lo, 6, hi - lo, 3, color, alpha=0.95)
        # 两端的横钩：从记录块的右沿伸到这道括号上
        rounded_rect(ctx, chip_x + chip_w, lo - 3, x - chip_x - chip_w + 3, 6, 3,
                     color, alpha=0.95)
        rounded_rect(ctx, chip_x + chip_w, hi - 3, x - chip_x - chip_w + 3, 6, 3,
                     color, alpha=0.95)
        # 事务名
        scene_layout.line(ctx, txn_id, x + 12, lo - 12, 120, 34, color,
                          bold=True)

    # ---- 图例：颜色代表哪个事务 ----
    legend_y = 1112.0
    scene_layout.line(ctx, p["legend_label"], left, legend_y + 38, 260, 30,
                      COLORS["primary"])
    for index, txn_id in enumerate(txn_ids):
        bx = left + 260 + index * 150
        rounded_rect(ctx, bx, legend_y, 42, 42, 8,
                     colors.get(txn_id, COLORS["secondary"]))
        scene_layout.line(ctx, txn_id, bx + 54, legend_y + 38, 100, 30,
                          COLORS["primary"], bold=True)

    scene_layout.caption(ctx, p["caption"], w, h)
