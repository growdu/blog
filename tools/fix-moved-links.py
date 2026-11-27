#!/usr/bin/env python3
"""搬家之后，把断掉的相对链接修回能走通的样子。

**为什么还需要这把工具**：搬家脚本改链接时，只能拿**旧树**当尺子 ——
旧文件还在磁盘上，才算得出一条相对链接原本指向哪儿；算出来，再按新位置改写。
问题是 2026-11-26 这一轮搬家**分成了前后两段**：

- 2026-11-17：PostgreSQL、Linux、工程化、分布式这几块先搬进
  `source-tracks/<赛道>/<阶段>/`；
- 2026-11-26：阶段目录改成带编号的 `L1-`/`L2-`，剩下的赛道（AI 工具、
  生活、博客、数据面…）也搬进来。

改链接那一段跑在**第二段开跑之前**。等到第二段真搬的时候，尺子量不到
已经搬走的那些文章 —— 链接只能留在原样，等于指向一个已经不存在的目录。
事后补：旧地址从**仓库自己的历史**里取（`git ls-tree` 给出搬家之前的树，
`git diff -M` 给出「旧路径 → 新路径」的完整对照），
断在哪由 `tools/check-internal-links.py` 指出来。一头一尾对上，
中间那层「这条链接本来指向谁」由旧树给出。

**三步找一条链接的本来面目**：

1. 按旧位置直接解析 —— 旧文件就在那儿，一对一对得上就用它；
2. 旧树里按路径尾巴认 —— 有些链接早先已经被改写过一次（多了一层
   `source-tracks/`），原路解析不到，但路径尾巴还是认得出来的；
3. 认不出来就放过 —— 猜比断着更坏，报告里列出来人工看。

**怎么用**：

    python3 tools/fix-moved-links.py            # 只报告
    python3 tools/fix-moved-links.py --apply    # 真改

尺子的基准树默认是 `e3986971`（2026-11-26 那一轮搬家之前）；
换基准树用 `--base <commit>`。
"""

import argparse
import importlib.util
import os
import re
import subprocess
import sys
from urllib.parse import quote, unquote

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(REPO, "docs")

#: 普通 markdown 链接（不含图片，图片是 ![]()）
LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)(\s+\"[^\"]*\")?\)")
#: 图片链接
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(\s+\"[^\"]*\")?\)")

EXTERNAL_PREFIXES = (
    "http://", "https://", "data:", "mailto:", "tel:", "ftp://",
    "javascript:", "about:", "//", "#",
)

#: bundle 的「首页」文件名
BUNDLE_INDEX = ("index.md", "index.html", "index.htm")


