import random

import pytest
from PIL import Image, ImageDraw

from toutiao.assets import (
    AssetNotFound, ImageTooLarge, RemoteAsset, UnreadableImage,
    can_make_cover, is_remote, make_cover, prepare_image, resolve_asset,
)


def _image(path, size, color=(120, 160, 200)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, "PNG")
    return path


def _noise(path, size):
    """An image that does not compress -- the only way to force a shrink."""
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = random.Random(0).randbytes(size[0] * size[1] * 3)
    Image.frombytes("RGB", size, blob).save(path, "PNG")
    return path


def _transparent(path, size=(200, 120)):
    """An RGBA picture: the top half opaque blue, the bottom half clear.

    The bottom half is what a white-background diagram looks like with the
    margins knocked out -- in the browser those pixels show as white.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, size[0], size[1] // 2], fill=(10, 20, 200, 255))
    image.save(path, "PNG")
    return path


def test_is_remote_tells_urls_from_paths():
    assert is_remote("https://example.com/a.png") is True
    assert is_remote("http://example.com/a.png") is True
    assert is_remote("images/a.png") is False


def test_resolve_asset_resolves_against_the_site_root(tmp_path):
    site = tmp_path / "source"
    target = site / "images" / "a.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x")
    posts = site / "_posts"
    posts.mkdir()
    assert resolve_asset("images/a.png", posts) == target.resolve()


def test_resolve_asset_keeps_absolute_paths(tmp_path):
    target = tmp_path / "b.png"
    target.write_bytes(b"x")
    assert resolve_asset(str(target), tmp_path / "posts") == target.resolve()


def test_resolve_asset_refuses_a_remote_url(tmp_path):
    """外链图不下载 —— 出包不能依赖网络。"""
    with pytest.raises(RemoteAsset):
        resolve_asset("https://example.com/a.png", tmp_path / "posts")


def test_resolve_asset_says_which_path_is_missing(tmp_path):
    """找不到图要说清是哪个路径，不能静默返回一个相对路径。"""
    posts = tmp_path / "source" / "_posts"
    posts.mkdir(parents=True)
    with pytest.raises(AssetNotFound) as error:
        resolve_asset("images/nope.png", posts)
    assert "images/nope.png" in str(error.value)


def test_resolve_asset_refuses_a_path_outside_the_site_root(tmp_path):
    """图路径是站点里的相对路径，不是出站的路。"""
    site = tmp_path / "source"
    posts = site / "_posts"
    posts.mkdir(parents=True)
    outside = tmp_path / "secret.png"
    outside.write_bytes(b"x")
    with pytest.raises(AssetNotFound):
        resolve_asset(str(outside), posts)


def test_prepare_image_writes_webp_under_the_limit(tmp_path):
    src = _image(tmp_path / "in.png", (1600, 1200))
    dst = tmp_path / "out" / "01.webp"
    result = prepare_image(src, dst, max_bytes=5242880)
    assert dst.is_file()
    assert dst.suffix == ".webp"
    assert result.size_bytes == dst.stat().st_size
    assert result.size_bytes <= 5242880
    assert (result.width, result.height) == (1600, 1200)


def test_prepare_image_shrinks_a_huge_image(tmp_path):
    src = _image(tmp_path / "big.png", (3000, 2400))
    dst = tmp_path / "out" / "01.webp"
    result = prepare_image(src, dst, max_bytes=60_000)
    assert result.size_bytes <= 60_000


def test_prepare_image_raises_when_it_cannot_fit(tmp_path):
    src = _image(tmp_path / "big.png", (4000, 3000))
    with pytest.raises(ImageTooLarge):
        prepare_image(src, tmp_path / "out" / "01.webp", max_bytes=512)


def test_can_make_cover_requires_both_minimums(tmp_path):
    ok = _image(tmp_path / "ok.png", (1200, 900))
    small = _image(tmp_path / "small.png", (400, 300))
    assert can_make_cover(ok, "3:4", (600, 800)) is True
    assert can_make_cover(small, "3:4", (600, 800)) is False


def test_make_cover_crops_to_the_ratio(tmp_path):
    src = _image(tmp_path / "wide.png", (1200, 900))
    dst = tmp_path / "out" / "cover.webp"
    result = make_cover(src, dst, "3:4", (600, 800))
    assert dst.is_file()
    assert result.width * 4 == result.height * 3
    assert result.width >= 600 and result.height >= 800


def test_make_cover_crops_a_tall_image_too(tmp_path):
    src = _image(tmp_path / "tall.png", (900, 1600))
    dst = tmp_path / "out" / "cover.webp"
    result = make_cover(src, dst, "3:4", (600, 800))
    assert result.width * 4 == result.height * 3


def test_make_cover_refuses_to_produce_a_cover_below_the_minimum(tmp_path):
    """3:4 的裁切会让图变小 —— 裁完不够下限的就不是封面。"""
    src = _image(tmp_path / "small.png", (800, 600))
    dst = tmp_path / "out" / "cover.webp"
    with pytest.raises(ValueError):
        make_cover(src, dst, "3:4", (600, 800))


# --- 以下是评审版用例之外的补充 ------------------------------------------------
#
# 补的每一条都对应一个「评审版代码块没覆盖、但实现必须成立」的行为：
# 裁切比例必须精确、两个封面函数必须用同一把尺子、报错时不能留下超限产物、
# 三种异常不能混成一个、以及外链图判定对大小写不敏感。


def test_make_cover_keeps_the_exact_ratio_when_the_size_does_not_divide(tmp_path):
    """裁出来的尺寸必须是比例的整数倍 —— 凑整会留下 399:400 这种比例。"""
    src = _image(tmp_path / "odd.png", (100, 333))
    dst = tmp_path / "out" / "cover.webp"
    result = make_cover(src, dst, "3:4", (60, 80))
    assert result.width * 4 == result.height * 3


def test_can_make_cover_and_make_cover_use_the_same_ruler(tmp_path):
    """能裁就不能说不能，不能裁就得报错 —— 两个函数不能各说各话。"""
    cases = [((1200, 900), True), ((900, 1600), True), ((640, 960), True),
             ((800, 600), False), ((400, 300), False)]
    for size, expected in cases:
        src = _image(tmp_path / "s-{}-{}.png".format(*size), size)
        assert can_make_cover(src, "3:4", (600, 800)) is expected
        dst = tmp_path / "out" / "c-{}-{}.webp".format(*size)
        if expected:
            assert make_cover(src, dst, "3:4", (600, 800)).width >= 600
        else:
            with pytest.raises(ValueError):
                make_cover(src, dst, "3:4", (600, 800))


def test_can_make_cover_checks_the_height_minimum_too(tmp_path):
    """两个下限都要过 —— 宽度够了不等于高度也够。

    3:4 的裁切里两个下限是等价的（比例相同），所以这一条要用别的比例
    才问得出「只查宽度」和「拿原图尺寸当裁后尺寸」这两种错法。
    """
    square = _image(tmp_path / "square.png", (700, 700))
    tall = _image(tmp_path / "tall.png", (700, 900))
    big = _image(tmp_path / "big.png", (900, 900))
    assert can_make_cover(square, "1:1", (600, 800)) is False
    assert can_make_cover(tall, "1:1", (600, 800)) is False
    assert can_make_cover(big, "1:1", (600, 800)) is True
    for src in (square, tall):
        with pytest.raises(ValueError):
            make_cover(src, tmp_path / "out" / "square.webp", "1:1", (600, 800))


def test_prepare_image_leaves_no_oversized_file_behind(tmp_path):
    """报错时不能把一个超限的图留在出包目录里。"""
    src = _image(tmp_path / "big.png", (4000, 3000))
    dst = tmp_path / "out" / "01.webp"
    with pytest.raises(ImageTooLarge):
        prepare_image(src, dst, max_bytes=512)
    assert not dst.exists()


def test_prepare_image_reports_the_size_it_actually_wrote(tmp_path):
    """报出来的尺寸得是真正写下去的那个 —— 缩放过就不能再报原图的。"""
    src = _noise(tmp_path / "noise.png", (600, 480))
    dst = tmp_path / "out" / "01.webp"
    result = prepare_image(src, dst, max_bytes=60_000)
    with Image.open(dst) as written:
        assert (result.width, result.height) == written.size
    assert result.width < 600


def test_the_asset_errors_are_separate_kinds_of_problem():
    """尺寸压不下去和路径解析不了是两回事，不能混成一个异常。"""
    assert not issubclass(ImageTooLarge, AssetNotFound)
    assert not issubclass(ImageTooLarge, RemoteAsset)
    assert not issubclass(AssetNotFound, RemoteAsset)
    for error in (ImageTooLarge, AssetNotFound, RemoteAsset):
        assert issubclass(error, ValueError)


def test_is_remote_does_not_care_about_case_or_padding():
    assert is_remote("  HTTPS://example.com/a.png  ") is True
    assert is_remote("Http://example.com/a.png") is True


# --- 读不了的格式 -----------------------------------------------------------
#
# Pillow 读不了的格式（真实语料里就有一张 SVG）会让裸的
# UnidentifiedImageError 漏出去 —— 出包时那一张图就会把整包带崩。
# 所以它有自己的异常：调用方要能分辨「这个文件不是我能转的格式」
# 和「这个文件我转不动（压不进 5MB）」。


def test_prepare_image_raises_unreadable_for_a_format_pillow_cannot_read(tmp_path):
    """SVG 之类 Pillow 读不了的格式要报成专用异常，不是裸的底层异常。"""
    src = tmp_path / "logo.svg"
    src.write_text("<svg></svg>", encoding="utf-8")
    dst = tmp_path / "out" / "01.webp"
    with pytest.raises(UnreadableImage) as error:
        prepare_image(src, dst, max_bytes=5242880)
    assert "logo.svg" in str(error.value)
    assert "SVG" in str(error.value)
    # 底层那个异常不能漏出去 —— 它不是 ValueError，出包时接不住。
    assert not isinstance(error.value, OSError)
    assert not (dst).exists()


def test_prepare_image_raises_unreadable_for_a_file_that_is_not_an_image(tmp_path):
    """后缀是 .png 但内容不是图 —— 一样是「读不了」，不是「转不动」。"""
    src = tmp_path / "broken.png"
    src.write_bytes(b"this is not an image at all")
    with pytest.raises(UnreadableImage):
        prepare_image(src, tmp_path / "out" / "01.webp", max_bytes=5242880)


def test_unreadable_image_is_its_own_kind_of_problem():
    """「读不了」与「转不动」「路径解析不了」是三件事。"""
    assert issubclass(UnreadableImage, ValueError)
    assert not issubclass(UnreadableImage, ImageTooLarge)
    assert not issubclass(UnreadableImage, AssetNotFound)
    assert not issubclass(UnreadableImage, RemoteAsset)


def test_prepare_image_does_not_call_a_missing_file_an_unreadable_one(tmp_path):
    """文件根本不在，不该被当成「读不了的图」——那是两回事。"""
    with pytest.raises(FileNotFoundError):
        prepare_image(tmp_path / "nope.png", tmp_path / "out" / "01.webp", max_bytes=5242880)


# --- 透明像素 ---------------------------------------------------------------
#
# ``convert("RGB")`` 是**丢弃** alpha，不是合成到背景：透明像素保留自己那点
# 几乎全黑的原色，图就变成黑底。真实语料里有两张白底示意图带真透明像素，
# 丢完 alpha，深色标注变成黑底上的深色，看不清。


def test_prepare_image_composes_transparency_onto_white(tmp_path):
    """透明区域要合成成白底，不是黑底 —— 博客页面上它们本来就是白的。"""
    src = _transparent(tmp_path / "alpha.png", (200, 120))
    dst = tmp_path / "out" / "01.webp"
    prepare_image(src, dst, max_bytes=5242880)
    with Image.open(dst) as written:
        assert written.mode == "RGB"
        # 下半截本来是全透明的：合成后必须是白
        assert written.getpixel((100, 100)) == (255, 255, 255)
        # 上半截是不透明的蓝：要原样留下（webp 有损，留一点余量）
        blue = written.getpixel((100, 10))
        assert all(abs(a - b) <= 5 for a, b in zip(blue, (10, 20, 200))), blue


def test_prepare_image_leaves_a_plain_rgb_picture_alone(tmp_path):
    """没有 alpha 的图不受影响 —— 合成白底对不透明图是空操作。"""
    src = _image(tmp_path / "plain.png", (200, 120), (10, 20, 200))
    dst = tmp_path / "out" / "01.webp"
    prepare_image(src, dst, max_bytes=5242880)
    with Image.open(dst) as written:
        pixel = written.getpixel((100, 60))
        assert all(abs(a - b) <= 5 for a, b in zip(pixel, (10, 20, 200))), pixel


def test_make_cover_composes_transparency_onto_white(tmp_path):
    """封面走同一套合成 —— 裁完也不能是黑底。"""
    src = _transparent(tmp_path / "alpha.png", (1200, 900))
    dst = tmp_path / "out" / "cover.webp"
    result = make_cover(src, dst, "3:4", (600, 800))
    with Image.open(dst) as written:
        assert written.mode == "RGB"
        # 3:4 的裁切保住整幅高度，透明的下半截仍在下半截
        bottom = written.getpixel((result.width // 2, result.height - 5))
        assert all(value >= 250 for value in bottom), bottom


def test_the_cover_functions_refuse_a_file_that_is_not_an_image(tmp_path):
    """与 prepare_image 同一个异常口径 —— 不漏出裸的 UnidentifiedImageError。"""
    src = tmp_path / "logo.svg"
    src.write_text("<svg></svg>", encoding="utf-8")
    with pytest.raises(UnreadableImage):
        can_make_cover(src, "3:4", (600, 800))
    with pytest.raises(UnreadableImage):
        make_cover(src, tmp_path / "out" / "cover.webp", "3:4", (600, 800))


def test_the_cover_decision_follows_the_shrunk_webp(tmp_path):
    """压不进上限时 prepare_image 把图缩一半 —— 裁切判定必须跟着 webp 走。

    原图 1200×900 裁 3:4 是 675×900（合规）；缩半后 600×450 裁 3:4 是
    336×448（不合规）。「原图能裁」不等于「webp 能裁」——这条锁住
    这个前提，Task 6 的判定才必须拿 webp 判。
    """
    src = _image(tmp_path / "wide.png", (1200, 900))
    dst = tmp_path / "out" / "01.webp"
    result = prepare_image(src, dst, max_bytes=800)
    assert can_make_cover(src, "3:4", (600, 800)) is True
    assert can_make_cover(result.path, "3:4", (600, 800)) is False
