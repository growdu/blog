"""内容契约：front matter 解析、字段校验、候选集判定。

这一层的测试盯三件事：
1. 解析语义在 **LF 输入下**与 ``weixin/wechat/posts.py`` 的
   ``parse_front_matter()`` 逐条一致（规格 §4.2 明文要求）；CRLF 输入下
   契约层更宽松（weixin 那份不认 CRLF）——这条差异是钉死的有意为之，
   由下面那条用例显式断言；
2. 坏字段必须以 ``ContractFieldError`` 明确失败，不漏出裸 KeyError / TypeError；
3. ``platforms`` 非空即进入发布候选集（06 规格 §3.2）。
"""

from datetime import date
from pathlib import Path
import sys

import pytest

from publishkit import (
    CONTENT_KINDS,
    PASSTHROUGH_FIELDS,
    REPRINT_POLICIES,
    ContentContract,
    ContractError,
    ContractFieldError,
    ContractFileError,
    PublishKitError,
    contract_from_fields,
    parse_front_matter,
    read_contract,
    validate_fields,
)

FULL_DRAFT = """\
---
title: "逻辑复制大事务同步要 30 分钟？"
short_title: "大事务同步"
tldr: "大事务同步把 WAL 推满了。"
description: "讲清楚大事务同步为什么慢。"
difficulty: 3
cover: images/cover.jpg
reprintPolicy: cc_by_nd
kind: post
platforms:
  - wechat
  - toutiao
publish_on: 2026-11-13
---

# 逻辑复制大事务同步要 30 分钟？

正文第一段。
"""


# --- 解析 ---------------------------------------------------------------


def test_parse_front_matter_scalars_and_lists():
    fields, body = parse_front_matter(FULL_DRAFT)

    assert fields["title"] == "逻辑复制大事务同步要 30 分钟？"
    assert fields["short_title"] == "大事务同步"
    assert fields["tldr"] == "大事务同步把 WAL 推满了。"
    assert fields["description"] == "讲清楚大事务同步为什么慢。"
    assert fields["difficulty"] == "3"
    assert fields["cover"] == "images/cover.jpg"
    assert fields["reprintPolicy"] == "cc_by_nd"
    assert fields["kind"] == "post"
    assert fields["publish_on"] == "2026-11-13"
    assert fields["platforms"] == ["wechat", "toutiao"]
    assert body.lstrip().startswith("# 逻辑复制大事务同步要 30 分钟？")


def test_parse_front_matter_without_front_matter():
    fields, body = parse_front_matter("# 只有正文\n")

    assert fields == {}
    assert body == "# 只有正文\n"


def test_parse_front_matter_strips_quotes():
    fields, _ = parse_front_matter('---\ntitle: "带引号"\n---\n\n正文\n')

    assert fields["title"] == "带引号"


def test_parse_front_matter_keeps_single_quotes():
    fields, _ = parse_front_matter("---\ntitle: '带引号'\n---\n\n正文\n")

    assert fields["title"] == "带引号"


def test_parse_front_matter_keeps_quotes_inside_the_value():
    fields, _ = parse_front_matter('---\ntitle: "他说"你好""\n---\n\n正文\n')

    assert fields["title"] == '他说"你好"'


def test_empty_list_header_becomes_an_empty_list():
    """``cover:`` 后面没有条目 → 空列表。这与 weixin 的解析器一致。"""
    fields, _ = parse_front_matter("---\ncover:\ntitle: x\n---\n\n正文\n")

    assert fields["cover"] == []
    assert fields["title"] == "x"


def test_single_item_list_stays_a_list():
    fields, _ = parse_front_matter("---\nplatforms:\n  - wechat\n---\n\n正文\n")

    assert fields["platforms"] == ["wechat"]


def test_a_new_top_level_key_closes_the_previous_list():
    fields, _ = parse_front_matter(
        "---\nplatforms:\n  - wechat\n  - toutiao\npublish_on: 2026-11-13\n---\n\n正文\n"
    )

    assert fields["platforms"] == ["wechat", "toutiao"]
    assert fields["publish_on"] == "2026-11-13"


def test_list_items_may_be_quoted():
    fields, _ = parse_front_matter('---\nplatforms:\n  - "wechat"\n---\n\n正文\n')

    assert fields["platforms"] == ["wechat"]


