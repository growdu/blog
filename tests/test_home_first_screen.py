"""首页的第一屏：导航栏里的一句定位 + 统计条，不该再是别的。

**背景**：首页的第一屏曾经是 ``_partial/index-cover`` 渲染的一个 Materialize
carousel——首张 ``about-cover`` 铺着主题默认的模糊橙树照片，上面是打字机、
口号「技术·学习·实践·人生·哲学」和四个统计。``my.css`` 里由
``patch-theme.py`` 注入的 ``RESPONSIVE-HERO-FIX`` 段把它撑到
``min-height: calc(100vh - 64px)``。

**后果**：统计条、学习路径、三个 tab 全部落在首屏之外。一个技术博客的第一
印象是「风景摄影 + 五词口号」，爬虫和分享卡片拿到的也是那张风景照。

**后来发生的事**（这一串改动都是「首页做减法」）：

* 2026-11-18：首屏换成一句定位；「最新一期」「三篇代表作」「文章区」
  三块删掉；统计条挪到了最上面。
* 2026-11-19：首屏里的搜索框、分类徽章、打字机退休。
* **2026-11-19（第二次）：那句定位搬到了顶部导航栏** —— 紧跟在站名
  「growdu」后面。首页正文只剩统计条 + 学习路径，正好一屏。

**这里断言的是行为契约**：

1. 首页不再渲染那个 cover carousel；
2. **统计条排在最上面**——读者第一眼看到的应该是「这个站有多少东西」
   （580 篇 / 175w 字 / 2701 天 / 64 个分类）；
3. 定位句住在**导航栏**里，紧跟站名 —— 而且它是站名后面那一块，
   不是导航栏下面又一行；
4. 定位句读 ``config.home_hero_lead`` 那句短话，没配就退回
   ``config.description``；它不再重复分类清单（那行小标签）；
5. 首页正文里**不再有首屏那块** —— ``home-hero.ejs`` 整个删掉了，
   留着就是留一份没人渲染的模板；
6. 首页那两段**不带 ``data-aos``** —— AOS 的 fade-up 会把内容整体往下
   挪 100px 再淡入，那 100px 让页面在动画期间比视口高出一截，
   滚动条闪一下、内容跳一下。「正好一屏」的版面不要这种入场动画；
7. ``patch-theme.py`` 不再往首屏注入分类徽章和打字机 —— 只删模板不删
   注入，CI 构建一次它就又长回来。

另外两条是给 ``patch-theme.py`` 的：它曾经拥有那段 hero CSS，也曾经往
hero partial 里注入分类徽章和打字机。hero 换掉之后，这两样都得跟着走——
CSS 要**从 my.css 里剥掉**（不能只是不再注入，留下来的死规则照样
占着 100vh），注入也要跟着退休。

放在根级 ``tests/``，随 ``site-guard.yml`` 进 CI。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
THEME = REPO / "themes" / "matery"
LAYOUT = THEME / "layout"
PARTIAL = LAYOUT / "_partial"

INDEX_EJS = LAYOUT / "index.ejs"
HOME_CONTENT = PARTIAL / "home-content.ejs"
HOME_HERO = PARTIAL / "home-hero.ejs"
HEADER = PARTIAL / "header.ejs"
LEARNING_PATH = PARTIAL / "learning-path.ejs"
MY_CSS = THEME / "source" / "css" / "my.css"
TECH_CSS = THEME / "source" / "css" / "tech.css"
LAYOUT_EJS = LAYOUT / "layout.ejs"
MAIN_STYLE = PARTIAL / "main-style.ejs"
PATCH_THEME = REPO / "tools" / "patch-theme.py"
SYNC_HEXO = REPO / "tools" / "sync-hexo.py"
FEATURED_JSON = REPO / "data" / "featured.json"


def _read(path: Path) -> str:
    assert path.is_file(), "找不到 {}".format(path)
    return path.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """去掉 ``<%# ... %>`` 注释与 ``/* ... */`` CSS 注释。

    注释里提到「定位句」「首屏」这些词不算真的用了它们。
    """
    text = re.sub(r"<%#.*?%>", "", text, flags=re.S)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


# --- 1. cover carousel 不再被渲染 ------------------------------------------


def test_the_homepage_no_longer_renders_the_cover_carousel():
    """首页不再渲染 ``_partial/index-cover``。

    断言的是**调用点没了**，不是「partial 文件还在」——文件可以留在仓库里
    （主题自带的），只要没人渲染它。
    """
    index = _read(INDEX_EJS)

    assert "_partial/index-cover" not in index, (
        "index.ejs 还在渲染 index-cover —— 全屏照片首屏没去掉"
    )


def test_the_cover_carousel_css_is_gone_from_the_patched_stylesheet():
    """``my.css`` 里不再有 ``.index-cover`` 的规则。

    ``my.css`` 由 ``patch-theme.py`` 拥有。hero 换掉之后，那段
    ``RESPONSIVE-HERO-FIX`` 规则（``min-height: calc(100vh - 64px)``）
    成了死代码——但死代码还在，就说明「首屏仍然占满一屏」这件事没有真的
    被处理掉，下次有人改主题样式时它会莫名其妙地生效。
    """
    css = _read(MY_CSS)

    assert "RESPONSIVE-HERO-FIX" not in css, (
        "my.css 里还留着 RESPONSIVE-HERO-FIX 段 —— 那段规则把首屏撑到 100vh"
    )
    assert ".index-cover" not in css, "my.css 里还留着 .index-cover 规则"


# --- 2. 统计条在最上面 -----------------------------------------------------


def test_the_stats_banner_is_the_first_thing_in_the_homepage_body():
    """``stats-banner`` 必须在学习路径之前。

    2026-11-19：统计条从「定位句下面」挪到了「最上面」。访客第一眼看到的
    应该是「这个站有多少东西」（580 篇 / 175w 字 / 2701 天 / 64 个分类）。

    顺序反过来的话，第一眼是那一句口号 —— 而口号不回答「这站有多少内容」，
    那是新访客最先想知道的事。
    """
    content = _read(HOME_CONTENT)

    stats_at = content.find("stats-banner")
    learning_at = content.find("partial('_partial/learning-path')")

    assert stats_at != -1, "home-content.ejs 里没有 stats-banner（结构变了？）"
    assert learning_at != -1, "home-content.ejs 里没有渲染学习路径"
    assert stats_at < learning_at, (
        "首页从上到下应该是：统计条 → 学习路径"
    )


def test_the_stats_banner_sits_in_its_own_section_at_the_top():
    """统计条有自己的 ``<section class="home-stats">``，在学习路径之前。

    它是 body 的直接子元素（flex 列的第一项），不是塞在别的容器里 ——
    「在最上面」得在 DOM 顺序上成立，才谈得上排在最上面。
    """
    content = _read(HOME_CONTENT)

    assert '<section class="home-stats"' in content, (
        "统计条没有自己的 section —— 它的位置就由外层容器决定了"
    )
    stats_at = content.find('<section class="home-stats"')
    learning_at = content.find("partial('_partial/learning-path')")

    assert stats_at != -1, "home-content.ejs 里没有 home-stats 那一段"
    assert learning_at != -1, "home-content.ejs 里没有渲染学习路径"
    assert stats_at < learning_at, "home-stats 必须在学习路径之前"


# --- 3. 定位句搬到导航栏里 ---------------------------------------------------


def test_the_hero_partial_is_gone():
    """``home-hero.ejs`` 整个删掉了。

    定位句搬到了导航栏，首屏那块就没有内容了。留着一个没人渲染的
    模板，下一个人会以为「改首屏要改它」——然后改了个没人用的东西。
    """
    assert not HOME_HERO.exists(), (
        "home-hero.ejs 还在 —— 定位句已经搬进导航栏了，这块没人渲染"
    )


def test_the_homepage_body_no_longer_renders_the_hero():
    """首页正文里不再渲染首屏那块。"""
    content = _strip_comments(_read(HOME_CONTENT))

    assert "home-hero" not in content, (
        "home-content.ejs 里还在渲染 home-hero —— 定位句已经搬进导航栏了"
    )


def test_the_tagline_sits_right_after_the_site_title_in_the_navbar():
    """定位句住在导航栏里，**紧跟在站名后面**。

    2026-11-19：定位句从首屏搬到了导航栏。站名「growdu」后面跟一句
    「让写代码成为一种习惯」——第一眼看到的是它，而不是要往下滚才看到。

    守两件事：一是在导航栏模板里（不在首页正文里），二是排在
    ``logo-span``（站名）**之后** —— 顺序反了就成了「口号 · 站名」。
    """
    header = _read(HEADER)

    span_at = header.find('class="logo-span"')
    tagline_at = header.find('class="logo-tagline"')

    assert tagline_at != -1, (
        "header.ejs 里没有 logo-tagline —— 定位句没搬到导航栏里"
    )
    assert span_at != -1, "header.ejs 里找不到站名（logo-span）"
    assert span_at < tagline_at, (
        "定位句要排在站名后面 —— 现在是「口号 · 站名」"
    )


def test_the_tagline_is_read_from_the_config():
    """定位句读 ``config.home_hero_lead``，没配就退回 ``config.description``。

    ``config.description`` 是给搜索引擎看的那句长描述；``home_hero_lead``
    是给人看的那句短话。两处都不在模板里硬编码，改配置时不会两处对不上。
    """
    header = _read(HEADER)

    assert re.search(
        r"config\.home_hero_lead\s*\|\|\s*config\.description", header
    ), "导航栏里的定位句应当是 config.home_hero_lead || config.description"


def test_the_hero_lead_is_a_short_sentence_and_not_the_seo_description():
    """导航栏里那句是**短句**，不是 SEO 用的那句长描述。

    ``config.description`` 是给搜索引擎看的（九十多个字、顿号串），
    挂在站名旁边读着像关键词堆砌。

    所以：短句单独放一个配置项 ``home_hero_lead``，长句留给 meta。
    """
    config = _read(REPO / "_config.yml")

    assert "home_hero_lead:" in config, "_config.yml 里应当有 home_hero_lead 这一句"

    lead = re.search(r"^home_hero_lead:\s*(.+)$", config, re.M)
    assert lead, "_config.yml 里读不出 home_hero_lead 的值"
    value = lead.group(1).strip().strip("'\"")
    assert value, "home_hero_lead 不能是空的"
    assert len(value) <= 24, (
        "定位句要是一句话，不是一段话：{}（{} 个字）".format(value, len(value))
    )


def test_the_tagline_does_not_repeat_the_category_list():
    """导航栏里不再有一行「技术·学习·实践·人生·哲学」的小标签。

    它列的就是下面那 9 个徽章里的同一批东西，留着是同一句话出现两遍。
    """
    header = _strip_comments(_read(HEADER))

    assert "config.subtitle" not in header, (
        "导航栏里不该再有一行重复分类清单的小标签"
    )


def test_the_built_home_page_shows_the_short_lead_in_the_navbar():
    """构建产物里，导航栏里是那句短句——不是 SEO 的长描述。

    对着 ``public/index.html`` 查，不是对着模板查：模板对了、产物没对，
    中间隔着的正是 sync-hexo 和 patch-theme 那两步。
    """
    built = REPO / "public" / "index.html"
    if not built.is_file():
        import pytest

        pytest.skip("还没构建（public/index.html 不存在）")

    html = built.read_text(encoding="utf-8")
    m = re.search(r'<h1 class="logo-tagline">(.*?)</h1>', html, re.S)
    assert m, "首页导航栏里的 h1 不见了"
    lead = m.group(1).strip()

    config = _read(REPO / "_config.yml")
    m2 = re.search(r"^home_hero_lead:\s*(.+)$", config, re.M)
    assert m2, "_config.yml 里没有 home_hero_lead"
    expect = m2.group(1).strip().strip("'\"")
    assert lead == expect, "导航栏里的是「{}」，配置里写的是「{}」".format(lead, expect)
    assert len(lead) <= 24, "导航栏里那句太长了：{}".format(lead)
    assert "home-hero__eyebrow" not in html, "首页还有那行重复分类清单的小标签"
    assert "技术·学习·实践·人生·哲学" not in html, (
        "首页还在显示那行「技术·学习·实践·人生·哲学」"
    )


def test_the_home_page_only_has_one_h1():
    """首页只有一个 h1 —— 导航栏里那句定位。

    首页原来那个 h1 在首屏那块里，首屏退休后就没有了。定位句搬到导航栏
    之后，h1 跟着它走（首页的 h1 就是这句定位）；别的页面 h1 是文章标题，
    那里用的是 span —— 两处不会打架。
    """
    built = REPO / "public" / "index.html"
    if not built.is_file():
        import pytest

        pytest.skip("还没构建（public/index.html 不存在）")

    html = built.read_text(encoding="utf-8")
    h1s = re.findall(r"<h1\b[^>]*>(.*?)</h1>", html, re.S)

    assert len(h1s) == 1, "首页有 {} 个 h1：{}".format(len(h1s), h1s)
    assert "logo-tagline" in html, "首页的 h1 不是导航栏里那句定位"


# --- 4. 首页那两段不要入场动画 ---------------------------------------------


def test_the_homepage_sections_have_no_aos_animation():
    """首页的那两段不带 ``data-aos``。

    AOS 的 fade-up 是「先往下挪 100px，再淡入」：那 100px 让页面在动画
    期间比视口高出一截（实测：innerHeight 813、scrollHeight 902），
    滚动条会闪一下，内容还会跳一下；动画结束后才落回一屏。

    首页是一个「正好一屏」的固定版面，不要这种入场动画。
    """
    for path in (HOME_CONTENT, LEARNING_PATH):
        content = _strip_comments(_read(path))

        assert "data-aos" not in content, (
            "{} 又带上了 data-aos —— 那 100px 的入场位移会让页面在动画期间"
            "比视口高，滚动条会闪一下".format(path.name)
        )


# --- 5. 首屏不再摆「三篇代表作」 --------------------------------------------


def test_the_theme_no_longer_reads_the_curated_list():
    """主题里不再读 ``site.data.featured``。

    2026-11-18：三篇代表作整块删掉了（首屏要回答的是「这个站是什么」，
    不是「作者推荐什么」）。
    """
    for ejs in sorted(LAYOUT.rglob("*.ejs")):
        text = _read(ejs)
        assert "site.data.featured" not in text, (
            "{} 还在读 site.data.featured —— 策展清单已经退休".format(
                ejs.relative_to(REPO)
            )
        )


def test_the_curated_list_file_is_gone():
    """``data/featured.json`` 退休了。

    留着它就是留一份没人读的清单：作者改了它以为首屏会变，其实不会。
    """
    assert not FEATURED_JSON.exists(), (
        "data/featured.json 还在 —— 但已经没有人读它了"
    )


def test_the_sync_no_longer_copies_the_curated_list():
    """``sync-hexo.py`` 不再往 ``source/_data/`` 拷 featured.json。

    ``source/`` 是 gitignore 的构建目录；拷贝这一步没了，那份 JSON 也就
    不会被挂到 ``site.data`` 上——首屏少一个数据源，而模板已经不读它了。
    """
    sync = _read(SYNC_HEXO)

    assert "featured.json" not in sync, (
        "sync-hexo.py 里还提到 featured.json —— 策展清单已经退休"
    )


# --- 6. patch-theme.py 的两处跟着走 -----------------------------------------


def test_the_patcher_no_longer_owns_the_hero_css():
    """``patch-theme.py`` 不再注入 ``RESPONSIVE-HERO-FIX``。

    只停止注入不够：my.css 里已经有一段了（见上面那条测试）。
    两边都要管。
    """
    patcher = _read(PATCH_THEME)

    assert "RESPONSIVE-HERO-FIX" not in patcher, (
        "patch-theme.py 还在注入 RESPONSIVE-HERO-FIX —— hero 换掉了它也该退休"
    )


def test_the_patcher_strips_the_hero_css_it_used_to_inject():
    """patcher 要有「把已注入的那段从 my.css 里剥掉」的逻辑。

    只停止注入的话，仓库里的 my.css 会永远留着旧段——本地构建一次、
    CI 构建一次，两边的 my.css 就不一样了。
    """
    patcher = _read(PATCH_THEME)

    assert re.search(r"re\.sub|subn\(", patcher), "patch-theme.py 里没有替换逻辑"
    assert "my.css" in patcher, "patch-theme.py 没有动过 my.css"


def test_the_patcher_no_longer_injects_the_hero_badges():
    """``patch-theme.py`` 不再往首页注入分类徽章 + 打字机。

    2026-11-19：首屏那块整个退休了（定位句搬进了导航栏），注入更没有
    地方可去。
    """
    patcher = _read(PATCH_THEME)

    assert "HERO-BADGES" not in patcher, (
        "patch-theme.py 还在往首页注入分类徽章 —— 只删模板不删注入，"
        "CI 构建一次它就又长回来"
    )
    assert "heroBadges" not in patcher, (
        "patch-theme.py 里还留着分类徽章的清单 —— 那一块已经退休"
    )


def test_the_patcher_no_longer_touches_the_hero_partial():
    """patcher 不再碰首屏那块模板。

    模板整个删掉了，patcher 里那段「剥掉已注入的徽章」也就没有对象了 ——
    留着只会让人以为首页还有那么一块。
    """
    patcher = _read(PATCH_THEME)

    assert 'os.path.join(theme_dir, "layout", "_partial", "home-hero.ejs")' not in patcher, (
        "patch-theme.py 里还在操作首屏那块模板 —— 那块已经退休"
    )


# --- 7. 首屏的搜索框与分类徽章退休了 ---------------------------------------


def test_the_homepage_has_no_search_box():
    """首屏不再有那个只搜标题的搜索框。

    顶部导航里本来就有全文搜索（``_partial/search.ejs``）。首屏再来一个
    只搜标题的框，是同一个去处的第二个入口 —— 而且它自己还写着
    「按标题搜索 · 全文搜索用顶部导航」，等于在首屏提醒读者「真正的
    搜索在别处」。
    """
    for path in (HOME_CONTENT, HEADER):
        text = _strip_comments(_read(path))

        assert "homeSearch" not in text, "{} 里还有首屏那个搜索框".format(path.name)
        assert "home-hero__search" not in text, (
            "{} 里还有首屏那个搜索框".format(path.name)
        )


def test_the_homepage_has_no_category_badges():
    """首屏不再有那一排分类徽章。

    导航栏里已经有「分类」入口，徽章是同一份清单的第二份。
    """
    for path in (HOME_CONTENT, HEADER):
        text = _strip_comments(_read(path))

        assert "hero-tech" not in text, "{} 里还有分类徽章".format(path.name)
        assert "hero-badge" not in text, "{} 里还有分类徽章".format(path.name)
        assert "hero-typing" not in text, "{} 里还有打字机".format(path.name)
        assert "home-hero__badges" not in text, "{} 里还有徽章容器".format(path.name)


def test_the_dead_hero_styles_are_gone():
    """徽章 / 打字机 / 搜索框 / 首屏本身的样式都退休了。

    死规则留着，下一个人会以为首页还有那么一块 —— 或者更糟：改首屏
    样式时去改一段没人用的规则，改了半天看不出效果。
    """
    css = _strip_comments(_read(TECH_CSS))
    my_css = _strip_comments(_read(MY_CSS))

    for dead in ("home-hero__search", "hero-tech", "hero-badge", "hero-typing"):
        assert dead not in css, "tech.css 里还留着 {} 的样式".format(dead)
        assert dead not in my_css, "my.css 里还留着 {} 的样式".format(dead)

    assert ".home-hero" not in css, (
        "tech.css 里还留着 .home-hero 的样式 —— 那块已经退休"
    )
    assert ".home-hero" not in my_css, (
        "my.css 里还留着 .home-hero 的样式 —— 那块已经退休"
    )


def test_the_tagline_has_a_style_of_its_own():
    """导航栏里那句定位有自己的样式。

    新样式只放 ``tech.css``（docs/blog/重构方案.md §5.4）—— 而且得
    真的有：定位句是 ``<h1>``（首页），matery 的 h1 是 4.2rem，不重置
    的话它会把这个导航栏撑成两行。
    """
    css = _strip_comments(_read(TECH_CSS))

    assert ".logo-tagline" in css, "tech.css 里没有 .logo-tagline 的样式"


def test_the_hero_stylesheet_is_linked_from_the_layout():
    """``tech.css`` 要在页面里被引进来。

    主题的 CSS 链接集中在 ``_partial/main-style.ejs``（``layout.ejs`` 只
    include 它），所以断言落在那个文件上。

    新建了 CSS 文件但没 link，页面会安静地没有样式——不报错，只是不好看。
    """
    main_style = _read(MAIN_STYLE)

    assert "tech.css" in main_style, "main-style.ejs 没有引用 tech.css"
