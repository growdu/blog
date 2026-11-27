#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 `data/tree-migration.json`：把 `docs/` 重排成「学习路径镜像」的搬运表。

**为什么要有这个脚本**：落点是**算出来的**，不是手抄的。
设计文档 §4.1 定了落点规则，这里把规则实现一遍，逐篇算出落点，
再把落点写成搬运表（`file_map` / `asset_map` / `out_map` / `drop_files` / …）。
规则改一次，重跑一次这个脚本，搬运表跟着变 ——
不留「文档里的表」和「脚本算的表」两份真相。

**它自己也是一次性的**：跑完就固化在 `data/tree-migration.json` 里。
留在仓库里是为了下一次搬家能重跑。

## 落点规则（§4.1）

> 一篇文章落到 `source-tracks/<赛道>/<阶段>/` 下，原顶层目录名这一层去掉，
> 顶层目录下面的结构原样保留。
>
> **再去掉一层（可选）**：顶层目录下的「一级子目录」如果
> ①整体落进同一个阶段、②不是 bundle（目录里没有 `index.md`）、
> ③扁平化之后不与同阶段任何其他内容重名 —— 那就把这个子目录名也去掉。

`source-tracks/` 下的文章走另一条路：系列目录**本身就是阶段目录**，
所以系列目录换成带编号的阶段目录，其余结构不动。

## 用法

```bash
python3 tools/build-tree-migration.py           # 生成表 + 打印核对数字
python3 tools/build-tree-migration.py --check   # 只核对，不写文件
```

## 输入

- `data/learning-path.pre-tree.json` —— **搬家前**的规则表（用来给每篇文章
  找到它当时的赛道与阶段；改赛道 id 时，靠它把旧阶段对上新的阶段目录）
- `data/learning-path.json` —— **搬家后**的规则表（赛道 id、阶段目录、中文名）
"""

import argparse
import collections
import importlib.util
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(REPO, "docs")
OLD_RULES = os.path.join(REPO, "data", "learning-path.pre-tree.json")
NEW_RULES = os.path.join(REPO, "data", "learning-path.json")
OUT_FILE = os.path.join(REPO, "data", "tree-migration.json")

#: 整棵不进产物的目录 —— 与 `tools/build-learning-path.py` 的同名集合一致。
#: 两处必须一样：少一个，多出来的文章就成了「没归类」的噪声。
EXCLUDED_DIR_NAMES = frozenset({
    "tests", "test", "fixtures", "plans", "pipeline",
    "build", "out", "_staging", "frames",
})

#: 资源文件不跟文章走的几种去向（§4.3、§9）。
#:
#: 判定顺序是**从上往下**，第一条命中的算数。
#:
#: - ``drop``：删掉 —— 重复文件、空文件、字节码、编辑器配置
#: - ``out``：移出 `docs/` 到 ``internal/`` —— 不是文章，也不是素材
#: - ``follow``：跟某个阶段走 —— 所在目录没有文章，但确实是那条线的素材
SPECIAL_RESOURCES = [
    ("__pycache__/", "drop", None),
    ("source-tracks/postgresql/logical-replication/sqlserver/unpacked/",
     "out", None),
    ("source-tracks/postgresql/.claude/", "drop", None),
    ("src/test/", "out", None),
    ("environment/vfox使用指南", "drop", None),
    ("report_restructured.pptx", "out", None),
    ("alg/alg_img/", "drop", None),
    ("code/", "follow", ("engineering", "L2-tooling")),
    ("pcap/", "follow", ("linux", "L4-networking/pcap")),
]

#: 扫不到、但要处理的东西：所在目录被排除规则（`test`）或隐藏目录挡掉了。
EXTRA_CLEANUP = [
    ("src/test/", "out", None),
    ("source-tracks/postgresql/.claude/", "drop", None),
]

#: 旧赛道的「家」→ 新赛道 id。
#:
#: 「家」= 那个赛道的系列目录都在这一层下面。搬完之后，家就是
#: `source-tracks/<赛道 id>/`。
#:
#: **为什么手写**：规则表推不出来 —— 系列的 `path_prefix` 里混着
#: 「系列目录」（`distributed/foundations/`）和「内容单元目录」
#: （`code/`、`language/python/`），两者不是一回事。表只有 7 条，
#: 每条都能对着树核对一遍。
#:
#: 没有家的赛道（AI 与工具、工程与语言、博客与自媒体、数据面），
#: 它们的旧内容散在好几个顶层目录里，赛道页是**新写**的 ——
#: 旧那些顶层目录页（`ai/_index.md` 之类，十几行的壳）归档。
TRACK_HOMES = {
    "source-tracks/postgresql": "postgresql",
    "distributed": "distributed",
    "source-tracks/ceph": "ceph",
    "source-tracks/linux-kernel": "linux-kernel",
    "source-tracks/linux": "linux",
    "life": "life",
    "platform-meta": "platform-meta",
}


def load_module(path, name):
    """按路径加载一个脚本当模块（`tools/` 不是包）。"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# 扫 docs/
