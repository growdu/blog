# 内容审校落地机制 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `review/README.md` 的审校规范落成可执行的机制——一个只出信号的确定性检查器、一套机器可校验的审校记录契约、一张进度索引，以及 5 篇试点审校记录。

**Architecture:** 两层分离。`tools/review-check.py` 把可计算的指标固定成 19 条带稳定编号的信号（只出位置与计数，不下结论）；Agent 按 README 六步流程读上下文做判断，产出 `review/<支柱>/<slug>.md` 记录；`review/INDEX.md` 是唯一的进度真相源。阶段 A 只出记录（`docs/` 不动），阶段 B 经确认后才改正文。

**Tech Stack:** Python 3 标准库（无第三方依赖）、pytest、根级 `tests/`（已被 `.github/workflows/site-guard.yml` 覆盖，零新增 CI 工作流）。

## Global Constraints

这些约束对每个 task 都生效，不再逐条重复：

- **审校记录、spec、plan 一律放仓库根 `review/`**，不得放 `docs/` 下——`tools/sync-hexo.py` 会把 `docs/**` 转成站点文章，内部流程漏进去就变成线上页面。
- **检查器纯标准库**，不引入第三方依赖（与 `tools/check-markdown.py`、`tools/check-built-links.py` 一致）。
- **检查器只读**：不修改被检文件，不往仓库内写文件（报告默认 stdout，`--out` 由调用方指定路径）。
- **每条规则对每篇文档最多产生 1 个信号**，全部命中位置写进 `detail`；INDEX 的「信号」列因此等于「命中了几条规则」。
- **规则编号一经发布不再变更**：`AIF-01..05`、`DEP-00..05`、`STR-01..05`、`MET-01..02`。
- **审校记录严格使用 `review/README.md` 的模板**，不新增 YAML front matter、不改小节名；机器可读信息从模板既有行（`- 原文：`、`- 范围：`、`- 审校状态：`）解析。
- **每个 commit 自包含**：在「只含该 commit 内容的干净检出」上独立跑通全部测试，不引用后续 commit 才引入的文件。
- **提交粒度**：审校记录每篇一个提交 `docs(review): 记录 <slug>`；正文合入每篇一个提交 `docs(review): <slug>`；两个前缀互斥。
- **含中文的 commit message 必须用 write 工具写成文件再 `git commit -F <file>`**，提交后按码位检查 U+FFFD（heredoc 会把多字节字符截断成替换字符）。
- **每个 commit 配套单元测试 + 集成测试**，且测试必须真的会因为缺陷而红。

---

### Task 1: 检查器骨架（文件发现、文档解析、身份推导、JSON 输出、CLI）

**Files:**
- Create: `tools/review-check.py`
- Create: `tests/test_review_check.py`

