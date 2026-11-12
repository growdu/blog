"""Tests for splitting an article that is too long for WeChat.

The split has to land where a reader can follow it, and the parts have
to be numbered and connected so that they read as one article rather
than as unrelated posts.
"""
import pytest

from wechat.mdparse import CodeBlock, Heading, Table, parse
from wechat.render import render
from wechat.split import (chinese_number, part_digest, part_title, split_blocks,
                          transition_head_html, transition_tail_html)

LIMIT = 20000


def _heading_text(block):
    """The text of a heading block."""
    return block.children[0].value


def _measure(blocks):
    """The size a group contributes: its body plus the links it brings."""
    result = render(blocks)
    return len(result.html)


def _paragraphs(count, text="正文一段。"):
    return "\n\n".join(text for _ in range(count))


def _big_section(paragraphs=400):
    """A section whose rendered length blows past the limit."""
    return _paragraphs(paragraphs)


# --- numbering ------------------------------------------------------------


@pytest.mark.parametrize("number,expected", [
    (1, "一"), (2, "二"), (3, "三"), (9, "九"), (10, "十"),
    (11, "十一"), (15, "十五"), (20, "二十"), (25, "二十五"), (99, "九十九"),
])
def test_chinese_number(number, expected):
    assert chinese_number(number) == expected


def test_chinese_number_falls_back_to_digits():
    assert chinese_number(0) == "零"
    assert chinese_number(120) == "120"


def test_part_title_uses_chinese_numerals():
    assert part_title("深入浅出", 1) == "深入浅出（一）"
    assert part_title("深入浅出", 12) == "深入浅出（十二）"


# --- the lines that connect the parts -------------------------------------


def test_an_unsplit_article_has_no_transition():
    assert transition_head_html("标题", 1, 1) == ""
    assert transition_tail_html("标题", 1, 1) == ""


def test_the_first_part_says_how_many_there_are():
    html = transition_head_html("标题", 1, 3)
    assert "共 3 部分" in html
    assert "第 1 部分" in html


def test_a_later_part_says_what_it_continues():
    html = transition_head_html("标题", 2, 3)
    assert "标题（一）" in html
    assert "第 2 部分" in html


def test_a_middle_part_points_at_the_next_one():
    html = transition_tail_html("标题", 1, 3)
    assert "未完待续" in html
    assert "标题（二）" in html


def test_the_last_part_says_the_article_is_over():
    html = transition_tail_html("标题", 3, 3)
    assert "全文完" in html
    assert "共 3 部分" in html


def test_the_transitions_carry_no_class_attribute():
    """WeChat drops ``class`` attributes, so the styles are inline."""
    for html in (transition_head_html("标题", 2, 3), transition_tail_html("标题", 1, 3)):
        assert "class=" not in html
        assert 'style="' in html


# --- where the split happens ----------------------------------------------


def test_a_short_article_is_one_part():
    blocks = parse("## 小节\n\n正文。")
    assert split_blocks(blocks, LIMIT, _measure) == [blocks]


def test_the_split_lands_on_a_heading():
    markdown = "## 第一节\n\n{}\n\n## 第二节\n\n{}\n\n## 第三节\n\n{}".format(
        _big_section(), _big_section(), _big_section())
    parts = split_blocks(parse(markdown), LIMIT, _measure)
    assert len(parts) > 1
    # Every part opens with the section it belongs to: a part that
    # begins in the middle of a section still says where it is.
    for part in parts:
        assert part[0].level == 2


def test_the_parts_keep_the_reading_order():
    markdown = "## 第一节\n\n{}\n\n## 第二节\n\n{}".format(
        _big_section(), _big_section())
    parts = split_blocks(parse(markdown), LIMIT, _measure)
    headings = [_heading_text(part[0]) for part in parts]
    # A section that was cut open is repeated in the part that carries
    # on, but the order never goes backwards.
    distinct = []
    for heading in headings:
        if not distinct or distinct[-1] != heading:
            distinct.append(heading)
    assert distinct == ["第一节", "第二节"]


