"""Render the Toutiao article as paste-ready HTML and as plain text.

Two artefacts, two purposes:

- ``html`` is what the author pastes into the Toutiao editor.  The styles
  are inline because the editor drops ``<style>`` blocks, and there are no
  ``class`` attributes for the same reason: whatever the editor keeps, it
  keeps as written.
- ``text`` is the fallback for the day the editor mangles the HTML: the
  same content with every tag taken away and every markdown marker
  flattened to the text it stands for.

The input is the *sliced* body, so its shape is fixed by
``contract.py``: blocks separated by a blank line, ``## `` for headings,
``- `` for list items, ``【图N】`` for pictures, and the inline markdown
the slicer leaves alone (``**bold**``, ``*italic*`, ```code```).
Everything else -- code fences, tables, quotes, headings deeper than
``##`` -- has already been dropped upstream and never reaches this
module.

The inline rules are CommonMark's, because the blog renders the same
post with marked and the two have to say the same thing: a reader who
reads the post on the blog and the copy on Toutiao must not see
different emphasis, and the emphasis must never change which words are
in the text.

So the line is scanned once, into pieces, and every pair of delimiters
is decided in that one pass.  A rule that ran on the output of another
rule would see the tags the first rule wrote and take them for text --
that is how ``**x**`` and ``*y*`` used to end up with the tags of one
inside the tags of the other.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .contract import ToutiaoArticle

__all__ = ["RenderResult", "render"]


# The styles are written inline, one per kind of block.  A ``<style>``
# block and a ``class`` attribute both need the editor to keep a
# ``<head>`` it does not have, so they are not an option here.
_P_STYLE = "margin:0 0 16px 0;line-height:1.75;font-size:16px;color:#333333;"
_H2_STYLE = "margin:24px 0 12px 0;font-size:18px;font-weight:bold;color:#222222;"
_ITEM_STYLE = "margin:0 0 8px 0;padding-left:12px;line-height:1.75;font-size:16px;color:#333333;"
_MARK_STYLE = "margin:16px 0;text-align:center;color:#999999;font-size:14px;"
_CODE_STYLE = (
    "padding:1px 4px;background-color:#f5f5f5;border-radius:3px;"
    "font-family:monospace;font-size:14px;color:#c7254e;"
)

# The blocks of the sliced body.  ``##`` is the only heading level the
# slicer keeps, and it always writes it with a space after the hashes.
_HEADING = re.compile(r"^##\s+(.+)$")
# List items are normalised to a dash by the slicer, and it only calls a
# line a list item when a space follows the dash -- "1.5" is a number,
# not an item.
_ITEM = re.compile(r"^-\s+(.+)$")
# The picture placeholder the slicer leaves behind, standalone or inline.
_MARKER = re.compile(r"【图(\d+)】")

# The characters a backslash may escape.  CommonMark calls them ASCII
# punctuation; a backslash in front of anything else is a backslash.
#
# The rule is the same for every character: ``\`` in front of one of
# them means "the character itself, not a marker".  Recognising it for
# the underscore only -- and leaving ``\-`` and ``\*`` alone -- would
# mean two different answers to the same question.
_ESCAPABLE = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"

# An autolink: ``<https://example.com/a>``.  The link markers go and the
# URL stays as plain text -- the blog shows it as a link, the Toutiao
# body must not have one, and the URL itself is allowed (see the design
# document, section 3.4).
#
# There is one rule for both artefacts, and it runs on the raw line: a
# second copy of it -- one for the escaped text and one for the plain
# text -- is how the two paths drift apart and start saying different
# things about the same words.
_AUTOLINK = re.compile(r"<(?:https?|ftp)://[^<>\s]+>")

# The tags a pair of delimiters becomes.  ``**x**`` is strong, ``*x*``
# is emphasis, and ``***x***`` is both -- written the way this module
# has always written it.  The blog's own renderer nests the two the
# other way round (``<em><strong>``); the display is the same, so this
# is a difference in the bytes, not in the meaning.  Do not "fix" it
# without checking what the product looks like.
_TAGS = {
    1: ("em",),
    2: ("strong",),
    3: ("strong", "em"),
}


@dataclass
class _Token:
    """One piece of a line.

    ``kind`` is ``"text"`` (words and punctuation), ``"code"`` (an inline
    code span) or ``"delim"`` (a run of emphasis characters).
    """

    kind: str
    value: str = ""
    count: int = 0
    can_open: bool = False
    can_close: bool = False


@dataclass(frozen=True)
class RenderResult:
    """The two pasteable forms of one article.

    ``blocks`` is the text of every top-level block, in order -- what the
    platform will show as one paragraph each.  It is not the same as
    splitting ``text`` on blank lines: consecutive list items share one
    line group in the plain-text form, but the platform shows each of them
    as its own paragraph, and the per-paragraph limit is judged on those.
    """

    html: str
    text: str
    image_markers: tuple[str, ...]
    blocks: tuple[str, ...] = ()


def _escape(text: str) -> str:
    """Escape the three characters that would otherwise become markup.

    ``&`` goes first: escaping it later would turn the ``&`` of an
    already-escaped ``&lt;`` into ``&amp;lt;`` and show the reader the
    escape instead of the character.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _is_punctuation(char: str) -> bool:
    """Whether a character counts as punctuation.

    CommonMark counts the Unicode P (punctuation) and S (symbol)
    categories; the blog's own renderer counts the same plus a handful of
    ASCII marks.  It matters: the full stop in "**数据：**描述" is what
    stops the bold from closing, and a rule that ignored punctuation
    would bold the wrong half of the sentence.
    """
    return unicodedata.category(char)[0] in ("P", "S")