def _load_checker():
    """借 `check-internal-links.py` 的判据 —— 两边对「算不算断链」得一致。"""
    path = os.path.join(REPO, "tools", "check-internal-links.py")
    spec = importlib.util.spec_from_file_location("check_internal_links", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CHECK = _load_checker()


def git(*args):
    r = subprocess.run(["git"] + list(args), cwd=REPO,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("git %s 失败：%s" % (" ".join(args), r.stderr.strip()))
    return r.stdout


# ---------------------------------------------------------------- 旧树与对照表


def old_tree(base):
    """基准树 `base` 上 `docs/` 的文件与目录（docs 相对路径）。"""
    out = git("ls-tree", "-r", base, "--name-only", "--", "docs/")
    files = set()
    dirs = set()
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("docs/"):
            continue
        rel = line[len("docs/"):]
        if not rel:
            continue
        files.add(rel)
        d = os.path.dirname(rel)
        while d:
            dirs.add(d)
            d = os.path.dirname(d)
    return files, dirs


def move_map(base, head):
    """旧路径 → 新路径。新路径为 `None` 表示那次搬家把它删了。

    路径一律去掉 `docs/` 前缀 —— 跟旧树那套口径对齐。
    """
    out = git("diff", "--name-status", "-M50%", base, head, "--", "docs/")
    m = {}

    def rel(p):
        return p[len("docs/"):] if p.startswith("docs/") else p

    for line in out.splitlines():
        parts = line.split("\t")
        st = parts[0]
        if st.startswith("R"):
            m[rel(parts[1])] = rel(parts[2])
        elif st.startswith("D"):
            m[rel(parts[1])] = None
        elif st.startswith("A"):
            m[rel(parts[2])] = None      # 新文件，没有旧路径
        elif st[0] in ("M", "T"):
            m[rel(parts[1])] = rel(parts[1])  # 路径没变
    return m


# ---------------------------------------------------------------- 解析旧树


def _split_tail(raw):
    """`../foo/index.html` → `("../foo/", "index.html")`；`../foo/` → `("../foo/", "")`。"""
    if "/" not in raw:
        return "", raw
    head, tail = raw.rsplit("/", 1)
    return head + "/", tail


def resolve_in_old(files, dirs, target_dir, tail):
    """链接落在旧树哪个文件上。规则与 `sync-hexo.py` 对齐。"""
    if target_dir.startswith("..") or os.path.isabs(target_dir):
        return None
    if tail == "" or tail in BUNDLE_INDEX:
        for name in BUNDLE_INDEX + ("_index.md",):
            p = target_dir + "/" + name
            if p in files:
                return p
        return None
    ext = os.path.splitext(tail)[1].lower()
    if ext in (".md", ".html", ".htm"):
        p = target_dir + "/" + tail
        return p if p in files else None
    for e in (".md", ".html", ".htm"):
        p = target_dir + "/" + tail + e
        if p in files:
            return p
    return None


def resolve_old(files, dirs, old_dir, raw_path):
    """按旧位置解析一条相对链接。"""
    head, tail = _split_tail(raw_path)
    target_dir = os.path.normpath(os.path.join(old_dir, head))
    hit = resolve_in_old(files, dirs, target_dir, tail)
    if hit:
        return hit
    # 自愈兜底：作者常写 `./<同级 bundle>/`，真实目标是上一级目录。
    cleaned = raw_path.lstrip("./")
    parent = os.path.dirname(old_dir)
    if parent and not parent.startswith(".."):
        sib = os.path.normpath(os.path.join(parent, cleaned))
        if not sib.startswith(".."):
            hit = resolve_in_old(files, dirs, os.path.dirname(sib),
                                 os.path.basename(sib))
            if hit:
                return hit
    return None


def trail_of(raw_path):
    """一条链接的「路径尾巴」—— 去掉开头的 `./` 与 `../`。

    `../source-tracks/postgresql/getting-started/x/index.html` 的尾巴是
    `postgresql/getting-started/x/index.html`。改写过一次的链接就是靠这条
    尾巴认回旧目标。
    """
    return [p for p in raw_path.split("/") if p not in ("", ".", "..")]


def suffix_match(files, trail, is_dir):
    """旧树里，路径尾巴跟 `trail` 一样的那些文件（或目录）。"""
    if not trail:
        return []
    out = []
    last = trail[-1]
    base, ext = os.path.splitext(last)
    for f in files:
        parts = f.split("/")
        if len(parts) < len(trail):
            continue
        if parts[-len(trail):-1] != trail[:-1]:
            continue
        name = parts[-1]
        if is_dir:
            if name != last:
                continue
        elif ext in (".html", ".htm"):
            if name not in (last, base + ".md"):
                continue
        elif ext == ".md":
            if name != last:
                continue
        else:
            if name not in (last, base + ".md"):
                continue
        out.append(f)
    return out


# ---------------------------------------------------------------- 当前树


def current_files():
    """当前工作区里 `docs/` 的文件（docs 相对路径）。"""
    out = []
    for root, dirs, files in os.walk(DOCS):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), DOCS)
            out.append(rel.replace(os.sep, "/"))
    return out


def link_resolves(post_dir, raw):
    """这条相对链接现在走不走得通 —— 判据跟查链接的工具一致。

    链接是**相对文章所在目录**的，所以候选路径都得带上 `post_dir`；
    少了这一层，链接里的 `../` 会一路爬到仓库根目录去，撞上根目录下
    同名的目录就误判成「走得通」（`../aiv/index.html` 撞上仓库根的
    `aiv/`），于是真正断了的链接被放过。
    """
    target = unquote(raw)
    return any(CHECK.resolves(os.path.join(DOCS, c))
               for c in CHECK._candidate_targets(post_dir, target))


def image_resolves(post_dir, raw):
    """图片链接现在走不走得通。"""
    target = unquote(raw.split("#", 1)[0].split("?", 1)[0])
    if not target:
        return True
    for cand in (os.path.normpath(os.path.join(post_dir, target)),
                 os.path.normpath(os.path.join(post_dir, target.lstrip("./")))):
        if os.path.isfile(os.path.join(DOCS, cand)):
            return True
    return False


