"""Read the Toutiao capability declaration.

The platform limits live in ``publish/capabilities/toutiao.toml`` -- data,
not code.  The adapter reads them at runtime so that a platform rule change
is a TOML edit and never a code change.
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


def _require(data: dict, key: str, where: str):
    if key not in data:
        raise ValueError("能力模型缺少字段 {}.{}".format(where, key))
    return data[key]


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

    limits_raw = _require(data, "limits", "根")
    adapter_raw = _require(data, "adapter", "根")

    limits = Limits(
        title_chars=int(_require(limits_raw, "title_chars", "limits")),
        body_chars=int(_require(limits_raw, "body_chars", "limits")),
        digest_chars=int(_require(limits_raw, "digest_chars", "limits")),
        image_bytes=int(_require(limits_raw, "image_bytes", "limits")),
        image_formats=tuple(_require(limits_raw, "image_formats", "limits")),
        cover_ratio=str(_require(limits_raw, "cover_ratio", "limits")),
        cover_min_pixels=tuple(_require(limits_raw, "cover_min_pixels", "limits")),
        max_body_images=int(_require(limits_raw, "max_body_images", "limits")),
    )

    return Capability(
        id=str(_require(data, "id", "根")),
        name=str(data.get("name", "")),
        kind=str(data.get("kind", "document")),
        automation=automation,
        review=str(data.get("review", "platform")),
        requires_certification=bool(data.get("requires_certification", False)),
        requires_min_followers=int(data.get("requires_min_followers", 0)),
        verified=data.get("verified"),
        limits=limits,
        adapter_package=str(_require(adapter_raw, "package", "adapter")),
        adapter_command=tuple(_require(adapter_raw, "command", "adapter")),
    )
