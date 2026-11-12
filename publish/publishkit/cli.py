"""调度层的命令行入口（``publish/spec/06-发布计划与调度.md`` §8）。

四条命令：

.. code-block:: bash

    python3 -m publishkit.cli schedule weekly [--dry-run]
    python3 -m publishkit.cli schedule status
    python3 -m publishkit.cli schedule candidates [--platform <id>]
    python3 -m publishkit.cli publish <content_id> --platform <id> [--publish]

**怎么跑**：``publish/`` 本身不是 Python 包，``publishkit`` 挂在它下面，
所以要么进到那个目录去，要么把 ``publish/`` 放进 ``PYTHONPATH``：

.. code-block:: bash

    cd publish && python3 -m publishkit.cli schedule weekly
    PYTHONPATH=publish python3 -m publishkit.cli schedule weekly

**退出码沿用 adapter 的约定**（``toutiao/toutiao/cli.py`` 那一套）：

===  ==========================================
0    成功
1    参数或配置错误
2    这一篇不合格
3    接口或写盘错误
===  ==========================================

**调度器只做调度**：选内容、写周键、记失败。它**不 import 任何平台
adapter 的模块**（§11.1）——平台怎么发，由 ``publish/capabilities/*.toml``
的 ``[adapter].command`` 决定，调度器只把那条命令调起来。

这一期只驱动文档类平台（能力模型里 ``kind == "document"``）。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from . import PublishKitError
from .capability import load_capability
from .schedule import (
    PUBLISHED_STATUSES,
    ScheduleConfig,
    ScheduleConfigError,
    ScheduleError,
    ScheduleIneligibleError,
    SchedulePublishError,
    ScheduleState,
    discover_units,
    load_outbox_index,
    resolve_config,
    run_weekly,
    snapshot_name,
    target_platforms,
    week_key,
)

__all__ = [
    "EXIT_ERROR",
    "EXIT_INELIGIBLE",
    "EXIT_OK",
    "EXIT_USAGE",
    "main",
]

#: 退出码是与调用方的约定（与 ``toutiao/toutiao/cli.py`` 同一套）。
EXIT_OK = 0
EXIT_USAGE = 1
EXIT_INELIGIBLE = 2
EXIT_ERROR = 3

#: 调 adapter 的默认超时（秒）。超时不等于失败（§7.1 第三条），
#: 但也不能无限等下去。
DEFAULT_ADAPTER_TIMEOUT = 300

#: 自动重试的次数上限（§7.2「超过上限（比如 3 次）转人工」）。
MAX_RETRY_ATTEMPTS = 3

#: 平台审核不通过的迹象（§7.1 第二条：审核不通过不自动重试，转人工）。
#:
#: adapter 的 CLI 契约只有退出码，没有结构化的错误码，所以只能从它的输出里
#: 认这几个词。认错了的后果是「多试一次」，比「少试一次」轻。
_REVIEW_MARKERS = (
    "审核",
    "驳回",
    "拒绝",
    "reject",
    "review_status",
    "publish_status",
)


class _Parser(argparse.ArgumentParser):
    """参数错了退出码是 1（不是 argparse 默认的 2）。

    2 在这一层的约定里是「这一篇不合格」，参数写错与「不合格」是两回事，
    不能共用一个退出码。
    """

    def error(self, message):
        self.print_usage(sys.stderr)
        print("参数错误：{}".format(message), file=sys.stderr)
        raise SystemExit(EXIT_USAGE)


@dataclass(frozen=True)
class AdapterResult:
    """调一次 adapter 的结果。"""

    code: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


def _common_options() -> argparse.ArgumentParser:
    """四个命令都能用的选项。

    每一个都能把写盘的位置指到别处——测试绝不许写进仓库。
    用了 ``SUPPRESS``：没给的选项不进命名空间，所以「命令行在前、
    子命令在后」两种写法都能用，而且子命令不会用默认值覆盖前面给过的值。
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--repo-root",
        metavar="路径",
        default=argparse.SUPPRESS,
        help="仓库根路径（默认：环境变量 PUBLISH_REPO，或从当前目录往上找）",
    )
    parser.add_argument(
        "--state-dir",
        metavar="路径",
        default=argparse.SUPPRESS,
        help="状态目录（默认：环境变量 PUBLISH_STATE_DIR，或 <仓库>/publish）",
    )
    parser.add_argument(
        "--posts-dir",
        metavar="路径",
        default=argparse.SUPPRESS,
        help="内容单元目录（默认：<仓库>/source/_posts）",
    )
    parser.add_argument(
        "--outbox-dir",
        metavar="路径",
        default=argparse.SUPPRESS,
        help="outbox 目录（默认：<状态目录>/outbox）",
    )
    parser.add_argument(
        "--schedule-file",
        metavar="路径",
        default=argparse.SUPPRESS,
        help="调度状态文件（默认：<状态目录>/schedule.json）",
    )
    parser.add_argument(
        "--capabilities-dir",
        metavar="路径",
        default=argparse.SUPPRESS,
        help="能力声明目录（默认：<仓库>/publish/capabilities）",
    )
    parser.add_argument(
        "--secrets",
        metavar="路径",
        default=argparse.SUPPRESS,
        help="凭据文件（默认：环境变量 PUBLISH_SECRETS，或 <仓库>/weixin/secrets.json）",
    )
    parser.add_argument(
        "--adapter-timeout",
        metavar="秒",
        type=float,
        default=argparse.SUPPRESS,
        help="调 adapter 的超时秒数（默认：{}）".format(DEFAULT_ADAPTER_TIMEOUT),
    )
    return parser


