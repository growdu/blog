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
