import hashlib
import io
import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest
from PIL import Image

from wechat import notify as notify_module
from wechat import split as split_module
from wechat.cli import (_docs_changed, _drop_batch_lock, _fingerprint,
                       _render_parts, _take_batch_lock, main)
from wechat.assets import prepare_image
from wechat.material import MaterialCache
from wechat.posts import CONTENT_LIMIT, load_post

# The tests below are about how an article is cut, so they pin the
# limit they cut at.  The default limit is a choice that may move --
# and when it moves, the split moves with it, which is a different
# question from the one these tests ask.
SPLIT_LIMIT = 20000

SAMPLE = """---
title: "演示文章"
date: 2026-11-09 15:00:00
author: growdu
categories:
  - 数据库
---

## 第一节

正文一段，用来生成摘要。

```sql
SELECT 1;
```

| a | b |
| --- | --- |
| 1 | 2 |

![示意图](images/demo.png)

参考 [外部](https://example.com/x) 链接。
"""

SAMPLE_NO_IMAGE = """---
title: "无图文章"
date: 2026-11-09 15:00:00
author: growdu
---

正文一段，没有任何图片。
"""


def _write_png(path):
    import io
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    Image.new("RGB", (60, 40), (20, 120, 200)).save(buffer, format="PNG")
    path.write_bytes(buffer.getvalue())


class _Handler(BaseHTTPRequestHandler):
    calls = []
    bodies = {}
    # Every article that was sent to draft/add, in order.
    drafts = []
    # Drafts that were deleted again.
    deleted = []
    # Titles the fake server should reject, so a batch can be tested
    # against an article that fails.
    fail_titles = set()
    # Media ids that no longer exist -- a material the user deleted in
    # the WeChat backend.
    stale_materials = set()
    # Titles the fake server should answer to draft/update with a WAF
    # page, the way the real API does when the body carries a SQL
    # pattern.
    waf_titles = set()

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
            self._json({"access_token": "TOKEN"})
        elif path.endswith("/media/uploadimg"):
            self._json({"url": "https://mmbiz.qpic.cn/body/1"})
        elif path.endswith("/material/add_material"):
            self._json({"media_id": "COVER_ID"})
        elif path.endswith("/draft/add"):
            article = json.loads(body)["articles"][0]
            title = article.get("title", "")
            if article.get("thumb_media_id") in _Handler.stale_materials:
                self._json({"errcode": 40007, "errmsg": "invalid media_id"})
                return
            if title in _Handler.fail_titles:
                # 45003 is what WeChat answers when a title is refused.
                # It is deliberately **not** 40007: that one means
                # "invalid media_id", and the pipeline reads it as
                # "the cover material was deleted" and uploads the
                # cover again.
                self._json({"errcode": 45003, "errmsg": "title size out of limit"})
                return
            _Handler.drafts.append(article)
            self._json({"media_id": "DRAFT_ID"})
        elif path.endswith("/draft/update"):
            article = json.loads(body)["articles"]
            if article.get("title", "") in _Handler.waf_titles:
                body = (b'<!DOCTYPE html><html><head><script>window.location.href='
                        b'"https://waf.tencent.com/501page.html?u="+location.origin;'
                        b'</script></head></html>')
                self.send_response(501)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self._json({"errcode": 0, "errmsg": "ok"})
        elif path.endswith("/draft/delete"):
            _Handler.deleted.append(json.loads(body)["media_id"])
            self._json({"errcode": 0, "errmsg": "ok"})
        elif path.endswith("/freepublish/submit"):
            self._json({"publish_id": "PUBLISH_ID"})
        elif path.endswith("/freepublish/get"):
            self._json({"publish_status": 0, "article_id": "ARTICLE_ID"})
        else:
            self._json({"errcode": 404, "errmsg": "not found"})


@pytest.fixture
def server():
    _Handler.calls = []
    _Handler.bodies = {}
    _Handler.drafts = []
    _Handler.deleted = []
    _Handler.fail_titles = set()
    _Handler.waf_titles = set()
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:{}".format(httpd.server_port)
    httpd.shutdown()


@pytest.fixture
def sample_post(tmp_path):
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database" / "demo.md"
    target.parent.mkdir(parents=True)
    target.write_text(SAMPLE, encoding="utf-8")
    _write_png(tmp_path / "source" / "images" / "demo.png")
    return posts_dir, "database/demo"


def _args(posts_dir, out_dir, slug=None, server=None, max_length=0):
    args = ["--posts-dir", str(posts_dir), "--out-dir", str(out_dir)]
    if server:
        args += ["--api-base", server]
    if max_length:
        args += ["--max-length", str(max_length)]
    return args


def _secrets_file(tmp_path, content):
    path = tmp_path / "secrets.json"
    path.write_text(content, encoding="utf-8")
    return path


def test_scan_lists_eligible_and_ineligible(tmp_path, capsys):
    posts_dir = tmp_path / "source" / "_posts"
    (posts_dir / "database").mkdir(parents=True)
    (posts_dir / "database" / "ok.md").write_text(
        "---\ntitle: \"ok\"\ndate: 2026-11-09 15:00:00\n---\n\n正文。\n", encoding="utf-8")
    (posts_dir / "database" / "bad.md").write_text(
        "---\ntitle: \"{}\"\ndate: 2026-11-09 15:00:00\n---\n\n正文。\n".format("标" * 70),
        encoding="utf-8")

    code = main(["scan"] + _args(posts_dir, tmp_path / "out"))
    out = capsys.readouterr().out
    assert code == 0
    assert "database/ok" in out
    assert "database/bad" in out
    assert "标题" in out


def test_convert_writes_html_without_touching_network(sample_post, tmp_path):
    posts_dir, slug = sample_post
    out_dir = tmp_path / "out"
    code = main(["convert", slug] + _args(posts_dir, out_dir))
    assert code == 0
    html = (out_dir / slug / "article.html").read_text(encoding="utf-8")
    assert "<p style=" in html
    assert "class=" not in html


def test_convert_reports_missing_post(sample_post, tmp_path, capsys):
    posts_dir, _ = sample_post
    code = main(["convert", "no/such/post"] + _args(posts_dir, tmp_path / "out"))
    assert code == 1


def test_convert_shortens_a_long_title_instead_of_refusing(tmp_path, capsys):
    """A title that is too long is cut, not a reason to skip.

    The title is the one thing a reader sees first, so it is cut at a
    boundary that keeps the topic: the part before the colon.
    """
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database" / "bad.md"
    target.parent.mkdir(parents=True)
    title = "一个很长很长的主标题部分：{}".format("副标题内容" * 10)
    target.write_text(
        "---\ntitle: \"{}\"\ndate: 2026-11-09 15:00:00\n---\n\n正文。\n".format(title),
        encoding="utf-8")
    code = main(["convert", "database/bad"] + _args(posts_dir, tmp_path / "out"))
    assert code == 0
    out = capsys.readouterr().out
    assert "一个很长很长的主标题部分" in out


