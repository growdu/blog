"""Tests for the reconciliation between the ledger and the draft box.

The ledger is what stops the tool from creating the same draft twice.
When a human deletes a draft in the WeChat backend the ledger goes
stale, and the article would never be drafted again.  These tests
cover the command that closes that gap.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from wechat.cli import main
from wechat.state import StateStore


class _Handler(BaseHTTPRequestHandler):
    calls = []
    bodies = {}
    # What the fake draft box holds: a list of media_id/title pairs.
    drafts = []
    # How many items one ``draft/batchget`` call may return.
    page_size = 20

    def log_message(self, *args):
        pass

    def _read_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length)

    def _json(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = self._read_body()
        path = self.path.split("?")[0]
        _Handler.calls.append(path)
        _Handler.bodies[path] = body
        if path.endswith("/stable_token"):
            self._json({"access_token": "TOKEN", "expires_in": 7200})
        elif path.endswith("/media/uploadimg"):
            self._json({"url": "https://mmbiz.qpic.cn/body/1"})
        elif path.endswith("/material/add_material"):
            self._json({"media_id": "COVER_ID"})
        elif path.endswith("/draft/add"):
            self._json({"media_id": "DRAFT_ID"})
        elif path.endswith("/draft/update"):
            self._json({"errcode": 0, "errmsg": "ok"})
        elif path.endswith("/draft/batchget"):
            payload = json.loads(body)
            offset = payload.get("offset", 0)
            # The server may hand out fewer items than were asked for;
            # the client has to keep paging until the count says it is
            # done.
            size = min(payload.get("count", 20), _Handler.page_size)
            page = _Handler.drafts[offset:offset + size]
            self._json({
                "total_count": len(_Handler.drafts),
                "item": [
                    {
                        "media_id": draft["media_id"],
                        "content": {"news_item": [{"title": draft.get("title", "")}]},
                    }
                    for draft in page
                ],
            })
        else:
            self._json({"errcode": 404, "errmsg": "not found"})


@pytest.fixture
def server():
    _Handler.calls = []
    _Handler.bodies = {}
    _Handler.drafts = []
    _Handler.page_size = 20
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:{}".format(httpd.server_port)
    httpd.shutdown()


def _write_ledger(out_dir, entries):
    path = out_dir / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"posts": entries}, ensure_ascii=False),
                    encoding="utf-8")
    return path


def _write_post(posts_dir, slug="demo/plain"):
    target = posts_dir / "{}.md".format(slug)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\ntitle: \"演示文章\"\ndate: 2026-11-09 15:00:00\n---\n\n正文一段。\n",
        encoding="utf-8")
    return slug


def _run(server, out_dir, *extra):
    return main([
        "reconcile",
        "--out-dir", str(out_dir),
        "--api-base", server,
        "--secrets-file", str(out_dir / "absent.json"),
        *extra,
    ])


def test_a_deleted_draft_is_forgotten(tmp_path, server, monkeypatch):
    """The ledger stops claiming a draft that is no longer in the box."""
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    out_dir = tmp_path / "out"
    _write_ledger(out_dir, {
        "a/gone": {"fingerprint": "f1", "media_id": "GONE", "publish_id": None},
        "a/here": {"fingerprint": "f2", "media_id": "HERE", "publish_id": None},
    })
    _Handler.drafts = [{"media_id": "HERE", "title": "还在的"}]

    assert _run(server, out_dir) == 0

    store = StateStore(out_dir / "state.json")
    assert store.get("a/gone").media_id is None
    assert store.get("a/here").media_id == "HERE"


def test_the_publish_record_survives_the_cleanup(tmp_path, server, monkeypatch):
    """An article that was published stays published, draft or not."""
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    out_dir = tmp_path / "out"
    _write_ledger(out_dir, {
        "a/gone": {"fingerprint": "f1", "media_id": "GONE",
                   "publish_id": "PID", "publish_status": 0},
    })
    _Handler.drafts = [{"media_id": "OTHER", "title": "别的"}]

    assert _run(server, out_dir) == 0

    state = StateStore(out_dir / "state.json").get("a/gone")
    assert state.media_id is None
    assert state.publish_id == "PID"


def test_dry_run_reports_without_writing(tmp_path, server, monkeypatch):
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    out_dir = tmp_path / "out"
    _write_ledger(out_dir, {
        "a/gone": {"fingerprint": "f1", "media_id": "GONE", "publish_id": None},
    })
    _Handler.drafts = [{"media_id": "OTHER", "title": "别的"}]

    assert _run(server, out_dir, "--dry-run") == 0

    assert StateStore(out_dir / "state.json").get("a/gone").media_id == "GONE"


def test_an_empty_box_does_not_wipe_the_ledger(tmp_path, server, monkeypatch):
    """An empty box next to a full ledger is a wrong account, not a cleanup.

    Pruning then would throw the whole ledger away and the next batch
    would rebuild every draft from scratch.
    """
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    out_dir = tmp_path / "out"
    _write_ledger(out_dir, {
        "a/gone": {"fingerprint": "f1", "media_id": "GONE", "publish_id": None},
    })
    _Handler.drafts = []

    assert _run(server, out_dir) == 2
    assert StateStore(out_dir / "state.json").get("a/gone").media_id == "GONE"


def test_an_empty_ledger_does_not_call_the_api(tmp_path, server, monkeypatch):
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    out_dir = tmp_path / "out"

    assert _run(server, out_dir) == 0
    assert "/cgi-bin/draft/batchget" not in _Handler.calls


def test_a_draft_the_ledger_does_not_know_is_reported(tmp_path, server, monkeypatch,
                                                       capsys):
    """A draft in the box that the ledger never recorded is worth reporting.

    It usually means the ledger was deleted, which would make the next
    batch create a second copy of every article.
    """
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    out_dir = tmp_path / "out"
    _write_ledger(out_dir, {
        "a/here": {"fingerprint": "f2", "media_id": "HERE", "publish_id": None},
    })
    _Handler.drafts = [
        {"media_id": "HERE", "title": "认得的"},
        {"media_id": "UNKNOWN", "title": "不认得的"},
    ]

    assert _run(server, out_dir) == 0

    report = json.loads((out_dir / "reconcile-report.json").read_text(encoding="utf-8"))
    assert [item["media_id"] for item in report["orphans"]] == ["UNKNOWN"]
    assert report["missing"] == []
    assert report["drafts_in_box"] == 2
    assert report["ledger_entries"] == 1
    assert "不认得的" in capsys.readouterr().out


def test_the_report_is_written(tmp_path, server, monkeypatch):
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    out_dir = tmp_path / "out"
    _write_ledger(out_dir, {
        "a/gone": {"fingerprint": "f1", "media_id": "GONE", "publish_id": None},
    })
    _Handler.drafts = [{"media_id": "HERE", "title": "还在的"}]

    assert _run(server, out_dir) == 0

    report = json.loads((out_dir / "reconcile-report.json").read_text(encoding="utf-8"))
    assert report["missing"] == [{"slug": "a/gone", "media_id": "GONE"}]
    assert report["pruned"] is True


def test_a_pruned_article_is_drafted_again(tmp_path, server, monkeypatch):
    """The whole point: a forgotten article comes back on the next run."""
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    posts_dir = tmp_path / "source" / "_posts"
    out_dir = tmp_path / "out"
    slug = _write_post(posts_dir)
    _write_ledger(out_dir, {
        slug: {"fingerprint": "f1", "media_id": "GONE", "publish_id": None},
    })
    _Handler.drafts = []

    # The box is empty, so the reconciliation refuses to prune -- that
    # is the safety check, not the path this test is about.
    assert _run(server, out_dir) == 2

    # With a draft in the box the cleanup happens ...
    _Handler.drafts = [{"media_id": "OTHER", "title": "别的"}]
    assert _run(server, out_dir) == 0
    assert StateStore(out_dir / "state.json").get(slug).media_id is None

    # ... and the article is drafted again as if it were new.
    code = main([
        "batch", "--new-only",
        "--posts-dir", str(posts_dir),
        "--out-dir", str(out_dir),
        "--api-base", server,
        "--secrets-file", str(out_dir / "absent.json"),
    ])
    assert code == 0
    assert "/cgi-bin/draft/add" in _Handler.calls
    assert StateStore(out_dir / "state.json").get(slug).media_id == "DRAFT_ID"


def test_the_box_is_walked_page_by_page(tmp_path, server, monkeypatch):
    """A box with more drafts than one page is not cut short."""
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    out_dir = tmp_path / "out"
    _write_ledger(out_dir, {
        "a/{}".format(index): {"fingerprint": "f", "media_id": "M{}".format(index),
                               "publish_id": None}
        for index in range(5)
    })
    _Handler.drafts = [{"media_id": "M{}".format(index), "title": str(index)}
                       for index in range(5)]
    _Handler.page_size = 2

    assert _run(server, out_dir) == 0

    report = json.loads((out_dir / "reconcile-report.json").read_text(encoding="utf-8"))
    assert report["drafts_in_box"] == 5
    assert report["missing"] == []
