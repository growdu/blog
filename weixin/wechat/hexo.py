"""Reuse of ``tools/sync-hexo.py``.

The converter must not re-implement anything the site build already
knows.  ``sync-hexo.py`` carries the ``slugize`` rule that turns a
category name into the URL segment the site actually serves -- a
category named 「PostgreSQL 源码修炼之路」 lives at
``/categories/.../PostgreSQL-源码修炼之路/`` and not at
``.../PostgreSQL%20源码修炼之路/``.  Copying the rule here would let
the two drift apart, so the module is loaded and its function called.

Loading is safe: every module-level statement in ``sync-hexo.py`` is a
definition, and the work happens inside ``main()`` behind an
``if __name__ == '__main__'`` guard.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

__all__ = ["slugize", "sync_module"]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SYNC_PATH = _REPO_ROOT / "tools" / "sync-hexo.py"

_module = None
_slugize = None


def sync_module():
    """Load ``tools/sync-hexo.py`` as a module, once per process."""
    global _module
    if _module is None:
        if not _SYNC_PATH.is_file():
            raise FileNotFoundError("找不到 {}".format(_SYNC_PATH))
        spec = importlib.util.spec_from_file_location("blog_sync_hexo", _SYNC_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _module = module
    return _module


def slugize(name: str, separator: str = "-") -> str:
    """Slugize a name the way the site build does."""
    global _slugize
    if _slugize is None:
        _slugize = sync_module().slugize
    return _slugize(name, separator)