def _legacy_fingerprint(post, tag_html, limit, author):
    """The fingerprint as it was before the title was shortened.

    The drafts that are already in the box carry this hash, so a draft
    that has not changed must keep it -- otherwise every one of them
    would have to be sent again for nothing.

    The limit is part of it: it decides where the article is cut, so a
    different limit means different parts, and the drafts that carry
    the old cut have to be replaced.  So is the author: it is printed
    above the body of every part.
    """
    digest = hashlib.sha256()
    digest.update(post.fingerprint.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(post.title.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(tag_html.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(str(limit).encode("utf-8"))
    digest.update(b"\x00")
    digest.update(author.encode("utf-8"))
    return digest.hexdigest()


def _post_with_title(tmp_path, title):
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database" / "demo.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\ntitle: \"{}\"\ndate: 2026-11-09 15:00:00\n---\n\n正文。\n".format(title),
        encoding="utf-8")
    return load_post(target, posts_dir)


def test_the_fingerprint_of_an_untouched_article_does_not_move(tmp_path):
    """Shortening must not invalidate the drafts that are already there.

    Every draft in the box costs one upload and one ``draft/add`` to
    send.  If the fingerprint of an article whose title did not change
    moves, all of them are sent again for no reason.
    """
    post = _post_with_title(tmp_path, "一个短标题")
    tag = "<p>分类</p>"
    assert _fingerprint(post, tag, CONTENT_LIMIT, "growdu") == _legacy_fingerprint(
        post, tag, CONTENT_LIMIT, "growdu")


def test_the_fingerprint_moves_when_the_title_is_shortened(tmp_path):
    """A title that was cut has to reach the drafts that carry it."""
    post = _post_with_title(tmp_path, "主标题在这里：{}".format("副标题" * 20))
    tag = "<p>分类</p>"
    assert _fingerprint(post, tag, CONTENT_LIMIT, "growdu") != _legacy_fingerprint(
        post, tag, CONTENT_LIMIT, "growdu")


def test_publish_creates_draft_with_expected_payload(sample_post, tmp_path, server, monkeypatch):
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    monkeypatch.setenv("WX_SOURCE_URL", "https://growdu.cn")

    code = main(["publish", slug] + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 0

    payload = json.loads(_Handler.bodies["/cgi-bin/draft/add"])
    article = payload["articles"][0]
    assert article["title"] == "演示文章"
    assert article["content_source_url"] == "https://growdu.cn/2026/11/09/database/demo/"
    assert article["thumb_media_id"] == "COVER_ID"
    assert len(article["digest"]) <= 120
    assert "参考链接" in article["content"]


def test_publish_is_idempotent_across_runs(sample_post, tmp_path, server, monkeypatch):
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    args = ["publish", slug] + _args(posts_dir, tmp_path / "out", server=server)
    assert main(args) == 0
    assert main(args) == 0
    assert _Handler.calls.count("/cgi-bin/draft/add") == 1


def test_publish_does_not_submit_without_flag(sample_post, tmp_path, server, monkeypatch):
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    main(["publish", slug] + _args(posts_dir, tmp_path / "out", server=server))
    assert "/cgi-bin/freepublish/submit" not in _Handler.calls


def test_publish_submits_with_flag(sample_post, tmp_path, server, monkeypatch):
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    main(["publish", slug, "--publish"] + _args(posts_dir, tmp_path / "out", server=server))
    assert _Handler.calls.count("/cgi-bin/freepublish/submit") == 1


def test_publish_requires_credentials(sample_post, tmp_path, server, monkeypatch, capsys):
    posts_dir, slug = sample_post
    monkeypatch.delenv("WX_APPID", raising=False)
    monkeypatch.delenv("WX_APPSECRET", raising=False)
    # Point at a file that does not exist: the default path is the
    # developer's own weixin/secrets.json, which may well hold real
    # credentials and must never leak into a test run.
    code = main(["publish", slug, "--secrets-file", str(tmp_path / "absent.json")]
                + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 2
    assert "WX_APPID" in capsys.readouterr().err


def test_publish_reads_credentials_from_the_secrets_file(sample_post, tmp_path, server, monkeypatch):
    """A local JSON file keeps the secret out of the shell history."""
    posts_dir, slug = sample_post
    monkeypatch.delenv("WX_APPID", raising=False)
    monkeypatch.delenv("WX_APPSECRET", raising=False)
    secrets = _secrets_file(tmp_path, json.dumps({"appid": "appid", "appsecret": "secret"}))

    code = main(["publish", slug, "--secrets-file", str(secrets)]
                + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 0
    assert "/cgi-bin/draft/add" in _Handler.calls


def test_environment_variables_win_over_the_secrets_file(sample_post, tmp_path, server, monkeypatch):
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "from-env")
    monkeypatch.setenv("WX_APPSECRET", "from-env")
    secrets = _secrets_file(tmp_path, json.dumps({"appid": "from-file", "appsecret": "from-file"}))

    code = main(["publish", slug, "--secrets-file", str(secrets)]
                + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 0
    assert b"from-env" in _Handler.bodies["/cgi-bin/stable_token"]


def test_a_malformed_secrets_file_is_reported(sample_post, tmp_path, server, monkeypatch, capsys):
    """A broken file is worth a word: the user meant to put credentials there."""
    posts_dir, slug = sample_post
    monkeypatch.delenv("WX_APPID", raising=False)
    monkeypatch.delenv("WX_APPSECRET", raising=False)
    secrets = _secrets_file(tmp_path, "{not json")

    code = main(["publish", slug, "--secrets-file", str(secrets)]
                + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 2
    assert "不是合法 JSON" in capsys.readouterr().err


def test_a_missing_secrets_file_is_not_an_error(sample_post, tmp_path, server, monkeypatch, capsys):
    posts_dir, slug = sample_post
    monkeypatch.delenv("WX_APPID", raising=False)
    monkeypatch.delenv("WX_APPSECRET", raising=False)

    code = main(["publish", slug, "--secrets-file", str(tmp_path / "absent.json")]
                + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 2
    assert "缺少 WX_APPID" in capsys.readouterr().err


def test_publish_reports_api_error(sample_post, tmp_path, server, monkeypatch, capsys):
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    code = main(["publish", slug] + _args(posts_dir, tmp_path / "out", "http://127.0.0.1:1"))
    assert code == 3
    assert "微信接口报错" in capsys.readouterr().err


def test_status_reports_recorded_state(sample_post, tmp_path, server, monkeypatch, capsys):
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    main(["publish", slug] + _args(posts_dir, tmp_path / "out", server=server))
    capsys.readouterr()

    code = main(["status"] + _args(posts_dir, tmp_path / "out"))
    out = capsys.readouterr().out
    assert code == 0
    assert slug in out
    assert "DRAFT_ID" in out


def test_publish_sends_cover_crop_info(sample_post, tmp_path, server, monkeypatch):
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    main(["publish", slug] + _args(posts_dir, tmp_path / "out", server=server))
    payload = json.loads(_Handler.bodies["/cgi-bin/draft/add"])
    crops = payload["articles"][0]["cover_info"]["crop_percent_list"]
    assert [crop["ratio"] for crop in crops] == ["2.35_1", "1_1"]


def test_publish_rejects_an_overlong_author(sample_post, tmp_path, server, monkeypatch, capsys):
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    code = main(["publish", slug, "--author", "x" * 20]
                + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 2
    assert "作者" in capsys.readouterr().err
    assert "/cgi-bin/draft/add" not in _Handler.calls


def test_publish_refuses_content_over_the_limit(tmp_path, server, monkeypatch, capsys):
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database" / "huge.md"
    target.parent.mkdir(parents=True)
    target.write_text(
        "---\ntitle: \"大文章\"\ndate: 2026-11-09 15:00:00\n---\n\n"
        + ("正文内容。" * 6000) + "\n",
        encoding="utf-8")
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    code = main(["publish", "database/huge"] + _args(posts_dir, tmp_path / "out", server=server, max_length=SPLIT_LIMIT))
    assert code == 2
    assert "/cgi-bin/draft/add" not in _Handler.calls


def test_publish_reports_missing_image(sample_post, tmp_path, server, monkeypatch, capsys):
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    (tmp_path / "source" / "images" / "demo.png").unlink()

    code = main(["publish", slug] + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 2
    assert "图片不存在" in capsys.readouterr().err


def test_publish_uses_the_default_cover_for_articles_without_images(tmp_path, server, monkeypatch):
    """Most of this corpus has no picture, and a draft still needs a cover.

    WeChat rejects a draft without ``thumb_media_id``, so the tool
    ships a default cover rather than refusing the article.
    """
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database" / "plain.md"
    target.parent.mkdir(parents=True)
    target.write_text(SAMPLE_NO_IMAGE, encoding="utf-8")
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    code = main(["publish", "database/plain"] + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 0
    payload = json.loads(_Handler.bodies["/cgi-bin/draft/add"])
    assert payload["articles"][0]["thumb_media_id"] == "COVER_ID"
    # The default cover is uploaded; no body picture was involved.
    assert _Handler.calls.count("/cgi-bin/media/uploadimg") == 0


def test_publish_uses_configured_cover_for_articles_without_images(tmp_path, server, monkeypatch):
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database" / "plain.md"
    target.parent.mkdir(parents=True)
    target.write_text(SAMPLE_NO_IMAGE, encoding="utf-8")
    cover = tmp_path / "cover.png"
    _write_png(cover)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    code = main(["publish", "database/plain", "--cover", str(cover)]
                + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 0
    payload = json.loads(_Handler.bodies["/cgi-bin/draft/add"])
    assert payload["articles"][0]["thumb_media_id"] == "COVER_ID"


# --- external images ------------------------------------------------------


def test_publish_rehosts_an_external_image(tmp_path, server, monkeypatch):
    """WeChat deletes images it does not host, so they must be re-hosted.

    The picture is fetched, uploaded, and the placeholder in the body
    replaced with the mmbiz URL.
    """
    payload = io.BytesIO()
    Image.new("RGB", (40, 30), (10, 120, 200)).save(payload, format="PNG")

    class _ImageHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            data = payload.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    image_httpd = HTTPServer(("127.0.0.1", 0), _ImageHandler)
    threading.Thread(target=image_httpd.serve_forever, daemon=True).start()
    image_base = "http://127.0.0.1:{}".format(image_httpd.server_port)

    posts_dir = tmp_path / "source" / "_posts"
    posts_dir.mkdir(parents=True)
    (posts_dir / "ext.md").write_text(
        "---\ntitle: \"外链图\"\ndate: 2026-11-09 15:00:00\n---\n\n"
        "正文。\n\n![封面](images/cover.png)\n\n![图]({}/a.png)\n".format(image_base),
        encoding="utf-8")
    _write_png(tmp_path / "source" / "images" / "cover.png")

    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    code = main(["publish", "ext", "--posts-dir", str(posts_dir),
                 "--out-dir", str(tmp_path / "out"), "--api-base", server,
                 "--secrets-file", str(tmp_path / "absent.json")])
    image_httpd.shutdown()
    assert code == 0

    article = json.loads(_Handler.bodies["/cgi-bin/draft/add"])["articles"][0]
    assert "https://mmbiz.qpic.cn/body/1" in article["content"]
    assert "{{ext:" not in article["content"]


def test_publish_leaves_a_note_when_an_external_image_cannot_be_fetched(
        tmp_path, server, monkeypatch, capsys):
    """A picture that cannot be fetched leaves a visible note, not a gap."""
    posts_dir = tmp_path / "source" / "_posts"
    posts_dir.mkdir(parents=True)
    (posts_dir / "ext.md").write_text(
        "---\ntitle: \"外链图\"\ndate: 2026-11-09 15:00:00\n---\n\n"
        "正文。\n\n![封面](images/cover.png)\n\n"
        "![图](http://127.0.0.1:1/nope.png)\n",
        encoding="utf-8")
    _write_png(tmp_path / "source" / "images" / "cover.png")

    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    code = main(["publish", "ext", "--posts-dir", str(posts_dir),
                 "--out-dir", str(tmp_path / "out"), "--api-base", server,
                 "--secrets-file", str(tmp_path / "absent.json")])
    assert code == 0

    article = json.loads(_Handler.bodies["/cgi-bin/draft/add"])["articles"][0]
    assert "{{ext:" not in article["content"]
    assert "原图未能转存" in article["content"]
    assert "原图未能转存" in capsys.readouterr().out


# --- notifications ---------------------------------------------------------


def test_publish_notifies_when_a_draft_is_created(sample_post, tmp_path, server, monkeypatch):
    """The last click is a human's job, so the phone should be told."""
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    sent = []
    monkeypatch.setattr(
        "wechat.cli.notify_module.send",
        lambda backend, key, title, body, **kw: sent.append((backend, key, title, body)))

    code = main(["publish", slug, "--notify", "serverchan", "--notify-key", "SCT1"]
                + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 0
    assert len(sent) == 1
    backend, key, title, body = sent[0]
    assert backend == "serverchan"
    assert key == "SCT1"
    assert "草稿" in title
    assert "演示文章" in body
    assert "mp.weixin.qq.com" in body


def test_publish_does_not_notify_again_for_a_reused_draft(sample_post, tmp_path, server, monkeypatch):
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    sent = []
    monkeypatch.setattr(
        "wechat.cli.notify_module.send",
        lambda backend, key, title, body, **kw: sent.append(title))

    args = ["publish", slug, "--notify", "serverchan", "--notify-key", "SCT1"]
    assert main(args + _args(posts_dir, tmp_path / "out", server=server)) == 0
    assert len(sent) == 1
    assert main(args + _args(posts_dir, tmp_path / "out", server=server)) == 0
    assert len(sent) == 1


def test_a_failed_notification_does_not_fail_the_publish(sample_post, tmp_path, server, monkeypatch, capsys):
    """The draft is in the box; a broken notification is only a warning."""
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    def boom(*args, **kwargs):
        raise notify_module.NotifyError("no such key")

    monkeypatch.setattr("wechat.cli.notify_module.send", boom)

    code = main(["publish", slug, "--notify", "serverchan", "--notify-key", "SCT1"]
                + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 0
    assert "通知发送失败" in capsys.readouterr().err
    assert "/cgi-bin/draft/add" in _Handler.calls


def test_publish_stays_quiet_without_a_notify_channel(sample_post, tmp_path, server, monkeypatch):
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    def boom(*args, **kwargs):
        raise AssertionError("should not be called")

    monkeypatch.setattr("wechat.cli.notify_module.send", boom)
    code = main(["publish", slug] + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 0


# --- categories and collections --------------------------------------------


def _series_posts(tmp_path):
    """Two posts sharing one category, so they form a collection."""
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database"
    target.mkdir(parents=True)
    for name, title in (("one", "第一篇"), ("two", "第二篇")):
        (target / (name + ".md")).write_text(
            "---\ntitle: \"{}\"\ndate: 2026-11-0{} 15:00:00\nauthor: growdu\n"
            "categories:\n  - 数据库\n---\n\n正文一段。\n\n![图](images/demo.png)\n".format(
                title, "1" if name == "one" else "2"),
            encoding="utf-8")
    _write_png(tmp_path / "source" / "images" / "demo.png")
    return posts_dir


def test_categories_lists_every_category_with_its_size(tmp_path, capsys):
    posts_dir = _series_posts(tmp_path)
    code = main(["categories"] + _args(posts_dir, tmp_path / "out"))
    out = capsys.readouterr().out
    assert code == 0
    assert "数据库" in out
    assert "2 篇" in out


def test_categories_lists_the_articles_of_one_category(tmp_path, capsys):
    posts_dir = _series_posts(tmp_path)
    code = main(["categories", "数据库"] + _args(posts_dir, tmp_path / "out"))
    out = capsys.readouterr().out
    assert code == 0
    assert "第一篇" in out
    assert "第二篇" in out


def test_categories_reports_an_unknown_category(tmp_path, capsys):
    posts_dir = _series_posts(tmp_path)
    code = main(["categories", "没有这个分类"] + _args(posts_dir, tmp_path / "out"))
    assert code == 1
    assert "找不到分类" in capsys.readouterr().err


def test_collections_lists_the_collections(tmp_path, capsys):
    posts_dir = _series_posts(tmp_path)
    code = main(["collections"] + _args(posts_dir, tmp_path / "out"))
    out = capsys.readouterr().out
    assert code == 0
    assert "数据库" in out


def test_collections_writes_the_index_article_and_the_checklist(tmp_path, capsys):
    posts_dir = _series_posts(tmp_path)
    out_dir = tmp_path / "out"
    code = main(["collections", "数据库", "--write"] + _args(posts_dir, out_dir))
    assert code == 0

    target = out_dir / "collections" / "数据库"
    html = (target / "article.html").read_text(encoding="utf-8")
    plan = (target / "plan.md").read_text(encoding="utf-8")
    assert "第一篇" in html and "第二篇" in html
    assert "class=" not in html
    assert "1. [ ] 第一篇" in plan


def test_collections_reports_an_unknown_collection(tmp_path, capsys):
    posts_dir = _series_posts(tmp_path)
    code = main(["collections", "没有这个合集"] + _args(posts_dir, tmp_path / "out"))
    assert code == 1
    assert "找不到合集" in capsys.readouterr().err


def test_publish_collection_creates_a_draft(tmp_path, server, monkeypatch):
    posts_dir = _series_posts(tmp_path)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    code = main(["publish-collection", "数据库"]
                + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 0

    article = json.loads(_Handler.bodies["/cgi-bin/draft/add"])["articles"][0]
    assert article["title"] == "「数据库」合集目录"
    assert "第一篇" in article["content"]
    assert "第二篇" in article["content"]
    assert article["thumb_media_id"] == "COVER_ID"
    assert article["content_source_url"].startswith("https://growdu.cn/categories/")


def test_publish_collection_is_idempotent(tmp_path, server, monkeypatch):
    posts_dir = _series_posts(tmp_path)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    args = ["publish-collection", "数据库"] + _args(posts_dir, tmp_path / "out", server=server)
    assert main(args) == 0
    assert main(args) == 0
    assert _Handler.calls.count("/cgi-bin/draft/add") == 1


def test_publish_collection_requires_credentials(tmp_path, server, monkeypatch, capsys):
    posts_dir = _series_posts(tmp_path)
    monkeypatch.delenv("WX_APPID", raising=False)
    monkeypatch.delenv("WX_APPSECRET", raising=False)

    code = main(["publish-collection", "数据库", "--secrets-file",
                 str(tmp_path / "absent.json")]
                + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 2
    assert "WX_APPID" in capsys.readouterr().err
    assert "/cgi-bin/draft/add" not in _Handler.calls


def test_publish_collection_reports_an_unknown_collection(tmp_path, server, monkeypatch, capsys):
    posts_dir = _series_posts(tmp_path)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    code = main(["publish-collection", "没有这个合集"]
                + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 1
    assert "/cgi-bin/draft/add" not in _Handler.calls


def test_publish_collection_takes_a_mermaid_diagram_as_cover(tmp_path, server, monkeypatch):
    """In the learning-path series the only picture is a diagram.

    The cover of a collection's index article comes from the articles
    of that collection, so a diagram has to count as a picture.
    """
    from wechat import mermaid as mermaid_module

    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database"
    target.mkdir(parents=True)
    source = "graph TD;\nA-->B;\n"
    for name in ("one", "two"):
        (target / (name + ".md")).write_text(
            "---\ntitle: \"{}\"\ndate: 2026-11-01 15:00:00\nauthor: growdu\n"
            "categories:\n  - 数据库\n---\n\n正文。\n\n```mermaid\n{}\n```\n".format(
                name, source),
            encoding="utf-8")

    png = tmp_path / "diagram.png"
    _write_png(png)
    asset = mermaid_module.MermaidAsset(
        key=mermaid_module.mermaid_key(source), source=source, png=png)
    monkeypatch.setattr(
        "wechat.cli.mermaid_module.render_mermaid",
        lambda blocks, out_dir: {asset.key: asset})

    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    code = main(["publish-collection", "数据库"]
                + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 0
    article = json.loads(_Handler.bodies["/cgi-bin/draft/add"])["articles"][0]
    assert article["thumb_media_id"] == "COVER_ID"


# --- the category tag ------------------------------------------------------


def test_publish_prints_the_category_tag_on_the_article(sample_post, tmp_path, server, monkeypatch):
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    main(["publish", slug] + _args(posts_dir, tmp_path / "out", server=server))
    article = json.loads(_Handler.bodies["/cgi-bin/draft/add"])["articles"][0]
    assert "分类" in article["content"]
    assert "数据库" in article["content"]


def test_publish_can_leave_the_category_tag_out(sample_post, tmp_path, server, monkeypatch):
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    main(["publish", slug, "--category-tag", "none"]
         + _args(posts_dir, tmp_path / "out", server=server))
    article = json.loads(_Handler.bodies["/cgi-bin/draft/add"])["articles"][0]
    assert "分类 ·" not in article["content"]


def test_publish_can_put_the_category_tag_at_the_end(sample_post, tmp_path, server, monkeypatch):
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    main(["publish", slug, "--category-tag", "bottom"]
         + _args(posts_dir, tmp_path / "out", server=server))
    content = json.loads(_Handler.bodies["/cgi-bin/draft/add"])["articles"][0]["content"]
    # The tag closes the article, above the mechanical list of links.
    assert content.index("分类 ·") > content.index("正文")
    assert content.index("分类 ·") < content.index("参考链接")


def test_changing_the_category_tag_updates_the_draft_in_place(sample_post, tmp_path, server, monkeypatch):
    """The tag is part of the body, so a changed tag has to reach the draft.

    The draft is updated rather than duplicated: ``draft/add`` would
    leave the old version in the box next to the new one.
    """
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    args = _args(posts_dir, tmp_path / "out", server=server)
    assert main(["publish", slug] + args) == 0
    assert main(["publish", slug, "--category-tag", "none"] + args) == 0

    assert _Handler.calls.count("/cgi-bin/draft/add") == 1
    assert _Handler.calls.count("/cgi-bin/draft/update") == 1

    payload = json.loads(_Handler.bodies["/cgi-bin/draft/update"])
    assert payload["media_id"] == "DRAFT_ID"
    assert payload["index"] == 0
    assert "分类 ·" not in payload["articles"]["content"]


def test_a_draft_the_waf_refuses_is_added_again_and_the_old_one_removed(
        sample_post, tmp_path, server, monkeypatch):
    """The WAF behind the API refuses ``draft/update`` for SQL bodies.

    A code block full of ``CREATE TABLE`` is ordinary in this corpus,
    and the body of ``draft/update`` is checked for SQL patterns while
    the body of ``draft/add`` is not.  The end state has to be the
    same: one draft, carrying the current content.
    """
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    args = _args(posts_dir, tmp_path / "out", server=server)
    assert main(["publish", slug] + args) == 0

    # Change the article so the second run has to update the draft.
    target = posts_dir / "database" / "demo.md"
    target.write_text(target.read_text(encoding="utf-8") + "\n补一段。\n",
                      encoding="utf-8")

    _Handler.waf_titles = {"演示文章"}
    _Handler.calls = []
    assert main(["publish", slug] + args) == 0

    # The update was refused, so the article was added again and the
    # old draft was deleted.
    assert _Handler.calls.count("/cgi-bin/draft/update") == 1
    assert _Handler.calls.count("/cgi-bin/draft/add") == 1
    assert _Handler.deleted == ["DRAFT_ID"]

    # The ledger points at the draft that is actually there.
    state = json.loads((tmp_path / "out" / "state.json").read_text(encoding="utf-8"))
    assert state["posts"][slug]["media_id"] == "DRAFT_ID"


def test_a_refused_update_does_not_swallow_other_errors(sample_post, tmp_path, server, monkeypatch):
    """Only the WAF gets the add-and-delete treatment."""
    posts_dir, slug = sample_post
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    args = _args(posts_dir, tmp_path / "out", server=server)
    assert main(["publish", slug] + args) == 0

    target = posts_dir / "database" / "demo.md"
    target.write_text(target.read_text(encoding="utf-8") + "\n补一段。\n",
                      encoding="utf-8")

    # The add fails; the update would have been tried first, but the
    # WAF is not what is being tested here.
    _Handler.waf_titles = {"演示文章"}
    _Handler.fail_titles = {"演示文章"}
    _Handler.calls = []
    code = main(["publish", slug] + args)
    assert code != 0
    # The failed add did not delete the draft that is already there.
    assert _Handler.deleted == []


# --- batch -----------------------------------------------------------------


def _batch_posts(tmp_path, count=3):
    """Several posts sharing one category, all with a picture."""
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database"
    target.mkdir(parents=True)
    for index in range(count):
        (target / ("post{}.md".format(index))).write_text(
            "---\ntitle: \"文章{}\"\ndate: 2026-11-0{} 15:00:00\nauthor: growdu\n"
            "categories:\n  - 数据库\n---\n\n正文一段。\n\n![图](images/demo.png)\n".format(
                index, index + 1),
            encoding="utf-8")
    _write_png(tmp_path / "source" / "images" / "demo.png")
    return posts_dir


def test_batch_dry_run_touches_no_network(tmp_path, capsys):
    posts_dir = _batch_posts(tmp_path)
    code = main(["batch", "--dry-run"] + _args(posts_dir, tmp_path / "out"))
    out = capsys.readouterr().out
    assert code == 0
    assert "预检" in out
    assert "database/post0" in out
    assert not (tmp_path / "out" / "state.json").exists()


def test_batch_creates_a_draft_for_every_eligible_post(tmp_path, server, monkeypatch):
    posts_dir = _batch_posts(tmp_path)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    code = main(["batch"] + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 0
    assert _Handler.calls.count("/cgi-bin/draft/add") == 3


def test_batch_is_resumable_and_costs_nothing_the_second_time(tmp_path, server, monkeypatch):
    """Re-running over the whole corpus must not upload a single image."""
    posts_dir = _batch_posts(tmp_path)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    args = _args(posts_dir, tmp_path / "out", server=server)
    assert main(["batch"] + args) == 0
    uploads_after_first = _Handler.calls.count("/cgi-bin/media/uploadimg")

    _Handler.calls = []
    assert main(["batch"] + args) == 0
    assert _Handler.calls.count("/cgi-bin/draft/add") == 0
    assert _Handler.calls.count("/cgi-bin/media/uploadimg") == 0
    assert uploads_after_first == 3


def test_batch_new_only_skips_articles_that_already_have_a_draft(tmp_path, server, monkeypatch):
    posts_dir = _batch_posts(tmp_path)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    args = _args(posts_dir, tmp_path / "out", server=server)
    assert main(["batch"] + args) == 0
    _Handler.calls = []
    assert main(["batch", "--new-only"] + args) == 0
    assert _Handler.calls.count("/cgi-bin/draft/add") == 0


def test_a_second_batch_does_not_run_while_one_is_going(tmp_path, server, monkeypatch):
    """The scheduled job and a manual batch must not overlap.

    Both would find an article without a draft and both would create
    one, leaving two copies of the same article in the box.
    """
    posts_dir = _batch_posts(tmp_path)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    out_dir = tmp_path / "out"
    lock = out_dir / "batch.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    # The pid of another process that is running: init always is.
    lock.write_text("1", encoding="utf-8")

    _Handler.calls = []
    code = main(["batch"] + _args(posts_dir, out_dir, server=server))
    assert code == 0
    assert _Handler.calls.count("/cgi-bin/draft/add") == 0

    # Once the lock is gone the next batch runs as usual.
    lock.unlink()
    _Handler.calls = []
    assert main(["batch"] + _args(posts_dir, out_dir, server=server)) == 0
    assert _Handler.calls.count("/cgi-bin/draft/add") == 3


def test_a_lock_left_behind_by_a_dead_process_is_taken_over(tmp_path):
    """A crash must not lock the tool out forever."""
    out_dir = tmp_path / "out"
    lock = out_dir / "batch.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    # A pid that is not running: the lock was left behind.
    lock.write_text("999999", encoding="utf-8")
    assert _take_batch_lock(out_dir) is True
    _drop_batch_lock(out_dir)
    assert not lock.exists()


def test_the_lock_is_given_back_when_the_batch_is_done(tmp_path, server, monkeypatch):
    """A finished batch must not keep the next one out."""
    posts_dir = _batch_posts(tmp_path)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    out_dir = tmp_path / "out"
    args = _args(posts_dir, out_dir, server=server)
    assert main(["batch"] + args) == 0
    assert not (out_dir / "batch.lock").exists()


def test_batch_changed_only_picks_up_an_edited_article(tmp_path, server, monkeypatch):
    posts_dir = _batch_posts(tmp_path)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    args = _args(posts_dir, tmp_path / "out", server=server)
    assert main(["batch"] + args) == 0

    edited = posts_dir / "database" / "post0.md"
    edited.write_text(edited.read_text(encoding="utf-8") + "\n补一段。\n", encoding="utf-8")

    _Handler.calls = []
    assert main(["batch", "--changed-only"] + args) == 0
    assert _Handler.calls.count("/cgi-bin/draft/update") == 1
    assert _Handler.calls.count("/cgi-bin/draft/add") == 0


def test_batch_limit_caps_the_number_of_articles(tmp_path, server, monkeypatch):
    posts_dir = _batch_posts(tmp_path)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    code = main(["batch", "--limit", "2"] + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 0
    assert _Handler.calls.count("/cgi-bin/draft/add") == 2


def test_one_failing_article_does_not_stop_the_batch(tmp_path, server, monkeypatch, capsys):
    """A single broken article must not cost the others their draft."""
    posts_dir = _batch_posts(tmp_path)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    _Handler.fail_titles = {"文章1"}

    code = main(["batch"] + _args(posts_dir, tmp_path / "out", server=server))
    out = capsys.readouterr()
    assert code == 3
    assert _Handler.calls.count("/cgi-bin/draft/add") == 3
    assert "失败 1 篇" in out.out
    assert "database/post1" in out.out


def test_batch_records_what_it_did(tmp_path, server, monkeypatch):
    posts_dir = _batch_posts(tmp_path)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    main(["batch"] + _args(posts_dir, tmp_path / "out", server=server))
    report = json.loads((tmp_path / "out" / "batch-report.json").read_text(encoding="utf-8"))
    assert report["created"] == 3
    assert report["failed"] == 0


def test_batch_splits_an_article_that_is_too_long(tmp_path, server, monkeypatch, capsys):
    """An article that does not fit becomes several drafts.

    400 short paragraphs are 800 characters of markdown but 26000 of
    rendered HTML -- every paragraph carries its own inline style.  That
    is the shape of the articles that do not fit, and instead of being
    skipped they are cut into parts at the paragraph boundaries.
    """
    posts_dir = _batch_posts(tmp_path, count=1)
    (posts_dir / "database" / "huge.md").write_text(
        "---\ntitle: \"太长\"\ndate: 2026-11-05 15:00:00\nauthor: growdu\n"
        "categories:\n  - 数据库\n---\n\n" + ("\n\n".join("短。" for _ in range(400))) + "\n",
        encoding="utf-8")
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    code = main(["batch"] + _args(posts_dir, tmp_path / "out", server=server, max_length=SPLIT_LIMIT))
    out = capsys.readouterr()
    assert code == 0
    # Two parts of the long article, plus the short one next to it.
    assert _Handler.calls.count("/cgi-bin/draft/add") == 3

    titles = [article["title"] for article in _Handler.drafts
              if article["title"].startswith("太长")]
    assert titles == ["太长（一）", "太长（二）"]
    # The parts are connected, so the reader knows how they fit together.
    assert "未完待续" in _Handler.drafts[0]["content"]
    assert "接《太长（一）》" in _Handler.drafts[1]["content"]


def test_the_report_tells_skips_and_failures_apart(tmp_path, server, monkeypatch):
    """A skip is not a failure, and the report must not call it one.

    Both end up in the same list, so the counts are derived from the
    entries themselves.  Otherwise a run that skipped twelve long
    articles would report twelve failures and look broken when it was
    not.
    """
    posts_dir = _batch_posts(tmp_path, count=2)
    # One paragraph of 30000 characters cannot be cut anywhere: it is
    # too long on its own and it is one block.
    (posts_dir / "database" / "giant.md").write_text(
        "---\ntitle: \"一整段\"\ndate: 2026-11-05 15:00:00\nauthor: growdu\n"
        "categories:\n  - 数据库\n---\n\n" + "字" * 30000 + "\n",
        encoding="utf-8")
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    _Handler.fail_titles = {"文章0"}

    main(["batch"] + _args(posts_dir, tmp_path / "out", server=server, max_length=SPLIT_LIMIT))
    report = json.loads((tmp_path / "out" / "batch-report.json").read_text(encoding="utf-8"))
    assert report["rejected"] == 1
    assert report["failed"] == 1
    assert report["created"] == 1
    assert sorted(item["kind"] for item in report["failures"]) == ["failed", "rejected"]


# --- auto-draft ------------------------------------------------------------


def _git_repo(tmp_path):
    """A tiny git repository with a docs/ directory."""
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "a.md").write_text("第一篇\n", encoding="utf-8")
    (repo / "tools").mkdir()
    (repo / "tools" / "sync-hexo.py").write_text("# stub\n", encoding="utf-8")

    def git(*args):
        subprocess.run(["git"] + list(args), cwd=str(repo), check=True,
                       capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "test")
    git("add", ".")
    git("commit", "-q", "-m", "init")
    return repo


def test_docs_changed_is_false_right_after_a_commit(tmp_path):
    repo = _git_repo(tmp_path)
    stamp = tmp_path / "stamp"
    stamp.write_text(subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True,
        text=True).stdout.strip() + "\n", encoding="utf-8")
    assert _docs_changed(repo, stamp) is False


def test_docs_changed_notices_a_new_committed_article(tmp_path):
    repo = _git_repo(tmp_path)
    stamp = tmp_path / "stamp"
    stamp.write_text(subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True,
        text=True).stdout.strip() + "\n", encoding="utf-8")
    (repo / "docs" / "b.md").write_text("第二篇\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "new"], cwd=str(repo), check=True,
                   capture_output=True)
    assert _docs_changed(repo, stamp) is True


def test_docs_changed_notices_an_uncommitted_article(tmp_path):
    """The author may have written the article and not committed it yet."""
    repo = _git_repo(tmp_path)
    stamp = tmp_path / "stamp"
    stamp.write_text(subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True,
        text=True).stdout.strip() + "\n", encoding="utf-8")
    (repo / "docs" / "b.md").write_text("第二篇\n", encoding="utf-8")
    assert _docs_changed(repo, stamp) is True


def test_docs_changed_ignores_changes_outside_docs(tmp_path):
    repo = _git_repo(tmp_path)
    stamp = tmp_path / "stamp"
    stamp.write_text(subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True,
        text=True).stdout.strip() + "\n", encoding="utf-8")
    (repo / "README.md").write_text("改了\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "readme"], cwd=str(repo), check=True,
                   capture_output=True)
    assert _docs_changed(repo, stamp) is False


def test_auto_draft_skips_the_sync_when_nothing_changed(tmp_path, server, monkeypatch, capsys):
    """``sync-hexo.py`` takes three minutes; it must not run for nothing."""
    repo = _git_repo(tmp_path)
    stamp = tmp_path / "stamp"
    stamp.write_text(subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True,
        text=True).stdout.strip() + "\n", encoding="utf-8")

    calls = []
    monkeypatch.setattr("wechat.cli._run_sync", lambda repo_dir: calls.append(repo_dir) or 0)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    posts_dir = tmp_path / "source" / "_posts"
    posts_dir.mkdir(parents=True)
    code = main(["auto-draft", "--repo-dir", str(repo), "--stamp-file", str(stamp),
                 "--posts-dir", str(posts_dir), "--out-dir", str(tmp_path / "out"),
                 "--api-base", server])
    out = capsys.readouterr().out
    assert code == 0
    assert calls == []
    assert "没有变化" in out


def test_auto_draft_runs_the_sync_when_docs_changed(tmp_path, server, monkeypatch, capsys):
    repo = _git_repo(tmp_path)
    stamp = tmp_path / "stamp"
    (repo / "docs" / "b.md").write_text("第二篇\n", encoding="utf-8")

    calls = []
    monkeypatch.setattr("wechat.cli._run_sync", lambda repo_dir: calls.append(repo_dir) or 0)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    posts_dir = tmp_path / "source" / "_posts"
    posts_dir.mkdir(parents=True)
    code = main(["auto-draft", "--repo-dir", str(repo), "--stamp-file", str(stamp),
                 "--posts-dir", str(posts_dir), "--out-dir", str(tmp_path / "out"),
                 "--api-base", server])
    assert code == 0
    assert calls == [repo]
    # The stamp records the commit, so the next run does not sync again.
    assert stamp.read_text(encoding="utf-8").strip() == subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True,
        text=True).stdout.strip()


def test_an_external_picture_can_serve_as_the_cover(tmp_path, server, monkeypatch):
    """An article with only external pictures still gets a cover.

    The picture is fetched and re-hosted anyway, so reusing it costs
    one extra upload and saves the default cover.
    """
    payload = io.BytesIO()
    Image.new("RGB", (40, 30), (10, 120, 200)).save(payload, format="PNG")

    class _ImageHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            data = payload.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    image_httpd = HTTPServer(("127.0.0.1", 0), _ImageHandler)
    threading.Thread(target=image_httpd.serve_forever, daemon=True).start()
    image_base = "http://127.0.0.1:{}".format(image_httpd.server_port)

    posts_dir = tmp_path / "source" / "_posts"
    posts_dir.mkdir(parents=True)
    (posts_dir / "ext.md").write_text(
        "---\ntitle: \"只有外链图\"\ndate: 2026-11-09 15:00:00\n---\n\n"
        "正文。\n\n![图]({}/a.png)\n".format(image_base),
        encoding="utf-8")
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    code = main(["publish", "ext", "--posts-dir", str(posts_dir),
                 "--out-dir", str(tmp_path / "out"), "--api-base", server,
                 "--secrets-file", str(tmp_path / "absent.json")])
    image_httpd.shutdown()
    assert code == 0

    article = json.loads(_Handler.bodies["/cgi-bin/draft/add"])["articles"][0]
    assert article["thumb_media_id"] == "COVER_ID"
    # The picture was fetched once and uploaded twice: once into the
    # body, once as the cover.
    assert _Handler.calls.count("/cgi-bin/media/uploadimg") == 1
    assert _Handler.calls.count("/cgi-bin/material/add_material") == 1


# --- split articles -------------------------------------------------------


def _long_post(posts_dir, paragraphs=400, title="很长"):
    """A post whose rendered body does not fit into one draft."""
    target = posts_dir / "database" / "long.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    body = "\n\n".join("第 {} 段。".format(index) for index in range(paragraphs))
    target.write_text(
        "---\ntitle: \"{}\"\ndate: 2026-11-05 15:00:00\nauthor: growdu\n"
        "categories:\n  - 数据库\n---\n\n".format(title) + body + "\n",
        encoding="utf-8")
    return target


def test_a_split_article_gets_one_ledger_entry_per_part(tmp_path, server, monkeypatch):
    posts_dir = tmp_path / "source" / "_posts"
    _long_post(posts_dir)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    assert main(["batch"] + _args(posts_dir, tmp_path / "out", server=server, max_length=SPLIT_LIMIT)) == 0

    state = json.loads((tmp_path / "out" / "state.json").read_text(encoding="utf-8"))["posts"]
    assert "database/long" in state
    assert "database/long#2" in state
    assert state["database/long"]["parts"] == 2


def test_re_running_a_split_article_creates_nothing(tmp_path, server, monkeypatch):
    posts_dir = tmp_path / "source" / "_posts"
    _long_post(posts_dir)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    args = _args(posts_dir, tmp_path / "out", server=server)

    assert main(["batch"] + args) == 0
    _Handler.calls = []
    assert main(["batch"] + args) == 0
    assert "/cgi-bin/draft/add" not in _Handler.calls
    assert "/cgi-bin/media/uploadimg" not in _Handler.calls


def _render_args(out_dir, max_length=SPLIT_LIMIT):
    """The arguments ``_render_parts`` needs -- no network, no server."""
    return SimpleNamespace(out_dir=str(out_dir), category_tag="top",
                          author="growdu", max_length=max_length)


def _long_render_post(tmp_path, paragraphs=700, title="很长",
                      categories=("数据库", "源码", "PostgreSQL")):
    """A post whose rendered body needs more than one draft.

    Short paragraphs are what make the packing tight: the parts are
    filled up to the last paragraph, so a part lands right on the
    limit -- which is exactly where a reserve that is a little too
    small does its damage.  Several categories make the framing of a
    part longer, and the framing is what the reserve has to cover.
    """
    posts_dir = tmp_path / "source" / "_posts"
    (posts_dir / "database").mkdir(parents=True, exist_ok=True)
    target = posts_dir / "database" / "long.md"
    target.write_text(
        "---\ntitle: \"{}\"\ndate: 2026-11-05 15:00:00\nauthor: growdu\n"
        "categories:\n".format(title)
        + "".join("  - {}\n".format(name) for name in categories)
        + "---\n\n"
        + "\n\n".join("短。" for _ in range(paragraphs)) + "\n",
        encoding="utf-8")
    return load_post(target, posts_dir)


def test_an_article_whose_parts_land_on_the_limit_is_split_not_refused(tmp_path):
    """An article that is a little too long is split, not refused.

    Every part pays once for its own framing -- the transition lines,
    the category tag and the reference-links wrapper -- and that room
    has to be kept back from the body.  When the room kept back was
    smaller than the framing really was, a part that was a few dozen
    characters too long took the whole article down with it.
    """
    post = _long_render_post(tmp_path)

    parts = _render_parts(post, _render_args(tmp_path / "out"))

    assert len(parts) > 1
    for part in parts:
        assert part.result.content_length <= SPLIT_LIMIT


def test_a_part_that_still_does_not_fit_is_cut_again(tmp_path, monkeypatch):
    """The pipeline does not trust its own estimate.

    The reserve is what keeps a part's framing out of the body's way.
    If it is too small the part does not get shorter -- it does not
    fit, and the article is refused.  So a part that is still too long
    after rendering is measured and cut once more.
    """
    monkeypatch.setattr(split_module, "framing_reserve",
                        lambda title, tag_html="", extra="": 0)
    post = _long_render_post(tmp_path)

    parts = _render_parts(post, _render_args(tmp_path / "out"))

    assert len(parts) > 1
    for part in parts:
        assert part.result.content_length <= SPLIT_LIMIT


def test_a_split_article_does_not_keep_the_file_of_a_whole_one(tmp_path):
    """The file of the other shape is removed.

    An article that used to be whole and is split now keeps a single
    file from the older run.  It looks like the current product and it
    is not: it is the whole article, over the limit, and it was never
    drafted.
    """
    post = _long_render_post(tmp_path)
    out_dir = tmp_path / "out"
    slug_dir = out_dir / post.slug
    slug_dir.mkdir(parents=True, exist_ok=True)
    (slug_dir / "article.html").write_text("<p>旧的整篇</p>", encoding="utf-8")

    parts = _render_parts(post, _render_args(out_dir))

    assert len(parts) > 1
    assert not (slug_dir / "article.html").exists()
    assert (slug_dir / "part-1.html").is_file()


def test_a_whole_article_does_not_keep_the_parts_of_an_older_split(tmp_path):
    """The other way round: parts of an older split are removed."""
    posts_dir = tmp_path / "source" / "_posts"
    (posts_dir / "database").mkdir(parents=True, exist_ok=True)
    target = posts_dir / "database" / "short.md"
    target.write_text(
        "---\ntitle: \"短\"\ndate: 2026-11-05 15:00:00\nauthor: growdu\n"
        "categories:\n  - 数据库\n---\n\n正文一段。\n", encoding="utf-8")
    post = load_post(target, posts_dir)
    out_dir = tmp_path / "out"
    slug_dir = out_dir / post.slug
    slug_dir.mkdir(parents=True, exist_ok=True)
    (slug_dir / "part-1.html").write_text("<p>旧的一部分</p>", encoding="utf-8")

    parts = _render_parts(post, _render_args(out_dir))

    assert len(parts) == 1
    assert (slug_dir / "article.html").is_file()
    assert not (slug_dir / "part-1.html").exists()


def test_new_only_finishes_an_article_whose_parts_are_missing(tmp_path, server, monkeypatch):
    """A run that stopped halfway must not leave the article half-drafted.

    The scheduled job only drafts articles that never had a draft, so
    an article whose first part exists but whose second does not would
    otherwise stay incomplete forever.
    """
    posts_dir = tmp_path / "source" / "_posts"
    _long_post(posts_dir)
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "state.json").write_text(json.dumps({"posts": {
        "database/long": {"fingerprint": "旧", "media_id": "DRAFT_ID", "parts": 2},
    }}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    assert main(["batch", "--new-only"] + _args(posts_dir, out_dir, server=server,
                                                max_length=SPLIT_LIMIT)) == 0
    # The first part is brought up to date, the second one is created.
    assert _Handler.calls.count("/cgi-bin/draft/update") == 1
    assert _Handler.calls.count("/cgi-bin/draft/add") == 1


def test_a_shorter_article_deletes_the_parts_it_no_longer_needs(tmp_path, server, monkeypatch):
    posts_dir = tmp_path / "source" / "_posts"
    target = _long_post(posts_dir)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    args = _args(posts_dir, tmp_path / "out", server=server, max_length=SPLIT_LIMIT)

    assert main(["batch"] + args) == 0
    assert len(_Handler.drafts) == 2

    # The article is shortened until it fits into one draft again.
    target.write_text(
        "---\ntitle: \"很长\"\ndate: 2026-11-05 15:00:00\nauthor: growdu\n"
        "categories:\n  - 数据库\n---\n\n短了。\n", encoding="utf-8")
    _Handler.calls = []
    assert main(["batch"] + args) == 0
    assert _Handler.calls.count("/cgi-bin/draft/delete") == 1

    state = json.loads((tmp_path / "out" / "state.json").read_text(encoding="utf-8"))["posts"]
    assert "database/long#2" not in state
    assert state["database/long"]["parts"] == 1


def test_every_part_gets_its_own_digest(tmp_path, server, monkeypatch):
    """The same summary on every row of the draft box tells the reader nothing."""
    posts_dir = tmp_path / "source" / "_posts"
    _long_post(posts_dir)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    assert main(["batch"] + _args(posts_dir, tmp_path / "out", server=server, max_length=SPLIT_LIMIT)) == 0

    digests = [article["digest"] for article in _Handler.drafts]
    assert len(digests) == 2
    assert len(set(digests)) == 2
    assert all(digest for digest in digests)


def test_the_parts_are_numbered_in_their_titles(tmp_path, server, monkeypatch):
    posts_dir = tmp_path / "source" / "_posts"
    _long_post(posts_dir)
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    assert main(["batch"] + _args(posts_dir, tmp_path / "out", server=server, max_length=SPLIT_LIMIT)) == 0

    titles = [article["title"] for article in _Handler.drafts]
    assert titles == ["很长（一）", "很长（二）"]
    # The first part points at the second, the second points back.
    assert "很长（二）" in _Handler.drafts[0]["content"]
    assert "很长（一）" in _Handler.drafts[1]["content"]


def test_every_part_carries_its_own_reference_links(tmp_path, server, monkeypatch):
    """A part that was cut out of an article keeps the links it uses.

    The links are collected per part, not per whole article: a reader
    who only opens the second part still finds the sources it cites.
    """
    posts_dir = tmp_path / "source" / "_posts"
    target = _long_post(posts_dir)
    body = target.read_text(encoding="utf-8")
    target.write_text(body + "\n\n参考 [外部](https://example.com/x) 链接。\n",
                      encoding="utf-8")
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    assert main(["batch"] + _args(posts_dir, tmp_path / "out", server=server)) == 0

    with_links = [article for article in _Handler.drafts
                   if "参考链接" in article["content"]]
    assert len(with_links) == 1
    assert "https://example.com/x" in with_links[0]["content"]


def test_an_unreadable_image_skips_the_article_instead_of_crashing_the_batch(
        tmp_path, server, monkeypatch):
    """A file that is not an image at all cannot be uploaded.

    The exception used to travel all the way up and kill the whole
    batch: 200 drafts already created, and the rest of the corpus never
    reached.  Now the article is skipped and the batch carries on.
    """
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database" / "broken.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\ntitle: \"带坏图的文章\"\ndate: 2026-11-09 15:00:00\nauthor: growdu\n"
        "categories:\n  - 数据库\n---\n\n正文。\n\n![图](images/notes.txt)\n",
        encoding="utf-8")
    image = posts_dir.parent / "images" / "notes.txt"
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_text("这根本不是一张图片。", encoding="utf-8")

    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    code = main(["batch"] + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 3
    report = json.loads((tmp_path / "out" / "batch-report.json").read_text(encoding="utf-8"))
    assert report["failed"] == 1
    assert "不是有效的图片" in report["failures"][0]["reason"]


def test_an_article_with_an_svg_is_drafted(tmp_path, server, monkeypatch):
    """An SVG is drawn to a PNG, so the article is not lost."""
    from wechat import svg as svg_module

    if not svg_module._find_chrome():
        pytest.skip("this machine has no browser to draw the SVG with")

    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database" / "svg.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\ntitle: \"带 SVG 的文章\"\ndate: 2026-11-09 15:00:00\nauthor: growdu\n"
        "categories:\n  - 数据库\n---\n\n正文。\n\n![图](images/icon.svg)\n",
        encoding="utf-8")
    image = posts_dir.parent / "images" / "icon.svg"
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
        '<rect width="100" height="50" fill="#3d7ea6"/></svg>', encoding="utf-8")

    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    code = main(["batch"] + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 0
    # The picture went up as a PNG.
    assert _Handler.calls.count("/cgi-bin/media/uploadimg") == 1
    payload = json.loads(_Handler.bodies["/cgi-bin/draft/add"])
    assert "https://mmbiz.qpic.cn/body/1" in payload["articles"][0]["content"]


def test_a_new_pipeline_version_makes_the_draft_look_changed(tmp_path, server, monkeypatch):
    """The article did not change, but the rules that turn it into a draft did.

    A draft made by an older pipeline has to be brought up to date: the
    fingerprint only covers the article, so without the version the
    stale draft would be reused as it is.
    """
    posts_dir = _batch_posts(tmp_path, count=1)
    out_dir = tmp_path / "out"
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    args = _args(posts_dir, out_dir, server=server)

    assert main(["batch"] + args) == 0
    assert _Handler.calls.count("/cgi-bin/draft/add") == 1

    path = out_dir / "state.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state["posts"]["database/post0"]["pipeline"] = 0
    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    _Handler.calls = []
    assert main(["batch"] + args) == 0
    assert _Handler.calls.count("/cgi-bin/draft/update") == 1
    assert "/cgi-bin/draft/add" not in _Handler.calls


# --- the brand of the draft -----------------------------------------------

BRAND_SAMPLE = """---
title: "带标题页的文章"
date: 2026-09-29 15:00:00
author: growdu
categories:
  - 数据库
---

| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 面向 PostgreSQL 内核开发 / DBA，把一张表的元数据完整拆开。 | 2026-09-29 |

正文一段，讲的是元数据到底存在哪里。
"""


def _brand_post(tmp_path, body=BRAND_SAMPLE, name="brand"):
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database" / "{}.md".format(name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return load_post(target, posts_dir), posts_dir, "database/{}".format(name)


def test_the_first_part_carries_the_card(tmp_path):
    """The title page the author wrote becomes a card at the top."""
    post, _, _ = _brand_post(tmp_path)

    parts = _render_parts(post, _render_args(tmp_path / "out"))
    html = parts[0].result.html

    assert html.startswith("<section")
    assert "面向 PostgreSQL 内核开发" in html
    assert "2026-09-29" in html


def test_the_title_page_is_not_a_table_in_the_body(tmp_path):
    """A three column table whose middle column is a paragraph is not
    something a reader should scroll past."""
    post, _, _ = _brand_post(tmp_path)

    parts = _render_parts(post, _render_args(tmp_path / "out"))

    assert "编写内容" not in parts[0].result.html
    assert "<table" not in parts[0].result.html


def test_every_part_ends_with_the_signature(tmp_path):
    """The last line of every part says who wrote it."""
    post, _, _ = _brand_post(tmp_path)

    parts = _render_parts(post, _render_args(tmp_path / "out"))

    assert parts
    for part in parts:
        assert part.result.html.rstrip().endswith("见文末「阅读原文」</p>")


def test_every_part_of_a_split_article_ends_with_the_signature(tmp_path):
    """A reader who comes in through part three finds the author there
    too -- not only in the first instalment."""
    post = _long_render_post(tmp_path)

    parts = _render_parts(post, _render_args(tmp_path / "out"))

    assert len(parts) > 1
    for part in parts:
        assert part.result.html.rstrip().endswith("见文末「阅读原文」</p>")


def test_the_card_and_the_signature_do_not_break_the_limit(tmp_path):
    """The framing is paid for out of the body, so an article that used
    to fit may have to be split."""
    post, _, _ = _brand_post(tmp_path)

    parts = _render_parts(post, _render_args(tmp_path / "out"))

    for part in parts:
        assert part.result.content_length <= SPLIT_LIMIT


def test_the_digest_is_the_authors_own_description(tmp_path, server, monkeypatch):
    """What the reader sees before opening the article is what the
    author wrote about it."""
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    post, posts_dir, slug = _brand_post(tmp_path)

    code = main(["publish", slug] + _args(posts_dir, tmp_path / "out",
                                          server=server))

    assert code == 0
    payload = json.loads(_Handler.bodies["/cgi-bin/draft/add"])
    article = payload["articles"][0]
    assert article["digest"].startswith("面向 PostgreSQL 内核开发")
    assert "正文一段" not in article["digest"]


def test_the_digest_of_a_split_part_does_not_repeat_the_title(tmp_path):
    """The row already carries the title; the summary has room to carry
    something else."""
    post = _long_render_post(tmp_path)

    parts = _render_parts(post, _render_args(tmp_path / "out"))

    assert len(parts) > 1
    for part in parts:
        assert not part.digest.startswith("很长｜")


def test_the_digest_carries_the_original_title_when_the_title_was_shortened(
        tmp_path, server, monkeypatch):
    """When the title is cut, the draft box still says what the article
    is called on the site."""
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database" / "demo.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\ntitle: \"一个很长很长的主标题部分：{}\"\n"
        "date: 2026-11-09 15:00:00\n---\n\n正文。\n".format("副标题内容" * 10),
        encoding="utf-8")

    code = main(["publish", "database/demo"] + _args(
        posts_dir, tmp_path / "out", server=server))

    assert code == 0
    payload = json.loads(_Handler.bodies["/cgi-bin/draft/add"])
    article = payload["articles"][0]
    assert article["digest"].startswith("一个很长很长的主标题部分")
    assert len(article["digest"]) <= 120


# --- the cover material is uploaded once ----------------------------------


def _cover_png(tmp_path):
    path = tmp_path / "cover.png"
    _write_png(path)
    return path


def test_the_same_cover_is_uploaded_once(tmp_path, server, monkeypatch):
    """Every refresh used to upload the cover of every part again.

    Each upload leaves another copy in the material library, so the
    library grew by one material per part per run -- 2129 materials for
    320 distinct covers after the first refresh cycle.
    """
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    posts_dir = _batch_posts(tmp_path, count=2)
    cover = _cover_png(tmp_path)

    code = main(["batch", "--cover", str(cover)]
                + _args(posts_dir, tmp_path / "out", server=server))

    assert code == 0
    assert _Handler.calls.count("/cgi-bin/material/add_material") == 1


def test_a_cover_material_that_was_deleted_is_uploaded_again(tmp_path, server,
                                                              monkeypatch):
    """The user cleans the material library up and one of the materials
    we cached is gone.  The draft is refused; the cover is sent again."""
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database" / "demo.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(SAMPLE_NO_IMAGE, encoding="utf-8")
    cover = _cover_png(tmp_path)
    out_dir = tmp_path / "out"

    prepared = prepare_image(cover)
    digest = hashlib.sha1(prepared.data).hexdigest()
    MaterialCache(out_dir / "materials.json").put(digest, "STALE_ID")
    _Handler.stale_materials = {"STALE_ID"}

    code = main(["publish", "database/demo", "--cover", str(cover)]
                + _args(posts_dir, out_dir, server=server))

    assert code == 0
    assert _Handler.drafts[0]["thumb_media_id"] == "COVER_ID"
    assert _Handler.calls.count("/cgi-bin/material/add_material") == 1


def test_a_refused_draft_is_not_retried_when_the_cover_was_just_uploaded(
        tmp_path, server, monkeypatch):
    """40007 means the media id is invalid.

    When the cover was uploaded a moment ago it cannot be the stale
    one, so uploading it again would only cost another upload and
    another refused draft.
    """
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database" / "demo.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(SAMPLE_NO_IMAGE, encoding="utf-8")
    cover = _cover_png(tmp_path)
    # The material that was just uploaded is refused.
    _Handler.stale_materials = {"COVER_ID"}

    code = main(["publish", "database/demo", "--cover", str(cover)]
                + _args(posts_dir, tmp_path / "out", server=server))

    assert code != 0
    assert _Handler.calls.count("/cgi-bin/material/add_material") == 1
    assert _Handler.calls.count("/cgi-bin/draft/add") == 1