def build_parser() -> argparse.ArgumentParser:
    """搭出命令行。"""
    common = _common_options()
    parser = _Parser(
        prog="python3 -m publishkit.cli",
        description="发布调度层：选内容、记状态、调平台 adapter。",
        parents=[common],
    )
    commands = parser.add_subparsers(dest="command", metavar="命令")
    commands.required = True

    schedule = commands.add_parser(
        "schedule", help="定时路径", parents=[common]
    )
    schedule_commands = schedule.add_subparsers(dest="schedule_command", metavar="子命令")
    schedule_commands.required = True

    weekly = schedule_commands.add_parser(
        "weekly",
        parents=[common],
        help="跑一次例行发布",
        description="跑一次例行发布（周键幂等，见 06 规格 §4.2）。",
    )
    weekly.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将要做什么：不写 outbox、不调 adapter、不写周键",
    )
    weekly.add_argument("--platform", metavar="id", help="只驱动这一个平台")
    weekly.set_defaults(func=cmd_schedule_weekly)

    status = schedule_commands.add_parser(
        "status",
        parents=[common],
        help="看本周发了什么、哪些待重试、哪些待人工",
    )
    status.set_defaults(func=cmd_schedule_status)

    candidates = schedule_commands.add_parser(
        "candidates",
        parents=[common],
        help="列出候选集",
    )
    candidates.add_argument("--platform", metavar="id", help="只看这一个平台的候选集")
    candidates.set_defaults(func=cmd_schedule_candidates)

    publish = commands.add_parser(
        "publish",
        parents=[common],
        help="主动路径：发指定内容到指定平台",
        description=(
            "主动发布：指定 content_id 与平台。"
            "**不写周键**（06 规格 §4.2 规则 3）——"
            "主动发的那篇会出现在 outbox 里，下次定时选题时它会被"
            "「已发过」规则剔除。"
        ),
    )
    publish.add_argument("content_id", help="内容单元 id（相对 source/_posts/ 的路径，去掉 .md）")
    publish.add_argument("--platform", metavar="id", required=True, help="目标平台 id")
    publish.add_argument(
        "--publish",
        action="store_true",
        help="真的发（不加这个选项只预览，什么都不做）",
    )
    publish.set_defaults(func=cmd_publish)

    return parser


