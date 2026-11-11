"""命令行入口。

用法：
    python -m pyv.cli validate --storyboard ../storyboard.json
    python -m pyv.cli align    --audio ../pa_decode_v2.mp3 --script ../字幕-并行解码.md
    python -m pyv.cli render   --storyboard ../storyboard.json --out ../build
    python -m pyv.cli compose  --storyboard ../storyboard.json --build ../build --out ../out
    python -m pyv.cli persona check --script ../字幕-并行解码.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

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
    from pyv import render, subtitle
    storyboard = _load_or_report(args)
    if storyboard is None:
        return 1
    palette.assert_font_available()
    # 预览片同样烧字幕，保证与成片一致、可被 compose 直接复用
    burner = subtitle.SubtitleBurner(
        storyboard.subtitle_events(), storyboard.subtitle_style
    )
    source_mtime = Path(args.storyboard).stat().st_mtime
    reused = sum(
        1 for scene in storyboard.scenes
        if scene.type == "code"
        and render.clip_is_fresh(
            Path(args.out) / f"{scene.id}.mp4", scene, source_mtime
        )
    )
    outputs = render.render_storyboard(
        storyboard, args.out, burner=burner, reuse=True,
        source_mtime=source_mtime,
    )
    print(
        f"OK {len(outputs)} 个片段（{reused} 个复用，"
        f"{len(outputs) - reused} 个新渲染）→ {args.out}"
    )
    return 0


def cmd_compose(args: argparse.Namespace) -> int:
    from pyv import compose
    storyboard = _load_or_report(args)
    if storyboard is None:
        return 1
    out = compose.compose(
        storyboard, args.build, args.out, narration=args.narration,
        bgm=args.bgm,
        source_mtime=Path(args.storyboard).stat().st_mtime,
    )
    print(f"OK 成片 → {out}")
    return 0


def cmd_brand(args: argparse.Namespace) -> int:
    from pyv import brand
    out = brand.apply_plates(
        args.storyboard, args.out, args.build,
        intro=not args.no_intro, outro=not args.no_outro,
    )
    storyboard = Storyboard.load(out)
    errors = storyboard.validate()
    if errors:
        for e in errors:
            print(f"ERROR {e}", file=sys.stderr)
        return 1
    plates = [s for s in storyboard.scenes if s.id.startswith("brand_")]
    detail = "、".join(
        f"{s.id} {s.duration:.3f}s" for s in plates
    ) or "无品牌片"
    print(
        f"OK 品牌片：{detail}；"
        f"{len(storyboard.scenes)} 个场景，总时长 {storyboard.duration:.3f}s → {out}"
    )
    return 0


def cmd_persona(args: argparse.Namespace) -> int:
    """检查口播稿符不符合《人格规范》。"""
    from pyv import persona

    report = persona.check_file(args.script)
    for finding in report.findings:
        marker = "ERROR  " if finding.level == persona.ERROR else "WARNING"
        print(f"{marker} {finding.rule_id}  {finding.message}")
    print(
        f"能力域：{report.domain_label}；"
        f"{len(report.sentences)} 句，"
        f"{len(report.errors)} 个硬约束违规，"
        f"{len(report.warnings)} 个倾向未达标"
    )
    if not report.ok:
        sys.stdout.flush()  # 别让 stderr 的结论跑到明细前面去
        print("FAIL 有硬约束违规，出片前必须改", file=sys.stderr)
        return 1
    print("OK 人格检查通过")
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
    p_compose.add_argument("--bgm", default=None)
    p_compose.set_defaults(func=cmd_compose)

    p_brand = sub.add_parser("brand")
    p_brand.add_argument("--storyboard", required=True)
    p_brand.add_argument("--out", required=True)
    p_brand.add_argument("--build", required=True)
    p_brand.add_argument("--no-intro", action="store_true")
    p_brand.add_argument("--no-outro", action="store_true")
    p_brand.set_defaults(func=cmd_brand)

    p_persona = sub.add_parser("persona")
    persona_sub = p_persona.add_subparsers(dest="persona_command", required=True)

    p_persona_check = persona_sub.add_parser("check")
    p_persona_check.add_argument("--script", required=True)
    p_persona_check.set_defaults(func=cmd_persona)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
