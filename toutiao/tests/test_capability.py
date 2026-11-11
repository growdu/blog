import pytest

from toutiao.capability import (
    AUTOMATIONS, default_capability_path, load_capability,
)

BASE_TOML = """\
id = "toutiao"
name = "头条号"
kind = "document"
automation = "manual"
review = "platform"
requires_certification = true
requires_min_followers = 1000

[limits]
title_chars = 30
body_chars = 3000
digest_chars = 120
image_bytes = 5242880
image_formats = ["webp"]
cover_ratio = "3:4"
cover_min_pixels = [600, 800]
max_body_images = 3

[adapter]
package = "toutiao"
command = ["python3", "-m", "toutiao.cli"]
"""


def _write(tmp_path, text):
    path = tmp_path / "cap.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_automations_are_the_three_tiers():
    assert AUTOMATIONS == ("manual", "api_draft", "api_publish")


def test_default_capability_path_is_in_the_repo():
    path = default_capability_path()
    assert path.name == "toutiao.toml"
    assert path.parent.name == "capabilities"
    assert path.parent.parent.name == "publish"
    assert path.is_file(), "publish/capabilities/toutiao.toml 必须存在"


def test_load_capability_reads_every_field():
    cap = load_capability(default_capability_path())
    assert cap.id == "toutiao"
    assert cap.name == "头条号"
    assert cap.kind == "document"
    assert cap.automation == "manual"
    assert cap.review == "platform"
    assert cap.requires_certification is True
    assert cap.requires_min_followers == 1000
    assert cap.limits.title_chars == 30
    assert cap.limits.body_chars == 3000
    assert cap.limits.digest_chars == 120
    assert cap.limits.image_bytes == 5242880
    assert cap.limits.image_formats == ("webp",)
    assert cap.limits.cover_ratio == "3:4"
    assert cap.limits.cover_min_pixels == (600, 800)
    assert cap.limits.max_body_images == 3
    assert cap.adapter_package == "toutiao"
    assert cap.adapter_command == ("python3", "-m", "toutiao.cli")


def test_unknown_automation_is_rejected(tmp_path):
    path = _write(tmp_path, BASE_TOML.replace('automation = "manual"', 'automation = "auto"'))
    with pytest.raises(ValueError, match="automation"):
        load_capability(path)


def test_missing_limit_is_rejected(tmp_path):
    path = _write(tmp_path, BASE_TOML.replace("title_chars = 30\n", ""))
    with pytest.raises(ValueError):
        load_capability(path)


def test_missing_adapter_section_is_rejected(tmp_path):
    path = _write(tmp_path, BASE_TOML.split("[adapter]")[0])
    with pytest.raises(ValueError):
        load_capability(path)


def test_verified_is_optional(tmp_path):
    path = _write(tmp_path, BASE_TOML)
    assert load_capability(path).verified is None