# --------------------------------------------------------------------------


def scan_docs():
    """扫 `docs/`，返回 `(articles, resources)`。

    `articles` 里每一篇有三样东西：

    - ``corpus_rel``：**展平**之后的路径（`ai/claude安装教程`）——
      学习路径的规则是按它写的；
    - ``file_rel``：磁盘上的真实路径（`ai/claude安装教程/index.md`）——
      搬运用的是它；
    - ``is_bundle``：这篇是不是一个目录包（目录里有 `index.md`）。

    `resources` 是所有非文章文件（图片、源码附件、抓包文件……）。
    """
    articles = []
    resources = []
    for root, dirs, files in os.walk(DOCS):
        dirs[:] = sorted(d for d in dirs
                         if not d.startswith(".")
                         and d.lower() not in EXCLUDED_DIR_NAMES)
        for name in sorted(files):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, DOCS).replace(os.sep, "/")
            ext = os.path.splitext(name)[1].lower()
            if ext in (".md", ".html", ".htm"):
                if name in ("_index.md", "_index.html", "_index.htm"):
                    continue  # 分类目录页不是文章
                articles.append(_article(rel, name))
            else:
                resources.append(rel)
    articles.sort(key=lambda a: a["corpus_rel"])
    resources.sort()
    return articles, resources


def _article(rel, name):
    """一篇文章的展平路径与真实路径。"""
    fdir = os.path.dirname(rel)
    if name == "index.md":
        slug = os.path.basename(fdir)
        parent = os.path.dirname(fdir)
        flat = os.path.join(parent, slug) if parent and parent != "." else slug
        is_bundle = True
    else:
        stem = os.path.splitext(name)[0]
        if os.path.splitext(name)[1].lower() in (".html", ".htm") \
                and not stem.endswith("-html"):
            stem += "-html"
        flat = os.path.join(fdir, stem) if fdir and fdir != "." else stem
        is_bundle = False
    return {
        "corpus_rel": flat.replace(os.sep, "/"),
        "file_rel": rel,
        "is_bundle": is_bundle,
    }


def check_corpus(blp, articles):
    """展平规则跟 `tools/build-learning-path.py` 对得上吗？

    对不上就是两边各写了一份展平规则 —— 那正是「一个站有两个真相」，
    必须当场响。
    """
    mine = {a["corpus_rel"] for a in articles}
    theirs = {p["rel"] for p in blp.docs_corpus()}
    missing = sorted(theirs - mine)
    extra = sorted(mine - theirs)
    if missing or extra:
        print("展平规则对不上：", file=sys.stderr)
        for r in missing[:10]:
            print("  那边有这边没有：", r, file=sys.stderr)
        for r in extra[:10]:
            print("  这边有那边没有：", r, file=sys.stderr)
        raise SystemExit(1)


# --------------------------------------------------------------------------
# 赛道与阶段
# --------------------------------------------------------------------------


def stage_dirs(new_rules):
    """新规则表 → `{赛道id: {阶段id: 阶段目录}}`。"""
    out = {}
    for track in new_rules["tracks"]:
        out[track["id"]] = {s["id"]: s["dir"] for s in track["stages"]}
    return out


def track_aliases(new_rules):
    """新规则表 → `{旧赛道id: 新赛道id}`。

    改名的那两条赛道在规则表里带 `aliases` 字段（老 id）。
    别的赛道老 id 就是新 id。
    """
    out = {}
    for track in new_rules["tracks"]:
        for alias in track.get("aliases", []):
            out[alias] = track["id"]
        out.setdefault(track["id"], track["id"])
    return out