def _left_flanking(before: str, after: str) -> bool:
    """Whether a delimiter run may open an emphasis.

    A run opens when what follows it is not whitespace, and -- when what
    follows it is punctuation -- what precedes it is whitespace or
    punctuation too.
    """
    if not after or after.isspace():
        return False
    if _is_punctuation(after) and not (
        not before or before.isspace() or _is_punctuation(before)
    ):
        return False
    return True


def _right_flanking(before: str, after: str) -> bool:
    """Whether a delimiter run may close an emphasis.

    The mirror image of :func:`_left_flanking`.  This is the rule that
    keeps C code intact: in ``void *data; int (*apply)(...)`` the star
    before "apply" follows a bracket and precedes a letter, so it is
    not a closing delimiter -- and the whole line stays what it is,
    instead of turning half a function signature into italics.
    """
    if not before or before.isspace():
        return False
    if _is_punctuation(before) and not (
        not after or after.isspace() or _is_punctuation(after)
    ):
        return False
    return True


def _can_delimit(text: str, start: int, end: int, char: str) -> tuple[bool, bool]:
    """Whether a delimiter run may open an emphasis, and may close one.

    The star and the underscore are not the same.  A star opens and
    closes wherever the flanking rules allow it.  An underscore between
    two words is part of the word -- ``snake_case``, ``__init__`` -- so
    it only opens when what stands on the outside of it is punctuation or
    whitespace.  That is also why an underscore between two Chinese
    characters is not emphasis: the characters are words, and a word is
    not punctuation.
    """
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    left = _left_flanking(before, after)
    right = _right_flanking(before, after)
    if char == "_":
        return (
            left and (not right or _is_punctuation(before)),
            right and (not left or _is_punctuation(after)),
        )
    return left, right


def _code_span(text: str, start: int) -> tuple[str, int] | None:
    """The inline code span that starts at ``start``, if there is one.

    A run of backticks opens a code span, and the next run of exactly
    the same length closes it -- a shorter run is just text inside the
    span.  When there is no such run, the backticks are text.

    The content loses one space at each end when it has a space at both
    ends and is not made of spaces alone.  That is CommonMark's rule,
    and it is what makes a fence written as ``` ```mermaid ``` ``` come
    out as ``` ```mermaid ``` ```.
    """
    length = len(text)
    opening = start
    while opening < length and text[opening] == "`":
        opening += 1
    size = opening - start
    pos = opening
    while pos < length:
        if text[pos] != "`":
            pos += 1
            continue
        closing = pos
        while closing < length and text[closing] == "`":
            closing += 1
        if closing - pos == size:
            return _trim_code(text[opening:pos]), closing
        pos = closing
    return None


def _trim_code(content: str) -> str:
    """Take one space off each end of a code span's content."""
    if len(content) >= 2 and content[0] in " \t" and content[-1] in " \t":
        if content.strip(" \t"):
            return content[1:-1]
    return content


