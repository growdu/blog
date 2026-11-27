#!/usr/bin/env python3
"""把全站文章按**我走过的顺序**排成一条成长路线，生成 /journey/ 页面。

**为什么要有这个工具**
--------------------
``/learning/`` 已经把全站文章排成了 11 条赛道（按学科），但赛道是**并排**的，
读者还是得自己拼顺序 —— 「我现在该先学什么」。这条工具排的是**另一根轴**：
我自己的成长顺序，从大学毕业、刚工作时的语言入门，一直到现在的内核源码。

**为什么顺序不是我拍脑袋定的**
------------------------------
分期不是我事后编的顺序，是**从我的提交记录里量出来的**：每一篇文章的首次
提交日期固化在 ``data/date-overrides.json``（591 条），生成器按「期包含的
阶段」把这些文章的年份统计出来。于是「这条路的顺序」是**可验证的事实**，
不是一句自我介绍。

**分期只引用现有阶段，不新增分类**
---------------------------------
``data/journey.json`` 里的每一期写的是 ``"<赛道 id>/<阶段 id>"``，
阶段标题、阶段目标、文章清单全部来自 ``data/learning-path.json`` ——
不复制，复制就会多一处会漂移的地方。

**语料从哪来**
------------
读 ``source/_posts/``（sync 之后的产物，front matter 和最终 permalink 都是对的）。
期页要链到具体文章，需要**真实标题**和**真实 permalink**；``docs/`` 那边
只有文件名。

归类也复用 ``tools/build-learning-path.py`` 的 ``read_posts()`` / ``classify()``
—— 归类的唯一真相是规则表，不在这里重写一遍。

**口径：只算 docs/ 里的 591 篇**
-------------------------------
站上另外 6 期视频内容单元住在 ``source/_posts/video/`` 下，**不在 docs/ 里**，
没有提交日期。它们在规则表里是有归属的（postgresql 的 L4 / L5 / L7），
所以赛道页上照旧有，但期页的篇数不包含它们 —— 页面上把这个口径写出来，
否则读者会数出 597 和 591 对不上。

**产物**
------
    source/journey/index.md            总览页（年份矩阵 + 五期主线 + 选修）
    source/journey/<期 id>/index.md    每期一页（p1…p5）
    source/journey/optional/index.md   选修线一页

用法：
    python3 tools/build-journey.py            # 生成
    python3 tools/build-journey.py --check    # 只检查，不写文件
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from site_root import rooted_path as _rooted_path  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = REPO_ROOT / "source" / "_posts"
RULES_FILE = REPO_ROOT / "data" / "learning-path.json"
JOURNEY_FILE = REPO_ROOT / "data" / "journey.json"
DATES_FILE = REPO_ROOT / "data" / "date-overrides.json"
OUT_DIR = REPO_ROOT / "source" / "journey"

#: 视频内容单元（``source/_posts/video/<期号>.md``）。它们不是 docs/ 里的
#: 文章，没有提交日期 —— 期页的篇数不计入它们。
VIDEO_PREFIX = "video/"

#: 链接检查用的正则：只取 ``[文字](地址)`` 里的地址部分。
LINK_RE = re.compile(r"\]\(([^)\s]+)")


def load_module(path: Path, name: str):
    """按路径加载一个脚本当模块（``tools/`` 不是包）。"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_learning_path():
    """加载 ``tools/build-learning-path.py``。

    归类的唯一真相在那儿：``read_posts()`` 与 ``classify()``。这里不重写。
    """
    return load_module(REPO_ROOT / "tools" / "build-learning-path.py",
                       "build_learning_path")


def _md_escape(text: str) -> str:
    """转义链接文字里会被 Markdown 当成语法的字符。

    和 ``build-learning-path.py`` 同一套规则：标题里带 ``[`` ``]`` ``(``
    ``)`` ``\\`` 时不转义，整行链接会退化成纯文本，读者点不开。
    """
    out = text.replace("\\", "\\\\")
    for ch in "[]()`*":
        out = out.replace(ch, "\\" + ch)
    return out


# --- 收集 --------------------------------------------------------------------


