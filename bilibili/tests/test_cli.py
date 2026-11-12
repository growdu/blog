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
