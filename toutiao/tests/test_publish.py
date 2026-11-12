"""Tests for the Toutiao publish package and the status snapshot.

Two layers:

- unit tests: one situation each, checked against the package layout or
  the snapshot content;
- integration tests: a markdown mother post goes through
  ``load_post`` -> ``slice_post`` -> ``render`` -> ``write_package`` ->
  ``write_snapshot``, and what lands on disk is checked for real.

The mother posts are written into ``tmp_path`` -- never into
``source/_posts``, which is gitignored and absent from a clean checkout.
"""

import dataclasses
import json
import re

import pytest
from PIL import Image

from toutiao.assets import make_cover
from toutiao.capability import default_capability_path, load_capability
from toutiao.contract import ToutiaoArticle, slice_post
from toutiao.mdparse import load_post
from toutiao.publish import (
    PackageResult, flatten_id, snapshot_name, write_package, write_snapshot,
)

CAP = load_capability(default_capability_path())

_MARKER = re.compile(r"【图(\d+)】")


# ---- 夹具 ---------------------------------------------------------------


def _article(body="段落。", images=(), content_id="db/postgresql/demo", **kwargs):
    defaults = dict(
        title="演示标题",
        digest="摘要",
        title_truncated=False,
        body_truncated=False,
        dropped_links=0,
        notes=(),
    )
    defaults.update(kwargs)
    return ToutiaoArticle(
        content_id=content_id, body=body, images=tuple(images), **defaults
    )


def _site(tmp_path):
    """A fake site root with one post directory and one picture."""
    site = tmp_path / "source"
    posts = site / "_posts"
    posts.mkdir(parents=True)
    image = site / "images" / "demo.png"
    image.parent.mkdir(parents=True)
    Image.new("RGB", (1200, 900), (10, 20, 30)).save(image, "PNG")
    return site, posts


def _site_with_two_images(tmp_path):
    """A site whose first picture is too small for a cover, and whose second one fits."""
    site = tmp_path / "source"
    posts = site / "_posts"
    posts.mkdir(parents=True)
    images = site / "images"
    images.mkdir(parents=True)
    Image.new("RGB", (400, 300), (10, 20, 30)).save(images / "small.png", "PNG")
    Image.new("RGB", (1200, 900), (10, 20, 30)).save(images / "good.png", "PNG")
    return site, posts


def _site_with_image(tmp_path, size, name="pic.png"):
    """A site with one picture of the given size."""
    site = tmp_path / "source"
    posts = site / "_posts"
    posts.mkdir(parents=True)
    images = site / "images"
    images.mkdir(parents=True)
    Image.new("RGB", size, (10, 20, 30)).save(images / name, "PNG")
    return site, posts


def _site_with_three_images(tmp_path):
    """A site with three usable pictures."""
    site = tmp_path / "source"
    posts = site / "_posts"
    posts.mkdir(parents=True)
    images = site / "images"
    images.mkdir(parents=True)
    for name in ("one.png", "two.png", "three.png"):
        Image.new("RGB", (1200, 900), (10, 20, 30)).save(images / name, "PNG")
    return site, posts


def _cap_with_image_bytes(size):
    """A capability whose picture size limit is ``size`` bytes.

    A small limit is what makes ``prepare_image()`` shrink the picture --
    and shrinking is what makes "the original can be cropped" and "the
    webp can be cropped" two different things.
    """
    return dataclasses.replace(
        CAP, limits=dataclasses.replace(CAP.limits, image_bytes=size)
    )


def _readme(result):
    return (result.package_dir / "README.md").read_text(encoding="utf-8")


def _cover_line(readme):
    """The cover line of the upload checklist."""
    for line in readme.splitlines():
        if line.startswith("- [ ] 封面："):
            return line
    raise AssertionError("清单里没有封面那一行：\n" + readme)


def _image_names(result):
    """The picture files of the package, by name."""
    images = result.package_dir / "images"
    if not images.is_dir():
        return []
    return sorted(path.name for path in images.iterdir() if path.is_file())


# ---- 名字规则 -----------------------------------------------------------


def test_flatten_id():
    assert flatten_id("db/postgresql/demo") == "db-postgresql-demo"


def test_snapshot_name():
    assert snapshot_name("db/postgresql/demo", "toutiao") == "db-postgresql-demo__toutiao.json"


@pytest.mark.parametrize(
    "content_id",
    ["..", ".", "", "   ", "a/../b", "../escape", "a/./b"],
)
def test_flatten_id_refuses_ids_that_leave_the_package_root(content_id):
    """会跑出包目录的 id —— 这里自己挡住，不留给调用方。

    ``..`` 落到包根的上一层；``.`` 和空串落到包根本身。``write_package``
    是导出的公共接口，而清掉旧包的那一步会在目标目录里删文件：包根
    之外删文件是破坏，不是脏。
    """
    with pytest.raises(ValueError) as excinfo:
        flatten_id(content_id)
    assert "content_id" in str(excinfo.value)


