#!/usr/bin/env python3
"""按 `data/tree-migration.json` 把 `docs/` 里的文章搬到新目录树。

**为什么需要它**：迁移不是「改个目录名」那么便宜。三件事会同时坏掉，
而这三件事肉眼都看不出来：

1. **日期**。`sync-hexo.py:606 git_date()` 走的是
   `git log --all --reverse -- <路径>` —— 路径一变，最早的提交就是
   「搬运」那一次，全站文章日期一起跳到搬运日，首页被冲垮，
   重定向页也会写到错误的旧 URL（`write_redirects()` 用新文件的日期
   拼旧 URL 的日期段）。**对策**：搬之前把 `git_date()` 的返回值按
   **新路径**固化下来。
2. **相对链接**。`sync-hexo.py:1407 rewrite_links()` 是在**编译时**
   按「引用方所在的 docs 目录」解析每条相对链接的。文章一搬，
   「同目录的兄弟」可能已经搬到另一个系列去了，链接就断。
   **对策**：搬完把被搬文件里的相对链接按新位置重算一遍，
   留在原地的文件里指向被搬文章的链接同样要改。
3. **站点外部的硬编码路径**。`tools/` `data/` `tests/` `publish/`
   里散着一百多处 docs 相对路径，搬完就失配。

**幂等**：同一份迁移表重复跑不会搬第二次（`git mv` 之前先看目标在不在），
所以中断了可以接着跑。

## 怎么用

```bash
# 1. 先看要搬什么（默认就是 dry-run）
python3 tools/migrate-tree.py

# 2. 真搬
python3 tools/migrate-tree.py --apply

# 3. 搬完自检：日期逐篇比对、死链、图、测试
python3 tools/capture-dates.py --check data/date-overrides.json
python3 tools/check-internal-links.py
python3 tools/check-mermaid.py
python3 -m pytest tests/ -q
```

## 边界

- **只搬 `docs/` 下的东西**。`internal/` 里的文件是「从 docs 移出去、
  不发布」的，脚本只负责搬，不负责判断哪一篇该移出去 ——
  那是 `data/tree-migration.json` 里的 `out_map` 表说了算。
- **不改文章正文的意思**。脚本只重写链接文字和 front matter 里的
  路径，正文一个字不动。
- **不提交**。搬完的改动留在工作区，由人看过再提交。
"""

import argparse
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
from urllib.parse import quote, unquote

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(REPO, "docs")
MIGRATION_FILE = "data/tree-migration.json"
DATE_FILE = "data/date-overrides.json"

# 图片链接（`![]()`）与普通链接分开处理：图片解析到的是**文件**，
# 不存在 bundle 那套「index.md 代表整个目录」的规则。
LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

#: 重定向表里**带日期的键**（``2022/10/25/cluster/raft/…``）—— 旧 URL
#: 当初发布时的日期段。跟 ``tools/sync-hexo.py`` 的 ``DATED_REDIRECT_RE``
#: 是同一套写法（两处各写一份，是有意付的重复：迁移脚本不 import 站点
#: 脚本，站点脚本也不 import 迁移脚本）。
DATED_REDIRECT_RE = re.compile(r"^(?P<stamp>\d{4}/\d{2}/\d{2})/(?P<path>.+)$")

EXTERNAL_PREFIXES = (
    "http://", "https://", "data:", "mailto:", "tel:", "ftp://",
    "javascript:", "about:", "//", "#",
)


# --------------------------------------------------------------------------
# 迁移表
# --------------------------------------------------------------------------


def load_migration(path=None):
    with open(os.path.join(REPO, path or MIGRATION_FILE), encoding="utf-8") as fh:
        return json.load(fh)


def load_redirects(path="data/redirects.json"):
    """现存的 ``data/redirects.json``（重写之前的那一份）。

    带日期的键是手工补的，重写时得留着 —— ``build_redirects`` 只从
    ``moves`` 推得出普通的键。
    """
    full = os.path.join(REPO, path)
    if not os.path.exists(full):
        return {}
    with open(full, encoding="utf-8") as fh:
        return json.load(fh)


def effective_map(table):
    """把 `dir_map` + `file_map` 摊平成一张「旧路径 → 新路径」的表。

    `file_map` 优先于 `dir_map` —— 目录级规则是「整目录搬」，
    文件级规则是「这一篇例外」。`out_map` 里的文件不进新树。
    """
    out = {}
    for old_dir, new_dir in table.get("dir_map", {}).items():
        prefix = old_dir.rstrip("/") + "/"
        for rel in sorted(_walk_docs()):
            if rel.startswith(prefix) and _is_article(rel):
                out[rel] = new_dir.rstrip("/") + "/" + rel[len(prefix):]
    out.update(table.get("file_map", {}))
    for rel in table.get("out_map", {}):
        out.pop(rel, None)
    return out


def _walk_docs():
    """`docs/` 下所有文件（相对 docs/，正斜杠）。"""
    out = []
    for root, dirs, files in os.walk(DOCS):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), DOCS)
            out.append(rel.replace(os.sep, "/"))
    return out


def _is_article(rel):
    """算不算「一篇文章」（`_index.md` 是分类目录页，不算）。"""
    ext = os.path.splitext(rel)[1].lower()
    return ext in (".md", ".html", ".htm") and not rel.endswith("_index.md")


def _is_index_file(rel):
    """是不是分类目录页（`_index.md` / `_index.html`）。"""
    return os.path.basename(rel).startswith("_index.")


# --------------------------------------------------------------------------
# 日期
# --------------------------------------------------------------------------


def load_sync_hexo():
    """把 `tools/sync-hexo.py` 当模块加载 —— 日期语义必须一模一样。"""
    import importlib.util

    os.chdir(REPO)
    spec = importlib.util.spec_from_file_location(
        "sync_hexo", os.path.join(REPO, "tools", "sync-hexo.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def capture_dates(module):
    """当前 `docs/` 里每一篇文章的 `git_date()`。"""
    table = {}
    for rel in sorted(_walk_docs()):
        if not _is_article(rel):
            continue
        table[rel] = module.git_date(os.path.join(DOCS, rel))
    return table


# --------------------------------------------------------------------------
# 链接解析（与 sync-hexo.py 同规则）
# --------------------------------------------------------------------------


def _bundle_index(abs_dir):
    for ext in ("index.md", "index.html", "index.htm", "_index.md"):
        p = os.path.join(abs_dir, ext)
        if os.path.isfile(p):
            return p
    return None


def resolve_in_dir(target_dir_rel, tail):
    """链接落在 `target_dir_rel` 目录下的哪个文件上。

    `tail` 是链接最后一节（`index.html` / `x.md` / 空串）。
    返回 docs 相对路径，找不到返回 None。

    规则与 `sync-hexo.py:_resolve_link_target()` 对齐：
    - 目录型 bundle 用目录里的 `index.*` 代表；
    - 链接写的是 `index.{md,html,htm}` 时，先当 bundle 目录看；
    - 无后缀的链接试 `.md` / `.html` / `.htm`。

    **只有 tail 为空才是「指目录」** —— 早先给图片链接开了个
    「指目录」的旁路，结果 `![]({image_url})` 这种代码里的占位符
    被当成了「指向本目录」，给一个跟链接无关的文档加了个 `./` 前缀。
    """
    abs_dir = os.path.join(DOCS, target_dir_rel)
    if not os.path.isdir(abs_dir):
        return None
    if tail == "":
        idx = _bundle_index(abs_dir)
        return os.path.relpath(idx, DOCS).replace(os.sep, "/") if idx else None
    if tail in ("index.md", "index.html", "index.htm"):
        idx = _bundle_index(abs_dir)
        return os.path.relpath(idx, DOCS).replace(os.sep, "/") if idx else None
    ext = os.path.splitext(tail)[1].lower()
    if ext in (".md", ".html", ".htm"):
        cand = os.path.join(abs_dir, tail)
        if os.path.isfile(cand):
            return os.path.relpath(cand, DOCS).replace(os.sep, "/")
        return None
    for ext in (".md", ".html", ".htm"):
        cand = os.path.join(abs_dir, tail + ext)
        if os.path.isfile(cand):
            return os.path.relpath(cand, DOCS).replace(os.sep, "/")
    return None


def resolve_link(post_dir_rel, raw):
    """一条相对链接指向哪个文件（docs 相对路径）。

    找不到就返回 None —— 这时链接文字保持原样。
    """
    if raw.startswith(EXTERNAL_PREFIXES) or raw.startswith("/"):
        return None
    raw_path = unquote(raw.split("#", 1)[0].split("?", 1)[0])
    if not raw_path:
        return None
    head, tail = _split_tail(raw_path)
    target_dir = os.path.normpath(os.path.join(post_dir_rel, head))
    if target_dir.startswith("..") or os.path.isabs(target_dir):
        return None
    hit = resolve_in_dir(target_dir, tail)
    if hit:
        return hit
    # 编译期自愈兜底：作者常写 `./<同级 bundle>/`，真实目标是上一级目录。
    cleaned = raw_path.lstrip("./")
    parent = os.path.dirname(post_dir_rel)
    if parent and not parent.startswith(".."):
        sib = os.path.normpath(os.path.join(parent, cleaned))
        if not sib.startswith(".."):
            hit = resolve_in_dir(os.path.dirname(sib), os.path.basename(sib))
            if hit:
                return hit
    return None


def _split_tail(raw):
    """`../foo/index.html` → `("../foo/", "index.html")`；`../foo/` → `("../foo/", "")`。"""
    if "/" not in raw:
        return "", raw
    head, tail = raw.rsplit("/", 1)
    return head + "/", tail


def rewrite_relative_links(moves, targets, report, categories=None):
    """重写 `docs/` 里所有文章的相对链接。

    两种情况：
    - **被搬的文章**：链接的相对基准目录变了 → 重算；
    - **留在原地的文章**：链接的目标被搬走了 → 重算。

    链接的「形状」（指目录还是指文件、末尾带不带 `index.html`）
    原样保留，只换路径。

    **必须在搬迁之前跑**：解析一条相对链接要靠磁盘上真的有那个目标，
    搬完之后旧目录已经空了，解析必然失败 —— 链接就会保持原样，
    变成指向空目录的死链。`targets` 是「旧路径 → 新路径」的完整表
    （文章 + 资源文件），链接的目标按它换算。
    """
    changed_files = 0
    changed_links = 0
    for rel in sorted(_walk_docs()):
        if not rel.endswith(".md"):
            continue
        path = os.path.join(DOCS, rel)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()

        post_dir = os.path.dirname(rel)
        # **目录页也算** —— `targets` 里除了文章，还有跟着搬走的旧目录页
        # （`index_map`）。只认 `moves` 的话，目录页的「新位置」算出来
        # 还是旧位置，于是它里面的相对链接会算成 `../source-tracks/...`
        # 这种从旧目录出发的路径 —— 搬完之后每一条都是死链。
        new_post_dir = os.path.dirname(targets.get(rel, rel))

        def repl_link(m):
            nonlocal changed_links
            text_, raw = m.group(1), m.group(2)
            new_raw = _rewrite_one(post_dir, new_post_dir, raw, targets,
                                   want_dir=False, categories=categories)
            if new_raw is None or new_raw == raw:
                return m.group(0)
            changed_links += 1
            return f"[{text_}]({new_raw})"

        def repl_image(m):
            nonlocal changed_links
            alt, raw = m.group(1), m.group(2)
            new_raw = _rewrite_one(post_dir, new_post_dir, raw, targets,
                                   want_dir=True, categories=categories)
            if new_raw is None or new_raw == raw:
                return m.group(0)
            changed_links += 1
            return f"![{alt}]({new_raw})"

        new_text = IMAGE_RE.sub(repl_image, text)
        new_text = LINK_RE.sub(repl_link, new_text)
        if new_text != text:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new_text)
            changed_files += 1
    report.append(f"链接改写：{changed_links} 条，动了 {changed_files} 个文件")
    return changed_links


def learning_alias_map():
    """老赛道 id → 新赛道 id。

    真相在规则表里：`data/learning-path.json` 的每条赛道可以带一个
    `aliases` 字段，列着它以前叫什么。老地址还得能进（别名页），
    文章正文里写死的地址也得跟着改 —— 同一份真相，两处用。
    """
    try:
        with open(os.path.join(REPO, "data/learning-path.json"),
                  encoding="utf-8") as fh:
            rules = json.load(fh)
    except (OSError, ValueError):
        return {}
    out = {}
    for track in rules.get("tracks", []):
        for alias in track.get("aliases", []):
            out[alias] = track["id"]
    return out


def rewrite_learning_links(report):
    """把文章正文里写死的旧赛道地址改成新赛道地址。

    赛道改过名字（db-internals → postgresql、linux-network → linux），
    正文里写死的 `/learning/<老 id>/` 会指向一个不存在的赛道页。

    老专题页（`/learning/db-internals/<某个中文专题>/`）早就跟着
    2026-11-19 那次分类页退休一起没了 —— 它们的落点是**赛道页**，
    不是某个专题页。
    """
    aliases = learning_alias_map()
    if not aliases:
        return 0
    changed_files = 0
    for rel in sorted(_walk_docs()):
        if not rel.endswith(".md"):
            continue
        path = os.path.join(DOCS, rel)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        new_text = text
        for alias, track_id in sorted(aliases.items(),
                                      key=lambda kv: -len(kv[0])):
            # 先处理带专题的那一截（顺序不能反：短的那一截是长的一截的前缀）
            new_text = re.sub(
                r"/learning/%s/[^/\s)\"']+/" % re.escape(alias),
                "/learning/%s/" % track_id, new_text)
            new_text = new_text.replace("/learning/%s/" % alias,
                                        "/learning/%s/" % track_id)
        if new_text != text:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new_text)
            changed_files += 1
    report.append("旧赛道地址：改了 %d 个文件" % changed_files)
    return changed_files


