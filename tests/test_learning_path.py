"""学习路径的守卫：全站每一篇文章都必须落在**一条**赛道的一个阶段里。

**背景**
------
站内 577 篇文章分在 43 个分类里，但分类是**检索**用的，不是**导航**用的：
读者从一篇文章落地之后，站点没有告诉他「下一篇该读什么」。学习路径
（``/learning/`` 和每条赛道一页）就是补这个洞的。

分类是脚本做的（``tools/build-learning-path.py`` + ``data/learning-path.json``），
所以它有三种失败方式，每一种都得有人拦：

1. **漏归类** —— 新加一篇文章，忘了写规则，它就悄悄从学习路径里消失了。
   读者看到的路径是「完整」的，实际上少了一块。
2. **重复归类** —— 一篇文章同时落进两条赛道或两个阶段，读者要读两遍，
   而且「这个阶段有多少篇」这个数字开始骗人。
3. **规则本身错了** —— 兜底规则写在了中间阶段，把后面阶段的文章全吞了；
   阶段 id 写重；``fallback_stage`` 指了一个不存在的阶段。

**契约**
--------
1. 全站每一篇文章都归到了**恰好一条**赛道的一个阶段（不许漏，不许重）。
2. 生成的赛道页里，每篇文章**恰好出现一次**（不许被渲染丢掉）。
3. 规则文件结构合法：赛道 id 唯一、阶段 id 递增、``fallback_stage`` 存在。
4. ``catch_all`` 只允许出现在**最后一个**阶段 —— 写在中间会把后面阶段
   的文章全吞掉（这是真踩过的坑，见工具里 classify() 的注释）。
5. 站内链接必须带挂载点前缀（主站 ``/``、镜像站 ``/blog/``）。
6. 生成器必须在**两个** CI job 里都跑（主站和 GitHub Pages 镜像），
   而且要排在 sync 之后、hexo generate 之前。

这个测试**不需要构建产物**：语料直接从 ``docs/`` 和 ``aiv/`` 推出来，
所以它能进 ``site-guard.yml``（那条工作流不构建产物）。

放在根级 ``tests/``，随 ``site-guard.yml`` 进 CI。
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools"
RULES_FILE = REPO_ROOT / "data" / "learning-path.json"
TOOL = TOOLS / "build-learning-path.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "hexo.yml"
THEME_LAYOUT = REPO_ROOT / "themes" / "matery" / "layout" / "learning.ejs"
HOME_HERO = REPO_ROOT / "themes" / "matery" / "layout" / "_partial" / "home-hero.ejs"
HOME_CONTENT = REPO_ROOT / "themes" / "matery" / "layout" / "_partial" / "home-content.ejs"
HOME_PANEL = (REPO_ROOT / "themes" / "matery" / "layout" / "_partial"
              / "learning-path.ejs")

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import site_root  # noqa: E402  (path set up above)


@pytest.fixture(scope="module")
def tool():
    """Import ``tools/build-learning-path.py`` as a module.

    ``main()`` is guarded by ``if __name__ == '__main__'``, so importing
    it only defines functions -- it does not write any file.
    """
    spec = importlib.util.spec_from_file_location("build_learning_path", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rules():
    return json.loads(RULES_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def corpus(tool):
    """The whole site's article list, derived **without** a build.

    ``docs/`` for the articles, ``aiv/pipeline/Makefile`` for the video
    episodes.  ``url`` is a placeholder that encodes the article's
    identity (``/`` + flattened path) -- the real permalink needs the
    git date, and the coverage questions below don't care about dates.

    The path is percent-encoded exactly like the real permalink does,
    so that a path containing parentheses (``--boot和--single``) can't
    be mistaken for the end of a Markdown link.
    """
    posts = tool.source_corpus()
    for post in posts:
        post["url"] = "/" + quote(post["rel"])
    return posts


@pytest.fixture(scope="module")
def classified(tool, rules, corpus):
    return tool.classify(corpus, rules)


# --------------------------------------------------------------- 1. 覆盖


def test_every_article_is_classified(classified, corpus):
    """No article may fall outside every track.

    A new article with no matching rule used to disappear from the
    learning path silently -- the path still looked complete, it was
    just missing a piece.  The tool exits non-zero on this case; this
    test is the version that runs without a build.
    """
    tracks, unclassified = classified
    assert not unclassified, (
        "有 {} 篇文章没归到任何赛道 —— 给它们加规则（data/learning-path.json）：\n"
        "{}".format(
            len(unclassified),
            "\n".join("  " + p["rel"] for p in unclassified[:30]),
        )
    )
    covered = sum(len(s["posts"]) for t in tracks for s in t["stages"])
    assert covered == len(corpus), (
        "覆盖数对不上：分类出 {} 篇，语料 {} 篇".format(covered, len(corpus))
    )


def test_no_article_lands_in_two_places(classified, corpus):
    """Each article belongs to exactly one track and exactly one stage."""
    tracks, _ = classified
    seen = {}
    for track in tracks:
        for stage in track["stages"]:
            for post in stage["posts"]:
                key = post["rel"]
                assert key not in seen, (
                    "{} 同时落进了 {} 和 {}".format(
                        key, seen.get(key), "{}/{}".format(track["id"], stage["id"])
                    )
                )
                seen[key] = "{}/{}".format(track["id"], stage["id"])
    assert len(seen) == len(corpus), (
        "有文章一次都没落进去：语料 {} 篇，归类 {} 篇".format(len(corpus), len(seen))
    )


def test_every_stage_has_articles(classified):
    """An empty stage is a hole in the curriculum -- remove it instead.

    An empty stage still shows up in the overview table with "0 篇",
    which reads like "there's nothing here yet" rather than "this stage
    doesn't exist".
    """
    tracks, _ = classified
    empty = [
        "{}/{}".format(t["id"], s["id"])
        for t in tracks for s in t["stages"]
        if not s["posts"]
    ]
    assert not empty, "这些阶段一篇都没有：{}".format(", ".join(empty))


def test_no_article_relies_on_the_fallback_stage(classified):
    """Every article needs a rule of its own.

    The fallback stage (``fallback_stage``) exists so the tool doesn't
    crash on a new article -- it is **not** a place to put articles that
    nobody bothered to classify.  An article that lands there was
    silently dropped into "扩展与杂项", which is exactly the failure
    this whole exercise is meant to remove.

    So: add a rule.  The fallback absorbs nothing.
    """
    tracks, _ = classified
    via_fallback = []
    for track in tracks:
        for stage in track["stages"]:
            for rel in stage.get("fallback_posts", []):
                via_fallback.append("{}/{} ← {}".format(
                    track["id"], stage["id"], rel))
    assert not via_fallback, (
        "这些文章没有专属规则，是靠兜底阶段混进来的：\n"
        + "\n".join("  " + line for line in via_fallback)
        + "\n给它们写规则（data/learning-path.json）。"
    )


# --------------------------------------------------------------- 2. 渲染


def test_every_article_appears_exactly_once_in_the_rendered_pages(tool, rules,
                                                                 corpus, classified):
    """The rendered track pages list every article exactly once.

    Coverage in the classifier is not enough: a renderer that drops a
    post (or prints it twice) would still pass the classifier's checks
    while the page a reader sees is wrong.
    """
    tracks, _ = classified
    rendered = []
    for track in tracks:
        rendered.append(tool.render_track(track))
    body = "\n".join(rendered)

    listed = re.findall(r"^- \[[^\]]*\]\(([^)]*)\)", body, re.M)
    assert len(listed) == len(corpus), (
        "赛道页里列了 {} 篇文章，语料是 {} 篇".format(len(listed), len(corpus))
    )
    assert len(set(listed)) == len(listed), "赛道页里有文章被列了不止一次"
    assert set(listed) == {p["url"] for p in corpus}


def test_the_overview_page_lists_every_track(tool, rules, classified):
    """The overview must point at every track -- that's the whole point
    of having an overview."""
    tracks, _ = classified
    overview = tool.render_overview(tracks, sum(t["count"] for t in tracks))
    for track in tracks:
        assert "/learning/{}/".format(track["id"]) in overview, (
            "总览页里没有 {} 这条赛道".format(track["id"])
        )


# --------------------------------------------------------------- 3. 规则文件


def test_the_rules_file_is_well_formed(rules):
    """Track ids and stage ids are unique, stages are ordered, and every
    ``fallback_stage`` points at a stage that exists."""
    assert rules["version"] >= 1
    tracks = rules["tracks"]
    assert len(tracks) >= 2, "赛道太少，学习路径没意义"

    track_ids = [t["id"] for t in tracks]
    assert len(set(track_ids)) == len(track_ids), "赛道 id 有重复：{}".format(track_ids)

    for track in tracks:
        assert track["title"], "赛道 {} 没有标题".format(track["id"])
        assert track["summary"], "赛道 {} 没有一句话简介".format(track["id"])
        assert track["goal"], "赛道 {} 没有「读完能做什么」".format(track["id"])
        assert track["stages"], "赛道 {} 一个阶段都没有".format(track["id"])

        stage_ids = [s["id"] for s in track["stages"]]
        assert len(set(stage_ids)) == len(stage_ids), (
            "赛道 {} 的阶段 id 有重复：{}".format(track["id"], stage_ids)
        )
        assert stage_ids == sorted(stage_ids), (
            "赛道 {} 的阶段没按顺序排：{}".format(track["id"], stage_ids)
        )

        fallback = track.get("fallback_stage")
        assert fallback in stage_ids, (
            "赛道 {} 的 fallback_stage 指向了不存在的阶段 {}".format(
                track["id"], fallback)
        )


def test_catch_all_only_in_the_last_stage(rules):
    """A ``catch_all`` rule in a non-final stage swallows the later ones.

    This is not hypothetical: an ``ai-tools`` L3 catch-all ate the
    ``ai/ai_video/`` articles before L4 could claim them, and L4 came
    out empty.  The greedy assignment in ``classify()`` means the first
    stage to match takes the article -- so a catch-all must be last.
    """
    offenders = []
    for track in rules["tracks"]:
        stages = track["stages"]
        for index, stage in enumerate(stages):
            is_last = index == len(stages) - 1
            for rule in stage.get("match", []):
                if rule.get("catch_all") and not is_last:
                    offenders.append(
                        "{}/{}".format(track["id"], stage["id"])
                    )
    assert not offenders, (
        "catch_all 只允许出现在最后一个阶段（中间阶段会把后面阶段的文章全吞掉）："
        "{}".format(", ".join(offenders))
    )


def test_the_rules_only_use_matchers_the_tool_implements(rules):
    """A rule key the matcher doesn't know about is a rule that never
    fires -- it looks like coverage but isn't."""
    known = {"path_prefix", "path_regex", "path_exact", "category", "tag",
             "title_contains", "any", "all", "catch_all"}
    unknown = []

    def walk(rules_, where):
        for rule in rules_ or []:
            for key in rule:
                if key not in known:
                    unknown.append("{}: {}".format(where, key))
            for key in ("any", "all"):
                if key in rule:
                    walk(rule[key], where)

    for track in rules["tracks"]:
        walk(track.get("track_match"), track["id"])
        for stage in track["stages"]:
            walk(stage.get("match"), "{}/{}".format(track["id"], stage["id"]))
    assert not unknown, "规则里有匹配器不认识的键：{}".format(", ".join(unknown))


