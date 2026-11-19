#!/usr/bin/env python3
"""
Transform Hugo-style docs/ content into Hexo source/ directory.

Creates:
  source/_posts/  - markdown posts with Hexo front matter
  source/images/  - all images from docs/ (paths rewritten to images/...)

Does NOT modify docs/ — runs in CI on a fresh checkout.
"""

import os, re, shutil, subprocess, sys, json, glob
from typing import TypeGuard

# The permalinks this tool emits must carry the mount point the
# site is served under (`root:` in _config.yml): the primary domain
# is at `/`, the GitHub Pages mirror at `/blog/`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from site_root import permalink as _permalink
from site_root import root_prefix_urls as _root_prefix_urls
from site_root import site_root as _site_root

SITE_ROOT = _site_root()
from urllib.parse import quote, unquote

DOCS = "docs"
SRC = "source"
POSTS = os.path.join(SRC, "_posts")
IMGS = os.path.join(SRC, "images")
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico"}

# 内部工程目录（§4.3 的路径排除规则）：路径中任意一级目录名命中即排除，
# 大小写不敏感。
#
# **只排除目录，不排除任何文件名**——初版排除 README.md，实测误伤
# aiv/voice/README.md 等 5 个内容资产（那是音色规范，不是垃圾）。
#
# 这条规则是**防回归守卫**，不是修复手段：真正的解法是「想清楚哪些内容该
# 发布，然后让发布路径与工程路径物理分离」（AIV 把工程目录迁出 docs/ 就是
# 那么做的）。它防的是「将来有人在 docs/ 下建了 tests/、pipeline/ 这类工程
# 目录，构建期把它们当成文章发布」。
#
# 与 main() 里的隐藏目录守卫**并列**，不是替换它。
EXCLUDED_DIR_NAMES = frozenset(
    {
        "tests",
        "test",
        "fixtures",
        "plans",
        "pipeline",
        "build",
        "out",
        "_staging",
        "frames",
    }
)


def is_excluded_dir(name):
    """Whether a directory name is an internal engineering directory (§4.3)."""
    return name.lower() in EXCLUDED_DIR_NAMES


def prune_excluded_dirs(dirs):
    """Drop excluded directories from an ``os.walk`` ``dirs`` list, in place.

    剪掉目录（而不是跳过文件）是对的：被排除的目录**整棵**不进产物——
    文章、分类、图都不进。
    """
    dirs[:] = [d for d in dirs if not is_excluded_dir(d)]
    return dirs


# Posts to feature in the homepage recommend section (relative to docs/)
# Higher top value = shown first in the recommend carousel
FEATURED_POSTS = {
    "life/road/00-intro.md": 100,
    "life/road/01-how_to_learn_program.md": 90,
    "distributed/foundations/分布式存储需要解决的问题.md": 85,
    "es/oh-my-search.md": 80,
    "source-tracks/postgresql/logical-replication/逻辑解码DDL-Replay框架设计/index.md": 75,
    "distributed/consensus/一文读懂openguass dcf网络模块.md": 70,
    "distributed/foundations/分布式一致性协议.md": 65,
    "distributed/foundations/分布式系统设计必知必会.md": 60,
    "source-tracks/postgresql/getting-started/postgresql基操.md": 55,
    "source-tracks/linux/kernel-internals/linux内核指北.md": 50,
    "dpdk/dpdk常用接口指北.md": 45,
    "docker/docker基础指北.md": 40,
    "ai/07_ChatGPT为什么能对话一篇引用17万次的论文.md": 35,
    "source-tracks/postgresql/logical-replication/逻辑解码/index.md": 30,
    "language/rust/rust设计原则.md": 25,
    "tools/那些你不得不会的提高工作效率的软件神器.md": 20,
    "source-tracks/linux/networking/从原理到实践，彻底告别 IPv6 上网不稳定的问题.md": 15,
    "ai/01_开场白目录.md": 10,
}


# Documents moved to a new directory keep their original publication date.
# git_date() derives the date from the git history under the CURRENT path,
# and a move only creates a new commit for that path -- so without this
# table every moved article would be dated with its move commit and jump
# to the top of "recent posts".  Keyed by docs/-relative path.
DATE_OVERRIDES = {
    "life/road/00-intro.md": "2025-04-16 09:20:54",
    "life/road/01-how_to_learn_program.md": "2025-04-16 09:20:54",
    "life/road/02-elevate_thinking.md": "2026-09-28 14:48:28",
    "life/road/左耳朵耗子的话——关于技术的一些思考.md": "2025-04-16 09:20:54",
    "life/hometown/家中对联.md": "2026-08-06 15:28:11",
    "life/hometown/家中对联-html.html": "2026-08-11 15:41:57",
    "life/gaokao/math-methods/index.md": "2026-11-06 21:20:33",
    "life/gaokao/math-paper2/index.md": "2026-11-08 11:59:40",
    "life/gaokao/english-roots/index.md": "2026-11-11 12:04:05",
    "life/gaokao/yunnan-policy/index.md": "2026-11-11 21:00:00",
    "life/gaokao/yunnan-apply/index.md": "2026-11-11 22:30:00",
    "life/gaokao/physics-methods/index.md": "2026-11-11 22:50:00",
    "life/gaokao/chemistry-methods/index.md": "2026-11-11 23:20:00",
    "life/gaokao/biology-methods/index.md": "2026-11-11 23:50:00",
    "life/gaokao/politics-methods/index.md": "2026-11-12 02:30:00",
    "life/gaokao/geography-methods/index.md": "2026-11-12 03:10:00",
    "life/daxue/电子科技大学-计算机-自考-复习计划/index.md": "2026-10-13 11:28:09",
    "life/daxue/腾冲事业编-公务员备考计划/index.md": "2026-10-13 11:07:22",
    "life/shehui/economic-downturn-strategy/index.md": "2026-10-28 14:09:55",
    "life/shehui/economic-downturn-deep-dive/index.md": "2026-10-28 16:30:00",
    "life/shehui/media-account/index.md": "2026-11-09 16:01:13",
    "life/shehui/self-host/index.md": "2026-10-23 14:28:54",
    "life/shehui/area.md": "2026-10-21 16:38:27",
    "life/shehui/zhuangxiu.md": "2026-10-21 16:38:27",
}

# Permalinks that changed when docs/life/ was restructured into
# gaokao/ daxue/ shehui/.  Keyed by the OLD post path (docs/-relative,
# without the .md extension for single-file posts), value = the new
# post path.  write_redirects() emits a redirect page at the old URL.
REDIRECTS = {
    "00-intro": "life/road/00-intro",
    "01-how_to_learn_program": "life/road/01-how_to_learn_program",
    "02-elevate_thinking": "life/road/02-elevate_thinking",
    "road/左耳朵耗子的话——关于技术的一些思考": "life/road/左耳朵耗子的话——关于技术的一些思考",
    "hometown/家中对联": "life/hometown/家中对联",
    "hometown/家中对联-html": "life/hometown/家中对联-html.html",
    "life/gaokao-math-methods": "life/gaokao/math-methods",
    "life/gaokao-math-paper2": "life/gaokao/math-paper2",
    "life/gaokao-english-roots": "life/gaokao/english-roots",
    "life/电子科技大学-计算机-自考-复习计划": "life/daxue/电子科技大学-计算机-自考-复习计划",
    "life/腾冲事业编-公务员备考计划": "life/daxue/腾冲事业编-公务员备考计划",
    "life/economic-downturn-strategy": "life/shehui/economic-downturn-strategy",
    "life/economic-downturn-deep-dive": "life/shehui/economic-downturn-deep-dive",
    "life/media-account": "life/shehui/media-account",
    "life/self-host": "life/shehui/self-host",
    "life/area": "life/shehui/area",
    "life/zhuangxiu": "life/shehui/zhuangxiu",
}


# Redirect pages are Hexo *pages* with `layout: false`.  Hexo's page
# generator (hexo/dist/plugins/generator/page.js) emits such pages
# verbatim -- no theme layout -- so the page keeps its own <head> with the
# meta refresh and a canonical pointing at the NEW url.  A themed layout
# would drop the meta refresh (it only works in <head>) and the theme's
# own canonical would point back at the old URL.
REDIRECT_PAGE = """---
title: "{title}"
layout: false
sitemap: false
comments: false
---

<meta http-equiv="refresh" content="0; url={new_url}">
<link rel="canonical" href="{new_url}">
<meta name="robots" content="noindex, follow">
<p>这篇文章已移动到新的目录，点击继续：<a href="{new_url}">{new_url}</a></p>
<script>location.replace("{new_url}");</script>
"""

# Category pages whose URL changed when a section gained/lost an _index.md
# or was nested under a parent category.  Keyed by the OLD category path
# (as it appeared under /categories/), value = the NEW category path.
#
#   成长之路  docs/road/  ->  docs/life/road/     (成长之路 becomes a child of 人生)
#   随笔      docs/*.md   ->  docs/life/road/     (root docs fell back to 「随笔」)
#   stock     docs/stock/ ->  title 股票与金融
#   hometown  docs/hometown/ -> title 家乡 (now a child of 人生)
CATEGORY_REDIRECTS = {
    "成长之路": "人生/成长之路",
    "随笔": "人生/成长之路",
    "stock": "股票与金融",
    "hometown": "人生/家乡",
}


# --- `data/` 下的策展表 ---------------------------------------------------
#
# 上面三张表的内容是**人工策展的映射**，不是代码逻辑：目录重排一次就是
# 几百条，写成 Python 字面量会让这个文件长到几千行，而且每次迁移都要
# 手改一遍 —— 改漏一条，死链就多一条。
#
# 放进 `data/` 之后，迁移脚本（`tools/migrate-tree.py`）直接写，
# 编译时读。表不存在就当没有（首次 clone、或还没跑过迁移）。
def _load_data_table(name):
    """读 `data/` 下的一张策展表。"""
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), name)
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# 顺序：后读到的覆盖先读到的。`data/` 里的表是最新的，
# 上面写死的字面量保留为「这段历史是怎么来的」的记录。
DATE_OVERRIDES.update(_load_data_table("data/date-overrides.json"))
REDIRECTS.update(_load_data_table("data/redirects.json"))
CATEGORY_REDIRECTS.update(_load_data_table("data/category-redirects.json"))

TOPIC_DEFS = [
    # (name, icon, color, blurb)
    (
        "内核基础",
        "fa-microchip",
        "#4283D4",
        "进程模型 · 存储 · WAL · 执行器 · 学习路径",
    ),
    (
        "MVCC 与事务",
        "fa-code-branch",
        "#10B981",
        "多版本并发控制 · 事务生命周期 · 隔离级别",
    ),
    (
        "逻辑复制",
        "fa-network-wired",
        "#F59E0B",
        "逻辑解码 · DDL 同步 · publisher / subscriber",
    ),
    (
        "分区",
        "fa-table-cells",
        "#8B5CF6",
        "分区表设计 · 跨分区 DML 路由 · 跨数据库对比",
    ),
    (
        "高可用与复制",
        "fa-shield-halved",
        "#EF4444",
        "流复制 · 同步复制 · HAProxy · repmgr",
    ),
    ("分布式一致性", "fa-share-nodes", "#EC4899", "Raft · DCF · 多数派 · Leader 选举"),
    (
        "性能调优",
        "fa-gauge-high",
        "#06B6D4",
        "Checkpoint · WAL Writer · 统计信息 · IO 调优",
    ),
    ("实战经验", "fa-bookmark", "#84CC16", "避坑清单 · 翻译整理 · PostgreSQL 万能论"),
]

# Inference rules: a post belongs to a topic if any path_contains substring
# matches its docs/-relative path OR any title_contains keyword matches
# its title (case-insensitive). A post can belong to multiple topics.
#
# The path fragments below are **the new tree's** paths
# (`source-tracks/postgresql/<series>/…`).  The fragments used to point at
# `db/postgresql/…` — a path that stopped existing two restructures ago,
# so the topic cards had quietly emptied out (the database landing page
# listed 10 posts instead of ~200).  Series directories are used as the
# coarse rule and the individual article paths as the precise one; the
# bare basenames still match because the migration kept the file names.
#
# One more set of fragments lives in DISTRIBUTED_DB_KERNEL (below): the
# openGauss DCF / Raft articles used to sit in `cluster/DCF/` and
# `cluster/raft/`, and after the distributed-block migration they are
# neighbours of ZooKeeper and corosync articles inside one series — so
# they can no longer be picked out by a directory name.

