from toutiao.capability import default_capability_path, load_capability
from toutiao.contract import slice_post
from toutiao.mdparse import SourcePost

LIMITS = load_capability(default_capability_path()).limits


def _post(title="标题", body="正文一段。", **fields):
    return SourcePost(
        slug="db/demo",
        title=title,
        date="2026-01-01",
        body=body,
        fields=fields,
    )


# ---- 标题 ----

def test_short_title_wins():
    post = _post(title="一个很长的标题" * 5, short_title="短标题")
    result = slice_post(post, LIMITS)
    assert result.article.title == "短标题"
    assert result.article.title_truncated is False


def test_overlong_short_title_skips_the_post():
    post = _post(title="标题", short_title="长" * 60)
    result = slice_post(post, LIMITS)
    assert result.article is None
    assert "short_title" in result.reason


def test_long_title_is_truncated_and_marked():
    post = _post(title="A" * 20 + "：" + "B" * 40)
    result = slice_post(post, LIMITS)
    assert result.article is not None
    assert result.article.title_truncated is True
    assert len(result.article.title) <= LIMITS.title_chars
    assert result.article.title == "A" * 20
    assert any("裁剪" in note for note in result.article.notes)


def test_long_title_without_a_separator_is_cut_to_the_limit():
    """标题里没有分隔符时走的是硬上限那一刀 —— 正好裁到上限。

    用带分隔符的标题测不到这一刀：`_truncate_title` 会在分隔符处提前返回，
    `title[:limit]` 那一步根本没被执行，断言就成了恒真。
    """
    post = _post(title="甲" * 45)
    result = slice_post(post, LIMITS)
    assert result.article.title == "甲" * LIMITS.title_chars
    assert len(result.article.title) == LIMITS.title_chars


# ---- 正文筛选 ----

def test_code_fences_are_dropped():
    post = _post(body="保留段。\n\n```python\nprint(1)\n```\n\n还有一段。")
    result = slice_post(post, LIMITS)
    assert "print(1)" not in result.article.body
    assert "保留段。" in result.article.body
    assert "还有一段。" in result.article.body


def test_tables_and_quotes_are_dropped():
    post = _post(body="| a | b |\n| --- | --- |\n| 1 | 2 |\n\n> 引用\n\n正文。")
    result = slice_post(post, LIMITS)
    assert "| a | b |" not in result.article.body
    assert "引用" not in result.article.body
    assert "正文。" in result.article.body


def test_inline_html_tags_are_stripped_but_the_text_stays():
    """标签是标记，标签里的文字是内容。"""
    post = _post(body='看 <font color="red">重要结论</font> 这段。')
    result = slice_post(post, LIMITS)
    assert "<font" not in result.article.body
    assert "重要结论" in result.article.body


def test_a_line_of_pure_html_is_dropped():
    post = _post(body='<div class="note">\n\n正文。')
    result = slice_post(post, LIMITS)
    assert "<div" not in result.article.body
    assert "正文。" in result.article.body


def test_a_line_of_pure_html_breaks_the_paragraph():
    """纯 HTML 行是独立的一块 —— 它断开段落，不跟正文粘在一起。"""
    post = _post(body='第一段第一行。\n<div class="note">\n第二段第二行。')
    result = slice_post(post, LIMITS)
    assert "第一段第一行。\n\n第二段第二行。" in result.article.body


def test_html_entities_are_decoded_in_blocks_that_carry_a_tag():
    post = _post(body="<b>Tom &amp; Jerry</b>")
    result = slice_post(post, LIMITS)
    assert "Tom & Jerry" in result.article.body


def test_entities_are_not_decoded_in_blocks_without_a_tag():
    """没有标签的段落不做实体解码 —— 别把不是 HTML 的文本改掉。"""
    post = _post(body="AT&T 与 &amp; 的写法")
    result = slice_post(post, LIMITS)
    assert "&amp;" in result.article.body


def test_shallow_headings_are_kept_and_deep_ones_dropped():
    post = _post(body="## 二级\n\n三级\n\n#### 四级\n\n段落。")
    result = slice_post(post, LIMITS)
    assert "## 二级" in result.article.body
    assert "四级" not in result.article.body


def test_heading_levels_are_normalized_to_h2():
    """`##` / `###` 统一输出成 `##`；`#`（文章标题）不进正文。"""
    post = _post(body="# 大标题\n\n### 小节\n\n段落。")
    result = slice_post(post, LIMITS)
    lines = result.article.body.splitlines()
    assert "## 小节" in lines
    assert "### 小节" not in lines
    assert "大标题" not in result.article.body


def test_lists_are_kept():
    post = _post(body="- 第一条\n- 第二条\n\n段落。")
    result = slice_post(post, LIMITS)
    assert "- 第一条" in result.article.body


def test_wrapped_chinese_lines_are_joined_without_a_space():
    """中文软换行合并后中间不留空格。"""
    post = _post(body="这是一段\n中文正文。")
    result = slice_post(post, LIMITS)
    assert "这是一段中文正文。" in result.article.body


