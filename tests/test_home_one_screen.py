"""首页要一屏放下：统计条 + 学习路径。

**为什么**：2026-11-18 之前，首页是「首屏 + 统计条 + 最新一期 + 学习路径
+ 18 张文章卡片」—— 要滚两屏半才到底。那几块（文章区、最新一期、代表作）
删掉之后，首页只剩三段，正好做得成一屏。

**2026-11-19 再删两块**：首屏的搜索框和分类徽章（+ 打字机）也没了；
统计条挪到了最上面。

**2026-11-19（第三次）**：那句定位（.home-hero）也搬进了顶部导航栏 ——
紧跟在站名「growdu」后面。于是首页正文只剩两段：统计条 + 学习路径。

**怎么做的**：``layout.ejs`` 给首页的 ``<body>`` 加一个 ``home-page`` 类，
``tech.css`` 挂在它上面：

* ``body.home-page`` 变成一个高度等于视口的 flex 列；
* 统计条内容固定（压扁）；
* 学习路径吃掉剩下的空间，卡片网格跟着长高铺满。

**这里守的是六件事**：

1. ``home-page`` 只加在**首页第一页**上 —— 别的页面带了这个类，
   文章页会被压成一屏（每篇文章只剩一屏高）；
2. 这套布局是**自适应**的：窄屏（< 1100px）整段不生效，回到正常文档流；
   空间真的不够时滚的是学习路径面板自己，不是整页；
3. 学习路径的卡片按视口高度换排版：视口 900px 以上，卡片里竖着列出
   **全部阶段**（卡片被拉高到 280px，只放一个角标的话中间空一大块，看着
   像漏了内容）；视口不够高就把 4 列换成 2 列 × 4 行，卡片变宽变矮，
   这时只列**第一个阶段**，后面折成「+N 个阶段」；
4. 统计条和学习路径都还在首页上（这是用户点名要留的两块）；
5. 首屏那块「从这里开始」已经退休 —— 它指的是 ``/learning/``，
   而首页下方就是学习路径面板本身，同一个去处摆两遍没有意义；
   面板的入口挪进了标题行（「看完整的学习地图」），不再单独占一行；
6. 统计条在 flex 列里排在**最上面**（``flex: 0 0 auto``），学习路径在
   最后 —— 顺序就是读者从上往下看到的顺序。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
THEME = REPO / "themes" / "matery"
LAYOUT_EJS = THEME / "layout" / "layout.ejs"
HOME_CONTENT = THEME / "layout" / "_partial" / "home-content.ejs"
LEARNING_PATH = THEME / "layout" / "_partial" / "learning-path.ejs"
TECH_CSS = THEME / "source" / "css" / "tech.css"
MY_CSS = THEME / "source" / "css" / "my.css"


def _read(path: Path) -> str:
    assert path.is_file(), "找不到 {}".format(path)
    return path.read_text(encoding="utf-8")


def _strip_css_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _home_page_block(css: str) -> str:
    """把 tech.css 里 ``body.home-page`` 那段规则抠出来。

    抠的是**选择器所在的媒体查询块** —— 「这段规则只在宽屏生效」这件事
    本身就是要守的，抠选择器会把它漏掉。
    """
    css = _strip_css_comments(css)
    for _query, block in _media_blocks(css):
        if "body.home-page" in block:
            return block
    return ""


def _media_blocks(css: str):
    """把 css 里的 ``@media`` 块拆成 (查询条件, 块内容)。

    只认一层嵌套 —— tech.css 里的媒体查询里没有再套媒体查询。
    """
    for m in re.finditer(r"@media([^{]*)\{", css):
        query = m.group(1).strip()
        i = m.end()
        depth = 1
        while i < len(css) and depth:
            if css[i] == "{":
                depth += 1
            elif css[i] == "}":
                depth -= 1
            i += 1
        yield query, css[m.end() : i - 1]


# --- 1. home-page 只加在首页 ------------------------------------------------


def test_the_homepage_body_carries_the_home_page_class():
    """首页的 ``<body>`` 要带 ``home-page``。"""
    layout = _read(LAYOUT_EJS)

    assert "home-page" in layout, (
        "layout.ejs 里没有 home-page —— tech.css 那套「占满一屏」挂不上去"
    )


def test_the_home_page_class_is_only_for_the_first_home_page():
    """``home-page`` 只在首页第一页。

    条件里必须同时有 ``is_home()`` 和 ``page.current === 1``：少了后一个，
    /page/2/ 这些翻页也会被压成一屏；少了前一个，所有页面都跟着变。
    """
    layout = _read(LAYOUT_EJS)

    m = re.search(r"<body class=\"<%-([^%]*?)%>\">", layout, re.S)
    assert m, "layout.ejs 里找不到 <body class=...> 的写法"
    expr = m.group(1)

    assert "is_home()" in expr, "body class 的条件里没有 is_home()"
    assert "page.current === 1" in expr, (
        "body class 的条件里没有 page.current === 1 —— 翻页也会被压成一屏"
    )
    assert "home-page" in expr, "body class 的条件里没有 home-page"


# --- 2. 那套布局还在，而且只对宽屏生效 ---------------------------------------


def test_the_homepage_fills_the_viewport_with_the_learning_path():
    """学习路径要吃掉统计条以外的空间。

    三条缺一不可：``body`` 定高（flex 的收缩要有一个确定的高度）、
    学习路径 ``flex: 1``、网格的行高跟着长高。
    """
    block = _home_page_block(_read(TECH_CSS))

    assert block, "tech.css 里找不到 body.home-page 那段规则"
    assert re.search(r"body\.home-page\s*\{[^}]*height:\s*100dvh", block, re.S), (
        "body.home-page 没有定高 —— 学习路径吃不掉剩下的空间"
    )
    assert re.search(r"\.learning-path\s*\{[^}]*flex:\s*1", block, re.S), (
        "学习路径面板没有 flex: 1 —— 它不会占满剩下的空间"
    )
    assert "grid-auto-rows" in block, (
        "卡片网格没有 grid-auto-rows —— 卡片不会跟着长高铺满"
    )
    assert re.search(r"grid-auto-rows:\s*minmax\(min-content,\s*1fr\)", block), (
        "卡片行高不是 minmax(min-content, 1fr) —— 面板下方会空出一大块，"
        "首页看着像少了一半内容"
    )


def test_the_fill_layout_is_scoped_to_wide_viewports():
    """窄屏不套这套布局。

    1100px 以下（平板、手机）强行塞进一屏，字会被压得没法看；那时候
    页面就该正常滚动。
    """
    css = _strip_css_comments(_read(TECH_CSS))

    queries = [q for q, block in _media_blocks(css) if "body.home-page" in block]
    assert queries, "找不到 body.home-page 那段所在的媒体查询"

    for query in queries:
        assert "min-width" in query, (
            "那段布局没有 min-width 限制：{}".format(query)
        )
        width = int(re.search(r"min-width:\s*(\d+)px", query).group(1))
        assert width >= 1024, "宽屏门槛太低了：{}px".format(width)


def test_the_learning_path_scrolls_itself_instead_of_the_page():
    """空间不够时滚的是面板自己，不是整页。

    整页滚动会把统计条一起推走 —— 读者想回头看一眼那四个数字，
    得一路滚回顶部。
    """
    block = _home_page_block(_read(TECH_CSS))

    assert re.search(r"\.lane-grid--tracks\s*\{[^}]*overflow:\s*auto", block, re.S), (
        "卡片网格没有 overflow: auto —— 空间不够时整页会跟着滚"
    )


def test_the_layout_adapts_to_short_and_tall_screens():
    """屏幕高矮不一样，首页得给两种不一样的排版。

    矮屏（老笔记本、开着开发者工具的浏览器）：把卡片里那行简介收起来
    （整句在赛道页上有）。
    统计条和学习路径本身不动，那是首页要看的东西。

    高屏（1920×1080 这类）：卡片被拉高，简介那行放开成两行——地方多，
    一句话说不完的话没必要截断。
    """
    css = _strip_css_comments(_read(TECH_CSS))
    queries = [q for q, block in _media_blocks(css) if "body.home-page" in block]

    assert any("max-height" in q for q in queries), (
        "没有针对矮屏的排版 —— 视口矮一点首页就要滚"
    )
    assert any("min-height" in q for q in queries), (
        "没有针对高屏的排版 —— 屏幕大一点卡片里的话就被白白截断"
    )


# --- 3. 卡片在首页只列第一个阶段 --------------------------------------------


def test_the_track_card_folds_the_stages_into_a_plus_n_chip():
    """八张卡各列全部阶段的话卡片高度翻三倍。

    首页只列第一个阶段，后面折成「+N 个阶段」；完整的阶段表在
    ``/learning/<track>/`` 那一页。
    """
    template = _read(LEARNING_PATH)

    assert "lane-card__stage--rest" in template, (
        "learning-path.ejs 里没有「+N 个阶段」那个角标"
    )
    assert "lane-card__stage-title" in template, (
        "阶段标题没有单独包一层 —— 首页没法只留阶段编号"
    )
    assert re.search(r"_stages\.length\s*-\s*1", template), (
        "「+N 个阶段」里的 N 应该是阶段总数减一"
    )


def test_the_homepage_folds_the_stages_when_the_screen_is_short():
    """卡片不够高的时候，首页只留第一个阶段（和「+N 个阶段」那个角标）。

    竖着列出全部阶段是高屏那一档的事（见下一条测试）：卡片只有 90px 高
    的时候，八个阶段列不下。
    """
    block = _home_page_block(_read(TECH_CSS))

    assert re.search(
        r"\.lane-card__stage:not\(:first-child\):not\(\.lane-card__stage--rest\)",
        block,
    ), "首页没有把第一个以外的阶段藏起来"


def test_tall_screens_list_every_stage_instead_of_the_plus_n_chip():
    """高屏（视口 900px 以上）：卡片里竖着列出全部阶段。

    卡片被拉高到 280px，里面只有标题、简介和一个角标的话，卡片中间空一
    大块 —— 看着像漏了内容。列出阶段，空出来的地方就是阶段本身。

    守三件事：折叠的阶段在高屏被放出来、「+N 个阶段」角标收起来（一个阶段
    都没折，角标是多余的）、阶段竖着排（横着排的话卡片中间还是空的）。
    """
    css = _strip_css_comments(_read(TECH_CSS))
    tall = [
        block
        for query, block in _media_blocks(css)
        if "body.home-page" in block and "min-height: 900px" in query
    ]
    assert tall, "没有针对高屏（视口 900px 以上）的排版"
    block = tall[0]

    assert re.search(
        r"\.lane-card__stages\s+\.lane-card__stage:not\(\.lane-card__stage--rest\)",
        block,
    ), "高屏那一档没有把折叠的阶段放出来"
    assert re.search(r"\.lane-card__stage--rest\s*\{[^}]*display:\s*none", block), (
        "高屏那一档还留着「+N 个阶段」角标 —— 一个阶段都没折，角标是多余的"
    )
    assert re.search(
        r"\.lane-card__stages\s*\{[^}]*flex-direction:\s*column", block, re.S
    ), "高屏那一档的阶段没有竖着排 —— 卡片中间还是空的"


def test_short_screens_lay_the_cards_out_in_two_columns():
    """视口不够高的时候，八张卡排 2 列 × 4 行。

    4 列 × 2 行的话每张卡只有 150px 高 —— 标题、简介、角标挤在一起，
    看清都看不清。2 列 × 4 行：卡片变宽变矮，八张卡正好占满面板。
    """
    css = _strip_css_comments(_read(TECH_CSS))
    short = [
        block
        for query, block in _media_blocks(css)
        if "body.home-page" in block and "max-height: 899px" in query
    ]
    assert short, "没有针对中屏（视口 800~899px）的排版"

    assert re.search(
        r"grid-template-columns:\s*repeat\(2,\s*1fr\)", short[0]
    ), "中屏那一档没有把卡片改成 2 列 —— 每张卡只有 150px 高，字挤成一团"


# --- 4. 要留的两块还在 ------------------------------------------------------


def test_the_stats_banner_and_the_learning_path_stay_on_the_homepage():
    """统计条和学习路径是首页要留的两块。"""
    content = _read(HOME_CONTENT)

    assert "stats-banner" in content, "首页的统计条没了"
    assert "partial('_partial/learning-path')" in content, "首页的学习路径没了"


def test_the_stats_banner_is_the_first_thing_in_the_flex_column():
    """统计条排在最上面。

    2026-11-19：统计条从「定位句下面」挪到了「最上面」。flex 列里的顺序
    就是读者从上往下看到的顺序 —— 统计条得是那一列的第一项。
    """
    content = _read(HOME_CONTENT)

    stats_at = content.find("home-stats")
    learning_at = content.find("partial('_partial/learning-path')")

    assert stats_at != -1, "home-content.ejs 里没有 home-stats"
    assert learning_at != -1, "home-content.ejs 里没有渲染学习路径"
    assert stats_at < learning_at, (
        "首页从上到下应该是：统计条 → 学习路径"
    )

    block = _home_page_block(_read(TECH_CSS))
    assert re.search(r"\.home-stats\s*\{[^}]*flex:\s*0 0 auto", block, re.S), (
        ".home-stats 没有固定高度 —— 它是 flex 列的第一项，不能被压扁"
    )


# --- 5. 首屏那块「从这里开始」退休了 ----------------------------------------


def test_the_start_cta_is_gone_from_the_hero():
    """首页不再有「从这里开始」按钮。

    它指的是 ``/learning/``，而首页下方就是学习路径面板本身——同一个去处
    在首屏摆一遍、下面再摆一遍没有意义，而且那 47px 是从学习路径那里
    借来的（首页要做成正好一屏）。
    """
    content = _read(HOME_CONTENT)

    assert "home-hero__start" not in content, (
        "首屏那块「从这里开始」又回来了 —— 入口在下面的学习路径面板里"
    )
    for css_path in (TECH_CSS, MY_CSS):
        css = _strip_css_comments(_read(css_path))
        assert "home-hero__start" not in css, (
            "{} 里还留着 .home-hero__start 的样式 —— 用它的那块已经删了".format(
                css_path.name
            )
        )


def test_the_learning_map_link_sits_in_the_title_row():
    """「看完整的学习地图」住在标题行里，不再单独占一行。

    它原来单独占一行（32px）。首页要做成正好一屏，那一行省下来给卡片；
    位置挪到标题行右边——一样好找。
    """
    template = _read(LEARNING_PATH)

    title_row = re.search(
        r"<div class=\"section-title\">(.*?)</div>", template, re.S
    )
    assert title_row, "learning-path.ejs 里找不到标题行"
    row = title_row.group(1)

    assert "learning-path__all-link" in row, (
        "「看完整的学习地图」不在标题行里 —— 它单独占一行，首页要多滚一屏"
    )
    assert "/learning/" in row, "标题行里的链接没有指向 /learning/"

    # 单独占一行的那层外壳已经删掉了：链接外面只有标题行这一个容器。
    assert 'class="learning-path__all"' not in template, (
        "「看完整的学习地图」又套回单独一行了"
    )
    css = _strip_css_comments(_read(TECH_CSS))
    assert ".learning-path__all " not in css and ".learning-path__all{" not in css, (
        "my.css/tech.css 里还留着 .learning-path__all 那层外壳的样式"
    )
