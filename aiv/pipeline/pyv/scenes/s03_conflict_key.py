"""段 C：判断依据模板。

左边一张表，两条事务都改了同一行。右边把这个判断依据摊开：
表、索引、键值——三者一样就是撞上了，撞上了就不能一起做。
（三个要素的名称由契约给出，这里不写死。）

版式在代码里，**这一期的表名、行号与文案在契约里**（`Scene.params`）。

**竖版（1080×1920）**：横版是「左表 + 右键」左右分栏，竖版改成
「上表 + 下键」上下堆叠——表铺满宽度放在上面，两条事务的芯片排在
表里、箭头向上指进被撞上的那一行，判定面板铺满宽度放在下面
（见 `pyv/scene_layout.py` 的三条规矩）。
"""
from __future__ import annotations

from pyv import easing
from pyv import scene_layout
from pyv.draw import arrow, rounded_rect, stroke_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "table_label", "row_labels", "hot_index", "key_title",
            "key_parts", "key_values", "key_conclusion", "txn_a", "txn_b",
            "conflict_label", "caption")

# 两条事务的颜色
TXN_COLORS = ("#F6AD55", "#4FD1C5")


def hot_row(row_labels: list[str], hot_index: int) -> str:
    """被撞上的那一行是哪个。"""
    if 0 <= hot_index < len(row_labels):
        return row_labels[hot_index]
    return row_labels[0]


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s03")
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return

    row_labels = [str(x) for x in p["row_labels"]]
    hot_index = int(p["hot_index"])
    parts = [str(x) for x in p["key_parts"]]
    values = [str(x) for x in p["key_values"]]

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    # ---- 左边的表 ----
    tbl_x, tbl_y = w * 0.07, h * 0.27
    tbl_w, tbl_h = w * 0.38, h * 0.30
    rounded_rect(ctx, tbl_x, tbl_y, tbl_w, tbl_h, 14, "#F2F5F9")
    stroke_rect(ctx, tbl_x, tbl_y, tbl_w, tbl_h, 14, "#DCE1E8", 3, 0.9)
    text(ctx, p["table_label"], tbl_x + w * 0.02, tbl_y + h * 0.06, 36,
         COLORS["primary"], bold=True)

    row_h = h * 0.062
    hot_y = tbl_y + h * 0.095 + hot_index * (row_h + h * 0.018) + row_h / 2
    for index, label in enumerate(row_labels):
        row_y = tbl_y + h * 0.095 + index * (row_h + h * 0.018)
        hot = index == hot_index
        rounded_rect(ctx, tbl_x + w * 0.018, row_y, tbl_w - w * 0.036, row_h, 8,
                     COLORS["problem"] if hot else "#FFFFFF",
                     alpha=1.0 if hot else 0.8)
        text(ctx, label, tbl_x + w * 0.038, row_y + row_h * 0.70, 30,
             "#FFFFFF" if hot else COLORS["primary"], bold=hot)

    # 撞上的那行：两条事务都指向它
    for index, txn_id in enumerate((str(p["txn_a"]), str(p["txn_b"]))):
        chip_x = tbl_x + w * 0.02 + index * w * 0.18
        chip_y = h * 0.63
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.12 - index * 0.12) * 3.0))
        )
        rounded_rect(ctx, chip_x, chip_y, w * 0.14, h * 0.075, 10,
                     TXN_COLORS[index], alpha=appear)
        text(ctx, txn_id, chip_x + w * 0.07, chip_y + h * 0.052, 34, "#FFFFFF",
             anchor="center", bold=True, alpha=appear)
        arrow(ctx, chip_x + w * 0.07, chip_y - h * 0.008,
              tbl_x + tbl_w - w * 0.012, hot_y, TXN_COLORS[index], 5, 16,
              alpha=0.85 * appear)

    # ---- 右边的冲突键 ----
    key_x = w * 0.52
    key_y = h * 0.27
    key_w = w * 0.42
    key_h = h * 0.48
    rounded_rect(ctx, key_x, key_y, key_w, key_h, 16, COLORS["primary"])
    text(ctx, p["key_title"], key_x + w * 0.025, key_y + h * 0.075, 38,
         "#FFFFFF", bold=True)

    for index, (part, value) in enumerate(zip(parts, values)):
        row_y = key_y + h * 0.115 + index * h * 0.095
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.28 - index * 0.10) * 3.0))
        )
        rounded_rect(ctx, key_x + w * 0.025, row_y, w * 0.085, h * 0.065, 9,
                     COLORS["secondary"], alpha=appear)
        text(ctx, part, key_x + w * 0.0675, row_y + h * 0.044, 30, "#FFFFFF",
             anchor="center", bold=True, alpha=appear)
        text(ctx, value, key_x + w * 0.125, row_y + h * 0.045, 36,
             "#FFFFFF", bold=True, alpha=appear)

    # 结论
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.50) * 3.0)))
    text(ctx, p["key_conclusion"], key_x + w * 0.025, key_y + key_h - h * 0.045,
         32, COLORS["secondary"], alpha=appear)

    # ---- 冲突标记 ----
    badge_x = key_x + key_w - w * 0.115
    badge_y = key_y + h * 0.026
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.42) * 3.5)))
    rounded_rect(ctx, badge_x, badge_y, w * 0.09, h * 0.055, 9,
                 COLORS["problem"], alpha=appear)
    text(ctx, p["conflict_label"], badge_x + w * 0.045, badge_y + h * 0.038, 32,
         "#FFFFFF", anchor="center", bold=True, alpha=appear)

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：上表（两条事务指进同一行）→ 下判定面板。

    横版是左右分栏，竖版是上下堆叠：表铺满内容宽度放在上面，
    判定面板铺满内容宽度放在下面。两条事务的芯片排在表里
    （表里才有「指同一行」的上下文），箭头向上指进被撞上的那一行。
    """
    row_labels = [str(x) for x in p["row_labels"]]
    hot_index = int(p["hot_index"])
    parts = [str(x) for x in p["key_parts"]]
    values = [str(x) for x in p["key_values"]]

    left = scene_layout.content_left(w)
    full_w = scene_layout.content_width(w)

    scene_layout.title(ctx, p["title"], w, h)

    # ---- 表 ----
    tbl_y = scene_layout.content_top(h)
    tbl_h = 440
    rounded_rect(ctx, left, tbl_y, full_w, tbl_h, 14, "#F2F5F9")
    stroke_rect(ctx, left, tbl_y, full_w, tbl_h, 14, "#DCE1E8", 3, 0.9)
    scene_layout.line(ctx, p["table_label"], left + 30, tbl_y + 48,
                      full_w - 60, 36, COLORS["primary"], bold=True)

    row_h, row_gap = 64, 12
    rows_top = tbl_y + 100
    hot_y = rows_top + hot_index * (row_h + row_gap) + row_h
    for index, label in enumerate(row_labels):
        row_y = rows_top + index * (row_h + row_gap)
        hot = index == hot_index
        rounded_rect(ctx, left + 18, row_y, full_w - 36, row_h, 8,
                     COLORS["problem"] if hot else "#FFFFFF",
                     alpha=1.0 if hot else 0.8)
        scene_layout.line(ctx, label, left + 38, row_y + row_h * 0.72,
                          full_w - 76, 30,
                          "#FFFFFF" if hot else COLORS["primary"], bold=hot)

    # 撞上的那行：两条事务都指向它。芯片排在表里，箭头向上指。
    # 箭头指到那一行的**下沿**而不是中间——否则橙色的箭头会落在橙色的
    # 那一行上，箭头整个看不见。
    chip_w, chip_h = 240, 76
    chip_y = tbl_y + tbl_h - 88
    chip_x0 = left + (full_w - (chip_w * 2 + 50)) / 2
    for index, txn_id in enumerate((str(p["txn_a"]), str(p["txn_b"]))):
        chip_x = chip_x0 + index * (chip_w + 50)
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.12 - index * 0.12) * 3.0))
        )
        rounded_rect(ctx, chip_x, chip_y, chip_w, chip_h, 10,
                     TXN_COLORS[index], alpha=appear)
        scene_layout.line(ctx, txn_id, chip_x + chip_w / 2, chip_y + 52,
                          chip_w - 30, 36, "#FFFFFF", bold=True,
                          alpha=appear, anchor="center")
        arrow(ctx, chip_x + chip_w / 2, chip_y - 8,
              chip_x + chip_w / 2, hot_y, TXN_COLORS[index], 5, 16,
              alpha=0.85 * appear)

    # ---- 判定面板 ----
    key_y = 720
    key_h = scene_layout.content_bottom(h) - key_y
    rounded_rect(ctx, left, key_y, full_w, key_h, 16, COLORS["primary"])
    scene_layout.line(ctx, p["key_title"], left + 30, key_y + 72,
                      full_w - 240, 40, "#FFFFFF", bold=True)

    for index, (part, value) in enumerate(zip(parts, values)):
        row_y = key_y + 130 + index * 100
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.28 - index * 0.10) * 3.0))
        )
        rounded_rect(ctx, left + 30, row_y, 180, 64, 9, COLORS["secondary"],
                     alpha=appear)
        scene_layout.line(ctx, part, left + 120, row_y + 46, 160, 32,
                          "#FFFFFF", bold=True, alpha=appear, anchor="center")
        scene_layout.line(ctx, value, left + 240, row_y + 48, full_w - 270,
                          40, "#FFFFFF", bold=True, alpha=appear)

    # 结论
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.50) * 3.0)))
    scene_layout.line(ctx, p["key_conclusion"], left + 30, key_y + key_h - 58,
                      full_w - 60, 34, COLORS["secondary"], alpha=appear)

    # ---- 冲突标记 ----
    badge_w, badge_h = 150, 58
    badge_x = left + full_w - 30 - badge_w
    badge_y = key_y + 34
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.42) * 3.5)))
    rounded_rect(ctx, badge_x, badge_y, badge_w, badge_h, 9,
                 COLORS["problem"], alpha=appear)
    scene_layout.line(ctx, p["conflict_label"], badge_x + badge_w / 2,
                      badge_y + 40, badge_w - 20, 32, "#FFFFFF", bold=True,
                      alpha=appear, anchor="center")

    scene_layout.caption(ctx, p["caption"], w, h)