#: The distributed-database kernel articles (openGauss DCF + Raft).
#:
#: They used to live in two directories -- ``cluster/DCF/`` and
#: ``cluster/raft/`` -- and the database landing page whitelisted exactly
#: those two directories.  After the distributed-block migration both
#: groups sit in ``distributed/consensus/`` side by side with ZooKeeper,
#: totem and corosync articles, which are *not* database-kernel
#: material, so a directory name can no longer pick them out.
#:
#: The entries are exact article paths rather than directory prefixes:
#: ``distributed/consensus/openguass dcf源码阅读.md`` (from
#: ``cluster/DCF/``) and ``distributed/consensus/openguass dcf启动详解.md``
#: (from ``openguass/``) differ by three characters, and only the
#: former was ever whitelisted.
DISTRIBUTED_DB_KERNEL = (
    "distributed/consensus/c-raft分布式存储方案.md",
    "distributed/consensus/c-rart.md",
    "distributed/consensus/raft协议动态调整quorum.md",
    "distributed/consensus/raft重要概念.md",
    "distributed/consensus/dcf投票系统详解.md",
    "distributed/consensus/dcf网络模块详解",
    "distributed/consensus/dcf写入机制.md",
    "distributed/consensus/dcf运行机制.md",
    "distributed/consensus/openguass dcf源码阅读.md",
    "distributed/consensus/一文读懂openguass dcf网络模块",
    "distributed/consensus/常用压缩算法编程.md",
)

TOPIC_RULES = {
    "MVCC 与事务": {
        "path_contains": [
            "postgresql-mvcc",
            "postgresql-transaction-lifecycle",
            "source-tracks/postgresql/transaction-mvcc",
        ],
        "title_contains": [
            "MVCC",
            "事务生命周期",
            "Transaction Lifecycle",
            "行锁",
            "MultiXact",
        ],
    },
    "逻辑复制": {
        "path_contains": [
            "postgresql-logical-replication",
            "source-tracks/postgresql/logical-replication",
            "source-tracks/postgresql/replication-ha/postgresql-create-replication-slot",
        ],
        "title_contains": [
            "逻辑复制",
            "逻辑解码",
            "Logical Replication",
            "DDL-Replay",
            "DDL Replay",
            "pglogical",
            "pgoutput",
            "Babelfish",
            "SnapBuild",
            "reorderbuffer",
            "ReorderBuffer",
            "applyparallelworker",
            "apply worker",
            "apply parallel",
            "并行解码",
            "并行 apply",
            "并行 Apply",
            "CSN",
            "apply",
            "subxact",
            "walsender",
        ],
    },
    "分区": {
        "path_contains": [
            "postgresql-partition",
            "postgresql-vs-sqlserver-partitioning",
            "postgresql-logical-replication-partitioned",
        ],
        "title_contains": ["分区", "Partition", "partitioned"],
    },
    "高可用与复制": {
        "path_contains": [
            # 伪双写那一组，原先是 cluster/postgresql/ 下的四篇
            "distributed/distributed-storage/haproxy",
            "distributed/distributed-storage/postgresql伪双写",
            "distributed/distributed-storage/事务管理",
            "source-tracks/postgresql/replication-ha",
        ],
        "title_contains": [
            "HAProxy",
            "PGBouncer",
            "repmgr",
            "流复制",
            "高可用",
            "双写",
            "failover",
        ],
    },
    "分布式一致性": {
        "path_contains": [
            *DISTRIBUTED_DB_KERNEL,
            # 「分布式一致性协议」那篇原先在 cluster 根目录，现在在「分布式基础」
            "distributed/foundations/分布式一致性协议",
        ],
        "title_contains": ["Raft", "DCF", "openGauss DCF", "分布式一致性"],
    },
    "性能调优": {
        "path_contains": [
            "source-tracks/postgresql/extensions-perf/postgresql-flame-graph",
            "source-tracks/postgresql/logical-replication/postgresql-logical-replication-apply-parallel-tuning",
        ],
        "title_contains": [
            "调优",
            "性能",
            "Checkpoint",
            "WalWriter",
            "WAL Writer",
            "统计信息",
            "keepalive",
            "pg_io",
            "bgwriter",
            "BgWriter",
            "火焰图",
            "flame graph",
            "TPC-C",
        ],
    },
    "内核基础": {
        "path_contains": [
            "postgresql-memory-management",
            "source-tracks/postgresql/getting-started",
            "source-tracks/postgresql/storage-engine",
            "source-tracks/postgresql/index-and-query",
            "source-tracks/postgresql/wal-and-recovery",
        ],
        "title_contains": [
            "源码",
            "源码修炼",
            "学习路径",
            "PostgreSQL 主结构",
            "启动流程",
            "插入",
            "进程架构",
            "syscache",
            "catcache",
            "relcache",
            "共享内存",
            "shared memory",
            "injection point",
            "InOutPoint",
            "WAL 记录",
            "RangeVar",
            "数据  结构",
            "TOAST",
            "latch",
        ],
    },
    "实战经验": {
        "path_contains": [
            "pg-challahscript-tips",
            "pg-dont-do-this",
            "postgresql-for-everything",
            "source-tracks/postgresql/extensions-perf/postgresql-injection-points",
            "source-tracks/postgresql/extensions-perf/postgresql-community-gems",
        ],
        "title_contains": [
            "Don't Do This",
            "万能论",
            "翻译整理",
            "内核开发者",
            "新增 GUC",
            "社区精髓",
            "pgsql-hackers",
        ],
    },
}

TOPIC_NAME_TO_DEF = {
    name: (icon, color, blurb) for name, icon, color, blurb in TOPIC_DEFS
}


# Hexo's slugize (hexo-util) — reimplemented so the URLs this script
# generates match the ones Hexo builds for categories/tags.  A tag named
# 「MVCC 与事务」 becomes /tags/MVCC-与事务/, NOT /tags/MVCC%20与事务/.
_R_CONTROL = re.compile(r"[\u0000-\u001f]")
_R_SPECIAL = re.compile(r'[\s~`!@#$%^&*()\-_+=[\]{}|\\;:"\'<>,.?/]+')


def slugize(name, separator="-"):
    """Mirror hexo-util's slugize() so generated links match Hexo's."""
    import unicodedata

    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = _R_CONTROL.sub("", s)
    s = _R_SPECIAL.sub(separator, s)
    s = re.sub(re.escape(separator) + "{2,}", separator, s)
    s = re.sub("^" + re.escape(separator) + "+|" + re.escape(separator) + "+$", "", s)
    return s


def infer_topics(rel, title):
    """Return the list of topic names a post belongs to.

    rel: docs/-relative path, e.g. 'source-tracks/postgresql/transaction-mvcc/postgresql-mvcc/index.md'.
    title: post title (already extracted).
    """
    matched = []
    title_lower = (title or "").lower()
    for topic_name, rules in TOPIC_RULES.items():
        path_hit = any(p in rel for p in rules.get("path_contains", []))
        title_hit = any(
            kw.lower() in title_lower for kw in rules.get("title_contains", [])
        )
        if path_hit or title_hit:
            matched.append(topic_name)
    return matched


def read_section_categories():
    """Map top-level section dir -> Chinese display name from _index.md."""
    titles = {}
    for section in os.listdir(DOCS):
        idx = os.path.join(DOCS, section, "_index.md")
        if not os.path.isfile(idx):
            continue
        with open(idx, encoding="utf-8") as f:
            txt = f.read()
        m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', txt, re.MULTILINE)
        if m:
            titles[section] = m.group(1).strip()
    return titles


def read_cascade_categories():
    """Walk docs/**/_index.md and collect `cascade.categories` per subdir.

    Returns {subdir_path_relative_to_docs: [list of category names]}.
    """
    cascades = {}
    for root, dirs, files in os.walk(DOCS):
        prune_excluded_dirs(dirs)
        if "_index.md" not in files:
            continue
        idx = os.path.join(root, "_index.md")
        with open(idx, encoding="utf-8") as f:
            txt = f.read()
        m = re.search(
            r"cascade:\s*\n\s*categories:\s*\n((?:\s*-\s*.+\n)+)", txt, re.MULTILINE
        )
        if m:
            items = []
            for line in m.group(1).split("\n"):
                item_m = re.match(r"\s*-\s*(.+)", line)
                if item_m:
                    items.append(item_m.group(1).strip())
            if items:
                rel = os.path.relpath(root, DOCS)
                cascades[rel] = items
    return cascades


def resolve_post_categories(rel, section_titles, cascades):
    """Resolve final category list for a post at relative path `rel`.

    1. Top-level section title (primary, drives URL slugs)
    2. Cascade categories from nearest ancestor _index.md (going up)

    De-duplicated; primary stays first.
    """
    section = rel.split(os.sep)[0] if os.sep in rel else ""
    primary = section_titles.get(section, section or "随笔")
    cats = [primary]
    seen = {primary}
    fdir = os.path.dirname(rel)
    if fdir:
        parts = fdir.split(os.sep)
        for i in range(1, len(parts) + 1):
            sub = os.sep.join(parts[:i])
            if sub in cascades:
                for c in cascades[sub]:
                    if c not in seen:
                        cats.append(c)
                        seen.add(c)
    return cats


def categories_yaml(cats):
    """Render a list of category strings as a YAML list body."""
    return "\n".join(f"  - {c}" for c in cats)


def git_date(filepath):
    """Get the earliest commit date across ALL branches.

    Files migrated from repo root to docs/ and some were converted from
    single .md files to page bundles (dir/index.md), so we search
    multiple historical path candidates on every branch."""
    rel = os.path.relpath(filepath, DOCS)
    override = DATE_OVERRIDES.get(rel.replace(os.sep, "/"))
    if override:
        return override
    candidates = [f"docs/{rel}", rel]
    if os.path.basename(filepath) == "index.md":
        parent = os.path.dirname(rel)
        if parent:
            candidates.append(f"docs/{parent}.md")
            candidates.append(f"{parent}.md")
    earliest = None
    for path in candidates:
        try:
            r = subprocess.run(
                ["git", "log", "--all", "--reverse", "--format=%ai", "--", path],
                capture_output=True,
                text=True,
            )
            if r.returncode == 0 and r.stdout.strip():
                d = r.stdout.strip().split("\n")[0].strip()
                if earliest is None or d < earliest:
                    earliest = d
        except Exception:
            continue
    if not earliest:
        return "2024-01-01 00:00:00"
    # Drop the trailing `+0800` / `+0000` offset.  Hexo's date path
    # generation goes through `node_modules/hexo/dist/plugins/processor/
    # common.js:51` `timezone()` which double-applies the offset when
    # the CI container TZ is UTC, shifting dates by one day for any
    # article that crosses UTC midnight.  Emitting a wall-clock string
    # without offset (and clearing `timezone:` in _config.yml) keeps
    # the rendered Y/M/D identical to the author-time wall clock.
    return earliest.split(" +")[0].split(" -")[0]


def extract_title(content):
    m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return m.group(1).strip() if m else None


def fallback_title(filepath):
    base = os.path.splitext(os.path.basename(filepath))[0]
    if base == "index":
        return os.path.basename(os.path.dirname(filepath))
    return base


def split_fm(content):
    """Return (fm_text, body). fm_text=None if no front matter."""
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", content, re.DOTALL)
    if m:
        return m.group(1), content[m.end() :]
    m = re.match(r"^---\r?\n---\r?\n", content)
    if m:
        return "", content[m.end() :]
    return None, content


def has_fm_title(fm) -> TypeGuard[str]:
    """front matter 里有没有 title 字段。

    **是 TypeGuard**：调用方写 `if has_fm_title(fm):` 之后，类型检查器
    就知道 fm 不是 None——否则紧接着的 re.search 得自己再判一遍 None。
    """
    return fm is not None and bool(re.search(r"^title\s*:", fm, re.MULTILINE))


def yaml_escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _front_matter_title(text):
    """Read the ``title`` out of a front matter block.

    **为什么不能按第一个引号切**：生成出来的 front matter 是
    ``title: "AI 能\\"创造\\"吗？"``——里面的引号被 YAML 转义过。
    按 ``[^"']+`` 取值会在**第一个**引号处停下，10 篇文章的标题在 404 页
    的索引里只剩「AI 能\\」，搜这些文章搜不到。

    三种写法都要认：双引号串（带转义）、单引号串（``''`` 是转义的单引号）、
    裸标量（引号只算正文的一部分）。
    """
    m = re.search(r"^title:[ \t]*(.*)$", text, re.M)
    if not m:
        return None
    value = m.group(1).strip()
    if not value:
        return None
    if value[0] == '"':
        # 双引号串：走到**没有被转义**的那个收尾引号为止。
        out = []
        i = 1
        while i < len(value):
            ch = value[i]
            if ch == "\\" and i + 1 < len(value):
                out.append(value[i + 1])
                i += 2
                continue
            if ch == '"':
                break
            out.append(ch)
            i += 1
        return "".join(out).strip()
    if value[0] == "'":
        end = value.find("'", 1)
        while end != -1 and value[end + 1 : end + 2] == "'":
            end = value.find("'", end + 2)
        return (value[1:end] if end != -1 else value[1:]).replace("''", "'").strip()
    # 裸标量：` #` 之后是 YAML 注释，不算标题的一部分。
    return re.split(r"\s+#", value, maxsplit=1)[0].strip()


