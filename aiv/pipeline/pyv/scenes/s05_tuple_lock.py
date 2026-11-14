"""段 E：锁没有自己的结构，它就寄存在行记录的固定字段里。

左边是那几个字段，右边是把其中一个字段展开成它的几个位，
最后再接一条岔路：只装得下一个事务的时候，换一个地方记。

版式在代码里，**这一期的字段名、位名与文案在契约里**（`Scene.params`）。

**竖版（1080×1920）**：横版是「左边字段列 + 右边位展开」，竖版只有
1080 宽，左右分栏会把位名压到放不下——所以改成上下堆叠：字段卡在上，
位展开在中间，换个地方记的那条岔路在最下面
（见 `pyv/scene_layout.py` 的三条规矩）。
"""
from __future__ import annotations

from pyv import easing
from pyv import scene_layout
from pyv.draw import arrow, rounded_rect, stroke_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "tuple_label", "field_labels", "bit_labels",
            "lock_only_label", "deleted_label", "multixact_label",
            "multixact_note", "caption")

# 版式常量
CARD_X_RATIO, CARD_Y_RATIO = 0.06, 0.28
CARD_W_RATIO, CARD_H_RATIO = 0.30, 0.46
CARD_TITLE_Y_RATIO = 0.335
FIELD_X_RATIO = 0.085
FIELD_W_RATIO = 0.245
FIELD_H_RATIO = 0.065
FIELD_Y = (0.38, 0.46, 0.655)
# 两种含义的小字排在 t_xmax 框下面：框底到第一行小字之间要留够空当，
# 压上去会读成「框里写了一半字」。
NOTE_Y = (0.565, 0.607)

BIT_X_RATIO = 0.42
BIT_W_RATIO, BIT_GAP_RATIO = 0.25, 0.02
BIT_Y = (0.27, 0.415)
BIT_H_RATIO = 0.125

