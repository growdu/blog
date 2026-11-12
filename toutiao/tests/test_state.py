"""Tests for the idempotency state.

Two layers:

- unit tests: one situation each -- what a record round-trips to, what a
  corrupt file does, when an article needs publishing again;
- integration tests: a store written by one instance is read by another,
  the way the CLI reads the file an earlier run wrote.

The state file is this machine's *working record*.  It is not the
committed idempotency key -- that one is the outbox snapshot written by
``publish.py`` -- and a test that confused the two would be the kind of
bug this module exists to prevent.
"""

import hashlib
import json

from toutiao.state import PublishState, StateStore, fingerprint, needs_publish


def test_fingerprint_is_stable_and_content_sensitive():
    assert fingerprint("abc") == fingerprint("abc")
    assert fingerprint("abc") != fingerprint("abd")
    assert len(fingerprint("abc")) == 64


def test_fingerprint_is_the_sha256_of_the_body():
    """指纹是 sha256：换算法就是换了一套幂等键，旧记录全部作废。"""
    body = "《标题》\n段落。"
    assert fingerprint(body) == hashlib.sha256(body.encode("utf-8")).hexdigest()


def test_store_round_trip(tmp_path):
    store = StateStore(tmp_path / "state.json")
    assert store.get("db/demo").fingerprint is None
    store.save("db/demo", PublishState(fingerprint="fp", status="packaged"))
    again = store.get("db/demo")
    assert again.fingerprint == "fp"
    assert again.status == "packaged"
    assert again.updated_at


def test_store_survives_a_corrupt_file(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not json", encoding="utf-8")
    assert StateStore(path).get("db/demo").fingerprint is None


def test_a_corrupt_file_is_quarantined_not_deleted(tmp_path):
    """损坏的状态文件被改名隔离：证据留着，调用方能报出来。

    直接删掉或直接吞掉都不行：状态一丢，所有记录都变成「没发过」，
    流水线会把发过的东西再发一遍。
    """
    path = tmp_path / "state.json"
    broken = b"{not json"
    path.write_bytes(broken)

    store = StateStore(path)
    store.get("db/demo")

    assert store.quarantined is not None
    assert store.quarantined == tmp_path / "state.json.corrupt"
    assert not path.exists()
    assert store.quarantined.read_bytes() == broken


def test_save_leaves_the_callers_state_untouched(tmp_path):
    """save() 存的是副本：调用方手里的对象一个字段都不动。

    悄悄改掉调用方的输入是看不见的副作用，而调用方随后读到的
    updated_at 会是一个「其实从没存过」的时间戳。
    """
    store = StateStore(tmp_path / "state.json")
    state = PublishState(fingerprint="fp", status="packaged")

    store.save("db/demo", state)

    assert state.updated_at is None
    assert store.get("db/demo").updated_at


def test_needs_publish_is_true_without_a_record():
    assert needs_publish("fp", PublishState()) is True


def test_needs_publish_is_false_for_the_same_content():
    state = PublishState(fingerprint="fp", status="packaged")
    assert needs_publish("fp", state) is False


def test_needs_publish_is_true_when_the_content_changed():
    state = PublishState(fingerprint="old", status="packaged")
    assert needs_publish("new", state) is True


def test_needs_publish_is_true_for_an_unfinished_status():
    """只有 packaged / published 算「已经处理过」，别的状态都要再发。"""
    state = PublishState(fingerprint="fp", status="drafted")
    assert needs_publish("fp", state) is True


def test_package_dir_travels_with_the_state(tmp_path):
    """package_dir 一路带到记录里：status 命令要打印它。"""
    store = StateStore(tmp_path / "state.json")
    store.save(
        "db/demo",
        PublishState(fingerprint="fp", status="packaged", package_dir="toutiao/out/db-demo"),
    )

    assert store.get("db/demo").package_dir == "toutiao/out/db-demo"
    assert store.all()["db/demo"]["package_dir"] == "toutiao/out/db-demo"


def test_all_lists_every_saved_article(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.save("db/one", PublishState(fingerprint="fp1", status="packaged"))
    store.save("db/two", PublishState(fingerprint="fp2", status="published"))

    articles = store.all()
    assert sorted(articles) == ["db/one", "db/two"]
    assert articles["db/two"]["status"] == "published"


def test_the_state_file_is_json_with_the_articles_key(tmp_path):
    path = tmp_path / "state.json"
    StateStore(path).save("db/demo", PublishState(fingerprint="fp", status="packaged"))

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert set(raw) == {"articles"}
    assert raw["articles"]["db/demo"]["fingerprint"] == "fp"


def test_a_second_store_sees_what_the_first_one_wrote(tmp_path):
    """集成：写状态的进程和读状态的进程不是同一个（CLI 每次重跑都是新进程）。"""
    path = tmp_path / "state.json"
    StateStore(path).save("db/demo", PublishState(fingerprint="fp", status="packaged"))

    assert StateStore(path).get("db/demo").status == "packaged"


def test_the_store_touches_nothing_but_its_own_file(tmp_path):
    """状态文件是本机工作记录：它不写进 outbox 那套入库快照里。"""
    path = tmp_path / "out" / "state.json"
    StateStore(path).save("db/demo", PublishState(fingerprint="fp", status="packaged"))

    assert sorted(p.name for p in path.parent.iterdir()) == ["state.json"]


def test_repackaging_the_same_body_is_refused(tmp_path):
    """集成：同篇第二次不重复出包 —— 指纹没变就不该再发。

    走的是 CLI 的那条路：读记录 → 填指纹与状态 → 存回去 → 再问一次。
    """
    store = StateStore(tmp_path / "state.json")
    body = "《标题》\n段落。"
    fp = fingerprint(body)

    state = store.get("db/demo")
    assert needs_publish(fp, state) is True

    state.fingerprint = fp
    state.status = "packaged"
    store.save("db/demo", state)

    assert needs_publish(fp, store.get("db/demo")) is False
