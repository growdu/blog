"""发布清单（manifest）：一个内容单元 × 一个平台。

manifest 是**纯数据、可重放**的：同样的输入必须产出同样的清单，所以它不含
时间戳、不含随机数、更不含任何凭据（``publish/spec/00-架构设计.md`` §6、§7.1）。

清单的 JSON 格式是契约层与平台 adapter 之间的**唯一接缝之一**（另一个是
``[adapter].command``）：adapter 只认这份 JSON 的字段名，**不 import 契约层**
（§11.1）。所以字段名一旦定下就是对外契约，改它要改规格文档。

字段清单（必填 / 可选见 ``Manifest.from_dict`` 的校验）：

===============  ======  ==============================================
字段             必填    说明
===============  ======  ==============================================
content_id       是      内容单元 id（相对 ``source/_posts/`` 的路径去后缀）
platform         是      平台 id
kind             是      ``document`` / ``video``
title            是      标题，须落在 ``limits.title_chars`` 内
body_html        是      已按平台要求渲染的正文（视频平台可以为空串）
digest           否      摘要，默认空串
cover            否      封面图路径，默认空串
source_url       否      母稿在站上的地址，默认空串
assets           否      附图路径列表，默认空列表
===============  ======  ==============================================
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from . import PublishKitError

__all__ = [
    "Manifest",
    "ManifestError",
    "ManifestFieldError",
    "validate_manifest",
]

#: 内容单元类型（与能力模型的 ``kind`` 同一套取值）。
KINDS = ("document", "video")

_REQUIRED_FIELDS = ("content_id", "platform", "kind", "title", "body_html")
_OPTIONAL_FIELDS = ("digest", "cover", "source_url", "assets")


class ManifestError(PublishKitError):
    """发布清单读不了，或内容不合法。"""


class ManifestFieldError(ManifestError):
    """某个字段缺失、类型不对，或取值不在域内。"""


@dataclass(frozen=True)
class Manifest:
    """One manifest: one content unit, one platform.

    用 ``from_dict`` / ``from_json`` 读，用 ``to_dict`` / ``to_json`` 写。
    字段是固定的，序列化结果稳定（同一个 manifest 序列化两次结果一致）。
    """

    content_id: str
    platform: str
    kind: str
    title: str
    body_html: str
    digest: str = ""
    cover: str = ""
    source_url: str = ""
    assets: tuple = ()

    # --- 构造 -----------------------------------------------------------

    @classmethod
    def from_dict(cls, data: object) -> "Manifest":
        """Build a manifest from a plain dict, validating every field."""
        if not isinstance(data, dict):
            raise ManifestFieldError(
                "发布清单必须是映射，实际是 {}".format(type(data).__name__)
            )

        allowed = _REQUIRED_FIELDS + _OPTIONAL_FIELDS
        for key in data:
            if key not in allowed:
                raise ManifestFieldError("发布清单出现未知字段 {}".format(key))

        values = {}
        for key in _REQUIRED_FIELDS:
            if key not in data:
                raise ManifestFieldError("发布清单缺少字段 {}".format(key))
            values[key] = _as_str(data[key], key)

        for key in ("digest", "cover", "source_url"):
            if key in data:
                values[key] = _as_str(data[key], key)

        assets = ()
        if "assets" in data:
            assets = _as_str_list(data["assets"], "assets")

        if values["kind"] not in KINDS:
            raise ManifestFieldError(
                "发布清单字段 kind 必须是 {} 之一，实际是 {!r}".format(
                    " / ".join(KINDS), values["kind"]
                )
            )
        if not values["content_id"].strip():
            raise ManifestFieldError("发布清单字段 content_id 不能为空")
        if not values["platform"].strip():
            raise ManifestFieldError("发布清单字段 platform 不能为空")
        if not values["title"].strip():
            raise ManifestFieldError("发布清单字段 title 不能为空")

        return cls(assets=assets, **values)

    @classmethod
    def from_json(cls, text: str) -> "Manifest":
        """Build a manifest from its JSON serialization."""
        if not isinstance(text, str):
            raise ManifestFieldError(
                "发布清单 JSON 必须是字符串，实际是 {}".format(type(text).__name__)
            )
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ManifestFieldError("发布清单不是合法 JSON：{}".format(exc)) from exc
        return cls.from_dict(data)

    # --- 序列化 ---------------------------------------------------------

    def to_dict(self) -> dict:
        """The manifest as a plain dict, with a stable key order."""
        return {
            "content_id": self.content_id,
            "platform": self.platform,
            "kind": self.kind,
            "title": self.title,
            "body_html": self.body_html,
            "digest": self.digest,
            "cover": self.cover,
            "source_url": self.source_url,
            "assets": list(self.assets),
        }

    def to_json(self, *, indent=None) -> str:
        """The manifest as JSON.  Deterministic: same manifest, same bytes."""
        return json.dumps(
            self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=False
        )

    # --- 校验 -----------------------------------------------------------

    def validate(self, capability) -> list:
        """Check the manifest against one platform's capability declaration.

        Returns the list of violations (empty means eligible).  超限**不截断**：
        截断出来的标题和正文对读者没有意义，反而掩盖问题（§6.2）。
        """
        violations = []

        declared_kind = getattr(capability, "kind", None)
        if declared_kind is not None and declared_kind != self.kind:
            violations.append(
                "清单 kind 是 {}，而平台 {} 声明的是 {}".format(
                    self.kind, getattr(capability, "id", "?"), declared_kind
                )
            )

        limits = getattr(capability, "limits", None) or {}

        title_limit = limits.get("title_chars")
        if isinstance(title_limit, int) and len(self.title) > title_limit:
            violations.append(
                "标题 {} 字，超过平台上限 {} 字".format(len(self.title), title_limit)
            )

        digest_limit = limits.get("digest_chars")
        if isinstance(digest_limit, int) and len(self.digest) > digest_limit:
            violations.append(
                "摘要 {} 字，超过平台上限 {} 字".format(
                    len(self.digest), digest_limit
                )
            )

        body_limit = limits.get("body_chars")
        if isinstance(body_limit, int) and len(self.body_html) > body_limit:
            violations.append(
                "正文 {} 字，超过平台上限 {} 字".format(
                    len(self.body_html), body_limit
                )
            )

        max_images = limits.get("max_body_images")
        if isinstance(max_images, int) and len(self.assets) > max_images:
            violations.append(
                "附图 {} 张，超过平台上限 {} 张".format(len(self.assets), max_images)
            )

        return violations

    def is_eligible(self, capability) -> bool:
        """Whether this manifest may enter the publishing stage."""
        return not self.validate(capability)


def validate_manifest(manifest: Manifest, capability) -> list:
    """Functional spelling of :meth:`Manifest.validate`."""
    return manifest.validate(capability)


def _as_str(value: object, key: str) -> str:
    if not isinstance(value, str):
        raise ManifestFieldError(
            "发布清单字段 {} 必须是字符串，实际是 {}".format(
                key, type(value).__name__
            )
        )
    return value


def _as_str_list(value: object, key: str) -> tuple:
    if not isinstance(value, list):
        raise ManifestFieldError(
            "发布清单字段 {} 必须是数组，实际是 {}".format(
                key, type(value).__name__
            )
        )
    for item in value:
        if not isinstance(item, str):
            raise ManifestFieldError(
                "发布清单字段 {} 的元素必须是字符串，实际有一个是 {}".format(
                    key, type(item).__name__
                )
            )
    return tuple(value)
