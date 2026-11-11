"""选题库检查测试。

两条线，跟 `test_bgm.py` 一个套路：

1. **规范与实现同步**——《选题库.md》里的规则编号，必须与 `pyv/topics.py`
   里的 `RULE_IDS` 一一对应。改了代码没改文档，判据就跟文档说的不是一回事了。
2. **规则真的抓得住**——每条规则都要有能触发它的用例；选题库本身必须过检。
"""
import re

from pyv import topics


def _spec_text() -> str:
    return (topics.AIV_ROOT / "选题库.md").read_text(encoding="utf-8")


def _episodes():
    return topics.parse_topics()


def _fake_episode(**overrides) -> topics.Episode:
    """造一期合规的选题，再按需改坏其中一处。"""
    episode = topics.Episode(
        heading="## EP99 · 测试用",
        fields={
            "id": "ep99",
            "标题": "一个测试用的标题",
            "主钩子": "一个测试用的钩子，讲的是 WAL 与事务。",
            "主线": "机制族",
            "能力域": "PostgreSQL 内核机制",
            "状态": "待做",
            "适配理由": "这是测试用例，适配理由随便写点字数够长就好填充用的。",
        },
        docs=[("docs/db/logical_decode/逻辑复制解惑.md", "取什么")],
        sentences=[f"这是第 {i} 句，用来凑够十句用的测试文本。" for i in range(1, 11)],
        evidence=[("陈述一句", "docs/db/logical_decode/逻辑复制解惑.md", "口径")],
        has_docs_section=True,
        has_script_section=True,
        has_evidence_section=True,
    )
    for key, value in overrides.items():
        setattr(episode, key, value)
    return episode


def _rule_ids(findings) -> set:
    return {finding.rule_id for finding in findings}


# ---------------------------------------------------------------- 规范同步


def test_spec_declares_every_rule():
    """《选题库.md》必须写出代码里的每一条规则。"""
    spec = _spec_text()
    for rule_id in topics.RULE_IDS:
        assert f"`{rule_id}`" in spec, f"选题库里没有规则 {rule_id}"


def test_spec_declares_no_extra_rule():
    """选题库里不能有代码里不存在的规则编号。"""
    spec_ids = set(re.findall(r"`(topics\.[a-z-]+)`", _spec_text()))
    assert spec_ids <= set(topics.RULE_IDS), (
        f"选题库里有代码里没有的规则：{sorted(spec_ids - set(topics.RULE_IDS))}"
    )


# ---------------------------------------------------------------- 选题库本身


def test_topic_library_passes_its_own_checks():
    """入库的选题库必须过自己的检。"""
    findings = topics.check_topics(_episodes())
    errors = [f for f in findings if f.level == topics.ERROR]
    assert not errors, "\n".join(str(f) for f in errors)


def test_parses_every_episode():
    """每一期都要解析出：10 句骨架、至少一篇关联文档、至少一条出处。"""
    episodes = _episodes()
    assert len(episodes) >= 3, f"只解析出 {len(episodes)} 期"
    for episode in episodes:
        assert episode.id, f"{episode.heading} 没有 id"
        assert len(episode.sentences) == topics.SENTENCE_COUNT, (
            f"{episode.id} 的口播骨架是 {len(episode.sentences)} 句"
        )
        assert episode.docs, f"{episode.id} 没有关联文档"
        assert episode.evidence, f"{episode.id} 没有数字与出处"


def test_every_episode_stays_in_a_capability_domain():
    """每期都要落在《人格规范》的能力域里，不能整期在边界外。"""
    from pyv import persona

    for episode in _episodes():
        domains = persona.detect_domains([episode.text()])
        assert domains, f"{episode.id} 一个能力域都没命中"
        assert episode.domain in persona.CAPABILITY_KEYWORDS, (
            f"{episode.id} 的能力域「{episode.domain}」不是合法域名"
        )


def test_episode_ids_are_unique():
    ids = [episode.id for episode in _episodes()]
    assert len(ids) == len(set(ids)), f"id 重复：{ids}"


# ---------------------------------------------------------------- 规则能触发


