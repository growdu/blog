"""人格检查测试。

两条线：

1. **规范与实现同步**——《人格规范》§7 的规则表、§3.1 的能力域表、
   §3.3 的边界表，必须和 `pyv/persona.py` 里的编号、域名一一对应。
   规范改了代码没改（或者反过来），人格就名存实亡。

2. **规则真的抓得住**——每条规则都要有正反用例；
   再拿一份真实的历史口播稿跑一遍，确认不误伤。
"""
import importlib.util
import re
import sys
from pathlib import Path

from pyv import character, cli, persona

FIXTURES = Path(__file__).parent / "fixtures"
OK_SCRIPT = FIXTURES / "persona_script_ok.md"
BAD_SCRIPT = FIXTURES / "persona_script_bad.md"
# 真实口播稿不入测试夹具目录：它就是这一期实际在用的稿子（aiv/字幕-并行解码.md），
# 夹具目录里放的是「测规则的样本」，两者不是一回事。
REAL_SCRIPT = Path(__file__).resolve().parents[2] / "字幕-并行解码.md"


def _load(name: str, relative: str):
    """加载 character/scripts/ 下的脚本（不在 pipeline 包内，按路径载入）。"""
    path = character.AIV_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _persona_module():
    return _load("persona_prompt", "character/scripts/_persona.py")


def _generate_character():
    return _load("generate_character", "character/scripts/generate_character.py")


def _spec_text() -> str:
    return persona.PERSONA_SPEC.read_text(encoding="utf-8")


def _spec_section(title: str) -> str:
    """取规范里某个小节的内容。"""
    text = _spec_text()
    start = text.index(f"### {title}")
    rest = text[start + 3:]
    for marker in ("\n### ", "\n## "):
        if marker in rest:
            return rest[:rest.index(marker)]
    return rest


def _spec_table_first_column(section: str) -> list[str]:
    """取规范里某节表格的第一列（加粗的域名）。"""
    names: list[str] = []
    for line in _spec_section(section).splitlines():
        match = re.match(r"\|\s*\*\*(.+?)\*\*", line)
        if match:
            names.append(match.group(1).strip())
    return names


# ---------------------------------------------------------------- 规范同步


def test_spec_declares_every_rule():
    """规范 §7 的规则表必须覆盖代码里的每一条规则。"""
    spec = _spec_text()
    for rule_id in persona.RULE_IDS:
        assert f"`{rule_id}`" in spec, f"规范里没有规则 {rule_id}"


def test_spec_declares_no_extra_rule():
    """规范里不能有代码里不存在的规则编号。"""
    spec_ids = set(re.findall(r"`(persona\.[a-z]+-[a-z-]+)`", _spec_text()))
    assert spec_ids <= set(persona.RULE_IDS), (
        f"规范里有代码里没有的规则：{sorted(spec_ids - set(persona.RULE_IDS))}"
    )


def test_spec_lists_every_capability_domain():
    """规范 §3.1 的能力域要和代码里的能力域同名。"""
    spec_domains = _spec_table_first_column("3.1 能力地图")
    missing = set(persona.CAPABILITY_KEYWORDS) - set(spec_domains)
    assert not missing, f"规范 §3.1 少了能力域：{sorted(missing)}"


def test_spec_lists_every_boundary():
    """规范 §3.3 的边界要和代码里的边界同名。"""
    spec_boundaries = _spec_table_first_column("3.3 能力边界（明确不讲、讲不深的）")
    code_boundaries = set(persona.ZERO_COVERAGE) | set(persona.SHALLOW_COVERAGE)
    missing = code_boundaries - set(spec_boundaries)
    assert not missing, f"规范 §3.3 少了边界：{sorted(missing)}"


def test_every_cited_path_exists():
    """规范里的出处必须真实存在。

    这个规范的全部价值就是「每条结论都带出处」——出处要是假的，
    整份规范就退回成凭空写的角色设定。
    """
    repo_root = character.REPO_ROOT
    spec = _spec_text()
    md_paths = sorted(set(re.findall(r"`(docs/[^`]+?\.md)`", spec)))
    assert md_paths, "规范里没有引用任何文章"
    for path in md_paths:
        assert (repo_root / path).exists(), f"规范引用的文章不存在：{path}"
    for path in sorted(set(re.findall(r"`(docs/[^`]+?/)`", spec))):
        assert (repo_root / path).exists(), f"规范引用的目录不存在：{path}"


