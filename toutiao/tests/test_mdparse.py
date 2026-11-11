import pytest

from toutiao.mdparse import discover, load_post, parse_front_matter


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


def test_discover_raises_when_posts_dir_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        discover(tmp_path / "nope")


def test_discover_finds_every_post(tmp_path):
    posts = tmp_path / "posts"
    (posts / "a").mkdir(parents=True)
    (posts / "b").mkdir(parents=True)
    (posts / "a" / "one.md").write_text("---\ntitle: 一\n---\n\nx\n", encoding="utf-8")
    (posts / "b" / "two.md").write_text("---\ntitle: 二\n---\n\ny\n", encoding="utf-8")
    found = discover(posts)
    assert [p.slug for p in found] == ["a/one", "b/two"]