MX_X_RATIO, MX_Y_RATIO = 0.42, 0.64
MX_W_RATIO, MX_H_RATIO = 0.52, 0.14


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s05")
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return
    fields = [str(x) for x in p["field_labels"]]
    bits = [[str(x) for x in pair] for pair in p["bit_labels"]]

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    # ---- 左边：元组头 ----
    card_x, card_y = w * CARD_X_RATIO, h * CARD_Y_RATIO
    card_w, card_h = w * CARD_W_RATIO, h * CARD_H_RATIO
    rounded_rect(ctx, card_x, card_y, card_w, card_h, 16, "#F2F5F9")
    stroke_rect(ctx, card_x, card_y, card_w, card_h, 16, "#DCE1E8", 3, 0.9)
    text(ctx, p["tuple_label"], card_x + w * 0.025, h * CARD_TITLE_Y_RATIO, 38,
         COLORS["primary"], bold=True)

    field_x = w * FIELD_X_RATIO
    field_w = w * FIELD_W_RATIO
    field_h = h * FIELD_H_RATIO
    for index, label in enumerate(fields[:3]):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.08 - index * 0.10) * 3.0))
        )
        y = h * FIELD_Y[index]
        highlight = index > 0
        rounded_rect(ctx, field_x, y, field_w, field_h, 9,
                     COLORS["primary"] if highlight else "#FFFFFF",
                     alpha=appear)
        if not highlight:
            stroke_rect(ctx, field_x, y, field_w, field_h, 9, "#C8D2DE", 3,
                        0.9 * appear)
        text(ctx, label, field_x + field_w / 2, y + field_h * 0.68, 30,
             "#FFFFFF" if highlight else COLORS["primary"], anchor="center",
             bold=True, alpha=appear)

    # ---- 元组头那一列的两种含义 ----
    for index, label in enumerate((str(p["lock_only_label"]),
                                   str(p["deleted_label"]))):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.40 - index * 0.08) * 3.0))
        )
        cy = h * NOTE_Y[index]
        rounded_rect(ctx, field_x, cy - h * 0.010, w * 0.008, w * 0.008, 4,
                     COLORS["accent"], alpha=appear)
        text(ctx, label, field_x + w * 0.018, cy, 22, COLORS["primary"],
             alpha=appear)

    # ---- 右边：位展开 ----
    bit_w = w * BIT_W_RATIO
    bit_h = h * BIT_H_RATIO
    gap = w * BIT_GAP_RATIO
    for index, pair in enumerate(bits[:4]):
        row, col = divmod(index, 2)
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.28 - index * 0.09) * 3.0))
        )
        x = w * BIT_X_RATIO + col * (bit_w + gap)
        y = h * BIT_Y[row]
        last = index == 3
        rounded_rect(ctx, x, y, bit_w, bit_h, 12,
                     COLORS["primary"] if last else "#FFFFFF", alpha=appear)
        if not last:
            stroke_rect(ctx, x, y, bit_w, bit_h, 12, "#C8D2DE", 3, 0.9 * appear)
        fg = "#FFFFFF" if last else COLORS["primary"]
        text(ctx, pair[0], x + bit_w / 2, y + bit_h * 0.44, 24, fg,
             anchor="center", bold=True, alpha=appear)
        text(ctx, pair[1], x + bit_w / 2, y + bit_h * 0.80, 22, fg,
             anchor="center", alpha=0.9 * appear)

    # ---- 元组头 → 位展开 ----
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.50) * 3.0)))
    arrow(ctx, w * 0.365, h * 0.687, w * 0.412, h * 0.478,
          COLORS["accent"], 5, 18, alpha=appear)

    # ---- 装不下时，换个地方记 ----
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.62) * 3.0)))
    arrow(ctx, w * 0.815, h * 0.548, w * 0.815, h * 0.632,
          COLORS["accent"], 5, 18, alpha=appear)

    mx_x, mx_y = w * MX_X_RATIO, h * MX_Y_RATIO
    mx_w, mx_h = w * MX_W_RATIO, h * MX_H_RATIO
    rounded_rect(ctx, mx_x, mx_y, mx_w, mx_h, 14, COLORS["secondary"],
                 alpha=appear)
    text(ctx, p["multixact_label"], mx_x + w * 0.025, mx_y + mx_h * 0.62, 36,
         "#FFFFFF", bold=True, alpha=appear)
    text(ctx, p["multixact_note"], mx_x + w * 0.175, mx_y + mx_h * 0.60, 28,
         "#FFFFFF", alpha=appear)

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：字段卡在上，位展开在中间，岔路在最下面。

    横版是「左边字段列 + 右边位展开」，竖版只有 1080 宽，左右分栏会把
    位名（最长的 21 个字符）压到放不下——所以改成上下堆叠：

    - **字号不缩、框变宽**：字段卡与位框都撑满 0.88w（位展开排成
      2×2），位名 28、字段名 32，都比横版大一号。
    - **字要放得下**：每一行字都过 `scene_layout.line`。
    """
    fields = [str(x) for x in p["field_labels"]]
    bits = [[str(x) for x in pair] for pair in p["bit_labels"]]

    left = w * scene_layout.MARGIN_X
    max_width = w * scene_layout.CONTENT_W
    center = left + max_width / 2

    scene_layout.title(ctx, p["title"], w, h, size=60)

    # ---- 上面的元组头 ----
    card_y = h * 0.125
    card_h = h * 0.182
    rounded_rect(ctx, left, card_y, max_width, card_h, 16, "#F2F5F9")
    stroke_rect(ctx, left, card_y, max_width, card_h, 16, "#DCE1E8", 3, 0.9)
    scene_layout.line(ctx, p["tuple_label"], left + w * 0.026, card_y + h * 0.030,
                      max_width * 0.4, 40, COLORS["primary"], bold=True)

    field_gap = w * 0.022
    field_inset = w * 0.026
    field_w = (max_width - 2 * field_inset - 2 * field_gap) / 3
    field_h = h * 0.047
    field_y = card_y + h * 0.045
    for index, label in enumerate(fields[:3]):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.08 - index * 0.10) * 3.0))
        )
        x = left + field_inset + index * (field_w + field_gap)
        highlight = index > 0
        rounded_rect(ctx, x, field_y, field_w, field_h, 9,
                     COLORS["primary"] if highlight else "#FFFFFF",
                     alpha=appear)
        if not highlight:
            stroke_rect(ctx, x, field_y, field_w, field_h, 9, "#C8D2DE", 3,
                        0.9 * appear)
        scene_layout.line(ctx, label, x + field_w / 2, field_y + field_h * 0.68,
                          field_w - 16, 32,
                          "#FFFFFF" if highlight else COLORS["primary"],
                          anchor="center", bold=True, alpha=appear)

    # ---- 元组头那一列的两种含义 ----
    for index, label in enumerate((str(p["lock_only_label"]),
                                   str(p["deleted_label"]))):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.40 - index * 0.08) * 3.0))
        )
        cy = card_y + h * (0.125 + index * 0.030)
        rounded_rect(ctx, left + field_inset, cy - h * 0.010, w * 0.010,
                     w * 0.010, 4, COLORS["accent"], alpha=appear)
        scene_layout.line(ctx, label, left + field_inset + w * 0.020, cy,
                          max_width * 0.8, 30, COLORS["primary"], alpha=appear)

    # ---- 中间的位展开：2×2 ----
    bit_gap = w * 0.028
    bit_w = (max_width - bit_gap) / 2
    bit_h = h * 0.070
    for index, pair in enumerate(bits[:4]):
        row, col = divmod(index, 2)
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.28 - index * 0.09) * 3.0))
        )
        x = left + col * (bit_w + bit_gap)
        y = h * 0.345 + row * (bit_h + h * 0.014)
        last = index == 3
        rounded_rect(ctx, x, y, bit_w, bit_h, 12,
                     COLORS["primary"] if last else "#FFFFFF", alpha=appear)
        if not last:
            stroke_rect(ctx, x, y, bit_w, bit_h, 12, "#C8D2DE", 3, 0.9 * appear)
        fg = "#FFFFFF" if last else COLORS["primary"]
        scene_layout.line(ctx, pair[0], x + bit_w / 2, y + bit_h * 0.44,
                          bit_w - 40, 28, fg, anchor="center", bold=True,
                          alpha=appear)
        scene_layout.line(ctx, pair[1], x + bit_w / 2, y + bit_h * 0.80,
                          bit_w - 40, 26, fg, anchor="center", alpha=0.9 * appear)

    # ---- 元组头 → 位展开 ----
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.50) * 3.0)))
    arrow(ctx, center, h * 0.312, center, h * 0.338, COLORS["accent"], 6, 20,
          alpha=appear)

    # ---- 装不下时，换个地方记 ----
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.62) * 3.0)))
    arrow(ctx, center, h * 0.496, center, h * 0.522, COLORS["accent"], 6, 20,
          alpha=appear)

    mx_y = h * 0.528
    mx_h = h * 0.072
    rounded_rect(ctx, left, mx_y, max_width, mx_h, 14, COLORS["secondary"],
                 alpha=appear)
    scene_layout.line(ctx, p["multixact_label"], left + w * 0.026,
                      mx_y + h * 0.030, max_width * 0.5, 40, "#FFFFFF", bold=True,
                      alpha=appear)
    scene_layout.line(ctx, p["multixact_note"], left + w * 0.026,
                      mx_y + h * 0.055, max_width * 0.8, 32, "#FFFFFF",
                      alpha=appear)

    scene_layout.caption(ctx, p["caption"], w, h)
