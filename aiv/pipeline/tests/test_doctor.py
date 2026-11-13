"""环境自检的守卫：缺什么报什么，且报得可执行。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pyv import doctor
from pyv import episodes as episodes_mod


def test_this_machine_has_no_hard_failures():
    """这台机器上自检必须全绿——它就是出片机。"""
    failures = [c for c in doctor.run_checks() if not c.ok and c.level == doctor.ERROR]
    assert failures == [], "\n".join(f"{c.name}: {c.detail}" for c in failures)


def test_doctor_covers_every_episode():
    """每一期的旁白都要被检查到——漏一期就等于漏一个坑。"""
    checks = doctor.run_checks()
    names = {c.name for c in checks}
    for ep in episodes_mod.EPISODE_ORDER:
        assert f"narration_{ep}.mp3" in names
        assert f"{ep} 的稿件与契约" in names


def test_missing_narration_is_reported_as_an_error(monkeypatch, tmp_path):
    monkeypatch.setattr(episodes_mod, "AIV_ROOT", tmp_path)
    checks = doctor._check_narrations()
    assert checks
    assert all(not c.ok and c.level == doctor.ERROR for c in checks)
    # 修复命令必须能照着抄
    assert all(c.fix for c in checks)
    assert "synthesize_narration.py" in checks[0].fix


def test_missing_asset_error_carries_a_fix_hint(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor, "AIV_ROOT", tmp_path)
    checks = doctor._check_assets()
    hard = [c for c in checks if c.level == doctor.ERROR]
    assert hard and all(c.fix for c in hard)


def test_report_shows_the_fix_command(capsys):
    checks = [doctor.Check("环境", "ffmpeg", doctor.ERROR, False, "没找到",
                           fix="sudo apt-get install -y ffmpeg")]
    report = doctor.format_report(checks)
    assert "sudo apt-get install -y ffmpeg" in report
    assert "FAIL" in report


def test_report_passes_when_only_warnings(capsys):
    checks = [doctor.Check("素材", "品牌片头", doctor.WARNING, False, "缺")]
    report = doctor.format_report(checks)
    assert "OK" in report
    assert "FAIL" not in report


def test_main_returns_nonzero_on_hard_failure(monkeypatch):
    monkeypatch.setattr(
        doctor, "run_checks",
        lambda: [doctor.Check("环境", "ffmpeg", doctor.ERROR, False, "没找到")],
    )
    assert doctor.main() == 1


def test_main_returns_zero_when_everything_is_fine(monkeypatch):
    monkeypatch.setattr(
        doctor, "run_checks",
        lambda: [doctor.Check("环境", "ffmpeg", doctor.INFO, True, "/usr/bin/ffmpeg")],
    )
    assert doctor.main() == 0


def test_python_version_check_flags_old_python(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 9, 0, "final", 0))
    check = doctor._check_python()
    assert not check.ok
    assert check.level == doctor.ERROR
    assert "3.11" in check.fix


def test_mark_distinguishes_levels():
    assert doctor.Check("g", "n", doctor.ERROR, False, "").mark == "✗"
    assert doctor.Check("g", "n", doctor.WARNING, False, "").mark == "!"
    assert doctor.Check("g", "n", doctor.INFO, True, "").mark == "·"
