"""Tests for the launchd template that drives the scheduled job.

The template is the one piece of this tool that runs on its own, so
the arguments it carries are worth pinning down: a missing
``--new-only`` would silently push the whole existing corpus into the
draft box.
"""
import plistlib
from pathlib import Path

import pytest

TEMPLATE = Path(__file__).resolve().parents[1] / "deploy" / "launchd.plist.template"


def _load() -> dict:
    text = TEMPLATE.read_text(encoding="utf-8")
    text = (text.replace("__PYTHON__", "/usr/bin/python3")
                .replace("__REPO__", "/repo")
                .replace("__HOME__", "/home/me"))
    return plistlib.loads(text.encode("utf-8"))


def test_the_template_is_valid_plist():
    assert _load()["Label"] == "com.growdu.weixin.auto-draft"


def test_the_job_only_drafts_new_articles():
    """``--new-only`` keeps the scheduled job from backfilling the corpus.

    Without it the first run would push every eligible article into
    the draft box, which is a decision a human has to make.
    """
    args = _load()["ProgramArguments"]
    assert args[-3:] == ["wechat.cli", "auto-draft", "--new-only"]


def test_the_job_runs_inside_the_weixin_package():
    config = _load()
    assert config["WorkingDirectory"].endswith("/weixin")
    assert config["EnvironmentVariables"]["PYTHONPATH"].endswith("/weixin")


def test_the_schedule_covers_every_other_hour():
    slots = _load()["StartCalendarInterval"]
    hours = sorted(slot["Hour"] for slot in slots)
    assert hours == list(range(1, 24, 2))
    assert all(slot["Minute"] == 0 for slot in slots)


def test_the_job_does_not_run_at_load_time():
    assert _load()["RunAtLoad"] is False


def test_the_path_carries_homebrew_for_mermaid():
    """mermaid rendering shells out to ``npx``, which lives in homebrew."""
    path = _load()["EnvironmentVariables"]["PATH"]
    assert "/opt/homebrew/bin" in path.split(":")


def test_the_log_goes_to_the_library_logs_folder():
    config = _load()
    assert config["StandardOutPath"].endswith("/Library/Logs/weixin-auto-draft.log")
    assert config["StandardErrorPath"] == config["StandardOutPath"]


def test_the_template_is_committed():
    """A template that is missing from the package cannot be installed."""
    assert TEMPLATE.is_file()
