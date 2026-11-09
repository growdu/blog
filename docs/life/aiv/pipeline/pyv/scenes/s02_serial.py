"""段 B：发布端单解码线程，事务排队积压。"""
from __future__ import annotations

from pyv import easing
from pyv.draw import arrow, rounded_rect, text
from pyv.palette import COLORS

QUEUE_COLORS = ("#F6AD55", "#F8C489", "#F6AD55", "#F8C489", "#F6AD55")


def render(ctx, t: float, w: int, h: int) -> None:
    text(ctx, "发布端只有一个解码线程", w * 0.07, h * 0.16, 60, COLORS["problem"], bold=True)

    # 排队的事务块：越靠前越接近解码器
    for i, color in enumerate(QUEUE_COLORS):
        y = h * (0.28 + i * 0.105)
        progress = easing.ease_in_out(min(1.0, t * 1.5))
        # 事务块朝解码器（右侧）推进，不能滑出画面左侧
        shift = progress * w * 0.065 * (i + 1) / len(QUEUE_COLORS)
        rounded_rect(ctx, w * 0.08 + shift, y, w * 0.20, h * 0.065, 10, color)

    # 唯一的解码线程
    rounded_rect(ctx, w * 0.36, h * 0.28, w * 0.17, h * 0.42, 18, COLORS["primary"])
    text(ctx, "decoder", w * 0.445, h * 0.53, 46, "#FFFFFF", anchor="center")
    text(ctx, "单线程", w * 0.445, h * 0.60, 34, COLORS["secondary"], anchor="center")

    arrow(ctx, w * 0.54, h * 0.49, w * 0.73, h * 0.49, COLORS["primary"], 8, 24)

    # 订阅端
    rounded_rect(ctx, w * 0.75, h * 0.34, w * 0.18, h * 0.30, 18, "#DCE1E8")
    text(ctx, "订阅端", w * 0.84, h * 0.52, 40, COLORS["primary"], anchor="center")

    text(ctx, "大事务小事务都得排队，队列越积越长",
         w * 0.07, h * 0.86, 44, COLORS["primary"])
