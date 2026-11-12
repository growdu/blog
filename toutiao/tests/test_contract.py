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


def test_only_the_first_three_images_are_kept():
    body = "\n\n".join("![图{}](images/{}.png)".format(i, i) for i in range(1, 6))
    result = slice_post(_post(body=body), LIMITS)
    assert len(result.article.images) == 3
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
