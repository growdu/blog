"""发布元数据的校验：缺一个字段就报错，不静默补默认值。

两条不同的语义必须分开测：

1. **平台整段缺失** = 这一期不发这个平台，合法，跳过。
2. **平台段内缺字段** = 想发但没填全，是配置错误，报错。

混为一谈的后果是：要么逼作者填一堆用不上的字段，
要么让「配了但配漏了」悄悄溜过去。
"""
import json

import pytest

from pyv import epmeta


def _write(tmp_path, payload):
    root = tmp_path / "publish"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "ep01.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return root


BASE = {
    "episode": "ep01",
    "title": "标题",
    "cover_at": 3.0,
    "channels": {"title": "短标题", "description": "简介", "topics": ["数据库"]},
    "bilibili": {
        "title": "标题",
        "description": "简介",
        "tags": ["数据库"],
        "tid": 231,
        "copyright": 1,
        "no_reprint": 1,
    },
}


def _meta(tmp_path, **overrides):
    payload = dict(BASE)
    payload.update(overrides)
    root = _write(tmp_path, payload)
    return epmeta.load_meta("ep01", root=root)


def _errors(findings):
    return [f for f in findings if f.level == epmeta.ERROR]


def test_a_complete_meta_has_no_errors(tmp_path):
    assert _errors(epmeta.check_meta(_meta(tmp_path))) == []


def test_episode_must_match_the_contract(tmp_path):
    findings = _errors(
        epmeta.check_meta(_meta(tmp_path), contract_episode="ep02"))
    assert any(f.rule_id == "epmeta.episode" for f in findings)


def test_missing_title_is_an_error(tmp_path):
    meta = _meta(tmp_path)
    broken = epmeta.EpisodeMeta(episode=meta.episode, title="", cover_at=meta.cover_at)
    assert any(f.rule_id == "epmeta.required"
               for f in _errors(epmeta.check_meta(broken)))


def test_cover_at_beyond_the_duration_is_an_error(tmp_path):
    findings = _errors(
        epmeta.check_meta(_meta(tmp_path, cover_at=30.0), duration=10.0))
    assert any(f.rule_id == "epmeta.cover-at" for f in findings)


def test_cover_at_exactly_at_the_duration_is_allowed(tmp_path):
    """规格说 cover_at ≤ 成片时长——正好落在片尾是合法的，不是越界。"""
    findings = _errors(
        epmeta.check_meta(_meta(tmp_path, cover_at=10.0), duration=10.0))
    assert [f for f in findings if f.rule_id == "epmeta.cover-at"] == []


def test_a_missing_platform_section_is_only_a_warning(tmp_path):
    payload = dict(BASE)
    payload.pop("channels")
    root = _write(tmp_path, payload)
    meta = epmeta.load_meta("ep01", root=root)
    findings = epmeta.check_meta(meta)
    warnings = [f for f in findings if f.level == epmeta.WARNING]
    assert any(f.rule_id == "epmeta.platform-missing" for f in warnings)
    assert _errors(findings) == []


def test_a_missing_field_inside_a_platform_section_is_an_error(tmp_path):
    payload = dict(BASE)
    payload["channels"] = {"title": "短标题", "topics": ["数据库"]}
    root = _write(tmp_path, payload)
    meta = epmeta.load_meta("ep01", root=root)
    findings = _errors(epmeta.check_meta(meta))
    assert any(f.rule_id == "epmeta.platform-required" for f in findings)


def test_a_title_over_the_limit_is_an_error_and_is_not_truncated(tmp_path):
    payload = dict(BASE)
    payload["channels"] = {
        "title": "字" * 23, "description": "简介", "topics": ["数据库"],
    }
    root = _write(tmp_path, payload)
    meta = epmeta.load_meta("ep01", root=root)
    findings = _errors(epmeta.check_meta(meta))
    assert any(f.rule_id == "epmeta.text-limit" for f in findings)
    # 不截断：原文一字不动
    assert meta.platform("channels")["title"] == "字" * 23


def test_too_many_topics_is_an_error(tmp_path):
    payload = dict(BASE)
    payload["channels"] = {
        "title": "短标题", "description": "简介",
        "topics": ["一", "二", "三", "四", "五", "六"],
    }
    root = _write(tmp_path, payload)
    meta = epmeta.load_meta("ep01", root=root)
    findings = _errors(epmeta.check_meta(meta))
    assert any(f.rule_id == "epmeta.list-limit" for f in findings)


def test_a_non_integer_tid_is_an_error(tmp_path):
    payload = dict(BASE)
    payload["bilibili"] = dict(BASE["bilibili"], tid="二百三十一")
    root = _write(tmp_path, payload)
    meta = epmeta.load_meta("ep01", root=root)
    findings = _errors(epmeta.check_meta(meta))
    assert any(f.rule_id == "epmeta.int-field" for f in findings)


def test_a_missing_file_raises(tmp_path):
    with pytest.raises(epmeta.MetaError):
        epmeta.load_meta("ep99", root=tmp_path)


# --- 列表限额：两个平台的总限额口径不一样 --------------------------------


