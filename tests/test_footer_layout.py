"""页脚：版权那句要在页面正中，页脚别摊开。

**为什么**：2026-11-23 首页放宽到 1560px 之后，页脚跟着摊开了 ——
版权那行字被塞在左边八列里（页面的四分之一处），社交图标甩到最右边，
中间空一大片。用户的话：「页脚的 copyright 没居中，然后页脚也太宽了」。

**怎么做的**（``themes/matery/source/css/tech.css``）：

* 页脚那一行改成 flex 竖排 —— 版权占一整行，社交图标落到下面一行；
* 两块各占满一行（不再是「左边三分之二 + 右边三分之一」）；
* 内容收在 860px 宽里居中 —— 版权那几行字加起来不到 500px，摊到
  1560px 上只是把两堆东西推得更远。页脚的绿底还是满宽的。

**这里守的是四件事**：

1. 页脚那一行必须是 **flex 竖排** —— materialize 的 ``.row`` 不是 flex，
   里面的列是 ``float: left``，光写 ``flex-direction`` 没用，列还是并排；
2. 版权和图标各自 **占满一行** —— 选择器里必须带上 ``.container.row``：
   materialize 那条是 ``.row .col.m8``（三个类），不带就压不住它；
3. 页脚内容 **有上限**（≤ 1000px）且 **居中**；
4. 首页「正好一屏」没有因为页脚变高而破掉 —— 首页的页脚留白收紧了。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TECH_CSS = REPO / "themes" / "matery" / "source" / "css" / "tech.css"
FOOTER_EJS = REPO / "themes" / "matery" / "layout" / "_partial" / "footer.ejs"


def _read(path: Path) -> str:
    assert path.is_file(), "找不到 {}".format(path)
    return path.read_text(encoding="utf-8")


def _strip_ejs_comments(ejs: str) -> str:
    """把 ``<%# ... %>`` 注释去掉 —— 注释里写着「原来用 <br>」，别当成真标签。"""
    return re.sub(r"<%#.*?%>", "", ejs, flags=re.S)


def _copy_right(ejs: str) -> str:
    """取 copy-right 那个容器的内容。"""
    m = re.search(r'<div class="col s12 m8 l8 copy-right">(.*?)</div>\s*\n\s*<div class="col s12 m4 l4 social-link',
                  ejs, re.S)
    assert m, "footer.ejs 里找不到 copy-right 容器"
    return m.group(1)


def _strip_css_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _rule(css: str, selector: str) -> str:
    """取一条规则的声明块（选择器后面必须紧跟 ``{``）。"""
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css, re.S)
    assert m, "tech.css 里没有 {}".format(selector)
    return m.group(1)


def _decl(css: str, selector: str, prop: str) -> str:
    m = re.search(re.escape(prop) + r"\s*:\s*([^;]+)", _rule(css, selector))
    assert m, "{} 里没有 {}".format(selector, prop)
    return m.group(1).strip()


def test_the_footer_row_stacks_the_copyright_above_the_icons():
    """版权一行、图标一行 —— 竖着排。

    materialize 的 ``.row`` **不是 flex 容器**（里面的列是
    ``float: left``），所以光写 ``flex-direction: column`` 一点用都没有：
    两块还是并排浮着，版权那句依旧被挤在左边三分之二里。
    """
    css = _strip_css_comments(_read(TECH_CSS))
    row = _rule(css, ".page-footer .container.row")

    assert re.search(r"display\s*:\s*flex", row), (
        "页脚那一行不是 flex 容器 —— materialize 的 .row 是 float 布局，"
        "两块会并排浮着"
    )
    assert re.search(r"flex-direction\s*:\s*column", row), (
        "页脚那一行不是竖着排 —— 版权和图标会并排，版权那句还是不在正中"
    )


def test_the_copyright_and_the_icons_each_take_a_full_row():
    """两块各占满一行。

    选择器里必须带上 ``.container.row``：materialize 那条是
    ``.row .col.m8``（**三个**类，比 ``.page-footer .copy-right`` 特异性高），
    不带就压不住它 —— 版权那块还是三分之二宽。
    """
    css = _strip_css_comments(_read(TECH_CSS))
    block = _rule(css, ".page-footer .container.row .copy-right,\n.page-footer .container.row .social-link")

    assert re.search(r"width\s*:\s*100%", block), (
        "版权那块没有占满一行 —— 文字还在半边里居中，不在页面正中"
    )
    assert re.search(r"float\s*:\s*none", block), (
        "float 没清掉 —— 块还是浮着，并排"
    )


