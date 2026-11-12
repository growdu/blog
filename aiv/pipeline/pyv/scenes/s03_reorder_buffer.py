"""段 C：按事务号归并的槽位模板。

上面三行是三个事务各自的槽。每读一条 WAL 记录，就按它带的事务号
落进对应那一行——记录被别的行隔开也不影响，因为槽是按号分的。

版式在代码里，**这一期的槽、事务编号与文案在契约里**（`Scene.params`）。
"""
from __future__ import annotations

from pyv import easing
from pyv.draw import rounded_rect, stroke_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "buffer_label", "txn_ids", "txn_xids", "xid_prefix",
            "records", "slot_label", "caption")

# 每个事务一个颜色：槽、落进去的记录、事务号标签用同一个颜色。
MARKER_COLORS = ("#F6AD55", "#4FD1C5", "#8FAADC")

# 第 i 条记录在场景进度上的落槽时刻
RECORD_STEP = 0.10
RECORD_DELAY = 0.10

# 槽内一块记录芯片的宽度与间距
CHIP_W_RATIO = 0.062
CHIP_GAP_RATIO = 0.008


def slot_index(txn_ids: list[str], txn_id: str) -> int:
    """某个事务落在第几个槽。找不到时返回 -1。"""
    try:
        return txn_ids.index(txn_id)
    except ValueError:
        return -1


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s03")
    txn_ids = [str(x) for x in p["txn_ids"]]
    xids = [str(x) for x in p["txn_xids"]]
    # 每条记录是 [位置, 事务, 操作]
    records = [(str(row[0]), str(row[1]), str(row[2])) for row in p["records"]]

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    # ---- 槽位区 ----
    left = w * 0.06
    right = w * 0.94
    row_top = h * 0.30
    row_h = h * 0.145
    row_gap = h * 0.055
    chip_w = w * CHIP_W_RATIO
    chip_gap = w * CHIP_GAP_RATIO
    label_w = w * 0.15

    text(ctx, p["buffer_label"], left, h * 0.235, 36, COLORS["accent"], bold=True)
    text(ctx, p["slot_label"], left + w * 0.16, h * 0.235, 32, COLORS["secondary"])

    for index, txn_id in enumerate(txn_ids):
        color = MARKER_COLORS[index % len(MARKER_COLORS)]
        y = row_top + index * (row_h + row_gap)
        rounded_rect(ctx, left, y, right - left, row_h, 14, "#F2F5F9")
        stroke_rect(ctx, left, y, right - left, row_h, 14, "#DCE1E8", 3, 0.9)

        # 槽头：事务编号 + 事务号
        rounded_rect(ctx, left + w * 0.015, y + row_h * 0.26, w * 0.055,
                     row_h * 0.48, 9, color)
        text(ctx, txn_id, left + w * 0.0425, y + row_h * 0.60, 34, "#FFFFFF",
             anchor="center", bold=True)
        text(ctx, f"{p['xid_prefix']} {xids[index]}", left + w * 0.082,
             y + row_h * 0.60, 32, COLORS["primary"], bold=True)

    # ---- 记录按事务号落进各自的槽 ----
    for index, (position, txn_id, op) in enumerate(records):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - RECORD_DELAY - RECORD_STEP * index) * 5.0))
        )
        slot = slot_index(txn_ids, txn_id)
        if slot < 0:
            continue
        color = MARKER_COLORS[slot % len(MARKER_COLORS)]
        y = row_top + slot * (row_h + row_gap)

        # 同一个事务的第几条记录
        order = sum(
            1 for prev in records[:index]
            if prev[1] == txn_id
        )
        x = left + label_w + order * (chip_w + chip_gap)
        chip_y = y + row_h * 0.26
        chip_h = row_h * 0.48
        rounded_rect(ctx, x, chip_y, chip_w, chip_h, 9, color, alpha=appear)
        text(ctx, op, x + chip_w / 2, chip_y + chip_h * 0.70, 28, "#FFFFFF",
             anchor="center", bold=True, alpha=appear)

    text(ctx, p["caption"], w * 0.07, h * 0.90, 44, COLORS["primary"])
