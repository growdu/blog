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


def cmd_topics(args: argparse.Namespace) -> int:
    """检查选题库的结构、口径与出处。"""
    from pyv import topics

    episodes = topics.parse_topics(args.library or topics.TOPICS_PATH)
    findings = topics.check_topics(episodes)
    for finding in findings:
        marker = "ERROR  " if finding.level == topics.ERROR else "WARNING"
        print(f"{marker} {finding.rule_id}  {finding.message}")
    print(f"选题库 {len(episodes)} 期，{len(findings)} 个问题")
    if any(f.level == topics.ERROR for f in findings):
        sys.stdout.flush()
        print("FAIL 有硬约束违规，定稿前必须改", file=sys.stderr)
        return 1
    print("OK 选题库检查通过")
    return 0


def cmd_bgm(args: argparse.Namespace) -> int:
    """背景音乐检查：单条曲子 / 台账 / 混音参数 / 成片混音。"""
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

    if args.bgm_command == "verify":
        body_start, body_end = _mix_body_range(args)
        report = bgm.measure_mix(
            args.video, args.narration, args.music, body_start, body_end)
        print(report.summary())
        findings = bgm.check_mix(report)
        for finding in findings:
            print(f"{finding.level.upper():7} {finding}")
        if not findings:
            print("OK 成片混音合格")
            return 0
        print(f"FAIL {len(findings)} 个硬约束违规", file=sys.stderr)
        return 1

    if args.bgm_command == "library":
        entries = bgm.load_library(args.library)
        findings = bgm.check_library(entries, args.library)
        for finding in findings:
            print(f"{finding.level.upper():7} {finding}")
        print(f"台账 {len(entries)} 首，{len(findings)} 个问题")
        return 1 if any(f.level == bgm.ERROR for f in findings) else 0

    if args.bgm_command == "windows":
        return _cmd_bgm_windows(args)

    if args.bgm_command == "brand-check":
        windows = bgm.load_brand_windows(args.windows)
        music = args.music
        if music is None:
            entries = bgm.load_library()
            motif = next((e for e in entries if e.series_role == "motif"), None)
            if motif is None:
                print("台账里没有 series_role=motif 的曲子", file=sys.stderr)
                return 1
            music = str(bgm.AIV_ROOT / motif.local_path)
        findings = bgm.check_brand_windows(windows, music)
        print(f"片头 {windows.intro_start_s:.3f}~{windows.intro_end_s:.3f}s / "
              f"片尾 {windows.outro_start_s:.3f}~{windows.outro_end_s:.3f}s"
              f"（{windows.track_id}，起音比 {windows.onset_ratio:.2f}）")
        for finding in findings:
            print(f"{finding.level.upper():7} {finding}")
        errors = [f for f in findings if f.level == bgm.ERROR]
        if errors:
            print(f"FAIL {len(errors)} 个硬约束违规", file=sys.stderr)
            return 1
        print("OK 片头片尾首尾相接")
        return 0

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


def cmd_publish(args: argparse.Namespace) -> int:
    """检查一期的发布元数据与成片技术门槛。

    不发任何请求、不写任何文件——这是给作者看的体检报告。
    """
    from pyv import epmeta, preflight

    try:
        meta = epmeta.load_meta(args.episode)
    except epmeta.MetaError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1

    contract_episode = ""
    contract_path = epmeta.AIV_ROOT / "contracts" / f"{args.episode}.json"
    if contract_path.is_file():
        from pyv import contract as contract_mod
        contract_episode = contract_mod.load_contract(contract_path).episode

    video = epmeta.AIV_ROOT / "out" / f"{args.episode}.mp4"
    info = None
    duration = None
    if video.is_file():
        info = preflight.probe(video)
        duration = info.duration
    else:
        print(f"WARNING preflight.video 成片不在本机（{video}），"
              f"跳过技术门槛检查")

    findings = epmeta.check_meta(
        meta, contract_episode=contract_episode, duration=duration)
    if info is not None:
        for platform in ("channels", "bilibili"):
            findings.extend(preflight.check_video(info, platform))

    for finding in findings:
        marker = "ERROR  " if finding.level == epmeta.ERROR else "WARNING"
        print(f"{marker} {finding.rule_id}  {finding.message}")
    print(f"元数据 {meta.path}；{len(findings)} 个问题")
    if any(f.level == epmeta.ERROR for f in findings):
        sys.stdout.flush()
        print("FAIL 有硬约束违规，发布前必须改", file=sys.stderr)
        return 1
    print("OK 发布前检查通过")
    return 0


