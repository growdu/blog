"""Server-side code highlighting.

The site highlights code in the browser with Prism; WeChat has no
JavaScript, so the same treatment has to happen here and be inlined into
the HTML.  Pygments' ``nowrap=True`` formatter emits only inline styles,
which is exactly what WeChat accepts.
"""

from __future__ import annotations

import html as html_lib

from pygments import highlight as pygments_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

__all__ = ["highlight_code"]

_PLAIN_LANGUAGES = {"", "text", "plain", "plaintext", "txt"}
_FORMATTER = HtmlFormatter(nowrap=True, noclasses=True, style="default")


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
    return pygments_highlight(code, lexer, _FORMATTER)
