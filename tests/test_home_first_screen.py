"""首屏不该是一张风景照，也不该摆一堆入口。

**背景**：首页的第一屏是 ``_partial/index-cover`` 渲染的一个 Materialize
carousel——首张 ``about-cover`` 铺着主题默认的模糊橙树照片，上面是打字机、
口号「技术·学习·实践·人生·哲学」和四个统计。``my.css`` 里由
``patch-theme.py`` 注入的 ``RESPONSIVE-HERO-FIX`` 段把它撑到
``min-height: calc(100vh - 64px)``。

**后果**：统计条、学习路径、三个 tab 全部落在首屏之外。一个技术博客的第一
印象是「风景摄影 + 五词口号」，爬虫和分享卡片拿到的也是那张风景照。

**这里断言的是行为契约**：

1. 首页不再渲染那个 cover carousel；
2. **统计条排在最上面**——读者第一眼看到的应该是「这个站有多少东西」
   （580 篇 / 175w 字 / 2701 天 / 64 个分类），定位句压在它下面；
3. 首屏不是全屏的（全屏 = 还是在卖风景）；
4. 首屏带的是**站点定位**（读 ``config.home_hero_lead`` 那句短话，没配
   就退回 ``config.description``），不是一句硬编码的口号；首屏也不再有一行
   重复分类清单的小标签——那 9 个徽章已经列过一遍了；
5. 首屏不再摆「三篇代表作」——那三张卡上的分类全是「源码主线」，
   等于在首屏摆广告位。首屏要回答的是「这个站是什么、从哪儿开始」。

**2026-11-19 再删两块**：首屏的站内搜索框和分类徽章（+ 打字机）。
搜索框是顶部导航那个全文搜索的缩水版（只搜标题），徽章是导航栏「分类」
入口的第二份清单 —— 两个都是同一个去处的第二个入口。删掉之后首屏只剩
一句定位，统计条挪到了最上面。

另外两条是给 ``patch-theme.py`` 的：它曾经拥有那段 hero CSS，也曾经往
hero partial 里注入分类徽章和打字机。hero 换掉之后，这两样都得跟着走——
CSS 要**从 my.css 里剥掉**（不能只是不再注入，留下来的死规则照样
占着 100vh），注入也要跟着退休（只删模板不删注入，CI 构建一次它就又
长回来）。

放在根级 ``tests/``，随 ``site-guard.yml`` 进 CI。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
THEME = REPO / "themes" / "matery"
LAYOUT = THEME / "layout"
PARTIAL = LAYOUT / "_partial"

INDEX_EJS = LAYOUT / "index.ejs"
HOME_CONTENT = PARTIAL / "home-content.ejs"
HOME_HERO = PARTIAL / "home-hero.ejs"
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


def test_the_stats_banner_comes_first():
    """``stats-banner`` 必须在 ``home-hero`` 之前。

    2026-11-19：统计条挪到了最上面。访客第一眼看到的应该是「这个站有多
    少东西」（580 篇 / 175w 字 / 2701 天 / 64 个分类），定位句压在它下面。

    顺序反过来的话，第一眼是那一句口号 —— 而口号不回答「这站有多少内容」，
    那是新访客最先想知道的事。
    """
    content = _read(HOME_CONTENT)

    hero_at = content.find("home-hero")
    stats_at = content.find("stats-banner")

    assert hero_at != -1, "home-content.ejs 里没有渲染 home-hero"
    assert stats_at != -1, "home-content.ejs 里没有 stats-banner（结构变了？）"
    assert stats_at < hero_at, "stats-banner 必须排在 home-hero 之前"


def test_the_stats_banner_sits_in_its_own_section_at_the_top():
    """统计条有自己的 ``<section class="home-stats">``，在 hero 之前。

    它是 body 的直接子元素（flex 列的第一项），不是塞在别的容器里 ——
    「在最上面」得在 DOM 顺序上成立，才谈得上排在最上面。
    """
    content = _read(HOME_CONTENT)

    assert '<section class="home-stats"' in content, (
        "统计条没有自己的 section —— 它的位置就由外层容器决定了"
    )
    stats_at = content.find('<section class="home-stats"')
    hero_at = content.find("<%- partial('_partial/home-hero') %>")

    assert stats_at != -1, "home-content.ejs 里没有 home-stats 那一段"
    assert hero_at != -1, "home-content.ejs 里没有渲染 home-hero"
    assert stats_at < hero_at, "home-stats 必须在 home-hero 之前"


# --- 3. 首屏不是全屏的 ------------------------------------------------------


def test_the_hero_is_not_full_screen():
    """``home-hero`` 不能是 100vh。

    首屏全屏 = 所有内容还是在折线以下，只是把照片换了个内容。

    注释先剥掉再扫：tech.css 里写着「别用 100vh」的那句说明本身含有这个
    词，把它算成一条违规规则，就等于逼着文档不许提这件事。
    """
    assert TECH_CSS.is_file(), "找不到 themes/matery/source/css/tech.css"

    css = re.sub(r"/\*.*?\*/", "", _read(TECH_CSS), flags=re.S)

    hero_blocks = re.findall(r"\.home-hero[^{]*\{[^}]*\}", css)
    assert hero_blocks, "tech.css 里没有 .home-hero 的样式"

    for block in hero_blocks:
        assert "100vh" not in block, (
            ".home-hero 不该是 100vh —— 那样内容还是全在折线以下：{}".format(block)
        )


# --- 4. 首屏带的是站点定位 ---------------------------------------------------


def test_the_hero_carries_the_site_positioning_sentence():
    """首屏的定位句读 ``config.description``。

    ``config.description`` 现在是一句具体的技术描述（「技术学习实践，
    涵盖数据库内核（PostgreSQL/openGauss）、分布式系统、高性能网络
    （DPDK/VPP）等工程实践……」）。硬编码一句口号等于把它复制一份，
    改配置时两处会对不上。
    """
    hero = _read(HOME_HERO)

    assert "config.description" in hero, (
        "home-hero.ejs 应当读 config.description 当定位句"
    )


def test_the_hero_lead_is_a_short_sentence_and_not_the_seo_description():
    """首屏那句大标题是**短句**，不是 SEO 用的那句长描述。

    ``config.description`` 是给搜索引擎看的（九十多个字、顿号串），
    当大标题读着像关键词堆砌，占掉四行。而那行 13px 的小标签
    （「技术·学习·实践·人生·哲学」）列的又是下面 9 个徽章里的同一批东西。

    所以：短句单独放一个配置项 ``home_hero_lead``，长句留给 meta。
    """
    hero = _read(HOME_HERO)
    config = _read(REPO / "_config.yml")

    assert "config.home_hero_lead" in hero, (
        "home-hero.ejs 应当读 config.home_hero_lead 当首屏大标题"
    )
    assert "home_hero_lead:" in config, "_config.yml 里应当有 home_hero_lead 这一句"

    lead = re.search(r"^home_hero_lead:\s*(.+)$", config, re.M)
    assert lead, "_config.yml 里读不出 home_hero_lead 的值"
    value = lead.group(1).strip().strip("'\"")
    assert value, "home_hero_lead 不能是空的"
    assert len(value) <= 24, (
        "首屏大标题要是一句话，不是一段话：{}（{} 个字）".format(value, len(value))
    )


def test_the_hero_lead_falls_back_to_the_description_when_it_is_not_configured():
    """没配 ``home_hero_lead`` 时退回 ``config.description``，那一格不空着。"""
    hero = _read(HOME_HERO)

    assert re.search(r"config\.home_hero_lead\s*\|\|\s*config\.description", hero), (
        "home-hero.ejs 的 h1 应当是 config.home_hero_lead || config.description"
    )


def test_the_hero_does_not_repeat_the_category_list_as_an_eyebrow():
    """首屏不再有一行「技术·学习·实践·人生·哲学」的小标签。

    它列的就是下面那 9 个徽章里的同一批东西，留着是同一句话出现两遍。

    注释里提到 ``config.subtitle`` 不算——那是解释「为什么删了它」，
    所以先剥掉 ``<%# ... %>`` 注释块再查。
    """
    hero = re.sub(r"<%#.*?%>", "", _read(HOME_HERO), flags=re.S)

    assert "config.subtitle" not in hero, "首屏不该再有一行重复分类清单的小标签"


def test_the_built_home_page_shows_the_short_lead():
    """构建产物里，h1 是那句短句——不是 SEO 的长描述。

    对着 ``public/index.html`` 查，不是对着模板查：模板对了、产物没对，
    中间隔着的正是 sync-hexo 和 patch-theme 那两步。
    """
    built = REPO / "public" / "index.html"
    if not built.is_file():
        import pytest

        pytest.skip("还没构建（public/index.html 不存在）")

    html = built.read_text(encoding="utf-8")
    m = re.search(r'<h1 class="home-hero__lead">(.*?)</h1>', html, re.S)
    assert m, "首页的 h1 不见了"
    lead = m.group(1).strip()

    config = _read(REPO / "_config.yml")
    m2 = re.search(r"^home_hero_lead:\s*(.+)$", config, re.M)
    assert m2, "_config.yml 里没有 home_hero_lead"
    expect = m2.group(1).strip().strip("'\"")
    assert lead == expect, "首页 h1 是「{}」，配置里写的是「{}」".format(lead, expect)
    assert len(lead) <= 24, "首页 h1 太长了：{}".format(lead)
    assert "home-hero__eyebrow" not in html, "首页还有那行重复分类清单的小标签"
    assert "技术·学习·实践·人生·哲学" not in html, (
        "首页还在显示那行「技术·学习·实践·人生·哲学」"
    )


# --- 5. 首屏不再摆「三篇代表作」 --------------------------------------------


def test_the_hero_has_no_curated_post_cards():
    """首屏不再有三篇代表作。

    2026-11-18：那三张卡上的分类全是「源码主线」——等于在首屏摆三个
    「读源码」的广告位。首屏该回答的是「这个站是什么、从哪儿开始」，
    那两件事已经由定位句 + 分类徽章 + 「从这里开始」回答了。
    """
    hero = _read(HOME_HERO)

    assert "home-hero__featured" not in hero, "首屏的三篇代表作还在"
    assert "home-hero__card" not in hero, "首屏的代表作卡片还在"


def test_the_hero_does_not_read_the_curated_list():
    """首屏不再读 ``site.data.featured``。"""
    hero = _read(HOME_HERO)

    assert "site.data.featured" not in hero, (
        "home-hero.ejs 不该再读 site.data.featured —— 策展清单已经退休"
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
    """``patch-theme.py`` 不再往 ``home-hero.ejs`` 注入分类徽章 + 打字机。

    2026-11-19：首屏只剩一句定位，徽章和打字机都退休了。
    """
    patcher = _read(PATCH_THEME)

    assert "HERO-BADGES" not in patcher, (
        "patch-theme.py 还在往首页注入分类徽章 —— 只删模板不删注入，"
        "CI 构建一次它就又长回来"
    )
    assert "heroBadges" not in patcher, (
        "patch-theme.py 里还留着分类徽章的清单 —— 那一块已经退休"
    )


def test_the_patcher_strips_the_hero_badges_it_used_to_inject():
    """已经注入过的（老仓库 / 别人改回来）要能剥掉。

    跟「最新一期」那块一个道理：停止注入只管得住以后，**已经注进去的
    那份**得有人负责拆。
    """
    patcher = _read(PATCH_THEME)

    assert "Stripped hero badges" in patcher or "home-hero__badges" in patcher, (
        "patch-theme.py 没有剥掉已注入的徽章块 —— 老仓库构建一次它就回来了"
    )


# --- 7. 首屏的搜索框与分类徽章退休了 ---------------------------------------


def test_the_hero_has_no_search_box():
    """首屏不再有那个只搜标题的搜索框。

    顶部导航里本来就有全文搜索（``_partial/search.ejs``）。首屏再来一个
    只搜标题的框，是同一个去处的第二个入口 —— 而且它自己还写着
    「按标题搜索 · 全文搜索用顶部导航」，等于在首屏提醒读者「真正的
    搜索在别处」。
    """
    hero = re.sub(r"<%#.*?%>", "", _read(HOME_HERO), flags=re.S)

    assert "homeSearch" not in hero, "首屏的搜索框还在"
    assert "home-hero__search" not in hero, "首屏的搜索框还在"
    assert "search-lite.json" not in hero, "首屏不该再抓精简索引"


def test_the_hero_has_no_category_badges():
    """首屏不再有那一排分类徽章。

    导航栏里已经有「分类」入口，徽章是同一份清单的第二份。而且它们把
    首屏从 50px 撑到 220px —— 八张赛道卡只好挤在剩下的空间里。
    """
    hero = re.sub(r"<%#.*?%>", "", _read(HOME_HERO), flags=re.S)

    assert "hero-tech" not in hero, "首屏的分类徽章还在"
    assert "hero-badge" not in hero, "首屏的分类徽章还在"
    assert "hero-typing" not in hero, "首屏的打字机还在"
    assert "home-hero__badges" not in hero, "首屏的徽章容器还在"


def test_the_dead_hero_styles_are_gone():
    """徽章 / 打字机 / 搜索框的样式都退休了。

    死规则留着，下一个人会以为首页还有那么一块 —— 或者更糟：改首屏
    样式时去改一段没人用的规则，改了半天看不出效果。
    """
    css = re.sub(r"/\*.*?\*/", "", _read(TECH_CSS), flags=re.S)
    my_css = re.sub(r"/\*.*?\*/", "", _read(MY_CSS), flags=re.S)

    for dead in ("home-hero__search", "hero-tech", "hero-badge", "hero-typing"):
        assert dead not in css, "tech.css 里还留着 {} 的样式".format(dead)
        assert dead not in my_css, "my.css 里还留着 {} 的样式".format(dead)


def test_the_hero_stylesheet_is_linked_from_the_layout():
    """``tech.css`` 要在页面里被引进来。

    主题的 CSS 链接集中在 ``_partial/main-style.ejs``（``layout.ejs`` 只
    include 它），所以断言落在那个文件上。

    新建了 CSS 文件但没 link，页面会安静地没有样式——不报错，只是不好看。
    """
    main_style = _read(MAIN_STYLE)

    assert "tech.css" in main_style, "main-style.ejs 没有引用 tech.css"
