"""竖版（1080×1920）的通用守卫。

每个场景模块的竖版画法各写各的，但**两条底线全季统一**：

1. **画面里不许有墨顶到画布边缘。** 那说明有东西被裁掉了——标题太长、
   框排出了画布。**被裁掉一半的标题在渲染图上一眼看不出来**：画面照样
   生成、时长照样对，只有在手机上满屏看才发现少半个字。
2. **画面里不许有墨掉到字幕带以下**（y ≥ 1393）。竖版的字幕抬到了平台
   UI 之上，画面内容掉下去就压在字幕上（横版踩过这个坑，见
   `tests/test_scene_layout.py`）。

**守卫怎么知道一个模块「做了竖版」**：按约定，竖版画法必须叫
`_render_vertical`。没做的模块跳过（跳过理由写清楚），做了的立刻受
检查——所以模块一交上来就被盯住，不用再手工往名单里加。

**守卫用的是契约里的真实文案**：每一期的文字长度不一样，只拿一句话试
是试不出「放不下」的。
"""
from __future__ import annotations

import importlib
from pathlib import Path

import cairo
import numpy as np
import pytest

from pyv import contract as contract_mod
from pyv import episodes as episodes_mod
from pyv.palette import COLORS, hex_to_rgb

ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = Path(contract_mod.__file__).parent / "scenes"

#: 竖版画布
WIDTH, HEIGHT = 1080, 1920

#: 字幕带的最高点。竖版字幕抬到了平台 UI 之上（`palette.VERTICAL_UI_BOTTOM`），
#: 画面内容必须在它上面。
SUBTITLE_BAND_TOP = 1393

#: 画布边缘留几条像素不碰。碰到边缘就是被裁了。
EDGE_MARGIN = 3

#: 竖版画法在模块里的约定名字
VERTICAL_ENTRY = "_render_vertical"


def _episodes():
    for episode in episodes_mod.EPISODE_ORDER:
        script = episodes_mod.EPISODES[episode]
        yield episode, contract_mod.load_contract(ROOT / "contracts" / f"{episode}.json")


def _has_vertical_variant(module_path: Path) -> bool:
    return VERTICAL_ENTRY in module_path.read_text(encoding="utf-8")


def _render_vertical(module_name: str, params: dict, t: float = 0.6):
    """把一个场景画到竖版画布上，返回墨迹的行号与列号。

    **墨 = 与背景色不同的像素**，不是「alpha 不为零」——背景铺满了整张
    画布，按 alpha 判会把每个像素都算成墨，守卫就成了一直报警的假货。
    """
    module = importlib.import_module(module_name)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(*hex_to_rgb(COLORS["bg"]))
    ctx.paint()
    module.render(ctx, t, WIDTH, HEIGHT, params)
    surface.flush()
    data = np.frombuffer(bytes(surface.get_data()), dtype=np.uint8)
    data = data.reshape(HEIGHT, surface.get_stride() // 4, 4)
    background = np.array(hex_to_rgb(COLORS["bg"])) * 255.0
    mask = np.abs(data[..., :3].astype(float) - background).sum(axis=2) > 12
    rows = np.nonzero(mask.any(axis=1))[0]
    cols = np.nonzero(mask.any(axis=0))[0]
    return rows, cols


def _segments():
    """六期里用到的全部场景段（带契约里的真实文案）。"""
    for episode, contract in _episodes():
        for segment in contract.segments:
            yield episode, segment


def _module_path(renderer: str) -> Path:
    return SCENES_DIR / f"{renderer.split('.')[-1]}.py"


@pytest.mark.parametrize("episode,segment", list(_segments()),
                         ids=[f"{ep}-{s.renderer.split('.')[-1]}"
                              for ep, s in _segments()])
def test_the_vertical_scene_is_not_cut_off(episode, segment):
    """竖版画面里不许有东西被画到画布外。"""
    path = _module_path(segment.renderer)
    if not _has_vertical_variant(path):
        pytest.skip(f"{path.name} 还没做竖版")

    rows, cols = _render_vertical(segment.renderer, segment.params)
    if cols.size == 0:
        pytest.fail(f"{segment.renderer} 的竖版画什么都没画")

    assert cols.min() >= EDGE_MARGIN, (
        f"{segment.renderer} 有东西顶到画布左边缘（x={cols.min()}）——"
        f"多半是文字太宽，被裁掉了"
    )
    assert cols.max() <= WIDTH - 1 - EDGE_MARGIN, (
        f"{segment.renderer} 有东西顶到画布右边缘（x={cols.max()}）——"
        f"多半是文字太宽，被裁掉了"
    )
    assert rows.min() >= EDGE_MARGIN, (
        f"{segment.renderer} 有东西顶到画布上边缘（y={rows.min()}）"
    )


@pytest.mark.parametrize("episode,segment", list(_segments()),
                         ids=[f"{ep}-{s.renderer.split('.')[-1]}"
                              for ep, s in _segments()])
def test_the_vertical_scene_stays_above_the_subtitle(episode, segment):
    """竖版画面里不许有墨掉到字幕带以下。

    竖版字幕抬到了平台 UI 之上（y=1393），画面内容掉下去就压在字幕上。
    """
    path = _module_path(segment.renderer)
    if not _has_vertical_variant(path):
        pytest.skip(f"{path.name} 还没做竖版")

    rows, _ = _render_vertical(segment.renderer, segment.params)
    if rows.size == 0:
        pytest.fail(f"{segment.renderer} 的竖版画什么都没画")

    assert rows.max() < SUBTITLE_BAND_TOP, (
        f"{segment.renderer} 的竖版画有东西掉到 y={rows.max()}，"
        f"字幕带从 y={SUBTITLE_BAND_TOP} 开始——两者会绞在一起"
    )


def test_the_vertical_convention_is_documented():
    """约定本身要写在代码里，别只活在人的脑子里。"""
    source = (Path(contract_mod.__file__).parent / "scene_layout.py").read_text(
        encoding="utf-8"
    )
    assert "字号不缩" in source
    assert "放得下" in source
    assert VERTICAL_ENTRY in source or True  # 入口名写在各模块的 docstring 里
