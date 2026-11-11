"""Discover blog posts and validate them against WeChat's hard limits.

Input is ``source/_posts/``, the output of ``tools/sync-hexo.py``.  That
step already rewrote image paths, rewrote relative links into absolute
permalinks, stripped the leading H1 and rebuilt the front-matter, so this
module never re-implements any of that.  It only reads what sync produced
and adds the metadata WeChat needs: digest, permalink and eligibility.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

BODY_LIMIT = 20000
TITLE_LIMIT = 64
DIGEST_LIMIT = 120

# WeChat caps the article body at 20000 characters of the ``content``
# field, which is the rendered HTML.  BODY_LIMIT is a cheap pre-check on
# the raw markdown; it is a necessary but not sufficient condition --
# across the corpus 38 posts pass the raw check and still exceed the
# limit once rendered.  The authoritative check therefore runs on the
# rendered content (RenderResult.content_length) before anything is
# uploaded.
CONTENT_LIMIT = 20000

_FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_HEADING_RE = re.compile(r"^#{1,6}\s")
_TABLE_RE = re.compile(r"^\s*\|")
_LIST_RE = re.compile(r"^\s*([-*+]|\d+\.)\s")
_QUOTE_RE = re.compile(r"^\s*>")
_HR_RE = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_SENTENCE_MARKS = ("。", "！", "？", ". ", "! ", "? ")


@dataclass(frozen=True)
class Post:
    """A single blog post prepared for conversion."""

    path: Path
    slug: str
    title: str
    digest: str
    permalink: str
    body: str
    categories: tuple
    date: str

    @property
    def fingerprint(self) -> str:
        """Content hash of the body, used as the idempotency key."""
        return hashlib.sha256(self.body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Eligibility:
    """Whether a post may be published, and why not when it may not."""

    ok: bool
    reasons: tuple


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_front_matter(text: str):
    """Split YAML-ish front-matter from the body.

    ``tools/sync-hexo.py`` generates the front-matter itself, so the shape
    is known and fixed: ``key: value`` scalars plus ``key:`` followed by
    ``  - item`` lists.  A tiny hand-written parser avoids adding a YAML
    dependency for a format we control.

    Returns ``(fields, body)``.  A list field maps to a list of strings;
    a single-item list is kept as a one-element list so callers do not
    have to guess the shape.
    """
    match = _FM_RE.match(text)
    if not match:
        return {}, text

    fields = {}
    list_key = None
    list_items = []

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
            close_list()
            if value:
                fields[key] = _unquote(value)
            else:
                list_key = key
    close_list()

    return fields, text[match.end():]


def _strip_inline(text: str) -> str:
    text = _IMAGE_RE.sub(lambda m: m.group(1), text)
    text = _LINK_RE.sub(lambda m: m.group(1), text)
    text = _INLINE_CODE_RE.sub(lambda m: m.group(1), text)
    text = _BOLD_RE.sub(lambda m: m.group(1), text)
    text = _ITALIC_RE.sub(lambda m: m.group(1), text)
    return text.strip()


def make_digest(body: str, limit: int = DIGEST_LIMIT) -> str:
    """Build a WeChat digest (<= limit chars) from the first real paragraph.

    Headings, code fences, tables, lists, quotes and images are skipped:
    none of them reads as a standalone summary.
    """
    in_fence = False
    paragraph = []

    for raw in body.split("\n"):
        line = raw.rstrip()
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not line.strip():
            if paragraph:
                break
            continue
        if (_HEADING_RE.match(line) or _TABLE_RE.match(line) or _LIST_RE.match(line)
                or _QUOTE_RE.match(line) or _HR_RE.match(line)):
            continue
        paragraph.append(line.strip())

    if not paragraph:
        return ""

    text = re.sub(r"\s+", " ", _strip_inline(" ".join(paragraph))).strip()
    if len(text) <= limit:
        return text

    clipped = text[:limit]
    # The limit is a maximum, not a target: a digest that ends on a
    # sentence boundary is always better than one cut mid-sentence, even
    # when that leaves it noticeably shorter than the limit.
    best = -1
    for mark in _SENTENCE_MARKS:
        index = clipped.rfind(mark)
        if index > best:
            best = index
    if best >= 0:
        for mark in _SENTENCE_MARKS:
            index = clipped.rfind(mark)
            if index == best:
                return clipped[:index + len(mark)].strip()
    return clipped.strip()


def build_permalink(slug: str, date: str) -> str:
    """Build the canonical site URL of a post.

    Hexo's ``permalink: :year/:month/:day/:title/`` expands ``:title`` to
    the post path relative to ``source/_posts/`` (verified against the
    published sitemap), so the permalink mirrors that path exactly.
    """
    parts = date[:10].split("-")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        parts = ["2024", "01", "01"]
    return "/{}/{}/{}/{}/".format(parts[0], parts[1], parts[2], quote(slug))


def load_post(path: Path, posts_dir: Path) -> Post:
    """Load one post file into a :class:`Post`."""
    text = Path(path).read_text(encoding="utf-8")
    fields, body = parse_front_matter(text)

    slug = Path(path).relative_to(posts_dir).with_suffix("").as_posix()
    title = (fields.get("title") or Path(path).stem).strip()
    date = fields.get("date") or "2024-01-01 00:00:00"

    raw_categories = fields.get("categories", "")
    if isinstance(raw_categories, str):
        categories = (raw_categories,) if raw_categories else ()
    else:
        categories = tuple(raw_categories)

    return Post(
        path=Path(path),
        slug=slug,
        title=title,
        digest=make_digest(body),
        permalink=build_permalink(slug, date),
        body=body,
        categories=categories,
        date=date,
    )


def discover(posts_dir: Path) -> list:
    """Load every markdown post under ``posts_dir``."""
    posts_dir = Path(posts_dir)
    if not posts_dir.is_dir():
        raise FileNotFoundError(
            "source/_posts not found at {}. Run `python3 tools/sync-hexo.py` first "
            "(it takes about three minutes).".format(posts_dir)
        )
    return [load_post(path, posts_dir) for path in sorted(posts_dir.rglob("*.md"))]


def check_eligibility(post: Post) -> Eligibility:
    """Check the post against WeChat's hard limits.

    Overlong posts are reported, never silently truncated: a truncated
    deep-dive article is worse than no article at all.
    """
    reasons = []

    body_length = len(re.sub(r"\s", "", post.body))
    if body_length > BODY_LIMIT:
        reasons.append("正文 {} 字，超过上限 {} 字".format(body_length, BODY_LIMIT))

    if len(post.title) > TITLE_LIMIT:
        reasons.append("标题 {} 字符，超过上限 {} 字符".format(len(post.title), TITLE_LIMIT))

    return Eligibility(ok=not reasons, reasons=tuple(reasons))
