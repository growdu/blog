"""段 C：在读写的隔离之上，多加一层写与写之间的协调。

上面两块对照：左边那一层管读与读、写与读，右边那一层管写与写。
下面一排模式卡，按强弱排开。

版式在代码里，**这一期的对照文字、模式名与 SQL 在契约里**（`Scene.params`）。

**竖版（1080×1920）**：横版是「左右两块对照 + 下面一排模式卡」，
竖版改成上下堆叠——两块对照改为上下叠放（中间一支向下的箭头），
四种模式卡改成四条整宽的横条依次排开，从最弱到最强
（见 `pyv/scene_layout.py` 的三条规矩）。
"""
from __future__ import annotations

from pyv import easing
from pyv import scene_layout
from pyv.draw import arrow, rounded_rect, stroke_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "left_label", "left_note", "right_label", "right_note",
            "modes", "weak_label", "strong_label", "caption")

# 四种模式从弱到强的配色：青 → 蓝 → 深蓝
MODE_COLORS = ("#4FD1C5", "#74B9E0", "#4A7FB5", "#2B4C7E")

# 版式常量
CMP_Y_RATIO, CMP_H_RATIO = 0.26, 0.15
CMP_W_RATIO = 0.34
CMP_A_X_RATIO, CMP_B_X_RATIO = 0.06, 0.60
MODE_Y_RATIO, MODE_H_RATIO = 0.50, 0.16
MODE_W_RATIO, MODE_GAP_RATIO = 0.21, 0.015
STRENGTH_Y_RATIO = 0.715


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s03")
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return

    modes = [[str(x) for x in pair] for pair in p["modes"]]

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    # ---- 上面两块对照 ----
    cmp_y, cmp_h = h * CMP_Y_RATIO, h * CMP_H_RATIO
    cmp_w = w * CMP_W_RATIO
    for index, (label, note, x_ratio, fill) in enumerate((
        (str(p["left_label"]), str(p["left_note"]), CMP_A_X_RATIO, "#F2F5F9"),
        (str(p["right_label"]), str(p["right_note"]), CMP_B_X_RATIO,
         COLORS["primary"]),
    )):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.08 - index * 0.16) * 3.0))
        )
        box_x = w * x_ratio
        rounded_rect(ctx, box_x, cmp_y, cmp_w, cmp_h, 14, fill, alpha=appear)
        if fill == "#F2F5F9":
            stroke_rect(ctx, box_x, cmp_y, cmp_w, cmp_h, 14, "#DCE1E8", 3,
                        0.9 * appear)
        dark = fill != "#F2F5F9"
        text(ctx, label, box_x + w * 0.025, cmp_y + h * 0.068, 40,
             "#FFFFFF" if dark else COLORS["primary"], bold=True, alpha=appear)
        text(ctx, note, box_x + w * 0.025, cmp_y + h * 0.125, 30,
             "#FFFFFF" if dark else COLORS["secondary"], alpha=appear)

    # 中间那支箭头：从 MVCC 指向行锁
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.30) * 3.0)))
    arrow(ctx, w * 0.43, cmp_y + cmp_h * 0.5, w * 0.57, cmp_y + cmp_h * 0.5,
          COLORS["accent"], 6, 20, alpha=appear)

    # ---- 下面四种模式 ----
    mode_y, mode_h = h * MODE_Y_RATIO, h * MODE_H_RATIO
    mode_w = w * MODE_W_RATIO
    gap = w * MODE_GAP_RATIO
    for index, pair in enumerate(modes[:4]):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.38 - index * 0.09) * 3.0))
        )
        box_x = w * 0.06 + index * (mode_w + gap)
        rounded_rect(ctx, box_x, mode_y, mode_w, mode_h, 12,
                     MODE_COLORS[index % len(MODE_COLORS)], alpha=appear)
        text(ctx, pair[0], box_x + mode_w / 2, mode_y + mode_h * 0.44, 32,
             "#FFFFFF", anchor="center", bold=True, alpha=appear)
        text(ctx, pair[1], box_x + mode_w / 2, mode_y + mode_h * 0.80, 24,
             "#FFFFFF", anchor="center", alpha=0.88 * appear)

    # ---- 从弱到强 ----
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.72) * 3.0)))
    strength_y = h * STRENGTH_Y_RATIO
    text(ctx, p["weak_label"], w * 0.06, strength_y - h * 0.012, 30,
         COLORS["secondary"], bold=True, alpha=appear)
    text(ctx, p["strong_label"], w * 0.94, strength_y - h * 0.012, 30,
         COLORS["primary"], anchor="right", bold=True, alpha=appear)
    arrow(ctx, w * 0.14, strength_y, w * 0.86, strength_y,
          COLORS["secondary"], 6, 20, alpha=appear)

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：两块对照上下叠放，四种模式卡排成四条整宽横条。

    横版把两块对照并排放、中间一支向右的箭头；竖版把两块改成
    上下叠放、中间一支向下的箭头。四种模式卡从横版的一排四张改成
    竖向的四条横条，每条左侧是模式名、右侧是对应的 SQL。
    """
    modes = [[str(x) for x in pair] for pair in p["modes"]]

    left = scene_layout.content_left(w)
    full_w = scene_layout.content_width(w)
    center = left + full_w / 2

    scene_layout.title(ctx, p["title"], w, h)

    # ---- 上面两块对照：改成上下叠放 ----
    cmp_h = 150
    cmp_a_y = scene_layout.content_top(h)
    cmp_b_y = cmp_a_y + cmp_h + 70
    for index, (label, note, box_y, fill) in enumerate((
        (str(p["left_label"]), str(p["left_note"]), cmp_a_y, "#F2F5F9"),
        (str(p["right_label"]), str(p["right_note"]), cmp_b_y, COLORS["primary"]),
    )):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.08 - index * 0.16) * 3.0))
        )
        rounded_rect(ctx, left, box_y, full_w, cmp_h, 14, fill, alpha=appear)
        if fill == "#F2F5F9":
            stroke_rect(ctx, left, box_y, full_w, cmp_h, 14, "#DCE1E8", 3,
                        0.9 * appear)
        dark = fill != "#F2F5F9"
        scene_layout.line(ctx, label, left + 30, box_y + 66, full_w - 60, 44,
                          "#FFFFFF" if dark else COLORS["primary"], bold=True,
                          alpha=appear)
        scene_layout.line(ctx, note, left + 30, box_y + 122, full_w - 60, 34,
                          "#FFFFFF" if dark else COLORS["secondary"],
                          alpha=appear)

    # 中间那支箭头：从 MVCC 指向行锁（竖版是向下）
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.30) * 3.0)))
    arrow(ctx, center, cmp_a_y + cmp_h + 12, center, cmp_b_y - 12,
          COLORS["accent"], 6, 20, alpha=appear)

    # ---- 四种模式：四条整宽横条 ----
    mode_y = cmp_b_y + cmp_h + 40
    mode_h = 86
    mode_gap = 16
    for index, pair in enumerate(modes[:4]):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.38 - index * 0.09) * 3.0))
        )
        box_y = mode_y + index * (mode_h + mode_gap)
        rounded_rect(ctx, left, box_y, full_w, mode_h, 12,
                     MODE_COLORS[index % len(MODE_COLORS)], alpha=appear)
        scene_layout.line(ctx, pair[0], left + 30, box_y + 54, 430, 34,
                          "#FFFFFF", bold=True, alpha=appear)
        scene_layout.line(ctx, pair[1], left + full_w - 30, box_y + 54, 430,
                          30, "#FFFFFF", alpha=0.88 * appear, anchor="right")

    # ---- 从弱到强 ----
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.72) * 3.0)))
    strength_y = mode_y + 4 * mode_h + 3 * mode_gap + 60
    scene_layout.line(ctx, p["weak_label"], left, strength_y, 200, 34,
                      COLORS["secondary"], bold=True, alpha=appear)
    scene_layout.line(ctx, p["strong_label"], left + full_w, strength_y, 200,
                      34, COLORS["primary"], bold=True, alpha=appear,
                      anchor="right")
    arrow(ctx, left + 160, strength_y + 30, left + full_w - 160,
          strength_y + 30, COLORS["secondary"], 6, 20, alpha=appear)

    scene_layout.caption(ctx, p["caption"], w, h)