@pytest.mark.parametrize("content_id", ["..", ".", ""])
def test_a_dangerous_content_id_writes_and_deletes_nothing(tmp_path, content_id):
    """越界的 id —— 包根之外不能有文件被创建或删除。

    包根的上一层先放一个「上一次出包」留下的 cover.webp 和
    images/01.webp：id 是 ``..`` 时，那正是会被清掉的地方。
    """
    site, posts = _site(tmp_path)
    package_root = tmp_path / "out"

    outside_cover = tmp_path / "cover.webp"
    outside_cover.write_bytes(b"keep me")
    outside_images = tmp_path / "images"
    outside_images.mkdir()
    (outside_images / "01.webp").write_bytes(b"keep me too")

    article = _article(
        body="【图1】\n\n段落。", images=("images/demo.png",), content_id=content_id
    )
    with pytest.raises(ValueError):
        write_package(article, CAP, package_root, posts, "https://growdu.cn")

    # 包根之外：文件既没被删，也没被改
    assert outside_cover.read_bytes() == b"keep me"
    assert (outside_images / "01.webp").read_bytes() == b"keep me too"
    # 包根本身：一个文件也没写出来
    assert not package_root.exists() or not any(package_root.iterdir())


def test_write_snapshot_refuses_a_dangerous_content_id(tmp_path):
    """快照的文件名也来自 content_id —— 一样要挡住。"""
    result = PackageResult(
        content_id="..", platform="toutiao", automation="manual", status="packaged",
        title="演示标题", package_dir=tmp_path / "out" / "demo", files=(),
    )
    with pytest.raises(ValueError) as excinfo:
        write_snapshot(result, tmp_path / "outbox")
    assert "content_id" in str(excinfo.value)
    # 连目录都不该被建出来
    assert not (tmp_path / "outbox").exists()


# ---- 包的结构 -----------------------------------------------------------


def test_write_package_produces_the_expected_files(tmp_path):
    site, posts = _site(tmp_path)
    article = _article(body="【图1】\n\n段落。", images=("images/demo.png",))
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    assert result.status == "packaged"
    names = {p.name for p in result.package_dir.iterdir()}
    assert {"article.html", "article.txt", "title.txt", "README.md", "cover.webp"} <= names
    assert (result.package_dir / "images" / "01.webp").is_file()
    assert (result.package_dir / "article.html").read_text(encoding="utf-8")
    assert (result.package_dir / "title.txt").read_text(encoding="utf-8").startswith("演示标题")


def test_the_package_result_describes_what_was_written(tmp_path):
    site, posts = _site(tmp_path)
    article = _article(body="【图1】\n\n段落。", images=("images/demo.png",))
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    assert result.content_id == "db/postgresql/demo"
    assert result.platform == "toutiao"
    assert result.automation == "manual"
    assert result.title == "演示标题"
    assert result.package_dir == tmp_path / "out" / "db-postgresql-demo"
    # files 里是包里每一个文件（相对路径），不是只有顶层那几个
    assert "images/01.webp" in result.files
    assert "cover.webp" in result.files
    assert result.files == tuple(sorted(result.files))
    for name in result.files:
        assert (result.package_dir / name).is_file()


def test_the_package_has_no_files_beyond_the_ones_it_declares(tmp_path):
    site, posts = _site(tmp_path)
    article = _article(body="【图1】\n\n段落。", images=("images/demo.png",))
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    on_disk = {
        path.relative_to(result.package_dir).as_posix()
        for path in result.package_dir.rglob("*")
        if path.is_file()
    }
    assert on_disk == set(result.files)


def test_package_readme_lists_the_manual_steps(tmp_path):
    site, posts = _site(tmp_path)
    result = write_package(_article(), CAP, tmp_path / "out", posts, "https://growdu.cn")
    readme = _readme(result)
    assert "- [ ]" in readme
    assert "封面" in readme
    # 每一步该做什么都要写清楚
    assert "打开头条号后台" in readme
    assert "title.txt" in readme
    assert "article.html" in readme
    assert "article.txt" in readme
    assert "发表" in readme


