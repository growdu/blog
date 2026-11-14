"""段 D：4×4 的兼容性矩阵。

左边一列是手里已经拿着的锁，上面一排是现在想申请的那一种，
交叉的那一格就是答案：不打架就放行，打架就排队。

格子用颜色和符号区分，不靠文字——四个字塞进一格会看不清。

版式在代码里，**这一期的模式名、矩阵取值与文案在契约里**（`Scene.params`）。

**竖版（1080×1920）**：矩阵的结构不变，还是「左边一列 + 上面一排」，
只是把左边那一列压窄：竖版只有 1080 宽，四列格子只能各占 165 宽。
格子用颜色和符号区分，不靠文字，所以格子窄一点不影响可读性
（见 `pyv/scene_layout.py` 的三条规矩）。
"""
from __future__ import annotations

import math

import cairo

from pyv import easing
from pyv import scene_layout
from pyv.draw import rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "row_axis_label", "col_axis_label", "mode_labels",
            "matrix", "compatible_label", "conflict_label", "legend_label",
            "caption")

# 两格的颜色：放行 / 排队
OK_FILL, OK_MARK = "#E3F7F4", "#2FB8A8"
BAD_FILL, BAD_MARK = "#FDEBD0", "#E07B22"

# 版式常量
LABEL_COL_X_RATIO, LABEL_COL_W_RATIO = 0.06, 0.19
CELL_X_RATIO, CELL_W_RATIO = 0.27, 0.16
CELL_GAP_RATIO = 0.008
CELL_Y_RATIO, CELL_H_RATIO, CELL_STEP_RATIO = 0.335, 0.082, 0.092
HEADER_Y_RATIO = 0.275
AXIS_Y_RATIO = 0.225
LEGEND_Y_RATIO = 0.775

# 竖版：矩阵的版式常量（比例相对画面高度；宽度相对内容区宽度）
V_AXIS_Y_RATIO = 0.133       # 两个轴说明的基线
V_HEADER_Y_RATIO = 0.159     # 上面一排的第一行基线
V_HEADER_STEP_RATIO = 0.020  # 上面一排的行距
V_CELL_TOP_RATIO = 0.196     # 矩阵第一行的上沿
V_CELL_H_RATIO = 0.073       # 格子高
V_CELL_STEP_RATIO = 0.102    # 格子之间的行距
V_CELL_LEFT_RATIO = 0.268    # 矩阵左沿（相对内容区宽度）
V_CELL_GAP_RATIO = 0.013     # 格子之间的列距（相对内容区宽度）
V_LABEL_RIGHT_RATIO = 0.248  # 左边一列标签的右沿（相对内容区宽度）
V_LEGEND_Y_RATIO = 0.615     # 图例的基线