**Interfaces:**
- Consumes: 无（本仓库第一批工具）
- Produces:
  - `derive_identity(path: Path, docs_root: Path = DOCS_ROOT) -> tuple[str, str]` → `(pillar, slug)`
    （`docs_root` 可传临时目录，让规则能在临时树上被测）
  - `parse_blocks(lines: list[str]) -> list[Block]`
  - `load_doc(path: Path) -> Doc`
  - `collect_files(paths: list[str]) -> list[Path]`
  - `check_doc(doc: Doc) -> Doc`
  - `to_report(doc: Doc) -> dict`
  - `render_text(docs: list[Doc]) -> str`
  - `main(argv: list[str] | None = None) -> int`
  - `RULES: list` —— 规则函数注册表，Task 2/3/4 往里追加
  - 规则函数签名统一为 `rule_<组>_<编号>(doc: Doc) -> list[Signal]`
  - `Block(kind, text, line, level=0)`、`Signal(rule, severity, line, excerpt, detail)`、`Doc(path, pillar, slug, title, text, lines, blocks, signals, depth)`

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_review_check.py`：

```python
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
```

- [ ] **Step 2: 跑测试确认它红**

Run: `python3 -m pytest tests/test_review_check.py -q`

Expected: FAIL —— `tools/review-check.py` 不存在，collection error。

- [ ] **Step 3: 写最小实现**

创建 `tools/review-check.py`：

```python
#!/usr/bin/env python3
"""审校信号检查器 —— 把 review/README.md 里的机械指标变成可复现的信号。

为什么存在
----------
``review/README.md`` 定义了一套严谨的内容审校规范，但其中最容易漏的一类检查
（AI 味信号、证据密度、章节结构）靠人眼数：同一篇文章今天判「有 AI 味」、
明天判「没有」，谁都说不清依据，也无法回归。

这个脚本把这类**可计算的**指标固定下来，对每篇文章输出一组带编号的信号
（位置、摘录、计数）。它**不下结论**——「是不是空泛评价」「技术深度够不够」
仍然要读上下文的人来判断。工具只负责把「值得看一眼的地方」标出来。

信号不是门禁：命中信号不会让脚本返回非零退出码。一篇老文章的历史问题
不该永久卡住流水线。

用法::

    python3 tools/review-check.py docs/database/postgresql-mvcc/index.md
    python3 tools/review-check.py docs/database docs/db --json --out /tmp/s.json

只读：不修改任何被检文件，也不往仓库里写文件。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO_ROOT / "docs"

HEADING = "heading"
PARAGRAPH = "paragraph"
CODE = "code"
LIST = "list"
TABLE = "table"
QUOTE = "quote"

FENCE_RE = re.compile(r"^\s*(```+|~~~+)(.*)$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
TABLE_RE = re.compile(r"^\s*\|.*\|\s*$")
QUOTE_RE = re.compile(r"^\s*>")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
# 链接与图片的区别在 ``!`` 上，而 ``!`` 出现在 ``[`` **之前**——
# 用 ``(?<!\!)`` 挂在 ``]`` 前面是拦不住图片的，只能把 ``!`` 收进捕获组。
LINK_RE = re.compile(r"(!?)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


@dataclass
class Block:
    kind: str
    text: str
    line: int
    level: int = 0


@dataclass
class Signal:
    rule: str
    severity: str
    line: int
    excerpt: str
    detail: str

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "line": self.line,
            "excerpt": self.excerpt,
            "detail": self.detail,
        }


@dataclass
class Doc:
    path: Path
    pillar: str
    slug: str
    title: str
    text: str
    lines: list[str]
    blocks: list[Block]
    signals: list[Signal] = field(default_factory=list)
    depth: dict = field(default_factory=dict)

    @property
    def rel_path(self) -> str:
        return self.path.relative_to(REPO_ROOT).as_posix()

    def paragraphs(self) -> list[Block]:
        return [b for b in self.blocks if b.kind == PARAGRAPH]

    def excerpt(self, line: int, limit: int = 120) -> str:
        """The source line at ``line`` (1-based), truncated."""
        if 1 <= line <= len(self.lines):
            text = self.lines[line - 1].strip()
        else:
            text = ""
        return text[:limit]


# 规则注册表：每个任务往里追加自己的规则函数。
RULES: list = []


def derive_identity(path: Path, docs_root: Path = DOCS_ROOT) -> tuple[str, str]:
    """Derive ``(pillar, slug)`` from a docs/-relative path.

    ``docs/database/postgresql-mvcc/index.md`` -> ``("database", "postgresql-mvcc")``
    ``docs/database/pg-dont-do-this.md``      -> ``("database", "pg-dont-do-this")``
    ``docs/db/postgresql/xxx.md``             -> ``("db", "postgresql/xxx")``

    ``docs_root`` exists so the rule can be exercised on a temporary tree
    instead of the repository's own ``docs/``.
    """
    try:
        rel = path.resolve().relative_to(docs_root.resolve())
    except ValueError:
        return "", path.stem
    parts = list(rel.parts)
    if len(parts) == 1:
        return "", parts[0].rsplit(".", 1)[0]
    pillar = parts[0]
    rest = parts[1:]
    if rest and rest[-1] in ("index.md", "README.md"):
        rest = rest[:-1]
    else:
        rest[-1] = rest[-1].rsplit(".", 1)[0]
    return pillar, "/".join(rest)


def parse_blocks(lines: list[str]) -> list[Block]:
    """Split markdown source lines into typed blocks.

    A leading YAML front matter block (``---`` ... ``---``) is metadata,
    not prose -- 51 of the 282 reviewed articles have one -- so it is
    skipped instead of being parsed as paragraphs.
    """
    blocks: list[Block] = []
    i = 0
    total = len(lines)
    if lines and lines[0].strip() == "---":
        j = 1
        while j < total and lines[j].strip() != "---":
            j += 1
        i = j + 1
    while i < total:
        raw = lines[i]
        line_no = i + 1
        if not raw.strip():
            i += 1
            continue

        fence = FENCE_RE.match(raw)
        if fence:
            marker = fence.group(1)
            body = []
            j = i + 1
            while j < total and not lines[j].strip().startswith(marker[:3]):
                body.append(lines[j])
                j += 1
            blocks.append(Block(CODE, "\n".join(body), line_no))
            i = j + 1
            continue

        heading = HEADING_RE.match(raw)
        if heading:
            blocks.append(Block(HEADING, heading.group(2).strip(), line_no, len(heading.group(1))))
            i += 1
            continue

        if TABLE_RE.match(raw):
            body = []
            j = i
            while j < total and TABLE_RE.match(lines[j]):
                body.append(lines[j])
                j += 1
            blocks.append(Block(TABLE, "\n".join(body), line_no))
            i = j
            continue

        if LIST_RE.match(raw):
            body = []
            j = i
            while j < total and (LIST_RE.match(lines[j]) or
                                 (lines[j].startswith(("  ", "\t")) and lines[j].strip())):
                body.append(lines[j])
                j += 1
            blocks.append(Block(LIST, "\n".join(body), line_no))
            i = j
            continue

        if QUOTE_RE.match(raw):
            body = []
            j = i
            while j < total and QUOTE_RE.match(lines[j]):
                body.append(lines[j])
                j += 1
            blocks.append(Block(QUOTE, "\n".join(body), line_no))
            i = j
            continue

        body = []
        j = i
        while j < total and lines[j].strip() \
                and not FENCE_RE.match(lines[j]) \
                and not HEADING_RE.match(lines[j]) \
                and not TABLE_RE.match(lines[j]) \
                and not LIST_RE.match(lines[j]) \
                and not QUOTE_RE.match(lines[j]):
            body.append(lines[j])
            j += 1
        blocks.append(Block(PARAGRAPH, "\n".join(body), line_no))
        i = j
    return blocks


def collect_files(paths: list[str]) -> list[Path]:
    """Expand the CLI arguments into a sorted, de-duplicated list of files."""
    found: list[Path] = []
    for raw in paths:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        if candidate.is_file():
            found.append(candidate.resolve())
        elif candidate.is_dir():
            for child in sorted(candidate.rglob("*.md")):
                if any(part.startswith(".") for part in child.parts):
                    continue
                found.append(child.resolve())
        else:
            raise FileNotFoundError(raw)
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in found:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def load_doc(path: Path) -> Doc:
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines = raw.split("\n")
    blocks = parse_blocks(lines)
    pillar, slug = derive_identity(path)
    title = ""
    for block in blocks:
        if block.kind == HEADING:
            title = block.text
            break
    return Doc(path=path, pillar=pillar, slug=slug, title=title,
               text=raw, lines=lines, blocks=blocks)


def check_doc(doc: Doc) -> Doc:
    doc.signals = []
    doc.depth = {}
    for rule in RULES:
        for signal in rule(doc):
            doc.signals.append(signal)
    return doc


def to_report(doc: Doc) -> dict:
    depth_ok = sum(1 for key, value in doc.depth.items() if key != "DEP-00" and value > 0) >= 2
    return {
        "source": doc.rel_path,
        "pillar": doc.pillar,
        "slug": doc.slug,
        "title": doc.title,
        "stats": {
            "chars": len(doc.text),
            "paragraphs": len(doc.paragraphs()),
            "h2": sum(1 for b in doc.blocks if b.kind == HEADING and b.level == 2),
            "code_blocks": sum(1 for b in doc.blocks if b.kind == CODE),
            "tables": sum(1 for b in doc.blocks if b.kind == TABLE),
            "images": len(IMAGE_RE.findall(doc.text)),
            "links": sum(1 for m in LINK_RE.finditer(doc.text) if m.group(1) != "!"),
        },
        "depth": doc.depth,
        "depth_ok": depth_ok,
        "signals": [s.to_dict() for s in doc.signals],
    }


def render_text(docs: list[Doc]) -> str:
    out: list[str] = []
    for doc in docs:
        report = to_report(doc)
        stats = report["stats"]
        out.append(f"{report['source']}  [{report['pillar']}/{report['slug']}]")
        out.append(f"  {report['title']}")
        out.append(
            "  段落 {paragraphs} · 章节 {h2} · 代码块 {code_blocks} · 图 {images} · 链接 {links}".format(**stats)
        )
        depth = report["depth"]
        if depth:
            out.append("  深度 " + " ".join(f"{k}={v}" for k, v in sorted(depth.items())))
        for signal in report["signals"]:
            mark = "⚠" if signal["severity"] == "warn" else "·"
            out.append(f"  {mark} {signal['rule']} L{signal['line']}  {signal['detail']}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="审校信号检查器")
    parser.add_argument("paths", nargs="+", help="要检查的文件或目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 而不是人读摘要")
    parser.add_argument("--out", help="输出到文件（默认 stdout）")
    args = parser.parse_args(argv)

    try:
        files = collect_files(args.paths)
    except FileNotFoundError as exc:
        print(f"路径不存在: {exc}", file=sys.stderr)
        return 1

    docs = [check_doc(load_doc(path)) for path in files]
    if args.json:
        text = json.dumps({"docs": [to_report(d) for d in docs]}, ensure_ascii=False, indent=2)
    else:
        text = render_text(docs)

    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 跑测试确认它绿**

Run: `python3 -m pytest tests/test_review_check.py -q`

Expected: PASS（9 passed）。

- [ ] **Step 5: 提交**

用 write 工具把下面的内容写成 `/tmp/review-task1-commit.txt`，然后：

```bash
cd /Users/growduduan/code/blog
git add tools/review-check.py tests/test_review_check.py
git commit -F /tmp/review-task1-commit.txt
git log -1 --format=%B | python3 -c "
import sys
t = sys.stdin.read()
print('U+FFFD 坏字符:', sum(1 for c in t if ord(c) == 0xFFFD))
"
```

commit message：

```
feat(review): 审校检查器骨架

把审校的机械部分做成工具：文件发现、markdown 分块解析、支柱/slug 推导、
JSON 输出与 CLI。

检查器只出信号不下结论——AI 味、技术深度这些判断仍然要读上下文的人来做，
工具的价值是让「值得看一眼的地方」可复现，而不是成为内容标准。

纯标准库、只读、不写仓库内文件；命中信号不导致非零退出码。
```

---

### Task 2: AI 味信号（AIF-01 ~ AIF-05）

**Files:**
- Modify: `tools/review-check.py`
- Modify: `tests/test_review_check.py`

**Interfaces:**
- Consumes: Task 1 的 `Doc` / `Block` / `Signal` / `RULES`
- Produces: `rule_aif_01(doc) ~ rule_aif_05(doc) -> list[Signal]`，注册进 `RULES`

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_review_check.py`：

```python
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


def test_aif_05_ignores_parallel_code_introduction_lines(tmp_path):
    """回归：「事务 XID=200 执行：」和「事务 XID=300 执行：」是并列结构，不是冗余。"""
    text = (
        "事务 XID=200 执行：\n\n"
        "```sql\nDELETE FROM account WHERE id = 1;\n```\n\n"
        "事务 XID=300 执行：\n"
    )
    doc = make_doc(tmp_path, text)
    assert load_tool().rule_aif_05(doc) == []


def test_aif_05_flags_near_duplicate_sentences(tmp_path):
    text = (
        "在并发场景下，写入会阻塞另一个事务的读取操作。\n\n"
        "在并发场景下，写入会阻塞另一个事务的读取行为。\n"
    )
    doc = make_doc(tmp_path, text)
    signals = load_tool().rule_aif_05(doc)
    assert len(signals) == 1
    assert signals[0].rule == "AIF-05"
```

- [ ] **Step 2: 跑测试确认它红**

Run: `python3 -m pytest tests/test_review_check.py -q -k aif`

Expected: FAIL —— `AttributeError: module 'review_check' has no attribute 'rule_aif_01'`

- [ ] **Step 3: 写实现**

在 `tools/review-check.py` 的 `RULES: list = []` **之后**插入：

```python
# --- AI 味信号 -------------------------------------------------------------

CONNECTORS = ("首先", "其次", "最后", "此外", "值得注意的是",
              "总而言之", "综上所述", "总的来说", "事实上")
CONNECTOR_RATIO = 0.15

VAGUE_WORDS = ("高效", "全面", "显著", "至关重要", "强大", "极大",
               "非常好", "行业领先", "完美")
LONG_PARAGRAPH = 200

GENERIC_ENDINGS = ("希望本文", "本文到此结束", "以上就是", "让我们一起")
GENERIC_ENDING_RE = re.compile(r"随着.{0,20}的发展")

SENTENCE_SPLIT_RE = re.compile(r"[。！？!?；;]")
DUPLICATE_THRESHOLD = 0.85
DUPLICATE_MIN_LEN = 12
DUPLICATE_MIN_CJK = 15
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _paragraphs_with_index(doc: Doc) -> list[tuple[int, Block]]:
    return [(index, b) for index, b in enumerate(doc.blocks) if b.kind == PARAGRAPH]


def rule_aif_01(doc: Doc) -> list[Signal]:
    """Paragraphs that open with a structural connector.

    Only the paragraph start counts: 「最后」 inside a sentence is not a
    structural connector, and counting it would drown the signal in noise.
    """
    paragraphs = doc.paragraphs()
    if not paragraphs:
        return []
    hits = []
    for block in paragraphs:
        for word in CONNECTORS:
            if block.text.startswith(word):
                hits.append((block.line, word))
                break
    ratio = len(hits) / len(paragraphs)
    if ratio <= CONNECTOR_RATIO:
        return []
    line = hits[0][0]
    detail = f"{len(hits)}/{len(paragraphs)} 段落以连接词开头（{ratio:.0%}）: " + \
             "、".join(f"L{ln} {word}" for ln, word in hits[:8])
    return [Signal("AIF-01", "warn", line, doc.excerpt(line), detail)]


def rule_aif_02(doc: Doc) -> list[Signal]:
    """Empty praise with nothing backing it up."""
    hits = []
    for index, block in _paragraphs_with_index(doc):
        for word in VAGUE_WORDS:
            if word not in block.text:
                continue
            has_number = re.search(r"\d", block.text) is not None
            next_kind = doc.blocks[index + 1].kind if index + 1 < len(doc.blocks) else ""
            supported = has_number or next_kind in (CODE, TABLE)
            if not supported:
                hits.append((block.line, word))
    if not hits:
        return []
    line = hits[0][0]
    detail = f"{len(hits)} 处空泛评价无证据支撑: " + \
             "、".join(f"L{ln} {word}" for ln, word in hits[:8])
    return [Signal("AIF-02", "warn", line, doc.excerpt(line), detail)]


def rule_aif_03(doc: Doc) -> list[Signal]:
    """Paragraphs long enough to hide several claims in one breath."""
    hits = [(b.line, len(b.text)) for b in doc.paragraphs() if len(b.text) > LONG_PARAGRAPH]
    if not hits:
        return []
    line = hits[0][0]
    detail = f"{len(hits)} 段超过 {LONG_PARAGRAPH} 字: " + \
             "、".join(f"L{ln}({size}字)" for ln, size in hits[:8])
    return [Signal("AIF-03", "warn", line, doc.excerpt(line), detail)]


def rule_aif_04(doc: Doc) -> list[Signal]:
    """The closing paragraph that says nothing."""
    paragraphs = doc.paragraphs()
    if not paragraphs:
        return []
    tail = paragraphs[-3:]
    hits = []
    for block in tail:
        for word in GENERIC_ENDINGS:
            if word in block.text:
                hits.append((block.line, word))
                break
        else:
            if GENERIC_ENDING_RE.search(block.text):
                hits.append((block.line, "随着…的发展"))
    if not hits:
        return []
    line = hits[0][0]
    detail = f"结尾出现泛化收尾语: " + "、".join(f"L{ln} {word}" for ln, word in hits)
    return [Signal("AIF-04", "warn", line, doc.excerpt(line), detail)]


def rule_aif_05(doc: Doc) -> list[Signal]:
    """Sentences that say the same thing twice.

    Only sentences written in Chinese prose count.  Code-introduction
    lines like 「事务 XID=200 执行：」 and 「事务 XID=300 执行：」 are
    93% identical but are parallel structure, not redundancy -- flagging
    them would bury the real finding under noise.
    """
    sentences = []
    for block in doc.paragraphs():
        for piece in SENTENCE_SPLIT_RE.split(block.text):
            piece = piece.strip()
            if len(piece) < DUPLICATE_MIN_LEN:
                continue
            if len(CJK_RE.findall(piece)) < DUPLICATE_MIN_CJK:
                continue
            sentences.append((block.line, piece))
    buckets: dict[int, list[tuple[int, str]]] = {}
    for line, sentence in sentences:
        buckets.setdefault(len(sentence) // 5, []).append((line, sentence))
    pairs = []
    for group in buckets.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i][1], group[j][1]
                similarity = difflib.SequenceMatcher(None, a, b).ratio()
                if similarity >= DUPLICATE_THRESHOLD:
                    pairs.append((group[i][0], group[j][0], similarity))
    if not pairs:
        return []
    line = pairs[0][0]
    detail = f"{len(pairs)} 对近似重复句: " + \
             "、".join(f"L{a}~L{b}({sim:.2f})" for a, b, sim in pairs[:5])
    return [Signal("AIF-05", "warn", line, doc.excerpt(line), detail)]


RULES.extend([rule_aif_01, rule_aif_02, rule_aif_03, rule_aif_04, rule_aif_05])
```

并在文件顶部的 import 区加上 `import difflib`（放在 `import argparse` 之前，按字母序）。

- [ ] **Step 4: 跑测试确认它绿**

Run: `python3 -m pytest tests/test_review_check.py -q`

Expected: PASS（17 passed）。

- [ ] **Step 5: 提交**

write 工具写 `/tmp/review-task2-commit.txt`，内容：

```
feat(review): 审校检查器加 AI 味信号

按 review/README.md 的「常见 AI 味信号」清单落 5 条规则：连接词开头的段落、
无证据的空泛评价、超长段落、泛化收尾、近似重复句。

每条规则每篇文档最多出一个信号，全部命中位置写进 detail——INDEX 的
「信号」列因此是「命中了几条规则」，不会被重复句数量灌水。

规则只标位置不下结论：连接词占比高不一定是坏文，得看上下文。
```

然后 `git add tools/review-check.py tests/test_review_check.py && git commit -F /tmp/review-task2-commit.txt`。

---

### Task 3: 技术深度五要素（DEP-01 ~ DEP-05 + DEP-00）

**Files:**
- Modify: `tools/review-check.py`
- Modify: `tests/test_review_check.py`

**Interfaces:**
- Consumes: Task 1 的 `Doc` / `Block` / `Signal` / `RULES`；Task 2 的 `CODE` / `TABLE` 常量
- Produces: `rule_dep_01(doc) ~ rule_dep_05(doc) -> list[Signal]`，并把命中计数写进 `doc.depth`

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_review_check.py`：

```python
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


def test_dep_04_counts_tradeoff_wording_beyond_comparison(tmp_path):
    """回归：只认「相比/替代」会漏掉用「优点/缺点」讲取舍的文章。"""
    doc = make_doc(tmp_path, "它的优点是简单，缺点是不好扩展。\n")
    module = load_tool()
    module.check_doc(doc)
    assert doc.depth["DEP-04"] > 0


def test_dep_03_needs_a_code_block_not_prose(tmp_path):
    doc = make_doc(tmp_path, "正文里提到 SELECT 这个关键字，但没有代码块。\n")
    module = load_tool()
    module.check_doc(doc)
    assert doc.depth["DEP-03"] == 0
```

- [ ] **Step 2: 跑测试确认它红**

Run: `python3 -m pytest tests/test_review_check.py -q -k dep`

Expected: FAIL —— `doc.depth` 为空，断言失败。

- [ ] **Step 3: 写实现**

在 Task 2 的规则之后插入：

```python
# --- 技术深度五要素 ---------------------------------------------------------

VERSION_RE = re.compile(
    r"(?i)\b(?:postgresql|pg|opengauss|linux|kernel|ubuntu|centos)\s+v?\d+(?:\.\d+)*"
    r"|\bv?\d+\.\d+(?:\.\d+)*\b"
)
BOUNDARY_WORDS = ("环境", "前提", "规模", "边界", "前置条件", "版本")

SOURCE_PATH_RE = re.compile(r"(?:src|backend|include)/[A-Za-z0-9_./-]+\.[ch]\b")
IDENTIFIER_CALL_RE = re.compile(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\s*\(")
MECHANISM_WORDS = ("调用链", "状态机", "执行器", "流程", "实现", "源码")

EVIDENCE_RE = re.compile(
    r"(?i)\b(?:select|insert|update|delete|create|explain|vacuum|psql|docker|gdb|strace|perf|tcpdump)\b"
)
EVIDENCE_SHELL_RE = re.compile(r"(?m)^\s*(\$ |#\s|docker |psql |gdb |strace |perf |tcpdump )")
EVIDENCE_LOG_RE = re.compile(r"(?m)^\s*(LOG|ERROR|WARNING|PANIC|FATAL)[:\s]")

TRADEOFF_WORDS = ("相比", "相比之下", "替代", "取舍", "权衡", "代价", "适用场景",
                  "优点", "缺点", "利弊", "优劣", "对比", "选型", "不建议", "更推荐")
PITFALL_WORDS = ("坑", "注意", "误区", "验证", "校验", "复现", "监控", "陷阱", "别用",
                 "不要用", "风险", "切勿", "务必", "检查", "观察")


def _count_regex(doc: Doc, pattern: re.Pattern) -> int:
    return len(pattern.findall(doc.text))


def _count_words(doc: Doc, words: tuple[str, ...]) -> int:
    return sum(doc.text.count(word) for word in words)


def rule_dep_01(doc: Doc) -> list[Signal]:
    """问题边界：版本、系统规模、前置条件。"""
    doc.depth["DEP-01"] = _count_regex(doc, VERSION_RE) + _count_words(doc, BOUNDARY_WORDS)
    return []


def rule_dep_02(doc: Doc) -> list[Signal]:
    """机制解释：源码定位与调用链。"""
    doc.depth["DEP-02"] = (_count_regex(doc, SOURCE_PATH_RE)
                            + _count_regex(doc, IDENTIFIER_CALL_RE)
                            + _count_words(doc, MECHANISM_WORDS))
    return []


def rule_dep_03(doc: Doc) -> list[Signal]:
    """可复现证据：能照着跑的命令、SQL 或日志。"""
    total = 0
    for block in doc.blocks:
        if block.kind != CODE:
            continue
        if EVIDENCE_RE.search(block.text) or EVIDENCE_SHELL_RE.search(block.text) \
                or EVIDENCE_LOG_RE.search(block.text):
            total += 1
    doc.depth["DEP-03"] = total
    return []


def rule_dep_04(doc: Doc) -> list[Signal]:
    """工程取舍：替代方案、代价、适用场景。"""
    doc.depth["DEP-04"] = _count_words(doc, TRADEOFF_WORDS)
    return []


def rule_dep_05(doc: Doc) -> list[Signal]:
    """踩坑与校验：怎么观察、怎么验证结果。"""
    doc.depth["DEP-05"] = _count_words(doc, PITFALL_WORDS)
    return []


def rule_dep_00(doc: Doc) -> list[Signal]:
    """要素命中少于 2 项：技术深度可能不够。"""
    elements = sum(1 for key in ("DEP-01", "DEP-02", "DEP-03", "DEP-04", "DEP-05")
                   if doc.depth.get(key, 0) > 0)
    doc.depth["DEP-00"] = 0 if elements >= 2 else 1
    if elements >= 2:
        return []
    return [Signal("DEP-00", "warn", 1, "",
                   f"只命中 {elements}/5 个技术深度要素（边界/机制/证据/取舍/校验）")]


RULES.extend([rule_dep_01, rule_dep_02, rule_dep_03, rule_dep_04, rule_dep_05, rule_dep_00])
```

- [ ] **Step 4: 跑测试确认它绿**

Run: `python3 -m pytest tests/test_review_check.py -q`

Expected: PASS（21 passed）。

- [ ] **Step 5: 提交**

write 工具写 `/tmp/review-task3-commit.txt`：

```
feat(review): 审校检查器加技术深度五要素

把 review/README.md 的五要素落成可数的东西：版本与边界、源码定位、
可跑的命令/SQL/日志、取舍对比、踩坑与校验。

DEP-00 只在命中少于 2 项时报警——要素计数是提示，「这篇深度够不够」
仍然要读全文判断。
```

然后 `git add tools/review-check.py tests/test_review_check.py && git commit -F /tmp/review-task3-commit.txt`。

---

### Task 4: 结构、产物与元信息（STR-01 ~ STR-05、MET-01 ~ MET-02）

**Files:**
- Modify: `tools/review-check.py`
- Modify: `tests/test_review_check.py`

**Interfaces:**
- Consumes: Task 1 的 `Doc` / `Block` / `Signal` / `RULES`；Task 2 的 `CODE` / `TABLE`
- Produces: `rule_str_01(doc) ~ rule_str_05(doc)`、`rule_met_01(doc)`、`rule_met_02(doc)`

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_review_check.py`：

```python
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


def test_met_01_flags_a_missing_author_table(tmp_path):
    doc = make_doc(tmp_path, "# 标题\n\n正文。\n")
    signals = load_tool().rule_met_01(doc)
    assert len(signals) == 1
    assert signals[0].rule == "MET-01"


def test_met_01_accepts_the_author_table(tmp_path):
    text = "# 标题\n\n| 编写人 | 编写内容 | 编写时间 |\n| --- | --- | --- |\n| growdu | 初稿 | 2026-08-20 |\n\n正文。\n"
    doc = make_doc(tmp_path, text)
    assert load_tool().rule_met_01(doc) == []


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


def test_str_02_flags_a_missing_opening_positioning(tmp_path):
    doc = make_doc(tmp_path, "# 标题\n\n正文开始了。\n\n第二段。\n\n第三段。\n")
    signals = load_tool().rule_str_02(doc)
    assert len(signals) == 1
    assert signals[0].rule == "STR-02"
```

- [ ] **Step 2: 跑测试确认它红**

Run: `python3 -m pytest tests/test_review_check.py -q -k "str_ or met_"`

Expected: FAIL —— `AttributeError: ... has no attribute 'rule_str_04'`

- [ ] **Step 3: 写实现**

在 Task 3 的规则之后插入：

```python
# --- 结构、产物与元信息 -----------------------------------------------------

POSITIONING_RE = re.compile(
    r"本文.{0,20}(回答|解决|讲|介绍|将|会|带|拆|说|帮你)"
    r"|这篇文章|为什么|难题|先说"
)
TAKEAWAY_WORDS = ("清单", "检查表", "决策表", "排查", "下一步", "下一篇", "延伸阅读",
                   "相关阅读", "参考资料", "同系列", "前文", "总结", "小结", "要点")

# 图片不是文章链接：``![]()`` 必须排除，否则图片路径会被判成断链。
# ``!`` 在 ``[`` 之前而不是 ``]`` 之前，所以只能把 ``!`` 收进捕获组来区分。
MD_LINK_RE = re.compile(r"(!?)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def rule_str_01(doc: Doc) -> list[Signal]:
    """Fewer than three second-level sections."""
    count = sum(1 for b in doc.blocks if b.kind == HEADING and b.level == 2)
    if count >= 3:
        return []
    return [Signal("STR-01", "info", 1, "", f"二级章节只有 {count} 个（< 3）")]


def rule_str_02(doc: Doc) -> list[Signal]:
    """The opening does not say what problem the article solves."""
    for block in doc.paragraphs()[:5]:
        if POSITIONING_RE.search(block.text):
            return []
        if block.text.rstrip().endswith("？"):
            return []
    return [Signal("STR-02", "info", 1, "", "开头 5 段没有说明文章解决什么问题")]


def rule_str_03(doc: Doc) -> list[Signal]:
    """The ending leaves the reader with nothing to carry away.

    The tail is inspected as *blocks*, not paragraphs: the takeaway is
    usually a heading plus a list（「参考资料」「同系列前文」「排查清单」）,
    and looking at paragraphs only would miss every one of them.
    """
    for block in doc.blocks[-8:]:
        if any(word in block.text for word in TAKEAWAY_WORDS):
            return []
    return [Signal("STR-03", "info", 1, "", "结尾没有可带走的产物（清单/参考资料/下一篇）")]


def _link_target_exists(target: str, post_dir: Path) -> bool:
    """Whether a relative article link points at something that exists.

    The resolution rule mirrors ``tools/sync-hexo.py:rewrite_links``:
    resolve the link as written against the post's own directory, and if
    that misses, fall back to the sibling directory one level up -- the
    publisher does the same, so ``./b/index.html`` inside
    ``docs/database/a/index.md`` means ``docs/database/b/``.

    Only existence is checked here; producing the permalink would need
    git lookups, and the review only needs to know the target is there.
    """
    candidate = (post_dir / target).resolve()
    if candidate.is_dir():
        return any((candidate / name).is_file()
                   for name in ("index.md", "index.html", "index.htm", "_index.md"))
    if candidate.is_file():
        return True
    if target.endswith((".html", ".htm")):
        if candidate.with_suffix(".md").is_file():
            return True
        return (candidate.parent / "index.md").is_file()
    return False


def rule_str_04(doc: Doc) -> list[Signal]:
    """Relative links that point at nothing."""
    post_dir = doc.path.parent
    hits = []
    for match in MD_LINK_RE.finditer(doc.text):
        if match.group(1) == "!":
            continue  # 图片
        raw = match.group(2)
        if raw.startswith(("http://", "https://", "//", "#", "mailto:", "data:")):
            continue
        if not raw.startswith(("./", "../")):
            continue
        target = raw.split("#", 1)[0].split("?", 1)[0]
        if not target:
            continue
        # 先按写法解析，再回退兄弟目录——两步都不中才算断链。
        if _link_target_exists(target, post_dir):
            continue
        if _link_target_exists(target.lstrip("./"), post_dir.parent):
            continue
        line = doc.text[: match.start()].count("\n") + 1
        hits.append((line, target))
    if not hits:
        return []
    line = hits[0][0]
    detail = f"{len(hits)} 个相对链接指向不存在的文章: " + \
             "、".join(f"L{ln} {target}" for ln, target in hits[:6])
    return [Signal("STR-04", "warn", line, doc.excerpt(line), detail)]


def rule_str_05(doc: Doc) -> list[Signal]:
    """Wrong capitalisation of the product name."""
    hits = [number for number, line in enumerate(doc.lines, 1) if "Postgresql" in line]
    if not hits:
        return []
    return [Signal("STR-05", "info", hits[0], doc.excerpt(hits[0]),
                   f"{len(hits)} 行把 PostgreSQL 写成了 Postgresql")]


def rule_met_01(doc: Doc) -> list[Signal]:
    """The article is missing its author table."""
    for block in doc.blocks:
        if block.kind == TABLE and "编写人" in block.text:
            return []
    return [Signal("MET-01", "info", 1, "", "缺少「编写人 / 编写内容 / 编写时间」信息表")]


def rule_met_02(doc: Doc) -> list[Signal]:
    """The article is missing its H1 title."""
    if any(b.kind == HEADING and b.level == 1 for b in doc.blocks):
        return []
    return [Signal("MET-02", "info", 1, "", "缺少 H1 标题")]

RULES.extend([rule_str_01, rule_str_02, rule_str_03, rule_str_04,
```

- [ ] **Step 4: 跑测试确认它绿**

Run: `python3 -m pytest tests/test_review_check.py -q`

Expected: PASS（31 passed）。

- [ ] **Step 5: 跑真实文章看信号合不合理**
Run:

```bash
python3 tools/review-check.py docs/database/postgresql-mvcc/index.md
python3 tools/review-check.py docs/database docs/db docs/pgsql docs/cluster --json --out /tmp/review-signals.json
python3 -c "
import json
d = json.load(open('/tmp/review-signals.json'))['docs']
warn = [x for x in d if any(s['severity']=='warn' for s in x['signals'])]
print('总篇数', len(d), '有 warn 的', len(warn))
from collections import Counter
c = Counter(s['rule'] for x in d for s in x['signals'])
print(c.most_common())
"
```

**验收**：规则编号都能命中；`STR-04` 不应大面积误报（若超过 20% 的文章报断链，
说明解析规则与 `sync-hexo.py` 不一致，**先修规则再往下走**）。

- [ ] **Step 6: 提交**

write 工具写 `/tmp/review-task4-commit.txt`：

```
feat(review): 审校检查器加结构与元信息规则

落 7 条规则：章节数、开头定位、结尾产物、相对链接可达性、术语大小写、
编写人信息表、H1 标题。

STR-04 的解析规则与发布器一致：先按写法解析，再回退兄弟目录——
docs/database/a/index.md 里的 ./b/index.html 指的是 docs/database/b/。
判「可达」而不是「长什么样」，因为审校只需要知道目标在不在。
```

然后 `git add tools/review-check.py tests/test_review_check.py && git commit -F /tmp/review-task4-commit.txt`。

---

### Task 5: 审校记录契约、进度索引与第一篇试点记录

**Files:**
- Create: `tests/test_review_records.py`
- Create: `review/INDEX.md`
- Create: `review/database/postgresql-mvcc.md`

**Interfaces:**
- Consumes: Task 1~4 的检查器（仅用于给记录填「信号」列）
- Produces:
  - `tests/test_review_records.py` 里的 `parse_record(path) -> dict`（键 `source` / `scope` / `status`）
  - `review/INDEX.md` 的表格格式：`| [slug](<相对路径>) | <支柱> | <状态> | <信号数> | <待确认数> | <批次> |`

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_review_records.py`：

```python
"""契约测试：审校记录、进度索引与 docs/ 纯净性。

