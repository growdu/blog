"""Split an article that is too long for WeChat into several parts.

WeChat counts the rendered body, not the markdown, and the limit is
20000 characters per draft.  An article that does not fit therefore
has to become several drafts -- and the split has to land where a
reader can follow it: a heading first, a paragraph next, a table row
or a line of code last.

The pieces are also numbered and connected, so the parts read as one
article split into instalments rather than as unrelated posts.
"""

from __future__ import annotations

from .digest import part_digest
from .mdparse import (Bold, CodeBlock, Heading, Image, InlineCode, Italic, Link,
                      ListBlock, Paragraph, Quote, Table, Text)
from .render import links_html, links_items_html

__all__ = [
    "LINK_WRAPPER",
    "RESERVE",
    "chinese_number",
    "framing_reserve",
    "part_digest",
    "part_title",
    "plan_parts",
    "split_blocks",
    "transition_head_html",
    "transition_tail_html",
]

_CN_DIGITS = "零一二三四五六七八九"

# The reference-links wrapper is paid once per part.  Its items are
# counted apart from it, so the wrapper itself has a fixed length.
LINK_WRAPPER = len(links_html([("", "")])) - len(links_items_html([("", "")]))

# Every part pays once for its own framing: the reference-links
# wrapper, the category tag and the two transition lines.  This is the
# floor of that -- the wrapper plus a margin for the odd character the
# estimate and the render may disagree about.  :func:`framing_reserve`
# adds the article-specific part on top.
RESERVE = LINK_WRAPPER + 50


def chinese_number(number: int) -> str:
    """1 -> 一, 2 -> 二, 10 -> 十, 11 -> 十一, 20 -> 二十, 25 -> 二十五."""
    if number < 0 or number > 99:
        return str(number)
    if number < 10:
        return _CN_DIGITS[number]
    tens, ones = divmod(number, 10)
    head = "十" if tens == 1 else _CN_DIGITS[tens] + "十"
    if ones == 0:
        return head
    return head + _CN_DIGITS[ones]


def part_title(title: str, index: int) -> str:
    """The draft title of one part: ``标题（一）``."""
    return "{}（{}）".format(title, chinese_number(index))


def _inline_text(nodes) -> str:
    """The plain text of an inline node list."""
    out = []
    for node in nodes:
        if isinstance(node, Text):
            out.append(node.value)
        elif isinstance(node, InlineCode):
            out.append(node.value)
        elif isinstance(node, Image):
            out.append(node.alt)
        elif isinstance(node, (Bold, Italic, Link)):
            out.append(_inline_text(node.children))
    return "".join(out)


_TRANSITION_STYLE = ("margin:0 0 16px;padding:10px 14px;"
                     "border-left:4px solid #3d7ea6;background:#f6f8fa;"
                     "color:#555;font-size:14px;")
_TAIL_STYLE = ("margin:20px 0 0;padding-top:12px;"
               "border-top:1px solid #e5e5e5;color:#888;font-size:13px;")


def transition_head_html(title: str, index: int, total: int) -> str:
    """The line that opens a part and tells the reader where they are.

    An article that is not split gets no transition at all: there is
    nothing to connect.
    """
    if total <= 1:
        return ""
    if index <= 1:
        text = "全文共 {} 部分，这是第 {} 部分。".format(total, index)
    else:
        text = "接上文《{}》。全文共 {} 部分，这是第 {} 部分。".format(
            part_title(title, index - 1), total, index)
    return '<p style="{}">{}</p>'.format(_TRANSITION_STYLE, text)


def transition_tail_html(title: str, index: int, total: int) -> str:
    """The line that closes a part and points at the next one."""
    if total <= 1:
        return ""
    if index < total:
        text = "（未完待续，下一篇：{}）".format(part_title(title, index + 1))
    else:
        text = "（全文完，共 {} 部分）".format(total)
    return '<p style="{}">{}</p>'.format(_TAIL_STYLE, text)


def framing_reserve(title: str, tag_html: str = "") -> int:
    """The characters one part spends on its own framing.

    The transition lines carry the article title and the part numbers,
    and the category tag carries the categories, so the length depends
    on the article.  The numbers are taken at their widest (99 of 999)
    -- more than any real article needs -- so the reserve covers the
    framing of every part and not just of the shortest one.

    Getting this wrong is not a rounding error: a reserve that is a
    few dozen characters short does not make a part shorter, it makes
    the whole article unpublishable.
    """
    head = transition_head_html(title, 99, 999)
    tail = transition_tail_html(title, 99, 999)
    return RESERVE + len(tag_html) + len(head) + len(tail)


