import re

from toutiao.capability import default_capability_path, load_capability
from toutiao.contract import ToutiaoArticle, slice_post
from toutiao.mdparse import load_post
from toutiao.render import render

LIMITS = load_capability(default_capability_path()).limits

# A real HTML tag has an element name: the ones this renderer emits, plus
# the ones a mangled editor might leave behind.  A bare "<" is text
# ("a < b"), and so is a placeholder that only looks like a tag
# ("<db_oid>"): neither is markup, and neither may be called one.
_TAG = re.compile(r"</?([A-Za-z][A-Za-z0-9]*)[^>]*>")
_ELEMENTS = frozenset((
    "a", "b", "blockquote", "br", "code", "div", "em", "font", "h1", "h2",
    "h3", "h4", "h5", "h6", "i", "img", "li", "ol", "p", "pre", "script",
    "span", "strong", "style", "table", "td", "tr", "ul",
))

# The lines that have broken the emphasis rules in one way or another.
# Every one of them has to render to well formed markup.
_NASTY_EMPHASIS = (
    "a ****b**** c",
    "****x****",
    "***x***",
    "**a *b* c**",
    "*a **b** c*",
    "~~a **b** c~~",
    "**a ~~b** c~~",
    "*a ~~b* c~~",
    "**a****b**",
    "*a**b*c**d*",
    "****",
    "**",
    "*",
    "_",
    "__",
    "~~~~",
    "****1**收藏**",
    "a **b** c ****d**** e",
)


def _tags_in(text):
    """The HTML tags in a text -- the real ones, not the placeholders."""
    return [
        match.group(0)
        for match in _TAG.finditer(text)
        if match.group(1).lower() in _ELEMENTS
    ]


def _wellformed(markup):
    """The problems in a piece of markup, if its tags do not nest.

    A stack of the tags that are open: a closing tag has to close the
    one on top of it, and every tag has to be closed.  Returns a list of
    problems -- empty when the markup is well formed.
    """
    problems = []
    stack = []
    for match in _TAG.finditer(markup):
        raw = match.group(0)
        name = match.group(1).lower()
        if raw.startswith("</"):
            if not stack:
                problems.append("close without open: {}".format(raw))
            elif stack[-1] != name:
                problems.append("</{}> closes <{}>".format(name, stack[-1]))
                stack.pop()
            else:
                stack.pop()
        else:
            stack.append(name)
    if stack:
        problems.append("never closed: {}".format(stack))
    return problems




def _article(body="段落。", **kwargs):
    defaults = dict(
        content_id="db/demo",
        title="标题",
        digest="摘要",
        body=body,
        images=(),
        title_truncated=False,
        body_truncated=False,
        dropped_links=0,
        notes=(),
    )
    defaults.update(kwargs)
    return ToutiaoArticle(**defaults)


# ---- 块级结构 ----

def test_paragraph_becomes_a_styled_p():
    result = render(_article(body="正文内容"))
    assert "<p style=" in result.html
    assert "正文内容" in result.html


def test_heading_becomes_h2():
    result = render(_article(body="## 小标题"))
    assert "<h2 style=" in result.html
    assert "小标题" in result.html
    assert "##" not in result.html


def test_list_items_become_bulleted_paragraphs():
    result = render(_article(body="- 第一条\n- 第二条"))
    assert "• 第一条" in result.html
    assert "• 第二条" in result.html


def test_a_list_marker_is_not_left_in_the_html():
    """列表项的 `- ` 是切片的记号，不是正文 —— 它不许留在产物里。"""
    result = render(_article(body="- 第一条"))
    assert "- 第一条" not in result.html
    assert "• 第一条" in result.html


def test_a_standalone_marker_is_centred():
    """独占一行的图片占位符是一整段，居中显示，人一眼能找到插图的位置。"""
    result = render(_article(body="【图1】"))
    assert "text-align:center" in result.html
    assert "【图1】" in result.html


def test_an_empty_body_renders_nothing():
    """正文空了，产物就空 —— 不许凭空造出一段。"""
    result = render(_article(body=""))
    assert result.html == ""
    assert result.text == ""
    assert result.image_markers == ()


