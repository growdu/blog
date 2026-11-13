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


PROCESSING_PAGE = FIXTURES / "post-processing.html"
LIST_PAGE = FIXTURES / "post-list.html"


def _selectors_for(page_path: Path, target: Path, *, timeouts: dict | None = None) -> Path:
    """把测试夹具的选择器表指向另一个假页面。"""
    raw = json.loads(SELECTORS.read_text(encoding="utf-8"))
    raw["entry_url"] = page_path.as_uri()
    if timeouts:
        raw["timeouts"] = timeouts
    target.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return target


@pytest.fixture
def processing_selectors(tmp_path):
    """指向「视频还在平台处理中」的假页面。

    超时调得很短：这一页面的等待逻辑在真实站上要等几分钟，
    测试里等几分钟没意义——要验的是「等」这个动作发生了，不是等了多久。
    """
    return _selectors_for(
        PROCESSING_PAGE, tmp_path / "processing-selectors.json",
        timeouts={"publish_ready_ms": 5000, "publish_effect_ms": 1500},
    )


@pytest.fixture
def fixture_server():
    """把 fixtures 目录用本地 HTTP 伺服起来。

    **为什么不用 file://**：剪贴板 API 只在「安全上下文」里可用，
    而 file:// 是不透明来源——权限授不上，写剪贴板也会被拒。
    127.0.0.1 算安全上下文，所以测剪贴板得走 http。
    """
    import functools
    import http.server
    import threading

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):  # 别把测试日志刷满
            pass

    handler = functools.partial(Quiet, directory=str(FIXTURES))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def list_selectors(tmp_path, fixture_server):
    """指向假的内容列表页（取公开链接用）。"""
    raw = json.loads(SELECTORS.read_text(encoding="utf-8"))
    raw["entry_url"] = f"{fixture_server}/post-list.html"
    raw["selectors"]["list"] = {
        "entry_item": [".finder-ui-desktop-sub-menu__item:has-text('视频')"],
        "share_button": [".post-feed-item:has-text('{row_text}') "
                         ".opr-item-wrap .more-actions"],
        "copy_link_item": [":text-is('复制视频链接')"],
    }
    target = tmp_path / "list-selectors.json"
    target.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return target
