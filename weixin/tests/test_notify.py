import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from wechat.notify import BACKENDS, NotifyError, describe, send


class _Handler(BaseHTTPRequestHandler):
    calls = []
    bodies = {}
    query = {}
    status = 200
    response = {"code": 0, "errcode": 0}

    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        path = self.path.split("?")[0]
        _Handler.calls.append(path)
        _Handler.bodies[path] = raw
        if "?" in self.path:
            _Handler.query[path] = self.path.split("?", 1)[1]
        body = json.dumps(_Handler.response).encode("utf-8")
        self.send_response(_Handler.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def server():
    _Handler.calls = []
    _Handler.bodies = {}
    _Handler.query = {}
    _Handler.status = 200
    _Handler.response = {"code": 0, "errcode": 0}
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:{}".format(httpd.server_port)
    httpd.shutdown()


def _redirect(monkeypatch, server):
    """Point every backend at the local fake server."""
    for name in BACKENDS:
        monkeypatch.setitem(
            BACKENDS, name,
            lambda key, title, body, timeout, _name=name: _post_local(server, _name, key, title, body))


def _post_local(server, name, key, title, body):
    import urllib.parse
    import urllib.request
    if name == "serverchan":
        url = server + "/sctapi.ftqq.com/{}.send".format(key)
        payload = urllib.parse.urlencode({"title": title, "desp": body}).encode()
        content_type = "application/x-www-form-urlencoded"
    elif name == "wechat_work":
        url = server + "/qyapi.weixin.qq.com/cgi-bin/webhook/send"
        payload = json.dumps({"msgtype": "text",
                              "text": {"content": "{}\n{}".format(title, body)}}).encode()
        content_type = "application/json"
    else:
        url = server + "/hook"
        payload = json.dumps({"title": title, "body": body}).encode()
        content_type = "application/json"
    request = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": content_type}, method="POST")
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read()
    result = json.loads(raw.decode("utf-8"))
    code = result.get("code", result.get("errcode", 0))
    if code:
        raise NotifyError("failed")


# --- the module -----------------------------------------------------------


def test_send_without_a_backend_is_a_no_op():
    send("", "", "标题", "正文")
    send("serverchan", "", "标题", "正文")


def test_send_rejects_an_unknown_backend():
    with pytest.raises(NotifyError):
        send("carrier-pigeon", "key", "标题", "正文")


def test_describe_names_the_channel():
    assert "微信" in describe("serverchan", "SCT1")
    assert describe("wechat_work", "k") == "企业微信群机器人"
    assert describe("webhook", "u") == "自定义 webhook"


def test_the_serverchan_url_follows_the_key_format():
    """Turbo keys, legacy keys and the sctp family use different hosts."""
    from wechat import notify

    seen = []

    def fake_post(url, **kwargs):
        seen.append(url)
        return b'{"code":0}'

    original = notify._post
    notify._post = fake_post
    try:
        notify._serverchan("SCTabc", "t", "b", 5)
        notify._serverchan("SCabc", "t", "b", 5)
        notify._serverchan("sctp123txyz", "t", "b", 5)
    finally:
        notify._post = original

    assert seen[0] == "https://sctapi.ftqq.com/SCTabc.send"
    assert seen[1] == "https://sc.ftqq.com/SCabc.send"
    assert seen[2] == "https://123.push.ft07.com/send/sctp123txyz.send"


def test_serverchan_raises_when_the_service_reports_a_failure():
    from wechat import notify

    def fake_post(url, **kwargs):
        return b'{"code":40001,"message":"bad key"}'

    original = notify._post
    notify._post = fake_post
    try:
        with pytest.raises(NotifyError) as error:
            notify._serverchan("SCTbad", "t", "b", 5)
    finally:
        notify._post = original
    assert "bad key" in str(error.value)


def test_wechat_work_raises_on_a_nonzero_errcode():
    from wechat import notify

    def fake_post(url, **kwargs):
        return b'{"errcode":93000,"errmsg":"invalid webhook"}'

    original = notify._post
    notify._post = fake_post
    try:
        with pytest.raises(NotifyError) as error:
            notify._wechat_work("key", "t", "b", 5)
    finally:
        notify._post = original
    assert "invalid webhook" in str(error.value)


def test_the_webhook_backend_posts_title_and_body():
    from wechat import notify

    seen = {}

    def fake_post(url, **kwargs):
        seen["url"] = url
        seen["data"] = kwargs["data"]
        return b""

    original = notify._post
    notify._post = fake_post
    try:
        notify._webhook("https://example.com/hook", "标题", "正文", 5)
    finally:
        notify._post = original

    assert seen["url"] == "https://example.com/hook"
    assert json.loads(seen["data"].decode("utf-8")) == {"title": "标题", "body": "正文"}