def test_render_is_deterministic():
    """同一篇文章渲染两次要一模一样 —— 出包流程会重跑一次来核对。"""
    article = _article(body="## 标题\n\n段落里有 **粗体**。\n\n【图1】")
    assert render(article) == render(article)


# ---- 行内 markdown ----

def test_inline_markdown_becomes_html():
    result = render(_article(body="**粗体** 与 `代码`"))
    assert "<strong>粗体</strong>" in result.html
    assert "<code" in result.html
    assert "代码</code>" in result.html
    assert "**粗体**" not in result.html


def test_italic_becomes_em():
    result = render(_article(body="这是*斜体*字"))
    assert "<em>斜体</em>" in result.html
    assert "*斜体*" not in result.html


def test_arithmetic_with_stars_is_not_italic():
    """`2 * 3 * 4` 是算式，不是强调 —— 把它变成斜体就是改错了原文。"""
    result = render(_article(body="2 * 3 * 4"))
    assert "<em>" not in result.html
    assert "2 * 3 * 4" in result.html


def test_bold_italic_becomes_both():
    """`***x***` 是粗体加斜体 —— 只做成粗体会剩下两个孤零零的星号。"""
    result = render(_article(body="***dcf_write***"))
    assert "<strong><em>dcf_write</em></strong>" in result.html
    assert "*" not in result.html


def test_double_underscore_becomes_bold():
    result = render(_article(body="__write()__"))
    assert "<strong>write()</strong>" in result.html
    assert "__" not in result.html


def test_single_underscore_becomes_italic():
    result = render(_article(body="标题很朴素： _Attention Is All You Need_ 。"))
    assert "<em>Attention Is All You Need</em>" in result.html
    assert "_Attention" not in result.html


def test_an_underscore_inside_a_word_is_not_italic():
    """`snake_case_name` 是标识符，不是强调 —— 斜体化它就是改错了原文。"""
    result = render(_article(body="字段名是 user_name，别写成斜体。"))
    assert "<em>" not in result.html
    assert "user_name" in result.html


def test_a_blank_of_three_underscores_is_not_italic():
    """`___` 是填空的下划线，不是强调。"""
    result = render(_article(body="风险最高的是 ___"))
    assert "<em>" not in result.html
    assert "___" in result.html


def test_an_escaped_underscore_is_not_a_delimiter():
    """`\\__attribute__` 里的反斜杠说明作者要的是字面下划线。

    反斜杠只对「标点」认，认的是一个字符，不是一类：它吃掉自己，
    后面的下划线就按普通的下划线规则算。博客自己的渲染器（marked）
    也是这个结果 —— `_<em>attribute</em>_`。
    """
    result = render(_article(body="用 \\__attribute__((constructor)) 特性。"))
    assert "<strong>" not in result.html
    assert "_<em>attribute</em>_" in result.html


def test_a_backslash_escapes_any_punctuation():
    """`\\-` `\\*` `\\[` 跟 `\\=` 是一回事 —— 反斜杠的口径只有一个。"""
    result = render(_article(body="参数是 \\- \\* \\[ \\= 四种。"))
    assert "\\" not in result.html
    assert "参数是 - * [ = 四种。" in result.html


def test_strikethrough_keeps_the_words_and_drops_the_markers():
    """删除线没有对应的标签可用 —— 编辑器不认它，标记去掉，字留下。"""
    result = render(_article(body="~~1.页眉~~"))
    assert "1.页眉" in result.html
    assert "~~" not in result.html
    assert "<del" not in result.html
    assert "<s>" not in result.html
    # 也不能拿别的标签顶上去 —— 那是在说一件文章没说的事。
    assert "<em>" not in result.html
    assert "<strong>" not in result.html
    assert result.text == "1.页眉"


def test_c_code_is_not_italic():
    """C 代码里的 `*` 是指针，不是强调 —— 斜体化它就是改错了原文。

    ``void *data; int (*apply)(...)`` 里那一对星号，一个在括号前、
    一个在括号后：按 CommonMark 的左右侧判定，它们都不是收尾的定界符，
    这一行因此原样留下。博客自己的渲染器（marked）也是这个结果。
    """
    body = "struct raft_fsm { void *data; int (*apply)(struct raft_fsm *fsm); }"
    result = render(_article(body=body))
    assert "<em>" not in result.html
    assert "void *data; int (*apply)(struct raft_fsm *fsm);" in result.html


def test_a_bold_whose_closer_follows_punctuation_stays_literal():
    """`**数据：**描述` 里的星号不是收尾的定界符 —— 它是正文，不是标记。

    博客自己的渲染器（marked）也把这句原样留下；头条版要跟博客一样，
    不能比博客多强调一次。
    """
    result = render(_article(body="**数据：**描述客观事物"))
    assert "<strong>" not in result.html
    assert "**数据：**描述客观事物" in result.html


def test_a_bold_at_the_end_of_a_sentence_is_converted():
    """`**加粗**后面` 里的星号是收尾的定界符 —— 它就该变成粗体。"""
    result = render(_article(body="**加粗**后面紧跟文字"))
    assert "<strong>加粗</strong>后面紧跟文字" in result.html


def test_an_autolink_loses_its_angle_brackets():
    """`<https://a>` 的尖括号是链接标记 —— 链接不带走，地址留下。

    博客把它渲染成一个链接（可见文字就是地址），头条版不许有链接，
    于是只剩地址本身（设计文档 §3.4：正文里没有可点击 URL）。
    """
    result = render(_article(body="一键直达: <https://example.com/a>"))
    assert "一键直达: https://example.com/a" in result.html
    assert "&lt;https://example.com/a&gt;" not in result.html
    assert "https://example.com/a" in result.text


# ---- 强调：定界符与嵌套 ----

def test_the_html_is_well_formed_for_any_emphasis():
    """标签必须良构嵌套 —— 不管正文写成什么样。

    这是一条通用守卫，不是给某一行写的。任何把强调拆成多遍、或者
    让一条规则看见另一条规则产出的标签的改法，都会被它抓住：那些
    标签会交叉，闭标签就对不上开标签。
    """
    for body in _NASTY_EMPHASIS:
        result = render(_article(body=body))
        assert _wellformed(result.html) == [], (body, result.html)


def test_four_stars_do_not_produce_broken_html():
    """`a ****b**** c` 曾经产出嵌套错乱的标签。

    错乱的写法是 `<strong><em><em>b</em></strong></em>`：闭标签的
    顺序对不上开标签的顺序。头条版要粘进编辑器，编辑器未必按 HTML5
    的规则自愈，所以它必须是良构的。
    """
    result = render(_article(body="a ****b**** c"))
    assert _wellformed(result.html) == []
    assert "<strong>" in result.html
    assert "b" in result.html


# ---- 转义 ----

def test_html_is_escaped():
    result = render(_article(body="a < b & c"))
    assert "a &lt; b &amp; c" in result.html
    assert "< b" not in result.html


def test_angle_brackets_outside_the_whitelist_are_escaped():
    """`<db_oid>` 不是标签，但它是正文 —— 原样留着可以，混进 HTML 不行。"""
    result = render(_article(body="占位符 <db_oid> 要留着。"))
    assert "&lt;db_oid&gt;" in result.html
    assert "<db_oid>" not in result.html
    assert "占位符" in result.html


def test_ampersand_is_escaped_once():
    """正文里的 `&amp;` 是正文里的五个字符 —— 不能被解码成 `&` 再转义。"""
    result = render(_article(body="AT&T 与 &amp; 的写法"))
    assert "AT&amp;T" in result.html
    assert "&amp;amp;" in result.html


def test_no_class_attributes():
    result = render(_article(body="段落\n\n## 标题"))
    assert "class=" not in result.html


def test_no_style_block():
    """样式只能内联 —— 编辑器会把 `<style>` 块丢掉。"""
    result = render(_article(body="段落"))
    assert "<style" not in result.html
    assert "style=\"" in result.html


# ---- 行内代码 ----

def test_bold_inside_inline_code_is_not_bold():
    """代码里的 `**` 是两个星号，不是粗体。

    先转义再整体跑强调规则的做法会把 ```**x**``` 变成粗体代码：
    代码示例一旦被强调，就不再说明它自己说明的东西了。
    """
    result = render(_article(body="命令是 `**x**` 这样。"))
    assert "<strong>" not in result.html
    assert "<code" in result.html
    assert "**x**</code>" in result.html


def test_italic_inside_inline_code_is_not_italic():
    result = render(_article(body="命令是 `*x*` 这样。"))
    assert "<em>" not in result.html
    assert "*x*</code>" in result.html