这些是 review/README.md 流程的「不可绕过」部分。规范写在纸上没有约束力，
能让人绕过规范的是「反正没人查」——所以这里把规范里最容易被绕过的几条
钉成断言：

1. 记录必须落在受审支柱目录下（审校范围不扩散）；
2. 记录必须齐全 README 模板的每个小节（半截记录等于没记录）；
3. 记录里引用的原文必须真实存在（原文改名了，记录就成了孤儿）；
4. 索引与记录目录必须双向一致（进度表不能骗人）；
5. 状态取值必须在状态机内，且「已合入」必须真有对应提交、该提交确实改了正文；
6. 「已合入」的记录不能还留着没销掉的待核事实；
7. docs/ 下不得出现审校记录——docs/ 会被 sync-hexo.py 发布成站点文章，
   内部流程漏到线上就是事故。
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_ROOT = REPO_ROOT / "review"
DOCS_ROOT = REPO_ROOT / "docs"

# 首轮审校范围：数据库内核四支柱。
REVIEWED_PILLARS = ("database", "db", "pgsql", "cluster")

STATES = ("待审", "审校中", "建议中", "已确认", "已合入")

# README 模板里的小节标题，一个都不能少。
TEMPLATE_SECTIONS = (
    "## 优先修改",
    "## 事实待核",
    "## 可补的技术证据或产物",
    "## 已确认的改动",
)

