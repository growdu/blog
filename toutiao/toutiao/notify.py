"""Notify the author that a package is waiting, or that a post is out.

The wording matters more here than in most tools.  A message that says
"published" when the article is only packaged is the worst possible bug in
a publishing pipeline: the author stops checking and the article never
goes out.  So each state has its own subject line, and the three of them
say three different things:

- ``packaged``  -- the package is on disk, a human still has to upload it
- ``drafted``   -- a draft exists on the platform, a human still has to publish it
- ``published`` -- it is out

The three backends are thin wrappers over one HTTP POST, so the shape of
each request can be checked without touching the network: the tests
replace ``_post()`` and look at the URL, the payload and the content type
that *would* have been sent.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

__all__ = ["STATUS_SUBJECTS", "build_message", "send"]

#: The subject prefix of each state.  The three of them are deliberately
#: different words: 「待上传」/「待发表」/「已发布」 say three different
#: things about what has happened to the article.
STATUS_SUBJECTS = {
    "packaged": "头条号待上传",
    "drafted": "头条号待发表",
    "published": "头条号已发布",
}


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


def _post(url: str, *, data: bytes, content_type: str, timeout: int) -> None:
    """Send one POST request -- the only place in this module that opens
    a socket."""
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", content_type)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response.read()


def _serverchan(key: str, subject: str, body: str, timeout: int) -> None:
    """Server酱: a form post, the key in the path."""
    payload = urllib.parse.urlencode({"title": subject, "desp": body}).encode("utf-8")
    _post(
        "https://sctapi.ftqq.com/{}.send".format(key),
        data=payload,
        content_type="application/x-www-form-urlencoded",
        timeout=timeout,
    )


def _wechat_work(key: str, subject: str, body: str, timeout: int) -> None:
    """企业微信群机器人: a JSON text message, the key in the query."""
    payload = json.dumps(
        {"msgtype": "text", "text": {"content": subject + "\n" + body}}
    ).encode("utf-8")
    _post(
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={}".format(key),
        data=payload,
        content_type="application/json",
        timeout=timeout,
    )


def _webhook(key: str, subject: str, body: str, timeout: int) -> None:
    """A self-hosted webhook: the key is the whole URL."""
    payload = json.dumps({"title": subject, "body": body}).encode("utf-8")
    _post(key, data=payload, content_type="application/json", timeout=timeout)


_BACKENDS = {
    "serverchan": _serverchan,
    "wechat_work": _wechat_work,
    "webhook": _webhook,
}


def send(backend: str, key: str, subject: str, body: str, *, timeout: int = 15) -> None:
    """Push one notification through ``backend``.

    A notification failure is not a publishing failure: the caller decides
    whether to let the exception out.
    """
    handler = _BACKENDS.get(backend)
    if handler is None:
        raise ValueError("未知通知通道 {!r}".format(backend))
    handler(key, subject, body, timeout)
