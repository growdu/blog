"""Site-root awareness for the URLs this blog emits.

Why this module exists
----------------------
One build is published to two places:

* ``growdu.cn``             -- mounted at ``/``
* ``growdu.github.io/blog`` -- mounted at ``/blog/``

``_config.yml`` carries the mount point in ``root:``, and the GitHub
Pages job rewrites it to ``/blog/`` before building.  Every absolute
URL the build emits therefore has to carry that prefix, otherwise the
mirror serves 404s for links that work on the primary domain.

Two distinct bugs came out of that:

* **Missing prefix.**  Article cross-links were emitted as
  ``/2026/11/11/...`` with no prefix at all, so every cross-article
  link on the mirror was dead -- 830 pages, including posts from 2022.
* **Doubled prefix.**  The theme's ``canonical`` / ``og:image`` were
  built as ``config.url + url_for(page.path)``, but ``config.url``
  already carried ``/blog`` while ``url_for()`` adds the root again,
  yielding ``/blog/blog/...``.

The rule this module encodes:

* a **path** (what the browser requests) must carry the mount point --
  use :func:`permalink`, :func:`root_prefix_urls` and
  :func:`rewrite_media_paths`;
* an **absolute URL** must be assembled from ``config.url`` (which
  already carries the mount point) plus a path *without* the root --
  in a Hexo template that is ``<%- page.permalink %>`` for a page's
  own address, and ``config.url`` plus a literal path for a static
  asset.
"""

from __future__ import annotations

import os
import re
from urllib.parse import quote

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A root-absolute media path inside a quoted string.  The leading quote
# is what makes it safe to match: `https://cdn.example/libs/x.js` has
# no quote immediately before `/libs/`, so it never matches.
_MEDIA_PATH_RE = re.compile(r"""(['"])(/(?:medias|libs)/[^'"]*)\1""")

# Cache of config path -> mount point (see site_root below).
_ROOT_CACHE: dict[str, str] = {}


def site_root(config_path: str | None = None) -> str:
    """Read the deployment mount point from ``_config.yml``.

    Returns the prefix without a trailing slash: ``''`` for the primary
    domain, ``'/blog'`` for the GitHub Pages mirror.

    The answer is cached per config path: the sync tool asks for a
    permalink thousands of times per build, and re-reading the config
    for each of them is pure overhead.
    """
    if config_path is None:
        config_path = os.path.join(REPO_ROOT, '_config.yml')
    cached = _ROOT_CACHE.get(config_path)
    if cached is not None:
        return cached
    root = ''
    try:
        with open(config_path, encoding='utf-8') as f:
            for line in f:
                m = re.match(r'^root:\s*(\S+)\s*$', line)
                if m:
                    root = m.group(1).strip().strip('"\'')
                    if not root.startswith('/'):
                        root = '/' + root
                    root = root.rstrip('/')
                    break
    except OSError:
        pass
    _ROOT_CACHE[config_path] = root
    return root


def permalink(date: str, post_path: str, root: str | None = None) -> str:
    """Absolute permalink for a post, carrying the mount point.

    ``date`` is the ``YYYY-MM-DD HH:MM:SS`` string the sync tool works
    with; only its first ten characters matter here.
    """
    if root is None:
        root = site_root()
    return f'{root}/{date[:4]}/{date[5:7]}/{date[8:10]}/{quote(post_path)}/'


def root_prefix_urls(html: str, root: str | None = None) -> str:
    """Prefix every root-absolute URL in a raw HTML blob with the root.

    Used for the hand-written 404 page, whose links are plain
    ``href="/..."`` strings rather than Hexo helpers.  Protocol-relative
    URLs (``//cdn.example/...``) are left alone.
    """
    if root is None:
        root = site_root()
    if not root:
        return html
    return re.sub(r'(["\'])/(?!/)', lambda m: m.group(1) + root + '/', html)


def media_paths_are_root_aware(text: str) -> bool:
    """True when no root-absolute media URL is left in ``text``.

    A root-absolute media URL is one that the browser would request
    from the domain root -- ``href="/libs/prism/prism.min.css"`` --
    which 404s on a site that is mounted under a sub-path.  Only
    ``href`` / ``src`` attributes are considered: a bare path fragment
    (a default image path that is later concatenated into an absolute
    URL, say) is not a URL on its own.
    """
    for match in re.finditer(r"""(?:href|src)\s*=\s*(['"])(/(?:medias|libs)/[^'"]*)\1""", text):
        return False
    for match in re.finditer(r"""url\(\s*(['"])(/(?:medias|libs)/[^'"]*)\1\s*\)""", text):
        return False
    return True