def series_to_stage(new_rules):
    """`platform-meta` 这类「系列目录就是阶段目录」的赛道 → `{系列名: 阶段目录}`。

    规则表里阶段目录叫 `L1-platform-overview`，系列目录叫 `platform-overview`
    —— 去掉 `L#-` 前缀就是系列名。
    """
    out = {}
    for track in new_rules["tracks"]:
        if track["id"] == "platform-meta":
            for stage in track["stages"]:
                _, _, suffix = stage["dir"].partition("-")
                out[suffix] = stage["dir"]
    return out


def classify_old(blp, old_rules, articles):
    """用**旧**规则表给每篇文章找到它当时的赛道与阶段。

    返回 `{corpus_rel: (旧赛道id, 旧阶段id)}`。
    """
    posts = [{"rel": a["corpus_rel"], "title": "", "date": "", "categories": [],
              "tags": [], "url": ""} for a in articles]
    tracks, unclassified = blp.classify(posts, old_rules)
    out = {}
    for track in tracks:
        for stage in track["stages"]:
            for post in stage.get("posts", []):
                out[post["rel"]] = (track["id"], stage["id"])
    if unclassified:
        raise SystemExit("有 %d 篇文章在旧规则表里没归类" % len(unclassified))
    return out


# --------------------------------------------------------------------------
# 落点
# --------------------------------------------------------------------------


def compute_landings(articles, old_stage, new_rules):
    """算每篇文章的落点。

    返回 `{corpus_rel: 新文件路径}`（含扩展名，bundle 是 `.../index.md`）。
    """
    aliases = track_aliases(new_rules)
    dirs = stage_dirs(new_rules)
    pm_series = series_to_stage(new_rules)

    # 每篇文章的「阶段前缀」= source-tracks/<新赛道>/<新阶段目录>
    prefix = {}
    for art in articles:
        rel = art["corpus_rel"]
        track_id, stage_id = old_stage[rel]
        if rel.startswith("platform-meta/"):
            # platform-meta 从「寄居在 blogging 下」升为独立赛道：
            # 阶段由**系列目录**决定，不再由旧规则表的博客阶段决定。
            series = rel.split("/")[1]
            if series not in pm_series:
                raise SystemExit("platform-meta 里有认不出的系列：%s" % series)
            prefix[rel] = "source-tracks/platform-meta/" + pm_series[series]
        else:
            new_track = aliases[track_id]
            stage_dir = dirs[new_track].get(stage_id)
            if stage_dir is None:
                raise SystemExit("规则表里没有 %s 的阶段 %s" % (new_track, stage_id))
            prefix[rel] = "source-tracks/%s/%s" % (new_track, stage_dir)

    # 第一步：不扁平，算出「顶层目录 / 一级子目录」的分组
    groups = collections.defaultdict(list)
    for art in articles:
        parts = art["corpus_rel"].split("/")
        if parts[0] == "source-tracks" or len(parts) < 3:
            continue
        groups[(parts[0], parts[1])].append(art)

    # 条件 ①（整体落同一个阶段）与 ②（不是 bundle）
    flat_ok = {}
    for (top, unit), members in groups.items():
        stages = {prefix[m["corpus_rel"]] for m in members}
        # 这个子目录自己是个 bundle（目录里有 index.md）→ 不能扁平：
        # 扁平会把它的子文章从它自己的目录里拽出去。
        is_bundle = os.path.isfile(os.path.join(DOCS, top, unit, "index.md"))
        flat_ok[(top, unit)] = (len(stages) == 1 and not is_bundle)

    # 第二步：算落点 + 冲突守卫（条件 ③）
    for _ in range(30):
        dest = _landings(articles, prefix, flat_ok)
        clash = collections.defaultdict(list)
        for rel, path in dest.items():
            clash[path].append(rel)
        bad = {k: v for k, v in clash.items() if len(v) > 1}
        if not bad:
            return dest
        disable = set()
        for path, rels in bad.items():
            for rel in rels:
                parts = rel.split("/")
                if parts[0] == "source-tracks" or len(parts) < 3:
                    continue
                unit = (parts[0], parts[1])
                if flat_ok.get(unit):
                    disable.add(unit)
        if not disable:
            raise SystemExit("落点冲突没法靠守卫解开：%s" % bad)
        for unit in disable:
            flat_ok[unit] = False
    raise SystemExit("落点冲突守卫转了 30 轮还没解开")