def test_the_checklist_says_the_footer_must_stay_plain_text(tmp_path):
    """清单末尾那一行要提醒上传者：末尾是纯文本的「完整版见」，不是超链接。

    这一行是清单里唯一防「末尾变成超链接」的提示。删了它，上传者就会
    把末尾那句「完整版见 growdu.cn」当成普通链接贴出去。
    """
    site, posts = _site(tmp_path)
    result = write_package(_article(), CAP, tmp_path / "out", posts, "https://growdu.cn")
    lines = [
        line for line in _readme(result).splitlines()
        if line.startswith("- [ ] 检查正文末尾")
    ]
    assert len(lines) == 1, lines
    assert "完整版见 growdu.cn" in lines[0]
    assert "不是超链接" in lines[0]


def test_write_package_refuses_a_tier_it_does_not_serve(tmp_path):
    """档位不是 manual —— 出包这一步不接，得当场拒绝。

    规格说「升级路径是改一行 TOML，不是改代码」：那一行从 manual 改成
    api_draft 之后，write_package 要是照跑，就会产出一个
    ``status="packaged"`` + ``reason=null`` 的快照 —— 看起来完全正常，
    档位却是错的。这正是「不静默成功」要防的形状。
    """
    site, posts = _site(tmp_path)
    api_draft = dataclasses.replace(CAP, automation="api_draft")
    article = _article(body="【图1】\n\n段落。", images=("images/demo.png",))
    with pytest.raises(ValueError) as excinfo:
        write_package(article, api_draft, tmp_path / "out", posts, "https://growdu.cn")
    message = str(excinfo.value)
    assert "api_draft" in message
    assert "manual" in message
    # 一个文件也不能有
    assert not (tmp_path / "out").exists()


# ---- 没有封面不是错误 ---------------------------------------------------


def test_package_without_a_cover_still_produces_a_package(tmp_path):
    """没有正文图照样出包 —— 头条有无图模式。

    硬失败会让 470/542 篇（86.7%）可发布文章出不了包；
    清单里那一行要明写「按无图模式发布」。
    """
    site, posts = _site(tmp_path)
    result = write_package(_article(), CAP, tmp_path / "out", posts, "https://growdu.cn")
    assert result.status == "packaged"
    assert not (result.package_dir / "cover.webp").exists()
    readme = _readme(result)
    assert "这篇没有正文图" in readme
    assert "无图" in readme


# ---- 图的各种毛病 -------------------------------------------------------


def test_remote_images_are_listed_for_manual_download(tmp_path):
    """外链图不下载 —— 清单里列出来，附上 URL。"""
    site, posts = _site(tmp_path)
    article = _article(body="【图1】\n\n段落。", images=("https://example.com/a.png",))
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    readme = _readme(result)
    assert "https://example.com/a.png" in readme
    assert not (result.package_dir / "images" / "01.webp").exists()


def test_a_missing_image_is_listed_for_manual_checking(tmp_path):
    """找不到的图不静默丢 —— 路径收进清单，附上路径。"""
    site, posts = _site(tmp_path)
    article = _article(body="【图1】\n\n段落。", images=("images/gone.png",))
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    assert result.status == "packaged"
    readme = _readme(result)
    assert "images/gone.png" in readme
    assert "缺图" in readme
    assert not (result.package_dir / "images" / "01.webp").exists()


def test_an_unreadable_image_does_not_break_the_package(tmp_path):
    """SVG 之类 Pillow 读不了的图 —— 不当失败，列进清单交给人工。

    真实语料里就有一张 SVG：不管它，这一篇的整包会直接崩掉。
    """
    site, posts = _site(tmp_path)
    svg = site / "images" / "logo.svg"
    svg.write_text("<svg></svg>", encoding="utf-8")
    article = _article(body="【图1】\n\n段落。", images=("images/logo.svg",))
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    assert result.status == "packaged"
    readme = _readme(result)
    assert "读不了的图" in readme
    assert "images/logo.svg" in readme
    assert not (result.package_dir / "images" / "01.webp").exists()


def test_an_oversized_image_does_not_break_the_package(tmp_path):
    """压不进上限的图 —— 同样不当失败，列进清单交给人工。

    ``prepare_image()`` 压到最小还超限时抛 ``ImageTooLarge``：这一篇
    照样能发，只是这张图得人工处理。
    """
    site, posts = _site_with_image(tmp_path, (4000, 3000), "huge.png")
    article = _article(body="【图1】\n\n段落。", images=("images/huge.png",))
    result = write_package(
        article, _cap_with_image_bytes(100), tmp_path / "out", posts, "https://growdu.cn"
    )
    assert result.status == "packaged"
    readme = _readme(result)
    assert "超限的图" in readme
    assert "images/huge.png" in readme
    assert not (result.package_dir / "images" / "01.webp").exists()


