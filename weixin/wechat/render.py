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

__all__ = ["RenderResult", "Resolver", "render", "mermaid_key", "sanitize_html", "css"]


def css(*declarations: str) -> str:
    """Join CSS declarations and drop the optional whitespace.

    WeChat counts the ``content`` field in characters, so every space
    in a style string is paid for on every element.  The site has 1234
    style attributes in a single long article; trimming them is the
    difference between fitting the limit and not.
    """
    text = ";".join(declarations)
    return text.replace(": ", ":").replace("; ", ";").strip()


BODY_FONT = css("font-size: 15px", "line-height: 1.75", "margin: 0 0 12px")
H2_STYLE = css("font-size: 17px", "font-weight: 700", "margin: 24px 0 12px",
               "border-left: 4px solid #3d7ea6", "padding-left: 10px")
H3_STYLE = css("font-size: 16px", "font-weight: 700", "margin: 20px 0 10px")
H4_STYLE = css("font-size: 15px", "font-weight: 700", "margin: 18px 0 10px")
CODE_BLOCK_STYLE = css("background: #f6f8fa", "padding: 12px", "overflow-x: auto",
                       "font-size: 13px", "line-height: 1.5")
INLINE_CODE_STYLE = css("background: #f6f8fa", "padding: 2px 5px", "border-radius: 3px")
TABLE_STYLE = css("border-collapse: collapse", "width: 100%", "font-size: 13px")
TABLE_CELL_STYLE = css("border: 1px solid #dfe2e5", "padding: 7px 9px")
QUOTE_STYLE = css("border-left: 3px solid #d0d0d0", "padding-left: 12px", "color: #666")
IMAGE_STYLE = css("max-width: 100%")
MUTED_STYLE = css("color: #888", "font-size: 13px")
LIST_STYLE = css("padding-left: 22px")
HR_STYLE = css("border: none", "border-top: 1px solid #e5e5e5", "margin: 24px 0")
CODE_FONT = css("font-family: Menlo, Consolas, monospace")

_TAG_RE = re.compile(r"<[^>]+>")

# Raw HTML blocks are rare in this corpus but not forbidden, so they are
# cleaned rather than trusted.  WeChat honours inline styles only, runs no
# JavaScript, and rejects script/style/iframe outright.
_RAW_DROP_RE = re.compile(r"<(script|style|iframe)\b.*?(?:</\1\s*>|$)", re.I | re.S)
_CLASS_ATTR_RE = re.compile(r"""\s+class\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)""", re.I)
_EVENT_ATTR_RE = re.compile(r"""\s+on[a-z]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)""", re.I)


