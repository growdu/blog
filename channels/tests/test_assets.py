"""封面：从成片抽帧，做成视频号要的两个尺寸。"""

from PIL import Image

from channels import assets


def test_make_covers_writes_both_sizes(video, tmp_path):
    covers = assets.make_covers(video, 1.0, tmp_path)
    assert set(covers) == {"4x3", "3x4"}
    assert Image.open(covers["4x3"]).size == assets.COVER_4X3
    assert Image.open(covers["3x4"]).size == assets.COVER_3X4


def test_the_cover_sizes_match_the_platform_slots():
    """实测：分享卡片 4:3、个人主页卡片 3:4。改尺寸就是改平台规则。"""
    assert assets.COVER_4X3 == (1080, 810)
    assert assets.COVER_3X4 == (1080, 1440)


def test_the_vertical_cover_keeps_the_frame_in_the_middle(video, tmp_path):
    """竖版封面是「横屏画面放进竖框」，不是把画面裁成竖的。"""
    covers = assets.make_covers(video, 1.0, tmp_path)
    image = Image.open(covers["3x4"]).convert("RGB")
    width, height = image.size
    top = image.getpixel((width // 2, 10))
    middle = image.getpixel((width // 2, height // 2))
    assert top == (255, 255, 255), "上下应该是留白"
    assert middle != (255, 255, 255), "中间才是画面"


def test_the_cover_embeds_the_frame_without_stretching(video, tmp_path):
    """封面里嵌的是等比缩放的原画面——没有被拉伸变形。"""
    covers = assets.make_covers(video, 1.0, tmp_path)
    tall = Image.open(covers["3x4"]).convert("RGB")
    inner = assets.fit_inside(Image.open(covers["4x3"]).convert("RGB"), assets.COVER_3X4)
    top = (tall.height - inner.height) // 2
    embedded = tall.crop((0, top, inner.width, top + inner.height))
    assert _mean_abs_diff(embedded, inner) < 8


def test_fit_inside_never_upscales_beyond_the_box():
    from PIL import Image as PILImage

    source = PILImage.new("RGB", (1920, 1080))
    inner = assets.fit_inside(source, assets.COVER_4X3)
    assert inner.width <= assets.COVER_4X3[0]
    assert inner.height <= assets.COVER_4X3[1]
    # 比例不变
    assert abs(inner.width / inner.height - 1920 / 1080) < 0.01


def _mean_abs_diff(one: Image.Image, other: Image.Image) -> float:
    """两张图的平均像素差（抽样即可）。"""
    left, right = one.load(), other.load()
    total = 0
    count = 0
    for y in range(0, one.height, 8):
        for x in range(0, one.width, 8):
            total += sum(abs(left[x, y][i] - right[x, y][i]) for i in range(3))
            count += 3
    return total / max(count, 1)


def test_extract_frame_beyond_the_end_fails_loudly(video, tmp_path):
    """取帧点超出成片时长时，要报人话，而不是留下一个不存在的文件。"""
    import pytest

    with pytest.raises(RuntimeError):
        assets.extract_frame(video, 99.0, tmp_path / "frame.png")