def test_the_four_image_problems_are_not_merged_into_one_line(tmp_path):
    """四种图的问题各有各的行，不能并成一句「图有问题」。"""
    site, posts = _site(tmp_path)
    svg = site / "images" / "logo.svg"
    svg.write_text("<svg></svg>", encoding="utf-8")
    article = _article(
        body="【图1】\n\n【图2】\n\n【图3】\n\n【图4】\n\n段落。",
        images=(
            "https://example.com/a.png",
            "images/gone.png",
            "images/logo.svg",
            "images/demo.png",
        ),
    )
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    readme = _readme(result)
    for marker in ("远程图", "缺图", "读不了的图"):
        assert marker in readme, marker
    # 四种问题各占一行
    assert len([line for line in readme.splitlines() if line.startswith("- [ ] 远程图")]) == 1
    assert len([line for line in readme.splitlines() if line.startswith("- [ ] 缺图")]) == 1
    assert len([line for line in readme.splitlines() if line.startswith("- [ ] 读不了的图")]) == 1


def test_remote_images_never_reach_the_asset_resolver(tmp_path, monkeypatch):
    """外链图在 ``is_remote()`` 那里就分走了，从不进 ``resolve_asset()``。

    ``resolve_asset()`` 只对外链抛 ``RemoteAsset``，而 ``publish.py``
    在调它之前先用 ``is_remote()`` 判过一次 —— 所以下面那道
    ``except RemoteAsset`` 是防御性冗余，不是活代码。这条测试把它钉
    住：哪天有人删了上面那道判断，外链图会被当成缺图。
    """
    import toutiao.publish as publish_module

    site, posts = _site(tmp_path)
    calls = []
    original = publish_module.resolve_asset

    def spy(path, posts_dir):
        calls.append(path)
        return original(path, posts_dir)

    monkeypatch.setattr(publish_module, "resolve_asset", spy)

    article = _article(
        body="【图1】\n\n【图2】\n\n段落。",
        images=("https://example.com/a.png", "images/demo.png"),
    )
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    assert calls == ["images/demo.png"]
    readme = _readme(result)
    assert "远程图" in readme
    assert "缺图" not in readme


# ---- 图的编号 -----------------------------------------------------------


def test_only_the_pictures_the_body_points_at_are_packaged(tmp_path):
    """正文被截断后，切片里还留着没进正文的图 —— 出包不能把它们打进去。

    ``article.images`` 里多出来的那几张在正文里没有占位符：打进去的
    文件编号在正文里找不到对应，人工还得多传一张没人要的图。
    """
    site, posts = _site_with_three_images(tmp_path)
    article = _article(
        body="【图1】\n\n段落。",
        images=("images/one.png", "images/two.png", "images/three.png"),
    )
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    assert _image_names(result) == ["01.webp"]
    assert "【图1】" in _readme(result)
    assert "【图2】" not in _readme(result)


def test_the_file_number_follows_the_placeholder_not_the_packing_order(tmp_path):
    """图1 缺了、图2 还在 —— 文件必须是 02.webp，不能是 01.webp。

    按打包顺序编号的话，【图2】会指向不存在的文件：正文里的占位符和
    包里的文件对不上。
    """
    site, posts = _site_with_image(tmp_path, (1200, 900), "good.png")
    article = _article(
        body="【图1】\n\n【图2】\n\n段落。",
        images=("images/gone.png", "images/good.png"),
    )
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    assert _image_names(result) == ["02.webp"]
    assert "images/gone.png" in _readme(result)


def test_a_remote_picture_keeps_its_number(tmp_path):
    """外链图不下载，但它的序号照样留着 —— 后面的图不能往前挪。"""
    site, posts = _site_with_image(tmp_path, (1200, 900), "good.png")
    article = _article(
        body="【图1】\n\n【图2】\n\n段落。",
        images=("https://example.com/a.png", "images/good.png"),
    )
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    assert _image_names(result) == ["02.webp"]
    readme = _readme(result)
    assert "https://example.com/a.png" in readme
    # 清单要写清正文里要替换的是哪几个占位符
    assert "【图1】" in readme and "【图2】" in readme


def test_placeholder_zero_does_not_pick_the_last_picture(tmp_path):
    """【图0】 —— 编号从 1 开始，0 号没有对应的图。

    ``images[number - 1]`` 在 number=0 时会取到**最后**一张图：正文里
    的【图0】悄悄变成了另一张图。切片器不会编号到 0，但这个函数是导出
    的公共接口，手搓的 article 就能触发。
    """
    site, posts = _site_with_two_images(tmp_path)
    article = _article(body="【图0】\n\n段落。", images=("images/good.png",))
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    # 没有打包任何图（0 号不是 good.png）
    assert _image_names(result) == []
    readme = _readme(result)
    assert "【图0】" in readme
    assert "没有对应的图" in readme


