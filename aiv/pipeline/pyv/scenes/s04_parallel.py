"""段 D：reader 读取与协调，多 worker 并行解码。"""
from __future__ import annotations

from pyv import easing
from pyv.draw import arrow, rounded_rect, text
from pyv.palette import COLORS

WORKERS = 4


def worker_count() -> int:
    """并行解码的 worker 数量。"""
    return WORKERS


def render(ctx, t: float, w: int, h: int) -> None:
    text(ctx, "reader 读取与协调", w * 0.06, h * 0.15, 60, COLORS["primary"], bold=True)

    # reader
    rounded_rect(ctx, w * 0.05, h * 0.26, w * 0.19, h * 0.24, 18, COLORS["primary"])
    text(ctx, "reader", w * 0.145, h * 0.41, 48, "#FFFFFF", anchor="center")
    text(ctx, "WALSender", w * 0.145, h * 0.545, 28, COLORS["primary"], anchor="center")

    # workers
    worker_h = h * 0.115
    worker_gap = h * 0.04
    top = h * 0.20
    for i in range(worker_count()):
        y = top + i * (worker_h + worker_gap)
        delay = 0.10 * i
        grow = easing.ease_out_cubic(max(0.0, min(1.0, (t - delay) * 3.0)))
        box_w = w * 0.17 * (0.4 + 0.6 * grow)
        rounded_rect(ctx, w * 0.47, y, box_w, worker_h,
                     14, COLORS["secondary"])
        # 标签跟着盒子一起长：居中于当前盒子宽度，盒子没展开到位就先不显示
        label_alpha = max(0.0, min(1.0, (grow - 0.55) / 0.45))
        text(ctx, f"worker {i + 1}", w * 0.47 + box_w / 2, y + worker_h * 0.68,
             34, "#FFFFFF", anchor="center", alpha=label_alpha)

        arrow(ctx, w * 0.25, h * 0.38, w * 0.46, y + worker_h / 2,
              COLORS["accent"], 5, 16)
        arrow(ctx, w * 0.65, y + worker_h / 2, w * 0.72, h * 0.50,
              COLORS["secondary"], 4, 14)

    # 统一输出
    rounded_rect(ctx, w * 0.73, h * 0.30, w * 0.19, h * 0.40, 18, "#DCE1E8")
    text(ctx, "统一输出", w * 0.825, h * 0.53, 40, COLORS["primary"], anchor="center")

    text(ctx, "多个 worker 并行解码，速度显著提升",
         w * 0.06, h * 0.86, 44, COLORS["primary"])
