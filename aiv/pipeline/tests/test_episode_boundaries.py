"""EP03~EP05 的口径红线。

第一季后三期各有各的雷区，写在这里钉住：

1. **EP03 讲的是上游的公开机制**——ReorderBuffer 是上游逻辑解码的机制，
   不是 openGauss 的能力，更不是 PostgreSQL 18 的新东西；
   画面上那组 LSN 是文档里的举例，不是实测。
2. **EP04 讲的是我自己写的、尚未合入上游的设计方案**——
   不能讲成「PostgreSQL 18 已经这样了」，也不能把设计文档内部的项目代号放上画面。
3. **EP05 讲的是社区讨论方向**——社区讨论里没有一个已合入主线的最终版本，
   拟议的记录名与内部实现细节都不能当成已存在的东西。

另外还盯一条**跨期的同步关系**：口播稿的句数、字幕表的行数、契约期望的句数
三者必须一致——任何一期改了稿而忘了改契约，`align` 会在出片时才报错。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pyv import align
from pyv import contract as contract_mod
from pyv import topics as topics_mod

ROOT = Path(__file__).resolve().parents[2]

EPISODES = {
    "ep01": ("字幕-并行解码.md", "pg-parallel-decode.json"),
    "ep02": ("字幕-CSN全序.md", "csn-total-ordering.json"),
    "ep03": ("字幕-WAL顺序.md", "wal-interleave.json"),
    "ep04": ("字幕-并行apply.md", "parallel-apply.json"),
    "ep05": ("字幕-结构化DDL.md", "structured-ddl.json"),
    "ep06": ("字幕-行锁.md", "row-lock.json"),
}


def _video_text(episode: str) -> str:
    """这一期里会被念出来、被烧进画面的全部文字。"""
    script, contract_name = EPISODES[episode]
    sentences = align.parse_script(ROOT / script)
    subtitles = align.parse_subtitle_table(ROOT / script)
    contract = contract_mod.load_contract(ROOT / "contracts" / contract_name)

    parts: list[str] = list(sentences) + list(subtitles) + [contract.title]
    for segment in contract.segments:
        for value in segment.params.values():
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, list):
                parts.extend(str(item) for item in value)
    return "\n".join(parts)


def _sentences(episode: str) -> list[str]:
    script, _ = EPISODES[episode]
    return align.parse_script(ROOT / script)


def _topic(episode_id: str):
    for episode in topics_mod.parse_topics():
        if episode.id == episode_id:
            return episode
    raise AssertionError(f"选题库里没有 {episode_id}")


# ---------------------------------------------------------------- 跨期同步


@pytest.mark.parametrize("episode", sorted(EPISODES))
def test_script_and_contract_agree_on_the_sentence_count(episode):
    """口播稿的句数、字幕表的行数、契约期望的句数必须一致。

    改了一句稿子却忘了改契约，`align` 会在出片那一刻才报错；
    这里提前把它变成一条测试。
    """
    script, contract_name = EPISODES[episode]
    sentences = align.parse_script(ROOT / script)
    subtitles = align.parse_subtitle_table(ROOT / script)
    contract = contract_mod.load_contract(ROOT / "contracts" / contract_name)

    assert len(sentences) == contract.sentence_count, \
        f"{episode} 的口播稿 {len(sentences)} 句，契约要 {contract.sentence_count} 句"
    assert len(subtitles) == len(sentences), \
        f"{episode} 的字幕表 {len(subtitles)} 行，口播稿 {len(sentences)} 句"


@pytest.mark.parametrize("episode", sorted(EPISODES))
def test_subtitle_lines_fit_the_burn_in_width(episode):
    """字幕是烧进画面的，每行都不能超过允许的显示宽度。"""
    from pyv.timeline import MAX_SUBTITLE_LINE, display_width

    script, _ = EPISODES[episode]
    for index, line in enumerate(align.parse_subtitle_table(ROOT / script), 1):
        assert display_width(line) <= MAX_SUBTITLE_LINE, \
            f"{episode} 第 {index} 行字幕宽 {display_width(line)}，超过 {MAX_SUBTITLE_LINE}"


# ---------------------------------------------------------------- EP03


def test_ep03_does_not_claim_postgresql_18():
    """上游逻辑解码的机制不是 PostgreSQL 18 的新东西。"""
    assert "PostgreSQL 18" not in _video_text("ep03")


def test_ep03_only_mentions_opengauss_for_the_csn_boundary():
    """EP03 里出现 openGauss，只能是为了说清「CSN 是 openGauss 额外加的」。

    一旦把 ReorderBuffer 说成 openGauss 的机制，观众就会以为
    上一期讲的并行解码和这期的归并是同一件事。
    """
    for sentence in _sentences("ep03"):
        if "openGauss" in sentence:
            assert "CSN" in sentence, \
                "EP03 里提到 openGauss，必须同时说明说的是 CSN 那套"
            assert "额外" in sentence, \
                "必须说清 CSN 是在上游机制之上额外加的，不是同一件事"


def test_ep03_marks_the_lsn_example_as_an_illustration():
    """画面上那组 LSN 与条数是文档里的举例，必须标明是示意。

    只看「举例」那几行——「事务顺序 = commit LSN 顺序」是机制陈述，
    它讲的是上游的规则，不是画面上那组编号。
    """
    topic = _topic("ep03")
    hits = [row for row in topic.evidence
            if "示例" in row[0] or "举例" in row[0]]
    assert hits, "EP03 的数字与出处表里应当有那组举例"
    for _, _, caliber in hits:
        assert "示意" in caliber or "举例" in caliber, \
            "文档里的举例必须标明是示意，不能说成实测"


# ---------------------------------------------------------------- EP04


def test_ep04_says_it_is_my_own_design():
    """这期讲的是我自己写的方案，口播必须把这句话说出来。"""
    sentences = _sentences("ep04")
    hits = [s for s in sentences if "我自己的设计方案" in s]
    assert hits, "EP04 必须说清这是作者本人的设计方案"
    assert any("没合进上游主线" in s or "尚未合入主线" in s for s in sentences), \
        "还必须说清它没有合入上游主线"


def test_ep04_does_not_claim_postgresql_18():
    """内部设计文档适配 PG 18，不等于 PG 18 已经有这个能力。"""
    assert "PostgreSQL 18" not in _video_text("ep04")


def test_ep04_keeps_internal_codenames_off_screen():
    """设计文档内部的项目代号不能上画面。"""
    for codename in ("TWPA", "pa_launch_parallel_worker", "ParallelApplyWorkerInfo"):
        assert codename not in _video_text("ep04"), \
            f"内部代号 {codename} 不该出现在口播或画面里"


def test_ep04_does_not_reuse_the_ep01_benchmark():
    """EP01 的压测数字不能挪用到这期。"""
    for number in ("2 到 5 倍", "2–5 倍"):
        assert number not in _video_text("ep04"), \
            "EP01 的压测数字不得挪用到别的期"


# ---------------------------------------------------------------- EP05


def test_ep05_says_it_is_a_community_discussion():
    """社区讨论里没有一个已合入主线的最终版本，这句必须说在最后。"""
    sentences = _sentences("ep05")
    assert any("社区还在讨论" in s for s in sentences), \
        "EP05 必须说清这是社区讨论的方向"
    assert any("合入主线" in s for s in sentences), \
        "还必须说清它还没有合入主线"


def test_ep05_does_not_claim_postgresql_18():
    """社区讨论方向不是 PostgreSQL 18 的能力。"""
    assert "PostgreSQL 18" not in _video_text("ep05")


def test_ep05_keeps_proposed_record_names_off_screen():
    """拟议的 WAL 记录名与内部实现的细节不能当成已存在的东西上画面。"""
    for name in ("xl_logical_ddl_message", "XLOG_LOGICAL_DDL_MESSAGE",
                 "LogLogicalMessage", "xl_logical_message", "pg_ddl"):
        assert name not in _video_text("ep05"), \
            f"拟议或内部的记录名 {name} 不该出现在口播或画面里"


# ---------------------------------------------------------------- EP06


def test_ep06_says_it_is_an_upstream_mechanism():
    """这期讲的是上游 PostgreSQL 的公开机制，这句话必须说在口播里。"""
    sentences = _sentences("ep06")
    assert any("上游" in s and "公开机制" in s for s in sentences), \
        "EP06 必须说清这是上游的公开机制"
    assert any("私有扩展" in s for s in sentences), \
        "还要说清它不是哪一家的私有能力"


def test_ep06_marks_postgresql_18_as_the_source_version():
    """口播里的「PostgreSQL 18」是出处文章的源码版本，不是版本特性声明。

    行锁不是 PG 18 新增的能力。版本号出现在这里，只是在说
    「我读的是哪个版本的源码」，所以同一句里必须有「源码」二字。
    """
    sentences = _sentences("ep06")
    hits = [s for s in sentences if "PostgreSQL 18" in s]
    assert hits, "EP06 的源码出处应该讲出来"
    for sentence in hits:
        assert "源码" in sentence, \
            "提到 PostgreSQL 18 必须同时说明那指的是源码版本"


def test_ep06_does_not_claim_row_lock_is_new_in_18():
    """行锁不是 PostgreSQL 18 新增的能力。"""
    for phrase in ("18 新增", "18 才", "18 才有", "18 引入", "新增了行锁"):
        assert phrase not in _video_text("ep06"), \
            f"不能把行锁说成 PostgreSQL 18 的新能力（命中 {phrase}）"


def test_ep06_marks_the_bit_values_as_source_definitions():
    """画面上的位定义是源码里的定义，不是实测数据。"""
    topic = _topic("ep06")
    hits = [row for row in topic.evidence if "0x" in row[0] or "位定义" in row[0]]
    assert hits, "EP06 的数字与出处表里应当有那组位定义"
    for _, _, caliber in hits:
        assert "源码" in caliber, "位定义必须标明是源码里的定义"
        assert "不是实测" in caliber or "非实测" in caliber, \
            "源码里的定义必须说清不是实测数据"


# ---------------------------------------------------------------- 跨期共同


@pytest.mark.parametrize("episode", ["ep03", "ep04", "ep05", "ep06"])
def test_new_episodes_do_not_reuse_the_ep01_benchmark(episode):
    """第一季只有 EP01 有那组压测数字，其余各期不许挪用。"""
    for number in ("2 到 5 倍", "2–5 倍"):
        assert number not in _video_text(episode)
