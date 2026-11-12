"""视频平台的能力声明：字段齐全、数值有出处、档位取值合法。

契约层的数据文件也要有测试——平台规则变了改 TOML，
但「该有的键有没有」「数值还是不是当初核过的那几个」得有人盯着。
"""
import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CAPABILITIES = REPO_ROOT / "publish" / "capabilities"

PLATFORMS = ("channels", "bilibili")

TOP_KEYS = ("id", "name", "kind", "auth", "automation", "review",
            "requires_certification", "requires_min_followers", "verified")
AUTOMATION = ("manual", "api_draft", "api_publish")
REVIEW = ("none", "platform", "precheck")
AUTH = ("none", "appid_secret")

LIMIT_KEYS = {
    "channels": ("title_chars", "description_chars", "topics_max", "topic_chars"),
    "bilibili": ("title_chars", "description_chars", "tags_chars", "tag_chars"),
}
MEDIA_KEYS = {
    "channels": ("min_width", "min_height", "max_fps", "require_pix_fmt",
                 "require_video_codec", "max_duration_s", "max_bytes",
                 "max_audio_channels", "max_sample_rate", "require_faststart"),
    "bilibili": ("max_width", "max_height", "max_fps", "require_pix_fmt",
                 "require_video_codec", "max_duration_s", "max_bytes",
                 "max_audio_bitrate", "max_audio_channels", "max_sample_rate",
                 "max_video_bitrate", "max_keyframe_gap_s"),
}

# 核过的数值。改了这里就要同时改规格文档，并说明出处。
PINNED = {
    "channels": {"title_chars": 22, "description_chars": 1000,
                 "topics_max": 5, "topic_chars": 15},
    "bilibili": {"title_chars": 79, "description_chars": 249,
                 "tags_chars": 199, "tag_chars": 20},
}

# [media] 段核过的数值。这些是成片的技术门槛，来源见规格 §5.2。
MEDIA_PINNED = {
    "channels": {
        "min_width": 1280, "min_height": 720, "max_fps": 60,
        "require_pix_fmt": "yuv420p", "require_video_codec": "h264",
        "max_duration_s": 3600, "max_bytes": 2147483648,
        "max_audio_channels": 2, "max_sample_rate": 48000,
        "require_faststart": True,
    },
    "bilibili": {
        "max_width": 4096, "max_height": 4096, "max_fps": 120,
        "require_pix_fmt": "yuv420p", "require_video_codec": "h264",
        "max_duration_s": 17999, "max_bytes": 4294967296,
        "max_audio_bitrate": 320000, "max_audio_channels": 2,
        "max_sample_rate": 48000, "max_video_bitrate": 60000000,
        "max_keyframe_gap_s": 10,
    },
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
def test_the_pinned_media_numbers_still_hold(platform):
    """[media] 段的关键数值也钉住。

    「键在不在」只是一半——键在但数值被人改掉，闸还在，只是判的是另一个标准。
    变异测试证明过这一点：把 max_duration_s 改回 18000、把 require_faststart 改 false、
    把 max_video_bitrate 改大，整套测试照样全绿。
    """
    media = _load(platform)["media"]
    for key, value in MEDIA_PINNED[platform].items():
        assert media[key] == value, (
            f"{platform}.toml 的 media.{key} 变成了 {media[key]}，"
            f"当初核过的是 {value}"
        )


@pytest.mark.parametrize("platform", PLATFORMS)
def test_the_pinned_switches_still_hold(platform):
    """顶层那两个开关也钉住：认证要求与粉丝数门槛。"""
    data = _load(platform)
    assert data["requires_certification"] is False
    assert data["requires_min_followers"] == 0


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


def test_top_level_key_sets_are_identical():
    """两个平台的顶层键必须完全一样。

    不对称的键集合意味着「有一个平台少了一道闸」。
    少一道闸比闸判错更糟——它不报错，只是静悄悄地不生效。
    """
    channels = set(_load("channels"))
    bilibili = set(_load("bilibili"))
    assert channels == bilibili, (
        f"两个平台的顶层键不一致："
        f"只有视频号有 {sorted(channels - bilibili)}，"
        f"只有B站有 {sorted(bilibili - channels)}"
    )


def test_auth_takes_a_known_value():
    """`auth` 决定 adapter 要不要凭据，取值域是封闭的。"""
    for platform in PLATFORMS:
        assert _load(platform)["auth"] in AUTH


def test_verified_is_an_iso_date():
    """`verified` = 这些平台数字最后对着平台文档复核过的日期。"""
    for platform in PLATFORMS:
        value = _load(platform)["verified"]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", value), (
            f"{platform}.toml 的 verified={value!r} 不是 ISO 日期"
        )


def test_both_platforms_keep_the_audio_gates():
    """规格 §5.2 说音频门槛两平台都适用。

    视频号曾经漏掉这两道闸——闸缺席不报错，只是静悄悄地不生效。
    """
    channels = _load("channels")["media"]
    assert channels["max_audio_channels"] == 2
    assert channels["max_sample_rate"] == 48000


def test_both_platforms_demand_h264():
    """视频号部分安卓机不解 H.265，两平台都要 H.264。"""
    for platform in PLATFORMS:
        assert _load(platform)["media"]["require_video_codec"] == "h264"