def category_targets(table):
    """解散的旧分类页 → 新分类地址。

    旧分类页（`_index.md`）被删掉之后，指向它的链接得有地方去。
    新分类页是**分类地址**（`/categories/xxx/`），不是一篇文章 ——
    直接把链接指到新目录下的 `_index.md` 会生成一个不存在的
    permalink（分类页不发成文章，只有 `/categories/` 下的地址是真的）。
    """
    out = {}
    redirects = table.get("category_redirects", {})
    for rel in table.get("drop_index", []):
        path = os.path.join(DOCS, rel)
        if not os.path.isfile(path):
            continue
        title = _read_title(path)
        new = redirects.get(title)
        if new:
            out[rel] = "/categories/" + quote(new) + "/"
    return out


def _read_title(path):
    """一个 markdown 文件 front matter 或首个 H1 里的标题。"""
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _rewrite_one(post_dir, new_post_dir, raw, moves, want_dir, categories=None):
    """重算一条相对链接。返回新的链接文字，或 None（不用改）。"""
    if raw.startswith(EXTERNAL_PREFIXES) or raw.startswith("/"):
        return None
    raw_path = unquote(raw.split("#", 1)[0].split("?", 1)[0])
    if not raw_path:
        return None
    suffix = raw[len(raw_path):] if raw.startswith(raw_path) else ""
    head, tail = _split_tail(raw_path)
    target_dir = os.path.normpath(os.path.join(post_dir, head))
    if target_dir.startswith("..") or os.path.isabs(target_dir):
        return None
    hit = resolve_in_dir(target_dir, tail)
    if not hit:
        # 编译期自愈兜底那一路，先按原样解析，解析不到就不动。
        cleaned = raw_path.lstrip("./")
        parent = os.path.dirname(post_dir)
        if parent and not parent.startswith(".."):
            sib = os.path.normpath(os.path.join(parent, cleaned))
            if not sib.startswith(".."):
                hit = resolve_in_dir(os.path.dirname(sib), os.path.basename(sib))
        if not hit:
            return None
    # 指向一个被解散的分类页 —— 改指新分类地址
    if categories and hit in categories:
        return categories[hit] + suffix
    new_hit = moves.get(hit, hit)
    if _same_place(post_dir, new_post_dir, hit, new_hit):
        # 目标相对作者没挪窝 —— 链接**一个字都不改**。
        #
        # 为什么要这一条：文章和它的目标一起搬走时，相对链接照旧是对的，
        # 可工具照样会把它重写成 `./目标.md`（同目录的写法）或者把
        # `%E5%B8%B8` 这种百分号编码解成中文。改出来的链接照样能跳，
        # 但那是**一篇没搬过的文章被无端改了一行** —— 迁移的 diff 里
        # 全是这种噪音，就没人敢看 diff 了。链接的形状（带不带 `./`、
        # 百分号编码不编码）属于原文，搬家不改。
        return None
    new_dir = os.path.dirname(new_hit)
    rel = os.path.relpath(new_dir, new_post_dir) if new_post_dir else new_dir
    rel = rel.replace(os.sep, "/")
    if rel == ".":
        rel = "./" if raw_path.startswith("./") else ""
    elif raw_path.startswith("./") and not rel.startswith("."):
        # 链接的**形状**原样保留：原来带 `./` 的，重算完还得带。
        # `os.path.relpath` 吐出来的是 `politics-methods/` 而不是
        # `./politics-methods/` —— 两种写法在 Markdown 里等价，但
        # 有测试是按字面量找链接的（`tests/test_gaokao_docs.py`），
        # 悄悄改形状就会把那些守卫弄红。
        rel = "./" + rel
    if rel and not rel.endswith("/"):
        rel += "/"
    return rel + tail + suffix


def _same_place(post_dir, new_post_dir, hit, new_hit):
    """链接的目标相对作者挪窝了吗？

    没挪窝 = 目标文件没换名字，且它相对于作者的位置没变 ——
    典型情形是「文章和它的目标一起搬到了同一个新目录」。
    """
    if hit == new_hit:
        return True
    if os.path.basename(hit) != os.path.basename(new_hit):
        return False
    old_dir = os.path.dirname(hit)
    new_dir = os.path.dirname(new_hit)
    old_rel = "" if old_dir == post_dir else os.path.relpath(old_dir, post_dir)
    new_rel = ("" if new_dir == new_post_dir
               else os.path.relpath(new_dir, new_post_dir))
    return old_rel.replace(os.sep, "/") == new_rel.replace(os.sep, "/")


# --------------------------------------------------------------------------
# 搬
# --------------------------------------------------------------------------


def git(*args):
    return subprocess.run(
        ["git"] + list(args), cwd=REPO, capture_output=True, text=True)


def do_move(old_rel, new_rel):
    """`git mv` 一个文件（保留文件历史）。目标已存在就跳过 —— 幂等。

    **例外：目标已存在且两份内容逐字节相同** —— 这是同一篇文章在树上有
    两个副本（`docs/cluster/raft协议动态调整quorum.md` 与
    `docs/cluster/raft/raft协议动态调整quorum.md` 就是这么一对）。
    留一份、删一份：内容一个字不丢，两个旧 URL 都重定向到合并后的那篇。
    内容不同则**不动** —— 那不是副本，硬删就是丢内容。
    """
    old_abs = os.path.join(DOCS, old_rel)
    new_abs = os.path.join(DOCS, new_rel)
    if not os.path.exists(old_abs):
        return "skip-missing"
    if os.path.exists(new_abs):
        if (os.path.isfile(old_abs) and os.path.isfile(new_abs)
                and filecmp.cmp(old_abs, new_abs, shallow=False)):
            res = git("rm", "-f", os.path.join("docs", old_rel))
            if res.returncode == 0:
                return "merged-duplicate"
        return "skip-exists"
    os.makedirs(os.path.dirname(new_abs), exist_ok=True)
    r = git("mv", os.path.join("docs", old_rel), os.path.join("docs", new_rel))
    if r.returncode != 0:
        # 没入库的文件 `git mv` 不动它（"not under version control"）。
        # 这种文件本来就还没有历史，退回普通改名 —— 别把内容丢了。
        shutil.move(old_abs, new_abs)
        return "moved-untracked"
    return "moved"


