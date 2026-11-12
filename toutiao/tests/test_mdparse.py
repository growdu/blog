import typing
from pathlib import Path

import pytest

from toutiao.mdparse import (
    SourcePost,
    discover,
    discover_unsupported,
    load_post,
    parse_front_matter,
)


def test_front_matter_scalars_and_lists():
    text = (
        "---\n"
        'title: "标题"\n'
        "date: 2026-09-04 11:39:04\n"
        "categories:\n"
        "  - 数据库\n"
        "  - 源码\n"
        "---\n"
        "\n正文第一段。\n"
    )
    fields, body = parse_front_matter(text)
    assert fields["title"] == "标题"
    assert fields["date"] == "2026-09-04 11:39:04"
    assert fields["categories"] == ["数据库", "源码"]
    assert body.strip() == "正文第一段。"


def test_escaped_quotes_are_unescaped():
    """``tools/sync-hexo.py`` escapes quotes inside a title; we must undo it.

    ``yaml_escape`` writes ``\\"`` for a quote inside a double-quoted title,
    so a post whose title contains ``"`` reaches us as ``\\"``.  Hexo reads
    that back with a real YAML parser, which turns ``\\"`` into ``"``; if we
    keep the backslash the published title shows ``\\"`` to the reader.
    """
    fields, _ = parse_front_matter(
        '---\ntitle: "为什么\\"获得就释放\\"的机制"\n---\n\nx\n'
    )
    assert fields["title"] == '为什么"获得就释放"的机制'


def test_escaped_backslash_is_unescaped():
    """``yaml_escape`` doubles a backslash, so ``\\`` must become ``\\``."""
    fields, _ = parse_front_matter('---\ntitle: "C:\\\\路径"\n---\n\nx\n')
    assert fields["title"] == "C:\\路径"


def test_unknown_keys_are_kept():
    fields, _ = parse_front_matter(
        "---\nfoo: bar\nplatforms:\n  - wechat\n---\n\nx\n"
    )
    assert fields["foo"] == "bar"
    assert fields["platforms"] == ["wechat"]


def test_text_without_front_matter_is_all_body():
    fields, body = parse_front_matter("正文\n")
    assert fields == {}
    assert body == "正文\n"


def test_front_matter_closing_without_trailing_newline():
    """文件以结束 ``---`` 收尾（末尾没有换行）也是闭合的。

    ``---`` 独占一行就够了，文件可以在此结束。之前用正则匹配
    ``\\n---\\n``，末尾没换行的文件会被当成「未闭合」而误报。
    """
    fields, body = parse_front_matter("---\ntitle: x\n---")
    assert fields["title"] == "x"
    assert body == ""


def test_front_matter_closing_may_carry_trailing_whitespace():
    """结束 ``---`` 行尾可以有空白（YAML 允许），这也还是闭合的。"""
    fields, body = parse_front_matter("---\ntitle: x\n--- \n")
    assert fields["title"] == "x"
    assert body == ""


def test_unterminated_front_matter_raises():
    """A file that starts with ``---`` but never closes it is broken.

    Silently treating it as "no front matter" would publish the raw
    ``---`` and ``title:`` lines as body text and fall back to the file
    name for the title -- a broken file would go out as a good one.
    """
    with pytest.raises(ValueError) as excinfo:
        parse_front_matter("---\ntitle: 坏文件\n\n正文还在\n")
    message = str(excinfo.value)
    assert "闭合" in message
    # 消息说的是「找不到配对的结束 '---'」，只有真的没找到时才成立。
    assert "没有找到配对的结束" in message


def test_document_without_leading_dashes_is_not_an_error():
    """A normal document that merely contains ``---`` in its body is fine."""
    fields, body = parse_front_matter("正文\n\n---\n\n更多正文\n")
    assert fields == {}
    assert body == "正文\n\n---\n\n更多正文\n"


def test_empty_front_matter_raises():
    """``---\\n---\\n`` has no content for the field parser to read."""
    with pytest.raises(ValueError) as excinfo:
        parse_front_matter("---\n---\n\n正文\n")
    # 与「未闭合」是两种坏法，消息要能分开。
    assert "为空" in str(excinfo.value)


def test_load_post_derives_slug_and_title(tmp_path):
    posts = tmp_path / "source" / "_posts"
    (posts / "db").mkdir(parents=True)
    path = posts / "db" / "demo.md"
    path.write_text(
        "---\ntitle: 演示\ndate: 2026-01-01\n---\n\n内容\n", encoding="utf-8"
    )
    post = load_post(path, posts)
    assert post.slug == "db/demo"
    assert post.title == "演示"
    assert post.date == "2026-01-01"
    assert post.body.strip() == "内容"