def test_every_placeholder_in_the_body_has_a_file_or_an_explanation(tmp_path):
    """正文里的每个占位符，要么有文件，要么在清单里说清楚为什么没有。"""
    site, posts = _site(tmp_path)
    svg = site / "images" / "logo.svg"
    svg.write_text("<svg></svg>", encoding="utf-8")
    article = _article(
        body="【图1】\n\n【图2】\n\n【图3】\n\n【图4】\n\n段落。",
        images=(
            "https://example.com/a.png",
            "images/gone.png",
            "images/logo.svg",
            "images/demo.png",
        ),
    )
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    readme = _readme(result)
    for number in (1, 2, 3, 4):
        marker = "【图{}】".format(number)
        assert marker in readme
    # 只有能用上的那张图落了文件，编号仍是它自己的 04
    assert _image_names(result) == ["04.webp"]


def test_every_placeholder_without_a_file_is_explained_on_its_own_line(tmp_path):
    """没有文件的占位符，清单里要有它自己那一行解释。

    光写一句「见下面几行」不够：下面那几行必须真的写着这张图的路径
    或 URL，否则上传者不知道要处理哪一张。占位符符号本身出现在清单里
    是不够的 —— 它总是出现在「图片」那一行，哪张图缺文件并不能看出来。
    """
    site, posts = _site(tmp_path)
    svg = site / "images" / "logo.svg"
    svg.write_text("<svg></svg>", encoding="utf-8")
    article = _article(
        body="【图1】\n\n【图2】\n\n【图3】\n\n【图4】\n\n段落。",
        images=(
            "https://example.com/a.png",
            "images/gone.png",
            "images/logo.svg",
            "images/demo.png",
        ),
    )
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    lines = _readme(result).splitlines()

    picture_line = next(line for line in lines if line.startswith("- [ ] 图片："))
    assert "（没有文件的占位符见下面几行）" in picture_line

    for relative, tag in (
        ("https://example.com/a.png", "- [ ] 远程图"),
        ("images/gone.png", "- [ ] 缺图"),
        ("images/logo.svg", "- [ ] 读不了的图"),
    ):
        # 这个路径/URL 只出现在解释它的那一行里
        explaining = [line for line in lines if relative in line]
        assert len(explaining) == 1, (relative, explaining)
        assert explaining[0].startswith(tag), (relative, explaining[0])


# ---- 封面 ---------------------------------------------------------------


def test_the_cover_is_cut_from_the_converted_webp(tmp_path):
    """封面裁的是已转好的 webp，不是原始 PNG。

    限额调到 2500 字节，prepare_image 会把这张 2400×1800 的图缩一半：
    缩过的 webp（1200×900）裁 3:4 是 675×900，裁原图则是 1350×1800 ——
    两者不一样，这条才有鉴别力。默认 5MB 下原图根本不会被压缩，
    两者裁出来逐字节相同，这条会恒真。
    """
    site, posts = _site_with_image(tmp_path, (2400, 1800), "big.png")
    article = _article(body="【图1】\n\n段落。", images=("images/big.png",))
    result = write_package(
        article, _cap_with_image_bytes(2500), tmp_path / "out", posts, "https://growdu.cn"
    )
    assert (result.package_dir / "cover.webp").is_file()
    expected = tmp_path / "expected.webp"
    make_cover(result.package_dir / "images" / "01.webp", expected, "3:4", (600, 800))
    assert (result.package_dir / "cover.webp").read_bytes() == expected.read_bytes()
    with Image.open(expected) as cover:
        # 缩过的 webp 裁出来是 675×900；裁原图会是 1350×1800
        assert cover.size == (675, 900)


def test_the_cover_comes_from_the_first_image_that_can_be_cropped(tmp_path):
    """第一张裁不动、第二张能裁 —— 封面要用第二张，不能白白丢掉。

    真实语料里 60 张本地图只有 20 张裁得出合规封面，「只试第一张」
    会把剩下那 40 张的封面也一起丢掉。
    """
    site, posts = _site_with_two_images(tmp_path)
    article = _article(body="【图1】\n\n【图2】\n\n段落。",
                       images=("images/small.png", "images/good.png"))
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    assert (result.package_dir / "cover.webp").is_file()
    expected = tmp_path / "expected.webp"
    make_cover(result.package_dir / "images" / "02.webp", expected, "3:4", (600, 800))
    assert (result.package_dir / "cover.webp").read_bytes() == expected.read_bytes()


