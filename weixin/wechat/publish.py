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

    def _request(self, path: str, *, data=None, headers=None, params=None):
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
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
        if with_token:
            headers["Authorization"] = "Bearer {}".format(self.stable_token())
        response = self._request(path, data=body, headers=headers)
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
        headers = {
            "Content-Type": "multipart/form-data; boundary={}".format(boundary),
            "Authorization": "Bearer {}".format(self.stable_token()),
        }
        response = self._request(path, data=body, headers=headers, params=params)
        errcode = response.get("errcode", 0)
        if errcode:
            raise WeChatError(errcode, response.get("errmsg", ""), path)
        return response

    # -- endpoints ----------------------------------------------------

    def stable_token(self) -> str:
        """Fetch (and cache) an access token."""
        if self._token:
            return self._token
        payload = {
            "grant_type": "client_credential",
            "appid": self.appid,
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