# 透传字段（§4.1）：契约层（publish/publishkit/contract.py）要读的那些。
# sync 只负责**原样搬运**——值的校验归契约层管（publish/spec/00-架构设计.md §4.1）。
#
# §4.1 的白名单共 10 个字段：title / short_title / tldr / description /
# difficulty / cover / reprintPolicy / kind / platforms / publish_on。
#
# ``title`` 不在下面两个列表里——它**已经通了**：front matter 模板的第一行
# ``title: "..."`` 就是从作者的 front matter 取出来的（process() 里的
# has_fm_title 分支），送到的也是 §4.1 表里写的同一个目标（page.title）。
# 再搬一遍会产出两个 title 键——重复的 YAML 键是新问题，不是补齐。
#
# 平台 id 与发布日期不参与站点渲染，展示元数据（tldr / description /
# difficulty ...）同理——所以接上这条通道不改动现有页面的渲染结果。
# 期号字段（契约七 §4.3）在这里**再写一份**。
#
# 这一层**不许** import 契约层——有测试盯着
# （publish/tests/test_sync_passthrough.py::test_sync_script_does_not_import_the_contract_layer）。
# 所以两份清单各自写字面量，一致性靠测试钉住：
# publish/tests/test_episode.py 里两条——「期号字段逐个出现在本文件里」
# 与「真文章 → 期号字段全部到达产物」。
#
# 这与上面那十来个字段的处理方式完全一致，不是新开的口子。
#
# 全部是**扁平键名**：front matter 的格式规则只允许扁平标量与单层列表，
# 嵌套的 episode_media 会被静默丢掉——页面照常渲染，只是期号区块是空的。
PASSTHROUGH_LIST_FIELDS = (
    "platforms",
    "episode_sources",
    "episode_repro",
)
PASSTHROUGH_SCALAR_FIELDS = (
    "short_title",
    "tldr",
    "description",
    "difficulty",
    "cover",
    "reprintPolicy",
    "kind",
    "publish_on",
    "episode",
    "episode_no",
    "series",
    "episode_hook",
    "episode_subtitle",
    "episode_duration_s",
    "episode_license",
)


def _fm_scalar(fm, key):
    """Raw text of a top-level ``key: value`` line in ``fm``.

    Returns ``None`` when the key is absent or carries no value.  The value
    comes back verbatim (quotes included) so the passthrough is byte-exact.
    """
    if not fm:
        return None
    for raw in fm.split("\n"):
        if not raw.strip() or raw[:1] in (" ", "\t"):
            continue
        head, sep, tail = raw.partition(":")
        if sep and head.strip() == key:
            value = tail.strip()
            return value or None
    return None


def _fm_indented_scalar(fm, key):
    """Raw content of the first indented, non-list line under ``key:``.

    作者把列表写成**缩进标量**时（``platforms:`` 下面缩进的 ``wechat``），
    ``_fm_list`` 认不出列表（没有 ``- `` 前缀），``_fm_scalar`` 又因为这一行
    尾部是空的而认不到值——两个都返回 ``None``，这个字段就会**静默消失**。

    这一段把它捞回来：内容原样当标量带走，让契约层去报「platforms 必须是
    列表」——与内联列表走同一条路。在这里悄悄丢掉更糟——丢了等于「这篇不发」，
    而作者以为自己写了。
    """
    if not fm:
        return None
    under_key = False
    for raw in fm.split("\n"):
        if not raw.strip():
            continue
        if raw[:1] in (" ", "\t"):
            if not under_key:
                continue
            stripped = raw.strip()
            if stripped.startswith("- "):
                continue  # 列表形态，交给 _fm_list
            return stripped
        head, sep, tail = raw.partition(":")
        under_key = bool(sep) and head.strip() == key and not tail.strip()
    return None


def _fm_list(fm, key):
    """Raw items of a top-level ``key:`` + ``  - item`` block in ``fm``.

    Returns ``None`` when the key is absent or carries a scalar value.
    Items come back verbatim (quotes included).
    """
    if not fm:
        return None
    items = []
    list_key = None
    for raw in fm.split("\n"):
        if not raw.strip():
            continue
        if raw[:1] in (" ", "\t"):
            stripped = raw.strip()
            if list_key == key and stripped.startswith("- "):
                items.append(stripped[2:].strip())
            continue
        head, sep, tail = raw.partition(":")
        if sep and head.strip() == key and not tail.strip():
            list_key = key
        else:
            list_key = None
    return items or None


def passthrough_block(fm):
    """The front-matter lines the publish contract needs, carried verbatim.

    §4.1 的白名单字段全部原样搬过去——列表字段写回 ``key:`` + ``  - item``
    的形态，其余写回 ``key: value``。值一个字都不改：校验归契约层管
    （publish/spec/00-架构设计.md §4.1）。

    值不在域内时（``difficulty: 高`` / ``reprintPolicy: 瞎写``）也照样搬——
    与内联列表的处理方式一样：原样带过去，让契约层去报错。在这里悄悄丢掉
    更糟——丢了等于「这篇不发」，而作者以为自己写了。

    A post that declares none of them gets no extra lines, so its front
    matter stays byte-identical to what it was before.
    """
    lines = []
    for key in PASSTHROUGH_LIST_FIELDS:
        items = _fm_list(fm, key)
        if items:
            lines.append("{}:".format(key))
            lines.extend("  - {}".format(item) for item in items)
        else:
            # 不是列表形态（内联列表 / 单个标量 / 缩进标量）：原样带过去，
            # 让契约层去报错。在这里悄悄丢掉更糟——丢了等于「这篇不发」，
            # 而作者以为自己写了。
            value = _fm_scalar(fm, key)
            if value is None:
                value = _fm_indented_scalar(fm, key)
            if value:
                lines.append("{}: {}".format(key, value))
    for key in PASSTHROUGH_SCALAR_FIELDS:
        value = _fm_scalar(fm, key)
        if value is None:
            value = _fm_indented_scalar(fm, key)
        if value:
            lines.append("{}: {}".format(key, value))
    return "".join(line + "\n" for line in lines)


def read_matery_about_config():
    """Read profile/myProjects/mySkills from _config.matery.yml.

    Lightweight YAML parser tailored to the structure used by the about
    section. Handles comments, quoted strings, multiline `|` blocks, and
    the 0/2/4/6-space indent structure used in _config.matery.yml.

    Returns (profile, my_projects, my_skills, my_education, my_honors,
    my_timeline) as dicts.
    """
    config_path = "_config.matery.yml"
    if not os.path.isfile(config_path):
        # **返回值个数要与末尾那条 return 一致**：调用方解包 6 个，少给一个
        # 就是 ValueError——配置文件不在时反而把整个构建搞崩。
        return (
            {},
            {"enable": False, "data": {}},
            {"enable": False, "data": {}},
            {"enable": False, "data": []},
            {"enable": False, "data": []},
            {"enable": False, "data": []},
        )

    with open(config_path, encoding="utf-8") as f:
        lines = f.readlines()

    profile = {}
    my_projects = {"enable": False, "data": {}}
    my_skills = {"enable": False, "data": {}}
    my_education = {"enable": False, "data": []}
    my_honors = {"enable": False, "data": []}
    my_timeline = {"enable": False, "data": []}

    # Sections whose `data:` is a list of dicts (vs dict of dicts).
    LIST_DATA_SECTIONS = {"myEducation", "myHonors", "myTimeline"}

    # Map top-level section name -> mutable target dict so we can
    # look up enable flag and data container uniformly.
    section_data_map = {
        "myProjects": my_projects,
        "mySkills": my_skills,
        "myEducation": my_education,
        "myHonors": my_honors,
        "myTimeline": my_timeline,
    }

    current_top = None
    current_data_target = None
    current_data_key = None
    current_list_item = None
    current_dict_item = None  # dict we are currently populating with key/value pairs
    current_list_key = None  # key whose list we are currently appending to
    multiline_indicator_indent = -1  # indent of the line that opened the block
    in_multiline = False
    multiline_target = None
    multiline_block_indent = None
    multiline_value = []

    def strip_comment(s):
        in_q = False
        q_char = ""
        for i, c in enumerate(s):
            if c in ('"', "'") and (i == 0 or s[i - 1] != "\\"):
                if not in_q:
                    in_q = True
                    q_char = c
                elif c == q_char:
                    in_q = False
            elif c == "#" and not in_q:
                return s[:i].rstrip()
        return s.rstrip()

    def flush_multiline():
        nonlocal in_multiline, multiline_value, multiline_target
        nonlocal multiline_block_indent, multiline_indicator_indent
        if multiline_target == "profile_intro":
            # Drop leading blank lines, then lstrip the first content line
            # so the introduction starts flush-left even if the YAML
            # author indented the first line relative to the indicator.
            while multiline_value and not multiline_value[0].strip():
                multiline_value.pop(0)
            if multiline_value:
                multiline_value[0] = multiline_value[0].lstrip()
            profile["introduction"] = "\n".join(multiline_value).rstrip()
        in_multiline = False
        multiline_value = []
        multiline_target = None
        multiline_block_indent = None
        multiline_indicator_indent = -1

    def unquote(v):
        """Strip matching outer quotes from a YAML scalar."""
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
            return v[1:-1]
        return v

    for raw in lines:
        stripped = raw.rstrip("\n").rstrip("\r")
        if not stripped.strip():
            if in_multiline:
                multiline_value.append("")
            continue
        if stripped.lstrip().startswith("#"):
            continue

        indent = len(stripped) - len(stripped.lstrip())
        content = strip_comment(stripped[indent:])

        if in_multiline:
            # End the block when we hit a line at or above the
            # indicator's indent, or when we reach a top-level key.
            if indent <= multiline_indicator_indent:
                flush_multiline()
            elif multiline_block_indent is None and stripped.strip():
                multiline_block_indent = indent
                line_text = stripped[multiline_block_indent:]
                multiline_value.append(line_text)
                continue
            elif (
                multiline_block_indent is not None and indent >= multiline_block_indent
            ):
                line_text = stripped[multiline_block_indent:]
                multiline_value.append(line_text)
                continue
            else:
                flush_multiline()

        if not content:
            continue

        # Top-level key (indent 0)
        if indent == 0 and content.endswith(":"):
            # Flush any pending list-of-dicts item from the previous
            # section before transitioning.
            if (
                current_list_item is not None
                and current_data_target in LIST_DATA_SECTIONS
            ):
                section_data_map[current_data_target]["data"].append(current_list_item)
                current_list_item = None
                current_dict_item = None
            current_list_key = None
            current_top = content[:-1].strip()
            current_data_target = None
            current_data_key = None
            continue

        # 2-space indent (subkey of top-level section)
        if indent == 2 and ":" in content:
            key, _, value = content.partition(":")
            key = key.strip()
            value = value.strip()

            if current_top == "profile":
                if key == "introduction" and value == "|":
                    in_multiline = True
                    multiline_target = "profile_intro"
                    multiline_block_indent = None
                    multiline_indicator_indent = indent
                    multiline_value = []
                else:
                    profile[key] = unquote(value)
            elif current_top in section_data_map:
                target = section_data_map[current_top]
                if key == "enable":
                    target["enable"] = value == "true"
                elif key == "data" and value == "":
                    current_data_target = current_top
            current_data_key = None
            current_list_item = None
            continue

        # 4-space indent (item in data dict or list)
        if indent == 4 and current_data_target:
            current_list_key = None  # exiting any prior list-collecting scope
            if current_data_target in LIST_DATA_SECTIONS:
                # List-of-dicts: each `- key: ...` starts a new item.
                if content.startswith("- "):
                    if current_list_item is not None:
                        section_data_map[current_data_target]["data"].append(
                            current_list_item
                        )
                    current_list_item = {}
                    current_dict_item = current_list_item
                    # Inline `- key: value` populates the new item's
                    # first field; otherwise the key comes from a
                    # following 6-space indent line.
                    rest = content[2:].strip()
                    if ":" in rest:
                        k, _, v = rest.partition(":")
                        current_dict_item[k.strip()] = unquote(v.strip())
                continue
            if content.endswith(":"):
                item_name = content[:-1].strip()
                current_data_key = item_name
                section_data_map[current_data_target]["data"][item_name] = {}
                current_dict_item = section_data_map[current_data_target]["data"][
                    item_name
                ]
            continue

        # 6-space indent (property of data item)
        if indent == 6 and ":" in content:
            key, _, value = content.partition(":")
            key = key.strip()
            value = unquote(value.strip())
            current_list_key = None  # a fresh 6-space key resets nested-list mode
            if current_dict_item is not None:
                if value == "" and not content.startswith("- "):
                    # Empty value: a following 8-space `- xxx` list
                    # populates this key as a list.
                    current_dict_item[key] = []
                    current_list_key = key
                elif content.startswith("- "):
                    current_dict_item.setdefault(key, []).append(value)
                else:
                    current_dict_item[key] = value
                continue
            continue

        # 8-space indent: items in a list under the current key.
        if indent >= 8 and current_dict_item is not None and current_list_key:
            target_list = current_dict_item.get(current_list_key)
            if isinstance(target_list, list):
                if content.startswith("- "):
                    target_list.append(unquote(content[2:].strip()))
                elif ":" in content:
                    _, _, vv = content.partition(":")
                    target_list.append(unquote(vv.strip()))
            continue

    if in_multiline:
        flush_multiline()
    if current_list_item is not None and current_data_target in LIST_DATA_SECTIONS:
        section_data_map[current_data_target]["data"].append(current_list_item)

    return profile, my_projects, my_skills, my_education, my_honors, my_timeline


