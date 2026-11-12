"""调度 CLI：命令契约、adapter 调用、失败与重试（06 规格 §7、§8）。

这一层是**集成测试**：真的起一个假 adapter（一个临时目录里的 Python
脚本），真的走一遍子进程调用。

**不依赖网络**：假 adapter 只做「按预设模式退出码 + 写一份快照」。

这一层盯住的边界：

1. ``--dry-run`` 什么也不写（不写 outbox、不调 adapter、不写周键）；
2. adapter 的退出码 1 / 2 / 3 **分别**怎么处理；
3. **超时不当失败**——超时是「结果未知」，重试可能发两遍；
4. 主动发布**不写周键**；
5. 周键幂等：同一周第二次跑被跳过；
6. 失败可重试、审核不通过与不合格**不自动重试**。
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

from publishkit.cli import EXIT_ERROR, EXIT_INELIGIBLE, EXIT_OK, EXIT_USAGE, main
from publishkit.schedule import resolve_config, snapshot_name

#: 假的 adapter：按 PLAN 里写的模式决定退出码与要不要写快照。
#:
#: 它住在 ``<仓库>/fakeadapter/fakeadapter/``，跟真的 adapter 一样是
#: 「顶层目录不是包、同名子目录才是包」——调度器把 cwd 设成
#: ``<仓库>/fakeadapter``，靠它让 ``python3 -m fakeadapter.cli`` 找得到。
FAKE_ADAPTER = '''\
"""假的 adapter：按 PLAN 里的模式退出。"""
import json
import os
import sys
import time


def main(argv):
    if not argv or argv[0] != "publish":
        print("用法：fakeadapter.cli publish <content_id>", file=sys.stderr)
        return 1

    content_id = argv[1]
    plan = {}
    plan_path = os.environ.get("FAKE_ADAPTER_PLAN")
    if plan_path and os.path.isfile(plan_path):
        with open(plan_path, encoding="utf-8") as handle:
            plan = json.load(handle)
    mode = plan.get(content_id, "ok")

    record = os.environ.get("FAKE_ADAPTER_RECORD")
    if record:
        with open(record, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "argv": list(argv),
                "cwd": os.getcwd(),
                "content_id": content_id,
            }, ensure_ascii=False) + "\\n")

    if mode == "timeout":
        time.sleep(60)

    outbox = os.environ.get("PUBLISH_OUTBOX_DIR")
    if mode in ("ok", "snapshot_then_fail") and outbox:
        os.makedirs(outbox, exist_ok=True)
        name = content_id.replace("/", "-") + "__fake.json"
        with open(os.path.join(outbox, name), "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "content_id": content_id,
                "platform": "fake",
                "status": "packaged",
                "automation": "manual",
                "title": content_id,
                "published_url": None,
                "updated_at": "2026-11-13T09:00:03+08:00",
                "reason": "假 adapter 出的包",
            }, ensure_ascii=False, indent=2, sort_keys=True))

    if mode == "usage":
        print("参数错了", file=sys.stderr)
        return 1
    if mode == "ineligible":
        print("不能发到假平台：正文没有可保留的内容", file=sys.stderr)
        return 2
    if mode == "review":
        print("平台审核不通过：publish_status=4", file=sys.stderr)
        return 3
    if mode in ("fail", "snapshot_then_fail"):
        print("平台接口报错：errcode 45009", file=sys.stderr)
        return 3

    print("发好了：{}".format(content_id))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''

CAPABILITY_TOML = """\
id = "fake"
name = "假平台"
kind = "document"
automation = "manual"
review = "platform"

[adapter]
package = "fakeadapter"
command = ['{python}', '-m', 'fakeadapter.cli']
""".format(python=sys.executable)

VIDEO_CAPABILITY_TOML = """\
id = "fakevideo"
name = "假视频平台"
kind = "video"
automation = "manual"
review = "platform"

[adapter]
package = "fakeadapter"
command = ['{python}', '-m', 'fakeadapter.cli']
""".format(python=sys.executable)


@pytest.fixture
def workspace(tmp_path):
    """一份临时仓库：语料、能力声明、假 adapter。

    全部在 ``tmp_path`` 里——测试一个字节都不许写进仓库。
    """
    root = tmp_path / "blog"
    posts = root / "source" / "_posts"
    posts.mkdir(parents=True)
    (posts / "db").mkdir(parents=True)
    (posts / "db" / "demo.md").write_text(
        "---\ntitle: 演示\ndate: 2026-01-01 00:00:00\nplatforms:\n  - fake\n---\n\n正文。\n",
        encoding="utf-8",
    )
    (posts / "db" / "other.md").write_text(
        "---\ntitle: 另一篇\ndate: 2026-02-02 00:00:00\nplatforms:\n  - fake\n---\n\n正文。\n",
        encoding="utf-8",
    )

    caps = root / "publish" / "capabilities"
    caps.mkdir(parents=True)
    (caps / "fake.toml").write_text(CAPABILITY_TOML, encoding="utf-8")
    (caps / "fakevideo.toml").write_text(VIDEO_CAPABILITY_TOML, encoding="utf-8")

    package = root / "fakeadapter" / "fakeadapter"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "cli.py").write_text(FAKE_ADAPTER, encoding="utf-8")

    plan = tmp_path / "plan.json"
    plan.write_text("{}", encoding="utf-8")
    record = tmp_path / "record.jsonl"

    monkey = pytest.MonkeyPatch()
    monkey.setenv("FAKE_ADAPTER_PLAN", str(plan))
    monkey.setenv("FAKE_ADAPTER_RECORD", str(record))

    class Workspace:
        def __init__(self, root, plan, record):
            self.root = root
            self.plan = plan
            self.record = record

        def argv(self, *args):
            return [
                "--repo-root",
                str(self.root),
                "--capabilities-dir",
                str(self.root / "publish" / "capabilities"),
                *args,
            ]

        def set_mode(self, content_id, mode):
            data = json.loads(self.plan.read_text(encoding="utf-8"))
            data[content_id] = mode
            self.plan.write_text(json.dumps(data), encoding="utf-8")

        def calls(self):
            if not self.record.exists():
                return []
            return [
                json.loads(line)
                for line in self.record.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        def outbox(self):
            return self.root / "publish" / "outbox"

        def schedule_file(self):
            return self.root / "publish" / "schedule.json"

    yield Workspace(root, plan, record)
    monkey.undo()


# --- 命令契约（§8） -------------------------------------------------------


def test_a_bad_argument_exits_with_one(workspace):
    """参数错是 1——2 在这一层是「这一篇不合格」，不能共用。"""
    with pytest.raises(SystemExit) as error:
        main(["schedule", "weekly", "--nonsense"])

    assert error.value.code == EXIT_USAGE


def test_the_dry_run_writes_nothing(workspace, capsys):
    """``--dry-run``：不写 outbox、不调 adapter、不写周键。"""
    code = main(workspace.argv("schedule", "weekly", "--dry-run"))

    assert code == EXIT_OK
    assert workspace.calls() == []
    assert not workspace.schedule_file().exists()
    assert not workspace.outbox().exists()
    assert "演练" in capsys.readouterr().out


def test_the_weekly_run_publishes_and_writes_the_week_key(workspace):
    code = main(workspace.argv("schedule", "weekly"))

    assert code == EXIT_OK
    calls = workspace.calls()
    assert len(calls) == 1
    assert calls[0]["content_id"] in ("db/demo", "db/other")

    state = json.loads(workspace.schedule_file().read_text(encoding="utf-8"))
    assert len(state) == 1
    week = list(state)[0]
    assert re.match(r"^\d{4}-W\d{2}$", week)
    assert state[week]["done"] is True
    assert state[week]["platforms"] == ["fake"]
    assert state[week]["trigger"] == "weekly"
    # adapter 自己写的快照在 outbox 里。
    written = workspace.calls()[0]["content_id"].replace("/", "-")
    assert (workspace.outbox() / (written + "__fake.json")).is_file()


def test_the_adapter_is_called_with_the_documented_contract(workspace):
    """命令是 ``<command> publish <content_id>``，cwd 是 adapter 的包目录。"""
    main(workspace.argv("schedule", "weekly"))

    call = workspace.calls()[0]
    assert call["argv"][0] == "publish"
    assert call["argv"][1] == call["content_id"]
    assert call["cwd"] == str(workspace.root / "fakeadapter")


def test_the_second_weekly_run_in_the_same_week_is_skipped(workspace):
    first = main(workspace.argv("schedule", "weekly"))
    second = main(workspace.argv("schedule", "weekly"))

    assert first == EXIT_OK
    assert second == EXIT_OK
    assert len(workspace.calls()) == 1


def test_the_candidates_command_lists_the_candidate_set(workspace, capsys):
    code = main(workspace.argv("schedule", "candidates"))

    assert code == EXIT_OK
    output = capsys.readouterr().out
    assert "db/demo" in output
    assert "db/other" in output


def test_the_status_command_shows_what_is_pending(workspace, capsys):
    main(workspace.argv("schedule", "weekly"))
    capsys.readouterr()

    code = main(workspace.argv("schedule", "status"))

    assert code == EXIT_OK
    output = capsys.readouterr().out
    assert "本周" in output
    assert "已发过" in output


# --- 主动发布（§4.2 规则 3） ---------------------------------------------


def test_the_active_publish_does_not_write_the_week_key(workspace):
    """主动发布不写周键——否则手动发一篇，周五就什么都不发了。"""
    code = main(workspace.argv("publish", "db/demo", "--platform", "fake", "--publish"))

    assert code == EXIT_OK
    assert not workspace.schedule_file().exists()
    assert len(workspace.calls()) == 1


def test_the_active_publish_without_the_flag_only_previews(workspace, capsys):
    code = main(workspace.argv("publish", "db/demo", "--platform", "fake"))

    assert code == EXIT_OK
    assert workspace.calls() == []
    assert not workspace.schedule_file().exists()
    assert "预览" in capsys.readouterr().out


def test_the_active_publish_of_an_unknown_content_is_a_config_error(workspace):
    code = main(workspace.argv("publish", "db/nope", "--platform", "fake", "--publish"))

    assert code == EXIT_USAGE


def test_the_active_publish_to_a_video_platform_is_refused(workspace):
    """视频平台走它们自己那套 CLI——点名要它们时报错。"""
    code = main(workspace.argv("publish", "db/demo", "--platform", "fakevideo", "--publish"))

    assert code == EXIT_USAGE
    assert workspace.calls() == []


# --- 失败与重试（§7） -----------------------------------------------------


def _snapshot(workspace, content_id, platform="fake"):
    path = workspace.outbox() / snapshot_name(content_id, platform)
    return json.loads(path.read_text(encoding="utf-8"))


def test_an_interface_error_is_recorded_in_the_outbox(workspace):
    """§7.1：平台接口报错 → 记进 outbox（status = failed + reason）。"""
    workspace.set_mode("db/demo", "fail")

    code = main(workspace.argv("schedule", "weekly"))

    assert code == EXIT_ERROR
    record = _snapshot(workspace, "db/demo")
    assert record["status"] == "failed"
    assert record["platform"] == "fake"
    assert record["content_id"] == "db/demo"
    assert "errcode" in record["reason"]
    assert record["updated_at"]


def test_an_ineligible_article_is_never_retried_automatically(workspace):
    """这一篇不合格（退出码 2）→ 转人工，不自动重试。"""
    workspace.set_mode("db/demo", "ineligible")

    code = main(workspace.argv("schedule", "weekly"))

    assert code == EXIT_INELIGIBLE
    record = _snapshot(workspace, "db/demo")
    assert record["status"] == "failed"
    assert record["retryable"] is False

    # 下一轮不重试它。
    before = len(workspace.calls())
    main(workspace.argv("schedule", "weekly"))
    retried = [
        call
        for call in workspace.calls()[before:]
        if call["content_id"] == "db/demo"
    ]
    assert retried == []


def test_a_review_rejection_is_never_retried_automatically(workspace):
    """平台审核不通过 → 不自动重试，转人工（§7.1 第二条）。"""
    workspace.set_mode("db/demo", "review")

    code = main(workspace.argv("schedule", "weekly"))

    assert code == EXIT_ERROR
    record = _snapshot(workspace, "db/demo")
    assert record["status"] == "failed"
    assert record["retryable"] is False
    assert "审核" in record["reason"]


def test_an_interface_error_is_retried_once_on_the_next_run(workspace):
    """§7.2：下次跑时对失败且可重试的记录重试一次。"""
    workspace.set_mode("db/demo", "fail")

    main(workspace.argv("schedule", "weekly"))
    before = len(workspace.calls())

    workspace.set_mode("db/demo", "ok")
    main(workspace.argv("schedule", "weekly"))

    retried = [
        call
        for call in workspace.calls()[before:]
        if call["content_id"] == "db/demo"
    ]
    assert len(retried) == 1


def test_a_timeout_is_not_treated_as_a_failure(workspace):
    """超时 = **结果未知**，不是失败。

    当成失败就会重试，于是可能发两遍——这是发布场景最容易翻车的地方
    （§7.1 第三条）。
    """
    workspace.set_mode("db/demo", "timeout")

    code = main(
        workspace.argv("schedule", "weekly", "--adapter-timeout", "1")
    )

    assert code == EXIT_ERROR
    record = _snapshot(workspace, "db/demo")
    assert record["status"] == "unknown"
    assert record["retryable"] is False
    assert "未知" in record["reason"]


def test_an_unknown_content_is_not_republished_after_a_timeout(workspace):
    """结果未知的那一篇不能被自动再发一次。"""
    workspace.set_mode("db/demo", "timeout")
    main(workspace.argv("schedule", "weekly", "--adapter-timeout", "1"))

    before = len(workspace.calls())
    workspace.set_mode("db/demo", "ok")
    main(workspace.argv("schedule", "weekly"))

    again = [
        call
        for call in workspace.calls()[before:]
        if call["content_id"] == "db/demo"
    ]
    assert again == []


def test_an_adapter_without_a_publish_subcommand_fails_loudly(workspace):
    """adapter 没有 ``publish`` 子命令 → 响亮地失败，不静默跳过。"""
    workspace.set_mode("db/demo", "usage")

    code = main(workspace.argv("schedule", "weekly"))

    assert code == EXIT_USAGE
    # 参数或配置错误不是发布尝试 → 不进 outbox（§7.4）。
    assert not (workspace.outbox() / snapshot_name("db/demo", "fake")).exists()


def test_the_adapters_own_snapshot_is_not_overwritten(workspace):
    """adapter 自己记过了 → 调度器不覆盖它的记录。"""
    workspace.set_mode("db/demo", "snapshot_then_fail")

    code = main(workspace.argv("schedule", "weekly"))

    assert code == EXIT_ERROR
    record = _snapshot(workspace, "db/demo")
    assert record["status"] == "packaged"
    assert record["reason"] == "假 adapter 出的包"


# --- 可配项（§5.4） -------------------------------------------------------


def test_the_environment_variables_configure_the_paths(workspace, monkeypatch):
    """环境变量给默认值（launchd 只能给环境变量）。"""
    state_dir = workspace.root / "elsewhere"
    monkeypatch.setenv("PUBLISH_REPO", str(workspace.root))
    monkeypatch.setenv("PUBLISH_STATE_DIR", str(state_dir))

    code = main(["schedule", "weekly", "--dry-run"])

    assert code == EXIT_OK


def test_the_command_line_overrides_the_environment(workspace, monkeypatch):
    monkeypatch.setenv("PUBLISH_STATE_DIR", str(workspace.root / "elsewhere"))

    code = main(
        workspace.argv(
            "--state-dir",
            str(workspace.root / "publish"),
            "schedule",
            "weekly",
        )
    )

    assert code == EXIT_OK
    assert (workspace.root / "publish" / "schedule.json").is_file()
    assert not (workspace.root / "elsewhere").exists()


def test_the_outbox_directory_follows_the_state_directory(workspace, monkeypatch):
    state_dir = workspace.root / "elsewhere"
    monkeypatch.setenv("PUBLISH_REPO", str(workspace.root))
    monkeypatch.setenv("PUBLISH_STATE_DIR", str(state_dir))

    main(["schedule", "weekly"])

    assert (state_dir / "schedule.json").is_file()
    assert (state_dir / "outbox").is_dir()


def test_the_module_entry_point_works(workspace):
    """``python3 -m publishkit.cli`` 真能跑起来。

    ``publish/`` 不是 Python 包，``publishkit`` 挂在它下面——所以要么
    ``cd publish``，要么 ``PYTHONPATH=publish``。这条用例把那条路钉住。
    """
    repo_root = Path(__file__).resolve().parents[2]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(repo_root / "publish")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "publishkit.cli",
            "schedule",
            "weekly",
            "--dry-run",
            "--repo-root",
            str(workspace.root),
            "--capabilities-dir",
            str(workspace.root / "publish" / "capabilities"),
        ],
        cwd=str(repo_root / "publish"),
        env=environment,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    assert not workspace.schedule_file().exists()
