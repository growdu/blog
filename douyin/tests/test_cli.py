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


def test_the_missing_video_hint_points_at_the_nobrand_target():
    """找不到成片时的提示必须指向无品牌版。

    抖音这一档用的是**无品牌导流版**——带品牌字标与 `growdu.cn` 胶囊的
    版本会被判「过度营销 + 站外引流」。提示里必须写出来，
    否则下一个人会拿带品牌的那版去发。
    """
    from douyin import cli

    assert "nobrand" in cli.MISSING_VIDEO_HINT
    assert "make EP={episode} nobrand" in cli.MISSING_VIDEO_HINT


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
    assert "nobrand" in err
    assert "make EP=structured-ddl nobrand" in err


def test_the_default_video_is_the_nobrand_one():
    """默认成片是 `<EP>__nobrand.mp4`，不是 `<EP>.mp4`。

    静默回退到带品牌的那版，等于带着水印发出去——发出去就收不回来了。
    """
    from douyin import cli

    assert cli._video_path("row-lock").name == "row-lock__nobrand.mp4"


def test_marking_published_without_a_url_is_refused(tmp_path):
    """published 档必须带公开链接——没有链接就不知道发出去的是哪一条。"""
    proc = _run(["mark", "published", "ep01", "--out", str(tmp_path / "out")])
    assert proc.returncode == 1
    assert "--url" in proc.stderr


def test_drafted_is_not_an_option():
    """抖音这一档**没有**草稿档。

    抖音创作者后台的草稿能力没核实过，设一个没验证过的档位，
    等于给「其实存不下来」发一张通行证（规格 §6.6.1）。
    """
    proc = _run(["mark", "drafted", "ep01"])
    assert proc.returncode != 0
    assert "drafted" not in proc.stdout
