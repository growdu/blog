"""段 D：传播链模板。

四个节点从左到右排开，用箭头连成一条链路，讲的是「同一个号一路带过去」。
每个节点写什么，在契约里（`Scene.params`）；版式在代码里。
"""
from __future__ import annotations

from pyv import easing
from pyv.draw import arrow, rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "csn_label", "wal_label", "wal_sub", "begin_label",
            "begin_sub", "subscriber_label", "caption")

# 版式常量：节点宽度、间隙、起始位置
NODE_W = 0.185
NODE_GAP = 0.055
NODE_LEFT = 0.05


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s04")
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
