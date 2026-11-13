import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BROWSER_ROOT = REPO_ROOT / "browser"
if str(BROWSER_ROOT) not in sys.path:
    sys.path.insert(0, str(BROWSER_ROOT))

FIXTURES = Path(__file__).resolve().parent / "fixtures"
POST_PAGE = FIXTURES / "post.html"
SELECTORS = FIXTURES / "channels-selectors.json"


@pytest.fixture
def page():
    """一个真的 Chromium 页面（本地，不联网）。

    没装 playwright 就跳过——浏览器相关的测试需要浏览器，
    但**不该让没装浏览器的机器把整个测试套件拖红**。
    """
    from browser import pw

    if not pw.is_installed():
        pytest.skip("没装 playwright，跳过浏览器相关测试")

    sync_playwright = pw.import_playwright()
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        context = browser.new_context()
        new_page = context.new_page()
        yield new_page
        context.close()
        browser.close()


@pytest.fixture
def fixture_selectors(tmp_path):
    """指向本地假页面的选择器表（entry_url 换成真路径）。"""
    raw = json.loads(SELECTORS.read_text(encoding="utf-8"))
    raw["entry_url"] = POST_PAGE.as_uri()
    target = tmp_path / "channels-selectors.json"
    target.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return target


@pytest.fixture
def package_dir(tmp_path):
    """一个假的发布包目录，结构照 channels/out/<EP>/ 来。"""
    root = tmp_path / "ep01"
    root.mkdir()
    (root / "title.txt").write_text("两个事务改同一行，谁先谁后", encoding="utf-8")
    (root / "description.txt").write_text("MVCC 只管读和写。", encoding="utf-8")
    (root / "topics.txt").write_text("#PostgreSQL #行锁", encoding="utf-8")
    (root / "video.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    (root / "cover-4x3.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 64)
    (root / "cover-3x4.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 64)
    (root / "meta.json").write_text(
        json.dumps({"episode": "ep01", "status": "packaged"}, ensure_ascii=False),
        encoding="utf-8")
    return root


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT
