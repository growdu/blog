"""Tests for the command line.

Three layers:

- unit tests: one situation each -- what a command prints, what exit
  code it answers with;
- integration tests: a command run end to end over a throwaway corpus
  that lives in a temporary directory;
- the two guards that keep the state file honest: a corrupt state file
  has to be announced, and a write has to be atomic.

**No test here touches the network**, and **no test here touches the
repository**: every path the commands use is pointed at a temporary
directory, and the notification is replaced by a recorder.
"""

import json

import pytest
from PIL import Image

from toutiao import cli
from toutiao import state as state_module
from toutiao.cli import EXIT_ERROR, EXIT_INELIGIBLE, EXIT_OK, EXIT_USAGE, main
from toutiao.state import PublishState, StateStore


def _site(tmp_path):
    """A throwaway site: one post with one picture."""
    site = tmp_path / "source"
    posts = site / "_posts" / "db"
    posts.mkdir(parents=True)
    image = site / "images" / "demo.png"
    image.parent.mkdir(parents=True)
    Image.new("RGB", (1200, 900), (10, 20, 30)).save(image, "PNG")
    (posts / "demo.md").write_text(
        "---\ntitle: 演示标题\ndate: 2026-01-01\n---\n\n"
        "第一段结论。\n\n"
        "![图](images/demo.png)\n\n"
        "第二段。\n",
        encoding="utf-8",
    )
    return site, posts.parent


def _args(tmp_path, command, slug=None):
    """Build a CLI argument list that never touches the repository."""
    argv = [command]
    if slug:
        argv.append(slug)
    argv += [
        "--posts-dir", str(tmp_path / "source" / "_posts"),
        "--out-dir", str(tmp_path / "out"),
        "--outbox-dir", str(tmp_path / "outbox"),
        "--state-file", str(tmp_path / "out" / "state.json"),
    ]
    return argv


def _notify_recorder(monkeypatch, error=None):
    """Replace the notification call with a recorder.

    Returns the recorded calls.  ``error`` makes the recorder fail, the
    way a platform that refuses the message would.
    """
    calls = []

    def fake_send(backend, key, subject, body, **kwargs):
        calls.append(
            {"backend": backend, "key": key, "subject": subject, "body": body}
        )
        if error is not None:
            raise error

    monkeypatch.setattr(cli, "send", fake_send)
    return calls


# --- scan ---------------------------------------------------------------


def test_scan_reports_the_corpus(tmp_path, capsys):
    _site(tmp_path)
    code = main(_args(tmp_path, "scan"))
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "演示标题" in out
    assert "1 篇" in out


def test_scan_reports_unsupported_formats(tmp_path, capsys):
    site, posts = _site(tmp_path)
    (posts / "db" / "legacy.html").write_text("<p>老文章</p>", encoding="utf-8")
    code = main(_args(tmp_path, "scan"))
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "不支持" in out
    assert "legacy.html" in out


def test_scan_reports_a_broken_post_and_exits_non_zero(tmp_path, capsys):
    """母稿坏掉（front matter 没闭合）时，scan 要干净地退出并指出是哪个文件。

    ``discover()`` 遇到未闭合的 front matter 会抛 ``ValueError``；没有这层
    兜底就是一条裸 traceback，排障时看不出是哪个文件坏了。
    """
    site, posts = _site(tmp_path)
    (posts / "db" / "broken.md").write_text(
        "---\ntitle: 坏文件\n\n正文还在\n", encoding="utf-8"
    )
    code = main(_args(tmp_path, "scan"))
    assert code != EXIT_OK
    err = capsys.readouterr().err
    assert "broken.md" in err
    # 坏掉的母稿是扫描自己的失败，不是别的命令的失败：说清楚是哪一种。
    assert "扫描失败" in err
    assert "Traceback" not in err


# --- convert ------------------------------------------------------------


def test_convert_writes_the_package(tmp_path):
    _site(tmp_path)
    code = main(_args(tmp_path, "convert", "db/demo"))
    assert code == EXIT_OK
    package = tmp_path / "out" / "db-demo"
    assert (package / "article.html").is_file()
    assert (package / "cover.webp").is_file()


def test_convert_writes_the_snapshot(tmp_path):
    _site(tmp_path)
    main(_args(tmp_path, "convert", "db/demo"))
    snapshot = tmp_path / "outbox" / "db-demo__toutiao.json"
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    assert data["status"] == "packaged"
    assert data["content_id"] == "db/demo"


def test_convert_twice_is_idempotent(tmp_path, capsys):
    _site(tmp_path)
    assert main(_args(tmp_path, "convert", "db/demo")) == EXIT_OK
    capsys.readouterr()
    assert main(_args(tmp_path, "convert", "db/demo")) == EXIT_OK
    assert "内容未变" in capsys.readouterr().out


