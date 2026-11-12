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
the slicer leaves alone (``**bold**``, ``*italic*``, ```code```).
Everything else -- code fences, tables, quotes, headings deeper than
``##`` -- has already been dropped upstream and never reaches this
module.
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

# Inline code: a backtick-quoted span is literal by definition.  The same
# shape the slicer recognises, so both modules agree on where a code span
# starts and ends.
_INLINE_CODE = re.compile(r"(`+)(.+?)\1", re.DOTALL)
# The emphasis rules, in the order they are applied.  ``***bold italic***``
# goes first: otherwise the bold rule eats it and leaves a stray star on
# each side.
#
# Every pattern names its three parts, because the flanking rules below
# have to know where the delimiter starts and ends.
_BOLD_ITALIC = re.compile(
    r"(?P<open>\*\*\*)(?P<content>.+?)(?P<close>\*\*\*)"
)
_BOLD = re.compile(r"(?P<open>\*\*)(?P<content>.+?)(?P<close>\*\*)")
# The italic pattern refuses a content that starts or ends with a space:
# "2 * 3 * 4" is arithmetic, not emphasis, and turning it into italics
# would be a wrong claim about the text.
_ITALIC = re.compile(
    r"(?P<open>\*)(?P<content>\S(?:[^*\n]*\S)?)(?P<close>\*)"
)
# The underscore forms.  Underscores are the tricky ones: they are all
# over the place in identifiers (``snake_case``, ``__init__``, ``_id``),
# so a delimiter may not touch a word character -- an underscore inside a
# word never starts an emphasis.  A backslash in front of it means the
# author escaped it, so it is a literal underscore and not a delimiter
# either.
_UNDER_BOLD = re.compile(
    r"(?<![A-Za-z0-9_\\])(?P<open>__)(?![_])"
    r"(?P<content>\S(?:[^_\n]*\S)?)(?<![_])(?P<close>__)(?![A-Za-z0-9_])"
)
_UNDER_ITALIC = re.compile(
    r"(?<![A-Za-z0-9_\\])(?P<open>_)(?![_])"
    r"(?P<content>\S(?:[^_\n]*\S)?)(?<![_])(?P<close>_)(?![A-Za-z0-9_])"
)
# ``~~struck out~~``: the markers go and the words stay.  No tag: the
# editor has no strikethrough, and a tag it does not know is a tag it
# may drop -- the WeChat adapter makes the same call.
_STRIKE = re.compile(r"(?P<open>~~)(?P<content>[^~]+)(?P<close>~~)")

# The rules above with the tags a matched pair becomes.  An empty tuple
# means the markers go and nothing takes their place.
_EMPHASIS = (
    (_BOLD_ITALIC, ("strong", "em")),
    (_BOLD, ("strong",)),
    (_ITALIC, ("em",)),
    (_UNDER_BOLD, ("strong",)),
    (_UNDER_ITALIC, ("em",)),
    (_STRIKE, ()),
)

# An autolink: ``<https://example.com/a>``.  The link markers go and the
# URL stays as plain text -- the blog shows it as a link, the Toutiao
# body must not have one, and the URL itself is allowed (see the design
# document, section 3.4).
_AUTOLINK = re.compile(r"&lt;((?:https?|ftp)://(?:&amp;|[^&\s<])+)&gt;")
# The same rule for the plain text, which is not escaped.
_AUTOLINK_TEXT = re.compile(r"<((?:https?|ftp)://[^>\s]+)>")

# The placeholder that stands in for a code span while the emphasis rules
# run.  ``\x00`` cannot appear in a post, and the rules below do not
# touch it.
_CODE_SLOT = "\x00{}\x00"


@dataclass(frozen=True)
class RenderResult:
    """The two pasteable forms of one article."""

    html: str
    text: str
    image_markers: tuple[str, ...]


