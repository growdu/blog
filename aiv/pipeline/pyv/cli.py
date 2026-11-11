"""命令行入口。

用法：
    python -m pyv.cli validate --storyboard ../storyboard.json
    python -m pyv.cli align    --audio ../pa_decode_v2.mp3 --script ../字幕-并行解码.md
    python -m pyv.cli render   --storyboard ../storyboard.json --out ../build
    python -m pyv.cli compose  --storyboard ../storyboard.json --build ../build --out ../out
    python -m pyv.cli persona check --script ../字幕-并行解码.md
    python -m pyv.cli bgm check --music ../music/tracks/motif.wav
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pyv import contract
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
    storyboard = align.build_storyboard(
        args.audio, args.script, args.out, contract_path=args.scenes
    )
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


def cmd_bgm(args: argparse.Namespace) -> int:
    """背景音乐检查：单条曲子 / 台账 / 混音参数。"""
    from pyv import bgm

    if args.bgm_command == "mix":
        print(f"BGM 母带归一化     {bgm.MASTER_LUFS} LUFS")
        print(f"基础增益           {bgm.BGM_GAIN_DB} dB")
        print(f"duck 深度         {bgm.DUCK_DEPTH_DB} dB"
              f"（起落 {bgm.DUCK_ATTACK_MS}/{bgm.DUCK_RELEASE_MS} ms）")
        print(f"避让 EQ           {bgm.EQ_BELL_HZ} Hz / {bgm.EQ_BELL_DB} dB"
              f" / Q={bgm.EQ_BELL_Q}")
        print(f"高通              {bgm.HIGHPASS_HZ} Hz")
        print(f"通道链             {bgm.bgm_chain()}")
        return 0

    if args.bgm_command == "library":
        entries = bgm.load_library(args.library)
        findings = bgm.check_library(entries, args.library)
        for finding in findings:
            print(f"{finding.level.upper():7} {finding}")
        print(f"台账 {len(entries)} 首，{len(findings)} 个问题")
        return 1 if any(f.level == bgm.ERROR for f in findings) else 0

    # check
    profile = bgm.measure(args.music)
    print(f"{Path(args.music).name}  {profile.duration_s:.1f}s / "
          f"{profile.sample_rate} Hz / {profile.channels} ch / "
          f"LUFS {profile.lufs:.1f} / 真峰值 {profile.true_peak_db:.1f} dBTP / "
          f"重心 {profile.centroid_hz:.0f} Hz")
    findings = bgm.check_track(args.music, args.duration)
    for finding in findings:
        print(f"{finding.level.upper():7} {finding}")
    if not findings:
        print("OK 这条曲子合格")
        return 0
    errors = [f for f in findings if f.level == bgm.ERROR]
    if errors:
        print(f"FAIL {len(errors)} 个硬约束违规", file=sys.stderr)
        return 1
    print("OK 通过（只有倾向类提示）")
    return 0


def main(argv: list[str] | None = None) -> int:
    from pyv import bgm

    parser = argparse.ArgumentParser(prog="pyv")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--storyboard", required=True)
    p_validate.set_defaults(func=cmd_validate)

    p_align = sub.add_parser("align")
    p_align.add_argument("--audio", required=True)
    p_align.add_argument("--script", required=True)
    p_align.add_argument("--out", required=True)
    p_align.add_argument("--scenes", default=str(contract.DEFAULT_CONTRACT),
                         help="视觉分镜契约（本期文案与段落划分）")
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

    p_bgm = sub.add_parser("bgm")
    bgm_sub = p_bgm.add_subparsers(dest="bgm_command", required=True)

    p_bgm_check = bgm_sub.add_parser("check")
    p_bgm_check.add_argument("--music", required=True)
    p_bgm_check.add_argument("--duration", type=float, default=None,
                             help="目标视频时长（秒）；曲子短于此则不合格")
    p_bgm_check.set_defaults(func=cmd_bgm)

    p_bgm_library = bgm_sub.add_parser("library")
    p_bgm_library.add_argument("--library", default=str(bgm.LIBRARY_PATH))
    p_bgm_library.set_defaults(func=cmd_bgm)

    p_bgm_mix = bgm_sub.add_parser("mix")
    p_bgm_mix.set_defaults(func=cmd_bgm)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