# --------------------------------------------------------------- 4. 挂载点前缀


def test_internal_links_carry_the_site_root(tool, rules, corpus, classified):
    """Links written into the pages must carry the mount point.

    The same build is published at ``/`` and at ``/blog/``.  A link
    written as ``/learning/`` is dead on the mirror.  Every internal
    link goes through ``site_root.rooted_path()``; this test simulates
    the mirror and checks that nothing slipped through.
    """
    tracks, _ = classified
    # 文章链接是语料带来的（真 permalink 由 site_root.permalink 加前缀），
    # 这里要查的是**页面自己写出来的**那些链接 —— 把文章链接抹掉，
    # 剩下的就只有渲染器发的。
    tracks = copy.deepcopy(tracks)
    for track in tracks:
        for stage in track["stages"]:
            for post in stage["posts"]:
                post["url"] = ""

    config_path = str(REPO_ROOT / "_config.yml")
    cached = site_root._ROOT_CACHE.get(config_path)
    site_root._ROOT_CACHE[config_path] = "/blog"
    try:
        overview = tool.render_overview(tracks, len(corpus))
        body = "\n".join(tool.render_track(t) for t in tracks)
    finally:
        if cached is None:
            site_root._ROOT_CACHE.pop(config_path, None)
        else:
            site_root._ROOT_CACHE[config_path] = cached

    for text in (overview, body):
        links = re.findall(r"\]\((/[^)]*)\)", text)
        assert links, "页面里一条站内链接都没有 —— 渲染器没写链接？"
        for link in links:
            assert link.startswith("/blog/"), (
                "站内链接没带挂载点前缀，镜像站上会 404：{}".format(link)
            )


