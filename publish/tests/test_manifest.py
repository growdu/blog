"""发布清单：字段必填/可选、类型严格、序列化稳定、限额校验不截断。

清单是契约层与平台 adapter 之间的接缝，所以它的字段名就是对外契约：
多一个字段、少一个字段、类型不对，都必须明确报错。
"""

import json
from dataclasses import dataclass

import pytest

from publishkit import (
    Manifest,
    ManifestError,
    ManifestFieldError,
    PublishKitError,
    validate_manifest,
)

FULL_MANIFEST = {
    "content_id": "db/postgresql/postgresql-logical-replication-add-guc",
    "platform": "wechat",
    "kind": "document",
    "title": "逻辑复制大事务同步要 30 分钟？",
    "digest": "大事务同步把 WAL 推满了。",
    "cover": "source/images/xxx.jpg",
    "body_html": "<p>正文</p>",
    "source_url": "https://growdu.cn/2026/09/14/xxx/",
    "assets": ["source/images/a.png"],
}


def make_manifest(**overrides) -> Manifest:
    data = dict(FULL_MANIFEST)
    data.update(overrides)
    return Manifest.from_dict(data)


class FakeCapability:
    """A capability stub — the validator only reads ``kind`` and ``limits``."""

    def __init__(self, kind="document", limits=None):
        self.id = "wechat"
        self.kind = kind
        self.limits = limits or {}


# --- 构造 ---------------------------------------------------------------


def test_from_dict_reads_every_field():
    manifest = make_manifest()

    assert manifest.content_id == FULL_MANIFEST["content_id"]
    assert manifest.platform == "wechat"
    assert manifest.kind == "document"
    assert manifest.title == FULL_MANIFEST["title"]
    assert manifest.digest == FULL_MANIFEST["digest"]
    assert manifest.cover == FULL_MANIFEST["cover"]
    assert manifest.body_html == FULL_MANIFEST["body_html"]
    assert manifest.source_url == FULL_MANIFEST["source_url"]
    assert manifest.assets == ("source/images/a.png",)


def test_optional_fields_may_be_omitted():
    manifest = Manifest.from_dict(
        {
            "content_id": "db/x",
            "platform": "wechat",
            "kind": "document",
            "title": "标题",
            "body_html": "<p>x</p>",
        }
    )

    assert manifest.digest == ""
    assert manifest.cover == ""
    assert manifest.source_url == ""
    assert manifest.assets == ()


@pytest.mark.parametrize(
    "missing",
    ["content_id", "platform", "kind", "title", "body_html"],
)
def test_missing_required_field_is_rejected(missing):
    data = dict(FULL_MANIFEST)
    del data[missing]

    with pytest.raises(ManifestFieldError) as excinfo:
        Manifest.from_dict(data)
    assert missing in str(excinfo.value)


@pytest.mark.parametrize(
    "field",
    ["content_id", "platform", "kind", "title", "body_html", "digest", "cover", "source_url"],
)
def test_wrong_scalar_type_is_rejected(field):
    data = dict(FULL_MANIFEST)
    data[field] = 123

    with pytest.raises(ManifestFieldError) as excinfo:
        Manifest.from_dict(data)
    assert field in str(excinfo.value)


def test_assets_must_be_a_list_of_strings():
    data = dict(FULL_MANIFEST)
    data["assets"] = "source/images/a.png"

    with pytest.raises(ManifestFieldError) as excinfo:
        Manifest.from_dict(data)
    assert "assets" in str(excinfo.value)


def test_assets_elements_must_be_strings():
    data = dict(FULL_MANIFEST)
    data["assets"] = ["source/images/a.png", 7]

    with pytest.raises(ManifestFieldError) as excinfo:
        Manifest.from_dict(data)
    assert "assets" in str(excinfo.value)


def test_kind_out_of_domain_is_rejected():
    data = dict(FULL_MANIFEST)
    data["kind"] = "text"

    with pytest.raises(ManifestFieldError) as excinfo:
        Manifest.from_dict(data)
    assert "kind" in str(excinfo.value)


def test_unknown_field_is_rejected():
    data = dict(FULL_MANIFEST)
    data["body_hml"] = "<p>typo</p>"

    with pytest.raises(ManifestFieldError) as excinfo:
        Manifest.from_dict(data)
    assert "body_hml" in str(excinfo.value)


def test_empty_required_values_are_rejected():
    for field in ("content_id", "platform", "title"):
        data = dict(FULL_MANIFEST)
        data[field] = "   "

        with pytest.raises(ManifestFieldError) as excinfo:
            Manifest.from_dict(data)
        assert field in str(excinfo.value)


def test_non_mapping_input_is_rejected():
    with pytest.raises(ManifestFieldError):
        Manifest.from_dict(["not", "a", "manifest"])


def test_errors_share_one_base_class():
    with pytest.raises(PublishKitError):
        Manifest.from_dict({})
    assert issubclass(ManifestFieldError, ManifestError)


# --- 序列化 -------------------------------------------------------------


def test_to_dict_carries_every_field():
    assert make_manifest().to_dict() == FULL_MANIFEST


def test_to_json_is_valid_json_and_round_trips():
    manifest = make_manifest()

    text = manifest.to_json()
    assert json.loads(text) == FULL_MANIFEST
    assert Manifest.from_json(text) == manifest