def test_wrapped_english_lines_are_joined_with_a_space():
    """非中文的软换行合并后留一个空格。"""
    post = _post(body="this is a\nwrapped line")
    result = slice_post(post, LIMITS)
    assert "this is a wrapped line" in result.article.body


def test_ordered_lists_are_normalized_to_dashes():
    """有序列表项统一输出成 `- `。"""
    post = _post(body="1. 第一条\n2. 第二条\n\n段落。")
    result = slice_post(post, LIMITS)
    assert "- 第一条" in result.article.body
    assert "- 第二条" in result.article.body
    assert "1. 第一条" not in result.article.body


# ---- 图片 ----

def test_images_become_markers():
    post = _post(body="![甲](images/a.png)\n\n段落。\n\n![乙](images/b.png)")
    result = slice_post(post, LIMITS)
    assert result.article.images == ("images/a.png", "images/b.png")
    assert "【图1】" in result.article.body
    assert "【图2】" in result.article.body
    assert "images/a.png" not in result.article.body


def test_inline_images_are_collected_and_replaced():
    """行内图片也是图：要收进 `images`，正文里换成占位符。"""
    post = _post(body="其架构如下图![](images/a.png)。\n\n段落。")
    result = slice_post(post, LIMITS)
    assert result.article.images == ("images/a.png",)
    assert "其架构如下图【图1】。" in result.article.body
    assert "images/a.png" not in result.article.body


def test_inline_and_standalone_images_share_one_numbering():
    """行内图与独占行的图共用一套编号，按正文顺序连续。"""
    post = _post(
        body="图一 ![](images/a.png)\n\n![乙](images/b.png)\n\n图三 ![](images/c.png)"
    )
    result = slice_post(post, LIMITS)
    assert result.article.images == ("images/a.png", "images/b.png", "images/c.png")
    assert "图一 【图1】" in result.article.body
    assert "【图2】" in result.article.body
    assert "图三 【图3】" in result.article.body


def test_inline_images_beyond_the_cap_are_dropped():
    """超限的行内图，占位符也要一起消失。"""
    body = "图 ![](images/a.png)\n\n图 ![](images/b.png)\n\n图 ![](images/c.png)\n\n图 ![](images/d.png)"
    result = slice_post(_post(body=body), LIMITS)
    assert len(result.article.images) == 3
    assert "【图4】" not in result.article.body
    assert "图 【图1】" in result.article.body


def test_image_path_drops_the_trailing_title():
    """`![alt](url "标题")` 里的标题不是路径的一部分，必须剥掉。"""
    post = _post(body='![甲](https://example.com/a.png "在这里插入图片描述")')
    result = slice_post(post, LIMITS)
    assert result.article.images == ("https://example.com/a.png",)


def test_image_path_drops_a_single_quoted_title():
    post = _post(body="![甲](https://example.com/a.png 'recover_without_timeline')")
    result = slice_post(post, LIMITS)
    assert result.article.images == ("https://example.com/a.png",)


def test_inline_image_path_drops_the_trailing_title():
    post = _post(body='其架构如下图![](images/a.png "架构图")。')
    result = slice_post(post, LIMITS)
    assert result.article.images == ("images/a.png",)


def test_only_the_first_three_images_are_kept():
    body = "\n\n".join("![图{}](images/{}.png)".format(i, i) for i in range(1, 6))
    result = slice_post(_post(body=body), LIMITS)
    assert len(result.article.images) == 3
    assert "【图1】" in result.article.body
    assert "【图4】" not in result.article.body
    assert any("只保留" in note for note in result.article.notes)


def test_image_only_post_falls_back_to_the_title():
    """整篇只有图时没有首段可摘，兜底用文章标题（不是图占位符）。"""
    result = slice_post(
        _post(title="图集标题", body="![甲](images/a.png)\n\n![乙](images/b.png)"), LIMITS
    )
    assert result.article is not None
    assert result.article.digest == "图集标题"


# ---- 链接降级 ----

def test_links_become_plain_text():
    post = _post(body="看 [这篇](https://example.com/a) 的说明。")
    result = slice_post(post, LIMITS)
    assert "https://example.com/a" not in result.article.body
    assert "这篇" in result.article.body
    assert result.article.dropped_links == 1


def test_reference_links_become_plain_text():
    """`[文字][1]` 也是链接：降级成文字，并计入 `dropped_links`。"""
    post = _post(body="看 [wiki.postgresql.org][1] 的说明。")
    result = slice_post(post, LIMITS)
    assert "[wiki.postgresql.org][1]" not in result.article.body
    assert "wiki.postgresql.org" in result.article.body
    assert result.article.dropped_links == 1


def test_reference_definitions_are_dropped():
    """引用定义行是链接定义不是正文 —— 整行丢掉，别把 URL 漏出去。"""
    post = _post(body="正文一段。\n\n[1]: https://example.com/a")
    result = slice_post(post, LIMITS)
    assert "[1]" not in result.article.body
    assert "https://example.com/a" not in result.article.body


