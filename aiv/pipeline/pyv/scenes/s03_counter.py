"""段 C：原子计数器发号模板。

左边一个原子计数器方块，右边三个事务依次来取号，拿到的是递增的号。
计数器上的数字跟着取号逐次往上跳——「自增一号就归你」这句就是这块方块。

版式在代码里，**这一期的计数器名、事务编号与发出的号在契约里**（`Scene.params`）。

**竖版（1080×1920）**：横版是「左计数器 + 右事务」左右分栏，竖版改成
上下堆叠——计数器铺满宽度放在上面，三笔取号排在下面：
一条竖线从计数器引下来，每笔取号从竖线上分出一支箭头指进自己的芯片
（见 `pyv/scene_layout.py` 的三条规矩）。
"""
from __future__ import annotations

from pyv import easing
from pyv import scene_layout
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
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return

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


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：计数器在上，三笔取号在下。

    横版是「计数器 → 箭头 → 事务芯片 → 号」一条横线；竖版把这条
    横线拆成上下两段：计数器铺满宽度放上面，从计数器引一条竖线下来，
    每笔取号从竖线上分出一支箭头指进自己的芯片，号右对齐排在芯片那一行
    的右边（键值行：左边事务、右边号）。
    """
    ids = [str(x) for x in p["txn_ids"]]
    values = csn_sequence(p.as_dict())
    readings = counter_reading(p.as_dict())

    left = scene_layout.content_left(w)
    full_w = scene_layout.content_width(w)
    center = left + full_w / 2

    scene_layout.title(ctx, p["title"], w, h)

    # ---- 原子计数器 ----
    box_y = scene_layout.content_top(h)
    box_h = 380
    rounded_rect(ctx, left, box_y, full_w, box_h, 18, COLORS["primary"])
    scene_layout.line(ctx, p["counter_label"], center, box_y + 72,
                      full_w - 60, 42, "#FFFFFF", bold=True, anchor="center")
    scene_layout.line(ctx, p["counter_sub"], center, box_y + 130,
                      full_w - 60, 32, COLORS["secondary"], anchor="center")
    scene_layout.line(ctx, p["counter_bits"], center, box_y + 340,
                      full_w - 60, 32, COLORS["secondary"], anchor="center")

    # 计数器当前读数：谁取到了号，读数就跳到那个号
    issued = 0
    for index in range(len(ids)):
        if t >= CLAIM_STEP * index:
            issued = index + 1
    reading = readings[issued]
    bump = easing.ease_out_cubic(
        max(0.0, min(1.0, (t - CLAIM_STEP * (issued - 1)) * 6.0))) if issued else 1.0
    scene_layout.line(ctx, reading, center, box_y + 250, full_w - 60, 88,
                      COLORS["accent"], bold=True, alpha=0.6 + 0.4 * bump,
                      anchor="center")

    # ---- 三笔取号 ----
    spine_x = left + 80
    chip_x = left + 210
    chip_w, chip_h = 250, 90
    rows = [690 + index * 175 for index in range(len(ids))]

    for index, (txn_id, value) in enumerate(zip(ids, values)):
        chip_y = rows[index]
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - CLAIM_STEP * index) * 2.6)))
        # 竖线是一段一段长出来的：还没出现的取号，竖线也不该垂在那儿。
        branch_y = chip_y + chip_h / 2
        spine_top = rows[index - 1] + chip_h / 2 if index else box_y + box_h
        rounded_rect(ctx, spine_x - 3, spine_top, 6,
                     max(0.0, branch_y - spine_top), 3, COLORS["primary"],
                     alpha=appear)
        arrow(ctx, spine_x, branch_y, chip_x, branch_y,
              COLORS["primary"], 5, 16, alpha=appear)
        rounded_rect(ctx, chip_x, chip_y, chip_w, chip_h, 12,
                     COLORS["secondary"], alpha=appear)
        scene_layout.line(ctx, txn_id, chip_x + chip_w / 2, chip_y + 58,
                          chip_w - 30, 38, "#FFFFFF", bold=True,
                          alpha=appear, anchor="center")
        # 号右对齐到内容区右沿：这一行读起来是「事务 → 号」的键值行，
        # 右对齐才不会在右边留一条空白。
        scene_layout.line(ctx, f"{p['csn_prefix']} {value}", left + full_w - 4,
                          chip_y + 58, 460, 46, COLORS["accent"],
                          bold=True, alpha=appear, anchor="right")

    scene_layout.caption(ctx, p["caption"], w, h)
