"""Tests for shortening a title and drawing a cover card.

The title is the first thing a reader sees, so it is cut at a boundary
that keeps the topic rather than at a fixed offset.  The cover card is
what makes a part of an article tellable from the next one in the
draft box.
"""
import pytest

from wechat.cover import cover_card, cover_text
from wechat.titles import (SUFFIX_RESERVE, TITLE_LIMIT, effective_title,
                           shorten, topic)


# --- shortening ------------------------------------------------------------


def test_a_title_that_fits_is_left_alone():
    assert shorten("很短", 20) == "很短"
    assert shorten("刚好二十个字符的标题啊哦", 20) == "刚好二十个字符的标题啊哦"


def test_the_title_is_cut_at_the_colon():
    """The colon separates the topic from the elaboration."""
    title = "PostgreSQL 万能论：为什么一家公司可以用它替代 Kafka"
    assert shorten(title, 20) == "PostgreSQL 万能论"


def test_the_subtitle_is_what_goes():
    """The part that says what the article is about is what stays."""
    title = "PostgreSQL 万能论：为什么一家公司可以用它替代 Kafka"
    assert "为什么" not in shorten(title, 20)


def test_a_title_without_a_colon_keeps_as_much_as_fits():
    """Without a topic boundary, the cut keeps as much as it can."""
    title = "PostgreSQL 逻辑复制streaming 与 spill 从 reorderbuffer 说起"
    assert shorten(title, 24) == "PostgreSQL 逻辑复制streaming"


def test_a_cut_leaves_no_dangling_punctuation():
    title = "主标题在这里：副标题也在这里"
    assert not shorten(title, 8).endswith(("：", "，", "、", " "))
    assert shorten(title, 8) == "主标题在这里"


def test_a_cut_does_not_leave_an_open_bracket():
    title = "PostgreSQL（详解）：从 WAL 到数据完整性"
    assert shorten(title, 12) == "PostgreSQL"


def test_a_title_without_any_boundary_is_cut_in_the_middle():
    """And it says so: a truncated title that admits it is honest."""
    title = "abcdefghijklmnopqrstuvwxyz0123456789"
    out = shorten(title, 10)
    assert out.endswith("…")
    assert len(out) == 10


def test_a_cut_that_leaves_nothing_is_not_a_title():
    """A head of two characters is not a title, so the next boundary wins."""
    title = "说：这是一个很长的副标题部分"
    assert shorten(title, 12) != "说"
    assert len(shorten(title, 12)) <= 12


def test_shortening_never_exceeds_the_limit():
    for title in ("短", "标题：副标题", "一" * 200, "标题：{}".format("长" * 100)):
        for limit in (5, 20, 61, 64):
            assert len(shorten(title, limit)) <= limit


def test_the_effective_title_leaves_room_for_the_part_suffix():
    """A split article's parts are titled 「标题（一）」."""
    title = "一个很长的主标题：" + "副标题" * 30
    effective = effective_title(title)
    assert len(effective) + SUFFIX_RESERVE <= TITLE_LIMIT


def test_the_effective_title_of_a_normal_article_is_untouched():
    assert effective_title("很短") == "很短"


def test_the_topic_is_what_goes_on_the_cover():
    title = "PostgreSQL 万能论：为什么一家公司可以用它替代 Kafka"
    assert topic(title) == "PostgreSQL 万能论"


def test_the_topic_of_a_title_without_a_boundary_is_its_head():
    assert topic("PostgreSQL 逻辑复制streaming 与 spill") == "PostgreSQL 逻辑复制str"


# --- the cover card --------------------------------------------------------


def test_the_cover_carries_the_topic_and_the_part_number(tmp_path):
    text = cover_text("PostgreSQL 万能论：为什么", 2, 4)
    assert "PostgreSQL 万能论" in text
    assert "（二）" in text


def test_a_card_is_drawn_and_kept(tmp_path):
    path = cover_card("db/one", "标题：副标题", "数据库内核", tmp_path)
    assert path.is_file()
    assert path.suffix == ".png"
    # The same inputs give the same file: the card is drawn once.
    again = cover_card("db/one", "标题：副标题", "数据库内核", tmp_path)
    assert again == path


def test_different_articles_get_different_cards(tmp_path):
    one = cover_card("db/one", "标题：副标题", "数据库内核", tmp_path)
    two = cover_card("db/two", "标题：副标题", "数据库内核", tmp_path)
    assert one != two
    assert one.read_bytes() != two.read_bytes()


def test_the_card_has_the_ratio_wechat_shows(tmp_path):
    from PIL import Image

    path = cover_card("db/one", "标题：副标题", "数据库内核", tmp_path)
    with Image.open(path) as image:
        assert image.size == (900, 383)
        assert abs(image.size[0] / image.size[1] - 2.35) < 0.01


def test_a_whole_article_has_no_part_number():
    assert "（" not in cover_text("标题：副标题", 1, 1)


def test_a_part_of_a_split_article_carries_its_number():
    assert "（三）" in cover_text("标题：副标题", 3, 12)