def test_angle_brackets_inside_inline_code_are_escaped():
    """行内代码里的 `<...>` 要转义 —— 它是代码，不是标签。"""
    result = render(_article(body="路径是 `base/<db_oid>/`"))
    assert "<db_oid>" not in result.html
    assert "base/&lt;db_oid&gt;/</code>" in result.html


def test_code_content_is_not_escaped_twice():
    """代码里的 `&` 只转义一次 —— 转两次就成了 `&amp;amp;`。"""
    result = render(_article(body="`a & b`"))
    assert "a &amp; b</code>" in result.html
    assert "&amp;amp;" not in result.html


# ---- 图片占位符 ----

def test_image_markers_are_listed():
    result = render(_article(body="【图1】\n\n段落。"))
    assert result.image_markers == ("【图1】",)
    assert "【图1】" in result.html
    assert "【图1】" in result.text


def test_an_inline_image_marker_is_listed():
    """行内图也是图，也占一个位置 —— 少了它，出包流程就少一张图。"""
    result = render(_article(body="其架构如下图【图1】。"))
    assert result.image_markers == ("【图1】",)
    assert "【图1】" in result.html
    assert "【图1】" in result.text


def test_markers_are_listed_in_document_order():
    result = render(_article(body="【图1】\n\n段落。\n\n【图2】\n\n再有【图3】。"))
    assert result.image_markers == ("【图1】", "【图2】", "【图3】")


def test_a_marker_inside_code_is_not_a_marker():
    """代码里的占位符是示例，不是真的插图位置。"""
    result = render(_article(body="占位符长这样：`【图1】`"))
    assert result.image_markers == ()
    assert "【图1】" in result.html


def test_a_repeated_marker_is_listed_once():
    """同一个位置出现两次，槽位还是一个 —— 列表是槽位集合，不是字数。"""
    result = render(_article(body="【图1】\n\n这里再说一次【图1】。"))
    assert result.image_markers == ("【图1】",)


# ---- 纯文本兜底 ----

def test_plain_text_has_no_tags():
    result = render(_article(body="## 标题\n\n段落。"))
    assert _tags_in(result.text) == []
    assert "标题" in result.text


def test_plain_text_keeps_the_words_but_not_the_markers():
    """纯文本是要粘给人看的 —— 星号和反引号留在里面，读者会看到一堆符号。"""
    result = render(_article(body="**粗体** 与 *斜体* 与 `代码`"))
    assert result.text == "粗体 与 斜体 与 代码"


def test_plain_text_has_no_heading_hashes():
    result = render(_article(body="## 小标题"))
    assert result.text == "小标题"


def test_plain_text_keeps_one_line_per_list_item():
    """连续的列表项在纯文本里是一份清单，不是一段段空行隔开的散文。"""
    result = render(_article(body="- 第一条\n- 第二条"))
    assert result.text == "• 第一条\n• 第二条"


def test_plain_text_keeps_the_angle_bracket_placeholders():
    """纯文本不是 HTML：`<db_oid>` 是正文，原样留着，不许变成 `&lt;db_oid&gt;`。"""
    result = render(_article(body="占位符 <db_oid> 要留着。"))
    assert "<db_oid>" in result.text
    assert "&lt;" not in result.text


def test_plain_text_and_html_carry_the_same_paragraphs():
    """两份产物说的是同一件事 —— 段落数必须一样多。"""
    body = "## 标题\n\n第一段。\n\n- 第一条\n\n第二段。\n\n【图1】"
    result = render(_article(body=body))
    assert result.text.split("\n\n") == [
        "标题",
        "第一段。",
        "• 第一条",
        "第二段。",
        "【图1】",
    ]
    assert result.html.count("<p ") + result.html.count("<h2 ") == 5


# ---- 端到端 ----

_MOTHER = """---
title: 渲染链路测试
description: 用来钉住渲染产物的母稿
---

# 文章标题不进正文

## 小节一

这是**粗体**与*斜体*，还有 `code` 与 `base/<db_oid>/`。

- 列表一
- 列表二

其架构如下图![](images/a.png)。

![独占图](images/b.png)

| 列 | 列 |
| --- | --- |
| 1 | 2 |

```python
print("dropped")
```

[链接文字](https://example.com/a)
"""


