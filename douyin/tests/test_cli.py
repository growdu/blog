"""命令行：开箱可用的调用方式。

规格里写着的调用方式是 `cd douyin && python3 -m douyin.cli package <期号>`——
这条命令得能直接跑，不该要求调用者先设 `PYTHONPATH`。
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

DOUYIN_DIR = Path(__file__).resolve().parents[1]


def _run(args: list[str]) -> subprocess.CompletedProcess:
    """在**没有 PYTHONPATH** 的环境里跑 adapter 的命令行。

    带着继承来的 PYTHONPATH 跑，测试就是假的：路径一给，`pyv` 自然能找到，
    adapter 挂没挂 `sys.path` 这件事根本没被验到。
    """
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    return subprocess.run([sys.executable, "-m", "douyin.cli", *args],
                          cwd=DOUYIN_DIR, env=env, capture_output=True, text=True)


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


def test_the_missing_video_hint_points_at_the_vertical_target():
    """找不到成片时的提示必须指向竖版那一档。

    抖音这一档用的是**竖版 9:16**（同时也是无品牌导流版）——横版在
    抖音的信息流里吃亏，带品牌字标与 `growdu.cn` 胶囊的版本会被判
    「过度营销 + 站外引流」。提示里必须写出来，
    否则下一个人会拿错成片去发。
    """
    from douyin import cli

    assert "vertical" in cli.MISSING_VIDEO_HINT
    assert "make EP={episode} vertical" in cli.MISSING_VIDEO_HINT
    assert "__nobrand" not in cli.MISSING_VIDEO_HINT


def test_the_missing_video_hint_reaches_the_terminal(tmp_path, monkeypatch, capsys):
    """提示要真的打到 stderr 上——只写在常量里等于没写。

    把成片目录指到一个空的地方，「缺成片」这条分支就不依赖本机状态：
    这台机器有六期成片、那台没有，测出来的结果会两样。

    **也不能顺手往仓库的 outbox 写快照**：命令在**另一个进程**里跑，
    conftest 那个 monkeypatch 拦不住。上一版这个测试就把
    `publish/outbox/structured-ddl__douyin.json` 写成了指向
    pytest 临时目录的垃圾。
    """
    from douyin import cli

    monkeypatch.setattr(cli, "AIV_ROOT", tmp_path / "aiv")
    assert cli.main(["package", "structured-ddl"]) == 1
    err = capsys.readouterr().err
    assert "vertical" in err
    assert "make EP=structured-ddl vertical" in err


def test_the_default_video_is_the_vertical_one():
    """默认成片是 `<EP>__vertical.mp4`。

    静默回退到横版或带品牌的那版，等于发错片子——发出去就收不回来了：
    横版在抖音信息流里吃亏，带品牌那版会被判过度营销 + 站外引流。
    """
    from douyin import cli

    assert cli._video_path("row-lock").name == "row-lock__vertical.mp4"
    assert cli._video_path("row-lock").name != "row-lock.mp4"
    assert cli._video_path("row-lock").name != "row-lock__nobrand.mp4"


def test_marking_published_without_a_url_is_refused(tmp_path):
    """published 档必须带公开链接——没有链接就不知道发出去的是哪一条。"""
    proc = _run(["mark", "published", "ep01", "--out", str(tmp_path / "out")])
    assert proc.returncode == 1
    assert "--url" in proc.stderr


def test_marking_published_without_a_package_is_refused(tmp_path, outbox,
                                                        capsys):
    """**没有发布包就不许回填「已发布」。**

    上一版把「发布包不存在」降级成 WARNING，然后照样写状态、照样写快照：
    命令返回 0，快照写着「已发布」并指向一个空的 `package_dir`——
    下一个人照着快照去找发布包，什么都没有，而「已发布」已经记上去了。

    **回填的前提是「发出去的是包里那一版」**。没有包，就没有那一版。
    """
    from douyin import cli

    out = tmp_path / "out"
    assert cli.main(["mark", "published", "row-lock", "--url",
                      "https://www.douyin.com/video/1", "--out", str(out)]) == 1
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
    from douyin import cli

    out = tmp_path / "out"
    assert cli.main(["mark", "published", "no-such-episode", "--url",
                      "https://www.douyin.com/video/1", "--out", str(out)]) == 1
    err = capsys.readouterr().err
    assert "ERROR" in err
    assert "Traceback" not in err
    assert not (out / "state.json").exists(), "失败的回填留下了状态文件"


def test_a_video_that_vanished_gives_an_error_not_a_traceback(tmp_path,
                                                               monkeypatch,
                                                               capsys):
    """成片在预检之后没了：报错退出，别甩 traceback。

    `cmd_package` 先看文件在不在，`build_package` 又探一次——两次之间
    文件没了的话，裸的 `FileNotFoundError` 会一路冒到终端上，
    看着像崩溃，不像「这一条没出包」。
    """
    from douyin import cli, package

    def _vanished(*args, **kwargs):
        raise FileNotFoundError("成片不存在：/tmp/gone.mp4")

    video = tmp_path / "v.mp4"
    video.write_bytes(b"not really a video")
    monkeypatch.setattr(package, "build_package", _vanished)
    assert cli.main(["package", "row-lock", "--video", str(video),
                      "--out", str(tmp_path / "out")]) == 1
    err = capsys.readouterr().err
    assert "ERROR" in err
    assert "Traceback" not in err


def test_drafted_is_not_an_option():
    """抖音这一档**没有**草稿档。

    抖音创作者后台的草稿能力没核实过，设一个没验证过的档位，
    等于给「其实存不下来」发一张通行证（规格 §6.6.1）。
    """
    proc = _run(["mark", "drafted", "ep01"])
    assert proc.returncode != 0
    assert "drafted" not in proc.stdout
