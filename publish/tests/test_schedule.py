"""调度层：候选集、选题规则、周键、配置解析、outbox 索引。

这一层的测试盯四件事：

1. **周键算得对**——尤其是跨年那一周（06 规格 §4.3）；
2. **选题规则按 §3.3 的顺序来**——``publish_on`` 优先、没有就发最久未发的、
   发过的剔除掉、一个都不剩时**明确说**「本周没有可发的」；
3. **候选集只认文档类平台**——视频平台走它们自己那套 CLI；
4. **写盘的位置全都能配**——环境变量给默认值，命令行选项覆盖环境变量。

语料是**临时造的**：``source/_posts/`` 不入库（``.gitignore`` 第 3 行
``/source/``），干净检出里它根本不存在，测试不能依赖它。
"""

from datetime import date
import json
import os
from pathlib import Path

import pytest

from publishkit import (
    PublishKitError,
)
from publishkit.schedule import (
    PUBLISHED_STATUSES,
    OutboxIndex,
    ScheduleConfigError,
    ScheduleError,
    content_id_for,
    discover_units,
    flatten_content_id,
    load_outbox_index,
    resolve_config,
    select_for_platform,
    snapshot_name,
    target_platforms,
    week_key,
    week_window,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_OUTBOX = REPO_ROOT / "publish" / "outbox"

#: 2026-11-13 是周五，属于 2026-W46（周一 2026-11-09，周日 2026-11-15）。
FRIDAY = date(2026, 11, 13)
THIS_WEEK = (date(2026, 11, 9), date(2026, 11, 15))


# --- 夹具 ----------------------------------------------------------------


def write_post(posts_dir: Path, rel: str, front_matter: str) -> Path:
    """造一篇内容单元。"""
    path = posts_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n{}\n---\n\n正文第一段。\n".format(front_matter), encoding="utf-8")
    return path


def make_unit(content_id, *, platforms=("wechat",), publish_on=None, day=None):
    """造一个内容单元（不落盘，只给选题规则用）。"""

    class _Contract:
        def __init__(self):
            self.platforms = tuple(platforms)
            self.title = content_id

    return type(
        "Unit",
        (),
        {
            "content_id": content_id,
            "contract": _Contract(),
            "publish_on": publish_on,
            "date": day,
            "platforms": tuple(platforms),
            "title": content_id,
            "sort_date": publish_on or day or date.max,
        },
    )()


def write_snapshot(outbox_dir: Path, content_id, platform, status="packaged", **extra):
    """造一条 outbox 快照（文件名按约定）。"""
    outbox_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "content_id": content_id,
        "platform": platform,
        "status": status,
        "automation": "manual",
        "title": content_id,
        "published_url": None,
        "updated_at": "2026-11-13T09:00:03+08:00",
        "reason": "测试夹具",
    }
    payload.update(extra)
    path = outbox_dir / snapshot_name(content_id, platform)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


# --- 周键（§4.3） --------------------------------------------------------


def test_week_key_is_the_iso_week_number():
    assert week_key(date(2026, 11, 13)) == "2026-W46"
    assert week_key(date(2026, 11, 9)) == "2026-W46"
    assert week_key(date(2026, 11, 15)) == "2026-W46"


def test_week_key_crosses_the_year_boundary():
    """跨年那一周属于**上一年的最后一周**。

    ISO 的年份看的是「这一周的星期四在哪一年」。2026-12-31 是星期四，
    它自己那一周（2026-12-28 至 2027-01-03）的星期四就是它自己 → 2026 年
    → 2026-W53。2027-01-01 是星期五，它那一周的星期四是 2026-12-31 →
    还是 2026 年 → 还是 2026-W53。

    **别自己写周数算法**：自己写的版本会把 2027-01-01 算成 2027-W01，
    于是「本周」和「上周」错位一周，同一周会被发两遍。
    """
    assert week_key(date(2026, 12, 31)) == "2026-W53"
    assert week_key(date(2027, 1, 1)) == "2026-W53"
    assert week_key(date(2027, 1, 3)) == "2026-W53"
    assert week_key(date(2027, 1, 4)) == "2027-W01"
    assert week_key(date(2021, 1, 1)) == "2020-W53"


def test_week_window_is_monday_to_sunday():
    monday, sunday = week_window(FRIDAY)

    assert monday == date(2026, 11, 9)
    assert sunday == date(2026, 11, 15)
    assert monday.weekday() == 0
    assert sunday.weekday() == 6


