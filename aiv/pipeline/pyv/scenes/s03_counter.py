"""段 C：原子计数器发号模板。

左边一个原子计数器方块，右边三个事务依次来取号，拿到的是递增的号。
计数器上的数字跟着取号逐次往上跳——「自增一号就归你」这句就是这块方块。

版式在代码里，**这一期的计数器名、事务编号与发出的号在契约里**（`Scene.params`）。
"""
from __future__ import annotations

from pyv import easing
from pyv.draw import arrow, rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "counter_label", "counter_sub", "counter_bits",
            "counter_value", "txn_ids", "csn_values", "csn_prefix", "caption")

# 取号的间隔（场景进度）：每间隔这么多，进度就多发一个号
CLAIM_STEP = 0.15


def csn_sequence(params=None) -> list[str]:
    """发出去的号，必须严格递增。"""
    p = Params(params, "s03")
    return [str(x) for x in p["csn_values"]]


def counter_reading(params=None) -> list[str]:
    """计数器上依次会显示的数：起始值，加上每发一个号之后的新值。

    索引 0 是起始值，索引 i+1 是第 i 个号发出去之后的读数。
    """
    p = Params(params, "s03")
    return [str(p["counter_value"])] + csn_sequence(params)


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s03")
    ids = [str(x) for x in p["txn_ids"]]
    values = csn_sequence(params)
    readings = counter_reading(params)

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    # ---- 原子计数器 ----
    box_x, box_y = w * 0.06, h * 0.255
    box_w, box_h = w * 0.28, h * 0.44
    rounded_rect(ctx, box_x, box_y, box_w, box_h, 18, COLORS["primary"])
    text(ctx, p["counter_label"], box_x + box_w / 2, box_y + h * 0.105, 42,
         "#FFFFFF", anchor="center", bold=True)
    text(ctx, p["counter_sub"], box_x + box_w / 2, box_y + h * 0.165, 32,
         COLORS["secondary"], anchor="center")
    text(ctx, p["counter_bits"], box_x + box_w / 2, box_y + box_h * 0.90, 34,
         COLORS["secondary"], anchor="center")

    # 计数器当前读数：谁取到了号，读数就跳到那个号
    issued = 0
    for index in range(len(ids)):
        if t >= CLAIM_STEP * index:
            issued = index + 1
    reading = readings[issued]
    bump = easing.ease_out_cubic(
        max(0.0, min(1.0, (t - CLAIM_STEP * (issued - 1)) * 6.0))) if issued else 1.0
    text(ctx, reading, box_x + box_w / 2, box_y + h * 0.30, 74,
         COLORS["accent"], anchor="center", bold=True, alpha=0.6 + 0.4 * bump)

    # ---- 三个事务依次取号 ----
    for index, (txn_id, value) in enumerate(zip(ids, values)):
        y = h * (0.295 + index * 0.135)
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - CLAIM_STEP * index) * 2.6)))
        rounded_rect(ctx, w * 0.44, y, w * 0.135, h * 0.088, 12,
                     COLORS["secondary"], alpha=appear)
        text(ctx, txn_id, w * 0.5075, y + h * 0.059, 38, "#FFFFFF",
             anchor="center", bold=True, alpha=appear)
        arrow(ctx, w * 0.375, y + h * 0.044, w * 0.432, y + h * 0.044,
              COLORS["primary"], 5, 16, alpha=appear)
        text(ctx, f"{p['csn_prefix']} {value}", w * 0.605, y + h * 0.063, 46,
             COLORS["accent"], bold=True, alpha=appear)

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])
