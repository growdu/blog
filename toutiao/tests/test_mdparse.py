import pytest

from toutiao.mdparse import (
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


def test_document_without_leading_dashes_is_not_an_error():
    """A normal document that merely contains ``---`` in its body is fine."""
    fields, body = parse_front_matter("正文\n\n---\n\n更多正文\n")
    assert fields == {}
    assert body == "正文\n\n---\n\n更多正文\n"


def test_empty_front_matter_raises():
    """``---\\n---\\n`` has no content for the field parser to read."""
    with pytest.raises(ValueError):
        parse_front_matter("---\n---\n\n正文\n")


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


def test_discover_unsupported_returns_empty_when_posts_dir_missing(tmp_path):
    assert discover_unsupported(tmp_path / "nope") == []


def test_discover_finds_every_post(tmp_path):
    posts = tmp_path / "posts"
    (posts / "a").mkdir(parents=True)
    (posts / "b").mkdir(parents=True)
    (posts / "a" / "one.md").write_text("---\ntitle: 一\n---\n\nx\n", encoding="utf-8")
    (posts / "b" / "two.md").write_text("---\ntitle: 二\n---\n\ny\n", encoding="utf-8")
    found = discover(posts)
    assert [p.slug for p in found] == ["a/one", "b/two"]
