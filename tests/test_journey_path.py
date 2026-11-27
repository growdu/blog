"""成长路线（``/journey/``）的结构守卫。

**这条路是什么**
----------------
``/learning/`` 把全站文章排成 11 条**赛道**（按学科），但赛道是并排的，
读者还是得自己拼顺序。成长路线（``/journey/``）排的是另一根轴 ——
**我走过的顺序**：从刚工作时的语言入门，一直到今天读内核源码。

**为什么顺序要守**
-----------------
分期表 ``data/journey.json`` 是**手写**的：它引用现有阶段，不新增分类，
但「哪一期装哪些阶段」是人决定的。新加一个赛道或阶段时，它不会自动长出来 ——
漏了就得有人发现。这里守的就是那件事。

**这几条测试不依赖构建产物**
---------------------------
``source/_posts/`` 在 CI 的 ``site-guard``（不构建产物）里根本不存在。
所以这里的一切都从**仓库里的三张表**推出来：
``data/learning-path.json``（阶段表）、``data/journey.json``（分期表）、
``data/date-overrides.json``（每篇文章的固化日期）。
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RULES_FILE = REPO / "data" / "learning-path.json"
JOURNEY_FILE = REPO / "data" / "journey.json"
DATES_FILE = REPO / "data" / "date-overrides.json"
TOOL = REPO / "tools" / "build-journey.py"
LEARNING_TOOL = REPO / "tools" / "build-learning-path.py"
THEME_LAYOUT = REPO / "themes" / "matery" / "layout" / "learning.ejs"
HOME_PANEL = REPO / "themes" / "matery" / "layout" / "_partial" / "learning-path.ejs"
MATERY_CONFIG = REPO / "_config.matery.yml"
PACKAGE_JSON = REPO / "package.json"
WORKFLOW = REPO / ".github" / "workflows" / "hexo.yml"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _rules():
    return _load(RULES_FILE)


def _journey():
    return _load(JOURNEY_FILE)


def _all_stages() -> set[tuple[str, str]]:
    """规则表里的全部阶段，``(赛道 id, 阶段 id)``。"""
    out = set()
    for track in _rules()["tracks"]:
        for stage in track["stages"]:
            out.add((track["id"], stage["id"]))
    return out


def _stage_of_path(path: str) -> tuple[str, str] | None:
    """母稿路径 → 它属于哪个阶段。

    母稿路径的形状是 ``source-tracks/<赛道>/<阶段目录>/<文件名>``，
    阶段目录名就是规则表里的 ``dir``。这里按目录前缀认。
    """
    for track in _rules()["tracks"]:
        for stage in track["stages"]:
            prefix = "source-tracks/%s/%s/" % (track["id"], stage["dir"])
            if path.startswith(prefix):
                return (track["id"], stage["id"])
    return None


def _periods() -> list[dict]:
    """五期主线 + 选修，统一成一样的形状。"""
    journey = _journey()
    return list(journey["periods"]) + [journey["optional"]]


# --------------------------------------------------------------- 1. 阶段归属


def test_every_stage_belongs_to_exactly_one_period():
    """48 个阶段，每个**恰好**属于一期。

    少一个 —— 新加的阶段没人管，它就悄悄从成长路线上消失了。
    多一个 —— 同一批文章在两页里各出现一次，读者会以为有两篇。
    """
    stages = _all_stages()
    seen: dict[tuple[str, str], list[str]] = {}
    for period in _periods():
        for key in period["stages"]:
            track_id, stage_id = key.split("/", 1)
            seen.setdefault((track_id, stage_id), []).append(period["id"])

    missing = sorted(stages - set(seen))
    unknown = sorted(set(seen) - stages)
    duplicated = sorted(k for k, v in seen.items() if len(v) > 1)

    assert not missing, "有 %d 个阶段没归到任何一期：%s" % (
        len(missing), "、".join("%s/%s" % s for s in missing))
    assert not unknown, "分期引用了规则表里没有的阶段：%s" % (
        "、".join("%s/%s" % s for s in unknown))
    assert not duplicated, "有阶段被分到了不止一期：%s" % (
        "、".join("%s/%s" % s for s in duplicated))
    assert len(stages) == 48, "规则表里的阶段数变了（现在是 %d），分期表要跟着看" % len(stages)


# --------------------------------------------------------------- 2. 引用存在


def test_every_referenced_stage_exists_in_the_rules():
    """``data/journey.json`` 里引用的阶段都必须在规则表里找得到。

    这条是上一条的前置检查：写错一个阶段 id，上一条会以「阶段没归到
    任何一期」的形式报出来，但报不出「你拼错了 id」。这里把拼错单独抓住。
    """
    stages = _all_stages()
    for period in _periods():
        for key in period["stages"]:
            assert "/" in key, "分期 %s 里的 %r 不是 '<赛道>/<阶段>' 的形状" % (
                period["id"], key)
            track_id, stage_id = key.split("/", 1)
            assert (track_id, stage_id) in stages, (
                "分期 %s 引用了不存在的阶段 %s" % (period["id"], key))


# --------------------------------------------------------------- 3. 期数顺序


def test_the_main_line_has_exactly_five_periods_in_order():
    """主线恰好 5 期，id 依次 ``p1``…``p5``，顺序就是阅读顺序。

    期是**一条直线**（2026-11-27 定的方案 A）：不分岔、不许跳。
    期数一多，「第几期」这个说法就散了；id 一乱，页面链接就指错地方。
    """
    journey = _journey()
    ids = [p["id"] for p in journey["periods"]]
    assert ids == ["p1", "p2", "p3", "p4", "p5"], "主线的期 id/顺序变了：%s" % ids
    assert journey["optional"]["id"] == "optional", "选修线的 id 变了"
    # 选修线不在主线的 id 序列里 —— 它是主线之外的另一条线。
    assert "optional" not in ids


def test_every_period_says_what_it_is_for():
    """每一期都得说清楚「这一期解决什么」和「读完你能做什么」。

    没有这两句，这一页就只是一张目录，读者还是不知道自己该学什么。
    """
    for period in _periods():
        assert period.get("goal"), "分期 %s 没写 goal" % period["id"]
        assert period.get("can_do"), "分期 %s 没写 can_do" % period["id"]


# --------------------------------------------------------------- 4. 起步文章


def test_the_first_read_articles_exist_and_belong_to_their_period():
    """起步文章必须真实存在，**而且**落在本期的某个阶段里。

    存在但不属于本期 —— 那是个错：读者点进去发现跟这一期没关系。
    路径的形状跟 ``data/date-overrides.json`` 的键一致（带扩展名、
    不带 ``docs/`` 前缀），不另立一套格式。
    """
    dates = _load(DATES_FILE)
    for period in _journey()["periods"]:
        first_read = period.get("first_read") or []
        assert first_read, "分期 %s 没有起步文章" % period["id"]
        assert len(first_read) <= 2, (
            "分期 %s 给了 %d 篇起步文章 —— 起步的意义是「现在读哪篇」，"
            "给一堆等于没给" % (period["id"], len(first_read)))
        own_stages = {tuple(k.split("/", 1)) for k in period["stages"]}
        for item in first_read:
            path = item["path"]
            assert path in dates, (
                "分期 %s 的起步文章 %s 不在 data/date-overrides.json 里" % (
                    period["id"], path))
            stage = _stage_of_path(path)
            assert stage is not None, (
                "分期 %s 的起步文章 %s 不属于任何阶段" % (period["id"], path))
            assert stage in own_stages, (
                "分期 %s 的起步文章 %s 属于 %s/%s，不在本格子里" % (
                    period["id"], path, stage[0], stage[1]))
            assert item.get("why"), "分期 %s 的起步文章 %s 没写理由" % (
                period["id"], path)


# --------------------------------------------------------------- 5. 人称


def _string_literals(path: Path) -> list[str]:
    """Python 文件里的所有字符串常量（含文档字符串）。

    用 ``ast`` 而不是正则：注释里出现「作者」不算数 —— 生成器的注释
    在讲工具，不在跟读者说话。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)]


