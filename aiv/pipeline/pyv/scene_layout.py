"""竖版（1080×1920）的共用版式件。

横版与竖版不是同一张画面旋转过来的：横版是「左右分栏」，竖版是
「上下堆叠」。所以每个场景模块各有一份竖版画法，但**共用的规矩**
只有一份——各模块各写各的版式，规矩不许各写各的。

规矩一：**字号不缩，框变宽。**
    竖版画布只有 1080 宽，横版是 1920。同一档字号（30、38、58……）
    在竖版里相对画面更大——手机上看，文字要顶得住。相应地，框要
    占满宽度，元素改成纵向堆叠。

规矩二：**字要放得下。**
    竖版的框比横版窄一半，同一句话放不下是常态。统一用 `fit_size()`
    收字号——**宁可字小一点，也不能出框**：出框的标题在手机上就是
    「被裁掉半个字」，而这种事在渲染图上一眼看不出来（画面照样生成）。

规矩三：**说明与字幕都在字幕带之上。**
    竖版字幕抬到了平台 UI 之上（`palette.VERTICAL_UI_BOTTOM`），
    画面里的说明也跟着抬——两行都在下缘就会绞在一起
    （横版踩过这个坑，见 `tests/test_scene_layout.py`）。

**竖版的三个位置**（比例相对画面高度 1920）：

| 位置 | 比例 | 像素 | 说明 |
| --- | --- | --- | --- |
| 标题基线 | 0.085 | 163 | 所有场景统一 |
| 内容区上沿 | 0.125 | 240 | 内容从这里开始 |
| 内容区下沿 | 0.645 | 1238 | 内容到这里为止 |
| 说明基线 | 0.695 | 1334 | 说明的墨迹下沿要高于字幕带 1393 |

这些数字不是随手定的：**说明基线 1334 的墨迹下沿约 1345**，
而竖版字幕带从 **1393** 开始——中间留 48 px 的余量。
"""
from __future__ import annotations

import cairo

from pyv import fonts
from pyv.draw import text
from pyv.palette import COLORS

#: 竖版的三个位置（比例相对画面高度）
TITLE_Y = 0.085
CONTENT_TOP = 0.125
CONTENT_BOTTOM = 0.645
CAPTION_Y = 0.695

#: 左右边距与内容区宽度（比例相对画面宽度）。
#: 横版的内容从 w*0.06 开始，竖版沿用同一个边距，宽度给到 0.88。
MARGIN_X = 0.06
CONTENT_W = 0.88

#: 标题与说明的字号（竖版比横版大一号：手机上看，标题要顶得住）
TITLE_SIZE = 64
CAPTION_SIZE = 40

#: 字号收小的下限。再小就不是「字」了，宁可让版式重排。
MIN_SIZE = 20.0


def _select_face(ctx: cairo.Context, bold: bool) -> None:
    """把 ctx 的字体族设成**画的时候真正用的那一个**。

    `draw.text` 画之前会自己 `select_font_face(fonts.font_family(), ...)`，
    所以量宽度必须用同一个族与同一个字重——量出来的宽度要和画出来的
    宽度一致，否则「收字号」就是在跟一个假的宽度较劲。
    """
    ctx.select_font_face(
        fonts.font_family(),
        cairo.FONT_SLANT_NORMAL,
        cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL,
    )


def _ink_extent(ctx: cairo.Context, s: str, size: float,
                bold: bool) -> float:
    """从落笔点算起，这行字的墨迹右沿有多远。

    **量的是墨迹右沿，不是步进宽度。** cairo 的 `text_extents().width`
    是墨迹包围盒的宽，`x_bearing` 是从落笔点到最左墨迹的距离——
    两者相加才是墨迹真正占到的右沿（实测中文左边距约 2 px）。
    少算这一截，字就会画出框外几个像素。
    """
    _select_face(ctx, bold)
    ctx.set_font_size(size)
    ext = ctx.text_extents(s)
    return ext.x_bearing + ext.width


def fit_size(ctx: cairo.Context, s: str, max_width: float, size: float,
             floor: float = MIN_SIZE, bold: bool = False) -> float:
    """把字号往下收，直到这行字放得进 `max_width`。

    **宁可字小一点，也不能出框。** 出框的标题在手机上就是「被裁掉
    半个字」，而渲染图上一眼看不出来——画面照样生成、时长照样对。

    **测量前必须先选定字体族**（见 `_select_face`）：cairo 的 toy API
    默认族是 sans，没有中文字形，量中文只能量到 .notdef 的宽度——
    实测只有真实宽度的 63%。拿这个宽度去收字号，中文标题就会被判成
    「放得下」，实际画出去却是出框的。

    **要迭代，不能只缩一次。** 字体 hinting 会把每个字的步进宽度取整，
    所以「宽度正比于字号」只是近似：缩一次之后量出来仍可能超几个像素。
    所以收完再量一次，直到真的放下。
    """
    if not s or size <= floor:
        return floor
    for _ in range(4):
        extent = _ink_extent(ctx, s, size, bold)
        if extent <= max_width or extent <= 0:
            break
        size = max(floor, size * max_width / extent)
        if size <= floor:
            break
    return size


def line(ctx: cairo.Context, s: str, x: float, y: float, max_width: float,
         size: float, color: str, bold: bool = False, alpha: float = 1.0,
         anchor: str = "left") -> None:
    """一行字：放不下就收字号。

    这是竖版最常用的入口——竖版的框比横版窄一半，**每一行字都要
    过一遍 `fit_size`**。
    """
    fitted = fit_size(ctx, s, max_width, size, bold=bold)
    text(ctx, s, x, y, fitted, color, anchor=anchor, bold=bold, alpha=alpha)


def title(ctx: cairo.Context, text_value: str, w: int, h: int,
          size: float = TITLE_SIZE, color: str = COLORS["primary"],
          bold: bool = True, alpha: float = 1.0) -> None:
    """竖版的标题：左对齐，与横版一样从边距起排。

    左对齐而不是居中——竖版的内容是纵向堆叠的，标题跟着内容左边缘
    对齐，整张画面才有一条统一的竖轴。
    """
    line(ctx, text_value, w * MARGIN_X, h * TITLE_Y, w * CONTENT_W,
         size, color, bold=bold, alpha=alpha)


def caption(ctx: cairo.Context, text_value: str, w: int, h: int,
            size: float = CAPTION_SIZE, color: str = COLORS["primary"],
            alpha: float = 1.0) -> None:
    """竖版的说明（画面左下角那行字）。

    位置在字幕带之上——两行都在下缘会绞在一起（横版踩过）。
    """
    line(ctx, text_value, w * MARGIN_X, h * CAPTION_Y, w * CONTENT_W,
         size, color, alpha=alpha)


def content_width(w: int) -> float:
    """内容区的宽度。"""
    return w * CONTENT_W


def content_left(w: int) -> float:
    """内容区的左边缘。"""
    return w * MARGIN_X


def content_top(h: int) -> float:
    """内容区的上沿。"""
    return h * CONTENT_TOP


def content_bottom(h: int) -> float:
    """内容区的下沿。"""
    return h * CONTENT_BOTTOM
