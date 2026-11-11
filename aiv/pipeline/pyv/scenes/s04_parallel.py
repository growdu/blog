"""段 D：多路并行分支模板。

左边一个来源方，中间一列并行分支，右边一个汇聚方。
版式在代码里，**这一期的数量与文案在契约里**（`Scene.params`）。
"""
from __future__ import annotations

from pyv import easing
from pyv.draw import arrow, rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "source_label", "source_sub", "worker_count",
            "worker_prefix", "target_label", "caption")


def worker_count(params=None) -> int:
    """并行分支的数量。"""
    p = Params(params, "s04")
    return int(p["worker_count"])


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s04")
    text(ctx, p["title"], w * 0.06, h * 0.15, 60, COLORS["primary"], bold=True)

    # 来源方
    rounded_rect(ctx, w * 0.05, h * 0.26, w * 0.19, h * 0.24, 18, COLORS["primary"])
    text(ctx, p["source_label"], w * 0.145, h * 0.41, 48, "#FFFFFF", anchor="center")
    text(ctx, p["source_sub"], w * 0.145, h * 0.545, 28, COLORS["primary"], anchor="center")

    # 并行分支
    worker_h = h * 0.115
    worker_gap = h * 0.04
    top = h * 0.20
    for i in range(worker_count(params)):
        y = top + i * (worker_h + worker_gap)
        delay = 0.10 * i
        grow = easing.ease_out_cubic(max(0.0, min(1.0, (t - delay) * 3.0)))
        box_w = w * 0.17 * (0.4 + 0.6 * grow)
        rounded_rect(ctx, w * 0.47, y, box_w, worker_h,
                     14, COLORS["secondary"])
        # 标签跟着盒子一起长：居中于当前盒子宽度，盒子没展开到位就先不显示
        label_alpha = max(0.0, min(1.0, (grow - 0.55) / 0.45))
        text(ctx, f"{p['worker_prefix']} {i + 1}", w * 0.47 + box_w / 2, y + worker_h * 0.68,
             34, "#FFFFFF", anchor="center", alpha=label_alpha)

        arrow(ctx, w * 0.25, h * 0.38, w * 0.46, y + worker_h / 2,
              COLORS["accent"], 5, 16)
        arrow(ctx, w * 0.65, y + worker_h / 2, w * 0.72, h * 0.50,
              COLORS["secondary"], 4, 14)

    # 汇聚方
    rounded_rect(ctx, w * 0.73, h * 0.30, w * 0.19, h * 0.40, 18, "#DCE1E8")
    text(ctx, p["target_label"], w * 0.825, h * 0.53, 40, COLORS["primary"], anchor="center")

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])
