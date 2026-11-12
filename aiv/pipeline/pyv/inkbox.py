"""测一段文字在画面上真正占的那块地方（墨迹）。

两个坑：

1. cairo 的 font_extents 给的 ascent/descent 是字体度量值，
   中文的实际墨迹比它矮不少——拿度量值判重叠，会把「看着分开的」
   两行字判成重叠。
2. **整行的包围盒不能直接拿来判重叠**。一行里既有中文又有拉丁小写时，
   包围盒的上沿来自汉字、下沿来自小写字母，于是它会「盖住」
   实际没有墨的地方。

所以这里按墨迹算，并支持只看一条带（比如只关心下沿）。
"""
from __future__ import annotations

import cairo


def _render(text: str, x: float, baseline: float, size: float,
            width: int = 1920, height: int = 1080,
            font: str = "PingFang SC"):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    ctx.select_font_face(font)
    ctx.set_font_size(size)
    ctx.move_to(x, baseline)
    ctx.show_text(text)
    surface.flush()
    return surface


def ink_bottom(text: str, x: float, baseline: float, size: float,
               width: int = 1920, height: int = 1080,
               font: str = "PingFang SC") -> float:
    """这行字最下面那点墨迹的纵坐标。没有墨就返回 baseline。"""
    surface = _render(text, x, baseline, size, width, height, font)
    data = surface.get_data()
    stride = surface.get_stride()
    top = max(0, int(baseline - size * 2.2))
    bottom = min(height, int(baseline + size * 1.2))
    for row in range(bottom - 1, top - 1, -1):
        offset = row * stride
        alpha = bytes(data[offset:offset + width * 4])[3::4]
        if any(alpha):
            return float(row)
    return float(baseline)


def ink_columns(text: str, x: float, baseline: float, size: float,
                width: int = 1920, height: int = 1080,
                font: str = "PingFang SC") -> list[tuple[int, int, int]]:
    """每一列的墨迹上下沿。列号是画面横坐标。没有墨的列不出现。"""
    surface = _render(text, x, baseline, size, width, height, font)
    data = surface.get_data()
    stride = surface.get_stride()
    top = max(0, int(baseline - size * 2.2))
    bottom = min(height, int(baseline + size * 1.2))
    column_top: dict[int, int] = {}
    column_bottom: dict[int, int] = {}
    for row in range(top, bottom):
        offset = row * stride
        alpha = bytes(data[offset:offset + width * 4])[3::4]
        if not any(alpha):
            continue
        for column, value in enumerate(alpha):
            if not value:
                continue
            if column not in column_top:
                column_top[column] = row
            column_bottom[column] = row
    return [(column, column_top[column], column_bottom[column])
            for column in sorted(column_top)]


def columns_intersect(a: list[tuple[int, int, int]],
                      b: list[tuple[int, int, int]]) -> list[int]:
    """两段文字在同一列上、且上下沿交叠的列。"""
    b_map = {column: (top, bottom) for column, top, bottom in b}
    hits: list[int] = []
    for column, top, bottom in a:
        other = b_map.get(column)
        if other is None:
            continue
        if min(bottom, other[1]) > max(top, other[0]):
            hits.append(column)
    return hits