def _cmd_bgm_windows(args: argparse.Namespace) -> int:
    """挑（或重挑）系列片头片尾的配乐窗口。

    窗口是**决策**，所以入库；音频才是产物。
    """
    from pyv import bgm

    music = args.music
    track_id = ""
    track_sha = ""
    if music is None:
        entries = bgm.load_library()
        motif = next((e for e in entries if e.series_role == "motif"), None)
        if motif is None:
            print("台账里没有 series_role=motif 的曲子", file=sys.stderr)
            return 1
        music = str(bgm.AIV_ROOT / motif.local_path)
        track_id = motif.id
        track_sha = motif.sha256
    else:
        entries = bgm.load_library()
        for entry in entries:
            if entry.local_path and str(bgm.AIV_ROOT / entry.local_path) == str(
                    Path(music).resolve()):
                track_id = entry.id
                track_sha = entry.sha256
                break

    windows = bgm.pick_brand_windows(
        music, track_id=track_id, track_sha256=track_sha)
    target = bgm.save_brand_windows(windows, args.out)
    print(f"片头 {windows.intro_start_s:.3f}~{windows.intro_end_s:.3f}s / "
          f"片尾 {windows.outro_start_s:.3f}~{windows.outro_end_s:.3f}s"
          f"（起音比 {windows.onset_ratio:.2f}）")
    print(f"→ {target}")
    findings = bgm.check_brand_windows(windows, music)
    for finding in findings:
        print(f"{finding.level.upper():7} {finding}")
    return 1 if any(f.level == bgm.ERROR for f in findings) else 0


def _mix_body_range(args: argparse.Namespace) -> tuple[float, float]:
    """正文区间：优先从 storyboard 取，和 compose 用的是同一段。"""
    if getattr(args, "storyboard", None):
        from pyv import compose
        from pyv.timeline import Storyboard

        storyboard = Storyboard.load(args.storyboard)
        return compose._body_range(storyboard)
    if args.body_start is None or args.body_end is None:
        raise SystemExit("要么给 --storyboard，要么给 --body-start 和 --body-end")
    return args.body_start, args.body_end


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

    p_topics = sub.add_parser("topics")
    topics_sub = p_topics.add_subparsers(dest="topics_command", required=True)

    p_topics_check = topics_sub.add_parser("check")
    p_topics_check.add_argument("--library", default=None,
                                help="选题库文件，默认 aiv/选题库.md")
    p_topics_check.set_defaults(func=cmd_topics)

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

    p_bgm_verify = bgm_sub.add_parser("verify")
    p_bgm_verify.add_argument("--video", required=True, help="成片文件")
    p_bgm_verify.add_argument("--narration", required=True, help="旁白文件")
    p_bgm_verify.add_argument("--music", required=True, help="BGM 母带")
    p_bgm_verify.add_argument("--storyboard", default=None,
                              help="正文区间从这里取（与 compose 同一段）")
    p_bgm_verify.add_argument("--body-start", type=float, default=None)
    p_bgm_verify.add_argument("--body-end", type=float, default=None)
    p_bgm_verify.set_defaults(func=cmd_bgm)

    # 系列片头片尾的配乐窗口：挑窗口 / 查窗口
    p_bgm_windows = bgm_sub.add_parser("windows")
    p_bgm_windows.add_argument("--music", default=None,
                               help="motif 音频，默认取台账里 series_role=motif 的那条")
    p_bgm_windows.add_argument("--out", default=None,
                               help="窗口文件，默认 brand/brand_windows.json")
    p_bgm_windows.set_defaults(func=cmd_bgm)

    p_bgm_brand = bgm_sub.add_parser("brand-check")
    p_bgm_brand.add_argument("--windows", default=None,
                             help="窗口文件，默认 brand/brand_windows.json")
    p_bgm_brand.add_argument("--music", default=None,
                             help="motif 音频，默认取台账里 series_role=motif 的那条")
    p_bgm_brand.set_defaults(func=cmd_bgm)

    p_publish = sub.add_parser("publish")
    publish_sub = p_publish.add_subparsers(dest="publish_command", required=True)

    p_publish_check = publish_sub.add_parser("check")
    p_publish_check.add_argument("--episode", required=True)
    p_publish_check.set_defaults(func=cmd_publish)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