def test_week_window_crosses_the_year_boundary():
    monday, sunday = week_window(date(2027, 1, 1))

    assert monday == date(2026, 12, 28)
    assert sunday == date(2027, 1, 3)


# --- 配置（§5.4） --------------------------------------------------------


def test_config_defaults_to_the_repository_layout(tmp_path):
    """没有环境变量时：仓库根从 cwd 往上找，状态目录在 ``publish/``。"""
    root = tmp_path / "blog"
    (root / "publish" / "capabilities").mkdir(parents=True)
    (root / "source" / "_posts").mkdir(parents=True)

    config = resolve_config(repo_root=root)

    assert config.repo_root == root
    assert config.state_dir == root / "publish"
    assert config.schedule_file == root / "publish" / "schedule.json"
    assert config.outbox_dir == root / "publish" / "outbox"
    assert config.posts_dir == root / "source" / "_posts"
    assert config.capabilities_dir == root / "publish" / "capabilities"
    assert config.secrets_file == root / "weixin" / "secrets.json"


def test_config_reads_the_environment_variables(tmp_path):
    """环境变量给默认值（launchd 的 EnvironmentVariables 只能给环境变量）。"""
    env = {
        "PUBLISH_REPO": str(tmp_path / "blog"),
        "PUBLISH_SECRETS": str(tmp_path / "creds.json"),
        "PUBLISH_STATE_DIR": str(tmp_path / "state"),
    }

    config = resolve_config(environ=env)

    assert config.repo_root == tmp_path / "blog"
    assert config.secrets_file == tmp_path / "creds.json"
    assert config.state_dir == tmp_path / "state"
    assert config.schedule_file == tmp_path / "state" / "schedule.json"
    # 状态目录一改，outbox 跟着走——不是钉死在 $REPO/publish/outbox。
    assert config.outbox_dir == tmp_path / "state" / "outbox"


def test_command_line_options_override_the_environment(tmp_path):
    """命令行优先于环境变量。"""
    env = {
        "PUBLISH_REPO": str(tmp_path / "blog"),
        "PUBLISH_STATE_DIR": str(tmp_path / "state"),
    }

    config = resolve_config(
        repo_root=tmp_path / "other",
        state_dir=tmp_path / "other-state",
        outbox_dir=tmp_path / "other-outbox",
        posts_dir=tmp_path / "other-posts",
        capabilities_dir=tmp_path / "other-caps",
        schedule_file=tmp_path / "other-schedule.json",
        secrets=tmp_path / "other-secrets.json",
        environ=env,
    )

    assert config.repo_root == tmp_path / "other"
    assert config.state_dir == tmp_path / "other-state"
    assert config.outbox_dir == tmp_path / "other-outbox"
    assert config.posts_dir == tmp_path / "other-posts"
    assert config.capabilities_dir == tmp_path / "other-caps"
    assert config.schedule_file == tmp_path / "other-schedule.json"
    assert config.secrets_file == tmp_path / "other-secrets.json"


def test_repo_root_is_discovered_from_the_working_directory(tmp_path, monkeypatch):
    root = tmp_path / "blog"
    (root / "publish" / "capabilities").mkdir(parents=True)
    deep = root / "a" / "b"
    deep.mkdir(parents=True)
    monkeypatch.chdir(deep)

    config = resolve_config(environ={})

    assert config.repo_root == root


# --- 内容单元（§3.2） ----------------------------------------------------


def test_discover_units_reads_the_content_id_from_the_path(tmp_path):
    posts = tmp_path / "_posts"
    write_post(
        posts,
        "db/logical_decode/postgresql逻辑复制-DML.md",
        "title: \"逻辑复制(DML)\"\ndate: 2026-07-27 10:40:11\nplatforms:\n  - wechat",
    )

    units, errors = discover_units(posts)

    assert errors == []
    assert len(units) == 1
    assert units[0].content_id == "db/logical_decode/postgresql逻辑复制-DML"
    assert units[0].platforms == ("wechat",)
    assert units[0].date == date(2026, 7, 27)
    assert units[0].publish_on is None


def test_discover_units_reports_a_broken_post_without_stopping(tmp_path):
    """一篇坏了不是其余的都不发——但坏的那篇要**说出来**。"""
    posts = tmp_path / "_posts"
    write_post(posts, "good.md", "title: 好的一篇\ndate: 2026-07-27\nplatforms:\n  - wechat")
    write_post(posts, "bad.md", "title: 坏的一篇\npublish_on: 2026-02-30")

    units, errors = discover_units(posts)

    assert [unit.content_id for unit in units] == ["good"]
    assert len(errors) == 1
    assert "bad" in errors[0]
    assert "2026-02-30" in errors[0]