def _write_mother(tmp_path):
    posts = tmp_path / "_posts"
    posts.mkdir()
    path = posts / "demo.md"
    path.write_text(_MOTHER, encoding="utf-8")
    return load_post(path, posts)


def test_the_whole_chain_produces_the_expected_html(tmp_path):
    post = _write_mother(tmp_path)
    sliced = slice_post(post, LIMITS)
    assert sliced.article is not None
    result = render(sliced.article)

    assert result.html == "\n".join([
        '<h2 style="margin:24px 0 12px 0;font-size:18px;font-weight:bold;color:#222222;">小节一</h2>',
        '<p style="margin:0 0 16px 0;line-height:1.75;font-size:16px;color:#333333;">'
        '这是<strong>粗体</strong>与<em>斜体</em>，还有 '
        '<code style="padding:1px 4px;background-color:#f5f5f5;border-radius:3px;'
        'font-family:monospace;font-size:14px;color:#c7254e;">code</code> 与 '
        '<code style="padding:1px 4px;background-color:#f5f5f5;border-radius:3px;'
        'font-family:monospace;font-size:14px;color:#c7254e;">base/&lt;db_oid&gt;/</code>。</p>',
        '<p style="margin:0 0 8px 0;padding-left:12px;line-height:1.75;font-size:16px;color:#333333;">• 列表一</p>',
        '<p style="margin:0 0 8px 0;padding-left:12px;line-height:1.75;font-size:16px;color:#333333;">• 列表二</p>',
        '<p style="margin:0 0 16px 0;line-height:1.75;font-size:16px;color:#333333;">其架构如下图【图1】。</p>',
        '<p style="margin:16px 0;text-align:center;color:#999999;font-size:14px;">【图2】</p>',
        '<p style="margin:0 0 16px 0;line-height:1.75;font-size:16px;color:#333333;">链接文字</p>',
        '<p style="margin:0 0 16px 0;line-height:1.75;font-size:16px;color:#333333;">完整版见 growdu.cn</p>',
    ])


def test_the_whole_chain_produces_the_expected_text(tmp_path):
    post = _write_mother(tmp_path)
    sliced = slice_post(post, LIMITS)
    result = render(sliced.article)

    assert result.text == "\n\n".join([
        "小节一",
        "这是粗体与斜体，还有 code 与 base/<db_oid>/。",
        "• 列表一\n• 列表二",
        "其架构如下图【图1】。",
        "【图2】",
        "链接文字",
        "完整版见 growdu.cn",
    ])


def test_the_whole_chain_drops_what_the_slicer_dropped(tmp_path):
    """表格、代码围栏、一级标题、链接 URL 都不许进产物。"""
    post = _write_mother(tmp_path)
    sliced = slice_post(post, LIMITS)
    result = render(sliced.article)

    assert "print" not in result.html
    assert "| 列 |" not in result.html
    assert "文章标题不进正文" not in result.html
    assert "https://example.com/a" not in result.html
    assert "链接文字" in result.html


def test_the_whole_chain_has_one_marker_per_picture(tmp_path):
    """占位符与图片一一对应 —— 出包流程靠这条核对「几个槽位、几张图」。"""
    post = _write_mother(tmp_path)
    sliced = slice_post(post, LIMITS)
    article = sliced.article
    result = render(article)

    assert article.images == ("images/a.png", "images/b.png")
    assert result.image_markers == ("【图1】", "【图2】")
    assert len(result.image_markers) == len(article.images)
    for marker in result.image_markers:
        assert marker in result.html
        assert marker in result.text


def test_the_whole_chain_produces_a_paste_ready_html(tmp_path):
    """粘进编辑器的东西：内联样式、没有 class、没有 style 块。"""
    post = _write_mother(tmp_path)
    result = render(slice_post(post, LIMITS).article)

    assert "class=" not in result.html
    assert "<style" not in result.html
    assert result.html.startswith("<h2 style=")
    assert _TAG.sub("", result.html).strip() != ""


def test_the_whole_chain_text_has_no_tags(tmp_path):
    post = _write_mother(tmp_path)
    result = render(slice_post(post, LIMITS).article)

    assert _tags_in(result.text) == []
    assert "完整版见 growdu.cn" in result.text

