"""环境自检。"""

from browser import doctor
from browser.session import login_state_present


def test_doctor_reports_on_every_item():
    findings = doctor.run_doctor()
    assert findings
    items = {f.item for f in findings}
    assert "playwright" in items
    assert "chromium" in items
    assert "profile" in items


def test_a_missing_profile_is_a_warning_not_a_failure(tmp_path):
    findings = doctor.run_doctor(tmp_path / "no-such-profile")
    profile = [f for f in findings if f.item == "profile"]
    assert profile
    assert profile[0].level == "warn"
    assert "login" in profile[0].fix


def test_an_existing_profile_with_cookies_is_reported_as_logged_in(tmp_path):
    (tmp_path / "Default").mkdir()
    (tmp_path / "Default" / "Cookies").write_bytes(b"")
    findings = doctor.run_doctor(tmp_path)
    profile = [f for f in findings if f.item == "profile"]
    assert profile[0].level == "ok"


def test_login_state_presence_is_detected(tmp_path):
    assert login_state_present(tmp_path) is False
    (tmp_path / "Default").mkdir()
    (tmp_path / "Default" / "Cookies").write_bytes(b"")
    assert login_state_present(tmp_path) is True


def test_a_finding_renders_its_fix():
    finding = doctor.Finding("warn", "chromium", "没装", "python3 -m playwright install chromium")
    text = finding.render()
    assert "WARN" in text
    assert "没装" in text
    assert "playwright install chromium" in text
