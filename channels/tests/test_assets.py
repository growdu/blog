"""封面：从成片抽帧，裁成两个尺寸。"""

from PIL import Image

from channels import assets


def test_make_covers_writes_both_sizes(video, tmp_path):
    covers = assets.make_covers(video, 1.0, tmp_path)
    assert set(covers) == {"16x9", "9x16"}
    assert Image.open(covers["16x9"]).size == assets.COVER_16X9
    assert Image.open(covers["9x16"]).size == assets.COVER_9X16


def test_the_vertical_cover_keeps_the_frame_in_the_middle(video, tmp_path):
    """竖框版是「横屏画面放进竖框」，不是把画面裁成竖的。"""
    covers = assets.make_covers(video, 1.0, tmp_path)
    image = Image.open(covers["9x16"]).convert("RGB")
    width, height = image.size
    top = image.getpixel((width // 2, 10))
    middle = image.getpixel((width // 2, height // 2))
    assert top == (255, 255, 255), "上下应该是留白"
    assert middle != (255, 255, 255), "中间才是画面"


def test_the_vertical_cover_embeds_the_wide_one(video, tmp_path):
    """竖框版里嵌的就是那张横版封面本身——没有被拉伸变形。"""
    covers = assets.make_covers(video, 1.0, tmp_path)
    wide = Image.open(covers["16x9"]).convert("RGB")
    tall = Image.open(covers["9x16"]).convert("RGB")
    top = (tall.height - wide.height) // 2
    embedded = tall.crop((0, top, wide.width, top + wide.height))
    assert _mean_abs_diff(embedded, wide) < 8


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