def do_move_out(old_rel, new_rel):
    """把文件从 `docs/` 移到仓库里的 `internal/`（不发布，但入库）。"""
    old_abs = os.path.join(DOCS, old_rel)
    new_abs = os.path.join(REPO, new_rel)
    if not os.path.exists(old_abs):
        return "skip-missing"
    if os.path.exists(new_abs):
        return "skip-exists"
    os.makedirs(os.path.dirname(new_abs), exist_ok=True)
    r = git("mv", os.path.join("docs", old_rel), new_rel)
    if r.returncode != 0:
        raise RuntimeError("git mv 失败：%s -> %s\n%s" % (old_rel, new_rel, r.stderr))
    return "moved"


RESOLVED_FILE = "data/migration-moves.json"


def load_resolved():
    """上次跑解析出来的搬迁清单。

    为什么要有它：`dir_map` 是「整目录搬」，目录搬空之后就没法再从
    树上推出「这个文件本来在哪」了 —— 重跑时 `effective_map()` 只能
    看到 `file_map` 里逐篇写死的那部分。清单落盘，重跑才是同一个动作。
    """
    path = os.path.join(REPO, RESOLVED_FILE)
    if not os.path.exists(path):
        return {}, {}
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return raw.get("articles", {}), raw.get("assets", {})


def save_resolved(articles, assets):
    path = os.path.join(REPO, RESOLVED_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"articles": articles, "assets": assets}, fh,
                  ensure_ascii=False, indent=2, sort_keys=True)


def prune_empty_dirs(root):
    """删掉空目录（从深到浅）。返回删掉的目录列表。"""
    removed = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        if os.path.abspath(dirpath) == os.path.abspath(root):
            continue
        if not os.listdir(dirpath):
            try:
                os.rmdir(dirpath)
                removed.append(os.path.relpath(dirpath, root))
            except OSError:
                pass
    return removed


def plan_moves(table):
    """把迁移表摊平成一份「要执行的动作清单」。"""
    moves = effective_map(table)
    actions = []
    for old_rel in sorted(moves):
        actions.append(("in", old_rel, moves[old_rel]))
    for old_rel, new_rel in sorted(table.get("out_map", {}).items()):
        actions.append(("out", old_rel, new_rel))
    for old_rel in sorted(table.get("drop_index", [])):
        actions.append(("drop", old_rel, None))
    for old_rel in sorted(table.get("drop_files", [])):
        actions.append(("drop_file", old_rel, None))
    return actions, moves


def index_actions(table):
    """旧目录页（`_index.md`）的动作。

    四种去向：

    - `index_map`：跟着目录搬走（系列目录 → 阶段目录、赛道目录 → 赛道目录）；
    - `index_archive`：搬不走的，存进 `internal/legacy-index/` ——
      **不删**：`_index.md` 是不发布的目录页，可里面有人手写的东西
      （PostgreSQL 那张「数据库总览」的总图、人生那条阅读路线）；
    - `index_keep`：原地不动 —— 已经落在新结构里的那几份
      （`source-tracks/_index.md` 与四个赛道目录页），`write_index_files()`
      会在原地合并；
    - 名单之外的：一律归档。留在 `docs/` 里就是一份没人维护的旧结构说明，
      分类链还可能多出一级。

    返回 `[(动作, 旧路径, 新路径)]`，动作是 `move` / `archive` / `keep`。
    """
    index_map = table.get("index_map", {})
    index_archive = table.get("index_archive", {})
    index_keep = set(table.get("index_keep", []))
    out = []
    for rel in table.get("drop_index", []):
        if rel in index_map:
            out.append(("move", rel, index_map[rel]))
        elif rel in index_archive:
            out.append(("archive", rel, index_archive[rel]))
        elif rel in index_keep:
            out.append(("keep", rel, None))
        else:
            out.append(("archive", rel, "internal/legacy-index/" + rel))
    return out


def asset_moves(table, moves):
    """随文章一起搬的资源文件（图片等）。

    **优先读迁移表里的 `asset_map`**（逐文件的落点）。理由：顶层目录
    会被拆到多个阶段，「跟着目录搬」这条规则表达不了；而文章目录里的
    **子目录**（`code/xxx/assets/`）也不是「文章旁边的同级文件」，
    两条老规则都认不出来。`asset_map` 是一张一对一的全表，逐文件说了算。

    表里没有的，才退回下面两条老规则：

    1. 凡是落在 `dir_map` 目录下的非文章文件，跟着目录一起搬 ——
       图片的站内 URL 是 `images/<docs 相对路径>`，不跟着搬就会指向旧路径；
    2. 逐篇搬的文章旁边的资源文件（同一目录下的图片）。

    ``_index.md`` **不算资源**：它是分类链的载体（``cascade.categories``），
    搬走它等于把一个分类悄悄改名。被搬文章旁边的 ``_index.md`` 留在原地。
    """
    out = dict(table.get("asset_map", {}))
    for old_dir, new_dir in table.get("dir_map", {}).items():
        prefix = old_dir.rstrip("/") + "/"
        for rel in _walk_docs():
            if not rel.startswith(prefix):
                continue
            if _is_article(rel) or _is_index_file(rel) or rel in out:
                continue
            out[rel] = new_dir.rstrip("/") + "/" + rel[len(prefix):]
    # 逐篇搬的文章旁边的资源文件（同一目录下的图片）
    for old_rel, new_rel in moves.items():
        old_dir = os.path.dirname(old_rel)
        new_dir = os.path.dirname(new_rel)
        for rel in _walk_docs():
            if os.path.dirname(rel) != old_dir:
                continue
            if _is_article(rel) or _is_index_file(rel) or rel in out:
                continue
            out[rel] = new_dir + "/" + os.path.basename(rel)
    return out


# --------------------------------------------------------------------------
# 新目录页
# --------------------------------------------------------------------------


def _projects(table):
    """迁移表里的「主线项目」列表。

    每条项目有自己的 `target_root`（在 `docs/` 里的落点）、显示名
    和系列表。**为什么不是一个**：`source-tracks/` 下面会同时住着
    PostgreSQL、Linux、DPDK 几条主线 —— 每个项目的中文显示名和系列表
    都不一样，塞进一张扁平的 `series` 里就分不清谁是谁了。

    旧版迁移表只有一个 `target_root` + 一张扁平的 `series` —— 兼容它：
    合成一个项目出来。
    """
    projects = table.get("projects")
    if projects:
        return projects
    return [{
        "target_root": table.get("target_root", "source-tracks/postgresql"),
        "series": table.get("series", {}),
        "series_meta": table.get("series_meta", {}),
    }]


# 目录名 → 中文显示名。分类链与 URL 里的中文都靠它。
#
# **顶层目录名只写死这一个**：`source-tracks/` 装的是全部内容，
# 它的中文名是「内容库」—— 不再是「源码主线」（那名字只覆盖了
# 搬之前的 270 篇，搬完是 590 篇全覆盖）。
# 赛道名与阶段名不写死 —— 从 `data/learning-path.json` 读（§7.1）。
TOP_DISPLAY_NAMES = {"source-tracks": "内容库"}
TOP_DESCRIPTION = "内容库：全站内容按「赛道 → 阶段」两层组织，每条赛道从入门排到进阶。"