def build_about_markdown(
    profile, my_projects, my_skills, my_education=None, my_honors=None, my_timeline=None
):
    """Build source/about/index.md content from matery config + static sections.

    `my_education`, `my_honors`, `my_timeline` are optional list-of-dicts
    sections. `my_timeline` renders right under the bio intro as a
    vertical timeline; the others render after the project cards.
    """
    my_education = my_education or {"enable": False, "data": []}
    my_honors = my_honors or {"enable": False, "data": []}
    my_timeline = my_timeline or {"enable": False, "data": []}

    intro = profile.get("introduction") or ""
    # Skip the intro paragraph entirely when empty so no <p></p>
    # appears at the top of the about page.
    intro = profile.get("introduction") or ""
    # Skip the intro paragraph entirely when empty so no <p></p>
    # appears at the top of the about page.
    intro_block = (intro.strip() + "\n\n") if intro.strip() else ""

    # Skill bars
    skill_lines = []
    if my_skills.get("enable") and my_skills.get("data"):
        for name, props in my_skills["data"].items():
            bg = props.get(
                "background", "linear-gradient(to right, #336791 0%, #4B8BBE 100%)"
            )
            pct = props.get("percent", "80%")
            skill_lines.append(
                f'<div class="skill-bar">\n'
                f'  <div class="skill-row"><span>{name}</span><span>{pct}</span></div>\n'
                f'  <div class="skill-track"><div class="skill-fill" '
                f'style="width:{pct};background:{bg}"></div></div>\n'
                f"</div>"
            )
    skills_block = "\n".join(skill_lines) if skill_lines else ""

    # Project cards (richer: time / company / role / achievements / tech)
    project_lines = []
    if my_projects.get("enable") and my_projects.get("data"):
        for name, props in my_projects["data"].items():
            icon = props.get("icon", "fas fa-code")
            bg = props.get(
                "iconBackground",
                "linear-gradient(to bottom right, #3367D6 0%, #0084FF 100%)",
            )
            url = props.get("url", "")
            time = props.get("time", "")
            company = props.get("company", "")
            role = props.get("role", "")
            desc = props.get("desc", "")
            tech = props.get("tech", "")
            achievements = props.get("achievements") or []

            meta_bits = [b for b in (company, role, time) if b]
            meta_sep = " · ".join(meta_bits)
            meta_html = f'<div class="proj-meta">{meta_sep}</div>' if meta_bits else ""
            ach_html = ""
            if achievements:
                items = "".join(f"<li>{a}</li>" for a in achievements)
                ach_html = f'<ul class="proj-achievements">{items}</ul>'
            tech_html = f'<div class="proj-tech">技术栈: {tech}</div>' if tech else ""
            url_attr = f' data-url="{url}"' if url else ""

            project_lines.append(
                f'<div class="project-card"{url_attr}>\n'
                f'  <div class="proj-icon" style="background:{bg};"><i class="{icon}"></i></div>\n'
                f'  <div class="proj-body">\n'
                f'    <div class="proj-name">{name}</div>\n'
                f"    {meta_html}\n"
                f'    <div class="proj-desc">{desc}</div>\n'
                f"    {ach_html}\n"
                f"    {tech_html}\n"
                f"  </div>\n"
                f"</div>"
            )
    projects_block = "\n".join(project_lines) if project_lines else ""

    # Education cards
    edu_lines = []
    if my_education.get("enable") and my_education.get("data"):
        for ed in my_education["data"]:
            school = ed.get("school", "")
            major = ed.get("major", "")
            degree = ed.get("degree", "")
            period = ed.get("period", "")
            honor = ed.get("honor", "")
            major_line = " · ".join(b for b in (major, degree) if b)
            honor_html = (
                f'<div class="edu-honor"><i class="fas fa-award"></i> {honor}</div>'
                if honor
                else ""
            )
            edu_lines.append(
                f'<div class="edu-item">\n'
                f'  <div class="edu-school">{school}</div>\n'
                f'  <div class="edu-major">{major_line}</div>\n'
                f'  <div class="edu-period">{period}</div>\n'
                f"  {honor_html}\n"
                f"</div>"
            )
    edu_block = "\n".join(edu_lines) if edu_lines else ""

    # Bio timeline
    timeline_lines = []
    if my_timeline.get("enable") and my_timeline.get("data"):
        for t in my_timeline["data"]:
            period = t.get("period", "")
            title = t.get("title", "")
            desc = t.get("desc", "")
            timeline_lines.append(
                f'<div class="timeline-item">\n'
                f'  <div class="timeline-date">{period}</div>\n'
                f'  <div class="timeline-title">{title}</div>\n'
                f'  <div class="timeline-desc">{desc}</div>\n'
                f"</div>"
            )
    timeline_block = "\n".join(timeline_lines) if timeline_lines else ""

    # Honors list
    honor_lines = []
    if my_honors.get("enable") and my_honors.get("data"):
        for h in my_honors["data"]:
            name = h.get("name", "")
            level = h.get("level", "")
            year = h.get("year", "")
            year_html = f'<span class="honor-year">{year}</span>\n  ' if year else ""
            honor_lines.append(
                f'<div class="honor-item">\n'
                f'  <span class="honor-name">{name}</span>\n'
                f'  <span class="honor-level">{level}</span>\n'
                f"  {year_html}</div>"
            )
    honor_block = "\n".join(honor_lines) if honor_lines else ""

    # Compose optional sections
    edu_section = (
        f'\n## 教育背景\n\n<div class="edu-grid">\n{edu_block}\n</div>\n'
        if edu_block
        else ""
    )
    honor_section = (
        f'\n## 个人荣誉\n\n<div class="honor-list">\n{honor_block}\n</div>\n'
        if honor_block
        else ""
    )
    timeline_section = (
        f'\n<div class="about-timeline">\n{timeline_block}\n</div>\n'
        if timeline_block
        else ""
    )

    # Compose the template as a plain string and use str.format_map
    # so we can keep literal CSS braces (single { is fine in format()
    # when we use a SafeFormatter or escape via {{}}).
    template = """---
title: "关于我"
date: 2026-07-29 00:00:00
layout: about
type: about
---

{intro_block}{timeline_section}
## 重点项目

{projects_block}{edu_section}{honor_section}
## GitHub 数据

<div id="gh-stats" class="gh-stats">
  <div class="gh-stat"><div class="gh-stat-num">--</div><div class="gh-stat-label">加载中</div></div>
</div>
<script>
fetch('https://api.github.com/users/growdu')
  .then(function(r){{return r.json()}})
  .then(function(d){{
    var el=document.getElementById('gh-stats');
    if(el&&d) el.innerHTML=
      '<div class="gh-stat"><div class="gh-stat-num">'+d.public_repos+'</div><div class="gh-stat-label">公开仓库</div></div>'+
      '<div class="gh-stat"><div class="gh-stat-num">'+d.followers+'</div><div class="gh-stat-label">关注者</div></div>'+
      '<div class="gh-stat"><div class="gh-stat-num">'+d.following+'</div><div class="gh-stat-label">关注中</div></div>'+
      '<div class="gh-stat"><div class="gh-stat-num">'+(d.created_at?d.created_at.substring(0,4):'--')+'</div><div class="gh-stat-label">加入GitHub</div></div>';
  }})
  .catch(function(){{}});
</script>

## 技术栈

{skills_block}

## 联系方式

- **GitHub**: https://github.com/growdu
- **Email**: growdu@gmail.com
- **QQ**: 2689304284
"""
    return template.format(
        intro_block=intro_block,
        timeline_section=timeline_section,
        skills_block=skills_block,
        projects_block=projects_block,
        edu_section=edu_section,
        honor_section=honor_section,
    )


def rewrite_images(content, file_dir):
    """Rewrite ![alt](rel_path) -> ![alt](images/<resolved>)."""

    def repl(m):
        alt, path = m.group(1), m.group(2)
        if path.startswith(("http://", "https://", "data:", "#")):
            return m.group(0)
        path = path.lstrip("./")
        resolved = os.path.normpath(os.path.join(file_dir, path))
        return f"![{alt}](images/{resolved})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, content)


def _resolve_link_target(rel_target, current_post_dir):
    """Map a docs/-relative target path to an absolute Hexo permalink.

    `rel_target` is the path of the link target as it would appear under
    docs/ (already resolved through os.path.normpath against the current
    post's docs/-relative directory).  Returns the final permalink string
    like "/2026/08/24/database/foo/" or None if no matching docs/ file
    exists (in which case the caller should leave the link untouched).
    """
    abs_target = os.path.join(DOCS, rel_target)
    basename = os.path.basename(rel_target)
    # If the link ends in index.{md,html,htm}, treat the parent as a
    # page-bundle directory first; many docs/ posts live under
    # docs/<section>/<slug>/index.md and the link from a sibling bundle
    # points at ./<slug>/index.html.
    if basename in ("index.md", "index.html", "index.htm"):
        bundle_dir_rel = os.path.dirname(rel_target)
        bundle_dir_abs = os.path.join(DOCS, bundle_dir_rel)
        if os.path.isdir(bundle_dir_abs):
            for ext in ("index.md", "index.html", "index.htm", "_index.md"):
                bundle_index = os.path.join(bundle_dir_abs, ext)
                if os.path.isfile(bundle_index):
                    slug = os.path.basename(bundle_dir_rel)
                    parent = os.path.dirname(bundle_dir_rel)
                    post_path = os.path.join(parent, slug) if parent else slug
                    date = git_date(bundle_index)
                    return _permalink(date, post_path)
            return None
    if os.path.isdir(abs_target):
        # Page bundle — look for an index file inside it.
        for ext in ("index.md", "index.html", "index.htm", "_index.md"):
            bundle_index = os.path.join(abs_target, ext)
            if os.path.isfile(bundle_index):
                slug = os.path.basename(rel_target.rstrip("/"))
                parent = os.path.dirname(rel_target.rstrip("/"))
                post_path = os.path.join(parent, slug) if parent else slug
                date = git_date(bundle_index)
                return _permalink(date, post_path)
        return None
    if os.path.isfile(abs_target):
        ext = os.path.splitext(rel_target)[1].lower()
        slug = os.path.splitext(os.path.basename(rel_target))[0]
        if ext in (".html", ".htm") and not slug.endswith("-html"):
            slug += "-html"
        parent = os.path.dirname(rel_target)
        post_path = os.path.join(parent, slug) if parent else slug
        date = git_date(abs_target)
        return _permalink(date, post_path)
    # Extension-less link such as `./foo` — try common suffixes.
    for ext in (".md", ".html", ".htm"):
        candidate = abs_target + ext
        if os.path.isfile(candidate):
            slug = os.path.splitext(os.path.basename(candidate))[0]
            if ext in (".html", ".htm") and not slug.endswith("-html"):
                slug += "-html"
            parent = os.path.dirname(candidate)
            post_path = os.path.join(parent, slug) if parent else slug
            date = git_date(candidate)
            return _permalink(date, post_path)
    return None


