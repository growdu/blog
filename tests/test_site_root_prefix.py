"""Contract tests for the site-root prefix of generated permalinks.

Background
----------
The same build is published twice:

* ``growdu.cn``             -- served from ``/``
* ``growdu.github.io/blog`` -- served from ``/blog/``

``_config.yml`` carries the mount point (``root:``), and the GitHub Pages
job rewrites it to ``/blog/`` before building.  Every absolute URL the
build emits therefore has to carry that prefix -- otherwise the mirror
serves 404s for links that work on the primary domain.

That is not hypothetical: article cross-links were emitted as
``/2026/11/11/...`` with no prefix at all, so *every* cross-article link
on the mirror was dead (830 pages, including posts from 2022).  The
canonical tag and ``og:image`` had the opposite bug -- ``config.url``
(``https://growdu.github.io/blog``) was concatenated with a
``url_for()`` result that already contained ``/blog``, producing
``/blog/blog/...``.

These tests pin both behaviours, plus the invariant that matters most:
the primary domain's output must not change.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"
SYNC_TOOL = TOOLS / "sync-hexo.py"
PATCH_TOOL = TOOLS / "patch-theme.py"
CHECK_TOOL = TOOLS / "check-built-links.py"
THEME_LAYOUT = REPO_ROOT / "themes" / "matery" / "layout"

# Put tools/ on sys.path so `import site_root` resolves the way the two
# build scripts resolve it.
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import site_root  # noqa: E402  (path set up above)


@pytest.fixture(scope="module")
def sync():
    """Import ``tools/sync-hexo.py`` as a module.

    Its ``main()`` is guarded by ``if __name__ == '__main__'``, so
    importing it only defines functions -- it does not rewrite ``source/``.
    """
    spec = importlib.util.spec_from_file_location("sync_hexo_under_test", SYNC_TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------- root reading


def test_site_root_defaults_to_empty_for_primary_domain():
    """The repo's `_config.yml` mounts the primary domain at `/`."""
    assert site_root.site_root() == ""


def test_site_root_reads_the_configured_mount_point(tmp_path):
    config = tmp_path / "_config.yml"
    config.write_text("url: https://growdu.github.io/blog\nroot: /blog/\n", encoding="utf-8")
    assert site_root.site_root(str(config)) == "/blog"


def test_site_root_tolerates_a_missing_config(tmp_path):
    assert site_root.site_root(str(tmp_path / "nope.yml")) == ""


def test_site_root_keeps_a_relative_root_rooted(tmp_path):
    config = tmp_path / "_config.yml"
    config.write_text("root: blog\n", encoding="utf-8")
    assert site_root.site_root(str(config)) == "/blog"


# ---------------------------------------------------------------- permalinks


def test_permalink_without_root_is_the_legacy_format():
    """The primary domain's URLs must not change."""
    assert (
        site_root.permalink("2026-11-11 23:20:00", "life/gaokao/chemistry-methods")
        == "/2026/11/11/life/gaokao/chemistry-methods/"
    )


def test_permalink_carries_the_mount_point():
    assert (
        site_root.permalink(
            "2026-11-11 23:20:00", "life/gaokao/chemistry-methods", root="/blog"
        )
        == "/blog/2026/11/11/life/gaokao/chemistry-methods/"
    )


def test_resolved_cross_links_carry_the_mount_point(sync, monkeypatch):
    """The whole point: a link from one article to another must keep the root."""
    monkeypatch.setattr(site_root, "_ROOT_CACHE", {})
    monkeypatch.setattr(site_root, "site_root", lambda *a, **k: "/blog")
    url = sync._resolve_link_target(
        "life/gaokao/yunnan-policy/index.html", "life/gaokao/chemistry-methods"
    )
    assert url is not None
    assert url.startswith("/blog/")
    assert url.endswith("/life/gaokao/yunnan-policy/")


def test_no_hardcoded_absolute_permalinks_remain_in_the_sync_tool():
    """A literal `/YYYY/...` f-string would silently bypass the root."""
    source = SYNC_TOOL.read_text(encoding="utf-8")
    assert "f'/{date[:4]}" not in source
    assert 'f"/{date[:4]}' not in source