def test_crlf_front_matter_is_parsed():
    fields, _ = parse_front_matter("---\r\ntitle: x\r\n---\r\n\r\n正文\r\n")

    assert fields["title"] == "x"


# --- 契约读取 -----------------------------------------------------------


def test_read_contract_reads_platforms_and_publish_on(tmp_path):
    path = tmp_path / "post.md"
    path.write_text(FULL_DRAFT, encoding="utf-8")

    contract = read_contract(path)

    assert contract.platforms == ("wechat", "toutiao")
    assert contract.publish_on == "2026-11-13"
    assert contract.title == "逻辑复制大事务同步要 30 分钟？"
    assert contract.kind == "post"
    assert contract.difficulty == 3
    assert contract.short_title == "大事务同步"
    assert contract.tldr == "大事务同步把 WAL 推满了。"
    assert contract.description == "讲清楚大事务同步为什么慢。"
    assert contract.cover == "images/cover.jpg"
    assert contract.reprint_policy == "cc_by_nd"
    assert contract.path == path


def test_contract_defaults_kind_to_post(tmp_path):
    path = tmp_path / "post.md"
    path.write_text("---\ntitle: x\n---\n\n正文\n", encoding="utf-8")

    assert read_contract(path).kind == "post"


def test_contract_reports_a_missing_file(tmp_path):
    with pytest.raises(ContractFileError):
        read_contract(tmp_path / "nope.md")


def test_errors_share_one_base_class(tmp_path):
    with pytest.raises(PublishKitError):
        read_contract(tmp_path / "nope.md")
    assert issubclass(ContractFieldError, ContractError)
    assert issubclass(ContractFileError, ContractError)


# --- 候选集 -------------------------------------------------------------


def test_non_empty_platforms_makes_a_publish_candidate(tmp_path):
    path = tmp_path / "post.md"
    path.write_text(FULL_DRAFT, encoding="utf-8")

    assert read_contract(path).is_publish_candidate is True


def test_no_platforms_is_not_a_publish_candidate(tmp_path):
    path = tmp_path / "post.md"
    path.write_text("---\ntitle: x\n---\n\n正文\n", encoding="utf-8")

    assert read_contract(path).is_publish_candidate is False


def test_empty_platforms_list_is_not_a_publish_candidate(tmp_path):
    path = tmp_path / "post.md"
    path.write_text("---\ntitle: x\nplatforms:\n---\n\n正文\n", encoding="utf-8")

    contract = read_contract(path)

    assert contract.platforms == ()
    assert contract.is_publish_candidate is False


# --- 坏输入 -------------------------------------------------------------


def test_platforms_must_be_a_list(tmp_path):
    path = tmp_path / "post.md"
    path.write_text("---\ntitle: x\nplatforms: wechat\n---\n\n正文\n", encoding="utf-8")

    with pytest.raises(ContractFieldError) as excinfo:
        read_contract(path)
    assert "platforms" in str(excinfo.value)


def test_platforms_items_must_be_non_empty_strings(tmp_path):
    path = tmp_path / "post.md"
    path.write_text("---\ntitle: x\nplatforms:\n  - wechat\n  - \"\"\n---\n\n正文\n", encoding="utf-8")

    with pytest.raises(ContractFieldError) as excinfo:
        read_contract(path)
    assert "platforms" in str(excinfo.value)


def test_platform_id_must_look_like_an_id(tmp_path):
    path = tmp_path / "post.md"
    path.write_text("---\ntitle: x\nplatforms:\n  - WeChat\n---\n\n正文\n", encoding="utf-8")

    with pytest.raises(ContractFieldError) as excinfo:
        read_contract(path)
    assert "platforms" in str(excinfo.value)


@pytest.mark.parametrize(
    "bad_date",
    ["2026/11/13", "26-11-13", "2026-11", "not-a-date", "20261113"],
)
def test_publish_on_must_be_yyyy_mm_dd(tmp_path, bad_date):
    path = tmp_path / "post.md"
    path.write_text(
        "---\ntitle: x\npublish_on: {}\n---\n\n正文\n".format(bad_date),
        encoding="utf-8",
    )

    with pytest.raises(ContractFieldError) as excinfo:
        read_contract(path)
    assert "publish_on" in str(excinfo.value)


