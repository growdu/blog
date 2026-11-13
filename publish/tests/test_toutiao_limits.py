"""头条号的能力声明必须等于 2026-11-13 实测出来的数。

这一份 TOML 是**契约层与头条号 adapter 共同认的唯一真相**（规格 §11.1 的
接缝）。限额是数据——但数据没有测试守着的话，「顺手改回旧值」没有任何人会
发现：平台不会报错，测试不会报警，最后传上去的封面是一张竖图，而平台的
封面框是横的。

所以这里钉的不是「某个数」，而是「实测那天测到的数」。每一条的出处见
``toutiao/docs/02-试点记录.md`` §R2。改数字要同时改那份记录——
两边对不上，说明其中一个不是实测来的。
"""

from pathlib import Path

from publishkit.capability import load_capability_file

REPO_ROOT = Path(__file__).resolve().parents[2]
DECLARATION = REPO_ROOT / "publish" / "capabilities" / "toutiao.toml"

#: 2026-11-13 实测出来的限额。原样抄在这里，而不是从文件里读出来再断言
#: 自己——那只是把文件内容抄了一遍，测不出「被改回去了」。
MEASURED_LIMITS = {
    "title_chars": 30,
    "body_chars": 3000,
    "digest_chars": 120,
    "image_bytes": 20971520,
    "image_formats": ["webp"],
    "cover_ratio": "452:352",
    "cover_min_pixels": [452, 352],
    "max_body_images": 3,
    "paragraph_words": 200,
}

MEASUREMENT_DATE = "2026-11-13"


def test_limits_are_the_measured_values():
    """每个限额都等于实测值。"""
    limits = load_capability_file(DECLARATION).limits

    for key, expected in MEASURED_LIMITS.items():
        actual = limits[key]
        if isinstance(expected, list):
            assert list(actual) == expected, key
        else:
            assert actual == expected, key


def test_verified_is_the_day_of_the_measurement():
    """``verified`` 是复核日期，不是「大概复核过」。"""
    cap = load_capability_file(DECLARATION)
    assert cap.verified == MEASUREMENT_DATE


def test_the_cover_is_landscape_not_portrait():
    """封面是横图——这是 2026-11-13 最大的一个更正。

    早先按「3:4 竖图」假设切封面。实测平台的封面框是 152×118（≈1.29:1 横图），
    上传面板原文写的是「封面图尺寸建议大于 672*462，不可小于 452*352」，
    平台把正文首图自动裁成 1620×1261（1.285:1）。

    竖图切法不会报错，只会被平台再裁一次——而且裁掉的是上下两半，
    宽图被切成一条窄竖片，图里的字就没人看得清了。

    这条断言写的是「横图」这个**结论**，不是「452:352」这个数字：
    比例将来微调，结论不变；哪天又有人改回竖的，本条立刻红。
    """
    ratio = load_capability_file(DECLARATION).limits["cover_ratio"]
    width, height = (int(part) for part in ratio.split(":"))
    assert width > height, "封面比例 {} 是竖图，平台要的是横图".format(ratio)


def test_the_measurement_leaves_a_trace_in_the_declaration():
    """数字的出处必须留在文件里。

    限额被抄进代码库以后，最容易丢的就是「这个数是怎么来的」——
    半年后没人敢改，也没人知道该不该改。
    """
    text = DECLARATION.read_text(encoding="utf-8")

    assert MEASUREMENT_DATE in text, "声明里没有实测日期"
    assert "02-试点记录.md" in text, "声明里没有指向实测记录的出处"