INDEX_ROW_RE = re.compile(r"^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|(.*)\|\s*$")


def record_files() -> list[Path]:
    return sorted(p for p in REVIEW_ROOT.rglob("*.md")
                  if p.name not in ("README.md", "INDEX.md")
                  and "specs" not in p.parts and "plans" not in p.parts)


def parse_record(path: Path) -> dict:
    """Pull the machine-readable lines out of a review record."""
    text = path.read_text(encoding="utf-8")
    info = {"source": "", "scope": "", "status": "", "text": text}
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- 原文："):
            info["source"] = stripped[len("- 原文："):].strip().strip("`")
        elif stripped.startswith("- 范围："):
            info["scope"] = stripped[len("- 范围："):].strip()
        elif stripped.startswith("- 审校状态："):
            info["status"] = stripped[len("- 审校状态："):].strip()
    return info


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT,
                            capture_output=True, text=True)
    return result.stdout


def merged_commit_for(slug: str) -> list[str]:
    """Commits whose subject is exactly ``docs(review): <slug>``."""
    out = git("log", "--format=%H%x00%s", "--all")
    shas = []
    for line in out.split("\n"):
        if "\x00" not in line:
            continue
        sha, subject = line.split("\x00", 1)
        if subject.strip() == f"docs(review): {slug}":
            shas.append(sha)
    return shas