def sanitize_html(raw: str) -> str:
    """Make a raw HTML block safe for WeChat.

    Drops ``script``/``style``/``iframe`` elements together with their
    content, and strips ``class`` and event handler attributes from what
    is left.  Everything else is passed through unchanged.
    """
    text = _RAW_DROP_RE.sub("", raw)
    text = _CLASS_ATTR_RE.sub("", text)
    text = _EVENT_ATTR_RE.sub("", text)
    return text


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
    external_images: tuple = ()
    token: str = ""

    def placeholder(self, index: int) -> str:
        """The placeholder token standing in for asset ``index``."""
        return "{{img:%d:%s}}" % (index, self.token)

    def external_placeholder(self, index: int) -> str:
        """The placeholder standing in for an externally hosted image."""
        return "{{ext:%d:%s}}" % (index, self.token)

    def substitute(self, urls, html: str = None) -> str:
        """Replace every placeholder with the uploaded URL at that index.

        ``html`` lets a second substitution continue where this one
        stopped; without it the substitution starts from :attr:`html`.
        """
        out = self.html if html is None else html
        for index, url in enumerate(urls):
            out = out.replace(self.placeholder(index), url)
        return out

    def substitute_external(self, urls, fallback: str = "", html: str = None) -> str:
        """Replace the external-image placeholders.

        ``urls`` holds the uploaded URL of each external image, in the
        order they appear in :attr:`external_images`.  A missing entry
        means the image could not be fetched; ``fallback`` then takes its
        place so the reader sees a note instead of a silent gap.
        """
        out = self.html if html is None else html
        for index in range(len(self.external_images)):
            url = urls[index] if index < len(urls) else None
            if url:
                out = out.replace(self.external_placeholder(index), url)
            else:
                out = out.replace(self.external_placeholder(index), fallback)
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
    def __init__(self, resolver=None, highlight: bool = True):
        self.resolver = resolver or Resolver()
        self.highlight = highlight
        self.token = uuid.uuid4().hex[:8]
        self.assets = []
        self.asset_index = {}
        self.external_links = []
        self.external_images = []

    def register(self, path: str) -> str:
        """Return the placeholder token for a local asset, registering once."""
        if path not in self.asset_index:
            self.asset_index[path] = len(self.assets)
            self.assets.append(path)
        return self.placeholder(self.asset_index[path])

    def placeholder(self, index: int) -> str:
        return "{{img:%d:%s}}" % (index, self.token)

    def register_external(self, url: str) -> str:
        """Return the placeholder for an externally hosted image.

        WeChat drops any image whose URL does not come from
        ``media/uploadimg`` -- it removes the element without a trace.
        So an external image is given a placeholder too, and the publish
        step downloads it and stores it on WeChat.
        """
        self.external_images.append(url)
        return "{{ext:%d:%s}}" % (len(self.external_images) - 1, self.token)

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
                # WeChat removes images that are not hosted on mmbiz, so
                # an external image needs the same treatment as a local
                # one: a placeholder the publish step can fill.
                return "<img src=\"%s\" alt=\"%s\" style=\"%s\" />" % (
                    self.register_external(target), alt, IMAGE_STYLE)
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
            if self.highlight:
                from .highlight import highlight_code
                code = highlight_code(node.code, node.lang)
            else:
                code = _escape(node.code)
            return ("<pre style=\"%s\"><code style=\"%s\">%s</code></pre>") % (
                CODE_BLOCK_STYLE, CODE_FONT, code)
        if isinstance(node, Table):
            return self._table(node)
        if isinstance(node, ListBlock):
            return self._list(node)
        if isinstance(node, Quote):
            inner = "".join(self.block(child) for child in node.blocks)
            return "<section style=\"%s\">%s</section>" % (QUOTE_STYLE, inner)
        if isinstance(node, ThematicBreak):
            return "<hr style=\"%s\" />" % HR_STYLE
        if isinstance(node, HtmlBlock):
            return sanitize_html(node.html)
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
            items.append("<li>%s%s</li>" % (marker, inner))
        tag = "ol" if node.ordered else "ul"
        return "<{tag} style=\"{style}\">{items}</{tag}>".format(
            tag=tag, style=LIST_STYLE, items="".join(items))


def render(blocks: list, *, resolver=None, highlight: bool = True,
           head_html: str = "", tail_html: str = "") -> RenderResult:
    """Render a block AST into WeChat-ready HTML.

    ``highlight=False`` renders code blocks as plain escaped text.  That
    is the fallback for articles that would otherwise exceed WeChat's
    20000-character limit: syntax colouring costs one ``<span>`` per
    token, which on a code-heavy article is more than a quarter of the
    budget.

    ``head_html`` and ``tail_html`` are raw HTML fragments placed before
    and after the article body.  WeChat's article payload has no field
    for a category or a collection, so a classification line has to
    live in the body itself.
    """
    renderer = _Renderer(resolver, highlight=highlight)
    body = head_html + "".join(renderer.block(block) for block in blocks) + tail_html

    if renderer.external_links:
        items = "".join(
            "<li>%s：%s</li>" % (_escape(text), _escape(url))
            for text, url in renderer.external_links
        )
        body += (
            "<section style=\"margin:24px 0 0;padding-top:12px;border-top:1px solid #e5e5e5;\">"
            "<p style=\"%s\">参考链接</p><ul style=\"padding-left:22px;\">%s</ul></section>"
        ) % (MUTED_STYLE, items)

    return RenderResult(
        html=body,
        assets=tuple(renderer.assets),
        external_links=tuple(renderer.external_links),
        external_images=tuple(renderer.external_images),
        token=renderer.token,
    )
