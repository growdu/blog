"""Tests for the summary under the title in the draft box.

The digest is what a reader sees before deciding to open the article.
Most digests in the box were the article's first paragraph -- a topic
sentence that says what the article is about but not what the author
thinks about it.

The corpus has better material, and the author wrote it: a title page
that says who the article is for, an opening statement that says what
kind of article this is, a conclusion that says what the author came
to.  These tests make sure the digest is dug out of those, in that
order, and that it falls back to the first paragraph when there is
nothing better.
"""
import pytest

from wechat.digest import article_digest, clip, make_digest, part_digest
from wechat.mdparse import parse

TITLE_PAGE = """| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 面向 PostgreSQL 内核开发 / DBA，把"一张表的元数据到底存在哪里"完整拆开。 | 2026-09-29 |
"""

OPENING = """> 这是一篇程序员视角的反思，AI 时代每个人都该想想自己该练什么。

正文一段。
"""

CONCLUSION = """## 一、背景

背景一段。

## 二、总结

真正的结论在这里：关键在于判断，而不是罗列事实。

## 三、后续

后续一段。
"""


# --- where the digest comes from ------------------------------------------


def test_the_digest_is_the_authors_own_description_when_there_is_one():
    """The title page says what the article is for -- better than the
    first paragraph ever does."""
    digest = article_digest(parse(TITLE_PAGE + "\n正文一段。\n"))

    assert digest.startswith("面向 PostgreSQL 内核开发")
    assert "初稿" not in digest


def test_the_digest_falls_back_to_the_opening_statement():
    digest = article_digest(parse(OPENING))

    assert digest == "这是一篇程序员视角的反思，AI 时代每个人都该想想自己该练什么。"


def test_the_digest_falls_back_to_the_conclusion():
    """The conclusion is where the author says what he thinks."""
    digest = article_digest(parse(CONCLUSION))

    assert digest == "真正的结论在这里：关键在于判断，而不是罗列事实。"


def test_the_digest_falls_back_to_the_first_paragraph():
    body = "## 第一节\n\n正文第一段，讲的是这张表的元数据到底存在哪里。\n"

    assert article_digest(parse(body)) == "正文第一段，讲的是这张表的元数据到底存在哪里。"


def test_the_digest_is_never_taken_from_a_citation():
    """A quote that only says where the text came from is a citation."""
    body = "> 来源: [https://example.com/x](https://example.com/x)\n\n正文一段。\n"

    assert article_digest(parse(body)) == "正文一段。"


# --- the digest has to be a digest ----------------------------------------


def test_the_digest_is_not_an_image_caption():
    """An image line is not a summary.

    The alt text of a picture -- "@AI产出图", "示意图" -- says nothing
    about the article, and it used to be what the digest was.
    """
    body = "![@AI产出图](images/ai.png)\n\n正文一段。\n"

    assert article_digest(parse(body)) == "正文一段。"


def test_a_short_first_paragraph_is_completed_by_the_next_one():
    """A digest of eight characters tells the reader nothing."""
    body = "运行大模型的框架。\n\n后面这一段把话说完，说清楚到底有哪些框架、各自适合什么场景。\n"

    digest = article_digest(parse(body))

    assert digest.startswith("运行大模型的框架。")
    assert "适合什么场景" in digest


def test_the_digest_is_at_most_the_limit():
    body = "很长的一段话。" * 100 + "\n"

    assert len(article_digest(parse(body))) <= 120


def test_the_digest_ends_on_a_sentence_boundary():
    body = "第一句话在这里。" + "填充" * 100 + "第二句话在这里。"

    digest = article_digest(parse(body))

    assert digest.endswith("。")
    assert len(digest) <= 120


def test_the_conclusion_is_not_taken_from_a_lead_in():
    """「当前市场已经进入：」 is the beginning of a sentence, not one."""
    body = "## 总结\n\n当前 AI 视频市场已经进入：\n\n后面才是内容。\n"

    assert article_digest(parse(body)) == "后面才是内容。"


def test_the_conclusion_digest_drops_the_raw_html():
    body = ("## 总结\n\n<font color=\"red\">集群元信息采用分布式方式保存，"
            "每个节点都会保存一份元数据。</font>\n")

    assert article_digest(parse(body)) == "集群元信息采用分布式方式保存，每个节点都会保存一份元数据。"


# --- the digest of one part ----------------------------------------------