def _config_from_args(args) -> ScheduleConfig:
    """把命令行选项与环境变量合成一份配置。"""
    return resolve_config(
        repo_root=getattr(args, "repo_root", None),
        state_dir=getattr(args, "state_dir", None),
        posts_dir=getattr(args, "posts_dir", None),
        outbox_dir=getattr(args, "outbox_dir", None),
        capabilities_dir=getattr(args, "capabilities_dir", None),
        schedule_file=getattr(args, "schedule_file", None),
        secrets=getattr(args, "secrets", None),
    )


def _timeout_from_args(args) -> float:
    value = getattr(args, "adapter_timeout", None)
    return DEFAULT_ADAPTER_TIMEOUT if value is None else float(value)


# --- 调 adapter -----------------------------------------------------------


def invoke_adapter(config: ScheduleConfig, capability, content_id: str, timeout: float):
    """调平台 adapter 的 CLI。

    命令是 ``<adapter_command...> publish <content_id>``，**cwd 必须是
    ``<仓库>/<adapter 包名>``**：adapter 的包目录是 ``repo/toutiao/toutiao/``，
    ``python3 -m toutiao.cli`` 要靠 cwd 在 ``sys.path`` 里找到它。

    adapter 自己按它自己的 ``automation`` 分支，调度器不替它分支。
    """
    command = list(capability.adapter_command)
    if not command:
        raise ScheduleConfigError(
            "能力声明 {} 没有 [adapter].command，不知道怎么调它".format(capability.id)
        )

    package = capability.adapter_package
    if not package:
        raise ScheduleConfigError(
            "能力声明 {} 没有 [adapter].package，不知道它住在哪".format(capability.id)
        )

    working_dir = config.repo_root / package
    if not working_dir.is_dir():
        raise ScheduleConfigError(
            "adapter 的包目录不存在：{}（能力声明 {} 写的 package 是 {!r}）".format(
                working_dir, capability.id, package
            )
        )

    argv = command + ["publish", content_id]
    environment = os.environ.copy()
    environment["PUBLISH_REPO"] = str(config.repo_root)
    # 状态目录可以被指到别处，adapter 写快照时得知道写到哪去。
    # CLI 契约是固定的 ``publish <content_id>``，位置只能从 argv 之外传。
    environment["PUBLISH_OUTBOX_DIR"] = str(config.outbox_dir)

    try:
        completed = subprocess.run(
            argv,
            cwd=str(working_dir),
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return AdapterResult(code=None, timed_out=True)
    except OSError as exc:
        raise SchedulePublishError(
            "调不起 adapter（{}）：{}".format(" ".join(argv), exc)
        ) from exc

    return AdapterResult(
        code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def write_snapshot(
    config: ScheduleConfig,
    content_id: str,
    platform: str,
    *,
    status: str,
    reason: str,
    title: str | None = None,
    automation: str | None = None,
    retryable: bool | None = None,
):
    """把一次发布结果写进 outbox（§7.1）。

    快照是**公开信息**：没有 token、没有 secret、没有本机的绝对路径。
    文件名按约定：``<压平后的 content_id>__<platform>.json``。
    """
    outbox = config.outbox_dir
    outbox.mkdir(parents=True, exist_ok=True)
    path = outbox / snapshot_name(content_id, platform)

    previous = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                previous = loaded
        except (OSError, ValueError):
            previous = {}

    attempts = 1
    if isinstance(previous.get("attempts"), int):
        attempts = previous["attempts"] + 1

    payload = {
        "content_id": content_id,
        "platform": platform,
        "status": status,
        "automation": automation or "manual",
        "title": title or content_id,
        "published_url": None,
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "reason": reason,
        "attempts": attempts,
    }
    if retryable is not None:
        payload["retryable"] = retryable

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _is_review_rejection(capability, result: AdapterResult) -> bool:
    """这次失败是不是「平台审核不通过」（§7.1 第二条）？

    审核不通过的记录**永不自动重试**：内容有问题，重试无意义，转人工。
    """
    if getattr(capability, "review", None) != "platform":
        return False
    haystack = "{}\n{}".format(result.stdout, result.stderr).lower()
    return any(marker.lower() in haystack for marker in _REVIEW_MARKERS)


def publish_one(
    config: ScheduleConfig,
    capability,
    content_id: str,
    platform: str,
    *,
    timeout: float,
    title: str | None = None,
) -> tuple:
    """把一篇发到一个平台上。返回 ``(退出码, 消息列表)``。

    失败要**记进 outbox**（§7.1），不吞异常；某个平台失败不阻塞其他平台
    （§3.4）——所以这里返回退出码，由调用方决定要不要继续。
    """
    index = load_outbox_index(config.outbox_dir)
    if index.is_published(content_id, platform):
        return EXIT_OK, ["{} 已经发到过 {}，跳过。".format(content_id, platform)]

    before = index.get(content_id, platform)
    result = invoke_adapter(config, capability, content_id, timeout)

    if result.timed_out:
        # 超时 = **结果未知**，不是失败（§7.1 第三条）：可能已经发出去了。
        # 当成失败就会重试，于是可能发两遍。
        path = write_snapshot(
            config,
            content_id,
            platform,
            status="unknown",
            reason="调 adapter 超时（{} 秒），结果未知：不能当失败，待人工核对".format(
                timeout
            ),
            title=title,
            automation=capability.automation,
            retryable=False,
        )
        return EXIT_ERROR, [
            "{} → {}：超时，结果未知（已记进 {}），待人工核对。".format(
                content_id, platform, path.name
            )
        ]

    if result.code == 0:
        return EXIT_OK, ["{} → {}：成功。".format(content_id, platform)]

    # adapter 自己写没写快照：它写了就以它的为准（它是平台那一侧的事实），
    # 调度器不覆盖别人的记录。
    after = load_outbox_index(config.outbox_dir).get(content_id, platform)
    adapter_wrote = after is not None and (
        before is None or after.mtime_ns != before.mtime_ns
    )

    reason = (result.stderr or result.stdout or "").strip()
    if not reason:
        reason = "adapter 退出码 {}".format(result.code)

    if result.code == EXIT_USAGE:
        # 参数或配置错误：不是发布尝试，不进 outbox（§7.4）。
        raise ScheduleConfigError(
            "adapter {} 报参数或配置错误：{}".format(capability.id, reason)
        )

    if not adapter_wrote:
        if result.code == EXIT_INELIGIBLE:
            # 不合格：不是发布尝试，但**要记下来**，否则它会一直霸占
            # 「最久未发」的位置（§7.4）。不自动重试。
            write_snapshot(
                config,
                content_id,
                platform,
                status="failed",
                reason="adapter 报这一篇不合格：{}".format(reason),
                title=title,
                automation=capability.automation,
                retryable=False,
            )
            return EXIT_INELIGIBLE, [
                "{} → {}：不合格（{}），已记进 outbox，转人工。".format(
                    content_id, platform, reason
                )
            ]

        review = _is_review_rejection(capability, result)
        write_snapshot(
            config,
            content_id,
            platform,
            status="failed",
            reason=(
                "平台审核不通过：{}".format(reason)
                if review
                else "平台接口报错：{}".format(reason)
            ),
            title=title,
            automation=capability.automation,
            retryable=not review,
        )
        return EXIT_ERROR, [
            "{} → {}：失败（{}），已记进 outbox{}。".format(
                content_id,
                platform,
                reason,
                "，转人工（审核不通过不自动重试）" if review else "，下次跑会重试一次",
            )
        ]

    # adapter 自己记过了：调度器不覆盖它的记录，只把失败说出来。
    return EXIT_ERROR, [
        "{} → {}：失败（{}），adapter 自己已记进 outbox。".format(
            content_id, platform, reason
        )
    ]


# --- 命令 -----------------------------------------------------------------


def _capability_for(config: ScheduleConfig, platform: str):
    """读一个平台的能力声明，并确认它是文档类平台。"""
    capability = load_capability(platform, capabilities_dir=config.capabilities_dir)
    if capability.kind != "document":
        raise ScheduleConfigError(
            "{} 是视频平台，这一期调度器只驱动文档类平台".format(platform)
        )
    return capability


def _titles_of(units) -> dict:
    return {unit.content_id: unit.title for unit in units}


class _Publisher:
    """把「发一篇到某个平台」这件事包起来，顺带记住退出码。

    退出码取最严重的那个：接口错误（3）比「这一篇不合格」（2）严重。

    **成功时不说话**：成功的话由调度层那一句「成功」交代（两层各说一遍
    是噪声）；只有出问题时它才开口——那时候要说的是**为什么**。
    """

    def __init__(self, config: ScheduleConfig, *, timeout: float, titles=None):
        self.config = config
        self.timeout = timeout
        self.titles = titles or {}
        self.exit_code = EXIT_OK
        self.calls = []
        self.messages = []

    def __call__(self, content_id: str, platform: str) -> bool:
        capability = _capability_for(self.config, platform)
        self.calls.append((content_id, platform))
        code, messages = publish_one(
            self.config,
            capability,
            content_id,
            platform,
            timeout=self.timeout,
            title=self.titles.get(content_id),
        )
        self.messages.extend(messages)
        if code != EXIT_OK:
            for message in messages:
                print(message)
        if code == EXIT_ERROR:
            self.exit_code = EXIT_ERROR
        elif code == EXIT_INELIGIBLE and self.exit_code == EXIT_OK:
            self.exit_code = EXIT_INELIGIBLE
        return code == EXIT_OK


def cmd_schedule_weekly(args) -> int:
    """定时路径：跑一次例行发布。"""
    config = _config_from_args(args)
    timeout = _timeout_from_args(args)

    units, errors = discover_units(config.posts_dir)
    publisher = _Publisher(config, timeout=timeout, titles=_titles_of(units))

    result = run_weekly(
        config,
        publisher=publisher,
        platform_filter=getattr(args, "platform", None),
        dry_run=bool(getattr(args, "dry_run", False)),
    )

    for message in result.messages:
        print(message)

    if result.action == "nothing":
        print("本周没有可发的。")
    elif result.action == "skipped":
        print("{} 跳过（本周已经发过了）。".format(result.week))
    elif result.action == "retry":
        print("重试了没跑完的那一周：{}".format(result.content_id))
    elif getattr(args, "dry_run", False):
        print("（演练）没有真的发，也没有写任何状态。")
    else:
        # 不说「已发布」——平台那边到底发出去没有，看 outbox 里的状态
        # （manual 档只是「出了包，待人工上传」，§6.7）。
        print(
            "{} 完成：{} → {}（各平台的实际状态见 outbox）".format(
                result.week, result.content_id, "、".join(result.platforms)
            )
        )

    if not result.ok:
        return publisher.exit_code or EXIT_ERROR
    return publisher.exit_code


def cmd_schedule_status(args) -> int:
    """看本周发了什么、哪些待重试、哪些待人工。"""
    config = _config_from_args(args)
    state = ScheduleState.load(config.schedule_file)
    week = week_key(date.today())

    print("本周：{}".format(week))
    record = state.get(week)
    if record is None:
        print("  本周还没有记录。")
    else:
        print(
            "  {} → {}（{}）{}".format(
                week,
                record.content_id,
                "、".join(record.platforms),
                "已完成" if record.done else "**没跑完，下次跑会先重试它**",
            )
        )

    for key in state.unfinished_weeks():
        if key == week:
            continue
        unfinished = state.get(key)
        print(
            "  {} 没跑完：{}（{}）——下次跑会先重试它".format(
                key, unfinished.content_id, "、".join(unfinished.platforms)
            )
        )

    index = load_outbox_index(config.outbox_dir)
    for error in index.errors:
        print("  outbox 有读不动的快照：{}".format(error))

    pending = []
    manual = []
    unknown = []
    done = []
    for item in sorted(index.records.values(), key=lambda r: (r.platform, r.content_id)):
        if item.status in PUBLISHED_STATUSES:
            done.append(item)
        elif item.status == "unknown":
            unknown.append(item)
        elif item.status == "failed":
            if item.data.get("retryable") is False:
                manual.append(item)
            else:
                pending.append(item)

    print("已发过（{}）：".format(len(done)))
    for item in done:
        print("  {} → {}（{}）".format(item.content_id, item.platform, item.status))
    print("待重试（{}）：".format(len(pending)))
    for item in pending:
        print(
            "  {} → {}（试了 {} 次）{}".format(
                item.content_id,
                item.platform,
                item.data.get("attempts", 1),
                item.data.get("reason", ""),
            )
        )
    print("待人工（{}）：".format(len(manual) + len(unknown)))
    for item in manual:
        print(
            "  {} → {}（不自动重试）{}".format(
                item.content_id, item.platform, item.data.get("reason", "")
            )
        )
    for item in unknown:
        print(
            "  {} → {}（结果未知，待核对）{}".format(
                item.content_id, item.platform, item.data.get("reason", "")
            )
        )
    return EXIT_OK


def cmd_schedule_candidates(args) -> int:
    """列出候选集（选题前先看看有什么可发）。"""
    config = _config_from_args(args)
    platform_filter = getattr(args, "platform", None)
    capabilities = target_platforms(config, platform_filter)

    units, errors = discover_units(config.posts_dir)
    index = load_outbox_index(config.outbox_dir)

    for error in errors:
        print("语料有问题：{}".format(error))

    wanted = {cap.id for cap in capabilities}
    rows = []
    for unit in units:
        if not unit.platforms:
            continue
        if wanted and not wanted.intersection(unit.platforms):
            continue
        if platform_filter and platform_filter not in unit.platforms:
            continue
        rows.append(unit)

    print("候选集：{} 篇（目标平台：{}）".format(len(rows), "、".join(sorted(wanted))))
    for unit in rows:
        published = sorted(
            platform
            for platform in unit.platforms
            if index.is_published(unit.content_id, platform)
        )
        print(
            "  {}  {}  publish_on={}  date={}  platforms={}{}".format(
                unit.content_id,
                unit.title,
                unit.publish_on or "-",
                unit.date or "-",
                "、".join(unit.platforms),
                "  已发到过：{}".format("、".join(published)) if published else "",
            )
        )
    if not rows:
        print("  （候选集是空的：没有内容单元声明 platforms）")
    return EXIT_OK


def cmd_publish(args) -> int:
    """主动路径：发指定内容到指定平台（不写周键）。"""
    config = _config_from_args(args)
    timeout = _timeout_from_args(args)

    units, errors = discover_units(config.posts_dir)
    for error in errors:
        print("语料有问题：{}".format(error), file=sys.stderr)

    unit = None
    for candidate in units:
        if candidate.content_id == args.content_id:
            unit = candidate
            break
    if unit is None:
        raise ScheduleConfigError(
            "找不到内容单元 {!r}（在 {} 里找）".format(args.content_id, config.posts_dir)
        )

    capability = _capability_for(config, args.platform)

    if not args.publish:
        print("（预览）会把 {} 发到 {}（{}）。".format(
            unit.content_id, args.platform, capability.name
        ))
        print("真的发就加上 --publish。")
        print("主动发布不写周键（06 规格 §4.2 规则 3）。")
        return EXIT_OK

    publisher = _Publisher(config, timeout=timeout, titles=_titles_of(units))
    ok = publisher(args.content_id, args.platform)
    if ok:
        for message in publisher.messages:
            print(message)
        return publisher.exit_code
    return publisher.exit_code or EXIT_ERROR


def main(argv=None) -> int:
    """命令行入口。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ScheduleConfigError as exc:
        print("配置错误：{}".format(exc), file=sys.stderr)
        return EXIT_USAGE
    except ScheduleIneligibleError as exc:
        print("不合格：{}".format(exc), file=sys.stderr)
        return EXIT_INELIGIBLE
    except SchedulePublishError as exc:
        print("发布失败：{}".format(exc), file=sys.stderr)
        return EXIT_ERROR
    except ScheduleError as exc:
        print("错误：{}".format(exc), file=sys.stderr)
        return EXIT_ERROR
    except PublishKitError as exc:
        print("错误：{}".format(exc), file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
