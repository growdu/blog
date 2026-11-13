"""Tests for the cache of permanent materials.

A cover is uploaded to WeChat as a **permanent** material, and every
refresh used to upload it again -- each upload leaves another copy in
the material library.  After the first refresh cycle the library held
2129 materials for 320 distinct covers.

A permanent material can be used by any number of drafts, so the media
id is kept per image content and looked up before uploading.
"""
import json

import pytest

from wechat.material import MaterialCache


def test_a_material_id_is_kept_per_image(tmp_path):
    cache = MaterialCache(tmp_path / "materials.json")

    cache.put("abc123", "MEDIA_A")

    assert cache.get("abc123") == "MEDIA_A"


def test_an_image_that_was_never_uploaded_has_no_material(tmp_path):
    cache = MaterialCache(tmp_path / "materials.json")

    assert cache.get("nothing") is None


def test_the_cache_survives_a_restart(tmp_path):
    """The refresh runs in another process; the next run has to see
    what the last one uploaded."""
    path = tmp_path / "materials.json"
    MaterialCache(path).put("abc123", "MEDIA_A")

    assert MaterialCache(path).get("abc123") == "MEDIA_A"


def test_a_forgotten_material_is_gone(tmp_path):
    """A material the user deleted in the backend must not be used
    again."""
    path = tmp_path / "materials.json"
    cache = MaterialCache(path)
    cache.put("abc123", "MEDIA_A")

    cache.forget("abc123")

    assert cache.get("abc123") is None
    assert MaterialCache(path).get("abc123") is None


def test_a_corrupt_cache_is_ignored(tmp_path):
    """A truncated file must not stop the pipeline."""
    path = tmp_path / "materials.json"
    path.write_text("{not json", encoding="utf-8")

    cache = MaterialCache(path)

    assert cache.get("abc123") is None
    cache.put("abc123", "MEDIA_A")
    assert cache.get("abc123") == "MEDIA_A"


def test_two_writers_do_not_lose_each_other(tmp_path):
    """The cache is read in full and written back in full, so two
    writers at the same time would drop each other's entries."""
    import threading

    path = tmp_path / "materials.json"
    cache = MaterialCache(path)
    written = []
    barrier = threading.Barrier(4)

    def writer(index):
        barrier.wait()
        for round_number in range(20):
            cache.put("key-{}-{}".format(index, round_number),
                      "MEDIA_{}_{}".format(index, round_number))
            written.append(index)

    threads = [threading.Thread(target=writer, args=(index,))
               for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    entries = json.loads(path.read_text(encoding="utf-8"))["materials"]
    assert len(entries) == 80
