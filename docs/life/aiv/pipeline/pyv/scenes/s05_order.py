"""段 E：按事务结束顺序输出，订阅端顺序与发布端一致；性能 2–5 倍。"""
from __future__ import annotations

from pyv import easing
from pyv.draw import arrow, rounded_rect, text
from pyv.palette import COLORS


def output_order() -> list[int]:
    """订阅端接收顺序，必须与发布端一致。"""
    return [1, 2, 3, 4]


def render(ctx, t: float, w: int, h: int) -> None:
    text(ctx, "按事务结束顺序输出", w * 0.06, h * 0.13, 56, COLORS["primary"], bold=True)

    for index, number in enumerate(output_order()):
        y = h * 0.22 + index * h * 0.105
        appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.08 * index) * 3.0)))
        rounded_rect(ctx, w * 0.07, y, w * 0.30, h * 0.072, 12, COLORS["secondary"],
                     alpha=0.25 + 0.75 * appear)
        text(ctx, str(number), w * 0.22, y + h * 0.05, 38, "#FFFFFF", anchor="center",
             alpha=0.25 + 0.75 * appear)

    # PingFang SC 没有 "→" 字形，箭头必须画出来而不是当文字渲染
    arrow(ctx, w * 0.39, h * 0.44, w * 0.455, h * 0.44, COLORS["primary"], 7, 20)

    rounded_rect(ctx, w * 0.47, h * 0.22, w * 0.17, h * 0.42, 16, COLORS["primary"])
    text(ctx, "订阅端", w * 0.555, h * 0.47, 42, "#FFFFFF", anchor="center")

    scale = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.35) * 2.2)))
    text(ctx, "2–5 倍", w * 0.82, h * 0.44, 132, COLORS["accent"], anchor="center",
         bold=True, alpha=scale)
    text(ctx, "并行解码整体性能", w * 0.82, h * 0.575, 36, COLORS["primary"],
         anchor="center", alpha=scale)

    text(ctx, "订阅端收到的顺序，和发布端保持一致",
         w * 0.07, h * 0.86, 44, COLORS["primary"])
