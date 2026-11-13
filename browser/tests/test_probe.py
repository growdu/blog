"""探测：把页面结构 dump 出来。"""

from browser import probe


def test_dump_finds_the_form_controls(page):
    page.set_content("""
      <input id="video-file" type="file" accept="video/*">
      <textarea id="desc" placeholder="填写描述"></textarea>
      <button id="publish">发表</button>
    """)
    dump = probe.dump_structure(page)
    ids = {node.get("id") for node in dump["nodes"]}
    assert {"video-file", "desc", "publish"} <= ids


def test_dump_suggests_a_selector_for_each_node(page):
    page.set_content("<textarea id='desc' placeholder='填写描述'></textarea>")
    dump = probe.dump_structure(page)
    suggested = {node.get("suggested") for node in dump["nodes"]}
    assert "#desc" in suggested


def test_dump_notices_hidden_elements(page):
    page.set_content("<input id='hidden' type='file' style='display:none'>")
    dump = probe.dump_structure(page)
    node = [n for n in dump["nodes"] if n.get("id") == "hidden"][0]
    assert node["visible"] is False


def test_render_text_shows_the_url_and_the_suggestions(page):
    page.set_content("<input id='x' type='text'>")
    dump = probe.dump_structure(page)
    text = probe.render_text(dump)
    assert "URL" in text
    assert "#x" in text


def test_render_text_can_hide_invisible_nodes(page):
    page.set_content("<input id='x' type='text' style='display:none'>")
    dump = probe.dump_structure(page)
    assert "不可见" in probe.render_text(dump)
    assert "不可见" not in probe.render_text(dump, only_visible=True)


def test_save_writes_json(page, tmp_path):
    page.set_content("<input id='x' type='text'>")
    dump = probe.dump_structure(page)
    target = probe.save(dump, tmp_path / "structure.json")
    assert target.is_file()
    assert "\"id\"" in target.read_text(encoding="utf-8")
