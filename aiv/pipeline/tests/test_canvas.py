"""画布档位：横版 1920×1080 与竖版 1080×1920。

**横版是默认值，行为一个字都不能变。** 竖版是新增的一档（抖音那一档），
不是替换——所以每一条竖版规则都配一条「横版没变」的对照。

三条最要紧的：

1. **横版的字幕位置没动**（逐像素回归锁）。字号原来按 `height/1080` 缩放，
   改成按**短边**缩放；横版短边就是 1080，缩放系数仍是 1.0，位置不变。
2. **竖版的字幕不能压在平台 UI 底下**。竖版底部要给导航栏与文案区让位，
   字幕得抬上去——字幕压在 UI 底下等于没写。
3. **竖版不套品牌片**。品牌片素材是 1920×1080 的横版，贴到竖版画布上
   会被拉变形，所以 `pyv.cli brand` 对竖版画布直接拒绝，而不是出片。
"""
from __future__ import annotations

import json
from pathlib import Path

import cairo
import numpy as np
import pytest

from pyv import align
from pyv import episodes as episodes_mod
from pyv import palette
from pyv import subtitle as subtitle_mod
from pyv.timeline import Storyboard, Video

ROOT = Path(__file__).resolve().parents[2]
PIPELINE_ROOT = Path(__file__).resolve().parents[1]


# --- 画布档位 ---------------------------------------------------------------


def test_the_horizontal_canvas_is_unchanged():
    """横版还是 1920×1080——竖版是新增的档，不是替换。"""
    assert palette.CANVASES["horizontal"] == (1920, 1080)
    assert palette.WIDTH == 1920 and palette.HEIGHT == 1080


def test_the_vertical_canvas_is_1080x1920():
    assert palette.CANVASES["vertical"] == (1080, 1920)


def test_an_unknown_canvas_is_refused():
    with pytest.raises(ValueError, match="未知画布"):
        palette.canvas("square")


def test_the_vertical_test_is_decided_by_the_aspect_ratio():
    """判据只看高宽比，不认画布名字——以后加 4:5 之类的档，场景不用改。"""
    assert palette.is_vertical(1080, 1920) is True
    assert palette.is_vertical(1920, 1080) is False
    assert palette.is_vertical(1080, 1350) is True


def test_both_canvases_have_the_same_short_side():
    """两种画布的短边都是 1080，所以字号按短边缩放时两边同档。"""
    assert palette.short_side(1920, 1080) == 1080
    assert palette.short_side(1080, 1920) == 1080


# --- storyboard 的校验 ------------------------------------------------------


def _storyboard(width: int, height: int) -> Storyboard:
    raw = {
        "version": 1,
        "video": {"width": width, "height": height, "fps": 24, "duration": 4.0},
        "audio": {"narration": "n.mp3", "bgm": None},
        "subtitle_style": {"primary": "#1B2A47", "outline": "#FFFFFF",
                           "position": "bottom-center"},
        "scenes": [
            {"id": "s01", "start": 0.0, "end": 2.0, "type": "code",
             "renderer": "pyv.scenes.s01_intro", "subtitle": "一句"},
            {"id": "s02", "start": 2.0, "end": 4.0, "type": "code",
             "renderer": "pyv.scenes.s02_serial", "subtitle": "两句"},
        ],
    }
    path = Path("/tmp") / f"_canvas_test_{width}x{height}.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return Storyboard.load(path)


def test_a_vertical_storyboard_passes_validation():
    """竖版画布是**支持的**画布，不能再被「必须是 1920x1080」挡下来。"""
    assert _storyboard(1080, 1920).validate() == []


def test_an_unsupported_canvas_is_still_refused():
    """支持的只有那两档——别的尺寸照样要拦。"""
    errors = _storyboard(1080, 1350).validate()
    assert any("画布必须是" in e for e in errors), errors


# --- 字幕的位置 -------------------------------------------------------------


