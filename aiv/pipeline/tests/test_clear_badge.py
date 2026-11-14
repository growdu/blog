"""胸口铭牌抹除测试（character/scripts/clear_badge.py）。

**最要紧的一条是「产出必须真的跟原图不一样」。**

抹铭牌的脚本曾经是空操作：羽化的 alpha 算错，全被 clip 成 0，
产出跟原图**逐字节相同**，却照样打印「已抹成马甲色」。空操作比报错
难发现得多——画面里那个白铭牌还在，肉眼要凑近才看得见，
而文件在、命令成功、素材「已生成」。所以这里钉死两件事：

1. 改动像素数必须大于 0（不是空操作）
2. 铭牌检测器在产出上必须**找不到**铭牌（不是「抹得不太干净」）
"""
import importlib.util
import sys

import numpy as np
import pytest

from pyv import character


def _module():
    """加载 character/scripts/clear_badge.py（不在 pipeline 包内，按路径载入）。"""
    path = character.AIV_ROOT / "character" / "scripts" / "clear_badge.py"
    spec = importlib.util.spec_from_file_location("clear_badge", path)
    module = importlib.util.module_from_spec(spec)
    # 必须先注册进 sys.modules：模块里 import 了 stamp_badge
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BADGED = character.AIV_ROOT / "character" / "growdu_character_2k_nobg.png"
CLEARED = character.AIV_ROOT / "character" / "growdu_character_2k_nobg_nobadge.png"


def _badge_box():
    """在带铭牌的那份素材上定位铭牌。"""
    from PIL import Image

    stamp = _stamp_badge_module()
    image = Image.open(BADGED).convert("RGBA")
    box = stamp.find_badge(image)
    assert box is not None, "带铭牌的素材上找不到铭牌——素材本身不对"
    return box


def _stamp_badge_module():
    path = character.AIV_ROOT / "character" / "scripts" / "stamp_badge.py"
    spec = importlib.util.spec_from_file_location("stamp_badge", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _rgb(path):
    from PIL import Image

    return np.array(Image.open(path).convert("RGB")).astype(int)


# --- 产出必须真的变了 -------------------------------------------------------


def test_the_cleared_asset_really_differs_from_the_source():
    """**空操作守卫。** 产出跟原图一模一样等于没抹。

    这条是本文件存在的理由：脚本曾经把内框坐标写成相对偏移，
    distance 算成几千、alpha 全成 0，产出与原图逐字节相同。
    """
    assert BADGED.is_file(), f"本机没有带铭牌的素材 {BADGED}"
    assert CLEARED.is_file(), f"本机没有无标牌素材 {CLEARED}"

    source = _rgb(BADGED)
    cleared = _rgb(CLEARED)
    assert source.shape == cleared.shape

    changed = int((np.abs(source - cleared).sum(axis=2) > 12).sum())
    assert changed > 1000, (
        f"改动像素只有 {changed} 个——脚本没真抹（空操作），"
        f"而画面里那个白铭牌还在"
    )


def test_the_badge_detector_finds_nothing_in_the_cleared_asset():
    """抹完之后，铭牌检测器必须找不到铭牌。

    这是「抹干净了」最直接的判据：不只是没有白像素，
    而是整块区域不再构成一枚铭牌。
    """
    if not CLEARED.is_file():
        pytest.skip(f"本机没有无标牌素材 {CLEARED}")

    from PIL import Image

    stamp = _stamp_badge_module()
    image = Image.open(CLEARED).convert("RGBA")
    assert stamp.find_badge(image) is None, "无标牌素材里还能检出铭牌"


def test_no_bright_pixels_are_left_in_the_badge_area():
    """铭牌那块不能还留着白色铭牌或白色描边。"""
    if not CLEARED.is_file():
        pytest.skip(f"本机没有无标牌素材 {CLEARED}")

    x0, y0, x1, y1 = _badge_box()
    cleared = _rgb(CLEARED)
    region = cleared[y0:y1, x0:x1]
    bright = int(((region[..., 0] > 200) & (region[..., 1] > 200) &
                  (region[..., 2] > 200)).sum())
    assert bright == 0, f"铭牌区里还剩 {bright} 个白色像素"


def test_the_filled_area_looks_like_the_vest():
    """填进去的必须是马甲色（深藏蓝），不能是白的、也不能是别的东西。"""
    if not CLEARED.is_file():
        pytest.skip(f"本机没有无标牌素材 {CLEARED}")

    x0, y0, x1, y1 = _badge_box()
    cleared = _rgb(CLEARED)
    region = cleared[y0:y1, x0:x1]
    mean = region.reshape(-1, 3).mean(axis=0)
    assert mean[2] > mean[0], f"填的不是深藏蓝（平均 RGB {tuple(mean.round(1))}）"
    assert mean.mean() < 90, f"填完太亮了（平均 RGB {tuple(mean.round(1))}）"


def test_the_source_asset_still_has_its_badge():
    """源素材必须还带着铭牌——否则上面的测试都是在拿空气比。

    这条也守住「无标牌素材是派生物，不是源」：源被抹了，
    再生成就抹不出东西来了。
    """
    if not BADGED.is_file():
        pytest.skip(f"本机没有带铭牌的素材 {BADGED}")

    x0, y0, x1, y1 = _badge_box()
    source = _rgb(BADGED)
    region = source[y0:y1, x0:x1]
    bright = int(((region[..., 0] > 200) & (region[..., 1] > 200) &
                  (region[..., 2] > 200)).sum())
    assert bright > 1000, "源素材上的铭牌没了——源被误改了"


# --- 脚本行为 ---------------------------------------------------------------


def test_clearing_a_missing_file_returns_none(tmp_path):
    module = _module()
    assert module.clear_badge(tmp_path / "nope.png") is None


def test_clearing_an_image_without_a_badge_returns_none(tmp_path):
    """没铭牌的图不能瞎抹——否则会平白弄脏一块马甲。"""
    from PIL import Image

    module = _module()
    plain = tmp_path / "plain.png"
    Image.new("RGBA", (512, 512), (30, 50, 90, 255)).save(plain)
    assert module.clear_badge(plain, tmp_path / "out.png") is None


def test_clearing_is_deterministic(tmp_path):
    """同样的输入必须产出同样的字节——素材要入库，就得可复现。"""
    if not BADGED.is_file():
        pytest.skip(f"本机没有带铭牌的素材 {BADGED}")

    module = _module()
    first = module.clear_badge(BADGED, tmp_path / "a.png")
    second = module.clear_badge(BADGED, tmp_path / "b.png")
    assert first.is_file() and second.is_file()
    assert first.read_bytes() == second.read_bytes(), "同样的输入产出了不同的文件"
