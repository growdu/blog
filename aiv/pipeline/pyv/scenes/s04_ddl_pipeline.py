"""段 D：五步链路的模板。

五个方块从左到右排开，每一步一个编号、一步一句话，箭头把流程串起来。
中间那一步做的活最多，所以画得最深。

版式在代码里，**这一期的步骤、说明与文案在契约里**（`Scene.params`）。

**竖版（1080×1920）**：横版是「五块并排」，竖版改成「五块从上往下排」。
竖版只有 1080 宽，五块并排每块只剩 200 宽，带英文的长步骤名根本放不下。
竖版里每一步占满一整行：编号在左边的竖轴上，步骤名与说明分列卡片两侧
（见 `pyv/scene_layout.py` 的三条规矩）。
"""
from __future__ import annotations

from pyv import easing
from pyv import scene_layout
from pyv.draw import arrow, rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "steps", "caption")

# 每一步一个颜色
STEP_COLORS = ("#F6AD55", "#4FD1C5", "#8FAADC", "#E9A0DC", "#9AD19A")

# 第 i 步在场景进度上的出现时刻
STEP_STEP = 0.13
STEP_DELAY = 0.08

# 竖版：一步一行的版式常量
V_CARD_H_RATIO = 0.078      # 卡片高（相对画面高度）
V_CARD_GAP_RATIO = 0.022    # 卡片之间的间隙（相对画面高度）
V_BADGE_RATIO = 0.055       # 编号圆的直径（相对画面宽度）
V_BAND_RATIO = 0.014        # 卡片左侧色带的宽（相对画面宽度）
V_TEXT_X_RATIO = 0.133      # 步骤名相对画面左边距（相对画面宽度）
V_NAME_RATIO = 0.40         # 步骤名可占的宽度（相对内容区宽度）
V_DESC_RATIO = 0.40         # 说明可占的宽度（相对内容区宽度）


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s04")
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return

    steps = [(str(row[0]), str(row[1])) for row in p["steps"]]

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    count = len(steps)
    box_w = w * 0.145
    gap = w * 0.035
    x0 = (w - (count * box_w + (count - 1) * gap)) / 2
    box_y = h * 0.34
    box_h = h * 0.27

    for index, (name, desc) in enumerate(steps):
        cx = x0 + index * (box_w + gap)
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - STEP_DELAY - STEP_STEP * index) * 3.2))
        )
        color = STEP_COLORS[index % len(STEP_COLORS)]
        rounded_rect(ctx, cx, box_y, box_w, box_h, 14, "#F2F5F9", alpha=appear)
        # 顶部一条色带
        rounded_rect(ctx, cx, box_y, box_w, h * 0.014, 7, color, alpha=appear)
        # 编号
        badge_x = cx + w * 0.022
        badge_y = box_y + h * 0.045
        rounded_rect(ctx, badge_x, badge_y, w * 0.032, w * 0.032, w * 0.016,
                     color, alpha=appear)
        text(ctx, str(index + 1), badge_x + w * 0.016, badge_y + w * 0.023, 30,
             "#FFFFFF", anchor="center", bold=True, alpha=appear)
        # 步骤名与说明
        text(ctx, name, cx + box_w / 2, box_y + h * 0.135, 36, COLORS["primary"],
             anchor="center", bold=True, alpha=appear)
        text(ctx, desc, cx + box_w / 2, box_y + h * 0.205, 26,
             COLORS["secondary"], anchor="center", alpha=appear)

        # 步骤之间的箭头
        if index < count - 1:
            arrow(ctx, cx + box_w + w * 0.006, box_y + box_h * 0.5,
                  cx + box_w + gap - w * 0.006, box_y + box_h * 0.5,
                  COLORS["accent"], 5, 16, alpha=appear)

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：五步从上往下排成一条竖轴。

    **字号不缩、框变宽**：步骤名 40、说明 30，跟横版同档甚至更大，
    但每一步都占满一整行（内容区宽 950），所以放得下——
    横版那种「五块并排」在 1080 宽的竖版里每块只有 200 宽，放不下。

    每一步一张卡片，编号圆排在左边同一条竖轴上，卡片之间的箭头也接在
    这条轴上——五步从上到下一眼看得出顺序。
    """
    steps = [(str(row[0]), str(row[1])) for row in p["steps"]]
    count = len(steps)
    left = w * scene_layout.MARGIN_X
    width = w * scene_layout.CONTENT_W
    right = left + width

    scene_layout.title(ctx, p["title"], w, h)

    card_h = h * V_CARD_H_RATIO
    gap = h * V_CARD_GAP_RATIO
    total = count * card_h + (count - 1) * gap
    top = h * scene_layout.CONTENT_TOP
    bottom = h * scene_layout.CONTENT_BOTTOM
    y0 = top + (bottom - top - total) / 2

    badge = w * V_BADGE_RATIO
    badge_x = left + w * 0.035
    for index, (name, desc) in enumerate(steps):
        card_y = y0 + index * (card_h + gap)
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - STEP_DELAY - STEP_STEP * index) * 3.2))
        )
        color = STEP_COLORS[index % len(STEP_COLORS)]
        # 卡片本体
        rounded_rect(ctx, left, card_y, width, card_h, 14, "#F2F5F9", alpha=appear)
        # 左侧一条色带：竖着排之后，色带走左边才看得出这一步是第几步
        rounded_rect(ctx, left, card_y, w * V_BAND_RATIO, card_h, 7, color,
                     alpha=appear)
        # 编号
        badge_y = card_y + (card_h - badge) / 2
        rounded_rect(ctx, badge_x, badge_y, badge, badge, badge / 2, color,
                     alpha=appear)
        scene_layout.line(ctx, str(index + 1), badge_x + badge / 2,
                          badge_y + badge * 0.62, badge, 30, "#FFFFFF",
                          bold=True, alpha=appear, anchor="center")
        # 步骤名（左）与说明（右）：一行两列，卡片两头都不留空
        baseline = card_y + card_h * 0.62
        scene_layout.line(ctx, name, left + w * V_TEXT_X_RATIO, baseline,
                          width * V_NAME_RATIO, 40, COLORS["primary"],
                          bold=True, alpha=appear)
        scene_layout.line(ctx, desc, right - w * 0.035, baseline,
                          width * V_DESC_RATIO, 30, COLORS["secondary"],
                          alpha=appear, anchor="right")

        # 步骤之间的箭头：接在编号那一列上，串起五步
        if index < count - 1:
            axis_x = badge_x + badge / 2
            arrow(ctx, axis_x, card_y + card_h + h * 0.004,
                  axis_x, card_y + card_h + gap - h * 0.004,
                  COLORS["accent"], 4, 12, alpha=appear)

    scene_layout.caption(ctx, p["caption"], w, h)
