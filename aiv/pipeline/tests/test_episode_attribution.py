"""每一期的归属口径红线。

2026-11-12 用户指出：并行解码不是 PostgreSQL 18 的功能，而是 openGauss
（以及 Vastbase）有的功能，EP01 因此整期重做。这组测试把这次的修正钉住：

1. **并行解码是 openGauss 的实现**——EP01 的口播、字幕、画面里不得出现
   PostgreSQL 18；
2. **Vastbase 不并列**——仓库里没有任何 Vastbase 材料，没有依据的并列一律不写；
3. **提交顺序整段留给 EP02**——EP01 不得出现任何「顺序」的断言；
4. **「2 到 5 倍」必须带归因**——数字出自作者本人在 openGauss 上的本地压测，
   口播、字幕、画面、选题库四处都要带上归因。

查的是**真正会出现在片子里、会被读出去**的地方：口播稿的句子、字幕表、
视觉分镜契约里的文案。只查选题库那份「说明文字」是不够的——
说明会改，画面不会自己改。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pyv import align
from pyv import contract as contract_mod
from pyv import topics as topics_mod

ROOT = Path(__file__).resolve().parents[2]
EP01_SCRIPT = ROOT / "字幕-并行解码.md"
EP01_CONTRACT = ROOT / "contracts" / "pg-parallel-decode.json"

BENCH_NUMBER = "2–5 倍"


@pytest.fixture(scope="module")
def ep01_video_text() -> str:
    """EP01 里会被念出来、被烧进画面的全部文字。"""
    sentences = align.parse_script(EP01_SCRIPT)
    subtitles = align.parse_subtitle_table(EP01_SCRIPT)
    contract = contract_mod.load_contract(EP01_CONTRACT)

    parts: list[str] = list(sentences) + list(subtitles) + [contract.title]
    for segment in contract.segments:
        for value in segment.params.values():
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, list):
                parts.extend(str(item) for item in value)
    return "\n".join(parts)


@pytest.fixture(scope="module")
def ep01_topic():
    """选题库里的 EP01 条目。"""
    for episode in topics_mod.parse_topics():
        if episode.id == "ep01":
            return episode
    raise AssertionError("选题库里没有 EP01")


def test_ep01_does_not_claim_postgresql_18(ep01_video_text):
    """并行解码是 openGauss 的实现，不是 PostgreSQL 18 的能力。"""
    assert "PostgreSQL 18" not in ep01_video_text, \
        "EP01 不得把并行解码说成 PostgreSQL 18 的功能"


def test_ep01_does_not_mention_vastbase(ep01_video_text, ep01_topic):
    """仓库里没有任何 Vastbase 材料，没有依据的并列不写。"""
    assert "Vastbase" not in ep01_video_text
    assert "Vastbase" not in ep01_topic.text()


def test_ep01_leaves_the_commit_order_to_ep02(ep01_video_text):
    """顺序问题整段留给 EP02，本期一个字都不提。"""
    assert "顺序" not in ep01_video_text, \
        "EP01 不得出现提交顺序的断言——那是 EP02（CSN 全序）的内容"


def test_ep01_cites_the_opengauss_design_doc(ep01_topic):
    """出处必须落在 openGauss 的真实实现上，不能再引 PostgreSQL 的设计提案。"""
    paths = [path for path, _ in ep01_topic.docs]
    assert any("opengauss-parallel-decoding-design" in path for path in paths), \
        "EP01 的关联文档里必须有 openGauss 的并行解码设计"
    assert not any("概要设计说明书" in path for path in paths), \
        "PG18 的并行解码设计提案只是提案，不能当 EP01 的出处"


def test_bench_number_carries_the_author_attribution(ep01_video_text):
    """「2 到 5 倍」是作者本人压出来的，念出来时必须带着归因。"""
    sentences = align.parse_script(EP01_SCRIPT)
    hits = [s for s in sentences if "2 到 5 倍" in s]
    assert hits, "口播里应当有那组压测数字"
    for sentence in hits:
        assert "openGauss" in sentence, "必须说清是在哪个系统上压的"
        assert "我" in sentence, "必须带作者本人的归因"


def test_bench_number_is_attributed_on_screen(ep01_video_text):
    """画面上写「2–5 倍」时，旁边也必须有归因，不能只有数字。"""
    contract = contract_mod.load_contract(EP01_CONTRACT)
    segment = next(s for s in contract.segments if s.renderer.endswith("s05_bench"))
    assert segment.params["callout"] == BENCH_NUMBER
    assert "我" in segment.params["caption"], \
        "画面上的压测数字必须标注是作者本人自己压的"
    assert "openGauss" in segment.params["title"], \
        "画面上要写清压测是在 openGauss 上做的"


def test_bench_number_attribution_is_in_the_topics_entry(ep01_topic):
    """选题库的「数字与出处」表里也必须带作者本人归因。"""
    hits = [row for row in ep01_topic.evidence if "2 到 5 倍" in row[0]]
    assert hits, "EP01 的数字与出处表里应当有那组压测数字"
    for _, source, _ in hits:
        assert "作者本人" in source or "我自己" in source, \
            "实测数字必须带作者本人的归因"
        assert "openGauss" in source, "必须说清是在 openGauss 上压的"