def _rule_titles():
    """`data/learning-path.json` → `{赛道id: 赛道名}`。

    **赛道名与阶段名的唯一来源是规则表**（§7.1）。再手写一份中文名，
    两份必然漂移 —— 那正是 `docs/source-tracks/platform-meta/L4-info-architecture/` 里
    说的「一个站有两个真相」。
    """
    path = os.path.join(REPO, "data", "learning-path.json")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        rules = json.load(fh)
    return {t["id"]: t["title"] for t in rules.get("tracks", [])}


def write_index_files(table, moves, report):
    """给新树写 `_index.md`。

    每个目录页带 `cascade.categories` —— `sync-hexo.py` 的
    `read_cascade_categories()` 靠它把分类链拼出来（内容库 → PostgreSQL
    源码内核 → 起步与全景）。

    2026-11-19：分类页整套退休了，这条链不再生成任何页面 —— 它现在只
    当**检索维度**用（学习路径的归类规则、搜索索引都读它）。链条本身
    还得拼全：少一级，文章就归不进对应的赛道。
    """
    titles = _rule_titles()
    made = []
    tops_done = set()
    for proj in _projects(table):
        series_cn = proj.get("series", {})
        series_meta = proj.get("series_meta", {})
        target_root = proj["target_root"]
        parts = target_root.split("/")

        # 顶层：docs/<target_root 的第一段>/_index.md
        #
        # **落点只有一段时顶层页就是项目页** ——
        # 写两遍会把「## 阶段」那一节吃掉：第二遍写进去的正文里没有
        # 「本系列文章」这一节，项目页没有，于是项目页的阶段清单
        # 永远补不上。
        top = parts[0]
        top_cn = TOP_DISPLAY_NAMES.get(top, top)
        single_segment = len(parts) == 1
        if top not in tops_done and not single_segment:
            tops_done.add(top)
            made.append(_write_index(
                f"{top}/_index.md", top_cn, top_cn, TOP_DESCRIPTION,
                [], table))

        # 中间层（target_root 有三段以上时才有；两段时这一层是空的）
        for depth in range(2, len(parts)):
            rel_dir = "/".join(parts[:depth])
            name = parts[depth - 1]
            cn = titles.get(name, name)
            made.append(_write_index(
                f"{rel_dir}/_index.md", cn, cn, f"{cn} 主线。", [], table))

        # 项目层：项目目录页 + 它下面的阶段目录页。
        #
        # 项目目录页**不能少** —— 少了它，分类链就少一级：文章的
        # cascade 只有「内容库」和阶段名，而不是完整的链条
        # （内容库 → PostgreSQL 源码内核 → 起步与全景）。
        # 分类页退休后这条链只用于归类，缺一级文章就归不进对应赛道。
        proj_dir = target_root
        proj_name = parts[-1]
        proj_cn = (proj.get("display_name")
                   or titles.get(proj_name, proj_name))
        series_lines = []
        for slug, scn in series_cn.items():
            desc = series_meta.get(slug, f"{proj_cn} 的{scn}方向。")
            made.append(_write_index(
                f"{proj_dir}/{slug}/_index.md", scn, proj_cn,
                desc, _series_articles(moves, f"{proj_dir}/{slug}/"),
                table))
            series_lines.append(f"- [{scn}](./{slug}/_index.md)")
        # `source-tracks/` 下装的是**赛道**；别的落点叫「专题」。
        kind = "赛道" if target_root.startswith("source-tracks/") else "专题"
        made.append(_write_index(
            f"{proj_dir}/_index.md", proj_cn, proj_cn,
            f"{proj_cn} {kind}：{len(series_cn)} 个阶段，由浅入深。",
            [], table, extra=["## 阶段", ""] + series_lines + [""]))
    report.append(f"目录页：新建 {len(made)} 个")
    return made


def _series_articles(moves, prefix):
    """某个系列下的文章（按旧路径排序，稳定的顺序）。

    同一篇合并后的副本只列一次 —— 两份旧文件逐字节相同，
    合并成一篇之后目录页上不该出现两条一模一样的链接。
    """
    out = []
    seen = set()
    for old_rel, new_rel in moves.items():
        if new_rel.startswith(prefix) and new_rel not in seen:
            seen.add(new_rel)
            out.append((old_rel, new_rel))
    out.sort()
    return out


def _article_title(path):
    """一篇文章的标题（front matter 优先，其次首个 H1）。"""
    if not os.path.isfile(path):
        return ""
    return _read_title(path)


def _md_link_target(path):
    """把链接目标里会破坏 Markdown 链接语法的字符转义掉。

    **为什么要转义**：Markdown 的链接目标写成 ``[标题](目标)`` 时，目标里
    不能直接出现未转义的右括号 —— 否则链接在那里就断了。站上有一篇的
    文件名带括号（``Postgres中postmaster代码解析(--boot和--single).md``），
    生成的目录页链接就会断成两截。

    转成 %28 / %29 / %20：既能过 CommonMark，GitHub 上也认；
    站内查链工具会 ``unquote`` 再解析，落到磁盘上的真文件。
    """
    return path.replace("(", "%28").replace(")", "%29").replace(" ", "%20")


def _write_index(rel, title, parent_cn, description, articles, table, extra=None):
    """写一个 `_index.md`。已存在就只更新文章清单那一段。"""
    path = os.path.join(DOCS, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        "---",
        f'title: "{title}"',
        f'description: "{description}"',
        "cascade:",
        "  categories:",
        f"    - {title}",
        "tags:",
        f"  - {title}",
        "---",
        "",
        f"# {title}",
        "",
        description,
        "",
    ]
    if articles:
        lines.append("## 本系列文章")
        lines.append("")
        here = os.path.dirname(rel)
        for old_rel, new_rel in articles:
            name = os.path.basename(new_rel)
            if name == "index.md":
                name = os.path.basename(os.path.dirname(new_rel))
            else:
                name = os.path.splitext(name)[0]
            link = os.path.relpath(new_rel, here).replace(os.sep, "/")
            if not link.startswith("."):
                link = "./" + link
            link = _md_link_target(link)
            title = _article_title(os.path.join(DOCS, new_rel)) or name
            # 标题里的方括号会提前结束链接文字
            title = title.replace("[", "\\[").replace("]", "\\]")
            lines.append(f"- [{title}]({link})")
        lines.append("")
    if extra:
        lines.extend(extra)
    body = "\n".join(lines)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            old = fh.read()
        if old == body:
            return rel
        # 目录页可能被人手写过 —— 项目目录页后来并进了一整张几百行的
        # 「数据库总览」。整篇覆盖会把那些内容抹掉，所以**换掉 front
        # matter 和文章清单，中间的手写正文留着**。
        merged = _merge_index(old, body)
        if merged != old:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(merged)
        return rel
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return rel


