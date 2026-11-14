"""段 E：结构化之后的收益模板。

上面一条线：两头的对象名，经过一层语义处理，成了不同的名字。
下面三张卡片：结构化之后才谈得上的三件事。

版式在代码里，**这一期的名称、收益与文案在契约里**（`Scene.params`）。

**竖版（1080×1920）**：横版是「左 → 中 → 右」一条线加一排卡片，竖版
只有 1080 宽，左右三个框会挤成一条——所以改成上下串起来：
两端的框 → 中间的语义层 → 另一端的框，三张收益卡片改成竖着摞
（见 `pyv/scene_layout.py`）。
"""
from __future__ import annotations

from pyv import easing
from pyv import scene_layout
from pyv.draw import arrow, rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "source_label", "source_value", "mid_label",
            "target_label", "target_value", "benefits", "caption")

# 三张收益卡片的配色
CARD_COLORS = ("#4FD1C5", "#8FAADC", "#E9A0DC")


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s05")
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return
    benefits = [str(x) for x in p["benefits"]]

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    # ---- 两端：发布端的对象名与订阅端的对象名 ----
    box_y = h * 0.29
    box_h = h * 0.20
    box_w = w * 0.24
    for index, (label, value, x) in enumerate((
            (str(p["source_label"]), str(p["source_value"]), w * 0.11),
            (str(p["target_label"]), str(p["target_value"]), w * 0.65))):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.08 - index * 0.16) * 3.0))
        )
        rounded_rect(ctx, x, box_y, box_w, box_h, 16, COLORS["primary"],
                     alpha=appear)
        text(ctx, label, x + box_w / 2, box_y + h * 0.06, 32, COLORS["secondary"],
             anchor="center", alpha=appear)
        text(ctx, value, x + box_w / 2, box_y + h * 0.135, 44, "#FFFFFF",
             anchor="center", bold=True, alpha=appear)

    # ---- 中间：按语义执行的那一层 ----
    mid_x = w * 0.42
    mid_w = w * 0.16
    mid_y = box_y + h * 0.01
    mid_h = h * 0.18
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.30) * 3.0)))
    rounded_rect(ctx, mid_x, mid_y, mid_w, mid_h, 14, COLORS["accent"],
                 alpha=appear)
    text(ctx, p["mid_label"], mid_x + mid_w / 2, mid_y + mid_h * 0.62, 36,
         "#FFFFFF", anchor="center", bold=True, alpha=appear)

    arrow(ctx, w * 0.355, box_y + box_h * 0.5, mid_x - w * 0.008,
          mid_y + mid_h * 0.5, COLORS["accent"], 5, 18, alpha=appear)
    arrow(ctx, mid_x + mid_w + w * 0.008, mid_y + mid_h * 0.5,
          w * 0.645, box_y + box_h * 0.5, COLORS["accent"], 5, 18, alpha=appear)

    # ---- 三张收益卡片 ----
    card_w = w * 0.24
    gap = w * 0.04
    x0 = (w - (len(benefits) * card_w + (len(benefits) - 1) * gap)) / 2
    card_y = h * 0.60
    card_h = h * 0.13
    for index, benefit in enumerate(benefits):
        cx = x0 + index * (card_w + gap)
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.46 - index * 0.10) * 3.0))
        )
        color = CARD_COLORS[index % len(CARD_COLORS)]
        rounded_rect(ctx, cx, card_y, card_w, card_h, 12, "#F2F5F9", alpha=appear)
        rounded_rect(ctx, cx, card_y, w * 0.010, card_h, 5, color, alpha=appear)
        text(ctx, benefit, cx + card_w / 2 + w * 0.005, card_y + card_h * 0.66,
             30, COLORS["primary"], anchor="center", bold=True, alpha=appear)

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：两端的框 → 中间的语义层 → 另一端的框，三张收益卡片竖着摞。

    横版是「左 → 中 → 右」一条线，竖版只有 1080 宽，三个框并排会挤成
    一条线——所以改成上下串起来，框占满内容区宽度：

    - **字号不缩、框变宽**：三个框都撑满 0.88w，标签与名字比横版大一号。
    - **字要放得下**：每一行字都过 `scene_layout.line`。
    """
    benefits = [str(x) for x in p["benefits"]]
    left = w * scene_layout.MARGIN_X
    max_width = w * scene_layout.CONTENT_W
    center = left + max_width / 2

    scene_layout.title(ctx, p["title"], w, h, size=60)

    # ---- 两端：发布端的对象名与订阅端的对象名（上下串起来） ----
    for index, (label, value, y) in enumerate((
            (str(p["source_label"]), str(p["source_value"]), h * 0.130),
            (str(p["target_label"]), str(p["target_value"]), h * 0.342))):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.08 - index * 0.16) * 3.0))
        )
        rounded_rect(ctx, left, y, max_width, h * 0.078, 16, COLORS["primary"],
                     alpha=appear)
        scene_layout.line(ctx, label, center, y + h * 0.029, max_width, 36,
                          COLORS["secondary"], anchor="center", alpha=appear)
        scene_layout.line(ctx, value, center, y + h * 0.058, max_width, 46,
                          "#FFFFFF", bold=True, anchor="center", alpha=appear)

    # ---- 中间：按语义执行的那一层 ----
    mid_y = h * 0.240
    mid_h = h * 0.068
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.30) * 3.0)))
    rounded_rect(ctx, left, mid_y, max_width, mid_h, 14, COLORS["accent"],
                 alpha=appear)
    scene_layout.line(ctx, p["mid_label"], center, mid_y + mid_h * 0.63,
                      max_width, 42, "#FFFFFF", anchor="center", bold=True,
                      alpha=appear)

    arrow(ctx, center, h * 0.213, center, h * 0.235, COLORS["accent"], 6, 20,
          alpha=appear)
    arrow(ctx, center, h * 0.313, center, h * 0.337, COLORS["accent"], 6, 20,
          alpha=appear)

    # ---- 三张收益卡片：竖着摞 ----
    card_y = h * 0.436
    card_h = h * 0.055
    card_gap = h * 0.010
    for index, benefit in enumerate(benefits):
        y = card_y + index * (card_h + card_gap)
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.46 - index * 0.10) * 3.0))
        )
        color = CARD_COLORS[index % len(CARD_COLORS)]
        rounded_rect(ctx, left, y, max_width, card_h, 12, "#F2F5F9", alpha=appear)
        rounded_rect(ctx, left, y, w * 0.010, card_h, 5, color, alpha=appear)
        scene_layout.line(ctx, benefit, center + w * 0.005, y + card_h * 0.68,
                          max_width - w * 0.020, 32, COLORS["primary"],
                          anchor="center", bold=True, alpha=appear)

    scene_layout.caption(ctx, p["caption"], w, h)
