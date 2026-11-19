"""分类/标签这套页面退休的守卫（2026-11-19）。

**为什么删**：站点在做减法，而分类页、标签页本来就是**坏的**——
``/categories/`` 与 ``/tags/`` 的总览页要靠 ``tools/sync-hexo.py`` 自己
写一份 ``source/<slug>/index.md`` 才存在（``hexo-generator-category`` 只管
底下的子页面）。那份文件有一阵子没写成 → 目录在、``index.html`` 不在 →
nginx 不开 autoindex → 访客看到的是 **403**。菜单里的「分类」「标签」两项、
首页统计条里的「个分类」那块、文章页顶部的分类名与标签 chip，指向的都是
这套东西。

**为什么整套删**（而不是只把 403 修好）：分类和标签是 Hexo 的两个**检索
维度**，跟站点的「学习路径」那套**导航维度**是同一件事的两个入口。文章
front matter 里的 ``categories`` / ``tags`` 字段留着 —— 学习路径的归类
规则、搜索索引的字段都在用它们 —— 只是不再往访客面前摆，也不再有页面。

**旧 URL 为什么不是 404**：这些地址发布出去很久了，书签、搜索引擎的索引、
别人的博客都还链着（重构方案 §7.4 把 URL 稳定性列成硬约束）。所以旧地址
原地留一个重定向页，跳到「全部文章」（``/all/``）。

这一份守的是「别让它复活」：模板、工具、生成器、菜单、样式，五处都得干净。
只删一处的话，CI 构建一次就把页面带回来了 —— 本地看着删干净了，线上又
长出来。
"""

from __future__ import annotations

import ast
import json
import re
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
THEME = REPO_ROOT / "themes" / "matery"
LAYOUT = THEME / "layout"
TOOLS = REPO_ROOT / "tools"
PUBLIC = REPO_ROOT / "public"
CONFIG = REPO_ROOT / "_config.matery.yml"
SITE_CONFIG = REPO_ROOT / "_config.yml"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_ejs_comments(text: str) -> str:
    """把 EJS 注释去掉（``<%# ... %>`` 单行、``<%/* ... */%>`` 块）。

    模板的注释里会提到「那套页面已经删了」—— 提到路径是说明，不是链接。
    """
    text = re.sub(r"<%#.*?%>", "", text, flags=re.S)
    return re.sub(r"<%/\*.*?\*/%>", "", text, flags=re.S)


def _py_strings(path: Path) -> list:
    """取一个 Python 文件里**不是文档字符串**的字符串常量。

    文档字符串说的是「这个文件不由本脚本写」—— 那是说明，不是写入。
    """
    with warnings.catch_warnings():
        # 别的工具文件里有历史遗留的无效转义序列 —— 解析它不是本测试的事。
        warnings.simplefilter("ignore")
        tree = ast.parse(_read(path))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docstrings.add(doc)
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value not in docstrings
    ]


def _menu_block(config: str) -> str:
    """抠出 ``menu:`` 下面那一段（到下一个顶层键为止）。"""
    body = config.split("menu:", 1)[1]
    lines = []
    for line in body.splitlines():
        if line and not line[0].isspace():
            break
        # 注释行不算菜单项 —— 注释里提到「那个页面删了」是说明。
        if line.strip().startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


# --- 1. 入口：菜单里那两项 ------------------------------------------------


def test_the_menu_no_longer_has_category_or_tag_entries():
    """菜单里指向那两个 403 页面的项得撤掉。"""
    menu = _menu_block(_read(CONFIG))

    assert "分类:" not in menu, "菜单里还有「分类」这一项 —— 它指向的页面没了"
    assert "标签:" not in menu, "菜单里还有「标签」这一项 —— 它指向的页面没了"
    assert "/categories/" not in menu
    assert "/tags/" not in menu


def test_the_homepage_stats_banner_lost_its_category_card():
    """首页统计条里「个分类」那块链的就是 /categories/。"""
    home = _strip_ejs_comments(_read(LAYOUT / "_partial" / "home-content.ejs"))

    assert "个分类" not in home, "首页统计条里还有「个分类」那块"
    assert "/categories/" not in home


