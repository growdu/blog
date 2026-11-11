"""形象接入层测试（pyv/character.py）。"""
import inspect
from pathlib import Path

import cairo
import pytest

from pyv import character


def test_repo_paths_are_resolved_correctly():
    assert character.AIV_ROOT.name == "aiv"
    assert character.REPO_ROOT == character.AIV_ROOT.parents[2]
    assert character.STATIC_IMAGE.is_relative_to(character.AIV_ROOT)


def test_avatar_asset_lives_in_repo():
    """落版头像同样必须入库（原来的 growdu.jpg 从未入库、现已丢失）。"""
    assert character.avatar_path() is not None
    assert character.AVATAR_IMAGE.is_relative_to(character.REPO_ROOT)


def test_mascot_mode_is_known():
    assert character.Mascot().mode in ("static", "none")


def test_no_2d_mascot_fallback_remains():
    """2D 形象已整体移除：旧模块、旧素材、旧兜底分支都不能再有。

    2D 那套是颜色连通块切分 + 部件动画，阈值与绝对坐标都为扁平图硬编码；
    3D 渲染的渐变高光会直接破坏分割。形象一律走静帧 + 位移/缩放/淡入。
    """
    package = Path(character.__file__).parent
    assert not (package / "elephant.py").exists(), "2D 部件切分模块还在"
    assert not (character.REPO_ROOT / "growdu.png").exists(), "2D 形象素材还在仓库里"
    assert not hasattr(character, "LEGACY_IMAGE")
    assert not hasattr(character, "LEGACY_SOURCE_HEIGHT")


def test_mascot_draw_has_no_pose_parameter():
    """静帧形象没有姿势，接口里不能再留 pose。"""
    assert "pose" not in inspect.signature(character.Mascot.draw).parameters


def test_scenes_do_not_pass_pose():
    """场景里不能再有 pose= 调用——留着就会在渲染时炸掉。"""
    scenes = Path(character.__file__).parent / "scenes"
    assert scenes.is_dir()
    for path in sorted(scenes.glob("s*.py")):
        assert "pose=" not in path.read_text(encoding="utf-8"), path.name


def test_draw_without_asset_does_not_raise(monkeypatch):
    """没有形象素材时不画、也不报错。

    2D 兜底移除后，缺素材只剩这一条路。媒体产物不入库，
    新克隆的机器上就没有小象——流水线照样要跑得完。
    """
    monkeypatch.setattr(character, "STATIC_IMAGE",
                        character.REPO_ROOT / "__no_such_mascot__.png")
    mascot = character.Mascot()
    assert mascot.mode == "none"
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 320, 180)
    ctx = cairo.Context(surface)
    mascot.draw(ctx, (160.0, 170.0), 120.0)
    assert not any(byte != 0 for byte in surface.get_data())


def test_mascot_draws_pixels():
    mascot = character.Mascot()
    if mascot.mode == "none":
        pytest.skip("本机没有任何形象素材")
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 320, 180)
    ctx = cairo.Context(surface)
    mascot.draw(ctx, (160.0, 170.0), 120.0)
    assert any(byte != 0 for byte in surface.get_data())


def test_mascot_stands_on_the_anchor():
    """脚底锚点：形象要坐在 dest.y 上，不能穿过地面或浮在上面。"""
    mascot = character.Mascot()
    if mascot.mode == "none":
        pytest.skip("本机没有任何形象素材")
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 320, 180)
    ctx = cairo.Context(surface)
    mascot.draw(ctx, (160.0, 160.0), 100.0)
    data = bytes(surface.get_data())
    stride = surface.get_stride()
    bottom = 0
    for y in range(180):
        if any(data[y * stride:(y + 1) * stride][3::4]):
            bottom = y
    assert bottom == pytest.approx(160, abs=3)


def test_mascot_slide_and_alpha_change_output():
    """滑入位移与淡入必须真的影响输出（否则动效形同虚设）。"""
    mascot = character.Mascot()
    if mascot.mode == "none":
        pytest.skip("本机没有任何形象素材")

    def render(slide: float, alpha: float) -> bytes:
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 320, 180)
        ctx = cairo.Context(surface)
        mascot.draw(ctx, (160.0, 170.0), 120.0, alpha=alpha, slide=slide)
        return bytes(surface.get_data())

    assert render(0.0, 1.0) != render(-60.0, 1.0), "滑入没有改变画面"
    assert render(0.0, 1.0) != render(0.0, 0.2), "淡入没有改变画面"


def test_subject_box_finds_the_real_foot():
    """透明底素材四周留白，包围盒必须落在主体上而不是画布上。"""
    from PIL import Image

    image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    image.paste((255, 0, 0, 255), (20, 10, 60, 70))
    x0, y0, x1, y1 = character.subject_box(image)
    assert (x0, y0, x1, y1) == (20, 10, 60, 70)

    empty = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    assert character.subject_box(empty) == (0, 0, 50, 50)


def test_pil_to_cairo_keeps_rgba_order():
    """BGRA 字节序弄错会让整个形象偏色。"""
    from PIL import Image

    image = Image.new("RGBA", (2, 1), (10, 20, 30, 255))
    surface = character.pil_to_cairo(image)
    data = bytes(surface.get_data())
    blue, green, red, alpha = data[0], data[1], data[2], data[3]
    assert (red, green, blue, alpha) == (10, 20, 30, 255)
