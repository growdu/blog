"""The parts of a draft that say who wrote it.

A WeChat draft is read in a feed: cover, title, digest, then the body.
The platform already shows the account name and the byline, so what it
cannot show is the thing that makes a reader remember the writer -- what
the article is about, who it is for, and which version of the source it
was read against.

That information is already written down in this corpus.  Most deep
dive articles open with a block the author wrote for exactly that
purpose::

    | 编写人 | 编写内容 | 编写时间 |
    | growdu | 初稿，面向 PostgreSQL 内核开发 / DBA / 内核爱好者，把"一张表的
      元数据到底存在哪里..."完整拆开。配套源码版本：PostgreSQL 18 dev。 | 2026-09-29 |

    > 本文是「PostgreSQL 源码系列」元数据与缓存篇。同系列前文：...

A block like that is a title page, not a table.  This module finds
those blocks and turns them into the two things the drafts are missing:
a card at the top of the article, and a signature at the bottom.

Nothing here invents copy.  The wording is the author's own, dug out
of the article -- which is the point: a personal brand that is
extracted from the writing is consistent with the writing, and a
personal brand that is written for the author is not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .mdparse import Paragraph, Quote, Table, block_text, inline_text

__all__ = ["Byline", "SIGNATURE_TEXT", "byline_html", "purpose_of",
           "series_note_of", "signature_html", "strip_title_page",
           "title_page_of"]

# The header cells a "purpose table" may carry.  The author has used
# more than one name for the same thing.
_PURPOSE_HEADERS = ("编写内容", "内容简介", "本文目的", "文章目的", "内容说明")
_AUTHOR_HEADERS = ("编写人", "作者", "作者名")
_DATE_HEADERS = ("编写时间", "撰写时间", "日期", "更新时间")

# A title page sits at the very top of the article.  Looking further
# down would risk lifting a table out of the middle of the text.
_TITLE_PAGE_DEPTH = 3

# A quote block that only says where the text came from is not a title
# page, it is a citation.  A disclaimer is not one either.
_CITATION = re.compile(r"^(来源|source|出处|译自|原文链接|原文|转自|via)\b", re.I)
_DISCLAIMER = re.compile(r"^(⚠|免责声明|免责聲明)")

# 「初稿」 is a status of the writing, not part of the description.
_DRAFT_MARK = re.compile(r"^初稿\s*[，。、,.\s+]*")

# The shortest a self description may be and still be one.
_MIN_NOTE = 12

# The longest a card may get.  The description is the author's, but a
# card that runs to five lines is a paragraph again.
_CARD_LIMIT = 180

_SENTENCE_END = "。！？!?；;"

# The signature that closes every part.  It says who wrote it and where
# the complete version is; the platform's own byline says only the name.
SIGNATURE_TEXT = ("本文作者：{author} ｜ 完整版、勘误与后续更新见文末「阅读原文」")

_BYLINE_STYLE = (
    "margin:0 0 18px;padding:12px 14px;border-left:3px solid #3d7ea6;"
    "background:#f6f8fa;")
_BYLINE_NAME_STYLE = (
    "margin:0 0 4px;font-size:12px;color:#8a94a0;letter-spacing:.5px;")
_BYLINE_TEXT_STYLE = (
    "margin:0;font-size:13px;color:#444;line-height:1.75;")
_SIGNATURE_STYLE = (
    "margin:22px 0 0;padding-top:12px;border-top:1px solid #e5e5e5;"
    "font-size:13px;color:#8a94a0;line-height:1.8;")


@dataclass(frozen=True)
class Byline:
    """What the author wrote about the article, in his own words."""

    author: str = ""
    purpose: str = ""
    date: str = ""
    series: str = ""


def _escape(text: str) -> str:
    """Escape the three characters that would otherwise be markup."""
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _normalise(text: str) -> str:
    """Collapse the whitespace of a piece of text."""
    return re.sub(r"\s+", " ", text).strip()


def _first_sentence(text: str, limit: int = 160) -> str:
    """The first sentence of a piece of text.

    A sentence boundary is preferred, but a text that has none is still
    usable -- it is only cut when it is much too long for the place it
    goes.
    """
    text = _normalise(text)
    for index, char in enumerate(text):
        if char in _SENTENCE_END:
            return text[:index + 1]
    if len(text) > limit:
        return text[:limit].rstrip() + "…"
    return text


def _clip(text: str, limit: int) -> str:
    """Cut a text to a length, on a sentence boundary where there is one."""
    text = _normalise(text)
    if len(text) <= limit:
        return text
    clipped = text[:limit]
    best = -1
    for mark in _SENTENCE_END:
        index = clipped.rfind(mark)
        if index > best:
            best = index
    if best >= 0:
        return clipped[:best + 1].strip()
    return clipped.rstrip() + "…"


def _cell_text(cell) -> str:
    """The plain text of a table cell."""
    return _normalise(inline_text(cell))


def _title_page_table(blocks: list):
    """The table that is the author's title page, if there is one.

    Returns ``(index, table)``.  The table has to be one of the first
    blocks of the article: a table in the middle of the text is part of
    the text, even if its columns happen to look familiar.
    """
    for index, block in enumerate(blocks[:_TITLE_PAGE_DEPTH]):
        if not isinstance(block, Table):
            continue
        header = [_cell_text(cell) for cell in block.header]
        if any(name in _PURPOSE_HEADERS for name in header):
            return index, block
    return None, None


def _column_of(header: list, names: tuple):
    """The index of the first column with one of these names."""
    for column, name in enumerate(header):
        if name in names:
            return column
    return None


def _row_text(table: Table, column):
    """The text of one column of the first data row of a table."""
    if column is None or not table.rows:
        return ""
    row = table.rows[0]
    if column >= len(row):
        return ""
    return _cell_text(row[column])


def purpose_of(blocks: list) -> str:
    """The author's own description of what the article is about.

    It lives in a table at the top of the article, in a column headed
    「编写内容」 or one of its relatives.  The column is found by its
    heading, not by its position, so the table may change shape.
    """
    _, table = _title_page_table(blocks)
    if table is None:
        return ""
    header = [_cell_text(cell) for cell in table.header]
    purpose = _row_text(table, _column_of(header, _PURPOSE_HEADERS))
    purpose = _DRAFT_MARK.sub("", purpose).strip()
    return purpose if len(purpose) >= _MIN_NOTE else ""


def _leading_quote(blocks: list):
    """The quote block the article opens with, if it opens with one.

    A quote after the first paragraph is a quotation inside the text,
    not the article's opening statement.
    """
    for block in blocks:
        if isinstance(block, Quote):
            return block
        if isinstance(block, Table):
            continue
        if isinstance(block, Paragraph):
            return None
        return None
    return None


def series_note_of(blocks: list) -> str:
    """The note the article opens with, if it opens with one.

    Most deep dive articles start with a block in which the author says
    which series this is and which version of the source it was read
    against.  A block that only cites a source, or that only carries a
    disclaimer, is not that.
    """
    quote = _leading_quote(blocks)
    if quote is None:
        return ""
    text = _normalise(block_text(quote))
    if not text or _CITATION.match(text) or _DISCLAIMER.match(text):
        return ""
    if len(text) < _MIN_NOTE:
        return ""
    return _first_sentence(text)


def title_page_of(blocks: list) -> Byline:
    """The title page of an article, in the author's own words."""
    _, table = _title_page_table(blocks)
    author = ""
    date = ""
    if table is not None:
        header = [_cell_text(cell) for cell in table.header]
        author = _row_text(table, _column_of(header, _AUTHOR_HEADERS))
        date = _row_text(table, _column_of(header, _DATE_HEADERS))
    return Byline(
        author=author,
        purpose=purpose_of(blocks),
        date=date,
        series=series_note_of(blocks),
    )


