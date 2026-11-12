"""视频号版文案：切片规则与话题拼装。"""

from channels import contract


def test_slice_copy_reads_the_channels_section(meta):
    copy = contract.slice_copy(meta)
    assert copy.title == "32 核机器，解码只占 1 核"
    assert copy.topics == ("PostgreSQL", "逻辑复制", "数据库内核")
    assert copy.cover_at == 1.0


def test_topics_line_uses_hash_prefixes():
    assert contract.topics_line(("数据库", "内核")) == "#数据库 #内核"


def test_topics_line_of_nothing_is_empty():
    assert contract.topics_line(()) == ""


def test_slice_copy_without_a_channels_section_raises(meta):
    import pytest

    from pyv import epmeta

    bare = epmeta.EpisodeMeta(episode="ep01", title="x", cover_at=1.0)
    with pytest.raises(epmeta.MetaError):
        contract.slice_copy(bare)
