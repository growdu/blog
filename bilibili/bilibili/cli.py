"""B站 adapter 的命令行入口。

    python -m bilibili.cli package <期号>
    python -m bilibili.cli status <期号>
    python -m bilibili.cli mark published <期号> --url <链接>

只做「把包准备好」这一件事。发布在人工手里（`manual` 档）——
真发出去之后用 `mark published` 回填链接，状态与快照才跟着变成 `published`。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pyv import epmeta

from bilibili import notify, package, snapshot, state, subtitle

AIV_ROOT = Path(__file__).resolve().parents[2] / "aiv"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "out"
WEBHOOK_ENV = "BILIBILI_WEBHOOK"


def _video_path(episode: str) -> Path:
    return AIV_ROOT / "out" / f"{episode}.mp4"


def _storyboard_path(episode: str) -> Path:
    return AIV_ROOT / f"storyboard_{episode}.json"


def _title_of(meta) -> str:
    return (meta.platform("bilibili") or {}).get("title", meta.title)


def _subtitle_events(episode: str):
    """读 storyboard，取字幕事件。

    **没有就返回空列表**，不是报错：字幕是加分项，
    没有字幕的片子照样能发（只是没字幕轨）。

    这里不 import `pyv.timeline`——adapter 只 import `epmeta` 与 `preflight`
    （规格 §3.3）。storyboard 是本机产物，读它不违反「只读元数据与能力声明」，
    因为它不是另一个平台的接口。
    """
    path = _storyboard_path(episode)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"WARNING 读不到 storyboard：{path}（{error}），这一期不出字幕",
              file=sys.stderr)
        return []
    return subtitle.events_from_storyboard(raw)


def cmd_package(args: argparse.Namespace) -> int:
    try:
        meta = epmeta.load_meta(args.episode)
    except epmeta.MetaError as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 1

    video = Path(args.video) if args.video else _video_path(args.episode)
    if not video.is_file():
        print(f"ERROR 成片不存在：{video}（先跑 make all 出片）", file=sys.stderr)
        return 1

    try:
        result = package.build_package(
            args.episode, meta, video, args.out,
            subtitle_events=_subtitle_events(args.episode),
            outbox_dir=args.outbox)
    except package.PackageError as error:
        for finding in error.findings:
            print(f"ERROR  {finding.rule_id}  {finding.message}", file=sys.stderr)
        print("FAIL 预检没过，不出包", file=sys.stderr)
        return 1
    except epmeta.MetaError as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 1
    except FileNotFoundError as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 1

    for warning in result.warnings:
        print(f"WARNING {warning}")
    notify.notify(args.episode, result.status, _title_of(meta),
                  str(result.dir), os.environ.get(WEBHOOK_ENV))
    print(f"OK 发布包 → {result.dir}"
          + ("（成片没变，复用已有的包）" if result.reused else ""))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    store = state.StateStore(Path(args.out) / "state.json")
    current = store.get(args.episode)
    print(f"{args.episode}  状态 {current.status}  "
          f"链接 {current.published_url or '（未回填）'}")
    if current.resource_id:
        print(f"稿件 {current.resource_id}"
              + (f"  审核态 {current.archive_state}" if current.archive_state is not None else ""))
    if current.reject_reason:
        print(f"驳回原因 {current.reject_reason}")
    print(f"通知措辞：{notify.phrase(current.status)}")
    return 0


def cmd_mark(args: argparse.Namespace) -> int:
    """回填发布状态。

    **两个状态的区别不能混。**
    `drafted` = 视频已存进B站 的**草稿箱**，还没公开；
    `published` = 已经公开出去，有链接了。
    标成 `published` 必须给 `--url`——没有链接就不该说「已发布」。

    **先做完会失败的事，再落状态。** 顺序反了就会留下假的「已发布」：
    状态文件写着已发布、快照也写了链接，而发布包根本不存在——
    下一个人照着快照去找，找不到任何东西。
    """
    if args.state == "published" and not args.url:
        print("ERROR 标成 published 必须给 --url——"
              "没有公开链接就不该说「已发布」。", file=sys.stderr)
        return 2

    # 1. 元数据：读不到就退出（这一期压根没配 B站文案）
    try:
        meta = epmeta.load_meta(args.episode)
    except epmeta.MetaError as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 1
    title = _title_of(meta)

    # 2. 发布包：没有包就没有「发出去的是哪一版」——不许回填
    target = Path(args.out) / args.episode
    try:
        if args.state == "published":
            package.mark_published(target, args.url)
        else:
            # B站这一档没有「草稿」要写进包里的 meta.json，
            # 但包**必须在**：草稿是拿这个包投出去的。
            if not (target / "meta.json").is_file():
                raise FileNotFoundError(f"发布包不存在：{target}")
    except FileNotFoundError as error:
        print(f"ERROR {error}", file=sys.stderr)
        print("      没有发布包就回填不了：先出包，再投稿，再回填"
              f"（python -m bilibili.cli package {args.episode}）",
              file=sys.stderr)
        return 1

    # 3. 到这儿才算成了：状态与快照一起落
    store = state.StateStore(Path(args.out) / "state.json")
    current = store.get(args.episode)
    current.status = args.state
    if args.state == "published":
        current.published_url = args.url
    store.save(args.episode, current)

    outbox = Path(args.outbox) if args.outbox else snapshot.OUTBOX_DIR
    reason = ("人工发布后回填" if args.state == "published"
              else "已存草稿，未投稿")
    snapshot.write_snapshot(
        outbox / f"{args.episode}__bilibili.json",
        episode=args.episode, status=args.state, title=title,
        # 相对路径：快照要入库，绝对路径换台机器就对不上
        package_dir=package.repo_relative(target),
        published_url=current.published_url,
        reason=reason,
    )
    notify.notify(args.episode, args.state, title, str(target),
                  os.environ.get(WEBHOOK_ENV))
    if args.state == "published":
        print(f"OK {args.episode} 已回填发布链接")
    else:
        print(f"OK {args.episode} 已标成「{args.state}」（还没公开）")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bilibili")
    sub = parser.add_subparsers(dest="command", required=True)

    p_package = sub.add_parser("package")
    p_package.add_argument("episode")
    p_package.add_argument("--video", default=None, help="成片路径，默认 aiv/out/<期号>.mp4")
    p_package.add_argument("--out", default=str(DEFAULT_OUT))
    p_package.add_argument("--outbox", default=None,
                           help="状态快照目录，默认 publish/outbox")
    p_package.set_defaults(func=cmd_package)

    p_status = sub.add_parser("status")
    p_status.add_argument("episode")
    p_status.add_argument("--out", default=str(DEFAULT_OUT))
    p_status.set_defaults(func=cmd_status)

    p_mark = sub.add_parser("mark")
    p_mark.add_argument("state", choices=["drafted", "published"])
    p_mark.add_argument("episode")
    p_mark.add_argument("--url", default=None,
                        help="公开链接；标 published 时必填")
    p_mark.add_argument("--out", default=str(DEFAULT_OUT))
    p_mark.add_argument("--outbox", default=None,
                        help="状态快照目录，默认 publish/outbox")
    p_mark.set_defaults(func=cmd_mark)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
