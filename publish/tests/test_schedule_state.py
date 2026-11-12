"""调度状态文件与周键幂等（06 规格 §4.1、§4.2、§7.3）。

这一层的测试盯四件事：

1. **写入是原子的**——写到一半崩了不能留下半个 JSON（半个 JSON 会被读成
   「没发过」，于是同一周发两遍）；
2. **周键幂等**：同一周第二次触发被跳过（``done = true``）；
   ``done = false`` 时重跑并覆盖该周的记录；
3. **未完成的周优先重试**（§7.3），而不是直接选新的一篇；
4. **主动发布不写周键**——那是 CLI 的事，但周键这条规则要在这儿钉住。

语料与状态文件都在临时目录里——测试一个字节都不许写进仓库。
"""

from datetime import date, datetime
import json
import os
from pathlib import Path

import pytest

from publishkit.schedule import (
    ScheduleError,
    ScheduleState,
    WeekRecord,
    resolve_config,
    run_weekly,
    week_key,
)

from test_schedule import (
    DOCUMENT_TOML,
    THIS_WEEK,
    write_post,
    write_snapshot,
)

FRIDAY = datetime(2026, 11, 13, 9, 0, 3)
WEEK = "2026-W46"


def make_config(tmp_path, *, capabilities=None):
    """一份指向临时目录的配置（语料、状态、outbox 全在 tmp_path 里）。"""
    root = tmp_path / "blog"
    root.mkdir(parents=True, exist_ok=True)
    caps = tmp_path / "capabilities"
    caps.mkdir(parents=True, exist_ok=True)
    for name, text in (capabilities or {"toutiao": DOCUMENT_TOML}).items():
        (caps / "{}.toml".format(name)).write_text(text, encoding="utf-8")
    return resolve_config(repo_root=root, capabilities_dir=caps)


class RecordingPublisher:
    """假的发布动作：记下被叫了哪些次，返回自己设定的结果。"""

    def __init__(self, results=None):
        self.calls = []
        self.results = results or {}

    def __call__(self, content_id, platform):
        self.calls.append((content_id, platform))
        return self.results.get((content_id, platform), True)


# --- 状态文件 -------------------------------------------------------------


def test_a_missing_state_file_means_nothing_has_run_yet(tmp_path):
    state = ScheduleState.load(tmp_path / "schedule.json")

    assert state.records == {}
    assert state.unfinished_weeks() == []


def test_the_state_file_is_written_with_the_shape_of_the_spec(tmp_path):
    path = tmp_path / "schedule.json"
    state = ScheduleState(path)
    state.put(
        WEEK,
        WeekRecord(
            content_id="db/postgresql/demo",
            platforms=("wechat",),
            scheduled_at="2026-11-13 09:00:03",
            trigger="weekly",
            done=True,
        ),
    )

    state.save()

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {
        "2026-W46": {
            "content_id": "db/postgresql/demo",
            "platforms": ["wechat"],
            "scheduled_at": "2026-11-13 09:00:03",
            "trigger": "weekly",
            "done": True,
        }
    }


def test_the_state_file_round_trips(tmp_path):
    path = tmp_path / "schedule.json"
    state = ScheduleState(path)
    state.put(
        WEEK,
        WeekRecord("a/b", ("wechat", "toutiao"), "2026-11-13 09:00:03", "weekly", False),
    )
    state.save()

    again = ScheduleState.load(path)

    assert again.get(WEEK).content_id == "a/b"
    assert again.get(WEEK).platforms == ("wechat", "toutiao")
    assert again.get(WEEK).done is False
    assert again.unfinished_weeks() == [WEEK]


def test_a_crash_while_writing_leaves_no_half_json(tmp_path):
    """写到一半崩了不能留半个 JSON——原来的内容必须完好。

    半个 JSON 比没有更坏：读不出来的那份会被当成「没发过」，于是同一周
    发两遍。所以换名必须是原子的（``os.replace``），崩了要么还是旧内容，
    要么已经是完整的新内容。
    """
    path = tmp_path / "schedule.json"
    state = ScheduleState(path)
    state.put(WEEK, WeekRecord("a/b", ("wechat",), "2026-11-13 09:00:03", "weekly", True))
    state.save()
    original = path.read_text(encoding="utf-8")

    def boom(src, dst):
        raise OSError("磁盘满了")

    broken = ScheduleState(path)
    broken.put(WEEK, WeekRecord("c/d", ("wechat",), "2026-11-13 09:00:03", "weekly", True))

    real_replace = os.replace
    os.replace = boom
    try:
        with pytest.raises(OSError):
            broken.save()
    finally:
        os.replace = real_replace

    assert path.read_text(encoding="utf-8") == original
    # 临时文件也不能留在状态目录里。
    assert [item.name for item in tmp_path.iterdir()] == ["schedule.json"]


