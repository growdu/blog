"""命令行：开箱可用的调用方式。

规格里写着的调用方式是 `cd douyin && python3 -m douyin.cli package <期号>`——
这条命令得能直接跑，不该要求调用者先设 `PYTHONPATH`。
"""

import os
import subprocess
import sys
from pathlib import Path

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