def _scan(text: str) -> list[_Token]:
    """Split a line into the pieces the inline rules work on.

    The scan runs on the *raw* line, before anything is escaped.  The
    flanking rules have to see the characters the author wrote: a
    backtick right next to ``**`` is a backtick, and it is punctuation,
    so the ``**`` after it cannot close a bold.  That is the difference
    between "**系统表 `pg_publication`**" being bold and being text --
    and the blog says text.
    """
    tokens: list[_Token] = []
    buffer: list[str] = []
    pos = 0
    length = len(text)

    def flush() -> None:
        if buffer:
            tokens.append(_Token("text", "".join(buffer)))
            buffer.clear()

    while pos < length:
        char = text[pos]
        if char == "\\" and pos + 1 < length and text[pos + 1] in _ESCAPABLE:
            # A backslash says "the next character is itself".  The
            # backslash goes, the character stays -- and the character
            # is not a delimiter, so `\_` cannot open an emphasis.
            flush()
            tokens.append(_Token("text", text[pos + 1]))
            pos += 2
            continue
        if char == "`":
            span = _code_span(text, pos)
            if span is not None:
                content, end = span
                flush()
                tokens.append(_Token("code", content))
                pos = end
                continue
        if char == "<":
            match = _AUTOLINK.match(text, pos)
            if match:
                flush()
                tokens.append(_Token("text", match.group(0)[1:-1]))
                pos = match.end()
                continue
        if char in "*_~":
            run = pos
            while run < length and text[run] == char:
                run += 1
            flush()
            token = _Token("delim", char, count=run - pos)
            if char != "~":
                token.can_open, token.can_close = _can_delimit(text, pos, run, char)
            tokens.append(token)
            pos = run
            continue
        buffer.append(char)
        pos += 1
    flush()
    return tokens


@dataclass
class _Pairing:
    """Which runs of delimiters pair up, and how much of each run they use.

    ``pairs`` maps the index of an opening run to the pairs it opened,
    each one the index of its closing run and the tags it becomes.  (A
    run of four stars opens two pairs: ``****x****``.)  ``used_open`` and
    ``used_close`` count the characters every run spent on each side: an
    opener eats them from the end of the run, a closer from its
    beginning.  What is left over stays in the text.
    """

    pairs: dict[int, tuple[int, tuple[str, ...]]]
    used_open: dict[int, int]
    used_close: dict[int, int]

    def remaining(self, index: int, token: _Token) -> int:
        """How many delimiter characters of a run are still free."""
        return (
            token.count
            - self.used_open.get(index, 0)
            - self.used_close.get(index, 0)
        )


def _odd_match(opener: _Token, closer: _Token) -> bool:
    """CommonMark's rule of three.

    When a delimiter can both open and close, a pair whose two counts
    add up to a multiple of three is not a pair -- unless both counts
    are multiples of three themselves.  It is what keeps
    ``*foo**bar**baz*`` from turning into the wrong emphasis.
    """
    if not (closer.can_open or opener.can_close):
        return False
    if closer.count % 3 == 0:
        return False
    return (opener.count + closer.count) % 3 == 0


def _delims_used(left: int, right: int) -> int:
    """How many delimiter characters a pair of runs uses."""
    if left == 3 and right == 3:
        # `***x***` is bold and italic at once.
        return 3
    if left >= 2 and right >= 2:
        return 2
    return 1


