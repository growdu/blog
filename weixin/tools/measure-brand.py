"""Measure the brand elements over the whole corpus.

Run from the repository root:

    python3 weixin/tools/measure-brand.py

It prints what the drafts look like before and after the brand change:
how many articles carry a card, how many summaries are empty or thin,
and how many summaries say something about the article rather than
just starting it off.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "weixin"))

from wechat.brand import (byline_html, series_note_of, strip_title_page,  # noqa: E402
                          title_page_of)
from wechat.digest import article_digest, clip  # noqa: E402
from wechat.mdparse import parse  # noqa: E402
from wechat.posts import load_post  # noqa: E402

# Words that carry a judgement rather than a topic.
JUDGEMENT = re.compile(
    r"(结论|判断|本质|核心|关键|真正|其实|因此|所以|意味着|区别在于|"
    r"根本|必须|值得|建议|风险|边界|代价|取舍)")


def main() -> int:
    posts_dir = ROOT / "source" / "_posts"
    if not posts_dir.is_dir():
        print("找不到 source/_posts，请先跑 tools/sync-hexo.py", file=sys.stderr)
        return 1

    posts = [load_post(path, posts_dir)
             for path in sorted(posts_dir.rglob("*.md"))]

    cards = 0
    series_notes = 0
    old_empty = 0
    new_empty = 0
    old_thin = 0
    new_thin = 0
    old_judgement = 0
    new_judgement = 0
    changed = 0
    samples = []

    for post in posts:
        blocks = parse(post.body)
        byline = title_page_of(blocks)
        card = byline_html(byline)
        if card:
            cards += 1
        if series_note_of(blocks):
            series_notes += 1

        old = post.digest
        new = article_digest(blocks)

        if not old:
            old_empty += 1
        if not new:
            new_empty += 1
        if len(old) < 25:
            old_thin += 1
        if len(new) < 25:
            new_thin += 1
        if old and JUDGEMENT.search(old):
            old_judgement += 1
        if new and JUDGEMENT.search(new):
            new_judgement += 1
        if old != new:
            changed += 1
            if len(samples) < 12:
                samples.append((post.slug, old, new))

    total = len(posts)
    print("语料 {} 篇".format(total))
    print()
    print("名片卡            {:>4} 篇（{:>5.1f}%）".format(
        cards, 100.0 * cards / total))
    print("开头自述引用块    {:>4} 篇（{:>5.1f}%）".format(
        series_notes, 100.0 * series_notes / total))
    print()
    print("摘要为空          旧 {:>4}  →  新 {:>4}".format(old_empty, new_empty))
    print("摘要过短(<25字)   旧 {:>4}  →  新 {:>4}".format(old_thin, new_thin))
    print("摘要带判断词      旧 {:>4}  →  新 {:>4}".format(old_judgement, new_judgement))
    print("摘要发生变化      {:>4} 篇（{:>5.1f}%）".format(
        changed, 100.0 * changed / total))
    print()
    print("摘要改写样例：")
    for slug, old, new in samples:
        print("  * {}".format(slug))
        print("    旧: {}".format(old[:90] or "（空）"))
        print("    新: {}".format(new[:90] or "（空）"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
