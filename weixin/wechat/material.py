"""A cache of the permanent materials already uploaded to WeChat.

A cover is uploaded as a **permanent** material, and every refresh used
to upload it again: each upload leaves another copy in the material
library, so the library grew by one material per part per run -- 2129
materials for 320 distinct covers after the first refresh cycle.

A permanent material is meant to be used by any number of drafts, so
the media id is kept per image content and looked up before uploading.

The cache lives next to the other build output and is never committed.
A material that was deleted in the WeChat backend is noticed when the
draft is refused (``40007 invalid media_id``): the entry is dropped and
the image is uploaded again.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

__all__ = ["MaterialCache"]

# The error WeChat answers with when the cover of a draft points at a
# material that no longer exists.
INVALID_MEDIA_ID = 40007


class MaterialCache:
    """A JSON file mapping the content of an image to its media id."""

    def __init__(self, path: Path):
        self.path = Path(path)

    @contextmanager
    def _locked(self):
        """Hold the lock on the cache while it is read and written.

        The cache is one file that every writer reads in full and
        writes back in full, the same hazard the publish ledger has.
        """
        lock_path = self.path.with_name(self.path.name + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "a+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _load_all(self) -> dict:
        if not self.path.is_file():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(raw, dict):
            return {}
        materials = raw.get("materials", {})
        return materials if isinstance(materials, dict) else {}

    def _write(self, materials: dict) -> None:
        """Write the cache out, atomically.

        The write goes to a temporary file that is then moved into
        place, so a reader never sees half a file, and the temporary
        name is unique, so two writers cannot move each other's file
        away.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=self.path.name + ".",
            suffix=".tmp")
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                json.dump({"materials": materials}, out, ensure_ascii=False,
                          indent=2, sort_keys=True)
            temporary.replace(self.path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    def get(self, digest: str):
        """The media id of an image, or None when it was never uploaded."""
        if not digest:
            return None
        value = self._load_all().get(digest)
        return value if isinstance(value, str) and value else None

    def put(self, digest: str, media_id: str) -> None:
        """Remember the media id of an image."""
        if not digest or not media_id:
            return
        with self._locked():
            materials = self._load_all()
            materials[digest] = media_id
            self._write(materials)

    def forget(self, digest: str) -> None:
        """Forget a material -- it was deleted in the WeChat backend."""
        if not digest:
            return
        with self._locked():
            materials = self._load_all()
            if digest not in materials:
                return
            del materials[digest]
            self._write(materials)
