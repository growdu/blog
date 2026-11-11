"""Read the Toutiao capability declaration.

The platform limits live in ``publish/capabilities/toutiao.toml`` -- data,
not code.  The adapter reads them at runtime so that a platform rule change
is a TOML edit and never a code change.

The declaration is external input, so every field is validated strictly:
a malformed value raises ``ValueError`` naming the offending field
(``limits.title_chars``), never ``TypeError`` and never a silent coercion.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "AUTOMATIONS", "Capability", "Limits", "default_capability_path",
    "load_capability",
]

AUTOMATIONS = ("manual", "api_draft", "api_publish")

_REPO_ROOT = Path(__file__).resolve().parents[2]

_REQUIRED = object()


@dataclass(frozen=True)
class Limits:
    """What the platform accepts."""

    title_chars: int
    body_chars: int
    digest_chars: int
    image_bytes: int
    image_formats: tuple[str, ...]
    cover_ratio: str
    cover_min_pixels: tuple[int, int]
    max_body_images: int


@dataclass(frozen=True)
class Capability:
    """The whole declaration for one platform."""

    id: str
    name: str
    kind: str
    automation: str
    review: str
    requires_certification: bool
    requires_min_followers: int
    verified: str | None
    limits: Limits
    adapter_package: str
    adapter_command: tuple[str, ...]


def default_capability_path() -> Path:
    """The declaration shipped with the repository."""
    return _REPO_ROOT / "publish" / "capabilities" / "toutiao.toml"


# --- 字段校验 -----------------------------------------------------------
#
# 能力声明是外部输入（一份 TOML 文件）。写错的值必须以 ValueError 拒绝，
# 而且消息里要带字段全名 —— 否则调用方的 except ValueError 会被 TypeError
# 穿透，报错也指不到是哪个字段的问题。


def _type_name(value: object) -> str:
    return type(value).__name__


def _path(parent: str, key: str) -> str:
    """Dotted field path: ``limits`` + ``title_chars`` -> ``limits.title_chars``."""
    return "{}.{}".format(parent, key) if parent else key


def _lookup(data: object, key: str, parent: str):
    """Return ``(found, value)`` for one key of a table.

    A non-table ``data`` is an error in its own right -- checking
    ``key not in data`` against a string would silently degrade into a
    substring test.
    """
    if not isinstance(data, dict):
        raise ValueError(
            "能力模型字段 {} 期望是表/映射，实际是 {}".format(
                parent or "根", _type_name(data)
            )
        )
    if key not in data:
        return False, None
    return True, data[key]


def _table(data: object, key: str, parent: str = "") -> dict:
    """Fetch a required table; a non-table value is rejected as such."""
    found, value = _lookup(data, key, parent)
    if not found:
        raise ValueError("能力模型缺少字段 {}".format(_path(parent, key)))
    if not isinstance(value, dict):
        raise ValueError(
            "能力模型字段 {} 期望是表/映射，实际是 {}".format(
                _path(parent, key), _type_name(value)
            )
        )
    return value


def _convert(value: object, path: str, converter):
    """Run one strict conversion; TypeError/ValueError become ValueError."""
    try:
        return converter(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "能力模型字段 {} 不合法：{}".format(path, exc)
        ) from exc


def _field(data: object, key: str, parent: str, converter, default=_REQUIRED):
    """Read one field and convert it strictly.

    A missing key falls back to ``default`` when one is given, and is an
    error otherwise.  A present-but-wrong value always raises.
    """
    found, value = _lookup(data, key, parent)
    if not found:
        if default is _REQUIRED:
            raise ValueError("能力模型缺少字段 {}".format(_path(parent, key)))
        return default
    return _convert(value, _path(parent, key), converter)


def _as_int(value: object) -> int:
    """A TOML integer.  A bool is not an int here, and a float is not truncated."""
    if isinstance(value, bool):
        raise TypeError("布尔值不是整数")
    if not isinstance(value, int):
        raise TypeError("不是整数")
    return value


def _as_str(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("不是字符串")
    return value


def _as_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise TypeError("不是布尔值")
    return value


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError("不是字符串数组")
    for item in value:
        if not isinstance(item, str):
            raise TypeError("数组元素不是字符串")
    return tuple(value)


def _as_int_pair(value: object) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)):
        raise TypeError("不是数组")
    if len(value) != 2:
        raise ValueError("必须正好 2 个整数，实际有 {} 个".format(len(value)))
    return (_as_int(value[0]), _as_int(value[1]))


def load_capability(path: Path) -> Capability:
    """Load and validate one capability declaration."""
    path = Path(path)
    with path.open("rb") as handle:
        data = tomllib.load(handle)

    automation = data.get("automation", "")
    if automation not in AUTOMATIONS:
        raise ValueError(
            "automation 必须是 {} 之一，实际是 {!r}".format(
                " / ".join(AUTOMATIONS), automation
            )
        )

    limits_raw = _table(data, "limits")
    adapter_raw = _table(data, "adapter")

    limits = Limits(
        title_chars=_field(limits_raw, "title_chars", "limits", _as_int),
        body_chars=_field(limits_raw, "body_chars", "limits", _as_int),
        digest_chars=_field(limits_raw, "digest_chars", "limits", _as_int),
        image_bytes=_field(limits_raw, "image_bytes", "limits", _as_int),
        image_formats=_field(
            limits_raw, "image_formats", "limits", _as_str_tuple
        ),
        cover_ratio=_field(limits_raw, "cover_ratio", "limits", _as_str),
        cover_min_pixels=_field(
            limits_raw, "cover_min_pixels", "limits", _as_int_pair
        ),
        max_body_images=_field(
            limits_raw, "max_body_images", "limits", _as_int
        ),
    )

    return Capability(
        id=_field(data, "id", "", _as_str),
        name=_field(data, "name", "", _as_str, default=""),
        kind=_field(data, "kind", "", _as_str, default="document"),
        automation=automation,
        review=_field(data, "review", "", _as_str, default="platform"),
        requires_certification=_field(
            data, "requires_certification", "", _as_bool, default=False
        ),
        requires_min_followers=_field(
            data, "requires_min_followers", "", _as_int, default=0
        ),
        verified=_field(data, "verified", "", _as_str, default=None),
        limits=limits,
        adapter_package=_field(adapter_raw, "package", "adapter", _as_str),
        adapter_command=_field(
            adapter_raw, "command", "adapter", _as_str_tuple
        ),
    )
