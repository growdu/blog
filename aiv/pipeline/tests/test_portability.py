"""跨平台守卫：这条流水线不许偷偷依赖 macOS。

换机器这件事，最费时间的不是「装依赖」，而是**跑到一半才发现某个脚本
用了 macOS 专有的东西**。这里把那些坑一条条钉死：

1. 用了 macOS 专有命令的脚本，**必须在文件头写明**「macOS 专有」——
   否则在 Linux 上的人会以为整条链路都跑不了；
2. 不许出现 `/Users/<某人>/` 这样的绝对路径；
3. `requirements.txt` 必须覆盖源码里出现的**每一个**第三方 import；
4. Makefile 不能把解释器写死成 `python`（Linux 上常常只有 `python3`）；
5. CI 必须真的在 Linux 上跑一遍——不然「跨平台」只是嘴上说说。
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
AIV_ROOT = REPO_ROOT / "aiv"
PIPELINE = AIV_ROOT / "pipeline"

#: macOS 专有的命令行工具。Linux 上一个都没有。
MACOS_ONLY_COMMANDS = (
    "say", "osascript", "afplay", "sips", "sw_vers",
    "diskutil", "qlmanage", "screencapture",
)

#: 第三方 import → pip 包名（不一致的写在这里）
THIRD_PARTY_PACKAGES = {
    "cairo": "pycairo",
    "PIL": "Pillow",
    "numpy": "numpy",
    "scipy": "scipy",
    "pytest": "pytest",
}

STDLIB = {
    "__future__", "abc", "argparse", "ast", "collections", "contextlib",
    "copy", "dataclasses", "datetime", "difflib", "enum", "fractions",
    "functools", "glob", "hashlib", "importlib", "inspect", "io",
    "itertools", "json", "math", "os", "pathlib", "random", "re", "shutil",
    "statistics", "string", "struct", "subprocess", "sys", "tempfile",
    "textwrap", "time", "tomllib", "typing", "unicodedata", "urllib",
    "warnings", "wave",
}


def _source_files() -> list[Path]:
    """要扫的源码：aiv/ 下的 .py 与 .sh（跳过 plans/，那是历史记录）。"""
    files: list[Path] = []
    for pattern in ("**/*.py", "**/*.sh"):
        files.extend(
            path for path in AIV_ROOT.glob(pattern)
            if "plans" not in path.parts and "__pycache__" not in path.parts
        )
    return sorted(files)


def test_macos_only_commands_are_declared_in_the_file_header():
    """用了 macOS 专有命令的脚本，必须在文件头写明「macOS 专有」。"""
    files = _source_files()
    # 防空跑：扫不到文件时，下面那个空列表断言会恒真通过
    assert len(files) > 50, f"只扫到 {len(files)} 个文件，扫描范围不对"
    offenders: list[str] = []
    for path in files:
        source = path.read_text(encoding="utf-8", errors="replace")
        used = [
            command for command in MACOS_ONLY_COMMANDS
            if re.search(rf"(?m)^[ \t]*{command}[\s]", source)
        ]
        if not used:
            continue
        header = "\n".join(source.splitlines()[:30])
        if "macOS" not in header:
            offenders.append(f"{path.relative_to(REPO_ROOT)}：{used}")
    assert offenders == [], (
        "这些脚本用了 macOS 专有命令却没在文件头声明：\n" + "\n".join(offenders)
    )


def test_no_source_hardcodes_a_user_home_path():
    """`/Users/<某人>/` 这样的绝对路径在别的机器上必然失效。"""
    files = _source_files()
    assert len(files) > 50, f"只扫到 {len(files)} 个文件，扫描范围不对"
    offenders: list[str] = []
    pattern = re.compile(r"/Users/[A-Za-z0-9_.-]+/")
    for path in files:
        if pattern.search(path.read_text(encoding="utf-8", errors="replace")):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []


def _third_party_imports() -> set[str]:
    """源码里用到的第三方 import（排除标准库与本地模块）。"""
    imported: set[str] = set()
    for path in _source_files():
        source = path.read_text(encoding="utf-8", errors="replace")
        for module in re.findall(r"(?m)^(?:import|from)\s+([A-Za-z0-9_]+)", source):
            if module in STDLIB or module.startswith("_"):
                continue
            imported.add(module)
    return imported


def test_requirements_cover_every_third_party_import():
    """requirements.txt 必须覆盖源码里出现的每一个第三方 import。"""
    requirements = (PIPELINE / "requirements.txt").read_text(encoding="utf-8")
    declared = {
        line.split(">=")[0].split("==")[0].strip().lower()
        for line in requirements.splitlines()
        if line.strip() and not line.startswith("#")
    }
    imported = _third_party_imports()
    # 防空跑：识别不到任何第三方 import 时，下面的 missing 断言会恒真通过
    known = {"cairo", "numpy", "PIL", "scipy", "pytest"}
    assert known <= imported, f"没识别出预期中的第三方 import：{sorted(imported)}"
    missing = sorted(
        THIRD_PARTY_PACKAGES[module]
        for module in imported
        if module in THIRD_PARTY_PACKAGES
        and THIRD_PARTY_PACKAGES[module].lower() not in declared
    )
    assert missing == [], f"requirements.txt 漏了：{missing}"


def test_makefile_does_not_hardcode_the_interpreter():
    """Linux 上常常只有 python3——Makefile 不能把解释器写死成 python。"""
    text = (PIPELINE / "Makefile").read_text(encoding="utf-8")
    assert "command -v python3" in text, "Makefile 没有探测 python3"
    assert not re.search(r"(?m)^PY\s*:?=\s*python\s*$", text), (
        "Makefile 把解释器写死成 python 了"
    )


def test_bootstrap_script_covers_the_linux_package_managers():
    """一键装依赖的脚本要认得主流发行版的包管理器。"""
    text = (PIPELINE / "scripts" / "bootstrap_linux.sh").read_text(encoding="utf-8")
    for manager in ("apt-get", "dnf", "pacman", "zypper"):
        assert manager in text, f"没认得包管理器 {manager}"
    assert "fonts-noto-cjk" in text or "noto-fonts-cjk" in text, (
        "没装中文字体——Linux 上渲染会直接失败"
    )


def test_ci_actually_runs_the_pipeline_on_linux():
    """「跨平台」不能只是嘴上说说：CI 得真的在 Linux 上跑一遍。"""
    workflow = REPO_ROOT / ".github" / "workflows" / "aiv-pipeline.yml"
    assert workflow.is_file(), "没有 Linux CI 工作流"
    text = workflow.read_text(encoding="utf-8")
    assert "ubuntu" in text, "CI 没有跑在 ubuntu 上"
    assert "fonts-noto-cjk" in text, "CI 没装中文字体"
    assert "pytest" in text, "CI 没跑测试"
