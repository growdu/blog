"""ASS 字幕生成 + cairo 直烧字幕。

本机 ffmpeg 没有编译 libass（无 `--enable-libass`），`ass=` 滤镜不可用，
所以成片字幕改为在渲染阶段由 cairo 直接画进画面；ASS 文件仍然生成，
作为契约副产物供 MiniMax Design 导入时复用。
"""
from __future__ import annotations

import cairo

from pyv import fonts
from pyv.palette import hex_to_rgb
from pyv.timeline import SubtitleEvent, SubtitleStyle, Storyboard, display_width

MAX_WIDTH = 14.0

# 烧录字幕的排版常量，与 ASS 样式保持一致
BURN_FONT_SIZE = 46
BURN_MARGIN_V = 52      # 字幕底边距画面底部的距离，对应 ASS MarginV
BURN_LINE_GAP = 10      # 多行之间的行距
BURN_OUTLINE = 3.0      # 描边宽度


def fmt_ass_time(seconds: float) -> str:
    """秒 → 'h:mm:ss.cc'。"""
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:d}:{minutes:02d}:{secs:05.2f}"


def wrap_line(text: str, limit: float = MAX_WIDTH) -> list[str]:
    """按视觉宽度切行，避免字幕溢出画面；已有的换行会被保留。"""
    lines: list[str] = []
    for raw_line in text.split("\n"):
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        current = ""
        for ch in raw_line:
            candidate = current + ch
            if current and display_width(candidate) > limit:
                lines.append(current)
                current = ch
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


def _ass_color(hex_color: str) -> str:
    """'#RRGGBB' → '&H00BBGGRR'。"""
    value = hex_color.lstrip("#")
    r, g, b = value[0:2], value[2:4], value[4:6]
    return f"&H00{b}{g}{r}".upper()


def build_ass(storyboard: Storyboard) -> str:
    style = storyboard.subtitle_style
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {storyboard.video.width}
PlayResY: {storyboard.video.height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{fonts.font_family()},{BURN_FONT_SIZE},{_ass_color(style.primary)},{_ass_color(style.primary)},{_ass_color(style.outline)},&H00000000,0,1,{BURN_OUTLINE:.0f},0,2,80,80,{BURN_MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for event in storyboard.subtitle_events():
        text = r"\N".join(wrap_line(event.text))
        lines.append(
            f"Dialogue: 0,{fmt_ass_time(event.start)},{fmt_ass_time(event.end)},"
            f"Default,,0,0,0,,{text}"
        )
    return "\n".join(lines) + "\n"


def _outlined_text(ctx: cairo.Context, s: str, x: float, baseline: float,
                   fill_color: str, outline_color: str,
                   outline_width: float) -> None:
    """画一行带描边的文字：转路径后先描边再填充。

    show_text 只负责渲染字形、不会把轮廓加进路径，描边必须走 text_path；
    而 cairo 的 stroke/fill 都会清空当前路径，所以描边与填充各建一次路径。
    """
    ctx.set_line_width(outline_width)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)

    ctx.move_to(x, baseline)
    ctx.text_path(s)
    ctx.set_source_rgb(*hex_to_rgb(outline_color))
    ctx.stroke()

    ctx.move_to(x, baseline)
    ctx.text_path(s)
    ctx.set_source_rgb(*hex_to_rgb(fill_color))
    ctx.fill()


def draw_event(ctx: cairo.Context, text: str, style: SubtitleStyle,
               width: int, height: int) -> None:
    """把一条字幕画在画面底部居中位置。

    字号、边距按 1080p 基准等比缩放，保证换分辨率导出时不会溢出。
    """
    lines = wrap_line(text)
    if not lines:
        return
    scale = height / 1080.0
    font_size = BURN_FONT_SIZE * scale
    margin_v = BURN_MARGIN_V * scale
    line_gap = BURN_LINE_GAP * scale
    outline = max(0.6, BURN_OUTLINE * scale)

    ctx.select_font_face(
        fonts.font_family(), cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL
    )
    ctx.set_font_size(font_size)
    descent = ctx.font_extents()[1]  # pycairo 返回 (ascent, descent, height, ...)
    line_height = font_size + line_gap
    last_baseline = height - margin_v - descent
    for index, line in enumerate(lines):
        baseline = last_baseline - (len(lines) - 1 - index) * line_height
        line_width = ctx.text_extents(line).width
        _outlined_text(
            ctx, line, (width - line_width) / 2, baseline,
            style.primary, style.outline, outline,
        )


class SubtitleBurner:
    """按绝对时间把字幕烧进画面。"""

    def __init__(self, events: list[SubtitleEvent], style: SubtitleStyle) -> None:
        self.events = sorted(events, key=lambda e: e.start)
        self.style = style

    def event_at(self, t: float) -> SubtitleEvent | None:
        for event in self.events:
            if event.start <= t < event.end:
                return event
        return None

    def draw(self, ctx: cairo.Context, t: float, width: int, height: int) -> None:
        event = self.event_at(t)
        if event is None:
            return
        draw_event(ctx, event.text, self.style, width, height)
