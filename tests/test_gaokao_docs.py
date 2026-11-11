"""Contract tests for the gaokao docs under ``docs/life/gaokao/``.

Three invariants are enforced here:

1. **Front matter** is present, closed, and carries the fields the Hexo
   sync tool reads (``title`` / ``date`` / ``tags`` / ``categories``).
2. **Relative links** inside the section resolve to a file that exists --
   a doc that points at a sibling article which was renamed silently
   publishes a dead link.
3. **In-page anchors** (``[text](#anchor)``) point at a heading that
   actually exists in the same document.

(3) is the one that earns its keep.  A wrong anchor still renders as a
clickable link -- it just silently lands on the top of the page instead
of the section it names, so nobody notices until someone complains that
the table of contents "does nothing".

Heading ids come from ``hexo-util``'s ``slugize()`` (used by
``hexo-renderer-marked`` to build ``<h2 id="...">``); it is replicated in
:func:`_slugize` below.  The replication is deliberately tolerant about
quote characters: the Markdown renderer applies a smart-quotes pass that
turns a straight ``"`` into a curly quote before the id is computed, and
which of the two curly quotes appears depends on the surrounding text.
Since that choice is invisible to a reader, anchors are compared with
quote characters removed on both sides.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SECTION = REPO_ROOT / "docs" / "life" / "gaokao"

# Sections that are not part of a table of contents.
_TOC_EXCLUDED_HEADINGS = {"目录", "相关阅读"}

# Quote characters the Markdown renderer may rewrite before slugizing.
_QUOTES = "\"'“”‘’"

# hexo-util's slugize(): whitespace and ASCII punctuation collapse to "-".
_SPECIAL = re.compile(r"[\s~`!@#$%^&*()\-_+=[\]{}|\\;:\"'<>,.?/]+")
_CONTROL = re.compile(r"[\u0000-\u001f]")


def _slugize(text: str) -> str:
    """Replicate ``hexo-util``'s ``slugize()``."""
    text = _CONTROL.sub("", text)
    text = _SPECIAL.sub("-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-")


