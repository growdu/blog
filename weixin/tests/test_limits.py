"""正文长度上限：能配，而且贯穿拆分、指纹与统计。

官方字段表写着「content 少于 2 万字符」，但那行字是错的：
``draft/add`` 实测收下 20001、25000、40000、65535、100000 字符，
原样存回，一个字都没有少。于是这个上限不是平台的硬限制，而是
「一篇草稿该有多长」的选择——所以它得能配，配了还得真的管用。

这里盯住三件事：

* 上限能配（命令行 > 环境变量 > 默认值），配错要报错而不是悄悄改口径；
* 上限真的切在拆分上（上限越大，部分越少），且每一部分都不超限；
* 上限进了内容指纹——换了上限，拆分变了，草稿必须重发。
"""

from types import SimpleNamespace

import pytest

from wechat.audit import audit_corpus
from wechat.cli import _fingerprint, _fits, _limit, _render_parts, main
from wechat.posts import (CONTENT_LIMIT, check_eligibility, load_post,
                          resolve_content_limit)


def _long_post(tmp_path, paragraphs=700, title="很长"):
    """一篇文章，长到一定会在某个上限下被拆开。"""
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database" / "long.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    body = "\n\n".join(
        "这是第 {} 段。".format(index) + "内容。" * 80
        for index in range(paragraphs))
    target.write_text(
        "---\ntitle: \"{}\"\ndate: 2026-11-09 15:00:00\n"
        "categories:\n  - 数据库\n---\n\n{}\n".format(title, body),
        encoding="utf-8")
    return load_post(target, posts_dir)


def _render_args(out_dir, max_length=0):
    return SimpleNamespace(out_dir=str(out_dir), category_tag="top",
                          author="growdu", max_length=max_length)


def _empty_post(tmp_path):
    """一篇文章，源文件里只剩 front matter。"""
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database" / "empty.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\ntitle: \"空的\"\ndate: 2026-11-09 15:00:00\n---\n\n",
        encoding="utf-8")
    return load_post(target, posts_dir)


# --- 上限从哪来 -----------------------------------------------------------


def test_the_command_line_limit_wins_over_the_environment(monkeypatch):
    monkeypatch.setenv("WX_MAX_LENGTH", "12345")
    assert resolve_content_limit(60000) == 60000


def test_the_environment_limit_is_used_when_the_command_line_is_silent(monkeypatch):
    monkeypatch.setenv("WX_MAX_LENGTH", "12345")
    assert resolve_content_limit(0) == 12345


def test_the_default_limit_is_used_when_nothing_is_given(monkeypatch):
    monkeypatch.delenv("WX_MAX_LENGTH", raising=False)
    assert resolve_content_limit(0) == CONTENT_LIMIT


def test_the_default_limit_is_the_measured_ceiling_with_a_margin(monkeypatch):
    """默认上限留有余地，不是贴着天花板。

    实测的天花板是 100000 字符（``draft/add`` 收下、``draft/get`` 原样
    存回，后台编辑器也不截断）。但默认取 60000：折合读者能看到的约
    1.5 万字，已经是一篇长文，还留着一段余量。要更长就 ``--max-length``。
    """
    monkeypatch.delenv("WX_MAX_LENGTH", raising=False)
    assert resolve_content_limit(0) == 60000


def test_a_broken_limit_is_refused(monkeypatch):
    """上限写错了要报错，不能悄悄换一个数继续跑。"""
    monkeypatch.setenv("WX_MAX_LENGTH", "很多")
    with pytest.raises(ValueError):
        resolve_content_limit(0)
    with pytest.raises(ValueError):
        resolve_content_limit(-1)
    with pytest.raises(ValueError):
        resolve_content_limit(0)


def test_a_limit_of_zero_means_the_default_not_an_empty_article(monkeypatch):
    monkeypatch.delenv("WX_MAX_LENGTH", raising=False)
    assert _limit(SimpleNamespace(max_length=0)) == CONTENT_LIMIT
    assert _limit(SimpleNamespace()) == CONTENT_LIMIT
    assert _limit(SimpleNamespace(max_length=60000)) == 60000


# --- 上限切在拆分上 -------------------------------------------------------


def test_a_bigger_limit_makes_fewer_parts(tmp_path):
    """上限变大，文章就该少拆几刀。"""
    post = _long_post(tmp_path)
    small = _render_parts(post, _render_args(tmp_path / "out-small", 20000))
    large = _render_parts(post, _render_args(tmp_path / "out-large", 60000))
    assert len(large) < len(small)


def test_no_part_is_longer_than_the_limit(tmp_path):
    """每一部分都得装得下——超限的部分发不出去。"""
    post = _long_post(tmp_path, paragraphs=200)
    for limit in (20000, 60000):
        parts = _render_parts(post, _render_args(tmp_path / "out", limit))
        assert parts
        for part in parts:
            assert part.result.content_length <= limit