def test_too_many_tags_is_an_error(tmp_path):
    """B站的 `tags_chars` 是**逗号分隔后的总字符数**，不是标签个数。

    规格 §4.3：「英文逗号分隔后总长 < 200 字」。当成个数上限就放过了
    「199 个 1 字标签」这种真实超限的情况。
    """
    payload = dict(BASE)
    payload["bilibili"] = dict(
        BASE["bilibili"],
        tags=["x" * 20] * 11,   # 11 项，单项没超 20 字，但总长 219 > 199
    )
    root = _write(tmp_path, payload)
    meta = epmeta.load_meta("ep01", root=root)
    findings = _errors(epmeta.check_meta(meta))
    assert any(f.rule_id == "epmeta.list-limit" for f in findings)


def test_a_long_joined_tag_string_is_an_error_even_with_few_tags(tmp_path):
    """标签少但总长超限也要报错——这正是「当成个数上限」漏掉的那一类。"""
    payload = dict(BASE)
    payload["bilibili"] = dict(
        BASE["bilibili"],
        tags=["a" * 20, "b" * 20, "c" * 20, "d" * 20, "e" * 20,
              "f" * 20, "g" * 20, "h" * 20, "i" * 20, "j" * 20],
    )
    root = _write(tmp_path, payload)
    meta = epmeta.load_meta("ep01", root=root)
    findings = _errors(epmeta.check_meta(meta))
    assert any(f.rule_id == "epmeta.list-limit" for f in findings)


def test_the_joined_length_counts_the_separators(tmp_path):
    """分隔用的逗号也算进总长——平台收到的是拼好的那一串。"""
    payload = dict(BASE)
    payload["bilibili"] = dict(
        BASE["bilibili"], tags=["a" * 20] * 10,
    )
    root = _write(tmp_path, payload)
    meta = epmeta.load_meta("ep01", root=root)
    # 10 项 × 20 字 + 9 个逗号 = 209 > 199
    findings = _errors(epmeta.check_meta(meta))
    assert any(f.rule_id == "epmeta.list-limit" for f in findings)


def test_topics_still_use_the_count_limit(tmp_path):
    """视频号的话题上限是**个数**（5 个），口径不能跟着 B站一起改。"""
    payload = dict(BASE)
    payload["channels"] = {
        "title": "短标题", "description": "简介",
        "topics": ["一", "二", "三", "四", "五", "六"],
    }
    root = _write(tmp_path, payload)
    meta = epmeta.load_meta("ep01", root=root)
    findings = _errors(epmeta.check_meta(meta))
    assert any(f.rule_id == "epmeta.list-limit" for f in findings)


# --- 整数字段的取值域 ------------------------------------------------------


def test_an_out_of_domain_copyright_is_an_error(tmp_path):
    """copyright 只认 1（原创）与 2（转载）。3 是平台会拒的值。"""
    payload = dict(BASE)
    payload["bilibili"] = dict(BASE["bilibili"], copyright=3)
    root = _write(tmp_path, payload)
    meta = epmeta.load_meta("ep01", root=root)
    findings = _errors(epmeta.check_meta(meta))
    assert any(f.rule_id == "epmeta.int-domain" for f in findings)


def test_an_out_of_domain_no_reprint_is_an_error(tmp_path):
    payload = dict(BASE)
    payload["bilibili"] = dict(BASE["bilibili"], no_reprint=2)
    root = _write(tmp_path, payload)
    meta = epmeta.load_meta("ep01", root=root)
    findings = _errors(epmeta.check_meta(meta))
    assert any(f.rule_id == "epmeta.int-domain" for f in findings)


def test_a_reprint_without_a_source_is_an_error(tmp_path):
    """转载必须给 source——平台会拒没有来源的转载（规格 §4.3）。"""
    payload = dict(BASE)
    payload["bilibili"] = dict(BASE["bilibili"], copyright=2, no_reprint=0)
    root = _write(tmp_path, payload)
    meta = epmeta.load_meta("ep01", root=root)
    findings = _errors(epmeta.check_meta(meta))
    assert any(f.rule_id == "epmeta.conditional-required" for f in findings)


def test_a_reprint_with_a_source_is_fine(tmp_path):
    payload = dict(BASE)
    payload["bilibili"] = dict(
        BASE["bilibili"], copyright=2, no_reprint=0, source="https://growdu.cn/x")
    root = _write(tmp_path, payload)
    meta = epmeta.load_meta("ep01", root=root)
    assert _errors(epmeta.check_meta(meta)) == []


def test_an_original_needs_no_source(tmp_path):
    """原创（copyright = 1）不要求 source——那是转载才要的字段。"""
    root = _write(tmp_path, BASE)
    meta = epmeta.load_meta("ep01", root=root)
    assert _errors(epmeta.check_meta(meta)) == []


# --- 元数据本身坏了 --------------------------------------------------------


def test_a_non_numeric_cover_at_raises_a_meta_error(tmp_path):
    """`float("x")` 抛的裸 ValueError 会被 CLI 漏成 traceback。"""
    payload = dict(BASE, cover_at="第十八秒")
    root = _write(tmp_path, payload)
    with pytest.raises(epmeta.MetaError):
        epmeta.load_meta("ep01", root=root)


def test_broken_json_raises_a_meta_error(tmp_path):
    root = tmp_path / "publish"
    root.mkdir(parents=True, exist_ok=True)
    (root / "ep01.json").write_text("{不是 JSON", encoding="utf-8")
    with pytest.raises(epmeta.MetaError):
        epmeta.load_meta("ep01", root=root)
