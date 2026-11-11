"""Read a source post: front matter plus body.

Deliberately line-based.  The WeChat adapter needs a full block AST because
it keeps code blocks and tables; the Toutiao version drops both, so a line
scanner is enough -- and much smaller.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "SourcePost", "parse_front_matter", "load_post", "discover",
    "discover_unsupported",
]

_FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)

# The escapes ``tools/sync-hexo.py`` writes into a double-quoted value.
# ``yaml_escape`` doubles a backslash and escapes a double quote, so these
# two are exactly what can come back out of a quoted title.
_ESCAPES = {"\\": "\\", '"': '"'}
_ESCAPE_RE = re.compile(r"\\(.)")


@dataclass(frozen=True)
class SourcePost:
    """One blog post as it exists in ``source/_posts``."""

    slug: str
    title: str
    date: str
    body: str
    fields: dict[str, object] = field(default_factory=dict)


def _unquote(value: str) -> str:
    """Strip the surrounding quotes and undo the escapes inside them.

    ``tools/sync-hexo.py`` writes the title as a double-quoted YAML scalar
    and escapes what it has to (``yaml_escape``).  Hexo reads that back
    with a real YAML parser, which turns ``\\"`` into ``"`` again -- so we
    must undo the same escapes, otherwise the published title carries
    stray backslashes.  Single-quoted scalars keep their content verbatim,
    which is what YAML says.
    """
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        if value[0] == '"':
            inner = _ESCAPE_RE.sub(lambda m: _ESCAPES.get(m.group(1), m.group(0)), inner)
        return inner
    return value


def parse_front_matter(text: str) -> tuple[dict[str, object], str]:
    """Split front matter from the body.

    ``tools/sync-hexo.py`` generates the front matter itself, so its shape is
    known and fixed: ``key: value`` scalars plus ``key:`` followed by
    ``  - item`` lists.  Unknown keys are kept as they are, so a future
    contract field cannot break the parser.

    A document that opens a front matter block but never closes it is
    broken, and this raises ``ValueError`` rather than passing it off as a
    document without front matter.  Silently doing the latter would publish
    the raw ``---`` and ``title:`` lines as body text and fall back to the
    file name for the title -- a broken file going out as a good one.
    """
    match = _FM_RE.match(text)
    if not match:
        if text.startswith("---\n"):
            raise ValueError(
                "front matter 未闭合：文件以 '---' 开头，但没有找到配对的结束 '---'。"
            )
        return {}, text

    fields: dict[str, object] = {}
    list_key = None
    list_items: list[str] = []

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


def discover(posts_dir: Path) -> list[SourcePost]:
    """Load every markdown post under ``posts_dir``."""
    posts_dir = Path(posts_dir)
    if not posts_dir.is_dir():
        raise FileNotFoundError(
            "找不到 {}。先跑 `python3 tools/sync-hexo.py`（约 3 分钟）。".format(posts_dir)
        )
    return [load_post(path, posts_dir) for path in sorted(posts_dir.rglob("*.md"))]


def discover_unsupported(posts_dir: Path) -> list[str]:
    """列出 source/_posts 下本适配器不支持的文件（当前是 .html 母稿）。

    这些文件会被站点发布，但头条号 adapter 不解析它们。
    返回相对 posts_dir 的路径字符串列表，排序后返回。
    目录不存在时返回空列表。

    ``tools/sync-hexo.py`` 也会把 ``docs/`` 下的 .html 博文写进
    ``source/_posts/``，而 ``discover()`` 只收 .md —— 这些母稿不会进头条号
    的发布流程。把它们显式列出来，扫描方才能说清楚「哪些没发」而不是
    静默少发几篇。

    隐藏文件（``.DS_Store`` 之类）与隐藏目录不算：站点不会发布它们。
    """
    posts_dir = Path(posts_dir)
    if not posts_dir.is_dir():
        return []

    unsupported = []
    for path in posts_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(posts_dir)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if path.suffix == ".md":
            continue
        unsupported.append(relative.as_posix())
    return sorted(unsupported)