ARTICLE_SECTION = "本系列文章"

FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
SECTION_RE = re.compile(r"(?m)^##[ \t]+(.+?)[ \t]*$")


def _split_fm(text):
    """front matter 与正文分开。

    两种写法都要认：

    - 标准的 `---` 分隔（`_write_index()` 生成的那种）；
    - **没有分隔线的** —— 手写的目录页就是长这样（`docs/life/_index.md`、
      `docs/source-tracks/postgresql/_index.md`）：开头一段顶格的
      `key: value` 就是 front matter，遇到第一个空行结束。
      `sync-hexo.py` 读 `cascade.categories` 用的是正则，不挑写法；
      迁移脚本得跟它对齐。
    """
    m = FM_RE.match(text)
    if m:
        return m.group(1), text[m.end():]
    fm_lines = []
    for line in text.split("\n"):
        if not line.strip():
            break
        if re.match(r"^[A-Za-z_][\w-]*:", line) or line[:1] in (" ", "\t"):
            fm_lines.append(line)
        else:
            break
    if not fm_lines:
        return "", text
    block = "\n".join(fm_lines)
    return block, text[len(block):].lstrip("\n")


def _fm_value(fm, key):
    m = re.search(r'^%s:\s*["\']?(.+?)["\']?\s*$' % re.escape(key),
                  fm, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _split_sections(text):
    """正文按 `## ` 标题切成若干节。

    返回 `(前言, [(标题, 该节正文)])` —— 前言是第一个 `## ` 之前的内容。
    """
    matches = list(SECTION_RE.finditer(text))
    if not matches:
        return text.strip(), []
    head = text[:matches[0].start()].strip()
    out = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group(1).strip(), text[m.start():end].strip()))
    return head, out


def _merge_index(old, body):
    """新的目录页 + 旧的手写正文 → 一份。

    **三件事**：

    1. **front matter 用新的** —— `title` 与 `cascade.categories` 是
       分类链的输入（`sync-hexo.py` 的 `resolve_post_categories()` 读它），
       旧的那份带着旧阶段名，留着就是两份真相；
    2. **旧正文里手写的段落留着** —— PostgreSQL 那张「数据库总览」的
       总图、人生那条「路径 A / B / C」的阅读路线，整篇覆盖就没了；
    3. **「本系列文章」那一节用新的** —— 文章清单变了。
    """
    old_fm, old_body = _split_fm(old)
    new_fm, new_body = _split_fm(body)
    new_head, new_sections = _split_sections(new_body)
    old_head, old_sections = _split_sections(old_body)

    # 旧的小节在前（保持作者写的顺序），新的小节替换同名或补在后面。
    merged = dict(old_sections)
    for heading, content in new_sections:
        if heading == "阶段" and "系列" in merged:
            # 旧的那一节（「## 系列」）被新的（「## 阶段」）取代 ——
            # 两份都留着，读者会看到两张阶段清单。
            del merged["系列"]
        merged[heading] = content
    parts = [new_head.strip()]
    prose = _old_prose(old_head, old_fm)
    if prose:
        parts.append(prose)
    for content in merged.values():
        parts.append(content.strip())

    return "---\n%s\n---\n\n%s\n" % (new_fm.strip(),
                                     "\n\n".join(p for p in parts if p))


def _old_prose(old_head, old_fm):
    """旧正文里手写的那部分（去掉 H1 与旧的 description）。"""
    text = old_head.strip()
    if text.startswith("# "):
        text = text.split("\n", 1)[1] if "\n" in text else ""
    desc = _fm_value(old_fm, "description")
    if desc and text.strip().startswith(desc.strip()):
        text = text.strip()[len(desc.strip()):]
    return text.strip()


# --------------------------------------------------------------------------
# 常量补丁：REDIRECTS / DATE_OVERRIDES
# --------------------------------------------------------------------------


def permalink_path(rel):
    """一篇文章的 permalink 路径（不含日期段、不含扩展名）。

    bundle（`.../index.md`）的 permalink 是它所在的目录。

    **HTML 文章带 `-html` 后缀**：编译时 HTML 文章的文件名会被改成
    `<basename>-html.html`（见 `sync-hexo.py` 的 `process_html_post` ——
    hexo 用文件名推 slug，不加后缀就跟同名 .md 抢 permalink），
    所以它的 permalink 里也有这个后缀。实测站点上的地址是
    `/2026/07/03/source-tracks/postgresql/L7-logical-replication/sqlserver/sqlserver逻辑复制ddl-html/`，
    少了后缀的重定向页会指到一个从来不存在的地址。
    """
    base = os.path.basename(rel)
    if base in ("index.md", "index.html", "index.htm"):
        return os.path.dirname(rel)
    stem, ext = os.path.splitext(rel)
    if ext.lower() in (".html", ".htm") and not os.path.basename(stem).endswith("-html"):
        stem += "-html"
    return stem


def build_redirects(moves, existing=None):
    """旧 permalink 路径 → 新 permalink 路径。

    ``existing`` 是上一轮的 ``data/redirects.json``：**带日期的键**
    （``2022/10/25/cluster/raft/…``）是手工补的 —— 合并两篇逐字节相同的
    重复文章时，旧 URL 的日期段跟新文件对不上，键里带上日期才落得准。
    ``moves`` 推不出这种条目，所以从旧表里留着；同一条路径的普通键
    （日期由新文件决定，落错地方的那个）去掉，免得白生成一个多余的页面。

    **老重定向要链式归并**（2026-11-26）：上一轮的 320 条重定向，
    目标**全部**是这一轮要搬的路径。照搬就会让老 URL 跳到一个
    这一轮之后就不存在的中间地址上。所以：

        新表[旧键] = 新表.get(旧表[旧键], 旧表[旧键])

    即：旧键的目标如果也在本轮被搬了，就把它的目标改成**最终新路径**。
    """
    out = {}
    for old_rel, new_rel in sorted(moves.items()):
        out[permalink_path(old_rel)] = permalink_path(new_rel)
    dated = {}
    for key, value in (existing or {}).items():
        m = DATED_REDIRECT_RE.match(key)
        if not m:
            continue
        dated[key] = value
        out.pop(m.group("path"), None)
    out.update(dated)
    # 链式归并：旧键的目标如果也在本轮被搬了，指最终新路径
    merged = {}
    for key, value in out.items():
        merged[key] = out.get(value, value)
    return merged


