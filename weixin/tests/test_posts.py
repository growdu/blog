from wechat.posts import (
    BODY_LIMIT,
    TITLE_LIMIT,
    build_permalink,
    check_eligibility,
    discover,
    load_post,
    make_digest,
    parse_front_matter,
)
from wechat.titles import effective_title

FM = """---
title: "在 PostgreSQL 18 逻辑复制中新增 GUC 参数"
date: 2026-11-09 15:00:00
author: growdu
categories:
  - 数据库
tags:
  - 逻辑复制
  - GUC
---

## 第一节

第一段正文内容，足够长以便生成摘要。

```sql
SELECT 1;
```
"""


def _write(tmp_path, rel, content):
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return posts_dir, target


def test_parse_front_matter_splits_and_reads_scalars():
    fm, body = parse_front_matter(FM)
    assert fm["title"] == "在 PostgreSQL 18 逻辑复制中新增 GUC 参数"
    assert fm["date"] == "2026-11-09 15:00:00"
    assert fm["author"] == "growdu"
    assert body.lstrip().startswith("## 第一节")


def test_parse_front_matter_reads_list_values():
    fm, _ = parse_front_matter(FM)
    assert fm["categories"] == ["数据库"]
    assert fm["tags"] == ["逻辑复制", "GUC"]


def test_parse_front_matter_without_front_matter_returns_empty():
    fm, body = parse_front_matter("# 只有正文\n")
    assert fm == {}
    assert body == "# 只有正文\n"


def test_parse_front_matter_keeps_inline_list_value():
    fm, _ = parse_front_matter("---\ntitle: \"x\"\ncategories: 数据库\n---\n\n正文\n")
    assert fm["categories"] == "数据库"


def test_make_digest_takes_first_paragraph_and_strips_markup():
    body = "## 标题\n\n这是一段**加粗**和 `代码` 的正文。\n\n第二段不取。\n"
    assert make_digest(body) == "这是一段加粗和 代码 的正文。"


def test_make_digest_skips_code_blocks_and_tables():
    body = "```sql\nSELECT 1;\n```\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n\n真正的正文段落。\n"
    assert make_digest(body) == "真正的正文段落。"


def test_make_digest_respects_limit():
    body = "甲" * 200 + "。后文"
    assert len(make_digest(body, limit=120)) <= 120


def test_make_digest_prefers_sentence_boundary():
    body = "第一句话讲清楚问题。" + "补充说明" * 80 + "第二句话。"
    digest = make_digest(body, limit=120)
    assert digest.endswith("。")
    assert len(digest) <= 120


def test_make_digest_returns_empty_for_body_without_paragraph():
    assert make_digest("## 只有标题\n\n```sql\nSELECT 1;\n```\n") == ""


def test_build_permalink_uses_date_and_quoted_slug():
    assert build_permalink("database/postgresql-row-lock", "2026-11-09 15:00:00") == \
        "/2026/11/09/database/postgresql-row-lock/"
    assert build_permalink("db/postgresql/常用压缩算法", "2023-05-22 10:00:00") == \
        "/2023/05/22/db/postgresql/%E5%B8%B8%E7%94%A8%E5%8E%8B%E7%BC%A9%E7%AE%97%E6%B3%95/"


def test_build_permalink_falls_back_on_bad_date():
    assert build_permalink("a/b", "not-a-date") == "/2024/01/01/a/b/"


def test_load_post_builds_slug_permalink_and_fingerprint(tmp_path):
    posts_dir, target = _write(tmp_path, "database/postgresql-row-lock.md", FM)

    post = load_post(target, posts_dir)

    assert post.slug == "database/postgresql-row-lock"
    assert post.permalink == "/2026/11/09/database/postgresql-row-lock/"
    assert post.categories == ("数据库",)
    assert len(post.fingerprint) == 64
    assert post.fingerprint == load_post(target, posts_dir).fingerprint


def test_discover_lists_every_markdown_post(tmp_path):
    posts_dir, _ = _write(tmp_path, "database/a.md", FM)
    _write(tmp_path, "db/postgresql/b.md", FM)

    posts = discover(posts_dir)

    assert sorted(post.slug for post in posts) == ["database/a", "db/postgresql/b"]


def test_discover_raises_with_actionable_message(tmp_path):
    missing = tmp_path / "source" / "_posts"
    try:
        discover(missing)
    except FileNotFoundError as error:
        assert "sync-hexo.py" in str(error)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_check_eligibility_accepts_valid_post(tmp_path):
    posts_dir, target = _write(tmp_path, "database/ok.md", FM)
    post = load_post(target, posts_dir)
    assert check_eligibility(post).ok is True
    assert check_eligibility(post).reasons == ()


def test_check_eligibility_accepts_an_overlong_body(tmp_path):
    """A long body is split into several drafts, not skipped.

    WeChat's limit is per draft, so an article that does not fit
    becomes several -- the body length no longer decides whether the
    article may be published at all.
    """
    posts_dir, target = _write(tmp_path, "database/long.md", FM + "很长的一段内容。" * 3000)
    post = load_post(target, posts_dir)
    result = check_eligibility(post)
    assert result.ok is True
    assert result.reasons == ()


def test_check_eligibility_keeps_a_long_title(tmp_path):
    """A long title is shortened, not a reason to skip the article.

    WeChat takes 85 characters; anything longer is cut at a boundary
    that keeps the topic, so no title keeps an article out of the
    draft box.
    """
    long_title = "标" * (TITLE_LIMIT + 5)
    posts_dir, target = _write(
        tmp_path, "database/titled.md", FM.replace(FM.split('"')[1], long_title))
    post = load_post(target, posts_dir)
    result = check_eligibility(post)
    assert result.ok is True
    assert result.reasons == ()
    assert len(effective_title(post.title)) <= TITLE_LIMIT


def test_check_eligibility_title_boundary(tmp_path):
    """The limit is 64 characters -- the editor's.

    The ``draft/add`` API takes 85, but the editor behind it lets a
    person type 64, and publishing is a human step.  An earlier
    reading of the documentation said 32, and the corpus proved it
    wrong.
    """
    assert TITLE_LIMIT == 64
    exact = "标" * TITLE_LIMIT
    posts_dir, target = _write(
        tmp_path, "database/exact.md", FM.replace(FM.split('"')[1], exact))
    post = load_post(target, posts_dir)
    assert check_eligibility(post).ok is True

    over = "标" * (TITLE_LIMIT + 1)
    posts_dir, target = _write(
        tmp_path, "database/over.md", FM.replace(FM.split('"')[1], over))
    post = load_post(target, posts_dir)
    assert check_eligibility(post).ok is True


def test_check_eligibility_body_limit_boundary(tmp_path):
    """The body limit is a measurement now, not a gate.

    ``BODY_LIMIT`` still tells the audit how long the articles are; it
    no longer keeps them out of the draft box.
    """
    body = "文" * (BODY_LIMIT + 1)
    posts_dir, target = _write(tmp_path, "database/edge.md", FM + body)
    post = load_post(target, posts_dir)
    assert check_eligibility(post).ok is True