def rewrite_links(content, rel):
    """Rewrite relative markdown links to absolute Hexo permalinks.

    `rel` is the docs/-relative path of the post being processed, e.g.
    'source-tracks/postgresql/transaction-mvcc/postgresql-mvcc/index.md'.  Relative links of the form
    [text](./other/index.html) are resolved against the post's own
    docs/ directory and replaced with the target's full permalink so
    that the browser navigation from the rendered page lands on a real
    URL.  Links that already point at an absolute URL, an external
    scheme, an anchor, a /-rooted path, or a target we can't resolve
    are left as-is.
    """
    # The post lives at docs/<dirname>/index.md (page bundle).  All
    # relative links inside the markdown resolve against this directory.
    if os.path.basename(rel) == "index.md":
        post_dir = os.path.dirname(rel)
    else:
        post_dir = os.path.dirname(rel)

    def repl(m):
        text, raw = m.group(1), m.group(2)
        # Split anchor / query off so we can preserve them on the rewrite.
        suffix = ""
        if "#" in raw or "?" in raw:
            # Preserve both anchor and query string verbatim by holding
            # them aside while we resolve only the path component.
            hash_idx = raw.find("#")
            q_idx = raw.find("?")
            cut = min(i for i in (hash_idx, q_idx) if i >= 0)
            raw, suffix = raw[:cut], raw[cut:]
        if not raw or raw.startswith(
            ("http://", "https://", "data:", "mailto:", "tel:", "#")
        ):
            return m.group(0)
        if raw.startswith("//"):
            return m.group(0)
        if raw.startswith("/"):
            # A root-absolute site-internal link still needs the
            # mount point on the GitHub Pages mirror.
            if not SITE_ROOT:
                return m.group(0)
            return f"[{text}]({SITE_ROOT}{raw}{suffix})"
        # Resolve the link against the post's own directory, keeping the
        # leading ../ segments. Dropping them before normpath() (the old
        # behaviour) mis-resolves any link that points at a sibling
        # top-level section — e.g. life/aiv/ -> db/postgresql/... — and
        # leaves it as a relative URL that 404s on the published site.
        candidate = os.path.normpath(os.path.join(post_dir, raw))
        # normpath can produce a leading '../' if the link escaped the
        # docs tree entirely — bail out in that case to avoid rewriting
        # something we don't actually understand.
        if candidate.startswith("..") or os.path.isabs(candidate):
            return m.group(0)
        # Normalise away any leading ./ segments for the sibling fallback
        # below, which re-tries the lookup one directory up.
        cleaned = raw.lstrip("./")
        # First try the path as written.  If the post is a page bundle
        # (docs/<section>/<slug>/index.md) the author is often thinking
        # in terms of the permalink folder `<slug>/` rather than the
        # docs/ subtree, so a link like `./other-article/index.html`
        # may be written with `./` even though the real target is a
        # sibling bundle (`../other-article/index.html`).  Fall back to
        # the parent directory so this common typo self-heals.
        url = _resolve_link_target(candidate, post_dir)
        if url is not None:
            return f"[{text}]({url}{suffix})"
        if post_dir:
            parent_dir = os.path.dirname(post_dir)
            if parent_dir and not parent_dir.startswith(".."):
                sibling = os.path.normpath(os.path.join(parent_dir, cleaned))
                if not sibling.startswith(".."):
                    url = _resolve_link_target(sibling, parent_dir)
                    if url is not None:
                        return f"[{text}]({url}{suffix})"
        return m.group(0)

    # Match ordinary markdown links but skip image links (which are
    # handled by rewrite_images and start with '!').  The (?<!!) look-
    # behind avoids matching inside an image description.
    return re.sub(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)", repl, content)


def copy_images():
    for root, dirs, files in os.walk(DOCS):
        prune_excluded_dirs(dirs)
        for f in files:
            if os.path.splitext(f)[1].lower() in IMG_EXT:
                src = os.path.join(root, f)
                rel = os.path.relpath(src, DOCS)
                dst = os.path.join(IMGS, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)


#: 编辑履历表：这样的表是站点自己的编辑记录，不是文章内容——留在正文里
#: 会污染三处摘要：``<meta name="description">``、首页卡片摘要
#: （smart_summary）、RSS 的 ``<summary>``。全站 97 张。
#:
#: 表头第一格的取值：「编写人」是最常见的写法，也有 3 篇写的是「修改人」。
#: （要「第一格」而不是「任意一格」：正文里提到「编写人」这三个字的表格
#: 比比皆是——重构方案.md 里就有一张。）
EDIT_HISTORY_FIRST_CELLS = ("编写人", "修改人", "编辑人")

#: 履历表里装着「这篇文章是什么」的那一列。别的列名（「修改内容」）不抽
#: 摘要——那几列装的是「文档初稿」这类空话，不是文章摘要。
EDIT_HISTORY_CONTENT_CELL = "编写内容"

#: 履历前缀：「初稿，」「初稿。」「修订：」说的是「这次改了什么」，不是
#: 「文章是什么」。摘要是给读者看这篇文章是什么的——前缀得去掉。
#:
#: 关键词后面必须跟着分隔符（或到此为止）才算前缀：「补充完善解决方案」里的
#: 「补充」是正文，不是履历前缀。
HISTORY_PREFIX_RE = re.compile(
    r"^\s*(初稿|修订|校验|校对|更新|整理|补充)\s*(?:[：:，,。；;！!？?+]\s*|$)"
)

#: 摘要里的 markdown 标记。摘要要进 meta / 卡片 / RSS——那里的 markdown
#: 标记不会被渲染，是字面量（「**PostgreSQL 目录快照**」显示成带星号的）。
MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
MD_CODE_RE = re.compile(r"`([^`]+)`")
MD_ITALIC_RE = re.compile(r"(?<![\*\w])\*([^*\s][^*]*?)\*(?!\w)")

#: description 的契约上限（publish/spec/00-架构设计.md §4.1）。
DESCRIPTION_LIMIT = 150


def _table_cells(line):
    """Cells of a markdown table row, or ``None`` if the line is not a row.

    A row is a line that starts with a pipe.  Leading/trailing pipes are
    optional; the cells come back stripped.
    """
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    cells = [c.strip() for c in stripped.strip("|").split("|")]
    if len(cells) < 2:
        return None
    return cells


def _is_separator_row(cells):
    """True for a markdown table's ``| --- | --- |`` divider row."""
    if not cells:
        return False
    return all(re.match(r"^:?-+:?$", c.replace(" ", "")) for c in cells)


def find_edit_history_tables(text):
    """Every editing-history table in ``text``.

    Returns a list of ``(header_cells, data_rows)``.  A table qualifies
    when its **first** header cell names the editor（「编写人」/「修改人」/
    「编辑人」）——那是站点自己的编辑履历，不是文章内容。
    """
    lines = text.split("\n")
    tables = []
    i = 0
    while i < len(lines):
        cells = _table_cells(lines[i])
        if cells and cells[0] in EDIT_HISTORY_FIRST_CELLS:
            sep = _table_cells(lines[i + 1]) if i + 1 < len(lines) else None
            if sep and _is_separator_row(sep):
                rows = []
                k = i + 2
                while k < len(lines):
                    row = _table_cells(lines[k])
                    if not row:
                        break
                    rows.append(row)
                    k += 1
                tables.append((cells, rows))
                i = k
                continue
        i += 1
    return tables


def _plain_text(text):
    """A markdown fragment → plain text.

    The summary lands in ``<meta name="description">``, in the card
    summaries, in the OG/Twitter cards and in the RSS ``<summary>`` —
    none of which render markdown, so ``**粗体**`` shows up as literal
    asterisks.
    """
    text = MD_BOLD_RE.sub(r"\1", text)
    text = MD_CODE_RE.sub(r"\1", text)
    text = MD_ITALIC_RE.sub(r"\1", text)
    return text


def _fit_description(text, limit=DESCRIPTION_LIMIT):
    """Cut to the contract's limit — measured on the **escaped** form.

    The contract layer reads front matter with its own tiny parser
    (``publish/publishkit/contract.py``), which strips the quotes but does
    **not** unescape: ``\\"`` counts as two characters there.  Cap the
    escaped form and the semantic form is bounded by the same number —
    both readings of 「≤150 字」 hold.
    """
    if len(yaml_escape(text)) <= limit:
        return text
    while text and len(yaml_escape(text + "…")) > limit:
        text = text[:-1]
    return text.rstrip() + "…"


def edit_history_description(header, rows):
    """The one-line summary an editing-history table carries (or ``None``).

    Takes the last non-empty 「编写内容」 cell—the table may hold one row
    per revision, and the last row is the most recent one—strips the
    revision prefix, flattens the markdown, collapses whitespace, and cuts
    to the contract's 150 characters.

    A cell that only says 「初稿」 is not a summary: it yields ``None``
    rather than a description of 「初稿」.
    """
    if EDIT_HISTORY_CONTENT_CELL not in header:
        return None
    idx = header.index(EDIT_HISTORY_CONTENT_CELL)
    value = ""
    for row in rows:
        cell = row[idx] if len(row) > idx else ""
        if cell.strip():
            value = cell
    if not value.strip():
        return None
    text = HISTORY_PREFIX_RE.sub("", value).strip()
    if not text:
        return None
    text = re.sub(r"\s+", " ", text)
    text = _plain_text(text)
    return _fit_description(text)


def extract_edit_history(body):
    """Strip the editing-history tables out of ``body``.

    Returns ``(clean_body, description)``: the body without those tables,
    and the one-line summary the first table that carries a 「编写内容」
    column had to offer (``None`` when no table offers one).

    The table is not article content.  Left in the body it becomes the
    first thing every summary scraper sees — the ``<meta name=
    "description">`` of 98 pages was table residue.
    """
    lines = body.split("\n")
    description = None
    for header, rows in find_edit_history_tables(body):
        if description is None:
            description = edit_history_description(header, rows)
    out = []
    i = 0
    while i < len(lines):
        cells = _table_cells(lines[i])
        if cells and cells[0] in EDIT_HISTORY_FIRST_CELLS:
            sep = _table_cells(lines[i + 1]) if i + 1 < len(lines) else None
            if sep and _is_separator_row(sep):
                i += 2
                while i < len(lines) and _table_cells(lines[i]):
                    i += 1
                # 表后面跟着的空行一并收掉，别留三连空行。
                while i < len(lines) and not lines[i].strip():
                    i += 1
                if out and not out[-1].strip():
                    out.pop()
                out.append("")
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out), description


def process(filepath, section_titles, cascades):
    rel = os.path.relpath(filepath, DOCS)
    fdir = os.path.dirname(rel)

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    if os.path.basename(filepath) == "_index.md":
        return False

    fm, body = split_fm(content)
    src = body if fm is not None else content

    title = extract_title(src) or fallback_title(filepath)
    if has_fm_title(fm):
        m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', fm, re.MULTILINE)
        if m:
            title = m.group(1).strip()

    date = git_date(filepath)
    post_cats = resolve_post_categories(rel, section_titles, cascades)
    topics = infer_topics(rel, title)

    # 编辑履历表不是文章内容：先剥掉它，摘要才不会变成表格残骸。
    # （剥在改写之前：履历里那一句是原始素材，改写会把它里的链接改成
    # permalink，混进 description 里就不是人话。）
    src, history_desc = extract_edit_history(src)
    # rewrite images, strip first H1 (title is in front matter)
    body_out = rewrite_images(src, fdir)
    # Rewrite markdown intra-doc links to absolute Hexo permalinks so
    # that `[text](./other-article/index.html)` survives the move from
    # docs/<bundle>/ into source/_posts/<parent>/<bundle>.md without
    # breaking navigation.  Must run after rewrite_images (which already
    # turned `![]()` into `images/...`) so it only sees link references.
    body_out = rewrite_links(body_out, rel)
    body_out = re.sub(r"^#\s+.+\n?", "", body_out, count=1, flags=re.MULTILINE)

    top_val = FEATURED_POSTS.get(rel)
    top_line = f"\ntop: {top_val}" if top_val else ""
    cats_block = categories_yaml(post_cats)
    # Merge categories + topics into the tags list. Order-preserving dedupe
    # keeps the primary category first and appends each topic exactly once.
    all_tags = list(dict.fromkeys(post_cats + topics))
    tags_block = categories_yaml(all_tags)
    # 发布契约要读的两个字段，原样搬过去（没有就什么都不加）。
    passthrough = passthrough_block(fm)
    # 履历表里那一列是现成的摘要素材（见 docs/blog/重构方案.md §八 B5）：
    # 源 front matter 里已经写了 description 的以源为准，不覆盖。
    if history_desc and not _fm_scalar(fm, "description"):
        if not _fm_indented_scalar(fm, "description"):
            passthrough += 'description: "{}"\n'.format(yaml_escape(history_desc))
    fm_out = f'---\ntitle: "{yaml_escape(title)}"\ndate: {date}\nauthor: growdu{top_line}\ncategories:\n{cats_block}\ntags:\n{tags_block}\n{passthrough}---\n'

    if os.path.basename(filepath) == "index.md":
        name = os.path.basename(os.path.dirname(filepath))
        parent = os.path.dirname(fdir)
        out = os.path.join(POSTS, parent, f"{name}.md")
    else:
        out = os.path.join(POSTS, fdir, os.path.basename(filepath))

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(fm_out + body_out)
    return True