def test_publish_on_must_be_a_real_date(tmp_path):
    path = tmp_path / "post.md"
    path.write_text("---\ntitle: x\npublish_on: 2026-02-30\n---\n\n正文\n", encoding="utf-8")

    with pytest.raises(ContractFieldError) as excinfo:
        read_contract(path)
    assert "publish_on" in str(excinfo.value)


def test_publish_on_accepts_a_real_date(tmp_path):
    path = tmp_path / "post.md"
    path.write_text("---\ntitle: x\npublish_on: 2026-11-13\n---\n\n正文\n", encoding="utf-8")

    assert read_contract(path).publish_on == "2026-11-13"


def test_kind_must_be_in_the_content_domain(tmp_path):
    """内容契约的 kind 是 post / video——不是能力模型的 document / video。"""
    path = tmp_path / "post.md"
    path.write_text("---\ntitle: x\nkind: document\n---\n\n正文\n", encoding="utf-8")

    with pytest.raises(ContractFieldError) as excinfo:
        read_contract(path)
    assert "kind" in str(excinfo.value)
    assert set(CONTENT_KINDS) == {"post", "video"}


@pytest.mark.parametrize("bad_difficulty", ["0", "6", "高", "3.5", "-1"])
def test_difficulty_must_be_one_to_five(tmp_path, bad_difficulty):
    path = tmp_path / "post.md"
    path.write_text(
        "---\ntitle: x\ndifficulty: {}\n---\n\n正文\n".format(bad_difficulty),
        encoding="utf-8",
    )

    with pytest.raises(ContractFieldError) as excinfo:
        read_contract(path)
    assert "difficulty" in str(excinfo.value)


def test_title_over_eighty_chars_is_rejected(tmp_path):
    path = tmp_path / "post.md"
    path.write_text("---\ntitle: {}\n---\n\n正文\n".format("标" * 81), encoding="utf-8")

    with pytest.raises(ContractFieldError) as excinfo:
        read_contract(path)
    assert "title" in str(excinfo.value)


def test_tldr_over_one_hundred_twenty_chars_is_rejected(tmp_path):
    path = tmp_path / "post.md"
    path.write_text("---\ntitle: x\ntldr: {}\n---\n\n正文\n".format("句" * 121), encoding="utf-8")

    with pytest.raises(ContractFieldError) as excinfo:
        read_contract(path)
    assert "tldr" in str(excinfo.value)


def test_description_over_one_hundred_fifty_chars_is_rejected(tmp_path):
    path = tmp_path / "post.md"
    path.write_text(
        "---\ntitle: x\ndescription: {}\n---\n\n正文\n".format("句" * 151),
        encoding="utf-8",
    )

    with pytest.raises(ContractFieldError) as excinfo:
        read_contract(path)
    assert "description" in str(excinfo.value)


def test_unknown_reprint_policy_is_rejected(tmp_path):
    path = tmp_path / "post.md"
    path.write_text("---\ntitle: x\nreprintPolicy: free\n---\n\n正文\n", encoding="utf-8")

    with pytest.raises(ContractFieldError) as excinfo:
        read_contract(path)
    assert "reprintPolicy" in str(excinfo.value)


def test_known_reprint_policies_are_accepted():
    for policy in REPRINT_POLICIES:
        fields = {"title": "x", "reprintPolicy": policy}
        assert validate_fields(fields) == []


# --- 校验器 -------------------------------------------------------------


def test_validate_fields_collects_every_violation_at_once():
    fields = {
        "title": "标" * 81,
        "platforms": "wechat",
        "publish_on": "2026-02-30",
        "difficulty": "9",
        "kind": "document",
    }

    violations = validate_fields(fields)

    assert len(violations) == 5
    joined = "；".join(violations)
    for field in ("title", "platforms", "publish_on", "difficulty", "kind"):
        assert field in joined


def test_validate_fields_accepts_a_clean_draft():
    assert validate_fields(
        {
            "title": "x",
            "platforms": ["wechat"],
            "publish_on": "2026-11-13",
            "difficulty": "1",
            "kind": "post",
        }
    ) == []


def test_contract_from_fields_accepts_parsed_fields():
    fields, _ = parse_front_matter(FULL_DRAFT)

    contract = contract_from_fields(fields)

    assert isinstance(contract, ContentContract)
    assert contract.platforms == ("wechat", "toutiao")


