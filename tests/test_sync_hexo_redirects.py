"""重定向页生成器的三条硬规矩（tools/sync-hexo.py）。

一是**旧 URL 必须还在**：文章换了目录，旧链接要能跳到新地方，
所以生成器在旧路径上放一个 meta refresh 的静态页。

二是**日期段要对得上**：重定向页默认落在新文件的日期段上（文章搬家时
日期不变）；旧 URL 的日期跟新文件对不上时（合并两篇逐字节相同的重复
文章就会碰上），键里可以带一段日期，照它写。

三是**产物必须传得上去**：GitHub 的 upload-artifact / upload-pages-artifact
拒绝含文件名非法字符（``: * ? " < > |``）的路径 —— 一个带冒号的目录就能让
整个部署断在那里。2026-11-17 的 Deploy Hexo 就是这么断的：旧分类
「PostgreSQL 源码修炼之路:内核深度拆解专题」生成出来的目录带了冒号，
连着两个 push 没上成线。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SYNC_TOOL = REPO_ROOT / "tools" / "sync-hexo.py"

#: 文件名里不能有的字符（Windows NTFS 与 GitHub artifact 的共同限制）
INVALID = ':*?"<>|'


@pytest.fixture(scope="module")
def sync():
    """Import ``tools/sync-hexo.py`` as a module.

    Its ``main()`` is guarded by ``if __name__ == '__main__'``, so importing
    it only defines functions -- it does not rewrite ``source/``.
    """
    spec = importlib.util.spec_from_file_location("sync_hexo_under_test", SYNC_TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_hexo_under_test"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def out_dir(sync, tmp_path, monkeypatch):
    """把生成目录指到临时目录，并清空重定向表。"""
    monkeypatch.setattr(sync, "SRC", str(tmp_path))
    monkeypatch.setattr(sync, "REDIRECTS", {})
    monkeypatch.setattr(sync, "POSTS", str(tmp_path / "_posts"))
    monkeypatch.setattr(sync, "RETIRED_TAXONOMY_PATHS", [])
    (tmp_path / "_posts").mkdir()
    return tmp_path


def _write_post(sync, out_dir, name, categories=(), tags=()):
    """造一篇假文章（只要 front matter）。"""
    lines = ["---", "title: 假文章", "date: 2026-01-01 00:00:00"]
    if categories:
        lines.append("categories:")
        lines.extend("  - {}".format(c) for c in categories)
    if tags:
        lines.append("tags:")
        lines.extend("  - {}".format(t) for t in tags)
    lines.append("---")
    lines.append("")
    path = out_dir / "_posts" / (name + ".md")
    path.write_text("\n".join(lines), encoding="utf-8")


def test_taxonomy_overviews_become_redirect_pages(sync, out_dir):
    """/categories/ 与 /tags/ 的总览页退休了 —— 旧地址跳到「全部文章」。"""
    written = sync.write_taxonomy_redirects()
    assert written == 2
    for slug in ("categories", "tags"):
        page = out_dir / slug / "index.md"
        assert page.is_file(), "/{}/ 的重定向页没生成".format(slug)
        content = page.read_text(encoding="utf-8")
        assert 'content="0; url=/all/"' in content
        assert '<link rel="canonical" href="/all/">' in content
        # 跳不过去的时候（meta refresh 被禁），人还能点过去。
        assert '<a href="/all/">' in content


def test_a_category_url_becomes_a_redirect_page(sync, out_dir):
    """每篇用过的分类也要有去处 —— 那是发布出去过的地址。"""
    _write_post(sync, out_dir, "post-1", categories=["数据库"])
    written = sync.write_taxonomy_redirects()
    assert written == 3  # 两个总览页 + 一个分类
    page = out_dir / "categories" / "数据库" / "index.md"
    assert page.is_file()
    assert 'content="0; url=/all/"' in page.read_text(encoding="utf-8")


def test_a_tag_url_becomes_a_redirect_page(sync, out_dir):
    _write_post(sync, out_dir, "post-1", tags=["PostgreSQL"])
    written = sync.write_taxonomy_redirects()
    assert written == 3
    page = out_dir / "tags" / "PostgreSQL" / "index.md"
    assert page.is_file()
    assert 'content="0; url=/all/"' in page.read_text(encoding="utf-8")


def test_a_nested_category_keeps_its_layers(sync, out_dir):
    """层级分类（``人生/成长之路``）的地址也是发布过的。"""
    _write_post(sync, out_dir, "post-1", categories=["人生/成长之路"])
    sync.write_taxonomy_redirects()
    page = out_dir / "categories" / "人生" / "成长之路" / "index.md"
    assert page.is_file()


def test_the_retired_paths_from_the_data_table_are_stubbed_too(sync, out_dir, monkeypatch):
    """历史上用过、现在没有文章归进去的分类名也得有去处。"""
    monkeypatch.setattr(sync, "RETIRED_TAXONOMY_PATHS", ["categories/集群"])
    sync.write_taxonomy_redirects()
    assert (out_dir / "categories" / "集群" / "index.md").is_file()


def test_taxonomy_redirect_with_an_illegal_filename_char_is_skipped(sync, out_dir):
    """分类名带冒号 —— 那个目录过不了 artifact 上传，宁可不发。"""
    _write_post(sync, out_dir, "post-1", categories=["PostgreSQL 源码修炼之路:内核深度拆解专题"])
    written = sync.write_taxonomy_redirects()
    assert written == 2  # 只有两个总览页
    assert not (out_dir / "categories" / "PostgreSQL 源码修炼之路:内核深度拆解专题").exists()


@pytest.mark.parametrize("bad", list(INVALID))
def test_no_illegal_char_ever_reaches_a_directory_name(sync, out_dir, bad):
    """每个非法字符都要被拦下来 —— 不是只拦冒号。"""
    _write_post(sync, out_dir, "post-1", categories=["分类{}名字".format(bad)])
    assert sync.write_taxonomy_redirects() == 2
    assert not (out_dir / "categories" / "分类{}名字".format(bad)).exists()


def test_article_redirect_with_an_illegal_filename_char_is_skipped(sync, out_dir, monkeypatch):
    """文章重定向的旧路径也一样 —— 拦在同一个地方。"""
    monkeypatch.setattr(sync, "_redirect_target_file", lambda p: "docs/somewhere/index.md")
    monkeypatch.setattr(sync, "git_date", lambda p: "2026-01-02")
    sync.REDIRECTS["旧路径:带冒号"] = "新路径"
    assert sync.write_redirects() == 0
    assert not (out_dir / "2026").exists()


def test_redirect_with_a_dated_key_lands_on_the_old_date(sync, out_dir, monkeypatch):
    """键里带日期的重定向：页面落在**旧 URL 当初的日期段**上。

    合并两篇逐字节相同的重复文章时，合并后的那篇只有一个日期 ——
    另一个旧 URL 的日期段跟它对不上。不带日期的键会落在错的地址上，
    真正的旧地址就 404 了；键里带上日期才落得准。
    """
    monkeypatch.setattr(sync, "_redirect_target_file", lambda p: "docs/merged/index.md")
    monkeypatch.setattr(sync, "git_date", lambda p: "2022-06-13 16:14:13")
    sync.REDIRECTS["2022/10/25/cluster/raft/旧文章"] = "merged/新文章"
    assert sync.write_redirects() == 1
    page = out_dir / "2022" / "10" / "25" / "cluster" / "raft" / "旧文章" / "index.md"
    assert page.is_file()
    # 指向的是新文章自己的地址
    assert "/2022/06/13/merged/" in page.read_text(encoding="utf-8")


def test_redirect_without_a_date_still_uses_the_new_files_date(sync, out_dir, monkeypatch):
    """普通键不受影响 —— 页面照旧落在新文件的日期段上。"""
    monkeypatch.setattr(sync, "_redirect_target_file", lambda p: "docs/merged/index.md")
    monkeypatch.setattr(sync, "git_date", lambda p: "2022-06-13 16:14:13")
    sync.REDIRECTS["cluster/raft/旧文章"] = "merged/新文章"
    assert sync.write_redirects() == 1
    assert (out_dir / "2022" / "06" / "13" / "cluster" / "raft" / "旧文章"
            / "index.md").is_file()
