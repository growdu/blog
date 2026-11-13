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

from .collection import render_category_tag
from .mdparse import parse
from .posts import CONTENT_LIMIT, discover, is_empty
from .render import links_html, links_items_html, render
from .split import framing_reserve, plan_parts
from .titles import TITLE_LIMIT, effective_title

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

    An article that does not fit into one draft is not lost: it is split
    into several.  ``split_posts`` counts the articles that need more
    than one draft and ``split_parts`` is how many drafts the corpus
    turns into.
    """

    posts: int
    categories: int
    # Cascade: how many posts each gate lets through, and how many it stops.
    title_ok: int
    title_over: int
    # Titles that have to be shortened before they reach WeChat.
    title_shortened: int
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
    # The split dimension.
    split_posts: int
    split_parts: int
    unsplittable: int
    buckets: dict = field(default_factory=dict)
    violations: list = field(default_factory=list)
    # The limit these numbers were measured against.
    limit: int = CONTENT_LIMIT
    # Posts that carry nothing but their front matter.
    empty_posts: int = 0

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


def word_buckets(lengths) -> dict:
    """Group raw word counts into the buckets used by the analysis docs.

    The edges are absolute: they describe the corpus, not the limit.
    A limit that moves would otherwise change the name of the buckets
    and the numbers quoted in the docs along with them.
    """
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
        elif length <= 20000:
            buckets["10000-20000"] += 1
        else:
            buckets[">20000"] += 1
    return buckets


def _measure(blocks, highlight: bool = True) -> int:
    """The size a group of blocks contributes to a draft.

    The reference links are counted apart from the body: their wrapper
    is paid once per draft, not once per block.
    """
    result = render(blocks, highlight=highlight)
    body = len(result.html) - len(links_html(result.external_links))
    return body + len(links_items_html(result.external_links))


def audit_corpus(posts_dir: Path, limit: int = CONTENT_LIMIT) -> Audit:
    """Measure the corpus in ``posts_dir`` against the publishing limits.

    Both rendering modes are measured, because the pipeline falls back to
    plain code blocks when the highlighted version does not fit.  A post
    that fits in neither mode is not lost: it is split into several
    drafts, which is what ``split_posts`` and ``split_parts`` report.

    ``limit`` is the body limit one draft has to fit into -- the same
    number the pipeline splits with, so the numbers here describe the
    drafts that would really be created.

    The measurement is a conservative one: no mermaid resolver is used
    here, so a diagram counts as its own source code -- which is longer
    than the picture it becomes in the real pipeline.
    """
    posts = discover(Path(posts_dir))
    if not posts:
        return Audit(posts=0, categories=0, title_ok=0, title_over=0,
                     title_shortened=0, raw_ok=0, raw_over=0, render_ok=0,
                     render_over=0, raw_within=0, fit_highlight=0, fit_plain=0,
                     fit_either=0, publishable=0, needs_plain_only=0,
                     median_highlight=0.0, median_plain=0.0, split_posts=0,
                     split_parts=0, unsplittable=0, limit=limit)

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

    # The title is no longer a gate: it is shortened at a boundary that
    # keeps the topic, so every title fits.  What the numbers below
    # report is how many titles have to be shortened, and by how much.
    after_title = []
    after_raw = []
    after_render = []
    needs_plain_only = 0
    shortened = 0
    for index, post in enumerate(posts):
        after_title.append(index)
        if len(effective_title(post.title)) < len(post.title):
            shortened += 1
        if len(re.sub(r"\s", "", post.body)) > limit:
            continue
        after_raw.append(index)
        if min(highlighted[index], plain[index]) > limit:
            continue
        after_render.append(index)
        if highlighted[index] > limit:
            needs_plain_only += 1

    # Posts that carry nothing but their front matter never become a
    # draft: there is nothing to publish.
    empty = sum(1 for post in posts if is_empty(post))

    # How many drafts the corpus turns into once the long articles are
    # split -- and how many articles cannot be split at all.
    split_posts = 0
    split_parts = 0
    unsplittable = 0
    for post in posts:
        if is_empty(post):
            continue
        blocks = parse(post.body)
        title = effective_title(post.title)
        # The same reserve the pipeline uses: every part pays once for
        # its transition lines, its category tag and its reference-links
        # wrapper, and that room has to be kept back from the body.
        reserve = framing_reserve(title, render_category_tag(post.categories))
        budget = limit - reserve
        parts = plan_parts(
            blocks, limit,
            lambda group: _measure(group, True),
            lambda group: _measure(group, False),
            reserve=reserve)
        if any(_measure(group, True) > budget
               and _measure(group, False) > budget for group, _ in parts):
            # One block is too big on its own: there is nowhere left to
            # cut it, so the article cannot be published at all.
            unsplittable += 1
            continue
        split_parts += len(parts)
        if len(parts) > 1:
            split_posts += 1

    # Corpus wide: how every post measures on each criterion on its own.
    raw_within = sum(1 for length in raw_lengths if length <= limit)
    fit_highlight = sum(1 for length in highlighted if length <= limit)
    fit_plain = sum(1 for length in plain if length <= limit)
    fit_either = sum(
        1 for high, low in zip(highlighted, plain) if min(high, low) <= limit)

    categories = {post.categories[0] for post in posts if post.categories}

    return Audit(
        posts=len(posts),
        categories=len(categories),
        title_ok=len(after_title),
        title_over=len(posts) - len(after_title),
        title_shortened=shortened,
        raw_ok=len(after_raw),
        raw_over=len(after_title) - len(after_raw),
        render_ok=len(after_render),
        render_over=len(after_raw) - len(after_render),
        raw_within=raw_within,
        fit_highlight=fit_highlight,
        fit_plain=fit_plain,
        fit_either=fit_either,
        # An article is publishable as soon as its title fits and it
        # can be cut into parts that fit: a long body is split, not
        # refused -- unless there is nowhere left to cut it, or there is
        # nothing to publish in the first place.
        publishable=len(after_title) - unsplittable - empty,
        needs_plain_only=needs_plain_only,
        median_highlight=statistics.median(highlighted),
        median_plain=statistics.median(plain),
        split_posts=split_posts,
        split_parts=split_parts,
        unsplittable=unsplittable,
        buckets=word_buckets(raw_lengths),
        violations=html_violations_from_htmls(rendered),
        limit=limit,
        empty_posts=empty,
    )