def test_spec_has_no_broken_characters():
    """中文文案不能有损坏字符。"""
    assert "�" not in _spec_text()


def test_spec_and_code_agree_on_thresholds():
    """短句宽度、占比、单句上限，规范里写的和代码里的一致。"""
    spec = _spec_text()
    assert f"≤ {persona.SHORT_SENTENCE_WIDTH}" in spec
    assert f"≥ {persona.SHORT_SENTENCE_RATIO:.0%}" in spec
    assert f"≤ {persona.MAX_SENTENCE_WIDTH}" in spec


# ---------------------------------------------------------------- 视觉气质


def test_persona_traits_are_in_sync_with_the_spec():
    """人格特质的关键词，规范与生成脚本必须一致。"""
    traits = _persona_module().PERSONA_TRAITS
    spec_traits = _spec_table_first_column("1.1 视觉气质（落到形象上）")
    assert set(spec_traits) == set(traits), (
        f"规范 §1.1 与 _persona.py 的特质不一致："
        f"{sorted(set(spec_traits) ^ set(traits))}"
    )


def test_character_prompt_carries_the_persona():
    """主形象与姿态表的生成 prompt 都必须带人格气质。"""
    module = _persona_module()
    generate = _generate_character()
    for trait in module.PERSONA_TRAITS:
        assert trait in module.PERSONA_PROMPT
    assert module.PERSONA_PROMPT in generate.CHARACTER_PROMPT
    assert module.PERSONA_PROMPT in generate.POSE_PROMPT


# ---------------------------------------------------------------- 品牌片文案


def _render_brand():
    return _load("render_brand", "brand/scripts/render_brand.py")


def test_brand_copy_is_in_sync_with_the_specs():
    """片头片尾的文案，三处（渲染脚本 / 形象规范 / 品牌 README）必须一致。

    文案散在三个地方最容易漂——改了渲染脚本忘了改文档，
    下一次照文档重渲就又换回去了。
    """
    render = _render_brand()
    aiv = character.AIV_ROOT
    docs = {
        "形象与音色规范": (aiv / "形象与音色规范.md").read_text(encoding="utf-8"),
        "人格规范": (aiv / "人格规范.md").read_text(encoding="utf-8"),
        "brand/README": (aiv / "brand" / "README.md").read_text(encoding="utf-8"),
    }
    for text in (render.INTRO_TAGLINE, render.INTRO_CAPTION, render.OUTRO_SUBTITLE,
                 render.INTRO_NARRATION, render.OUTRO_NARRATION):
        for name, doc in docs.items():
            assert text in doc, f"{name} 里没有这句文案：{text}"


def test_brand_copy_passes_the_persona_check():
    """片头片尾的文案本身就得过人格检查。"""
    render = _render_brand()
    report = persona.check_sentences([
        render.INTRO_TAGLINE,
        render.INTRO_CAPTION,
        render.OUTRO_SUBTITLE,
    ])
    assert report.errors == [], [f.message for f in report.errors]


# ---------------------------------------------------------------- 硬约束


def test_hype_word_is_rejected():
    """营销腔禁词是硬约束。"""
    report = persona.check_sentences(["这是一篇史上最全的解码教程。"])
    findings = report.by_rule("persona.no-hype")
    assert findings and findings[0].level == persona.ERROR
    assert not report.ok


def test_brand_self_reference_is_rejected():
    """以机构/平台自称是硬约束。"""
    report = persona.check_sentences(["大家好，我是本公众号的小编。"])
    findings = report.by_rule("persona.no-brand-self")
    assert findings and findings[0].level == persona.ERROR


def test_absolute_claim_is_rejected():
    """绝对化断言是硬约束——人格是给边界，不是把话说满。"""
    report = persona.check_sentences(["这个方案一定会提升性能，绝对没有坑。"])
    findings = report.by_rule("persona.no-absolute")
    assert findings and findings[0].level == persona.ERROR


def test_zero_coverage_topic_is_rejected():
    """博客里零记录的方向，讲了就是编。"""
    report = persona.check_sentences(["顺便说说量子计算和区块链在数据库里的应用。"])
    findings = report.by_rule("persona.domain")
    assert findings and findings[0].level == persona.ERROR


def test_shallow_coverage_topic_is_only_a_warning():
    """只有一两篇记录的方向，是倾向不是违规。"""
    report = persona.check_sentences(["顺便说说量化交易怎么入门。"])
    findings = report.by_rule("persona.domain")
    assert findings and findings[0].level == persona.WARNING
    assert report.ok


