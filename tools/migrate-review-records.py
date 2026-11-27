#!/usr/bin/env python3
"""把 `review/` 下的逐篇审校记录跟着文章一起搬家。

**为什么记录也要搬**：审校记录是**逐篇**的 —— 一份记录对应一篇文章，
开头那行 `- 原文：docs/<路径>` 就是它的地址。文章搬了家而记录没搬，
两个答案对不上：读者拿着记录找不到文章，审校者拿着记录不知道说的是哪篇。

**记录落到哪儿**：镜像文章的新路径。记录的文件名沿用作者起的那份
（`corosync-down网卡仍处于多数派.md` 这种收平过的名字不���改），
只换目录 —— 目录跟着文章走，文章在哪，读者就能顺着找过去。

**改什么**：

- 记录文件本身搬家（`git mv`，历史跟着走）；
- 开头那行 `- 原文：docs/<路径>` 改成新路径；
- `review/INDEX.md` 表格里的「记录」列跟着改，「支柱」列换成赛道名。

**两次搬家是一张链**：2026-11-17 那一轮（`cluster/` → `distributed/`）
和 2026-11-26 那一轮（`distributed/foundations/` → `distributed/L1-foundations/`）
首尾相接 —— 一篇文章可能搬了两次。这里把两张表接成一条链，
顺着链走到底才是它现在的位置。

用法：

    python3 tools/migrate-review-records.py           # 先看会搬成什么样
    python3 tools/migrate-review-records.py --apply   # 真搬
"""

import argparse
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEW = os.path.join(REPO, "review")
INDEX_FILE = os.path.join(REPO, "review", "INDEX.md")

#: 两轮搬家的表，按时间从早到晚排 —— 后一轮的「旧路径」正是前一轮的「新路径」。
MOVES_FILES = (
    os.path.join(REPO, "data", "migration-moves-2026-11-17.json"),
    os.path.join(REPO, "data", "migration-moves.json"),
)

#: `- 原文：docs/<路径>` —— 路径里**可以有空格**（文件名带空格的那些）
SOURCE_RE = re.compile(r"^(\s*-\s*原文：\s*)(.+?)\s*$", re.MULTILINE)
#: `review/INDEX.md` 表格里的「记录」列
INDEX_ROW_RE = re.compile(r"^\|\s*\[([^\]]*)\]\(([^)]+)\)\s*\|(.*)$", re.MULTILINE)

#: 不搬的：`review/` 下这些是**历史快照**，改了就是篡改历史
SKIP_DIRS = ("plans", "specs", "scope")

#: `review/` 下不是审校记录的文件
NON_RECORD_FILES = ("README.md", "INDEX.md", "description-drafts.md")


def git(*args):
    return subprocess.run(["git"] + list(args), cwd=REPO,
                          capture_output=True, text=True)


def load_moves():
    """旧路径 → 新路径（两轮接成一条链）。"""
    moves = {}
    for path in MOVES_FILES:
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        for old, new in raw.get("articles", {}).items():
            moves[old] = new
    return moves


def new_article_path(old_rel, moves):
    """顺着链走到底 —— 一篇文章可能搬了两次。"""
    seen = set()
    cur = old_rel
    while cur in moves and cur not in seen:
        seen.add(cur)
        cur = moves[cur]
    return cur


def record_files():
    """逐篇审校记录（排除 plans / specs / scope 这些历史快照）。"""
    out = []
    for root, dirs, files in os.walk(REVIEW):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith(".md") and name not in NON_RECORD_FILES:
                out.append(os.path.relpath(os.path.join(root, name),
                                           REVIEW).replace(os.sep, "/"))
    return sorted(out)


def parse_source(text):
    m = SOURCE_RE.search(text)
    return m.group(2) if m else ""


def find_record_by_name(name):
    """按文件名在 `review/` 下找一份记录。"""
    for rel in record_files():
        if os.path.basename(rel) == name:
            return os.path.join(REVIEW, rel)
    return None


def track_of(article_rel):
    """文章现在在哪条赛道上 —— `source-tracks/<赛道>/…`。"""
    parts = article_rel.split("/")
    if len(parts) >= 2 and parts[0] == "source-tracks":
        return parts[1]
    return parts[0] if parts else ""


