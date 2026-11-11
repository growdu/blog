#!/usr/bin/env python3
"""Check the built site for dead in-page anchors.

Run after ``npx hexo generate``::

    python3 tools/check-built-links.py

Scope is the ``life/gaokao`` section of the generated site, discovered
dynamically so the checker never has to be updated when a post is added,
renamed, or re-dated.

Why this exists
---------------
A table-of-contents anchor that points at a heading id which does not
exist still renders as a perfectly normal, clickable link -- it just
silently lands the reader back on the top of the page instead of the
section it names.  Nothing in the build complains, so the breakage
survives until a reader reports that the table of contents "does
nothing".

The heading ids are produced by ``hexo-util``'s ``slugize()``; this
script reads them straight out of the generated HTML, so it stays in
step with the renderer without re-implementing it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC = REPO_ROOT / "public"

# The mount point the site is built for (`root:` in _config.yml).  The
# GitHub Pages build mounts the site under /blog/, and its links carry
# that prefix; the paths inside public/ never do, so the prefix has to
# come back off before a link is resolved against the built tree.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from site_root import site_root  # noqa: E402

ROOT_PREFIX = site_root()


def strip_root(link: str) -> str:
    """Remove the mount-point prefix from a built link."""
    if ROOT_PREFIX and link.startswith(ROOT_PREFIX + "/"):
        return link[len(ROOT_PREFIX):]
    return link

# Anchors injected by the theme itself (search box, back-to-top, ...).
THEME_ANCHORS = {"searchModal", "top", "!", "headerlink", "comments"}

ID_RE = re.compile(r'<h[1-6] id="([^"]*)"')
ANCHOR_RE = re.compile(r'href="#([^"]+)"')
LINK_RE = re.compile(r'href="(/[^"]*?/life/gaokao/[^"]*)"')


def gaokao_pages() -> list[Path]:
    """Every built page that belongs to the gaokao section.

    Covers both the bundle layout (``life/gaokao/<name>/index.html``) and
    the flat permalink layout (``life/gaokao-<name>/index.html``).
    """
    return sorted(
        page
        for page in PUBLIC.rglob("index.html")
        if "/life/gaokao" in page.as_posix()
    )


def main() -> int:
    if not PUBLIC.is_dir():
        print(f"找不到 {PUBLIC}，请先执行 npx hexo generate")
        return 2

    pages = gaokao_pages()
    if not pages:
        print("gaokao 小节下没有已生成的页面")
        return 2

    failures: list[str] = []

    for page in pages:
        html = page.read_text(encoding="utf-8")
        rel = page.relative_to(PUBLIC).as_posix()

        ids = set(ID_RE.findall(html))
        if not ids:
            # Flat permalink stubs are redirect pages, not articles.
            continue

        anchors = {unquote(a) for a in ANCHOR_RE.findall(html)}
        anchors = {a for a in anchors if a not in THEME_ANCHORS}
        dead = sorted(a for a in anchors if a not in ids)
        if dead:
            failures.append(f"{rel}: 失效页内锚点 {dead}")

        for link in sorted(set(LINK_RE.findall(html))):
            target = PUBLIC / strip_root(link).strip("/") / "index.html"
            if not target.exists():
                failures.append(f"{rel}: 失效文章链接 {link}")

        status = "OK" if not dead else f"失效锚点 {len(dead)}"
        print(f"  {rel}: {len(ids)} 个标题 id, {len(anchors)} 个目录锚点 -> {status}")

    print()
    if failures:
        print("=== 存在问题 ===")
        for failure in failures:
            print(" -", failure)
        return 1

    print(f"=== 全部通过（{len(pages)} 个页面）===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
