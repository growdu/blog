"""B站版文案：切片与标签拼装。"""

import pytest

from bilibili import contract


def test_slice_copy_reads_the_bilibili_section(meta):
    copy = contract.slice_copy(meta)
    assert copy.title == "一个 64 位计数器，决定所有事务的提交顺序"
    assert copy.tags == ("openGauss", "数据库", "源码")
    assert copy.tid == 231
    assert copy.copyright == 1
    assert copy.no_reprint == 1


def test_tags_line_is_comma_separated():
    """B站的 tag 是英文逗号分隔的一串，不是 # 井号。"""
    assert contract.tags_line(("数据库", "源码")) == "数据库,源码"


def test_tags_line_of_nothing_is_empty():
    assert contract.tags_line(()) == ""


def test_reprint_keeps_the_source_as_it_is():
    """adapter **不判**平台规则，只把文案取出来。

    「转载必须给 source」由契约层（`pyv.epmeta` 的 `required_when`）负责——
    两处各判一次会出现两个结论（规格 §6.1.3）。
    """
    from pyv import epmeta

    meta_with_reprint = epmeta.EpisodeMeta(
        episode="ep02", title="x", cover_at=1.0,
        bilibili={
            "title": "t", "description": "d", "tags": ["x"],
            "tid": 231, "copyright": 2, "no_reprint": 0,
            "source": "https://growdu.cn/2026/11/12/life/aiv/",
        },
    )
    copy = contract.slice_copy(meta_with_reprint)
    assert copy.copyright == 2
    assert copy.source == "https://growdu.cn/2026/11/12/life/aiv/"


def test_the_contract_layer_rejects_a_reprint_without_a_source():
    """规则本身在契约层判——出包前那道闸会把它拦下来。"""
    from pyv import epmeta

    meta_with_reprint = epmeta.EpisodeMeta(
        episode="ep02", title="x", cover_at=1.0,
        bilibili={
            "title": "t", "description": "d", "tags": ["x"],
            "tid": 231, "copyright": 2, "no_reprint": 0,
        },
    )
    findings = epmeta.check_meta(meta_with_reprint)
    assert any(f.rule_id == "epmeta.conditional-required" for f in findings), (
        "转载缺 source 没有被契约层拦下来")


def test_a_missing_bilibili_section_is_a_configuration_error():
    """这一期不发B站 ≠ 配置写错了。缺整段要报错，别默默出一个空标题的包。"""
    from pyv import epmeta

    meta = epmeta.EpisodeMeta(episode="ep02", title="x", cover_at=1.0)
    with pytest.raises(epmeta.MetaError):
        contract.slice_copy(meta)