# --------------------------------------------------------------- 5. 接线


def test_the_theme_has_a_learning_layout():
    """``layout: learning`` needs a layout of that name.

    Hexo falls back to ``post.ejs`` when a page's layout file is
    missing -- and ``post.ejs`` brings a date, categories, word count
    and prev/next, none of which mean anything for an index page.
    """
    assert THEME_LAYOUT.is_file(), "缺 {}".format(THEME_LAYOUT)
    text = THEME_LAYOUT.read_text(encoding="utf-8")
    assert "page.content" in text, "learning 版式没有输出正文"
    # 只看真正输出的标记：EJS 注释（<%# ... %>）里提到 <nav> 不算。
    markup = re.sub(r"<%#.*?%>", "", text, flags=re.S)
    assert "<nav" not in markup, (
        "版式里用了 <nav>：Materialize 按元素名给 nav 上样式，会压成一条红条"
    )


def test_the_homepage_links_to_the_learning_path():
    """首页要有通往学习路径的入口。

    2026-11-18：这条入口原来在首屏那块「从这里开始」按钮上。它退休了 ——
    首页要做成正好一屏，那块按钮的 47px 让给下面的学习路径面板，而它指的
    `/learning/` 就是那个面板本身（八张赛道卡 + 「看完整的学习地图」）：
    同一个去处在首屏摆两遍没有意义。入口现在住在面板的标题行里。

    2026-11-19：连首屏那块都没了（那句定位搬进了顶部导航栏），所以
    首页正文里不该再有第二个 ``/learning/`` 入口。
    """
    panel = HOME_PANEL.read_text(encoding="utf-8")
    assert "/learning/" in panel, "首页没有指向 /learning/ 的入口"
    assert "site.data.learning" in panel, (
        "首页入口的赛道数/文章数应当取自生成的数据，不写死在模板里"
    )
    assert not HOME_HERO.exists(), (
        "首屏那块已经退休了 —— 定位句搬进了导航栏"
    )
    home_content = HOME_CONTENT.read_text(encoding="utf-8")
    # 只看真正输出的标记：EJS 注释（<%# ... %>）里提到 /learning/ 不算。
    markup = re.sub(r"<%#.*?%>", "", home_content, flags=re.S)
    assert "/learning/" not in markup, (
        "首页正文里又出现了一个 /learning/ 入口 —— 入口在下面的学习路径面板里"
    )


