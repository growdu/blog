"""段 E：压测数字模板。

左边两条吞吐条（串行一条整条，并行一段区间），右边一个强调数字。
版式在代码里，**这一期的标签与数字在契约里**（`Scene.params`）。
"""
from __future__ import annotations

from pyv import easing
from pyv.draw import rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "serial_label", "parallel_label", "callout",
            "callout_sub", "caption")

# 刻度：单位是「相对串行解码的倍数」。1 倍对应 UNIT_W 宽的画布比例。
UNIT_W = 0.09
TRACK_X = 0.07
SERIAL_LABEL_Y = 0.30
SERIAL_Y = 0.33
PARALLEL_LABEL_Y = 0.50
PARALLEL_Y = 0.53
BAR_H = 0.085
TRACK_Y = 0.635
TICK_Y = 0.70
# 实测区间：2 倍到 5 倍
RANGE_LOW = 2
RANGE_HIGH = 5
CALL_OUT_X = 0.80


def scale(unit: float) -> dict:
    """刻度上的关键位置。"""
    x0 = unit * TRACK_X
    return {
        "x0": x0,
        "unit": unit,
        "serial_end": x0 + unit,
        "range_x": x0 + unit * RANGE_LOW,
        "range_end": x0 + unit * RANGE_HIGH,
    }


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s05")
    text(ctx, p["title"], w * 0.06, h * 0.14, 56, COLORS["primary"], bold=True)

    unit = w * UNIT_W
    s = scale(unit)

    # 串行：一条整条，1 倍
    text(ctx, p["serial_label"], s["x0"], h * SERIAL_LABEL_Y, 34, COLORS["primary"])
    rounded_rect(ctx, s["x0"], h * SERIAL_Y, unit, h * BAR_H, 10, "#DCE1E8")
    grow = easing.ease_out_cubic(max(0.0, min(1.0, t * 2.0)))
    rounded_rect(ctx, s["x0"], h * SERIAL_Y, unit * grow, h * BAR_H, 10,
                 COLORS["primary"])

    # 并行：一段区间（2 倍到 5 倍）
    text(ctx, p["parallel_label"], s["x0"], h * PARALLEL_LABEL_Y, 34,
         COLORS["primary"])
    band_w = s["range_end"] - s["range_x"]
    rounded_rect(ctx, s["range_x"], h * PARALLEL_Y, band_w, h * BAR_H, 10,
                 COLORS["secondary"], alpha=0.28)
    grow2 = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.15) * 2.0)))
    rounded_rect(ctx, s["range_x"], h * PARALLEL_Y, band_w * grow2, h * BAR_H, 10,
                 COLORS["secondary"], alpha=0.9)

    # 刻度轨道：两条共用一条，0 到 5 倍
    rounded_rect(ctx, s["x0"], h * TRACK_Y, unit * RANGE_HIGH, h * 0.012, 4,
                 "#E4E8EE")
    for value, x in ((1, s["serial_end"]), (RANGE_LOW, s["range_x"]),
                     (RANGE_HIGH, s["range_end"])):
        rounded_rect(ctx, x - 3, h * (TRACK_Y - 0.012), 6, h * 0.036, 3,
                     COLORS["primary"])
        text(ctx, f"{value} 倍", x, h * TICK_Y, 28, COLORS["primary"],
             anchor="center")

    # 右侧强调数字：数字落在句子末尾，得在场景结束前完全显出来
    scale_in = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.15) * 2.5)))
    text(ctx, p["callout"], w * CALL_OUT_X, h * 0.44, 132, COLORS["accent"],
         anchor="center", bold=True, alpha=scale_in)
    text(ctx, p["callout_sub"], w * CALL_OUT_X, h * 0.56, 36, COLORS["primary"],
         anchor="center", alpha=scale_in)

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])