def test_comparison_sentence_is_exempt():
    """拿越界主题做对比不算越界。"""
    report = persona.check_sentences(["这跟量子计算完全不一样。"])
    assert not report.by_rule("persona.domain")


def test_whole_episode_outside_the_domain_is_rejected():
    """整期都在能力边界外，是硬约束。"""
    report = persona.check_sentences(["量子计算最近很火。", "区块链的技术原理也不复杂。"])
    errors = [f for f in report.by_rule("persona.domain") if f.level == persona.ERROR]
    assert errors, "整期越界应该报错"


# ---------------------------------------------------------------- 倾向


def test_missing_evidence_is_a_warning():
    """没有量化依据是倾向，不是违规。"""
    report = persona.check_sentences(["今天聊聊这个特性到底怎么用。"])
    findings = report.by_rule("persona.evidence")
    assert findings and findings[0].level == persona.WARNING
    assert report.ok


def test_missing_boundary_is_a_warning():
    """只讲优点不讲边界，是倾向。"""
    report = persona.check_sentences(["今天聊聊这个特性到底怎么用。"])
    assert report.by_rule("persona.boundary")


def test_missing_method_is_a_warning():
    """没透出方法论人格，是倾向。"""
    report = persona.check_sentences(["今天聊聊这个特性到底怎么用。"])
    assert report.by_rule("persona.method")


def test_short_sentence_ratio_is_a_warning():
    """全是长句念不顺，是倾向。"""
    sentences = [
        "PostgreSQL 18 的并行解码方案由 reader 负责读取和协调多个 worker 并行解码速度显著提升",
        "PostgreSQL 18 的并行解码方案由 reader 负责读取和协调多个 worker 并行解码速度显著提升",
    ]
    assert persona.check_sentences(sentences).by_rule("persona.short-sentence")


def test_long_sentence_is_a_warning():
    """单句塞太多信息，是倾向。"""
    long_sentence = "PostgreSQL 18 的并行解码方案" * 4
    findings = persona.check_sentences([long_sentence]).by_rule(
        "persona.sentence-length"
    )
    assert findings and findings[0].sentence == 1


def test_clean_script_has_no_findings():
    """一条规范都满足的稿子，不该有任何判定。"""
    report = persona.check_file(OK_SCRIPT)
    assert report.findings == (), [f.message for f in report.findings]
    assert report.ok


# ---------------------------------------------------------------- 夹具


def test_bad_fixture_triggers_every_hard_rule():
    """违规夹具要能同时踩中四条硬约束。"""
    report = persona.check_file(BAD_SCRIPT)
    assert not report.ok
    for rule_id in (
        "persona.no-hype",
        "persona.no-brand-self",
        "persona.no-absolute",
        "persona.domain",
    ):
        assert report.by_rule(rule_id), f"违规夹具没有触发 {rule_id}"


def test_real_script_has_no_hard_violation():
    """真实的历史口播稿不能被判违规。

    它是规范出来之前写的，缺边界感和方法论表达——那是倾向，不是违规。
    """
    report = persona.check_file(REAL_SCRIPT)
    assert report.ok, [f.message for f in report.errors]
    assert report.by_rule("persona.boundary")
    assert report.by_rule("persona.method")


def test_extract_sentences_from_plain_text(tmp_path):
    """纯文本稿：每行一句。"""
    plain = tmp_path / "script.txt"
    plain.write_text("第一句。\n\n第二句。\n", encoding="utf-8")
    assert persona.extract_sentences(plain) == ["第一句。", "第二句。"]


def test_detect_capability_domain():
    """选题落在哪个能力域，要说得出来。"""
    report = persona.check_file(OK_SCRIPT)
    assert "PostgreSQL 内核机制" in report.domains


# ---------------------------------------------------------------- 命令行


def test_cli_check_passes_on_clean_script(capsys):
    """命令行：合规稿退出码 0。"""
    code = cli.main(["persona", "check", "--script", str(OK_SCRIPT)])
    out = capsys.readouterr().out
    assert code == 0
    assert "人格检查通过" in out
    assert "能力域" in out


def test_cli_check_fails_on_bad_script(capsys):
    """命令行：违规稿退出码 1，并把违规打出来。"""
    code = cli.main(["persona", "check", "--script", str(BAD_SCRIPT)])
    captured = capsys.readouterr()
    assert code == 1
    assert "persona.no-hype" in captured.out
    assert "persona.domain" in captured.out
