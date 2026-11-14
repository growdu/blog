"""段 D：依赖图模板。

一个窗口框住窗口内的几条事务，改了同一行的两条之间连一条边。
边画出来，谁必须排在谁前面就一目了然。

版式在代码里，**这一期的节点、说明与边在契约里**（`Scene.params`）。

**竖版（1080×1920）**：图的结构不变，还是窗口里的 2×2，只是窗口改成竖着的
方框——竖版只有 1080 宽，横版那种 0.8 倍宽的窗口放不下边上的说明文字。
节点格子因此收窄，格子里的字反而更大（见 `pyv/scene_layout.py` 的三条规矩）。
"""
from __future__ import annotations

from pyv import easing
from pyv import scene_layout
from pyv.draw import arrow, rounded_rect, stroke_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "window_label", "nodes", "node_notes", "edges", "caption")

# 节点配色：按列交替
NODE_COLORS = ("#F6AD55", "#F6AD55", "#4FD1C5", "#4FD1C5")

# 竖版：窗口与节点格子的版式常量
V_WIN_TOP_RATIO = 0.156     # 窗口上沿（相对画面高度）
V_WIN_H_RATIO = 0.443       # 窗口高（相对画面高度）
V_NODE_W_RATIO = 0.42       # 节点格子宽（相对内容区宽度）
V_NODE_H_RATIO = 0.104      # 节点格子高（相对画面高度）
V_COL_X_RATIOS = (0.05, 0.56)   # 两列的左沿（相对内容区宽度）
V_ROW_Y_RATIOS = (0.224, 0.417)  # 两行的上沿（相对画面高度）


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
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return

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

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：窗口框变成竖着的方框，里面的 2×2 依赖图不变。

    **字号不缩、框变宽**：格子虽然比横版窄，但格子里的字更大
    （节点 48、说明 32，比横版的 40/30 大一档）——竖版只有 1080 宽，
    字不顶得住就白做了。
    """
    nodes = [str(x) for x in p["nodes"]]
    notes = [str(x) for x in p["node_notes"]]
    edges = [(str(row[0]), str(row[1])) for row in p["edges"]]

    left = w * scene_layout.MARGIN_X
    width = w * scene_layout.CONTENT_W

    scene_layout.title(ctx, p["title"], w, h)

    # ---- 窗口框 ----
    win_x, win_y = left, h * V_WIN_TOP_RATIO
    win_w, win_h = width, h * V_WIN_H_RATIO
    rounded_rect(ctx, win_x, win_y, win_w, win_h, 16, "#F7F9FC")
    stroke_rect(ctx, win_x, win_y, win_w, win_h, 16, "#DCE1E8", 3, 0.9)
    scene_layout.line(ctx, p["window_label"], win_x + width * 0.03,
                      win_y + h * 0.030, width * 0.5, 34, COLORS["secondary"],
                      bold=True)

    node_w = width * V_NODE_W_RATIO
    node_h = h * V_NODE_H_RATIO
    positions: dict[str, tuple[float, float]] = {}
    for index, node in enumerate(nodes):
        row, col = divmod(index, 2)
        positions[node] = (win_x + width * V_COL_X_RATIOS[col],
                           h * V_ROW_Y_RATIOS[row])

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
        scene_layout.line(ctx, node, sx + node_w / 2, sy + node_h * 0.68,
                          node_w * 0.9, 48, "#FFFFFF", bold=True, alpha=appear,
                          anchor="center")
        if index < len(notes):
            scene_layout.line(ctx, notes[index], sx + node_w / 2,
                              sy + node_h + h * 0.028, node_w, 32,
                              COLORS["primary"], alpha=appear, anchor="center")

    scene_layout.caption(ctx, p["caption"], w, h)
