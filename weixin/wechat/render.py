"""Block AST -> WeChat official account HTML.

WeChat's editor accepts inline styles only: ``class`` attributes are
dropped and external CSS or JavaScript never runs.  Every style in this
module is therefore written into ``style="..."``.

Two conversions happen here:

1. Styles are inlined so the article survives WeChat's sanitiser.
2. Links degrade.  WeChat blocks outbound H5 links inside the body, so
   external links lose their anchor and are collected into a
   "reference links" block at the end of the article.
"""

from __future__ import annotations

import hashlib
import html as html_lib
import re
import uuid
from dataclasses import dataclass

from .mdparse import (
    Bold,
    CodeBlock,
    Heading,
    HtmlBlock,
    Image,
    InlineCode,
    Italic,
    Link,
    ListBlock,
    Paragraph,
    Quote,
    Table,
    Text,
    ThematicBreak,
)

__all__ = ["RenderResult", "Resolver", "render", "mermaid_key"]

BODY_FONT = "font-size:15px; line-height:1.75; margin:0 0 16px; word-break:break-word;"
H2_STYLE = ("font-size:18px; font-weight:700; margin:28px 0 14px; "
            "border-left:4px solid #3d7ea6; padding-left:10px;")
H3_STYLE = "font-size:16px; font-weight:700; margin:24px 0 12px;"
H4_STYLE = "font-size:15px; font-weight:700; margin:20px 0 10px;"
CODE_BLOCK_STYLE = (
    "background:#f6f8fa; padding:12px; border-radius:4px; overflow-x:auto; "
    "font-size:13px; line-height:1.5; margin:0 0 16px; "
    "font-family:Menlo,Consolas,'Courier New',monospace;"
)
INLINE_CODE_STYLE = "background:#f6f8fa; padding:2px 5px; border-radius:3px; font-size:14px;"
TABLE_STYLE = "border-collapse:collapse; width:100%; font-size:13px;"
TABLE_CELL_STYLE = "border:1px solid #dfe2e5; padding:7px 9px; text-align:left;"
QUOTE_STYLE = "border-left:3px solid #d0d0d0; padding-left:12px; color:#666; margin:0 0 16px;"
IMAGE_STYLE = "max-width:100%; height:auto; display:block; margin:0 auto 16px;"
MUTED_STYLE = "color:#888; font-size:13px; margin:0 0 8px;"
LIST_STYLE = "padding-left:22px; margin:0 0 16px;"
ITEM_STYLE = "margin:0 0 6px;"
CODE_FONT = "font-family:Menlo,Consolas,'Courier New',monospace;"

_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class RenderResult:
    """Rendered HTML plus the assets that still need uploading.

    ``token`` randomises the placeholder syntax.  Without it an article
    that talks about the placeholder mechanism (this repository's own
    design notes do) would have its prose rewritten when the placeholders
    are replaced with real URLs.
    """

    html: str
    assets: tuple = ()
    external_links: tuple = ()
    token: str = ""

    def placeholder(self, index: int) -> str:
        """The placeholder token standing in for asset ``index``."""
        return "{{img:%d:%s}}" % (index, self.token)

    def substitute(self, urls) -> str:
        """Replace every placeholder with the uploaded URL at that index."""
        out = self.html
        for index, url in enumerate(urls):
            out = out.replace(self.placeholder(index), url)
        return out

    @property
    def content_length(self) -> int:
        """Character count of the content WeChat will receive.

        WeChat caps the article body at 20000 characters of the ``content``
        field, which is this HTML string.
        """
        return len(self.html)


class Resolver:
    """Resolves a mermaid diagram to a rendered PNG on disk.

    The default resolver never finds anything, so mermaid blocks fall
    back to showing their source.  The CLI passes a resolver backed by
    the mermaid renderer.
    """

    def mermaid_path(self, key: str):
        return None


def mermaid_key(source: str) -> str:
    """Stable key for a mermaid diagram, independent of its position."""
    return hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]


def _escape(text: str) -> str:
    return html_lib.escape(text, quote=False)


def _strip_tags(text: str) -> str:
    return _TAG_RE.sub("", text)