def collect():
    """把语料、规则、分期收成生成页面需要的一切。

    返回一个字典：``periods``（分期，含阶段、文章、年份统计）、
    ``tracks``（赛道索引）、``posts``（全站语料）、``dates``（固化日期）。
    """
    lp = load_learning_path()
    rules = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    journey = json.loads(JOURNEY_FILE.read_text(encoding="utf-8"))
    dates = json.loads(DATES_FILE.read_text(encoding="utf-8"))

    posts = lp.read_posts(POSTS_DIR)
    tracks, unclassified = lp.classify(posts, rules)

    stage_index = {}
    for t in tracks:
        for s in t["stages"]:
            stage_index[(t["id"], s["id"])] = (t, s)

    periods = []
    for spec in list(journey.get("periods", [])) + [journey["optional"]]:
        stages = []
        seen_posts = []
        for key in spec["stages"]:
            track_id, stage_id = key.split("/", 1)
            pair = stage_index.get((track_id, stage_id))
            if pair is None:
                raise SystemExit(
                    "分期 %s 引用了不存在的阶段 %s —— "
                    "阶段表在 data/learning-path.json" % (spec["id"], key))
            track, stage = pair
            stage_posts = [p for p in stage["posts"]
                           if not p["rel"].startswith(VIDEO_PREFIX)]
            stages.append({"track": track, "stage": stage, "posts": stage_posts})
            seen_posts.extend(stage_posts)
        years = Counter(p["date"][:4] for p in seen_posts if p["date"])
        periods.append({
            "id": spec["id"],
            "title": spec["title"],
            "goal": spec.get("goal", ""),
            "can_do": spec.get("can_do", ""),
            "first_read": spec.get("first_read", []),
            "stages": stages,
            "posts": seen_posts,
            "years": years,
            "count": len(seen_posts),
        })

    return {"periods": periods, "tracks": tracks, "posts": posts,
            "unclassified": unclassified, "dates": dates,
            "journey": journey}


def resolve_first_read(period: dict, post_by_rel: dict) -> list[dict]:
    """把 ``first_read`` 里的母稿路径解析成「文章 + 理由」。

    母稿路径用的是 ``data/date-overrides.json`` 的键格式（带扩展名、
    不带 ``docs/`` 前缀）。母稿目录里 ``<包>/index.md`` 在产物里会被展平成
    ``<包>``，``.html`` 会加 ``-html`` 后缀 —— 所以一个键可能要试三种形态。
    """
    resolved = []
    for item in period.get("first_read", []):
        key = item["path"]
        stem = key.rsplit(".", 1)[0]
        candidates = [stem, stem + "-html"]
        if stem.rsplit("/", 1)[-1] == "index":
            candidates.append(stem.rsplit("/", 1)[0])
        post = next((post_by_rel[c] for c in candidates if c in post_by_rel), None)
        if post is None:
            raise SystemExit(
                "分期 %s 的起步文章 %s 在语料里找不到 —— "
                "路径要跟 data/date-overrides.json 的键同格式" % (period["id"], key))
        resolved.append({"post": post, "why": item.get("why", "")})
    return resolved


# --- 渲染 --------------------------------------------------------------------


def _year_row(period: dict, years: list[str]) -> list[str]:
    return [str(period["years"].get(y, 0)) for y in years]


def _all_years(periods: list[dict]) -> list[str]:
    """年份轴：从最早到最晚的**连续**区间。

    中间空着的年份（2020、2021）也得占一列 —— 那两年的空白本身就是这条
    曲线的一部分，藏掉它，读者就看不出「我那两年一篇没写」。
    """
    seen = set()
    for p in periods:
        seen.update(p["years"])
    if not seen:
        return []
    first, last = min(seen), max(seen)
    return [str(y) for y in range(int(first), int(last) + 1)]


def _span_text(period: dict) -> str:
    """一句话说明这一期的时间跨度。"""
    years = sorted(period["years"])
    if not years:
        return "我在这一期还没写东西。"
    if years[0] == years[-1]:
        return "我在这一期写了 **%d 篇**，全部写于 %s 年。" % (period["count"], years[0])
    return "我在这一期写了 **%d 篇**，从 %s 到 %s。" % (
        period["count"], years[0], years[-1])


