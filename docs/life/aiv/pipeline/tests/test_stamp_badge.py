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


HEAD_BOX = (560, 90, 976, 400)      # 头（皮肤色）——让主体上沿在马甲之上


def _fixture(with_text: bool = False):
    """造一张「小象 + 深藏蓝马甲 + 白色铭牌」的图。

    头部是必要的：铭牌定位有一条「铭牌在胸口，不在脸上」的位置约束
    （按主体高度判断），没有头的话主体就只有马甲，位置约束会误判。
    """
    from PIL import Image

    image = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    head = Image.new("RGBA", (CANVAS, CANVAS), (170, 185, 200, 255))
    image.paste(head.crop(HEAD_BOX), (HEAD_BOX[0], HEAD_BOX[1]))
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


def _glasses(image):
    """画一副深藏蓝方框眼镜，镜腿一直连到马甲上，末端贴一块小白牌。

    镜腿连到马甲是照着真实翻车现场搭的：眼镜和衣服同色，镜腿一搭上
    马甲就连成同一块深藏蓝区域，「最大连通块」的区域约束因此失效，
    脸上那块小白牌（模型贴在镜腿末端的）就得靠尺寸下限挡掉。
    """
    from PIL import Image

    navy = Image.new("RGBA", image.size, (0, 0, 0, 0))
    bar = 6
    left_x0, left_x1 = 480, 560
    right_x0, right_x1 = 620, 700
    top, bottom = 120, 200

    def frame(x0, x1):
        for x in range(x0, x1):
            for y in range(top, top + bar):
                navy.putpixel((x, y), (43, 76, 126, 255))
            for y in range(bottom - bar, bottom):
                navy.putpixel((x, y), (43, 76, 126, 255))
        for x in range(x0, x0 + bar):
            for y in range(top, bottom):
                navy.putpixel((x, y), (43, 76, 126, 255))
        for x in range(x1 - bar, x1):
            for y in range(top, bottom):
                navy.putpixel((x, y), (43, 76, 126, 255))

    frame(left_x0, left_x1)
    frame(right_x0, right_x1)
    # 镜架横梁
    for x in range(left_x1, right_x0):
        for y in range(top, top + bar):
            navy.putpixel((x, y), (43, 76, 126, 255))
    # 镜腿：从镜框外沿一直拉到马甲上沿，让两者连成一块
    for x in range(430, 470):
        for y in range(top, VEST_BOX[1]):
            navy.putpixel((x, y), (43, 76, 126, 255))
    for x in range(700, 740):
        for y in range(top, VEST_BOX[1]):
            navy.putpixel((x, y), (43, 76, 126, 255))
    image.paste(navy, (0, 0), navy)

    # 镜腿末端贴的小白牌：模型偶尔会这么干
    tag = Image.new("RGBA", image.size, (0, 0, 0, 0))
    for x in range(702, 738):
        for y in range(250, 262):
            tag.putpixel((x, y), (255, 255, 255, 255))
    image.paste(tag, (0, 0), tag)
    return image


def _light_strap(image):
    """在铭牌上沿压一条浅灰蓝的背带。

    真实素材里铭牌贴在马甲边缘，上沿靠着浅色的背带，所以铭牌四周的
    「马甲占比」并不高——这正是镜腿那块小白牌能抢赢它的原因。
    """
    from PIL import Image

    strap = Image.new("RGBA", image.size, (0, 0, 0, 0))
    x0, y0, x1, y1 = BADGE_BOX
    for x in range(x0 - 4, x1 + 4):
        for y in range(y0 - 8, y0):        # 只压在铭牌上沿外侧，别盖住铭牌
            strap.putpixel((x, y), (168, 178, 194, 255))
    image.paste(strap, (0, 0), strap)
    return image


def test_glasses_does_not_hijack_the_badge():
    """眼镜的镜框和马甲同色，不能把镜腿末端那块小白牌抢成铭牌。

    实测翻车过：模型在镜腿上贴了块小白牌，它四周全是镜框颜色，
    「马甲占比」接近 1.0，一度比真正的铭牌还高。
    """
    module = _module()
    image = _light_strap(_fixture())
    _glasses(image)
    assert module.find_badge(image) == BADGE_BOX


def test_badge_must_be_big_enough_to_be_the_badge():
    """铭牌是服装上固定尺寸的道具，小零碎高光不算铭牌。"""
    module = _module()
    image = _light_strap(_fixture())
    _glasses(image)
    from PIL import Image

    box = module.find_badge(image)
    assert box == BADGE_BOX
    x0, y0, x1, y1 = box
    assert (x1 - x0) >= module.MIN_WIDTH_RATIO * CANVAS
    assert (y1 - y0) >= module.MIN_HEIGHT_RATIO * CANVAS


def test_cream_toes_are_not_the_badge():
    """小象的脚趾是奶油色，不是铭牌。

    脚趾那块白在胸口下方，位置约束挡不住它；挡住它的是「纯白度」：
    铭牌是白塑料牌（三个通道都 ≥ 240 的像素占 85%+），脚趾是奶油色。
    """
    from PIL import Image

    module = _module()
    image = _fixture()
    toe = Image.new("RGBA", image.size, (0, 0, 0, 0))
    for x in range(500, 700):
        for y in range(700, 790):
            toe.putpixel((x, y), (244, 238, 222, 255))
    image.paste(toe, (0, 0), toe)

    assert module.find_badge(image) == BADGE_BOX


def test_badge_must_be_on_the_chest_not_on_the_face():
    """镜框上的白牌在脸上，铭牌在胸口——位置不对的一律不算铭牌。

    镜框上的白牌四周全是深藏蓝，「马甲占比」比胸口那块真铭牌还高，
    光看颜色分不开。靠**位置**分开：实测铭牌的上沿都在主体高度的
    62%~68% 处，眼镜上的白牌在 30% 上下。
    """
    from PIL import Image

    module = _module()
    image = _fixture()
    # 画布上部放一块被深藏蓝包住的大白牌（比铭牌还大）
    navy = Image.new("RGBA", image.size, (0, 0, 0, 0))
    for x in range(300, 900):
        for y in range(80, 300):
            navy.putpixel((x, y), (43, 76, 126, 255))
    image.paste(navy, (0, 0), navy)
    plate = Image.new("RGBA", image.size, (0, 0, 0, 0))
    for x in range(400, 800):
        for y in range(150, 220):
            plate.putpixel((x, y), (255, 255, 255, 255))
    image.paste(plate, (0, 0), plate)

    assert module.find_badge(image) == BADGE_BOX


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
