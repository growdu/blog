"""Push a note to the phone when a draft is waiting.

This account cannot publish on its own: WeChat revoked the publishing
API for personal, unverified accounts, so the last click is a human's
job.  That makes a notification worth sending -- otherwise you have to
come back to the console to find out a draft is ready.

Three backends are supported, chosen with the ``WX_NOTIFY`` environment
variable:

=============  ==================================================
``serverchan``  Server酱 -- pushes straight into WeChat.  Needs a
               SendKey from https://sct.ftqq.com (free tier: five
               messages a day, enough for one article a day).
``wechat_work`` A WeCom group robot.  Needs the webhook URL from the
               group.
``webhook``     Any endpoint that accepts a JSON body with ``title``
               and ``body`` -- Bark, Discord, a self-hosted relay.
=============  ==================================================

The key itself goes in ``WX_NOTIFY_KEY``.  With nothing configured the
tool stays quiet: a missing notification is never an error.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

__all__ = ["NotifyError", "BACKENDS", "send", "describe"]

_USER_AGENT = "weixin-wechat/1.0"

# Where the human goes to publish the draft.
DRAFT_BOX_URL = "https://mp.weixin.qq.com/"


class NotifyError(RuntimeError):
    """The notification could not be delivered."""


def _post(url: str, *, data: bytes, content_type: str, timeout: int):
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": content_type,
                                 "User-Agent": _USER_AGENT}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        raise NotifyError("HTTP {} from {}".format(error.code, url)) from error
    except urllib.error.URLError as error:
        raise NotifyError("{} ({})".format(error.reason, url)) from error


def _serverchan(key: str, title: str, body: str, timeout: int) -> None:
    """Server酱 (Turbo).  Sends straight into WeChat.

    A Turbo SendKey starts with ``SCT`` and uses ``sctapi.ftqq.com``.
    The older ``SC`` keys use ``sc.ftqq.com``, and the ``sctp`` family
    needs the uid form.
    """
    if key.startswith("sctp"):
        # sctp<uid>t<token>: the uid is the part between "sctp" and the
        # next "t" -- the one inside "sctp" does not count.
        uid = key[4:key.index("t", 4)]
        url = "https://{}.push.ft07.com/send/{}.send".format(uid, key)
    elif key.startswith("SC") and not key.startswith("SCT"):
        # The legacy "SC..." keys; "SCT..." is Turbo and must be checked
        # first, because "SCT".startswith("SC") is true.
        url = "https://sc.ftqq.com/{}.send".format(key)
    else:
        url = "https://sctapi.ftqq.com/{}.send".format(key)

    payload = urllib.parse.urlencode({"title": title, "desp": body}).encode("utf-8")
    raw = _post(url, data=payload, content_type="application/x-www-form-urlencoded",
                timeout=timeout)
    try:
        result = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    code = result.get("code", result.get("errno", 0))
    if code:
        raise NotifyError("Server酱: {}".format(result.get("message", "code={}".format(code))))


def _wechat_work(key: str, title: str, body: str, timeout: int) -> None:
    """A WeCom group robot webhook."""
    url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={}".format(
        urllib.parse.quote(key))
    payload = json.dumps({
        "msgtype": "text",
        "text": {"content": "{}\n{}".format(title, body)},
    }).encode("utf-8")
    raw = _post(url, data=payload, content_type="application/json", timeout=timeout)
    try:
        result = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if result.get("errcode"):
        raise NotifyError("企业微信: {}".format(result.get("errmsg", "unknown")))


def _webhook(key: str, title: str, body: str, timeout: int) -> None:
    """Any endpoint that accepts ``{"title": ..., "body": ...}``."""
    payload = json.dumps({"title": title, "body": body}).encode("utf-8")
    _post(key, data=payload, content_type="application/json", timeout=timeout)


BACKENDS = {
    "serverchan": _serverchan,
    "wechat_work": _wechat_work,
    "webhook": _webhook,
}


def describe(backend: str, key: str) -> str:
    """A short description of where a notification would go."""
    if backend == "serverchan":
        return "Server酱 -> 微信"
    if backend == "wechat_work":
        return "企业微信群机器人"
    if backend == "webhook":
        return "自定义 webhook"
    return backend or "未配置"


def send(backend: str, key: str, title: str, body: str, *, timeout: int = 15) -> None:
    """Send one message through ``backend``.

    Raises :class:`NotifyError` when the message could not be delivered.
    Callers treat that as a warning, never as a failure of the thing
    that was being announced.
    """
    if not backend or not key:
        return
    handler = BACKENDS.get(backend)
    if handler is None:
        raise NotifyError("未知的通知通道: {}（可用: {}）".format(
            backend, ", ".join(sorted(BACKENDS))))
    handler(key, title, body, timeout)