def test_to_json_is_stable():
    """同一份清单序列化两次必须逐字节一致——清单是可重放的纯数据。"""
    manifest = make_manifest()

    assert manifest.to_json() == manifest.to_json()
    assert manifest.to_json(indent=2) == manifest.to_json(indent=2)


def test_to_json_keeps_chinese_readable():
    text = make_manifest().to_json()

    assert "逻辑复制大事务同步要 30 分钟？" in text


def test_from_json_rejects_broken_json():
    with pytest.raises(ManifestFieldError) as excinfo:
        Manifest.from_json("{not json")
    assert "JSON" in str(excinfo.value)


# --- 限额校验 -----------------------------------------------------------


def test_manifest_within_limits_is_eligible():
    manifest = make_manifest(title="短标题", digest="短摘要")
    cap = FakeCapability(limits={"title_chars": 32, "digest_chars": 120})

    assert manifest.validate(cap) == []
    assert manifest.is_eligible(cap)
    assert validate_manifest(manifest, cap) == []


def test_title_over_limit_is_reported_not_truncated():
    manifest = make_manifest(title="标" * 33)
    cap = FakeCapability(limits={"title_chars": 32})

    violations = manifest.validate(cap)

    assert len(violations) == 1
    assert "标题" in violations[0]
    assert "32" in violations[0]
    # 超限不截断——标题还是原来那个 33 字的。
    assert manifest.title == "标" * 33
    assert not manifest.is_eligible(cap)


def test_digest_over_limit_is_reported():
    manifest = make_manifest(digest="摘" * 121)
    cap = FakeCapability(limits={"digest_chars": 120})

    violations = manifest.validate(cap)

    assert len(violations) == 1
    assert "摘要" in violations[0]


def test_body_over_limit_is_reported():
    manifest = make_manifest(body_html="<p>" + "x" * 100 + "</p>")
    cap = FakeCapability(limits={"body_chars": 50})

    violations = manifest.validate(cap)

    assert len(violations) == 1
    assert "正文" in violations[0]


def test_too_many_assets_is_reported():
    manifest = make_manifest(assets=["a.png", "b.png", "c.png", "d.png"])
    cap = FakeCapability(limits={"max_body_images": 3})

    violations = manifest.validate(cap)

    assert len(violations) == 1
    assert "附图" in violations[0]


def test_kind_mismatch_with_the_platform_is_reported():
    manifest = make_manifest(kind="document")
    cap = FakeCapability(kind="video")

    violations = manifest.validate(cap)

    assert len(violations) == 1
    assert "kind" in violations[0]


def test_limits_the_platform_does_not_declare_are_not_checked():
    """平台没声明 title_chars，就不该按它判不合格。"""
    manifest = make_manifest(title="标" * 200)
    cap = FakeCapability(limits={})

    assert manifest.validate(cap) == []
    assert manifest.is_eligible(cap)


def test_a_capability_without_limits_is_tolerated():
    manifest = make_manifest(title="标" * 200)

    assert manifest.validate(FakeCapability(limits=None)) == []


# --- 两种 limits 形态 ----------------------------------------------------
#
# 契约层自己的 capability 用 dict，平台 adapter 自己的 capability 用 dataclass
# （toutiao/toutiao/capability.py 的 Limits）。validate() 的签名是鸭子类型，
# 两种形态都要能校验——而且这一层只抛 PublishKitError 这一族，裸 AttributeError
# 不许漏出去。


@dataclass(frozen=True)
class AdapterLimits:
    """The shape a platform adapter uses for its own limits."""

    title_chars: int = 32
    digest_chars: int = 120
    body_chars: int = 20000
    max_body_images: int = 20


class AdapterCapability:
    """A capability in the shape a platform adapter hands out."""

    def __init__(self, limits=None, kind="document"):
        self.id = "toutiao"
        self.kind = kind
        self.limits = limits if limits is not None else AdapterLimits()


def test_validate_reads_limits_from_a_dataclass():
    """adapter 形态的 capability（dataclass 的 limits）也能校验。"""
    manifest = make_manifest(title="短标题", digest="短摘要")

    assert manifest.validate(AdapterCapability()) == []
    assert manifest.is_eligible(AdapterCapability())


def test_validate_reports_the_limits_of_a_dataclass():
    """dataclass 形态的 limits 要真的参与判定，不是被跳过。"""
    manifest = make_manifest(title="标" * 33)
    cap = AdapterCapability(AdapterLimits(title_chars=32))

    violations = manifest.validate(cap)

    assert len(violations) == 1
    assert "标题" in violations[0]
    assert "32" in violations[0]


def test_validate_does_not_leak_a_bare_attribute_error():
    """裸 AttributeError 违反「这一层只抛 PublishKitError 这一族」的规矩。"""
    manifest = make_manifest(title="标" * 200)

    try:
        manifest.validate(AdapterCapability())
    except PublishKitError:
        pass
    except AttributeError as exc:  # pragma: no cover - 变异会被这里抓住
        raise AssertionError("漏出了裸 AttributeError：{}".format(exc))
    except Exception as exc:  # pragma: no cover
        raise AssertionError("漏出了 PublishKitError 之外的异常：{}".format(exc))
