"""命令行入口。

用法：
    python -m pyv.cli validate --storyboard ../storyboard.json
    python -m pyv.cli align    --audio ../pa_decode_v2.mp3 --script ../字幕-并行解码.md
    python -m pyv.cli render   --storyboard ../storyboard.json --out ../build
    python -m pyv.cli compose  --storyboard ../storyboard.json --build ../build --out ../out
"""
from __future__ import annotations

import argparse
import sys

from pyv import palette
from pyv.timeline import Storyboard


def _load_or_report(args: argparse.Namespace) -> Storyboard | None:
    storyboard = Storyboard.load(args.storyboard)
    errors = storyboard.validate()
    if errors:
        for e in errors:
            print(f"ERROR {e}", file=sys.stderr)
        return None
    return storyboard


def cmd_validate(args: argparse.Namespace) -> int:
    storyboard = _load_or_report(args)
    if storyboard is None:
        return 1
    palette.assert_font_available()
    print(
        f"OK {len(storyboard.scenes)} 个场景，"
        f"{len(storyboard.subtitle_events())} 条字幕，"
        f"总时长 {storyboard.duration:.3f}s"
    )
    return 0


def cmd_align(args: argparse.Namespace) -> int:
    from pyv import align
    storyboard = align.build_storyboard(args.audio, args.script, args.out)
    print(
        f"OK {len(storyboard.scenes)} 个视觉段，"
        f"{len(storyboard.subtitle_events())} 条字幕 → {args.out}"
    )
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    from pyv import render
    storyboard = _load_or_report(args)
    if storyboard is None:
        return 1
    palette.assert_font_available()
    outputs = render.render_storyboard(storyboard, args.out)
    print(f"OK 渲染 {len(outputs)} 个片段 → {args.out}")
    return 0


def cmd_compose(args: argparse.Namespace) -> int:
    from pyv import compose
    storyboard = _load_or_report(args)
    if storyboard is None:
        return 1
    out = compose.compose(
        storyboard, args.build, args.out, narration=args.narration
    )
    print(f"OK 成片 → {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pyv")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--storyboard", required=True)
    p_validate.set_defaults(func=cmd_validate)

    p_align = sub.add_parser("align")
    p_align.add_argument("--audio", required=True)
    p_align.add_argument("--script", required=True)
    p_align.add_argument("--out", required=True)
    p_align.set_defaults(func=cmd_align)

    p_render = sub.add_parser("render")
    p_render.add_argument("--storyboard", required=True)
    p_render.add_argument("--out", required=True)
    p_render.set_defaults(func=cmd_render)

    p_compose = sub.add_parser("compose")
    p_compose.add_argument("--storyboard", required=True)
    p_compose.add_argument("--build", required=True)
    p_compose.add_argument("--out", required=True)
    p_compose.add_argument("--narration", default=None)
    p_compose.set_defaults(func=cmd_compose)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
