import os

import pytest

from pyv import palette


def test_canvas_constants_match_spec():
    assert palette.WIDTH == 1920
    assert palette.HEIGHT == 1080
    assert palette.FPS == 24


def test_all_colors_are_hex():
    for name, value in palette.COLORS.items():
        assert value.startswith("#") and len(value) == 7, name
        int(value[1:], 16)


def test_subtitle_colors_are_dark_text_on_light_bg():
    assert palette.COLORS["subtitle_text"] == "#1B2A47"
    assert palette.COLORS["subtitle_outline"] == "#FFFFFF"
    assert palette.COLORS["bg"] == "#FFFFFF"


def test_hex_to_rgb_roundtrip():
    assert palette.hex_to_rgb("#FFFFFF") == (1.0, 1.0, 1.0)
    assert palette.hex_to_rgb("#000000") == (0.0, 0.0, 0.0)


def test_assert_font_available_passes_on_this_machine():
    palette.assert_font_available()


def test_assert_font_available_is_delegated_to_the_fonts_module():
    """字体解析归 `pyv.fonts` 管（跨平台挑字体），palette 只做转发。"""
    from pyv import fonts

    assert palette.assert_font_available.__module__ == "pyv.palette"
    assert fonts.assert_font_available is not palette.assert_font_available