def test_discover_units_reports_a_missing_posts_dir(tmp_path):
    with pytest.raises(ScheduleConfigError):
        discover_units(tmp_path / "nope")


def test_content_id_is_the_path_without_the_suffix(tmp_path):
    assert content_id_for(tmp_path / "a" / "b.md", tmp_path) == "a/b"


# --- 选题规则（§3.3） ----------------------------------------------------


def test_a_publish_on_inside_this_week_wins():
    units = [
        make_unit("old-one", day=date(2020, 1, 1)),
        make_unit("this-week", publish_on=date(2026, 11, 10)),
    ]

    chosen, reason = select_for_platform(units, "wechat", window=THIS_WEEK)

    assert chosen.content_id == "this-week"
    assert "publish_on" in reason


def test_the_earliest_publish_on_inside_this_week_wins():
    units = [
        make_unit("later", publish_on=date(2026, 11, 12)),
        make_unit("earlier", publish_on=date(2026, 11, 10)),
    ]

    chosen, _ = select_for_platform(units, "wechat", window=THIS_WEEK)

    assert chosen.content_id == "earlier"


def test_a_tie_on_publish_on_is_broken_by_content_id():
    """并列时按 content_id 字典序——保证确定性。"""
    units = [
        make_unit("b-post", publish_on=date(2026, 11, 10)),
        make_unit("a-post", publish_on=date(2026, 11, 10)),
    ]

    chosen, _ = select_for_platform(units, "wechat", window=THIS_WEEK)

    assert chosen.content_id == "a-post"


def test_the_oldest_unpublished_one_is_chosen():
    """没有 publish_on 落在本周 → 发最久未发的。"""
    units = [
        make_unit("newer", day=date(2026, 7, 27)),
        make_unit("older", day=date(2020, 1, 1)),
        make_unit("middle", day=date(2024, 5, 5)),
    ]

    chosen, reason = select_for_platform(units, "wechat", window=THIS_WEEK)

    assert chosen.content_id == "older"
    assert "最久未发" in reason


def test_publish_on_wins_over_date_when_sorting():
    """排序键是「publish_on，缺省用 date」——有 publish_on 就按它排。

    注意这条规则的字面含义：``publish_on`` 一旦存在就**取代** ``date``，
    不取两者的较小值。所以下面这篇虽然 ``date`` 更老，仍然排在后面。
    """
    units = [
        make_unit("with-publish-on", publish_on=date(2026, 11, 1), day=date(2020, 1, 1)),
        make_unit("only-date", day=date(2026, 12, 1)),
    ]

    chosen, _ = select_for_platform(units, "wechat", window=THIS_WEEK)

    assert chosen.content_id == "with-publish-on"


def test_already_published_units_are_dropped(tmp_path):
    outbox = tmp_path / "outbox"
    write_snapshot(outbox, "older", "wechat", status="packaged")
    index = load_outbox_index(outbox)
    units = [
        make_unit("older", day=date(2020, 1, 1)),
        make_unit("newer", day=date(2026, 7, 27)),
    ]

    chosen, _ = select_for_platform(units, "wechat", window=THIS_WEEK, outbox=index)

    assert chosen.content_id == "newer"


def test_a_failed_record_is_not_treated_as_published(tmp_path):
    """失败 ≠ 已发过——失败的那篇还要能被选出来重试。"""
    outbox = tmp_path / "outbox"
    write_snapshot(outbox, "older", "wechat", status="failed")
    index = load_outbox_index(outbox)
    units = [make_unit("older", day=date(2020, 1, 1))]

    chosen, _ = select_for_platform(units, "wechat", window=THIS_WEEK, outbox=index)

    assert chosen.content_id == "older"


def test_nothing_to_publish_is_stated_out_loud(tmp_path):
    """一个都不剩 → 明确说「本周没有可发的」，不静默成功。"""
    outbox = tmp_path / "outbox"
    write_snapshot(outbox, "only-one", "wechat", status="packaged")
    index = load_outbox_index(outbox)
    units = [make_unit("only-one", day=date(2020, 1, 1))]

    chosen, reason = select_for_platform(units, "wechat", window=THIS_WEEK, outbox=index)

    assert chosen is None
    assert "本周没有可发的" in reason