def test_the_three_reasons_for_no_cover_are_worded_differently(tmp_path):
    """零封面有三种原因，要分开说。

    ① 正文没有图；② 正文图全是外链（出包不下载，没有本地文件可裁）；
    ③ 有本地图但都裁不出合规封面。真实语料里 ② 有 46 篇、③ 有 15 篇 ——
    把 ② 说成 ③ 是错的：它们不是「裁不出」，是「没有文件可裁」。
    """
    site, posts = _site(tmp_path)

    # ① 正文没有图
    without = write_package(_article(), CAP, tmp_path / "out", posts, "https://growdu.cn")
    line = _cover_line(_readme(without))
    assert "这篇没有正文图" in line

    # ② 正文图全是外链
    remote = write_package(
        _article(body="【图1】\n\n段落。", images=("https://example.com/a.png",)),
        CAP, tmp_path / "out", posts, "https://growdu.cn",
    )
    line = _cover_line(_readme(remote))
    assert "外链" in line
    assert "裁不出合规封面" not in line
    assert "这篇没有正文图" not in line

    # ③ 有本地图但都裁不出
    small = site / "images" / "small.png"
    Image.new("RGB", (400, 300), (10, 20, 30)).save(small, "PNG")
    local = write_package(
        _article(body="【图1】\n\n段落。", images=("images/small.png",)),
        CAP, tmp_path / "out", posts, "https://growdu.cn",
    )
    line = _cover_line(_readme(local))
    assert "裁不出合规封面" in line
    assert "外链" not in line


@pytest.mark.parametrize(
    "relative, svg",
    [
        ("images/gone.png", False),
        ("images/logo.svg", True),
    ],
    ids=["missing-file", "unreadable-file"],
)
def test_a_local_picture_that_never_became_a_file_is_not_called_uncroppable(
    tmp_path, relative, svg
):
    """本地图转不出来（缺文件 / 读不了）—— 说「没有文件可裁」，不是「裁不出」。

    这两种情况下本机一张能裁的图都没有：文件压根没有，和「裁不出合
    规尺寸」不是一回事。套用 ③ 的措辞，会让人以为图在、只是尺寸不够，
    于是去改尺寸而不是去补文件。
    """
    site, posts = _site(tmp_path)
    if svg:
        (site / "images" / "logo.svg").write_text("<svg></svg>", encoding="utf-8")

    result = write_package(
        _article(body="【图1】\n\n段落。", images=(relative,)),
        CAP, tmp_path / "out", posts, "https://growdu.cn",
    )
    line = _cover_line(_readme(result))
    # 不是 ③：那儿说的是「裁不出合规封面」
    assert "裁不出合规封面" not in line
    # 不是 ①：正文里是有图的
    assert "这篇没有正文图" not in line
    # 不是 ②：这不是外链
    assert "外链" not in line
    # 真正的原因：没有本地文件可裁
    assert "没有本地文件可裁" in line
    assert "转不出来" in line


def test_the_cover_decision_follows_the_converted_webp(tmp_path):
    """压不进上限时 prepare_image 会把图缩一半 —— 封面判定必须跟着 webp 走。

    这张 1200×900 的图在 800 字节的限额下会被缩成 600×450：裁原图是
    675×900（合规），裁缩过的 webp 是 336×448（不合规）。判定拿原图
    判就会多出一个平台根本没见过的封面。
    """
    site, posts = _site_with_image(tmp_path, (1200, 900), "wide.png")
    article = _article(body="【图1】\n\n段落。", images=("images/wide.png",))
    result = write_package(
        article, _cap_with_image_bytes(800), tmp_path / "out", posts, "https://growdu.cn"
    )
    assert result.status == "packaged"
    assert not (result.package_dir / "cover.webp").exists()
    readme = _readme(result)
    assert "裁不出合规封面" in _cover_line(readme)


def test_repackaging_does_not_leave_stale_files_behind(tmp_path):
    """重出包不能留下上一次的图和封面。

    母稿改了（或者图被截掉了），旧文件留在包里，人工就会上传一张
    正文里根本没有的图，或者传一个这一版不该有的封面。
    """
    site, posts = _site_with_three_images(tmp_path)
    article = _article(
        body="【图1】\n\n【图2】\n\n段落。",
        images=("images/one.png", "images/two.png"),
    )
    first = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    assert _image_names(first) == ["01.webp", "02.webp"]
    assert (first.package_dir / "cover.webp").is_file()

    fewer = _article(body="【图1】\n\n段落。", images=("images/small.png",))
    Image.new("RGB", (400, 300), (10, 20, 30)).save(site / "images" / "small.png", "PNG")
    second = write_package(fewer, CAP, tmp_path / "out", posts, "https://growdu.cn")
    assert _image_names(second) == ["01.webp"]
    # 这一版裁不出封面 —— 上一版的封面不能留着
    assert not (second.package_dir / "cover.webp").exists()


# ---- 状态快照 -----------------------------------------------------------