# --- where a split may happen -------------------------------------------


def _groups_at_heading(blocks: list, level: int) -> list:
    """Group blocks at the headings of one level.

    Only the headings of exactly that level start a group, so a
    sub-heading stays with the section it belongs to and the chain of
    headings is never broken.
    """
    groups = []
    current = []
    for block in blocks:
        if isinstance(block, Heading) and block.level == level and current:
            groups.append(current)
            current = []
        current.append(block)
    if current:
        groups.append(current)
    return groups


def _groups_at_block(blocks: list) -> list:
    """One group per block."""
    return [[block] for block in blocks]


def _split_table(table: Table) -> list:
    """Cut a table between rows; every piece keeps the header."""
    if len(table.rows) <= 1:
        return [[table]]
    return [[Table(header=table.header, rows=[row], align=table.align)]
            for row in table.rows]


def _split_code(block: CodeBlock) -> list:
    """Cut a code block between lines."""
    lines = block.code.split("\n")
    if len(lines) <= 1:
        return [[block]]
    chunks = []
    current = []
    size = 0
    for line in lines:
        if current and size + len(line) > 3000:
            chunks.append(current)
            current = []
            size = 0
        current.append(line)
        size += len(line) + 1
    if current:
        chunks.append(current)
    return [[CodeBlock(lang=block.lang, code="\n".join(chunk))] for chunk in chunks]


def _split_list(block: ListBlock) -> list:
    """Cut a list between items."""
    if len(block.items) <= 1:
        return [[block]]
    return [[ListBlock(ordered=block.ordered, items=[item])] for item in block.items]


def _groups_inside(blocks: list) -> list:
    """Cut inside the blocks themselves -- the last resort."""
    groups = []
    for block in blocks:
        if isinstance(block, Table):
            groups.extend(_split_table(block))
        elif isinstance(block, CodeBlock):
            groups.extend(_split_code(block))
        elif isinstance(block, ListBlock):
            groups.extend(_split_list(block))
        elif isinstance(block, Quote):
            groups.extend([[child] for child in block.blocks])
        else:
            groups.append([block])
    return groups


# Coarse to fine: a heading boundary is the nicest place to break, a
# line of code the ugliest.  Each step splits at one heading level, so
# a section is broken up before its own sub-sections are.
_LADDER = (
    lambda blocks: _groups_at_heading(blocks, 2),
    lambda blocks: _groups_at_heading(blocks, 3),
    lambda blocks: _groups_at_heading(blocks, 4),
    lambda blocks: _groups_at_heading(blocks, 5),
    lambda blocks: _groups_at_heading(blocks, 6),
    _groups_at_block,
    _groups_inside,
)

# The heading level each step of the ladder splits at.  The last two
# steps go below the headings altogether, so they take whatever heading
# is in front of them.
_LADDER_LEVEL = (2, 3, 4, 5, 6, None, None)


def _leading_heading(group: list):
    """The heading a group starts with, if any."""
    if group and isinstance(group[0], Heading):
        return group[0]
    return None


def _same_heading(first, second) -> bool:
    """True when two headings are the same heading."""
    if not isinstance(first, Heading) or not isinstance(second, Heading):
        return False
    if first.level != second.level:
        return False
    return _inline_text(first.children) == _inline_text(second.children)


def _fit_pieces(blocks: list, limit: int, measure, level: int = 0,
                context: tuple = ()) -> list:
    """Break blocks down until every piece fits under the limit.

    Returns ``[(blocks, cost, context)]``.  ``context`` is the chain of
    headings the piece was cut out of.  The heading itself is *not* in
    the blocks -- it is put back in front of the piece by the caller,
    so that a part which begins in the middle of a section still says
    where it is.

    A piece that cannot be broken down any further is returned as it
    is -- the caller decides whether to publish it or to skip the
    article.
    """
    pieces = []
    for group in _LADDER[level](blocks):
        cost = measure(group)
        if cost <= limit or level + 1 >= len(_LADDER):
            pieces.append((group, cost, context))
            continue
        heading = _leading_heading(group)
        level_of_step = _LADDER_LEVEL[level]
        if heading is not None and (level_of_step is None
                                    or heading.level == level_of_step):
            body_blocks = group[1:]
            nested = context + (heading,)
        else:
            body_blocks = group
            nested = context
        for sub in _LADDER[level + 1](body_blocks):
            pieces.extend(_fit_pieces(sub, limit, measure, level + 1, nested))
    return pieces


