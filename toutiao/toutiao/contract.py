"""Slice a source post into the Toutiao version.

The Toutiao version is a re-cut, not a copy: 3K of prose, one to three
images, and every link flattened to plain text.  The reasons are platform
constraints, not taste:

- the title cap is 30 characters
- Toutiao will not render an external image, so every image is a manual
  upload step -- which is why there are only three of them
- an external URL is not a link unless the account has the "insert external
  link" entitlement, and the platform forbids external jump code outright
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .capability import Limits
from .mdparse import SourcePost

__all__ = ["SliceResult", "ToutiaoArticle", "slice_post"]

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
_LIST = re.compile(r"^(?:[-*+]|\d+\.)\s+(.*)$")
_MARKER = re.compile(r"^【图(\d+)】$")
_LINK = re.compile(r"(?<!!)\[([^\]]*)\]\([^)]*\)")
_CJK = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")


@dataclass(frozen=True)
class ToutiaoArticle:
    """The Toutiao-shaped version of one post."""

    content_id: str
    title: str
    digest: str
    body: str
    images: tuple[str, ...]
    title_truncated: bool
    body_truncated: bool
    dropped_links: int
    notes: tuple[str, ...]


@dataclass(frozen=True)
class SliceResult:
    """Either an article, or the reason the post cannot be published."""

    article: ToutiaoArticle | None = None
    reason: str | None = None


def _field_text(fields: dict, key: str) -> str:
    value = fields.get(key)
    if isinstance(value, str):
        return value.strip()
    return ""


def _join(lines: list) -> str:
    """Join wrapped lines back into one paragraph.

    Chinese text is joined without a space; anything else keeps one.
    """
    out = ""
    for line in lines:
        if not out:
            out = line
            continue
        if _CJK.search(out[-1]) and _CJK.search(line[0]):
            out += line
        else:
            out += " " + line
    return out


def _truncate_title(title: str, limit: int) -> str:
    """Cut a title to ``limit`` characters, preferring a natural break."""
    head = title[:limit]
    for separator in ("：", ":", "，", "、", "——", "—", " ", "|"):
        cut = head.rfind(separator)
        if cut >= limit // 2:
            return head[:cut].rstrip(" ：:，、—|")
    return head.rstrip(" ：:，、—|")


def _scan(body: str) -> tuple[list[str], list[str]]:
    """Split a post body into kept blocks and image paths.

    Kept: ``##`` / ``###`` headings, paragraphs, list items.
    Dropped: fenced code, tables, block quotes, raw HTML, ``####`` and
    deeper headings -- they are exactly what makes a 3K version impossible.

    Heading levels are normalized: ``##`` and ``###`` both come out as
    ``##``, because a ``##`` sub-heading is what the Toutiao version must
    carry between paragraphs.  ``#`` is dropped -- that is the post title,
    which already lives in the title field.
    """
    blocks: list[str] = []
    images: list[str] = []
    paragraph: list[str] = []

    def flush():
        if paragraph:
            blocks.append(_join(paragraph))
            del paragraph[:]

    in_fence = False
    fence_marker = ""
    for raw in body.split("\n"):
        stripped = raw.strip()

        if in_fence:
            if stripped.startswith(fence_marker):
                in_fence = False
            continue

        if stripped.startswith("```") or stripped.startswith("~~~"):
            flush()
            in_fence = True
            fence_marker = stripped[:3]
            continue

        if not stripped:
            flush()
            continue

        if stripped.startswith("|") or stripped.startswith(">") or stripped.startswith("<"):
            flush()
            continue

        heading = _HEADING.match(stripped)
        if heading:
            flush()
            if 2 <= len(heading.group(1)) <= 3:
                blocks.append("## " + heading.group(2).strip())
            continue

        image = _IMAGE.match(stripped)
        if image:
            flush()
            images.append(image.group(2).strip())
            blocks.append("【图{}】".format(len(images)))
            continue

        item = _LIST.match(stripped)
        if item:
            flush()
            blocks.append("- " + item.group(1).strip())
            continue

        paragraph.append(stripped)

    flush()
    return blocks, images


def _strip_links(text: str) -> tuple[str, int]:
    """Turn every markdown link into plain text; count what was removed."""
    count = 0

    def replace(match):
        nonlocal count
        count += 1
        return match.group(1)

    return _LINK.sub(replace, text), count


def _first_paragraph(blocks: list[str]) -> str:
    for block in blocks:
        if not block or block.startswith("## ") or block.startswith("【图"):
            continue
        if block.startswith("- "):
            return block[2:].strip()
        return block
    return ""


def slice_post(post: SourcePost, limits: Limits, source_url: str = "https://growdu.cn") -> SliceResult:
    """Cut one source post into the Toutiao version.

    The digest falls back through ``description`` -> ``tldr`` -> the first
    paragraph -> the article title.  The title is the last resort: it only
    steps in when the body has no paragraph to summarize at all, which is
    what a picture-led post looks like.  A digest that is still too long
    is cut down and the cut is written into ``notes`` -- nothing is
    shortened silently.
    """
    notes: list[str] = []

    short_title = _field_text(post.fields, "short_title")
    if short_title:
        if len(short_title) > limits.title_chars:
            return SliceResult(
                reason="short_title 超过 {} 字（{}）".format(limits.title_chars, len(short_title))
            )
        title = short_title
        title_truncated = False
    elif len(post.title) > limits.title_chars:
        title = _truncate_title(post.title, limits.title_chars)
        title_truncated = True
        notes.append("标题已裁剪到 {} 字".format(limits.title_chars))
    else:
        title = post.title
        title_truncated = False

    blocks, images = _scan(post.body)
    if not blocks:
        # Nothing survived the filter: a body of nothing but tables,
        # quotes, code fences or raw HTML has no Toutiao version.  Say so
        # instead of publishing an empty article.
        return SliceResult(reason="正文里没有可保留的内容")

    if len(images) > limits.max_body_images:
        dropped = len(images) - limits.max_body_images
        images = images[: limits.max_body_images]
        blocks = [
            block
            for block in blocks
            if not (_MARKER.match(block) and int(_MARKER.match(block).group(1)) > limits.max_body_images)
        ]
        notes.append("正文图 {} 张，只保留前 {} 张".format(len(images) + dropped, limits.max_body_images))

    dropped_links = 0
    stripped_blocks = []
    for block in blocks:
        text, count = _strip_links(block)
        dropped_links += count
        stripped_blocks.append(text)
    blocks = stripped_blocks

    digest = (
        _field_text(post.fields, "description")
        or _field_text(post.fields, "tldr")
        or _first_paragraph(blocks)
        or title
    )
    if not digest:
        return SliceResult(reason="正文里没有可摘要的段落")
    if len(digest) > limits.digest_chars:
        digest = digest[: limits.digest_chars]
        notes.append("摘要已裁剪到 {} 字".format(limits.digest_chars))

    site = source_url.split("://", 1)[-1].rstrip("/")
    tail = "完整版见 {}".format(site)
    budget = max(limits.body_chars - len(tail) - 2, 1)

    body_text = "\n\n".join(blocks).strip()
    body_truncated = False
    if len(body_text) > budget:
        cut = body_text.rfind("\n\n", 0, budget)
        if cut <= 0:
            cut = budget
        body_text = body_text[:cut].rstrip()
        body_truncated = True
        notes.append("正文超过 {} 字，已截断".format(limits.body_chars))
    body_text = body_text + "\n\n" + tail

    article = ToutiaoArticle(
        content_id=post.slug,
        title=title,
        digest=digest,
        body=body_text,
        images=tuple(images),
        title_truncated=title_truncated,
        body_truncated=body_truncated,
        dropped_links=dropped_links,
        notes=tuple(notes),
    )
    return SliceResult(article=article)