def process_html(filepath, section_titles, cascades):
    """Sync a .html (or .htm) file from docs/ into source/_posts/.

    Source files in docs/<section>/<name>.html become Hexo posts at
    source/_posts/<section>/<name>.html with no `layout` field, so
    they inherit `_config.yml`'s `default_layout: post`. The
    html renderer (scripts/html-renderer.js) strips the surrounding
    <html>/<head>/<body> wrapper; the resulting body lands in
    matery's `post.ejs` article slot, giving HTML posts the same
    header/footer/reward/comments/related/prev-next chrome as
    markdown posts — matching the user's "本来就是 html 格式"
    expectation: keep the rich HTML body, but surface it with the
    blog's normal chrome.

    Title extraction:
        1. <title>...</title> at the top of the file (case-insensitive).
        2. Stripping any inner HTML tags from the title.
        3. Fallback to filename (via fallback_title()).
    The <title> tag is stripped from the body after extraction so
    the rendered page does not carry it twice.

    Date: same git_date() walk as markdown posts.

    Images in the body are NOT rewritten — pass-through rendering
    keeps the HTML verbatim. Users who want images should reference
    them by absolute path (e.g. /blog/images/foo.png) or external URL,
    or place them next to the HTML file and reference them relatively.
    """
    rel = os.path.relpath(filepath, DOCS)
    fdir = os.path.dirname(rel)
    base = os.path.basename(filepath)

    if base in ("_index.html", "_index.htm"):
        return False

    with open(filepath, encoding="utf-8") as f:
        html_text = f.read()

    # title extraction from <title> tag (case-insensitive), with
    # optional inner HTML stripped.
    title_m = re.search(
        "<title[^>]*>(.*?)</title>",
        html_text,
        re.IGNORECASE | re.DOTALL,
    )
    title = None
    if title_m:
        inner = title_m.group(1)
        inner = re.sub(r"<[^>]+>", "", inner).strip()
        if inner:
            title = inner
    if not title:
        title = fallback_title(filepath)

    date = git_date(filepath)
    post_cats = resolve_post_categories(rel, section_titles, cascades)

    top_val = FEATURED_POSTS.get(rel)
    top_line = f"\ntop: {top_val}" if top_val else ""
    cats_block = categories_yaml(post_cats)
    fm_out = (
        f"---\n"
        f'title: "{yaml_escape(title)}"\n'
        f"date: {date}\n"
        f"author: growdu{top_line}\n"
        f"categories:\n{cats_block}\n"
        f"tags:\n{cats_block}\n"
        f"---\n"
    )

    body_out = html_text
    if title_m:
        body_out = re.sub(
            r"<title[^>]*>.*?</title>",
            "",
            body_out,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )

    # Rename the file (not the front matter title) so hexo\'s filename-
    # derived slug carries a -html suffix.  Hexo 7\'s post processor
    # sets `data.slug = info.title` from the filename, OVERWRITING any
    # `slug:` value set in the front matter (see node_modules/hexo/dist/
    # plugins/processor/post.js line 49: `data.slug = info.title;`).
    # The suffix keeps HTML posts out of any markdown twin\'s permalink
    # without relying on a front-matter field that hexo silently ignores.
    out_base, out_ext = os.path.splitext(base)
    if out_base.endswith("-html"):
        out_basename = base
    else:
        out_basename = f"{out_base}-html{out_ext}"

    if base in ("index.html", "index.htm"):
        name = os.path.basename(os.path.dirname(filepath))
        parent = os.path.dirname(fdir)
        out = os.path.join(POSTS, parent, out_basename)
    else:
        out = os.path.join(POSTS, fdir, out_basename)

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(fm_out + body_out)
    return True


def create_theme_pages():
    """Create Hexo pages that the matery theme expects for the
    categories and tags overview pages.  hexo-generator-category/tag
    only produce per-category/per-tag pages, not the index listing."""
    pages = [
        ("categories/index.md", "分类", "categories"),
        ("tags/index.md", "标签", "tags"),
    ]
    for rel, title, layout in pages:
        path = os.path.join(SRC, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fm = f'---\ntitle: {title}\ndate: 2024-01-01 00:00:00\ntype: "{layout}"\nlayout: "{layout}"\n---\n\n'
        with open(path, "w", encoding="utf-8") as f:
            f.write(fm)

    # About page - generated from _config.matery.yml profile/myProjects/mySkills
    # so updates to the config (e.g. career dates, project list) flow through
    # to the rendered page automatically on the next sync.
    about_path = os.path.join(SRC, "about", "index.md")
    os.makedirs(os.path.dirname(about_path), exist_ok=True)
    _profile, _my_projects, _my_skills, _my_education, _my_honors, _my_timeline = (
        read_matery_about_config()
    )
    about_md = build_about_markdown(
        _profile,
        _my_projects,
        _my_skills,
        _my_education,
        _my_honors,
        _my_timeline,
    )
    with open(about_path, "w", encoding="utf-8") as f:
        f.write(about_md)


def _redirect_target_file(new_path):
    """在 docs/ 里找出这个 permalink 路径对应的源文件。

    `new_path` 有三种写法，重定向表里三种都有：

    - 带扩展名的 docs 路径（`life/hometown/家中对联-html.html`）
    - 不带扩展名的单文件（`db/foo` → `db/foo.md`）
    - bundle 目录（`db/foo` → `db/foo/index.md`）

    HTML 文章的 permalink 带 `-html` 后缀（编译时文件名被改成
    `<basename>-html.html`，见 `process_html_post`），但**源文件**
    不一定带 —— `sqlserver逻辑复制ddl.html` 的 permalink 是
    `sqlserver逻辑复制ddl-html`。所以后缀要去掉再试一次。

    找不到就返回 None。
    """
    base = os.path.join(DOCS, new_path)
    cands = []
    if new_path.endswith((".md", ".html", ".htm")):
        cands.append(base)
    else:
        cands.append(base + ".md")
        cands.append(os.path.join(base, "index.md"))
        cands.append(base + ".html")
        if new_path.endswith("-html"):
            trimmed = base[: -len("-html")]
            cands.append(trimmed + ".html")
            cands.append(os.path.join(trimmed, "index.html"))
    for cand in cands:
        if os.path.isfile(cand):
            return cand
    return None


def _site_encode_url(path):
    """按站点真实发布的规则编码路径。

    站点上的地址是 hexo-util 的 `encodeURL`（= `encodeURI`）的产物：
    中文编成 `%E6%95%B0`，空格编成 `%20`，但 `&` `(` `)` `+` `,`
    `=` 这些**原样保留**（见站点上 `.../WalReceiver&startup交互/`
    这条地址）。`urllib.parse.quote` 默认会把它们也编码掉，
    生成的地址跟站点上发布的不是一个字符串 —— 都能访问，但
    canonical 指向的字面量跟目标页自己的 canonical 对不上。
    """
    return quote(path, safe=";,/?:@&=+$-_.!~*'()#")


#: 文件名里不能有的字符。Windows 的 NTFS 不允许，GitHub 的
#: upload-artifact / upload-pages-artifact 也直接拒绝含这些字符的路径 ——
#: 整个产物传不上去，部署直接断在那里（2026-11-17 的 Deploy Hexo 就是
#: 栽在「PostgreSQL 源码修炼之路:内核深度拆解专题」这个带冒号的目录上，
#: 连着两个 push 没上成线）。
INVALID_PATH_CHARS = ':*?"<>|'

#: 重定向表的键可以带一段日期（``2022/10/25/cluster/raft/…``）。
#:
#: 重定向页的日期段历来取自**新文件**的日期（``git_date()``）——文章搬家时
#: 日期不变，这正是 ``data/date-overrides.json`` 存在的意义。但合并两篇
#: **逐字节相同**的重复文章时情况不一样：合并后的那篇只有一个日期，
#: 另一个旧 URL 的日期段就对不上了（键里不带日期就落在错的地址上，
#: 真正的旧地址 404）。键里带上日期即可 —— 那是这条旧 URL 当初发布时的
#: 日期段，一字不差。
DATED_REDIRECT_RE = re.compile(r"^(?P<stamp>\d{4}/\d{2}/\d{2})/(?P<path>.+)$")


def write_redirects():
    """Generate redirect pages for permalinks that changed.

    A doc moved to a new directory gets a new permalink, so every old
    URL that was ever published (and every link from outside the site)
    would 404.  For each entry in REDIRECTS we emit a static HTML page
    at the OLD path that forwards to the new one.  The pages live in
    source/ (not source/_posts/), so Hexo copies them verbatim into
    public/ and they survive as plain files.

    **键里可以带一段日期**（``2022/10/25/cluster/raft/…``）：重定向页落在
    旧 URL 当初发布时的日期段上。默认取新文件的日期 —— 文章搬家时日期不变；
    合并两篇逐字节相同的重复文章时，合并后的那篇只有一个日期，另一个旧
    URL 的日期段就对不上了，这时键里带上日期才落得准（见
    :data:`DATED_REDIRECT_RE`）。

    **目录名用原始路径，不做百分号编码。** nginx 拿到的 `$uri` 是
    解码过的：浏览器请求 `/2023/05/17/pgsql/replication/PostgreSQL%E6%95%B0.../`，
    nginx 落盘查找的是解码后的 `PostgreSQL数据...` —— 磁盘上就得是
    这个名字，编码过的目录名它找不到（实测：`public/2026/08/06/hometown/`
    下只有一个 `%E5%AE%B6%E4%B8%AD%E5%AF%B9%E8%81%94` 目录）。而且
    百分号编码把中文放大 3 倍，一个目录名就能顶破 255 字节的
    NAME_MAX 上限（`pgsql/replication/PostgreSQL数据库复制——…`
    编码后 323 字节，`os.makedirs` 直接报 File name too long）。
    Hexo 发布这页时自己会用 `encodeURL` 把目录名编码成地址，
    所以地址形态跟原来一模一样。

    Returns the number of redirect pages written.
    """
    written = 0
    for old_path, new_path in REDIRECTS.items():
        bad = [c for c in INVALID_PATH_CHARS if c in old_path]
        if bad:
            print(f"  ! 跳过文章重定向 {old_path!r}：旧路径含文件名非法字符 {bad}"
                  f"（写出来的目录过不了 GitHub artifact 上传）",
                  file=sys.stderr)
            continue
        new_file = _redirect_target_file(new_path)
        if new_file is None:
            print(f"WARNING redirect target missing: {new_path}", file=sys.stderr)
            continue
        date = git_date(new_file)
        target_stamp = f"{date[:4]}/{date[5:7]}/{date[8:10]}"
        # The permalink slug drops the source extension (.md / .html).
        new_slug = new_path
        for ext in (".md", ".html", ".htm"):
            if new_slug.endswith(ext):
                new_slug = new_slug[: -len(ext)]
                break
        new_url = f"{SITE_ROOT}/{target_stamp}/{_site_encode_url(new_slug)}/"
        # 重定向页落在**旧 URL** 的日期段上。默认取新文件的日期（文章搬家时
        # 日期不变）；键里带了日期就照它写 —— 合并重复文章时旧 URL 的日期
        # 跟新文件对不上，只有照旧写才落得在真正的旧地址上。
        page_stamp = target_stamp
        dated = DATED_REDIRECT_RE.match(old_path)
        if dated:
            page_stamp = dated.group("stamp")
            old_path = dated.group("path")
        out_dir = os.path.join(SRC, page_stamp, old_path)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "index.md"), "w", encoding="utf-8") as f:
            f.write(
                REDIRECT_PAGE.format(
                    new_url=new_url,
                    title=new_path.rsplit("/", 1)[-1],
                )
            )
        written += 1
    return written