def test_a_changed_body_is_packaged_again(tmp_path, capsys):
    """改了一个字就不能再跳过：指纹变了，这篇必须重新出包。"""
    site, posts = _site(tmp_path)
    assert main(_args(tmp_path, "convert", "db/demo")) == EXIT_OK
    capsys.readouterr()

    post = posts / "db" / "demo.md"
    post.write_text(
        post.read_text(encoding="utf-8").replace("第二段。", "第二段改了。"),
        encoding="utf-8",
    )

    assert main(_args(tmp_path, "convert", "db/demo")) == EXIT_OK
    out = capsys.readouterr().out
    assert "内容未变" not in out
    assert "发布包：" in out


def test_unknown_slug_exits_non_zero(tmp_path):
    _site(tmp_path)
    assert main(_args(tmp_path, "convert", "db/nope")) != EXIT_OK


def test_ineligible_post_exits_with_two(tmp_path, capsys):
    """不合规的那一篇要退出码 2，并且说清为什么。

    母稿只有一段代码：切片后正文里什么都不剩，没有可发的头条版。
    """
    site, posts = _site(tmp_path)
    (posts / "db" / "bad.md").write_text(
        "---\ntitle: 无内容\ndate: 2026-01-01\n---\n\n"
        "```python\nprint('hi')\n```\n",
        encoding="utf-8",
    )
    assert main(_args(tmp_path, "convert", "db/bad")) == EXIT_INELIGIBLE
    err = capsys.readouterr().err
    assert "不能发到头条号" in err


def test_convert_reports_a_broken_post(tmp_path, capsys):
    """母稿解析错误是退出码 3：接口、写盘或母稿解析错误。"""
    site, posts = _site(tmp_path)
    (posts / "db" / "broken.md").write_text(
        "---\ntitle: 坏文件\n\n正文还在\n", encoding="utf-8"
    )
    assert main(_args(tmp_path, "convert", "db/broken")) == EXIT_ERROR
    err = capsys.readouterr().err
    assert "broken.md" in err
    assert "Traceback" not in err


# --- status -------------------------------------------------------------


def test_status_lists_the_recorded_articles(tmp_path, capsys):
    _site(tmp_path)
    main(_args(tmp_path, "convert", "db/demo"))
    capsys.readouterr()

    assert main(_args(tmp_path, "status")) == EXIT_OK
    out = capsys.readouterr().out
    assert "db/demo" in out
    assert "待人工上传" in out
    # 发布包目录也在状态里：status 要能告诉人这一篇的包在哪。
    assert str(tmp_path / "out" / "db-demo") in out


def test_status_explains_that_drafted_means_waiting_for_a_human(tmp_path, capsys):
    """``drafted`` 是「草稿已在平台上，等人点发表」，不是「还没发」。

    读成「还没发」的人会把这篇重发一遍；读成「已经发了」的人会漏掉它。
    """
    state_file = tmp_path / "out" / "state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {"articles": {"db/demo": {"status": "drafted", "fingerprint": "fp"}}}
        ),
        encoding="utf-8",
    )

    assert main(_args(tmp_path, "status")) == EXIT_OK
    out = capsys.readouterr().out
    assert "待人工发表" in out
    assert "已发布" not in out


def test_status_says_nothing_was_published_when_the_state_is_empty(tmp_path, capsys):
    assert main(_args(tmp_path, "status")) == EXIT_OK
    assert "还没有发过任何文章" in capsys.readouterr().out


# --- publish ------------------------------------------------------------


def test_publish_notifies_and_does_not_claim_it_is_published(tmp_path, monkeypatch):
    """通知里必须说「待上传」：manual 档下这一篇还没发出去。"""
    _site(tmp_path)
    calls = _notify_recorder(monkeypatch)

    code = main(_args(tmp_path, "publish", "db/demo")
                + ["--notify", "serverchan", "--notify-key", "SCTKEY"])

    assert code == EXIT_OK
    assert len(calls) == 1
    assert calls[0]["backend"] == "serverchan"
    assert calls[0]["key"] == "SCTKEY"
    assert "待上传" in calls[0]["subject"]
    assert "已发布" not in calls[0]["subject"]


def test_publish_reports_a_failed_notification_without_failing_the_publish(
    tmp_path, monkeypatch, capsys
):
    """通知失败不影响发布结果 —— 但必须说出来，不能当成发成功了。"""
    _site(tmp_path)
    _notify_recorder(monkeypatch, error=RuntimeError("回执说没收到"))

    code = main(_args(tmp_path, "publish", "db/demo")
                + ["--notify", "serverchan", "--notify-key", "SCTKEY"])

    assert code == EXIT_OK
    err = capsys.readouterr().err
    assert "通知失败" in err
    assert "回执说没收到" in err