def test_root_absolute_markdown_links_get_the_mount_point(sync, monkeypatch):
    """A hand-written `](/2026/...)` link is site-internal, so it needs the root."""
    monkeypatch.setattr(sync, "SITE_ROOT", "/blog")
    out = sync.rewrite_links(
        "见 [政策](/2026/11/11/life/gaokao/yunnan-policy/)",
        "life/gaokao/chemistry-methods/index.md",
    )
    assert "](/blog/2026/11/11/life/gaokao/yunnan-policy/)" in out


def test_root_absolute_markdown_links_are_untouched_without_a_root(sync, monkeypatch):
    monkeypatch.setattr(sync, "SITE_ROOT", "")
    out = sync.rewrite_links(
        "见 [政策](/2026/11/11/life/gaokao/yunnan-policy/)",
        "life/gaokao/chemistry-methods/index.md",
    )
    assert "](/2026/11/11/life/gaokao/yunnan-policy/)" in out


def test_protocol_relative_links_are_never_rewritten(sync, monkeypatch):
    monkeypatch.setattr(sync, "SITE_ROOT", "/blog")
    out = sync.rewrite_links(
        "见 [CDN](//cdn.example/x.js)",
        "life/gaokao/chemistry-methods/index.md",
    )
    assert "](//cdn.example/x.js)" in out


def test_the_sync_tool_uses_the_shared_site_root_module():
    source = SYNC_TOOL.read_text(encoding="utf-8")
    assert "from site_root import" in source


# -------------------------------------------------------------- 404 page URLs


def test_root_prefix_urls_leaves_protocol_relative_urls_alone():
    html = '<script src="//cdn.example/x.js"></script>'
    assert site_root.root_prefix_urls(html, root="/blog") == html


def test_root_prefix_urls_prefixes_root_absolute_urls():
    html = '<a href="/about/">关于</a><img src="/medias/logo.jpg">'
    out = site_root.root_prefix_urls(html, root="/blog")
    assert 'href="/blog/about/"' in out
    assert 'src="/blog/medias/logo.jpg"' in out


def test_root_prefix_urls_is_a_noop_without_a_root():
    html = '<a href="/about/">关于</a>'
    assert site_root.root_prefix_urls(html, root="") == html


def test_the_404_page_goes_through_the_root_prefixer():
    source = SYNC_TOOL.read_text(encoding="utf-8")
    assert "root_prefix_urls(" in source


# --------------------------------------------------------------- theme patches


def test_theme_head_does_not_double_the_mount_point():
    """`config.url` already carries the mount point; `url_for()` adds it again."""
    source = PATCH_TOOL.read_text(encoding="utf-8")
    assert "config.url %><%- url_for(page.path)" not in source


def test_no_template_combines_config_url_with_url_for():
    """Any `config.url ... url_for(...)` pair yields a doubled mount point."""
    offenders = []
    for path in sorted(THEME_LAYOUT.rglob("*.ejs")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"config\.url[^%\n]{0,60}url_for\(", text):
            offenders.append(f"{path.relative_to(REPO_ROOT)}: {match.group(0)[:70]}")
    assert not offenders, "config.url 与 url_for 混用会产生双前缀：\n" + "\n".join(offenders)


def test_theme_head_uses_a_root_less_absolute_url_for_canonical():
    source = (REPO_ROOT / "themes" / "matery" / "layout" / "_partial" / "head.ejs").read_text(
        encoding="utf-8"
    )
    assert '<link rel="canonical" href="<%- _selfUrl %>">' in source


def test_theme_head_assets_are_root_aware():
    source = PATCH_TOOL.read_text(encoding="utf-8")
    assert "url_for('/manifest.json')" in source
    assert "url_for('/favicon.svg')" in source