def strip_title_page(blocks: list) -> list:
    """The blocks of the article without its title-page table.

    A three column table whose middle column is a paragraph reads as
    a table in the draft box.  The same words as a card at the top of
    the article read as a title page, which is what they are.
    """
    index, _ = _title_page_table(blocks)
    if index is None:
        return list(blocks)
    return list(blocks[:index]) + list(blocks[index + 1:])


def byline_html(byline: Byline) -> str:
    """The title page of an article, as HTML.

    Empty when the article does not carry one: a card with nothing in
    it is worse than no card.
    """
    text = byline.purpose or byline.series
    if not text:
        return ""
    name = byline.author or "growdu"
    if byline.date:
        name = "{} ｜ {}".format(name, byline.date)
    return (
        '<section style="{box}">'
        '<p style="{name}">{name_text}</p>'
        '<p style="{text}">{body}</p>'
        "</section>"
    ).format(
        box=_BYLINE_STYLE, name=_BYLINE_NAME_STYLE, text=_BYLINE_TEXT_STYLE,
        name_text=_escape(name), body=_escape(_clip(text, _CARD_LIMIT)),
    )


def signature_html(author: str = "growdu") -> str:
    """The line that closes every part."""
    return '<p style="{style}">{text}</p>'.format(
        style=_SIGNATURE_STYLE,
        text=_escape(SIGNATURE_TEXT.format(author=author)))
