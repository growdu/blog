"""段 B：串行排队模板。

左边一列积压块，中间一个处理方，右边一个接收方。
版式在代码里，**这一期的文字在契约里**（`Scene.params`）。
"""
from __future__ import annotations

from pyv import easing
from pyv.draw import arrow, rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "decoder_label", "decoder_sub", "target_label", "caption")

QUEUE_COUNT = 5
QUEUE_COLORS = ("#F6AD55", "#F8C489", "#F6AD55", "#F8C489", "#F6AD55")


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s02")
    text(ctx, p["title"], w * 0.07, h * 0.16, 60, COLORS["problem"], bold=True)

    # 排队的事务块：越靠前越接近解码器
    for i, color in enumerate(QUEUE_COLORS[:QUEUE_COUNT]):
        y = h * (0.28 + i * 0.105)
        progress = easing.ease_in_out(min(1.0, t * 1.5))
        # 事务块朝解码器（右侧）推进，不能滑出画面左侧
        shift = progress * w * 0.065 * (i + 1) / QUEUE_COUNT
        rounded_rect(ctx, w * 0.08 + shift, y, w * 0.20, h * 0.065, 10, color)

    # 唯一的解码线程
    rounded_rect(ctx, w * 0.36, h * 0.28, w * 0.17, h * 0.42, 18, COLORS["primary"])
    text(ctx, p["decoder_label"], w * 0.445, h * 0.53, 46, "#FFFFFF", anchor="center")
    text(ctx, p["decoder_sub"], w * 0.445, h * 0.60, 34, COLORS["secondary"], anchor="center")

    arrow(ctx, w * 0.54, h * 0.49, w * 0.73, h * 0.49, COLORS["primary"], 8, 24)

    # 接收方
    rounded_rect(ctx, w * 0.75, h * 0.34, w * 0.18, h * 0.30, 18, "#DCE1E8")
    text(ctx, p["target_label"], w * 0.84, h * 0.52, 40, COLORS["primary"], anchor="center")

    text(ctx, p["caption"], w * 0.07, h * 0.86, 44, COLORS["primary"])
