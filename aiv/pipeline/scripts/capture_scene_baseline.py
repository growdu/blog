"""重抓场景画面的逐像素基准指纹。

用法（在 `aiv/pipeline/` 下跑）：

    python3 scripts/capture_scene_baseline.py

抓取方式与 `tests/test_contract.py` 里那条守卫**完全一致**：
cairo ARGB32 1920×1080，刷 `COLORS['bg']` 底色，对整帧字节取 sha256；
形象以 `character.Mascot._load` 强制降级为 none——3D 形象是媒体产物不入库，
基准若带着素材抓，换台机器、换个干净检出就必然对不上，
那条测试会退化成「看本机有没有图」，而不是「看这次改造有没有改到画面」。

**什么时候该重抓**：画面文案或版式**有意**改了之后。
那条守卫的本意是「文案搬进契约不该动到画面」，所以基准一红，
先问是不是手滑改了画面；确认是有意的，再跑这个脚本重抓。
"""
from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

import cairo

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE_ROOT))

from pyv import contract as contract_mod  # noqa: E402
from pyv.palette import COLORS, hex_to_rgb  # noqa: E402

TIMES = (0.0, 0.45, 0.9)
BASELINE = PIPELINE_ROOT / "tests" / "fixtures" / "scene_baseline.json"

NOTE = (
    "场景画面的基准指纹。**形象一律不画**——3D 形象是媒体产物不入库，"
    "基准若带着素材抓，换台机器或换个干净检出就必然对不上，"
    "测试就变成「看本机有没有图」。"
    "抓取方式：cairo ARGB32 1920×1080，刷 COLORS['bg'] 底色，"
    "对整帧字节取 sha256；形象以 character.Mascot._load 强制降级为 none。"
    "重抓脚本：pipeline/scripts/capture_scene_baseline.py"
)


def _without_mascot() -> None:
    """让形象一律不画（与测试里的做法一致）。"""
    from pyv import character

    def _no_mascot(self) -> None:
        self._mode = "none"

    character.Mascot._load = _no_mascot


def frame_hash(module_name: str, params: dict, t: float) -> str:
    module = importlib.import_module(module_name)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1920, 1080)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(*hex_to_rgb(COLORS["bg"]))
    ctx.paint()
    module.render(ctx, t, 1920, 1080, params)
    return hashlib.sha256(bytes(surface.get_data())).hexdigest()


def _captured_from() -> str:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PIPELINE_ROOT, check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        sha = "unknown"
    return f"{sha}（重抓于本脚本）"


def main() -> None:
    _without_mascot()
    contract = contract_mod.load_contract()
    frames: dict[str, str] = {}
    for segment in contract.segments:
        for t in TIMES:
            key = f"{segment.renderer}@{t}"
            frames[key] = frame_hash(segment.renderer, segment.params, t)
            print(f"  {key}  {frames[key][:16]}")

    payload = {
        "note": NOTE,
        "capture": {
            "size": "1920x1080",
            "times": list(TIMES),
            "mascot": "none",
            "captured_from": _captured_from(),
        },
        "frames": frames,
    }
    BASELINE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"已写入 {BASELINE}（{len(frames)} 帧）")


if __name__ == "__main__":
    main()