def write_category_redirects():
    """Generate redirect pages for category URLs that changed.

    A category page lives at /categories/<path>/.  When a section gains an
    _index.md (its category name changes) or is nested under a parent
    category (its path gains a prefix), the old URL 404s.  We emit a
    static redirect page there so old links keep working.

    旧分类名里带文件名非法字符的**跳过并喊一声**：那个目录在 Linux 上
    建得出来，可它会让整个产物传不上 GitHub（见 INVALID_PATH_CHARS）。
    宁可不发这一页（那个 URL 就没有内链指向它），也不能让部署断掉。

    Returns the number of redirect pages written.
    """
    written = 0
    for old_path, new_path in CATEGORY_REDIRECTS.items():
        bad = [c for c in INVALID_PATH_CHARS if c in old_path]
        if bad:
            print(f"  ! 跳过分类重定向 {old_path!r}：旧分类名含文件名非法字符 {bad}"
                  f"（写出来的目录过不了 GitHub artifact 上传）",
                  file=sys.stderr)
            continue
        new_url = f"{SITE_ROOT}/categories/{quote(new_path)}/"
        old_url = f"{SITE_ROOT}/categories/{quote(old_path)}/"
        out_dir = os.path.join(SRC, "categories", old_path)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "index.md"), "w", encoding="utf-8") as f:
            f.write(
                REDIRECT_PAGE.format(
                    new_url=new_url,
                    title=new_path,
                )
            )
        written += 1
    return written


#: 不算文章的目录：站点自己的元文档（攻略、工具说明、页面集合）。
META_CATS = ("blog", "tools", "page")


def collect_index_posts(posts_root, meta_cats=META_CATS):
    """Scan ``source/_posts`` and return one record per article.

    每条记录::

        {"title": ..., "url": ..., "cat": ..., "date": "YYYY-MM-DD", "top": int}

    ``url`` 是站点**真实**的 permalink——日期段 + 完整路径 + 挂载点前缀，
    由 ``site_root.permalink`` 一处拼出来。404 页的「最近发布」与它的
    搜索索引都从这里出，两个地方不许各拼各的。

    跳过 ``_index`` 与元文档目录（``blog/`` / ``tools/`` / ``page/``）——
    它们不是文章。
    """
    records = []
    if not os.path.isdir(posts_root):
        return records

    for fp in glob.glob(os.path.join(posts_root, "**", "*.md"), recursive=True):
        try:
            with open(fp, encoding="utf-8") as f:
                txt = f.read(4000)
        except OSError:
            continue
        rel = os.path.relpath(fp, posts_root).replace("\\", "/")
        parts = rel.split("/")
        cat = parts[0] if len(parts) > 1 else ""
        slug = parts[-1].replace(".md", "").replace(".html", "")
        if not slug or slug.startswith("_index") or cat in meta_cats:
            continue
        # 文章在站点里的相对路径（去掉扩展名）。站点的 permalink 是
        # /:year/:month/:day/:title/，:title 就是这个路径——**整条**，
        # 不是首尾两段：只拿 {cat}/{slug} 拼的话，db/nested/deep.md
        # 会被拼成 /db/deep/，中间那层掉了。
        post_path = os.path.splitext(rel)[0]
        title = _front_matter_title(txt) or slug
        dm = re.search(r"^date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", txt, re.M)
        top_m = re.search(r"^top:\s*([0-9]+)", txt, re.M)
        date_str = dm.group(1) if dm else "1970-01-01"
        top_n = int(top_m.group(1)) if top_m else 0
        records.append(
            {
                "title": title,
                "url": _permalink(date_str, post_path),
                "cat": cat or post_path.rsplit("/", 1)[-1],
                "date": date_str,
                "top": top_n,
            }
        )
    return records


def copy_view_counts_snapshot(src_dir=None, repo_root=None):
    """把仓库根的 data/view-counts.json 复制到 source/_data/。

    hexo 只把 ``source/_data/`` 里的 json 挂到 ``site.data`` 上（键名是
    文件名去掉后缀，即 ``view-counts``）。不复制的话，模板里的
    ``site.data['view-counts']`` 永远是 undefined，侧栏与首页那个 tab
    拿不到任何真实阅读量。

    源文件不在就返回 None——快照是**可选**的，缺了不该把整次同步带崩。
    """
    if src_dir is None:
        src_dir = SRC
    if repo_root is None:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "data", "view-counts.json")
    if not os.path.isfile(src):
        return None
    dest_dir = os.path.join(src_dir, "_data")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "view-counts.json")
    shutil.copyfile(src, dest)
    return dest


