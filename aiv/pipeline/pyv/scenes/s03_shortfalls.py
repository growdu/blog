"""段 C：四条短板的模板。

上面是订阅端真正遇到的问题——只拿到一段文本，判断不了这条命令做了什么。
下面四张卡片是社区讨论里列出来的四条短板。

版式在代码里，**这一期的问题、短板与文案在契约里**（`Scene.params`）。

**竖版（1080×1920）**：横版是「上面一条问题横幅 + 下面一排四张卡片」，
竖版改成上下堆叠——问题横幅铺满宽度放在上面，四条短板改成四张
整宽卡片依次排开（见 `pyv/scene_layout.py` 的三条规矩）。
"""
from __future__ import annotations

from pyv import easing
from pyv import scene_layout
from pyv.draw import rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "question_label", "shortfalls", "caption")

# 四张卡片的配色
CARD_COLORS = ("#F6AD55", "#4FD1C5", "#8FAADC", "#E9A0DC")


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s03")
    if h > w:
        _render_vertical(ctx, t, w, h, p)
        return

    shortfalls = [(str(row[0]), str(row[1])) for row in p["shortfalls"]]

    text(ctx, p["title"], w * 0.06, h * 0.145, 58, COLORS["primary"], bold=True)

    # ---- 订阅端遇到的问题 ----
    ask_x = w * 0.18
    ask_y = h * 0.26
    ask_w = w * 0.64
    ask_h = h * 0.15
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.06) * 3.0)))
    rounded_rect(ctx, ask_x, ask_y, ask_w, ask_h, 16, COLORS["primary"],
                 alpha=appear)
    text(ctx, "?", ask_x + w * 0.05, ask_y + ask_h * 0.80, 76, COLORS["accent"],
         anchor="center", bold=True, alpha=appear)
    text(ctx, p["question_label"], ask_x + w * 0.10, ask_y + ask_h * 0.66, 42,
         "#FFFFFF", bold=True, alpha=appear)

    # ---- 四条短板 ----
    card_w = w * 0.20
    gap = w * 0.03
    x0 = (w - (len(shortfalls) * card_w + (len(shortfalls) - 1) * gap)) / 2
    card_y = h * 0.53
    card_h = h * 0.17
    for index, (name, desc) in enumerate(shortfalls):
        cx = x0 + index * (card_w + gap)
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.22 - index * 0.11) * 3.0))
        )
        color = CARD_COLORS[index % len(CARD_COLORS)]
        rounded_rect(ctx, cx, card_y, card_w, card_h, 14, "#F2F5F9",
                     alpha=appear)
        rounded_rect(ctx, cx, card_y, card_w, h * 0.012, 6, color, alpha=appear)
        text(ctx, name, cx + card_w / 2, card_y + h * 0.075, 36, COLORS["primary"],
             anchor="center", bold=True, alpha=appear)
        text(ctx, desc, cx + card_w / 2, card_y + h * 0.125, 26,
             COLORS["secondary"], anchor="center", alpha=appear)

    text(ctx, p["caption"], w * 0.06, h * 0.86, 44, COLORS["primary"])


def _render_vertical(ctx, t: float, w: int, h: int, p: Params) -> None:
    """竖版：问题横幅在上，四条短板卡在下。

    横版把四张卡片并排成一行——竖版只有 1080 宽，并排会把每张卡
    压到 190 宽、字全得缩。竖版改成四张整宽卡片依次排开。
    """
    shortfalls = [(str(row[0]), str(row[1])) for row in p["shortfalls"]]

    left = scene_layout.content_left(w)
    full_w = scene_layout.content_width(w)

    scene_layout.title(ctx, p["title"], w, h)

    # ---- 订阅端遇到的问题 ----
    ask_y = scene_layout.content_top(h)
    ask_h = 170
    appear = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.06) * 3.0)))
    rounded_rect(ctx, left, ask_y, full_w, ask_h, 16, COLORS["primary"],
                 alpha=appear)
    scene_layout.line(ctx, "?", left + 60, ask_y + 120, 120, 80,
                      COLORS["accent"], bold=True, alpha=appear,
                      anchor="center")
    scene_layout.line(ctx, p["question_label"], left + 140, ask_y + 110,
                      full_w - 170, 42, "#FFFFFF", bold=True, alpha=appear)

    # ---- 四条短板 ----
    card_h = 170
    card_gap = 26
    card_y0 = 450
    for index, (name, desc) in enumerate(shortfalls):
        card_y = card_y0 + index * (card_h + card_gap)
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - 0.22 - index * 0.11) * 3.0))
        )
        color = CARD_COLORS[index % len(CARD_COLORS)]
        rounded_rect(ctx, left, card_y, full_w, card_h, 14, "#F2F5F9",
                     alpha=appear)
        rounded_rect(ctx, left, card_y, full_w, 12, 6, color, alpha=appear)
        scene_layout.line(ctx, name, left + 30, card_y + 72, full_w - 60, 40,
                          COLORS["primary"], bold=True, alpha=appear)
        scene_layout.line(ctx, desc, left + 30, card_y + 130, full_w - 60, 32,
                          COLORS["secondary"], alpha=appear)

    scene_layout.caption(ctx, p["caption"], w, h)
