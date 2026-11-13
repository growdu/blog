"""字体解析的守卫：跨平台挑字体，且渲染代码不再硬编码 macOS 字体。"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from pyv import fonts

PIPELINE_DIR = Path(__file__).resolve().parent.parent
PYV_DIR = PIPELINE_DIR / "pyv"


@pytest.fixture(autouse=True)
def _reset_cache():
    """字体解析是缓存的，改完环境变量必须清缓存，否则测的是上一轮的结果。"""
    fonts.reset_font_cache()
    yield
    fonts.reset_font_cache()


def test_resolve_font_finds_a_usable_family():
    """这台机器上必须能解析出一款中文字体（否则渲染会直接抛错）。"""
    font = fonts.resolve_font()
    assert font.resolves, f"没解析出可用字体：{font}"
    assert font.family.strip()


def test_environment_variable_wins(monkeypatch):
    monkeypatch.setenv(fonts.FONT_ENV, "Some Explicit Family")
    fonts.reset_font_cache()
    font = fonts.resolve_font()
    assert font.family == "Some Explicit Family"
    assert fonts.FONT_ENV in font.label


def test_macos_font_is_tried_before_linux_fonts():
    """macOS 上必须继续用 PingFang SC——否则历史成片的画面会变。"""
    macos = {c.family for c in fonts.MACOS_CANDIDATES}
    assert macos == {"PingFang SC"}
    families = [c.family for c in fonts._all_candidates()]
    assert families.index("PingFang SC") < families.index("Noto Sans CJK SC")


def test_linux_fallback_is_a_cjk_font():
    """Linux 上退到的必须是开源中文字体（PingFang 是 Apple 授权，不能分发）。"""
    families = {c.family for c in fonts.LINUX_CANDIDATES}
    assert "Noto Sans CJK SC" in families
    assert "Source Han Sans SC" in families
    for candidate in fonts.LINUX_CANDIDATES:
        assert candidate.path.startswith("/usr/share/fonts/")


def test_no_linux_candidate_points_at_apple_font():
    """Linux 候选里不能出现 /System/Library（那是 macOS 专有路径）。"""
    for candidate in fonts.LINUX_CANDIDATES:
        assert "/System/" not in candidate.path


def test_assert_font_available_raises_with_install_hint(monkeypatch):
    monkeypatch.setattr(
        fonts, "resolve_font",
        lambda: fonts.ResolvedFont("Nope", None, "没有", False),
    )
    with pytest.raises(RuntimeError) as excinfo:
        fonts.assert_font_available()
    message = str(excinfo.value)
    assert "fonts-noto-cjk" in message
    assert fonts.FONT_ENV in message


def test_assert_font_available_passes_when_resolvable(monkeypatch):
    monkeypatch.setattr(
        fonts, "resolve_font",
        lambda: fonts.ResolvedFont("Some Family", None, "有", True),
    )
    fonts.assert_font_available()


def test_palette_delegates_to_fonts(monkeypatch):
    from pyv import palette

    called = []
    monkeypatch.setattr(fonts, "assert_font_available",
                        lambda: called.append(1))
    palette.assert_font_available()
    assert called == [1]


def _source_files() -> list[Path]:
    """要扫的源码：流水线与脚本，不含 tests（测试自己会提到这些路径）。"""
    out = []
    for directory in (PYV_DIR, PIPELINE_DIR / "scripts"):
        if not directory.is_dir():
            continue
        out.extend(sorted(directory.rglob("*.py")))
    return out


def test_no_render_module_hardcodes_pingfang():
    """渲染代码不许再硬编码「PingFang SC」——换平台时会静默画成豆腐块。"""
    offenders = []
    for path in _source_files():
        if path.name == "fonts.py":
            continue          # 候选表本身当然要提这个名字
        source = path.read_text(encoding="utf-8")
        if re.search(r'"PingFang SC"|\'PingFang SC\'', source):
            offenders.append(str(path.relative_to(PIPELINE_DIR)))
    assert offenders == []


def test_no_module_hardcodes_apple_font_paths():
    """macOS 专有的字体路径只允许出现在 fonts.py 的候选表里。"""
    offenders = []
    pattern = re.compile(r"/System/Library/Fonts/")
    for path in _source_files():
        if path.name == "fonts.py":
            continue
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(PIPELINE_DIR)))
    assert offenders == []


def test_missing_glyph_detects_a_character_the_font_lacks():
    """字体里没有的字符会被画成豆腐块，必须能识别出来。"""
    # 私有区字符，几乎所有中文字体都没有
    assert fonts.missing_glyph("\ue123")
    # 常用汉字肯定有
    assert not fonts.missing_glyph("并")


def test_font_family_matches_resolved_font():
    assert fonts.font_family() == fonts.resolve_font().family
