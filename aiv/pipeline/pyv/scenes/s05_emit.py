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

#: 起飞时「整组发出」标签与箭头的让位速度（相对飞行进度）。
#:
#: **标签与箭头都在芯片的飞行走廊上**：竖版是芯片从它们上面压过去，
#: 横版是芯片从它们前面横穿过去。它们跟芯片挤在同一条通道里，
#: 硬留着就会被芯片切碎——字被劈成两半、箭头从字里穿出来。
#:
#: 所以起飞就让位：让飞出去的那一组自己说话。
LABEL_FADE_SPAN = 0.25

#: 竖版：飞行组压过的那一行退到多淡。
#:
#: 竖版只有 1080 宽，发射组（三块芯片，639 px）要从缓冲第一行一路降到
#: 接收方框，中间**必然**压过下面两行的芯片。两组芯片一样大、一样对齐，
#: 半透明地叠在一起就糊成一团（橙的压着绿的，看不出谁是谁）。
#:
#: 被压过的那一行让开：面板、徽标、芯片一起退成背景。**整行一起退**
#: 才有信号——只让芯片退的话，芯片正好被飞过来的那组盖住，退了也看不见。
ROW_DIM_ALPHA = 0.45

#: 飞行中的芯片放大多大。
#:
#: 竖版里飞行组要从缓冲第一行降到接收方框，中间必然压过下面两行的芯片。
#: 一样大的两组芯片叠在一起，分不清谁压着谁——放大的那组是**浮在上面的**
#: 那一组，被盖住的那块还会从边上露出一点，看得出下面本来是有东西的。
FLY_SCALE = 1.08


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
            # **芯片是不透明的。** 它飞过去的时候会盖住箭头、盖住别的字——
            # 半透明的话，被盖住的东西会从芯片里透出来，箭头就从字里
            # 穿过去了（看着像字被箭头劈开）。「飞过去盖住」是正常动画，
            # 「盖住但还透出来」才是事故。
            rounded_rect(ctx, cx, cy, chip_w, chip_h, 9,
                         "#FFFFFF" if is_commit else color)
            text(ctx, op, cx + chip_w / 2, cy + chip_h * 0.70, 28,
                 COLORS["primary"] if is_commit else "#FFFFFF",
                 anchor="center", bold=True)

    # ---- 中间的去向 ----
    # 标签与箭头跟芯片在同一条通道上：起飞就让位（见 LABEL_FADE_SPAN）。
    lane_y = target_y + target_h / 2
    emit_alpha = 1.0 - min(1.0, progress / LABEL_FADE_SPAN)
    arrow(ctx, panel_x + panel_w + w * 0.015, lane_y,
          target_x - w * 0.015, lane_y, COLORS["accent"], 7, 24,
          alpha=emit_alpha)
    text(ctx, p["emit_label"], (panel_x + panel_w + target_x) / 2,
         lane_y - h * 0.045, 40, COLORS["accent"], anchor="center", bold=True,
         alpha=emit_alpha)

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

    # 飞行组此刻占的那条带：被它压过的行要让开（见 ROW_DIM_ALPHA）。
    fly_chip_h = chip_h * FLY_SCALE
    fly_top = start_y + dy * progress + (chip_h - fly_chip_h) / 2
    fly_bottom = fly_top + fly_chip_h

    for index, (txn_id, ops) in enumerate(slots):
        color = MARKER_COLORS[index % len(MARKER_COLORS)]
        y = row_top + index * (row_h + row_gap)
        badge_y = y + (row_h - chip_h) / 2
        # 这一行被飞行组压住了吗？压住多少就让开多少——
        # 刚碰到边缘时只淡一点，整个盖住了才退到底。
        overlap = min(fly_bottom, badge_y + chip_h) - max(fly_top, badge_y)
        row_alpha = 1.0
        if overlap > 0:
            row_alpha = 1.0 - (1.0 - ROW_DIM_ALPHA) * min(1.0, overlap / chip_h)
        rounded_rect(ctx, left, y, max_width, row_h, 14, "#F2F5F9",
                     alpha=row_alpha)
        stroke_rect(ctx, left, y, max_width, row_h, 14, "#DCE1E8", 3, row_alpha)
        rounded_rect(ctx, left + w * 0.020, badge_y, badge_w, chip_h, 9, color,
                     alpha=row_alpha)
        scene_layout.line(ctx, txn_id, left + w * 0.020 + badge_w / 2,
                          badge_y + chip_h * 0.70, badge_w, 32, "#FFFFFF",
                          anchor="center", bold=True, alpha=row_alpha)

        if txn_id == target_txn:
            # 整组搬走的那一组留到最后一轮再画：它要一路往下飞过
            # 下面几行，在行里画就会被后画的行面板盖住半个芯片。
            continue
        for op_index, op in enumerate(ops):
            x = chip_x0 + op_index * (chip_w + chip_gap)
            is_commit = op == commit_op
            rounded_rect(ctx, x, badge_y, chip_w, chip_h, 9,
                         "#FFFFFF" if is_commit else color, alpha=row_alpha)
            scene_layout.line(ctx, op, x + chip_w / 2, badge_y + chip_h * 0.70,
                              chip_w - 16, 28,
                              COLORS["primary"] if is_commit else "#FFFFFF",
                              anchor="center", bold=True, alpha=row_alpha)

    # ---- 发出去的那一组：整组平移，相对位置不变 ----
    emit_color = MARKER_COLORS[emit_index % len(MARKER_COLORS)]
    # 一层影子 + 大一点：芯片是从「上面」飞过去的，压在谁头上要看得出来。
    # 不加影子的话，两组一样大的芯片叠在一起还是像混成了一组；
    # 大一点还能让被盖住的那块从边上露出来——看得出下面本来是有东西的，
    # 不然看着像那一行凭空多了几块芯片。
    shadow_dx = chip_w * 0.035
    shadow_dy = chip_h * 0.10
    for op_index, op in enumerate(emit_ops):
        x = chip_x0 + op_index * (chip_w + chip_gap)
        cx = x + dx * progress
        cy = start_y + dy * progress
        is_commit = op == commit_op
        # 放大是**围着芯片中心**放大的：整组的相对位置不变，还是「一组」。
        big_w = chip_w * FLY_SCALE
        big_h = chip_h * FLY_SCALE
        bx = cx + chip_w / 2 - big_w / 2
        by = cy + chip_h / 2 - big_h / 2
        rounded_rect(ctx, bx + shadow_dx, by + shadow_dy, big_w, big_h, 9,
                     "#0B1F3A", alpha=0.16)
        rounded_rect(ctx, bx, by, big_w, big_h, 9,
                     "#FFFFFF" if is_commit else emit_color)
        scene_layout.line(ctx, op, bx + big_w / 2, by + big_h * 0.70,
                          big_w - 16, 28 * FLY_SCALE,
                          COLORS["primary"] if is_commit else "#FFFFFF",
                          anchor="center", bold=True)

    # ---- 中间的去向 ----
    # 标签与箭头在芯片的飞行走廊上：起飞就让位（见 LABEL_FADE_SPAN）。
    emit_alpha = 1.0 - min(1.0, progress / LABEL_FADE_SPAN)
    scene_layout.line(ctx, p["emit_label"], center, h * 0.468, max_width, 36,
                      COLORS["accent"], anchor="center", bold=True,
                      alpha=emit_alpha)
    arrow(ctx, center, h * 0.478, center, h * 0.505, COLORS["accent"], 7, 24,
          alpha=emit_alpha)

    scene_layout.caption(ctx, p["caption"], w, h)