def link_style(raw):
    """这条链接原来用哪种写法：整条编码，还是只把空格编码掉。

    仓库里两种都有 —— 目录页里生成的链接整条 `%E5%…` 编码，
    作者手写的链接只把空格写成 `%20`、中文留白。搬家的时候**照原样搬**：
    改掉写法等于把一条链接改成另一条链接，连带段落字数都变了
    （审校规则按段落长度报警，链接一长就多出一条假信号）。
    """
    stripped = re.sub(r"%20", "", raw)
    if re.search(r"%[0-9A-Fa-f]{2}", stripped):
        return "encoded"
    return "spaced"


def encode_rel(rel, style):
    """按原来的写法给一条相对路径上编码。

    - `encoded`：整条 `%XX`（目录页里生成的那种）；
    - `spaced`：只把空格写成 `%20`、括号写成 `%28`/`%29`，中文留白
      （作者手写的那种，链接指向磁盘上的真文件名）。
    """
    if style == "encoded":
        return quote(rel, safe="/")
    return rel.replace("(", "%28").replace(")", "%29").replace(" ", "%20")


def build_dir_link(new_dir_of_target, new_dir, raw):
    """指向一个目录的链接。"""
    anchor = ""
    path = raw
    if "#" in path:
        path, anchor = path.split("#", 1)
        anchor = "#" + anchor
    rel = os.path.relpath(new_dir_of_target, new_dir).replace(os.sep, "/")
    return encode_rel(rel, link_style(path)).rstrip("/") + "/" + anchor


def archived_landing(files, mmap, old_target):
    """一个旧目录页被归档了 —— 它的内容搬到哪儿去了。

    归档的意思是「这一层的目录页没有了」，但底下的文章还在。
    链接指的还是那一层，就落到内容现在所在的那一层 —— 一堆文章的新位置
    取公共祖先目录，那才是链接该指的地方。

    返回新目录（docs 相对路径），找不到返回 None。
    """
    old_dir = os.path.dirname(old_target)
    news = []
    for f in files:
        if not f.startswith(old_dir + "/"):
            continue
        n = mmap.get(f, f)
        if n:
            news.append(n)
    if not news:
        return None
    parts = [p.split("/") for p in news]
    common = []
    for i in range(min(len(p) for p in parts)):
        seg = parts[0][i]
        if all(p[i] == seg for p in parts):
            common.append(seg)
        else:
            break
    if not common:
        return None
    # 公共祖先要是文件本身，就退到它所在的目录
    if len(common) == len(news[0].split("/")):
        return "/".join(common[:-1])
    return "/".join(common)


def build_link(new_target, new_dir, raw):
    """按新位置算出新的相对链接，保留原来的「形状」。

    形状指四件事：指的是目录还是文件、末尾是不是 bundle 的 `index.html`、
    锚点还在不在、文件名那截**怎么编码**的。改掉形状 = 把一条链接改成
    另一条链接。

    编码这一条特别要紧：文件名里带空格，markdown 里必须写成 `%20`，否则
    链接在第一个空格处就断了。仓库里两种写法都有（`./10_AI%20到底有多聪明…`
    是「空格编码、中文留白」，`getting-started/%E5%91%BD…` 是「全编码」），
    所以**原来的那截原样留着**，只把目录换成新的 —— 整条路径都按原来那种
    写法来（`link_style` 判一次，整条统一），不掺着来。
    """
    anchor = ""
    path = raw
    if "#" in path:
        path, anchor = path.split("#", 1)
        anchor = "#" + anchor
    decoded = unquote(path)
    style = link_style(path)

    if decoded.endswith("/"):
        d = os.path.dirname(new_target)
        rel = os.path.relpath(d, new_dir).replace(os.sep, "/")
        return encode_rel(rel, style) + "/" + anchor

    name = os.path.basename(path)
    if name in ("index.html", "index.htm") and new_target.endswith(".md"):
        d = os.path.dirname(new_target)
        rel = os.path.relpath(d, new_dir).replace(os.sep, "/")
        return encode_rel(rel, style) + "/" + name + anchor

    rel = os.path.relpath(new_target, new_dir).replace(os.sep, "/")
    return encode_rel(rel, style) + anchor


# ---------------------------------------------------------------- 找旧目标


