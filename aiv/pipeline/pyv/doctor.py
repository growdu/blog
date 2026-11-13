"""环境自检：这台机器能不能跑出片。

**跑之前先自检**，比跑到一半炸掉省时间得多。自检分四组：

* **环境**——Python 版本、第三方库、ffmpeg/ffprobe、字体
* **素材**——出片必需的旁白、BGM、形象素材在不在
* **可选工具**——`mcode-tools`（只有重新合成旁白、重新生成形象才需要）
* **入口**——Makefile 的常用目标

缺什么就报什么，并给出**可执行的修复命令**（不是「请安装依赖」这种废话）。

跑法：

    make doctor
    python -m pyv.cli doctor
"""
from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

AIV_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_ROOT = Path(__file__).resolve().parents[1]

ERROR = "error"
WARNING = "warning"
INFO = "info"

#: Python 最低版本：3.11 起才有 tomllib（能力声明文件是 toml）
MIN_PYTHON = (3, 11)

#: 第三方库 → pip 包名（导入名和安装名不一致的写在这里）
THIRD_PARTY = (
    ("cairo", "pycairo"),
    ("numpy", "numpy"),
    ("PIL", "Pillow"),
    ("scipy", "scipy"),
)

#: 出片必需的媒体素材：(相对 aiv/ 的路径, 说明, 缺了算多严重)
REQUIRED_ASSETS = (
    ("character/growdu_character_2k_nobg.png", "小象立绘（渲染必需）", ERROR),
    ("music/tracks/series-bed-01.wav", "正文铺底 BGM（混音必需）", ERROR),
)

#: 缺了只是「成片不带品牌片」，不算致命
OPTIONAL_ASSETS = (
    ("brand/clips/growdu_intro_3s_1080p.mp4", "品牌片头", WARNING),
    ("brand/clips/growdu_outro_3s_1080p.mp4", "品牌片尾", WARNING),
    ("brand/audio/intro_mix.wav", "片头成品音轨", WARNING),
    ("brand/audio/outro_mix.wav", "片尾成品音轨", WARNING),
)


@dataclass(frozen=True)
class Check:
    """一条自检结论。"""

    group: str
    name: str
    level: str
    ok: bool
    detail: str
    fix: str = ""

    @property
    def mark(self) -> str:
        return {ERROR: "✗", WARNING: "!", INFO: "·"}.get(self.level, "·")


def _check_python() -> Check:
    version = ".".join(str(part) for part in sys.version_info[:3])
    ok = sys.version_info[:2] >= MIN_PYTHON
    return Check(
        "环境", "Python", ERROR if not ok else INFO, ok, version,
        fix="" if ok else f"需要 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} 及以上",
    )


def _check_imports() -> list[Check]:
    checks: list[Check] = []
    for module_name, package in THIRD_PARTY:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001 - 任何导入失败都算缺
            checks.append(Check(
                "环境", module_name, ERROR, False, f"导入失败：{exc}",
                fix=f"pip install {package}",
            ))
            continue
        version = getattr(module, "__version__", None) or (
            getattr(module, "version", None) or "已安装"
        )
        checks.append(Check("环境", module_name, INFO, True, str(version)))
    return checks


def _ffmpeg_encoders() -> str:
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout or ""


def _check_ffmpeg() -> list[Check]:
    checks: list[Check] = []
    for tool, fix in (("ffmpeg", "sudo apt-get install -y ffmpeg"),
                      ("ffprobe", "sudo apt-get install -y ffmpeg")):
        path = shutil.which(tool)
        checks.append(Check(
            "环境", tool, INFO if path else ERROR, bool(path),
            path or "没找到", fix="" if path else fix,
        ))
    if not shutil.which("ffmpeg"):
        return checks

    encoders = _ffmpeg_encoders()
    for name, keyword, fix in (
        ("H.264 编码", "libx264", "换个带 libx264 的 ffmpeg（Debian/Ubuntu 的官方包自带）"),
        ("AAC 编码", " aac ", "换个带原生 aac 编码器的 ffmpeg"),
    ):
        present = keyword in encoders
        checks.append(Check(
            "环境", name, INFO if present else ERROR, present,
            "可用" if present else "不可用", fix="" if present else fix,
        ))
    return checks


