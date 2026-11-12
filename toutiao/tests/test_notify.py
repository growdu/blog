"""Tests for the notification wording and the three backends.

Three layers:

- unit tests: one situation each -- what a state says, what a backend
  would put on the wire, what a receipt means;
- integration tests: a message built by ``build_message()`` goes out
  through a backend unchanged.

**No test here touches the network.**  ``_post()`` is replaced by a
recorder, and the assertions look at the URL, the payload and the content
type that *would* have been sent, plus the receipt that came back.  A
test that really posted to Server酱 or 企业微信 would make the suite
depend on a third party and could wake somebody up at night.
"""

import json
import urllib.error
import urllib.parse

import pytest

from toutiao import notify
from toutiao.notify import STATUS_SUBJECTS, build_message, send

#: Each platform's own receipt shape: Server酱 puts the outcome in
#: ``code``, 企业微信 in ``errcode``.
_RECEIPTS = {
    "sctapi.ftqq.com": b'{"code":0,"message":"","data":{}}',
    "qyapi.weixin.qq.com": b'{"errcode":0,"errmsg":"ok"}',
}


def _recorder(monkeypatch, body=None):
    """Replace ``_post()`` with a recorder.  Returns the recorded calls.

    ``body`` overrides the answer the fake platform gives back; the
    default is the receipt each platform really sends.
    """
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
        if body is not None:
            return body
        for host, receipt in _RECEIPTS.items():
            if host in url:
                return receipt
        return b'{"ok":true}'

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
    """未知通道必须被本模块自己拒掉，不能让别人替我们报错。

    两条断言都要有牙：urllib 的 ``ValueError("unknown url type:
    'smoke-signal'")`` 里**也**有 ``smoke-signal``，所以只断言名字的话，
    把越界防护去掉、让它回落到默认通道之后，这条用例仍然绿——类型对，
    但不是本模块的拒绝。
    """
    with pytest.raises(ValueError) as excinfo:
        send("smoke-signal", "key", "主题", "正文")
    assert "smoke-signal" in str(excinfo.value)
    assert "未知通知通道" in str(excinfo.value)


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


# --- the receipt --------------------------------------------------------
#
# HTTP 200 不等于送达：Server酱 与企业微信在 200 的正文里放业务错误码。
# 只看状态码，通知失败会被当成通知成功——项目最恨的那种「静悄悄的成功」。


def test_a_successful_receipt_is_a_success(monkeypatch):
    _recorder(monkeypatch)
    send("serverchan", "SCTKEY", "主题", "正文")


def test_a_refused_serverchan_receipt_is_reported(monkeypatch):
    _recorder(monkeypatch, body=b'{"code":40001,"message":"bad key"}')
    with pytest.raises(notify.ReceiptError) as excinfo:
        send("serverchan", "SCTKEY", "主题", "正文")
    assert "40001" in str(excinfo.value)


def test_a_refused_wechat_work_receipt_is_reported(monkeypatch):
    _recorder(monkeypatch, body=b'{"errcode":93000,"errmsg":"invalid webhook url"}')
    with pytest.raises(notify.ReceiptError) as excinfo:
        send("wechat_work", "WKKEY", "主题", "正文")
    assert "93000" in str(excinfo.value)


def test_an_unreadable_receipt_is_not_a_success(monkeypatch):
    """读不出来的回执确认不了任何事：不能当成成功。"""
    _recorder(monkeypatch, body=b"not json")
    with pytest.raises(notify.ReceiptError):
        send("serverchan", "SCTKEY", "主题", "正文")


def test_a_receipt_without_the_code_field_is_not_a_success(monkeypatch):
    _recorder(monkeypatch, body=b"{}")
    with pytest.raises(notify.ReceiptError):
        send("wechat_work", "WKKEY", "主题", "正文")


def test_a_webhook_has_no_receipt_convention(monkeypatch):
    """自建 webhook 没有约定：只看 HTTP 状态码，正文是什么都不算失败。"""
    _recorder(monkeypatch, body=b"whatever the endpoint answers")
    send("webhook", "https://example.com/hook", "主题", "正文")


def test_an_http_error_is_a_delivery_failure(monkeypatch):
    """HTTP 错误是「没发出去」，跟「发出去了但被拒」是两回事。"""

    def boom(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://sctapi.ftqq.com/SCTKEY.send", 500, "Internal Server Error", {}, None
        )

    monkeypatch.setattr(notify.urllib.request, "urlopen", boom)
    with pytest.raises(notify.DeliveryError) as excinfo:
        send("serverchan", "SCTKEY", "主题", "正文")
    assert "500" in str(excinfo.value)


def test_the_two_failures_are_different_types():
    """调用方要能分辨「没发出去」和「发出去了但被拒」。"""
    assert issubclass(notify.DeliveryError, notify.NotificationError)
    assert issubclass(notify.ReceiptError, notify.NotificationError)
    assert not issubclass(notify.DeliveryError, notify.ReceiptError)
    assert not issubclass(notify.ReceiptError, notify.DeliveryError)
