"""Server-side code highlighting.

The site highlights code in the browser with Prism; WeChat has no
JavaScript, so the same treatment has to happen here and be inlined into
the HTML.  Pygments' ``nowrap=True`` formatter emits only inline styles,
which is exactly what WeChat accepts.

WeChat counts the ``content`` field in characters, and a highlighted code
block is the most expensive thing in a technical article: Pygments emits
one ``<span>`` per token, and the whitespace between tokens is a token
too.  Two cheap passes shrink that overhead without changing a single
visible character:

- whitespace-only spans are unwrapped, keeping their text
- the optional whitespace in ``style="..."`` values is dropped
"""

from __future__ import annotations

import html as html_lib
import re

from pygments import highlight as pygments_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

__all__ = ["highlight_code"]

_PLAIN_LANGUAGES = {"", "text", "plain", "plaintext", "txt"}
_FORMATTER = HtmlFormatter(nowrap=True, noclasses=True, style="default")

_WHITESPACE_SPAN_RE = re.compile(r'<span style="[^"]*">(\s+)</span>')
_STYLE_ATTR_RE = re.compile(r'style="([^"]*)"')


def _compact_styles(html: str) -> str:
    """Drop the optional whitespace inside style attribute values."""

    def replace(match):
        value = match.group(1).replace(": ", ":").replace("; ", ";")
        return 'style="{}"'.format(value)

    return _STYLE_ATTR_RE.sub(replace, html)


def highlight_code(code: str, lang: str) -> str:
    """Return inline-styled HTML for a code block.

    Unknown languages fall back to escaped plain text rather than
    raising: a blog post with an exotic fence should still publish.
    """
    if lang.lower() in _PLAIN_LANGUAGES:
        return html_lib.escape(code, quote=False)
    try:
        lexer = get_lexer_by_name(lang, stripall=False)
    except ClassNotFound:
        return html_lib.escape(code, quote=False)
    html = pygments_highlight(code, lexer, _FORMATTER)
    html = _WHITESPACE_SPAN_RE.sub(r"\g<1>", html)
    return _compact_styles(html)