def _escape(text: str) -> str:
    """Escape the three characters that would otherwise become markup.

    ``&`` goes first: escaping it later would turn the ``&`` of an
    already-escaped ``&lt;`` into ``&amp;lt;`` and show the reader the
    escape instead of the character.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _protect_code(text: str) -> tuple[str, list[str]]:
    """Take the inline code spans out of the text.

    They have to come out *before* the emphasis rules run: inside a code
    span ``**`` is two stars, not bold.  Running the rules over the
    whole string instead turns ```**x**``` into bold code, and a code
    sample that is bold is a code sample that no longer says what it
    said.
    """
    spans: list[str] = []

    def protect(match):
        spans.append(match.group(2))
        return _CODE_SLOT.format(len(spans) - 1)

    return _INLINE_CODE.sub(protect, text), spans


def _is_punctuation(char: str) -> bool:
    """Whether a character counts as punctuation.

    CommonMark counts the Unicode P (punctuation) and S (symbol)
    categories; the blog's own renderer counts the same plus a handful of
    ASCII marks.  It matters: the full stop in "**数据：**描述" is what
    stops the bold from closing, and a rule that ignored punctuation
    would bold the wrong half of the sentence.
    """
    return unicodedata.category(char)[0] in ("P", "S")


def _left_flanking(text: str, start: int, end: int) -> bool:
    """Whether the delimiter at ``[start, end)`` may open an emphasis.

    A delimiter opens when what follows it is not whitespace, and --
    when what follows it is punctuation -- what precedes it is
    whitespace or punctuation too.
    """
    after = text[end] if end < len(text) else ""
    before = text[start - 1] if start > 0 else ""
    if not after or after.isspace():
        return False
    if _is_punctuation(after) and not (
        not before or before.isspace() or _is_punctuation(before)
    ):
        return False
    return True


def _right_flanking(text: str, start: int, end: int) -> bool:
    """Whether the delimiter at ``[start, end)`` may close an emphasis.

    The mirror image of :func:`_left_flanking`.  This is the rule that
    keeps C code intact: in ``void *data; int (*apply)(...)`` the star
    before "apply" follows a bracket and precedes a letter, so it is not
    a closing delimiter -- and the whole line stays what it is, instead
    of turning half a function signature into italics.
    """
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    if not before or before.isspace():
        return False
    if _is_punctuation(before) and not (
        not after or after.isspace() or _is_punctuation(after)
    ):
        return False
    return True


def _apply_emphasis(text: str, as_html: bool) -> str:
    """Run the inline emphasis rules over the text.

    ``as_html`` says what a matched pair becomes: a tag for the HTML,
    nothing for the plain text.  The rules themselves are the same, so
    the two artefacts can never disagree about what is emphasised.

    A pair that the flanking rules reject is left exactly as it was --
    the stars stay visible, the way the blog shows them.
    """
    for pattern, tags in _EMPHASIS:
        text = _substitute(pattern, text, tags, as_html)
    return text


def _substitute(pattern, text: str, tags: tuple[str, ...], as_html: bool) -> str:
    """Replace the emphasis pairs of one rule, if they are really pairs.

    A candidate pair is only an emphasis when its delimiters can open
    and close one; otherwise it is literal text and has to stay that
    way.
    """

    def replace(match):
        if not _left_flanking(text, match.start("open"), match.end("open")):
            return match.group(0)
        if not _right_flanking(text, match.start("close"), match.end("close")):
            return match.group(0)
        content = match.group("content")
        if not as_html or not tags:
            return content
        # The tags nest: "***x***" is a bold inside an italic.
        html = content
        for tag in reversed(tags):
            html = "<{0}>{1}</{0}>".format(tag, html)
        return html

    return pattern.sub(replace, text)


def _inline_html(text: str) -> str:
    """The text of one block, as HTML.

    Escape first, then turn the inline markdown into tags.  The order
    matters both ways round: escaping afterwards would eat the tags that
    were just written, and the emphasis rules would eat the escapes
    that were just written if they ran first.
    """
    protected, spans = _protect_code(_escape(text))
    protected = _AUTOLINK.sub(r"\1", protected)
    protected = _apply_emphasis(protected, as_html=True)
    for index, content in enumerate(spans):
        protected = protected.replace(
            _CODE_SLOT.format(index),
            '<code style="{}">{}</code>'.format(_CODE_STYLE, content),
        )
    return protected


def _inline_text(text: str) -> str:
    """The text of one block, as plain text.

    The markdown markers are dropped, not kept: this text is pasted into
    an editor that renders no markup, and a reader must not see a row of
    asterisks or backticks.
    """
    protected, spans = _protect_code(text)
    protected = _AUTOLINK_TEXT.sub(r"\1", protected)
    protected = _apply_emphasis(protected, as_html=False)
    for index, content in enumerate(spans):
        protected = protected.replace(_CODE_SLOT.format(index), content)
    return protected


def _markers_in(text: str) -> list[str]:
    """The picture placeholders in one line, in the order they appear.

    Code spans are skipped: a ``【图1】`` between backticks is a sample
    of the placeholder syntax, not a picture.
    """
    protected, _ = _protect_code(text)
    return [match.group(0) for match in _MARKER.finditer(protected)]


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
    markers: list[str] = []
    seen: set[str] = set()
    previous_was_item = False

    for block in article.body.split("\n\n"):
        for raw_line in block.split("\n"):
            line = raw_line.strip()
            if not line:
                continue

            for marker in _markers_in(line):
                if marker not in seen:
                    seen.add(marker)
                    markers.append(marker)

            heading = _HEADING.match(line)
            if heading:
                title = heading.group(1).strip()
                html_parts.append(
                    '<h2 style="{}">{}</h2>'.format(_H2_STYLE, _inline_html(title))
                )
                text_groups.append(_inline_text(title))
                previous_was_item = False
                continue

            item = _ITEM.match(line)
            if item:
                content = item.group(1).strip()
                html_parts.append(
                    '<p style="{}">• {}</p>'.format(_ITEM_STYLE, _inline_html(content))
                )
                line_text = "• " + _inline_text(content)
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
                previous_was_item = False
                continue

            html_parts.append(
                '<p style="{}">{}</p>'.format(_P_STYLE, _inline_html(line))
            )
            text_groups.append(_inline_text(line))
            previous_was_item = False

    return RenderResult(
        html="\n".join(html_parts),
        text="\n\n".join(text_groups),
        image_markers=tuple(markers),
    )
