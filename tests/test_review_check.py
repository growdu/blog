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