def _landings(articles, prefix, flat_ok):
    """按当前的扁平决定，算出每篇文章的落点。"""
    out = {}
    for art in articles:
        rel = art["corpus_rel"]
        parts = rel.split("/")
        if parts[0] == "source-tracks":
            # 系列目录 = 阶段目录：换掉这一层，其余原样保留
            rest = parts[3:]
            tail = "/".join(rest)
        else:
            tail = "/".join(parts[1:])
            if len(parts) >= 3 and flat_ok.get((parts[0], parts[1])):
                tail = tail[len(parts[1]) + 1:]
        path = prefix[rel] + ("/" + tail if tail else "")
        if art["is_bundle"]:
            path += "/index.md"
        else:
            path += os.path.splitext(art["file_rel"])[1]
        out[rel] = path
    return out


# --------------------------------------------------------------------------
# 资源
# --------------------------------------------------------------------------


def compute_assets(articles, dest, resources):
    """算每个资源的落点。

    规则：资源的**主人**是它所在目录里最近的那篇文章（往上找）。
    跟着主人走，它和引用它的文章就还在同一个目录下，相对链接不用改。

    返回 `(asset_map, out_map, drop_files, unowned)`：
    - `asset_map`：旧路径 → 新路径
    - `out_map`：移出 `docs/` 的（进 `internal/`）
    - `drop_files`：删掉的
    - `unowned`：找不到主人的资源（它们的去向单独定）
    """
    # 主人目录 → 新目录
    owner_new = {}
    for art in articles:
        rel = art["corpus_rel"]
        old_dir = os.path.dirname(art["file_rel"])
        new_dir = os.path.dirname(dest[rel])
        owner_new[old_dir] = new_dir

    asset_map = {}
    out_map = {}
    drop_files = []
    unowned = []
    for res in resources:
        special = _special(res)
        if special is not None:
            action, target = special
            if action == "drop":
                drop_files.append(res)
            elif action == "out":
                out_map[res] = "internal/" + res
            else:  # follow
                track, path = target
                asset_map[res] = "source-tracks/%s/%s/%s" % (
                    track, path, "/".join(res.split("/")[1:]))
            continue
        owner = None
        cur = os.path.dirname(res)
        while cur and cur != ".":
            if cur in owner_new:
                owner = cur
                break
            cur = os.path.dirname(cur)
        if owner is None:
            unowned.append(res)
            continue
        new_path = os.path.join(owner_new[owner],
                                 os.path.relpath(res, owner)).replace(os.sep, "/")
        asset_map[res] = new_path
    return asset_map, out_map, drop_files, unowned


def _special(res):
    """资源有没有特殊去向？返回 `(动作, 目标)` 或 None。"""
    for prefix, action, target in SPECIAL_RESOURCES:
        if prefix in res:
            return (action, target)
    return None


def extra_cleanup():
    """扫不到、但要处理的东西（所在目录被排除规则或隐藏目录挡掉了）。"""
    out_map = {}
    drop_files = []
    for prefix, action, _target in EXTRA_CLEANUP:
        root = os.path.join(DOCS, prefix)
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in files:
                rel = os.path.relpath(os.path.join(dirpath, name),
                                      DOCS).replace(os.sep, "/")
                if action == "drop":
                    drop_files.append(rel)
                else:
                    out_map[rel] = "internal/" + rel
    return out_map, drop_files


# --------------------------------------------------------------------------
# 表的其余几段
# --------------------------------------------------------------------------


def build_projects(new_rules):
    """11 块 `projects` —— 每条赛道一块。

    `series` 的 slug 是阶段目录名（带 `L#-` 前缀，顺序即学习顺序），
    值是阶段的中文名；`series_meta` 是阶段的一句话说明。
    """
    projects = []
    for track in new_rules["tracks"]:
        series = {}
        series_meta = {}
        for stage in track["stages"]:
            series[stage["dir"]] = stage["title"]
            series_meta[stage["dir"]] = stage.get("goal", "")
        projects.append({
            "target_root": "source-tracks/%s" % track["id"],
            "display_name": track["title"],
            "series": series,
            "series_meta": series_meta,
        })
    return projects


