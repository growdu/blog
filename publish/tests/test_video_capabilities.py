"""视频平台的能力声明：字段齐全、数值有出处、档位取值合法。

契约层的数据文件也要有测试——平台规则变了改 TOML，
但「该有的键有没有」「数值还是不是当初核过的那几个」得有人盯着。
"""
import tomllib
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CAPABILITIES = REPO_ROOT / "publish" / "capabilities"

PLATFORMS = ("channels", "bilibili", "douyin")

TOP_KEYS = ("id", "name", "kind", "auth", "automation", "review",
            "requires_certification", "requires_min_followers", "verified")
AUTOMATION = ("manual", "api_draft", "api_publish")
REVIEW = ("none", "platform", "precheck")
AUTH = ("none", "appid_secret")

LIMIT_KEYS = {
    "channels": ("title_chars", "description_chars", "topics_max", "topic_chars"),
    "bilibili": ("title_chars", "description_chars", "tags_chars", "tag_chars"),
    # 抖音的 text 是**一个字段**装下标题+正文+话题，所以限额是四项 + 拼装后的总量。
    # text_chars 是给 adapter 拼装完做总量校验用的（epmeta 逐字段查不到总量）。
    "douyin": ("text_chars", "title_chars", "description_chars",
               "topics_max", "topic_chars"),
}
# 核过的数值。改了这里就要同时改规格文档，并说明出处。
PINNED = {
    # 标题上限 16：**实测**（2026-11-13，投稿页标「标题超过16字限制」）。
    # 公开口径里的 20 / 22 / 34 都不作数——规格 §十四 第 1 条。
    "channels": {"title_chars": 16, "description_chars": 1000,
                 "topics_max": 5, "topic_chars": 15},
    "bilibili": {"title_chars": 79, "description_chars": 249,
                 "tags_chars": 199, "tag_chars": 20},
    # 抖音（2026-11-14 对官方文档核对，**非实测**——个人主体批不下发布能力）。
    # text_chars = 1000 是**平台写明**的（错误码 2100005「标题文字不得多于1000个」）；
    # 剩下四项是**我们自己的编辑口径**，平台没写死（规格 §6.6）。
    "douyin": {"text_chars": 1000, "title_chars": 55, "description_chars": 500,
               "topics_max": 5, "topic_chars": 15},
}