def _track_links(period: dict) -> str:
    """这一期涉及的赛道（去重）—— 同一个赛道出现多个阶段时不重复列。"""
    seen = []
    for item in period["stages"]:
        track = item["track"]
        if track["id"] in [t["id"] for t in seen]:
            continue
        seen.append(track)
    return "、".join(
        "[%s](%s)" % (t["title"], _rooted_path("/learning/%s/" % t["id"]))
        for t in seen)


def render_overview(data: dict) -> str:
    journey = data["journey"]
    periods = data["periods"]
    main = [p for p in periods if p["id"] != "optional"]
    optional = next((p for p in periods if p["id"] == "optional"), None)
    years = _all_years(periods)
    total_posts = sum(p["count"] for p in periods)

    lines = [
        "---",
        'title: "%s"' % journey["title"],
        "date: 2026-01-01 00:00:00",
        "type: journey",
        "layout: learning",
        'crumb_label: "%s"' % journey["title"],
        'crumb_path: "/journey/"',
        "---",
        "",
        "# %s" % journey["title"],
        "",
        journey["subtitle"],
        "",
        "全站 %d 篇文章，我按**自己走过的顺序**排成了 5 期主线 + 一段选修。"
        % total_posts,
        "这条路不是按学科分的 —— 它是我从刚工作时的语言入门，走到今天读内核源码"
        "的**实际顺序**，每一步都留了文章在这儿。",
        "",
        "## 我写它们的年份",
        "",
        "| 期 | " + " | ".join(years) + " | 篇数 |",
        "| --- | " + " | ".join("---:" for _ in years) + " | ---: |",
    ]
    for p in main:
        lines.append("| **第 %d 期 · %s** | %s | **%d** |" % (
            main.index(p) + 1, p["title"], " | ".join(_year_row(p, years)), p["count"]))
    if optional:
        lines.append("| 选修 · %s | %s | **%d** |" % (
            optional["title"], " | ".join(_year_row(optional, years)), optional["count"]))
    totals = Counter()
    for p in periods:
        totals.update(p["years"])
    lines.append("| **合计** | %s | **%d** |" % (
        " | ".join(str(totals.get(y, 0)) for y in years), sum(totals.values())))
    lines.append("")

    lines.extend([
        "> **口径**：这张表只算 `docs/` 里的 %d 篇文章。站上另外 6 期**视频内容单元**"
        % total_posts,
        "> 不在 `docs/` 里，没有提交日期，所以不在表内 —— 它们在",
        "> [PostgreSQL 源码内核](%s) 那一页上照旧有。" % _rooted_path("/learning/postgresql/"),
        "",
        "这张表本身就是那条曲线：2018 年只有第 1 期；2020 和 2021，我一篇没写；",
        "2022 年一年铺开了第 2、3、4 期；2026 年全压在第 4、5 期上。",
        "",
        "## 五期主线",
        "",
    ])

    for i, p in enumerate(main):
        lines.extend([
            "### 第 %d 期 · %s" % (i + 1, p["title"]),
            "",
            "- **这一期解决什么**：%s" % p["goal"],
            "- **读完这一期，你能**：%s" % p["can_do"],
            "",
            _span_text(p),
            "",
            "包含的赛道阶段：%s" % _track_links(p),
            "",
            "[开始这一期 →](%s)" % _rooted_path("/journey/%s/" % p["id"]),
            "",
        ])

    if optional:
        lines.extend([
            "## 选修 · %s" % optional["title"],
            "",
            "- **这一段解决什么**：%s" % optional["goal"],
            "- **读完这一块，你能**：%s" % optional["can_do"],
            "",
            "这 %d 篇不在五期主线上 —— 主线讲的是**一条主线怎么走通**，"
            % optional["count"],
            "这些是同一段时间里我顺手写下的别的东西。它们单独成线，不占主线的位置。",
            "",
            "[去看看 →](%s)" % _rooted_path("/journey/optional/"),
            "",
        ])

    lines.extend([
        "## 两条路的关系",
        "",
        "[学习路径](%s) 是**按学科**查的：11 条赛道并排放，你想找某个主题的文章，"
        % _rooted_path("/learning/"),
        "去那儿。这里是**按顺序**走的：5 期主线，每一期告诉你先学什么、学完能干什么。",
        "两页看的是同一批文章，只是排法不同。",
        "",
        "这条路我走了 8 年 —— 从 2018 年 9 月的第一篇文章，到今天。",
        "",
        "---",
        "",
        "这份页面由 `tools/build-journey.py` 生成，",
        "分期规则在仓库根的 `data/journey.json`。",
        "文章列表与年份分布都是从 `data/learning-path.json` 和",
        "`data/date-overrides.json` 现算的 —— 规则对不上语料，CI 会红。",
        "",
    ])
    return "\n".join(lines)