def test_structure_rule_fires():
    """缺字段要报。"""
    episode = _fake_episode()
    episode.fields.pop("主钩子")
    assert "topics.structure" in _rule_ids(topics.check_topics([episode]))


def test_doc_exists_rule_fires():
    """关联文档不存在要报。"""
    episode = _fake_episode(docs=[("docs/db/根本没有这个文件.md", "取什么")])
    assert "topics.doc-exists" in _rule_ids(topics.check_topics([episode]))


def test_no_hype_rule_fires():
    """标题带营销腔要报。"""
    episode = _fake_episode()
    episode.fields["标题"] = "史上最全的解码教程"
    assert "topics.no-hype" in _rule_ids(topics.check_topics([episode]))


def test_absolute_claim_rule_fires():
    """标题带绝对化断言要报。"""
    episode = _fake_episode()
    episode.fields["主钩子"] = "这样一定会提升性能"
    assert "topics.no-hype" in _rule_ids(topics.check_topics([episode]))


def test_domain_rule_fires_on_unknown_domain():
    """能力域写成不存在的名字要报。"""
    episode = _fake_episode()
    episode.fields["能力域"] = "不存在的域"
    assert "topics.domain" in _rule_ids(topics.check_topics([episode]))


def test_domain_rule_fires_outside_the_boundary():
    """整期都在能力边界外要报。"""
    episode = _fake_episode()
    episode.fields["标题"] = "量子计算芯片设计"
    episode.fields["主钩子"] = "分布式训练与推理框架"
    episode.fields["适配理由"] = "量子计算元宇宙智能驾驶区块链芯片设计"
    episode.sentences = ["量子计算芯片设计区块链" for _ in range(10)]
    episode.evidence = [("量子计算", "docs/db/logical_decode/逻辑复制解惑.md", "口径")]
    assert "topics.domain" in _rule_ids(topics.check_topics([episode]))


def test_sentence_count_rule_fires():
    """句数不对要报。"""
    episode = _fake_episode()
    episode.sentences = episode.sentences[:9]
    assert "topics.sentence-count" in _rule_ids(topics.check_topics([episode]))


def test_word_count_rule_fires():
    """字数超区间要报。"""
    episode = _fake_episode()
    episode.sentences = ["短。" for _ in range(10)]
    assert "topics.word-count" in _rule_ids(topics.check_topics([episode]))


def test_sentence_width_is_a_warning_not_an_error():
    """单句太宽是倾向类：报出来，但不拦住。

    造法要小心：只有一句超宽，其余九句补字数，
    否则会先撞上字数规则，看不出宽度这一条单独生效。
    """
    episode = _fake_episode()
    long_sentence = "这一句长到根本念不顺" * 5      # 50 字，显示宽度 50 > 40
    _, high = topics.WORD_COUNT_RANGE
    filler_len = (high - 5 - len(long_sentence)) // 9
    episode.sentences = [long_sentence] + ["字" * filler_len] * 9
    findings = topics.check_topics([episode])
    assert "topics.sentence-width" in _rule_ids(findings)
    width_findings = [f for f in findings if f.rule_id == "topics.sentence-width"]
    assert all(f.level == topics.WARNING for f in width_findings)
    assert "topics.word-count" not in _rule_ids(findings), "字数不该被顺带撞上"


def test_evidence_rule_requires_author_attribution():
    """实测数字没写作者本人归因要报。"""
    episode = _fake_episode()
    episode.evidence = [("性能提升 2 到 5 倍", "本地压测", "口径")]
    assert "topics.evidence" in _rule_ids(topics.check_topics([episode]))


def test_evidence_rule_accepts_author_attribution():
    """带归因的实测数字不该报。"""
    episode = _fake_episode()
    episode.evidence = [("性能提升 2 到 5 倍", "作者本人压测", "口径")]
    assert "topics.evidence" not in _rule_ids(topics.check_topics([episode]))


def test_evidence_rule_fires_on_empty_table():
    """「数字与出处」表空了要报。"""
    episode = _fake_episode(evidence=[])
    assert "topics.evidence" in _rule_ids(topics.check_topics([episode]))
