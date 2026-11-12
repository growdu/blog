"""平台能力模型：字段齐全、取值合法、坏输入当场报错。

能力声明是外部输入，所以这一层的测试重点是**坏输入**：
缺字段、类型不对、取值不在域内、键名打错——每一种都必须以
``CapabilityFieldError`` / ``CapabilityFileError`` 明确失败，
不能漏出裸 KeyError / TypeError。
"""

from pathlib import Path

import pytest

from publishkit import (
    AUTOMATIONS,
    KINDS,
    REVIEWS,
    CapabilityError,
    CapabilityFieldError,
    CapabilityFileError,
    PublishKitError,
    available_platforms,
    default_capabilities_dir,
    list_capabilities,
    load_capability,
    load_capability_file,
)

FULL_TOML = """\
id = "wechat"
name = "微信公众号"
kind = "document"
auth = "appid_secret"
ip_allowlist = true
automation = "api_draft"
review = "platform"
requires_certification = true
verified = "2026-11-11"

[limits]
title_chars = 32
body_chars = 20000
digest_chars = 120
image_bytes = 1048576
image_formats = ["jpg", "png"]

[adapter]
package = "wechat"
command = ["python3", "-m", "wechat.cli"]
"""


def write_toml(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def write_full(tmp_path: Path, platform: str = "wechat") -> Path:
    return write_toml(tmp_path, "{}.toml".format(platform), FULL_TOML)


# --- 读得对 -------------------------------------------------------------


def test_load_capability_reads_every_field(tmp_path):
    path = write_full(tmp_path)
    cap = load_capability_file(path)

    assert cap.id == "wechat"
    assert cap.name == "微信公众号"
    assert cap.kind == "document"
    assert cap.automation == "api_draft"
    assert cap.review == "platform"
    assert cap.auth == "appid_secret"
    assert cap.ip_allowlist is True
    assert cap.requires_certification is True
    assert cap.verified == "2026-11-11"
    assert cap.path == path


def test_load_capability_reads_limits_as_dict(tmp_path):
    """规格 §5.3 的兼容性测试就是这么用的：cap.limits["title_chars"]。"""
    path = write_full(tmp_path)
    cap = load_capability_file(path)

    assert cap.limits["title_chars"] == 32
    assert cap.limits["body_chars"] == 20000
    assert cap.limits["digest_chars"] == 120
    assert cap.limits["image_bytes"] == 1048576
    assert cap.limits["image_formats"] == ["jpg", "png"]


def test_load_capability_reads_adapter_seam(tmp_path):
    path = write_full(tmp_path)
    cap = load_capability_file(path)

    assert cap.adapter_package == "wechat"
    assert cap.adapter_command == ("python3", "-m", "wechat.cli")


def test_load_capability_by_platform_id(tmp_path):
    write_full(tmp_path)
    cap = load_capability("wechat", capabilities_dir=tmp_path)

    assert cap.id == "wechat"


def test_optional_fields_fall_back_to_defaults(tmp_path):
    path = write_toml(
        tmp_path,
        "channels.toml",
        'id = "channels"\nname = "微信视频号"\nkind = "video"\n'
        'automation = "manual"\nreview = "platform"\n',
    )
    cap = load_capability_file(path)

    assert cap.auth == "none"
    assert cap.ip_allowlist is False
    assert cap.requires_certification is False
    assert cap.requires_min_followers == 0
    assert cap.verified is None
    assert cap.limits == {}
    assert cap.adapter == {}
    assert cap.adapter_command == ()


def test_unknown_limit_keys_are_kept_verbatim(tmp_path):
    """视频平台自有的限额键契约层不认识，但不许丢——丢了就等于没有这道闸。"""
    path = write_toml(
        tmp_path,
        "channels.toml",
        'id = "channels"\nname = "微信视频号"\nkind = "video"\n'
        'automation = "manual"\nreview = "platform"\n'
        "\n[limits]\ntitle_chars = 22\ntopics_max = 5\n",
    )
    cap = load_capability_file(path)

    assert cap.limits["title_chars"] == 22
    assert cap.limits["topics_max"] == 5


def test_media_table_is_accepted(tmp_path):
    path = write_toml(
        tmp_path,
        "channels.toml",
        'id = "channels"\nname = "微信视频号"\nkind = "video"\n'
        'automation = "manual"\nreview = "platform"\n'
        "\n[media]\nmin_width = 1280\nrequire_faststart = true\n",
    )
    cap = load_capability_file(path)

    assert cap.media["min_width"] == 1280
    assert cap.media["require_faststart"] is True


# --- 坏输入 -------------------------------------------------------------


@pytest.mark.parametrize(
    "broken",
    [
        'name = "x"\nkind = "document"\nautomation = "manual"\nreview = "none"\n',
        'id = "x"\nkind = "document"\nautomation = "manual"\nreview = "none"\n',
        'id = "x"\nname = "x"\nautomation = "manual"\nreview = "none"\n',
        'id = "x"\nname = "x"\nkind = "document"\nreview = "none"\n',
        'id = "x"\nname = "x"\nkind = "document"\nautomation = "manual"\n',
    ],
    ids=["no-id", "no-name", "no-kind", "no-automation", "no-review"],
)
def test_missing_required_field_is_rejected(tmp_path, broken):
    path = write_toml(tmp_path, "x.toml", broken)

    with pytest.raises(CapabilityFieldError) as excinfo:
        load_capability_file(path)
    assert "缺少字段" in str(excinfo.value)


def test_wrong_type_is_rejected(tmp_path):
    path = write_toml(
        tmp_path,
        "x.toml",
        'id = "x"\nname = "x"\nkind = "document"\nautomation = "manual"\n'
        'review = "none"\nrequires_certification = "yes"\n',
    )

    with pytest.raises(CapabilityFieldError) as excinfo:
        load_capability_file(path)
    assert "requires_certification" in str(excinfo.value)


def test_bool_is_not_an_int_for_limits(tmp_path):
    path = write_toml(
        tmp_path,
        "x.toml",
        'id = "x"\nname = "x"\nkind = "document"\nautomation = "manual"\n'
        'review = "none"\n\n[limits]\ntitle_chars = true\n',
    )

    with pytest.raises(CapabilityFieldError) as excinfo:
        load_capability_file(path)
    assert "limits.title_chars" in str(excinfo.value)


@pytest.mark.parametrize("bad_kind", ["text", "post", "DOCUMENT", ""])
def test_kind_out_of_domain_is_rejected(tmp_path, bad_kind):
    path = write_toml(
        tmp_path,
        "x.toml",
        'id = "x"\nname = "x"\nkind = "{}"\nautomation = "manual"\n'
        'review = "none"\n'.format(bad_kind),
    )

    with pytest.raises(CapabilityFieldError) as excinfo:
        load_capability_file(path)
    assert "kind" in str(excinfo.value)


@pytest.mark.parametrize("bad_automation", ["auto", "api", "manual ", ""])
def test_automation_out_of_domain_is_rejected(tmp_path, bad_automation):
    path = write_toml(
        tmp_path,
        "x.toml",
        'id = "x"\nname = "x"\nkind = "document"\nautomation = "{}"\n'
        'review = "none"\n'.format(bad_automation),
    )

    with pytest.raises(CapabilityFieldError) as excinfo:
        load_capability_file(path)
    assert "automation" in str(excinfo.value)


def test_review_out_of_domain_is_rejected(tmp_path):
    path = write_toml(
        tmp_path,
        "x.toml",
        'id = "x"\nname = "x"\nkind = "document"\nautomation = "manual"\n'
        'review = "maybe"\n',
    )

    with pytest.raises(CapabilityFieldError) as excinfo:
        load_capability_file(path)
    assert "review" in str(excinfo.value)


def test_unknown_top_level_key_is_rejected(tmp_path):
    """键名打错必须当场发现——不然这份声明会被当成另一份声明用。"""
    path = write_toml(
        tmp_path,
        "x.toml",
        'id = "x"\nname = "x"\nkind = "document"\nautomation = "manual"\n'
        'review = "none"\nautomaion = "manual"\n',
    )

    with pytest.raises(CapabilityFieldError) as excinfo:
        load_capability_file(path)
    assert "automaion" in str(excinfo.value)


def test_verified_must_look_like_a_date(tmp_path):
    path = write_toml(
        tmp_path,
        "x.toml",
        'id = "x"\nname = "x"\nkind = "document"\nautomation = "manual"\n'
        'review = "none"\nverified = "last tuesday"\n',
    )

    with pytest.raises(CapabilityFieldError) as excinfo:
        load_capability_file(path)
    assert "verified" in str(excinfo.value)


def test_verified_accepts_an_unspecified_day(tmp_path):
    """规格 §6.4 的示例就是 verified = "2026-11-XX"——那天的日期还没定。"""
    path = write_toml(
        tmp_path,
        "x.toml",
        'id = "x"\nname = "x"\nkind = "document"\nautomation = "manual"\n'
        'review = "none"\nverified = "2026-11-XX"\n',
    )

    assert load_capability_file(path).verified == "2026-11-XX"


def test_id_must_match_the_file_name(tmp_path):
    path = write_toml(
        tmp_path,
        "toutiao.toml",
        'id = "wechat"\nname = "x"\nkind = "document"\nautomation = "manual"\n'
        'review = "none"\n',
    )

    with pytest.raises(CapabilityFileError) as excinfo:
        load_capability_file(path)
    assert "文件名" in str(excinfo.value)


def test_missing_file_is_a_file_error(tmp_path):
    with pytest.raises(CapabilityFileError):
        load_capability("nosuch", capabilities_dir=tmp_path)


def test_invalid_toml_is_a_file_error(tmp_path):
    path = write_toml(tmp_path, "x.toml", "id = \nthis is not toml\n")

    with pytest.raises(CapabilityFileError):
        load_capability_file(path)


def test_errors_share_one_base_class(tmp_path):
    """调用方一句 except PublishKitError 就能兜住这一层。"""
    path = write_toml(tmp_path, "x.toml", "id = \nnot toml\n")

    with pytest.raises(PublishKitError):
        load_capability_file(path)
    assert issubclass(CapabilityFieldError, CapabilityError)
    assert issubclass(CapabilityFileError, CapabilityError)


# --- 目录级 -------------------------------------------------------------


def test_list_capabilities_reads_every_file(tmp_path):
    write_toml(
        tmp_path,
        "toutiao.toml",
        'id = "toutiao"\nname = "头条号"\nkind = "document"\n'
        'automation = "manual"\nreview = "platform"\n',
    )
    write_toml(
        tmp_path,
        "bilibili.toml",
        'id = "bilibili"\nname = "哔哩哔哩"\nkind = "video"\n'
        'automation = "manual"\nreview = "platform"\n',
    )

    caps = list_capabilities(capabilities_dir=tmp_path)

    assert [cap.id for cap in caps] == ["bilibili", "toutiao"]
    assert available_platforms(capabilities_dir=tmp_path) == ["bilibili", "toutiao"]


def test_list_capabilities_on_a_missing_directory(tmp_path):
    assert list_capabilities(capabilities_dir=tmp_path / "nope") == []


def test_repository_capabilities_all_parse():
    """仓库里现有的 capabilities/*.toml 必须逐个读得动。

    目录为空时 skip 而不是 fail——这一层的进度取决于别的分支什么时候
    把平台声明搬过来，测试不该替它们挡路。
    """
    caps = list_capabilities()
    if not caps:
        pytest.skip(
            "publish/capabilities/ 目前为空，还没有平台声明（目录：{}）".format(
                default_capabilities_dir()
            )
        )

    for cap in caps:
        assert cap.id == cap.path.stem
        assert cap.kind in KINDS
        assert cap.automation in AUTOMATIONS
        assert cap.review in REVIEWS
        assert cap.limits.get("title_chars", 1) > 0
