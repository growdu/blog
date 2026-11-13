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
