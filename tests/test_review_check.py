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


# --- FIG 规则：图示可读性 ------------------------------------------------
#
# 「流程图不能太长，布局要合理，不然一眼看不完」——这一节判的是
# 图的**尺寸**，不是图画得对不对。超限只说明「该拆」。


def _mermaid(source: str) -> str:
    """把一段 mermaid 源码包成一篇 markdown 文章。"""
    return f"# 标题\n\n```mermaid\n{source}\n```\n"


# (mermaid 源码, (框数, 最长路径的框数, 最大扇出))
#
# 这些数字是人工核过的：框数只算 id，最长路径按整图算（不是按行），
# 扇出按**不同的目标**算（同一条边的两种画法只算一条支线）。
MERMAID_SIZE_CASES = (
    ("graph TB\n    A --> B --> C\n", (3, 3, 1)),
    ("graph TB\n    A --> B\n    B --> C\n    C --> D\n", (4, 4, 1)),
    ("graph TB\n    A -->|说明|B\n", (2, 2, 1)),
    ("graph TB\n    subgraph one\n    A --> B\n    end\n", (2, 2, 1)),
    ("stateDiagram-v2\n    [*] --> S1\n    S1 --> S2\n", (2, 2, 1)),
    ("graph TB\n    A --> B\n    B --> A\n", (2, 2, 1)),
    ("graph LR\n    Root --> A\n    Root --> B\n    Root --> C\n", (4, 2, 3)),
    # 同一条边的两种画法（实线 + 虚线）指向同一个目标：只算一条支线
    ("graph TB\n    A --> B\n    A -.-> B\n", (2, 2, 1)),
)


def test_mermaid_size_matches_the_expected_shape():
    """单元：mermaid 尺寸解析的定版用例。"""
    module = load_tool()
    for source, expected in MERMAID_SIZE_CASES:
        assert module._mermaid_size(source) == expected, source


def test_fig_01_flags_a_diagram_with_too_many_boxes(tmp_path):
    body = "\n".join(f"    N{i} --> M{i}" for i in range(16))
    doc = make_doc(tmp_path, _mermaid("graph TB\n" + body))
    signals = load_tool().rule_fig_01(doc)
    assert len(signals) == 1
    assert signals[0].rule == "FIG-01"
    assert signals[0].severity == "warn"


def test_fig_01_accepts_a_balanced_diagram(tmp_path):
    """结构规整的图不该被判超限——只看框数会把好图也抓进来。"""
    body = [f"    Root --> A{i}" for i in range(1, 5)]
    for i in range(1, 5):
        body.append(f"    A{i} --> A{i}L")
        body.append(f"    A{i} --> A{i}R")
    doc = make_doc(tmp_path, _mermaid("graph TB\n" + "\n".join(body)))
    assert load_tool().rule_fig_01(doc) == []


def test_fig_01_flags_a_chain_that_is_too_long(tmp_path):
    chain = " --> ".join(f"S{i}" for i in range(10))
    doc = make_doc(tmp_path, _mermaid(f"graph TB\n{chain}"))
    assert len(load_tool().rule_fig_01(doc)) == 1


def test_fig_01_counts_a_chain_written_one_edge_per_line(tmp_path):
    """回归：链一行写一条边时，图照样是长条，不能漏判。

    按「单行有几个节点」去数的话，这种图每行只有 2 个节点，
    一条十步的链会被算成 2——这是最容易漏的一种写法。
    """
    body = "\n".join(f"    S{i} --> S{i + 1}" for i in range(10))
    doc = make_doc(tmp_path, _mermaid("graph TB\n" + body))
    assert len(load_tool().rule_fig_01(doc)) == 1


def test_fig_01_flags_a_node_with_too_many_branches(tmp_path):
    body = "\n".join(f"    Root --> T{i}" for i in range(8))
    doc = make_doc(tmp_path, _mermaid("graph TB\n" + body))
    assert len(load_tool().rule_fig_01(doc)) == 1


def test_fig_01_ignores_a_plain_code_block(tmp_path):
    """不是 mermaid 的代码块不判——里面写几行步骤是正常事。"""
    body = "\n".join(f"step {i}" for i in range(60))
    doc = make_doc(tmp_path, f"# 标题\n\n```text\n{body}\n```\n")
    assert load_tool().rule_fig_01(doc) == []


def test_fig_01_aggregates_into_one_signal_per_article(tmp_path):
    """一篇一条信号：图的个数不该把「信号」列撑爆。"""
    parts = []
    for k in range(3):
        body = "\n".join(f"    N{k}_{i} --> M{k}_{i}" for i in range(16))
        parts.append(f"```mermaid\ngraph TB\n{body}\n```\n")
    doc = make_doc(tmp_path, "# 标题\n\n" + "\n".join(parts))
    signals = load_tool().rule_fig_01(doc)
    assert len(signals) == 1
    assert "3 张图超限" in signals[0].detail


def test_fig_01_does_not_count_the_diagram_header_as_a_box(tmp_path):
    """回归：``stateDiagram-v2`` 是图类型，不是图里的一个框。"""
    module = load_tool()
    body = "stateDiagram-v2\n    [*] --> S1\n    S1 --> S2\n"
    assert module._mermaid_size(body) == (2, 2, 1)
    doc = make_doc(tmp_path, _mermaid(body))
    assert module.rule_fig_01(doc) == []


