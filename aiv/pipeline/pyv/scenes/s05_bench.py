"""段 E：压测数字模板。

左边两条吞吐条（串行一条整条，并行一段区间），右边一个强调数字。
版式在代码里，**这一期的标签与数字在契约里**（`Scene.params`）。

**竖版（1080×1920）**：横版是「左边两条条 + 右边一个数字」，竖版只有
1080 宽，左右分栏会把每条条压到一半宽、数字也会掉出框——所以改成
「上下堆叠」：强调数字在上，两条条与刻度轨道在下
（见 `pyv/scene_layout.py` 的三条规矩）。
"""
from __future__ import annotations

from pyv import easing
from pyv import scene_layout
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
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return
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


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：标题 → 强调数字 → 串行条 → 并行条 → 刻度轨道。

    横版把两条条放左边、数字放右边；竖版只有 1080 宽，左右分栏会让
    每条条只剩一半宽，数字也会掉出框。所以改成上下堆叠：

    - **字号不缩、框变宽**：强调数字仍是 132，两条条撑满内容区宽度
      （0 倍到 5 倍铺满 0.88w），标签比横版还大一号。
    - **字要放得下**：每一行字都过 `scene_layout.line`，放不下就收字号。
    """
    left = w * scene_layout.MARGIN_X
    max_width = w * scene_layout.CONTENT_W

    scene_layout.title(ctx, p["title"], w, h, size=60)

    # 强调数字：横版在右边，竖版挪到标题下面当主角。
    # 放在一张卡片里：卡片撑满内容区宽度，右半边不留白。
    hero_y = h * 0.140
    hero_h = h * 0.140
    rounded_rect(ctx, left, hero_y, max_width, hero_h, 16, "#F2F5F9")
    scale_in = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.15) * 2.5)))
    scene_layout.line(ctx, p["callout"], left + w * 0.030, hero_y + h * 0.075,
                      max_width - w * 0.060, 132, COLORS["accent"], bold=True,
                      alpha=scale_in)
    scene_layout.line(ctx, p["callout_sub"], left + w * 0.030,
                      hero_y + h * 0.118, max_width - w * 0.060, 40,
                      COLORS["primary"], alpha=scale_in)

    # 刻度：0 到 5 倍铺满内容区宽度，1 倍占五分之一
    unit = max_width / RANGE_HIGH
    serial_end = left + unit
    range_x = left + unit * RANGE_LOW
    range_end = left + unit * RANGE_HIGH

    # 串行：一条整条，1 倍
    scene_layout.line(ctx, p["serial_label"], left, h * 0.320, max_width, 40,
                      COLORS["primary"])
    rounded_rect(ctx, left, h * 0.337, unit, h * 0.065, 10, "#DCE1E8")
    grow = easing.ease_out_cubic(max(0.0, min(1.0, t * 2.0)))
    rounded_rect(ctx, left, h * 0.337, unit * grow, h * 0.065, 10,
                 COLORS["primary"])

    # 并行：一段区间（2 倍到 5 倍）
    scene_layout.line(ctx, p["parallel_label"], left, h * 0.430, max_width, 40,
                      COLORS["primary"])
    band_w = range_end - range_x
    rounded_rect(ctx, range_x, h * 0.447, band_w, h * 0.065, 10,
                 COLORS["secondary"], alpha=0.28)
    grow2 = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.15) * 2.0)))
    rounded_rect(ctx, range_x, h * 0.447, band_w * grow2, h * 0.065, 10,
                 COLORS["secondary"], alpha=0.9)

    # 刻度轨道：两条共用一条，0 到 5 倍
    rounded_rect(ctx, left, h * 0.525, max_width, h * 0.008, 4, "#E4E8EE")
    for value, x in ((1, serial_end), (RANGE_LOW, range_x),
                     (RANGE_HIGH, range_end)):
        rounded_rect(ctx, x - 3, h * 0.513, 6, h * 0.036, 3, COLORS["primary"])
        scene_layout.line(ctx, f"{value} 倍", x, h * 0.588, max_width, 36,
                          COLORS["primary"], anchor="center")

    scene_layout.caption(ctx, p["caption"], w, h)
