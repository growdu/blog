"""期号区块的契约测试（契约七 §4.2）。

这一层测三件事：

1. **构建工具**——``tools/build-podcast-index.py`` 从内容单元里读出期号线：
   地址是**派生**的、期号是排好序的、平台链接来自发布索引。
2. **主题装配**——期号区块的 partial 在库里、渲染位在正文之前、
   CSS 与 mermaid 适配都接上了、CI 里跑得着那两步。
3. **渲染产物**——``tools/check-episode-block.py`` 在**渲染出来的 HTML** 上
   断言区块该有的东西都在。这是唯一能证明「区块真的在」的地方：
   静态检查模板只证明模板里有那几行字，不证明页面上有那一块。

第 3 条在真实构建里由 ``.github/workflows/hexo.yml`` 的
「Verify episode blocks」那一步跑（渲染产物只在那儿才有）。
本文件用样本 HTML 单测那个检查器本身。
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"
THEME_PARTIALS = REPO_ROOT / "themes" / "matery" / "layout" / "_partial"

#: 六期母稿：期号 slug → 母稿路径（docs/ 下）。
#: 母稿是唯一真相（不变量一），期号线由它们认领。
SIX_DRAFTS = {
    "pg-parallel-decode": "docs/source-tracks/postgresql/logical-replication/postgresql-logical-replication-end-to-end-flow/index.md",
    "csn-total-ordering": "docs/source-tracks/postgresql/logical-replication/opengauss-csn-total-ordering/index.md",
    "wal-interleave": "docs/source-tracks/postgresql/logical-replication/postgresql-logical-replication-worker-model/index.md",
    "parallel-apply": "docs/source-tracks/postgresql/logical-replication/postgresql-logical-replication-ddl-trigger-apply-worker/index.md",
    "structured-ddl": "docs/source-tracks/postgresql/logical-replication/postgresql-logical-replication-ddl-dml-ordering/index.md",
    "row-lock": "docs/source-tracks/postgresql/transaction-mvcc/postgresql-row-lock-deep-dive/index.md",
}


def load_tool(name):
    """Import one of the build tools as a module.

    ``main()`` is guarded by ``if __name__ == '__main__'``, so importing
    only defines functions -- it does not rewrite ``source/``.
    """
    spec = importlib.util.spec_from_file_location(
        "tool_under_test_{}".format(name.replace("-", "_")), TOOLS / (name + ".py")
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


podcast_index = load_tool("build-podcast-index")
episode_checker = load_tool("check-episode-block")


# --- 母稿 → 内容单元（测试用的那一步） -------------------------------------


def _split_front_matter(text):
    """拆出 front matter 与正文。"""
    assert text.startswith("---\n")
    end = text.index("\n---\n", 3)
    return text[4:end], text[end + 5:]


def _content_unit_text(draft_path, date_text):
    """母稿 → 内容单元的 front matter。

    真实构建里这一步是 ``tools/sync-hexo.py`` 做的（它还处理标签、分类、
    摘要）。这里只取 front matter，够期号索引用。

    日期用测试给的固定值：真实构建里日期来自 git 提交历史（最早一次
    提交日），那不是本仓库的事实，不该由测试来断言。
    """
    text = (REPO_ROOT / draft_path).read_text(encoding="utf-8")
    front, body = _split_front_matter(text)
    lines = [
        line for line in front.split("\n") if not line.startswith("date:")
    ]
    lines.append("date: {}".format(date_text))
    return "---\n" + "\n".join(lines) + "\n---\n" + body


def _write_posts_tree(root, date_text="2026-10-15 09:00:00"):
    """在临时目录里造出六期的内容单元，外加一篇**不是期号**的普通文章。

    content_id 取母稿的路径（``docs/<分类>/<名>/index.md`` → ``<分类>/<名>``），
    与 ``sync-hexo.py`` 的编译规则一致。

    那篇普通文章是**必须的**：没有它，「只收带 episode 字段的内容单元」
    这条规则就没有被测到——六期全带字段时，筛选写错了也看不出来。
    """
    posts_dir = Path(root) / "source" / "_posts"
    for slug, draft_path in SIX_DRAFTS.items():
        content_id = Path(draft_path).relative_to("docs").with_suffix("").as_posix()
        content_id = content_id[: -len("/index")] if content_id.endswith("/index") else content_id
        target = posts_dir / (content_id + ".md")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_content_unit_text(draft_path, date_text), encoding="utf-8")

    plain = posts_dir / "database" / "not-an-episode.md"
    plain.parent.mkdir(parents=True, exist_ok=True)
    plain.write_text(
        '---\ntitle: "一篇普通文章"\ndate: {}\n---\n\n正文。\n'.format(date_text),
        encoding="utf-8",
    )

    # 视频内容单元（``tools/build-video-pages.py`` 的产物）：它的日期来自
    # 口播稿（``aiv/字幕-*.md``）的 front matter——母稿里的
    # ``episode_subtitle`` 指明了是哪一份。
    for slug, draft_path in SIX_DRAFTS.items():
        draft_text = (REPO_ROOT / draft_path).read_text(encoding="utf-8")
        subtitle_rel = ""
        for line in draft_text.split("\n"):
            if line.startswith("episode_subtitle:"):
                subtitle_rel = line.split(":", 1)[1].strip()
                break
        if not subtitle_rel:
            continue
        subtitle_file = REPO_ROOT / subtitle_rel
        if not subtitle_file.is_file():
            continue
        subtitle_text = subtitle_file.read_text(encoding="utf-8")
        subtitle_date = ""
        for line in subtitle_text.split("\n"):
            if line.startswith("date:"):
                subtitle_date = line.split(":", 1)[1].strip()
                break
        video = posts_dir / "video" / (slug + ".md")
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_text(
            '---\ntitle: "口播稿"\ndate: {}\nkind: video\n---\n'.format(subtitle_date),
            encoding="utf-8",
        )
    return posts_dir


def _write_publish_index(root, videos):
    data_dir = Path(root) / "source" / "_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "publish_index.json"
    path.write_text(json.dumps({"videos": videos}, ensure_ascii=False), encoding="utf-8")
    return path


def _default_videos():
    """六期视频在发布索引里的样子。

    真实构建里 ``build-publish-index.py`` 会把每个视频内容单元都收进
    ``videos``（地址来自内容单元，平台来自 outbox 快照）。这里照着做，
    免得测试里「视频页不存在」成了默认状态——那是个特例，不是常态。
    """
    videos = {}
    for slug, draft_path in SIX_DRAFTS.items():
        draft_text = (REPO_ROOT / draft_path).read_text(encoding="utf-8")
        subtitle_rel = ""
        for line in draft_text.split("\n"):
            if line.startswith("episode_subtitle:"):
                subtitle_rel = line.split(":", 1)[1].strip()
                break
        subtitle_date = ""
        subtitle_file = REPO_ROOT / subtitle_rel
        if subtitle_file.is_file():
            for line in subtitle_file.read_text(encoding="utf-8").split("\n"):
                if line.startswith("date:"):
                    subtitle_date = line.split(":", 1)[1].strip()
                    break
        videos["video/" + slug] = {
            "content_id": "video/" + slug,
            "kind": "video",
            "title": "一期口播稿",
            "url": "/{}/{}/{}/video/{}/".format(
                subtitle_date[:4], subtitle_date[5:7], subtitle_date[8:10], slug
            ),
            "platforms": [],
        }
    return videos


def _build(tmp_path, monkeypatch, videos=None, date_text="2026-10-15 09:00:00"):
    posts_dir = _write_posts_tree(tmp_path, date_text)
    _write_publish_index(
        tmp_path, _default_videos() if videos is None else videos
    )
    monkeypatch.setattr(podcast_index, "POSTS_DIR", posts_dir)
    monkeypatch.setattr(podcast_index, "PUBLISH_INDEX", posts_dir.parent / "_data" / "publish_index.json")
    return podcast_index.build_index()


# --- 1. 构建工具 -----------------------------------------------------------


def test_the_index_covers_exactly_the_six_episodes(tmp_path, monkeypatch):
    index = _build(tmp_path, monkeypatch)

    assert index["stats"]["episodes"] == 6
    assert {row["episode"] for row in index["episodes"]} == set(SIX_DRAFTS)
    assert index["series"]["name"] == "数据库内核机制"


def test_an_ordinary_article_does_not_join_the_episode_line(tmp_path, monkeypatch):
    """只有带 ``episode`` 字段的内容单元才进期号线。

    判据是**有没有那个字段**，不是「长不长得像一期」——
    全站六百多篇文章，混进一期就是串台。
    """
    index = _build(tmp_path, monkeypatch)

    assert "database/not-an-episode" not in {
        row["content_id"] for row in index["episodes"]
    }
    assert "not-an-episode" not in {row["episode"] for row in index["episodes"]}


def test_the_episodes_are_ordered_by_episode_number(tmp_path, monkeypatch):
    index = _build(tmp_path, monkeypatch)

    numbers = [row["episode_no"] for row in index["episodes"]]
    assert numbers == sorted(numbers)
    assert numbers == [1, 2, 3, 4, 5, 6]


def test_the_landing_url_is_derived_not_copied(tmp_path, monkeypatch):
    """地址由 content_id 与内容单元的日期**派生**。

    换个日期，地址跟着变——这正是「派生」与「手写常量」的区别。
    """
    index = _build(tmp_path, monkeypatch, date_text="2026-10-15 09:00:00")
    row = next(r for r in index["episodes"] if r["episode"] == "row-lock")

    assert row["url"] == "/2026/10/15/source-tracks/postgresql/transaction-mvcc/postgresql-row-lock-deep-dive/"
    assert row["content_id"] == "source-tracks/postgresql/transaction-mvcc/postgresql-row-lock-deep-dive"

    other = _build(tmp_path / "second", monkeypatch, date_text="2027-01-02 00:00:00")
    other_row = next(r for r in other["episodes"] if r["episode"] == "row-lock")
    assert other_row["url"] == "/2027/01/02/source-tracks/postgresql/transaction-mvcc/postgresql-row-lock-deep-dive/"


def test_the_index_carries_the_drafts_own_episode_facts(tmp_path, monkeypatch):
    """钩子 / 时长 / 出处 / 源码 / 复现都来自母稿的 front matter。"""
    index = _build(tmp_path, monkeypatch)
    row = next(r for r in index["episodes"] if r["episode"] == "row-lock")

    assert row["hook"].startswith("MVCC 让读不挡写")
    assert row["duration_s"] == 35.172
    assert row["license"] == "PostgreSQL BSD"
    assert "src/backend/access/heap/heapam.c" in row["sources"]
    assert row["repro"]
    assert row["subtitle"] == "aiv/字幕-行锁.md"


def test_the_episode_label_is_padded_once_and_for_all(tmp_path, monkeypatch):
    """期号标签（EP01）在索引里定一次，主题、系列页、检查器都用它。

    三处各拼一遍「EP」+ 补零，早晚拼歪（而且 EP1 与 EP01 不是同一个字符串）。
    """
    index = _build(tmp_path, monkeypatch)

    labels = [row["episode_label"] for row in index["episodes"]]
    assert labels == ["EP01", "EP02", "EP03", "EP04", "EP05", "EP06"]


def test_the_index_carries_the_video_page_date(tmp_path, monkeypatch):
    """视频页的地址也是派生的（日期 + content_id），所以索引里要带日期。"""
    index = _build(tmp_path, monkeypatch)
    row = next(r for r in index["episodes"] if r["episode"] == "row-lock")

    assert row["video_content_id"] == "video/row-lock"
    assert row["video_date"] == "2026-11-12"


def test_the_platform_links_come_from_the_publish_index(tmp_path, monkeypatch):
    """平台链接是发布动作的产物——只从发布索引来，母稿里不抄。"""
    videos = {
        "video/row-lock": {
            "content_id": "video/row-lock",
            "kind": "video",
            "title": "两个事务改同一行，谁先谁后",
            "url": "/2026/11/12/video/row-lock/",
            "platforms": [
                {
                    "platform": "bilibili",
                    "platform_name": "哔哩哔哩",
                    "status": "published",
                    "published_url": "https://www.bilibili.com/video/BV1NBWv6qECn",
                },
                {
                    "platform": "douyin",
                    "platform_name": "douyin",
                    "status": "packaged",
                    "published_url": None,
                },
            ],
        }
    }
    index = _build(tmp_path, monkeypatch, videos=videos)
    row = next(r for r in index["episodes"] if r["episode"] == "row-lock")

    assert row["title"] == "两个事务改同一行，谁先谁后"
    assert row["video_url"] == "/2026/11/12/video/row-lock/"
    assert [item["published_url"] for item in row["platforms"] if item["published_url"]] == [
        "https://www.bilibili.com/video/BV1NBWv6qECn"
    ]
    # 没发出去的平台也在，但 published_url 是空的——区块据此不给它链接。
    assert row["platforms"][1]["published_url"] is None
    assert index["stats"]["published_links"] == 1


def test_the_platform_label_is_human_readable(tmp_path, monkeypatch):
    """区块里说「在 B站看」，不是「在哔哩哔哩看」。"""
    videos = {
        "video/row-lock": {
            "url": "/2026/11/12/video/row-lock/",
            "platforms": [
                {
                    "platform": "bilibili",
                    "platform_name": "哔哩哔哩",
                    "published_url": "https://www.bilibili.com/video/BV1",
                }
            ],
        }
    }
    index = _build(tmp_path, monkeypatch, videos=videos)
    row = next(r for r in index["episodes"] if r["episode"] == "row-lock")

    assert row["platforms"][0]["label"] == "B站"


def test_an_episode_without_a_video_page_is_reported(tmp_path, monkeypatch):
    """没有视频页要报出来，不能悄悄当成「有视频」。"""
    index = _build(tmp_path, monkeypatch, videos={})

    assert set(index["stats"]["missing_video_page"]) == set(SIX_DRAFTS)
    assert index["episodes"][0]["video_url"] == ""


# --- 2. 主题装配 -----------------------------------------------------------


def test_the_episode_block_partial_is_in_the_repo():
    """partial 是**入库**的（不是构建期生成的）。"""
    path = THEME_PARTIALS / "episode-block.ejs"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "site.data.podcast_index" in text
    assert "player.bilibili.com" in text
    # 判据是**确切的标记**（class 名连着引号），不是子串——
    # "episode-sources" 是 "episode-sources-x" 的子串，只查子串等于没查。
    assert '<ul class="episode-sources">' in text
    assert '<pre class="episode-repro">' in text
    assert 'class="episode-nav"' in text
    assert 'class="episode-hook"' in text


def test_the_block_is_rendered_before_the_article_body():
    """D3：期号区块在正文之前。

    判据是**位置**，不是「文件里有没有那行」——include 在正文之后，
    读者看到的还是「先读文章、后见期号」。
    """
    text = (THEME_PARTIALS / "post-detail.ejs").read_text(encoding="utf-8")

    block_at = text.find("partial('_partial/episode-block'")
    body_at = text.find('id="articleContent"')
    assert block_at != -1, "post-detail.ejs 里没有 include 期号区块"
    assert body_at != -1
    assert block_at < body_at, "期号区块必须在正文容器之前"


def test_the_article_body_renders_the_content_without_the_lifted_diagram():
    """机制图搬进区块，正文里就不再重复一份。"""
    text = (THEME_PARTIALS / "post-detail.ejs").read_text(encoding="utf-8")

    assert "<%- _epContent %>" in text
    assert "<%- page.content %>" not in text


def test_the_patch_theme_injects_the_block_and_the_styles():
    """patch-theme.py 负责渲染位与样式——渲染位不能只活在主题文件里。"""
    text = (TOOLS / "patch-theme.py").read_text(encoding="utf-8")

    assert "partial('_partial/episode-block'" in text
    assert "/* EPISODE-BLOCK */" in text
    # 样式得**真的被写进 my.css**：只声明一段 CSS 而不写，页面照样没有样式。
    assert "f.write(ep_css)" in text
    # 样式得进 my.css，主题文件里没有第二份副本。
    css = (REPO_ROOT / "themes" / "matery" / "source" / "css" / "my.css").read_text(
        encoding="utf-8"
    )
    assert "/* EPISODE-BLOCK */" in css
    assert ".episode-player" in css


def test_the_mermaid_fitter_covers_the_episode_block():
    """搬出正文的那张图也要能被缩放、能点开放大。

    两处都要查：缩放的那处（querySelectorAll）与点开放大的那处（closest）。
    少改一处 = 窄屏上那张图溢出、点不开，而且没人看得出来。
    """
    text = (TOOLS / "patch-theme.py").read_text(encoding="utf-8")

    assert (
        "document.querySelectorAll('#articleContent .mermaid svg, "
        ".episode-block .mermaid svg')" in text
    )
    assert (
        "closest('#articleContent .mermaid svg, .episode-block .mermaid svg')" in text
    )


def test_the_ci_builds_the_index_and_checks_the_rendered_pages():
    """两套构建都要有那两步：先建索引，构建后查渲染产物。"""
    workflow = (REPO_ROOT / ".github" / "workflows" / "hexo.yml").read_text(
        encoding="utf-8"
    )

    assert workflow.count("python3 tools/build-podcast-index.py") == 2
    assert workflow.count("python3 tools/check-episode-block.py") == 2

    # 顺序：索引要在 patch-theme 之前（partial 渲染时读它），
    # 检查要在 hexo generate 之后（渲染产物那时候才有）。
    for build in workflow.split("- name: Build publish index")[1:]:
        assert "tools/build-podcast-index.py" in build.split("- name: Apply theme patches")[0]
    for build in workflow.split("npx hexo generate")[1:]:
        assert "tools/check-episode-block.py" in build


# --- 3. 渲染产物 -----------------------------------------------------------


def _episode_row(**overrides):
    row = {
        "episode": "row-lock",
        "episode_no": 6,
        "episode_label": "EP06",
        "title": "两个事务改同一行，谁先谁后",
        "hook": "MVCC 让读不挡写",
        "sources": ["src/backend/access/heap/heapam.c"],
        "repro": ["git clone https://github.com/postgres/postgres"],
        "platforms": [
            {
                "platform": "bilibili",
                "label": "B站",
                "published_url": "https://www.bilibili.com/video/BV1NBWv6qECn",
            }
        ],
        "url": "/2026/10/15/source-tracks/postgresql/transaction-mvcc/postgresql-row-lock-deep-dive/",
    }
    row.update(overrides)
    return row


def _good_page(row):
    """一份「全都对」的页面。"""
    return (
        '<div class="card episode-block">'
        "<div>{}</div>".format(row["episode_label"])
        + "<div>{}</div>".format(row["hook"])
        + '<iframe src="//player.bilibili.com/player.html?bvid=BV1NBWv6qECn"></iframe>'
        + '<a href="https://www.bilibili.com/video/BV1NBWv6qECn">在B站看</a>'
        + "<code>{}</code>".format(row["sources"][0])
        + "<pre>{}</pre>".format(row["repro"][0])
        + '<nav class="episode-nav">上一期</nav>'
        + "</div>"
    )


def test_text_is_found_whether_it_was_escaped_or_not():
    """``<%= %>`` 会转义、``<%- %>`` 不会——两种形态都算「在页面上」。

    只认一种形态，就会在换一种输出方式时误报（比如平台链接带 `&`）。
    """
    assert episode_checker.on_page("<p>a&#39;b</p>", "a'b")
    assert episode_checker.on_page("<p>a'b</p>", "a'b")
    assert not episode_checker.on_page("<p>ab</p>", "a'b")


def test_a_complete_page_passes_the_check():
    row = _episode_row()
    assert episode_checker.check_episode(_good_page(row), row, previous={"x": 1}) == []


def test_a_page_without_the_block_is_reported():
    row = _episode_row()
    problems = episode_checker.check_episode("<div>普通文章</div>", row)

    assert any("没有期号区块" in problem for problem in problems)


def test_an_unpublished_episode_has_to_say_so():
    """没发出去的期号不能空着——必须明说「还没发出去」。"""
    row = _episode_row(platforms=[])
    html = (
        '<div class="card episode-block">'
        "<div>EP06</div><div>MVCC 让读不挡写</div>"
        "<div>这一期的视频还没发出去——发出去之后这里会出现播放器。</div>"
        "<code>src/backend/access/heap/heapam.c</code>"
        "<pre>git clone https://github.com/postgres/postgres</pre>"
        '<nav class="episode-nav">上一期</nav>'
        "</div>"
    )
    assert episode_checker.check_episode(html, row) == []

    empty = html.replace("这一期的视频还没发出去——发出去之后这里会出现播放器。", "")
    problems = episode_checker.check_episode(empty, row)
    assert any("还没发出去" in problem for problem in problems)


def test_an_episode_published_only_elsewhere_says_so():
    """发到抖音了、还没发到 B 站——不能说「还没发出去」。

    说错了就是骗读者：页面上明明挂着「在抖音看」，却说视频还没发。
    """
    row = _episode_row(
        platforms=[
            {
                "platform": "douyin",
                "label": "抖音",
                "published_url": "https://www.douyin.com/video/7708359383492218122",
            }
        ]
    )
    html = (
        '<div class="card episode-block">'
        "<div>EP06</div><div>MVCC 让读不挡写</div>"
        "<div>这一期的视频还没发到 B站——发出去之后这里会出现播放器。</div>"
        '<a href="https://www.douyin.com/video/7708359383492218122">在抖音看</a>'
        "<code>src/backend/access/heap/heapam.c</code>"
        "<pre>git clone https://github.com/postgres/postgres</pre>"
        '<nav class="episode-nav">上一期</nav>'
        "</div>"
    )
    assert episode_checker.check_episode(html, row) == []

    wrong = html.replace("还没发到 B站", "还没发出去")
    problems = episode_checker.check_episode(wrong, row)
    assert any("不该说" in problem for problem in problems)


def test_a_player_for_another_episode_is_reported():
    """播放器在，但不是这一期的——数字对不上就是错了。"""
    row = _episode_row()
    html = _good_page(row).replace("BV1NBWv6qECn", "BV1OTHERxxxx")
    problems = episode_checker.check_episode(html, row)

    assert any("不是那一期" in problem for problem in problems)


def test_a_missing_source_list_is_reported():
    row = _episode_row()
    html = _good_page(row).replace("src/backend/access/heap/heapam.c", "…")
    problems = episode_checker.check_episode(html, row)

    assert any("源码路径清单" in problem for problem in problems)


def test_the_missing_source_list_is_reported_not_hidden():
    """找不到渲染产物要报出来，不能当没事。"""
    index = {"episodes": [_episode_row()]}
    problems = episode_checker.check_all(index, Path("/nonexistent-public-dir"))

    assert any("渲染产物不存在" in problem for problem in problems)


def _write_public_tree(root, row, html):
    """把一期母稿页的渲染产物摆进临时目录。"""
    target = episode_checker.page_path(root, row["url"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return target


def _write_index_file(root, row):
    path = Path(root) / "podcast_index.json"
    path.write_text(json.dumps({"episodes": [row]}, ensure_ascii=False), encoding="utf-8")
    return path


def test_the_checker_fails_the_build_when_the_block_is_missing(tmp_path):
    """命令行入口要真的以非零退出——CI 靠它拦下坏构建。"""
    row = _episode_row()
    _write_public_tree(tmp_path, row, "<div>普通文章，没有期号区块</div>")
    index_path = _write_index_file(tmp_path, row)

    assert (
        episode_checker.main(
            ["--public", str(tmp_path), "--index", str(index_path)]
        )
        == 1
    )


def test_the_checker_passes_a_good_build(tmp_path):
    row = _episode_row()
    _write_public_tree(tmp_path, row, _good_page(row))
    index_path = _write_index_file(tmp_path, row)

    assert (
        episode_checker.main(
            ["--public", str(tmp_path), "--index", str(index_path)]
        )
        == 0
    )


def test_the_checker_no_longer_looks_at_the_retired_series_page(tmp_path):
    """系列页（/videos/）2026-11-19 退休了，检查器不再看它。

    检查器要是还去查那个页面，构建一定失败 —— 页面没了，检查永远通不过。
    """
    row = _episode_row()
    _write_public_tree(tmp_path, row, _good_page(row))
    index_path = _write_index_file(tmp_path, row)

    assert (
        episode_checker.main(
            ["--public", str(tmp_path), "--index", str(index_path)]
        )
        == 0
    )


def test_the_checker_refuses_to_run_without_a_build(tmp_path):
    """没有渲染产物就说没有，不能当成「检查通过」。"""
    index_path = _write_index_file(tmp_path, _episode_row())

    assert (
        episode_checker.main(
            ["--public", str(tmp_path / "no-such-dir"), "--index", str(index_path)]
        )
        == 1
    )


# --- 4. 数据契约：partial 读的字段，索引必须真的产出 -----------------------

FIELD_RE = re.compile(r"episode(?:Now|Prev|Next)\.([A-Za-z_][A-Za-z0-9_]*)")


def test_every_field_the_partial_reads_is_produced_by_the_index(tmp_path, monkeypatch):
    """模板与数据的两份清单要一致。

    少一个字段 → 页面上那一处是空的（而且**不报错**）。
    多一个字段 → 数据里躺着一个没人用的值。
    两条都要在构建期就对上，所以这条守卫拿**工具的真实产出**比对模板。
    """
    partial = (THEME_PARTIALS / "episode-block.ejs").read_text(encoding="utf-8")
    used = set(FIELD_RE.findall(partial))

    assert used, "没能从 partial 里读出任何字段名——守卫本身失效了"

    index = _build(tmp_path, monkeypatch)
    produced = set(index["episodes"][0])
    assert used <= produced, "partial 读了索引里没有的字段：{}".format(sorted(used - produced))
