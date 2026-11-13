"""平台字数口径：实测出来的探针就是用例。

2026-11-13 在头条号后台实测。每一个探针都是「往正文末尾追加一段，
看编辑器底部的『共 N 字』涨了多少」——涨的值就是这一段的贡献。

这些数字不是猜的，是从真实编辑器里读出来的；写成用例以后，
哪天平台改了口径，本文件立刻红，而不是等到发出去才发现字数对不上。
"""

import pytest

from toutiao.wordcount import platform_word_count


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("测试", 2),
        ("abcd", 2),
        ("12345678", 4),
        (" ", 0),
        ("。", 1),
    ],
    ids=["two_chinese", "four_latin", "eight_digits", "one_space", "one_punctuation"],
)
def test_the_measured_probes(text, expected):
    """往正文末尾追加一段，计数器涨多少。"""
    assert platform_word_count(text) == expected


def test_a_picture_placeholder_costs_four_words():
    """``【图1】`` 是三个非 ASCII 字加一个 ASCII 数字。

    ASCII 单独一个也折算一个字（不是半个）——所以这一小段平台计 4 个字。
    这条是「向上取整」那一半的证据：少了它，这段会算成 3。
    """
    assert platform_word_count("【图1】") == 4
    assert platform_word_count("【图1】\n\n普通段落甲") == 9


def test_the_mixed_body_matches_the_editors_counter():
    """一整篇短正文，实测计数器显示 20。"""
    body = "标题甲\n\n列表项一\n\n列表项二\n\n普通段落甲\n\n【图1】"
    assert platform_word_count(body) == 20


def test_whitespace_is_not_counted():
    """空白一律不计：换行、空格、制表符都不算字。"""
    assert platform_word_count("  \n\t ") == 0
    assert platform_word_count("甲 乙\n丙") == platform_word_count("甲乙丙")


def test_an_empty_text_is_zero_words():
    assert platform_word_count("") == 0


def test_odd_ascii_rounds_up():
    """ASCII 字符两个折一个，多出来的那半个也算一个。"""
    assert platform_word_count("a") == 1
    assert platform_word_count("ab") == 1
    assert platform_word_count("abc") == 2
    assert platform_word_count("abcd") == 2


def test_a_pure_chinese_paragraph_counts_one_word_per_character():
    """纯汉字：一字一词。平台单段上限就是按这个口径数的。"""
    assert platform_word_count("测" * 200) == 200
    assert platform_word_count("测" * 201) == 201