def test_the_part_digest_describes_the_part():
    body = "## 二、缓冲池\n\n这是第二部分的开头段落，讲的是缓冲池。\n"

    assert part_digest(parse(body)) == "这是第二部分的开头段落，讲的是缓冲池。"


def test_the_part_digest_is_not_the_article_digest():
    """Every part says something different, or the draft box is a wall
    of identical summaries."""
    title_page = parse(TITLE_PAGE + "\n正文一段。\n")
    part = parse("## 二、缓冲池\n\n这是第二部分的开头段落。\n")

    assert part_digest(part) != article_digest(title_page)


def test_the_part_digest_is_empty_when_there_is_nothing_to_say():
    assert part_digest(parse("## 只有标题")) == ""


# --- the clipping ---------------------------------------------------------


def test_clip_keeps_a_short_text():
    assert clip("短句。", 120) == "短句。"


def test_clip_cuts_on_a_sentence_boundary():
    text = "第一句。" + "填充" * 100 + "第二句。"

    clipped = clip(text, 40)

    assert clipped.endswith("。")
    assert len(clipped) <= 40


def test_clip_ends_with_an_ellipsis_when_there_is_no_boundary():
    clipped = clip("没有句号的一段文字" * 20, 30)

    assert len(clipped) <= 30
    assert clipped.endswith("…")


# --- the markdown level digest -------------------------------------------


def test_the_markdown_digest_skips_an_image_line():
    """The markdown level digest is the fallback of the fallback, but it
    must not end up being an image caption."""
    body = "![](images/ai.png)\n\n正文一段。\n"

    assert make_digest(body) == "正文一段。"


def test_a_digest_is_not_empty_when_the_only_paragraph_is_a_lead_in():
    """Better a lead-in than nothing: an empty summary says nothing at
    all."""
    body = "## 第一节\n\n本文要回答 4 个问题：\n"

    assert article_digest(parse(body)) == "本文要回答 4 个问题："


def test_the_conclusion_must_be_a_statement():
    """A paragraph that ends in the middle of a word is a reference, not
    a conclusion."""
    body = ("## 第一节\n\n正文一段，讲的是逻辑复制。\n\n"
            "## 总结\n\n"
            "[1]: https://wiki.postgresql.org/wiki/Logical_replication_of_DDLs\n")

    assert article_digest(parse(body)) == "正文一段，讲的是逻辑复制。"


def test_the_conclusion_must_be_long_enough():
    """「选择 haproxy 来实现。」 is an answer, not a summary."""
    body = ("## 第一节\n\n正文一段，讲的是代理怎么做。\n\n"
            "## 总结\n\n选择 haproxy 来实现。\n")

    assert article_digest(parse(body)) == "正文一段，讲的是代理怎么做。"


def test_the_digest_does_not_use_a_purpose_that_only_says_how_it_was_written():
    """「结合 PostgreSQL 17 源码」 is a method, not a description.

    It is the right thing for the card at the top of the article -- it
    says which source the article was read against -- but as a summary
    it tells the reader nothing about the article.
    """
    body = ("| 编写人 | 编写内容 | 编写时间 |\n| --- | --- | --- |\n"
            "| growdu | 结合 PostgreSQL 17 源码 + Babelfish T-SQL 扩展 | 2026-09-29 |\n\n"
            "PostgreSQL 启动时申请的 shared_buffers 那一大段内存，其实只是冰山一角。\n")

    digest = article_digest(parse(body))

    assert digest.startswith("PostgreSQL 启动时申请的 shared_buffers")


def test_a_purpose_that_describes_the_article_is_used_even_with_the_method():
    body = ("| 编写人 | 编写内容 | 编写时间 |\n| --- | --- | --- |\n"
            "| growdu | 基于 PostgreSQL 17 源码梳理 schema、search_path、DDL AST 与系统目录归属 | 2026-09-29 |\n\n"
            "PostgreSQL 启动时申请的 shared_buffers 那一大段内存，其实只是冰山一角。\n")

    digest = article_digest(parse(body))

    assert digest.startswith("基于 PostgreSQL 17 源码梳理 schema")


def test_the_digest_does_not_use_an_opening_block_that_is_only_metadata():
    """「配套源码：…」 tells the reader where the code was read, not
    what the article says."""
    body = ("> 配套源码:~/cwork/postgresql/src/backend/replication/logical/snapbuild.c(PG 18 主干)\n\n"
            "逻辑解码的核心矛盾：我们要在 WAL 记录中还原当时的元组。\n")

    digest = article_digest(parse(body))

    assert digest.startswith("逻辑解码的核心矛盾")
