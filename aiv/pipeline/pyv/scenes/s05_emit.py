"""段 E：整组搬走的模板。

左边是攒好的三组变更，右边是接收方。中间那一组等到自己的提交记录出现，
才整组一起飞过去——三块芯片保持原来的相对位置，像一叠纸一样搬走。

版式在代码里，**这一期的分组、事务编号与文案在契约里**（`Scene.params`）。

**竖版（1080×1920）**：横版是「左边一列缓冲 + 右边一个接收方」，竖版只有
1080 宽，左右分栏会把芯片压扁——所以改成上下堆叠：缓冲在上，接收方在
下，中间那一组整组往下飞（见 `pyv/scene_layout.py` 的三条规矩）。
"""
from __future__ import annotations

from pyv import easing
from pyv import scene_layout
from pyv.draw import arrow, rounded_rect, stroke_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "buffer_label", "emit_label", "target_label", "slots",
            "emit_txn", "commit_op", "caption")

# 每个事务一个颜色
MARKER_COLORS = ("#F6AD55", "#4FD1C5", "#8FAADC")

# 整组开始发出的时刻与时长
EMIT_START = 0.42
EMIT_DURATION = 0.36

CHIP_W_RATIO = 0.065
CHIP_GAP_RATIO = 0.008


def emit_slot(params=None) -> list[str]:
    """要发出去的那一组：它有哪些操作，按什么顺序。"""
    p = Params(params, "s05")
    target = str(p["emit_txn"])
    for row in p["slots"]:
        if str(row[0]) == target:
            return [str(op) for op in row[1]]
    return []


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s05")
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return
    # 每行是 [事务, 操作列表]
    slots = [(str(row[0]), [str(op) for op in row[1]]) for row in p["slots"]]
    target_txn = str(p["emit_txn"])
    commit_op = str(p["commit_op"])

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    # ---- 左边的缓冲 ----
    panel_x = w * 0.06
    panel_w = w * 0.46
    row_top = h * 0.30
    row_h = h * 0.135
    row_gap = h * 0.055
    chip_w = w * CHIP_W_RATIO
    chip_gap = w * CHIP_GAP_RATIO

    text(ctx, p["buffer_label"], panel_x, h * 0.245, 36, COLORS["accent"], bold=True)

    # ---- 右边的订阅端 ----
    target_x = w * 0.64
    target_y = h * 0.28
    target_w = w * 0.30
    target_h = h * 0.30
    rounded_rect(ctx, target_x, target_y, target_w, target_h, 16, COLORS["primary"])
    text(ctx, p["target_label"], target_x + target_w / 2, target_y + h * 0.085, 40,
         "#FFFFFF", anchor="center", bold=True)

    emit_ops = emit_slot(params)
    progress = easing.ease_in_out(
        max(0.0, min(1.0, (t - EMIT_START) / EMIT_DURATION))
    )

    # 发出去的那一组：整组平移，相对位置不变
    emit_index = next(
        (i for i, (txn_id, _) in enumerate(slots) if txn_id == target_txn), 0
    )
    emit_row_y = row_top + emit_index * (row_h + row_gap)
    emit_chip_y = emit_row_y + row_h * 0.26
    chip_h = row_h * 0.48
    group_w = len(emit_ops) * chip_w + max(0, len(emit_ops) - 1) * chip_gap
    land_x = target_x + (target_w - group_w) / 2
    land_y = target_y + (target_h - chip_h) / 2
    start_x = panel_x + w * 0.085
    dx = land_x - start_x
    dy = land_y - emit_chip_y

    for index, (txn_id, ops) in enumerate(slots):
        color = MARKER_COLORS[index % len(MARKER_COLORS)]
        y = row_top + index * (row_h + row_gap)
        rounded_rect(ctx, panel_x, y, panel_w, row_h, 14, "#F2F5F9")
        stroke_rect(ctx, panel_x, y, panel_w, row_h, 14, "#DCE1E8", 3, 0.9)
        rounded_rect(ctx, panel_x + w * 0.012, y + row_h * 0.26, w * 0.05,
                     row_h * 0.48, 9, color)
        text(ctx, txn_id, panel_x + w * 0.037, y + row_h * 0.60, 32, "#FFFFFF",
             anchor="center", bold=True)

        is_emit = txn_id == target_txn
        for op_index, op in enumerate(ops):
            x = start_x + op_index * (chip_w + chip_gap)
            chip_y = y + row_h * 0.26
            offset = progress if is_emit else 0.0
            cx = x + dx * offset
            cy = chip_y + dy * offset
            is_commit = op == commit_op
            rounded_rect(ctx, cx, cy, chip_w, chip_h, 9,
                         "#FFFFFF" if is_commit else color,
                         alpha=1.0 - 0.20 * offset)
            text(ctx, op, cx + chip_w / 2, cy + chip_h * 0.70, 28,
                 COLORS["primary"] if is_commit else "#FFFFFF",
                 anchor="center", bold=True, alpha=1.0 - 0.20 * offset)

    # ---- 中间的去向 ----
    lane_y = target_y + target_h / 2
    arrow(ctx, panel_x + panel_w + w * 0.015, lane_y,
          target_x - w * 0.015, lane_y, COLORS["accent"], 7, 24)
    text(ctx, p["emit_label"], (panel_x + panel_w + target_x) / 2,
         lane_y - h * 0.045, 40, COLORS["accent"], anchor="center", bold=True)

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：缓冲在上（三行往下摞），接收方在下，中间那一组整组往下飞。

    横版是「左边的缓冲 + 右边的接收方」，竖版只有 1080 宽，左右分栏会
    把芯片压扁、芯片里的字也放不下——所以改成上下堆叠：

    - **字号不缩、框变宽**：缓冲行与接收方都撑满 0.88w，芯片比横版宽。
    - **字要放得下**：每一行字都过 `scene_layout.line`。
    """
    slots = [(str(row[0]), [str(op) for op in row[1]]) for row in p["slots"]]
    target_txn = str(p["emit_txn"])
    commit_op = str(p["commit_op"])

    left = w * scene_layout.MARGIN_X
    max_width = w * scene_layout.CONTENT_W
    center = left + max_width / 2

    scene_layout.title(ctx, p["title"], w, h, size=60)

    # ---- 上面的缓冲：三行往下摞 ----
    row_top = h * 0.146
    row_h = h * 0.085
    row_gap = h * 0.014
    badge_w = w * 0.085
    chip_w = w * 0.185
    chip_gap = w * 0.0185
    chip_h = h * 0.0435
    # 芯片往右让开一点：整组要一路往下飞，飞的这条道不能压住
    # 接收方框左上角那个名字。
    chip_x0 = left + w * 0.155

    scene_layout.line(ctx, p["buffer_label"], left, h * 0.132, max_width, 40,
                      COLORS["accent"], bold=True)

    emit_ops = next((ops for txn_id, ops in slots if txn_id == target_txn), [])
    progress = easing.ease_in_out(
        max(0.0, min(1.0, (t - EMIT_START) / EMIT_DURATION))
    )

    # 发出去的那一组：整组平移，相对位置不变
    emit_index = next(
        (i for i, (txn_id, _) in enumerate(slots) if txn_id == target_txn), 0
    )
    group_w = len(emit_ops) * chip_w + max(0, len(emit_ops) - 1) * chip_gap

    # ---- 下面的订阅端 ----
    # 接收方的名字放在框的左上角：芯片是飞过来的，从框的上边进来，
    # 名字放在上面会被落下来的芯片盖住（横版也是这样：名字在上，芯片在中间）。
    target_y = h * 0.512
    target_h = h * 0.115
    rounded_rect(ctx, left, target_y, max_width, target_h, 16, COLORS["primary"])
    scene_layout.line(ctx, p["target_label"], left + w * 0.026,
                      target_y + h * 0.027, max_width * 0.5, 40, "#FFFFFF",
                      bold=True)

    land_x = left + (max_width - group_w) / 2
    land_y = target_y + h * 0.043
    start_x = chip_x0
    emit_row_y = row_top + emit_index * (row_h + row_gap)
    start_y = emit_row_y + (row_h - chip_h) / 2
    dx = land_x - start_x
    dy = land_y - start_y

    for index, (txn_id, ops) in enumerate(slots):
        color = MARKER_COLORS[index % len(MARKER_COLORS)]
        y = row_top + index * (row_h + row_gap)
        rounded_rect(ctx, left, y, max_width, row_h, 14, "#F2F5F9")
        stroke_rect(ctx, left, y, max_width, row_h, 14, "#DCE1E8", 3, 0.9)
        badge_y = y + (row_h - chip_h) / 2
        rounded_rect(ctx, left + w * 0.020, badge_y, badge_w, chip_h, 9, color)
        scene_layout.line(ctx, txn_id, left + w * 0.020 + badge_w / 2,
                          badge_y + chip_h * 0.70, badge_w, 32, "#FFFFFF",
                          anchor="center", bold=True)

        if txn_id == target_txn:
            # 整组搬走的那一组留到最后一轮再画：它要一路往下飞过
            # 下面几行，在行里画就会被后画的行面板盖住半个芯片。
            continue
        for op_index, op in enumerate(ops):
            x = chip_x0 + op_index * (chip_w + chip_gap)
            is_commit = op == commit_op
            rounded_rect(ctx, x, badge_y, chip_w, chip_h, 9,
                         "#FFFFFF" if is_commit else color)
            scene_layout.line(ctx, op, x + chip_w / 2, badge_y + chip_h * 0.70,
                              chip_w - 16, 28,
                              COLORS["primary"] if is_commit else "#FFFFFF",
                              anchor="center", bold=True)

    # ---- 发出去的那一组：整组平移，相对位置不变 ----
    emit_color = MARKER_COLORS[emit_index % len(MARKER_COLORS)]
    for op_index, op in enumerate(emit_ops):
        x = chip_x0 + op_index * (chip_w + chip_gap)
        cx = x + dx * progress
        cy = start_y + dy * progress
        is_commit = op == commit_op
        rounded_rect(ctx, cx, cy, chip_w, chip_h, 9,
                     "#FFFFFF" if is_commit else emit_color,
                     alpha=1.0 - 0.20 * progress)
        scene_layout.line(ctx, op, cx + chip_w / 2, cy + chip_h * 0.70,
                          chip_w - 16, 28,
                          COLORS["primary"] if is_commit else "#FFFFFF",
                          anchor="center", bold=True, alpha=1.0 - 0.20 * progress)

    # ---- 中间的去向 ----
    # 画在飞过去的那一组之上：芯片飞过时盖住字，看着像字被吃掉了。
    scene_layout.line(ctx, p["emit_label"], center, h * 0.468, max_width, 36,
                      COLORS["accent"], anchor="center", bold=True)
    arrow(ctx, center, h * 0.478, center, h * 0.505, COLORS["accent"], 7, 24)

    scene_layout.caption(ctx, p["caption"], w, h)
