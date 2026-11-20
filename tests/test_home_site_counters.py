"""首页顶上的两个访问量格子：不蒜子的数、只出现一次、摆在一行里。

**背景**：「总访问量」「总访问人数」原来只在 footer 里 —— 读者要滚到
最底下才看得到「这站有多少人看过」。2026-11-20 它们被搬到了首页最上面
的统计条里，跟「580 篇文章 / 175w 字 / 2702 天」并排。

**这里守的是三件事**：

1. 两个格子确实在统计条里（不在别的段落里），且排在学习路径之前；
2. **整个页面里只有一组这样的 id** —— 不蒜子的脚本按固定的 id 找元素
   （``busuanzi_value_site_pv`` / ``busuanzi_value_site_uv``），一个页面里
   同名的 id 只能有一个。首页要是既在顶上渲染一次、footer 里又渲染一次，
   脚本只会填到先出现的那一个，footer 里就剩一个「总访问量：」的空壳；
3. CSS 那边统计条是**五列** —— 少一列的话五张卡会挤成两行，首页那个
   「正好一屏」的版面就被顶破了。``my.css`` 里的那段是
   ``patch-theme.py`` 注入的，两边得一致。

放在根级 ``tests/``，随 ``site-guard.yml`` 进 CI。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
THEME = REPO / "themes" / "matery"
LAYOUT = THEME / "layout"
PARTIAL = LAYOUT / "_partial"

HOME_CONTENT = PARTIAL / "home-content.ejs"
FOOTER = PARTIAL / "footer.ejs"
MY_CSS = THEME / "source" / "css" / "my.css"
PATCH_THEME = REPO / "tools" / "patch-theme.py"

PV_ID = "busuanzi_value_site_pv"
UV_ID = "busuanzi_value_site_uv"


def _read(path: Path) -> str:
    assert path.is_file(), "找不到 {}".format(path)
    return path.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """去掉 ``<%# ... %>`` 注释与 ``/* ... */`` CSS 注释。"""
    text = re.sub(r"<%#.*?%>", "", text, flags=re.S)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


# --- 1. 两个格子在统计条里 --------------------------------------------------


def test_the_counters_sit_in_the_stats_banner():
    """两个访问量格子是统计条的一部分。

    它们得跟「篇文章 / 总字数 / 天持续更新」并排摆在最上面 —— 摆在
    别的段落里（比如塞进学习路径），就又变成「要往下翻才看得到」。
    """
    content = _read(HOME_CONTENT)

    banner_at = content.find('<div class="stats-banner">')
    assert banner_at != -1, "home-content.ejs 里没有 stats-banner"

    banner_end = content.find("</section>", banner_at)
    assert banner_end != -1, "stats-banner 的结构变了？"

    banner = content[banner_at:banner_end]
    assert PV_ID in banner, "总访问数不在统计条里"
    assert UV_ID in banner, "总访问人数不在统计条里"


def test_the_counters_come_before_the_learning_path():
    """两个格子排在学习路径之前 —— 统计条整体在最上面。"""
    content = _read(HOME_CONTENT)

    pv_at = content.find(PV_ID)
    uv_at = content.find(UV_ID)
    learning_at = content.find("partial('_partial/learning-path')")

    assert pv_at != -1 and uv_at != -1, "统计条里少了访问量格子"
    assert learning_at != -1, "home-content.ejs 里没有渲染学习路径"
    assert pv_at < learning_at and uv_at < learning_at, (
        "访问量格子要排在学习路径之前"
    )


def test_the_counters_carry_the_site_wide_labels():
    """两个格子的标签是「总访问量」「总访问人数」。

    标签读的是站点自己的 i18n（``siteTotalVisits`` /
    ``siteTotalVisitors``），不是模板里硬编码的中文 —— 换语言时
    footer 和首页说的是同一句话。
    """
    content = _read(HOME_CONTENT)

    assert "__('siteTotalVisits')" in content, "总访问量的标签没读 i18n"
    assert "__('siteTotalVisitors')" in content, "总访问人数的标签没读 i18n"


