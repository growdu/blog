"""Corpus audit: the numbers behind the analysis documents.

Every figure quoted in ``weixin/docs/`` is derived here, so the analysis
can be re-derived whenever the blog changes::

    python3 -m wechat.cli audit

Two things make the numbers easy to get wrong, and this module exists to
remove both traps:

* The authoritative body limit is the length of the **rendered HTML**,
  not the length of the markdown.  Counting raw words is only a cheap
  pre-check.
* ``class=`` appears in the corpus as *escaped prose* (articles that
  quote HTML examples).  A substring search reports those as violations;
  only real tags carry real attributes.  :func:`check_html` therefore
  parses tags instead of matching text.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from .mdparse import parse
from .posts import BODY_LIMIT, CONTENT_LIMIT, TITLE_LIMIT, discover
from .render import render

__all__ = [
    "Audit",
    "audit_corpus",
    "check_html",
    "html_violations",
    "html_violations_from_htmls",
    "word_buckets",
]

# Only real tags count.  Escaped text (``&lt;div class="x"&gt;``) is prose,
# not markup, and WeChat parses the DOM rather than the raw string.
_TAG_RE = re.compile(r"<([a-zA-Z][a-zA-Z0-9-]*)((?:\s+[^<>]*?)?)\s*/?>")

_FORBIDDEN_TAGS = ("script", "style", "iframe")


@dataclass(frozen=True)
class Audit:
    """The state of the corpus against WeChat's publishing limits.

    The three gate counters form a **cascade**: each one counts only the
    posts that survived the previous one.  The corpus-wide counters below
    them answer a different question -- how the whole corpus measures on
    each criterion regardless of the others -- and are therefore counted
    over every post.
    """

    posts: int
    categories: int
    # Cascade: how many posts each gate lets through, and how many it stops.
    title_ok: int
    title_over: int
    raw_ok: int
    raw_over: int
    render_ok: int
    render_over: int
    # Corpus wide.
    raw_within: int
    fit_highlight: int
    fit_plain: int
    fit_either: int
    publishable: int
    needs_plain_only: int
    median_highlight: float
    median_plain: float
    buckets: dict = field(default_factory=dict)
    violations: list = field(default_factory=list)

    @property
    def publishable_ratio(self) -> float:
        if not self.posts:
            return 0.0
        return self.publishable * 100.0 / self.posts


def check_html(html: str) -> list:
    """Return the list of WeChat-incompatible constructs in ``html``.

    WeChat's editor only honours inline styles, has no JavaScript, and
    filters external links in the body.  A violation is therefore a real
    element carrying a ``class`` attribute, a ``script``/``style``/
    ``iframe`` element, or an anchor with an ``href``.
    """
    problems = []
    for match in _TAG_RE.finditer(html):
        tag = match.group(1).lower()
        attrs = match.group(2) or ""
        if re.search(r"\bclass\s*=", attrs, re.I):
            problems.append("class@" + tag)
        if tag in _FORBIDDEN_TAGS:
            problems.append(tag)
        if tag == "a" and re.search(r"\bhref\s*=", attrs, re.I):
            problems.append("a[href]")
    return sorted(set(problems))


def html_violations(posts) -> list:
    """Check every post's rendered HTML and return ``(slug, problems)``."""
    violations = []
    for post in posts:
        problems = check_html(render(parse(post.body)).html)
        if problems:
            violations.append((post.slug, problems))
    return violations


def html_violations_from_htmls(pairs) -> list:
    """Check already rendered HTML, given as ``(slug, html)`` pairs."""
    violations = []
    for slug, html in pairs:
        problems = check_html(html)
        if problems:
            violations.append((slug, problems))
    return violations


def word_buckets(lengths, limit: int = BODY_LIMIT) -> dict:
    """Group raw word counts into the buckets used by the analysis docs."""
    buckets = {
        "<2000": 0,
        "2000-5000": 0,
        "5000-10000": 0,
        "10000-20000": 0,
        ">20000": 0,
    }
    for length in lengths:
        if length < 2000:
            buckets["<2000"] += 1
        elif length < 5000:
            buckets["2000-5000"] += 1
        elif length < 10000:
            buckets["5000-10000"] += 1
        elif length <= limit:
            buckets["10000-20000"] += 1
        else:
            buckets[">20000"] += 1
    return buckets


def audit_corpus(posts_dir: Path) -> Audit:
    """Measure the corpus in ``posts_dir`` against the publishing limits.

    Both rendering modes are measured, because the pipeline falls back to
    plain code blocks when the highlighted version does not fit.  A post
    counts as publishable when it passes the raw pre-check *and* fits in
    at least one of the two modes.
    """
    posts = discover(Path(posts_dir))
    if not posts:
        return Audit(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0.0)

    raw_lengths = [len(re.sub(r"\s", "", post.body)) for post in posts]
    highlighted = []
    plain = []
    rendered = []
    for post in posts:
        blocks = parse(post.body)
        with_highlight = render(blocks)
        highlighted.append(with_highlight.content_length)
        plain.append(render(blocks, highlight=False).content_length)
        rendered.append((post.slug, with_highlight.html))

    # Cascade: each gate counts only the posts the previous one let through.
    after_title = []
    after_raw = []
    after_render = []
    needs_plain_only = 0
    for index, post in enumerate(posts):
        if len(post.title) > TITLE_LIMIT:
            continue
        after_title.append(index)
        if len(re.sub(r"\s", "", post.body)) > BODY_LIMIT:
            continue
        after_raw.append(index)
        if min(highlighted[index], plain[index]) > CONTENT_LIMIT:
            continue
        after_render.append(index)
        if highlighted[index] > CONTENT_LIMIT:
            needs_plain_only += 1

    # Corpus wide: how every post measures on each criterion on its own.
    raw_within = sum(1 for length in raw_lengths if length <= BODY_LIMIT)
    fit_highlight = sum(1 for length in highlighted if length <= CONTENT_LIMIT)
    fit_plain = sum(1 for length in plain if length <= CONTENT_LIMIT)
    fit_either = sum(
        1 for high, low in zip(highlighted, plain) if min(high, low) <= CONTENT_LIMIT)

    categories = {post.categories[0] for post in posts if post.categories}

    return Audit(
        posts=len(posts),
        categories=len(categories),
        title_ok=len(after_title),
        title_over=len(posts) - len(after_title),
        raw_ok=len(after_raw),
        raw_over=len(after_title) - len(after_raw),
        render_ok=len(after_render),
        render_over=len(after_raw) - len(after_render),
        raw_within=raw_within,
        fit_highlight=fit_highlight,
        fit_plain=fit_plain,
        fit_either=fit_either,
        publishable=len(after_render),
        needs_plain_only=needs_plain_only,
        median_highlight=statistics.median(highlighted),
        median_plain=statistics.median(plain),
        buckets=word_buckets(raw_lengths),
        violations=html_violations_from_htmls(rendered),
    )
