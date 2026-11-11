"""选题库：结构、口径与出处检查。

`选题库.md` 是选题这件事的**唯一事实来源**。这里把它的可机检部分做成检查：

1. **结构完整**——每期必备字段齐全，关联文档 / 口播骨架 / 数字与出处三段都在。
2. **文档真实存在**——关联文档是入库的路径，被删了就该红。
3. **口径不跑偏**——标题与主钩子不命中《人格规范》的禁词表（复用 `persona` 的词表）。
4. **落在能力域内**——整期不能在能力边界外（复用 `persona.detect_domains`）。
5. **句数对得上**——口播骨架必须 10 句，与契约的段落、字幕表一一对应。
6. **数字有出处**——「数字与出处」表非空，实测类数字必须带作者本人归因。

**为什么选题要机检**：选题库是入库的事实，会一直被人手改。
口径跑偏、关联文档被删、实测数字丢了归因，这三件事不查一遍就会漏到片子里。

用法：
    python -m pyv.cli topics check
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pyv import persona
from pyv.timeline import display_width

# aiv/ 是 pipeline/ 的上一级：pyv/topics.py → pyv → pipeline → aiv
AIV_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = AIV_ROOT.parent
TOPICS_PATH = AIV_ROOT / "选题库.md"

RULE_IDS = (
    "topics.structure",
    "topics.doc-exists",
    "topics.no-hype",
    "topics.domain",
    "topics.sentence-count",
    "topics.word-count",
    "topics.sentence-width",
    "topics.evidence",
)

ERROR = "error"
WARNING = "warning"

# 每期必备的字段（字段表的左列）
REQUIRED_FIELDS = (
    "id", "标题", "主钩子", "主线", "能力域", "状态", "适配理由",
)

# 口播骨架的句数。与契约的段落划分、字幕表的行数一一对应。
SENTENCE_COUNT = 10
# 口播骨架的总字数区间（口径：各句原始长度求和，含标点与空格）。
# 本期实测 255 字，33.156 秒。
WORD_COUNT_RANGE = (230, 280)
# 单句显示宽度的上限（中文 1、拉丁 0.5）。与《人格规范》§7 同源，这里是倾向类。
MAX_SENTENCE_WIDTH = 40

# 实测类数字必须带的归因词
_ATTRIBUTION_WORDS = ("作者本人", "我自己", "我本人", "作者实测")


@dataclass(frozen=True)
class Finding:
    """一条检查结果。"""

    rule_id: str
    level: str
    message: str
    target: str = ""

    def __str__(self) -> str:
        where = f"[{self.target}] " if self.target else ""
        return f"{where}{self.rule_id} {self.message}"


@dataclass
class Episode:
    """一期选题。"""

    heading: str
    fields: dict = field(default_factory=dict)
    docs: list = field(default_factory=list)        # [(路径, 取什么)]
    sentences: list = field(default_factory=list)
    evidence: list = field(default_factory=list)    # [(陈述, 出处, 口径)]
    has_docs_section: bool = False
    has_script_section: bool = False
    has_evidence_section: bool = False

    @property
    def id(self) -> str:
        return self.fields.get("id", "")

    @property
    def title(self) -> str:
        return self.fields.get("标题", "")

    @property
    def hook(self) -> str:
        return self.fields.get("主钩子", "")

    @property
    def domain(self) -> str:
        return self.fields.get("能力域", "")

    def text(self) -> str:
        """这一期的全部实质内容，供域检测与禁词扫描用。"""
        parts = [self.title, self.hook, self.fields.get("适配理由", "")]
        parts.extend(self.sentences)
        parts.extend(path for path, _ in self.docs)
        parts.extend(statement for statement, _, _ in self.evidence)
        return "\n".join(part for part in parts if part)


# ---------------------------------------------------------------- 解析


def _is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(set(c) <= set("-: ") for c in cells)


def _parse_table(lines: list[str]) -> list[list[str]]:
    """取第一张表格，返回单元格行（跳过分隔行）。"""
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            if rows:
                break
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if _is_separator(cells):
            continue
        rows.append(cells)
    return rows


def _after_marker(lines: list[str], marker: str) -> list[str] | None:
    """找以 marker 开头的行，返回它之后的全部行。"""
    for index, line in enumerate(lines):
        if line.strip().startswith(marker):
            return lines[index + 1:]
    return None


def _first_code_block(lines: list[str]) -> list[str]:
    """取第一个代码块里的非空行。"""
    out: list[str] = []
    inside = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if inside:
                break
            inside = True
            continue
        if inside and stripped:
            out.append(stripped)
    return out


def _split_sections(text: str) -> list[tuple[str, list[str]]]:
    """按二级标题切段，返回 (标题, 段落行)。"""
    sections: list[tuple[str, list[str]]] = []
    heading = ""
    body: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if heading or body:
                sections.append((heading, body))
            heading = line[3:].strip()
            body = []
        else:
            body.append(line)
    if heading or body:
        sections.append((heading, body))
    return sections


def parse_topics(path: str | Path = TOPICS_PATH) -> list[Episode]:
    """从选题库里解析出各期。"""
    text = Path(path).read_text(encoding="utf-8")
    episodes: list[Episode] = []
    for heading, body in _split_sections(text):
        field_table = None
        for candidate in _all_tables(body):
            if candidate and candidate[0] and candidate[0][0] == "字段":
                field_table = candidate
                break
        if field_table is None:
            continue
        fields = {}
        for row in field_table[1:]:
            if len(row) >= 2 and row[0]:
                fields[row[0]] = row[1]
        episode = Episode(heading=heading, fields=fields)

        docs_body = _after_marker(body, "**关联文档**")
        if docs_body is not None:
            episode.has_docs_section = True
            table = _parse_table(docs_body)
            episode.docs = [(row[0].strip("` "), row[1] if len(row) > 1 else "")
                            for row in table[1:] if row and row[0]]

        script_body = _after_marker(body, "**口播骨架**")
        if script_body is not None:
            episode.has_script_section = True
            episode.sentences = _first_code_block(script_body)

        evidence_body = _after_marker(body, "**数字与出处**")
        if evidence_body is not None:
            episode.has_evidence_section = True
            table = _parse_table(evidence_body)
            episode.evidence = [
                (row[0], row[1] if len(row) > 1 else "",
                 row[2] if len(row) > 2 else "")
                for row in table[1:] if row and row[0]
            ]
        episodes.append(episode)
    return episodes


def _all_tables(body: list[str]) -> list[list[list[str]]]:
    """把段落里的所有表格拆出来。"""
    tables: list[list[list[str]]] = []
    current: list[str] = []
    for line in body + [""]:
        if line.strip().startswith("|"):
            current.append(line)
            continue
        if current:
            tables.append(_parse_table(current))
            current = []
    return tables


# ---------------------------------------------------------------- 检查


def check_topics(episodes: list[Episode]) -> list[Finding]:
    """把选题库过一遍，返回所有问题。"""
    findings: list[Finding] = []

    def add(rule_id: str, level: str, message: str, target: str = "") -> None:
        findings.append(Finding(rule_id, level, message, target))

    if not episodes:
        add("topics.structure", ERROR, "选题库里没解析出任何一期")
        return findings

    seen: set[str] = set()
    for episode in episodes:
        target = episode.id or episode.heading

        # ---- 结构
        missing = [name for name in REQUIRED_FIELDS
                   if not episode.fields.get(name, "").strip()]
        if missing:
            add("topics.structure", ERROR, f"缺字段：{'、'.join(missing)}", target)
        for name, present in (
            ("关联文档", episode.has_docs_section),
            ("口播骨架", episode.has_script_section),
            ("数字与出处", episode.has_evidence_section),
        ):
            if not present:
                add("topics.structure", ERROR, f"缺「{name}」小节", target)
        if episode.id in seen:
            add("topics.structure", ERROR, f"id 重复：{episode.id}", target)
        seen.add(episode.id)

        # ---- 关联文档真实存在
        for path, _ in episode.docs:
            if not path:
                add("topics.doc-exists", ERROR, "关联文档路径为空", target)
                continue
            if not (REPO_ROOT / path).is_file():
                add("topics.doc-exists", ERROR,
                    f"关联文档不存在：{path}", target)

        # ---- 口径：不命中禁词表
        for word in persona.HYPE_WORDS:
            if word in episode.title or word in episode.hook:
                add("topics.no-hype", ERROR, f"标题或钩子命中营销腔词「{word}」", target)
        for word in persona.BRAND_SELF_WORDS:
            if word in episode.title or word in episode.hook:
                add("topics.no-hype", ERROR,
                    f"标题或钩子命中机构自称词「{word}」", target)
        for word in persona.ABSOLUTE_WORDS:
            if word in episode.title or word in episode.hook:
                add("topics.no-hype", ERROR,
                    f"标题或钩子命中绝对化断言「{word}」", target)

        # ---- 能力域
        if episode.domain and episode.domain not in persona.CAPABILITY_KEYWORDS:
            add("topics.domain", ERROR,
                f"能力域「{episode.domain}」不在《人格规范》§3.1 的域名表里", target)
        domains = persona.detect_domains([episode.text()])
        if not domains:
            add("topics.domain", ERROR,
                "整期文本一个能力域都没命中——选题跑到能力边界外了", target)
        zero_words = [w for words in persona.ZERO_COVERAGE.values() for w in words]
        for word in zero_words:
            if word.lower() in episode.text().lower():
                add("topics.domain", ERROR,
                    f"命中零覆盖方向「{word}」", target)

        # ---- 句数
        if episode.sentences and len(episode.sentences) != SENTENCE_COUNT:
            add("topics.sentence-count", ERROR,
                f"口播骨架 {len(episode.sentences)} 句，应为 {SENTENCE_COUNT} 句", target)

        # ---- 字数
        if episode.sentences:
            total = sum(len(sentence) for sentence in episode.sentences)
            low, high = WORD_COUNT_RANGE
            if not low <= total <= high:
                add("topics.word-count", ERROR,
                    f"口播骨架 {total} 字，应在 {low}~{high} 字之间", target)

        # ---- 单句宽度
        for index, sentence in enumerate(episode.sentences, 1):
            width = display_width(sentence)
            if width > MAX_SENTENCE_WIDTH:
                add("topics.sentence-width", WARNING,
                    f"第 {index} 句宽 {width}，超过 {MAX_SENTENCE_WIDTH}——念不顺",
                    target)

        # ---- 数字有出处
        if episode.has_evidence_section and not episode.evidence:
            add("topics.evidence", ERROR, "「数字与出处」表是空的", target)
        for statement, source, _ in episode.evidence:
            if re.search(r"实测|压测", source) and not any(
                    word in source for word in _ATTRIBUTION_WORDS):
                add("topics.evidence", ERROR,
                    f"「{statement}」的出处是实测/压测，但没写作者本人归因", target)

    return findings
