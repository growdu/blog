"""学习路径目录树的守卫：树的结构必须和规则表、重定向表、分类链对得上。

**背景**
------
2026-11-26，`docs/` 的物理目录被重排成学习路径的镜像：
`docs/source-tracks/<赛道>/<阶段>/…`。搬家本身是一次性工程，
但**规则表**（`data/learning-path.json`）、**重定向表**
（`data/redirects.json`）、**分类链**（`_index.md` 的 `cascade.categories`）
与**审校台账**（`review/source-tracks/`）是四份会继续各自演进的东西。

四份东西一旦对不上，读者看到的站点就自相矛盾：

- 规则表说阶段在 `L7-logical-replication/`，目录却在别处 ——
  学习路径页列出来的文章点开是 404；
- 重定向表的目标指向一篇不存在的文章 ——
  老链接跳过去是软 404（HTTP 200 + 首页），**看起来一切正常**；
- 分类链少一层或多一层 ——
  分类页的层级和导航对不上，搜索的分类维度也跟着歪；
- 审校记录挂在一条赛道下，原文却在另一条 ——
  台账说「这篇审过了」，其实审的是另一篇。

所以这里有五条守卫，全部是**结构对账**，不需要构建产物，
因此能进 `site-guard.yml`（那条工作流不构建产物）。

放在根级 ``tests/``，随 ``site-guard.yml`` 进 CI。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"
RULES_FILE = REPO_ROOT / "data" / "learning-path.json"
REDIRECTS_FILE = REPO_ROOT / "data" / "redirects.json"
REVIEW_DIR = REPO_ROOT / "review"

# 顶层目录（``docs/`` 下的一级）到中文分类名的映射。
# 与 ``tools/sync-hexo.py`` 的 ``read_section_categories()`` 同一口径：
# 一级目录下的 ``_index.md`` 的 ``title`` 就是这个目录的分类名。
#
# 链条的形状固定是三级：**内容库 → 赛道 → 阶段**。
CATEGORY_CHAIN_LENGTH = 3
ROOT_CATEGORY = "内容库"


def _read_front_matter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[3:end] if end != -1 else ""


def _section_titles() -> dict[str, str]:
    """``docs/<一级目录>/_index.md`` 的 ``title`` → 该目录的中文名。"""
    titles = {}
    for section in sorted(p for p in DOCS.iterdir() if p.is_dir()):
        index = section / "_index.md"
        if not index.is_file():
            continue
        match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$',
                          _read_front_matter(index), re.MULTILINE)
        if match:
            titles[section.name] = match.group(1).strip()
    return titles


def _cascade_categories() -> dict[str, list[str]]:
    """``docs/**/_index.md`` 的 ``cascade.categories`` → 目录 → 分类名列表。

    与 ``tools/sync-hexo.py`` 的 ``read_cascade_categories()`` 同一口径
    （同一条正则：``cascade:`` 下一行 ``categories:``，再下一行是列表）。
    """
    cascades: dict[str, list[str]] = {}
    for index in sorted(DOCS.rglob("_index.md")):
        front = _read_front_matter(index)
        match = re.search(
            r"cascade:\s*\n\s*categories:\s*\n((?:\s*-\s*.+\n)+)", front, re.MULTILINE
        )
        if not match:
            continue
        names = [line.strip()[1:].strip().strip('"\'')
                 for line in match.group(1).splitlines()]
        rel = index.parent.relative_to(DOCS).as_posix()
        cascades[rel] = [n for n in names if n]
    return cascades


def _category_chain(rel: str, titles: dict[str, str],
                    cascades: dict[str, list[str]]) -> list[str]:
    """一篇文章的分类链 —— 与 ``resolve_post_categories()`` 同一算法。

    1. 一级目录的中文名（``primary``，排在最前）；
    2. 从最近的祖先目录往上走，把 ``cascade.categories`` 依次追加，
       重复的去掉。

    搬完家之后这条链**必须**正好三级：一级目录（内容库）、
    赛道、阶段。多一级少一级，分类页和导航就对不上了。
    """
    section = rel.split("/")[0]
    primary = titles.get(section, section or "随笔")
    cats = [primary]
    seen = {primary}
    parent = "/".join(rel.split("/")[:-1])
    parts = parent.split("/") if parent else []
    for i in range(1, len(parts) + 1):
        sub = "/".join(parts[:i])
        for name in cascades.get(sub, []):
            if name not in seen:
                cats.append(name)
                seen.add(name)
    return cats


def _article_paths() -> list[str]:
    """``docs/`` 下会被当成文章的路径（相对 ``docs/``，正斜杠）。

    ``_index.md`` 是目录页，不发；``video/`` 那种内容单元在 ``aiv/`` 下，
    不走 ``docs/`` 的分类链，所以这里只取 ``docs/``。
    """
    out = []
    for path in sorted(DOCS.rglob("*.md")):
        rel = path.relative_to(DOCS).as_posix()
        if path.name == "_index.md":
            continue
        out.append(rel)
    return out


# --------------------------------------------------- 1. 重定向表的对账


def test_every_redirect_target_exists_in_docs():
    """重定向表里每一条的**目标**都必须是 ``docs/`` 下真实存在的文章。

    一条指向不存在文章的重定向，老链接跳过去是**软 404** ——
    服务端对任何未知路径返回首页，HTTP 200、页面完整，
    探活脚本看起来一切正常。这条守卫就是拦住那种「接住了但接空」的跳转。

    表里的**值是 URL 形态**（没有扩展名），对应 ``docs/`` 下的源文件：
    ``X`` → ``X.md``（文章）、``X.html``（本来就是 html 的文章）、
    ``X.so``（资源原样搬过去）、``X/index.md``（目录页）。
    """
    redirects = json.loads(REDIRECTS_FILE.read_text(encoding="utf-8"))
    missing = []
    for old, new in redirects.items():
        target = DOCS / new
        candidates = [
            target,
            target.parent / (target.name + ".md"),
            target.parent / (target.name + ".html"),
            target / "index.md",
        ]
        if not any(candidate.exists() for candidate in candidates):
            missing.append(f"{old} -> {new}")
    assert not missing, (
        "这些重定向的目标在 docs/ 里不存在（跳过去是软 404 首页）：\n"
        + "\n".join("  " + m for m in missing)
    )


def test_every_redirect_target_is_reachable_from_the_rules_table():
    """重定向的目标必须落在**某条赛道**里，不能指向树外的东西。

    目标路径如果不在 ``docs/source-tracks/`` 下面，它就不在分类链里，
    也不在学习路径页上 —— 读者从老链接进来，看到的是一篇没有导航的孤儿文章。
    """
    redirects = json.loads(REDIRECTS_FILE.read_text(encoding="utf-8"))
    outside = sorted({
        new for new in redirects.values()
        if not new.startswith("source-tracks/")
    })
    assert not outside, (
        "这些重定向的目标不在 docs/source-tracks/ 下面（不在任何赛道里）：\n"
        + "\n".join("  " + p for p in outside)
    )


# --------------------------------------------------- 2. 规则表与目录的对账


def test_each_stage_directory_has_exactly_one_path_prefix_rule():
    """每个阶段目录恰好一条 ``path_prefix`` 规则。

    两条就意味着这个阶段的边界是含糊的：一条文章同时命中两个阶段时，
    工具按贪心规则交给**先匹配到的那个**，另一个阶段就少了一篇
    ——「这个阶段有多少篇」这个数字开始骗人。

    一条都没有更糟：这个阶段收不到任何文章，是个空壳。
    """
    rules = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    offenders = []
    for track in rules["tracks"]:
        for stage in track["stages"]:
            prefixes = [rule for rule in stage.get("match", [])
                        if "path_prefix" in rule]
            if len(prefixes) != 1:
                offenders.append(
                    "{}/{}: {} 条 path_prefix 规则".format(
                        track["id"], stage["id"], len(prefixes))
                )
    assert not offenders, (
        "阶段目录的 path_prefix 规则不是恰好一条：\n"
        + "\n".join("  " + o for o in offenders)
    )


def test_every_stage_rule_points_at_a_directory_that_exists():
    """规则里写的目录必须真实存在。

    规则表是「事实源」，目录是「事实」——两者对不上的时候，
    阶段页会显示一个空阶段，而空阶段在页面上读起来像
    「这里还没写」，而不是「这个阶段不存在」。
    """
    rules = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    missing = []
    for track in rules["tracks"]:
        for stage in track["stages"]:
            for rule in stage.get("match", []):
                prefix = rule.get("path_prefix")
                if not prefix:
                    continue
                directory = DOCS / prefix.rstrip("/")
                if not directory.is_dir():
                    missing.append(f"{track['id']}/{stage['id']}: {prefix}")
    assert not missing, (
        "规则里的目录在 docs/ 下不存在：\n"
        + "\n".join("  " + m for m in missing)
    )


def test_the_stage_prefix_is_the_stage_directory_under_its_track():
    """阶段的 ``path_prefix`` 必须是 ``source-tracks/<赛道>/<阶段目录>/``。

    这一条钉住「规则表里的阶段 id 和磁盘上的目录名是同一个东西」。
    阶段目录带 ``L1-`` 这样的编号前缀，规则里也必须带 ——
    不带的话，规则写的是 ``postgresql/getting-started/``，
    目录却是 ``postgresql/L1-getting-started/``，规则一条都命中不了。
    """
    rules = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    offenders = []
    for track in rules["tracks"]:
        for stage in track["stages"]:
            expected = "source-tracks/{}/{}/".format(track["id"], stage["dir"])
            for rule in stage.get("match", []):
                prefix = rule.get("path_prefix")
                if prefix and prefix != expected:
                    offenders.append(
                        "{}/{}: 规则写的是 {}，目录是 {}".format(
                            track["id"], stage["id"], prefix, expected)
                    )
    assert not offenders, (
        "阶段规则的前缀与它的目录对不上：\n"
        + "\n".join("  " + o for o in offenders)
    )


def test_no_rule_still_uses_a_path_regex():
    """规则表里一条正则都不剩。

    正则规则是「按学科切目录」那套的老办法：分类名一变、正则就失配，
    而失配是**静默**的 —— 文章悄悄从学习路径里消失，页面看起来还是完整的。
    目录重排之后，规则全部变成「路径前缀」，一条正则都不该剩下。
    """
    rules = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    offenders = []

    def walk(node, where):
        for rule in node or []:
            if "path_regex" in rule:
                offenders.append(f"{where}: {rule['path_regex']}")
            for key in ("any", "all"):
                if key in rule:
                    walk(rule[key], where)

    for track in rules["tracks"]:
        walk(track.get("track_match"), track["id"])
        for stage in track["stages"]:
            walk(stage.get("match"), f"{track['id']}/{stage['id']}")
    assert not offenders, (
        "规则表里还有 path_regex —— 目录重排之后不该再有正则规则：\n"
        + "\n".join("  " + o for o in offenders)
    )


def test_every_track_has_a_lane_card_colour_in_the_theme():
    """每条赛道都要在主题 CSS 里有一条配色规则。

    首页的赛道卡片靠 ``.lane-card--<track.id>`` 取色。
    规则表里加了一条赛道、CSS 里忘了加 —— 那张卡片就退回默认色，
    看起来像「这条赛道没配过」，而页面本身没有任何报错。
    """
    css = (REPO_ROOT / "themes" / "matery" / "source" / "css" / "tech.css").read_text(
        encoding="utf-8"
    )
    rules = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    missing = [
        track["id"] for track in rules["tracks"]
        if f".lane-card--{track['id']}" not in css
    ]
    assert not missing, (
        "这些赛道在主题 CSS 里没有配色规则（卡片会退回默认色）：\n"
        + "\n".join("  " + m for m in missing)
    )


def test_the_theme_carries_no_colour_for_a_retired_track_id():
    """主题里不该留着已经退场的赛道 id。

    2026-11-26 之前有两条赛道叫 ``db-internals`` 和 ``linux-network``，
    现在叫 ``postgresql`` 和 ``linux``。老类名留在 CSS 里不碍事，
    但它会让人以为老 id 还在用 —— 下一次改赛道名的人就会照着它改，
    于是两条赛道共用一个颜色。
    """
    css = (REPO_ROOT / "themes" / "matery" / "source" / "css" / "tech.css").read_text(
        encoding="utf-8"
    )
    retired = ["db-internals", "linux-network"]
    left = [name for name in retired if f".lane-card--{name}" in css]
    assert not left, (
        "主题 CSS 里还留着退场赛道的类名：\n"
        + "\n".join("  " + name for name in left)
    )


# --------------------------------------------------- 3. 分类链


def test_the_category_chain_is_three_levels_for_every_article():
    """每篇文章的分类链正好三级：内容库 → 赛道 → 阶段。

    链的层数由**祖先目录的 ``cascade.categories``** 决定，
    而祖先目录的层数由规则表的阶段目录决定。两条链一旦错开一位
    （比如某个阶段的 ``_index.md`` 漏了 ``cascade``），
    那条赛道下的所有文章就少一级分类 ——
    分类页少一层、搜索的分类维度歪一层，而页面上看不出哪里不对。
    """
    titles = _section_titles()
    cascades = _cascade_categories()
    offenders = []
    for rel in _article_paths():
        chain = _category_chain(rel, titles, cascades)
        if len(chain) != CATEGORY_CHAIN_LENGTH:
            offenders.append(f"{rel} → {chain}")
    assert not offenders, (
        "这些文章的分类链不是三级（{}）：\n{}".format(
            CATEGORY_CHAIN_LENGTH,
            "\n".join("  " + o for o in offenders[:40]))
    )


def test_every_article_chain_starts_with_the_root_category():
    """链的第一级必须统一是「内容库」。

    第一级由 ``docs/`` 一级目录的 ``_index.md`` 的 ``title`` 决定。
    它变了，分类页的第一层和导航栏对不上，全站的分类 URL 也跟着变。
    """
    titles = _section_titles()
    cascades = _cascade_categories()
    offenders = []
    for rel in _article_paths():
        chain = _category_chain(rel, titles, cascades)
        if not chain or chain[0] != ROOT_CATEGORY:
            offenders.append(f"{rel} → {chain}")
    assert not offenders, (
        "这些文章的分类链第一级不是「{}」：\n{}".format(
            ROOT_CATEGORY, "\n".join("  " + o for o in offenders[:40]))
    )


def test_every_track_and_stage_directory_has_a_cascade():
    """赛道目录与阶段目录都得有 ``_index.md`` 和 ``cascade.categories``。

    少一个，挂在它下面的所有文章就少一级分类 —— 而这不会报错，
    只会让分类页少一层。
    """
    rules = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    cascades = _cascade_categories()
    missing = []
    for track in rules["tracks"]:
        for stage in track["stages"]:
            rel = "source-tracks/{}/{}".format(track["id"], stage["dir"])
            if rel not in cascades:
                missing.append(rel)
    assert not missing, (
        "这些阶段目录没有 cascade.categories（挂在下面的文章会少一级分类）：\n"
        + "\n".join("  " + m for m in missing)
    )


# --------------------------------------------------- 4. 审校台账


def _review_records() -> list[Path]:
    """逐篇审校记录 —— 只有 ``review/source-tracks/`` 下面是。

    ``review/plans/``、``review/specs/``、``review/scope/`` 装的是
    规划与规范，不是「某一篇文章的审校记录」，不该被这条守卫扫到。
    """
    return sorted((REVIEW_DIR / "source-tracks").rglob("*.md"))


# 「原文：docs/source-tracks/…/xxx.md」——路径里有空格，所以不能用 ``\\S+``。
_ORIGIN_RE = re.compile(r"^-\s*原文：(.+?)\s*$", re.MULTILINE)


def test_every_review_record_points_at_an_article_that_exists():
    """审校记录里的「原文」路径必须指向真实存在的文章。

    记录写的是**相对仓库根**的路径（``docs/...``）。
    文章搬家而记录没跟着搬，台账就会审一篇已经不存在的文章 ——
    「已审 18 篇」这个数字就成了假话。
    """
    offenders = []
    for record in _review_records():
        text = record.read_text(encoding="utf-8")
        match = _ORIGIN_RE.search(text)
        if not match:
            offenders.append(f"{record.relative_to(REPO_ROOT)}: 没有「原文」行")
            continue
        target = REPO_ROOT / match.group(1)
        if not target.exists():
            offenders.append(
                f"{record.relative_to(REPO_ROOT)}: 原文不存在（{match.group(1)}）"
            )
    assert not offenders, (
        "这些审校记录的「原文」对不上：\n" + "\n".join("  " + o for o in offenders)
    )


def test_every_review_record_sits_under_its_article_track():
    """记录要放在**原文所属赛道**的目录下。

    台账的目录就是分组键：读者按赛道找「这条线审到哪了」，
    靠的就是 ``review/source-tracks/<赛道>/``。
    记录挂在别的赛道下，那条赛道的进度就少了一篇 ——
    而索引表里那一行还在，数字照样好看。
    """
    offenders = []
    for record in _review_records():
        text = record.read_text(encoding="utf-8")
        match = _ORIGIN_RE.search(text)
        if not match:
            continue
        rel = match.group(1)
        parts = rel.split("/")
        if len(parts) < 3 or parts[0] != "docs" or parts[1] != "source-tracks":
            offenders.append(f"{record.relative_to(REPO_ROOT)}: 原文不在赛道里（{rel}）")
            continue
        track = parts[2]
        if record.relative_to(REVIEW_DIR / "source-tracks").parts[0] != track:
            offenders.append(
                f"{record.relative_to(REPO_ROOT)}: 原文属于 {track} 赛道，记录却不在那下面"
            )
    assert not offenders, (
        "这些审校记录不在原文所属赛道的目录下：\n"
        + "\n".join("  " + o for o in offenders)
    )
