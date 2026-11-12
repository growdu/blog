"""段 E：调度与提交模板。

上面一排是执行线程，各自按图的顺序接活；下面一条是通道，
事务按依赖顺序一个一个落进去——并行的是执行，提交仍然有先后。

版式在代码里，**这一期的线程数、分发与提交顺序在契约里**（`Scene.params`）。
"""
from __future__ import annotations

from pyv import easing
from pyv.draw import arrow, rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "worker_count", "worker_prefix", "dispatch", "commit_label",
            "commit_order", "caption")

# 事务配色
MARKER_COLORS = ("#F6AD55", "#4FD1C5", "#8FAADC", "#E9A0DC")

# 分发与提交的时间节奏
DISPATCH_STEP = 0.11
DISPATCH_DELAY = 0.10
COMMIT_STEP = 0.08
COMMIT_DELAY = 0.42


def worker_of(dispatch: list[list], txn_id: str) -> int:
    """某个事务分给第几个执行线程（0 起）。找不到返回 -1。"""
    for row in dispatch:
        if str(row[0]) == txn_id:
            return int(row[1])
    return -1


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s05")
    dispatch = [(str(row[0]), int(row[1])) for row in p["dispatch"]]
    commit_order = [str(x) for x in p["commit_order"]]
    worker_count = int(p["worker_count"])

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    # ---- 上面的执行线程 ----
    box_gap = w * 0.06
    box_w = (w * 0.82 - box_gap * (worker_count - 1)) / worker_count
    box_x0 = w * 0.09
    box_y = h * 0.26
    box_h = h * 0.27
    for index in range(worker_count):
        bx = box_x0 + index * (box_w + box_gap)
        rounded_rect(ctx, bx, box_y, box_w, box_h, 16, "#F2F5F9")
        text(ctx, f"{p['worker_prefix']} {index + 1}", bx + box_w / 2,
             box_y + h * 0.065, 38, COLORS["primary"], anchor="center", bold=True)

    chip_w = w * 0.15
    chip_h = h * 0.062
    for order, (txn_id, worker_index) in enumerate(dispatch):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - DISPATCH_DELAY - DISPATCH_STEP * order) * 3.0))
        )
        bx = box_x0 + worker_index * (box_w + box_gap)
        # 同一个线程里，事务按来的先后往下排
        stack = [row for row in dispatch
                 if row[1] == worker_index and dispatch.index(row) <= order]
        row = stack.index((txn_id, worker_index))
        cx = bx + (box_w - chip_w) / 2
        cy = box_y + h * 0.105 + row * (chip_h + h * 0.018)
        color = MARKER_COLORS[dispatch.index((txn_id, worker_index))
                              % len(MARKER_COLORS)]
        rounded_rect(ctx, cx, cy, chip_w, chip_h, 10, color, alpha=appear)
        text(ctx, txn_id, cx + chip_w / 2, cy + chip_h * 0.70, 32, "#FFFFFF",
             anchor="center", bold=True, alpha=appear)

    # ---- 下面的提交通道 ----
    lane_y = h * 0.68
    lane_x0 = w * 0.14
    lane_x1 = w * 0.90
    text(ctx, p["commit_label"], w * 0.07, lane_y - h * 0.03, 36, COLORS["accent"],
         bold=True)
    rounded_rect(ctx, lane_x0, lane_y, lane_x1 - lane_x0, 6, 3, "#DCE1E8")

    step = (lane_x1 - lane_x0) / len(commit_order)
    for order, txn_id in enumerate(commit_order):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - COMMIT_DELAY - COMMIT_STEP * order) * 3.5))
        )
        cx = lane_x0 + (order + 0.5) * step
        color = MARKER_COLORS[dispatch.index(
            next(row for row in dispatch if row[0] == txn_id))
            % len(MARKER_COLORS)]
        rounded_rect(ctx, cx - chip_w / 2, lane_y - chip_h / 2, chip_w, chip_h, 10,
                     color, alpha=appear)
        text(ctx, txn_id, cx, lane_y + chip_h * 0.22, 32, "#FFFFFF",
             anchor="center", bold=True, alpha=appear)
        if order < len(commit_order) - 1:
            arrow(ctx, cx + chip_w / 2, lane_y, cx + step - chip_w / 2, lane_y,
                  COLORS["accent"], 5, 18, alpha=appear)

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])
