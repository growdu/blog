"""Font Awesome 图标裁剪的守卫。

背景
----
站点的字体文件是 ``fa-solid-900.woff2`` 151 KB 与 ``fa-brands-400.woff2``
103 KB——浏览器第一次访问时整个拉下来，woff2 本来就压过一轮，再上 gzip 也
省不了多少。而站点实际只用到 90 个左右的图标，裁剪后能省下 240 KB 上下。

``tools/subset-icons.py`` 负责这件事。裁剪的失败模式很隐蔽，所以这里把
它盯住：

1. **图标类必须都存在**。站点里写了一个 CSS 里没有的图标类，那个图标就是
   空的——不报错，只是不显示。这类问题必须在上线前就被抓住。
2. **Font Awesome 6 的 CSS 把多个图标类合并在一条规则里**
   （``.fa-bolt:before,.fa-zap:before{content:"\\f0e7"}``）。只认第一个
   就会漏掉别名，站点用别名时图标变空白。
3. **字体族不能认错**。图标类本身不带字体信息，字体由同一段 class 里的
   族前缀（``fab`` / ``far`` / ``fas``）决定。认错族，码位会被裁进错误的
   字体，页面上是个豆腐块。

裁剪本身要有 fontTools；没装就只跑前两项（site-guard 的 CI 只装了 pytest，
第三项在那边是跳过的，裁剪由 build 那个 job 自己装 fontTools 跑）。
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TOOL = REPO / "tools" / "subset-icons.py"
THEME = REPO / "themes" / "matery"
FA_CSS = THEME / "source" / "libs" / "awesome" / "css" / "all.min.css"


def _load_tool():
    """按路径加载 ``tools/subset-icons.py``。

    ``tools/`` 不是包，所以走文件加载。模块顶层没有副作用（fontTools 是
    在函数里延迟导入的），没装 fontTools 也能 import。
    """
    spec = importlib.util.spec_from_file_location("subset_icons", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


subset_icons = _load_tool()


def _theme_texts() -> list[str]:
    out: list[str] = []
    for suffix in (".ejs", ".js"):
        for path in THEME.rglob("*" + suffix):
            try:
                out.append(path.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
    return out


# --- CSS 解析 -------------------------------------------------------------


def test_grouped_icon_rules_are_all_parsed() -> None:
    """一条规则里的多个图标类必须都认出来。

    FA6 的写法是 ``.fa-bolt:before,.fa-zap:before{content:"\\f0e7"}``：
    主名和别名共用一条规则。只认第一个，站点一旦用别名，图标就是空的。
    """
    css = FA_CSS.read_text(encoding="utf-8")
    icons, _ = subset_icons._parse_css(css)

    assert "fa-bolt" in icons, "fa-bolt 没解析出来"
    assert "fa-zap" in icons, "fa-zap（fa-bolt 的别名）没解析出来"
    assert icons["fa-bolt"] == icons["fa-zap"], (
        "fa-bolt 与它的别名 fa-zap 应当是同一个码位"
    )
    # 再挑一条多类别的规则核对码位对得上
    for name in ("fa-github", "fa-github-square", "fa-user", "fa-database"):
        assert name in icons, f"{name} 没解析出来"


def test_family_is_read_from_the_same_class_attribute() -> None:
    """字体族由同一段 class 里的族前缀决定。"""
    assert subset_icons._family_of("fab fa-github") == "brands"
    assert subset_icons._family_of("fa-brands fa-github") == "brands"
    assert subset_icons._family_of("far fa-user") == "regular"
    assert subset_icons._family_of("fa-regular fa-user") == "regular"
    assert subset_icons._family_of("fas fa-user") == "solid"
    assert subset_icons._family_of("fa-solid fa-user") == "solid"
    # 没写族前缀的按 solid 算（主题里绝大多数是这么用的）
    assert subset_icons._family_of("fa fa-bell") == "solid"


def test_modifier_classes_are_not_treated_as_icons() -> None:
    """``fa-fw`` / ``fa-spin`` / ``fa-3x`` 是修饰类，不该被当成图标。"""
    css = FA_CSS.read_text(encoding="utf-8")
    _, modifiers = subset_icons._parse_css(css)
    for name in ("fa-fw", "fa-spin", "fa-3x", "fa-stack"):
        assert name in modifiers, f"{name} 应该被认成修饰类"


# --- 站点里用到的图标 -----------------------------------------------------


def test_every_icon_class_used_by_the_theme_exists_in_the_css() -> None:
    """站点用到的图标类，CSS 里必须都有——否则那个图标是空的。

    这条是"空白图标"的最后一道闸：图标类写错、用了 v3 时代的老名字，
    或者引号写坏，都会在这里被抓住。
    """
    css = FA_CSS.read_text(encoding="utf-8")
    icons, modifiers = subset_icons._parse_css(css)
    used = subset_icons._used_icons(_theme_texts())

    unknown: set[str] = set()
    for family, names in used.items():
        for name in names:
            if name not in icons and name not in modifiers:
                unknown.add(name)

    assert not unknown, (
        "这些图标类在 Font Awesome 的 CSS 里不存在，页面上会是空的："
        + " ".join(sorted(unknown))
    )


def test_the_v3_only_icon_names_are_gone() -> None:
    """``fa-zhihu1`` 是 Font Awesome 3/4 时代的老名字，FA6 里没有。

    写成 ``fa-zhihu`` 才有码位。顺带守住那个被写坏过的深色模式提示图标：
    ``class="fa fa-bellaria-hidden="true"`` 的引号是错的，铃铛一直不显示。
    """
    texts = "\n".join(_theme_texts())
    assert "fa-zhihu1" not in texts, (
        "fa-zhihu1 在 Font Awesome 6 里没有对应图标（该用 fa-zhihu）"
    )
    assert "fa-bellaria-hidden" not in texts, (
        "class 里把 fa-bell 和 aria-hidden 粘在了一起，引号写坏了"
    )
    assert 'class="fa fa-bell" aria-hidden="true"' in texts, (
        "深色模式提示的铃铛图标应该是 fa-bell + aria-hidden"
    )


# --- 字体族判断要用真字体核对 -----------------------------------------------


def _ttf_codepoints(path: Path) -> set[int]:
    """读出 TTF 里有哪些码位。

    纯 Python，不依赖 fontTools：TTF 是未压缩的，cmap 表（格式 4 / 12）
    可以直接解析。这样"某个图标的码位到底在不在这个字体里"这个问题，
    在只装了 pytest 的 site-guard CI 上也能问。

    （woff2 是压缩的，要读它得有 brotli/fontTools，所以这里用同名的 .ttf
    ——两个文件装的是同一套字形。）
    """
    data = path.read_bytes()
    num_tables = int.from_bytes(data[4:6], "big")
    tables: dict[str, tuple[int, int]] = {}
    for i in range(num_tables):
        entry = 12 + i * 16
        tag = data[entry : entry + 4].decode("latin-1")
        offset = int.from_bytes(data[entry + 8 : entry + 12], "big")
        length = int.from_bytes(data[entry + 12 : entry + 16], "big")
        tables[tag] = (offset, length)

    cmap_off = tables["cmap"][0]
    num_subtables = int.from_bytes(data[cmap_off + 2 : cmap_off + 4], "big")
    codepoints: set[int] = set()
    for i in range(num_subtables):
        record = cmap_off + 4 + i * 8
        sub_off = cmap_off + int.from_bytes(data[record + 4 : record + 8], "big")
        fmt = int.from_bytes(data[sub_off : sub_off + 2], "big")
        if fmt == 4:
            seg_x2 = int.from_bytes(data[sub_off + 6 : sub_off + 8], "big")
            seg_count = seg_x2 // 2
            ends = sub_off + 14
            starts = ends + seg_x2 + 2
            deltas = starts + seg_x2
            ranges = deltas + seg_x2
            for s in range(seg_count):
                end = int.from_bytes(data[ends + s * 2 : ends + s * 2 + 2], "big")
                start = int.from_bytes(
                    data[starts + s * 2 : starts + s * 2 + 2], "big"
                )
                delta = int.from_bytes(
                    data[deltas + s * 2 : deltas + s * 2 + 2], "big"
                )
                range_offset = int.from_bytes(
                    data[ranges + s * 2 : ranges + s * 2 + 2], "big"
                )
                if start > end or start == 0xFFFF:
                    continue
                for code in range(start, min(end, 0xFFFE) + 1):
                    if range_offset == 0:
                        glyph = (code + delta) & 0xFFFF
                    else:
                        index = ranges + s * 2 + range_offset + (code - start) * 2
                        if index + 2 > len(data):
                            continue
                        glyph = int.from_bytes(data[index : index + 2], "big")
                        if glyph:
                            glyph = (glyph + delta) & 0xFFFF
                    if glyph:
                        codepoints.add(code)
        elif fmt == 12:
            groups = int.from_bytes(data[sub_off + 12 : sub_off + 16], "big")
            for g in range(groups):
                goff = sub_off + 16 + g * 12
                start = int.from_bytes(data[goff : goff + 4], "big")
                end = int.from_bytes(data[goff + 4 : goff + 8], "big")
                codepoints.update(range(start, min(end, start + 0x20000) + 1))
    return codepoints


def test_every_used_icon_lives_in_the_font_of_its_family() -> None:
    """每个用到的图标，它的码位必须真的在它该在的那个字体里。

    这是"字体族判断错了"的最后一道闸。认错族不会报错，只会让图标变成
    豆腐块——所以这里拿真字体（.ttf，未压缩，纯 Python 就能读 cmap）核对一遍：
    ``fab fa-github`` 的码位必须在 brands 字体里，``fas fa-user`` 的必须在
    solid 字体里。

    用 .ttf 而不是 .woff2 是因为 woff2 是压缩的，读它需要 fontTools——
    那道防线在工具内部（裁之前先对原字体），这里要的是 site-guard 的 CI
    只装 pytest 也能跑。
    """
    webfonts = THEME / "source" / "libs" / "awesome" / "webfonts"
    fonts = {
        "brands": _ttf_codepoints(webfonts / "fa-brands-400.ttf"),
        "regular": _ttf_codepoints(webfonts / "fa-regular-400.ttf"),
        "solid": _ttf_codepoints(webfonts / "fa-solid-900.ttf"),
    }

    css = FA_CSS.read_text(encoding="utf-8")
    icons, _ = subset_icons._parse_css(css)
    used = subset_icons._used_icons(_theme_texts())

    checked = 0
    for family, names in used.items():
        for name in names:
            code = icons.get(name)
            if code is None:
                continue
            checked += 1
            assert code in fonts[family], (
                f"{name}（码位 {hex(code)}）不在 {family} 字体里——"
                "要么这个图标类用错了族前缀，要么字体文件配错了"
            )
    assert checked > 30, f"只核对了 {checked} 个图标，扫描多半没生效"


# --- 脚本里换上去的图标 ----------------------------------------------------


def test_the_icons_swapped_in_by_javascript_are_not_cut_out() -> None:
    """脚本里 ``addClass`` 上去的图标，码位不能被裁掉。

    白天/黑夜那个切换按钮：HTML 里写的是 ``<i id="sum-moon-icon"
    class="fas fa-sun">``，脚本会把它换成 ``fa-moon``。``fa-moon`` 从来
    没进过任何 ``class="..."`` 属性 —— 只扫 class 属性的做法会把它漏掉，
    码位被裁掉，线上那个按钮就是一个豆腐块（框里一个叉）。
    2026-11-24 上线后才在真机上发现。

    这条守的是「补上那一步」：脚本里的图标类要进清单，而且要落进对的
    字体族（``fa-moon`` 的码位在 solid 字体里）。
    """
    css = FA_CSS.read_text(encoding="utf-8")
    icons, modifiers = subset_icons._parse_css(css)

    texts = _theme_texts()
    used = subset_icons._used_icons(texts)
    assert "fa-moon" not in used["solid"], (
        "fa-moon 竟然已经在 class 属性里找到了 —— 那这条测试的前提变了，"
        "day-night.ejs 里的 addClass('fa-moon') 没了？"
    )

    webfonts = THEME / "source" / "libs" / "awesome" / "webfonts"
    original_cmaps = {
        "solid": subset_icons._cmap_codepoints(webfonts / "fa-solid-900.ttf"),
        "regular": subset_icons._cmap_codepoints(webfonts / "fa-regular-400.ttf"),
        "brands": subset_icons._cmap_codepoints(webfonts / "fa-brands-400.ttf"),
    }
    added = subset_icons._add_script_icons(
        texts, used, icons, modifiers, original_cmaps
    )

    assert "fa-moon" in added, (
        "fa-moon 没被补进清单 —— 它的码位会被裁掉，线上那个切换按钮是豆腐块"
    )
    assert "fa-moon" in used["solid"], "fa-moon 落错字体族了"
    assert "fa-moon" not in used["regular"], "fa-moon 不该落进 regular 字体"
    assert icons["fa-moon"] in original_cmaps["solid"], (
        "fa-moon 的码位本来就不在 solid 字体里"
    )
    # regular 字体里也有月亮 —— 两个字体共用一部分字形，所以反查只能定到
    # 「候选有两个」，最后按 solid 优先定下来（站点的图标一律是 `fas`）。
    assert icons["fa-moon"] in original_cmaps["regular"], (
        "fa-moon 在 regular 字体里没有 —— 那族就能靠码位唯一确定，"
        "这条测试的前提变了"
    )


def test_the_modifier_classes_are_not_pulled_in_as_icons() -> None:
    """``fa-fw`` / ``fa-spin`` 这些修饰类不能当成图标补进去。"""
    css = FA_CSS.read_text(encoding="utf-8")
    icons, modifiers = subset_icons._parse_css(css)
    texts = _theme_texts()
    used = subset_icons._used_icons(texts)
    added = subset_icons._add_script_icons(texts, used, icons, modifiers, {})

    assert not set(added) & modifiers, (
        "修饰类被当成图标补进去了："
        + " ".join(sorted(set(added) & modifiers))
    )


# --- 裁剪本身 -------------------------------------------------------------


def test_missing_fonttools_is_reported_not_crashed(monkeypatch, capsys) -> None:
    """缺 fontTools 时要明说，不能让构建以一句 ImportError 收场。

    2026-11-15 实测：CI 里那一步退出码 1，字体没裁成，日志里只有一句
    「Process completed with exit code 1」——看不出是没装上还是裁不动。
    现在缺依赖会说清楚、发 ::warning:: 注解，并且**退出 0**（原字体照常
    发布，站点不受影响）。
    """
    def fake_import(name):
        raise ImportError(f"No module named {name!r}")

    monkeypatch.setattr(subset_icons, "_import_module", fake_import)
    assert subset_icons._fonttools_ready() is False

    out = capsys.readouterr().out
    assert "::warning::" in out, "缺依赖时应该发一条 ::warning:: 注解"
    assert "fontTools" in out, "警告里要说清缺的是哪个模块"


def test_the_subset_shrinks_the_font_and_keeps_the_glyphs(tmp_path: Path) -> None:
    """裁完的字体必须更小，而且用到的码位一个不少。

    需要 fontTools；site-guard 的 CI 只装了 pytest，这项在那边是跳过的
    （裁剪由 build 那个 job 自己装 fontTools 跑）。

    裁的是 TTF 不是 woff2：2026-11-15 实测 runner 上的 brotli 解 woff2 会
    报 "brotli: decoder failed"，所以工具改成裁 TTF（fontTools 原生支持），
    再把 CSS 里的 woff2 引用摘掉。
    """
    pytest.importorskip("fontTools")

    webfonts = tmp_path / "webfonts"
    webfonts.mkdir()
    for name in ("fa-solid-900.ttf", "fa-brands-400.ttf"):
        source = THEME / "source" / "libs" / "awesome" / "webfonts" / name
        if not source.is_file():
            pytest.skip(f"仓库里没有 {name}")
        shutil.copy2(source, webfonts / name)

    css = FA_CSS.read_text(encoding="utf-8")
    icons, _ = subset_icons._parse_css(css)

    kept_solid = {icons["fa-search"], icons["fa-database"]}
    kept_brands = {icons["fa-github"]}

    for name, keep in (
        ("fa-solid-900.ttf", kept_solid),
        ("fa-brands-400.ttf", kept_brands),
    ):
        target = webfonts / name
        before = target.stat().st_size
        subset_icons._subset_font(target, target.with_suffix(".out.ttf"), keep)
        out = target.with_suffix(".out.ttf")
        after = out.stat().st_size
        assert after < before, f"{name} 裁完没有变小"
        available = subset_icons._cmap_codepoints(out)
        assert keep <= available, f"{name} 裁完缺字形"


def test_the_css_stops_pointing_at_the_whole_woff2(tmp_path: Path) -> None:
    """CSS 里必须摘掉 woff2 那条引用，否则浏览器还是下完整的大字体。

    CSS 的 ``src`` 列表是"按顺序挑第一个支持的格式"——只裁 TTF 而不摘
    woff2，浏览器照样去下 151 KB 的完整 woff2，等于一点没省。
    """
    css = tmp_path / "all.min.css"
    css.write_text(
        "@font-face{font-family:\"FA\";src:url(../webfonts/fa-solid-900.woff2) "
        "format(\"woff2\"),url(../webfonts/fa-solid-900.ttf) format(\"truetype\")}",
        encoding="utf-8",
    )
    patched = subset_icons._patch_css(css, ["fa-solid-900"])
    assert patched == 1, "应当摘掉一处 woff2 引用"
    text = css.read_text(encoding="utf-8")
    assert "fa-solid-900.woff2" not in text, "woff2 引用还在"
    assert "fa-solid-900.ttf" in text, "ttf 引用被误删了"



