from wechat.state import PublishState, StateStore, needs_draft, needs_submit


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
