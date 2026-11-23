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


def _read(path: Path) -> str:
    assert path.is_file(), "找不到 {}".format(path)
    return path.read_text(encoding="utf-8")


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
        "首页页脚的行距没压 —— 版权那四行省不出图标那行的位置"
    )
