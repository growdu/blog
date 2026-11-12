"""Tests for the notification wording and the three backends.

Two layers:

- unit tests: one situation each -- what a state says, what a backend
  would put on the wire;
- integration tests: a message built by ``build_message()`` goes out
  through a backend unchanged.

**No test here touches the network.**  ``_post()`` is replaced by a
recorder, and the assertions look at the URL, the payload and the content
type that *would* have been sent.  A test that really posted to
Server酱 or 企业微信 would make the suite depend on a third party and
could wake somebody up at night.
"""

import json
import urllib.parse

import pytest

from toutiao import notify
from toutiao.notify import STATUS_SUBJECTS, build_message, send


def _recorder(monkeypatch):
    """Replace ``_post()`` with a recorder.  Returns the recorded calls."""
    calls = []

    def fake_post(url, *, data, content_type, timeout):
        calls.append(
            {
                "url": url,
                "data": data,
                "content_type": content_type,
                "timeout": timeout,
            }
        )

    monkeypatch.setattr(notify, "_post", fake_post)
    return calls


def test_three_states_have_three_subjects():
    assert set(STATUS_SUBJECTS) == {"packaged", "drafted", "published"}
    assert STATUS_SUBJECTS["packaged"] == "头条号待上传"
    assert STATUS_SUBJECTS["drafted"] == "头条号待发表"
    assert STATUS_SUBJECTS["published"] == "头条号已发布"


def test_packaged_message_does_not_claim_it_is_published():
    subject, body = build_message("packaged", "演示标题")
    assert "待上传" in subject
    assert "已发布" not in subject
    assert "待上传" in body
    assert "已发布" not in body


def test_published_message_says_published():
    subject, body = build_message("published", "演示标题", detail="https://example.com/x")
    assert "已发布" in subject
    assert "https://example.com/x" in body


def test_drafted_message_does_not_claim_it_is_published():
    subject, body = build_message("drafted", "演示标题")
    assert "待发表" in subject
    assert "已发布" not in subject
    assert "已发布" not in body


def test_detail_is_appended():
    _, body = build_message("drafted", "标题", detail="包目录：toutiao/out/x")
    assert "包目录：toutiao/out/x" in body


def test_unknown_status_is_rejected():
    with pytest.raises(ValueError):
        build_message("posted", "标题")


def test_unknown_backend_is_rejected():
    with pytest.raises(ValueError):
        send("smoke-signal", "key", "主题", "正文")


def test_serverchan_posts_a_form(monkeypatch):
    calls = _recorder(monkeypatch)

    send("serverchan", "SCTKEY", "头条号待上传：标题", "正文")

    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://sctapi.ftqq.com/SCTKEY.send"
    assert call["content_type"] == "application/x-www-form-urlencoded"
    fields = urllib.parse.parse_qs(call["data"].decode("utf-8"))
    assert fields["title"] == ["头条号待上传：标题"]
    assert fields["desp"] == ["正文"]


def test_wechat_work_posts_a_text_message(monkeypatch):
    calls = _recorder(monkeypatch)

    send("wechat_work", "WKKEY", "主题", "正文")

    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=WKKEY"
    assert call["content_type"] == "application/json"
    payload = json.loads(call["data"].decode("utf-8"))
    assert payload["msgtype"] == "text"
    assert payload["text"]["content"] == "主题\n正文"


def test_webhook_posts_to_the_given_url(monkeypatch):
    calls = _recorder(monkeypatch)

    send("webhook", "https://example.com/hook", "主题", "正文")

    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://example.com/hook"
    assert call["content_type"] == "application/json"
    payload = json.loads(call["data"].decode("utf-8"))
    assert payload == {"title": "主题", "body": "正文"}


def test_the_default_timeout_is_fifteen_seconds(monkeypatch):
    calls = _recorder(monkeypatch)

    send("serverchan", "SCTKEY", "主题", "正文")

    assert calls[0]["timeout"] == 15


def test_an_explicit_timeout_reaches_the_transport(monkeypatch):
    calls = _recorder(monkeypatch)

    send("serverchan", "SCTKEY", "主题", "正文", timeout=3)

    assert calls[0]["timeout"] == 3


def test_no_backend_opens_a_socket(monkeypatch):
    """所有后端都只经由 _post() 出网：没有第二个出口。"""
    calls = _recorder(monkeypatch)

    def forbidden(*args, **kwargs):
        raise AssertionError("通知测试不许发真的 HTTP 请求")

    monkeypatch.setattr(notify.urllib.request, "urlopen", forbidden)

    send("serverchan", "SCTKEY", "主题", "正文")
    send("wechat_work", "WKKEY", "主题", "正文")
    send("webhook", "https://example.com/hook", "主题", "正文")

    assert len(calls) == 3


def test_a_built_message_goes_out_unchanged(monkeypatch):
    """集成：措辞与投递连起来 —— 发出去的主题就是 build_message 给的主题。"""
    calls = _recorder(monkeypatch)
    subject, body = build_message("packaged", "演示标题", detail="发布包：toutiao/out/x")

    send("serverchan", "SCTKEY", subject, body)

    fields = urllib.parse.parse_qs(calls[0]["data"].decode("utf-8"))
    assert fields["title"] == [subject]
    assert fields["desp"] == [body]
    assert "已发布" not in fields["desp"][0]
