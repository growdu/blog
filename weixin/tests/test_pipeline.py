import io
import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from PIL import Image

from wechat import notify as notify_module
from wechat.cli import _docs_changed, main

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
    # Titles the fake server should reject, so a batch can be tested
    # against an article that fails.
    fail_titles = set()

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
            title = json.loads(body)["articles"][0].get("title", "")
            if title in _Handler.fail_titles:
                self._json({"errcode": 40007, "errmsg": "invalid media_id"})
                return
            self._json({"media_id": "DRAFT_ID"})
        elif path.endswith("/draft/update"):
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
    _Handler.fail_titles = set()
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


def _args(posts_dir, out_dir, slug=None, server=None):
    args = ["--posts-dir", str(posts_dir), "--out-dir", str(out_dir)]
    if server:
        args += ["--api-base", server]
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


def test_convert_rejects_ineligible_post(tmp_path, capsys):
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database" / "bad.md"
    target.parent.mkdir(parents=True)
    target.write_text(
        "---\ntitle: \"{}\"\ndate: 2026-11-09 15:00:00\n---\n\n正文。\n".format("标" * 70),
        encoding="utf-8")
    code = main(["convert", "database/bad"] + _args(posts_dir, tmp_path / "out"))
    assert code == 2
    assert "标题" in capsys.readouterr().err


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

    code = main(["publish", "database/huge"] + _args(posts_dir, tmp_path / "out", server=server))
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


def test_publish_requires_a_cover_for_articles_without_images(tmp_path, server, monkeypatch, capsys):
    posts_dir = tmp_path / "source" / "_posts"
    target = posts_dir / "database" / "plain.md"
    target.parent.mkdir(parents=True)
    target.write_text(SAMPLE_NO_IMAGE, encoding="utf-8")
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    code = main(["publish", "database/plain"] + _args(posts_dir, tmp_path / "out", server=server))
    assert code == 2
    assert "封面" in capsys.readouterr().err
    assert "/cgi-bin/draft/add" not in _Handler.calls


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


def test_batch_skips_an_article_that_is_too_long(tmp_path, server, monkeypatch, capsys):
    """Over the limit is a skip, not a failure: the rest still get drafted.

    400 short paragraphs are 800 characters of markdown but 26000 of
    rendered HTML -- every paragraph carries its own inline style.  That
    is the shape of the articles that do not fit, and one of them must
    not take the rest of the batch down with it.
    """
    posts_dir = _batch_posts(tmp_path, count=1)
    (posts_dir / "database" / "huge.md").write_text(
        "---\ntitle: \"太长\"\ndate: 2026-11-05 15:00:00\nauthor: growdu\n"
        "categories:\n  - 数据库\n---\n\n" + ("\n\n".join("短。" for _ in range(400))) + "\n",
        encoding="utf-8")
    monkeypatch.setenv("WX_APPID", "appid")
    monkeypatch.setenv("WX_APPSECRET", "secret")

    code = main(["batch"] + _args(posts_dir, tmp_path / "out", server=server))
    out = capsys.readouterr()
    assert code == 0
    assert "跳过 1 篇" in out.out
    assert _Handler.calls.count("/cgi-bin/draft/add") == 1


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
