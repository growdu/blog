import dataclasses
import re
from pathlib import Path

import pytest

import toutiao
from toutiao import capability as capability_module
from toutiao.capability import (
    AUTOMATIONS, Capability, Limits, default_capability_path, load_capability,
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

LIMITS_TABLE = """[limits]
title_chars = 30
body_chars = 3000
digest_chars = 120
image_bytes = 5242880
image_formats = ["webp"]
cover_ratio = "3:4"
cover_min_pixels = [600, 800]
max_body_images = 3
"""


def _write(tmp_path, text):
    path = tmp_path / "cap.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_automations_are_the_three_tiers():
    assert AUTOMATIONS == ("manual", "api_draft", "api_publish")


def test_default_capability_path_is_in_the_repo():
    """路径必须落在仓库根下 —— 只断言片段名的话，任意位置的同名文件都能蒙混过关。"""
    repo_root = Path(toutiao.__file__).resolve().parents[2]
    path = default_capability_path()
    assert path.name == "toutiao.toml"
    assert path.parent.name == "capabilities"
    assert path.parent.parent.name == "publish"
    assert path == repo_root / "publish" / "capabilities" / "toutiao.toml"
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


def test_public_interface_is_locked():
    """后面 9 个任务要 import 这些名字。

    字段名、**字段顺序**、不可变性、导出清单 —— 任何一个悄悄变了，
    下游全部崩，而现有 7 个测试察觉不到。
    """
    assert tuple(f.name for f in dataclasses.fields(Limits)) == (
        "title_chars", "body_chars", "digest_chars", "image_bytes",
        "image_formats", "cover_ratio", "cover_min_pixels", "max_body_images",
    )
    assert tuple(f.name for f in dataclasses.fields(Capability)) == (
        "id", "name", "kind", "automation", "review", "requires_certification",
        "requires_min_followers", "verified", "limits", "adapter_package",
        "adapter_command",
    )

    cap = load_capability(default_capability_path())
    with pytest.raises(dataclasses.FrozenInstanceError):
        cap.limits.title_chars = 999
    with pytest.raises(dataclasses.FrozenInstanceError):
        cap.automation = "api_publish"

    assert set(capability_module.__all__) == {
        "AUTOMATIONS", "Capability", "Limits",
        "default_capability_path", "load_capability",
    }
    assert len(capability_module.__all__) == 5


def test_unknown_automation_is_rejected(tmp_path):
    path = _write(tmp_path, BASE_TOML.replace('automation = "manual"', 'automation = "auto"'))
    with pytest.raises(ValueError, match="automation"):
        load_capability(path)


def test_missing_limit_is_rejected(tmp_path):
    path = _write(tmp_path, BASE_TOML.replace("title_chars = 30\n", ""))
    with pytest.raises(ValueError, match=re.escape("limits.title_chars")):
        load_capability(path)


def test_missing_adapter_section_is_rejected(tmp_path):
    path = _write(tmp_path, BASE_TOML.split("[adapter]")[0])
    with pytest.raises(ValueError, match=re.escape("adapter")):
        load_capability(path)


def test_verified_is_optional(tmp_path):
    path = _write(tmp_path, BASE_TOML)
    assert load_capability(path).verified is None


@pytest.mark.parametrize(
    ("old", "new", "field"),
    [
        ('image_formats = ["webp"]', "image_formats = 5", "limits.image_formats"),
        ("cover_min_pixels = [600, 800]", "cover_min_pixels = 5", "limits.cover_min_pixels"),
        ('command = ["python3", "-m", "toutiao.cli"]', "command = 5", "adapter.command"),
        (LIMITS_TABLE, "limits = 5", "limits"),
        ("title_chars = 30", 'title_chars = "abc"', "limits.title_chars"),
        ("title_chars = 30", "title_chars = 1.5", "limits.title_chars"),
        (
            "requires_min_followers = 1000",
            "requires_min_followers = true",
            "requires_min_followers",
        ),
        (
            "requires_min_followers = 1000",
            "requires_min_followers = 1000\nverified = true",
            "verified",
        ),
        (
            "cover_min_pixels = [600, 800]",
            "cover_min_pixels = [600, 800, 1000]",
            "limits.cover_min_pixels",
        ),
    ],
    ids=[
        "image_formats_not_an_array",
        "cover_min_pixels_not_an_array",
        "adapter_command_not_an_array",
        "limits_not_a_table",
        "title_chars_not_an_int",
        "title_chars_is_a_float",
        "requires_min_followers_is_bool",
        "verified_is_bool",
        "cover_min_pixels_wrong_length",
    ],
)
def test_malformed_values_are_rejected(tmp_path, old, new, field):
    """畸形 TOML 必须抛 ValueError（不是 TypeError），且消息里带字段全名。

    这些值都会让 `except ValueError` 的调用方被 TypeError 穿透，
    或者被静默转换成另一个值（float 截断、bool 当 int）。
    """
    assert old in BASE_TOML, "注入点没匹配上，测试会变成空跑"
    path = _write(tmp_path, BASE_TOML.replace(old, new))
    with pytest.raises(ValueError, match=re.escape(field)):
        load_capability(path)


def test_non_table_limits_is_reported_as_a_type_problem(tmp_path):
    """`limits = "x"` 要报「期望是表/映射」，不能报「缺少字段 limits.title_chars」。

    后者是误导：字段其实在，错的是它不是一张表。
    """
    path = _write(tmp_path, BASE_TOML.replace(LIMITS_TABLE, 'limits = "x"'))
    with pytest.raises(ValueError) as excinfo:
        load_capability(path)
    message = str(excinfo.value)
    assert "limits" in message
    assert "期望是表/映射" in message
    assert "缺少字段" not in message
