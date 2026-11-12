"""段 E：六层一览模板。

六行，每行一层：层号徽标 + 机制名 + 这层管住什么。
从上到下就是链路本身的顺序，逐层点亮——观众跟着出现顺序读，不用一次全看完。

版式在代码里，**这一期的层号、机制名与作用说明在契约里**（`Scene.params`）。
"""
from __future__ import annotations

from pyv import easing
from pyv.draw import rounded_rect, text
from pyv.palette import COLORS
from pyv.params import Params

REQUIRED = ("title", "layer_ids", "layer_names", "layer_roles", "caption")

# 版式常量：每层一行，行的起点与步长
ROW_TOP = 0.225
ROW_STEP = 0.103
ROW_H = 0.082
# 层与层之间的点亮间隔（场景进度）：六层铺满整个场景，读完一层才出下一层
ROW_STAGGER = 0.12


def layer_count(params=None) -> int:
    """层数。"""
    p = Params(params, "s05")
    return len(p["layer_ids"])


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    p = Params(params, "s05")
    ids = [str(x) for x in p["layer_ids"]]
    names = [str(x) for x in p["layer_names"]]
    roles = [str(x) for x in p["layer_roles"]]

    text(ctx, p["title"], w * 0.06, h * 0.13, 58, COLORS["primary"], bold=True)

    for index in range(layer_count(params)):
        y = h * ROW_TOP + index * h * ROW_STEP
        row_h = h * ROW_H
        appear = easing.ease_out_cubic(
            max(0.0, min(1.0, (t - ROW_STAGGER * index) * 3.5)))
        badge = COLORS["accent"] if index % 2 == 0 else COLORS["secondary"]
        rounded_rect(ctx, w * 0.07, y, w * 0.066, row_h, 10, badge, alpha=appear)
        text(ctx, ids[index], w * 0.103, y + row_h * 0.66, 34, "#FFFFFF",
             anchor="center", bold=True, alpha=appear)
        text(ctx, names[index], w * 0.16, y + row_h * 0.64, 40,
             COLORS["primary"], bold=True, alpha=appear)
        text(ctx, roles[index], w * 0.42, y + row_h * 0.64, 33,
             COLORS["secondary"], alpha=appear)

    # 收束句最后才出，六层亮完再落一句
    closing = easing.ease_out_cubic(max(0.0, min(1.0, (t - 0.80) * 5.0)))
    text(ctx, p["caption"], w * 0.07, h * 0.91, 44, COLORS["primary"],
         alpha=closing)
