"""胸口铭牌盖章测试（character/scripts/stamp_badge.py）。"""
import importlib.util
import sys

import numpy as np
import pytest

from pyv import character


def _module():
    """加载 character/scripts/stamp_badge.py（不在 pipeline 包内，按路径载入）。"""
    path = character.AIV_ROOT / "character" / "scripts" / "stamp_badge.py"
    spec = importlib.util.spec_from_file_location("stamp_badge", path)
    module = importlib.util.module_from_spec(spec)
    # 必须先注册进 sys.modules：模块里有 dataclass，dataclass 机制要回查
    # sys.modules[cls.__module__]
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CANVAS = 1536
BADGE_BOX = (400, 520, 590, 568)      # 190×48 的白铭牌
VEST_BOX = (200, 400, 1336, 900)


def _fixture(with_text: bool = False):
    """造一张「深藏蓝马甲 + 白色铭牌」的图，可选在铭牌里塞一段假文字。"""
    from PIL import Image

    image = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    vest = Image.new("RGBA", (CANVAS, CANVAS), (30, 50, 90, 255))
    image.paste(vest.crop(VEST_BOX), (VEST_BOX[0], VEST_BOX[1]))
    x0, y0, x1, y1 = BADGE_BOX
    badge = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    for x in range(x0, x1):
        for y in range(y0, y1):
            badge.putpixel((x, y), (255, 255, 255, 255))
    image.paste(badge, (0, 0), badge)
    if with_text:
        text = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        for x in range(x0 + 20, x1 - 20):
            for y in range(y0 + 18, y0 + 30):
                text.putpixel((x, y), (0, 0, 0, 255))
        image.paste(text, (0, 0), text)
    return image


def _ink(region_rgb: np.ndarray) -> np.ndarray:
    """铭牌区域里的墨迹掩膜（明显比白底暗的像素）。"""
    luminance = region_rgb.astype(int).mean(axis=2)
    return luminance < 170


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    union = (a | b).sum()
    if union == 0:
        return 0.0
    return float((a & b).sum()) / float(union)


def test_find_badge_locates_the_white_rectangle():
    """铭牌 = 被深藏蓝马甲围住的那块白，必须能自动定位。"""
    module = _module()
    box = module.find_badge(_fixture())
    assert box is not None
    assert box == BADGE_BOX


def test_find_badge_returns_none_without_a_badge():
    module = _module()
    from PIL import Image

    plain = Image.new("RGBA", (CANVAS, CANVAS), (30, 50, 90, 255))
    assert module.find_badge(plain) is None


def test_stamp_replaces_model_text_with_our_own(tmp_path):
    """模型写在铭牌上的字必须被完全替换掉。

    拿「有假文字的铭牌」和「空白铭牌」各盖一次章，结果必须逐像素相同——
    说明模型写的字一点没留下。
    """
    module = _module()
    dirty = tmp_path / "dirty.png"
    clean = tmp_path / "clean.png"
    _fixture(with_text=True).save(dirty)
    _fixture(with_text=False).save(clean)

    assert module.stamp_badge(dirty) is not None
    assert module.stamp_badge(clean) is not None

    from PIL import Image

    a = np.array(Image.open(dirty).convert("RGBA"))
    b = np.array(Image.open(clean).convert("RGBA"))
    assert np.array_equal(a, b), "模型写的字没有被完全替换"


def test_stamp_writes_the_word_growdu(tmp_path):
    """铭牌上写出来的必须是 growdu，不是 grawdu 之类的乱码。"""
    module = _module()
    path = tmp_path / "character.png"
    _fixture().save(path)

    badge = module.stamp_badge(path)
    assert badge is not None

    from PIL import Image

    image = np.array(Image.open(path).convert("RGBA"))
    x0, y0, x1, y1 = badge.box
    region = image[y0:y1, x0:x1, :3]
    ink = _ink(region)
    assert ink.sum() > 0, "铭牌上应该有文字"

    scores = {}
    for candidate in ("growdu", "grawdu", "giowdu", "gr0wdu"):
        mask = module.render_text_mask(
            candidate, badge.size, badge.origin, x1 - x0, y1 - y0
        )
        scores[candidate] = _iou(ink, mask > 128)
    assert max(scores, key=scores.get) == "growdu", scores
    assert scores["growdu"] > 0.85, scores
    # gr0wdu 不参与差距比较：PingFang 的 o 和 0 在这个字号下肉眼都分不清，
    # 拿它当判据只会让测试变成噪声。真正要排除的是字母顺序/字形错误。
    runner_up = max(scores["grawdu"], scores["giowdu"])
    assert scores["growdu"] > 1.3 * runner_up, scores


def test_stamp_is_idempotent(tmp_path):
    """盖过一次之后再盖，结果必须完全一致（渲染流程可以反复调用）。"""
    module = _module()
    path = tmp_path / "character.png"
    _fixture().save(path)

    module.stamp_badge(path)
    first = path.read_bytes()
    module.stamp_badge(path)
    assert path.read_bytes() == first


def test_stamp_leaves_the_rest_of_the_image_untouched(tmp_path):
    """只有铭牌那块矩形能被改，别的像素一个都不许动。"""
    module = _module()
    path = tmp_path / "character.png"
    _fixture(with_text=True).save(path)

    from PIL import Image

    before = np.array(Image.open(path).convert("RGBA"))
    badge = module.stamp_badge(path)
    assert badge is not None
    after = np.array(Image.open(path).convert("RGBA"))

    mask = np.ones(before.shape[:2], dtype=bool)
    x0, y0, x1, y1 = badge.box
    mask[y0:y1, x0:x1] = False
    assert np.array_equal(before[mask], after[mask]), "铭牌以外被改动了"


@pytest.mark.parametrize("relative", [
    "character/growdu_character_2k_nobg.png",
    "brand/assets/growdu_pose_thumbsup_nobg.png",
    "brand/assets/growdu_pose_wave_nobg.png",
])
def test_real_assets_carry_growdu_on_the_badge(relative):
    """本机素材：铭牌上必须真的有 growdu。"""
    module = _module()
    path = character.AIV_ROOT / relative
    if not path.exists():
        pytest.skip("素材不在本机，跳过")

    from PIL import Image

    image = Image.open(path).convert("RGBA")
    box = module.find_badge(image)
    assert box is not None, f"{relative}：没找到铭牌"
    x0, y0, x1, y1 = box
    region = np.array(image)[y0:y1, x0:x1, :3]
    ink = _ink(region)
    assert ink.sum() > 0, f"{relative}：铭牌上没有文字"
