"""内容里的 ``<nav>`` 不能是 Materialize 的导航条。

**背景**：Materialize 的 ``nav`` 是**按元素名**选的，不是按类选的：

```css
nav{color:#fff;background-color:#ee6e73;width:100%;height:56px;line-height:56px}
@media (min-width:601px){nav{height:64px;line-height:64px}}
```

也就是说，**页面上任何一个 ``<nav>`` 都会被当成顶部那条 64px 的红导航条**：
固定高度、64px 行高、红底白字。主题自己的头部导航（``#headNav``）就该是这个
样子，但内容里的 ``<nav>`` 不该。

**后果（2026-11-16 实测）**：

1. 首页 ``_partial/home-hero.ejs`` 的「三篇代表作」用的是 ``<nav>``：
   ``height:64px`` 把那个三列网格硬压成 64px 高，卡片自己溢出；
   ``line-height:64px`` 让每行文字高 64px，卡片涨到 261px 高。
   首屏的盒子因此比内容矮 84px，**统计条（文章数 / 总字数 / 天数 / 分类数）
   直接盖在代表作卡片上**——分类是「数据库深入 / 数据库」的那几张被拦腰截断。
2. 文章页 ``_partial/episode-block.ejs`` 的「上一期 / 下一期 / 全部期号」
   用的也是 ``<nav>``：它渲染成一条**红色横条**，白字，在文章中间非常突兀。

**契约**：内容模板里不许出现 ``<nav>``；唯一允许的是头部那条
（``header.ejs`` 里的 ``<nav id="headNav">``）。以后谁想加导航条，
用 ``<div>`` / ``<section>`` 加自己的类，不要用 ``<nav>``——
Materialize 会抢走它的样式。

放在根级 ``tests/``，随 ``site-guard.yml`` 进 CI（不构建产物，只读模板）。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
THEME = REPO / "themes" / "matery"
LAYOUT = THEME / "layout"
PARTIAL = LAYOUT / "_partial"

HOME_HERO = PARTIAL / "home-hero.ejs"
EPISODE_BLOCK = PARTIAL / "episode-block.ejs"
HEADER = PARTIAL / "header.ejs"
MATERIALIZE_CSS = THEME / "source" / "libs" / "materialize" / "materialize.min.css"

PUBLIC = REPO / "public"

# 头部那条导航条：Materialize 的样式就是给它写的，唯一允许的 ``<nav>``。
HEADER_NAV = '<nav id="headNav"'


def _read(path: Path) -> str:
    assert path.is_file(), "找不到 {}".format(path)
    return path.read_text(encoding="utf-8")


def _strip_ejs_comments(text: str) -> str:
    """去掉 ``<%# ... %>`` 注释——注释里的示例代码不算真的用了 ``<nav>``。"""
    return re.sub(r"<%#.*?%>", "", text, flags=re.S)


def _nav_tags(text: str) -> list[str]:
    """返回 HTML 里所有 ``<nav ...>`` 开始标签的原文。"""
    return re.findall(r"<nav\b[^>]*>", text)


# --- 1. Materialize 确实按元素名抢 nav 的样式 --------------------------------


def test_materialize_styles_every_nav_as_a_fixed_height_bar():
    """前提：Materialize 按**元素名**给 ``nav`` 上样式。

    这条测试不是断言「我们的页面没问题」，而是断言「这个坑还在」——
    哪天 Materialize 改了这条规则（或者我们换掉这个框架），
    这条会先红，提示下面几条的必要性也要重新评估。
    """
    css = _read(MATERIALIZE_CSS)
    assert "nav{color:#fff;background-color:#ee6e73" in css, (
        "Materialize 不再按元素名给 nav 上导航条样式了——"
        "下面关于 <nav> 的几条契约可以放宽，但请先看一眼实际效果"
    )
    assert "nav,nav .nav-wrapper i,nav a.sidenav-trigger" in css and "line-height:64px" in css, (
        "Materialize 的 nav 固定高度/行高的规则变了，"
        "首页代表作与统计条重叠那件事的成因可能已经不同"
    )


# --- 2. 内容模板里不许有 <nav> ---------------------------------------------


def test_no_content_template_uses_a_nav_element():
    """除头部那条，内容模板里不许出现 ``<nav>``。

    一次把所有模板扫一遍，这样以后新增模板忘了这条也会被抓住，
    而不是等下一个 <nav> 又被 Materialize 抢了样式才发现。
    """
    offenders = []
    for ejs in sorted(LAYOUT.rglob("*.ejs")):
        for tag in _nav_tags(_strip_ejs_comments(_read(ejs))):
            if tag.startswith(HEADER_NAV):
                continue
            offenders.append("{}: {}".format(ejs.relative_to(REPO), tag))
    assert not offenders, (
        "内容模板里出现了 <nav>，Materialize 会把它渲染成 64px 的红导航条：\n"
        + "\n".join(offenders)
        + "\n改用 <div> / <section> 加自己的类。"
    )


def test_the_home_hero_has_no_navigable_landing_blocks():
    """首屏里不许再出现「代表作」那一块。

    2026-11-18：三篇代表作整块删掉了（首屏要回答的是「这个站是什么」，
    不是「作者推荐什么」）。这一条留着是为了防它改回来——它当初是
    ``<nav>``，被 Materialize 压成 64px 的红条，把底下的统计条盖住了；
    改回 ``<section>`` 治的是症状，删掉整块才是根治。
    """
    html = _read(HOME_HERO)
    assert "home-hero__featured" not in html, (
        "首屏的三篇代表作又回来了 —— 那三张卡上的分类全是「源码主线」"
    )


def test_the_episode_nav_is_a_div_not_a_nav():
    """文章页的「上一期 / 下一期 / 全部期号」不该是 ``<nav>``。

    它现在渲染成一条红色横条（Materialize 的导航条颜色），
    白字，在文章正中间非常突兀。
    """
    html = _read(EPISODE_BLOCK)
    assert '<nav class="episode-nav"' not in html, (
        "期号导航还是 <nav>：它会被 Materialize 渲染成一条红色导航条"
    )
    assert '<div class="episode-nav"' in html, (
        "期号导航应该改成 <div class=\"episode-nav\">"
    )


def test_the_header_nav_is_still_the_only_nav():
    """头部那条仍然是 ``<nav id="headNav">``——它是 Materialize 样式的目标。"""
    assert HEADER_NAV in _read(HEADER)


# --- 3. 产物上的复核（构建过才跑） -------------------------------------------


def test_the_built_home_page_has_no_content_nav():
    """构建产物里，首页除了头部那条不许再有 ``<nav>``。"""
    index = PUBLIC / "index.html"
    if not index.is_file():
        import pytest

        pytest.skip("没有 public/index.html（本地没构建，跳过产物复核）")
    html = _read(index)
    bad = [t for t in _nav_tags(html) if not t.startswith(HEADER_NAV)]
    assert not bad, "构建出来的首页里有内容用的 <nav>：{}".format(bad)
