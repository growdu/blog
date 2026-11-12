"""段 D：五步链路的模板。

五个方块从左到右排开，每一步一个编号、一步一句话，箭头把流程串起来。
中间那一步做的活最多，所以画得最深。

版式在代码里，**这一期的步骤、说明与文案在契约里**（`Scene.params`）。
"""
from __future__ import annotations

from pyv import easing
from pyv.draw import arrow, rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "steps", "caption")

# 每一步一个颜色
STEP_COLORS = ("#F6AD55", "#4FD1C5", "#8FAADC", "#E9A0DC", "#9AD19A")

# 第 i 步在场景进度上的出现时刻
STEP_STEP = 0.13
STEP_DELAY = 0.08


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s04")
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