# --- 2. 一个页面里只有一组这样的 id ---------------------------------------


def test_the_footer_skips_the_counters_on_the_homepage():
    """首页的 footer 不再重复渲染这两个数。

    不蒜子的脚本是 ``document.getElementById`` 找元素的 —— 一个页面里
    同名的 id 有两个时，它只会填到先出现的那一个。首页的 footer 要是
    再渲染一遍，footer 里就剩「总访问量：」的空标签。
    """
    footer = _read(FOOTER)

    assert "showSiteCounters" in footer, (
        "footer.ejs 里没有 showSiteCounters —— 首页会同时出现两组 id"
    )
    assert "is_home()" in footer, (
        "footer.ejs 里的计数器没有区分首页 —— 首页会同时出现两组 id"
    )


def test_the_homepage_has_exactly_one_set_of_counter_ids():
    """构建产物里，首页**只有一组**访问量 id。

    对着 ``public/index.html`` 查，不是对着模板查：模板对了、产物没对，
    中间隔着的正是 sync-hexo 和 patch-theme 那两步。
    """
    built = REPO / "public" / "index.html"
    if not built.is_file():
        import pytest

        pytest.skip("还没构建（public/index.html 不存在）")

    html = built.read_text(encoding="utf-8")

    for counter_id in (PV_ID, UV_ID):
        assert html.count('id="{}"'.format(counter_id)) == 1, (
            "首页里 {} 出现了 {} 次 —— 脚本只会填到第一个".format(
                counter_id, html.count('id="{}"'.format(counter_id))
            )
        )

    # 两格都住在统计条里，而不是散落在别处。
    banner_at = html.find('class="stats-banner"')
    assert banner_at != -1, "构建产物里没有 stats-banner"
    assert html.find('id="{}"'.format(PV_ID)) > banner_at, (
        "总访问数不在统计条里"
    )


def test_other_pages_keep_the_footer_counters():
    """别的页面照旧在 footer 里显示这两个数。

    这次搬家只动首页 —— 文章页、归档页的 footer 一行没变。
    """
    built = REPO / "public" / "about" / "index.html"
    if not built.is_file():
        import pytest

        pytest.skip("还没构建（public/about/index.html 不存在）")

    html = built.read_text(encoding="utf-8")

    for counter_id in (PV_ID, UV_ID):
        assert 'id="{}"'.format(counter_id) in html, (
            "非首页的 footer 里没有 {} —— 这次搬家只该动首页".format(counter_id)
        )


# --- 3. 统计条是五列 --------------------------------------------------------


def test_the_stats_banner_has_five_columns():
    """统计条是五列 —— 五张卡排一行。

    少一列的话五张卡会挤成两行，首页那个「正好一屏」的版面就被顶破了。
    """
    css = _strip_comments(_read(MY_CSS))

    m = re.search(r"\.stats-banner\s*\{[^}]*grid-template-columns:\s*repeat\((\d+),\s*1fr\)", css)
    assert m, "my.css 里读不出统计条的列数"
    assert int(m.group(1)) == 5, (
        "统计条是 {} 列 —— 应该是 5 列（文章 / 字数 / 天数 / 访问量 / 访问人数）".format(
            m.group(1)
        )
    )


def test_the_patcher_and_the_stylesheet_agree_on_the_column_count():
    """``my.css`` 里那段是 ``patch-theme.py`` 注入的，两边得一致。

    只改 my.css 的话，CI 重新注入（或者哪天主题目录被重新同步）时，
    列数就被改回去了。
    """
    patcher = _read(PATCH_THEME)

    m = re.search(
        r"\.stats-banner \{\\n    display: grid;\\n"
        r"    grid-template-columns: repeat\((\d+), 1fr\);",
        patcher,
    )
    assert m, "patch-theme.py 里读不出统计条的列数"
    assert int(m.group(1)) == 5, (
        "patch-theme.py 注入的统计条是 {} 列 —— 应该是 5 列".format(m.group(1))
    )
