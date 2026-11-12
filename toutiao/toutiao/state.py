"""Idempotency bookkeeping for Toutiao publishing.

Publishing the same article twice is the worst failure mode of an automated
pipeline, so the state is kept in three layers:

- the body fingerprint decides whether the content changed at all
- the platform-side id (``object_id``) records that a post already exists
- ``published_url`` records that it is out there

**Two state mechanisms live in this project, and they are not the same
thing.**  Mixing them up is the easy mistake here:

- ``publish/outbox/<content_id>__<platform>.json`` is the *committed*
  idempotency key: the snapshot written by ``publish.py``.  It is public,
  it goes into the repository, and it is what the "already published, do
  not publish again" rule reads.
- ``toutiao/out/state.json`` is this machine's *working record*: the
  content fingerprint, the state of an attempt, the package directory.
  ``toutiao/.gitignore`` excludes it and it never enters the repository.

The fingerprint covers the *sliced Toutiao body* -- ``fingerprint(result.
article.body)`` in the CLI -- not the source post.  Only a change in what
actually goes out is a change worth republishing for: a paragraph the
slicer drops is not a new article.

A corrupt state file is never swallowed.  It is renamed to
``<path>.corrupt`` -- the bytes are kept as evidence -- and the store
remembers where it went in ``quarantined`` so the caller can report it
loudly.  Reading a broken file as "nothing was ever published" would
republish everything, and publishing twice is much worse than being slow.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

__all__ = ["PublishState", "StateStore", "fingerprint", "needs_publish"]


@dataclass
class PublishState:
    """What we already did with one article.

    Mutable on purpose: the CLI reads a record, fills in what it just
    learned (``fingerprint``, ``status``) and hands the same object back
    to ``StateStore.save()``.
    """

    fingerprint: str | None = None
    status: str | None = None
    object_id: str | None = None
    published_url: str | None = None
    updated_at: str | None = None
    package_dir: str | None = None


def fingerprint(body: str) -> str:
    """The content hash used to detect a changed article.

    The body is the Toutiao version that would be published, not the
    source post -- see the module docstring.
    """
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class StateStore:
    """A JSON file holding the state of every article we have packaged.

    The file is this machine's own working record (``toutiao/out/
    state.json``) and is never committed.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        #: The broken file that was moved aside, if there was one.
        #: ``None`` until the store has read its file.
        self.quarantined: Path | None = None

    def _load_all(self) -> dict:
        """Every record, keyed by content id.

        A file that cannot be read as the expected shape is moved aside
        and the records are treated as empty -- the caller has to be
        told about it (``quarantined``), because an empty state reads as
        "never published".
        """
        if not self.path.is_file():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            self._quarantine()
            return {}
        if not isinstance(raw, dict):
            self._quarantine()
            return {}
        articles = raw.get("articles", {})
        if not isinstance(articles, dict):
            self._quarantine()
            return {}
        return articles

    def _quarantine(self) -> None:
        """Move a broken state file aside, keeping the evidence.

        The file is renamed, never deleted: whatever went wrong, the
        bytes that caused it are worth keeping for the next look.
        """
        target = self._quarantine_path()
        try:
            self.path.rename(target)
        except OSError:
            # The file could not be moved aside (permissions, a race).
            # It stays where it is, the caller still gets an empty state,
            # and ``quarantined`` stays ``None`` so that nothing claims
            # the file was dealt with.
            return
        self.quarantined = target

    def _quarantine_path(self) -> Path:
        """A free ``<name>.corrupt`` path next to the state file.

        An earlier quarantine must not be overwritten: it is the evidence
        of an earlier failure.
        """
        candidate = self.path.with_name(self.path.name + ".corrupt")
        index = 1
        while candidate.exists():
            candidate = self.path.with_name(
                "{}.corrupt.{}".format(self.path.name, index)
            )
            index += 1
        return candidate

    def all(self) -> dict:
        """Every recorded article, keyed by content id."""
        return self._load_all()

    def get(self, content_id: str) -> PublishState:
        """The record of one article; an empty one when there is none."""
        entry = self._load_all().get(content_id)
        if not isinstance(entry, dict):
            return PublishState()
        known = {name: entry.get(name) for name in PublishState.__dataclass_fields__}
        return PublishState(**known)

    def save(self, content_id: str, state: PublishState) -> None:
        """Write one record, stamped with the time of the write.

        The caller's object is left alone: a store that quietly stamps
        the object it was handed makes the caller's ``updated_at`` mean
        "somebody wrote this somewhere" instead of "this was stored".
        The timestamp therefore goes onto a copy.
        """
        articles = self._load_all()
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        articles[content_id] = asdict(replace(state, updated_at=stamp))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {"articles": articles}, ensure_ascii=False, indent=2, sort_keys=True
            ) + "\n",
            encoding="utf-8",
        )


def needs_publish(fp: str, state: PublishState) -> bool:
    """True when the article still has to be packaged or published.

    Only ``packaged`` and ``published`` count as handled: the fingerprint
    of those decides whether the article may be skipped.  Any other
    status means the attempt did not get that far, so it has to run
    again.
    """
    if state.status in ("published", "packaged"):
        return state.fingerprint != fp
    return True