def build_date_overrides(moves, dates_before, out_map=None):
    """按**新路径**固化的日期表。"""
    out_map = out_map or {}
    out = {}
    for old_rel, new_rel in sorted(moves.items()):
        # 重跑时旧路径已经不在树上，日期表里存的是**新路径** —— 两个键都认。
        date = dates_before.get(old_rel) or dates_before.get(new_rel)
        out[new_rel] = date or "2024-01-01 00:00:00"
    for rel, date in dates_before.items():
        # 搬走的文章用新路径做键，旧路径那个键就是死的 —— 留着它，
        # 以后再搬一次会被当成「有记录」而跳过改写。
        # 移出 docs/ 的文件不再是站上的文章，不进表。
        if rel not in out and rel not in moves and rel not in out_map:
            out[rel] = date
    return out


# 2026-11-19：分类/标签这套页面整套退休了 —— 「旧分类 → 新分类」的映射表
# （data/category-redirects.json）不再需要：所有旧分类地址统一由
# sync-hexo.py 写成跳到「全部文章」的重定向页，映射到哪一层都一样。
# 所以这里不再生成那张表（原来那张表留着只会让人以为还在用）。


# --------------------------------------------------------------------------
# 外部引用改写
# --------------------------------------------------------------------------


def path_forms(rel):
    """一个 docs 相对路径的各种写法。

    - `docs`：母稿路径，含扩展名（`db/postgresql/foo/index.md`）
    - `flat`：编译产物 `source/_posts/` 里的路径（bundle 拍平成 `db/postgresql/foo.md`）
    - `postid`：`source/_posts/` 路径去掉 `.md`
    - `cid`：内容单元 id（`db/postgresql/foo`）
    """
    base = os.path.basename(rel)
    if base in ("index.md", "index.html", "index.htm"):
        parent = os.path.dirname(rel)
        flat = (parent + ".md") if parent else "index.md"
        cid = parent
    else:
        flat = rel
        cid = os.path.splitext(rel)[0]
    return {
        "docs": rel,
        "flat": flat,
        "postid": os.path.splitext(flat)[0],
        "cid": cid,
    }


def rewrite_refs(targets, moves, report):
    """改写站点外部文件里硬编码的 docs 路径。

    `targets` 是 `(文件, 路径形态)` 的清单；形态决定拿哪种写法去替换。

    `permalink` 形态特殊一些：站内绝对地址带一段日期
    （`/2023/09/14/source-tracks/postgresql/L1-getting-started/postgresql源码编译/`）。日期在迁移前后不变
    （这正是 `DATE_OVERRIDES` 存在的意义），所以只换路径那一段。
    站上有两种写法 —— 中文未编码的、百分号编码的 —— 两种都要替。

    **替换按「长的先替」**（2026-11-26）：`docs` / `flat` / `postid` / `cid`
    四种写法互相包含 —— `ai/x` 是 `ai/x.md` 的前缀，`ai/x/index.md` 又是
    `ai/x` 的延伸。先替短的会把长的吃掉（`ai/x` 替完，`ai/x/index.md`
    已经不成其为原来那串了），替出来的地址是错的。
    """
    total = 0
    for rel_file, form in targets:
        path = os.path.join(REPO, rel_file)
        if not os.path.exists(path):
            report.append(f"外部引用：{rel_file} 不存在，跳过")
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        original = text
        hits = 0
        if form == "permalink":
            pairs = []
            for old_rel, new_rel in moves.items():
                pairs.extend(_permalink_pairs(old_rel, new_rel))
            text, hits = _replace_loose(text, pairs)
        else:
            table = {}
            for old_rel, new_rel in moves.items():
                old_form = path_forms(old_rel)[form]
                new_form = path_forms(new_rel)[form]
                if old_form == new_form:
                    continue
                table[old_form] = new_form
            text, hits = _replace_paths(text, table)
        if text != original:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            report.append(f"外部引用：{rel_file} 改了 {hits} 处")
            total += hits
    return total


#: 路径左右两侧不能是这些字符 —— 否则就不是「一条路径」，而是
#: 某个更长的标识符的一部分（`ai/x` 出现在 `ai/xyz` 里就是这种情况）。
_PATH_EDGE = r"[0-9A-Za-z_.\-]"


def _replace_paths(text, table):
    """把文本里的路径按 `table` 换掉。

    **只在路径的两侧是「边界」时才换**：`ai/x` 不许在 `ai/xyz` 里被替掉，
    也不许在 `mail/x` 里被替掉。宁可漏改（人来看一眼），不可改错。

    长的先替：同一个表里 `ai/x/index.md` 与 `ai/x` 同时存在时，
    先替长的。
    """
    if not table:
        return text, 0
    items = sorted(table.items(), key=lambda kv: (-len(kv[0]), kv[0]))
    pattern = re.compile(
        "(?<!" + _PATH_EDGE + ")(?:"
        + "|".join(re.escape(old) for old, _ in items)
        + ")(?!" + _PATH_EDGE + ")")

    def repl(m):
        return table[m.group(0)]

    return pattern.subn(repl, text)


def _replace_loose(text, pairs):
    """把文本里的路径按 `pairs` 换掉（**不查边界**）。

    给站内绝对地址用：那种写法自带前后两个斜杠
    （`/2023/09/14/old/path/`），前后是日期段和域名 ——
    「边界」检查会把日期里的数字当成路径的一部分，判成不是路径。
    """
    hits = 0
    table = {}
    for old, new in pairs:
        if old and old != new:
            table[old] = new
    for old, new in sorted(table.items(), key=lambda kv: (-len(kv[0]), kv[0])):
        if old not in text:
            continue
        hits += text.count(old)
        text = text.replace(old, new)
    return text, hits


