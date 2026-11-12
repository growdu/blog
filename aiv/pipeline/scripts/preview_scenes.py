"""把一期契约的画面渲成 PNG，用来肉眼核对图示。

技术图示一律由代码绘制（不交给模型生成），所以每一张图都得有人看过。
出片之前跑一次，把这一期的六张图逐段看一遍——版式有没有挤、文案有没有压边、
颜色是不是够分得开，都是看出来的，不是测出来的。

用法（在 `aiv/pipeline/` 下跑）：

    python3 scripts/preview_scenes.py --contract ../contracts/wal-interleave.json
    python3 scripts/preview_scenes.py --contract ../contracts/wal-interleave.json \
        --times 0.2 0.6 --out ../_staging/preview

输出是 PNG，一个场景一张。默认抓三个时间点：开场、居中、收尾。
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

import cairo

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE_ROOT))

from pyv import contract as contract_mod  # noqa: E402
from pyv.palette import COLORS, hex_to_rgb  # noqa: E402

DEFAULT_TIMES = (0.15, 0.55, 0.95)
WIDTH = 1920
HEIGHT = 1080


def _without_mascot() -> None:
    """形象一律不画：预览要看的是版式，不是素材。

    3D 形象是媒体产物、不入库，预览里带上它只会让「换台机器预览就不一样」。
    """
    from pyv import character

    def _no_mascot(self) -> None:
        self._mode = "none"

    character.Mascot._load = _no_mascot


def render_png(renderer: str, params: dict, t: float, out_path: Path) -> Path:
    module = importlib.import_module(renderer)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(*hex_to_rgb(COLORS["bg"]))
    ctx.paint()
    module.render(ctx, t, WIDTH, HEIGHT, params)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    surface.write_to_png(str(out_path))
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="把契约的画面渲成 PNG 预览")
    parser.add_argument("--contract", default=None,
                        help="契约文件路径，默认用默认那一期")
    parser.add_argument("--times", type=float, nargs="*", default=list(DEFAULT_TIMES),
                        help="要抓的场景内进度，0~1")
    parser.add_argument("--out", default=None,
                        help="输出目录，默认 _staging/preview/<期号>")
    args = parser.parse_args()

    _without_mascot()
    contract = contract_mod.load_contract(args.contract)
    out_dir = Path(args.out) if args.out else (
        PIPELINE_ROOT.parent / "_staging" / "preview" / contract.episode
    )

    for segment in contract.segments:
        for t in args.times:
            name = f"{segment.id}-{str(t).replace('.', 'p')}.png"
            path = render_png(segment.renderer, segment.params, t, out_dir / name)
            print(f"  {segment.id} t={t}  {path}")


if __name__ == "__main__":
    main()
