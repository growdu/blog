"""环境自检：这台机器缺什么、怎么补。

**为什么要单独一个 doctor。** 「换台机器也能跑」这句话要能验证，
就得有一个入口能回答「这台机器现在能不能跑浏览器投稿」。
参照 `aiv/pipeline` 的 `make doctor` 做成同一形状。

自检**不碰网络**，也不启动浏览器窗口（只读一下 chromium 的可执行文件路径）。
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass
from pathlib import Path

from browser import pw
from browser.session import default_profile_dir, login_state_present


@dataclass
class Finding:
    """一条自检结论。"""

    level: str          # "ok" / "warn" / "fail"
    item: str
    message: str
    fix: str = ""

    def render(self) -> str:
        mark = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}.get(self.level, "?")
        line = f"{mark} {self.item}：{self.message}"
        if self.fix:
            line += f"\n     → {self.fix}"
        return line


def _check_playwright() -> list[Finding]:
    if not pw.is_installed():
        return [Finding("fail", "playwright",
                        "没装 playwright",
                        "pip install -r browser/requirements.txt")]
    version = pw.installed_version()
    return [Finding("ok", "playwright", f"已装，版本 {version or '未知'}")]


def _check_chromium() -> list[Finding]:
    """chromium 的可执行文件在不在。

    只读路径，不启动浏览器——doctor 不该弹出窗口来。
    """
    try:
        sync_playwright = pw.import_playwright()
        with sync_playwright() as play:
            executable = play.chromium.executable_path
    except Exception as error:
        return [Finding("fail", "chromium", f"查不到 chromium：{error}",
                        "python3 -m playwright install chromium")]
    if not executable or not Path(executable).exists():
        return [Finding("fail", "chromium", f"可执行文件不存在：{executable}",
                        "python3 -m playwright install chromium")]
    return [Finding("ok", "chromium", f"就位：{executable}")]


def _check_profile(profile_dir: Path | None = None) -> list[Finding]:
    root = Path(profile_dir) if profile_dir else default_profile_dir()
    if not root.exists():
        return [Finding("warn", "profile", f"还没有 profile 目录：{root}",
                        "第一次跑 `python3 -m browser.cli probe` 时会自动创建")]
    if login_state_present(root):
        return [Finding("ok", "profile", f"{root}（有登录态）")]
    return [Finding("warn", "profile", f"{root}（还没有登录态）",
                    "跑 `python3 -m browser.cli probe` 扫一次码")]


def _check_display() -> list[Finding]:
    """有没有能弹窗口的显示环境。

    Linux 上没有 X/Wayland 时，headless=False 的 Chromium 起不来——
    扫码登录必须要有窗口，所以这里给的是硬失败而不是警告。
    """
    if platform.system() != "Linux":
        return []
    if not (sys.platform.startswith("linux")):
        return []
    display = None
    try:
        import os

        display = os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    except Exception:  # pragma: no cover
        pass
    if display:
        return [Finding("ok", "显示环境", f"{display}（可以用有头模式）")]
    return [Finding("fail", "显示环境",
                    "没有 DISPLAY / WAYLAND_DISPLAY，有头模式起不来",
                    "本地桌面直接跑；纯服务器上装 xvfb："
                    "sudo apt-get install -y xvfb，然后 xvfb-run -a python3 -m browser.cli ...")]


def run_doctor(profile_dir: Path | None = None) -> list[Finding]:
    """跑一遍自检，返回结论清单。"""
    findings: list[Finding] = []
    findings.extend(_check_playwright())
    findings.extend(_check_chromium())
    findings.extend(_check_profile(profile_dir))
    findings.extend(_check_display())
    return findings


def render(findings: list[Finding]) -> str:
    return "\n".join(f.render() for f in findings)
