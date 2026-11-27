#!/usr/bin/env python3
"""把全站每一篇文章归到「赛道 + 阶段」，生成学习路径页面。

**为什么要有这个工具**
------------------
站上有 574 篇文章，分在 43 个分类里，但**没有一条覆盖全站的学习路径**：
目前只有一条 PostgreSQL 源码修炼之路（14 章）和一条高考系列。
首页的 9 个徽章只盖到 9 个分类，`数据库`(154)、`数据库深入`(94)、
`Linux`(38)、`AI`(29) 这些大头都没有入口。读者从一篇文章落地之后，
**没有任何一条通向「下一篇该读什么」的可靠路径**。

**分类规则在哪**
----------------
规则不在这个文件里，在仓库根的 ``data/learning-path.json``——那是人工策展的
部分：8 条赛道，每条赛道几个阶段，每个阶段一条条匹配规则。
改那个文件就能改路径，不用改代码。

**怎么分类**
------------
读 ``source/_posts/``（sync 之后的产物，front matter 和最终 permalink 都是对的），
对每篇文章：

1. 按赛道顺序试 ``track_match``，第一条命中的就是它的赛道；
2. 在赛道内按阶段顺序试 ``stages[].match``，第一条命中的就是它的阶段；
3. 都不中就落到 ``fallback_stage``（通常是最后一个阶段）。

**分类不出来的怎么办**
----------------------
一条都匹配不上的文章会进 ``unclassified`` 清单，脚本以非零退出码结束，
``tests/test_learning_path.py`` 也会因此失败——**漏归类必须补规则，不许悄悄
塞进兜底阶段**。

落进 ``fallback_stage`` 的文章（也就是「没有专属规则」的那些）同样被记在
``stage["fallback_posts"]`` 里，守卫测试钉住它是空的：**兜底只防崩溃，
不防偷懒**。

**产物**
------
    source/learning/index.md           总览页（赛道地图 + 从哪开始）
    source/learning/<track>/index.md   每条赛道一页（阶段表 + 全部文章）
    source/_data/learning.json         给首页/主题用的结构化数据

用法：

    python3 tools/build-learning-path.py            # 生成
    python3 tools/build-learning-path.py --check    # 只检查，不写文件
    python3 tools/build-learning-path.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from site_root import permalink as _permalink  # noqa: E402
from site_root import rooted_path as _rooted_path  # noqa: E402
from site_root import absolute_url as _absolute_url  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = REPO_ROOT / "source" / "_posts"
DOCS_DIR = REPO_ROOT / "docs"
RULES_FILE = REPO_ROOT / "data" / "learning-path.json"
OUT_DIR = REPO_ROOT / "source" / "learning"
DATA_OUT = REPO_ROOT / "source" / "_data" / "learning.json"

FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)

#: ``tools/sync-hexo.py`` 里的同名集合：这些目录整棵不进产物。
#: 两处必须一致 —— 少一个，多出来的文章就成了「没归类」的噪声。
EXCLUDED_DIR_NAMES = frozenset({
    "tests", "test", "fixtures", "plans", "pipeline",
    "build", "out", "_staging", "frames",
})

#: 文件名开头的编号（``ai/03_AI怎么读懂文字``、``.../07-btree-index``）。
#: 带编号的说明它自己是一条有序的系列，阶段内要按编号排，不能按时间排。
LEADING_NUMBER = re.compile(r"^(?:.*/)?(\d+)(?:[-_]|$)")


def _load_video_pages():
    """按路径加载 ``tools/build-video-pages.py``。

    ``tools/`` 不是包，所以走文件加载。模块顶层没有副作用
    （生成逻辑在 ``main()`` 里），import 不会写文件。
    """
    import importlib.util

    path = REPO_ROOT / "tools" / "build-video-pages.py"
    spec = importlib.util.spec_from_file_location("build_video_pages", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sort_key(post: dict):
    """阶段内的排序键。

    **带编号的系列在前，按编号排；其余按时间由早到晚。**

    为什么要分开：站内不少系列是 ``ai/01_``、``ai/02_`` 这样带前缀编号的，
    编号就是作者自己定的顺序（同一批文章常常是同一天写的，按时间排会退化成
    按字典序排，``10_`` 会排在 ``2_`` 前面）。而没有编号的文章，早的一般是
    更基础的。
    """
    name = post["rel"].rsplit("/", 1)[-1]
    m = LEADING_NUMBER.match(name)
    if m:
        return (0, int(m.group(1)), post["date"], post["rel"])
    return (1, 0, post["date"], post["rel"])


# --- 读文章 -----------------------------------------------------------------


def _load_sync():
    """按路径加载 ``tools/sync-hexo.py``。

    借它的 ``_front_matter_title()``：**解 YAML 标题只有一份实现**。
    sync 把标题写成 ``title: "...数据库\\"脱颖而出\\""``（引号是 YAML 转义过的），
    生成器必须用同一个解析器把它还原成 ``…"脱颖而出"``。
    自己另写一份 ``.strip('"')`` 就会漏掉转义 —— 末尾多出一个孤零零的反斜杠，
    Markdown 链接就解析不出来了（整行退化成纯文本，页面上那条文章点不开）。
    """
    import importlib.util

    path = REPO_ROOT / "tools" / "sync-hexo.py"
    spec = importlib.util.spec_from_file_location("sync_hexo", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SYNC_MODULE = None


def _front_matter_title(text: str) -> str:
    """取 front matter 里的标题（YAML 转义由 sync 的解析器负责）。"""
    global _SYNC_MODULE
    if _SYNC_MODULE is None:
        _SYNC_MODULE = _load_sync()
    return _SYNC_MODULE._front_matter_title(text) or ""


def _fm_list(fm: str, key: str) -> list[str]:
    """读 front matter 里的列表字段（``- a`` 或 ``a, b`` 两种写法都认）。"""
    block = re.search(r"^%s:\s*\n((?:\s*-\s*.+\n)+)" % re.escape(key), fm, re.M)
    if block:
        return [line.strip().lstrip("-").strip().strip('"\'')
                for line in block.group(1).splitlines() if line.strip()]
    scalar = re.search(r"^%s:\s*(.+)$" % re.escape(key), fm, re.M)
    if not scalar:
        return []
    return [x.strip().strip('"\'') for x in scalar.group(1).split(",") if x.strip()]


def read_posts(posts_dir: Path) -> list[dict]:
    """读 ``source/_posts/`` 下的全部文章。

    **为什么读 source/_posts/ 而不是 docs/**：sync 之后这里已经有了
    正确的 front matter、正确的扁平化路径和正确的日期——也就是正确的
    permalink。要在这儿重算一遍 sync 的那套逻辑（git 日期、路径扁平化）
    只会造出第二份真相。

    **``.html`` 的文章也在内**：站上有 3 篇是 HTML 写的（``source-tracks/postgresql/L7-logical-replication/ddl同步架构-html``、
    ``source-tracks/postgresql/logical-replication/sqlserver/sqlserver逻辑复制ddl-html``、``source-tracks/life/L4-hometown/家中对联-html``）。
    它们同样是文章，同样该出现在学习路径里 —— 只收 ``*.md`` 的话，
    学习路径就漏了它们。
    """
    posts = []
    for path in sorted(posts_dir.rglob("*")):
        if path.suffix.lower() not in (".md", ".html", ".htm"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        m = FRONT_MATTER.match(text)
        fm = m.group(1) if m else ""
        title = _front_matter_title(fm) if fm else ""
        if not title:
            # HTML 文章的标题在 <title> 里（sync 把 front matter 剥了）。
            hm = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
            if hm:
                title = re.sub(r"<[^>]+>", "", hm.group(1)).strip()
        date = ""
        dm = re.search(r"^date:\s*(.+)$", fm, re.M)
        if dm:
            date = dm.group(1).strip()
        rel = path.relative_to(posts_dir).with_suffix("")
        rel = str(rel).replace(os.sep, "/")
        posts.append({
            "rel": rel,
            "title": title or path.stem,
            "date": date,
            "categories": _fm_list(fm, "categories"),
            "tags": _fm_list(fm, "tags"),
            # permalink 用 sync 的那套：日期 + 扁平化路径，带挂载点前缀。
            "url": _permalink(date, rel),
        })
    return posts


def docs_corpus(docs_dir: Path = DOCS_DIR) -> list[dict]:
    """``docs/`` 里的全部文章，按 sync 的展平规则算出它在 ``source/_posts/`` 里的路径。

    **为什么要有第二个语料来源**：生成器读的是 ``source/_posts/``——那是构建
    产物，CI 的 ``site-guard``（不构建产物）里根本没有。而「有没有文章漏掉
    归类」这个问题必须**在没有构建产物的地方也能问**，否则 CI 拦不住它：
    新加一篇文章、忘了写规则，它就悄悄从学习路径里消失了。

    所以这里按 sync 的展平规则（``index.md`` → ``父目录/包名.md``、
    ``.html`` 加 ``-html`` 后缀、排除工程目录）从 ``docs/`` 直接算出路径。

    **和 sync 的展平规则重复了**：是的，这是有意付的重复——重复的是**路径
    展平**（几行），换来的是「构建产物」和「源码树」两条独立的语料。
    :func:`corpus_mismatch` 在构建时把两者对上，对不上就报错。
    """
    posts = []
    for root, dirs, files in os.walk(docs_dir):
        dirs[:] = [d for d in dirs
                   if not d.startswith(".") and d.lower() not in EXCLUDED_DIR_NAMES]
        for name in sorted(files):
            if name.startswith("."):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in (".md", ".html", ".htm"):
                continue
            if name in ("_index.md", "_index.html", "_index.htm"):
                continue
            rel = os.path.relpath(os.path.join(root, name), docs_dir)
            fdir = os.path.dirname(rel)
            if name == "index.md":
                # sync: docs/<包>/index.md → source/_posts/<父>/<包>.md
                slug = os.path.basename(fdir)
                parent = os.path.dirname(fdir)
                flat = os.path.join(parent, slug) if parent and parent != "." else slug
            elif ext in (".html", ".htm"):
                # sync: 展平时给 HTML 文章的文件名加 -html 后缀
                slug = os.path.splitext(name)[0]
                if not slug.endswith("-html"):
                    slug += "-html"
                flat = os.path.join(fdir, slug) if fdir and fdir != "." else slug
            else:
                # sync 落盘时保留文件名，读的时候去掉扩展名
                stem = os.path.splitext(name)[0]
                flat = os.path.join(fdir, stem) if fdir and fdir != "." else stem
            posts.append({
                "rel": flat.replace(os.sep, "/"),
                "title": os.path.splitext(name)[0],
                "date": "",
                "categories": [],
                "tags": [],
                "url": "",
            })
    posts.sort(key=lambda p: p["rel"])
    return posts


def video_corpus() -> list[dict]:
    """AIV 的视频内容单元（``source/_posts/video/<期号>.md``）。

    这些不是 ``docs/`` 里的文章，是 ``tools/build-video-pages.py`` 从
    ``aiv/字幕-*.md`` 生成的——但它们**同样会发布成文章**，同样该在学习路径里
    （6 期讲的是行锁、并行解码、WAL 顺序、CSN 全序、结构化 DDL、并行 apply，
    都在数据库内核这条线的中段）。

    期号从 ``aiv/pipeline/Makefile`` 读——那是期号与母稿的唯一映射，
    直接复用 ``build-video-pages.py`` 的读法，不在这里另建一份。
    """
    try:
        video_pages = _load_video_pages()
    except Exception as exc:  # noqa: BLE001 —— 读不到就当没有视频单元
        print("读不到 aiv 的期号登记（%s），视频内容单元没进语料" % exc,
              file=sys.stderr)
        return []
    posts = []
    for episode in video_pages.read_episode_scripts():
        posts.append({
            "rel": "video/%s" % episode,
            "title": episode,
            "date": "",
            "categories": ["视频"],
            "tags": ["视频"],
            "url": "",
        })
    return posts


def source_corpus(docs_dir: Path = DOCS_DIR) -> list[dict]:
    """不构建产物也能拿到的全站语料（``docs/`` 的文章 + AIV 的视频单元）。"""
    return docs_corpus(docs_dir) + video_corpus()


def corpus_mismatch(posts_dir: Path = POSTS_DIR, docs_dir: Path = DOCS_DIR) -> list[str]:
    """``source/_posts/`` 与源码树的语料差异（双向）。

    空列表 = 两边一致。这是**两套展平规则**唯一的交叉验证点：
    ``source_corpus()`` 复制了 sync 的展平逻辑，复制错了这里就会响。
    """
    built = {p["rel"] for p in read_posts(posts_dir)}
    source = {p["rel"] for p in source_corpus(docs_dir)}
    return (["构建产物里多出来的：" + r for r in sorted(built - source)]
            + ["源码树里没进产物的：" + r for r in sorted(source - built)])



# --- 匹配规则 ----------------------------------------------------------------


def match_rule(rule: dict, post: dict) -> bool:
    """一条规则对一篇文章是否成立。

    规则的形式：

    ==========================  ==========================================
    键                          含义
    ==========================  ==========================================
    ``path_prefix``             路径以此开头
    ``path_regex``              路径匹配这个正则（``re.search``）
    ``path_exact``              路径完全等于
    ``category``                分类名完全等于（任一分类命中即可）
    ``tag``                     标签名完全等于
    ``title_contains``          标题含这个子串
    ``any``                     里面的规则**有一条**成立即可
    ``all``                     里面的规则**全部**成立
    ``catch_all``               无条件成立（兜底用）
    ==========================  ==========================================
    """
    if rule.get("catch_all"):
        return True
    if "path_prefix" in rule:
        if not post["rel"].startswith(rule["path_prefix"]):
            return False
    if "path_regex" in rule:
        if not re.search(rule["path_regex"], post["rel"]):
            return False
    if "path_exact" in rule:
        if post["rel"] != rule["path_exact"]:
            return False
    if "category" in rule:
        if rule["category"] not in post["categories"]:
            return False
    if "tag" in rule:
        if rule["tag"] not in post["tags"]:
            return False
    if "title_contains" in rule:
        if rule["title_contains"] not in post["title"]:
            return False
    if "any" in rule:
        if not any(match_rule(r, post) for r in rule["any"]):
            return False
    if "all" in rule:
        if not all(match_rule(r, post) for r in rule["all"]):
            return False
    return True


def match_any(rules: list[dict], post: dict) -> bool:
    return any(match_rule(r, post) for r in rules or [])


# --- 分类 --------------------------------------------------------------------


def classify(posts: list[dict], rules: dict) -> tuple[list[dict], list[dict]]:
    """把每篇文章分到「赛道 + 阶段」。

    返回 ``(tracks, unclassified)``：``tracks`` 是每个赛道的阶段列表，
    ``unclassified`` 是没能归到任何赛道的文章。
    """
    tracks = []
    used = set()

    for spec in rules["tracks"]:
        # 先定赛道：这一条赛道管的文章是哪些。**必须先判赛道再判阶段**——
        # 否则赛道里的兜底阶段（catch_all）会把后面几条赛道的文章也吞掉。
        members = [p for p in posts
                   if p["rel"] not in used
                   and match_any(spec.get("track_match"), p)]
        for p in members:
            used.add(p["rel"])

        stages = []
        # 阶段之间**互斥**：一篇文章只落一个阶段。阶段按顺序贪心分配，
        # 先命中先占位 —— 所以规则要按「具体 → 笼统」写。
        assigned = set()
        for stage in spec["stages"]:
            hit = [p for p in members
                   if p["rel"] not in assigned
                   and match_any(stage.get("match"), p)]
            for p in hit:
                assigned.add(p["rel"])
            hit.sort(key=sort_key)
            stages.append({
                "id": stage["id"],
                "title": stage["title"],
                "goal": stage.get("goal", ""),
                "posts": hit,
                # 这篇文章是靠兜底阶段进来的（没写专属规则）——见下面的注释。
                "fallback_posts": [],
            })

        # 兜底阶段：这条赛道里一条阶段规则都没命中的文章 → 落这儿。
        #
        # **兜底只是防崩溃，不是防偷懒**：文章落进兜底，意味着它没有专属
        # 规则。``tests/test_learning_path.py`` 因此钉住「兜底吸收 0 篇」
        # —— 加了新文章就得给它写规则，不许靠兜底蒙混过关。
        fallback_id = spec.get("fallback_stage") or stages[-1]["id"]
        for stage in stages:
            if stage["id"] != fallback_id:
                continue
            leftover = [p for p in members if p["rel"] not in assigned]
            leftover.sort(key=sort_key)
            stage["posts"].extend(leftover)
            stage["fallback_posts"] = [p["rel"] for p in leftover]
            for p in leftover:
                assigned.add(p["rel"])

        tracks.append({
            "id": spec["id"],
            # 老赛道 id。赛道改过名字之后，老地址要还能进（§8.3）。
            "aliases": spec.get("aliases", []),
            "title": spec["title"],
            "icon": spec.get("icon", ""),
            "summary": spec.get("summary", ""),
            "audience": spec.get("audience", ""),
            "goal": spec.get("goal", ""),
            "stages": stages,
            "count": sum(len(s["posts"]) for s in stages),
        })

    unclassified = [p for p in posts if p["rel"] not in used]
    return tracks, unclassified


# --- 渲染 --------------------------------------------------------------------


def _md_escape(text: str) -> str:
    """把链接文字里会被 Markdown 当成语法的字符转义掉。

    链接文字本身还是 Markdown：标题里要是有 ``[``、``]``、``(``、``)``，
    不转义就会被重新解析一遍。真实的坑有两个：

    * 标题以 ``\\`` 结尾时，marked 会把紧跟其后的 ``]`` 一起吞进链接文字，
      整个 ``[...](...)`` 不再是链接 —— 渲染出来是一行纯文本。
    * 标题里自带 Markdown 链接（有一篇的标题是
      ``[kali](https://so.csdn.net/...)搭建docker``），不转义就会渲染出
      **嵌套的 ``<a>``** —— 那是非法 HTML，浏览器会把里层的链接提出来，
      外层的文章链接就断了。
    """
    out = text.replace("\\", "\\\\")
    for ch in "[]()`*":
        out = out.replace(ch, "\\" + ch)
    return out


def build_data(tracks: list[dict], total: int) -> dict:
    """首页面板和总览页用的数据（写进 ``source/_data/learning.json``）。

    单独抽出来是为了能直接测：首页面板是照着这份数据画的，
    数据缺一项（图标、简介、链接），首页就少一块。
    """
    return {
        "total": total,
        "tracks": [{
            "id": t["id"], "title": t["title"], "icon": t["icon"],
            "summary": t["summary"], "count": t["count"],
            "url": _rooted_path("/learning/%s/" % t["id"]),
            "stages": [{
                "id": s["id"], "title": s["title"], "goal": s["goal"],
                "count": len(s["posts"]),
                "posts": [{"title": p["title"], "url": p["url"]} for p in s["posts"]],
            } for s in t["stages"]],
        } for t in tracks],
    }


# 「已经在写数据库内核」那一格指向哪条赛道的哪个阶段。
# 这里写的是**查表用的 id**，不是地址：赛道改名、阶段重排之后，
# 这一格跟着规则表走，不会指向一个已经不存在的页面。
DEEP_DIVE_TRACK = "postgresql"
DEEP_DIVE_STAGE = "L7"


def _deep_dive_cell(tracks: list[dict]) -> str:
    track = next((t for t in tracks if t["id"] == DEEP_DIVE_TRACK), None)
    if track is None:
        return "从下面挑一条赛道"
    stage = next((s for s in track["stages"] if s["id"] == DEEP_DIVE_STAGE), None)
    url = _rooted_path("/learning/%s/" % track["id"])
    label = stage["title"] if stage else DEEP_DIVE_STAGE
    return "直接进 [%s](%s) 的 **%s**" % (track["title"], url, label)


def render_overview(tracks: list[dict], total: int) -> str:
    # 站内链接必须带挂载点前缀（主站 /，镜像站 /blog）——
    # 写死的 /learning/ 在镜像站上会 404。参见 tools/site_root.py。
    lines = [
        "---",
        'title: "学习路径"',
        "date: 2026-01-01 00:00:00",
        "type: learning",
        "layout: learning",
        "---",
        "",
        "# 学习路径",
        "",
        "全站 %d 篇文章，按**赛道**和**阶段**排成了一条可以从头读到尾的路。" % total,
        "每条赛道都说明了：读它之前该会什么、读完能做什么、下一篇读哪篇。",
        "",
        "**不是分类，是顺序。** 文章按主题分了类（分类页 2026-11-19 整套退休了，",
        "那一层只留在文章自己的 front matter 里），那是**检索**用的；",
        "这里是**导航**用的 —— 告诉你先读什么。",
        "",
        "## 从哪开始",
        "",
        "| 你是谁 | 从这里进 |",
        "| --- | --- |",
        "| 只想找一篇能马上用的文章 | [归档页](%s)，按时间翻 |" % _rooted_path("/archives/"),
        "| 想系统学一门技术 | 下面挑一条赛道，从它的 **L1** 开始 |",
        "| 已经在写数据库内核 | %s |" % _deep_dive_cell(tracks),
        "| 只想看看这个站长什么样 | [首页](%s) |" % _rooted_path("/"),
        "",
        "## 赛道地图",
        "",
    ]
    for t in tracks:
        lines.append("### [%s](%s) · %d 篇" % (
            t["title"], _rooted_path("/learning/%s/" % t["id"]), t["count"]))
        lines.append("")
        lines.append("%s" % t["summary"])
        lines.append("")
        lines.append("| 阶段 | 主题 | 文章数 |")
        lines.append("| --- | --- | ---: |")
        for s in t["stages"]:
            lines.append("| **%s** | %s | %d |" % (s["id"], s["title"], len(s["posts"])))
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("这份路径由 `tools/build-learning-path.py` 生成，")
    lines.append("分类规则在仓库根的 `data/learning-path.json`。")
    lines.append("加了新文章却没归类的话，CI 会红。")
    lines.append("")
    return "\n".join(lines)


def render_track(track: dict) -> str:
    lines = [
        "---",
        'title: "%s · 学习路径"' % track["title"],
        "date: 2026-01-01 00:00:00",
        "type: learning",
        "layout: learning",
        "---",
        "",
        "# %s" % track["title"],
        "",
        "> %s" % track["summary"],
        "",
        "**适合谁**：%s" % track["audience"],
        "",
        "**读完能做什么**：%s" % track["goal"],
        "",
        "[← 回到学习路径总览](%s)" % _rooted_path("/learning/"),
        "",
        "## 阶段一览",
        "",
        "| 阶段 | 主题 | 文章数 | 读完这一阶段，你该能做到 |",
        "| --- | --- | ---: | --- |",
    ]
    for s in track["stages"]:
        lines.append("| **%s** | %s | %d | %s |" % (
            s["id"], s["title"], len(s["posts"]), s["goal"]))
    lines.append("")

    for s in track["stages"]:
        if not s["posts"]:
            continue
        lines.append("## %s · %s" % (s["id"], s["title"]))
        lines.append("")
        lines.append("%s" % s["goal"])
        lines.append("")
        for p in s["posts"]:
            cats = " / ".join(p["categories"][:2])
            lines.append("- [%s](%s) — %s" % (
                _md_escape(p["title"]), p["url"], cats))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("[← 回到学习路径总览](%s)" % _rooted_path("/learning/"))
    lines.append("")
    return "\n".join(lines)


def render_alias(alias: str, track: dict) -> str:
    """老赛道地址的别名页：老链接还得能进。

    赛道改过名字之后，老的 ``/learning/<老 id>/`` 不能变成 404。
    这一页是一张跳转页：

    * ``meta refresh`` —— 浏览器一跳就过去；
    * ``canonical`` —— 告诉搜索引擎「正身在那边」，别把老地址当正本；
    * 正文里再留一个普通链接 —— meta refresh 被策略挡掉时的退路
      （也方便没跳过去的读者自己点）。

    canonical 写的是**绝对地址**，且不带挂载点前缀 —— 绝对地址由
    ``config.url`` 拼出来，而 ``config.url`` 里已经有挂载点了
    （镜像站是 ``https://growdu.github.io/blog``）。参见 tools/site_root.py。
    """
    target_path = "/learning/%s/" % track["id"]
    target_url = _rooted_path(target_path)
    canonical = _absolute_url(target_path)
    lines = [
        "---",
        'title: "%s（赛道已改名）"' % track["title"],
        "date: 2026-01-01 00:00:00",
        "type: learning",
        "layout: learning",
        'canonical: "%s"' % canonical,
        "---",
        "",
        '<meta http-equiv="refresh" content="0; url=%s">' % target_url,
        "",
        "# %s" % track["title"],
        "",
        "这条赛道改过名字了：老地址 `/learning/%s/` 已经并到 **%s**。"
        % (alias, track["title"]),
        "",
        "[继续阅读 →](%s)" % target_url,
        "",
    ]
    return "\n".join(lines)


# --- 主流程 ------------------------------------------------------------------


def build(posts_dir: Path = POSTS_DIR, rules_file: Path = RULES_FILE) -> dict:
    """跑一遍分类，返回结果字典。"""
    rules = json.loads(rules_file.read_text(encoding="utf-8"))
    posts = read_posts(posts_dir)
    tracks, unclassified = classify(posts, rules)
    return {"posts": posts, "tracks": tracks, "unclassified": unclassified,
            "total": len(posts)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生成学习路径页面")
    ap.add_argument("--check", action="store_true",
                    help="只检查（不写文件）：有文章没归类就以非零码退出")
    ap.add_argument("--json", metavar="FILE", help="把结果写成 JSON")
    args = ap.parse_args(argv)

    if not POSTS_DIR.is_dir():
        raise SystemExit(
            "没有 %s —— 先跑 python3 tools/sync-hexo.py（学习路径读的是 sync "
            "之后的产物，front matter 和 permalink 都在那儿）" % POSTS_DIR)

    result = build()
    tracks = result["tracks"]
    total = result["total"]

    # 两套语料（docs/ 和构建产物）必须一致——不一致说明展平规则漂了，
    # 那学习路径覆盖的就是另一批文章。
    mismatch = corpus_mismatch()
    if mismatch:
        print("语料对不上：docs/ 和 source/_posts/ 不是同一批文章", file=sys.stderr)
        for line in mismatch[:20]:
            print("  " + line, file=sys.stderr)
        return 1

    print("文章总数：%d" % total)
    for t in tracks:
        stages = " ".join("%s:%d" % (s["id"], len(s["posts"])) for s in t["stages"])
        print("  %-16s %3d 篇   %s" % (t["id"], t["count"], stages))

    # 靠兜底阶段进来的文章 = 没有专属规则的文章。守卫测试钉住它是空的，
    # 这里报出来，是为了让人在本地就能看见「哪几篇还没写规则」。
    via_fallback = [
        rel
        for t in tracks for s in t["stages"]
        for rel in s.get("fallback_posts", [])
    ]
    if via_fallback:
        print("\n靠兜底进来的 %d 篇（得给它写规则）：" % len(via_fallback))
        for rel in via_fallback:
            print("  " + rel)

    if result["unclassified"]:
        print("\n有 %d 篇文章没归到任何赛道 —— 给它们加规则："
              % len(result["unclassified"]), file=sys.stderr)
        for p in result["unclassified"]:
            print("  %s  (%s)" % (p["rel"], p["title"][:40]), file=sys.stderr)
        return 1

    covered = sum(t["count"] for t in tracks)
    print("\n覆盖：%d / %d" % (covered, total))
    if covered != total:
        print("覆盖不全！", file=sys.stderr)
        return 1

    if args.json:
        Path(args.json).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("结果已写到 %s" % args.json)

    if args.check:
        print("（--check：没有写文件）")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "index.md").write_text(render_overview(tracks, total), encoding="utf-8")
    for t in tracks:
        d = OUT_DIR / t["id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.md").write_text(render_track(t), encoding="utf-8")
    # 别名页：老赛道地址照旧能进（§8.3）。
    aliases = []
    for t in tracks:
        for alias in t.get("aliases", []):
            d = OUT_DIR / alias
            d.mkdir(parents=True, exist_ok=True)
            (d / "index.md").write_text(render_alias(alias, t), encoding="utf-8")
            aliases.append(alias)
    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    DATA_OUT.write_text(json.dumps(build_data(tracks, total),
                                   ensure_ascii=False, indent=2), encoding="utf-8")

    print("生成：%s/index.md + %d 个赛道页 + %s"
          % (OUT_DIR, len(tracks), DATA_OUT))
    if aliases:
        print("别名页：%s" % "、".join(aliases))
    return 0


if __name__ == "__main__":
    sys.exit(main())