def test_a_section_that_is_too_big_is_cut_finer():
    """One section that does not fit is cut at its own sub-headings."""
    markdown = "## 大节\n\n### 小节一\n\n{}\n\n### 小节二\n\n{}".format(
        _big_section(), _big_section())
    parts = split_blocks(parse(markdown), LIMIT, _measure)
    assert len(parts) > 1
    # The parent heading is repeated; the sub-headings stay in order.
    for part in parts:
        assert part[0].level == 2
        assert _heading_text(part[0]) == "大节"
    sub_headings = [_heading_text(block) for part in parts for block in part
                    if isinstance(block, Heading) and block.level == 3]
    assert sub_headings == ["小节一", "小节一", "小节二", "小节二"]


def test_a_block_that_does_not_fit_is_cut_at_the_paragraphs():
    markdown = "## 大节\n\n{}".format(_big_section())
    parts = split_blocks(parse(markdown), LIMIT, _measure)
    assert len(parts) == 2
    for part in parts:
        assert _measure(part) <= LIMIT


def test_a_big_table_is_cut_between_its_rows():
    rows = "\n".join("| a | b |\n| --- | --- |\n| {} | x |".format(index)
                     for index in range(1))
    table = ("| 列一 | 列二 |\n| --- | --- |\n"
             + "\n".join("| 值{} | 内容{} |".format(i, i) for i in range(400)))
    blocks = parse("## 表格\n\n" + table)
    parts = split_blocks(blocks, LIMIT, _measure)
    assert len(parts) > 1
    for part in parts:
        assert _measure(part) <= LIMIT


def test_a_big_code_block_is_cut_between_its_lines():
    code = "\n".join("行 {}".format(index) for index in range(2000))
    blocks = parse("## 代码\n\n```python\n" + code + "\n```")
    parts = split_blocks(blocks, LIMIT, _measure)
    assert len(parts) > 1
    for part in parts:
        assert _measure(part) <= LIMIT


def test_every_part_fits_under_the_limit():
    markdown = "## 一\n\n{}\n\n## 二\n\n{}\n\n## 三\n\n{}".format(
        _big_section(), _big_section(), _big_section())
    parts = split_blocks(parse(markdown), LIMIT, _measure)
    for part in parts:
        assert _measure(part) <= LIMIT


def test_the_split_keeps_every_block():
    """Nothing may be dropped on the way to the parts.

    The only blocks that are added are the repeated section headings,
    and they are added on purpose: a part that continues a section
    has to say which one.
    """
    from wechat.mdparse import Heading

    markdown = "## 一\n\n{}\n\n## 二\n\n{}".format(_big_section(), _big_section())
    blocks = parse(markdown)
    parts = split_blocks(blocks, LIMIT, _measure)

    content = [block for part in parts for block in part
               if not isinstance(block, Heading)]
    original = [block for block in blocks if not isinstance(block, Heading)]
    assert len(content) == len(original)
    assert content == original


# --- the digest of a part --------------------------------------------------


def test_the_digest_is_the_first_paragraph():
    blocks = parse("## 标题\n\n第一段说明。\n\n第二段。")
    assert part_digest(blocks) == "第一段说明。"


def test_the_digest_skips_a_part_that_starts_with_a_heading():
    blocks = parse("## 标题\n\n正文从这里开始。")
    assert part_digest(blocks) == "正文从这里开始。"


def test_the_digest_is_empty_without_a_paragraph():
    assert part_digest(parse("## 只有标题")) == ""


def test_the_digest_is_capped():
    blocks = parse("正文。" * 200)
    assert len(part_digest(blocks)) <= 120


def test_a_cut_table_keeps_one_header():
    """A table cut between its rows must not repeat the header per row."""
    table = ("| 列一 | 列二 |\n| --- | --- |\n"
             + "\n".join("| 值{} | 内容{} |".format(i, i) for i in range(400)))
    parts = split_blocks(parse("## 表格\n\n" + table), LIMIT, _measure)
    assert len(parts) > 1
    for part in parts:
        tables = [block for block in part if isinstance(block, Table)]
        assert len(tables) == 1
        assert len(tables[0].rows) > 1


def test_a_cut_code_block_stays_one_block():
    """A code block cut between its lines must not break into pieces."""
    code = "\n".join("行 {}".format(index) for index in range(2000))
    parts = split_blocks(parse("## 代码\n\n```python\n" + code + "\n```"), LIMIT, _measure)
    assert len(parts) > 1
    for part in parts:
        blocks = [block for block in part if isinstance(block, CodeBlock)]
        assert len(blocks) == 1
        assert len(blocks[0].code.split("\n")) > 1
