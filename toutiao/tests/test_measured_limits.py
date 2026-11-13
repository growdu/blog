"""2026-11-13 实测出来的限额，adapter 这一侧必须照着执行。

契约层那边（``publish/tests/test_toutiao_limits.py``）钉的是「声明里的数」；
这一边钉的是「**用这个数切出来的东西**对不对」——声明改了、切法没跟上，
两边会各自绿，而发出去的封面仍然是竖的。

实测的三条结论在这里落地：

* 封面是**横图**（平台封面框 152×118 ≈ 1.29:1），不是竖的 3:4；
* 封面不得小于 452×352，平台建议大于 672×462；
* webp 能直接上传（面板虽只列 jpg/jpeg/png），所以图片格式这一栏不动。
"""

from pathlib import Path

from PIL import Image

from toutiao.assets import can_make_cover, make_cover
from toutiao.capability import default_capability_path, load_capability

REPO_ROOT = Path(__file__).resolve().parents[2]


def _image(path, size, color=(120, 160, 200)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, "PNG")
    return path


def _limits():
    return load_capability(default_capability_path()).limits


def test_the_real_declaration_holds_the_measured_values():
    """adapter 读到的是同一份实测值（契约层那边钉的是同一组数）。"""
    limits = _limits()

    assert limits.title_chars == 30
    assert limits.image_bytes == 20971520
    assert limits.image_formats == ("webp",)
    assert limits.cover_ratio == "452:352"
    assert limits.cover_min_pixels == (452, 352)


def test_a_cover_cut_with_the_real_ratio_is_landscape(tmp_path):
    """一张宽图按实测比例切出来，产物是横图，且清得掉平台的下限。

    2026-11-13 实测时用的是包里的 ``images/02.webp``（1620×1526）：
    按竖图切会得到 600×800 的窄条，按实测比例切得到 1356×1056——
    同一张图，两种切法差着一倍多的可用面积。
    """
    limits = _limits()
    src = _image(tmp_path / "wide.png", (1620, 1526))

    assert can_make_cover(src, limits.cover_ratio, limits.cover_min_pixels)

    result = make_cover(
        src, tmp_path / "cover.webp", limits.cover_ratio, limits.cover_min_pixels
    )

    assert result.width > result.height, "封面切成了竖图"
    target_width, target_height = (int(p) for p in limits.cover_ratio.split(":"))
    assert result.width * target_height == result.height * target_width, (
        "封面比例不是声明里的那个"
    )
    assert result.width >= limits.cover_min_pixels[0]
    assert result.height >= limits.cover_min_pixels[1]


def test_a_portrait_source_no_longer_produces_a_portrait_cover(tmp_path):
    """竖图当素材，切出来的仍然是横图。

    这正是实测推翻旧假设的那一版：包里的 ``cover.webp`` 当时是
    1143×1524（3:4 竖图），平台收下之后自己裁成 1143×890——
    上下各裁掉 317 像素。素材是竖的，产物也必须是横的。
    """
    limits = _limits()
    src = _image(tmp_path / "tall.png", (1143, 1524))

    result = make_cover(
        src, tmp_path / "cover.webp", limits.cover_ratio, limits.cover_min_pixels
    )

    assert result.width > result.height, "竖素材切出了竖封面"
    assert result.height <= 1524


def test_the_measured_minimum_is_enforced(tmp_path):
    """小于 452×352 的封面不能出——平台那句「不可小于」是会拦人的。"""
    limits = _limits()
    tiny = _image(tmp_path / "tiny.png", (400, 300))

    assert can_make_cover(tiny, limits.cover_ratio, limits.cover_min_pixels) is False
