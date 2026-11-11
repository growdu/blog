"""胸口铭牌擦白测试（character/scripts/blank_badge.py）。"""
import importlib.util

from pyv import character


def _blank_badge_module():
    """加载 character/scripts/blank_badge.py（不在 pipeline 包内，按路径载入）。"""
    path = character.AIV_ROOT / "character" / "scripts" / "blank_badge.py"
    spec = importlib.util.spec_from_file_location("blank_badge", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _badge_fixture():
    """造一张「深藏蓝马甲 + 白色铭牌 + 黑色假文字」的图。"""
    from PIL import Image

    image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    vest = Image.new("RGBA", (512, 512), (30, 50, 90, 255))
    image.paste(vest.crop((100, 150, 400, 350)), (100, 150))
    badge = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    for x in range(160, 200):
        for y in range(190, 208):
            badge.putpixel((x, y), (255, 255, 255, 255))
    image.paste(badge, (0, 0), badge)
    text = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    for x in range(168, 192):
        for y in range(196, 202):
            text.putpixel((x, y), (0, 0, 0, 255))
    image.paste(text, (0, 0), text)
    return image


def test_find_badge_locates_the_white_rectangle():
    """铭牌 = 被深藏蓝马甲围住的那块白，必须能自动定位。"""
    module = _blank_badge_module()
    box = module.find_badge(_badge_fixture())
    assert box is not None
    x0, y0, x1, y1 = box
    assert x0 == 160 and x1 == 200
    assert y0 == 190 and y1 == 208


def test_find_badge_returns_none_without_a_badge():
    module = _blank_badge_module()
    from PIL import Image

    plain = Image.new("RGBA", (512, 512), (30, 50, 90, 255))
    assert module.find_badge(plain) is None


def test_blank_badge_erases_model_text(tmp_path):
    """模型写在铭牌上的字必须被刷成纯白（模型生成的文字一律不可信）。"""
    module = _blank_badge_module()
    path = tmp_path / "character.png"
    _badge_fixture().save(path)

    assert module.blank_badge(path) is True

    from PIL import Image

    image = Image.open(path).convert("RGBA")
    # 铭牌范围内全部是纯白
    for x in range(160, 200):
        for y in range(190, 208):
            assert image.getpixel((x, y))[:3] == (255, 255, 255), (x, y)
    # 马甲没被动过
    assert image.getpixel((120, 160))[:3] == (30, 50, 90)


def test_blank_badge_is_idempotent(tmp_path):
    """刷过一次之后再刷，不应该报错也不应该改变结果。"""
    module = _blank_badge_module()
    path = tmp_path / "character.png"
    _badge_fixture().save(path)

    module.blank_badge(path)
    first = path.read_bytes()
    module.blank_badge(path)
    assert path.read_bytes() == first