# --- 2. 模板：那些页面本身 ------------------------------------------------


def test_the_taxonomy_layouts_are_gone():
    """四个页面模板不许还在 —— 留着就有人能渲染出那套页面。"""
    for name in ("tags.ejs", "categories.ejs", "tag.ejs", "category.ejs"):
        assert not (LAYOUT / name).exists(), "themes/matery/layout/{} 还在".format(name)


def test_the_taxonomy_widgets_are_gone():
    """标签云、分类云、词云、雷达图、分类图表 —— 都没人渲染了。"""
    for name in (
        "tag-cloud.ejs",
        "tag-wordcloud.ejs",
        "category-cloud.ejs",
        "category-radar.ejs",
        "post-charts.ejs",
    ):
        assert not (LAYOUT / "_widget" / name).exists(), (
            "themes/matery/layout/_widget/{} 还在".format(name)
        )


def test_no_template_links_to_a_category_or_tag_page():
    """全主题扫一遍：没有 ``url_for(category.path)`` / ``url_for(tag.path)``。

    这两处是「分类名」「标签 chip」链接的来源 —— 页面没了，链接就是死链。
    """
    offenders = []
    for path in sorted(LAYOUT.rglob("*.ejs")):
        text = _strip_ejs_comments(_read(path))
        for needle in ("url_for(category.path)", "url_for(tag.path)", "url_for(cat.path)"):
            if needle in text:
                offenders.append("{}: {}".format(path.relative_to(REPO_ROOT), needle))

    assert offenders == [], "还有模板链着分类/标签页：{}".format(offenders)


def test_the_article_page_shows_no_category_or_tag_chip():
    """文章页顶部那两块（分类名 + 标签 chip）撤了。"""
    detail = _strip_ejs_comments(_read(LAYOUT / "_partial" / "post-detail.ejs"))

    assert "article-tag" not in detail, "文章页还有标签 chip"
    assert "post-cate" not in detail, "文章页还有分类名"
    assert "post-category" not in detail


# --- 3. 生成器：让页面回来的那一条路 --------------------------------------


def test_the_hexo_category_and_tag_generators_are_uninstalled():
    """两个生成器不在依赖里了 —— 否则每个分类/标签的子页面都会重新长出来。"""
    package = json.loads(_read(REPO_ROOT / "package.json"))

    assert "hexo-generator-category" not in package["dependencies"], (
        "hexo-generator-category 还在 —— 分类子页面会被重新生成"
    )
    assert "hexo-generator-tag" not in package["dependencies"], (
        "hexo-generator-tag 还在 —— 标签子页面会被重新生成"
    )


def test_no_tool_writes_a_taxonomy_page_any_more():
    """一个文件一个写入者 —— 现在是**零个**写入者。

    判据是「写一份**列表页**」：source/categories/、source/tags/ 下的
    index.md，或者 front matter 里带 ``type: category`` / ``type: tag``
    （Hexo 靠这两个字段认出列表页）。重定向页写的是 ``layout: false``，
    不算 —— 那是我们要留的东西。
    """
    offenders = []
    for path in sorted(TOOLS.glob("*.py")):
        values = _py_strings(path)
        for value in values:
            if any(
                needle in value
                for needle in (
                    "categories/index.md",
                    "tags/index.md",
                    "source/categories",
                    "source/tags",
                )
            ):
                offenders.append("{}: {}".format(path.name, value))
            if re.search(r"type:\s*(category|tag)\b", value):
                offenders.append("{}: {}".format(path.name, value))

    assert offenders == [], "还有工具在写分类/标签列表页：{}".format(offenders)


def test_the_sync_tool_no_longer_creates_the_overview_pages():
    """总览页原来靠 sync-hexo 自己写 —— 那一段要退休。"""
    values = _py_strings(TOOLS / "sync-hexo.py")

    assert not any("categories/index.md" in v for v in values), (
        "sync-hexo.py 还在写 source/categories/index.md —— 总览页会回来"
    )
    assert not any("tags/index.md" in v for v in values), (
        "sync-hexo.py 还在写 source/tags/index.md —— 总览页会回来"
    )


