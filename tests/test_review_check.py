"""单元 + 集成测试：审校信号检查器 tools/review-check.py。

为什么要测这个工具
----------------
它替人做「AI 味信号、证据密度、章节结构」这类机械检查。如果它算错，
审校记录就会把错误的位置写进正文修改建议——比没有工具更糟。

两类测试：
* 单元：解析与身份推导，给最小输入；
* 集成：真的跑一遍 CLI，检查它能吃下真实文章目录。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL = REPO_ROOT / "tools" / "review-check.py"


def load_tool():
    """Import review-check.py as a module (it is a script, not a package)."""
    spec = importlib.util.spec_from_file_location("review_check", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["review_check"] = module
    spec.loader.exec_module(module)
    return module


def make_doc(tmp_path: Path, text: str):
    module = load_tool()
    path = tmp_path / "index.md"
    path.write_text(text, encoding="utf-8")
    return module.load_doc(path)


def test_derive_identity_from_page_bundle(tmp_path):
    module = load_tool()
    path = tmp_path / "database" / "postgresql-mvcc" / "index.md"
    path.parent.mkdir(parents=True)
    path.write_text("# t\n", encoding="utf-8")
    pillar, slug = module.derive_identity(path, tmp_path)
    assert slug == "postgresql-mvcc"
    assert pillar == "database"


def test_derive_identity_from_single_file(tmp_path):
    module = load_tool()
    path = tmp_path / "database" / "pg-dont-do-this.md"
    path.parent.mkdir(parents=True)
    path.write_text("# t\n", encoding="utf-8")
    pillar, slug = module.derive_identity(path, tmp_path)
    assert (pillar, slug) == ("database", "pg-dont-do-this")


def test_derive_identity_keeps_nested_path(tmp_path):
    module = load_tool()
    path = tmp_path / "db" / "postgresql" / "xxx.md"
    path.parent.mkdir(parents=True)
    path.write_text("# t\n", encoding="utf-8")
    pillar, slug = module.derive_identity(path, tmp_path)
    assert (pillar, slug) == ("db", "postgresql/xxx")


def test_parse_blocks_splits_heading_paragraph_and_code():
    module = load_tool()
    lines = [
        "# 标题",
        "",
        "第一段。",
        "",
        "```sql",
        "SELECT 1;",
        "```",
        "",
        "## 二级标题",
        "",
        "第二段。",
    ]
    blocks = module.parse_blocks(lines)
    kinds = [b.kind for b in blocks]
    assert kinds == ["heading", "paragraph", "code", "heading", "paragraph"]
    assert blocks[0].level == 1
    assert blocks[3].level == 2
    assert blocks[2].text.strip() == "SELECT 1;"


def test_parse_blocks_detects_table_and_list():
    module = load_tool()
    lines = [
        "| a | b |",
        "| --- | --- |",
        "",
        "- 第一项",
        "- 第二项",
    ]
    blocks = module.parse_blocks(lines)
    assert [b.kind for b in blocks] == ["table", "list"]


def test_load_doc_reads_first_h1_as_title(tmp_path):
    module = load_tool()
    path = tmp_path / "index.md"
    path.write_text("# PostgreSQL MVCC\n\n正文。\n", encoding="utf-8")
    doc = module.load_doc(path)
    assert doc.title == "PostgreSQL MVCC"


def test_cli_json_output_has_expected_shape():
    """集成：真跑一次 CLI，检查 JSON 结构。"""
    target = REPO_ROOT / "docs" / "database" / "postgresql-mvcc" / "index.md"
    assert target.exists(), "样例文章不在了，集成测试要换一个真实文章"
    result = subprocess.run(
        [sys.executable, str(TOOL), str(target), "--json"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "docs" in payload
    doc = payload["docs"][0]
    assert doc["pillar"] == "database"
    assert doc["slug"] == "postgresql-mvcc"
    assert doc["stats"]["paragraphs"] > 0
    assert isinstance(doc["signals"], list)


def test_cli_runs_over_a_whole_pillar():
    """集成：整目录跑一遍，不许崩。"""
    pillar = REPO_ROOT / "docs" / "database"
    result = subprocess.run(
        [sys.executable, str(TOOL), str(pillar), "--json"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert len(payload["docs"]) >= 50


def test_cli_reports_missing_path():
    result = subprocess.run(
        [sys.executable, str(TOOL), "docs/does-not-exist"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 1
    assert "路径不存在" in result.stderr


# --- AIF 规则 -------------------------------------------------------------


def test_aif_01_flags_paragraphs_opening_with_connectors(tmp_path):
    text = "\n\n".join([
        "首先看第一件事。",
        "其次看第二件事。",
        "最后看第三件事。",
        "此外还有补充。",
        "这段是正常叙述，不带连接词开头。",
    ]) + "\n"
    doc = make_doc(tmp_path, text)
    signals = load_tool().rule_aif_01(doc)
    assert len(signals) == 1
    assert signals[0].rule == "AIF-01"
    assert signals[0].severity == "warn"


def test_aif_01_ignores_connectors_used_inside_a_sentence(tmp_path):
    text = "\n\n".join([
        "这个方案最后落地了。",
        "他首先想到的是数据。",
        "这是一段普通叙述。",
    ]) + "\n"
    doc = make_doc(tmp_path, text)
    assert load_tool().rule_aif_01(doc) == []


def test_aif_02_flags_praise_without_evidence(tmp_path):
    doc = make_doc(tmp_path, "PostgreSQL 的性能非常显著。\n")
    signals = load_tool().rule_aif_02(doc)
    assert len(signals) == 1
    assert signals[0].rule == "AIF-02"


def test_aif_02_accepts_praise_backed_by_a_number(tmp_path):
    doc = make_doc(tmp_path, "PostgreSQL 的性能提升了 30%。\n")
    assert load_tool().rule_aif_02(doc) == []


def test_aif_03_flags_a_long_paragraph(tmp_path):
    doc = make_doc(tmp_path, "长" * 250 + "\n")
    signals = load_tool().rule_aif_03(doc)
    assert len(signals) == 1
    assert signals[0].rule == "AIF-03"


def test_aif_04_flags_generic_ending(tmp_path):
    text = "第一段讲清楚机制。\n\n第二段讲清楚取舍。\n\n希望本文对你有帮助。\n"
    doc = make_doc(tmp_path, text)
    signals = load_tool().rule_aif_04(doc)
    assert len(signals) == 1
    assert signals[0].rule == "AIF-04"


def test_aif_05_flags_near_duplicate_sentences(tmp_path):
    text = (
        "在并发场景下，写入会阻塞另一个事务的读取操作。\n\n"
        "在并发场景下，写入会阻塞另一个事务的读取行为。\n"
    )
    doc = make_doc(tmp_path, text)
    signals = load_tool().rule_aif_05(doc)
    assert len(signals) == 1
    assert signals[0].rule == "AIF-05"


def test_aif_05_ignores_parallel_code_introduction_lines(tmp_path):
    """回归：「事务 XID=200 执行：」和「事务 XID=300 执行：」是并列结构，不是冗余。"""
    text = (
        "事务 XID=200 执行：\n\n"
        "```sql\nDELETE FROM account WHERE id = 1;\n```\n\n"
        "事务 XID=300 执行：\n"
    )
    doc = make_doc(tmp_path, text)
    assert load_tool().rule_aif_05(doc) == []


# --- DEP 规则 -------------------------------------------------------------


def test_dep_counts_each_element(tmp_path):
    text = (
        "# 标题\n\n"
        "本文基于 PostgreSQL 17.2 环境，源码路径是 src/backend/access/heap/heapam.c。\n\n"
        "```sql\nSELECT * FROM pg_class;\n```\n\n"
        "相比之下，逻辑复制代价更高，适用场景也不同。\n\n"
        "注意这里的坑：要用 pg_stat_statements 验证。\n"
    )
    doc = make_doc(tmp_path, text)
    module = load_tool()
    module.check_doc(doc)
    for key in ("DEP-01", "DEP-02", "DEP-03", "DEP-04", "DEP-05"):
        assert doc.depth[key] > 0, key
    assert doc.depth["DEP-00"] == 0


def test_dep_00_flags_a_shallow_article(tmp_path):
    doc = make_doc(tmp_path, "# 标题\n\n这是一篇很短的文章，讲了一点点东西。\n")
    module = load_tool()
    module.check_doc(doc)
    assert doc.depth["DEP-00"] == 1


def test_dep_03_needs_a_code_block_not_prose(tmp_path):
    doc = make_doc(tmp_path, "正文里提到 SELECT 这个关键字，但没有代码块。\n")
    module = load_tool()
    module.check_doc(doc)
    assert doc.depth["DEP-03"] == 0


def test_dep_04_counts_tradeoff_wording_beyond_comparison(tmp_path):
    """回归：只认「相比/替代」会漏掉用「优点/缺点」讲取舍的文章。"""
    doc = make_doc(tmp_path, "它的优点是简单，缺点是不好扩展。\n")
    module = load_tool()
    module.check_doc(doc)
    assert doc.depth["DEP-04"] > 0
