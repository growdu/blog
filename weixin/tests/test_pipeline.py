import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from wechat.cli import main

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
            self._json({"media_id": "DRAFT_ID"})
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
    code = main(["publish", slug] + _args(posts_dir, tmp_path / "out", server=server))
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
