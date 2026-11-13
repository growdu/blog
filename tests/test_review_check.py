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


# 审校过的正文合入后，段落不该又长回去——AIF-03 盯的就是「单段 > 200 字」。
# 改文章时把两段并回一段，这条测试会报出来：审校完的稿子不能带新债。
REVIEWED_ARTICLES = (
    "docs/database/postgresql-mvcc/index.md",
    "docs/database/postgresql-logical-replication-worker-model/index.md",
    "docs/db/postgresql/learning-path/06-heap-and-mvcc.md",
    "docs/pgsql/checkpoint机制浅析.md",
    "docs/cluster/分布式一致性协议.md",
)


def test_reviewed_articles_have_no_long_paragraph_signal():
    """集成：已合入审校的文章不该再被 AIF-03 命中。"""
    for rel in REVIEWED_ARTICLES:
        result = subprocess.run(
            [sys.executable, str(TOOL), str(REPO_ROOT / rel), "--json"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        hits = [s for s in payload["docs"][0]["signals"]
                if s["rule"] == "AIF-03" and s["severity"] == "warn"]
        assert not hits, f"{rel} 还有超长段落：{hits}"


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


# --- STR / MET 规则 --------------------------------------------------------


def test_str_04_accepts_a_sibling_article_link(tmp_path):
    module = load_tool()
    pillar = tmp_path / "database"
    (pillar / "postgresql-mvcc").mkdir(parents=True)
    (pillar / "postgresql-mvcc" / "index.md").write_text("# t\n", encoding="utf-8")
    (pillar / "pg-dont-do-this").mkdir()
    (pillar / "pg-dont-do-this" / "index.md").write_text("# t\n", encoding="utf-8")
    doc = module.load_doc(pillar / "postgresql-mvcc" / "index.md")
    doc.text = "见 [同系列](./pg-dont-do-this/index.html)\n"
    doc.lines = doc.text.split("\n")
    doc.blocks = module.parse_blocks(doc.lines)
    assert module.rule_str_04(doc) == []


def test_str_04_flags_a_link_to_a_missing_article(tmp_path):
    module = load_tool()
    pillar = tmp_path / "database"
    (pillar / "postgresql-mvcc").mkdir(parents=True)
    (pillar / "postgresql-mvcc" / "index.md").write_text("# t\n", encoding="utf-8")
    doc = module.load_doc(pillar / "postgresql-mvcc" / "index.md")
    doc.text = "见 [不存在的](./no-such-article/index.html)\n"
    doc.lines = doc.text.split("\n")
    doc.blocks = module.parse_blocks(doc.lines)
    signals = module.rule_str_04(doc)
    assert len(signals) == 1
    assert signals[0].rule == "STR-04"


def test_str_04_ignores_image_paths(tmp_path):
    """图片不是文章链接：图片路径散落在别处，判成断链就是误报。"""
    module = load_tool()
    pillar = tmp_path / "database"
    (pillar / "postgresql-mvcc").mkdir(parents=True)
    (pillar / "postgresql-mvcc" / "index.md").write_text("# t\n", encoding="utf-8")
    doc = module.load_doc(pillar / "postgresql-mvcc" / "index.md")
    doc.text = "![图](./images/somewhere-else/heap.png)\n"
    doc.lines = doc.text.split("\n")
    doc.blocks = module.parse_blocks(doc.lines)
    assert module.rule_str_04(doc) == []


def test_met_01_flags_a_missing_author_table(tmp_path):
    doc = make_doc(tmp_path, "# 标题\n\n正文。\n")
    signals = load_tool().rule_met_01(doc)
    assert len(signals) == 1
    assert signals[0].rule == "MET-01"


def test_met_01_accepts_the_author_table(tmp_path):
    text = ("# 标题\n\n| 编写人 | 编写内容 | 编写时间 |\n| --- | --- | --- |\n"
            "| growdu | 初稿 | 2026-08-20 |\n\n正文。\n")
    doc = make_doc(tmp_path, text)
    assert load_tool().rule_met_01(doc) == []


def test_str_02_flags_a_missing_opening_positioning(tmp_path):
    doc = make_doc(tmp_path, "# 标题\n\n正文开始了。\n\n第二段。\n\n第三段。\n")
    signals = load_tool().rule_str_02(doc)
    assert len(signals) == 1
    assert signals[0].rule == "STR-02"


def test_str_02_accepts_a_positioning_sentence(tmp_path):
    """回归：「本文会沿着源码拆给你看」也是定位句，不能当成没有定位。"""
    text = (
        "# 标题\n\n"
        "先讲个场景。\n\n"
        "PostgreSQL 选择了一条路。\n\n"
        "本文会沿着 src/backend/access/heap/ 的源码，把这条链路一步步拆给你看。\n"
    )
    doc = make_doc(tmp_path, text)
    assert load_tool().rule_str_02(doc) == []


def test_str_03_accepts_a_reference_section(tmp_path):
    """回归：结尾的「参考资料」是标题+列表，只看段落会全判成没有产物。"""
    text = (
        "# 标题\n\n"
        "正文讲完了。\n\n"
        "## 参考资料\n\n"
        "- PostgreSQL 17 源码：src/backend/access/heap/heapam.c\n"
    )
    doc = make_doc(tmp_path, text)
    assert load_tool().rule_str_03(doc) == []


def test_parse_blocks_skips_leading_front_matter():
    """回归：51 篇文章带 YAML front matter，它不是正文段落。"""
    module = load_tool()
    lines = [
        "---",
        'title: "PostgreSQL 目录快照源码级深度拆解"',
        "date: 2026-10-27 10:00:00",
        "---",
        "",
        "# 正文标题",
        "",
        "真正的第一段。",
    ]
    blocks = module.parse_blocks(lines)
    kinds = [b.kind for b in blocks]
    assert kinds == ["heading", "paragraph"]
    assert blocks[1].text == "真正的第一段。"


def test_str_02_accepts_a_later_positioning_sentence(tmp_path):
    """回归：「本文的目的就是把这 7 个维度讲透」—— 讲 字在 20 字开外。"""
    text = (
        "# 标题\n\n"
        "上一篇我们列了清单。\n\n"
        "那么问题来了——为什么有的数据库能脱颖而出？\n\n"
        "答案藏在这 7 个维度里。本文的目的就是把这 7 个维度讲透。\n"
    )
    doc = make_doc(tmp_path, text)
    assert load_tool().rule_str_02(doc) == []


def test_str_02_accepts_positioning_in_a_quote_block(tmp_path):
    """回归：定位写在 `> 目标：…` 引用块里，不能当成没有定位。"""
    text = "# 标题\n\n> 目标：理解 PostgreSQL 堆表的页面布局与 MVCC 可见性。\n\n正文。\n"
    doc = make_doc(tmp_path, text)
    assert load_tool().rule_str_02(doc) == []


def test_str_02_accepts_positioning_written_as_analysis(tmp_path):
    """回归：「本文主要分析下…」也是定位句。"""
    text = "# 标题\n\n上期讲过 WAL。本文主要分析下 checkpoint 机制。\n"
    doc = make_doc(tmp_path, text)
    assert load_tool().rule_str_02(doc) == []


def test_str_03_accepts_a_conclusion_section(tmp_path):
    """回归：结尾的「结语 + 结论表」是产物，不能判成没有。"""
    text = (
        "# 标题\n\n"
        "正文讲完了。\n\n"
        "## 结语\n\n"
        "| 维度 | 结论 |\n| --- | --- |\n| 一个订阅几个 worker | 1 个 |\n"
    )
    doc = make_doc(tmp_path, text)
    assert load_tool().rule_str_03(doc) == []


def test_str_03_accepts_a_modification_guide(tmp_path):
    """回归：「修改指南：要改哪些文件」是货真价实的可带走产物。"""
    text = (
        "# 标题\n\n"
        "正文讲完了。\n\n"
        "## 修改指南：要加新 worker 类型时碰哪些文件\n\n"
        "1. `src/include/replication/worker_internal.h`：加枚举值\n"
    )
    doc = make_doc(tmp_path, text)
    assert load_tool().rule_str_03(doc) == []


def test_str_03_scans_the_whole_last_section(tmp_path):
    """回归：最后一个大节下面还有子节时，产物标题不能因为「不在最后 8 块」而漏掉。"""
    text = (
        "# 标题\n\n"
        "正文讲完了。\n\n"
        "## 修改指南\n\n"
        "### 12.1 改枚举\n\n"
        "加一个新值。\n\n"
        "### 12.2 改 launcher\n\n"
        "加一个分支。\n\n"
        "### 12.3 改 worker\n\n"
        "改分发逻辑。\n\n"
        "### 12.4 改 Babelfish\n\n"
        "补一张状态表。\n"
    )
    doc = make_doc(tmp_path, text)
    assert load_tool().rule_str_03(doc) == []


def test_str_02_accepts_a_bold_target_marker(tmp_path):
    """回归：「**目标**：…」带 markdown 强调时也要认得出是定位句。"""
    text = "# 标题\n\n**目标**：理解 PostgreSQL 堆表的页面布局与 MVCC 可见性。\n\n正文。\n"
    doc = make_doc(tmp_path, text)
    assert load_tool().rule_str_02(doc) == []
