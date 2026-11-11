import importlib

import cairo
import pytest

SCENE_MODULES = [
    "pyv.scenes.s01_intro",
    "pyv.scenes.s02_serial",
    "pyv.scenes.s03_cores",
    "pyv.scenes.s04_parallel",
    "pyv.scenes.s05_order",
    "pyv.scenes.s06_outro",
]


@pytest.mark.parametrize("name", SCENE_MODULES)
def test_scene_module_exposes_render(name):
    module = importlib.import_module(name)
    assert callable(module.render)


@pytest.mark.parametrize("name", SCENE_MODULES)
def test_scene_render_draws_something(name):
    module = importlib.import_module(name)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 320, 180)
    ctx = cairo.Context(surface)
    module.render(ctx, 0.5, 320, 180)
    data = surface.get_data()
    assert any(byte != 0 for byte in data)


@pytest.mark.parametrize("name", SCENE_MODULES)
def test_scene_render_handles_endpoints(name):
    module = importlib.import_module(name)
    for t in (0.0, 1.0):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 320, 180)
        ctx = cairo.Context(surface)
        module.render(ctx, t, 320, 180)


def test_s03_highlights_exactly_one_core():
    import pyv.scenes.s03_cores as s03
    highlighted = s03.highlighted_cores()
    assert len(highlighted) == 1
    assert 0 <= highlighted[0] < 32


def test_s04_exposes_four_workers():
    import pyv.scenes.s04_parallel as s04
    assert s04.worker_count() == 4


def test_s05_outputs_in_ascending_order():
    import pyv.scenes.s05_order as s05
    assert s05.output_order() == [1, 2, 3, 4]


def test_s06_uses_personal_avatar_and_no_banned_words():
    import pyv.scenes.s06_outro as s06
    from pyv import character
    from pyv.timeline import BANNED_SUBSTRINGS
    source = open(s06.__file__, encoding="utf-8").read()
    assert "avatar_path" in source, "落版头像必须走统一入口"
    assert character.avatar_path() is not None, "个人头像素材缺失"
    for word in BANNED_SUBSTRINGS:
        assert word.lower() not in source.lower(), word


@pytest.mark.parametrize("name", SCENE_MODULES)
def test_scene_source_has_no_banned_words(name):
    from pyv.timeline import BANNED_SUBSTRINGS
    module = importlib.import_module(name)
    source = open(module.__file__, encoding="utf-8").read()
    for word in BANNED_SUBSTRINGS:
        assert word.lower() not in source.lower(), (name, word)


def _glyph_pixels(ch: str, size: int = 40) -> bytes:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size * 2, size * 2)
    ctx = cairo.Context(surface)
    ctx.select_font_face("PingFang SC", cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    ctx.set_source_rgb(0, 0, 0)
    ctx.move_to(4, size)
    ctx.show_text(ch)
    surface.flush()
    return bytes(surface.get_data())


def _is_missing_glyph(ch: str) -> bool:
    """字体没有该字形时会画成同一个豆腐块，可据此比对。"""
    return _glyph_pixels(ch) == _glyph_pixels("\ue000")


@pytest.mark.parametrize("name", SCENE_MODULES)
def test_every_character_in_scene_source_is_renderable(name, monkeypatch):
    """PingFang SC 缺字形时会静默画成豆腐块，必须提前拦住。"""
    module = importlib.import_module(name)
    original = module.text
    drawn: list[str] = []

    def spy(ctx, s, *args, **kwargs):
        drawn.append(s)
        return original(ctx, s, *args, **kwargs)

    monkeypatch.setattr(module, "text", spy)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 320, 180)
    ctx = cairo.Context(surface)
    module.render(ctx, 0.5, 320, 180)

    assert drawn, "场景应当至少画出一行文字"
    for s in drawn:
        for ch in s:
            if ch.isspace():
                continue
            assert not _is_missing_glyph(ch), (
                f"{name} 画的字符 {ch!r} 不在 PingFang SC 里，会渲染成豆腐块"
            )
