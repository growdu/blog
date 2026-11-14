"""Discover blog posts and validate them against WeChat's hard limits.

Input is ``source/_posts/``, the output of ``tools/sync-hexo.py``.  That
step already rewrote image paths, rewrote relative links into absolute
permalinks, stripped the leading H1 and rebuilt the front-matter, so this
module never re-implements any of that.  It only reads what sync produced
and adds the metadata WeChat needs: digest, permalink and eligibility.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from .digest import DIGEST_LIMIT, make_digest
from .titles import TITLE_LIMIT

AUTHOR_LIMIT = 16

# The author the drafts carry when nobody says otherwise.  It is also
# the one that is left out of the content fingerprint: the drafts in the
# box were made with it, so counting it would change the hash of every
# article and send all of them again for no change in their content.
DEFAULT_AUTHOR = "growdu"

# The body limit of one draft, in characters of rendered HTML.
#
# The official field table says "content 少于 2 万字符", but that line is
# wrong.  ``draft/add`` was measured taking 20 001, 25 000, 40 000,
# 65 535 and 100 000 characters, and every one of them came back from
# ``draft/get`` with the same length -- not one character was dropped.
# The same table claims the title is 32 characters while the editor
# takes 64: it is a copy of an old version, not a description of the
# platform.  The backend editor does not truncate either -- on
# 2026-11-14 the account owner opened a long draft and the body was
# complete.
#
# So this is not a platform limit but a choice -- how long one draft
# should be.  Only a quarter of the rendered HTML is text the reader
# sees; the inline styles eat the rest.  20 000 characters therefore
# reach the reader as about 5 000 words, and 60 000 as about 15 000.
#
# The default sits below the measured ceiling on purpose: 60 000
# characters is about 15 000 words for the reader, which is already a
# long read, and it keeps a comfortable margin against anything the
# platform might still enforce on the editor side.  A longer article is
# one flag away: ``--max-length`` (or ``WX_MAX_LENGTH``) takes it up to
# 100 000, and the limit is a parameter of the whole pipeline rather
# than a constant.
CONTENT_LIMIT = 60000

# The cheap pre-check on the raw markdown.  The rendered HTML is never
# shorter than the text it was rendered from -- checked over the whole
# corpus -- so the same number is a valid necessary condition.  The
# authoritative check runs on the rendered content
# (RenderResult.content_length) before anything is uploaded.
BODY_LIMIT = CONTENT_LIMIT

# WeChat also caps the body at 1 MB of bytes.
CONTENT_BYTES_LIMIT = 1024 * 1024


def resolve_content_limit(value: int = 0) -> int:
    """The body limit of this run.

    The command line wins, then ``WX_MAX_LENGTH``, then the default.
    A value that is not a positive whole number is refused rather than
    ignored: a typo in the limit must not quietly halve or double
    every article in the corpus.
    """
    raw = value or os.environ.get("WX_MAX_LENGTH", "") or 0
    if raw == 0 or raw == "":
        return CONTENT_LIMIT
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        raise ValueError("正文上限不是一个整数: {}".format(raw))
    if limit <= 0:
        raise ValueError("正文上限必须是正整数: {}".format(raw))
    return limit

_FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


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


def is_empty(post: Post) -> bool:
    """True when the article has no content left after its front matter.

    A file that carries nothing but its front matter is a page with a
    title and nothing else.  Put into the draft box it becomes a shell
    -- a title, a category line and a signature around no text at all
    -- so it is skipped instead, and the reason is written down.
    """
    return not re.sub(r"\s", "", post.body)


# How short a draft has to be to count as an empty shell.  The shell a
# post without content used to produce is about 115 characters: the
# category line, the signature and the transition line.  The limit is
# generous on purpose -- a draft the author has since written into is
# no longer a shell, and it must not be cleaned up.
SHELL_LIMIT = 500


def is_empty_shell(content: str) -> bool:
    """True when a draft still holds nothing but its own framing.

    The judgement is on the length of the body, not on the title: an
    author who opened such a draft and wrote something into it has
    turned it back into a real article, and that must survive.
    """
    return len(content) < SHELL_LIMIT


def check_eligibility(post: Post) -> Eligibility:
    """Check the post against the things that really stop it.

    Neither a long title nor a long body is a reason to skip the
    article any more.  The title is shortened at a boundary that keeps
    the topic (``wechat/titles``), and the body is split into several
    drafts that each fit (``wechat/split.py``).  The lengths are still
    measured -- the ``audit`` command reports them -- but they no longer
    decide whether the article may be published.

    An article with no content at all is the one thing that cannot be
    published: there is nothing to put in the draft.
    """
    reasons = []
    if is_empty(post):
        reasons.append("正文为空：源文件里只剩 front matter，没有可发布的内容")
    return Eligibility(ok=not reasons, reasons=tuple(reasons))
