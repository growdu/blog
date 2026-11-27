#!/usr/bin/env python3
"""把每篇文章的发布日期固化下来 —— 迁移目录前后的安全网。

**为什么需要它**：文章的日期不是作者填的，是 `sync-hexo.py:606 git_date()` 从
git 历史里取的「该路径在所有分支上的最早提交时间」。`git mv` 之后，新路径的
最早提交就变成了「搬运」那一次 —— 全站几百篇文章的日期同时变成搬运日，
一起跳到「最近发布」的顶部，把首页冲垮。更隐蔽的是重定向页：它用新文件的
日期去拼旧 URL 的日期段，日期一漂，旧链接照样 404。

**实测过的事实**（2026-11-17）：620 篇里 **314 篇（50%）**的 `git_date()`
与裸 `git log` 的结果**不一致**。例：`docs/source-tracks/engineering/L1-basics/data-struct.md` 的
`git_date()` 是 `2018-10-05`，裸 git log 是 `2025-04-16`。所以「跑一遍
git log 把结果存下来」这个朴素做法是错的 —— 必须**调用 `git_date()` 本身**
（它会走「仓库根 → docs/ → bundle 父目录」这条候选链）。

**怎么用**：

```bash
# 1. 搬之前：把当前所有文章的日期固化下来
python3 tools/capture-dates.py --out data/date-overrides.json

# 2. 搬之后：逐篇断言日期没变（不一致就退出码 1）
python3 tools/capture-dates.py --check data/date-overrides.json --map data/tree-migration.json

# 3. 单独看某几篇
python3 tools/capture-dates.py --show docs/source-tracks/engineering/L1-basics/data-struct.md
```

`--check` 是**逐篇比**，不靠抽查 —— 几百篇文章共用同一个批量导入日期，
肉眼抽查根本看不出来。
"""

import argparse
import importlib.util
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(REPO, "docs")

# 日期键 = docs 相对路径（含 index.md），与 sync-hexo.py 的 DATE_OVERRIDES
# 查表用的键一致。
KEY_SUFFIXES = ("index.md",)


def load_sync_hexo():
    """把 tools/sync-hexo.py 当模块加载 —— 日期语义必须跟它一模一样。"""
    os.chdir(REPO)
    spec = importlib.util.spec_from_file_location(
        "sync_hexo", os.path.join(REPO, "tools", "sync-hexo.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def article_keys():
    """所有会被当成文章的 docs 文件。

    含 HTML 文章（站上有 3 篇是 HTML 写的），不含 `_index.*` —— 分类索引
    文件不是文章，没有自己的发布日期。
    """
    out = []
    for root, dirs, files in os.walk(DOCS):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext not in (".md", ".html", ".htm"):
                continue
            if name.startswith("_index."):
                continue
            out.append(os.path.relpath(os.path.join(root, name), DOCS))
    return sorted(p.replace(os.sep, "/") for p in out)


def capture(module):
    table = {}
    for rel in article_keys():
        path = os.path.join(DOCS, rel)
        table[rel] = module.git_date(path)
    return table


def load_map(map_path):
    """读迁移映射，取出「旧路径 → 新路径」的对照。

    支持三种形态：
    - `data/migration-moves.json`（`{"articles": {旧: 新}, ...}`）——
      **搬家时真正用的那张表**，搬完之后唯一可靠的对照
    - `data/tree-migration.json`（`file_map` / `dir_map` / `out_map`）——
      搬之前用的策展表
    - 单纯的两列对照 `{"old/path.md": "new/path.md"}`

    搬完之后不要再用策展表展开 `dir_map`：旧路径已经不在磁盘上了，
    展开出来是空的，日期断言会拿旧路径去比新文件，报出一堆「文件不在」，
    而真问题被淹在里面。所以优先读 `migration-moves.json`。
    """
    with open(map_path, encoding="utf-8") as fh:
        raw = json.load(fh)
    if "articles" in raw and isinstance(raw["articles"], dict):
        return dict(raw["articles"])
    if "file_map" in raw or "dir_map" in raw:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "migrate_tree", os.path.join(REPO, "tools", "migrate-tree.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.effective_map(raw)
    return dict(raw)


def main():
    ap = argparse.ArgumentParser(description="固化 / 校验每篇文章的发布日期")
    ap.add_argument("--out", help="把当前日期写到哪个 JSON")
    ap.add_argument("--check", help="跟这个 JSON 比对，逐篇断言")
    ap.add_argument("--map", help="迁移映射（旧→新），--check 时用来换键")
    ap.add_argument("--show", nargs="+", help="只看这几篇的日期")
    args = ap.parse_args()

    module = load_sync_hexo()

    if args.show:
        for rel in args.show:
            path = rel if os.path.isabs(rel) else os.path.join(DOCS, rel)
            print(f"{rel}\t{module.git_date(path)}")
        return 0

    if args.out:
        table = capture(module)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(table, fh, ensure_ascii=False, indent=2, sort_keys=True)
        years = {}
        for v in table.values():
            years[v[:4]] = years.get(v[:4], 0) + 1
        print(f"固化 {len(table)} 篇文章的日期 → {args.out}")
        print("  年份分布：" + " ".join(f"{y} 年 {n} 篇" for y, n in sorted(years.items())))
        dupes = {}
        for v in table.values():
            dupes[v] = dupes.get(v, 0) + 1
        top = sorted(dupes.items(), key=lambda kv: -kv[1])[:3]
        print("  同日最多的几个：" + " ".join(f"{d} × {n}" for d, n in top))
        return 0

    if args.check:
        with open(args.check, encoding="utf-8") as fh:
            table = json.load(fh)
        mapping = load_map(args.map) if args.map else {}
        drift = []
        missing = []
        for rel, want in sorted(table.items()):
            new_rel = mapping.get(rel, rel)
            path = os.path.join(DOCS, new_rel)
            if not os.path.exists(path):
                missing.append((rel, new_rel))
                continue
            got = module.git_date(path)
            if got != want:
                drift.append((rel, new_rel, want, got))
        print(f"逐篇比对 {len(table)} 篇：漂移 {len(drift)} 篇，文件不在 {len(missing)} 篇")
        for rel, new_rel, want, got in drift[:20]:
            print(f"  {rel} → {new_rel}\n      原 {want}  现 {got}")
        for rel, new_rel in missing[:20]:
            print(f"  缺文件：{rel} → {new_rel}")
        return 1 if (drift or missing) else 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
