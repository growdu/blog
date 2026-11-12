"""守住设计文档里的「标题转义还原：影响面」数字。

这段数字被删过一次：第十节「复制，不是共用」重写时，原先记着
「语料 561 篇里 10 篇的标题会带多余反斜杠」的那句被顺手删了，
之后再没人把它写回任何被跟踪的文件 —— 于是仓库里查不到
「该验哪 10 篇母稿」。

现在用一对标记把数字圈出来，再由本文件盯着：
整块删掉、数字改错、slug 列表截短，三种改法都要让这个用例变红。
"""

import re

DOC_RELATIVE_PATH = ("toutiao", "docs", "00-设计.md")

BEGIN = "<!-- impact:begin -->"
END = "<!-- impact:end -->"

CORPUS_TOTAL_LABEL = "母稿语料总数"
QUOTED_TITLE_LABEL = "有效标题含双引号的篇数"

EXPECTED_CORPUS_TOTAL = 561
EXPECTED_QUOTED_TITLES = 10


def _table_values(block):
    """把块里的两列表格读成 {标签: 整数}。"""
    values = {}
    for raw in block.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 2:
            continue
        label, value = cells
        if not re.fullmatch(r"\d+", value):
            continue          # 表头行与分隔行
        values[label] = int(value)
    return values


def _slugs(block):
    """块里 ``- `slug``` 形式的清单项。"""
    return re.findall(r"^-\s+`([^`]+)`\s*$", block, re.MULTILINE)


def test_design_doc_records_the_escape_impact(repo_root):
    """设计文档必须记着 561 / 10 和那 10 条 slug。

    四个断言是一份契约：标记块在、两个数字对得上、slug 条数与数字一致、
    slug 非空且不重复。任何一条被改坏，这个用例就红。
    """
    text = repo_root.joinpath(*DOC_RELATIVE_PATH).read_text(encoding="utf-8")

    assert BEGIN in text, "设计文档缺少 {} 标记块".format(BEGIN)
    assert END in text, "设计文档缺少 {} 标记块".format(END)
    start = text.index(BEGIN)
    end = text.index(END)
    assert start < end, "impact 标记块的起止顺序反了"

    block = text[start + len(BEGIN):end]
    assert block.strip(), "impact 标记块是空的"

    values = _table_values(block)
    assert values[CORPUS_TOTAL_LABEL] == EXPECTED_CORPUS_TOTAL
    assert values[QUOTED_TITLE_LABEL] == EXPECTED_QUOTED_TITLES

    slugs = _slugs(block)
    assert len(slugs) == values[QUOTED_TITLE_LABEL]
    assert all(slug.strip() for slug in slugs)
    assert len(set(slugs)) == len(slugs)
