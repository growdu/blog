"""形象接入层测试（pyv/character.py）。"""
import inspect
from pathlib import Path

import cairo
import pytest

from pyv import character


def test_repo_paths_are_resolved_correctly():
    assert character.AIV_ROOT.name == "aiv"
    assert character.REPO_ROOT == character.AIV_ROOT.parents[0]
    assert character.STATIC_IMAGE.is_relative_to(character.AIV_ROOT)


def test_aiv_sits_next_to_weixin_at_repo_root():
    """aiv 是仓库根级模块，与 weixin 同级。

    目录层级被文档、脚本和 Makefile 里的相对路径引用着，挪一层就得全量改一遍。
    这里钉住它的位置，免得以后再被悄悄挪走。
    """
    repo_root = character.REPO_ROOT
    assert (repo_root / "aiv").is_dir()
    assert (repo_root / "weixin").is_dir()
    assert character.AIV_ROOT == repo_root / "aiv"
    # 旧位置只剩发布用的文档副本，工程内容（pipeline/ 等）必须已经搬走
    legacy = repo_root / "docs" / "life" / "aiv"
    assert legacy.is_dir()
    assert not (legacy / "pipeline").exists(), "工程目录还留在旧位置"


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


# --- 换素材 -----------------------------------------------------------------
#
# 抖音那一档备用：胸口那枚 growdu 铭牌也是品牌标识，被判「过度营销」
# 时要换成无铭牌那份。切换走 `use_image()`，命令行是 `render --character`。


def _solid(path, color):
    from PIL import Image

    Image.new("RGBA", (64, 64), color).save(path)
    return path


def test_use_image_switches_to_the_given_asset(tmp_path):
    """显式指定的那份素材要真的被用上。"""
    asset = _solid(tmp_path / "other.png", (10, 20, 30, 255))
    original = character.STATIC_IMAGE
    try:
        assert character.use_image(asset) is True
        assert character.STATIC_IMAGE == asset
    finally:
        character.STATIC_IMAGE = original


def test_use_image_refuses_a_missing_file(tmp_path):
    """指错了就报「指错了」，不能悄悄退回默认那份。

    退回默认 = 拿带铭牌的形象出片，胸口那枚 growdu 还在，
    而片子发出去就收不回来了。
    """
    original = character.STATIC_IMAGE
    try:
        assert character.use_image(tmp_path / "nope.png") is False
        assert character.STATIC_IMAGE == original
    finally:
        character.STATIC_IMAGE = original


def test_the_mascot_reloads_after_the_asset_is_switched(tmp_path):
    """换素材后，已经加载过的形象必须重载——否则画面里还是旧的那张。"""
    first = _solid(tmp_path / "a.png", (200, 30, 30, 255))
    second = _solid(tmp_path / "b.png", (30, 200, 30, 255))
    original = character.STATIC_IMAGE
    try:
        character.use_image(first)
        mascot = character.Mascot()
        mascot.draw(cairo.Context(cairo.ImageSurface(
            cairo.FORMAT_ARGB32, 320, 180)), (160.0, 170.0), 120.0)
        before = bytes(mascot._surface.get_data())

        character.use_image(second)
        mascot.draw(cairo.Context(cairo.ImageSurface(
            cairo.FORMAT_ARGB32, 320, 180)), (160.0, 170.0), 120.0)
        after = bytes(mascot._surface.get_data())

        assert before != after, "换素材后形象没重载，画面里还是旧的那张"
    finally:
        character.STATIC_IMAGE = original


def test_render_refuses_a_missing_character_asset(tmp_path, capsys):
    """命令行指错了素材要干净地报错，不能出片。"""
    from pyv import cli

    code = cli.main(["render", "--storyboard", str(tmp_path / "sb.json"),
                     "--out", str(tmp_path / "out"),
                     "--character", str(tmp_path / "nope.png")])
    assert code == 1
    assert "形象素材不存在" in capsys.readouterr().err


def test_pil_to_cairo_keeps_rgba_order():
    """BGRA 字节序弄错会让整个形象偏色。"""
    from PIL import Image

    image = Image.new("RGBA", (2, 1), (10, 20, 30, 255))
    surface = character.pil_to_cairo(image)
    data = bytes(surface.get_data())
    blue, green, red, alpha = data[0], data[1], data[2], data[3]
    assert (red, green, blue, alpha) == (10, 20, 30, 255)