def _merge_blocks(current: list, body: list) -> list:
    """Join two pieces that came out of the same block.

    A table cut between its rows and a code block cut between its
    lines would otherwise show up as two blocks: the header would be
    repeated for every single row, and one code block would break into
    a dozen pieces.
    """
    last = current[-1] if current else None
    first = body[0] if body else None
    if isinstance(last, Table) and isinstance(first, Table):
        if last.header == first.header and last.align == first.align:
            current[-1] = Table(header=last.header,
                                rows=list(last.rows) + list(first.rows),
                                align=last.align)
            return body[1:]
    if isinstance(last, CodeBlock) and isinstance(first, CodeBlock):
        if last.lang == first.lang:
            current[-1] = CodeBlock(lang=last.lang,
                                     code=last.code + "\n" + first.code)
            return body[1:]
    return body


def split_blocks(blocks: list, limit: int, measure) -> list:
    """Split a block list into parts that each fit under ``limit``.

    ``measure`` is called with a list of blocks and returns the size
    that group contributes: its rendered body plus the reference links
    it brings along.  The links are counted apart from the body
    because their wrapper is paid once per part, not once per block.

    The parts come back in reading order, each one a list of blocks.
    """
    pieces = _fit_pieces(blocks, limit, measure)

    parts = []
    current = []
    cost = 0
    opened = None
    for body, piece_cost, context in pieces:
        heading = context[-1] if context else _leading_heading(body)
        if current and cost + piece_cost > limit:
            parts.append(current)
            current = []
            cost = 0
            opened = None
        if context and (opened is None or not _same_heading(opened, heading)):
            # The part opens the section the piece belongs to.
            current.extend(context)
            cost += measure(list(context))
        body = _merge_blocks(current, body)
        current.extend(body)
        cost += piece_cost
        opened = heading
    if current:
        parts.append(current)
    return parts


def _fit_group(group: list, budget: int, measure, plain_measure) -> list:
    """Cut a group down until every piece fits into one draft.

    A group that is still too big after the first split is cut again.
    The first split works on an estimate, and the estimate can be off
    by the framing a part pays on top of its body -- losing a whole
    article to a few dozen characters is not acceptable, so the part
    is cut finer rather than refused.
    """
    if measure(group) <= budget:
        return [(group, False)]
    if plain_measure is not None and plain_measure(group) <= budget:
        return [(group, True)]

    pieces = split_blocks(group, budget, measure)
    if len(pieces) <= 1:
        # Nothing left to cut it smaller: one block is too big on its
        # own, and the caller refuses the article.
        return [(group, False)]

    parts = []
    for piece in pieces:
        parts.extend(_fit_group(piece, budget, measure, plain_measure))
    return parts


def plan_parts(blocks: list, limit: int, measure, plain_measure=None,
                reserve: int = None) -> list:
    """Decide how many drafts an article becomes.

    ``measure(blocks)`` returns the rendered size with syntax
    highlighting, ``plain_measure(blocks)`` the size without it.  An
    article that fits either way is one draft; one that fits neither
    is split.

    Returns ``[(blocks, use_plain)]`` -- one entry per draft, in
    reading order.  ``use_plain`` says whether that part has to drop
    the syntax highlighting to fit.

    ``limit`` is the limit WeChat enforces; ``reserve`` is the room
    kept back for the framing every part pays on top of its body --
    the transition lines, the category tag and the reference-links
    wrapper.  :func:`framing_reserve` computes it for an article.
    """
    budget = limit - (RESERVE if reserve is None else reserve)
    if measure(blocks) <= budget:
        return [(blocks, False)]
    if plain_measure is not None and plain_measure(blocks) <= budget:
        return [(blocks, True)]

    groups = split_blocks(blocks, budget, measure)
    parts = []
    for group in groups:
        parts.extend(_fit_group(group, budget, measure, plain_measure))
    return parts
