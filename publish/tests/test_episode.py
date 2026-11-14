"""期号内容单元与落地 URL 派生。

这一层做两件事：**把「这一期」从母稿里读出来**，**从内容单元 id 派生
落地 URL**。两件事都要验到位，因为断链就出在这儿：

- 字段读不出来 → 期号区块是空的（页面照常渲染，**静默**）；
- URL 派生错了 → 链接指向一个从未存在的路径，而服务器对未知路径返回
  **200 + 首页**（软 404），探活看不出来。

所以本文件分四组测：

1. **URL 派生**（单元）——拼出来的路径长什么样；
2. **content_id 派生**（单元）——母稿怎么对应到内容单元；
3. **字段校验**（单元）——缺一个必填字段就报错，绝不静默补默认值；
4. **接缝**（集成）——真跑一遍 ``tools/sync-hexo.py``，验母稿派生的
   content_id 与**编译产物**里的内容单元 id 一致、期号字段真的到了产物。

另外有两条**漂移守卫**：期号字段的两份白名单必须一致、规格里写的钩子
字数区间必须与代码里的常量一致。
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from publishkit.contract import PASSTHROUGH_FIELDS, parse_front_matter
from publishkit.episode import (
    EPISODE_LIST_FIELDS,
    EPISODE_SCALAR_FIELDS,
    Episode,
    EpisodeError,
    EpisodeFieldError,
    content_id_for_draft,
    discover_episodes,
    episode_from_fields,
    find_episode,
    landing_url,
    read_episode,
    validate_episode_fields,
    validate_episode_series,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNC_SCRIPT = REPO_ROOT / "tools" / "sync-hexo.py"
SPEC = REPO_ROOT / "publish" / "spec" / "08-站点IP骨架.md"

#: 六期母稿 → 内容单元 id。
#:
#: 这是**回归锁**：母稿换了路径或改结构，这里要跟着改。改错的后果是
#: 落地 URL 指向另一个页面——而软 404 会让它看起来是好的。
SIX_EPISODE_DRAFTS = {
    "pg-parallel-decode": (
        "docs/database/postgresql-logical-replication-end-to-end-flow/index.md",
        "database/postgresql-logical-replication-end-to-end-flow",
    ),
    "csn-total-ordering": (
        "docs/db/opengauss-csn-total-ordering/index.md",
        "db/opengauss-csn-total-ordering",
    ),
    "wal-interleave": (
        "docs/database/postgresql-logical-replication-worker-model/index.md",
        "database/postgresql-logical-replication-worker-model",
    ),
    "parallel-apply": (
        "docs/database/postgresql-logical-replication-ddl-trigger-apply-worker/index.md",
        "database/postgresql-logical-replication-ddl-trigger-apply-worker",
    ),
    "structured-ddl": (
        "docs/database/postgresql-logical-replication-ddl-dml-ordering/index.md",
        "database/postgresql-logical-replication-ddl-dml-ordering",
    ),
    "row-lock": (
        "docs/database/postgresql-row-lock-deep-dive/index.md",
        "database/postgresql-row-lock-deep-dive",
    ),
}


# --- 工具 -------------------------------------------------------------------


def build_corpus(root: Path, drafts) -> None:
    """Write a minimal docs/ tree plus the config sync-hexo.py reads."""
    for rel, text in drafts.items():
        path = root / "docs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    # sync-hexo.py 用 _config.matery.yml 生成关于页；缺了它脚本会中断。
    shutil.copy(REPO_ROOT / "_config.matery.yml", root / "_config.matery.yml")


def run_sync(root: Path) -> None:
    """Run the repository's sync-hexo.py over the corpus in ``root``."""
    result = subprocess.run(
        [sys.executable, str(SYNC_SCRIPT)],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, "sync-hexo.py 失败：\n{}\n{}".format(
        result.stdout, result.stderr
    )


def read_post(root: Path, rel: str) -> str:
    path = root / "source" / "_posts" / rel
    assert path.is_file(), "sync-hexo.py 没有生成 {}".format(path)
    return path.read_text(encoding="utf-8")


def complete_fields(**overrides) -> dict:
    """一份**合规**的期号字段。改一项就能测一项的校验。"""
    fields = {
        "episode": "row-lock",
        "episode_no": "6",
        "series": "内核机制",
        "episode_hook": "MVCC 让读不挡写，但两个写会互相覆盖——行锁在它上面加了一层协调",
        "episode_subtitle": "aiv/字幕-行锁.md",
        "episode_duration_s": "35.172",
        "episode_license": "PostgreSQL BSD",
    }
    fields.update(overrides)
    return fields


# --- 落地 URL 派生（单元） --------------------------------------------------


def test_landing_url_derives_the_permalink():
    assert (
        landing_url("database/postgresql-row-lock-deep-dive", "2026-10-15")
        == "/2026/10/15/database/postgresql-row-lock-deep-dive/"
    )


def test_landing_url_accepts_a_full_timestamp():
    """内容单元的 date 带时刻（``sync-hexo.py`` 写的就是这个形状）。"""
    assert (
        landing_url("database/x", "2026-10-15 11:30:25")
        == "/2026/10/15/database/x/"
    )


def test_landing_url_quotes_a_non_ascii_content_id():
    """中文路径要百分号编码——和站点实际发出的 URL 形态一致。"""
    assert (
        landing_url("life/aiv/人格规范", "2026-11-11 12:30:58")
        == "/2026/11/11/life/aiv/%E4%BA%BA%E6%A0%BC%E8%A7%84%E8%8C%83/"
    )


def test_landing_url_carries_the_mount_point():
    """镜像站挂在 ``/blog`` 下（``tools/site_root.py`` 的存在理由）。"""
    assert (
        landing_url("database/x", "2026-10-15", root="/blog")
        == "/blog/2026/10/15/database/x/"
    )


def test_landing_url_rejects_an_empty_content_id():
    """content_id 猜不出来时要**响亮地拒绝**，而不是给一条错的 URL。"""
    with pytest.raises(EpisodeFieldError):
        landing_url("", "2026-10-15")


def test_landing_url_rejects_a_malformed_date():
    """坏日期必须指名道姓地报出来，不能漏出裸 ValueError。"""
    with pytest.raises(Exception) as excinfo:
        landing_url("database/x", "不是日期")
    assert "date" in str(excinfo.value)


def test_landing_url_matches_the_site_build_layers_permalink():
    """**兼容性锁**：契约层与站点构建层各自算一遍，结果必须逐字相同。

    契约层不许 import ``tools/site_root.py``（两层之间不互相依赖，
    契约一 §11.1），所以等价性靠**这条测试**钉住——两边各自演进，
    漂了这里就红。

    ``site_root.permalink`` 收的是「日期 + 内容单元路径」，
    ``landing_url`` 收的是「内容单元 id + 日期」，两者参数顺序不同，
    拼出来的字符串必须一样。
    """
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    try:
        import site_root
    finally:
        sys.path.pop(0)

    cases = [
        ("2026-10-15 11:30:25", "database/postgresql-row-lock-deep-dive"),
        ("2026-11-11 12:30:58", "life/aiv/人格规范"),
        ("2026-08-24 14:22:40", "database/postgresql-logical-replication-worker-model"),
    ]
    for date, content_id in cases:
        assert landing_url(content_id, date) == site_root.permalink(
            date, content_id, root=""
        ), "契约层与站点构建层算出的落地 URL 不一致：{}".format(content_id)


# --- content_id 派生（单元） ------------------------------------------------


def test_content_id_for_draft_maps_index_md_to_its_own_directory():
    """``docs/<目录>/index.md`` 编译成 ``source/_posts/<目录>.md``。

    直接拿母稿路径去后缀会得到 ``.../index``——派生的落地 URL 指向一个
    **不存在**的页面。
    """
    assert (
        content_id_for_draft(
            "docs/database/postgresql-row-lock-deep-dive/index.md", "docs"
        )
        == "database/postgresql-row-lock-deep-dive"
    )


def test_content_id_for_draft_keeps_a_plain_file_as_is():
    assert content_id_for_draft("docs/blog/scheduled.md", "docs") == "blog/scheduled"


def test_content_id_for_draft_rejects_a_category_page():
    """``_index.md`` 是分类页，不是内容单元。"""
    with pytest.raises(EpisodeFieldError):
        content_id_for_draft("docs/database/_index.md", "docs")


def test_content_id_for_draft_rejects_a_file_outside_the_root():
    with pytest.raises(Exception):
        content_id_for_draft("elsewhere/x.md", "docs")


@pytest.mark.parametrize("slug", sorted(SIX_EPISODE_DRAFTS))
def test_the_six_episode_drafts_map_to_their_content_units(slug):
    """**回归锁**：六期母稿 → 内容单元 id。

    母稿换了路径或改了结构，这里要跟着改。改错的后果是落地 URL 指向
    另一个页面——而软 404 会让它看起来是好的。
    """
    draft, expected = SIX_EPISODE_DRAFTS[slug]

    assert content_id_for_draft(REPO_ROOT / draft, REPO_ROOT / "docs") == expected


# --- 字段校验（单元） ------------------------------------------------------


def test_validate_episode_fields_accepts_a_complete_episode():
    assert validate_episode_fields(complete_fields()) == []


def test_validate_episode_fields_accepts_a_plain_article():
    """没有 ``episode`` 键的普通文章不进期号线，也不该报错。"""
    assert validate_episode_fields({"title": "x", "platforms": ["wechat"]}) == []


def test_validate_episode_fields_rejects_a_bad_slug():
    violations = validate_episode_fields(complete_fields(episode="Row Lock"))

    assert any("episode" in v for v in violations)


def test_validate_episode_fields_rejects_a_slug_with_a_trailing_dash():
    violations = validate_episode_fields(complete_fields(episode="row-lock-"))

    assert any("episode" in v for v in violations)


def test_validate_episode_fields_requires_episode_no():
    fields = complete_fields()
    del fields["episode_no"]

    violations = validate_episode_fields(fields)

    assert any("episode_no" in v for v in violations)


def test_validate_episode_fields_rejects_a_non_integer_episode_no():
    violations = validate_episode_fields(complete_fields(episode_no="第六期"))

    assert any("episode_no" in v for v in violations)


def test_validate_episode_fields_rejects_episode_no_below_one():
    violations = validate_episode_fields(complete_fields(episode_no="0"))

    assert any("episode_no" in v for v in violations)


def test_validate_episode_fields_requires_a_hook():
    fields = complete_fields()
    del fields["episode_hook"]

    violations = validate_episode_fields(fields)

    assert any("episode_hook" in v for v in violations)


def test_validate_episode_fields_accepts_the_longest_real_hook():
    """**存量达标线**：六期实测最长的钩子是 61 字（EP04 并行解码）。

    上界取 65 就是为了让它过关——上界卡在 60 会把这一期判红，而它
    明明是仓库里真实在用的钩子。
    """
    assert validate_episode_fields(complete_fields(episode_hook="字" * 61)) == []


def test_validate_episode_fields_rejects_a_hook_over_the_limit():
    violations = validate_episode_fields(complete_fields(episode_hook="字" * 66))

    assert any("episode_hook" in v for v in violations)


def test_validate_episode_fields_rejects_a_hook_under_the_limit():
    violations = validate_episode_fields(complete_fields(episode_hook="字" * 19))

    assert any("episode_hook" in v for v in violations)


def test_validate_episode_fields_requires_a_duration():
    fields = complete_fields()
    del fields["episode_duration_s"]

    violations = validate_episode_fields(fields)

    assert any("episode_duration_s" in v for v in violations)


def test_validate_episode_fields_rejects_a_non_positive_duration():
    violations = validate_episode_fields(complete_fields(episode_duration_s="0"))

    assert any("episode_duration_s" in v for v in violations)


def test_validate_episode_fields_requires_a_license():
    """出处与许可证必填：母稿页比视频更容易越界（规格 §6.5）。"""
    fields = complete_fields()
    del fields["episode_license"]

    violations = validate_episode_fields(fields)

    assert any("episode_license" in v for v in violations)


def test_validate_episode_fields_rejects_a_non_string_list():
    violations = validate_episode_fields(complete_fields(episode_sources="不是列表"))

    assert any("episode_sources" in v for v in violations)


def test_validate_episode_fields_rejects_an_empty_list_item():
    violations = validate_episode_fields(complete_fields(episode_repro=["  "]))

    assert any("episode_repro" in v for v in violations)


def test_episode_from_fields_raises_on_a_violation():
    with pytest.raises(EpisodeFieldError):
        episode_from_fields(complete_fields(episode="Bad Slug"))


def test_episode_from_fields_keeps_the_values():
    episode = episode_from_fields(
        complete_fields(episode_sources=["a.c"], episode_repro=["make"])
    )

    assert isinstance(episode, Episode)
    assert episode.episode == "row-lock"
    assert episode.episode_no == 6
    assert episode.series == "内核机制"
    assert episode.episode_sources == ("a.c",)
    assert episode.episode_repro == ("make",)
    assert episode.episode_duration_s == 35.172
    assert episode.is_episode is True


# --- 系列一致性（单元） ----------------------------------------------------


def _episode(number, series="内核机制"):
    return episode_from_fields(complete_fields(episode_no=str(number), series=series))


def test_validate_episode_series_accepts_a_consecutive_series():
    episodes = [_episode(1), _episode(2), _episode(3)]

    assert validate_episode_series(episodes) == []


def test_validate_episode_series_rejects_duplicate_numbers():
    episodes = [_episode(1), _episode(1)]

    violations = validate_episode_series(episodes)

    assert any("重复" in v for v in violations)


def test_validate_episode_series_rejects_a_gap():
    """跳号意味着有一期没落地——观众是按期号往前数的。"""
    episodes = [_episode(1), _episode(3)]

    violations = validate_episode_series(episodes)

    assert any("不连续" in v for v in violations)


def test_validate_episode_series_ignores_articles_without_a_series():
    """没有 ``series`` 的文章不进系列一致性检查。"""
    fields = complete_fields()
    del fields["series"]
    episodes = [episode_from_fields(fields)]

    assert validate_episode_series(episodes) == []


# --- 读母稿 ----------------------------------------------------------------


def test_reading_a_draft_leaves_the_date_empty():
    """母稿的 ``date:`` 不是站点的日期。

    ``tools/sync-hexo.py`` 编译时把母稿的 ``date:`` 覆盖成 git 里最早的
    一次提交时间——站点 permalink 用的是那个值。2026-11-14 实测：六期
    母稿里**四期根本没写** ``date:``。

    所以读母稿时 ``date`` 留空：宁可让落地 URL 算不出来，也不能算出
    一个指向另一天的地址。
    """
    draft = REPO_ROOT / SIX_EPISODE_DRAFTS["row-lock"][0]

    episode = read_episode(draft, drafts_root=REPO_ROOT / "docs")

    assert episode.content_id == "database/postgresql-row-lock-deep-dive"
    assert episode.date is None


def test_reading_a_draft_refuses_to_invent_a_landing_url():
    draft = REPO_ROOT / SIX_EPISODE_DRAFTS["row-lock"][0]

    episode = read_episode(draft, drafts_root=REPO_ROOT / "docs")

    with pytest.raises(EpisodeFieldError):
        episode.landing_url()


def test_reading_a_missing_draft_says_so():
    with pytest.raises(EpisodeError):
        read_episode(REPO_ROOT / "docs/does-not-exist.md")


def test_discover_episodes_finds_nothing_in_a_tree_without_episodes(tmp_path):
    """没有 ``episode`` 键的母稿不进期号线。"""
    build_corpus(tmp_path, {"blog/plain.md": '---\ntitle: x\n---\n\n正文\n'})

    assert discover_episodes(tmp_path / "docs") == ()


def test_find_episode_returns_none_when_nothing_matches(tmp_path):
    build_corpus(tmp_path, {"blog/plain.md": '---\ntitle: x\n---\n\n正文\n'})

    assert find_episode(tmp_path / "docs", "row-lock") is None


def test_find_episode_rejects_two_drafts_claiming_the_same_slug(tmp_path):
    """两个母稿声明同一个 slug 是**身份冲突**，不是「取一个」。"""
    body = (
        "---\n"
        "title: x\n"
        "episode: row-lock\n"
        "episode_no: 6\n"
        "series: 内核机制\n"
        'episode_hook: "MVCC 让读不挡写，但两个写会互相覆盖——行锁在它上面加了一层协调"\n'
        "episode_subtitle: aiv/字幕-行锁.md\n"
        "episode_duration_s: 35.172\n"
        "episode_license: PostgreSQL BSD\n"
        "---\n\n正文\n"
    )
    build_corpus(tmp_path, {"blog/one.md": body, "blog/two.md": body})

    with pytest.raises(EpisodeFieldError):
        find_episode(tmp_path / "docs", "row-lock")


# --- 接缝：真跑一遍 sync-hexo.py（集成） ------------------------------------


EPISODE_DRAFT = """\
---
title: "带期号数据的一篇"
date: 2026-10-15 09:00:00
episode: row-lock
episode_no: 6
series: 内核机制
episode_hook: "MVCC 让读不挡写，但两个写会互相覆盖——行锁在它上面加了一层协调"
episode_subtitle: "aiv/字幕-行锁.md"
episode_duration_s: "35.172"
episode_license: "PostgreSQL BSD"
episode_sources:
  - "docs/database/postgresql-row-lock-deep-dive/index.md"
episode_repro:
  - "make -C aiv/pipeline out"
---

# 带期号数据的一篇

正文第一段。
"""


def test_the_draft_content_id_matches_the_compiled_content_unit(tmp_path):
    """**母稿 → content_id** 必须与**编译产物**里的内容单元 id 逐字相同。

    两边算法不同：母稿在 ``docs/`` 下（``index.md`` 要变成它所在的
    目录），产物在 ``source/_posts/`` 下（已经是 ``<目录>.md``）。
    算法错了，落地 URL 就指向一个不存在的页面——而服务器对未知路径
    返回 200 + 首页，**探活看不出来**。

    所以这条测试真的跑一遍 ``tools/sync-hexo.py``，把两边对上。
    """
    build_corpus(tmp_path, {"database/postgresql-row-lock-deep-dive/index.md": EPISODE_DRAFT})
    run_sync(tmp_path)

    from_draft = content_id_for_draft(
        tmp_path / "docs" / "database" / "postgresql-row-lock-deep-dive" / "index.md",
        tmp_path / "docs",
    )
    compiled = tmp_path / "source" / "_posts" / "database" / "postgresql-row-lock-deep-dive.md"

    assert compiled.is_file(), "sync-hexo.py 没有按 index.md 的规则编译"
    assert from_draft == "database/postgresql-row-lock-deep-dive"


def test_the_landing_url_is_derived_from_the_compiled_content_unit(tmp_path):
    """**母稿 → content_id → URL** 的整条链，跑在真的编译产物上。

    日期取**内容单元**的 ``date``（``sync-hexo.py`` 写进去的那个），
    不取母稿的——母稿的会被覆盖掉。
    """
    build_corpus(tmp_path, {"database/postgresql-row-lock-deep-dive/index.md": EPISODE_DRAFT})
    run_sync(tmp_path)

    post = tmp_path / "source" / "_posts" / "database" / "postgresql-row-lock-deep-dive.md"
    episode = read_episode(post, posts_root=tmp_path / "source" / "_posts")

    assert episode.content_id == "database/postgresql-row-lock-deep-dive"
    assert episode.date is not None
    assert episode.landing_url() == "/{}/{}/{}/database/postgresql-row-lock-deep-dive/".format(
        episode.date[:4], episode.date[5:7], episode.date[8:10]
    )


def test_every_episode_field_reaches_the_compiled_product(tmp_path):
    """**真文章 → 期号字段全部到达产物**。

    只改一道白名单，字段就在中途被**静默丢掉**：页面照常渲染，只是
    期号区块是空的。那正是 [00](00-架构设计.md) §2.2 记的「展示元数据
    通道是断的」那种故障。
    """
    build_corpus(tmp_path, {"blog/episode.md": EPISODE_DRAFT})
    run_sync(tmp_path)

    fields, _ = parse_front_matter(read_post(tmp_path, "blog/episode.md"))

    assert fields["episode"] == "row-lock"
    assert fields["episode_no"] == "6"
    assert fields["series"] == "内核机制"
    assert fields["episode_hook"] == (
        "MVCC 让读不挡写，但两个写会互相覆盖——行锁在它上面加了一层协调"
    )
    assert fields["episode_subtitle"] == "aiv/字幕-行锁.md"
    assert fields["episode_duration_s"] == "35.172"
    assert fields["episode_license"] == "PostgreSQL BSD"
    assert fields["episode_sources"] == [
        "docs/database/postgresql-row-lock-deep-dive/index.md"
    ]
    assert fields["episode_repro"] == ["make -C aiv/pipeline out"]


def test_the_compiled_product_satisfies_the_episode_contract(tmp_path):
    """搬过去的字段要能被契约层读懂——这不是巧合，是接缝的定义。"""
    build_corpus(tmp_path, {"blog/episode.md": EPISODE_DRAFT})
    run_sync(tmp_path)

    fields, _ = parse_front_matter(read_post(tmp_path, "blog/episode.md"))

    assert validate_episode_fields(fields) == []


def test_a_draft_without_episode_fields_is_untouched(tmp_path):
    """没写期号字段的母稿，front matter 必须与改动前逐字段一致。"""
    build_corpus(tmp_path, {"blog/plain.md": '---\ntitle: x\n---\n\n正文\n'})
    run_sync(tmp_path)

    fields, _ = parse_front_matter(read_post(tmp_path, "blog/plain.md"))

    assert set(fields) == {"title", "date", "author", "categories", "tags"}
    for field in EPISODE_SCALAR_FIELDS + EPISODE_LIST_FIELDS:
        assert field not in fields


# --- 两道白名单必须一致（漂移守卫） -----------------------------------------


def test_the_sync_script_lists_every_episode_field():
    """期号字段**逐个**出现在 ``tools/sync-hexo.py`` 的白名单里。

    这一层**不许** import 契约层（有测试盯着），所以两份清单各写一份
    字面量，一致性靠这两条测试钉住。
    """
    source = SYNC_SCRIPT.read_text(encoding="utf-8")

    for field in EPISODE_SCALAR_FIELDS + EPISODE_LIST_FIELDS:
        assert "'{}'".format(field) in source, (
            "sync-hexo.py 的白名单里没有 {}".format(field)
        )


def test_the_two_passthrough_lists_agree():
    """契约层与站点构建层的两份白名单必须是**同一组**期号字段。

    两份清单各写一份字面量（契约层不许 import 构建层，构建层也不许
    import 契约层），所以一致性靠这条测试钉住。

    整体上 ``sync`` 的清单是契约层的**子集**——``title`` 由
    ``sync-hexo.py`` 自己写（它要从正文里提标题），不需要透传。
    """
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("sync_hexo", SYNC_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)

    sync_fields = set(module.PASSTHROUGH_SCALAR_FIELDS) | set(
        module.PASSTHROUGH_LIST_FIELDS
    )
    contract_fields = set(PASSTHROUGH_FIELDS)
    episode_fields = set(EPISODE_SCALAR_FIELDS) | set(EPISODE_LIST_FIELDS)

    assert sync_fields & episode_fields == episode_fields, (
        "sync-hexo.py 少搬了期号字段：{}".format(
            sorted(episode_fields - sync_fields)
        )
    )
    assert episode_fields <= contract_fields, (
        "契约层少了期号字段：{}".format(sorted(episode_fields - contract_fields))
    )
    assert sync_fields <= contract_fields, (
        "sync-hexo.py 搬了契约层不认识的字段：{}".format(
            sorted(sync_fields - contract_fields)
        )
    )


# --- 规格漂移守卫 ----------------------------------------------------------


def _spec_section(title: str) -> str:
    """规格里某一节的正文（到下一个同级标题为止）。"""
    text = SPEC.read_text(encoding="utf-8")
    start = text.index(title)
    rest = text[start + len(title):]
    end = rest.find("\n### ")
    return rest if end == -1 else rest[:end]


def test_the_spec_hook_range_matches_the_code():
    """规格 §4.3 里写的钩子字数区间 == 代码里的常量。

    规格是**独立手写的事实源**，代码向它对齐。两边各写各的、靠这条
    守卫钉住——比从代码 import 常量当阈值强（那是自证）。
    """
    from publishkit import episode as episode_module

    section = _spec_section("### 4.3 front matter 字段表")
    match = re.search(r"`episode_hook`\s*\|\s*str\s*\|[^|]*\|\s*(\d+)~(\d+)\s*字", section)

    assert match, "规格 §4.3 里找不到 episode_hook 的字数区间"

    assert int(match.group(1)) == episode_module._HOOK_MIN_CHARS
    assert int(match.group(2)) == episode_module._HOOK_MAX_CHARS


def test_the_spec_field_table_matches_the_code():
    """规格 §4.3 的字段表 == 代码里的两个常量。

    **双向**：规格少一个字段要红，规格多一个字段也要红。
    """
    from publishkit import episode as episode_module

    section = _spec_section("### 4.3 front matter 字段表")
    table_rows = re.findall(r"^\|\s*`([a-z_]+)`\s*\|", section, re.MULTILINE)

    assert sorted(table_rows) == sorted(
        episode_module.EPISODE_SCALAR_FIELDS + episode_module.EPISODE_LIST_FIELDS
    ), "规格 §4.3 的期号字段表与代码常量不一致"


def test_the_spec_does_not_sell_a_nested_episode_media_anymore():
    """规格里不该再出现 ``episode_media``。

    嵌套的键会被两道白名单**静默丢掉**：页面照常渲染，只是期号区块
    是空的。规格与实现各留一份「嵌套版」，下一个人照着写就踩坑。
    """
    assert "episode_media" not in SPEC.read_text(encoding="utf-8")