def render_period(data: dict, period: dict, seq: int | None,
                  next_period: dict | None) -> str:
    journey = data["journey"]
    post_by_rel = {p["rel"]: p for p in data["posts"]}
    first_read = resolve_first_read(period, post_by_rel)
    # 年份轴跟总览页一致（连续区间），这样期页那一行能和总览的矩阵逐列对上。
    years = _all_years(data["periods"])

    if seq is None:
        heading = "%s · %s" % (period["title"], journey["title"])
    else:
        heading = "第 %d 期 · %s" % (seq, period["title"])

    lines = [
        "---",
        'title: "%s"' % heading,
        "date: 2026-01-01 00:00:00",
        "type: journey",
        "layout: learning",
        'crumb_label: "%s"' % journey["title"],
        'crumb_path: "/journey/"',
        "---",
        "",
        "# %s" % heading,
        "",
        "> %s" % period["goal"],
        "",
        "**读完这一期，你能**：%s" % period["can_do"],
        "",
        _span_text(period),
        "",
        "[← 回到成长路线](%s)" % _rooted_path("/journey/"),
        "",
    ]

    if first_read:
        lines.extend(["## 推荐起步", ""])
        for item in first_read:
            post = item["post"]
            lines.append("- [%s](%s) — %s" % (
                _md_escape(post["title"]), post["url"], item["why"]))
        lines.append("")

    lines.extend(["## 这一期包含的阶段", ""])
    for item in period["stages"]:
        track = item["track"]
        stage = item["stage"]
        lines.append("### [%s](%s) · %s · %s" % (
            track["title"], _rooted_path("/learning/%s/" % track["id"]),
            stage["id"], stage["title"]))
        lines.append("")
        if stage.get("goal"):
            lines.append("> %s" % stage["goal"])
            lines.append("")
        for post in item["posts"]:
            # 这里挂的是**日期**而不是分类 —— 这一页要讲的是「我什么时候写的」，
            # 分类在这一页是多余的（阶段本身已经说明了主题）。
            lines.append("- [%s](%s) — %s" % (
                _md_escape(post["title"]), post["url"], post["date"][:10]))
        lines.append("")

    lines.extend(["## 我在这一期", ""])
    lines.append("| " + " | ".join(years) + " |")
    lines.append("| " + " | ".join("---:" for _ in years) + " |")
    lines.append("| " + " | ".join(str(period["years"].get(y, 0)) for y in years) + " |")
    lines.append("")

    if next_period:
        url = _rooted_path("/journey/%s/" % next_period["id"])
        if next_period["id"] == "optional":
            # 选修线不是「第 6 期」——它是主线之外的另一条线。
            target = "[选修 · %s](%s)" % (next_period["title"], url)
        elif seq is None:
            target = "[%s](%s)" % (next_period["title"], url)
        else:
            target = "[第 %d 期 · %s](%s)" % (seq + 1, next_period["title"], url)
        lines.extend([
            "## 下一步",
            "",
            "走完这一期，你去%s。" % target,
            "",
        ])

    lines.extend([
        "---",
        "",
        "这一页由 `tools/build-journey.py` 生成，",
        "分期规则在仓库根的 `data/journey.json`。",
        "",
    ])
    return "\n".join(lines)


# --- 守卫 --------------------------------------------------------------------


def valid_site_paths(data: dict) -> set[str]:
    """站内**应该存在**的地址集合（链接检查用）。

    文章地址来自语料本身；页面地址是本工具和 ``build-learning-path.py``
    生成的那些。这里列全，是为了让「页面里链了个不存在的东西」能被发现。
    """
    paths = set()
    for post in data["posts"]:
        paths.add(post["url"])
    paths.add(_rooted_path("/"))
    paths.add(_rooted_path("/archives/"))
    paths.add(_rooted_path("/learning/"))
    for t in data["tracks"]:
        paths.add(_rooted_path("/learning/%s/" % t["id"]))
        for alias in t.get("aliases", []):
            paths.add(_rooted_path("/learning/%s/" % alias))
    paths.add(_rooted_path("/journey/"))
    for p in data["periods"]:
        paths.add(_rooted_path("/journey/%s/" % p["id"]))
    return paths