def test_the_patch_tool_head_block_is_root_aware():
    source = PATCH_TOOL.read_text(encoding="utf-8")
    assert "url_for('/manifest.json')" in source
    assert "url_for('/favicon.svg')" in source
    assert '<link rel="canonical" href="<%- _selfUrl %>">' in source


# --------------------------------------------------- built-link checker


def _load_link_checker():
    spec = importlib.util.spec_from_file_location(
        "check_built_links_under_test", CHECK_TOOL
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_link_checker_strips_the_mount_point_prefix():
    checker = _load_link_checker()
    prefix = checker.ROOT_PREFIX
    mounted = f"{prefix}/2026/11/11/life/gaokao/chemistry-methods/"
    assert checker.strip_root(mounted) == "/2026/11/11/life/gaokao/chemistry-methods/"


def test_link_checker_leaves_root_less_links_alone():
    checker = _load_link_checker()
    assert checker.strip_root("/2026/11/11/life/gaokao/chemistry-methods/") == (
        "/2026/11/11/life/gaokao/chemistry-methods/"
    )


def test_link_checker_resolves_a_mounted_link_to_the_built_file():
    checker = _load_link_checker()
    if not checker.PUBLIC.is_dir():
        pytest.skip("还没有构建产物（public/ 不存在）")
    link = f"{checker.ROOT_PREFIX}/2026/11/11/life/gaokao/chemistry-methods/"
    target = checker.PUBLIC / checker.strip_root(link).strip("/") / "index.html"
    assert target.exists(), f"干净检出里应存在 {target}"


# ------------------------------------------------------- media path awareness


def _malformed_ejs_blocks(text: str) -> list[str]:
    """EJS blocks that are nested or never closed.

    A ``<% ... %>`` opened inside another ``<% ... %>`` is a syntax error
    that EJS does not always report loudly -- the template simply stops
    rendering, and the page silently loses the part that came after it.
    """
    problems: list[str] = []
    pos = 0
    while True:
        start = text.find("<%", pos)
        if start < 0:
            return problems
        end = text.find("%>", start)
        if end < 0:
            problems.append("未闭合的 <% 块")
            return problems
        inner = text[start + 2:end]
        if "<%" in inner:
            problems.append(f"<% 嵌套在 <% ... %> 内：{inner.strip()[:60]}")
        pos = end + 2


def test_theme_templates_are_well_formed_ejs():
    offenders = []
    for path in sorted(THEME_LAYOUT.rglob("*.ejs")):
        for problem in _malformed_ejs_blocks(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.relative_to(REPO_ROOT)}: {problem}")
    assert not offenders, "EJS 模板语法有误：\n" + "\n".join(offenders)


def test_theme_head_template_is_well_formed_ejs():
    path = THEME_LAYOUT / "_partial" / "head.ejs"
    assert not _malformed_ejs_blocks(path.read_text(encoding="utf-8"))


def test_theme_media_urls_are_root_aware():
    """No theme file may request a media asset from the domain root.

    ``href="/libs/prism/prism.min.css"`` 404s on a site mounted under
    a sub-path; the template has to go through ``url_for()``.
    """
    offenders = []
    for path in sorted(THEME_LAYOUT.rglob("*.ejs")):
        text = path.read_text(encoding="utf-8")
        if not site_root.media_paths_are_root_aware(text):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, "仍以根绝对路径引用媒体资源的主题文件：\n" + "\n".join(offenders)


def test_media_paths_are_root_aware_accepts_url_for_wrappers():
    assert site_root.media_paths_are_root_aware(
        '<link href="<%- url_for(\'/libs/prism/prism.min.css\') %>" rel="stylesheet"/>'
    )


def test_media_paths_are_root_aware_rejects_a_bare_root_path():
    assert not site_root.media_paths_are_root_aware(
        '<script src="/libs/jquery/jquery.min.js"></script>'
    )


def test_media_paths_are_root_aware_ignores_bare_path_fragments():
    """A default path that is later concatenated into an absolute URL is fine."""
    assert site_root.media_paths_are_root_aware(
        "<% var ogImage = page.cover || '/medias/featureimages/0.jpg'; %>"
    )
