"""形象接入层测试（pyv/character.py）。"""
import cairo
import pytest

from pyv import character


def test_repo_paths_are_resolved_correctly():
    assert character.AIV_ROOT.name == "aiv"
    assert character.REPO_ROOT == character.AIV_ROOT.parents[2]
    assert character.LEGACY_IMAGE.name == "growdu.png"
    assert character.LEGACY_IMAGE.is_relative_to(character.REPO_ROOT)


def test_legacy_mascot_asset_lives_in_repo():
    """旧 2D 形象必须留在仓库里。

    新 3D 形象是媒体产物、不入库，新克隆的机器上只有它，
    流水线不能因此画不出小象。
    """
    assert character.LEGACY_IMAGE.exists(), character.LEGACY_IMAGE


def test_avatar_asset_lives_in_repo():
    """落版头像同样必须入库（原来的 growdu.jpg 从未入库、现已丢失）。"""
    assert character.avatar_path() is not None
    assert character.AVATAR_IMAGE.is_relative_to(character.REPO_ROOT)


def test_mascot_mode_is_known():
    assert character.Mascot().mode in ("static", "parts", "none")


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
