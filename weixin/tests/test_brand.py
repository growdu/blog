"""Tests for the parts of a draft that say who wrote it.

A draft is read in a feed: cover, title, digest, body.  What the
platform cannot show is the thing that makes a reader remember the
writer -- what the article is about, who it is for, and which version
of the source it was read against.

That information is already written down in the corpus: most deep dive
articles open with a title page the author wrote for exactly that
purpose.  These tests make sure it is found, lifted out of the body
and turned into a card -- without a single word being invented.
"""
import pytest

from wechat.brand import (SIGNATURE_TEXT, byline_html, purpose_of,
                          series_note_of, signature_html, strip_title_page,
                          title_page_of)
from wechat.mdparse import Table, inline_text, parse

TITLE_PAGE = """| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 初稿，面向 PostgreSQL 内核开发 / DBA / 内核爱好者，把"一张表的元数据到底存在哪里"完整拆开。配套源码版本：PostgreSQL 18 dev。 | 2026-09-29 |
"""

SERIES = """> 本文是「PostgreSQL 源码系列」元数据与缓存篇。同系列前文：
>
> - [前文一](/2026/09/02/database/x/)
"""

BODY = """正文第一段，讲的是这张表的元数据到底存在哪里。

第二段继续讲。

| a | b |
| --- | --- |
| 1 | 2 |
"""


def _blocks(text):
    return parse(text)


# --- finding the title page ----------------------------------------------


def test_the_purpose_column_is_the_authors_own_description():
    """The 「编写内容」 cell says what the article is about."""
    purpose = purpose_of(_blocks(TITLE_PAGE))

    assert purpose == ("面向 PostgreSQL 内核开发 / DBA / 内核爱好者，"
                       "把\"一张表的元数据到底存在哪里\"完整拆开。"
                       "配套源码版本：PostgreSQL 18 dev。")


def test_the_draft_mark_is_not_part_of_the_description():
    """「初稿」 is a status of the writing, not of the article.

    A card that opens with 「初稿，」 under the author's name reads as
    an unfinished draft, so the marker is taken off -- and nothing
    else is.
    """
    purpose = purpose_of(_blocks(TITLE_PAGE))

    assert not purpose.startswith("初稿")
    assert "面向 PostgreSQL" in purpose


def test_a_description_that_is_only_the_draft_mark_is_no_description():
    """「初稿」 on its own says nothing, so it is not a title page."""
    empty = """| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 初稿 | 2026-09-29 |
"""

    assert purpose_of(_blocks(empty)) == ""


def test_the_author_and_the_date_are_read():
    byline = title_page_of(_blocks(TITLE_PAGE))

    assert byline.author == "growdu"
    assert byline.date == "2026-09-29"


def test_the_series_note_comes_from_the_leading_quote():
    note = series_note_of(_blocks(SERIES))

    assert note.startswith("本文是「PostgreSQL 源码系列」元数据与缓存篇。")


def test_a_citation_is_not_a_series_note():
    """A quote that only says where the text came from is a citation."""
    citation = """> 来源: [https://example.com/origin](https://example.com/origin)
"""

    assert series_note_of(_blocks(citation)) == ""


def test_a_disclaimer_is_not_a_series_note():
    disclaimer = """> ⚠️ 免责声明:该篇文章内容仅用于技术交流和学习,切勿用作其他用途。
"""

    assert series_note_of(_blocks(disclaimer)) == ""


def test_an_article_without_a_title_page_has_none():
    byline = title_page_of(_blocks(BODY))

    assert byline.purpose == ""
    assert byline.series == ""


def test_a_table_that_is_not_a_title_page_is_left_alone():
    """Not every table at the top is the author's title page."""
    assert purpose_of(_blocks(BODY)) == ""


# --- lifting it out of the body ------------------------------------------


def test_the_title_page_table_is_taken_out_of_the_body():
    """A three column table is not a title page; a card is."""
    blocks = _blocks(TITLE_PAGE + "\n" + BODY)

    kept = strip_title_page(blocks)

    headers = [inline_text(table.header) for table in kept
               if isinstance(table, Table)]
    assert not any("编写内容" in header for header in headers)
    assert len(kept) == len(blocks) - 1


def test_the_rest_of_the_body_is_kept():
    blocks = _blocks(TITLE_PAGE + "\n" + BODY)

    kept = strip_title_page(blocks)

    assert kept[0].children[0].value.startswith("正文第一段")


def test_an_article_without_a_title_page_keeps_all_of_its_blocks():
    blocks = _blocks(BODY)

    assert strip_title_page(blocks) == blocks


# --- the card -------------------------------------------------------------


def test_the_card_shows_the_author_the_date_and_the_description():
    card = byline_html(title_page_of(_blocks(TITLE_PAGE)))

    assert "growdu" in card
    assert "2026-09-29" in card
    assert "面向 PostgreSQL 内核开发" in card


def test_the_card_is_empty_without_a_title_page():
    """A card with nothing in it is worse than no card."""
    assert byline_html(title_page_of(_blocks(BODY))) == ""


def test_a_long_description_is_cut_for_the_card():
    """The description is the author's, but a card that runs to five
    lines is a paragraph again."""
    card = byline_html(title_page_of(_blocks(
        "| 编写人 | 编写内容 | 编写时间 |\n| --- | --- | --- |\n"
        "| growdu | {} | 2026-09-29 |\n".format("拆" * 400))))

    assert card.count("拆") <= 180
    assert card.count("拆") > 100


def test_the_card_carries_no_class_attribute():
    """WeChat drops the class attribute, so the styles have to be inline."""
    card = byline_html(title_page_of(_blocks(TITLE_PAGE)))

    assert "class=" not in card


def test_the_card_escapes_the_html_of_the_description():
    card = byline_html(title_page_of(_blocks(
        "| 编写人 | 编写内容 | 编写时间 |\n| --- | --- | --- |\n"
        "| growdu | <script>alert(1)</script> 拆开 | 2026-09-29 |\n")))

    assert "<script>" not in card
    assert "&lt;script&gt;" in card


# --- the signature --------------------------------------------------------


def test_the_signature_names_the_author():
    signature = signature_html()

    assert "growdu" in signature
    assert SIGNATURE_TEXT.format(author="growdu") in signature


def test_the_signature_uses_the_author_it_is_given():
    signature = signature_html("growdu｜内核开发者")

    assert "growdu｜内核开发者" in signature


def test_the_signature_carries_no_class_attribute():
    assert "class=" not in signature_html()


def test_the_signature_points_at_the_read_more_link():
    """The full article lives on the site; the signature says where."""
    assert "阅读原文" in SIGNATURE_TEXT
