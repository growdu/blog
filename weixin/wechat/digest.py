"""The summary under the title in the draft box.

The digest is what a reader sees before deciding to open the article.
Most digests in the box were the article's first paragraph -- a topic
sentence that says what the article is about but not what the author
thinks about it.

The corpus has better material, and the author wrote it:

1. the title page -- what the article is for and who it is for,
2. the opening statement -- what kind of article this is,
3. the conclusion -- what the author came to think,
4. the first paragraph -- the fallback.

The order is a preference, not a rule: the first one that says
something usable wins.  Nothing is written here that the author did
not write.
"""

from __future__ import annotations

import re

from .brand import purpose_of, series_note_of
from .mdparse import Heading, Image, Paragraph, Text, inline_text

__all__ = ["DIGEST_LIMIT", "article_digest", "clip", "make_digest",
           "part_digest"]

# WeChat shows the digest under the title in the draft box and in the
# feed.  It is a maximum, not a target.
DIGEST_LIMIT = 120

_SENTENCE_MARKS = ("。", "！", "？", ". ", "! ", "? ")

# A digest shorter than this says nothing on its own, so the next
# paragraph is added to it.
_MIN_USEFUL = 30

# The shortest a conclusion may be and still be a conclusion.
_MIN_CONCLUSION = 20

# An opening block that only names the source the article was read
# against is metadata, not a statement about the article.  It belongs
# on the card; as a summary it says nothing.
_METADATA = re.compile(r"^(配套源码|源码版本|文档版本|适配版本|涉及文件|"
                       r"源码基线|基线|配套|涉及)")

# The headings whose section carries the author's conclusion.
_CONCLUSION = re.compile(r"(结论|总结|小结|结语|要点|写在最后|核心结论)")

# A purpose that only says how the article was researched -- 「结合
# PostgreSQL 17 源码」 -- is a method, not a description.  It belongs
# on the card at the top of the article; as a summary it says nothing
# about the article itself.
_METHOD_ONLY = re.compile(r"^(结合|基于|使用)[^，。；、]*$")

# The shortest a purpose may be and still describe an article.
_MIN_PURPOSE = 20

# A paragraph that ends with a colon is the beginning of a sentence --
# a lead-in, not a statement.
_LEAD_IN = ("：", ":")

_HTML_TAG = re.compile(r"<[^>]+>")

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

# A line that is nothing but a picture.  Its alt text is a caption,
# not a summary.
_IMAGE_LINE_RE = re.compile(r"^\s*!?\[[^\]]*\]\([^)]*\)\s*$")


def _normalise(text: str) -> str:
    """Collapse the whitespace of a piece of text."""
    return re.sub(r"\s+", " ", text).strip()


def _strip_inline(text: str) -> str:
    """Take the markup out of a piece of markdown text."""
    text = _IMAGE_RE.sub(lambda m: m.group(1), text)
    text = _LINK_RE.sub(lambda m: m.group(1), text)
    text = _INLINE_CODE_RE.sub(lambda m: m.group(1), text)
    text = _BOLD_RE.sub(lambda m: m.group(1), text)
    text = _ITALIC_RE.sub(lambda m: m.group(1), text)
    return text.strip()


def clip(text: str, limit: int = DIGEST_LIMIT) -> str:
    """Cut a text to a length, on a sentence boundary where there is one.

    The limit is a maximum, not a target: a digest that ends on a
    sentence boundary is always better than one cut mid-sentence, even
    when that leaves it noticeably shorter than the limit.  A text with
    no boundary at all is cut and marked with an ellipsis, because a
    digest that stops in the middle of a word looks broken.
    """
    text = _normalise(text)
    if len(text) <= limit:
        return text

    clipped = text[:limit]
    best = -1
    best_len = 0
    for mark in _SENTENCE_MARKS:
        index = clipped.rfind(mark)
        if index > best:
            best = index
            best_len = len(mark)
    if best >= 0:
        return clipped[:best + best_len].strip()
    return clipped[:limit - 1].rstrip() + "…"


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
        if _IMAGE_LINE_RE.match(line):
            # A picture is not a summary, and its caption is not one
            # either.
            continue
        paragraph.append(line.strip())

    if not paragraph:
        return ""

    text = re.sub(r"\s+", " ", _strip_inline(" ".join(paragraph))).strip()
    return clip(text, limit)