def main():
    # Preserve custom pages (source/all/, source/recommended/) across regeneration
    import tempfile

    preserved = tempfile.mkdtemp()
    all_path = os.path.join(SRC, "all")
    rec_path = os.path.join(SRC, "recommended")
    all_preserved = os.path.isdir(all_path)
    rec_preserved = os.path.isdir(rec_path)
    if all_preserved:
        shutil.move(all_path, os.path.join(preserved, "all"))
    if rec_preserved:
        shutil.move(rec_path, os.path.join(preserved, "recommended"))
    if os.path.exists(SRC):
        shutil.rmtree(SRC)
    if all_preserved:
        shutil.move(os.path.join(preserved, "all"), all_path)
    if rec_preserved:
        shutil.move(os.path.join(preserved, "recommended"), rec_path)
    shutil.rmtree(preserved)
    os.makedirs(POSTS)

    verification_dir = os.path.join(SRC, ".well-known")
    os.makedirs(verification_dir, exist_ok=True)
    verification_path = os.path.join(
        verification_dir, "vercount-verify-zd5pj09shdfkbm6h83ra5zzk.txt"
    )
    with open(verification_path, "w", encoding="utf-8") as f:
        f.write("vercount-domain-verify=growdu.github.io,zd5pj09shdfkbm6h83ra5zzk")
    print("Created Vercount verification file")

    section_titles = read_section_categories()
    cascade_map = read_cascade_categories()
    print(f"Section titles: {len(section_titles)}, cascade dirs: {len(cascade_map)}")

    copy_images()
    print("Images copied")

    n_md = 0
    n_html = 0
    for root, dirs, files in os.walk(DOCS):
        # Skip hidden directories (.pytest_cache, .venv, .hilo, .git ...).
        # They are build/tool artefacts that happen to contain .md files;
        # without this, e.g. docs/life/aiv/pipeline/.pytest_cache/README.md
        # became a published post ("pytest cache directory #") and got its
        # own Gitalk issue on the next deploy.
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        # §4.3 的路径排除规则：内部工程目录整棵不进产物。
        # 与上面那条隐藏目录守卫并列，不是替换它。
        prune_excluded_dirs(dirs)
        for f in sorted(files):
            if f.startswith("."):
                continue
            ext = os.path.splitext(f)[1].lower()
            fp = os.path.join(root, f)
            try:
                if ext == ".md":
                    if process(fp, section_titles, cascade_map):
                        n_md += 1
                elif ext in (".html", ".htm"):
                    # Naming convention: if an .html shares a basename
                    # with an .md in the same directory, the .html MUST
                    # carry a -html suffix (e.g. 'foo.html' ->
                    # 'foo-html.html') so the pair is visually distinct
                    # in the docs/ tree and the generated permalinks
                    # don't collide.  Detect violations here and fail
                    # loud — better to break the build than silently
                    # produce two posts with the same URL.
                    base_no_ext = os.path.splitext(f)[0]
                    if not base_no_ext.endswith("-html"):
                        twin_md = os.path.join(root, base_no_ext + ".md")
                        if os.path.isfile(twin_md):
                            print(
                                f"ERROR {fp}: shares basename with {twin_md} "
                                f"but is not suffixed with -html. Rename the .html "
                                f"file to {os.path.join(root, base_no_ext + '-html.html')} "
                                f"(see docs/blog/同名文章-html-与-md-版本管理.md).",
                                file=sys.stderr,
                            )
                            sys.exit(2)
                    if process_html(fp, section_titles, cascade_map):
                        n_html += 1
            except Exception as e:
                print(f"ERROR {fp}: {e}", file=sys.stderr)
    print(f"Markdown posts: {n_md}")
    print(f"HTML docs:      {n_html}")

    n_redirect = write_redirects()
    print(f"Redirect pages: {n_redirect}")

    n_cat_redirect = write_category_redirects()
    print(f"Category redirects: {n_cat_redirect}")

    # robots.txt for SEO
    robots_path = os.path.join(SRC, "robots.txt")
    with open(robots_path, "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n\nSitemap: https://growdu.cn/sitemap.xml\n")
    print("Created robots.txt")

    # PWA manifest (re-include icons[] on every regen so a fresh CI
    # checkout doesn't silently drop the 48x48 favicon + 192x192 logo
    # entries; aa9cfb6 originally restored them after a similar bug).
    manifest_path = os.path.join(SRC, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(
            '{\n  "name": "编程之路",\n  "short_name": "编程之路",\n  "description": "资深后端研发工程师的技术博客",\n  "start_url": "/",\n  "scope": "/",\n  "display": "standalone",\n  "background_color": "#ffffff",\n  "theme_color": "#009688",\n  "lang": "zh-CN",\n  "icons": [\n    {\n      "src": "/favicon.png",\n      "sizes": "48x48",\n      "type": "image/png"\n    },\n    {\n      "src": "/medias/logo.jpg",\n      "sizes": "192x192",\n      "type": "image/jpeg"\n    }\n  ]\n}\n'
        )
    print("Created manifest.json")

    # Custom SVG favicon (database icon)
    favicon_path = os.path.join(SRC, "favicon.svg")
    with open(favicon_path, "w", encoding="utf-8") as f:
        f.write(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#009688"/><ellipse cx="32" cy="18" rx="16" ry="6" fill="none" stroke="#fff" stroke-width="2.5"/><path d="M16 18v14a16 6 0 0 0 32 0V18" fill="none" stroke="#fff" stroke-width="2.5"/><path d="M16 32v14a16 6 0 0 0 32 0V32" fill="none" stroke="#fff" stroke-width="2.5"/></svg>'
        )
    print("Created favicon.svg")

    # Service worker for offline reading
    sw_path = os.path.join(SRC, "sw.js")
    with open(sw_path, "w", encoding="utf-8") as f:
        f.write(
            """const CACHE='blog-v3';self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==CACHE).map(x=>caches.delete(x)))).then(()=>self.clients.claim())));self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;const u=new URL(e.request.url);if(u.origin!==location.origin)return;const put=async(req,res)=>{try{if(res&&res.status===200&&res.clone){await caches.open(CACHE).then(c=>c.put(req,res.clone()));}}catch(_){}};if(e.request.headers.get('accept')&&e.request.headers.get('accept').includes('text/html')){e.respondWith(fetch(e.request).then(r=>{put(e.request,r);return r;}).catch(()=>caches.match(e.request)));}else{e.respondWith(caches.match(e.request).then(c=>c||fetch(e.request).then(r=>{put(e.request,r);return r;}).catch(()=>caches.match(e.request))));}});"""
        )
    print("Created sw.js")

    # 404 page (upgraded with search + recent posts)
    notfound_path = os.path.join(SRC, "404.html")
    with open(notfound_path, "w", encoding="utf-8") as f:
        f.write(
            _root_prefix_urls("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>404 · 页面走丢了 | growdu</title>
<meta name="description" content="页面不存在。试试在首页搜索，或浏览热门文章。">
<style>
:root{--c1:#009688;--c1l:#4dd0e1;--bg:#f8fafc;--card:#fff;--fg:#263238;--muted:#607d8b;--line:rgba(0,0,0,0.08)}
@media (prefers-color-scheme: dark){:root{--bg:#0f1417;--card:#1e272c;--fg:#eceff1;--muted:#b0bec5;--line:rgba(255,255,255,0.08)}}
*{margin:0;padding:0;box-sizing:border-box}
body{min-height:100vh;background:var(--bg);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;color:var(--fg);display:flex;align-items:center;justify-content:center;padding:32px 16px}
.wrap{max-width:680px;width:100%}
.card{background:var(--card);border-radius:18px;padding:48px 40px;box-shadow:0 8px 32px rgba(0,0,0,0.06);text-align:center}
.brand{display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:24px;color:var(--c1);font-weight:700;font-size:18px}
.brand img{width:32px;height:32px;border-radius:50%}
h1{font-size:96px;font-weight:900;color:var(--c1);line-height:1;letter-spacing:-2px;margin:0 0 8px}
h1 small{font-size:24px;color:var(--muted);font-weight:600;display:block;margin-top:6px;letter-spacing:0}
.lead{color:var(--muted);font-size:15px;margin:0 0 28px;line-height:1.7}
.search{display:flex;gap:8px;margin:0 0 28px}
.search input{flex:1;padding:12px 16px;font-size:14px;border:1px solid var(--line);border-radius:24px;background:var(--bg);color:var(--fg);outline:none;transition:border-color .15s}
.search input:focus{border-color:var(--c1)}
.search button{padding:0 22px;background:var(--c1);color:#fff;border:none;border-radius:24px;font-weight:600;cursor:pointer;font-size:14px;transition:background .15s}
.search button:hover{background:#00796b}
.divider{display:flex;align-items:center;gap:12px;margin:28px 0 16px;color:var(--muted);font-size:12px}
.divider::before,.divider::after{content:"";flex:1;height:1px;background:var(--line)}
.recent{list-style:none;text-align:left;margin:0 0 24px}
.recent li{padding:10px 0;border-bottom:1px solid var(--line)}
.recent li:last-child{border-bottom:none}
.recent a{color:var(--fg);text-decoration:none;display:flex;align-items:flex-start;gap:8px;font-size:14px;line-height:1.5}
.recent a:hover{color:var(--c1)}
.recent .title{flex:1}
.recent .cat{font-size:11px;color:var(--muted);background:var(--bg);padding:2px 8px;border-radius:10px;flex-shrink:0}
.actions{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-top:8px}
.btn{display:inline-flex;align-items:center;gap:6px;padding:10px 22px;border-radius:22px;font-size:14px;font-weight:600;text-decoration:none;transition:all .15s}
.btn-primary{background:var(--c1);color:#fff}
.btn-primary:hover{background:#00796b;transform:translateY(-1px)}
.btn-ghost{border:1px solid var(--line);color:var(--fg)}
.btn-ghost:hover{border-color:var(--c1);color:var(--c1)}
footer{text-align:center;color:var(--muted);font-size:12px;margin-top:20px}
footer a{color:var(--muted);text-decoration:none}
footer a:hover{color:var(--c1)}
@media (max-width:600px){.card{padding:32px 20px}h1{font-size:72px}.lead{font-size:14px}.actions{flex-direction:column;align-items:stretch}}
</style>
</head>
<body>
<div class="wrap">
<div class="card">
  <div class="brand">
    <img src="/medias/logo.jpg" alt="growdu">
    <span>growdu · 技术学习实践</span>
  </div>
  <h1>404<small>页面走丢了</small></h1>
  <p class="lead">你访问的页面可能搬走了、链接已过期，或者根本不存在。<br>试试下面的搜索框，或浏览最近文章 —</p>
  <form class="search" id="search-form" autocomplete="off">
    <input type="search" id="q" name="q" placeholder="搜索文章标题、标签…" autofocus>
    <button type="submit">搜索</button>
  </form>
  <div class="divider">最近发布</div>
  <ul class="recent" id="recent-list">
    <li style="color:var(--muted);font-size:13px;text-align:center;padding:14px 0">加载中…</li>
  </ul>
  <div class="actions">
    <a href="/" class="btn btn-primary"><i>←</i> 返回首页</a>
    <a href="javascript:history.length>1?history.back():location.href='/'" class="btn btn-ghost">返回上一页</a>
  </div>
</div>
<footer>
  <a href="/atom.xml">RSS</a> · <a href="/about/">关于</a> · <a href="mailto:growdu@gmail.com">联系</a>
</footer>
</div>
<script>
// 1) 站内搜索：用**精简索引**（title / url / cat）做标题匹配。
//
//    原来这里 fetch 的是 /search.xml —— 站点里根本没有这个文件
//    （hexo-generator-searchdb 出的是 search.json），于是这个 fetch 永远
//    失败，永远跳 Google，国内不可用：等于 404 页没有搜索。
//
//    也不直接用 search.json：那是 13.5 MB 的全文索引。让一个「页面不存在」
//    的页面下载 13.5 MB 才能搜一个词，等于把「搜索等于没有」换成「搜索慢到
//    等于没有」。全文搜索在首页（那里有 MiniSearch 索引）。
(function(){
  var form = document.getElementById('search-form');
  var input = document.getElementById('q');
  if (!form) return;
  var index = null;      // 精简索引，懒加载一次就留着
  var searched = false;  // 搜过就别让「最近发布」把结果冲掉

  function esc(s){
    return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){
      return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c];
    });
  }

  function loadIndex(){
    if (index) return Promise.resolve(index);
    return fetch('/search-lite.json').then(function(r){return r.json();}).then(function(d){
      index = Array.isArray(d) ? d : [];
      return index;
    });
  }

  form.addEventListener('submit', function(e){
    e.preventDefault();
    var q = (input.value || '').trim();
    if (!q) { input.focus(); return; }
    searched = true;
    var list = document.getElementById('recent-list');
    var divider = document.querySelector('.divider');
    loadIndex().then(function(posts){
      var needle = q.toLowerCase();
      var matched = posts.filter(function(p){
        var t = String(p.title || '').toLowerCase();
        var c = String(p.cat || '').toLowerCase();
        return t.indexOf(needle) >= 0 || c.indexOf(needle) >= 0;
      });
      var hits = matched.slice(0, 10);
      if (hits.length) {
        list.innerHTML = hits.map(function(p){
          return '<li><a href="'+esc(p.url)+'"><span class="title">'+esc(p.title)+'</span><span class="cat">'+esc(p.cat)+'</span></a></li>';
        }).join('');
        // 计数是**匹配的总数**，不是列出来的条数：命中 25 篇只列 10 条时，
        // 写「(10)」会让读者以为只有 10 篇，那 15 篇就无声无息地没了。
        if (divider) {
          divider.textContent = '搜索结果 ('+matched.length+')'
            + (matched.length > hits.length ? '，显示前 '+hits.length+' 条' : '');
        }
      } else {
        list.innerHTML = '<li style="text-align:center;color:var(--muted);padding:14px 0">没有匹配。换个词试试，或者 <a href="https://www.google.com/search?q='+encodeURIComponent(q+' site:growdu.cn')+'" target="_blank" rel="noopener">用搜索引擎找</a></li>';
        if (divider) divider.textContent = '搜索结果';
      }
    }).catch(function(){
      // 索引都拿不到：至少把 Google 兜底给出去
      window.location.href = 'https://www.google.com/search?q='+encodeURIComponent(q+' site:growdu.cn');
    });
  });

  // 2) Render recent posts from a pre-built JSON written by sync-hexo.py
  fetch('/recent-posts.json').then(function(r){return r.json();}).then(function(posts){
    if (!Array.isArray(posts) || !posts.length) return;
    if (searched) return;
    var html = posts.map(function(p){
      return '<li><a href="'+esc(p.url)+'"><span class="title">'+esc(p.title)+'</span><span class="cat">'+esc(p.cat)+'</span></a></li>';
    }).join('');
    document.getElementById('recent-list').innerHTML = html;
  }).catch(function(){});
})();
</script>
</body>
</html>""")
        )
    print("Created 404.html")

    # Recent posts JSON: consumed by the 404 page.
    # Source: source/_posts/**/*.md, sorted by `top` desc then `date` desc.
    # Skips `blog/` meta-docs and any path starting with `_index`.
    posts_root = os.path.join(SRC, "_posts")
    records = collect_index_posts(posts_root)

    # 404 页的「最近发布」：编辑推荐在前，其余按时间。
    scored = sorted(
        records, key=lambda r: (-r["top"], -int(r["date"].replace("-", "")))
    )
    recent = [
        {"title": r["title"], "url": r["url"], "cat": r["cat"]} for r in scored[:6]
    ]
    if recent:
        recent_path = os.path.join(SRC, "recent-posts.json")
        with open(recent_path, "w", encoding="utf-8") as f:
            json.dump(recent, f, ensure_ascii=False, indent=2)
        print("Wrote recent-posts.json (%d items)" % len(recent))

    # 404 页的搜索索引：**精简**版——每篇只有 title / url / cat。
    #
    # 不用站点的全文索引（search.json，13.5 MB）：让一个「页面不存在」的
    # 页面下载 13.5 MB 才能搜一个词，是把「搜索等于没有」换成「搜索慢到
    # 等于没有」。这里只匹配**标题和分类**，几十 KB 就能下完。
    #
    # 全文搜索在首页（那里有 MiniSearch 索引）。
    lite = [
        {"title": r["title"], "url": r["url"], "cat": r["cat"]}
        for r in sorted(records, key=lambda r: r["date"], reverse=True)
    ]
    if lite:
        lite_path = os.path.join(SRC, "search-lite.json")
        with open(lite_path, "w", encoding="utf-8") as f:
            json.dump(lite, f, ensure_ascii=False, separators=(",", ":"))
        print("Wrote search-lite.json (%d items)" % len(lite))

    # 首页首屏的策展清单（3 篇代表作 + 6 篇编辑推荐）。
    #
    # 真相在仓库根的 data/featured.json —— 作者改那个文件就能换首屏，
    # 不用去改模板。source/ 是 gitignore 的，所以必须复制到
    # source/_data/，hexo 才会把它挂到 site.data.featured 上。
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _featured_src = os.path.join(_repo_root, "data", "featured.json")
    if os.path.isfile(_featured_src):
        _featured_dir = os.path.join(SRC, "_data")
        os.makedirs(_featured_dir, exist_ok=True)
        shutil.copyfile(_featured_src, os.path.join(_featured_dir, "featured.json"))
        print("Copied data/featured.json -> source/_data/featured.json")
    else:
        print("WARNING: data/featured.json not found — 首页首屏将没有代表作")

    # 真实阅读量快照（GoatCounter 的 PV）。
    #
    # 真相在仓库根的 data/view-counts.json —— tools/fetch-view-counts.py
    # 抓的。跟 featured.json 同一个道理：source/ 是 gitignore 的，
    # 必须复制到 source/_data/，hexo 才会把它挂到 site.data 上
    # （键名是 'view-counts'，模板里读 site.data['view-counts']）。
    _vc_dest = copy_view_counts_snapshot()
    if _vc_dest:
        print("Copied data/view-counts.json -> %s" % _vc_dest)
    else:
        print("WARNING: data/view-counts.json not found — 侧栏不显示阅读量")

    # 2026-11-18：/database/ 与 /projects/ 两个落地页删掉了。
    # 旧 URL 不能 404（书签、搜索引擎、别人的博客都还链着），所以原地
    # 留一个重定向页，指到各自还在的正身。
    create_removed_landing_redirects()


def create_removed_landing_redirects():
    """为已经删掉的两个落地页留下重定向页。

    2026-11-18：``/database/``（数据库专题聚合页）与 ``/projects/``
    （GitHub 项目墙）删掉了 —— 站点要做减法，这两块属于「重复入口」：
    数据库的文章在分类页里，项目卡片在「关于我」页里。

    但**旧 URL 不能 404**：这两个地址已经发布出去很久了，书签、搜索引擎
    的索引、别人的博客都还链着。所以原地留一个重定向页，各自带
    ``meta refresh`` + ``canonical`` + 一个真链接（meta refresh 被禁掉时
    人还能走）。

    指向的正身：
      * ``/database/`` → ``/categories/``（分类总览，数据库文章在那儿）
      * ``/projects/`` → ``/about/``（「关于我」页有我的项目卡片）

    跟 ``write_redirects()`` 写的文章重定向页是同一套办法，只是这两页
    是**页面**而不是文章，日期段那套逻辑用不上。
    """
    pages = [
        ("database", "数据库专题", "/categories/"),
        ("projects", "我的开源项目", "/about/"),
    ]
    for slug, title, target in pages:
        path = os.path.join(SRC, slug, "index.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        new_url = SITE_ROOT + target
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                'title: "{title}"\n'
                "layout: false\n"
                "sitemap: false\n"
                "comments: false\n"
                "---\n"
                "\n"
                '<meta http-equiv="refresh" content="0; url={new_url}">\n'
                '<link rel="canonical" href="{new_url}">\n'
                '<meta name="robots" content="noindex, follow">\n'
                "<p>这一页已经合并到别处了，点击继续："
                '<a href="{new_url}">{new_url}</a></p>\n'
                '<script>location.replace("{new_url}");</script>\n'.format(
                    title=title, new_url=new_url
                )
            )
        print("Created redirect stub for /%s/ -> %s" % (slug, target))



if __name__ == "__main__":
    main()