def test_the_footer_content_is_capped_and_centered():
    """页脚的内容不能摊到整个页面那么宽。

    版权那几行字（版权、字数、运行天数、ICP 备案）加起来不到 500px，
    摊到 1560px 上只是把两堆东西推得更远。内容收在 860px 里居中 ——
    绿底还是满宽的，收窄的只是里面的内容。
    """
    css = _strip_css_comments(_read(TECH_CSS))
    row = _rule(css, ".page-footer .container.row")

    max_width = _decl(css, ".page-footer .container.row", "max-width")
    m = re.search(r"([\d.]+)px", max_width)
    assert m, "页脚内容区没有宽度上限：{}".format(max_width)
    assert float(m.group(1)) <= 1000, (
        "页脚内容区放宽到 {}px 了 —— 两堆东西离得太远".format(m.group(1))
    )
    assert float(m.group(1)) >= 600, (
        "页脚内容区收到 {}px 了 —— 那几行字会折行".format(m.group(1))
    )
    assert re.search(r"align-items\s*:\s*center", row), (
        "页脚内容没有居中 —— 它会靠左"
    )


def test_the_homepage_footer_gives_its_height_back_to_the_cards():
    """首页正好一屏 —— 页脚变高了，留白得收回来。

    社交图标落到版权下面一行，页脚高了三四十像素。首页的页脚上下留白
    因此收紧（materialize 默认 ``padding-top: 20px``），省下来的高度还给
    下面的卡片。
    """
    css = _strip_css_comments(_read(TECH_CSS))

    top = _decl(css, "body.home-page .page-footer", "padding-top")
    m = re.search(r"([\d.]+)px", top)
    assert m, "首页页脚的上留白不是一个 px 值：{}".format(top)
    assert float(m.group(1)) <= 10, (
        "首页页脚的上留白还是 {}px —— 页脚一高，首页就装不下一屏了".format(top)
    )
    assert "line-height" in _rule(css, "body.home-page .page-footer .copy-right"), (
        "首页页脚的行距没压 —— 版权那几行省不出图标那行的位置"
    )


def test_the_copyright_block_is_at_most_two_lines():
    """版权那块最多两行：一行备案号，一行「其他的」。

    原来那块用 ``<br>`` 硬换行，撑出四行高：版权、总字数、**一行空的**
    （``time.enable`` 关着，那个 ``<br>`` 前面没东西）、备案号。
    用户的话：「这个最多只能有两行，一行是备案号，另一行是其他」。
    """
    ejs = _strip_ejs_comments(_read(FOOTER_EJS))
    block = _copy_right(ejs)

    assert "<br>" not in block, (
        "版权那块还有 <br> 硬换行 —— 行数不受控，而且空开关着的选项会留一行空的"
    )
    assert block.count("<div") == 2, (
        "版权那块应该只有两个块（main + icp），现在是 {} 个".format(block.count("<div"))
    )


def test_the_icp_number_gets_its_own_line():
    """备案号单独一行，其他内容在另一行。"""
    ejs = _strip_ejs_comments(_read(FOOTER_EJS))
    block = _copy_right(ejs)

    main = re.search(r'<div class="copy-right__main">(.*?)\n\s*</div>', block, re.S)
    icp = re.search(r'<div class="copy-right__icp">(.*?)\n\s*</div>', block, re.S)
    assert main, "版权那块没有 .copy-right__main（放「其他的」那一行）"
    assert icp, "版权那块没有 .copy-right__icp（放备案号那一行）"

    assert "theme.icp.text" in icp.group(1), "备案号不在 .copy-right__icp 里"
    assert "theme.icp.text" not in main.group(1), "备案号还在第一行里"

    # 「其他的」都归到第一行
    for needle in ("Powered by", "siteTotalWords"):
        assert needle in main.group(1), "{} 不在第一行里".format(needle)

