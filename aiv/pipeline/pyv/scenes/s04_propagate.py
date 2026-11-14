"""段 D：传播链模板。

四个节点从左到右排开，用箭头连成一条链路，讲的是「同一个号一路带过去」。
每个节点写什么，在契约里（`Scene.params`）；版式在代码里。

**竖版（1080×1920）**：横版是「四个并排」，竖版改成「四个从上往下排」。
竖版只有 1080 宽，四个并排每块只剩 200 宽，日志类的长标签放不下；
竖版里每个节点占满一整行，箭头竖着往下指（见 `pyv/scene_layout.py` 的三条规矩）。
"""
from __future__ import annotations

from pyv import easing
from pyv import scene_layout
from pyv.draw import arrow, rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "csn_label", "wal_label", "wal_sub", "begin_label",
            "begin_sub", "subscriber_label", "caption")

# 版式常量：节点宽度、间隙、起始位置
NODE_W = 0.185
NODE_GAP = 0.055
NODE_LEFT = 0.05

# 竖版：节点竖着排，宽度占满内容区
V_NODE_H_RATIO = 0.094      # 节点高（相对画面高度）
V_NODE_GAP_RATIO = 0.042    # 节点之间的间隙（相对画面高度）


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s04")
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return

    text(ctx, p["title"], w * 0.06, h * 0.14, 58, COLORS["primary"], bold=True)

    node_w = w * NODE_W
    gap = w * NODE_GAP
    left = w * NODE_LEFT
    top = h * 0.29
    node_h = h * 0.32

    # (标签, 副标题, 底色, 字色, 字号)
    nodes = (
        (p["csn_label"], None, COLORS["accent"], "#FFFFFF", 62),
        (p["wal_label"], p["wal_sub"], COLORS["primary"], "#FFFFFF", 40),
        (p["begin_label"], p["begin_sub"], COLORS["secondary"], "#FFFFFF", 40),
        (p["subscriber_label"], None, "#DCE1E8", COLORS["primary"], 42),
    )

    for index, (label, sub, fill, fg, size) in enumerate(nodes):
        x = left + index * (node_w + gap)
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.12 * index) * 2.4)))
        rounded_rect(ctx, x, top, node_w, node_h, 16, fill, alpha=appear)
        if sub:
            text(ctx, label, x + node_w / 2, top + node_h * 0.44, size, fg,
                 anchor="center", bold=True, alpha=appear)
            text(ctx, sub, x + node_w / 2, top + node_h * 0.75, 28, fg,
                 anchor="center", alpha=appear)
        else:
            text(ctx, label, x + node_w / 2, top + node_h * 0.60, size, fg,
                 anchor="center", bold=True, alpha=appear)
        if index < len(nodes) - 1:
            arrow(ctx, x + node_w + 10, top + node_h / 2,
                  x + node_w + gap - 10, top + node_h / 2,
                  COLORS["primary"], 6, 18, alpha=appear)

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：四个节点从上往下串成一条竖链。

    **字号不缩、框变宽**：节点占满内容区宽 950，字号跟横版同档，
    竖着排之后每个节点都有一整行，日志类的长标签放得下。
    """
    left = w * scene_layout.MARGIN_X
    width = w * scene_layout.CONTENT_W
    center = left + width / 2

    scene_layout.title(ctx, p["title"], w, h)

    node_h = h * V_NODE_H_RATIO
    gap = h * V_NODE_GAP_RATIO
    nodes = (
        (p["csn_label"], None, COLORS["accent"], "#FFFFFF", 62),
        (p["wal_label"], p["wal_sub"], COLORS["primary"], "#FFFFFF", 40),
        (p["begin_label"], p["begin_sub"], COLORS["secondary"], "#FFFFFF", 40),
        (p["subscriber_label"], None, "#DCE1E8", COLORS["primary"], 42),
    )
    total = len(nodes) * node_h + (len(nodes) - 1) * gap
    top = h * scene_layout.CONTENT_TOP
    bottom = h * scene_layout.CONTENT_BOTTOM
    y0 = top + (bottom - top - total) / 2

    for index, (label, sub, fill, fg, size) in enumerate(nodes):
        node_y = y0 + index * (node_h + gap)
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.12 * index) * 2.4))
        )
        rounded_rect(ctx, left, node_y, width, node_h, 16, fill, alpha=appear)
        if sub:
            scene_layout.line(ctx, label, center, node_y + node_h * 0.44,
                              width * 0.9, size, fg, bold=True, alpha=appear,
                              anchor="center")
            scene_layout.line(ctx, sub, center, node_y + node_h * 0.75,
                              width * 0.9, 28, fg, alpha=appear, anchor="center")
        else:
            scene_layout.line(ctx, label, center, node_y + node_h * 0.60,
                              width * 0.9, size, fg, bold=True, alpha=appear,
                              anchor="center")
        if index < len(nodes) - 1:
            arrow(ctx, center, node_y + node_h + h * 0.008,
                  center, node_y + node_h + gap - h * 0.008,
                  COLORS["primary"], 6, 18, alpha=appear)

    scene_layout.caption(ctx, p["caption"], w, h)