def test_records_live_under_a_reviewed_pillar():
    for path in record_files():
        rel = path.relative_to(REVIEW_ROOT)
        assert rel.parts[0] in REVIEWED_PILLARS, f"{rel} 不在首轮审校范围内"


def test_record_has_all_template_sections():
    for path in record_files():
        text = path.read_text(encoding="utf-8")
        for section in TEMPLATE_SECTIONS:
            assert section in text, f"{path.name} 缺少小节 {section}"


def test_record_source_file_exists():
    for path in record_files():
        info = parse_record(path)
        assert info["source"], f"{path.name} 没写原文路径"
        source = REPO_ROOT / info["source"]
        assert source.exists(), f"{path.name} 的原文不存在: {info['source']}"


def test_index_matches_record_directory():
    index = REVIEW_ROOT / "INDEX.md"
    assert index.exists(), "缺少 review/INDEX.md"
    listed = set()
    for line in index.read_text(encoding="utf-8").split("\n"):
        match = INDEX_ROW_RE.match(line.strip())
        if not match:
            continue
        listed.add((REVIEW_ROOT / match.group(2)).resolve())
    on_disk = {p.resolve() for p in record_files()}
    assert listed == on_disk, (
        f"索引与记录不一致：索引多 {sorted(str(p) for p in listed - on_disk)}，"
        f"索引缺 {sorted(str(p) for p in on_disk - listed)}"
    )