def test_the_homepage_panel_is_driven_by_the_generated_data():
    """首页的学习路径面板不能自己手写一份赛道清单。

    改之前的面板是模板里写死的 6 条泳道，每条挑 3 篇代表作 ——
    覆盖不了全站，而且每加一条赛道都要改模板。
    现在赛道清单来自 ``site.data.learning``：模板里不该再出现
    硬编码的泳道定义（``var lanes``、``pathPrefix``、``cats:``）。
    """
    text = HOME_PANEL.read_text(encoding="utf-8")
    assert "site.data.learning" in text, (
        "首页学习路径面板没有读 site.data.learning —— 赛道清单应该来自生成的数据"
    )
    assert "track.id" in text, (
        "首页面板的赛道链接应该由 track.id 拼出来，每条赛道链到自己那一页"
    )
    for stale in ("var lanes =", "pathPrefix", "cats:"):
        assert stale not in text, (
            "首页面板里还留着旧的硬编码泳道定义（{}）—— 改用 site.data.learning".format(stale)
        )


def test_article_titles_carry_no_yaml_escape(classified):
    """标题里不该留着 YAML 的转义反斜杠。

    front matter 是 YAML：``title: "...数据库\\"脱颖而出\\""`` 里的 ``\\"``
    只是一个转义序列，YAML 解析出来的标题是 ``…"脱颖而出"``（没有反斜杠）。
    谁要是把原文照抄进 Markdown 链接文字，末尾就多出一个孤零零的
    ``\\``，marked 解析不出这个链接 —— 整行退化成纯文本，页面上那条文章
    就点不开了（这题里就有一篇：``database-selection-dimensions``）。
    """
    tracks, _ = classified
    bad = []
    for track in tracks:
        for stage in track["stages"]:
            for post in stage["posts"]:
                if "\\" in post["title"]:
                    bad.append("{} —— {}".format(post["rel"], post["title"]))
    assert not bad, (
        "这些标题里还留着 YAML 转义的反斜杠：\n" + "\n".join("  " + b for b in bad)
    )