def test_passthrough_whitelist_covers_the_spec_fields():
    """§4.1 的白名单字段一个都不能少。"""
    assert set(PASSTHROUGH_FIELDS) == {
        "title",
        "short_title",
        "tldr",
        "description",
        "difficulty",
        "cover",
        "reprintPolicy",
        "kind",
        "platforms",
        "publish_on",
    }


def test_undeclared_fields_are_dropped_not_carried():
    """未声明的顶层字段一律丢弃——白名单透传，不做全文转储。"""
    fields, _ = parse_front_matter("---\ntitle: x\nsecret: leaked\n---\n\n正文\n")

    contract = contract_from_fields(fields)

    assert set(contract.__dataclass_fields__) == {
        "path",
        "title",
        "kind",
        "platforms",
        "publish_on",
        "short_title",
        "tldr",
        "description",
        "difficulty",
        "cover",
        "reprint_policy",
    }
    assert not hasattr(contract, "secret")


def test_contract_reads_a_real_calendar_date():
    """publish_on 的日期是真的，不是只长得像。"""
    contract = contract_from_fields({"publish_on": "2026-11-13"})

    assert date.fromisoformat(contract.publish_on) == date(2026, 11, 13)


# --- 与 weixin 解析器的对齐 ---------------------------------------------
#
# 规格 §4.2：「这套格式不是新发明……契约与它逐条对齐，不是各写各的。」
# 这里的对照表是 weixin/wechat/posts.py 的 parse_front_matter()——两份实现
# 在 **LF 输入下**必须对同一段 front matter 给出同一个答案。这条测试**只读**
# weixin/，不改它一个字节；weixin 那边挪了目录或改了导入路径时，本条自动 skip。
#
# **CRLF 是唯一被允许的分歧**（契约层更宽松），由下面那条用例显式钉住。

WEIXIN_DIR = Path(__file__).resolve().parents[2] / "weixin"


def _weixin_parser():
    if not WEIXIN_DIR.is_dir():
        return None
    if str(WEIXIN_DIR) not in sys.path:
        sys.path.insert(0, str(WEIXIN_DIR))
    try:
        from wechat.posts import parse_front_matter as weixin_parser
    except Exception:  # pragma: no cover - weixin 那边在并行开发
        return None
    return weixin_parser


def test_parser_matches_the_weixin_parser_on_the_real_corpus():
    weixin_parser = _weixin_parser()
    if weixin_parser is None:
        pytest.skip("weixin/ 不可用，跳过与 wechat.posts 的对照")

    docs = Path(__file__).resolve().parents[2] / "docs"
    drafts = [
        path
        for path in sorted(docs.rglob("*.md"))
        if path.read_text(encoding="utf-8", errors="replace").startswith("---")
    ]
    if not drafts:
        pytest.skip("docs/ 下没有带 front matter 的母稿")

    mismatched = []
    for path in drafts:
        text = path.read_text(encoding="utf-8", errors="replace")
        mine_fields, _ = parse_front_matter(text)
        their_fields, _ = weixin_parser(text)
        if mine_fields != their_fields:
            mismatched.append(str(path))

    assert not mismatched, "解析结果与 wechat.posts 不一致：{}".format(mismatched)


def test_crlf_is_the_one_deliberate_divergence_from_the_weixin_parser():
    """CRLF 下两边给出不同答案——这是钉死的有意为之，不是漏网。

    契约层认 CRLF（``^---\\r?\\n``），weixin 那份只认 LF（``^---\\n``），
    所以同一段 CRLF 文本，契约层解析出字段、weixin 那份解析出空。

    为什么保留这个分歧：契约层的读者不止 weixin 一个（还有未来的 B站 /
    视频号 / 头条），对母稿格式更宽容是实质性的健壮性；而「与 weixin 一致」
    这个承诺不该把两边互相绑定（§11.1「各改各的」）。代价是两边对同一段
    CRLF 文本给出不同答案——所以那句话不能说「逐条一致」，钉在这里。
    """
    weixin_parser = _weixin_parser()
    if weixin_parser is None:
        pytest.skip("weixin/ 不可用，跳过与 wechat.posts 的对照")

    text = "---\r\ntitle: x\r\nplatforms:\r\n  - wechat\r\n---\r\n\r\n正文\r\n"

    mine_fields, _ = parse_front_matter(text)
    their_fields, _ = weixin_parser(text)

    assert mine_fields == {"title": "x", "platforms": ["wechat"]}
    assert their_fields == {}
