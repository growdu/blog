"""``/database/`` 与 ``/projects/`` 两个落地页删掉了，旧 URL 变成重定向。

**为什么删**：站点要做减法。这两块都是**重复入口**——
数据库的文章在「分类」页里按分类找得到，开源项目在「关于我」页里有卡片，
两页各自维护一份清单，跟真正的内容目录各走各的，改一处就漏一处。

**为什么不能直接 404**：这两个地址已经发布出去很久了。书签、搜索引擎的
索引、别人的博客都还链着。URL 稳定性是硬约束（spec §7.4），所以原地留
一个重定向页，各自带 ``meta refresh`` + ``canonical`` + 一个真链接
（meta refresh 被浏览器设置或公司代理禁掉时，人还能走）。

这里守的是三件事：

1. 菜单里不再有「项目」「数据库」两项；
2. ``sync-hexo.py`` 会生成这两个重定向页，且**指向的正身还在**；
3. 重定向页带着 ``meta refresh`` 与 ``canonical``——少了哪个，
   老链接要么不跳，要么还会被搜索引擎当成正身继续收录。
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG = REPO_ROOT / "_config.matery.yml"
SYNC = REPO_ROOT / "tools" / "sync-hexo.py"


def _load_sync():
    spec = importlib.util.spec_from_file_location("sync_hexo_landing", SYNC)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_menu_has_no_entry_for_the_removed_pages():
    """菜单里不许再有「项目」「数据库」。"""
    config = CONFIG.read_text(encoding="utf-8")

    assert not re.search(r"^  项目:\n", config, re.M), "菜单里还有「项目」"
    assert not re.search(r"^  数据库:\n", config, re.M), "菜单里还有「数据库」"
    assert "/projects/" not in config, "配置里还链着 /projects/"
    assert "/database/" not in config, "配置里还链着 /database/"


def test_the_sync_writes_a_redirect_stub_for_both_pages(tmp_path):
    """两个重定向页都要写出来，且内容对。"""
    sync = _load_sync()

    sync.SRC = str(tmp_path)
    sync.create_removed_landing_redirects()

    for slug, target in (("database", "/categories/"), ("projects", "/about/")):
        page = tmp_path / slug / "index.md"
        assert page.is_file(), "/{}/ 的重定向页没生成".format(slug)
        content = page.read_text(encoding="utf-8")
        assert 'content="0; url={}"'.format(target) in content, (
            "/{}/ 的重定向页没有跳到 {}".format(slug, target)
        )
        assert '<link rel="canonical" href="{}">'.format(target) in content, (
            "/{}/ 的重定向页没有 canonical".format(slug)
        )
        # 跳不过去的时候（meta refresh 被禁），人还能点过去。
        assert '<a href="{}">'.format(target) in content, (
            "/{}/ 的重定向页没有兜底链接".format(slug)
        )


def test_the_redirect_targets_still_exist(tmp_path):
    """重定向指向的正身必须还在——指到一个空页面等于把 404 换了个地方。"""
    sync = _load_sync()

    sync.SRC = str(tmp_path)
    sync.create_theme_pages()

    for target in ("categories", "about"):
        page = tmp_path / target / "index.md"
        assert page.is_file(), "/{}/ 这个正身页没有生成".format(target)


def test_the_old_landing_page_generator_is_gone():
    """老的落地页生成器不许还在——它会把那两个页面重新写回来。"""
    text = SYNC.read_text(encoding="utf-8")

    assert "def create_database_landing_page" not in text, (
        "create_database_landing_page 还在：跑一次 sync 就把 /database/ 写回来了"
    )
    assert "def create_projects_page" not in text, (
        "create_projects_page 还在：跑一次 sync 就把 /projects/ 写回来了"
    )
