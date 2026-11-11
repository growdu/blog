"""目录形状与凭据安全的不变量。

这些断言看着琐碎，但它们守的是**不可协商的底线**：
凭据永不入库、产物不入库、包的 import 路径唯一。
"""

import subprocess
from pathlib import Path

import pytest

import toutiao


def test_package_importable():
    """`import toutiao` 必须解析到 toutiao/toutiao/，不是仓库根的同名目录。"""
    assert toutiao.__version__
    package_dir = Path(toutiao.__file__).resolve().parent
    assert package_dir.name == "toutiao"
    assert package_dir.parent.name == "toutiao"
    assert (package_dir.parent / "toutiao").is_dir()


def test_top_level_dir_is_not_a_package():
    """顶层 toutiao/ 不是 Python 包，包在同名子目录里（照抄 weixin/ 的形状）。"""
    repo_root = Path(toutiao.__file__).resolve().parents[2]
    assert not (repo_root / "toutiao" / "__init__.py").exists()
    assert (repo_root / "toutiao" / "toutiao" / "__init__.py").exists()


@pytest.mark.parametrize("path", ["toutiao/secrets.json", "toutiao/out/package/x.html"])
def test_ignored_paths_are_git_ignored(repo_root: Path, path: str):
    """凭据与本地产物必须真的被 git 挡住 —— 用 git 自己判定，不靠肉眼读 .gitignore。"""
    result = subprocess.run(
        ["git", "check-ignore", "-q", path],
        cwd=repo_root,
        capture_output=True,
    )
    assert result.returncode == 0, f"{path} 没有被 .gitignore 挡住"


def test_credentials_example_is_not_ignored(repo_root: Path):
    """反向断言：示例文件必须可入库，否则模板改不动。"""
    result = subprocess.run(
        ["git", "check-ignore", "-q", "toutiao/secrets.example.json"],
        cwd=repo_root,
        capture_output=True,
    )
    assert result.returncode != 0