# --- 4. 旧地址的去处 ------------------------------------------------------


def test_the_sync_tool_writes_redirect_pages_for_the_old_urls():
    """旧地址得有去处：/categories/、/tags/、以及每个分类/标签子页。"""
    sync = _read(TOOLS / "sync-hexo.py")

    assert "def write_taxonomy_redirects(" in sync, (
        "sync-hexo.py 里没有写重定向页的函数 —— 旧地址会变成 404"
    )
    assert "TAXONOMY_REDIRECT_PAGE" in sync, "重定向页的模板没了"


def test_the_retired_paths_table_exists():
    """历史上用过、现在没有文章归进去的分类名，记在这张表里。"""
    table = REPO_ROOT / "data" / "retired-taxonomy-paths.json"

    assert table.is_file(), "data/retired-taxonomy-paths.json 不在了"
    paths = json.loads(_read(table))
    assert isinstance(paths, list) and paths, "那张表得是一份路径清单"
    assert all(p.startswith(("categories/", "tags/")) for p in paths), (
        "表里的路径得是分类/标签地址"
    )


def test_the_old_category_redirect_table_is_gone():
    """旧分类名 → 新分类名那张映射表退休了（旧地址统一跳「全部文章」）。"""
    assert not (REPO_ROOT / "data" / "category-redirects.json").exists(), (
        "data/category-redirects.json 还在 —— 那张表已经不读了"
    )


def test_the_removed_database_page_points_at_a_page_that_still_exists():
    """``/database/`` 的正身从 /categories/ 换成了 /all/（分类页退休了）。"""
    sync = _read(TOOLS / "sync-hexo.py")

    assert '("database", "数据库专题", "/all/")' in sync, (
        "/database/ 的重定向目标还是 /categories/ —— 那个页面已经没了"
    )


# --- 5. 站点配置 ----------------------------------------------------------


def test_the_site_config_no_longer_generates_taxonomy_pages():
    """配置里那两个生成器开关该撤了（生成器本身已经卸掉）。"""
    config = _read(SITE_CONFIG)

    assert "category_generator:" not in config
    assert "tag_generator:" not in config


def test_the_sitemap_no_longer_lists_the_taxonomy_urls():
    """sitemap 里别再列那些地址 —— 它们现在是 noindex 的跳转页。"""
    config = _read(SITE_CONFIG)

    assert re.search(r"^sitemap:\s*$", config, re.M), "配置里没有 sitemap 段"
    assert "tags: false" in config, "sitemap 里还在列标签地址"
    assert "categories: false" in config, "sitemap 里还在列分类地址"


# --- 6. 渲染产物 ----------------------------------------------------------


def test_the_built_site_has_no_taxonomy_overview_pages():
    """产物里那两个地址是**重定向页**，不再是分类/标签总览。"""
    if not PUBLIC.is_dir():
        return

    for slug in ("categories", "tags"):
        page = PUBLIC / slug / "index.html"
        assert page.is_file(), "/{}/ 在产物里不存在了（该留一个重定向页）".format(slug)
        content = page.read_text(encoding="utf-8")
        assert 'http-equiv="refresh"' in content, (
            "/{}/ 不是重定向页 —— 那套页面没删干净".format(slug)
        )
        assert "/all/" in content, "/{}/ 的重定向目标不对".format(slug)


def test_the_built_site_has_no_taxonomy_links():
    """产物里没有指向分类/标签页的链接了。"""
    if not PUBLIC.is_dir():
        return

    offenders = []
    for path in PUBLIC.rglob("*.html"):
        text = _read(path)
        for needle in ('href="/categories/', 'href="/tags/'):
            if needle in text:
                offenders.append("{}: {}".format(path.relative_to(PUBLIC), needle))

    assert offenders == [], "产物里还有链着分类/标签页的链接：{}".format(
        offenders[:10]
    )