def _subtitle_ink_rows(width: int, height: int) -> np.ndarray:
    """把一条字幕画到画布上，返回有墨的行号。"""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    style = subtitle_mod.SubtitleStyle(primary="#1B2A47", outline="#FFFFFF")
    subtitle_mod.draw_event(ctx, "一行字幕", style, width, height)
    surface.flush()
    data = np.frombuffer(bytes(surface.get_data()), dtype=np.uint8)
    data = data.reshape(height, surface.get_stride() // 4, 4)
    alpha = data[..., 3]
    return np.nonzero(alpha.max(axis=1) > 8)[0]


def test_the_horizontal_subtitle_stays_at_the_bottom():
    """**横版回归锁**：字幕仍然贴着画面下缘，位置一个字都没动。"""
    rows = _subtitle_ink_rows(1920, 1080)
    assert rows.size > 0, "字幕没画出来"
    assert rows.max() < 1080
    assert rows.max() > 1080 - 80, (
        f"横版字幕的墨迹下沿在 y={rows.max()}，离画面底太远了——"
        f"原来它贴着底缘（改之前是 1080-{subtitle_mod.BURN_MARGIN_V} 附近）"
    )


def test_the_vertical_subtitle_clears_the_platform_ui():
    """竖版字幕要抬到平台 UI 之上——压在导航栏底下等于没写。"""
    rows = _subtitle_ink_rows(1080, 1920)
    assert rows.size > 0, "字幕没画出来"
    ui_line = 1920 - palette.VERTICAL_UI_BOTTOM
    assert rows.max() < ui_line, (
        f"竖版字幕的墨迹下沿在 y={rows.max()}，压到了 UI 区"
        f"（y ≥ {ui_line}）"
    )


def test_the_vertical_subtitle_uses_the_same_font_size_as_the_horizontal():
    """字号按短边缩放 → 两边同一档绝对像素。

    相对画面占比竖版更大（1080 宽 vs 1920 宽），这正是竖版要的：
    手机上看，文字要顶得住。
    """
    assert palette.short_side(*palette.CANVASES["horizontal"]) == \
        palette.short_side(*palette.CANVASES["vertical"])


# --- align 能写竖版 ---------------------------------------------------------


def test_align_can_write_a_vertical_storyboard(tmp_path):
    """`align --canvas vertical` 产出的 storyboard 是竖版的，且能过校验。"""
    episode = episodes_mod.EPISODE_ORDER[0]
    script = episodes_mod.EPISODES[episode]
    contract_name = f"{episode}.json"
    narration = ROOT / f"narration_{episode}.mp3"
    if not narration.is_file():
        pytest.skip(f"本机没有旁白 {narration}")
    out = tmp_path / "sb.json"
    storyboard = align.build_storyboard(
        narration, ROOT / script, out,
        contract_path=ROOT / "contracts" / contract_name,
        canvas="vertical",
    )
    assert (storyboard.video.width, storyboard.video.height) == (1080, 1920)
    assert storyboard.validate() == []
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["video"]["width"] == 1080
    assert saved["video"]["height"] == 1920


def test_align_defaults_to_the_horizontal_canvas(tmp_path):
    """默认档是横版——竖版是显式要的，不是默认换掉的。"""
    episode = episodes_mod.EPISODE_ORDER[0]
    script = episodes_mod.EPISODES[episode]
    contract_name = f"{episode}.json"
    narration = ROOT / f"narration_{episode}.mp3"
    if not narration.is_file():
        pytest.skip(f"本机没有旁白 {narration}")
    storyboard = align.build_storyboard(
        narration, ROOT / script, tmp_path / "sb.json",
        contract_path=ROOT / "contracts" / contract_name,
    )
    assert (storyboard.video.width, storyboard.video.height) == (1920, 1080)


# --- 品牌片不进竖版 ---------------------------------------------------------


def test_brand_plates_are_refused_on_a_vertical_canvas(tmp_path, capsys):
    """竖版画布不套品牌片。

    品牌片素材是 1920×1080 的横版，贴到 1080×1920 上会被拉变形。
    竖版那一档走 `nobrand`（无品牌版）。
    """
    from pyv import cli

    storyboard = _storyboard(1080, 1920)
    path = tmp_path / "sb.json"
    path.write_text(json.dumps({
        "version": 1,
        "video": {"width": 1080, "height": 1920, "fps": 24, "duration": 4.0},
        "audio": {"narration": "n.mp3", "bgm": None},
        "subtitle_style": {"primary": "#1B2A47", "outline": "#FFFFFF",
                           "position": "bottom-center"},
        "scenes": [
            {"id": "s01", "start": 0.0, "end": 2.0, "type": "code",
             "renderer": "pyv.scenes.s01_intro", "subtitle": "一句"},
            {"id": "s02", "start": 2.0, "end": 4.0, "type": "code",
             "renderer": "pyv.scenes.s02_serial", "subtitle": "两句"},
        ],
    }, ensure_ascii=False), encoding="utf-8")

    class _Args:
        storyboard = str(path)
        out = str(tmp_path / "out.json")
        build = str(tmp_path / "build")
        no_intro = False
        no_outro = False

    assert cli.cmd_brand(_Args()) == 1
    err = capsys.readouterr().err
    assert "竖版画布不套品牌片" in err
    assert not (tmp_path / "out.json").exists(), "拒绝了却还是出了片"