class _Renderer:
    def __init__(self, resolver=None):
        self.resolver = resolver or Resolver()
        self.token = uuid.uuid4().hex[:8]
        self.assets = []
        self.asset_index = {}
        self.external_links = []

    def register(self, path: str) -> str:
        """Return the placeholder token for a local asset, registering once."""
        if path not in self.asset_index:
            self.asset_index[path] = len(self.assets)
            self.assets.append(path)
        return self.placeholder(self.asset_index[path])

    def placeholder(self, index: int) -> str:
        return "{{img:%d:%s}}" % (index, self.token)

    def inline(self, nodes) -> str:
        return "".join(self._inline_one(node) for node in nodes)

    def _inline_one(self, node) -> str:
        if isinstance(node, Text):
            return _escape(node.value)
        if isinstance(node, Bold):
            return "<strong>%s</strong>" % self.inline(node.children)
        if isinstance(node, Italic):
            return "<em>%s</em>" % self.inline(node.children)
        if isinstance(node, InlineCode):
            return "<code style=\"%s\">%s</code>" % (INLINE_CODE_STYLE, _escape(node.value))
        if isinstance(node, Link):
            text = self.inline(node.children)
            if node.target.startswith(("http://", "https://")):
                self.external_links.append((_strip_tags(text), node.target))
            return text
        if isinstance(node, Image):
            alt = _escape(node.alt)
            target = node.target
            if target.startswith(("http://", "https://", "data:")):
                return "<img src=\"%s\" alt=\"%s\" style=\"%s\" />" % (
                    _escape(target), alt, IMAGE_STYLE)
            return "<img src=\"%s\" alt=\"%s\" style=\"%s\" />" % (
                self.register(target), alt, IMAGE_STYLE)
        return ""

    def block(self, node) -> str:
        if isinstance(node, Heading):
            style = {2: H2_STYLE, 3: H3_STYLE}.get(node.level, H4_STYLE)
            return "<h{level} style=\"{style}\">{content}</h{level}>".format(
                level=node.level, style=style, content=self.inline(node.children))
        if isinstance(node, Paragraph):
            return "<p style=\"%s\">%s</p>" % (BODY_FONT, self.inline(node.children))
        if isinstance(node, CodeBlock):
            if node.lang.lower() == "mermaid":
                return self._mermaid(node)
            from .highlight import highlight_code
            return ("<pre style=\"%s\"><code style=\"%s\">%s</code></pre>") % (
                CODE_BLOCK_STYLE, CODE_FONT, highlight_code(node.code, node.lang))
        if isinstance(node, Table):
            return self._table(node)
        if isinstance(node, ListBlock):
            return self._list(node)
        if isinstance(node, Quote):
            inner = "".join(self.block(child) for child in node.blocks)
            return "<section style=\"%s\">%s</section>" % (QUOTE_STYLE, inner)
        if isinstance(node, ThematicBreak):
            return "<hr style=\"border:none; border-top:1px solid #e5e5e5; margin:24px 0;\" />"
        if isinstance(node, HtmlBlock):
            return node.html
        return ""

    def _mermaid(self, node) -> str:
        key = mermaid_key(node.code)
        path = self.resolver.mermaid_path(key)
        if path is not None:
            return "<img src=\"%s\" alt=\"mermaid diagram\" style=\"%s\" />" % (
                self.register(str(path)), IMAGE_STYLE)
        return (
            "<p style=\"%s\">图表渲染失败，以下为图表源码：</p>"
            "<pre style=\"%s\"><code style=\"%s\">%s</code></pre>"
        ) % (MUTED_STYLE, CODE_BLOCK_STYLE, CODE_FONT, _escape(node.code))

    def _table(self, node) -> str:
        aligns = node.align or [""] * len(node.header)
        head = "".join(
            "<th style=\"%s\">%s</th>" % (TABLE_CELL_STYLE, self.inline(cell))
            for cell in node.header
        )
        rows = []
        for row in node.rows:
            cells = []
            for index, cell in enumerate(row):
                align = aligns[index] if index < len(aligns) else ""
                style = TABLE_CELL_STYLE + (" text-align:%s;" % align if align else "")
                cells.append("<td style=\"%s\">%s</td>" % (style, self.inline(cell)))
            rows.append("<tr>%s</tr>" % "".join(cells))
        table = ("<table style=\"%s\"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>") % (
            TABLE_STYLE, head, "".join(rows))
        return "<section style=\"overflow-x:auto; margin:0 0 16px;\">%s</section>" % table

    def _list(self, node) -> str:
        items = []
        for item in node.items:
            marker = ""
            if item.checked is True:
                marker = "<span style=\"color:#3d7ea6;\">☑ </span>"
            elif item.checked is False:
                marker = "<span style=\"color:#999;\">☐ </span>"
            inner = "".join(self.block(child) for child in item.blocks)
            items.append("<li style=\"%s\">%s%s</li>" % (ITEM_STYLE, marker, inner))
        tag = "ol" if node.ordered else "ul"
        return "<{tag} style=\"{style}\">{items}</{tag}>".format(
            tag=tag, style=LIST_STYLE, items="".join(items))


def render(blocks: list, *, resolver=None) -> RenderResult:
    """Render a block AST into WeChat-ready HTML."""
    renderer = _Renderer(resolver)
    body = "".join(renderer.block(block) for block in blocks)

    if renderer.external_links:
        items = "".join(
            "<li style=\"%s\">%s：%s</li>" % (ITEM_STYLE, _escape(text), _escape(url))
            for text, url in renderer.external_links
        )
        body += (
            "<section style=\"margin:24px 0 0; padding-top:12px; border-top:1px solid #e5e5e5;\">"
            "<p style=\"%s\">参考链接</p><ul style=\"padding-left:22px;\">%s</ul></section>"
        ) % (MUTED_STYLE, items)

    return RenderResult(
        html=body,
        assets=tuple(renderer.assets),
        external_links=tuple(renderer.external_links),
        token=renderer.token,
    )