def build_drop_index():
    """现有的 `_index.md` 全部作废 —— 新的目录页由 `write_index_files()` 重写。

    分类页 2026-11-19 已退休，`_index.md` 现在只当**分类链的载体**
    （`cascade.categories`）。旧的那一份带着旧赛道名与旧阶段名，
    留着就是两份真相。

    **注意**：这张表是「旧目录页的名单」，不是「删掉的名单」。
    每一份的去向在 `index_map`（跟着搬）或 `index_archive`（归档）里。
    """
    out = []
    for root, dirs, files in os.walk(DOCS):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if name in ("_index.md", "_index.html", "_index.htm"):
                out.append(os.path.relpath(os.path.join(root, name),
                                           DOCS).replace(os.sep, "/"))
    return sorted(out)


def series_map(old_rules, new_rules):
    """旧系列目录 → 新阶段目录。

    「系列目录」= 赛道目录下面那一层（`source-tracks/postgresql/storage-engine/`）。
    规则表里每个阶段的 `path_prefix` 写着它管哪些目录；落在**赛道目录
    下面**的那些就是系列目录 —— 它们一个对一个地变成阶段目录。

    顶层的内容单元目录（`code/`、`life/gaokao/`、`protocol/`…）不算：
    它们是「单元」，不是「系列」，文章会被摊平进阶段目录。
    """
    aliases = track_aliases(new_rules)
    dirs = stage_dirs(new_rules)
    home_of = {track: home for home, track in TRACK_HOMES.items()}
    out = {}
    for track in old_rules["tracks"]:
        new_track = aliases[track["id"]]
        home = home_of.get(new_track)
        if not home:
            continue
        for stage in track["stages"]:
            new_stage = dirs[new_track].get(stage["id"])
            if not new_stage:
                continue
            for rule in stage.get("match", []):
                pref = (rule.get("path_prefix") or "").rstrip("/")
                if not pref or not pref.startswith(home + "/"):
                    continue
                out[pref] = "source-tracks/%s/%s" % (new_track, new_stage)
    # platform-meta：从「寄居在博客下」升为独立赛道，系列目录 → 阶段目录
    for series, stage_dir in series_to_stage(new_rules).items():
        out["platform-meta/" + series] = "source-tracks/platform-meta/" + stage_dir
    return out


def compute_index_landings(articles, dest, old_rules, new_rules):
    """旧 `_index.md` 的去向。

    返回 `(index_map, index_archive)`：

    - `index_map`：老目录页 → 新目录页（跟着它那个目录搬走）
    - `index_archive`：搬不走的 → `internal/legacy-index/<原路径>`

    **为什么不全删**：`_index.md` 是不发布的目录页（分类页 2026-11-19
    已退休），可里面有人手写的东西 —— PostgreSQL 那张「数据库总览」的
    总图、人生那条「路径 A / B / C」的阅读路线。删了就没了；
    留在 `docs/` 里又变成一份没人维护的旧结构说明。
    折中：**跟着搬的跟着搬，搬不走的归档。**

    **落点怎么定**，三档：

    1. 赛道目录（`TRACK_HOMES`）→ 新的赛道目录；
    2. 系列目录（`series_map()`）→ 新的阶段目录；
    3. 其余目录 → 它底下文章的落点（最浅的那一层），
       但**只认赛道目录和阶段目录** —— 阶段目录下面再放一个
       `_index.md`，分类链就多出一级（四级链），文章归不进赛道。

    一个新目录只放得下一份目录页：文章多的那个赢，其余归档。
    """
    series = series_map(old_rules, new_rules)

    # 目录 → 它底下（递归）的文章落到了哪些新目录
    land = collections.defaultdict(set)
    size = collections.defaultdict(int)
    for art in articles:
        new_dir = os.path.dirname(dest[art["corpus_rel"]])
        parts = art["file_rel"].split("/")
        for i in range(1, len(parts)):
            land["/".join(parts[:i])].add(new_dir)
            size["/".join(parts[:i])] += 1

    index_map = {}
    index_archive = {}
    index_keep = []
    # 新目录 → 抢这个位置的旧目录
    candidates = collections.defaultdict(list)

    for rel in build_drop_index():
        old_dir = os.path.dirname(rel)
        if old_dir == "source-tracks":
            # 顶层容器页：原地不动，交给 `_write_index()` 刷新
            index_keep.append(rel)
            continue
        if old_dir in TRACK_HOMES:
            new_rel = "source-tracks/%s/_index.md" % TRACK_HOMES[old_dir]
            if new_rel == rel:
                # 已经在赛道目录上了 —— 原地留着，`_write_index()` 合并
                # （PostgreSQL 那张「数据库总览」的总图就在里面）。
                index_keep.append(rel)
            else:
                index_map[rel] = new_rel
            continue
        if old_dir in series:
            candidates[series[old_dir]].append((old_dir, True))
            continue
        new_dir = _shallowest(land.get(old_dir))
        if new_dir is None or not _is_track_or_stage(new_dir):
            # 文章散在好几个赛道（落点找不到一个共同的祖先），
            # 或者落点在阶段目录下面（分类链会多出一级）—— 归档。
            index_archive[rel] = "internal/legacy-index/" + rel
            continue
        candidates[new_dir].append((old_dir, False))

    # 一个新目录只放得下一份目录页：
    # **系列目录优先**（它就是这一段的主页），其次文章多的赢。
    for new_dir, olds in candidates.items():
        olds.sort(key=lambda item: (not item[1], -size[item[0]], item[0]))
        for i, (old_dir, _is_series) in enumerate(olds):
            rel = old_dir + "/_index.md"
            if i == 0:
                index_map[rel] = new_dir + "/_index.md"
            else:
                index_archive[rel] = "internal/legacy-index/" + rel
    return index_map, index_archive, sorted(index_keep)


