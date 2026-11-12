#!/usr/bin/env python3
"""Check the drafts the pipeline wrote, straight from the local HTML.

The pipeline saves every part it renders under ``weixin/out/<slug>/`` --
one file per part.  Those files are what WeChat received, so they are
the cheapest way to verify a whole run: no API call, no quota.

Usage::

    python3 weixin/tools/check-drafts.py [out-dir]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WECHAT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WECHAT_ROOT))

from wechat.audit import check_html
from wechat.posts import CONTENT_LIMIT

TRANSITION_HEAD = re.compile(r"共 \d+ 部分，这是第 \d+ 部分")
TRANSITION_TAIL = re.compile(r"未完待续|全文完")
LINK_BLOCK = re.compile(r"参考链接")


def parts_of(slug_dir: Path) -> list:
    """The rendered parts of one article, in reading order.

    A split article has ``part-N.html`` files; a whole article has
    ``article.html``.  When both are there the parts win: the single
    file can be a leftover from before the article was split.
    """
    found = sorted(slug_dir.glob("part-*.html"),
                   key=lambda path: int(re.findall(r"\d+", path.stem)[0]))
    if found:
        return found
    single = slug_dir / "article.html"
    return [single] if single.is_file() else []


def main(argv) -> int:
    out_dir = (Path(argv[1]) if len(argv) > 1
               else WECHAT_ROOT / "out")
    state_path = out_dir / "state.json"
    ledger = json.loads(state_path.read_text(encoding="utf-8"))["posts"] if state_path.is_file() else {}

    slugs = sorted({key.split("#")[0] for key in ledger})
    problems = []
    over_length = []
    with_transition = 0
    with_links = 0
    total_parts = 0

    for slug in slugs:
        slug_dir = out_dir / slug
        if not slug_dir.is_dir():
            continue
        parts = parts_of(slug_dir)
        if not parts:
            continue
        total_parts += len(parts)
        for index, path in enumerate(parts, 1):
            html = path.read_text(encoding="utf-8")
            if len(html) > CONTENT_LIMIT:
                over_length.append((slug, index, len(html)))
            for issue in check_html(html):
                problems.append((slug, index, issue))
            if TRANSITION_HEAD.search(html):
                with_transition += 1
            if LINK_BLOCK.search(html):
                with_links += 1

    print("文章 {} 篇，渲染出的部分 {} 个".format(len(slugs), total_parts))
    print("带衔接语的部分: {}".format(with_transition))
    print("带参考链接区块的部分: {}".format(with_links))
    print("超长（>{} 字符）的部分: {}".format(CONTENT_LIMIT, len(over_length)))
    for slug, index, length in over_length[:10]:
        print("   {} 第{}部分 {} 字符".format(slug, index, length))
    print("HTML 不合规的部分: {}".format(len(problems)))
    for slug, index, issue in problems[:10]:
        print("   {} 第{}部分 {}".format(slug, index, issue))

    return 1 if (over_length or problems) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
