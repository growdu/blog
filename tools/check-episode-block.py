#!/usr/bin/env python3
"""期号线的**渲染产物**检查。

构建完之后跑一遍：

1. 每一期母稿页的 HTML 里必须真的有期号区块，而且区块里该有的东西都在——
   期号头、钩子、播放器（还没发出去就明说）、平台链接、源码清单、
   复现命令、系列导航。

2026-11-19：系列页（``/videos/``）退休了 —— 原来还检查它是不是把每一期
都列出来，那一条检查跟着删掉。

**为什么必须有这一步**：期号区块的数据走三条不同的通道——

    母稿 front matter 的透传  →  发布索引（平台链接）  →  主题 partial

任何一环断了，页面**照常渲染**：HTTP 200、版式完整，只是那一块是空的
（或者空成「还没发出去」）。「页面能打开」不等于「区块在」，
所以这件事只能在**渲染产物**上断言，不能靠静态检查模板。

用法：

    python3 tools/check-episode-block.py [--public public]
                                         [--index source/_data/podcast_index.json]

退出码 0 = 全部通过；1 = 有问题（问题逐条打印在 stdout）。
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = REPO_ROOT / "public"
PODCAST_INDEX = REPO_ROOT / "source" / "_data" / "podcast_index.json"

#: 区块的根 class。partial 里写着，主题文件被改动时会跟着变。
BLOCK_CLASS = "episode-block"

#: 「这一期还没发出去」的说明文案（一个平台都没发）。
NOT_PUBLISHED_TEXT = "这一期的视频还没发出去"

#: 「发出去了，但还没有能嵌播放器的 B 站」的说明文案。
NOT_ON_BILIBILI_TEXT = "这一期的视频还没发到 B站"

#: B站播放器。
BILIBILI_PLAYER = "player.bilibili.com"


def page_path(public_dir, url):
    """期号页的 URL → 渲染产物里的 HTML 文件。"""
    relative = url.strip("/")
    return Path(public_dir) / relative / "index.html"


def escaped(text):
    """EJS ``<%= %>`` 的转义结果。

    partial 用 ``<%= %>`` 输出文本，EJS 会把 ``& < > " '`` 转成实体。
    所以「这段文字在页面上」要按**转义后**的样子找——否则带引号的
    复现命令永远找不到（``'alice'`` 在 HTML 里是 ``&#39;alice&#39;``）。
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def on_page(html, text):
    """这段文字在页面上吗？

    ``<%= %>`` 会转义、``<%- %>`` 不会——所以两种形态都算「在」。
    只认一种形态，就会在换一种输出方式时误报。
    """
    return text in html or escaped(text) in html


def check_episode(html, episode, previous=None, following=None):
    """一期母稿页的渲染产物该有什么。

    返回**问题清单**（空清单 = 通过）。
    """
    problems = []
    tag = episode.get("episode_label") or "EP{}".format(episode.get("episode_no"))

    if BLOCK_CLASS not in html:
        problems.append("{}: 页面里没有期号区块（{}）".format(tag, BLOCK_CLASS))
        return problems

    if tag not in html:
        problems.append("{}: 页面里没有期号头 {}".format(tag, tag))

    hook = episode.get("hook") or ""
    if hook and not on_page(html, hook):
        problems.append("{}: 页面里没有钩子".format(tag))

    published = [
        item
        for item in episode.get("platforms", []) or []
        if item.get("published_url")
    ]
    bvid = ""
    for item in published:
        match = re.search(r"BV[0-9A-Za-z]+", item["published_url"])
        if match:
            bvid = match.group(0)
            break
    if bvid:
        if BILIBILI_PLAYER not in html:
            problems.append("{}: 有已发布的 B 站链接，页面里却没有播放器".format(tag))
        elif bvid not in html:
            problems.append("{}: 播放器不是那一期的（{} 不在页面里）".format(tag, bvid))
    elif published:
        # 发到别的平台去了，只是还没有能嵌播放器的 B 站。
        if NOT_ON_BILIBILI_TEXT not in html:
            problems.append("{}: 还没发到 B 站，页面里应当明说".format(tag))
        if NOT_PUBLISHED_TEXT in html:
            problems.append("{}: 已经发到别的平台了，不该说「还没发出去」".format(tag))
    elif NOT_PUBLISHED_TEXT not in html:
        problems.append("{}: 还没发布，页面里应当明说「还没发出去」".format(tag))

    if published:
        for item in published:
            if not on_page(html, item["published_url"]):
                problems.append(
                    "{}: 平台链接没进页面（{}）".format(tag, item.get("platform_name"))
                )

    sources = episode.get("sources") or []
    if sources and not on_page(html, sources[0]):
        problems.append("{}: 源码路径清单没进页面（{}）".format(tag, sources[0]))

    repro = episode.get("repro") or []
    if repro and not on_page(html, repro[0]):
        problems.append("{}: 复现命令没进页面".format(tag))

    if (previous or following) and "episode-nav" not in html:
        problems.append("{}: 没有系列导航".format(tag))

    return problems


def check_all(index, public_dir):
    """整条期号线：逐期检查渲染产物。"""
    episodes = index.get("episodes", []) or []
    problems = []
    for position, episode in enumerate(episodes):
        previous = episodes[position - 1] if position > 0 else None
        following = (
            episodes[position + 1] if position + 1 < len(episodes) else None
        )
        path = page_path(public_dir, episode.get("url", ""))
        if not path.is_file():
            problems.append(
                "EP{}: 渲染产物不存在：{}".format(
                    episode.get("episode_no"), path
                )
            )
            continue
        html = path.read_text(encoding="utf-8", errors="replace")
        problems.extend(check_episode(html, episode, previous, following))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="检查期号区块的渲染产物")
    parser.add_argument("--public", help="渲染产物目录（默认 public/）")
    parser.add_argument("--index", help="期号索引（默认 source/_data/podcast_index.json）")
    args = parser.parse_args(argv)

    public_dir = Path(args.public) if args.public else PUBLIC_DIR
    index_path = Path(args.index) if args.index else PODCAST_INDEX

    if not index_path.is_file():
        print("期号索引不存在：{}（先跑 tools/build-podcast-index.py）".format(index_path))
        return 1
    if not public_dir.is_dir():
        print("渲染产物不存在：{}（先跑 npx hexo generate）".format(public_dir))
        return 1

    index = json.loads(index_path.read_text(encoding="utf-8"))
    problems = check_all(index, public_dir)

    if problems:
        print("期号区块检查失败：")
        for problem in problems:
            print("  - {}".format(problem))
        return 1
    print(
        "期号区块检查通过：{} 期。".format(len(index.get("episodes", []) or []))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
