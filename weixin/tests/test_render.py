from wechat.mdparse import parse
from wechat.render import render


def _html(markdown: str, **kwargs) -> str:
    return render(parse(markdown), **kwargs).html


def test_render_emits_inline_styles_and_no_class_attributes():
    html = _html("## 标题\n\n正文一段。\n")
    assert 'style="' in html
    assert "class=" not in html


def test_render_wraps_table_for_horizontal_scroll():
    html = _html("| a | b |\n| --- | --- |\n| 1 | 2 |\n")
    assert "overflow-x:auto" in html or "overflow-x: auto" in html
    assert "<table" in html


def test_render_collects_external_links_and_strips_anchor():
    result = render(parse("看 [这个](https://example.com/a) 链接。\n"))
    assert result.external_links == (("这个", "https://example.com/a"),)
    assert "<a " not in result.html
    assert "这个" in result.html


def test_render_appends_reference_link_block():
    html = _html("看 [这个](https://example.com/a) 链接。\n")
    assert "参考链接" in html
    assert "https://example.com/a" in html


def test_render_keeps_internal_link_text_only():
    result = render(parse("见 [站内](/2026/11/09/database/x/) 。\n"))
    assert result.external_links == ()
    assert "<a " not in result.html


def test_render_uses_image_placeholder():
    result = render(parse("![说明](images/db/x.png)\n"))
    assert result.assets == ("images/db/x.png",)
    assert result.placeholder(0) in result.html


def test_render_deduplicates_repeated_image():
    result = render(parse("![a](images/x.png)\n\n![b](images/x.png)\n"))
    assert result.assets == ("images/x.png",)
    assert result.html.count(result.placeholder(0)) == 2


def test_render_substitute_replaces_placeholders_with_urls():
    result = render(parse("![a](images/x.png)\n\n![b](images/y.png)\n"))
    html = result.substitute(["https://mmbiz.qpic.cn/1", "https://mmbiz.qpic.cn/2"])
    assert "https://mmbiz.qpic.cn/1" in html
    assert "https://mmbiz.qpic.cn/2" in html
    assert "{{img:" not in html


def test_render_substitute_replaces_every_occurrence():
    result = render(parse("![a](images/x.png)\n\n![b](images/x.png)\n"))
    html = result.substitute(["https://mmbiz.qpic.cn/1"])
    assert html.count("https://mmbiz.qpic.cn/1") == 2
    assert "{{img:" not in html


def test_render_placeholder_does_not_collide_with_prose():
    """An article that talks about the placeholder syntax must survive.

    This repository's own design notes contain literal ``{{img:0}}``
    text; a fixed placeholder would be rewritten when the real URLs are
    substituted in.
    """
    result = render(parse("占位符 {{img:0}} 和 {{img:1}} 是正文。\n"))
    html = result.substitute(["https://mmbiz.qpic.cn/1", "https://mmbiz.qpic.cn/2"])
    assert "{{img:0}}" in html
    assert "{{img:1}}" in html


def test_render_content_length_counts_html_characters():
    result = render(parse("短正文。\n"))
    assert result.content_length == len(result.html)


def test_render_gives_a_remote_image_its_own_placeholder():
    """WeChat deletes images it does not host, so a remote one needs
    a placeholder the publish step can fill with a re-hosted URL."""
    result = render(parse("![远](https://example.com/a.png)\n"))
    assert result.assets == ()
    assert result.external_images == ("https://example.com/a.png",)
    assert result.external_placeholder(0) in result.html
    assert "https://example.com/a.png" not in result.html


def test_substitute_external_replaces_the_remote_placeholder():
    result = render(parse("![远](https://example.com/a.png)\n"))
    html = result.substitute_external(["https://mmbiz.qpic.cn/1"])
    assert "https://mmbiz.qpic.cn/1" in html
    assert "{{ext:" not in html


def test_substitute_external_falls_back_to_a_visible_note():
    """A picture that cannot be fetched leaves a note, never a gap."""
    result = render(parse("![远](https://example.com/a.png)\n"))
    html = result.substitute_external([None], fallback="<p>原图未能转存</p>")
    assert "<p>原图未能转存</p>" in html
    assert "{{ext:" not in html


def test_local_and_remote_images_use_separate_placeholders():
    result = render(parse("![本](images/a.png)\n\n![远](https://example.com/b.png)\n"))
    assert result.assets == ("images/a.png",)
    assert result.external_images == ("https://example.com/b.png",)
    html = result.substitute(["https://mmbiz.qpic.cn/local"])
    html = result.substitute_external(
        ["https://mmbiz.qpic.cn/remote"], fallback="", html=html)
    assert "https://mmbiz.qpic.cn/local" in html
    assert "https://mmbiz.qpic.cn/remote" in html
    assert "{{img:" not in html
    assert "{{ext:" not in html


def test_render_falls_back_to_source_block_when_mermaid_fails():
    html = _html("```mermaid\ngraph TD;\nA-->B;\n```\n")
    assert "图表渲染失败" in html
    assert "<pre" in html
    assert "A--&gt;B;" in html


def test_render_uses_mermaid_png_when_available(tmp_path):
    png = tmp_path / "m.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")

    class Resolver:
        def mermaid_path(self, key):
            return png

    result = render(parse("```mermaid\ngraph TD;\nA-->B;\n```\n"), resolver=Resolver())
    assert result.placeholder(0) in result.html
    assert result.assets == (str(png),)
    assert "图表渲染失败" not in result.html


def test_render_styles_code_block():
    html = _html("```sql\nSELECT 1;\n```\n")
    assert "<pre" in html
    assert "overflow" in html


def test_render_highlights_code_with_inline_spans():
    html = _html("```sql\nSELECT 1;\n```\n")
    assert "<span" in html
    assert "class=" not in html


def test_render_marks_task_list_with_checkbox():
    html = _html("- [x] done\n- [ ] todo\n")
    assert "☑" in html
    assert "☐" in html


def test_render_escapes_html_in_text():
    html = _html("一段 <script>alert(1)</script> 文本\n")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_render_sanitizes_raw_html_block():
    """A raw HTML block must not smuggle a class attribute through.

    WeChat honours inline styles only, so a ``class`` attribute is dead
    weight there -- and the project rule is that the output never carries
    one.
    """
    html = _html('<div class="mermaid">图</div>\n')
    assert "class=" not in html
    assert "<div>图</div>" in html


def test_render_drops_iframe_from_raw_html():
    html = _html('<iframe src="https://video.example.com/x"></iframe>\n')
    assert "<iframe" not in html


def test_render_escapes_script_that_stands_alone_as_text():
    """A lone ``<script>`` is not a raw HTML block, so it becomes text."""
    html = _html("<script>alert(1)</script>\n")
    assert "<script" not in html
    assert "&lt;script&gt;" in html


def test_render_drops_script_inside_a_raw_html_block():
    """Inside a raw HTML block the whole element is removed, content and all."""
    html = _html('<div>块</div>\n<script>alert(1)</script>\n')
    assert "<script" not in html
    assert "alert(1)" not in html
    assert "<div>块</div>" in html


def test_render_strips_event_handlers_from_raw_html():
    html = _html('<div onclick="steal()">正文</div>\n')
    assert "onclick" not in html


def test_render_uses_compressed_style_for_thematic_break():
    html = _html("---\n")
    assert "<hr" in html
    assert ": " not in html.split("<hr")[1].split(">")[0]


def test_render_emits_reference_link_for_each_external_link():
    result = render(parse("[a](https://one.com) 和 [b](https://two.com)\n"))
    assert result.external_links == (("a", "https://one.com"), ("b", "https://two.com"))
