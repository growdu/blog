"""系列页与站点入口的契约测试（契约七 §7.1 / §7.2）。

三块：

1. **系列页**（``/videos/``）——一行一期：期号、标题、钩子、时长、
   完整版（母稿页）、口播稿与字幕、发到了哪些平台。
   地址是**派生**的（日期 + content_id，带挂载点前缀）。
2. **站点入口**——菜单里有一项指向系列页；首页上有一块「最新一期」。
3. **装配**——partial 在库里、渲染位在正确的位置、样式在 my.css 里、
   CI 跑得着那一步。

**一个文件一个写入者**：合集页（系列页）由 ``build-series-page.py`` 写，
``build-video-pages.py`` 不碰它——两个工具写同一个文件，谁赢要看流水线
顺序，改了一处却没生效是最难查的那种问题。
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"
THEME_PARTIALS = REPO_ROOT / "themes" / "matery" / "layout" / "_partial"


def load_tool(name):
    """Import one of the build tools as a module."""
    spec = importlib.util.spec_from_file_location(
        "tool_under_test_{}".format(name.replace("-", "_")), TOOLS / (name + ".py")
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


series_page = load_tool("build-series-page")


def _index(rows=None):
    if rows is None:
        rows = [
            {
                "episode": "row-lock",
                "episode_no": 6,
                "episode_label": "EP06",
                "title": "两个事务改同一行，谁先谁后",
                "draft_title": "PostgreSQL 行锁机制源码级深度拆解",
                "hook": "MVCC 让读不挡写，但两个写会互相覆盖",
                "duration_s": 35.172,
                "date": "2026-03-08",
                "content_id": "source-tracks/postgresql/transaction-mvcc/postgresql-row-lock-deep-dive",
                "video_date": "2026-05-19",
                "video_content_id": "video/row-lock",
                "platforms": [
                    {
                        "platform": "bilibili",
                        "label": "B站",
                        "published_url": "https://www.bilibili.com/video/BV1NBWv6qECn",
                    },
                    {
                        "platform": "douyin",
                        "label": "抖音",
                        "published_url": None,
                    },
                ],
            }
        ]
    return {
        "series": {"name": "数据库内核机制", "tagline": "数据库内核机制，讲到源码那一行"},
        "episodes": rows,
    }


# --- 1. 系列页 -------------------------------------------------------------


def test_the_series_page_lists_every_episode(tmp_path, monkeypatch):
    index_path = tmp_path / "podcast_index.json"
    index_path.write_text(json.dumps(_index(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(series_page, "PODCAST_INDEX", index_path)

    out = tmp_path / "videos" / "index.md"
    assert series_page.main(["--out", str(out)]) == 0

    text = out.read_text(encoding="utf-8")
    assert "# 数据库内核机制" in text
    assert "## EP06 · 两个事务改同一行，谁先谁后" in text
    assert "MVCC 让读不挡写，但两个写会互相覆盖" in text
    assert "时长：35 秒" in text


def test_the_series_page_links_the_full_article_and_the_script(tmp_path, monkeypatch):
    """一期两跳：完整版（母稿页）与口播稿与字幕（视频页）。"""
    index_path = tmp_path / "podcast_index.json"
    index_path.write_text(json.dumps(_index(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(series_page, "PODCAST_INDEX", index_path)

    out = tmp_path / "videos" / "index.md"
    series_page.main(["--out", str(out)])
    text = out.read_text(encoding="utf-8")

    assert "/2026/03/08/source-tracks/postgresql/transaction-mvcc/postgresql-row-lock-deep-dive/" in text
    assert "/2026/05/19/video/row-lock/" in text


def test_the_series_page_does_not_pretend_an_unpublished_episode_is_out(tmp_path, monkeypatch):
    """没发出去的平台写成「（未发布）」，不给链接。"""
    index_path = tmp_path / "podcast_index.json"
    index_path.write_text(json.dumps(_index(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(series_page, "PODCAST_INDEX", index_path)

    out = tmp_path / "videos" / "index.md"
    series_page.main(["--out", str(out)])
    text = out.read_text(encoding="utf-8")

    assert "[B站](https://www.bilibili.com/video/BV1NBWv6qECn)" in text
    assert "抖音（未发布）" in text
    assert "](https://www.douyin.com" not in text


def test_an_empty_index_does_not_wipe_the_page(tmp_path, monkeypatch):
    """一期都没有就别覆盖——空页面比旧页面更糟。"""
    index_path = tmp_path / "podcast_index.json"
    index_path.write_text(
        json.dumps(_index(rows=[]), ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(series_page, "PODCAST_INDEX", index_path)

    out = tmp_path / "videos" / "index.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("---\ntitle: \"旧页面\"\n---\n", encoding="utf-8")

    assert series_page.main(["--out", str(out)]) == 0
    assert "旧页面" in out.read_text(encoding="utf-8")


def test_the_series_page_says_how_often_it_updates(tmp_path, monkeypatch):
    """承诺了就要兑现——更新节奏写在页面上。"""
    index_path = tmp_path / "podcast_index.json"
    index_path.write_text(json.dumps(_index(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(series_page, "PODCAST_INDEX", index_path)

    out = tmp_path / "videos" / "index.md"
    series_page.main(["--out", str(out)])

    assert "每周一期" in out.read_text(encoding="utf-8")


# --- 2. 站点入口 -----------------------------------------------------------


def test_the_menu_has_an_entry_for_the_series():
    """菜单里要有一项指向系列页。"""
    config = (REPO_ROOT / "_config.matery.yml").read_text(encoding="utf-8")

    assert re.search(r"^  播客:\n    url: /videos/$", config, re.M), (
        "菜单里应当有一项「播客」指向 /videos/"
    )


def test_the_homepage_has_the_latest_episode_block():
    """首页上要能一眼看到「最新一期是什么」。"""
    text = (THEME_PARTIALS / "home-content.ejs").read_text(encoding="utf-8")

    assert "partial('_partial/latest-episode')" in text
    # 位置：在学习路径之前——首页最上面就是它。
    # （2026-11-18：首页的文章区那三个 tab 整块删掉了，以前这里比的是
    #  「最新一期」与文章列表的先后；现在文章区没了，锚点是学习路径。）
    block_at = text.find("partial('_partial/latest-episode')")
    learning_at = text.find("partial('_partial/learning-path')")
    assert block_at != -1 and learning_at != -1
    assert block_at < learning_at


def test_the_latest_episode_block_is_in_the_repo():
    """partial 是**入库**的（不是构建期生成的）。"""
    path = THEME_PARTIALS / "latest-episode.ejs"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "site.data.podcast_index" in text
    assert "latest-episode-link" in text
    # 首页不放播放器：B站播放器要拉 1 MB 左右的 JS，首页是最热的页面。
    assert "player.bilibili.com" not in text


def test_the_patch_theme_injects_the_block_and_the_styles():
    text = (TOOLS / "patch-theme.py").read_text(encoding="utf-8")

    assert "partial('_partial/latest-episode')" in text
    assert "/* LATEST-EPISODE */" in text
    assert "f.write(le_css)" in text
    css = (REPO_ROOT / "themes" / "matery" / "source" / "css" / "my.css").read_text(
        encoding="utf-8"
    )
    assert "/* LATEST-EPISODE */" in css
    assert ".latest-episode-link" in css


# --- 3. 装配与流水线 -------------------------------------------------------


def test_the_ci_builds_the_series_page_after_the_index():
    """系列页读期号索引——顺序错了就生成一个空页面。"""
    workflow = (REPO_ROOT / ".github" / "workflows" / "hexo.yml").read_text(
        encoding="utf-8"
    )

    assert workflow.count("python3 tools/build-series-page.py") == 2
    for build in workflow.split("- name: Build publish index")[1:]:
        segment = build.split("- name: Apply theme patches")[0]
        assert "tools/build-podcast-index.py" in segment
        assert "tools/build-series-page.py" in segment


def test_only_one_tool_writes_the_series_page():
    """一个文件一个写入者。

    两个工具写同一个文件，谁赢要看流水线顺序——改了一处却没生效，
    是最难查的那类问题。

    这里查的是**代码**里的字符串常量（文档字符串不算）：文档里提到
    「这个文件不由本脚本写」是说明，不是写入。
    """
    writers = []
    for path in sorted(TOOLS.glob("*.py")):
        with warnings.catch_warnings():
            # 别的工具文件里有历史遗留的无效转义序列——解析它不是本测试的事，
            # 别把人家的警告带进测试输出里。
            warnings.simplefilter("ignore")
            tree = ast.parse(path.read_text(encoding="utf-8"))
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
        has_dir = any(value == "videos" or value.endswith("/videos") for value in values)
        has_file = any(value == "index.md" for value in values)
        if has_dir and has_file:
            writers.append(path.name)

    assert writers == ["build-series-page.py"], "有多个工具在写系列页：{}".format(writers)
