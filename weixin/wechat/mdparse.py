"""Markdown -> block AST.

Deliberately small: it covers exactly the constructs the blog corpus uses
(headings, paragraphs, fenced code, tables, lists, task lists, quotes,
thematic breaks, raw HTML, inline code, emphasis, links, images) and
nothing else.  Footnotes and LaTeX do not occur in the corpus, so they
are not implemented.

Pure module: no file access, no network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = [
    "Text", "Bold", "Italic", "InlineCode", "Link", "Image",
    "Heading", "Paragraph", "CodeBlock", "Table", "ListItem", "ListBlock",
    "Quote", "ThematicBreak", "HtmlBlock",
    "parse", "parse_inline",
]


@dataclass(frozen=True)
class Text:
    value: str


@dataclass(frozen=True)
class Bold:
    children: list = field(default_factory=list)


@dataclass(frozen=True)
class Italic:
    children: list = field(default_factory=list)


@dataclass(frozen=True)
class InlineCode:
    value: str


@dataclass(frozen=True)
class Link:
    target: str
    children: list = field(default_factory=list)


@dataclass(frozen=True)
class Image:
    alt: str
    target: str


@dataclass(frozen=True)
class Heading:
    level: int
    children: list = field(default_factory=list)


@dataclass(frozen=True)
class Paragraph:
    children: list = field(default_factory=list)


@dataclass(frozen=True)
class CodeBlock:
    lang: str
    code: str


@dataclass(frozen=True)
class Table:
    header: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    align: list = field(default_factory=list)


@dataclass(frozen=True)
class ListItem:
    blocks: list = field(default_factory=list)
    checked: bool | None = None


@dataclass(frozen=True)
class ListBlock:
    ordered: bool
    items: list = field(default_factory=list)


@dataclass(frozen=True)
class Quote:
    blocks: list = field(default_factory=list)


@dataclass(frozen=True)
class ThematicBreak:
    pass


@dataclass(frozen=True)
class HtmlBlock:
    html: str


_FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([A-Za-z0-9_+-]*)\s*$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_HR_RE = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
_UL_RE = re.compile(r"^(?P<indent>\s*)(?P<marker>[-*+])(?P<gap>\s+)(?P<content>.*)$")
_OL_RE = re.compile(r"^(?P<indent>\s*)(?P<marker>\d+\.)(?P<gap>\s+)(?P<content>.*)$")
_TASK_RE = re.compile(r"^\[([ xX])\]\s+(.*)$")
_QUOTE_RE = re.compile(r"^\s*>\s?(.*)$")
_HTML_RE = re.compile(
    r"^</?(?:div|table|tbody|thead|tr|td|th|img|details|summary|br|p|span|section|"
    r"video|iframe|ul|ol|li|h[1-6]|b|i|strong|em|code|pre|blockquote|figure|"
    r"figcaption|hr|a|input|label|form|figure)\b",
    re.I,
)
_HTML_COMMENT_RE = re.compile(r"^<!--")

_INLINE_RE = re.compile(
    r"(?P<image>!\[[^\]]*\]\([^)\s]*(?:\s+\"[^\"]*\")?\))"
    r"|(?P<link>\[[^\]]*\]\([^)\s]*(?:\s+\"[^\"]*\")?\))"
    r"|(?P<code>`[^`]+`)"
    r"|(?P<bold>\*\*[^*]+\*\*)"
    r"|(?P<strike>~~[^~]+~~)"
    r"|(?P<italic>(?<!\*)\*[^*\n]+\*(?!\*))"
)
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def parse_inline(text: str) -> list:
    """Parse inline markup into a flat list of inline nodes.

    The single regex below matches every inline construct in one pass.
    Doing it in one pass means inline code is recognised before emphasis,
    so markup inside backticks is never re-interpreted.
    """
    tokens = []
    position = 0
    for match in _INLINE_RE.finditer(text):
        if match.start() > position:
            tokens.append(Text(text[position:match.start()]))
        if match.group("image"):
            image = _IMAGE_RE.match(match.group("image"))
            tokens.append(Image(image.group(1), image.group(2)))
        elif match.group("link"):
            link = _LINK_RE.match(match.group("link"))
            tokens.append(Link(link.group(2), parse_inline(link.group(1))))
        elif match.group("code"):
            tokens.append(InlineCode(match.group("code")[1:-1]))
        elif match.group("bold"):
            tokens.append(Bold(parse_inline(match.group("bold")[2:-2])))
        elif match.group("strike"):
            tokens.append(Text(match.group("strike")[2:-2]))
        else:
            tokens.append(Italic(parse_inline(match.group("italic")[1:-1])))
        position = match.end()
    if position < len(text):
        tokens.append(Text(text[position:]))
    return [token for token in tokens if not (isinstance(token, Text) and not token.value)]


def _split_table_row(line: str) -> list:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    cells = []
    current = []
    escaped = False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            current.append(char)
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    cells.append("".join(current).strip())
    return cells


def _alignment(cells: list) -> list:
    aligns = []
    for cell in cells:
        left, right = cell.startswith(":"), cell.endswith(":")
        if left and right:
            aligns.append("center")
        elif right:
            aligns.append("right")
        elif left:
            aligns.append("left")
        else:
            aligns.append("")
    return aligns


def _is_table_separator(line: str) -> bool:
    cells = _split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{1,}:?", cell.strip()) for cell in cells)


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def _is_block_start(line: str) -> bool:
    """True when the line begins a block that cannot continue a paragraph."""
    stripped = line.strip()
    if not stripped:
        return True
    if _FENCE_RE.match(line) or _HEADING_RE.match(stripped) or _HR_RE.match(line):
        return True
    if _UL_RE.match(line) or _OL_RE.match(line) or _QUOTE_RE.match(line):
        return True
    if _HTML_RE.match(stripped) or _HTML_COMMENT_RE.match(stripped):
        return True
    return False


def _parse_list(lines: list, index: int, ordered: bool) -> tuple:
    """Parse a list starting at ``lines[index]``.

    Returns ``(items, next_index)``.  An item swallows every following
    line that is indented deeper than the marker, which is how nested
    lists become part of the parent item.
    """
    items = []
    total = len(lines)

    while index < total:
        line = lines[index]
        if not line.strip():
            lookahead = index + 1
            while lookahead < total and not lines[lookahead].strip():
                lookahead += 1
            if lookahead < total and _indent_of(lines[lookahead]) > _indent_of(line):
                index = lookahead
                continue
            break

        match = _OL_RE.match(line) if ordered else _UL_RE.match(line)
        other = _UL_RE.match(line) if ordered else _OL_RE.match(line)
        if other and not match:
            break
        if not match:
            break

        indent = len(match.group("indent"))
        marker_len = len(match.group("indent")) + len(match.group("marker")) + len(match.group("gap"))
        content_indent = indent + marker_len
        content = match.group("content")

        item_lines = [content]
        index += 1
        while index < total:
            candidate = lines[index]
            if not candidate.strip():
                break
            candidate_indent = _indent_of(candidate)
            if candidate_indent < content_indent:
                break
            item_lines.append(candidate[content_indent:])
            index += 1

        checked = None
        task = _TASK_RE.match(item_lines[0])
        if task:
            checked = task.group(1).lower() == "x"
            item_lines[0] = task.group(2)
        items.append(ListItem(blocks=_parse_blocks(item_lines), checked=checked))

    return items, index


def _parse_blocks(lines: list) -> list:
    blocks = []
    index = 0
    total = len(lines)

    while index < total:
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        fence = _FENCE_RE.match(line)
        if fence:
            marker = fence.group(2)
            body = []
            index += 1
            while index < total:
                closing = _FENCE_RE.match(lines[index])
                if (closing and closing.group(2)[0] == marker[0]
                        and len(closing.group(2)) >= len(marker)
                        and not closing.group(3)):
                    index += 1
                    break
                body.append(lines[index])
                index += 1
            blocks.append(CodeBlock(lang=fence.group(3), code="\n".join(body)))
            continue

        if _HR_RE.match(line):
            blocks.append(ThematicBreak())
            index += 1
            continue

        heading = _HEADING_RE.match(stripped)
        if heading:
            blocks.append(Heading(level=len(heading.group(1)),
                                  children=parse_inline(heading.group(2).strip())))
            index += 1
            continue

        quote = _QUOTE_RE.match(line)
        if quote:
            inner = []
            while index < total:
                match = _QUOTE_RE.match(lines[index])
                if not match:
                    break
                inner.append(match.group(1))
                index += 1
            blocks.append(Quote(blocks=_parse_blocks(inner)))
            continue

        if (index + 1 < total and "|" in line
                and _is_table_separator(lines[index + 1])):
            header = _split_table_row(line)
            align = _alignment(_split_table_row(lines[index + 1]))
            index += 2
            rows = []
            while index < total and lines[index].strip().startswith("|"):
                rows.append([parse_inline(cell) for cell in _split_table_row(lines[index])])
                index += 1
            blocks.append(Table(header=[parse_inline(cell) for cell in header],
                                rows=rows, align=align))
            continue

        if _UL_RE.match(line) or _OL_RE.match(line):
            ordered = _OL_RE.match(line) is not None
            items, index = _parse_list(lines, index, ordered)
            blocks.append(ListBlock(ordered=ordered, items=items))
            continue

        if _HTML_RE.match(stripped) or _HTML_COMMENT_RE.match(stripped):
            html = []
            while index < total and lines[index].strip():
                html.append(lines[index])
                index += 1
            blocks.append(HtmlBlock(html="\n".join(html)))
            continue

        paragraph = []
        while index < total:
            candidate = lines[index]
            if not candidate.strip():
                break
            if paragraph and _is_block_start(candidate):
                break
            paragraph.append(candidate.strip())
            index += 1
        if paragraph:
            blocks.append(Paragraph(children=parse_inline(" ".join(paragraph))))

    return blocks


def parse(markdown: str) -> list:
    """Parse a markdown document into a list of block nodes."""
    return _parse_blocks(markdown.replace("\r\n", "\n").split("\n"))