def find_target(files, dirs, old_dir, raw_path):
    """一条断掉的链接本来指向哪个旧文件。

    三步：

    1. 按旧位置直接解析；
    2. 旧树里按路径尾巴认（链接早先被改写过多一层前缀时用）；
    3. 认不出来 —— 返回 None，交给人看。
    """
    decoded = unquote(raw_path)
    is_dir = decoded.endswith("/")

    hit = resolve_old(files, dirs, old_dir, decoded)
    if hit:
        return hit

    trail = trail_of(decoded)
    if not trail:
        return None
    if is_dir:
        cands = [d for d in dirs if d.split("/")[-len(trail):] == trail]
    else:
        cands = suffix_match(files, trail, False)
    if len(cands) == 1:
        return cands[0]
    # 同一个赛道里认 —— 旧位置附近的那个最可能是它要的
    if len(cands) > 1:
        near = [c for c in cands if c.startswith(old_dir + "/")]
        if len(near) == 1:
            return near[0]
    return None


# ---------------------------------------------------------------- 主流程


def main():
    ap = argparse.ArgumentParser(description="把搬家之后断掉的相对链接修回来")
    ap.add_argument("--base", default="e3986971",
                    help="基准树：搬家之前的那一版（默认 e3986971）")
    ap.add_argument("--head", default="HEAD", help="搬完家的那一版（默认 HEAD）")
    ap.add_argument("--apply", action="store_true", help="真改（默认只报告）")
    args = ap.parse_args()

    files, dirs = old_tree(args.base)
    mmap = move_map(args.base, args.head)
    # 反向：新路径 → 旧路径
    new2old = {}
    for old, new in mmap.items():
        if new:
            new2old[new] = old

    fixed = []        # (文件, 旧链接, 新链接)
    unresolved = []   # (文件, 链接)
    for rel in sorted(current_files()):
        if not rel.endswith(".md"):
            continue
        if rel not in files and rel not in new2old:
            continue        # 这一轮新造的文件，没有旧位置可查
        path = os.path.join(DOCS, rel)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()

        new_dir = os.path.dirname(rel)
        old_rel = new2old.get(rel, rel)
        old_dir = os.path.dirname(old_rel)

        def handle(m, is_image):
            raw = m.group(2)
            if raw.startswith(EXTERNAL_PREFIXES) or raw.startswith("/"):
                return m.group(0)
            path_part = raw.split("#", 1)[0].split("?", 1)[0]
            if not path_part:
                return m.group(0)
            # 已经能走通的，不碰
            if is_image:
                if image_resolves(new_dir, path_part):
                    return m.group(0)
            elif link_resolves(new_dir, path_part):
                return m.group(0)

            target = find_target(files, dirs, old_dir, path_part)
            if target is None:
                unresolved.append((rel, raw))
                return m.group(0)
            new_target = mmap.get(target, target)
            if new_target is None:
                # 旧目录页被归档了 —— 落到它的内容现在所在的那一层。
                landing = archived_landing(files, mmap, target)
                if landing is None:
                    unresolved.append((rel, raw))
                    return m.group(0)
                new_raw = build_dir_link(landing, new_dir, raw)
                fixed.append((rel, raw, new_raw))
                title = m.group(3) or ""
                if is_image:
                    return "![%s](%s%s)" % (m.group(1), new_raw, title)
                return "[%s](%s%s)" % (m.group(1), new_raw, title)
            new_raw = build_link(new_target, new_dir, raw)
            fixed.append((rel, raw, new_raw))
            title = m.group(3) or ""
            if is_image:
                return "![%s](%s%s)" % (m.group(1), new_raw, title)
            return "[%s](%s%s)" % (m.group(1), new_raw, title)

        new_text = IMAGE_RE.sub(lambda m: handle(m, True), text)
        new_text = LINK_RE.sub(lambda m: handle(m, False), new_text)
        if new_text != text and args.apply:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new_text)

    for rel, raw, new_raw in fixed:
        print("  %s\n    %s\n    -> %s" % (rel, raw, new_raw))
    for rel, raw in unresolved:
        print("  ! %s —— %s（没认出来）" % (rel, raw))
    print("\n认出来了 %d 条，认不出来 %d 条。" % (len(fixed), len(unresolved)))
    if not args.apply and fixed:
        print("（还没改 —— 加 --apply 才动手）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