def _check_font() -> Check:
    from pyv import fonts

    font = fonts.resolve_font()
    return Check(
        "环境", "中文字体", INFO if font.resolves else ERROR, font.resolves,
        font.label, fix="" if font.resolves else fonts.INSTALL_HINT,
    )


def _check_assets() -> list[Check]:
    checks: list[Check] = []
    for relative, note, level in REQUIRED_ASSETS + OPTIONAL_ASSETS:
        path = AIV_ROOT / relative
        present = path.is_file()
        checks.append(Check(
            "素材", relative, INFO if present else level, present,
            note if present else f"缺：{note}", fix="" if present else
            f"从仓库取：git checkout -- {relative}（若刚 clone 就没取到）",
        ))
    return checks


def _check_narrations() -> list[Check]:
    """每一期的旁白 mp3。缺了就跑不了那一期的 align/render/compose。"""
    from pyv import episodes

    checks: list[Check] = []
    for ep in episodes.EPISODE_ORDER:
        narration = episodes.narration_path(ep)
        present = narration.is_file()
        script = episodes.EPISODES[ep]
        checks.append(Check(
            "素材", f"narration_{ep}.mp3", INFO if present else ERROR, present,
            "已就位" if present else "缺：这一期的旁白",
            fix="" if present else
            f"合成：python3 aiv/voice/scripts/synthesize_narration.py "
            f"--script aiv/{script} --out aiv/narration_{ep}.mp3",
        ))
    return checks


def _check_mcode_tools() -> Check:
    path = shutil.which("mcode-tools")
    return Check(
        "可选工具", "mcode-tools", INFO, True,
        path or "未安装（只有重新合成旁白 / 重新生成形象才需要）",
        fix="" if path else "见 mcode-tools-master skill 的安装说明",
    )


def _check_episodes() -> list[Check]:
    """每一期的口播稿与契约都在（这两样是入库的，必须齐）。"""
    from pyv import episodes

    checks: list[Check] = []
    for ep in episodes.EPISODE_ORDER:
        script = episodes.script_path(ep)
        contract = episodes.contract_path(ep)
        missing = [str(p) for p in (script, contract) if not p.is_file()]
        checks.append(Check(
            "素材", f"{ep} 的稿件与契约", INFO if not missing else ERROR,
            not missing,
            "已就位" if not missing else f"缺：{'、'.join(missing)}",
            fix="" if not missing else "git checkout -- aiv/",
        ))
    return checks


def run_checks() -> list[Check]:
    """跑完全部自检，返回结论列表。"""
    checks: list[Check] = [_check_python()]
    checks.extend(_check_imports())
    checks.extend(_check_ffmpeg())
    checks.append(_check_font())
    checks.extend(_check_episodes())
    checks.extend(_check_assets())
    checks.extend(_check_narrations())
    checks.append(_check_mcode_tools())
    return checks


def format_report(checks: list[Check]) -> str:
    lines: list[str] = []
    group = ""
    for check in checks:
        if check.group != group:
            group = check.group
            lines.append("")
            lines.append(f"== {group} ==")
        lines.append(f"  {check.mark} {check.name:<44} {check.detail}")
        if not check.ok and check.fix:
            lines.append(f"      → {check.fix}")
    errors = sum(1 for c in checks if not c.ok and c.level == ERROR)
    warnings = sum(1 for c in checks if not c.ok and c.level == WARNING)
    lines.append("")
    if errors:
        lines.append(f"FAIL {errors} 项硬性缺失、{warnings} 项告警——先补齐硬性缺失")
    else:
        lines.append(f"OK 环境就绪（{warnings} 项告警）")
    return "\n".join(lines)


def main() -> int:
    checks = run_checks()
    print(format_report(checks))
    return 1 if any(not c.ok and c.level == ERROR for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
