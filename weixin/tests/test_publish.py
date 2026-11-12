import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from wechat.publish import WeChatClient, WeChatError


class _Handler(BaseHTTPRequestHandler):
    calls = []
    bodies = {}
    urls = []
    headers_seen = {}
    # How many times an endpoint has been called.  The token is
    # answered with a fresh one every time.
    token_count = 0
    # Endpoints that should answer with an expired token once.
    expire_once = set()

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
        _Handler.urls.append(self.path)
        _Handler.headers_seen[path] = dict(self.headers)
        if path.endswith("/stable_token"):
            _Handler.token_count += 1
            self._json({"access_token": "TOKEN", "expires_in": 7200})
        elif path.endswith("/media/uploadimg"):
            if path in _Handler.expire_once:
                _Handler.expire_once.discard(path)
                self._json({"errcode": 42001, "errmsg": "access_token expired"})
                return
            self._json({"url": "https://mmbiz.qpic.cn/mmbiz_jpg/x/1"})
        elif path.endswith("/material/add_material"):
            if path in _Handler.expire_once:
                _Handler.expire_once.discard(path)
                self._json({"errcode": 42001, "errmsg": "access_token expired"})
                return
            self._json({"media_id": "COVER_ID"})
        elif path.endswith("/draft/add"):
            if path in _Handler.expire_once:
                _Handler.expire_once.discard(path)
                self._json({"errcode": 42001, "errmsg": "access_token expired"})
                return
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
    _Handler.token_count = 0
    _Handler.expire_once = set()
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:{}".format(httpd.server_port)
    httpd.shutdown()


def test_stable_token_returns_token(server):
    client = WeChatClient("appid", "secret", base_url=server)
    assert client.stable_token() == "TOKEN"


def test_stable_token_is_fetched_once(server):
    client = WeChatClient("appid", "secret", base_url=server)
    client.stable_token()
    client.stable_token()
    assert [path for path in _Handler.calls if "stable_token" in path] == ["/cgi-bin/stable_token"]


def test_stable_token_sends_the_credential_as_secret(server):
    """The live endpoint reads ``secret``, not the documented ``appsecret``.

    Sending ``appsecret`` alone is answered with ``41004 appsecret
    missing``, so the credential goes out under both names.
    """
    client = WeChatClient("appid", "s3cret", base_url=server)
    client.stable_token()
    payload = json.loads(_Handler.bodies["/cgi-bin/stable_token"])
    assert payload["secret"] == "s3cret"
    assert payload["appsecret"] == "s3cret"
    assert payload["appid"] == "appid"
    assert payload["grant_type"] == "client_credential"


def test_the_token_travels_in_the_query_as_well_as_the_header(server):
    """The upload endpoints ignore the Bearer header.

    ``media/uploadimg`` and ``material/add_material`` answer
    ``41001 access_token missing`` when the token is only in the
    header, so it goes out as a query parameter too.
    """
    client = WeChatClient("appid", "secret", base_url=server)
    client.upload_body_image(b"\x89PNG\r\n\x1a\n", "a.png")

    url = [u for u in _Handler.urls if "uploadimg" in u][0]
    assert "access_token=TOKEN" in url
    header = _Handler.headers_seen["/cgi-bin/media/uploadimg"]
    assert header.get("Authorization") == "Bearer TOKEN"


def test_draft_add_carries_the_token_in_both_places(server):
    client = WeChatClient("appid", "secret", base_url=server)
    client.add_draft({"articles": []})
    url = [u for u in _Handler.urls if "draft/add" in u][0]
    assert "access_token=TOKEN" in url
    assert _Handler.headers_seen["/cgi-bin/draft/add"].get("Authorization") == "Bearer TOKEN"


def test_the_token_request_itself_carries_no_token(server):
    """Fetching the token must not ask for one."""
    client = WeChatClient("appid", "secret", base_url=server)
    client.stable_token()
    url = [u for u in _Handler.urls if "stable_token" in u][0]
    assert "access_token" not in url


def test_upload_body_image_returns_url(server):
    client = WeChatClient("appid", "secret", base_url=server)
    assert client.upload_body_image(b"\x89PNG\r\n\x1a\n", "a.png") == \
        "https://mmbiz.qpic.cn/mmbiz_jpg/x/1"


def test_upload_body_image_sends_multipart_with_media_field(server):
    client = WeChatClient("appid", "secret", base_url=server)
    client.upload_body_image(b"\x89PNG\r\n\x1a\n", "a.png")
    body = _Handler.bodies["/cgi-bin/media/uploadimg"]
    assert b'name="media"' in body
    assert b'filename="a.png"' in body


def test_upload_cover_returns_media_id(server):
    client = WeChatClient("appid", "secret", base_url=server)
    assert client.upload_cover(b"\x89PNG\r\n\x1a\n", "cover.png") == "COVER_ID"


def test_upload_cover_sends_type_image_param(server):
    client = WeChatClient("appid", "secret", base_url=server)
    client.upload_cover(b"\x89PNG\r\n\x1a\n", "cover.png")
    assert any("material/add_material" in path for path in _Handler.calls)


