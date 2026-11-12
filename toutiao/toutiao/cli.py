"""Command line entry point for the Toutiao adapter.

    scan              list the corpus and what can go to Toutiao
    convert <slug>   slice one post and write the publish package
    publish <slug>   package it, and upload once the API permission exists
    status            show the recorded state of every article

Every path these commands touch can be pointed somewhere else --
``--posts-dir``, ``--out-dir``, ``--outbox-dir``, ``--state-file`` -- so a
run never has to write into the repository.  The shared options work on
either side of the command name.

Two things this module refuses to do quietly:

- a corrupt state file is announced on stderr and turns the exit code
  into ``EXIT_ERROR``.  An unreadable state reads as "nothing was ever
  published", and that is exactly how an article gets published twice;
- a post that cannot go to Toutiao says why and exits with
  ``EXIT_INELIGIBLE`` instead of exiting successfully with nothing done.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .capability import default_capability_path, load_capability
from .contract import slice_post
from .mdparse import discover, discover_unsupported, load_post
from .notify import build_message, send
from .publish import PackageResult, write_package, write_snapshot
from .state import StateStore, fingerprint, needs_publish

__all__ = [
    "EXIT_ERROR", "EXIT_INELIGIBLE", "EXIT_OK", "EXIT_USAGE", "main",
]

#: The exit codes are the contract with whoever runs the command:
#: ``0`` success, ``1`` a bad argument or a bad configuration, ``2`` this
#: post is not eligible for Toutiao, ``3`` an interface, a write or a
#: source-parsing error.
EXIT_OK = 0
EXIT_USAGE = 1
EXIT_INELIGIBLE = 2
EXIT_ERROR = 3

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POSTS_DIR = _REPO_ROOT / "source" / "_posts"
DEFAULT_OUT_DIR = _REPO_ROOT / "toutiao" / "out"
DEFAULT_OUTBOX_DIR = _REPO_ROOT / "publish" / "outbox"
DEFAULT_CAPABILITY = default_capability_path()
DEFAULT_STATE_FILE = _REPO_ROOT / "toutiao" / "out" / "state.json"

#: The value of every shared option when it was not given.  The options
#: are attached to the top-level parser *and* to every subcommand, so
#: they work before the command name as well as after it; argparse's
#: ``SUPPRESS`` keeps an option that was not given out of the namespace
#: entirely, because otherwise the subcommand's own default would
#: overwrite the value that was given before the command name.
_DEFAULTS = {
    "posts_dir": DEFAULT_POSTS_DIR,
    "out_dir": DEFAULT_OUT_DIR,
    "outbox_dir": DEFAULT_OUTBOX_DIR,
    "capability": DEFAULT_CAPABILITY,
    "state_file": DEFAULT_STATE_FILE,
    "source_url": "https://growdu.cn",
    "notify": "",
    "notify_key": "",
}

#: What each recorded status means.  ``drafted`` is the one that gets
#: misread: it means a draft exists on the platform and a human still has
#: to publish it -- not that the article was never sent.
_STATUS_TEXT = {
    "packaged": "packaged（待人工上传）",
    "drafted": "drafted（待人工发表）",
    "published": "published（已发布）",
}


class _ConfigError(Exception):
    """A configuration problem: a bad argument or a bad declaration.

    It is a separate type so that ``main()`` can tell it apart from a
    failure that happened while doing the work, and answer with the
    matching exit code.
    """


def _capability(path: Path):
    """Load the platform declaration, or refuse it as a configuration error.

    The declaration is configuration, not content: a broken TOML file is
    the exit code for a bad configuration (``EXIT_USAGE``), not the exit
    code for a broken post.
    """
    try:
        return load_capability(path)
    except (OSError, ValueError) as error:
        raise _ConfigError("能力声明读取失败：{}".format(error)) from error


def _inside(path: Path, root: Path) -> bool:
    """Is ``path`` inside ``root``?

    Used to keep a slug from pointing out of the posts directory: the
    command reads files, and it should only read the ones it was pointed
    at.
    """
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _resolve_post(posts_dir: Path, slug: str):
    """Find one post by slug, tolerating a missing ``.md``.

    The slug is a path inside the site (``db/postgresql/demo``).  A slug
    that points outside the posts directory is not followed.
    """
    posts_dir = Path(posts_dir)
    if not posts_dir.is_dir():
        raise FileNotFoundError(
            "找不到 {}。先跑 `python3 tools/sync-hexo.py`（约 3 分钟）。".format(posts_dir)
        )
    direct = posts_dir / (slug + ".md")
    if not _inside(direct, posts_dir):
        return None
    if direct.is_file():
        return load_post(direct, posts_dir)
    matches = sorted(posts_dir.rglob(slug + ".md"))
    if matches:
        return load_post(matches[0], posts_dir)
    return None


def _report_quarantine(store: StateStore) -> bool:
    """Announce that the state file was broken and has been set aside.

    Returns ``True`` when a broken file was found.  A corrupt state file
    reads as "nothing was ever published" unless somebody says so, and
    that is how an article gets published twice: the run has to announce
    it, and the exit code has to say the run was not clean.
    """
    if store.quarantined is None:
        return False
    print(
        "状态文件损坏，已隔离到 {}，本次按空状态处理，"
        "发过的文章可能被再发一遍，请人工核对".format(store.quarantined),
        file=sys.stderr,
    )
    return True


def cmd_scan(args) -> int:
    """List the corpus and say which posts can go to Toutiao."""
    capability = _capability(args.capability)
    try:
        posts = discover(args.posts_dir)
    except FileNotFoundError as error:
        # 目录不存在：错误消息里已经带了「先跑 tools/sync-hexo.py」的指引。
        print("扫描失败：{}".format(error), file=sys.stderr)
        return EXIT_USAGE
    except ValueError as error:
        # 母稿坏掉（front matter 没闭合）：消息里带着出错的文件路径。
        print("扫描失败：{}".format(error), file=sys.stderr)
        return EXIT_ERROR
    ok = 0
    print("共 {} 篇\n".format(len(posts)))
    for post in posts:
        result = slice_post(post, capability.limits, args.source_url)
        if result.article is None:
            print("  ✗ {} —— {}".format(post.title, result.reason))
            continue
        notes = "；".join(result.article.notes)
        print("  ✓ {}{}".format(
            result.article.title,
            "（{}）".format(notes) if notes else "",
        ))
        ok += 1
    print("\n可发 {} / {} 篇".format(ok, len(posts)))

    # 母稿格式不支持的文件要显式说出来，不能静默漏掉。
    unsupported = discover_unsupported(args.posts_dir)
    if unsupported:
        print("\n另有 {} 个母稿格式不支持，已跳过：".format(len(unsupported)))
        for path in unsupported:
            print("  - {}".format(path))
    return EXIT_OK


def _convert(args) -> tuple:
    """Slice one post and write the package.  Returns ``(code, package)``.

    The package is ``None`` when there was nothing to package: the post
    does not exist, does not qualify, or is already packaged unchanged.
    """
    capability = _capability(args.capability)
    post = _resolve_post(args.posts_dir, args.slug)
    if post is None:
        print("找不到文章: {}".format(args.slug), file=sys.stderr)
        return EXIT_USAGE, None

    result = slice_post(post, capability.limits, args.source_url)
    if result.article is None:
        print("不能发到头条号：{}".format(result.reason), file=sys.stderr)
        return EXIT_INELIGIBLE, None

    # The fingerprint covers the Toutiao version, not the source post: only
    # a change in what actually gets published matters here.
    fp = fingerprint(result.article.body)
    store = StateStore(args.state_file)
    state = store.get(result.article.content_id)
    # 状态文件坏掉了：先说出来，再往下走。这一次的空状态不可信。
    broken = _report_quarantine(store)
    if not needs_publish(fp, state):
        print("内容未变，已有同样的发布包：{}".format(state.updated_at))
        return EXIT_OK, None

    try:
        package = write_package(
            result.article, capability, args.out_dir, args.posts_dir, args.source_url
        )
    except ValueError as error:
        print("不能发到头条号：{}".format(error), file=sys.stderr)
        return EXIT_INELIGIBLE, None

    snapshot = write_snapshot(package, args.outbox_dir)

    state.fingerprint = fp
    state.status = package.status
    state.package_dir = str(package.package_dir)
    store.save(result.article.content_id, state)

    print("标题：{}".format(package.title))
    print("字数：{}（上限 {}）".format(len(result.article.body), capability.limits.body_chars))
    print("图片：{} 张".format(len(result.article.images)))
    print("发布包：{}".format(package.package_dir))
    print("状态快照：{}".format(snapshot))
    for note in result.article.notes:
        print("  ! {}".format(note))
    # 出包本身成功了，但状态文件坏过：这次运行不算干净。
    return (EXIT_ERROR if broken else EXIT_OK), package


def cmd_convert(args) -> int:
    """Slice one post and write the package; nothing is uploaded."""
    code, _package = _convert(args)
    return code


def cmd_publish(args) -> int:
    """Package one post and notify about it.

    The API permission is not available yet, so this is the manual path.
    The distinction matters: the notification must say "待上传", not "已发布".
    """
    code, package = _convert(args)
    if package is None:
        # 没有出包：原因已经说过了，退出码也已经带上了。
        return code
    if args.notify and not args.notify_key:
        print(
            "指定了通知通道 {} 但没有通知凭据（--notify-key），没有发通知".format(
                args.notify
            ),
            file=sys.stderr,
        )
    elif args.notify:
        subject, body = build_message(
            "packaged",
            package.title,
            detail="发布包：{}".format(package.package_dir),
        )
        try:
            send(args.notify, args.notify_key, subject, body)
        except Exception as error:                  # noqa: BLE001 -- 通知失败不影响发布结果
            print("通知失败（不影响发布结果）：{}".format(error), file=sys.stderr)
    return code


def cmd_status(args) -> int:
    """Show the recorded state of every article."""
    store = StateStore(args.state_file)
    articles = store.all()
    if _report_quarantine(store):
        # 状态文件坏掉时的空状态是不可信的：说清楚，别让它读成「没发过」。
        print("状态文件损坏，本次按空状态处理，没有可显示的记录（详情见 stderr）")
        return EXIT_ERROR
    if not articles:
        print("还没有发过任何文章")
        return EXIT_OK
    for content_id in sorted(articles):
        entry = articles[content_id]
        status = entry.get("status") or "-"
        print("  {}  {}  {}".format(
            content_id,
            _STATUS_TEXT.get(status, status),
            entry.get("published_url") or entry.get("package_dir") or "",
        ))
    return EXIT_OK


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    """Attach the options every command shares.

    ``default=argparse.SUPPRESS`` is what makes the option work on
    either side of the command name: an option that was not given stays
    out of the namespace, so the subcommand's default cannot overwrite
    the value that was given before the command name.
    """
    parser.add_argument("--posts-dir", type=Path, default=argparse.SUPPRESS,
                        help="母稿目录（默认：source/_posts）")
    parser.add_argument("--out-dir", type=Path, default=argparse.SUPPRESS,
                        help="发布包目录（默认：toutiao/out）")
    parser.add_argument("--outbox-dir", type=Path, default=argparse.SUPPRESS,
                        help="状态快照目录（默认：publish/outbox）")
    parser.add_argument("--capability", type=Path, default=argparse.SUPPRESS,
                        help="平台能力声明（默认：publish/capabilities/toutiao.toml）")
    parser.add_argument("--state-file", type=Path, default=argparse.SUPPRESS,
                        help="幂等状态文件（默认：toutiao/out/state.json）")
    parser.add_argument("--source-url", default=argparse.SUPPRESS,
                        help="正文末尾署名的站点地址")
    parser.add_argument("--notify", default=argparse.SUPPRESS,
                        help="通知通道：serverchan / wechat_work / webhook")
    parser.add_argument("--notify-key", default=argparse.SUPPRESS,
                        help="通知凭据")


def build_parser() -> argparse.ArgumentParser:
    """The argument parser, with the shared options on both sides."""
    parser = argparse.ArgumentParser(
        prog="toutiao", description="博客到头条号的切片与发布"
    )
    _add_common_options(parser)

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan", help="盘点：哪些文章能发到头条号",
                   parents=[_common_parser()]).set_defaults(func=cmd_scan)

    convert = sub.add_parser("convert", help="切片并产出发布包（不调接口）",
                             parents=[_common_parser()])
    convert.add_argument("slug")
    convert.set_defaults(func=cmd_convert)

    publish = sub.add_parser("publish", help="产出发布包（API 权限开通后才会真正上传）",
                             parents=[_common_parser()])
    publish.add_argument("slug")
    publish.set_defaults(func=cmd_publish)

    sub.add_parser("status", help="查看状态",
                   parents=[_common_parser()]).set_defaults(func=cmd_status)
    return parser


def _common_parser() -> argparse.ArgumentParser:
    """A parser holding the shared options, for a subcommand to inherit."""
    common = argparse.ArgumentParser(add_help=False)
    _add_common_options(common)
    return common


def _fill_defaults(namespace: argparse.Namespace) -> None:
    """Put the default value in for every shared option that was not given."""
    for name, value in _DEFAULTS.items():
        if not hasattr(namespace, name):
            setattr(namespace, name, value)


def main(argv=None) -> int:
    """Run one command and return its exit code."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        # argparse 已经把用法和错误打印出来了。``--help`` 退出码是 0，
        # 其余都是用法错误 —— 本命令约定用法错误是 1。
        return EXIT_OK if error.code == 0 else EXIT_USAGE
    _fill_defaults(args)
    try:
        return args.func(args)
    except _ConfigError as error:
        print(str(error), file=sys.stderr)
        return EXIT_USAGE
    except FileNotFoundError as error:
        print(str(error), file=sys.stderr)
        return EXIT_USAGE
    except Exception as error:                      # noqa: BLE001 -- 错误不吞
        print("失败：{}".format(error), file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