def test_a_yaml_escaped_title_comes_back_clean(tool):
    """标题按 YAML 解析，而不是照抄原文。

    这条针对的是**构建产物**里的标题：sync 把标题写成 YAML 双引号串，
    引号被转义成 ``\\"``。生成器读 ``source/_posts/`` 时必须用 YAML 的
    规则把它还原回来。

    顺带钉住「解标题只有一份实现」：生成器借的是 sync 的解析器，
    不是自己另写一份 ``.strip('"')``。
    """
    fm = 'title: "当我们在说\\"数据库\\"的时候 —— 从用户的视角拆解"'
    assert tool._front_matter_title(fm) == '当我们在说"数据库"的时候 —— 从用户的视角拆解'

    # 单引号串：'' 是转义的单引号
    assert tool._front_matter_title("title: 'It''s here'") == "It's here"

    # 裸标量：引号只是正文的一部分，# 之后是 YAML 注释
    assert tool._front_matter_title("title: 裸标题 # 注释") == "裸标题"

    # 末尾的转义引号不能把反斜杠留下来 —— 这就是那个「链接点不开」的坑
    assert "\\" not in tool._front_matter_title('title: "结尾有\\"引号\\""')


def test_the_rendered_article_links_are_well_formed(tool, rules, classified):
    """渲染出来的每一条文章链接都要是**一条**能解析的链接。

    链接文字以反斜杠结尾时，marked 会把 ``]`` 也吞进链接文字，
    整行变成纯文本 —— 分类器说「这篇在 L7」，页面上一条链接都没有。
    """
    tracks, _ = classified
    for track in tracks:
        for line in tool.render_track(track).splitlines():
            if not line.startswith("- ["):
                continue
            m = re.match(r"^- \[(.*)\]\(([^)]*)\)", line)
            assert m, "这条链接 marked 解析不了：{}".format(line[:120])
            assert not m.group(1).endswith("\\"), (
                "链接文字以反斜杠结尾，marked 解析不出来：{}".format(line[:120])
            )


def _unescaped_markdown_chars(text: str) -> str:
    """扫出**没被转义**的 Markdown 语法字符（跳过 ``\\x`` 这种转义序列）。"""
    found = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            i += 2
            continue
        if text[i] in "[]()`*":
            found.append(text[i])
        i += 1
    return "".join(found)