def test_add_draft_sends_expected_payload(server):
    client = WeChatClient("appid", "secret", base_url=server)
    media_id = client.add_draft({
        "title": "标题",
        "author": "growdu",
        "digest": "摘要",
        "content": "<p>正文</p>",
        "content_source_url": "https://growdu.cn/2026/11/09/a/",
        "thumb_media_id": "COVER",
    })
    assert media_id == "DRAFT_ID"
    payload = json.loads(_Handler.bodies["/cgi-bin/draft/add"])
    article = payload["articles"][0]
    assert article["title"] == "标题"
    assert article["author"] == "growdu"
    assert article["digest"] == "摘要"
    assert article["content"] == "<p>正文</p>"
    assert article["thumb_media_id"] == "COVER"
    assert article["content_source_url"].startswith("https://growdu.cn/")


def test_freepublish_submit_returns_publish_id(server):
    client = WeChatClient("appid", "secret", base_url=server)
    assert client.freepublish_submit("DRAFT_ID") == "PUBLISH_ID"


def test_freepublish_get_returns_status_and_article_id(server):
    client = WeChatClient("appid", "secret", base_url=server)
    status, article_id = client.freepublish_get("PUBLISH_ID")
    assert status == 0
    assert article_id == "ARTICLE_ID"


def test_error_code_raises_wechat_error(server):
    client = WeChatClient("appid", "secret", base_url=server)
    with pytest.raises(WeChatError) as excinfo:
        client._post_json("/unknown/endpoint", {})
    assert excinfo.value.errcode == 404
    assert "not found" in excinfo.value.errmsg
    assert excinfo.value.endpoint == "/unknown/endpoint"


def test_error_message_mentions_the_endpoint(server):
    client = WeChatClient("appid", "secret", base_url=server)
    with pytest.raises(WeChatError) as excinfo:
        client._post_json("/unknown/endpoint", {})
    assert "/unknown/endpoint" in str(excinfo.value)


def test_network_failure_raises_wechat_error():
    client = WeChatClient("appid", "secret", base_url="http://127.0.0.1:1", timeout=2)
    with pytest.raises(WeChatError):
        client.stable_token()


def test_an_expired_token_is_replaced_and_the_call_is_made_again(server):
    """A long batch outlives the token it started with.

    The cached token is then good for nothing, and every remaining call
    of the batch would fail with ``42001`` -- one expired token takes
    the whole rest of the run down with it.
    """
    client = WeChatClient("appid", "secret", base_url=server)
    client.stable_token()
    _Handler.expire_once = {"/cgi-bin/draft/add"}

    assert client.add_draft({"articles": []}) == "DRAFT_ID"
    # The token was fetched again, and the call went out a second time.
    assert _Handler.token_count == 2
    assert _Handler.calls.count("/cgi-bin/draft/add") == 2


def test_an_expired_token_is_replaced_for_the_upload_endpoints_too(server):
    client = WeChatClient("appid", "secret", base_url=server)
    _Handler.expire_once = {"/cgi-bin/media/uploadimg",
                            "/cgi-bin/material/add_material"}

    assert client.upload_body_image(b"\x89PNG\r\n\x1a\n", "a.png")
    assert client.upload_cover(b"\x89PNG\r\n\x1a\n", "a.png") == "COVER_ID"
    assert _Handler.token_count == 3


def test_a_token_that_keeps_failing_still_raises(server):
    """Refreshing is worth one try, not an endless loop."""
    client = WeChatClient("appid", "secret", base_url=server)
    client.stable_token()
    _Handler.expire_once = {"/cgi-bin/draft/add"}

    # The handler expires the call only once, so the second one works.
    assert client.add_draft({"articles": []}) == "DRAFT_ID"


class _FlakyHandler(BaseHTTPRequestHandler):
    """A server that drops connections.

    A dropped connection is not an answer from the API: the client has
    to try again, because an exception that travels out of the
    per-article error handling takes the whole batch down.
    """

    calls = 0
    # How many calls to drop before answering normally.
    drops = 1

    def log_message(self, *args):
        pass

    def do_POST(self):
        _FlakyHandler.calls += 1
        if _FlakyHandler.calls <= _FlakyHandler.drops:
            self.close_connection = True
            try:
                self.connection.close()
            except OSError:
                pass
            return
        body = json.dumps({"access_token": "TOKEN"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def flaky_server():
    _FlakyHandler.calls = 0
    _FlakyHandler.drops = 1
    httpd = HTTPServer(("127.0.0.1", 0), _FlakyHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:{}".format(httpd.server_port)
    httpd.shutdown()


def test_a_dropped_connection_is_retried(flaky_server):
    client = WeChatClient("appid", "secret", base_url=flaky_server)
    assert client.stable_token() == "TOKEN"
    assert _FlakyHandler.calls == 2


def test_a_server_that_never_answers_gives_up_after_three_tryings(flaky_server):
    """The retries are bounded: a dead server must not hang the batch."""
    _FlakyHandler.drops = 99
    client = WeChatClient("appid", "secret", base_url=flaky_server)
    with pytest.raises(WeChatError):
        client._request("/cgi-bin/draft/add", data=b"{}", retries=2)
    assert _FlakyHandler.calls == 2
