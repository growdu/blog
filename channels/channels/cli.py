"""视频号 adapter 的命令行入口。

    python -m channels.cli package <期号>
    python -m channels.cli status <期号>
    python -m channels.cli mark published <期号> --url <链接>
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pyv import epmeta

from channels import notify, package, snapshot, state

AIV_ROOT = Path(__file__).resolve().parents[2] / "aiv"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "out"
WEBHOOK_ENV = "CHANNELS_WEBHOOK"


def _video_path(episode: str) -> Path:
    return AIV_ROOT / "out" / f"{episode}.mp4"


def _title_of(meta) -> str:
    return (meta.platform("channels") or {}).get("title", meta.title)


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
    except FileNotFoundError as error:
        # 成片在预检之后没了（被人删了、路径写错了）：报错，别把 traceback
        # 甩到终端上——那看着像崩溃，不像「这一条没出包」。
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

    两个档：
    - `drafted`：草稿已存在平台上（视频号没有公开发布接口，人工点「保存草稿」后回填）；
    - `published`：已发表，带公开链接。

    **先做完会失败的事，再落状态。** 顺序反了就会留下假的「已发布」：
    状态文件写着已发布、快照也写了链接，而发布包根本不存在——
    下一个人照着快照去找，找不到任何东西。
    """
    if args.state == "published" and not args.url:
        print("ERROR published 需要 --url（公开链接）", file=sys.stderr)
        return 1

    # 1. 元数据：读不到就退出（这一期压根没配视频号文案）
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
            package.mark_drafted(target)
    except FileNotFoundError as error:
        print(f"ERROR {error}", file=sys.stderr)
        print("      没有发布包就回填不了：先出包，再上传，再回填"
              f"（python -m channels.cli package {args.episode}）",
              file=sys.stderr)
        return 1

    # 3. 到这儿才算成了：状态与快照一起落
    store = state.StateStore(Path(args.out) / "state.json")
    current = store.get(args.episode)
    current.status = args.state
    if args.state == "published":
        current.published_url = args.url
        reason = "人工发布后回填"
        published_url = args.url
        summary = "已回填发布链接"
    else:
        # 草稿还没发出去：链接必须清空，
        # 留着旧链接会让人以为这条已经发出去了。
        current.published_url = None
        reason = "已存草稿，待人工发表"
        published_url = None
        summary = "已回填草稿状态"
    store.save(args.episode, current)

    outbox = Path(args.outbox) if args.outbox else snapshot.OUTBOX_DIR
    snapshot.write_snapshot(
        outbox / f"{args.episode}__channels.json",
        episode=args.episode, status=args.state, title=title,
        # 相对路径：快照要入库，绝对路径换台机器就对不上
        package_dir=package.repo_relative(target), published_url=published_url,
        reason=reason,
    )
    notify.notify(args.episode, args.state, title, str(target),
                  os.environ.get(WEBHOOK_ENV))
    print(f"OK {args.episode} {summary}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="channels")
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
    p_mark.add_argument("state", choices=["published", "drafted"],
                        help="published=已发表（要 --url）；drafted=已存草稿，待人工发表")
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