# [media] 段核过的数值。这些是成片的技术门槛，来源见规格 §5.2。
MEDIA_PINNED = {
    "channels": {
        "min_width": 1280, "min_height": 720, "max_fps": 60,
        "require_pix_fmt": "yuv420p", "require_video_codec": "h264",
        # 时长 8 h / 体积 20 GB：投稿页实测提示（2026-11-13，规格 §5.2）
        "max_duration_s": 28800, "max_bytes": 21474836480,
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
    # 抖音：**只放有出处的闸**。平台没文档化尺寸与帧率上限，所以那两项不设
    # （设了就是拿编辑偏好冒充平台规则）。时长 15 分钟（错误码 2114006）、
    # 体积 4GB（官方「视频总大小 4GB 以内」）是平台写明的；音频两条平台
    # 未文档化，取我们出片的规格——标注在 douyin.toml 的注释里。
    "douyin": {
        "require_video_codec": "h264", "require_pix_fmt": "yuv420p",
        "max_duration_s": 900, "max_bytes": 4294967296,
        "max_audio_channels": 2, "max_sample_rate": 48000,
    },
}

# 键集合从 MEDIA_PINNED 推导，不另写一份——两份手工同步的同键列表迟早会漂。
MEDIA_KEYS = {platform: tuple(pinned) for platform, pinned in MEDIA_PINNED.items()}


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
    # 键集合必须**完全相等**：多出一个键就是凭空多一道闸——规格 §5.2 里视频号
    # 明确为「—」的项（比如 max_video_bitrate），加上去就多判一道。
    assert set(media) == set(MEDIA_PINNED[platform]), (
        f"{platform}.toml 的 media 键集合变了："
        f"多出 {sorted(set(media) - set(MEDIA_PINNED[platform]))}，"
        f"缺少 {sorted(set(MEDIA_PINNED[platform]) - set(media))}"
    )
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


def test_douyin_has_no_size_or_fps_gate():
    """抖音**没有文档化**尺寸与帧率上限，所以不设闸。

    加上去就是拿编辑偏好冒充平台规则——规格 §6.6 把这条写清楚了。
    真要加之前，先把官方文档的依据写进 `douyin.toml` 的注释里。
    """
    media = _load("douyin")["media"]
    for key in ("max_width", "max_height", "max_fps"):
        assert key not in media, (
            f"douyin.toml 的 media 多了 {key}——平台没文档化这一项，"
            f"这是我们自己的偏好，不是平台门槛"
        )


def test_douyin_editor_budgets_never_exceed_the_platform_text_limit():
    """我们的编辑预算拼起来不能顶穿平台的 `text` 硬上限。

    抖音的 `text` 一个字段装下标题+正文+话题（话题每个带一个 `#`）。
    如果编辑预算的最坏情况已经超过平台上限，那「编辑预算」就变成了
    平台拒绝的理由——闸会拦住一条本来能发的稿子。
    """
    limits = _load("douyin")["limits"]
    worst = (limits["title_chars"] + limits["description_chars"]
             + limits["topics_max"] * (limits["topic_chars"] + 1))
    assert worst <= limits["text_chars"], (
        f"抖音编辑预算最坏情况 {worst} 字，超过平台 text 上限 "
        f"{limits['text_chars']} 字"
    )


def test_top_level_key_sets_are_identical():
    """所有视频平台的顶层键必须完全一样。

    不对称的键集合意味着「有一个平台少了一道闸」。
    少一道闸比闸判错更糟——它不报错，只是静悄悄地不生效。

    之前这条只比视频号与B站两个平台；加进抖音之后改成**遍历全部**，
    否则新平台进来时这条守卫又变成半个。
    """
    sets = {platform: set(_load(platform)) for platform in PLATFORMS}
    reference = sets[PLATFORMS[0]]
    for platform, keys in sets.items():
        assert keys == reference, (
            f"{platform}.toml 的顶层键与 {PLATFORMS[0]} 不一致："
            f"多出 {sorted(keys - reference)}，"
            f"缺少 {sorted(reference - keys)}"
        )


def test_auth_takes_a_known_value():
    """`auth` 决定 adapter 要不要凭据，取值域是封闭的。"""
    for platform in PLATFORMS:
        assert _load(platform)["auth"] in AUTH


def test_verified_is_a_real_date():
    """`verified` = 这些平台数字最后对着平台文档复核过的日期。

    要真的是一个存在的日子——光对上正则的 `2026-13-45` 是蒙混过关。
    """
    for platform in PLATFORMS:
        value = _load(platform)["verified"]
        try:
            date.fromisoformat(value)
        except ValueError:
            raise AssertionError(
                f"{platform}.toml 的 verified={value!r} 不是一个存在的日期"
            ) from None


def test_every_platform_keeps_the_audio_gates():
    """规格 §5.2 说音频门槛所有平台都适用。

    视频号曾经漏掉这两道闸——闸缺席不报错，只是静悄悄地不生效。
    之前这条只查视频号一个平台；改成**遍历全部**，新平台进来就不再是例外。
    """
    for platform in PLATFORMS:
        media = _load(platform)["media"]
        assert media["max_audio_channels"] == 2, (
            f"{platform} 的 max_audio_channels 变成 {media['max_audio_channels']}"
        )
        assert media["max_sample_rate"] == 48000, (
            f"{platform} 的 max_sample_rate 变成 {media['max_sample_rate']}"
        )


def test_every_platform_demands_h264():
    """视频号部分安卓机不解 H.265，所有平台都要 H.264。"""
    for platform in PLATFORMS:
        codec = _load(platform)["media"]["require_video_codec"]
        assert codec == "h264", f"{platform} 的 require_video_codec 变成 {codec}"