def _strip_inline(text: str) -> str:
    """Reduce inline Markdown to its rendered plain text."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links
    text = re.sub(r"`([^`]*)`", r"\1", text)  # inline code
    text = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)  # bold
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)  # italic
    text = re.sub(r"<[^>]+>", "", text)  # raw html
    for entity, char in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"')):
        text = text.replace(entity, char)
    return text


def _strip_quotes(text: str) -> str:
    for quote in _QUOTES:
        text = text.replace(quote, "")
    return text


def _fenced_regions(markdown: str) -> list[tuple[int, int]]:
    """Return (start, end) line ranges of fenced code blocks."""
    regions: list[tuple[int, int]] = []
    start = None
    for index, line in enumerate(markdown.split("\n")):
        if line.lstrip().startswith("```"):
            if start is None:
                start = index
            else:
                regions.append((start, index + 1))
                start = None
    if start is not None:
        regions.append((start, len(markdown.split("\n"))))
    return regions


def _heading_ids(markdown: str) -> list[str]:
    """Heading ids the Hexo renderer would emit for this document.

    The leading ``# Title`` is skipped: ``tools/sync-hexo.py`` strips it
    before handing the body to the renderer, because the title already
    lives in the front matter.

    Returned in document order -- duplicate headings get the ``-1``,
    ``-2`` suffixes the renderer appends.
    """
    lines = markdown.split("\n")
    fenced = _fenced_regions(markdown)
    seen: dict[str, int] = {}
    ids: list[str] = []
    first_h1_skipped = False

    for index, line in enumerate(lines):
        if any(start <= index < end for start, end in fenced):
            continue
        match = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if not match:
            continue
        level, text = len(match.group(1)), match.group(2)
        if level == 1 and not first_h1_skipped:
            first_h1_skipped = True
            continue
        base = _slugize(_strip_quotes(_strip_inline(text)))
        if base in seen:
            base = f"{base}-{seen[base]}"
        seen[base] = seen.get(base, 0) + 1
        ids.append(base)

    return ids


def _doc_paths() -> list[Path]:
    return sorted(SECTION.rglob("*.md"))


def _split_front_matter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "", text
    return text[3:end], text[end + 4 :]


@pytest.fixture(scope="module")
def docs() -> list[tuple[Path, str]]:
    return [(path, path.read_text(encoding="utf-8")) for path in _doc_paths()]


def test_section_has_the_expected_docs(docs):
    names = {path.relative_to(SECTION).as_posix() for path, _ in docs}
    assert "yunnan-policy/index.md" in names, "云南政策文档缺失"
    assert "yunnan-apply/index.md" in names, "云南报考文档缺失"
    assert "physics-methods/index.md" in names, "物理方法文档缺失"
    assert "chemistry-methods/index.md" in names, "化学方法文档缺失"
    assert "biology-methods/index.md" in names, "生物方法文档缺失"
    assert "_index.md" in names, "小节索引缺失"


@pytest.mark.parametrize("path", _doc_paths(), ids=lambda p: p.relative_to(SECTION).as_posix())
def test_front_matter_is_complete(path: Path):
    text = path.read_text(encoding="utf-8")
    front, _ = _split_front_matter(text)
    assert front, f"{path.name} 缺少 front matter"
    # `tags` / `categories` may sit nested under Hugo's `cascade:` block,
    # so leading whitespace is allowed.
    assert re.search(r"^\s*title\s*:", front, re.M), f"{path.name} 的 front matter 缺少 title"
    assert re.search(r"^\s*tags\s*:", front, re.M), f"{path.name} 的 front matter 缺少 tags"

    if path.name == "_index.md":
        # A section index declares its categories through the Hugo
        # `cascade` block instead of a flat `categories` list.
        assert re.search(r"^\s*cascade\s*:", front, re.M), "_index.md 缺少 cascade 块"
        assert re.search(r"^\s*categories\s*:", front, re.M), "_index.md 的 cascade 缺少 categories"
    else:
        for field in ("date", "categories"):
            assert re.search(rf"^\s*{field}\s*:", front, re.M), f"{path.name} 的 front matter 缺少 {field}"


def _link_resolves(target: Path) -> bool:
    """A Hugo ``index.html`` link stands for the ``index.md`` bundle next to it."""
    if target.exists():
        return True
    if target.suffix == ".html":
        return target.with_suffix(".md").exists()
    return False


@pytest.mark.parametrize("path", _doc_paths(), ids=lambda p: p.relative_to(SECTION).as_posix())
def test_relative_links_resolve(path: Path):
    text = path.read_text(encoding="utf-8")
    broken: list[str] = []
    for target in re.findall(r"\]\((\.{1,2}/[^)#]*?\.html)\)", text):
        if not _link_resolves((path.parent / target).resolve()):
            broken.append(target)
    assert not broken, f"{path.name} 存在失效相对链接: {broken}"


@pytest.mark.parametrize("path", _doc_paths(), ids=lambda p: p.relative_to(SECTION).as_posix())
def test_toc_anchors_point_at_real_headings(path: Path):
    text = path.read_text(encoding="utf-8")
    anchors = re.findall(r"\[([^\]]+)\]\(#([^)]+)\)", text)
    if not anchors:
        pytest.skip(f"{path.name} 没有目录")

    ids = set(_heading_ids(text))
    missing = [
        (label, anchor)
        for label, anchor in anchors
        if _slugize(_strip_quotes(anchor)) not in ids
    ]
    assert not missing, (
        f"{path.name} 的目录锚点指向不存在的标题: {missing}\n"
        f"实际可用的标题 id: {sorted(ids)}"
    )


def test_every_doc_is_reachable_from_the_section_index(docs):
    index = next((body for path, body in docs if path.name == "_index.md"), "")
    for path, _ in docs:
        if path.name == "_index.md":
            continue
        bundle = path.relative_to(SECTION).with_suffix("").as_posix()
        assert f"./{bundle}" in index, f"./{bundle} 没有出现在 gaokao 小节索引里"


@pytest.mark.parametrize("path", _doc_paths(), ids=lambda p: p.relative_to(SECTION).as_posix())
def test_no_replacement_characters(path: Path):
    """U+FFFD means a byte sequence was decoded as garbage.

    It renders as a tofu box on the site and, worse, silently breaks any
    table-of-contents anchor that contains the corrupted character -- the
    link still looks clickable and just lands at the top of the page.
    """
    text = path.read_text(encoding="utf-8")
    lines = [n for n, line in enumerate(text.split("\n"), 1) if "\ufffd" in line]
    assert not lines, (
        f"{path.name} 第 {lines} 行含 U+FFFD 替换字符（写入时字节解码损坏）：\n"
        + "\n".join(text.split("\n")[n - 1] for n in lines[:5])
    )
