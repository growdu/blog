from wechat.mdparse import parse
from wechat.mermaid import _summarize_error, mermaid_key, render_mermaid


def test_summarize_error_keeps_the_meaningful_head():
    stderr = "\nError: Evaluation failed: UnknownDiagramError: No diagram type detected\n\n    at detectType (...)\n    at other (...)\n"
    message = _summarize_error(stderr, "")
    assert message.startswith("Error: Evaluation failed")
    assert "at detectType" not in message


def test_summarize_error_falls_back_to_first_line():
    assert _summarize_error("", "something went wrong\nmore") == "something went wrong"


def test_summarize_error_handles_empty_output():
    assert _summarize_error("", "") == "mermaid-cli failed"


def test_mermaid_key_is_stable_and_position_independent():
    assert mermaid_key("graph TD;\nA-->B;") == mermaid_key("graph TD;\nA-->B;")
    assert mermaid_key("a") != mermaid_key("b")


def test_render_mermaid_collects_only_mermaid_blocks(tmp_path):
    blocks = parse("```mermaid\ngraph TD;\nA-->B;\n```\n\n```sql\nSELECT 1;\n```\n")

    def runner(source, out_file):
        out_file.write_bytes(b"\x89PNG\r\n\x1a\n")
        return True, ""

    assets = render_mermaid(blocks, tmp_path, runner=runner)
    assert len(assets) == 1
    asset = next(iter(assets.values()))
    assert asset.png is not None
    assert asset.error is None
    assert asset.png.read_bytes().startswith(b"\x89PNG")


def test_render_mermaid_records_failure_without_raising(tmp_path):
    blocks = parse("```mermaid\nBROKEN\n```\n")

    def runner(source, out_file):
        return False, "Parse error on line 1"

    assets = render_mermaid(blocks, tmp_path, runner=runner)
    asset = next(iter(assets.values()))
    assert asset.png is None
    assert "Parse error" in asset.error


def test_render_mermaid_removes_partial_file_on_failure(tmp_path):
    blocks = parse("```mermaid\nBROKEN\n```\n")

    def runner(source, out_file):
        out_file.write_bytes(b"partial garbage")
        return False, "boom"

    assets = render_mermaid(blocks, tmp_path, runner=runner)
    asset = next(iter(assets.values()))
    assert asset.png is None
    assert not list(tmp_path.glob("*.png"))


def test_render_mermaid_reuses_cached_file(tmp_path):
    blocks = parse("```mermaid\ngraph TD;\nA-->B;\n```\n")
    calls = []

    def runner(source, out_file):
        calls.append(source)
        out_file.write_bytes(b"\x89PNG\r\n\x1a\n")
        return True, ""

    render_mermaid(blocks, tmp_path, runner=runner)
    render_mermaid(blocks, tmp_path, runner=runner)
    assert len(calls) == 1


def test_render_mermaid_deduplicates_identical_diagrams(tmp_path):
    blocks = parse(
        "```mermaid\ngraph TD;\nA-->B;\n```\n\n"
        "```mermaid\ngraph TD;\nA-->B;\n```\n"
    )
    calls = []

    def runner(source, out_file):
        calls.append(source)
        out_file.write_bytes(b"\x89PNG\r\n\x1a\n")
        return True, ""

    assets = render_mermaid(blocks, tmp_path, runner=runner)
    assert len(assets) == 1
    assert len(calls) == 1


def test_render_mermaid_uses_same_key_as_render_module(tmp_path):
    from wechat.render import mermaid_key as render_key

    blocks = parse("```mermaid\ngraph TD;\nA-->B;\n```\n")

    def runner(source, out_file):
        out_file.write_bytes(b"\x89PNG\r\n\x1a\n")
        return True, ""

    assets = render_mermaid(blocks, tmp_path, runner=runner)
    key = next(iter(assets))
    assert key == render_key("graph TD;\nA-->B;")