def _pair_delimiters(tokens: list[_Token]) -> _Pairing:
    """Pair the emphasis delimiters up, the way CommonMark does.

    Walk the runs from left to right; for every run that may close, look
    back for the nearest run that may open.  Each pair is decided here,
    once, before a single tag is written -- so no pair is ever matched
    against the tags of another pair, and the tags can only nest.
    """
    runs = [
        index for index, token in enumerate(tokens)
        if token.kind == "delim" and token.value in ("*", "_")
    ]
    count = len(runs)
    prev = [index - 1 for index in range(count)]
    nxt = [index + 1 for index in range(count)]
    if count:
        prev[0] = -1
        nxt[count - 1] = -1

    def remove(index: int) -> None:
        before, after = prev[index], nxt[index]
        if before != -1:
            nxt[before] = after
        if after != -1:
            prev[after] = before

    pairing = _Pairing({}, {}, {})
    if not count:
        return pairing
    index = 0
    while index != -1:
        closer = tokens[runs[index]]
        if not closer.can_close:
            index = nxt[index]
            continue
        # Look back for the nearest run that may open.  The rule of
        # three can turn a candidate away.
        candidate = prev[index]
        found = -1
        while candidate != -1:
            opener = tokens[runs[candidate]]
            if (opener.can_open and opener.value == closer.value
                    and not _odd_match(opener, closer)):
                found = candidate
                break
            candidate = prev[candidate]
        if found == -1:
            index = nxt[index]
            continue

        opener = tokens[runs[found]]
        used = _delims_used(
            pairing.remaining(runs[found], opener),
            pairing.remaining(runs[index], closer),
        )
        pairing.pairs.setdefault(runs[found], []).append((runs[index], _TAGS[used]))
        pairing.used_open[runs[found]] = pairing.used_open.get(runs[found], 0) + used
        pairing.used_close[runs[index]] = pairing.used_close.get(runs[index], 0) + used
        # The runs between the pair live inside it now.
        candidate = prev[index]
        while candidate != -1 and candidate != found:
            dead = candidate
            candidate = prev[candidate]
            remove(dead)
        if pairing.remaining(runs[found], opener) == 0:
            remove(found)
        if pairing.remaining(runs[index], closer) == 0:
            dead = index
            index = nxt[index]
            remove(dead)
            continue
        # The closer still has characters left: it may close another pair.
    return pairing


def _crosses(start: int, end: int, pairing: _Pairing) -> bool:
    """Whether a pair would cross one that is already paired."""
    for opener, chain in pairing.pairs.items():
        for closer, _ in chain:
            if start < opener < end < closer or opener < start < closer < end:
                return True
    return False


def _pair_strikes(tokens: list[_Token], pairing: _Pairing) -> None:
    """Pair the ``~~`` runs up: the markers go and the words stay.

    There is no tag for a strikethrough -- the editor does not know one,
    and a tag it does not know is a tag it may drop.  The WeChat adapter
    makes the same call.
    """
    pending = -1
    for index, token in enumerate(tokens):
        if token.kind != "delim" or token.value != "~" or token.count != 2:
            continue
        if pending == -1:
            pending = index
            continue
        if _crosses(pending, index, pairing):
            # The strike would cut across an emphasis.  Leave the
            # markers alone rather than tear the nesting apart.
            pending = -1
            continue
        pairing.pairs.setdefault(pending, []).append((index, ()))
        # The strike takes both markers whole.
        pairing.used_open[pending] = pairing.used_open.get(pending, 0) + 2
        pairing.used_close[index] = pairing.used_close.get(index, 0) + 2
        pending = -1


def _leftover(index: int, token: _Token, pairing: _Pairing) -> str:
    """The delimiter characters of a run that no pair used."""
    return token.value * pairing.remaining(index, token)


def _render_token(index: int, token: _Token, pairing: _Pairing, as_html: bool) -> str:
    """Render one piece that no pair of delimiters covers."""
    if token.kind == "code":
        if not as_html:
            return token.value
        return '<code style="{}">{}</code>'.format(_CODE_STYLE, _escape(token.value))
    if token.kind == "delim":
        return _leftover(index, token, pairing)
    if as_html:
        return _escape(token.value)
    return token.value


def _render_range(tokens, pairing: _Pairing, as_html: bool, low: int, high: int, out: list) -> None:
    """Render the pieces between two positions, tags and all."""
    index = low
    while index < high:
        token = tokens[index]
        chain = pairing.pairs.get(index)
        if chain is None:
            out.append(_render_token(index, token, pairing, as_html))
            index += 1
            continue
        _render_chain(tokens, pairing, as_html, index, chain, out)
        index = chain[-1][0] + 1


def _render_chain(tokens, pairing: _Pairing, as_html: bool, index: int, chain: list, out: list) -> None:
    """Render a run of delimiters that opened more than one pair.

    ``****x****`` is two pairs that share the same two runs: the first
    one takes two characters off each end, the second one takes the
    other two.  The pairs nest, so the tags open from the outside in
    and close from the inside out.
    """
    # The characters the opening run did not use stay in front of the
    # tags.
    if not pairing.used_close.get(index):
        out.append(_leftover(index, tokens[index], pairing))
    if as_html:
        for _, tags in reversed(chain):
            for tag in tags:
                out.append("<{0}>".format(tag))
    _render_range(tokens, pairing, as_html, index + 1, chain[0][0], out)
    for position, (closer_index, tags) in enumerate(chain):
        if as_html:
            for tag in reversed(tags):
                out.append("</{0}>".format(tag))
        if position + 1 < len(chain) and chain[position + 1][0] == closer_index:
            # The same run closes both pairs: it keeps its leftover
            # until the last of them is closed.
            continue
        # The characters the closing run did not use stay behind the
        # tags.
        out.append(_leftover(closer_index, tokens[closer_index], pairing))
        if position + 1 < len(chain):
            _render_range(
                tokens, pairing, as_html, closer_index + 1, chain[position + 1][0], out
            )