def _draw_dot(ctx, cx: float, cy: float, radius: float, alpha: float) -> None:
    """放行那一格：画一个实心圆点。"""
    ctx.save()
    ctx.set_source_rgba(*_rgb(OK_MARK), alpha)
    ctx.arc(cx, cy, radius, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()


def _draw_cross(ctx, cx: float, cy: float, radius: float, alpha: float) -> None:
    """排队那一格：画一个叉。用线条画，不依赖字体里有没有这个符号。"""
    ctx.save()
    ctx.set_source_rgba(*_rgb(BAD_MARK), alpha)
    ctx.set_line_width(6)
    ctx.move_to(cx - radius, cy - radius)
    ctx.line_to(cx + radius, cy + radius)
    ctx.move_to(cx + radius, cy - radius)
    ctx.line_to(cx - radius, cy + radius)
    ctx.stroke()
    ctx.restore()


def _rgb(value: str) -> tuple[float, float, float]:
    from pyv.palette import hex_to_rgb
    return hex_to_rgb(value)


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s04")
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return

    labels = [[str(line) for line in item] for item in p["mode_labels"]]
    matrix = p["matrix"]

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    # ---- 两个轴的说明 ----
    text(ctx, p["row_axis_label"], w * LABEL_COL_X_RATIO, h * AXIS_Y_RATIO, 30,
         COLORS["secondary"], bold=True)
    text(ctx, p["col_axis_label"], w * 0.605, h * AXIS_Y_RATIO, 30,
         COLORS["primary"], anchor="center", bold=True)

    # ---- 上面一排：想申请哪种锁 ----
    cell_w = w * CELL_W_RATIO
    gap = w * CELL_GAP_RATIO
    for index, lines in enumerate(labels[:4]):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.10 - index * 0.05) * 3.2))
        )
        cx = w * CELL_X_RATIO + index * (cell_w + gap) + cell_w / 2
        base = h * HEADER_Y_RATIO
        for line_index, line in enumerate(lines[:2]):
            text(ctx, line, cx, base + line_index * h * 0.032, 26,
                 COLORS["primary"], anchor="center", bold=True, alpha=appear)

    # ---- 左边一列：手里已经有的锁 ----
    row_y0 = h * CELL_Y_RATIO
    step = h * CELL_STEP_RATIO
    cell_h = h * CELL_H_RATIO
    for index, lines in enumerate(labels[:4]):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.10 - index * 0.05) * 3.2))
        )
        cy = row_y0 + index * step + cell_h / 2
        # 标签可能有两行（「KEY SHARE」拆成两行才放得下），
        # 只画第一行会把它读成「KEY」。
        if len(lines) > 1:
            offsets = (-h * 0.019, h * 0.019)
        else:
            offsets = (0.0,)
        for line_index, line in enumerate(lines[:2]):
            text(ctx, line, w * (LABEL_COL_X_RATIO + LABEL_COL_W_RATIO),
                 cy + offsets[line_index], 28, COLORS["primary"],
                 anchor="right", bold=True, alpha=appear)

    # ---- 矩阵本体 ----
    for row in range(4):
        for col in range(4):
            appear = easing.ease_out_cubic(
                max(0.0, min(1.0, (t - 0.22 - (row * 4 + col) * 0.022) * 3.2))
            )
            x = w * CELL_X_RATIO + col * (cell_w + gap)
            y = row_y0 + row * step
            ok = bool(matrix[row][col])
            rounded_rect(ctx, x, y, cell_w, cell_h, 10,
                         OK_FILL if ok else BAD_FILL, alpha=appear)
            cx, cy = x + cell_w / 2, y + cell_h / 2
            if ok:
                _draw_dot(ctx, cx, cy, cell_h * 0.16, appear)
            else:
                _draw_cross(ctx, cx, cy, cell_h * 0.16, appear)

    # ---- 图例 ----
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.62) * 3.0)))
    ly = h * LEGEND_Y_RATIO
    swatch = h * 0.035
    rounded_rect(ctx, w * 0.06, ly - swatch, swatch, swatch, 5, OK_FILL,
                 alpha=appear)
    _draw_dot(ctx, w * 0.06 + swatch / 2, ly - swatch / 2, swatch * 0.16, appear)
    text(ctx, p["compatible_label"], w * 0.06 + swatch + w * 0.012, ly, 30,
         COLORS["primary"], alpha=appear)

    x2 = w * 0.06 + swatch + w * 0.012 + w * 0.075
    rounded_rect(ctx, x2, ly - swatch, swatch, swatch, 5, BAD_FILL, alpha=appear)
    _draw_cross(ctx, x2 + swatch / 2, ly - swatch / 2, swatch * 0.16, appear)
    text(ctx, p["conflict_label"], x2 + swatch + w * 0.012, ly, 30,
         COLORS["primary"], alpha=appear)

    text(ctx, p["legend_label"], x2 + swatch + w * 0.012 + w * 0.075, ly, 30,
         COLORS["secondary"], alpha=appear)

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：矩阵还是「左边一列 + 上面一排」，只是整体压窄。

    **字号不缩、框变宽**：上面一排与左边一列的标签字号比横版还大
    （26/28，横版也是这一档），格子虽然只有 165 宽，但格子用颜色和
    符号区分、不靠文字，所以窄格子照样看得懂。
    """
    labels = [[str(line) for line in item] for item in p["mode_labels"]]
    matrix = p["matrix"]

    left = w * scene_layout.MARGIN_X
    width = w * scene_layout.CONTENT_W
    right = left + width

    scene_layout.title(ctx, p["title"], w, h)

    # ---- 矩阵本体：四列等分内容区右边，左边留给「已经持有」那一列 ----
    cell_left = left + width * V_CELL_LEFT_RATIO
    gap = width * V_CELL_GAP_RATIO
    cell_w = (right - cell_left - 3 * gap) / 4
    cell_h = h * V_CELL_H_RATIO
    cell_top = h * V_CELL_TOP_RATIO
    step = h * V_CELL_STEP_RATIO
    centers = [cell_left + col * (cell_w + gap) + cell_w / 2 for col in range(4)]

    # ---- 两个轴的说明 ----
    axis_y = h * V_AXIS_Y_RATIO
    scene_layout.line(ctx, p["row_axis_label"], left, axis_y, width * 0.20, 28,
                      COLORS["secondary"], bold=True)
    scene_layout.line(ctx, p["col_axis_label"], (cell_left + right) / 2, axis_y,
                      width * 0.40, 28, COLORS["primary"], bold=True,
                      anchor="center")

    # ---- 上面一排：想申请哪种锁 ----
    header_y = h * V_HEADER_Y_RATIO
    for index, lines in enumerate(labels[:4]):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.10 - index * 0.05) * 3.2))
        )
        for line_index, line in enumerate(lines[:2]):
            scene_layout.line(ctx, line, centers[index],
                              header_y + line_index * h * V_HEADER_STEP_RATIO,
                              cell_w, 26, COLORS["primary"], bold=True,
                              alpha=appear, anchor="center")

    # ---- 左边一列：手里已经有的锁 ----
    label_right = left + width * V_LABEL_RIGHT_RATIO
    for index, lines in enumerate(labels[:4]):
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.10 - index * 0.05) * 3.2))
        )
        cy = cell_top + index * step + cell_h / 2
        # 标签可能有两行（「KEY SHARE」拆成两行才放得下），
        # 只画第一行会把它读成「KEY」。
        if len(lines) > 1:
            offsets = (-cell_h * 0.15, cell_h * 0.15)
        else:
            offsets = (cell_h * 0.07,)
        for line_index, line in enumerate(lines[:2]):
            scene_layout.line(ctx, line, label_right, cy + offsets[line_index],
                              width * 0.22, 28, COLORS["primary"], bold=True,
                              alpha=appear, anchor="right")

    # ---- 矩阵本体 ----
    for row in range(4):
        for col in range(4):
            appear = easing.ease_out_cubic(
                max(0.0, min(1.0, (t - 0.22 - (row * 4 + col) * 0.022) * 3.2))
            )
            x = cell_left + col * (cell_w + gap)
            y = cell_top + row * step
            ok = bool(matrix[row][col])
            rounded_rect(ctx, x, y, cell_w, cell_h, 10,
                         OK_FILL if ok else BAD_FILL, alpha=appear)
            cx, cy = x + cell_w / 2, y + cell_h / 2
            if ok:
                _draw_dot(ctx, cx, cy, cell_h * 0.16, appear)
            else:
                _draw_cross(ctx, cx, cy, cell_h * 0.16, appear)

    # ---- 图例 ----
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.62) * 3.0)))
    ly = h * V_LEGEND_Y_RATIO
    swatch = cell_h * 0.29
    rounded_rect(ctx, left, ly - swatch, swatch, swatch, 5, OK_FILL,
                 alpha=appear)
    _draw_dot(ctx, left + swatch / 2, ly - swatch / 2, swatch * 0.16, appear)
    scene_layout.line(ctx, p["compatible_label"], left + swatch + width * 0.014,
                      ly, width * 0.12, 30, COLORS["primary"], alpha=appear)

    x2 = left + swatch + width * 0.014 + width * 0.085
    rounded_rect(ctx, x2, ly - swatch, swatch, swatch, 5, BAD_FILL, alpha=appear)
    _draw_cross(ctx, x2 + swatch / 2, ly - swatch / 2, swatch * 0.16, appear)
    scene_layout.line(ctx, p["conflict_label"], x2 + swatch + width * 0.014, ly,
                      width * 0.12, 30, COLORS["primary"], alpha=appear)

    x3 = x2 + swatch + width * 0.014 + width * 0.085
    scene_layout.line(ctx, p["legend_label"], x3, ly, width * 0.45, 30,
                      COLORS["secondary"], alpha=appear)

    scene_layout.caption(ctx, p["caption"], w, h)