def test_bare_urls_stay_in_the_body():
    """裸 URL 原样留着 —— 平台禁的是外链跳转代码，不是 URL 这个字符串。

    权益没开通时正文里的 URL 本来就只是文本，不会变成可点击的链接；
    被降级的只有 markdown 链接那种带链接标记的。见设计文档 §3.4。
    """
    post = _post(body="参考 https://example.com/a 这篇。")
    result = slice_post(post, LIMITS)
    assert "https://example.com/a" in result.article.body
    assert result.article.dropped_links == 0


# ---- 摘要 ----

def test_digest_prefers_description():
    result = slice_post(_post(body="正文。", description="摘要在这里"), LIMITS)
    assert result.article.digest == "摘要在这里"


def test_digest_prefers_description_over_tldr():
    """两个字段都在时 `description` 优先于 `tldr`。"""
    result = slice_post(
        _post(body="正文。", description="长摘要", tldr="短摘要"), LIMITS
    )
    assert result.article.digest == "长摘要"


def test_digest_prefers_the_first_paragraph_over_the_title():
    """正文有段落时用首段 —— 标题只是兜底，不参与竞争。"""
    result = slice_post(
        _post(title="文章标题", body="正文第一段。\n\n正文第二段。"), LIMITS
    )
    assert result.article.digest == "正文第一段。"


def test_digest_uses_the_first_list_item_when_the_body_starts_with_a_list():
    """正文以列表开头时，摘要取第一条列表项的文字（去掉 `- ` 前缀）。

    这是有意为之：跳过列表去找第一段散文，在「整篇只有列表」的母稿上会
    直接产出空摘要，反而更糟。列表项的文字总比空摘要有信息量。
    """
    result = slice_post(
        _post(title="文章标题", body="- 第一条\n\n这是一段散文。"), LIMITS
    )
    assert result.article.digest == "第一条"
    assert result.article.digest != "这是一段散文。"


def test_digest_uses_the_first_list_item_when_the_body_is_only_a_list():
    """整篇只有列表时，摘要还是第一条列表项的文字，不会空着。"""
    result = slice_post(_post(title="文章标题", body="- 第一条\n- 第二条"), LIMITS)
    assert result.article.digest == "第一条"


def test_empty_title_and_no_paragraph_is_skipped():
    """标题也空着、正文又没有段落时，跳过该篇并记下原因。"""
    result = slice_post(_post(title="", body="## 只有小标题"), LIMITS)
    assert result.article is None
    assert result.reason
    assert "标题" in result.reason


def test_title_truncated_to_nothing_is_skipped():
    """标题全是分隔符，裁完一个字都不剩 —— 跳过该篇，不产出空标题文章。"""
    result = slice_post(_post(title="：" * 40), LIMITS)
    assert result.article is None
    assert result.reason
    assert "标题" in result.reason


def test_long_digest_is_truncated_and_noted():
    """摘要超长要裁到 `digest_chars`，并且留下记录（不静默截断）。"""
    result = slice_post(_post(body="正文。", description="摘" * 200), LIMITS)
    assert len(result.article.digest) == LIMITS.digest_chars
    assert any("摘要" in note and "裁剪" in note for note in result.article.notes)


def test_short_digest_is_not_truncated_and_not_noted():
    """摘要没超长时不裁，也不添那条多余的 note。"""
    result = slice_post(_post(body="正文。", description="短摘要"), LIMITS)
    assert result.article.digest == "短摘要"
    assert not any("摘要" in note for note in result.article.notes)


def test_digest_falls_back_to_tldr_then_first_paragraph():
    assert slice_post(_post(body="正文。", tldr="短摘要"), LIMITS).article.digest == "短摘要"
    assert slice_post(_post(body="第一段。\n\n第二段。"), LIMITS).article.digest == "第一段。"


def test_digest_skips_the_leading_heading():
    result = slice_post(_post(body="## 小标题\n\n真正的第一段。"), LIMITS)
    assert result.article.digest == "真正的第一段。"


# ---- 长度与尾巴 ----

def test_body_fits_the_limit():
    post = _post(body=("段落内容。" * 2000))
    result = slice_post(post, LIMITS)
    assert len(result.article.body) <= LIMITS.body_chars
    assert result.article.body_truncated is True


def test_long_body_is_truncated_and_noted():
    """正文超限要截断，并且留下记录（不静默截断）。"""
    result = slice_post(_post(body="段落内容。" * 2000), LIMITS)
    assert result.article.body_truncated is True
    assert any("正文" in note and "截断" in note for note in result.article.notes)


def test_body_ends_with_the_plain_site_mention():
    result = slice_post(_post(body="正文。"), LIMITS)
    assert result.article.body.endswith("完整版见 growdu.cn")
    assert "http" not in result.article.body


def test_source_url_scheme_is_stripped():
    result = slice_post(_post(body="正文。"), LIMITS, source_url="https://example.com/")
    assert result.article.body.endswith("完整版见 example.com")


# ---- 不可发 ----

def test_post_without_any_paragraph_is_skipped():
    result = slice_post(_post(body="| a | b |\n| --- | --- |\n| 1 | 2 |"), LIMITS)
    assert result.article is None
    assert result.reason