def test_record_status_is_valid():
    for path in record_files():
        info = parse_record(path)
        assert info["status"] in STATES, f"{path.name} 的状态非法: {info['status']}"


def test_merged_record_has_a_matching_commit():
    for path in record_files():
        info = parse_record(path)
        if info["status"] != "已合入":
            continue
        slug = path.stem
        shas = merged_commit_for(slug)
        assert shas, f"{slug} 标了已合入，但没有 docs(review): {slug} 提交"
        touched = False
        for sha in shas:
            names = git("show", "--name-only", "--pretty=format:", sha)
            if info["source"] in names:
                touched = True
        assert touched, f"{slug} 的合入提交没有改动 {info['source']}"


def test_merged_record_has_no_open_facts():
    for path in record_files():
        info = parse_record(path)
        if info["status"] != "已合入":
            continue
        text = path.read_text(encoding="utf-8")
        section = text.split("## 事实待核", 1)[1].split("##", 1)[0]
        open_items = [line for line in section.split("\n")
                      if line.strip().startswith("- ")
                      and not line.strip().startswith("- [x]")
                      and not line.strip().startswith("- [不适用]")]
        assert not open_items, f"{path.name} 仍留着未核实的待核事实: {open_items}"


def test_docs_tree_has_no_review_leakage():
    """docs/ 会被发布成站点文章，审校记录绝不能漏进去。"""
    offenders = [p for p in DOCS_ROOT.rglob("*")
                 if p.is_dir() and p.name in ("review", "reviews")]
    assert not offenders, f"docs/ 下出现了审校目录: {offenders}"
    records = [p for p in DOCS_ROOT.rglob("*.md")
               if p.name.startswith("审校") or "审校记录" in p.name]
    assert not records, f"docs/ 下出现了审校记录: {records}"
