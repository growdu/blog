"""段 E：调度与提交模板。

上面一排是执行线程，各自按图的顺序接活；下面一条是通道，
事务按依赖顺序一个一个落进去——并行的是执行，提交仍然有先后。

版式在代码里，**这一期的线程数、分发与提交顺序在契约里**（`Scene.params`）。

**竖版（1080×1920）**：横版是「上面一排线程 + 下面一条通道」，竖版只有
1080 宽，线程并排会挤到放不下芯片——所以改成上下堆叠：线程一上一下，
提交通道放在最下面（见 `pyv/scene_layout.py` 的三条规矩）。
"""
from __future__ import annotations

from pyv import easing
from pyv import scene_layout
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
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return
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


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：执行线程一上一下，提交通道在最下面。

    横版是「上面一排线程 + 下面一条通道」，竖版只有 1080 宽，线程并排
    会挤到放不下芯片——所以改成上下堆叠：

    - **字号不缩、框变宽**：每个线程一块撑满 0.88w 的带子，芯片排在
      带子右边，字号比横版大一号。
    - **字要放得下**：每一行字都过 `scene_layout.line`。
    """
    dispatch = [(str(row[0]), int(row[1])) for row in p["dispatch"]]
    commit_order = [str(x) for x in p["commit_order"]]
    worker_count = int(p["worker_count"])

    left = w * scene_layout.MARGIN_X
    max_width = w * scene_layout.CONTENT_W
    center = left + max_width / 2

    scene_layout.title(ctx, p["title"], w, h, size=60)

    # ---- 执行线程：一个一块带子，从上往下排 ----
    box_h = h * 0.125
    box_gap = h * 0.013
    box_top = h * 0.130
    chip_w = w * 0.204
    chip_h = h * 0.043
    chip_gap = w * 0.024
    chip_x0 = left + w * 0.305

    for index in range(worker_count):
        box_y = box_top + index * (box_h + box_gap)
        rounded_rect(ctx, left, box_y, max_width, box_h, 16, "#F2F5F9")
        scene_layout.line(ctx, f"{p['worker_prefix']} {index + 1}",
                          left + w * 0.028, box_y + h * 0.070, max_width * 0.28,
                          42, COLORS["primary"], bold=True)

        # 同一个线程里，事务按来的先后往右排
        worker_rows = [txn_id for txn_id, wid in dispatch if wid == index]
        for order, (txn_id, worker_index) in enumerate(dispatch):
            if worker_index != index:
                continue
            appear = easing.ease_out_cubic(
                max(0.0, min(1.0, (t - DISPATCH_DELAY - DISPATCH_STEP * order) * 3.0))
            )
            cx = chip_x0 + worker_rows.index(txn_id) * (chip_w + chip_gap)
            cy = box_y + (box_h - chip_h) / 2
            color = MARKER_COLORS[dispatch.index((txn_id, worker_index))
                                  % len(MARKER_COLORS)]
            rounded_rect(ctx, cx, cy, chip_w, chip_h, 10, color, alpha=appear)
            scene_layout.line(ctx, txn_id, cx + chip_w / 2, cy + chip_h * 0.70,
                              chip_w - 16, 34, "#FFFFFF", anchor="center",
                              bold=True, alpha=appear)

    # ---- 提交通道：在最下面 ----
    lane_y = h * 0.545
    scene_layout.line(ctx, p["commit_label"], left, h * 0.475, max_width, 40,
                      COLORS["accent"], bold=True)

    step = max_width / len(commit_order)
    lane_chip_w = w * 0.176
    # 轨道从第一块芯片的左沿拉到最后一块的右沿，两头一样长
    lane_x0 = left + step / 2 - lane_chip_w / 2
    lane_x1 = left + (len(commit_order) - 0.5) * step + lane_chip_w / 2
    rounded_rect(ctx, lane_x0, lane_y, lane_x1 - lane_x0, 6, 3, "#DCE1E8")
    for order, txn_id in enumerate(commit_order):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - COMMIT_DELAY - COMMIT_STEP * order) * 3.5))
        )
        cx = left + (order + 0.5) * step
        color = MARKER_COLORS[dispatch.index(
            next(row for row in dispatch if row[0] == txn_id))
            % len(MARKER_COLORS)]
        rounded_rect(ctx, cx - lane_chip_w / 2, lane_y - chip_h / 2,
                     lane_chip_w, chip_h, 10, color, alpha=appear)
        scene_layout.line(ctx, txn_id, cx, lane_y + chip_h * 0.22,
                          lane_chip_w - 16, 34, "#FFFFFF", anchor="center",
                          bold=True, alpha=appear)
        if order < len(commit_order) - 1:
            arrow(ctx, cx + lane_chip_w / 2, lane_y,
                  cx + step - lane_chip_w / 2, lane_y, COLORS["accent"], 5, 18,
                  alpha=appear)

    scene_layout.caption(ctx, p["caption"], w, h)