def test_load_post_falls_back_to_filename_when_title_is_missing(tmp_path):
    """No ``title`` field means the file name stands in for it."""
    posts = tmp_path / "posts"
    posts.mkdir()
    path = posts / "no-title.md"
    path.write_text("---\ndate: 2026-01-01\n---\n\n内容\n", encoding="utf-8")

    post = load_post(path, posts)
    assert post.title == "no-title"


def test_load_post_date_is_empty_when_date_is_missing(tmp_path):
    """No ``date`` field means an empty date, not a guessed one."""
    posts = tmp_path / "posts"
    posts.mkdir()
    path = posts / "no-date.md"
    path.write_text("---\ntitle: 有标题\n---\n\n内容\n", encoding="utf-8")

    post = load_post(path, posts)
    assert post.date == ""


def test_load_post_error_mentions_the_file_path(tmp_path):
    """坏文件报错要带上路径，否则调用方不知道该去修哪一个。"""
    posts = tmp_path / "posts"
    posts.mkdir()
    path = posts / "broken.md"
    path.write_text("---\ntitle: 坏文件\n\n正文还在\n", encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        load_post(path, posts)
    assert "broken.md" in str(excinfo.value)


def test_discover_raises_when_posts_dir_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        discover(tmp_path / "nope")


def test_discover_unsupported_lists_non_markdown_files(tmp_path):
    """HTML posts are published by the site but not parsed by this adapter."""
    posts = tmp_path / "posts"
    posts.mkdir()
    (posts / "a.md").write_text("---\ntitle: 一\n---\n\nx\n", encoding="utf-8")
    (posts / "b.html").write_text("<p>html</p>", encoding="utf-8")
    (posts / "c.txt").write_text("plain\n", encoding="utf-8")

    assert discover_unsupported(posts) == ["b.html", "c.txt"]
    assert [p.slug for p in discover(posts)] == ["a"]


def test_discover_unsupported_skips_hidden_files_and_dirs(tmp_path):
    """隐藏文件与隐藏目录不算「不支持的母稿」：站点不会发布它们。"""
    posts = tmp_path / "posts"
    (posts / ".hidden").mkdir(parents=True)
    (posts / "visible").mkdir()
    (posts / ".hidden" / "inside.html").write_text("<p>x</p>", encoding="utf-8")
    (posts / ".DS_Store").write_text("junk", encoding="utf-8")
    (posts / "visible" / "page.html").write_text("<p>y</p>", encoding="utf-8")

    assert discover_unsupported(posts) == ["visible/page.html"]


def test_discover_unsupported_returns_sorted_paths(tmp_path, monkeypatch):
    """返回值按字典序排好，不靠文件系统碰巧的遍历顺序。"""
    posts = tmp_path / "posts"
    (posts / "b").mkdir(parents=True)
    (posts / "a").mkdir(parents=True)
    (posts / "b" / "z.html").write_text("<p>z</p>", encoding="utf-8")
    (posts / "a" / "y.html").write_text("<p>y</p>", encoding="utf-8")

    original_rglob = Path.rglob

    def reversed_rglob(self, pattern):
        """假装文件系统按倒序返回文件。"""
        return list(reversed(sorted(original_rglob(self, pattern))))

    monkeypatch.setattr(Path, "rglob", reversed_rglob)
    assert discover_unsupported(posts) == ["a/y.html", "b/z.html"]


def test_discover_unsupported_returns_empty_when_posts_dir_missing(tmp_path):
    assert discover_unsupported(tmp_path / "nope") == []


def test_discover_unsupported_does_not_scan_when_posts_dir_missing(
    tmp_path, monkeypatch
):
    """目录不存在时直接返回空列表，不去扫盘。"""

    def boom(self, pattern):
        raise AssertionError("目录不存在时不该扫描文件系统")

    monkeypatch.setattr(Path, "rglob", boom)
    assert discover_unsupported(tmp_path / "nope") == []


def test_discover_finds_every_post(tmp_path):
    posts = tmp_path / "posts"
    (posts / "a").mkdir(parents=True)
    (posts / "b").mkdir(parents=True)
    (posts / "a" / "one.md").write_text("---\ntitle: 一\n---\n\nx\n", encoding="utf-8")
    (posts / "b" / "two.md").write_text("---\ntitle: 二\n---\n\ny\n", encoding="utf-8")
    found = discover(posts)
    assert [p.slug for p in found] == ["a/one", "b/two"]


def test_public_type_hints_are_locked():
    """类型注解是接口的一部分，下游按它写代码。

    注解一旦回退成 ``dict`` / ``list``，运行时不报错，但下游拿到的
    形状已经不是约定的那个了 —— 只能靠断言提前钉住。
    """
    assert typing.get_type_hints(discover)["return"] == list[SourcePost]
    assert typing.get_type_hints(parse_front_matter)["return"] == tuple[
        dict[str, object], str
    ]
    assert typing.get_type_hints(SourcePost)["fields"] == dict[str, object]