```

- [ ] **Step 2: 跑测试确认它红**

Run: `python3 -m pytest tests/test_review_records.py -q`

Expected: PASS（当前没有记录，断言空集成立）——**这不是想要的结果**。
契约测试在没有任何记录时是空转的，所以这个 task 必须同时建立第一条记录，
否则测试证明不了任何事（见 Step 3）。

- [ ] **Step 3: 建立第一条试点记录与索引**

先读原文：`docs/database/postgresql-mvcc/index.md`，再跑检查器：

```bash
python3 tools/review-check.py docs/database/postgresql-mvcc/index.md
```

按 README 模板创建 `review/database/postgresql-mvcc.md`：

```markdown
# 审校：PostgreSQL MVCC：一条数据是如何拥有"分身术"的

- 原文：`docs/database/postgresql-mvcc/index.md`
- 范围：全文
- 目标读者：用过 PostgreSQL、想知道并发下「读到的是哪一版数据」的开发者
- 一句话定位：<从原文开头 3 段提炼，读者读完能回答「快照是怎么来的」
- 核心判断：<一句话，可证伪>
- 审校状态：建议中

## 优先修改

1. 位置：<章节 / 行号>
   - 问题：<规则编号 + 一句话描述>
   - 建议：<可直接采用的改法>
   - 原因：<为什么这么改>

## 事实待核

- <待核实的事实；没有就写「无」>

## 可补的技术证据或产物

- 机制 / 源码入口：
- 实验或观测：
- 工程取舍：
- 结尾清单或下一篇链接：

## 已确认的改动

- <已按确认落地的改动；阶段 A 没有就写「无」>
```

**填写要求**（不是占位，是硬要求）：
- 「位置」必须是**具体章节名或行号**，不能写「全文」；
- 「问题」必须带**规则编号**（AIF-01 / DEP-03 / STR-02…）或明确的文字描述；
- 「建议」必须是可以直接粘进正文的句子或段落；
- 「原因」必须说明取舍，不能写「更通顺」；
- 「事实待核」没有就写「无」，**不许编造事实来填坑**。

创建 `review/INDEX.md`：

```markdown
# 审校进度索引

首轮范围：`docs/` 数据库内核四支柱（`database` / `db` / `pgsql` / `cluster`，282 篇）。
规范见 [`README.md`](README.md)，落地机制见
[`specs/2026-11-13-content-review-design.md`](specs/2026-11-13-content-review-design.md)。

| 记录 | 支柱 | 状态 | 信号 | 待确认 | 批次 |
| --- | --- | --- | --- | --- | --- |
| [postgresql-mvcc](database/postgresql-mvcc.md) | database | 建议中 | 0 | 0 | 试点 |
```

（「信号」「待确认」两列填检查器给出的 warn 数与未销掉的待核事实数。）

- [ ] **Step 4: 跑测试确认它绿**

Run: `python3 -m pytest tests/ -q`

Expected: PASS。

- [ ] **Step 5: 提交**

write 工具写 `/tmp/review-task5-commit.txt`：

```
feat(review): 审校记录契约与进度索引

把 review/README.md 的流程钉成机器可校验的契约：记录必须落在受审支柱下、
小节齐全、原文存在、索引与记录双向一致、状态合法、已合入必须有对应提交且
该提交确实改了正文、已合入不能留着未销的待核事实。

外加一条防泄露守卫：docs/ 下不得出现审校记录——docs/ 会被 sync-hexo.py
发布成站点文章，内部流程漏进去就变成线上页面。