def test_a_title_containing_markdown_cannot_form_a_nested_link(tool):
    """标题里自带 Markdown 链接时，链接文字必须整体转义。

    站内有一篇的标题是 ``[kali](https://so.csdn.net/...)搭建docker``。
    原样放进链接文字，Markdown 会把里面的 ``[...]()`` 重新解析一遍，
    渲染出**嵌套的 ``<a>``** —— 那不是合法 HTML，浏览器会把里层的链接
    提出来，外层的文章链接就断了。
    """
    escaped = tool._md_escape("[kali](https://so.csdn.net/so/search?q=kali)搭建docker")
    assert not _unescaped_markdown_chars(escaped), (
        "链接文字里还有没转义的 Markdown 语法字符：{}".format(escaped)
    )


def test_no_rendered_link_text_carries_raw_markdown(tool, rules, classified):
    """渲染出来的每一条链接，链接文字里都不能有裸的 Markdown 语法字符。"""
    tracks, _ = classified
    offenders = []
    for track in tracks:
        for line in tool.render_track(track).splitlines():
            if not line.startswith("- ["):
                continue
            m = re.match(r"^- \[(.*)\]\(([^)]*)\)", line)
            if not m:
                continue
            bad = _unescaped_markdown_chars(m.group(1))
            if bad:
                offenders.append("{} —— {}".format(bad, line[:100]))
    assert not offenders, (
        "这些链接文字里有裸的 Markdown 语法字符：\n"
        + "\n".join("  " + o for o in offenders)
    )


def test_the_generated_data_describes_every_track(tool, rules, classified):
    """``source/_data/learning.json`` 是首页面板的唯一数据来源。

    它必须给每条赛道都备齐：id / 标题 / 图标 / 简介 / 文章数 / 链接，
    以及阶段清单（每条赛道的阶段数加起来 = 它的文章数）。
    首页面板照着这份数据画，缺一项首页就少一块。
    """
    tracks, _ = classified
    data = tool.build_data(tracks, sum(t["count"] for t in tracks))

    assert data["total"] == sum(t["count"] for t in tracks)
    assert len(data["tracks"]) == len(tracks)

    for entry, track in zip(data["tracks"], tracks):
        assert entry["id"] == track["id"]
        assert entry["title"] == track["title"]
        assert entry["icon"], "赛道 {} 没有图标".format(track["id"])
        assert entry["summary"], "赛道 {} 没有简介".format(track["id"])
        assert entry["count"] == track["count"]
        assert entry["url"].endswith("/learning/{}/".format(track["id"]))
        assert entry["stages"], "赛道 {} 没有阶段".format(track["id"])
        assert sum(s["count"] for s in entry["stages"]) == entry["count"], (
            "赛道 {} 的阶段文章数加起来对不上".format(track["id"])
        )


def test_the_workflow_builds_the_learning_path_in_both_jobs():
    """Both jobs must build it: the primary domain and the Pages mirror.

    It has to run *after* the content sync (it reads ``source/_posts/``)
    and *before* ``hexo generate`` (the pages have to be in the output).
    In the Pages job it must also run after the ``root:`` rewrite, or
    the links in the generated pages would be missing the ``/blog``
    prefix.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    steps = re.findall(r"- name: (.*?)\n(?:.*\n)*?\s*run: (.*?)\n", text)
    names = [name.strip() for name, _ in steps]
    assert names.count("Build learning path") == 2, (
        "两个 job（主站 + GitHub Pages）都要跑生成器，实际出现了 {} 次".format(
            names.count("Build learning path"))
    )

    for name, run in steps:
        if name.strip() != "Build learning path":
            continue
        assert "build-learning-path.py" in run


def test_the_learning_pages_are_built_after_the_content_sync():
    """Ordering: sync → video pages → learning path → hexo generate."""
    text = WORKFLOW.read_text(encoding="utf-8")
    sync_at = text.index("python3 tools/sync-hexo.py")
    learning_at = text.index("python3 tools/build-learning-path.py")
    generate_at = text.index("npx hexo generate")
    assert sync_at < learning_at < generate_at, (
        "生成器必须排在 sync 之后、hexo generate 之前"
    )
    video_at = text.index("python3 tools/build-video-pages.py")
    assert video_at < learning_at, (
        "生成器必须排在视频内容单元之后 —— 那 6 期视频也是文章，要一起归类"
    )
