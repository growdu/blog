"""段 E：按序输出与强调数字模板。

左边一列编号方块，右边一个接收方，配一句强调数字。
版式在代码里，**这一期的编号、强调数字与文案在契约里**（`Scene.params`）。
"""
from __future__ import annotations

from pyv import easing
from pyv.draw import arrow, rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "order", "target_label", "callout", "callout_sub", "caption")


def output_order(params=None) -> list[int]:
    """接收方的顺序，必须与来源端一致。"""
    p = Params(params, "s05")
    return [int(n) for n in p["order"]]


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s05")
    text(ctx, p["title"], w * 0.06, h * 0.13, 56, COLORS["primary"], bold=True)

    for index, number in enumerate(output_order(params)):
        y = h * 0.22 + index * h * 0.105
        appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.08 * index) * 3.0)))
        rounded_rect(ctx, w * 0.07, y, w * 0.30, h * 0.072, 12, COLORS["secondary"],
                     alpha=0.25 + 0.75 * appear)
        text(ctx, str(number), w * 0.22, y + h * 0.05, 38, "#FFFFFF", anchor="center",
             alpha=0.25 + 0.75 * appear)

    # PingFang SC 没有 "→" 字形，箭头必须画出来而不是当文字渲染
    arrow(ctx, w * 0.39, h * 0.44, w * 0.455, h * 0.44, COLORS["primary"], 7, 20)

    rounded_rect(ctx, w * 0.47, h * 0.22, w * 0.17, h * 0.42, 16, COLORS["primary"])
    text(ctx, p["target_label"], w * 0.555, h * 0.47, 42, "#FFFFFF", anchor="center")

    scale = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.35) * 2.2)))
    text(ctx, p["callout"], w * 0.82, h * 0.44, 132, COLORS["accent"], anchor="center",
         bold=True, alpha=scale)
    text(ctx, p["callout_sub"], w * 0.82, h * 0.575, 36, COLORS["primary"],
         anchor="center", alpha=scale)

    text(ctx, p["caption"], w * 0.07, h * 0.86, 44, COLORS["primary"])
