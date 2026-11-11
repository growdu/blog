"""Idempotency bookkeeping for WeChat publishing.

Publishing the same article twice is the worst failure mode of an
automated pipeline, so state is kept in three layers:

- the body fingerprint decides whether the content changed at all
- ``media_id`` records that a draft already exists
- ``publish_id`` records that a publish is already in flight

The state file lives next to the other build output and is never
committed.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

__all__ = ["PublishState", "StateStore", "needs_draft", "needs_submit"]


@dataclass
class PublishState:
    """What we already did with one post."""

    fingerprint: str | None = None
    media_id: str | None = None
    publish_id: str | None = None
    publish_status: int | None = None
    updated_at: str | None = None


class StateStore:
    """A JSON file holding the state of every post we have published."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def _load_all(self) -> dict:
        if not self.path.is_file():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(raw, dict):
            return {}
        posts = raw.get("posts", {})
        return posts if isinstance(posts, dict) else {}

    def all(self) -> dict:
        return self._load_all()

    def get(self, slug: str) -> PublishState:
        entry = self._load_all().get(slug)
        if not isinstance(entry, dict):
            return PublishState()
        known = {name: entry.get(name) for name in PublishState.__dataclass_fields__}
        return PublishState(**known)

    def save(self, slug: str, state: PublishState) -> None:
        posts = self._load_all()
        state.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        posts[slug] = asdict(state)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"posts": posts}, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def needs_draft(fingerprint: str, state: PublishState) -> bool:
    """True when a fresh draft has to be created for this content."""
    if not state.media_id:
        return True
    return state.fingerprint != fingerprint


def needs_submit(state: PublishState) -> bool:
    """True when the article still has to be submitted for publishing."""
    return not state.publish_id