def test_an_empty_candidate_set_is_stated_out_loud():
    units = [make_unit("other-platform", platforms=("toutiao",))]

    chosen, reason = select_for_platform(units, "wechat", window=THIS_WEEK)

    assert chosen is None
    assert "候选集是空的" in reason


def test_the_candidate_set_of_one_platform_does_not_leak_into_another():
    units = [
        make_unit("only-toutiao", platforms=("toutiao",), day=date(2020, 1, 1)),
        make_unit("only-wechat", platforms=("wechat",), day=date(2026, 7, 27)),
    ]

    chosen, _ = select_for_platform(units, "wechat", window=THIS_WEEK)

    assert chosen.content_id == "only-wechat"


def test_a_unit_without_any_date_still_can_be_chosen():
    """两个日期都没有时排序键也得存在——不能抛异常。"""
    units = [make_unit("no-date"), make_unit("dated", day=date(2020, 1, 1))]

    chosen, _ = select_for_platform(units, "wechat", window=THIS_WEEK)

    assert chosen.content_id == "dated"


# --- outbox 索引 ---------------------------------------------------------


def test_the_index_is_built_by_reading_the_files_not_by_computing_names(tmp_path):
    """快照是自描述的——文件名改了也照样读得出来。"""
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "随便一个名字.json").write_text(
        json.dumps(
            {"content_id": "a/b", "platform": "wechat", "status": "published"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    index = load_outbox_index(outbox)

    assert index.is_published("a/b", "wechat") is True
    assert index.get("a/b", "wechat").status == "published"


def test_the_index_reports_a_broken_snapshot(tmp_path):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "broken.json").write_text("{不是 JSON", encoding="utf-8")

    index = load_outbox_index(outbox)

    assert index.errors
    assert "broken.json" in index.errors[0]


def test_a_missing_outbox_directory_is_not_an_error(tmp_path):
    index = load_outbox_index(tmp_path / "nope")

    assert index.errors == ()
    assert index.is_published("a", "wechat") is False


def test_the_packaged_status_counts_as_already_handled():
    """``packaged`` 是「已出包待人工上传」——它也得算已发过。

    不算的话，它因为「最久未发」每周都会被选上一次，轮转队列卡在一篇上。
    """
    assert "packaged" in PUBLISHED_STATUSES
    assert "published" in PUBLISHED_STATUSES
    assert "failed" not in PUBLISHED_STATUSES
    assert "unknown" not in PUBLISHED_STATUSES


# --- outbox 文件名约定（§6.5） -------------------------------------------


def test_the_snapshot_name_flattens_the_content_id():
    assert snapshot_name("db/postgresql/demo", "toutiao") == "db-postgresql-demo__toutiao.json"
    assert snapshot_name("csn-total-ordering", "channels") == "csn-total-ordering__channels.json"


def test_the_snapshot_name_refuses_a_path_that_escapes_the_directory():
    """``.`` / ``..`` 一律拒绝——写错地方只是不整洁，删错地方是破坏。"""
    for bad in ("", "   ", ".", "..", "a/../b", "../etc/passwd", "a/./b"):
        with pytest.raises(ScheduleError):
            flatten_content_id(bad)


def test_the_snapshot_name_matches_the_files_already_in_the_repository():
    """拿仓库里现存的快照反推：按 content_id 算出来的名字 == 磁盘上的文件名。

    这条用例**遍历目录里的每一个 .json**，所以 master 上多出快照
    （``__bilibili.json`` 那批）时它自动多验几条，不用改测试。
    """
    if not REPO_OUTBOX.is_dir():
        pytest.skip("仓库里没有 publish/outbox/")

    checked = 0
    for path in sorted(REPO_OUTBOX.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        content_id = data["content_id"]
        platform = data["platform"]

        assert snapshot_name(content_id, platform) == path.name
        checked += 1

    assert checked > 0


# --- 平台（这一期只驱动文档类） -------------------------------------------


def _capability_dir(tmp_path, **tomls):
    directory = tmp_path / "capabilities"
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in tomls.items():
        (directory / "{}.toml".format(name)).write_text(text, encoding="utf-8")
    return directory


DOCUMENT_TOML = """\
id = "toutiao"
name = "头条号"
kind = "document"
automation = "manual"
review = "platform"

[adapter]
package = "toutiao"
command = ["python3", "-m", "toutiao.cli"]
"""

VIDEO_TOML = """\
id = "channels"
name = "微信视频号"
kind = "video"
automation = "manual"
review = "platform"

[adapter]
package = "channels"
command = ["python3", "-m", "channels.cli"]
"""


def test_only_document_platforms_are_driven(tmp_path):
    """视频平台走它们自己那套 CLI——不进这一期的候选集。"""
    config = resolve_config(
        repo_root=tmp_path,
        capabilities_dir=_capability_dir(tmp_path, toutiao=DOCUMENT_TOML, channels=VIDEO_TOML),
    )

    platforms = target_platforms(config)

    assert [cap.id for cap in platforms] == ["toutiao"]


def test_a_video_platform_is_refused_loudly(tmp_path):
    """点名要一个视频平台 → 报错，不静默跳过、更不假装发过了。"""
    config = resolve_config(
        repo_root=tmp_path,
        capabilities_dir=_capability_dir(tmp_path, toutiao=DOCUMENT_TOML, channels=VIDEO_TOML),
    )

    with pytest.raises(ScheduleConfigError) as error:
        target_platforms(config, "channels")

    assert "视频平台" in str(error.value)


def test_an_unknown_platform_is_refused_loudly(tmp_path):
    config = resolve_config(
        repo_root=tmp_path,
        capabilities_dir=_capability_dir(tmp_path, toutiao=DOCUMENT_TOML),
    )

    with pytest.raises(ScheduleConfigError):
        target_platforms(config, "wechat")


def test_every_schedule_error_is_a_publishkit_error():
    assert issubclass(ScheduleConfigError, ScheduleError)
    assert issubclass(ScheduleError, PublishKitError)


# --- 集成（语料 → 候选集 → 选题） -----------------------------------------


def test_the_whole_selection_flow_over_a_temporary_corpus(tmp_path):
    """从语料到选题走一遍：发现 → 读 outbox → 选题。

    语料是临时造的：``source/_posts/`` 不入库（``.gitignore`` 第 3 行
    ``/source/``），干净检出里它根本不存在，测试不能依赖它。
    """
    posts = tmp_path / "_posts"
    write_post(
        posts,
        "a/old.md",
        "title: 老的\ndate: 2020-01-01 00:00:00\nplatforms:\n  - wechat",
    )
    write_post(
        posts,
        "b/new.md",
        "title: 新的\ndate: 2026-07-27 00:00:00\nplatforms:\n  - wechat",
    )
    write_post(
        posts,
        "c/other.md",
        "title: 别的平台的\ndate: 2019-01-01 00:00:00\nplatforms:\n  - toutiao",
    )
    outbox = tmp_path / "outbox"
    write_snapshot(outbox, "a/old", "wechat", status="packaged")

    units, errors = discover_units(posts)
    index = load_outbox_index(outbox)
    chosen, reason = select_for_platform(units, "wechat", window=THIS_WEEK, outbox=index)

    assert errors == []
    assert chosen.content_id == "b/new"
    assert "最久未发" in reason


def test_the_selection_flow_over_a_configured_repository_layout(tmp_path):
    """整条链路按配置走一遍：配置 → 语料 → outbox → 选题。

    语料与 outbox 都在临时目录里——测试一个字节都不许写进仓库。
    """
    root = tmp_path / "blog"
    posts = root / "source" / "_posts"
    write_post(
        posts,
        "db/demo.md",
        "title: 演示\ndate: 2021-03-04 05:06:07\nplatforms:\n  - wechat\n  - toutiao",
    )
    outbox = root / "publish" / "outbox"
    write_snapshot(outbox, "db/demo", "toutiao", status="packaged")

    config = resolve_config(repo_root=root)
    units, errors = discover_units(config.posts_dir)
    index = load_outbox_index(config.outbox_dir)

    # toutiao 上这篇已经出包了 → 换成 wechat 选。
    chosen, _ = select_for_platform(units, "toutiao", window=THIS_WEEK, outbox=index)
    assert chosen is None

    chosen, _ = select_for_platform(units, "wechat", window=THIS_WEEK, outbox=index)
    assert chosen.content_id == "db/demo"
    assert errors == []


def test_a_corpus_where_everything_is_published_says_so(tmp_path):
    """整个候选集都发过了 → 明确说「本周没有可发的」。"""
    posts = tmp_path / "_posts"
    write_post(posts, "only.md", "title: 唯一\ndate: 2020-01-01\nplatforms:\n  - wechat")
    outbox = tmp_path / "outbox"
    write_snapshot(outbox, "only", "wechat", status="published")

    units, _errors = discover_units(posts)
    index = load_outbox_index(outbox)
    chosen, reason = select_for_platform(units, "wechat", window=THIS_WEEK, outbox=index)

    assert chosen is None
    assert "本周没有可发的" in reason