def plan():
    """算出每份记录的「从哪儿搬到哪儿」。"""
    moves = load_moves()
    out = []
    for rel in record_files():
        path = os.path.join(REVIEW, rel)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        source = parse_source(text)
        if not source.startswith("docs/"):
            out.append((rel, rel, None, "没有「原文」行"))
            continue
        old = source[len("docs/"):]
        new = new_article_path(old, moves)
        # 目录跟着文章走；bundle（`…/名字/index.md`）收平，跟文章同名的
        # 文件放在 bundle 目录旁边 —— 记录一直就是平的，不跟 bundle 一起
        # 拐进目录里。
        dest = record_rel_for_article(new)
        if dest == rel:
            continue        # 已经在该在的地方
        if new == old:
            out.append((rel, rel, None, "原文不在迁移表里：%s" % old))
            continue
        out.append((rel, dest, new, ""))
    return out


def apply_move(old_rel, new_rel):
    src = os.path.join("review", old_rel)
    dst = os.path.join("review", new_rel)
    os.makedirs(os.path.join(REPO, os.path.dirname(dst)), exist_ok=True)
    r = git("mv", src, dst)
    if r.returncode != 0:
        print("  搬不了 %s -> %s\n    %s" % (src, dst, r.stderr.strip()),
              file=sys.stderr)
        return False
    return True


def rewrite_source(new_rel, article_new_rel):
    path = os.path.join(REVIEW, new_rel)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    new_text = SOURCE_RE.sub(
        lambda m: "%sdocs/%s%s" % (m.group(1), article_new_rel, ""),
        text, count=1)
    if new_text != text:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new_text)


def record_rel_for_article(article_new_rel):
    """文章的新路径 → 记录该待的位置（bundle 收平）。"""
    if article_new_rel.endswith("/index.md"):
        return article_new_rel[: -len("/index.md")] + ".md"
    return article_new_rel


def rewrite_index():
    """`review/INDEX.md` 的「记录」列跟着改，「支柱」列换成赛道名。

    这一步是**自足**的：它不靠「刚才搬了哪些」这个上下文，而是回到每份
    记录自己的「原文」行，顺着链找到文章现在在哪儿，再算出记录该在哪儿。
    所以记录搬完了还能再跑一遍，也不会把没搬过的行改坏。
    """
    moves = load_moves()
    with open(INDEX_FILE, encoding="utf-8") as fh:
        text = fh.read()

    def repl(m):
        target = m.group(2)
        record_path = os.path.join(REVIEW, target)
        if not os.path.isfile(record_path):
            # 记录已经搬走了 —— 按文件名找它现在在哪儿。
            found = find_record_by_name(os.path.basename(target))
            if not found:
                return m.group(0)
            record_path = found
        with open(record_path, encoding="utf-8") as fh:
            source = parse_source(fh.read())
        if not source.startswith("docs/"):
            return m.group(0)
        new_article = new_article_path(source[len("docs/"):], moves)
        new_rel = record_rel_for_article(new_article)
        # 「支柱」列在「记录」列后面第一格。
        cells = m.group(3).split("|")
        if len(cells) >= 2:
            cells[0] = " %s " % track_of(new_article)
        return "| [%s](%s) |%s" % (m.group(1), new_rel, "|".join(cells))

    new_text = INDEX_ROW_RE.sub(repl, text)
    if new_text != text:
        with open(INDEX_FILE, "w", encoding="utf-8") as fh:
            fh.write(new_text)


def main():
    ap = argparse.ArgumentParser(description="把审校记录跟着文章搬家")
    ap.add_argument("--apply", action="store_true", help="真搬（默认只报告）")
    args = ap.parse_args()

    moves = plan()
    problems = [(o, n, why) for o, n, _, why in moves if why]
    for old_rel, new_rel, _, why in moves:
        if why:
            print("  ! %s —— %s" % (old_rel, why))
        else:
            print("  %s\n    -> %s" % (old_rel, new_rel))
    print("\n共 %d 份记录，%d 份有去向，%d 份有问题"
          % (len(moves), len(moves) - len(problems), len(problems)))
    if problems:
        print("有问题的那几份先别搬 —— 人工看一眼再说。")
        return 1
    if not args.apply:
        print("\n（还没搬 —— 加 --apply 才动手）")
        return 0

    moved = 0
    for old_rel, new_rel, article_new_rel, _ in moves:
        if old_rel == new_rel:
            continue
        if not apply_move(old_rel, new_rel):
            return 1
        rewrite_source(new_rel, article_new_rel)
        moved += 1
    rewrite_index()
    print("\n搬完了 %d 份。" % moved)
    return 0


if __name__ == "__main__":
    sys.exit(main())