附第一篇试点记录（database/postgresql-mvcc）。
```

然后：

```bash
git add tests/test_review_records.py review/INDEX.md review/database/postgresql-mvcc.md
git commit -F /tmp/review-task5-commit.txt
```

---

### Task 6: 剩余 4 篇试点记录

**Files:**
- Create: `review/db/<slug>.md`
- Create: `review/pgsql/<slug>.md`
- Create: `review/cluster/<slug>.md`
- Create: `review/database/<logical-replication-slug>.md`
- Modify: `review/INDEX.md`

**Interfaces:**
- Consumes: Task 5 的记录格式与 `review/INDEX.md` 表格；Task 1~4 的检查器
- Produces: 4 篇审校记录 + 索引补行

- [ ] **Step 1: 选文章（覆盖四个支柱 + 一个系列）**

从下列候选里各选一篇（先跑 `wc -c` 挑体量适中的，审校记录要写到具体行，
太长的一篇顶一篇半）：

| 支柱 | 候选 |
|---|---|
| database | `docs/database/postgresql-row-lock-deep-dive/index.md` |
| db | `docs/db/postgresql/` 下任选一篇非 index 的文章 |
| pgsql | `docs/pgsql/` 下任选一篇 |
| cluster | `docs/cluster/raft/` 或 `docs/cluster/DCF/` 下任选一篇 |
| 系列 | `docs/database/postgresql-logical-replication-*/index.md` 任选一篇 |

```bash
for f in docs/database/postgresql-row-lock-deep-dive/index.md \
         docs/db/postgresql/*.md docs/pgsql/*.md \
         docs/cluster/raft/*.md docs/cluster/DCF/*.md \
         docs/database/postgresql-logical-replication-*/index.md; do
  [ -f "$f" ] && printf "%8d %s\n" "$(wc -c < "$f")" "$f"
done | sort -n | head -30
```

- [ ] **Step 2: 逐篇跑检查器并写记录**

每篇四步：

```bash
python3 tools/review-check.py <原文路径>          # 看信号
```

然后按 **Task 5 Step 3 的模板**写 `review/<支柱>/<slug>.md`，要求：

1. 原文路径写对，slug 与文件名一致；
2. 「优先修改」至少一条**带行号**的建议；信号为空时也要写一条人工发现的
   （位置 / 问题 / 建议 / 原因四栏齐全）；
3. 「事实待核」里出现的事实**必须真去核对**（源码路径、命令、版本），
   核不了就明写「待核实」，**不许改写补全**（README 原则 1）；
4. 「可补的技术证据或产物」要具体到机制/源码入口/实验方法，不是「可以再补充」；
5. 状态一律 `建议中`——阶段 A 不碰 `docs/`。

**先判是不是「文章」**：四支柱里混着交付计划、配置流程、安装步骤、源码编译笔记
这类工作文档（`db/logical_decode/逻辑复制支持DDL开发交付计划`、
`db/mysql/macos安装mysql` 等）。它们是项目流水账不是技术文章，审校目标
「读者读完能学会什么」不成立——这类跳过，在 INDEX 里标「非文章，跳过」，
不产出审校记录。判据：文章有「问题→机制→证据→取舍」的结构。

**每篇一个提交**（写完一篇立刻提交，不要攒着）：

```bash
git add review/<支柱>/<slug>.md review/INDEX.md
git commit -F /tmp/review-<slug>-commit.txt
```

commit message 格式固定为 `docs(review): 记录 <slug>`，正文写这条记录发现了什么。

- [ ] **Step 3: 更新索引**

每写完一篇，在 `review/INDEX.md` 表格里加一行：

```
| [postgresql-row-lock-deep-dive](database/postgresql-row-lock-deep-dive.md) | database | 建议中 | 2 | 1 | 试点 |
```

- [ ] **Step 4: 跑全量测试**

Run: `python3 -m pytest tests/ -q`

Expected: PASS。索引与记录必须双向一致——少加一行或多加一行都会红。

- [ ] **Step 5: 确认 docs/ 一个字都没动**

```bash
git diff --stat f7cf035..HEAD -- docs/
```

Expected: 空输出。阶段 A 不允许碰 `docs/`。

- [ ] **Step 6: 最终提交**

若前面每篇已各自提交，这一步只需确认工作树干净：

```bash
git status --short
```

Expected: 空输出。

---

## 验收标准

- `python3 -m pytest tests/ -q` 全绿；
- `python3 tools/review-check.py docs/database docs/db docs/pgsql docs/cluster --json` 能跑完 282 篇；
- 5 篇试点记录齐备，索引与之一致，状态机合法；
- `git diff --stat <spec 提交>..HEAD -- docs/` 为空（阶段 A 不碰正文）；
- `docs/` 下无任何审校内容（契约测试守着）。

## 本计划不覆盖的部分

- **阶段 B（正文合入）**：需要你先确认审校建议。确认后按篇执行——改 `docs/` 里记录点名的
  位置 → 状态改 `已合入` → `git commit -m "docs(review): <slug>"` → 契约测试第 5 条
  会用 `git log` 反查这个提交确实动了正文。
- **批次 4（282 篇放量）**：在 5 篇试点验收后再排，届时按系列分批、每批 10~15 篇，
  另起计划。

---

## 执行结果（2026-11-13）

计划已全部执行完毕。实际提交序列：

| 提交 | 内容 |
| --- | --- |
| `f7cf035` | 设计文档（spec） |
| `a8949b0` | 实现计划（本文） |
| `087d1e8` | Task 1 检查器骨架 |
| `d3be06b` | Task 2 AI 味信号 |
| `cd2de08` | Task 3 技术深度五要素 |
| `cfa14fa` | Task 4 结构与元信息 |
| `dd850cf` | Task 5 记录契约 + 索引 + 第 1 篇试点 |
| `7398a35` | 试点：logical-replication-worker-model |
| `987dae7` | 试点：06-heap-and-mvcc |
| `9e68b65` | 试点：checkpoint机制浅析 |
| `6986919` | 试点：分布式一致性协议 |
| `cc38b8c` | 按真实文章校准检查器三处判据 |

**每个提交都在独立干净检出上跑通全部测试**（用 `git worktree` 逐个验证过）。

执行中相对计划的三处偏离，都有实测依据：

1. **AIF-05 收紧**：原判据在 282 篇里误报 81 篇——「事务 XID=200 执行：」与
   「事务 XID=300 执行：」相似度 0.93，但那是并列结构不是冗余。加上中文长度
   门槛后降到 14 篇。
2. **DEP-04/05 词表放宽**：只认「相比/替代」会漏掉用「优点/缺点」讲取舍的文章。
3. **STR-02/03 放宽到引用块与「结语/结论」**：定位句常写在 `> 目标：…` 里，
   「结语 + 结论表」也是货真价实的产物。

另外发现一个**范围问题**并写进了 spec：四支柱里混着交付计划、配置流程、安装
步骤这类工作文档，它们不是面向读者的技术文章，不按「技术深度五要素」审。

尚未执行：**阶段 B（正文合入）**与**批次 4（282 篇放量）**。