def test_publish_without_a_notify_key_says_so(tmp_path, capsys):
    """给了通道却没给凭据：不能静默当成「没要求通知」。"""
    _site(tmp_path)

    code = main(_args(tmp_path, "publish", "db/demo") + ["--notify", "serverchan"])

    assert code == EXIT_OK
    err = capsys.readouterr().err
    assert "notify-key" in err


# --- the state file the commands rely on --------------------------------


def test_a_corrupt_state_file_is_reported_loudly(tmp_path, capsys):
    """损坏的状态文件不能被默默当成空状态。

    空状态读起来就是「什么都没发过」——那正是把发过的文章再发一遍的
    起点。所以它必须被大声报出来，并且这次运行不算干净。
    """
    _site(tmp_path)
    state_file = tmp_path / "out" / "state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text("{not json", encoding="utf-8")

    code = main(_args(tmp_path, "status"))

    err = capsys.readouterr().err
    assert "状态文件损坏" in err
    assert str(state_file) + ".corrupt" in err
    assert "再发一遍" in err
    assert code != EXIT_OK
    # 证据留着，不删。
    assert (tmp_path / "out" / "state.json.corrupt").is_file()


def test_convert_also_reports_a_corrupt_state_file(tmp_path, capsys):
    """convert 读到损坏的状态文件也要喊出来。

    这一条最要命：出包照做不误，但状态是从空状态来的——发过的文章
    可能被再发一遍。喊出来，这一次运行就不算干净（退出码 3）。
    """
    _site(tmp_path)
    state_file = tmp_path / "out" / "state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text("{not json", encoding="utf-8")

    code = main(_args(tmp_path, "convert", "db/demo"))

    err = capsys.readouterr().err
    assert "状态文件损坏" in err
    assert "再发一遍" in err
    assert code == EXIT_ERROR
    # 出包本身还是做了：这一次只是不可信，不是失败。
    assert (tmp_path / "out" / "db-demo" / "article.html").is_file()


# --- the state file the commands rely on --------------------------------
#
# 这两条守的是「状态文件写成原子的」那件事。它们住在 test_cli.py 而不是
# test_state.py：本次只允许新增一个测试文件，而命令依赖的正是这个写。


def test_a_failed_write_leaves_the_previous_state_file_intact(tmp_path, monkeypatch):
    """状态文件必须原子替换：写坏了也不能把上一份记录截断。

    截断与写完之间进程被杀，状态就归零了——发过的文章会被再发一遍。
    """
    path = tmp_path / "state.json"
    store = StateStore(path)
    store.save("db/one", PublishState(fingerprint="fp1", status="packaged"))
    original = path.read_text(encoding="utf-8")

    def boom(*args, **kwargs):
        raise OSError("磁盘满了")

    monkeypatch.setattr(state_module.os, "replace", boom)
    with pytest.raises(OSError):
        store.save("db/two", PublishState(fingerprint="fp2", status="packaged"))

    assert path.read_text(encoding="utf-8") == original
    assert StateStore(path).get("db/one").fingerprint == "fp1"


def test_no_temporary_file_is_left_behind(tmp_path):
    """临时文件用完要清掉：状态目录里只该有状态文件本身。"""
    path = tmp_path / "state.json"
    StateStore(path).save("db/one", PublishState(fingerprint="fp", status="packaged"))
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]


# --- the command line itself --------------------------------------------


def test_the_cli_writes_nothing_into_the_repository(tmp_path, repo_root):
    """命令不得碰仓库：所有落盘都在临时目录里。"""
    outbox = repo_root / "publish" / "outbox"
    before = sorted(p.name for p in outbox.iterdir()) if outbox.is_dir() else []
    _site(tmp_path)

    assert main(_args(tmp_path, "convert", "db/demo")) == EXIT_OK

    after = sorted(p.name for p in outbox.iterdir()) if outbox.is_dir() else []
    assert after == before


def test_the_shared_options_work_before_the_command_name(tmp_path, capsys):
    """选项写在命令名前面也一样管用。

    子命令自己的默认值会把命令名前面给的值盖掉——那样 `--posts-dir`
    就会指向仓库里的真目录，命令会读错地方。
    """
    _site(tmp_path)
    code = main(["--posts-dir", str(tmp_path / "source" / "_posts"), "scan"])
    assert code == EXIT_OK
    assert "演示标题" in capsys.readouterr().out


def test_main_without_a_command_is_a_usage_error():
    assert main([]) == EXIT_USAGE