def test_the_artifact_speaks_in_the_first_person():
    """讲自己一律用「我」，不用「作者」。

    这一页讲的就是我本人从菜鸟到内核专家的过程 —— 换成第三人称，
    那条线就被抽掉了。守两处：生成器自己的文案常量，和人写的
    ``data/journey.json`` 里的 ``goal`` / ``can_do`` / ``first_read[].why``。

    **不扫生成出来的整页 Markdown** —— 文章标题里可能有「作者」两个字
    （那是别人的文章名，不是页面在自称），扫整页会误报。
    """
    for text in _string_literals(TOOL):
        assert "作者" not in text, "生成器里出现了「作者」，应当用「我」：%s" % (
            text[:60])

    journey = _journey()
    for period in _journeys_iter_text(journey):
        assert "作者" not in period, "文案里出现了「作者」，应当用「我」：%s" % period


def _journeys_iter_text(journey: dict):
    """分期表里所有**人写的**文案。"""
    for period in list(journey["periods"]) + [journey["optional"]]:
        yield period.get("goal", "")
        yield period.get("can_do", "")
        for item in period.get("first_read") or []:
            yield item.get("why", "")


# --------------------------------------------------------------- 6. 接线


def test_the_theme_layout_takes_the_crumb_from_the_front_matter():
    """``learning.ejs`` 的面包屑父级从 front matter 读。

    成长路线用的是同一个版式，它得能把父级换成「成长路线」。
    缺省仍是「学习路径 → /learning/」—— 赛道页不该被这次改动带偏。
    """
    text = THEME_LAYOUT.read_text(encoding="utf-8")
    assert "crumb_label" in text, "learning 版式的面包屑没有读 crumb_label"
    assert "crumb_path" in text, "learning 版式的面包屑没有读 crumb_path"
    assert "'/learning/'" in text, "面包屑的缺省值不该改掉 —— 赛道页还是它"


