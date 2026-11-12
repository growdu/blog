"""WeChat official account API client.

Only the standard library is used: ``urllib`` for HTTP and a hand-written
multipart encoder for the two upload endpoints.  Every non-zero
``errcode`` is raised as :class:`WeChatError` -- a pipeline that swallows
API errors reports success while nothing was published.

Note on tokens: ``/cgi-bin/stable_token`` is used rather than
``/cgi-bin/token`` because the legacy endpoint invalidates the previous
token on every call, which breaks two jobs that overlap.
"""

from __future__ import annotations

import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
import uuid

__all__ = ["WeChatClient", "WeChatError", "DEFAULT_BASE_URL", "PUBLISH_STATUS"]

DEFAULT_BASE_URL = "https://api.weixin.qq.com"

PUBLISH_STATUS = {
    0: "发布成功",
    1: "发布中",
    2: "原创失败",
    3: "常规失败",
    4: "平台审核不通过",
}


class WeChatError(RuntimeError):
    """A WeChat API call returned a non-zero errcode."""

    def __init__(self, errcode: int, errmsg: str, endpoint: str):
        super().__init__("{} failed: [{}] {}".format(endpoint, errcode, errmsg))
        self.errcode = errcode
        self.errmsg = errmsg
        self.endpoint = endpoint


