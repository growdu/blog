"""Notify the author that a package is waiting, or that a post is out.

The wording matters more here than in most tools.  A message that says
"published" when the article is only packaged is the worst possible bug in
a publishing pipeline: the author stops checking and the article never
goes out.  So each state has its own subject line, and the three of them
say three different things:

- ``packaged``  -- the package is on disk, a human still has to upload it
- ``drafted``   -- a draft exists on the platform, a human still has to publish it
- ``published`` -- it is out

**The receipt matters as much as the request.**  Server酱 and 企业微信
both answer HTTP 200 when they refuse the message: the outcome is in the
body (``code`` / ``errcode``).  A notification that only looks at the
HTTP status therefore reports a refusal as a success -- the silent
success this project refuses.  So ``send()`` reads the receipt and
raises when the platform says no, and it tells the two failures apart:
``DeliveryError`` (the request did not go out) and ``ReceiptError`` (it
went out and was refused).

The three backends are thin wrappers over one HTTP POST, so the shape of
each request can be checked without touching the network: the tests
replace ``_post()`` and look at the URL, the payload and the content type
that *would* have been sent, plus the receipt that came back.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

__all__ = [
    "DeliveryError", "NotificationError", "ReceiptError", "STATUS_SUBJECTS",
    "build_message", "send",
]

#: The subject prefix of each state.  The three of them are deliberately
#: different words: 「待上传」/「待发表」/「已发布」 say three different
#: things about what has happened to the article.
STATUS_SUBJECTS = {
    "packaged": "头条号待上传",
    "drafted": "头条号待发表",
    "published": "头条号已发布",
}


class NotificationError(Exception):
    """A notification did not go through."""


class DeliveryError(NotificationError):
    """The request never made it: no answer, or an HTTP error.

    The caller cannot tell whether the platform saw the message, so
    this is the failure that has to be reported.
    """


class ReceiptError(NotificationError):
    """The platform answered, and the answer says the message was refused.

    This is the one that gets missed: the request went out and the
    platform said no.  A caller that only checks the HTTP status calls
    that a success.
    """


def build_message(status: str, title: str, detail: str = "") -> tuple[str, str]:
    """Return ``(subject, body)`` for one status.

    The state comes first in the subject: the subject is what the author
    reads in the notification list, and that is where "已发布" on an
    article that is still waiting to be uploaded does its damage.
    """
    subject_prefix = STATUS_SUBJECTS.get(status)
    if subject_prefix is None:
        raise ValueError("未知状态 {!r}".format(status))
    subject = "{}：{}".format(subject_prefix, title)
    body = "《{}》\n{}".format(title, subject_prefix)
    if detail:
        body += "\n" + detail
    return subject, body


def _post(url: str, *, data: bytes, content_type: str, timeout: int) -> bytes:
    """Send one POST request and return the response body.

    This is the only place in this module that opens a socket.  An HTTP
    error becomes a ``DeliveryError``: the message did not go out, and
    the caller has to know that.
    """
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        # 先抓 HTTPError：它是 URLError 的子类，而 URLError 又是 OSError
        # 的子类，顺序反了 HTTP 的状态码就丢了。
        raise DeliveryError(
            "HTTP {} {}：{}".format(error.code, error.reason, url)
        ) from error
    except OSError as error:
        raise DeliveryError("请求失败：{}".format(error)) from error


def _serverchan(key: str, subject: str, body: str, timeout: int) -> bytes:
    """Server酱: a form post, the key in the path."""
    payload = urllib.parse.urlencode({"title": subject, "desp": body}).encode("utf-8")
    return _post(
        "https://sctapi.ftqq.com/{}.send".format(key),
        data=payload,
        content_type="application/x-www-form-urlencoded",
        timeout=timeout,
    )


def _wechat_work(key: str, subject: str, body: str, timeout: int) -> bytes:
    """企业微信群机器人: a JSON text message, the key in the query."""
    payload = json.dumps(
        {"msgtype": "text", "text": {"content": subject + "\n" + body}}
    ).encode("utf-8")
    return _post(
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={}".format(key),
        data=payload,
        content_type="application/json",
        timeout=timeout,
    )


def _webhook(key: str, subject: str, body: str, timeout: int) -> bytes:
    """A self-hosted webhook: the key is the whole URL."""
    payload = json.dumps({"title": subject, "body": body}).encode("utf-8")
    return _post(key, data=payload, content_type="application/json", timeout=timeout)


_BACKENDS = {
    "serverchan": _serverchan,
    "wechat_work": _wechat_work,
    "webhook": _webhook,
}

#: Which field of the JSON receipt carries the outcome, per backend.
#: ``webhook`` has no agreed convention -- it is a self-hosted endpoint --
#: so only its HTTP status counts for that one.
_RECEIPT_FIELD = {
    "serverchan": "code",
    "wechat_work": "errcode",
}


def _check_receipt(backend: str, field: str, response: bytes) -> None:
    """Confirm the platform's own success code, or refuse it.

    Both platforms answer HTTP 200 when they refuse the message, so the
    outcome is in the body.  A body that cannot be read as the expected
    receipt is a failure too: the point of the check is that a success
    is *confirmed*, and an answer nobody can read confirms nothing.
    """
    if not isinstance(response, (bytes, bytearray)):
        raise ReceiptError(
            "{} 的回执不是字节，无法确认是否送达：{!r}".format(backend, response)
        )
    try:
        payload = json.loads(response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReceiptError(
            "{} 的回执读不出来，无法确认是否送达：{}".format(backend, error)
        ) from error
    if not isinstance(payload, dict):
        raise ReceiptError(
            "{} 的回执不是 JSON 对象，无法确认是否送达：{!r}".format(backend, payload)
        )
    if field not in payload:
        raise ReceiptError(
            "{} 的回执里没有 {} 字段，无法确认是否送达：{}".format(
                backend, field, payload
            )
        )
    code = payload[field]
    # 只有整数 0 算成功：布尔值不算（False == 0），字符串也不算。
    if isinstance(code, bool) or not isinstance(code, int) or code != 0:
        message = payload.get("message") or payload.get("errmsg") or ""
        raise ReceiptError(
            "{} 拒绝了这条通知（{}={}）{}".format(backend, field, code, message)
        )


def send(backend: str, key: str, subject: str, body: str, *, timeout: int = 15) -> None:
    """Push one notification through ``backend``.

    Raises ``ValueError`` for an unknown backend, ``DeliveryError`` when
    the request did not go out, and ``ReceiptError`` when the platform
    answered that it refused the message.

    A notification failure is not a publishing failure: the caller
    decides whether to let the exception out.
    """
    handler = _BACKENDS.get(backend)
    if handler is None:
        raise ValueError("未知通知通道 {!r}".format(backend))
    response = handler(key, subject, body, timeout)
    field = _RECEIPT_FIELD.get(backend)
    if field is not None:
        _check_receipt(backend, field, response)
