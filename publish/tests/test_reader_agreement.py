"""两个读者读同一份能力声明，结论必须一致。

契约层（``publish/publishkit/capability.py``）与头条号 adapter
（``toutiao/toutiao/capability.py``）是**两份独立实现**——接缝原则（规格
§11.1）不许它们互相 import。它们认的是**同一份 TOML 文件**。

两份实现各自演化，最容易出的偏差是「同一份 TOML，一个说行、另一个说不行」。
那种分歧不咬人（发布流水线走的是契约层，它是唯一闸门），但它让「双读者
单真相」变成空话：真相只有一份的时候，两个读者得先同意那一份是什么。

这条测试只**读** ``toutiao/``，不改它一个字节（与 ``test_capability_compat.py``
对 ``weixin/`` 的做法一样）。头条号那边挪了目录或改了导入路径时，本条自动 skip。

**那三处已知的分歧也钉在这里**——更严的那一边必须拒。「有意为之」不能只靠
文档说，得有人盯着：哪一边变松了，本条立刻红。
"""

import sys
from pathlib import Path

import pytest

from publishkit.capability import load_capability_file

REPO_ROOT = Path(__file__).resolve().parents[2]
TOUTIAO_DIR = REPO_ROOT / "toutiao"
REAL_DECLARATION = REPO_ROOT / "publish" / "capabilities" / "toutiao.toml"

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
paragraph_words = 200

[adapter]
package = "toutiao"
command = ["python3", "-m", "toutiao.cli"]
"""


def _adapter_loader():
    """The Toutiao adapter's loader, or ``None`` when it is not importable."""
    if not TOUTIAO_DIR.is_dir():
        return None
    if str(TOUTIAO_DIR) not in sys.path:
        sys.path.insert(0, str(TOUTIAO_DIR))
    try:
        from toutiao.capability import load_capability
    except Exception:  # pragma: no cover - 头条号那边在并行开发
        return None
    return load_capability


def _read_by_both(tmp_path, text, filename="toutiao.toml"):
    """Feed one declaration to both readers.

    Returns ``(contract, adapter)``; each entry is ``("ok", capability)``
    or ``("rejected", message)``.
    """
    path = tmp_path / filename
    path.write_text(text, encoding="utf-8")

    loader = _adapter_loader()
    if loader is None:
        pytest.skip("toutiao/ 不可用，跳过跨读者对照")

    results = []
    for load in (load_capability_file, loader):
        try:
            results.append(("ok", load(path)))
        except Exception as error:
            results.append(("rejected", str(error)))
    return results


def test_both_readers_read_the_real_declaration_the_same_way():
    """仓库里那一份真实声明：两个读者都要接受，而且读出的值要一样。"""
    loader = _adapter_loader()
    if loader is None:
        pytest.skip("toutiao/ 不可用，跳过跨读者对照")

    contract_cap = load_capability_file(REAL_DECLARATION)
    adapter_cap = loader(REAL_DECLARATION)

    assert contract_cap.id == adapter_cap.id == "toutiao"
    assert contract_cap.name == adapter_cap.name == "头条号"
    assert contract_cap.kind == adapter_cap.kind == "document"
    assert contract_cap.automation == adapter_cap.automation == "manual"
    assert contract_cap.review == adapter_cap.review == "platform"
    assert contract_cap.requires_certification is True
    assert adapter_cap.requires_certification is True
    assert contract_cap.requires_min_followers == adapter_cap.requires_min_followers == 1000

    for key in ("title_chars", "body_chars", "digest_chars", "image_bytes",
                "cover_ratio", "max_body_images", "paragraph_words"):
        assert contract_cap.limits[key] == getattr(adapter_cap.limits, key), key
    assert list(contract_cap.limits["image_formats"]) == list(adapter_cap.limits.image_formats)
    assert list(contract_cap.limits["cover_min_pixels"]) == list(
        adapter_cap.limits.cover_min_pixels
    )


@pytest.mark.parametrize(
    ("label", "text"),
    [
        (
            "拼错的 requires_certificaton",
            BASE_TOML.replace(
                "requires_certification = true", "requires_certificaton = true"
            ),
        ),
        ("kind 值域外", BASE_TOML.replace('kind = "document"', 'kind = "article"')),
        ("review 值域外", BASE_TOML.replace('review = "platform"', 'review = "human"')),
        (
            "verified 不是日期",
            BASE_TOML.replace(
                'review = "platform"', 'review = "platform"\nverified = "last tuesday"'
            ),
        ),
        ("顶层缺 name", BASE_TOML.replace('name = "头条号"\n', "")),
        ("顶层缺 kind", BASE_TOML.replace('kind = "document"\n', "")),
        ("顶层缺 review", BASE_TOML.replace('review = "platform"\n', "")),
        ("automation 值域外", BASE_TOML.replace('automation = "manual"', 'automation = "api"')),
    ],
    ids=[
        "typo_in_requires_certification",
        "kind_out_of_domain",
        "review_out_of_domain",
        "verified_not_a_date",
        "no_name",
        "no_kind",
        "no_review",
        "automation_out_of_domain",
    ],
)
def test_both_readers_reject_the_same_broken_declarations(tmp_path, label, text):
    """同一份坏 TOML，两个读者都要拒。

    这八行是契约层 docstring 那张对照表里「两边一致」的部分。最刺眼的一条是
    ``requires_certificaton``（拼错）：修之前 adapter 接受它，
    ``requires_certification`` 取默认值 False，于是「该平台不需要认证」——
    **一个门槛开关被拼写错误静默翻掉了**。
    """
    contract, adapter = _read_by_both(tmp_path, text)

    assert contract[0] == "rejected", "契约层接受了：{}".format(label)
    assert adapter[0] == "rejected", "adapter 接受了：{}".format(label)


@pytest.mark.parametrize(
    ("label", "text", "strict_one"),
    [
        (
            "id 与文件名不一致",
            BASE_TOML.replace('id = "toutiao"', 'id = "other"'),
            "contract",
        ),
        (
            "[adapter] 多一个键",
            BASE_TOML.replace(
                'command = ["python3", "-m", "toutiao.cli"]',
                'command = ["python3", "-m", "toutiao.cli"]\nextra = 1',
            ),
            "contract",
        ),
        (
            "[limits] 里的键拼错",
            BASE_TOML.replace("body_chars = 3000", "body_char = 3000"),
            "adapter",
        ),
    ],
    ids=[
        "id_not_matching_the_filename",
        "extra_key_in_the_adapter_table",
        "typo_in_a_limit_key",
    ],
)
def test_the_three_known_divergences_stay_where_the_spec_puts_them(
    tmp_path, label, text, strict_one
):
    """三处分歧是「有意为之」，但有意也得有人盯着。

    每处都是「一边更严」：更严的那一边必须拒。这条测试的作用是——哪一边
    变松了，它立刻红；分歧的位置变了（谁更严换了人），它也立刻红。
    """
    contract, adapter = _read_by_both(tmp_path, text)

    if strict_one == "contract":
        assert contract[0] == "rejected", "契约层不再拒了：{}".format(label)
        assert adapter[0] == "ok", "adapter 变严了，分歧的位置变了：{}".format(label)
    else:
        assert adapter[0] == "rejected", "adapter 不再拒了：{}".format(label)
        assert contract[0] == "ok", "契约层变严了，分歧的位置变了：{}".format(label)