def check_links(pages: dict, valid: set[str]) -> list[str]:
    """页面里的站内链接不许指向不存在的地址。

    ``/journey/`` 在 CI 里根本没有产物（``hexo generate`` 还没跑），
    所以这道检查只能对着**生成出来的 Markdown** 做 —— 这也是
    ``--check`` 存在的理由之一。
    """
    problems = []
    for name, text in pages.items():
        for link in LINK_RE.findall(text):
            if link.startswith(("http://", "https://", "mailto:", "#")):
                continue
            if link not in valid:
                problems.append("%s 里链到了不存在的地址：%s" % (name, link))
    return problems


def check_counts(data: dict) -> list[str]:
    """篇数自洽：各期篇数加起来 = 语料里的文章数 = 固化日期的条目数。

    数字是**现算**的，不写死 —— 文章是会加的，写死 591 下一篇就红。
    """
    problems = []
    counted = sum(p["count"] for p in data["periods"])
    corpus = len([p for p in data["posts"]
                  if not p["rel"].startswith(VIDEO_PREFIX)])
    if counted != corpus:
        problems.append("各期篇数加起来是 %d，语料里却是 %d 篇文章" % (counted, corpus))
    frozen = len(data["dates"])
    if counted != frozen:
        problems.append("各期篇数加起来是 %d，data/date-overrides.json 却有 %d 条"
                        % (counted, frozen))
    return problems


# --- 主流程 ------------------------------------------------------------------


def build_pages(data: dict) -> "OrderedDict[str, str]":
    """生成所有页面的 Markdown（不落盘）。"""
    pages = OrderedDict()
    pages["index.md"] = render_overview(data)
    main = [p for p in data["periods"] if p["id"] != "optional"]
    optional = next((p for p in data["periods"] if p["id"] == "optional"), None)
    for i, p in enumerate(main):
        nxt = main[i + 1] if i + 1 < len(main) else optional
        pages["%s/index.md" % p["id"]] = render_period(data, p, i + 1, nxt)
    if optional:
        pages["optional/index.md"] = render_period(data, optional, None, None)
    return pages


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生成成长路线页面")
    ap.add_argument("--check", action="store_true",
                    help="只检查（不写文件）：篇数或链接对不上就以非零码退出")
    args = ap.parse_args(argv)

    if not POSTS_DIR.is_dir():
        raise SystemExit(
            "没有 %s —— 先跑 python3 tools/sync-hexo.py（成长路线读的是 sync "
            "之后的产物，front matter 和 permalink 都在那儿）" % POSTS_DIR)

    data = collect()

    if data["unclassified"]:
        print("有 %d 篇文章没归到任何赛道 —— 这是学习路径的规则漏了，"
              "先修 data/learning-path.json" % len(data["unclassified"]),
              file=sys.stderr)
        for p in data["unclassified"]:
            print("  " + p["rel"], file=sys.stderr)
        return 1

    print("文章总数：%d（视频内容单元不计入）"
          % sum(p["count"] for p in data["periods"]))
    for p in data["periods"]:
        span = ""
        if p["years"]:
            span = "%s–%s" % (min(p["years"]), max(p["years"]))
        print("  %-10s %3d 篇   %-12s %s" % (p["id"], p["count"], p["title"], span))

    pages = build_pages(data)

    problems = check_counts(data)
    problems += check_links(pages, valid_site_paths(data))
    if problems:
        print("\n有 %d 处对不上：" % len(problems), file=sys.stderr)
        for line in problems:
            print("  " + line, file=sys.stderr)
        return 1

    if args.check:
        print("\n（--check：没有写文件）")
        print("检查通过：%d 个页面，篇数自洽，站内链接没有死链。" % len(pages))
        return 0

    for name, text in pages.items():
        path = OUT_DIR / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    print("\n生成：%s/index.md + %d 个分期页"
          % (OUT_DIR, len(pages) - 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
