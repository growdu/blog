#!/usr/bin/env python3
"""把 AIV 的口播稿变成站上的视频页。

**母稿是 ``aiv/字幕-<主题>.md``**——那一行一句的口播稿与字幕表，是这条线
入库的唯一真相；画面契约在 ``aiv/contracts/<期号>.json``，发布状态在
``publish/outbox/*.json``。

生成的是**内容单元**（``source/_posts/video/<期号>.md``），不是页面：
视频和文章走同一套渲染、同一个 permalink、同一条「已发布到」通道。
这也补上了规格 §9.3 说的那句话——站点是内容谱系的根，而视频此前
在站上零呈现（video widget 关着、菜单无入口）。

期号与口播稿的对应关系读的是 ``aiv/pipeline/Makefile``（那里的
``ifeq ($(EP),<期号>)`` 登记），**不另建一份映射表**——两个地方各记一遍
就会漂。

生成物是派生产物：``source/`` 不入库，每次构建现生成（与 ``sync-hexo.py``
的产物一个待遇）。

用法：

    python3 tools/build-video-pages.py

产物：

    source/_posts/video/<期号>.md    每期一个内容单元

**合集页（``source/videos/index.md``）2026-11-19 退休了**：那一页是
**系列页**，按期号排，每期带钩子、时长与完整版（母稿页）的链接。它跟
生成它的工具（``tools/build-series-page.py``）一起删掉了 —— 现在没有
任何工具写合集页，一个文件一个写入者的规矩靠「零个写入者」守住。
期号线本身还在：文章页顶部的期号区块（上一期 / 下一期）和 RSS 订阅
（``/feed.xml``）都不依赖那一页。
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AIV_ROOT = REPO_ROOT / "aiv"
MAKEFILE = AIV_ROOT / "pipeline" / "Makefile"
CONTRACTS_DIR = AIV_ROOT / "contracts"
OUTBOX_DIR = REPO_ROOT / "publish" / "outbox"
POSTS_DIR = REPO_ROOT / "source" / "_posts"

CATEGORY = "视频"
AUTHOR = "growdu"

# Makefile 里的登记：ifeq ($(EP),<期号>) / SCRIPT := $(ROOT)/字幕-<主题>.md
_EP_RE = re.compile(r"ifeq\s*\(\$\(EP\),\s*([A-Za-z0-9_-]+)\)")
_SCRIPT_RE = re.compile(r"^\s*SCRIPT\s*:=\s*\$\(ROOT\)/(.+?)\s*$", re.MULTILINE)


def read_episode_scripts():
    """Map every episode to its script file, as registered in the Makefile."""
    text = MAKEFILE.read_text(encoding="utf-8")
    episodes = {}
    for match in _EP_RE.finditer(text):
        episode = match.group(1)
        tail = text[match.end():]
        script = _SCRIPT_RE.search(tail)
        if script:
            episodes[episode] = script.group(1)
    if not episodes:
        raise SystemExit(
            f"在 {MAKEFILE} 里没读到任何期号登记——Makefile 的格式变了？"
        )
    return episodes


def parse_front_matter(text):
    """Split the flat ``key: value`` front matter a script file carries.

    The format is the same one ``sync-hexo.py`` writes: flat scalars only.
    """
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not match:
        return {}, text
    fields = {}
    for line in match.group(1).split("\n"):
        if ":" not in line or line.startswith(" "):
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip('"')
    return fields, match.group(2)


def read_outbox():
    """Every publish snapshot, keyed by (content_id, platform)."""
    records = {}
    if not OUTBOX_DIR.is_dir():
        return records
    for path in sorted(OUTBOX_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        content_id = data.get("content_id")
        platform = data.get("platform")
        if isinstance(content_id, str) and isinstance(platform, str):
            records[(content_id, platform)] = data
    return records


def permalink(date_text, slug):
    """The site's permalink for one content unit.

    Mirrors the site's permalink rule (``:year/:month/:day/:title/``): the
    date comes from the front matter, the title part is the path under
    ``source/_posts``.
    """
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", date_text or "")
    if not match:
        # 没有日期就没有年/月/日，但路径形状不变。
        return f"/{slug}/"
    year, month, day = match.groups()
    return f"/{year}/{month}/{day}/{slug}/"


def rewrite_links(body, script_to_permalink):
    """Point sibling episode links at their site pages.

    ``./字幕-结构化DDL.md`` becomes the permalink of that episode's page.
    Links that have no published counterpart (the topic library, the module
    READMEs) keep their text but lose the link — a dead link on the site is
    worse than plain text.
    """
    def replace(match):
        target = match.group(1)
        url = script_to_permalink.get(target)
        if url:
            return f"]({url})"
        return "]"

    return re.sub(r"\]\(([^)]+)\)", replace, body)


def read_publish_meta(episode):
    """这一期的发布元数据（``aiv/publish/<EP>.json``）。

    **它是母版标题的出处**（视频发布契约 §4.3：「这一期的标题（母版标题）。
    各平台文案默认从这里派生」）。画面契约 ``aiv/contracts/<EP>.json`` 里的
    title 是**画面标题**，两者不必相同——EP01 的画面标题是「openGauss 的并行
    逻辑解码」，母版标题是「PostgreSQL 18 并行逻辑解码」。

    所以站上的视频页用母版标题：那一期在 B站/视频号叫什么，站内就叫什么。
    """
    path = AIV_ROOT / "publish" / f"{episode}.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def build_page(episode, script_path, outbox):
    """Build one content unit. Returns ``(slug, markdown)``."""
    script_file = AIV_ROOT / script_path
    fields, body = parse_front_matter(script_file.read_text(encoding="utf-8"))

    contract_file = CONTRACTS_DIR / f"{episode}.json"
    contract = {}
    if contract_file.is_file():
        contract = json.loads(contract_file.read_text(encoding="utf-8"))

    meta = read_publish_meta(episode)
    # 母版标题优先：那一期在平台上叫什么，站内就叫什么。
    title = meta.get("title") or contract.get("title") or fields.get("title") or episode
    date = fields.get("date") or "1970-01-01"
    description = meta.get("description") or ""

    platforms = sorted(
        platform
        for (content_id, platform) in outbox
        if content_id == episode
    )

    front_matter = [
        "---",
        f'title: "{title}"',
        f"date: {date}",
        f"author: {AUTHOR}",
        "categories:",
        f"  - {CATEGORY}",
        "tags:",
        f"  - {CATEGORY}",
        f"  - {episode}",
        "kind: video",
    ]
    if platforms:
        front_matter.append("platforms:")
        for platform in platforms:
            front_matter.append(f"  - {platform}")
    front_matter.append("---")

    return title, date, "\n".join(front_matter) + "\n\n" + body.lstrip("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="build-video-pages",
        description="把 AIV 的口播稿生成成站上的视频内容单元。",
    )
    parser.parse_args(argv)

    episodes = read_episode_scripts()
    outbox = read_outbox()

    # 先算出每期口播稿对应的站内地址：兄弟期之间的链接要指向这些地址。
    script_to_permalink = {}
    episode_meta = {}
    for episode, script_path in sorted(episodes.items()):
        script_file = AIV_ROOT / script_path
        if not script_file.is_file():
            print(f"跳过 {episode}：找不到 {script_file}", file=sys.stderr)
            continue
        fields, _body = parse_front_matter(script_file.read_text(encoding="utf-8"))
        date = fields.get("date") or "1970-01-01"
        url = permalink(date, f"video/{episode}")
        script_to_permalink[f"./{script_path}"] = url
        episode_meta[episode] = (script_path, date, url)

    posts_dir = POSTS_DIR / "video"
    posts_dir.mkdir(parents=True, exist_ok=True)

    pages = []
    for episode, (script_path, date, url) in sorted(episode_meta.items()):
        title, _date, markdown = build_page(episode, script_path, outbox)
        body_start = markdown.index("---", 4) + 3
        front, body = markdown[:body_start], markdown[body_start:]
        body = rewrite_links(body, script_to_permalink)
        path = posts_dir / f"{episode}.md"
        path.write_text(front + body, encoding="utf-8")

        platforms = sorted(
            platform for (content_id, platform) in outbox if content_id == episode
        )
        pages.append((episode, title, date, url, platforms))

    print("生成视频内容单元 {} 个：{}".format(
        len(pages), "、".join(episode for episode, *_ in pages)
    ))
    print("合集页（系列页）2026-11-19 退休了 —— 没有工具写它")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
