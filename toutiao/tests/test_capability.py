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


# --- 未知键与值域 ---------------------------------------------------------
#
# 这些用例守的是一个具体的失败：**拼错的键被静默吞掉，真实键落到默认值，
# 于是「该平台需要认证」被翻转成「不需要认证」**。
# 一个门槛开关被拼写错误关掉了——这是最不该静默的一种失败。


def test_a_misspelled_key_is_rejected_instead_of_being_swallowed(tmp_path):
    """``requires_certificaton``（拼错）必须报错，不能当成「没写」。"""
    path = _write(
        tmp_path,
        BASE_TOML.replace(
            "requires_certification = true", "requires_certificaton = true"
        ),
    )
    with pytest.raises(ValueError) as excinfo:
        load_capability(path)
    assert "requires_certificaton" in str(excinfo.value)


def test_a_misspelled_key_never_flips_the_certification_gate(tmp_path):
    """反证：拼错之后，门槛绝不能变成「不需要认证」。

    修之前的实测：拼错的键被吞掉，``requires_certification`` 取默认值
    False，于是这个平台「不需要认证」——一个门槛被拼写错误关掉了。
    """
    path = _write(
        tmp_path,
        BASE_TOML.replace(
            "requires_certification = true", "requires_certificaton = true"
        ),
    )
    with pytest.raises(ValueError):
        load_capability(path)

    # 并且：写对了的时候门槛确实是「需要认证」——修的不是读数，是读法。
    assert load_capability(_write(tmp_path, BASE_TOML)).requires_certification is True


def _with_top_level(text, line):
    """Insert a **top-level** key.

    Appending to the end of the file would put the key inside the last
    table (``[adapter]``) -- TOML assigns a key to the table it follows.
    """
    assert "[limits]" in text
    return text.replace("[limits]", "{}\n\n[limits]".format(line))


def test_an_unknown_top_level_key_is_rejected(tmp_path):
    path = _write(tmp_path, _with_top_level(BASE_TOML, 'automaion = "manual"'))
    with pytest.raises(ValueError) as excinfo:
        load_capability(path)
    assert "automaion" in str(excinfo.value)


@pytest.mark.parametrize("key", ["name", "kind", "review"])
def test_the_top_level_fields_the_adapter_reads_are_required(tmp_path, key):
    """这些字段以前有默认值（名字空串、kind 猜 document、review 猜 platform）。

    猜出来的值会让「这个平台到底是什么」变得不可控——比如 review 猜成
    platform 就等于替平台承诺了「要轮询审核状态」。
    """
    path = _write(
        tmp_path,
        re.sub(r'^{} = .*\n'.format(key), "", BASE_TOML, flags=re.MULTILINE),
    )
    with pytest.raises(ValueError) as excinfo:
        load_capability(path)
    assert key in str(excinfo.value)


def test_an_empty_name_is_rejected(tmp_path):
    path = _write(tmp_path, BASE_TOML.replace('name = "头条号"', 'name = ""'))
    with pytest.raises(ValueError) as excinfo:
        load_capability(path)
    assert "name" in str(excinfo.value)


@pytest.mark.parametrize(
    ("old", "new", "field"),
    [
        ('kind = "document"', 'kind = "article"', "kind"),
        ('review = "platform"', 'review = "human"', "review"),
    ],
    ids=["kind_out_of_domain", "review_out_of_domain"],
)
def test_a_value_outside_the_domain_is_rejected(tmp_path, old, new, field):
    """值域外的值必须拒——「这个平台发什么」「审不审」不能靠猜。"""
    path = _write(tmp_path, BASE_TOML.replace(old, new))
    with pytest.raises(ValueError) as excinfo:
        load_capability(path)
    assert field in str(excinfo.value)


def test_a_verified_that_is_not_a_date_is_rejected(tmp_path):
    path = _write(tmp_path, _with_top_level(BASE_TOML, 'verified = "last tuesday"'))
    with pytest.raises(ValueError) as excinfo:
        load_capability(path)
    assert "verified" in str(excinfo.value)


def test_a_verified_that_is_not_measured_yet_may_write_xx(tmp_path):
    """实测还没做的那天允许写 ``2026-11-XX``——「没实测」和「实测了但日期不对」是两件事。"""
    path = _write(tmp_path, _with_top_level(BASE_TOML, 'verified = "2026-11-XX"'))
    assert load_capability(path).verified == "2026-11-XX"

    path = _write(tmp_path, _with_top_level(BASE_TOML, 'verified = "2026-11-13"'))
    assert load_capability(path).verified == "2026-11-13"


def test_the_keys_the_adapter_does_not_read_are_still_accepted(tmp_path):
    """契约层允许平台在顶层加自有键（auth / media ...），adapter 也得放行。

    否则两个读者对「这份 TOML 合不合法」就会有分歧——那正是这套规则要消除的。
    """
    path = _write(
        tmp_path,
        _with_top_level(
            BASE_TOML, 'auth = "appid_secret"\nip_allowlist = ["1.2.3.4"]'
        ),
    )
    cap = load_capability(path)
    assert cap.id == "toutiao"
