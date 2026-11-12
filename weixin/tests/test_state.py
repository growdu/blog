import threading

from wechat.state import PublishState, StateStore, needs_draft, needs_submit


def test_two_writers_do_not_lose_each_other_s_entries(tmp_path):
    """The ledger is read in full and written back in full.

    Two writers doing that at the same time used to overwrite each
    other: an entry that was written by one of them was simply gone.
    A draft that is in the box but missing from the ledger is created a
    second time on the next run, which is the one failure the whole
    idempotency exists to prevent.
    """
    store = StateStore(tmp_path / "state.json")
    errors = []

    def writer(index):
        try:
            for step in range(20):
                store.save("writer-{}/{}".format(index, step),
                           PublishState(fingerprint="f", media_id="m"))
        except Exception as error:      # pragma: no cover - only on a failure
            errors.append(error)

    threads = [threading.Thread(target=writer, args=(index,)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert len(store.all()) == 80


def test_needs_draft_when_no_media_id():
    assert needs_draft("abc", PublishState()) is True


def test_needs_draft_when_fingerprint_changed():
    state = PublishState(fingerprint="old", media_id="m1")
    assert needs_draft("new", state) is True


def test_needs_draft_false_when_unchanged():
    state = PublishState(fingerprint="same", media_id="m1")
    assert needs_draft("same", state) is False


def test_needs_submit_only_without_publish_id():
    assert needs_submit(PublishState(media_id="m1")) is True
    assert needs_submit(PublishState(media_id="m1", publish_id="p1")) is False


def test_state_store_roundtrip(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.save("a/b", PublishState(fingerprint="f", media_id="m"))
    loaded = store.get("a/b")
    assert loaded.fingerprint == "f"
    assert loaded.media_id == "m"


def test_state_store_returns_default_for_unknown_slug(tmp_path):
    store = StateStore(tmp_path / "state.json")
    assert store.get("missing").media_id is None


def test_state_store_keeps_other_slugs(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.save("a", PublishState(media_id="m1"))
    store.save("b", PublishState(media_id="m2"))
    assert store.get("a").media_id == "m1"
    assert store.get("b").media_id == "m2"


def test_state_store_records_timestamp(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.save("a", PublishState(media_id="m1"))
    assert store.get("a").updated_at is not None


def test_state_store_survives_corrupt_file(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not json", encoding="utf-8")
    store = StateStore(path)
    assert store.get("a").media_id is None


def test_state_store_creates_parent_directory(tmp_path):
    store = StateStore(tmp_path / "nested" / "deep" / "state.json")
    store.save("a", PublishState(media_id="m1"))
    assert (tmp_path / "nested" / "deep" / "state.json").is_file()


def test_forget_draft_clears_the_draft_but_keeps_the_publish(tmp_path):
    """A deleted draft has to be drafted again; a published article stays published."""
    store = StateStore(tmp_path / "state.json")
    store.save("a", PublishState(fingerprint="f", media_id="m1",
                                 publish_id="p1", publish_status=0))
    store.forget_draft("a")
    state = store.get("a")
    assert state.media_id is None
    assert state.fingerprint is None
    assert state.publish_id == "p1"


def test_forget_draft_leaves_other_slugs_alone(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.save("a", PublishState(media_id="m1"))
    store.save("b", PublishState(media_id="m2"))
    store.forget_draft("a")
    assert store.get("a").media_id is None
    assert store.get("b").media_id == "m2"


def test_forget_draft_on_an_unknown_slug_is_harmless(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.save("a", PublishState(media_id="m1"))
    store.forget_draft("missing")
    assert store.get("a").media_id == "m1"
