"""Read a source post: front matter plus body.

Deliberately line-based.  The WeChat adapter needs a full block AST because
it keeps code blocks and tables; the Toutiao version drops both, so a line
scanner is enough -- and much smaller.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["SourcePost", "parse_front_matter", "load_post", "discover"]

_FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


@dataclass(frozen=True)
class SourcePost:
    """One blog post as it exists in ``source/_posts``."""

    slug: str
    title: str
    date: str
    body: str
    fields: dict = field(default_factory=dict)


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_front_matter(text: str):
    """Split front matter from the body.

    ``tools/sync-hexo.py`` generates the front matter itself, so its shape is
    known and fixed: ``key: value`` scalars plus ``key:`` followed by
    ``  - item`` lists.  Unknown keys are kept as they are, so a future
    contract field cannot break the parser.
    """
    match = _FM_RE.match(text)
    if not match:
        return {}, text

    fields: dict = {}
    list_key = None
    list_items: list = []

    def close_list():
        nonlocal list_key, list_items
        if list_key is not None:
            fields[list_key] = list(list_items)
        list_key = None
        list_items = []

    for raw in match.group(1).split("\n"):
        if not raw.strip():
            continue
        stripped = raw.lstrip()
        if stripped.startswith("- "):
            if list_key is not None:
                list_items.append(_unquote(stripped[2:]))
            continue
        if ":" in raw:
            key, _, value = raw.partition(":")
            key = key.strip()
            value = value.strip()
            if value == "":
                close_list()
                list_key = key
            else:
                close_list()
                fields[key] = _unquote(value)
    close_list()

    return fields, text[match.end():]


def load_post(path: Path, posts_dir: Path) -> SourcePost:
    """Load one post file into a :class:`SourcePost`."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    fields, body = parse_front_matter(text)
    slug = path.relative_to(posts_dir).with_suffix("").as_posix()
    title = str(fields.get("title") or path.stem).strip()
    date = str(fields.get("date") or "")
    return SourcePost(slug=slug, title=title, date=date, body=body, fields=fields)


def discover(posts_dir: Path) -> list:
    """Load every markdown post under ``posts_dir``."""
    posts_dir = Path(posts_dir)
    if not posts_dir.is_dir():
        raise FileNotFoundError(
            "找不到 {}。先跑 `python3 tools/sync-hexo.py`（约 3 分钟）。".format(posts_dir)
        )
    return [load_post(path, posts_dir) for path in sorted(posts_dir.rglob("*.md"))]
