"""命令行入口。"""

import json

import pytest

from browser import cli
from browser.plan import PlanError


def test_the_parser_knows_every_subcommand():
    parser = cli.build_parser()
    for argv in (["doctor"], ["probe"], ["prepare", "ep01"], ["submit", "ep01"]):
        args = parser.parse_args(argv)
        assert args.command == argv[0]


def test_prepare_defaults_to_the_channels_package_dir():
    target = cli._package_dir("row-lock", None)
    assert target.name == "row-lock"
    assert target.parent.name == "out"
    assert target.parent.parent.name == "channels"


def test_prepare_accepts_an_explicit_package_dir(tmp_path):
    target = cli._package_dir("ep01", str(tmp_path))
    assert target == tmp_path


def test_load_plan_stops_when_the_limits_are_violated(package_dir):
    (package_dir / "title.txt").write_text("标" * 40, encoding="utf-8")
    with pytest.raises(PlanError) as error:
        cli._load_plan("ep01", str(package_dir))
    assert "字数" in str(error.value)


def test_doctor_reports_a_failure_as_a_nonzero_exit(monkeypatch, capsys):
    from browser.doctor import Finding

    monkeypatch.setattr(cli.doctor, "run_doctor", lambda profile_dir=None: [
        Finding("fail", "chromium", "没装", "python3 -m playwright install chromium"),
    ])
    assert cli.cmd_doctor(type("Args", (), {"profile": None})()) == 1
    assert "FAIL" in capsys.readouterr().out


def test_doctor_reports_all_good_as_zero(monkeypatch, capsys):
    from browser.doctor import Finding

    monkeypatch.setattr(cli.doctor, "run_doctor", lambda profile_dir=None: [
        Finding("ok", "playwright", "已装"),
    ])
    assert cli.cmd_doctor(type("Args", (), {"profile": None})()) == 0
    assert "可以跑" in capsys.readouterr().out


def test_the_mark_command_is_a_template_not_a_hard_coded_call():
    """回填走外部命令，所以模板里必须能填 episode 与 url。"""
    assert "{episode}" in cli.DEFAULT_MARK_TEMPLATE
    assert "{url}" in cli.DEFAULT_MARK_TEMPLATE
    assert "{python}" in cli.DEFAULT_MARK_TEMPLATE


def test_main_turns_a_flow_error_into_a_nonzero_exit(monkeypatch, capsys):
    from browser.flows.channels import FlowError

    def boom(args):
        raise FlowError("选择器表里没有 post.submit_button")

    monkeypatch.setattr(cli, "cmd_prepare", boom)
    assert cli.main(["prepare", "ep01"]) == 1
    assert "ERROR" in capsys.readouterr().err


def test_submit_takes_a_screenshot_after_the_click(tmp_path, package_dir,
                                                   fixture_selectors, page, monkeypatch):
    """点完「发表」必须再留一张图。

    **出事的时候，现场证据在哪儿，全看这张图。** 2026-11-13 那次
    截图拍在点击之前，结果「点了没反应」这件事一点痕迹都没留下，
    只能靠猜——图必须拍在点击之后。
    """
    import argparse

    # 短标题里不能有中文逗号（视频号拒收），夹具里那份带逗号
    (package_dir / "title.txt").write_text("两个事务改同一行 谁先谁后", encoding="utf-8")

    class FakeSession:
        def __init__(self, target_page):
            self.page = target_page

        def grant_clipboard(self, origin):
            return True

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

    monkeypatch.setattr(cli, "_open_session", lambda args: FakeSession(page))

    out_dir = tmp_path / "out"
    args = argparse.Namespace(
        episode="ep01", package=str(package_dir), out=str(out_dir),
        selectors=str(fixture_selectors), cover=None, yes=True, timeout=3000,
        profile=None, headless=True, slow_mo=0, shot_dir=None,
        mark_cmd="echo {episode} {url}", mark_cwd=str(tmp_path),
    )

    assert cli.cmd_submit(args) == 0

    before = out_dir / "submit.png"
    after = out_dir / "submit-after.png"
    assert before.is_file(), "点发表之前也要留一张（填了什么）"
    assert after.is_file(), "点发表之后必须留一张（到底发生了什么）"
    # 两张图不一样 → 后一张确实是点击之后拍的
    assert before.read_bytes() != after.read_bytes()