def test_a_part_that_does_not_fit_is_not_accepted(tmp_path):
    """``_fits`` 认的是本次的上限，不是写死的那个数。"""
    post = _long_post(tmp_path, paragraphs=1)
    parts = _render_parts(post, _render_args(tmp_path / "out", 20000))
    result = parts[0].result
    assert _fits(result, 20000)
    assert not _fits(result, 10)


# --- 上限进了指纹 ---------------------------------------------------------


def test_the_limit_is_part_of_the_fingerprint(tmp_path):
    """换了上限，拆分就变了，草稿必须重发。"""
    post = _long_post(tmp_path, paragraphs=1)
    assert _fingerprint(post, "", 20000, "growdu") != _fingerprint(
        post, "", 60000, "growdu")


def test_the_fingerprint_of_an_unchanged_article_does_not_move(tmp_path):
    post = _long_post(tmp_path, paragraphs=1)
    assert _fingerprint(post, "", 60000, "growdu") == _fingerprint(
        post, "", 60000, "growdu")


def test_the_fingerprint_moves_when_the_author_changes(tmp_path):
    """改了署名要能刷到草稿里——所以署名得进指纹。

    以前 ``author`` 不在指纹里，单独改 ``--author`` 不会让草稿重刷，
    改完看着像没生效。现在署名和正文、标题、分类标签、上限一样，
    都是内容的一部分。
    """
    post = _long_post(tmp_path, paragraphs=1)
    assert _fingerprint(post, "", 60000, "growdu") != _fingerprint(
        post, "", 60000, "内核开发者")


# --- 上限进了统计 ---------------------------------------------------------


def test_the_audit_counts_the_parts_of_the_given_limit(tmp_path):
    """同一个语料，换个上限就该换个草稿数。"""
    posts_dir = tmp_path / "source" / "_posts"
    (posts_dir / "database").mkdir(parents=True)
    (posts_dir / "database" / "a.md").write_text(
        "---\ntitle: \"a\"\ndate: 2026-11-09 15:00:00\n---\n\n"
        + "\n\n".join("第 {} 段。".format(i) + "内容。" * 80 for i in range(300))
        + "\n", encoding="utf-8")

    small = audit_corpus(posts_dir, limit=20000)
    large = audit_corpus(posts_dir, limit=60000)
    assert large.split_parts < small.split_parts
    assert small.limit == 20000
    assert large.limit == 60000


def test_the_audit_prints_the_limit_it_used(tmp_path, capsys):
    posts_dir = tmp_path / "source" / "_posts"
    (posts_dir / "database").mkdir(parents=True)
    (posts_dir / "database" / "a.md").write_text(
        "---\ntitle: \"a\"\ndate: 2026-11-09 15:00:00\n---\n\n正文。\n",
        encoding="utf-8")

    code = main(["audit", "--posts-dir", str(posts_dir),
                 "--out-dir", str(tmp_path / "out"), "--max-length", "23456"])
    out = capsys.readouterr().out
    assert code == 0
    assert "23456" in out


def test_the_environment_limit_reaches_the_audit(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("WX_MAX_LENGTH", "34567")
    posts_dir = tmp_path / "source" / "_posts"
    (posts_dir / "database").mkdir(parents=True)
    (posts_dir / "database" / "a.md").write_text(
        "---\ntitle: \"a\"\ndate: 2026-11-09 15:00:00\n---\n\n正文。\n",
        encoding="utf-8")

    code = main(["audit", "--posts-dir", str(posts_dir),
                 "--out-dir", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert code == 0
    assert "34567" in out


# --- 空文章 ---------------------------------------------------------------


def test_a_post_without_content_is_not_publishable(tmp_path):
    """只剩 front matter 的文章不该建草稿——那是个空壳。"""
    post = _empty_post(tmp_path)
    result = check_eligibility(post)
    assert result.ok is False
    assert "空" in result.reasons[0]


def test_a_post_with_content_is_publishable(tmp_path):
    post = _long_post(tmp_path, paragraphs=1)
    assert check_eligibility(post).ok is True


def test_a_batch_leaves_an_empty_article_alone(tmp_path, capsys):
    """空文章不进草稿箱，但要说清楚为什么。"""
    posts_dir = tmp_path / "source" / "_posts"
    (posts_dir / "database").mkdir(parents=True)
    (posts_dir / "database" / "empty.md").write_text(
        "---\ntitle: \"空的\"\ndate: 2026-11-09 15:00:00\n---\n\n",
        encoding="utf-8")

    code = main(["batch", "--dry-run", "--posts-dir", str(posts_dir),
                 "--out-dir", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert code == 0
    assert "将处理 0 篇" in out
    assert "database/empty" in out
    assert "正文为空" in out
