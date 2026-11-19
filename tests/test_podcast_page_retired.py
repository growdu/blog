"""播客系列页（``/videos/``）退休的守卫。

2026-11-19：那个页面整个删掉了 —— 菜单里的「播客」项、生成它的工具、
文章页里指向它的「全部期号」链接，还有它自己的样式。

**为什么删**：站点在做减法，导航栏里的每一项都得是「读者真的会去」的
地方。系列页只是把六期视频列成一张表，而那六期在文章页顶部就能翻到
（上一期 / 下一期）。订阅入口（RSS，/feed.xml）跟着搬进了文章页顶部的
期号区块 —— feed 本身一个字都没改。

**这一份守的是「别让它复活」**：模板、工具、流水线、样式，四处都得
干净。只删一处的话，CI 构建一次就把页面带回来了 —— 本地看着删干净了，
线上又长出来。
"""

from __future__ import annotations

import ast
import re
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"
THEME_PARTIALS = REPO_ROOT / "themes" / "matery" / "layout" / "_partial"
PUBLIC = REPO_ROOT / "public"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_ejs_comments(text: str) -> str:
    """把 EJS 注释（``<%# ... %>``）去掉。

    模板的注释里会提到「那个页面已经删了」—— 提到路径是说明，不是链接。
    """
    return re.sub(r"<%#.*?%>", "", text, flags=re.S)


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


# --- 1. 入口 ---------------------------------------------------------------


def test_the_menu_no_longer_has_a_podcast_entry():
    """菜单里那一项指向的页面没了，留着就是死链。"""
    config = _read(REPO_ROOT / "_config.matery.yml")
    menu = _menu_block(config)

    assert "播客:" not in menu, "菜单里还有「播客」这一项 —— 它指向的页面没了"
    assert "/videos/" not in menu, "菜单里还有指向 /videos/ 的链接"


# --- 2. 生成它的工具 -------------------------------------------------------


def test_the_series_page_builder_is_gone():
    """partial 退休了 —— 没人渲染它，就不该留在仓库里。"""
    assert not (TOOLS / "build-series-page.py").exists(), (
        "build-series-page.py 还在 —— 流水线一跑就把系列页又生成了"
    )


def test_no_tool_writes_the_series_page_any_more():
    """一个文件一个写入者 —— 现在是**零个**写入者。

    只看代码里的字符串常量（文档字符串不算）：文档里提到
    「这个文件不由本脚本写」是说明，不是写入。
    """
    writers = []
    for path in sorted(TOOLS.glob("*.py")):
        with warnings.catch_warnings():
            # 别的工具文件里有历史遗留的无效转义序列——解析它不是本测试的事，
            # 别把人家的警告带进测试输出里。
            warnings.simplefilter("ignore")
            tree = ast.parse(_read(path))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(
                node,
                (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                doc = ast.get_docstring(node, clean=False)
                if doc is not None:
                    docstrings.add(doc)
        values = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value not in docstrings
        ]
        has_dir = any(
            value == "videos" or value.endswith("/videos") for value in values
        )
        has_file = any(value == "index.md" for value in values)
        if has_dir and has_file:
            writers.append(path.name)

    assert writers == [], "还有工具在写系列页：{}".format(writers)


# --- 3. 流水线 -------------------------------------------------------------


def test_the_ci_no_longer_builds_the_series_page():
    """流水线里那一步删了 —— 留着就等于没删。"""
    workflow = _read(REPO_ROOT / ".github" / "workflows" / "hexo.yml")

    assert "build-series-page.py" not in workflow, (
        "CI 还在跑 build-series-page.py —— 系列页会被重新生成"
    )


# --- 4. 文章页里那条链接 ---------------------------------------------------


def test_the_episode_block_no_longer_links_the_retired_page():
    """「全部期号」那条链接指向的页面没了。

    订阅入口还在 —— 它搬进了文章页顶部的期号区块（``episode-subscribe``）。
    """
    partial = _strip_ejs_comments(_read(THEME_PARTIALS / "episode-block.ejs"))

    assert "/videos/" not in partial, "期号区块里还有指向 /videos/ 的链接"
    assert "全部期号" not in partial, "「全部期号」那条链接还在"
    assert "episode-subscribe" in partial, (
        "订阅入口没搬进期号区块 —— 删掉系列页之后 feed 就没人链了"
    )
    assert "/feed.xml" in partial, "订阅入口没有指向 feed"


def test_the_dead_style_of_that_link_is_gone():
    """那条链接的样式也没用了 —— 仓库里和注入的那份都要清掉。

    ``my.css`` 是注入的产物（patch-theme.py 每次构建都会追加一段），
    只改注入的那份不改仓库里的，两边就不一样了。
    """
    css = _read(REPO_ROOT / "themes" / "matery" / "source" / "css" / "my.css")
    patcher = _read(TOOLS / "patch-theme.py")

    assert ".episode-nav-all" not in css, "my.css 里还留着 .episode-nav-all 的样式"
    # patcher 里可以**提到**这条规则（下面那段剥旧样式的代码就得按名字找它），
    # 但不能**注入**它 —— 找的是「注入的那段 CSS 里还有没有这条规则」。
    injected = patcher.split("ep_css = ", 1)[1].split('"""', 2)[1]
    assert ".episode-nav-all" not in injected, (
        "patcher 注入的那段 CSS 里还有 .episode-nav-all 的样式"
    )


def test_the_patcher_strips_the_leftover_style():
    """本地仓库里的 my.css 可能还是旧的 —— patcher 得主动把它剥掉。"""
    patcher = _read(TOOLS / "patch-theme.py")

    assert re.search(r"episode_nav_all_rule", patcher), (
        "patcher 没有剥掉旧 my.css 里那条 .episode-nav-all 的规则"
    )


# --- 5. 期号区块的守卫 -----------------------------------------------------


def test_the_episode_checker_no_longer_checks_the_series_page():
    """检查器里那条「系列页必须列出每一期」的检查跟着删了。"""
    checker = _read(TOOLS / "check-episode-block.py")

    assert "check_series_page" not in checker, (
        "check-episode-block.py 还在检查系列页 —— 页面没了，检查永远失败"
    )


def test_the_episode_checker_still_checks_the_episodes():
    """删的是系列页那一条，逐期检查必须还在。"""
    checker = _read(TOOLS / "check-episode-block.py")

    assert "def check_episode(" in checker
    assert "期号区块检查" in checker


# --- 6. 渲染产物 -----------------------------------------------------------


def test_the_built_site_has_no_series_page():
    """产物里不该再有那个页面（有产物才查 —— CI 里一定有）。"""
    if not PUBLIC.is_dir():
        return

    assert not (PUBLIC / "videos" / "index.html").exists(), (
        "渲染产物里还有 /videos/index.html —— 页面没删干净"
    )
