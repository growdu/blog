from wechat.mdparse import (
    Bold,
    CodeBlock,
    Heading,
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
    parse,
    parse_inline,
)


def test_parse_splits_headings_and_paragraphs():
    blocks = parse("## 标题\n\n正文一段。\n")
    assert isinstance(blocks[0], Heading)
    assert blocks[0].level == 2
    assert isinstance(blocks[1], Paragraph)


def test_parse_reads_heading_levels():
    blocks = parse("# 一\n\n## 二\n\n### 三\n\n#### 四\n")
    assert [b.level for b in blocks] == [1, 2, 3, 4]


def test_parse_reads_fenced_code_with_language():
    blocks = parse("```sql\nSELECT 1;\n```\n")
    assert isinstance(blocks[0], CodeBlock)
    assert blocks[0].lang == "sql"
    assert blocks[0].code == "SELECT 1;"


def test_parse_keeps_fence_content_verbatim():
    blocks = parse("```text\n# not a heading\n| not | a table |\n- not a list\n```\n")
    assert blocks[0].code == "# not a heading\n| not | a table |\n- not a list"


def test_parse_reads_fence_without_language():
    blocks = parse("```\nplain\n```\n")
    assert blocks[0].lang == ""
    assert blocks[0].code == "plain"


def test_parse_reads_mermaid_fence():
    blocks = parse("```mermaid\ngraph TD;\nA-->B;\n```\n")
    assert blocks[0].lang == "mermaid"
    assert "A-->B;" in blocks[0].code


def test_parse_reads_table_with_alignment():
    blocks = parse("| a | b |\n| :--- | ---: |\n| 1 | 2 |\n")
    assert isinstance(blocks[0], Table)
    assert blocks[0].align == ["left", "right"]
    assert len(blocks[0].rows) == 1
    assert len(blocks[0].header) == 2


def test_parse_table_with_escaped_pipe():
    blocks = parse("| a | b |\n| --- | --- |\n| x \\| y | 2 |\n")
    assert len(blocks[0].rows[0]) == 2


def test_parse_reads_unordered_and_ordered_lists():
    blocks = parse("- 一\n- 二\n")
    assert isinstance(blocks[0], ListBlock)
    assert blocks[0].ordered is False
    assert len(blocks[0].items) == 2

    blocks = parse("1. 一\n2. 二\n")
    assert blocks[0].ordered is True
    assert len(blocks[0].items) == 2


def test_parse_reads_nested_list():
    blocks = parse("- 外层\n  - 内层\n")
    outer = blocks[0]
    assert isinstance(outer, ListBlock)
    assert len(outer.items) == 1
    nested = next(b for b in outer.items[0].blocks if isinstance(b, ListBlock))
    assert len(nested.items) == 1


def test_parse_reads_task_list_checkbox():
    blocks = parse("- [x] done\n- [ ] todo\n")
    assert blocks[0].items[0].checked is True
    assert blocks[0].items[1].checked is False


def test_parse_reads_blockquote_and_thematic_break():
    blocks = parse("> 引用一句\n\n---\n")
    assert isinstance(blocks[0], Quote)
    assert isinstance(blocks[1], ThematicBreak)


def test_parse_keeps_raw_html_block():
    blocks = parse('<div class="x">raw</div>\n')
    assert "raw" in blocks[0].html


def test_parse_reads_paragraph_across_lazy_lines():
    blocks = parse("第一行\n第二行\n\n下一段\n")
    assert len(blocks) == 2
    assert "第一行" in blocks[0].children[0].value
    assert "第二行" in blocks[0].children[0].value


def test_parse_inline_reads_bold_italic_code_link_image():
    inlines = parse_inline("**粗** *斜* `code` [文字](http://x.com) ![图](a.png)")
    kinds = [type(i).__name__ for i in inlines]
    assert "Bold" in kinds
    assert "Italic" in kinds
    assert "InlineCode" in kinds
    assert "Link" in kinds
    assert "Image" in kinds


def test_parse_inline_does_not_parse_markup_inside_code():
    inlines = parse_inline("`**not bold**`")
    assert any(isinstance(i, InlineCode) for i in inlines)
    assert not any(isinstance(i, Bold) for i in inlines)


def test_parse_inline_keeps_plain_text():
    assert parse_inline("普通文字") == [Text("普通文字")]


def test_parse_inline_link_carries_children():
    inlines = parse_inline("[**粗**](http://x.com)")
    link = next(i for i in inlines if isinstance(i, Link))
    assert link.target == "http://x.com"
    assert any(isinstance(c, Bold) for c in link.children)


def test_parse_inline_image_carries_alt_and_target():
    inlines = parse_inline("![说明](images/a.png)")
    image = next(i for i in inlines if isinstance(i, Image))
    assert image.alt == "说明"
    assert image.target == "images/a.png"


def test_parse_inline_italic_does_not_break_bold():
    inlines = parse_inline("**粗体**")
    bold = next(i for i in inlines if isinstance(i, Bold))
    assert not any(isinstance(c, Italic) for c in bold.children)
