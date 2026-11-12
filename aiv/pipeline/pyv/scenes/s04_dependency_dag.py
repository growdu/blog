"""段 D：依赖图模板。

一个窗口框住窗口内的几条事务，改了同一行的两条之间连一条边。
边画出来，谁必须排在谁前面就一目了然。

版式在代码里，**这一期的节点、说明与边在契约里**（`Scene.params`）。
"""
from __future__ import annotations

from pyv import easing
from pyv.draw import arrow, rounded_rect, stroke_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "window_label", "nodes", "node_notes", "edges", "caption")

# 节点配色：按列交替
NODE_COLORS = ("#F6AD55", "#F6AD55", "#4FD1C5", "#4FD1C5")


def node_positions(nodes: list[str], w: int, h: int) -> dict[str, tuple[float, float]]:
    """节点在窗口里的位置：两列两行。"""
    cols = (w * 0.15, w * 0.52)
    rows = (h * 0.34, h * 0.59)
    out: dict[str, tuple[float, float]] = {}
    for index, node in enumerate(nodes):
        row, col = divmod(index, 2)
        out[node] = (cols[col], rows[row])
    return out


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s04")
    nodes = [str(x) for x in p["nodes"]]
    notes = [str(x) for x in p["node_notes"]]
    edges = [(str(row[0]), str(row[1])) for row in p["edges"]]

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    # ---- 窗口框 ----
    win_x, win_y = w * 0.10, h * 0.25
    win_w, win_h = w * 0.80, h * 0.52
    rounded_rect(ctx, win_x, win_y, win_w, win_h, 16, "#F7F9FC")
    stroke_rect(ctx, win_x, win_y, win_w, win_h, 16, "#DCE1E8", 3, 0.9)
    text(ctx, p["window_label"], win_x + w * 0.02, win_y + h * 0.062, 34,
         COLORS["secondary"], bold=True)

    node_w, node_h = w * 0.16, h * 0.075
    positions = node_positions(nodes, w, h)

    # ---- 边先画，压在节点下面 ----
    for index, (src, dst) in enumerate(edges):
        if src not in positions or dst not in positions:
            continue
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.34 - index * 0.12) * 3.0))
        )
        sx, sy = positions[src]
        dx, dy = positions[dst]
        arrow(ctx, sx + node_w, sy + node_h / 2, dx, dy + node_h / 2,
              COLORS["accent"], 6, 22, alpha=appear)

    # ---- 节点 ----
    for index, node in enumerate(nodes):
        sx, sy = positions[node]
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.10 - index * 0.08) * 3.0))
        )
        color = NODE_COLORS[index % len(NODE_COLORS)]
        rounded_rect(ctx, sx, sy, node_w, node_h, 12, color, alpha=appear)
        text(ctx, node, sx + node_w / 2, sy + node_h * 0.68, 40, "#FFFFFF",
             anchor="center", bold=True, alpha=appear)
        if index < len(notes):
            text(ctx, notes[index], sx + node_w / 2, sy + node_h + h * 0.045, 30,
                 COLORS["primary"], anchor="center", alpha=appear)

    text(ctx, p["caption"], w * 0.07, h * 0.90, 44, COLORS["primary"])