def test_the_homepage_offers_both_ways_in():
    """首页标题行里两个入口都在：按学科看、按顺序走一条路。

    两条路看的是同一批文章，排法不同。**不许新增一行** —— 首页要的是
    正好一屏，二十多条守卫盯着它。
    """
    text = HOME_PANEL.read_text(encoding="utf-8")
    row = re.search(r"<div class=\"section-title\">(.*?)</div>", text, re.S)
    assert row, "learning-path.ejs 里找不到标题行"
    block = row.group(1)
    assert "/learning/" in block, "标题行里没有按学科看的入口"
    assert "/journey/" in block, "标题行里没有按顺序走的入口"
    assert "learning-path__all-link" in block, (
        "「按学科看」不在标题行里 —— 它单独占一行，首页要多滚一屏"
    )


def test_the_menu_has_a_learning_path_entry():
    """菜单里要有「学习路径」。

    之前 ``/learning/`` 只能从首页的面板进 —— 站内没有任何一条常驻的
    路径通向它。成长路线是同一类问题：不给它一个常驻入口，就更没人看见。
    """
    text = MATERY_CONFIG.read_text(encoding="utf-8")
    menu = re.search(r"^menu:\n(.*?)(?=^\S)", text, re.S | re.M)
    assert menu, "_config.matery.yml 里找不到 menu"
    block = menu.group(1)
    assert "学习路径" in block, "菜单里没有「学习路径」"
    assert "url: /learning/" in block, "菜单里的「学习路径」没指向 /learning/"


def test_the_learning_overview_points_at_the_journey():
    """``/learning/`` 总览页要有一行链到成长路线。

    两页是**兄弟**：一个按学科查，一个按顺序走。读者从哪页进来，
    都要能在另一页找到去路 —— 不然他会以为是两批重复的文章。
    """
    text = LEARNING_TOOL.read_text(encoding="utf-8")
    assert "/journey/" in text, (
        "build-learning-path.py 生成的 /learning/ 总览页没有链到成长路线"
    )


def test_the_journey_is_built_after_the_content_sync():
    """顺序：sync → video pages → learning path → journey → hexo generate。

    成长路线读 ``source/_posts/``（真实标题、真实 permalink、真实日期），
    所以必须在 sync 之后；它引用规则表里的阶段，所以必须在 learning path
    之后；页面要进产物，所以必须在 hexo generate 之前。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count("Build journey path") == 2, (
        "两个 job 都得构建成长路线（主站 + 镜像站）")
    for name in ("Build journey path",):
        for match in re.finditer(r"- name: %s\n(.*?)(?=\n      - name:)" % name,
                                 text, re.S):
            block = match.group(1)
            assert "build-journey.py" in block, (
                "%s 这一步没跑 build-journey.py" % name)

    sync_at = text.index("python3 tools/sync-hexo.py")
    journey_at = text.index("python3 tools/build-journey.py")
    generate_at = text.index("npx hexo generate")
    assert sync_at < journey_at < generate_at, (
        "成长路线的构建位置不对：必须在 sync 之后、hexo generate 之前"
    )
    learning_at = text.index("python3 tools/build-learning-path.py")
    assert learning_at < journey_at, (
        "成长路线必须在学习路径之后构建 —— 期页引用的是规则表里的阶段"
    )


def test_the_local_sync_script_builds_the_journey_too():
    """``npm run sync`` 也要带上成长路线。

    本地跑一次同步，产物要跟 CI 一样 —— 否则本地预览的 ``/journey/``
    是上一版的。
    """
    pkg = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    sync = pkg["scripts"]["sync"]
    assert "build-journey.py" in sync, "npm run sync 没有构建成长路线"
    assert sync.index("build-learning-path.py") < sync.index("build-journey.py"), (
        "成长路线要在学习路径之后构建"
    )
