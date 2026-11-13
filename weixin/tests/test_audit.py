import subprocess
import sys
from pathlib import Path

from wechat.audit import (
    audit_corpus,
    check_html,
    html_violations_from_htmls,
    word_buckets,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _post(title, body):
    return "---\ntitle: {}\ndate: 2026-11-09 15:00:00\nauthor: growdu\ncategories:\n  - 数据库\n---\n\n{}\n".format(
        title, body)


def _write_corpus(tmp_path):
    posts_dir = tmp_path / "source" / "_posts"
    posts_dir.mkdir(parents=True)

    (posts_dir / "ok.md").write_text(
        _post("短标题", "## 第一节\n\n一段正文。\n\n```sql\nSELECT 1;\n```\n"),
        encoding="utf-8")

    (posts_dir / "long-title.md").write_text(
        _post("这是一个很长的主标题用来测试裁剪逻辑：" + "副标题" * 15, "正文。\n"),
        encoding="utf-8")

    # Prose that quotes HTML: the ``class=`` is escaped text, not an attribute.
    (posts_dir / "quoted-html.md").write_text(
        _post("讲 HTML 的文章", "看这段示例：\n\n```html\n<div class=\"mermaid\">图</div>\n```\n"),
        encoding="utf-8")

    (posts_dir / "huge.md").write_text(
        _post("很长的文章", "很长的正文。\n" * 20000), encoding="utf-8")

    return posts_dir


# --- check_html ------------------------------------------------------------


def test_check_html_accepts_inline_styles_only():
    html = '<p style="font-size:15px">正文</p>'
    assert check_html(html) == []


def test_check_html_reports_class_attribute():
    assert check_html('<p class="x">正文</p>') == ["class@p"]


def test_check_html_reports_forbidden_tags():
    assert check_html("<script>x()</script>") == ["script"]
    assert check_html("<style>p{}</style>") == ["style"]
    assert check_html('<iframe src="http://x"></iframe>') == ["iframe"]


def test_check_html_reports_external_anchor():
    assert check_html('<a href="http://x">链接</a>') == ["a[href]"]


def test_check_html_ignores_escaped_html_in_prose():
    """The corpus quotes HTML in prose; that text is not markup.

    A substring search for ``class=`` reports these as violations, which
    is a false positive -- WeChat parses the DOM, and escaped text is
    just text.
    """
    html = "<p>看这段示例：</p><pre><code>&lt;div class=&quot;mermaid&quot;&gt;</code></pre>"
    assert "class=" in html
    assert check_html(html) == []


def test_check_html_ignores_class_in_ordinary_word():
    html = "<p>pg_class=1259 是 catalog oid</p>"
    assert check_html(html) == []


# --- word_buckets ----------------------------------------------------------


def test_word_buckets_splits_on_the_documented_boundaries():
    buckets = word_buckets([100, 2000, 5000, 10000, 20000, 20001])
    assert buckets == {
        "<2000": 1,
        "2000-5000": 1,
        "5000-10000": 1,
        "10000-20000": 2,
        ">20000": 1,
    }


def test_word_buckets_upper_edge_belongs_to_the_last_bucket():
    assert word_buckets([20000])[">20000"] == 0


# --- audit_corpus ----------------------------------------------------------


def test_audit_corpus_measures_every_gate(tmp_path):
    posts_dir = _write_corpus(tmp_path)
    report = audit_corpus(posts_dir)

    assert report.posts == 4
    assert report.categories == 1

    # The title is no longer a gate: it is shortened at a boundary that
    # keeps the topic, so every post is let through.
    assert report.title_ok == 4
    assert report.title_shortened == 1

    # The 20000 word body is over the raw limit.
    assert report.raw_ok == 3
    assert report.raw_over == 1

    # The cascade: 4 -> 3 -> 3.
    assert report.render_ok == 3
    assert report.render_over == 0

    # Corpus wide: the raw body of the long post is the only one over.
    assert report.raw_within == 3

    # The quoted-HTML article renders to escaped text, so it is compliant.
    assert report.violations == []

    # An article is publishable as soon as its title fits and it can be
    # cut into parts that fit.  The long post here is a single
    # paragraph of 20000 lines: there is nowhere left to cut it, so it
    # is the one article that cannot be published.
    assert report.publishable == 3
    assert report.unsplittable == 1
    assert report.split_posts == 0
    assert report.split_parts == 3


def test_audit_counts_an_article_that_is_split(tmp_path):
    """An article made of many paragraphs is cut into several drafts."""
    posts_dir = tmp_path / "source" / "_posts"
    posts_dir.mkdir(parents=True)
    body = "\n\n".join("第 {} 段。".format(index) for index in range(400))
    (posts_dir / "long.md").write_text(
        _post("很长的文章", "## 第一节\n\n" + body), encoding="utf-8")

    report = audit_corpus(posts_dir, limit=20000)
    assert report.publishable == 1
    assert report.unsplittable == 0
    assert report.split_posts == 1
    assert report.split_parts == 2


def test_audit_corpus_reports_no_violation_for_sanitised_raw_html(tmp_path):
    """Raw HTML is cleaned on the way out, so it cannot break the rules.

    The audit is the belt to the renderer's braces: even when a post
    contains a class attribute or an iframe, the output stays compliant.
    """
    posts_dir = tmp_path / "source" / "_posts"
    posts_dir.mkdir(parents=True)
    (posts_dir / "raw.md").write_text(
        _post("原始 HTML", '正文\n\n<div class="x">块</div>\n\n'
                           '<iframe src="https://v.example.com/x"></iframe>\n'),
        encoding="utf-8")

    report = audit_corpus(posts_dir)
    assert report.violations == []


def test_violation_checker_reports_a_bad_construct():
    """The checker must be able to fail, not just pass everything."""
    violations = html_violations_from_htmls([
        ("good", '<p style="font-size:15px">正文</p>'),
        ("bad", '<p class="x">正文</p><script>alert(1)</script>'),
    ])
    assert violations == [("bad", ["class@p", "script"])]


def test_audit_corpus_on_empty_directory(tmp_path):
    posts_dir = tmp_path / "source" / "_posts"
    posts_dir.mkdir(parents=True)
    report = audit_corpus(posts_dir)
    assert report.posts == 0
    assert report.publishable == 0
    assert report.publishable_ratio == 0.0


# --- CLI integration -------------------------------------------------------


def test_cli_audit_prints_the_funnel(tmp_path):
    posts_dir = _write_corpus(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "wechat.cli", "audit", "--posts-dir", str(posts_dir)],
        cwd=str(REPO_ROOT / "weixin"),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "语料: 4 篇" in result.stdout
    assert "可发布: 3 篇" in result.stdout
    assert "其中拆不开（单块就超限）: 1 篇" in result.stdout
    assert "HTML 合规: 4 篇全部通过" in result.stdout
