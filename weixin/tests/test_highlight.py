import re

from wechat.highlight import highlight_code


def test_highlight_returns_span_with_inline_style():
    html = highlight_code("SELECT 1;", "sql")
    assert "<span" in html
    assert "style=" in html


def test_highlight_output_has_no_class_attribute():
    html = highlight_code("SELECT 1;", "sql")
    assert "class=" not in html


def test_highlight_escapes_html_in_code():
    html = highlight_code("<script>alert(1)</script>", "html")
    # No raw tag may survive: only the span elements Pygments emits.
    assert "<script>" not in html
    assert "&lt;" in html
    assert not re.search(r"<(?!/?span\b)", html)


def test_highlight_unknown_language_falls_back_to_escaped_text():
    html = highlight_code("a < b & c", "not-a-real-language")
    assert "a &lt; b &amp; c" in html


def test_highlight_plain_text_has_no_span():
    html = highlight_code("just text", "text")
    assert "<span" not in html
    assert "just text" in html


def test_highlight_empty_language_has_no_span():
    html = highlight_code("just text", "")
    assert "<span" not in html


def test_highlight_handles_c_code():
    html = highlight_code("int main(void) { return 0; }", "c")
    assert "<span" in html
    assert "class=" not in html


def test_highlight_never_raises_on_empty_code():
    html = highlight_code("", "sql")
    assert isinstance(html, str)