def test_write_snapshot_writes_public_json(tmp_path):
    site, posts = _site(tmp_path)
    article = _article(body="【图1】\n\n段落。", images=("images/demo.png",))
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    path = write_snapshot(result, tmp_path / "outbox")
    assert path.name == "db-postgresql-demo__toutiao.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["content_id"] == "db/postgresql/demo"
    assert data["platform"] == "toutiao"
    assert data["status"] == "packaged"
    assert data["automation"] == "manual"
    assert data["published_url"] is None
    assert "updated_at" in data
    # 只含公开信息：没有凭据、没有本机绝对路径
    text = path.read_text(encoding="utf-8")
    assert str(tmp_path) not in text
    assert "/Users/" not in text
    assert "secret" not in text.lower()
    assert "token" not in text.lower()


def test_the_snapshot_timestamp_carries_a_timezone_offset(tmp_path):
    """``updated_at`` 要带时区偏移 —— §6.5 的例子是 ``2026-11-13T09:00:03+08:00``。

    不带偏移的时间戳，同一个瞬间在别的机器上读出来是几点全看读它的人
    在哪。站点索引要拿它排序，光有「本地时间」是不够的。
    """
    site, posts = _site(tmp_path)
    article = _article(body="【图1】\n\n段落。", images=("images/demo.png",))
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    path = write_snapshot(result, tmp_path / "outbox")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert re.search(r"[+-]\d{2}:\d{2}$", data["updated_at"])


def test_the_snapshot_package_dir_is_relative_to_the_repository(tmp_path, monkeypatch):
    """快照里的包路径是仓库相对路径，不是本机绝对路径。

    §6.5 的例子是 ``toutiao/out/db-postgresql-...``：站点索引要靠它
    找回发布包，绝对路径在别的机器上没用。
    """
    import toutiao.publish as publish_module

    site, posts = _site(tmp_path)
    monkeypatch.setattr(publish_module, "_REPO_ROOT", tmp_path)
    article = _article(body="【图1】\n\n段落。", images=("images/demo.png",))
    result = write_package(
        article, CAP, tmp_path / "toutiao" / "out", posts, "https://growdu.cn"
    )
    path = write_snapshot(result, tmp_path / "publish" / "outbox")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["package_dir"] == "toutiao/out/db-postgresql-demo"
    assert not data["package_dir"].startswith("/")


def test_the_snapshot_says_the_article_is_waiting_for_a_human(tmp_path):
    """``packaged`` 不是「已发布」—— 快照里要写清楚在等人工上传。"""
    site, posts = _site(tmp_path)
    article = _article(body="【图1】\n\n段落。", images=("images/demo.png",))
    result = write_package(article, CAP, tmp_path / "out", posts, "https://growdu.cn")
    path = write_snapshot(result, tmp_path / "outbox")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "packaged"
    assert data["reason"]
    assert "待人工上传" in data["reason"]


# ---- 集成测试：母稿 → 切片 → 渲染 → 出包 → 快照 -------------------------


_MOTHER = """---
title: "演示文章：一篇母稿"
date: 2026-01-02 03:04:05
description: "母稿的摘要"
---

## 小标题

第一段，把结论先抛出来。

![配图](images/demo.png)

第二段，图后面还有话。

完整版见 growdu.cn
"""


def _write_mother(posts, name="db/demo.md", body=_MOTHER):
    path = posts / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_the_whole_chain_from_a_markdown_mother_post(tmp_path):
    """母稿 → front matter → 切片 → 渲染 → 出包 → 快照，落盘的产物要合理。"""
    site, posts = _site(tmp_path)
    path = _write_mother(posts)

    post = load_post(path, posts)
    assert post.title == "演示文章：一篇母稿"
    assert post.fields["description"] == "母稿的摘要"

    sliced = slice_post(post, CAP.limits, "https://growdu.cn")
    assert sliced.article is not None
    article = sliced.article
    assert article.content_id == "db/demo"
    assert article.images == ("images/demo.png",)

    result = write_package(article, CAP, tmp_path / "toutiao" / "out", posts, "https://growdu.cn")
    assert result.status == "packaged"

    # 正文：切片 → 渲染 → HTML，末尾是纯文本的完整版提示
    html = (result.package_dir / "article.html").read_text(encoding="utf-8")
    assert "第一段，把结论先抛出来。" in html
    assert "<h2" in html
    assert "完整版见 growdu.cn" in html
    assert "<a " not in html
    text = (result.package_dir / "article.txt").read_text(encoding="utf-8")
    assert "第一段，把结论先抛出来。" in text

    # 标题与摘要
    title = (result.package_dir / "title.txt").read_text(encoding="utf-8")
    assert title.splitlines()[0] == article.title
    assert title.splitlines()[1] == article.digest

    # 图：正文里的占位符和包里的文件一一对应
    assert "【图1】" in html
    assert _image_names(result) == ["01.webp"]
    assert (result.package_dir / "cover.webp").is_file()

    # 清单
    readme = _readme(result)
    assert "- [ ]" in readme
    assert "封面" in readme

    # 快照
    snapshot = write_snapshot(result, tmp_path / "publish" / "outbox")
    assert snapshot.name == "db-demo__toutiao.json"
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    assert data["content_id"] == "db/demo"
    assert data["platform"] == "toutiao"
    assert data["status"] == "packaged"
    assert data["automation"] == "manual"
    assert data["title"] == article.title
    assert data["published_url"] is None
    assert str(tmp_path) not in snapshot.read_text(encoding="utf-8")


