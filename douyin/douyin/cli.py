"""抖音 adapter 的命令行入口。

    python -m douyin.cli package <期号>
    python -m douyin.cli status <期号>
    python -m douyin.cli mark published <期号> --url <链接>
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pyv import epmeta

from douyin import notify, package, snapshot, state

AIV_ROOT = Path(__file__).resolve().parents[2] / "aiv"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "out"
WEBHOOK_ENV = "DOUYIN_WEBHOOK"


def _video_path(episode: str) -> Path:
    return AIV_ROOT / "out" / f"{episode}.mp4"


def _title_of(meta) -> str:
    return (meta.platform("douyin") or {}).get("title", meta.title)


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
        result = package.build_package(args.episode, meta, video, args.out,
                                       outbox_dir=args.outbox)
    except package.PackageError as error:
        for finding in error.findings:
            print(f"ERROR  {finding.rule_id}  {finding.message}", file=sys.stderr)
        print("FAIL 预检没过，不出包", file=sys.stderr)
        return 1
    except epmeta.MetaError as error:
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
    print(f"通知措辞：{notify.phrase(current.status)}")
    return 0


def cmd_mark(args: argparse.Namespace) -> int:
    """回填状态。

    抖音这一档只有 `published` 一档：抖音创作者后台的草稿能力没核实过，
    不设一个没验证过的档位（规格 §6.6.1）。
    """
    if not args.url:
        print("ERROR published 需要 --url（公开链接）", file=sys.stderr)
        return 1

    store = state.StateStore(Path(args.out) / "state.json")
    current = store.get(args.episode)
    target = Path(args.out) / args.episode

    current.status = "published"
    current.published_url = args.url
    try:
        package.mark_published(target, args.url)
    except FileNotFoundError as error:
        print(f"WARNING {error}", file=sys.stderr)
    reason = "人工发布后回填"

    store.save(args.episode, current)

    meta = epmeta.load_meta(args.episode)
    title = _title_of(meta)

    outbox = Path(args.outbox) if args.outbox else snapshot.OUTBOX_DIR
    snapshot.write_snapshot(
        outbox / f"{args.episode}__douyin.json",
        episode=args.episode, status="published", title=title,
        # 相对路径：快照要入库，绝对路径换台机器就对不上
        package_dir=package.repo_relative(target), published_url=args.url,
        reason=reason,
    )
    notify.notify(args.episode, "published", title, str(target),
                  os.environ.get(WEBHOOK_ENV))
    print(f"OK {args.episode} 已回填发布链接")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="douyin")
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
    p_mark.add_argument("state", choices=["published"],
                        help="published=已发表（要 --url）")
    p_mark.add_argument("episode")
    p_mark.add_argument("--url", default=None, help="公开链接，published 档必填")
    p_mark.add_argument("--out", default=str(DEFAULT_OUT))
    p_mark.add_argument("--outbox", default=None,
                        help="状态快照目录，默认 publish/outbox")
    p_mark.set_defaults(func=cmd_mark)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
