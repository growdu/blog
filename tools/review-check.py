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
LINK_RE = re.compile(r"(?<!\!)\[[^\]]*\]\([^)]*\)")


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
    """Split markdown source lines into typed blocks."""
    blocks: list[Block] = []
    i = 0
    total = len(lines)
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
            "links": len(LINK_RE.findall(doc.text)),
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
