"""发布执行器的命令行入口。

    python3 -m browser.cli doctor          这台机器能不能跑浏览器投稿
    python3 -m browser.cli probe           打开视频号助手，扫码，dump 页面结构
    python3 -m browser.cli prepare <EP>    上传 + 填表 + 截图，**不发表**
    python3 -m browser.cli submit <EP>     上传 + 填表 + 截图 + **确认后发表**

**prepare 与 submit 为什么分开。** 「发表」是不可逆的外部可见动作：
发出去就收不回来。所以填表和发表分成两步，`prepare` 跑完留下截图与
一份「填了什么」的清单，人能自己看一眼；`submit` 会**重新走一遍填表**
（浏览器一关表单就没了），在点「发表」之前把截图路径打出来并等确认。
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

from browser import doctor, probe
from browser.driver import ActionError, PageDriver
from browser.flows import channels as channels_flow
from browser.plan import PlanError, load_plan
from browser.session import BrowserSession, SessionConfig, default_profile_dir

BROWSER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BROWSER_ROOT.parent
DEFAULT_PACKAGES = REPO_ROOT / "channels" / "out"
DEFAULT_OUT = BROWSER_ROOT / "out"
DEFAULT_SELECTORS = BROWSER_ROOT / "selectors" / "channels.json"

# 回填快照用的命令模板。**用 subprocess 调外部命令，不 import channels**——
# 这样浏览器执行器可以给任意平台用，平台不会��进代码里。
DEFAULT_MARK_TEMPLATE = "{python} -m channels.cli mark published {episode} --url {url}"


def _package_dir(episode: str, override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    return DEFAULT_PACKAGES / episode


def _open_session(args: argparse.Namespace) -> BrowserSession:
    profile = Path(args.profile).expanduser().resolve() if args.profile else default_profile_dir()
    config = SessionConfig.build(profile_dir=profile, headless=args.headless,
                                 slow_mo=args.slow_mo)
    return BrowserSession(config)


def _load_plan(episode: str, override: str | None):
    target = _package_dir(episode, override)
    plan = load_plan(target)
    problems = channels_flow.check_limits(plan)
    if problems:
        for problem in problems:
            print(f"ERROR  {problem}", file=sys.stderr)
        raise PlanError(f"文案没过视频号的字数限制，不填进页面：{target}")
    return plan


# -- 子命令 -----------------------------------------------------------------

def cmd_doctor(args: argparse.Namespace) -> int:
    findings = doctor.run_doctor(Path(args.profile) if args.profile else None)
    print(doctor.render(findings))
    failed = [f for f in findings if f.level == "fail"]
    print()
    if failed:
        print(f"FAIL {len(failed)} 项没通过——先补齐再跑投稿")
        return 1
    print("OK 这台机器可以跑浏览器投稿")
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    """打开视频号助手，等人扫码，然后把页面结构 dump 出来。

    **这一步不需要任何选择器**——所以它能用来「先探页面，再填选择器」。
    """
    out_dir = Path(args.out) if args.out else DEFAULT_OUT / "probe"
    out_dir.mkdir(parents=True, exist_ok=True)

    with _open_session(args) as session:
        flow = channels_flow.ChannelsFlow(
            PageDriver(session.page, shot_dir=out_dir),
            _config_or_default(args),
        )
        flow.open_entry()
        print("== 视频号助手已打开 ==")
        print("请在弹出的浏览器窗口里用微信扫码登录。")
        print("登录完成后回到这个终端，按回车继续（Ctrl-C 取消）。")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            print("\n取消。", file=sys.stderr)
            return 1

        dump = probe.dump_structure(session.page)
        json_path = probe.save(dump, out_dir / "structure.json")
        shot = out_dir / "structure.png"
        try:
            session.page.screenshot(path=str(shot), full_page=True)
        except Exception:
            shot = None

    print()
    print(probe.render_text(dump))
    print()
    print(f"原始数据：{json_path}")
    if shot:
        print(f"截图：{shot}")
    print(f"照着上面的 suggested 填：{DEFAULT_SELECTORS}")
    return 0


def _config_or_default(args: argparse.Namespace) -> channels_flow.ChannelsConfig:
    path = Path(args.selectors) if getattr(args, "selectors", None) else None
    return channels_flow.ChannelsConfig.load(path)


def _prepare(session, plan, args) -> dict:
    flow = channels_flow.ChannelsFlow(
        PageDriver(session.page, timeout_ms=args.timeout,
                   shot_dir=Path(args.shot_dir) if args.shot_dir else None),
        _config_or_default(args),
    )
    return flow.prepare(plan)


def cmd_prepare(args: argparse.Namespace) -> int:
    episode = args.episode
    plan = _load_plan(episode, args.package)
    out_dir = Path(args.out) if args.out else DEFAULT_OUT / episode
    out_dir.mkdir(parents=True, exist_ok=True)

    with _open_session(args) as session:
        filled = _prepare(session, plan, args)
        shot = out_dir / "prepare.png"
        session.page.screenshot(path=str(shot), full_page=True)

    summary = {
        "episode": episode,
        "package_dir": str(plan.package_dir),
        "filled": filled,
        "screenshot": str(shot),
        "note": "还没发表。要发就跑 python3 -m browser.cli submit " + episode,
    }
    (out_dir / "prepare.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("== 填好的内容 ==")
    for key, value in filled.items():
        print(f"  {key}: {value}")
    print()
    print(f"截图：{shot}")
    print(f"清单：{out_dir / 'prepare.json'}")
    print("**还没发表。** 确认没问题后跑："
          f"python3 -m browser.cli submit {episode}")
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    episode = args.episode
    plan = _load_plan(episode, args.package)
    out_dir = Path(args.out) if args.out else DEFAULT_OUT / episode
    out_dir.mkdir(parents=True, exist_ok=True)

    with _open_session(args) as session:
        filled = _prepare(session, plan, args)
        shot = out_dir / "submit.png"
        session.page.screenshot(path=str(shot), full_page=True)

        print("== 填好的内容 ==")
        for key, value in filled.items():
            print(f"  {key}: {value}")
        print()
        print(f"截图：{shot}")

        if not args.yes:
            print()
            print("== 这一步会真的发表出去，收不回来 ==")
            try:
                answer = input("确认发表？输入 yes 继续：").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n取消。", file=sys.stderr)
                return 1
            if answer.lower() != "yes":
                print("取消。")
                return 1

        flow = channels_flow.ChannelsFlow(
            PageDriver(session.page, timeout_ms=args.timeout,
                       shot_dir=Path(args.shot_dir) if args.shot_dir else None),
            _config_or_default(args),
        )
        url = flow.submit()

    print()
    if not url:
        print("WARN 没能自动取到发布链接。")
        print(f"     请手动复制链接，然后跑：")
        print(f"     cd channels && {sys.executable} -m channels.cli mark published "
              f"{episode} --url \"<链接>\"")
        return 2

    print(f"OK 已发表：{url}")
    _mark_published(episode, url, args)
    return 0


def _mark_published(episode: str, url: str, args: argparse.Namespace) -> None:
    """回填发布状态。

    走外部命令而不是 import——浏览器执行器不认平台。
    """
    template = args.mark_cmd or DEFAULT_MARK_TEMPLATE
    command = template.format(python=sys.executable, episode=episode, url=url)
    cwd = Path(args.mark_cwd).resolve() if args.mark_cwd else REPO_ROOT / "channels"
    print(f"回填状态：{command}（cwd={cwd}）")
    result = subprocess.run(shlex.split(command), cwd=str(cwd))
    if result.returncode != 0:
        print(f"ERROR 回填失败（退出码 {result.returncode}）——"
              f"状态快照还是 packaged，别当成已发布。", file=sys.stderr)
        raise SystemExit(result.returncode)


# -- 入口 -------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="browser",
                                     description="用 Playwright 驱动真实 Chromium 做平台投稿")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--profile", default=None,
                       help="浏览器 profile 目录（登录态放这里）")
        p.add_argument("--headless", action="store_true",
                       help="无头模式——扫码登录时用不了")
        p.add_argument("--slow-mo", type=int, default=0,
                       help="每个动作放慢多少毫秒，调试时用")
        p.add_argument("--selectors", default=None,
                       help=f"选择器表路径，默认 {DEFAULT_SELECTORS}")
        p.add_argument("--timeout", type=int, default=20000,
                       help="单步等元素多久（毫秒）")
        p.add_argument("--shot-dir", default=None, help="失败截图放哪")

    p_doctor = sub.add_parser("doctor", help="环境自检")
    p_doctor.add_argument("--profile", default=None)
    p_doctor.set_defaults(func=cmd_doctor)

    p_probe = sub.add_parser("probe", help="打开视频号助手，扫码，dump 页面结构")
    add_common(p_probe)
    p_probe.add_argument("--out", default=None, help="探测结果存哪")
    p_probe.set_defaults(func=cmd_probe)

    p_prepare = sub.add_parser("prepare", help="上传 + 填表 + 截图，不发表")
    add_common(p_prepare)
    p_prepare.add_argument("episode")
    p_prepare.add_argument("--package", default=None, help="发布包目录")
    p_prepare.add_argument("--out", default=None, help="产物目录")
    p_prepare.set_defaults(func=cmd_prepare)

    p_submit = sub.add_parser("submit", help="上传 + 填表 + 截图 + 发表")
    add_common(p_submit)
    p_submit.add_argument("episode")
    p_submit.add_argument("--package", default=None, help="发布包目录")
    p_submit.add_argument("--out", default=None, help="产物目录")
    p_submit.add_argument("--yes", action="store_true",
                          help="跳过发表前的确认（无人值守时用）")
    p_submit.add_argument("--mark-cmd", default=None,
                          help="回填状态的命令模板")
    p_submit.add_argument("--mark-cwd", default=None,
                          help="跑回填命令时的工作目录")
    p_submit.set_defaults(func=cmd_submit)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (PlanError, channels_flow.FlowError) as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 1
    except ActionError as error:
        print(f"ERROR 页面操作失败：\n{error}", file=sys.stderr)
        return 1
    except Exception as error:  # pragma: no cover - 兜底
        print(f"ERROR {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
