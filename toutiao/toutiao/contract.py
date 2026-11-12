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

import html
import re
from dataclasses import dataclass

from .capability import Limits
from .mdparse import SourcePost

__all__ = ["SliceResult", "ToutiaoArticle", "slice_post"]

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_IMAGE_LINE = re.compile(r"^!\[([^\]]*)\]\(([^)]*)\)$")
_IMAGE_INLINE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
_IMAGE_TITLE = re.compile(r"""\s+(?:"[^"]*"|'[^']*')\s*$""")
_LIST = re.compile(r"^(?:[-*+]|\d+\.)\s+(.*)$")
_LIST_EMPTY = re.compile(r"^(?:[-*+]|\d+\.)\s*$")
_MARKER = re.compile(r"^【图(\d+)】$")
_MARKER_IN_TEXT = re.compile(r"【图(\d+)】")
_HTML_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9]*(?:\s[^<>]*)?/?>")
_LINK = re.compile(r"(?<!!)\[([^\]]*)\]\([^)]*\)")
_LINK_REFERENCE = re.compile(r"(?<!!)\[([^\]]*)\]\[[^\]]*\]")
_LINK_DEFINITION = re.compile(r"^\[[^\]]+\]:\s*\S+")
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


def _image_path(raw: str) -> str:
    """The path inside ``![alt](path)`` -- without the optional title.

    Markdown allows a title after the path: ``![alt](https://x/a.png "图说")``.
    Keeping it would hand the downloader a string that is not a path at all,
    so the title is dropped and only the URL or file path survives.
    """
    path = raw.strip()
    return _IMAGE_TITLE.sub("", path).strip()


def _replace_inline_images(text: str, images: list[str]) -> str:
    """Swap every inline image for a ``【图N】`` placeholder.

    An image that sits inside a line of prose is an image too: it has to
    be uploaded like the ones that stand on their own line, so it goes
    into ``images`` and leaves a placeholder behind.  The numbering is
    shared with the standalone images and follows document order.
    """

    def replace(match):
        images.append(_image_path(match.group(2)))
        return "【图{}】".format(len(images))

    return _IMAGE_INLINE.sub(replace, text)


def _clean_html(text: str) -> str:
    """Take the HTML markup out, keep the text it wraps.

    A tag is markup; the words around it are content.  Entities are
    decoded as well -- but only for the blocks that actually carry a
    tag, because decoding everywhere would rewrite text that never was
    HTML in the first place.
    """
    if not _HTML_TAG.search(text):
        return text
    return html.unescape(_HTML_TAG.sub("", text))


def _drop_excess_markers(block: str, keep: int) -> str:
    """Remove the placeholders of the images that did not make the cut."""
    return _MARKER_IN_TEXT.sub(
        lambda m: "" if int(m.group(1)) > keep else m.group(0), block
    )


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
            text = _clean_html(_replace_inline_images(_join(paragraph), images)).strip()
            if text:
                blocks.append(text)
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

        if stripped.startswith("|") or stripped.startswith(">"):
            flush()
            continue

        if _LINK_DEFINITION.match(stripped):
            # A reference definition is a link definition, not prose --
            # keeping it would leak the URL it points at.
            flush()
            continue

        if _HTML_TAG.search(stripped) and not _HTML_TAG.sub("", stripped).strip():
            # A line that is nothing but HTML markup goes; a line that
            # mixes markup with text keeps its text -- the tags are taken
            # out when the block is finished.
            flush()
            continue

        heading = _HEADING.match(stripped)
        if heading:
            flush()
            if 2 <= len(heading.group(1)) <= 3:
                text = _clean_html(
                    _replace_inline_images(heading.group(2).strip(), images)
                ).strip()
                if text:
                    blocks.append("## " + text)
            continue

        image = _IMAGE_LINE.match(stripped)
        if image:
            flush()
            images.append(_image_path(image.group(2)))
            blocks.append("【图{}】".format(len(images)))
            continue

        item = _LIST.match(stripped)
        if item:
            flush()
            text = _clean_html(
                _replace_inline_images(item.group(1).strip(), images)
            ).strip()
            if text:
                blocks.append("- " + text)
            continue

        if _LIST_EMPTY.match(stripped):
            # A list marker with nothing behind it is not a paragraph --
            # "1. " would otherwise come out as a stray "1." block.
            flush()
            continue

        paragraph.append(stripped)

    flush()
    return blocks, images


def _strip_links(text: str) -> tuple[str, int]:
    """Turn every markdown link into plain text; count what was removed.

    Both shapes count: the inline one (``[text](url)``) and the
    reference one (``[text][1]``).  Both are links, so both are counted.
    """
    count = 0

    def replace(match):
        nonlocal count
        count += 1
        return match.group(1)

    text = _LINK.sub(replace, text)
    return _LINK_REFERENCE.sub(replace, text), count


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
        if not title.strip():
            # A title of nothing but separators cuts down to nothing --
            # publishing it would be a silent success with no title.
            return SliceResult(reason="标题裁剪后为空")
        notes.append("标题已裁剪到 {} 字（实际 {} 字）".format(limits.title_chars, len(title)))
    else:
        title = post.title
        title_truncated = False
        if not title.strip():
            return SliceResult(reason="标题为空")

    blocks, images = _scan(post.body)
    if not blocks:
        # Nothing survived the filter: a body of nothing but tables,
        # quotes, code fences or raw HTML has no Toutiao version.  Say so
        # instead of publishing an empty article.
        return SliceResult(reason="正文里没有可保留的内容")

    if len(images) > limits.max_body_images:
        dropped = len(images) - limits.max_body_images
        images = images[: limits.max_body_images]
        # The placeholders of the images that did not make the cut go too --
        # they sit inside a line of prose as often as they stand alone.
        blocks = [
            _drop_excess_markers(block, limits.max_body_images).strip()
            for block in blocks
        ]
        blocks = [block for block in blocks if block]
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
    # `title` is non-empty here -- the three branches above guarantee it --
    # so the digest never is.
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