def test_a_corrupt_state_file_is_refused_loudly(tmp_path):
    """状态文件坏了不能当成「没发过」——那会让同一周发两遍。"""
    path = tmp_path / "schedule.json"
    path.write_text("{这不是 JSON", encoding="utf-8")

    with pytest.raises(ScheduleError):
        ScheduleState.load(path)


def test_a_state_record_with_a_wrong_field_is_refused_loudly(tmp_path):
    path = tmp_path / "schedule.json"
    path.write_text(
        json.dumps({"2026-W46": {"content_id": "a", "done": "yes"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ScheduleError):
        ScheduleState.load(path)


def test_a_state_record_with_an_unknown_field_is_refused_loudly(tmp_path):
    path = tmp_path / "schedule.json"
    path.write_text(
        json.dumps(
            {
                "2026-W46": {
                    "content_id": "a",
                    "platforms": [],
                    "scheduled_at": "x",
                    "trigger": "weekly",
                    "done": True,
                    "extra": 1,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ScheduleError):
        ScheduleState.load(path)


def test_unfinished_weeks_are_sorted_by_week_key(tmp_path):
    state = ScheduleState(tmp_path / "schedule.json")
    state.put("2026-W46", WeekRecord("a", ("wechat",), "x", "weekly", False))
    state.put("2026-W45", WeekRecord("b", ("wechat",), "x", "weekly", False))
    state.put("2026-W47", WeekRecord("c", ("wechat",), "x", "weekly", True))

    assert state.unfinished_weeks() == ["2026-W45", "2026-W46"]


# --- 周键幂等（§4.2） -----------------------------------------------------


def _corpus(tmp_path, content_id="db/demo", platforms=("toutiao",), day="2026-01-01"):
    front_matter = "title: 演示\ndate: {}\nplatforms:\n".format(day)
    for platform in platforms:
        front_matter += "  - {}\n".format(platform)
    write_post(
        tmp_path / "blog" / "source" / "_posts",
        "{}.md".format(content_id),
        front_matter,
    )


def test_the_first_run_publishes_and_writes_the_week_key(tmp_path):
    config = make_config(tmp_path)
    _corpus(tmp_path)
    publisher = RecordingPublisher()

    result = run_weekly(config, publisher=publisher, now=FRIDAY)

    assert result.action == "published"
    assert result.ok is True
    assert publisher.calls == [("db/demo", "toutiao")]
    state = ScheduleState.load(config.schedule_file)
    assert state.get(WEEK).done is True
    assert state.get(WEEK).content_id == "db/demo"


def test_the_second_run_in_the_same_week_is_skipped(tmp_path):
    """§4.2 规则 1：同一周被调度两次 → 发两篇是不能的。"""
    config = make_config(tmp_path)
    _corpus(tmp_path)
    publisher = RecordingPublisher()

    first = run_weekly(config, publisher=publisher, now=FRIDAY)
    second = run_weekly(config, publisher=publisher, now=FRIDAY)

    assert first.action == "published"
    assert second.action == "skipped"
    assert len(publisher.calls) == 1
    assert "跳过" in second.messages[0]


def test_a_week_that_did_not_finish_is_run_again(tmp_path):
    """§4.2 规则 2：存在但 ``done = false`` → 继续跑并覆盖该周的记录。"""
    config = make_config(tmp_path)
    _corpus(tmp_path)
    state = ScheduleState(config.schedule_file)
    state.put(
        WEEK,
        WeekRecord("db/demo", ("toutiao",), "2026-11-13 09:00:03", "weekly", False),
    )
    state.save()
    publisher = RecordingPublisher()

    result = run_weekly(config, publisher=publisher, now=FRIDAY)

    assert result.action != "skipped"
    assert publisher.calls == [("db/demo", "toutiao")]
    assert ScheduleState.load(config.schedule_file).get(WEEK).done is True


def test_an_unfinished_week_is_retried_before_a_new_one_is_picked(tmp_path):
    """§7.3：上次没跑完的周要**优先重试**，不是直接选新的一篇。

    所以这里备了两篇：一篇是上周没发完的，一篇是本周该发的。重试先跑，
    本周的新内容这一轮不发。
    """
    config = make_config(tmp_path)
    _corpus(tmp_path, content_id="db/old", day="2026-01-01")
    _corpus(tmp_path, content_id="db/new", day="2026-06-01")
    state = ScheduleState(config.schedule_file)
    state.put(
        "2026-W45",
        WeekRecord("db/old", ("toutiao",), "2026-11-06 09:00:03", "weekly", False),
    )
    state.save()
    publisher = RecordingPublisher()

    result = run_weekly(config, publisher=publisher, now=FRIDAY)

    assert result.action == "retry"
    assert publisher.calls == [("db/old", "toutiao")]
    assert ScheduleState.load(config.schedule_file).get("2026-W45").done is True
    # 本周没有新记录——这一轮只做重试。
    assert ScheduleState.load(config.schedule_file).get(WEEK) is None


def test_a_failed_week_stays_unfinished(tmp_path):
    """发布失败 → ``done = false``，下次跑优先重试它。"""
    config = make_config(tmp_path)
    _corpus(tmp_path)
    publisher = RecordingPublisher(results={("db/demo", "toutiao"): False})

    result = run_weekly(config, publisher=publisher, now=FRIDAY)

    assert result.ok is False
    assert ScheduleState.load(config.schedule_file).get(WEEK).done is False


def test_an_already_published_platform_is_skipped(tmp_path):
    """发布层的幂等键：重跑不会重发已成功的部分。"""
    config = make_config(tmp_path)
    _corpus(tmp_path)
    write_snapshot(config.outbox_dir, "db/demo", "toutiao", status="packaged")
    publisher = RecordingPublisher()

    result = run_weekly(config, publisher=publisher, now=FRIDAY)

    assert publisher.calls == []
    assert result.ok is True


def test_nothing_to_publish_is_stated_out_loud(tmp_path):
    """§3.3 规则 5：本周没有可发的 → 明确说，不静默成功。"""
    config = make_config(tmp_path)
    _corpus(tmp_path)
    write_snapshot(config.outbox_dir, "db/demo", "toutiao", status="packaged")
    publisher = RecordingPublisher()

    result = run_weekly(config, publisher=publisher, now=FRIDAY)

    assert result.action == "nothing"
    assert publisher.calls == []
    assert any("本周没有可发的" in message for message in result.messages)


def test_an_empty_candidate_set_is_stated_out_loud(tmp_path):
    """候选集为空（没有一篇声明 platforms）→ 明确说。"""
    config = make_config(tmp_path)
    write_post(
        tmp_path / "blog" / "source" / "_posts",
        "db/demo.md",
        "title: 演示\ndate: 2026-01-01",
    )
    publisher = RecordingPublisher()

    result = run_weekly(config, publisher=publisher, now=FRIDAY)

    assert result.action == "nothing"
    assert any("候选集是空的" in message for message in result.messages)
    assert publisher.calls == []


def test_a_dry_run_writes_nothing(tmp_path):
    """``--dry-run``：不写 outbox、不调 adapter、不写周键。"""
    config = make_config(tmp_path)
    _corpus(tmp_path)
    publisher = RecordingPublisher()

    result = run_weekly(config, publisher=publisher, now=FRIDAY, dry_run=True)

    assert result.action == "published"
    assert publisher.calls == []          # 没调 adapter
    assert not config.schedule_file.exists()   # 没写周键
    assert not config.outbox_dir.exists()      # 没写 outbox
    assert any("演练" in message for message in result.messages)


def test_a_broken_post_does_not_stop_the_run(tmp_path):
    """一篇坏了不是其余的都不发——但坏的那篇要**说出来**。"""
    config = make_config(tmp_path)
    write_post(
        tmp_path / "blog" / "source" / "_posts",
        "bad.md",
        "title: 坏的\npublish_on: 2026-02-30",
    )
    _corpus(tmp_path)
    publisher = RecordingPublisher()

    result = run_weekly(config, publisher=publisher, now=FRIDAY)

    assert publisher.calls == [("db/demo", "toutiao")]
    assert any("语料有问题" in message for message in result.messages)


def test_a_publish_on_inside_this_week_wins_over_the_oldest_one(tmp_path):
    """§3.3 规则 2：作者指定了本周发，就发它。"""
    config = make_config(tmp_path)
    _corpus(tmp_path, content_id="db/old", day="2026-01-01")
    write_post(
        tmp_path / "blog" / "source" / "_posts",
        "db/this-week.md",
        "title: 本周\ndate: 2026-01-02\npublish_on: 2026-11-12\nplatforms:\n  - toutiao",
    )
    publisher = RecordingPublisher()

    result = run_weekly(config, publisher=publisher, now=FRIDAY)

    assert result.content_id == "db/this-week"
    assert publisher.calls == [("db/this-week", "toutiao")]


def test_one_platform_failing_does_not_block_the_others(tmp_path):
    """§3.4：某个平台失败不阻塞其他平台。"""
    config = make_config(
        tmp_path,
        capabilities={
            "toutiao": DOCUMENT_TOML,
            "wechat": DOCUMENT_TOML.replace('id = "toutiao"', 'id = "wechat"'),
        },
    )
    _corpus(tmp_path, platforms=("toutiao", "wechat"))
    publisher = RecordingPublisher(results={("db/demo", "toutiao"): False})

    result = run_weekly(config, publisher=publisher, now=FRIDAY)

    assert ("db/demo", "toutiao") in publisher.calls
    assert ("db/demo", "wechat") in publisher.calls
    assert result.ok is False