def _has_words(block) -> bool:
    """True when a paragraph carries words and not only pictures."""
    if not isinstance(block, Paragraph):
        return True
    for child in block.children:
        if isinstance(child, Image):
            continue
        if isinstance(child, Text) and not child.value.strip():
            continue
        return True
    return False


def _is_lead_in(text: str) -> bool:
    """True when a paragraph is the beginning of a sentence."""
    return text.rstrip().endswith(_LEAD_IN)


def _opening_paragraphs(blocks: list) -> list:
    """The paragraphs of the opening section.

    The section ends at the next heading of the same level, so the
    digest never mixes what the article says at the start with what
    it says at the end.
    """
    out = []
    for block in blocks:
        if isinstance(block, Heading):
            if block.level <= 2 and out:
                break
            continue
        if not isinstance(block, Paragraph) or not _has_words(block):
            continue
        text = _normalise(inline_text(block.children))
        if text:
            out.append(text)
    return out


def _paragraph_source(blocks: list) -> str:
    """The opening of the article: its first paragraph that says something.

    A paragraph that ends with a colon is the lead-in to something else,
    so it is only used when there is nothing else -- an empty summary
    says nothing at all.
    """
    texts = _opening_paragraphs(blocks)
    statements = [text for text in texts if not _is_lead_in(text)]
    if not statements:
        statements = texts
    if not statements:
        return ""
    if len(statements[0]) < _MIN_USEFUL and len(statements) > 1:
        return "{} {}".format(statements[0], statements[1])
    return statements[0]


def _is_statement(text: str) -> bool:
    """True when a paragraph ends in a sentence and not in the middle of
    a word."""
    return any(mark in text for mark in _SENTENCE_MARKS)


def _conclusion_source(blocks: list) -> str:
    """The paragraph in which the author says what he concluded.

    The conclusion is the part of an article that carries the author's
    judgement, so it is worth more than a topic sentence -- but only
    when it is a statement and not the lead-in to one, and when it is
    long enough to say something.
    """
    for index, block in enumerate(blocks):
        if not isinstance(block, Heading):
            continue
        if not _CONCLUSION.search(inline_text(block.children)):
            continue
        for follower in blocks[index + 1:]:
            if isinstance(follower, Heading):
                break
            if not isinstance(follower, Paragraph) or not _has_words(follower):
                continue
            text = _normalise(_HTML_TAG.sub("", inline_text(follower.children)))
            if len(text) < _MIN_CONCLUSION or _is_lead_in(text):
                continue
            if not _is_statement(text):
                continue
            return text
    return ""


def _purpose_source(blocks: list) -> str:
    """The description the author wrote for the article.

    The title page is the best material there is, but only when it
    describes the article: a purpose that merely names the source the
    article was read against is a method, and the opening of the
    article says more than that.
    """
    purpose = purpose_of(blocks)
    if len(purpose) < _MIN_PURPOSE or _METHOD_ONLY.match(purpose):
        return ""
    return purpose


def _series_source(blocks: list) -> str:
    """The statement the article opens with, if it opens with one."""
    note = series_note_of(blocks)
    if not note or _METADATA.match(note):
        return ""
    return note


def article_digest(blocks: list, limit: int = DIGEST_LIMIT) -> str:
    """The digest of a whole article.

    The material is taken from the article itself, in the order of how
    much it says: the title page first, then the opening statement,
    then the conclusion, then the first paragraph.
    """
    for source in (_purpose_source, _series_source, _conclusion_source,
                   _paragraph_source):
        text = source(blocks)
        if text:
            return clip(text, limit)
    return ""


def part_digest(blocks: list, limit: int = DIGEST_LIMIT) -> str:
    """The digest of one part: its own first paragraph, clipped.

    A part that starts in the middle of an article has to describe
    itself -- the whole-article digest would put the same text on
    every part, and the draft box would show a row of identical
    summaries.
    """
    text = _paragraph_source(blocks)
    return clip(text, limit) if text else ""