def _permalink_pairs(old_rel, new_rel):
    """站内绝对地址里的路径段（三种写法）。

    站点上的地址有三种形态：中文原样、整段百分号编码（``quote()`` 的写法），
    以及**只把空格编码成 ``%20``**、中文照旧的那种。第三种最常见也最容易漏
    —— 文件名里带空格的文章（比如「一文读懂openguass dcf网络模块」）在
    模板里就长这样，少了这一对，链接就会在搬家后指向一个不存在的地址。
    """
    old_perm = permalink_path(old_rel)
    new_perm = permalink_path(new_rel)
    if old_perm == new_perm:
        return []
    pairs = []
    for old_text, new_text in (
        ("/" + old_perm + "/", "/" + new_perm + "/"),
        ("/" + quote(old_perm) + "/", "/" + quote(new_perm) + "/"),
        ("/" + old_perm.replace(" ", "%20") + "/",
         "/" + new_perm.replace(" ", "%20") + "/"),
    ):
        if old_text != new_text:
            pairs.append((old_text, new_text))
    return pairs


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description="按迁移表搬 docs/ 目录")
    ap.add_argument("--apply", action="store_true",
                    help="真的搬（默认只报告）")
    ap.add_argument("--map", default=MIGRATION_FILE, help="迁移表路径")
    ap.add_argument("--skip-refs", action="store_true",
                    help="不改外部引用（只搬 docs/ 内部）")
    args = ap.parse_args()

    table = load_migration(args.map)
    actions, moves = plan_moves(table)
    assets = asset_moves(table, moves)
    # 跟上次跑解析出来的清单合起来 —— 目录搬空之后，`dir_map` 推不出
    # 「本来在哪」了，只有落盘的清单知道。
    prior_articles, prior_assets = load_resolved()
    merged = dict(prior_articles)
    merged.update(moves)
    moves = merged
    merged_assets = dict(prior_assets)
    merged_assets.update(assets)
    assets = merged_assets

    print(f"迁移表：{args.map}")
    print(f"  文章搬迁 {len(moves)} 篇，资源 {len(assets)} 个，"
          f"移出 {len(table.get('out_map', {}))} 篇，"
          f"删除目录页 {len(table.get('drop_index', []))} 个，"
          f"删除文件 {len(table.get('drop_files', []))} 个")
    by_series = {}
    for new_rel in moves.values():
        key = "/".join(new_rel.split("/")[:3])
        by_series[key] = by_series.get(key, 0) + 1
    for key in sorted(by_series):
        print(f"    {by_series[key]:4d}  {key}")

    if not args.apply:
        print("\n这是 dry-run。加 --apply 真搬。")
        print("前 10 个动作：")
        for kind, old, new in actions[:10]:
            print(f"  [{kind}] {old} -> {new}")
        return 0

    if git("status", "--porcelain").stdout.strip():
        print("工作区不干净，先提交或 stash 再跑迁移。", file=sys.stderr)
        return 2

    report = []

    # 1. 搬之前先把日期固化下来（这一步的顺序不能变）
    module = load_sync_hexo()
    dates_before = capture_dates(module)
    print(f"搬之前固化了 {len(dates_before)} 篇的日期")

    # 2. 先改链接 —— 解析要对着旧树，搬完就解析不到了
    targets = dict(moves)
    targets.update(assets)
    # 旧目录页（`_index.md`）也搬了，指向它们的相对链接要跟着改
    targets.update(table.get("index_map", {}))
    categories = category_targets(table)
    rewrite_relative_links(moves, targets, report, categories)

    # 2.5 旧赛道地址（`/learning/db-internals/` 之类）改成新的
    rewrite_learning_links(report)

    # 3. 搬
    stats = {}
    missing = []
    index_acts = {rel: (act, new) for act, rel, new in index_actions(table)}
    for kind, old_rel, new_rel in actions:
        if kind == "in":
            r = do_move(old_rel, new_rel)
        elif kind == "out":
            r = do_move_out(old_rel, new_rel)
        elif kind == "drop_file":
            abs_old = os.path.join(DOCS, old_rel)
            if os.path.exists(abs_old):
                res = git("rm", "-f", os.path.join("docs", old_rel))
                if res.returncode != 0:
                    os.remove(abs_old)
                r = "removed"
            else:
                r = "skip-missing"
        else:
            # 旧目录页：跟着搬 / 归档 / 原地不动
            act, target = index_acts.get(old_rel, ("drop", None))
            if act == "move":
                r = do_move(old_rel, target)
            elif act == "archive":
                r = do_move_out(old_rel, target)
            elif act == "keep":
                r = "kept"
            else:
                abs_old = os.path.join(DOCS, old_rel)
                if os.path.exists(abs_old):
                    res = git("rm", "-f", os.path.join("docs", old_rel))
                    r = "removed" if res.returncode == 0 else "failed"
                else:
                    r = "skip-missing"
        stats[r] = stats.get(r, 0) + 1
        if r == "skip-missing":
            missing.append(old_rel)
    for old_rel, new_rel in sorted(assets.items()):
        if os.path.basename(old_rel) == ".DS_Store":
            git("rm", "-f", os.path.join("docs", old_rel))
            stats["removed-junk"] = stats.get("removed-junk", 0) + 1
            continue
        r = do_move(old_rel, new_rel)
        stats[r] = stats.get(r, 0) + 1
        if r == "skip-missing":
            missing.append(old_rel)
    report.append("搬运：" + "，".join(f"{k} {v}" for k, v in sorted(stats.items())))
    if missing:
        report.append("源文件不在（没搬成）：" + "、".join(sorted(missing)))
    save_resolved(moves, assets)

    # 3.5 扫掉搬空了的目录
    #
    # git 不跟踪空目录，但它们留在工作区里会让「`docs/` 下还剩几个顶层目录」
    # 这个问题答错 —— 搬完之后 `docs/` 应当只剩 `source-tracks/`。
    emptied = prune_empty_dirs(DOCS)
    if emptied:
        report.append(f"空目录：清掉 {len(emptied)} 个")

    # 4. 新目录页
    write_index_files(table, moves, report)

    # 5. 常量补丁
    redirects = build_redirects(moves, load_redirects())
    date_overrides = build_date_overrides(moves, dates_before,
                                          table.get("out_map", {}))
    for name, payload in (
        (DATE_FILE, date_overrides),
        ("data/redirects.json", redirects),
    ):
        with open(os.path.join(REPO, name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
    report.append(f"常量补丁：REDIRECTS +{len(redirects)} 条，"
                  f"DATE_OVERRIDES 写进 {DATE_FILE}（{len(date_overrides)} 条）")

    # 6. 外部引用
    if not args.skip_refs:
        targets = [(t["file"], t["form"]) for t in table.get("ref_rewrites", [])]
        n = rewrite_refs(targets, moves, report)
        report.append(f"外部引用：共改 {n} 处")

    # 7. 自检：日期逐篇比对
    #    重新加载一遍 —— sync-hexo.py 在**导入时**就把 `data/` 下的表读进
    #    内存了，而表是第 5 步才写的。不重载，断言拿到的是旧表，
    #    `git_date()` 查不到新键就退回「仓库里找不到这个路径」。
    module = load_sync_hexo()
    drift = []
    for old_rel, new_rel in sorted(moves.items()):
        want = dates_before.get(old_rel) or dates_before.get(new_rel)
        got = module.git_date(os.path.join(DOCS, new_rel))
        if got != want:
            drift.append((old_rel, new_rel, want, got))
    if drift:
        print("\n⚠ 日期漂移：", file=sys.stderr)
        for old_rel, new_rel, want, got in drift[:20]:
            print(f"  {old_rel} → {new_rel}\n    原 {want}  现 {got}",
                  file=sys.stderr)
        return 1

    print()
    for line in report:
        print("  " + line)
    print("\n完成。还没提交 —— 先跑自检：")
    print("  python3 tools/capture-dates.py --check data/date-overrides.json")
    print("  python3 tools/check-internal-links.py")
    print("  python3 tools/check-mermaid.py")
    print("  python3 -m pytest tests/ -q")
    return 0


if __name__ == "__main__":
    sys.exit(main())