def _is_track_or_stage(new_dir):
    """这个落点是赛道目录或者阶段目录吗？

    分类链是**三级**（内容库 → 赛道 → 阶段）。阶段目录下面再放一个
    `_index.md`，链就变成四级 —— 文章归不进赛道。
    """
    parts = new_dir.split("/")
    return len(parts) in (2, 3) and parts[0] == "source-tracks"


def _shallowest(dirs):
    """一组落点目录里最浅的那个（前提：它是其余目录的祖先）。

    系列目录里的文章会落到阶段目录**和**它的子目录里（子目录没被扁平化时），
    所以目录页该落在最浅的那一层 —— 也就是阶段目录本身。
    """
    if not dirs:
        return None
    best = min(dirs, key=lambda d: (d.count("/"), d))
    for d in dirs:
        if d != best and not d.startswith(best + "/"):
            return None
    return best


def build_ref_rewrites(old_rules, dest):
    """代码与配置里硬编码的 `docs/` 路径（§8.1）。

    扫的是**代码与配置**（`.py` / `.js` / `.json` / `.yml` / `.sh` …），
    散文（`.md`）里的路径提及不动 —— 那是文章在讲历史结构。

    只看 **git 入库的文件**：构建产物（`public/`、`source/`、`db.json`）
    是生成的，改了也没用；`.remember/` 之类的本地目录也不入库。

    `data/` 整个跳过：那几份 JSON 要么由脚本重新生成
    （`redirects.json` / `date-overrides.json` / `migration-moves.json`），
    要么是历史快照（`retired-taxonomy-paths.json`）。

    返回 `[{"file": ..., "form": ...}]`。
    """
    code_exts = {".py", ".js", ".mjs", ".cjs", ".ts", ".json", ".yml", ".yaml",
                 ".sh", ".bash", ".toml", ".cfg", ".ini", ".conf"}
    skip_prefixes = ("data/", "docs/", "public/", "source/", "internal/",
                     "node_modules/", ".git/")
    forms = ("docs", "flat", "postid", "permalink", "cid")
    out = []
    for rel in _git_tracked():
        ext = os.path.splitext(rel)[1].lower()
        if ext not in code_exts:
            continue
        if rel.startswith(skip_prefixes):
            continue
        try:
            with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        hit = set()
        for old_rel, new_rel in dest.items():
            for form in forms:
                old_text = _old_text(old_rel, form)
                new_text = _old_text(new_rel, form)
                if not old_text or old_text == new_text:
                    continue
                if old_text in text:
                    hit.add(form)
        for form in sorted(hit):
            out.append({"file": rel, "form": form})
    return out


def _git_tracked():
    """入库的文件（相对仓库根，正斜杠）。"""
    import subprocess
    res = subprocess.run(["git", "ls-files", "-z"], cwd=REPO,
                         capture_output=True, text=True)
    return [p for p in res.stdout.split("\0") if p]


def _old_text(rel, form):
    """一个 docs 相对路径在某种形态下的字面写法。"""
    if form == "permalink":
        return "/" + _permalink_path(rel) + "/"
    return _path_form(rel, form)


