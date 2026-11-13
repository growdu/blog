"""Measure what the body limit costs and buys over the whole corpus.

Run from the repository root:

    python3 weixin/tools/measure-length.py

It answers the question the number in ``wechat/posts.py`` cannot answer
by itself: at a limit of X, how many drafts does the corpus become, and
how long is one of them for the reader?

Two things make the answer less obvious than it looks:

* the limit counts the **rendered HTML**, and only about a quarter of
  that HTML is text the reader sees -- the inline styles eat the rest;
* an article that does not fit is not lost, it is cut into several
  drafts, so the draft count grows even when the article count does
  not.
"""
from __future__ import annotations

import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "weixin"))

from wechat.audit import _measure  # noqa: E402
from wechat.collection import render_category_tag  # noqa: E402
from wechat.mdparse import parse  # noqa: E402
from wechat.posts import discover, is_empty  # noqa: E402
from wechat.render import render  # noqa: E402
from wechat.split import framing_reserve, plan_parts  # noqa: E402
from wechat.titles import effective_title  # noqa: E402

DEFAULT_LIMITS = (20000, 30000, 40000, 50000, 60000, 80000, 100000)

_TAG = re.compile(r"<[^>]+>")


def main() -> int:
    posts_dir = ROOT / "source" / "_posts"
    if not posts_dir.is_dir():
        print("找不到 source/_posts，请先跑 tools/sync-hexo.py", file=sys.stderr)
        return 1

    posts = [post for post in discover(posts_dir) if not is_empty(post)]

    # Render everything once: the parts are planned from the same
    # blocks, so the only thing that changes between the limits is the
    # budget the plan is cut against.
    plans = []
    ratios = []
    for post in posts:
        blocks = parse(post.body)
        title = effective_title(post.title)
        reserve = framing_reserve(title, render_category_tag(post.categories))
        plans.append((blocks, reserve))
        html = render(blocks).html
        if html:
            visible = len(re.sub(r"\s", "", _TAG.sub("", html)))
            ratios.append(visible / len(html))

    ratio = statistics.median(ratios) if ratios else 0.25

    print("语料 {} 篇（不含正文为空的）".format(len(posts)))
    print("渲染后的 HTML 里，读者能看到的字占 {:.1%}".format(ratio))
    print()
    print("{:<9} {:>7} {:>7} {:>7} {:>11} {:>9}".format(
        "上限", "草稿数", "需拆篇", "拆不开", "读者看到", "最长一篇"))
    for limit in DEFAULT_LIMITS:
        parts_total = 0
        split_posts = 0
        unsplittable = 0
        worst = 0
        for blocks, reserve in plans:
            budget = limit - reserve
            parts = plan_parts(
                blocks, limit,
                lambda group: _measure(group, True),
                lambda group: _measure(group, False),
                reserve=reserve)
            if any(_measure(group, True) > budget
                   and _measure(group, False) > budget for group, _ in parts):
                unsplittable += 1
                continue
            parts_total += len(parts)
            worst = max(worst, len(parts))
            if len(parts) > 1:
                split_posts += 1
        print("{:<9} {:>7} {:>7} {:>7} {:>11} {:>9}".format(
            limit, parts_total, split_posts, unsplittable,
            "{} 字".format(int(limit * ratio)), "{} 部分".format(worst)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