def _inline(tokens: list[_Token], as_html: bool) -> str:
    """Render one block's pieces as HTML, or as plain text.

    ``as_html`` says what a matched pair becomes: a tag for the HTML,
    nothing for the plain text.  The pairs themselves are decided the
    same way for both, so the two artefacts can never disagree about
    what is emphasised.

    A pair the flanking rules reject is left exactly as it was -- the
    stars stay visible, the way the blog shows them.
    """
    pairing = _pair_delimiters(tokens)
    _pair_strikes(tokens, pairing)
    out: list[str] = []
    _render_range(tokens, pairing, as_html, 0, len(tokens), out)
    return "".join(out)


def _markers_in(tokens: list[_Token]) -> list[str]:
    """The picture placeholders in one line, in the order they appear.

    Code spans are skipped: a ``【图1】`` between backticks is a sample
    of the placeholder syntax, not a picture.
    """
    found: list[str] = []
    for token in tokens:
        if token.kind == "code":
            continue
        found.extend(match.group(0) for match in _MARKER.finditer(token.value))
    return found


def render(article: ToutiaoArticle) -> RenderResult:
    """Render the article body into HTML and plain text.

    ``image_markers`` lists the picture placeholders the body carries,
    in the order they appear -- the packaging flow uses it to check that
    every picture that has a slot in the text also has a file to upload
    into that slot.  A placeholder that shows up twice is listed once:
    the list is a set of slots, not a count of characters.
    """
    html_parts: list[str] = []
    text_groups: list[str] = []
    blocks: list[str] = []
    markers: list[str] = []
    seen: set[str] = set()
    previous_was_item = False

    for block in article.body.split("\n\n"):
        for raw_line in block.split("\n"):
            line = raw_line.strip()
            if not line:
                continue

            heading = _HEADING.match(line)
            item = _ITEM.match(line)
            if heading:
                content = heading.group(1).strip()
            elif item:
                content = item.group(1).strip()
            else:
                content = line
            tokens = _scan(content)
            for marker in _markers_in(tokens):
                if marker not in seen:
                    seen.add(marker)
                    markers.append(marker)

            if heading:
                html_parts.append(
                    '<h2 style="{}">{}</h2>'.format(_H2_STYLE, _inline(tokens, True))
                )
                text_groups.append(_inline(tokens, False))
                blocks.append(_inline(tokens, False))
                previous_was_item = False
                continue

            if item:
                html_parts.append(
                    '<p style="{}">• {}</p>'.format(_ITEM_STYLE, _inline(tokens, True))
                )
                line_text = "• " + _inline(tokens, False)
                blocks.append(line_text)
                if previous_was_item and text_groups:
                    # Consecutive items are one list: they stay on one
                    # line each, without a blank line between them.
                    text_groups[-1] += "\n" + line_text
                else:
                    text_groups.append(line_text)
                previous_was_item = True
                continue

            if _MARKER.fullmatch(line):
                # A picture on its own line: the slot is the whole
                # paragraph, centred and grey, so the uploader can see
                # where the picture goes.
                html_parts.append(
                    '<p style="{}">{}</p>'.format(_MARK_STYLE, _escape(line))
                )
                text_groups.append(line)
                blocks.append(line)
                previous_was_item = False
                continue

            html_parts.append(
                '<p style="{}">{}</p>'.format(_P_STYLE, _inline(tokens, True))
            )
            text_groups.append(_inline(tokens, False))
            blocks.append(_inline(tokens, False))
            previous_was_item = False

    return RenderResult(
        html="\n".join(html_parts),
        text="\n\n".join(text_groups),
        image_markers=tuple(markers),
        blocks=tuple(blocks),
    )