def _path_form(rel, form):
    """一个 docs 相对路径的某种写法（跟 `migrate-tree.py` 同一套）。"""
    base = os.path.basename(rel)
    if base in ("index.md", "index.html", "index.htm"):
        parent = os.path.dirname(rel)
        flat = (parent + ".md") if parent else "index.md"
        cid = parent
    else:
        flat = rel
        cid = os.path.splitext(rel)[0]
    return {"docs": rel, "flat": flat,
            "postid": os.path.splitext(flat)[0], "cid": cid}[form]


def _permalink_path(rel):
    """站内地址里的路径段（不含日期段）。"""
    base = os.path.basename(rel)
    if base in ("index.md", "index.html", "index.htm"):
        return os.path.dirname(rel)
    stem, ext = os.path.splitext(rel)
    if ext.lower() in (".html", ".htm") and not os.path.basename(stem).endswith("-html"):
        stem += "-html"
    return stem


def build_category_redirects(new_rules, articles, dest):
    """旧分类名 → 新分类名（§7.3）。

    旧分类页（`_index.md`）全部作废，指向它们的链接要有个去处。
    分类页已经退休，映射到哪一层都一样 —— 这张表只保证
    「旧名字有一个去处」，不追求精确。

    怎么算去处：看那个旧分类目录底下的文章搬到了哪儿。
    全落一个阶段 → 那个阶段的中文名；
    落到好几个阶段（顶层目录就是这样）→ 那条赛道的中文名。
    """
    stage_title = {}
    track_title = {}
    for track in new_rules["tracks"]:
        track_title[track["id"]] = track["title"]
        for stage in track["stages"]:
            stage_title[(track["id"], stage["dir"])] = stage["title"]

    # 顶层目录 → 那条赛道（按文章数多的那条算）
    top_track = collections.defaultdict(collections.Counter)
    for art in articles:
        top = art["file_rel"].split("/")[0]
        parts = dest[art["corpus_rel"]].split("/")
        top_track[top][parts[1]] += 1

    # 旧分类目录 → 落到哪儿
    dir_stage = collections.defaultdict(set)
    dir_track = collections.defaultdict(collections.Counter)
    for art in articles:
        old_dir = os.path.dirname(art["file_rel"])
        parts = dest[art["corpus_rel"]].split("/")
        dir_stage[old_dir].add((parts[1], parts[2]))
        dir_track[old_dir][parts[1]] += 1

    out = {}
    for root, dirs, files in os.walk(DOCS):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if name not in ("_index.md", "_index.html", "_index.htm"):
                continue
            path = os.path.join(root, name)
            old_dir = os.path.relpath(root, DOCS).replace(os.sep, "/")
            if old_dir == ".":
                old_dir = ""
            title = _read_title(path)
            if not title:
                continue
            stages = dir_stage.get(old_dir, set())
            if len(stages) == 1:
                new_title = stage_title.get(next(iter(stages)), "")
            elif old_dir:
                top = old_dir.split("/")[0]
                track = top_track[top].most_common(1)
                new_title = track_title.get(track[0][0], "") if track else ""
            else:
                new_title = ""
            if new_title:
                out[title] = new_title
    return out