def test_fig_01_counts_a_node_whose_name_starts_with_end(tmp_path):
    """回归：``end`` 是收尾一个 subgraph 的关键字，不能把 ``endpoint`` 也吞掉。"""
    module = load_tool()
    assert module._mermaid_size("graph TB\n    endpoint --> server\n") == (2, 2, 1)


def test_fig_01_flags_an_over_long_mindmap(tmp_path):
    body = "mindmap\n" + "\n".join(f"    分支{i}" for i in range(21))
    doc = make_doc(tmp_path, _mermaid(body))
    assert len(load_tool().rule_fig_01(doc)) == 1


def test_fig_01_accepts_a_mindmap_within_the_limit(tmp_path):
    body = "mindmap\n" + "\n".join(f"    分支{i}" for i in range(20))
    doc = make_doc(tmp_path, _mermaid(body))
    assert load_tool().rule_fig_01(doc) == []


def test_fig_02_flags_a_reference_far_from_the_figure(tmp_path):
    filler = "\n\n".join(f"第 {i} 段正文。" for i in range(8))
    text = ("# 标题\n\n下图给出这条链路。\n\n" + filler
            + "\n\n```mermaid\ngraph TB\n    A --> B\n```\n")
    doc = make_doc(tmp_path, text)
    signals = load_tool().rule_fig_02(doc)
    assert len(signals) == 1
    assert signals[0].rule == "FIG-02"
    assert signals[0].severity == "info"


def test_fig_02_accepts_a_reference_right_above_the_figure(tmp_path):
    text = "# 标题\n\n下图给出这条链路。\n\n```mermaid\ngraph TB\n    A --> B\n```\n"
    doc = make_doc(tmp_path, text)
    assert load_tool().rule_fig_02(doc) == []


def test_fig_02_ignores_a_reference_when_there_is_no_figure(tmp_path):
    text = "# 标题\n\n下图给出这条链路，但下面并没有图。\n"
    doc = make_doc(tmp_path, text)
    assert load_tool().rule_fig_02(doc) == []


def test_fig_02_finds_a_reference_in_the_middle_of_a_paragraph(tmp_path):
    """回归：引用常常写在段落中间，按「块首行」找会整个漏掉。"""
    filler = "\n\n".join(f"第 {i} 段正文。" for i in range(8))
    text = ("# 标题\n\n这一段先说了背景，\n下图给出这条链路。\n\n" + filler
            + "\n\n```mermaid\ngraph TB\n    A --> B\n```\n")
    doc = make_doc(tmp_path, text)
    signals = load_tool().rule_fig_02(doc)
    assert len(signals) == 1
    assert "下图" in signals[0].detail


def test_the_checker_reports_fig_signals_for_a_real_article():
    """集成：真实文章上跑一遍，FIG-01/FIG-02 真的会报出来。"""
    target = REPO_ROOT / "docs" / "cluster" / "DCF" / "一文读懂openguass dcf网络模块.md"
    assert target.exists(), "样例文章不在了，集成测试要换一个真实文章"
    result = subprocess.run(
        [sys.executable, str(TOOL), str(target), "--json"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    signals = payload["docs"][0]["signals"]
    fig1 = [s for s in signals if s["rule"] == "FIG-01"]
    assert fig1, "这篇有 6 张超长的链式流程图，检查器却没报 FIG-01"
    assert fig1[0]["severity"] == "warn"
    # 聚合信号：位置全部写进 detail，而不是每张图一条
    assert "6 张图超限" in fig1[0]["detail"]


def test_stats_count_mermaid_figures_not_just_markdown_images(tmp_path):
    """回归：一篇满是流程图的文章不该报「图 0」。

    ``images`` 只数 markdown 图片语法；mermaid 的图也是图，
    摘要里漏掉它，审校的人就看不出这篇到底有多少张图。
    """
    module = load_tool()
    text = ("# 标题\n\n```mermaid\ngraph TB\n    A --> B\n```\n\n"
            "![图](./images/x.png)\n")
    path = tmp_path / "index.md"
    path.write_text(text, encoding="utf-8")
    doc = module.load_doc(path)
    module.REPO_ROOT = tmp_path        # to_report 要靠它换算相对路径
    report = module.to_report(doc)
    assert report["stats"]["mermaid"] == 1
    assert report["stats"]["images"] == 1


def test_the_text_report_shows_the_total_figure_count(tmp_path):
    """回归：人读摘要里的「图 N」要是 mermaid 与图片之和。"""
    module = load_tool()
    text = ("# 标题\n\n```mermaid\ngraph TB\n    A --> B\n```\n\n"
            "![图](./images/x.png)\n")
    path = tmp_path / "index.md"
    path.write_text(text, encoding="utf-8")
    doc = module.load_doc(path)
    module.REPO_ROOT = tmp_path
    rendered = module.render_text([doc])
    assert "图 2（mermaid 1 + 图片 1）" in rendered
