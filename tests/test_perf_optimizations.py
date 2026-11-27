"""首屏性能改动的守卫测试。

这一轮做了三处优化，它们各自都有一个"很容易被后人改回去"的点：

* **prism 只在有代码块的页面加载**。全站 1239 个图、672 篇文章，但首页、
  归档、分类、标签这些页面一个代码块都没有，却照样要拉 14 KB 的
  ``prism.min.css``；post 页面还要多拉 13 KB 的 prism JS。有人会觉得
  "反正有缓存"就把它改回无条件加载——这里把它钉住。
* **正文图补 width/height**。``marked`` 的 ``lazyload`` 已经给图片加了
  ``loading="lazy"``（这一点别再重复做），但宽高仍然缺失，浏览器在图片
  下载完成前不给它留位置，滚动时会跳版。补宽高的过滤器是
  ``scripts/img-dimensions.js``，删掉它等于把 CLS 放回去。
* **第三方脚本 defer**。``typed.js`` / ``cn-banner.js`` 原来同步加载，
  会挡在首屏前面。

还有一条是**故意不改**的：jQuery 保持同步加载。主题里有十几处内联脚本
（深色模式开关、封面轮播、目录树、搜索、图库）在解析期就调用它，改成
``defer`` 需要把这些全部重写，而 CI 里没有任何浏览器级测试能兜住漏网的
一处——所以这里明确写死"不许随手 defer"，将来真要做，得先补前端冒烟测试。

放在根级 ``tests/``，随 ``site-guard.yml`` 进 CI。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
THEME_LAYOUT = REPO / "themes" / "matery" / "layout"
HEAD_EJS = THEME_LAYOUT / "_partial" / "head.ejs"
LAYOUT_EJS = THEME_LAYOUT / "layout.ejs"
COVER_EJS = THEME_LAYOUT / "_partial" / "bg-cover-content.ejs"
PATCH_THEME = REPO / "tools" / "patch-theme.py"
IMG_FILTER = REPO / "scripts" / "img-dimensions.js"

SAMPLE_PNG = REPO / "docs" / "source-tracks" / "engineering" / "L2-tooling" / "postgresql" / "logical-replication" / "pa_decode" / "image.png"
SAMPLE_JPG = REPO / "docs" / "source-tracks" / "linux" / "L4-networking" / "ipv6_img" / "07-55785c722b16.jpg"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _guarded_by_has_code(text: str, needle: str) -> bool:
    """``needle`` 那一行是不是落在 ``<% if (_hasCode) { %> ... <% } %>`` 里。"""
    at = text.find(needle)
    if at == -1:
        return False
    open_at = text.rfind("<% if (_hasCode) { %>", 0, at)
    close_at = text.find("<% } %>", at)
    if open_at == -1 or close_at == -1:
        return False
    return open_at < at < close_at


# --- prism：只在有代码块的页面加载 ---------------------------------------


def test_has_code_flag_is_derived_from_the_rendered_content():
    """判据必须来自页面正文，否则首页也会被判成"有代码"。"""
    for path in (HEAD_EJS, LAYOUT_EJS):
        text = _read(path)
        assert "_hasCode" in text, f"{path.name} 没有定义 _hasCode"
        assert "page.content" in text, f"{path.name} 的 _hasCode 不是从 page.content 判的"
        assert "<(?:pre|code)" in text, f"{path.name} 的判据没有同时覆盖 pre 与 code"


def test_prism_stylesheet_is_only_loaded_for_pages_with_code():
    head = _read(HEAD_EJS)
    assert "/libs/prism/prism.min.css" in head, "prism 样式表被整个删掉了"
    assert _guarded_by_has_code(head, "/libs/prism/prism.min.css"), (
        "prism 样式表不再按需加载，首页又要白拉 14 KB"
    )


def test_prism_javascript_is_only_loaded_for_pages_with_code():
    layout = _read(LAYOUT_EJS)
    assert "/lib/prism/prism-core.min.js" in layout, "prism 脚本被整个删掉了"
    assert "is_post() && _hasCode" in layout, (
        "prism 脚本必须同时满足「是文章」和「有代码块」两个条件"
    )


def test_prism_block_appears_exactly_once():
    """同一个页面里不能出现两份 prism 脚本。

    ``patch-theme.py`` 会在构建时把注入块先删掉再重新插一遍，所以仓库里
    留下的那份必须和它注入的形态一致，否则会出现两份（这里踩过一次：
    改了仓库里的那份，没改脚本注入的那份，构建后两份并存）。
    """
    layout = _read(LAYOUT_EJS)
    marker = "<script src=\"<%= url_for('/lib/prism/prism-core.min.js') %>\"></script>"
    assert layout.count(marker) == 1, "layout.ejs 里的 prism 脚本不止一份"
    patch = _read(PATCH_THEME)
    assert patch.count(marker) == 1, "patch-theme.py 里注入的 prism 脚本不止一份"


def test_mermaid_style_stays_unconditional():
    """``.mermaid`` 的样式不能跟着代码块一起被条件掉。

    有图无代码的文章是存在的（审校线里就有），那种页面必须有 mermaid 的
    排版样式。
    """
    head = _read(HEAD_EJS)
    assert ".mermaid{text-align:center;margin:16px 0}" in head
    mermaid_at = head.find(".mermaid{text-align:center")
    open_at = head.rfind("<% if (_hasCode) { %>", 0, mermaid_at)
    close_at = head.find("<% } %>", mermaid_at)
    assert not (open_at != -1 and close_at != -1 and open_at < mermaid_at < close_at), (
        "mermaid 样式被关进了代码块的条件里"
    )


def test_patch_theme_mirrors_the_prism_guard():
    """``patch-theme.py`` 是主题改动的源头，它也必须带同样的条件。

    现在 head.ejs 里有 og:title，patch-theme 的注入会被跳过；等哪天
    head.ejs 被重写、注入重新生效时，条件得已经在那里了。
    """
    text = _read(PATCH_THEME)
    assert "/libs/prism/prism.min.css" in text
    assert _guarded_by_has_code(text, "/libs/prism/prism.min.css"), (
        "patch-theme.py 注入的 prism 样式表没有按需加载的条件"
    )


# --- 脚本加载：第三方脚本 defer，jQuery 保持同步 ----------------------------


def test_typed_js_is_deferred_and_initialised_on_dom_ready():
    cover = _read(COVER_EJS)
    assert 'defer src="<%- theme.jsDelivr.url %><%- url_for(theme.libs.js.typed) %>"' in cover, (
        "typed.js 还在同步加载"
    )
    assert "new Typed(" in cover
    assert "DOMContentLoaded" in cover, (
        "typed.js 变成 defer 之后，new Typed 必须等到 DOMContentLoaded"
    )


def test_cn_banner_js_is_deferred():
    layout = _read(LAYOUT_EJS)
    assert 'defer src="<%- url_for(\'/js/cn-banner.js\') %>"' in layout, (
        "cn-banner.js 还在同步加载"
    )


def test_jquery_stays_synchronous_on_purpose():
    """jQuery 暂时不许 defer——见模块 docstring。

    真要 defer，得同时满足两件事：把解析期调用全部改掉，并且给 CI 补上
    浏览器级冒烟测试。这一条只负责让"随手加个 defer"变成一次显式的决定。
    """
    head = _read(HEAD_EJS)
    jquery_lines = [
        line for line in head.splitlines() if "theme.libs.js.jquery" in line
    ]
    assert jquery_lines, "head.ejs 里找不到 jQuery 的引用"
    for line in jquery_lines:
        assert "defer" not in line, (
            "jQuery 改成了 defer，但主题里还有十几处解析期调用没有重写"
        )
    assert "jQuery stays synchronous" in head, (
        "jQuery 保持同步的理由应当写在代码旁边，而不是只存在于提交信息里"
    )


# --- 正文图片宽高 ---------------------------------------------------------


def test_image_dimension_filter_exists_and_is_registered():
    assert IMG_FILTER.is_file(), "scripts/img-dimensions.js 不在了"
    text = _read(IMG_FILTER)
    assert "after_post_render" in text, "过滤器没有挂在 after_post_render 上"
    assert "width=" in text and "height=" in text, "过滤器没有补 width/height"


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "样本不是 PNG"
    assert data[12:16] == b"IHDR", "PNG 缺少 IHDR"
    return (
        int.from_bytes(data[16:20], "big"),
        int.from_bytes(data[20:24], "big"),
    )


def _jpeg_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:2] == b"\xff\xd8", "样本不是 JPEG"
    at = 2
    while at < len(data):
        assert data[at] == 0xFF, "JPEG 标记流损坏"
        marker = data[at + 1]
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            at += 2
            continue
        length = int.from_bytes(data[at + 2:at + 4], "big")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height = int.from_bytes(data[at + 5:at + 7], "big")
            width = int.from_bytes(data[at + 7:at + 9], "big")
            return width, height
        at += 2 + length
    raise AssertionError("JPEG 里没有找到 SOF 段")


@pytest.mark.parametrize(
    "sample,parse",
    [
        (SAMPLE_PNG, _png_size),
        (SAMPLE_JPG, _jpeg_size),
    ],
)
def test_image_size_parser_agrees_with_the_file_header(sample: Path, parse):
    """JS 解析出来的宽高必须和文件头里写的一致。

    宽高写错会让图片按错误的宽高比显示（``height:auto`` 救不回来，
    它是按属性里的宽高比换算的），所以这里做一次交叉校验。
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("没有 node，跳过 JS 侧校验")

    assert sample.is_file(), f"样本图片不见了：{sample}"
    expected = parse(sample)

    script = (
        "const m=require(process.argv[1]);"
        "const s=m.imageSize(process.argv[2]);"
        "process.stdout.write(JSON.stringify(s||null));"
    )
    result = subprocess.run(
        [node, "-e", script, str(IMG_FILTER), str(sample)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"node 执行失败：{result.stderr}"
    got = json.loads(result.stdout)
    assert got is not None, f"{sample.name} 没有解析出尺寸"
    assert (got["width"], got["height"]) == expected, (
        f"{sample.name} 的宽高不一致：node 读出 {got['width']}x{got['height']}，"
        f"文件头是 {expected[0]}x{expected[1]}"
    )


def test_image_size_is_sniffed_from_the_content_not_the_extension():
    """扩展名会骗人，必须按文件头判断。

    ``docs/`` 里确实有扩展名是 ``.png``、内容却是 JPEG 的图
    （``oceanbase_arch.png`` 就是），还有一批 ``.png`` 其实是纯文本占位
    文件。按扩展名分派会把这些图整批漏掉。
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("没有 node，跳过 JS 侧校验")

    sample = REPO / "docs" / "source-tracks" / "distributed" / "L3-ha-and-dr" / "ha元信息常见存储方式" / "img" / "oceanbase_arch.png"
    assert sample.is_file(), f"样本图片不见了：{sample}"
    assert sample.read_bytes()[:3] == b"\xff\xd8\xff", "样本不再是 JPEG 内容的 .png"

    expected = _jpeg_size(sample)
    script = (
        "const m=require(process.argv[1]);"
        "const s=m.imageSize(process.argv[2]);"
        "process.stdout.write(JSON.stringify(s||null));"
    )
    result = subprocess.run(
        [node, "-e", script, str(IMG_FILTER), str(sample)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"node 执行失败：{result.stderr}"
    got = json.loads(result.stdout)
    assert got is not None, "扩展名与内容不符的图没有被识别出来"
    assert (got["width"], got["height"]) == expected
