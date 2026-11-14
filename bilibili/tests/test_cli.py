"""命令行：开箱可用的调用方式。

规格里写着的调用方式是 `cd bilibili && python3 -m bilibili.cli package <期号>`——
这条命令得能直接跑，不该要求调用者先设 `PYTHONPATH`。
"""

import os
import subprocess
import sys
from pathlib import Path

BILIBILI_DIR = Path(__file__).resolve().parents[1]


def _run(args: list[str]) -> subprocess.CompletedProcess:
    """在**没有 PYTHONPATH** 的环境里跑 adapter 的命令行。

    带着继承来的 PYTHONPATH 跑，测试就是假的：路径一给，`pyv` 自然能找到，
    adapter 挂没挂 `sys.path` 这件事根本没被验到。
    """
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    return subprocess.run([sys.executable, "-m", "bilibili.cli", *args],
                          cwd=BILIBILI_DIR, env=env, capture_output=True, text=True)


def test_the_cli_runs_without_pythonpath():
    proc = _run(["--help"])
    assert proc.returncode == 0, proc.stderr[-500:]
    assert "package" in proc.stdout


def test_the_cli_reports_a_missing_video_instead_of_crashing(tmp_path):
    """成片不在就报错退出——不能留一个 traceback 给不熟代码的人。"""
    proc = _run(["package", "no-such-episode", "--out", str(tmp_path / "out")])
    assert proc.returncode == 1
    assert "ERROR" in proc.stderr
    assert "Traceback" not in proc.stderr


def test_marking_published_without_a_package_is_refused(tmp_path, outbox,
                                                        capsys):
    """**没有发布包就不许回填「已发布」。**

    上一版把「发布包不存在」降级成 WARNING，然后照样写状态、照样写快照：
    命令返回 0，快照写着「已发布」并指向一个空的 `package_dir`——
    下一个人照着快照去找发布包，什么都没有，而「已发布」已经记上去了。

    **回填的前提是「发出去的是包里那一版」。** 没有包，就没有那一版。
    """
    from bilibili import cli

    out = tmp_path / "out"
    assert cli.main(["mark", "published", "row-lock", "--url",
                      "https://www.bilibili.com/video/BV1", "--out", str(out)]) == 1
    err = capsys.readouterr().err
    assert "发布包不存在" in err
    assert not (out / "state.json").exists(), "失败的回填留下了状态文件"
    assert not list(outbox.glob("*.json")), "失败的回填留下了状态快照"


def test_marking_drafted_without_a_package_is_refused(tmp_path, outbox, capsys):
    """草稿档也一样：草稿是拿这个包投出去的，没有包就无从谈起。"""
    from bilibili import cli

    out = tmp_path / "out"
    assert cli.main(["mark", "drafted", "row-lock", "--out", str(out)]) == 1
    err = capsys.readouterr().err
    assert "发布包不存在" in err
    assert not (out / "state.json").exists(), "失败的回填留下了状态文件"
    assert not list(outbox.glob("*.json")), "失败的回填留下了状态快照"


def test_a_failed_mark_leaves_no_state_behind(tmp_path, capsys):
    """**失败不许留下假状态。**

    上一版的顺序是「先存状态，再读元数据」：元数据读不到时命令崩了，
    而状态文件里已经写着「已发布」。顺序反过来就好了——
    会失败的事先做完，都成了才落状态。
    """
    from bilibili import cli

    out = tmp_path / "out"
    assert cli.main(["mark", "published", "no-such-episode", "--url",
                      "https://www.bilibili.com/video/BV1", "--out", str(out)]) == 1
    err = capsys.readouterr().err
    assert "ERROR" in err
    assert "Traceback" not in err
    assert not (out / "state.json").exists(), "失败的回填留下了状态文件"