def _read_title(path):
    """一个 markdown 文件的标题（front matter 优先，其次首个 H1）。"""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return ""
    import re
    m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description="生成 docs/ 重排的搬运表")
    ap.add_argument("--check", action="store_true", help="只核对，不写文件")
    args = ap.parse_args()

    with open(OLD_RULES, encoding="utf-8") as fh:
        old_rules = json.load(fh)
    with open(NEW_RULES, encoding="utf-8") as fh:
        new_rules = json.load(fh)

    blp = load_module(os.path.join(REPO, "tools", "build-learning-path.py"),
                      "build_learning_path")

    articles, resources = scan_docs()
    check_corpus(blp, articles)
    print("扫到文章 %d 篇、资源 %d 个" % (len(articles), len(resources)))

    old_stage = classify_old(blp, old_rules, articles)
    dest = compute_landings(articles, old_stage, new_rules)
    print("落点算完：%d 篇，冲突 0" % len(dest))

    asset_map, out_map, drop_files, unowned = compute_assets(articles, dest, resources)
    extra_out, extra_drop = extra_cleanup()
    out_map.update(extra_out)
    drop_files.extend(extra_drop)
    print("资源：搬 %d、删 %d、移出 %d（无主 %d）"
          % (len(asset_map), len(drop_files), len(out_map), len(unowned)))
    if unowned:
        for res in unowned[:20]:
            print("  无主资源没定去留：", res)
        raise SystemExit("有 %d 个资源没定去留" % len(unowned))

    # 落点冲突自查：同一路径不能落两篇
    clash = collections.defaultdict(list)
    for rel, path in dest.items():
        clash[path].append(rel)
    bad = {k: v for k, v in clash.items() if len(v) > 1}
    if bad:
        raise SystemExit("落点冲突：%s" % bad)

    # 资源落点自查：同一路径不能落两个资源
    clash = collections.defaultdict(list)
    for res, path in asset_map.items():
        clash[path].append(res)
    bad = {k: v for k, v in clash.items() if len(v) > 1}
    if bad:
        raise SystemExit("资源落点冲突：%s" % bad)

    file_map = {}
    for art in articles:
        file_map[art["file_rel"]] = dest[art["corpus_rel"]]

    table = collections.OrderedDict()
    table["version"] = 2
    table["updated"] = "2026-11-26"
    table["note"] = (
        "把 `docs/` 重排成「学习路径镜像」的搬运表。\n\n"
        "**这张表是算出来的**：`tools/build-tree-migration.py` 按设计文档 §4.1 "
        "的落点规则逐篇算出落点，再写成这张表。改规则就重跑那个脚本，"
        "不要手改这里。\n\n"
        "段说明：\n"
        "- `file_map`：590 篇文章的落点（逐篇）\n"
        "- `asset_map`：资源的落点（逐文件，一对一）\n"
        "- `out_map`：移出 `docs/` 的东西（进 `internal/`，不发布）\n"
        "- `drop_files`：直接删掉的东西（重复文件、空文件、字节码）\n"
        "- `drop_index`：旧的 `_index.md` 名单（去向看 `index_map` / `index_archive` / `index_keep`）\n"
        "- `index_map`：跟着目录搬走的旧目录页\n"
        "- `index_archive`：搬不走的旧目录页（存进 `internal/legacy-index/`）\n"
        "- `index_keep`：原地不动的旧目录页（已经落在新结构里的那些）\n"
        "- `projects`：11 条赛道各一块，赛道名与阶段名从 `data/learning-path.json` 读\n"
        "- `ref_rewrites`：代码与配置里硬编码的 `docs/` 路径")
    table["file_map"] = dict(sorted(file_map.items()))
    table["asset_map"] = dict(sorted(asset_map.items()))
    table["out_map"] = dict(sorted(out_map.items()))
    table["drop_files"] = sorted(drop_files)
    table["drop_index"] = build_drop_index()
    index_map, index_archive, index_keep = compute_index_landings(
        articles, dest, old_rules, new_rules)
    table["index_map"] = dict(sorted(index_map.items()))
    table["index_archive"] = dict(sorted(index_archive.items()))
    table["index_keep"] = index_keep
    table["projects"] = build_projects(new_rules)
    table["category_redirects"] = build_category_redirects(new_rules, articles, dest)
    table["ref_rewrites"] = build_ref_rewrites(old_rules, dest)

    payload = json.dumps(table, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        with open(OUT_FILE, encoding="utf-8") as fh:
            current = fh.read()
        if current == payload:
            print("表跟磁盘上的一致。")
            return 0
        print("表跟磁盘上的**不一致** —— 重跑一次（不加 --check）。")
        return 1

    with open(OUT_FILE, "w", encoding="utf-8") as fh:
        fh.write(payload)
    print("写了 %s" % OUT_FILE)

    # --- 核对数字（设计文档 §4.2 / §11） ---
    by_track = collections.Counter()
    by_stage = collections.Counter()
    depth = collections.Counter()
    for rel, path in dest.items():
        parts = path.split("/")
        by_track[parts[1]] += 1
        by_stage["/".join(parts[1:3])] += 1
        depth[path.count("/")] += 1
    print("\n按赛道：")
    for track in sorted(by_track):
        print("  %-14s %d" % (track, by_track[track]))
    print("\n按阶段：")
    for stage in sorted(by_stage):
        print("  %-46s %d" % (stage, by_stage[stage]))
    print("\n落点深度：%s" % dict(sorted(depth.items())))
    print("表格大小：%d 字节" % len(payload.encode("utf-8")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
