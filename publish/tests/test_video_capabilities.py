"""视频平台的能力声明：字段齐全、数值有出处、档位取值合法。

契约层的数据文件也要有测试——平台规则变了改 TOML，
但「该有的键有没有」「数值还是不是当初核过的那几个」得有人盯着。
"""
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CAPABILITIES = REPO_ROOT / "publish" / "capabilities"

PLATFORMS = ("channels", "bilibili")

TOP_KEYS = ("id", "name", "kind", "automation", "review", "verified")
AUTOMATION = ("manual", "api_draft", "api_publish")
REVIEW = ("none", "platform", "precheck")

LIMIT_KEYS = {
    "channels": ("title_chars", "description_chars", "topics_max", "topic_chars"),
    "bilibili": ("title_chars", "description_chars", "tags_chars", "tag_chars"),
}
MEDIA_KEYS = {
    "channels": ("min_width", "min_height", "max_fps", "require_pix_fmt",
                 "max_duration_s", "max_bytes"),
    "bilibili": ("max_width", "max_height", "max_fps", "require_pix_fmt",
                 "max_duration_s", "max_bytes", "max_audio_bitrate",
                 "max_audio_channels", "max_sample_rate", "max_keyframe_gap_s"),
}

# 核过的数值。改了这里就要同时改规格文档，并说明出处。
PINNED = {
    "channels": {"title_chars": 22, "description_chars": 1000,
                 "topics_max": 5, "topic_chars": 15},
    "bilibili": {"title_chars": 79, "description_chars": 249,
                 "tags_chars": 199, "tag_chars": 20},
}


def _load(platform: str) -> dict:
    path = CAPABILITIES / f"{platform}.toml"
    assert path.is_file(), f"缺少能力声明：{path}"
    return tomllib.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("platform", PLATFORMS)
def test_top_level_fields_are_present(platform):
    data = _load(platform)
    for key in TOP_KEYS:
        assert key in data, f"{platform}.toml 缺少 {key}"
    assert data["id"] == platform
    assert data["kind"] == "video"


@pytest.mark.parametrize("platform", PLATFORMS)
def test_automation_and_review_take_legal_values(platform):
    data = _load(platform)
    assert data["automation"] in AUTOMATION
    assert data["review"] in REVIEW


@pytest.mark.parametrize("platform", PLATFORMS)
def test_limits_are_complete_and_positive(platform):
    limits = _load(platform)["limits"]
    for key in LIMIT_KEYS[platform]:
        assert key in limits, f"{platform}.toml 的 limits 缺少 {key}"
        assert limits[key] > 0


@pytest.mark.parametrize("platform", PLATFORMS)
def test_media_limits_are_complete(platform):
    media = _load(platform)["media"]
    for key in MEDIA_KEYS[platform]:
        assert key in media, f"{platform}.toml 的 media 缺少 {key}"


@pytest.mark.parametrize("platform", PLATFORMS)
def test_the_pinned_numbers_still_hold(platform):
    """这些数字是对着平台文档核过的，改动必须回到规格文档里说明理由。"""
    limits = _load(platform)["limits"]
    for key, value in PINNED[platform].items():
        assert limits[key] == value, (
            f"{platform}.toml 的 limits.{key} 变成了 {limits[key]}，"
            f"当初核过的是 {value}"
        )


@pytest.mark.parametrize("platform", PLATFORMS)
def test_adapter_section_declares_the_package(platform):
    adapter = _load(platform)["adapter"]
    assert adapter["package"] == platform
    assert adapter["command"][0] == "python3"
    assert adapter["command"][1] == "-m"
    assert adapter["command"][2] == f"{platform}.cli"


def test_bilibili_keeps_the_keyframe_rule():
    """B站的「关键帧至少 10 秒一个」是硬门槛，少这条键就等于少一道闸。"""
    media = _load("bilibili")["media"]
    assert media["max_keyframe_gap_s"] == 10


def test_channels_has_no_keyframe_rule():
    """视频号没这条要求，别把它也加上——加了会凭空多一道闸。"""
    media = _load("channels")["media"]
    assert "max_keyframe_gap_s" not in media