class WeChatClient:
    """Thin, explicit wrapper over the endpoints the pipeline needs."""

    def __init__(self, appid: str, appsecret: str, *, base_url: str = DEFAULT_BASE_URL,
                 timeout: int = 30):
        self.appid = appid
        self.appsecret = appsecret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._token = None

    # -- transport ----------------------------------------------------

    def _request(self, path: str, *, data=None, headers=None, params=None, token=None):
        url = self.base_url + path
        query = dict(params or {})
        if token:
            query["access_token"] = token
        if query:
            url += "?" + urllib.parse.urlencode(query)
        request = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            raw = error.read()
        except urllib.error.URLError as error:
            raise WeChatError(-1, "network error: {}".format(error), path) from error
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise WeChatError(-1, "non-JSON response: {}".format(raw[:200]), path) from error

    def _post_json(self, path: str, payload: dict, *, with_token: bool = True):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        token = self.stable_token() if with_token else None
        if token:
            headers["Authorization"] = "Bearer {}".format(token)
        response = self._request(path, data=body, headers=headers, token=token)
        errcode = response.get("errcode", 0)
        if errcode:
            raise WeChatError(errcode, response.get("errmsg", ""), path)
        return response

    def _post_multipart(self, path: str, filename: str, data: bytes, *, params=None):
        boundary = "----mavisweixin{}".format(uuid.uuid4().hex)
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        body = b"".join([
            "--{}\r\n".format(boundary).encode(),
            'Content-Disposition: form-data; name="media"; filename="{}"\r\n'.format(
                filename).encode("utf-8"),
            "Content-Type: {}\r\n\r\n".format(content_type).encode(),
            data,
            "\r\n--{}--\r\n".format(boundary).encode(),
        ])
        token = self.stable_token()
        headers = {
            "Content-Type": "multipart/form-data; boundary={}".format(boundary),
            "Authorization": "Bearer {}".format(token),
        }
        response = self._request(path, data=body, headers=headers, params=params, token=token)
        errcode = response.get("errcode", 0)
        if errcode:
            raise WeChatError(errcode, response.get("errmsg", ""), path)
        return response

    # -- endpoints ----------------------------------------------------

    def stable_token(self) -> str:
        """Fetch (and cache) an access token.

        The official field table calls the credential ``appsecret``, but
        the live endpoint only reads ``secret`` -- sending ``appsecret``
        alone is answered with ``41004 appsecret missing``.  Both names
        are sent so the call works whichever one the endpoint looks for.
        """
        if self._token:
            return self._token
        payload = {
            "grant_type": "client_credential",
            "appid": self.appid,
            "secret": self.appsecret,
            "appsecret": self.appsecret,
            "force_refresh": False,
        }
        response = self._post_json("/cgi-bin/stable_token", payload, with_token=False)
        token = response.get("access_token")
        if not token:
            raise WeChatError(-1, "no access_token in response", "/cgi-bin/stable_token")
        self._token = token
        return token

    def upload_body_image(self, data: bytes, filename: str) -> str:
        """Upload an inline image and return its mmbiz URL."""
        response = self._post_multipart("/cgi-bin/media/uploadimg", filename, data)
        url = response.get("url")
        if not url:
            raise WeChatError(-1, "no url in response", "/cgi-bin/media/uploadimg")
        return url

    def upload_cover(self, data: bytes, filename: str) -> str:
        """Upload the cover image and return its material media_id."""
        response = self._post_multipart(
            "/cgi-bin/material/add_material", filename, data,
            params={"type": "image"},
        )
        media_id = response.get("media_id")
        if not media_id:
            raise WeChatError(-1, "no media_id in response", "/cgi-bin/material/add_material")
        return media_id

    def add_draft(self, article: dict) -> str:
        """Create a draft and return its media_id."""
        response = self._post_json("/cgi-bin/draft/add", {"articles": [article]})
        media_id = response.get("media_id")
        if not media_id:
            raise WeChatError(-1, "no media_id in response", "/cgi-bin/draft/add")
        return media_id

    def list_drafts(self, page_size: int = 20) -> list:
        """List the drafts that are currently in the box.

        ``draft/batchget`` returns at most ``page_size`` items per
        call, so the whole box is walked page by page.  ``no_content``
        keeps the payload small: the article body is left out and only
        the title comes back, which is all a reconciliation needs.

        The walk follows ``total_count`` rather than the number of
        items that came back: a box that holds more drafts than one
        page is only finished when the count says so.
        """
        drafts = []
        offset = 0
        while True:
            response = self._post_json("/cgi-bin/draft/batchget", {
                "offset": offset,
                "count": page_size,
                "no_content": 1,
            })
            items = response.get("item") or []
            for item in items:
                news = ((item.get("content") or {}).get("news_item") or [])
                title = news[0].get("title", "") if news else ""
                drafts.append({
                    "media_id": item.get("media_id", ""),
                    "title": title,
                })
            if not items:
                break
            offset += len(items)
            total = response.get("total_count")
            if total is not None:
                if offset >= total:
                    break
            elif len(items) < page_size:
                break
        return drafts

    def update_draft(self, media_id: str, article: dict, index: int = 0) -> None:
        """Replace one article of an existing draft, in place.

        ``draft/add`` always creates *another* draft, so an edited
        article would leave the previous version behind in the box and
        the reader would find two versions of the same piece.
        Updating in place keeps the box free of stale copies.

        Unlike ``add``, ``articles`` here is a single object rather
        than a list, and the position inside a multi-article draft is
        given by ``index``.
        """
        self._post_json("/cgi-bin/draft/update", {
            "media_id": media_id,
            "index": index,
            "articles": article,
        })

    def delete_draft(self, media_id: str) -> None:
        """Remove a draft from the box.

        Used when an article needs fewer parts than it did before: the
        drafts of the parts that are gone would otherwise sit in the
        box looking like current content.
        """
        self._post_json("/cgi-bin/draft/delete", {"media_id": media_id})

    def freepublish_submit(self, media_id: str) -> str:
        """Submit a draft for publishing; returns the asynchronous publish_id."""
        response = self._post_json("/cgi-bin/freepublish/submit", {"media_id": media_id})
        publish_id = response.get("publish_id")
        if not publish_id:
            raise WeChatError(-1, "no publish_id in response", "/cgi-bin/freepublish/submit")
        return publish_id

    def freepublish_get(self, publish_id: str) -> tuple:
        """Poll a publish; returns ``(publish_status, article_id)``."""
        response = self._post_json("/cgi-bin/freepublish/get", {"publish_id": publish_id})
        return response.get("publish_status", -1), response.get("article_id")