def test_the_whole_chain_for_a_post_without_any_picture(tmp_path):
    """没有正文图的母稿照样出包 —— 这是绝大多数文章的情况。"""
    site, posts = _site(tmp_path)
    path = _write_mother(
        posts,
        body="""---
title: "没有配图的母稿"
date: 2026-01-02 03:04:05
description: "摘要"
---

只有文字的第一段。

第二段也没有图。
""",
    )

    post = load_post(path, posts)
    sliced = slice_post(post, CAP.limits, "https://growdu.cn")
    assert sliced.article is not None
    assert sliced.article.images == ()

    result = write_package(
        sliced.article, CAP, tmp_path / "toutiao" / "out", posts, "https://growdu.cn"
    )
    assert result.status == "packaged"
    assert not (result.package_dir / "cover.webp").exists()
    assert _image_names(result) == []
    assert "这篇没有正文图" in _cover_line(_readme(result))


def test_the_whole_chain_for_a_post_whose_body_is_cut(tmp_path):
    """正文被 3000 字截断 —— 截掉的那张图没有占位符，也不该进包。

    这是图编号最容易错的地方：切片里还留着那张图，正文里却没有它的
    【图N】了。按打包顺序出包会多出一张正文里没人引用的图。
    """
    site, posts = _site_with_three_images(tmp_path)
    filler = "这是用来把正文撑过三千字的段落。" * 250
    path = _write_mother(
        posts,
        body="""---
title: "被截断的母稿"
date: 2026-01-02 03:04:05
description: "摘要"
---

开头一段。

![图一](images/one.png)

{filler}

![图二](images/two.png)

![图三](images/three.png)
""".format(filler=filler),
    )

    post = load_post(path, posts)
    sliced = slice_post(post, CAP.limits, "https://growdu.cn")
    assert sliced.article is not None
    article = sliced.article
    assert article.body_truncated is True
    # 切片里留着三张图，正文里只剩第一张的占位符
    assert len(article.images) == 3
    assert sorted(set(_MARKER.findall(article.body))) == ["1"]

    result = write_package(
        article, CAP, tmp_path / "toutiao" / "out", posts, "https://growdu.cn"
    )
    assert result.status == "packaged"
    html = (result.package_dir / "article.html").read_text(encoding="utf-8")
    assert "【图1】" in html
    assert "【图2】" not in html
    # 包里只有正文真的引用的那张图
    assert _image_names(result) == ["01.webp"]
    # 清单要说清楚少了哪几张
    assert "未打包" in _readme(result)


def test_the_whole_chain_with_a_remote_picture(tmp_path):
    """外链图的母稿：出包不下载，图进清单，文章照样出包。"""
    site, posts = _site(tmp_path)
    path = _write_mother(
        posts,
        body="""---
title: "带外链图的母稿"
date: 2026-01-02 03:04:05
description: "摘要"
---

一段话。

![外链](https://example.com/remote.png)
""",
    )

    post = load_post(path, posts)
    sliced = slice_post(post, CAP.limits, "https://growdu.cn")
    assert sliced.article is not None

    result = write_package(
        sliced.article, CAP, tmp_path / "toutiao" / "out", posts, "https://growdu.cn"
    )
    assert result.status == "packaged"
    assert _image_names(result) == []
    assert not (result.package_dir / "cover.webp").exists()
    readme = _readme(result)
    assert "https://example.com/remote.png" in readme
    assert "远程图" in readme
    # 全是外链 → 封面那一行说的是「没有文件可裁」，不是「裁不出」
    line = _cover_line(readme)
    assert "外链" in line
    assert "裁不出合规封面" not in line


def test_the_package_result_is_a_frozen_dataclass(tmp_path):
    """结果是不可变的 —— 快照写出去之后不该有人改它。"""
    import dataclasses

    site, posts = _site(tmp_path)
    result = write_package(_article(), CAP, tmp_path / "out", posts, "https://growdu.cn")
    assert dataclasses.is_dataclass(result)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.status = "published"
