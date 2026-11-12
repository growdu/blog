import json

import cairo
import numpy as np

from pyv import subtitle
from pyv.timeline import Storyboard


def _sb(tmp_path, scenes, duration=5.0, subtitles=None):
    raw = {
        "version": 1,
        "video": {"width": 1920, "height": 1080, "fps": 24, "duration": duration},
        "audio": {"narration": "pa_decode_v2.mp3", "bgm": None},
        "subtitle_style": {"primary": "#1B2A47", "outline": "#FFFFFF",
                           "position": "bottom-center"},
        "scenes": scenes,
    }
    if subtitles is not None:
        raw["subtitles"] = subtitles
    path = tmp_path / "storyboard.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return Storyboard.load(path)


def test_fmt_ass_time():
    assert subtitle.fmt_ass_time(0.0) == "0:00:00.00"
    assert subtitle.fmt_ass_time(3.5) == "0:00:03.50"
    assert subtitle.fmt_ass_time(61.25) == "0:01:01.25"


def test_wrap_line_splits_at_width_limit():
    lines = subtitle.wrap_line("一二三四五六七八九十一二三四五六七八九十")
    assert all(subtitle.display_width(line) <= 14 for line in lines)
    assert "".join(lines) == "一二三四五六七八九十一二三四五六七八九十"


def test_wrap_line_keeps_latin_phrase_together():
    lines = subtitle.wrap_line("openGauss 并行逻辑解码")
    assert len(lines) == 1
    assert lines[0] == "openGauss 并行逻辑解码"


def test_build_ass_has_one_dialogue_per_subtitle_event(tmp_path):
    sb = _sb(tmp_path, [
        {"id": "s01", "start": 0.0, "end": 2.0, "type": "code",
         "renderer": "pyv.scenes.s01_intro", "subtitle": "我是独立开发者"},
    ], subtitles=[
        {"start": 0.0, "end": 1.0, "text": "字幕甲"},
        {"start": 1.0, "end": 2.0, "text": "字幕乙"},
    ])
    ass = subtitle.build_ass(sb)
    assert ass.count("Dialogue:") == 2
    assert "PlayResX: 1920" in ass
    assert "PlayResY: 1080" in ass
    assert "PingFang SC" in ass


def test_build_ass_uses_event_timecodes(tmp_path):
    sb = _sb(tmp_path, [
        {"id": "s01", "start": 0.0, "end": 2.0, "type": "code",
         "renderer": "pyv.scenes.s01_intro", "subtitle": "甲"},
    ], subtitles=[
        {"start": 1.5, "end": 2.5, "text": "甲"},
    ])
    ass = subtitle.build_ass(sb)
    assert "0:00:01.50,0:00:02.50" in ass


def test_build_ass_encodes_bgr_colors(tmp_path):
    sb = _sb(tmp_path, [
        {"id": "s01", "start": 0.0, "end": 5.0, "type": "code",
         "renderer": "pyv.scenes.s01_intro", "subtitle": "甲"},
    ])
    ass = subtitle.build_ass(sb)
    assert "&H00472A1B" in ass
    assert "&H00FFFFFF" in ass


def test_build_ass_escapes_newline_in_subtitle(tmp_path):
    sb = _sb(tmp_path, [
        {"id": "s01", "start": 0.0, "end": 5.0, "type": "code",
         "renderer": "pyv.scenes.s01_intro", "subtitle": "甲"},
    ], subtitles=[
        {"start": 0.0, "end": 1.0, "text": "第一行\n第二行"},
    ])
    ass = subtitle.build_ass(sb)
    assert r"\N" in ass


def _blank_surface(width: int, height: int):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(1, 1, 1)
    ctx.paint()
    return surface, ctx


def _pixels(surface) -> np.ndarray:
    """ARGB32 表面转成 (h, w, 4) 的 BGRA 数组。"""
    stride = surface.get_stride()
    width = surface.get_width()
    height = surface.get_height()
    raw = np.frombuffer(surface.get_data(), dtype=np.uint8).reshape(height, stride)
    return raw[:, :width * 4].reshape(height, width, 4)


def _dark_blue_mask(pixels: np.ndarray) -> np.ndarray:
    b, g, r = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
    return (abs(r.astype(int) - 0x1B) < 40) & (abs(g.astype(int) - 0x2A) < 40) & (
        abs(b.astype(int) - 0x47) < 40
    )


def _style():
    from pyv.timeline import SubtitleStyle
    return SubtitleStyle(primary="#1B2A47", outline="#FFFFFF")


def test_draw_event_puts_text_in_bottom_band():
    surface, ctx = _blank_surface(1920, 1080)
    subtitle.draw_event(ctx, "订阅端顺序与发布端一致", _style(), 1920, 1080)
    mask = _dark_blue_mask(_pixels(surface))
    assert mask.any(), "应当画出深蓝字幕"
    rows = np.where(mask.any(axis=1))[0]
    assert rows.min() > 1080 * 0.85, "字幕必须落在画面底部"
    assert rows.max() <= 1080 - 10


def test_draw_event_keeps_text_horizontally_centered():
    surface, ctx = _blank_surface(1920, 1080)
    subtitle.draw_event(ctx, "订阅端顺序与发布端一致", _style(), 1920, 1080)
    mask = _dark_blue_mask(_pixels(surface))
    cols = np.where(mask.any(axis=0))[0]
    center = (cols.min() + cols.max()) / 2
    assert abs(center - 960) < 20


def test_draw_event_scales_with_canvas():
    def ink_height(height):
        surface, ctx = _blank_surface(960, height)
        subtitle.draw_event(ctx, "订阅端顺序与发布端一致", _style(), 960, height)
        mask = _dark_blue_mask(_pixels(surface))
        rows = np.where(mask.any(axis=1))[0]
        return rows.max() - rows.min()

    big = ink_height(1080)
    small = ink_height(540)
    assert small < big * 0.75, "分辨率减半，字号也应当明显变小"


def test_subtitle_burner_selects_event_by_time():
    from pyv.timeline import SubtitleEvent
    events = [
        SubtitleEvent(start=0.0, end=2.0, text="甲"),
        SubtitleEvent(start=2.0, end=4.0, text="乙"),
    ]
    burner = subtitle.SubtitleBurner(events, _style())
    assert burner.event_at(0.5).text == "甲"
    assert burner.event_at(1.999).text == "甲"
    assert burner.event_at(2.0).text == "乙"
    assert burner.event_at(4.0) is None


def test_build_ass_and_burn_use_same_line_breaks(tmp_path):
    sb = _sb(tmp_path, [
        {"id": "s01", "start": 0.0, "end": 5.0, "type": "code",
         "renderer": "pyv.scenes.s01_intro", "subtitle": "甲"},
    ], subtitles=[
        {"start": 0.0, "end": 1.0, "text": "第一行\n第二行"},
    ])
    ass = subtitle.build_ass(sb)
    assert "第一行\\N第二行" in ass
    assert subtitle.wrap_line("第一行\n第二行") == ["第一行", "第二行"]
