"""`drafted` 档：草稿已在平台上，等人点发表。

**为什么要有第三档。** 只有「待上传」和「已发布」两个词是不够的：
草稿存到平台之后，它**既没发出去、也不在等人上传**——
它在等人**点发表**。这个状态说错了会有两种后果：

- 说成「已发布」→ 人以为发出去了，不再管；
- 说成「待上传」→ 人以为还没传，可能会**再传一遍**。

（头条号那边同一个状态用的是同一套措辞，见 toutiao/docs/00-设计.md。）
"""

import json
from pathlib import Path

from channels import notify, package, snapshot, state


# --- 回填 -------------------------------------------------------------------


def test_marking_drafted_updates_the_package_meta(meta, video, tmp_path):
    result = package.build_package("ep01", meta, video, tmp_path / "out")
    package.mark_drafted(result.dir)

    data = json.loads((result.dir / "meta.json").read_text(encoding="utf-8"))
    assert data["status"] == "drafted"
    # 草稿还没发出去，**没有**公开链接
    assert data["published_url"] is None


def test_marking_drafted_clears_a_stale_published_url(meta, video, tmp_path):
    """草稿没有公开链接——留着旧链接会让人以为这条已经发出去了。"""
    result = package.build_package("ep01", meta, video, tmp_path / "out")
    package.mark_published(result.dir, "https://channels.weixin.qq.com/x")
    package.mark_drafted(result.dir)

    data = json.loads((result.dir / "meta.json").read_text(encoding="utf-8"))
    assert data["status"] == "drafted"
    assert data["published_url"] is None


def _mark_drafted(out, episode):
    """模拟 `channels.cli mark drafted`：状态与包内快照一起更新。

    状态以 state store 为准，包里的 meta.json 只是跟着同步——
    出包时读的是 store（见 package.build_package）。
    """
    store = state.StateStore(out / "state.json")
    current = store.get(episode)
    current.status = "drafted"
    current.published_url = None
    store.save(episode, current)
    package.mark_drafted(out / episode)


def test_repackaging_keeps_the_drafted_status(meta, video, tmp_path, outbox):
    """重出包不能把「已存草稿」抹成「待上传」。

    草稿在平台上放着的还是这一条片子，重新出包只是刷新文案。
    """
    out = tmp_path / "out"
    package.build_package("ep01", meta, video, out)
    _mark_drafted(out, "ep01")

    result = package.build_package("ep01", meta, video, out)

    assert result.status == "drafted"
    shot = json.loads((outbox / "ep01__channels.json").read_text(encoding="utf-8"))
    assert shot["status"] == "drafted"


# --- 状态与措辞 -------------------------------------------------------------


def test_the_state_file_records_the_drafted_status(meta, video, tmp_path):
    out = tmp_path / "out"
    package.build_package("ep01", meta, video, out)
    store = state.StateStore(out / "state.json")
    current = store.get("ep01")
    current.status = "drafted"
    current.published_url = None
    store.save("ep01", current)

    again = store.get("ep01")
    assert again.status == "drafted"
    assert again.published_url is None


def test_the_drafted_phrase_does_not_claim_it_is_published():
    """含糊地说「已发布」是发布场景里最贵的一种 bug。"""
    text = notify.phrase("drafted")
    assert "已发布" not in text
    assert "草稿" in text
    assert "发表" in text


# --- 命令行 -----------------------------------------------------------------


def _publish_meta(tmp_path) -> Path:
    publish_dir = tmp_path / "publish"
    publish_dir.mkdir()
    (publish_dir / "ep01.json").write_text(json.dumps({
        "episode": "ep01",
        "title": "PostgreSQL 18 并行逻辑解码",
        "cover_at": 1.0,
        "url": "https://growdu.cn/2026/11/12/life/aiv/",
        "channels": {
            "title": "32 核机器，解码只占 1 核",
            "description": "默认发布端只有一个解码线程，串行处理。",
            "topics": ["PostgreSQL", "逻辑复制", "数据库内核"],
        },
    }, ensure_ascii=False), encoding="utf-8")
    return publish_dir


def test_the_cli_marks_a_draft_and_writes_a_drafted_snapshot(
        tmp_path, monkeypatch, make_video):
    """期号 → 元数据 → 发布包 → 存草稿 → 快照，一条线走完。"""
    from pyv import epmeta

    from channels import cli

    publish_dir = _publish_meta(tmp_path)
    aiv_root = tmp_path / "aiv"
    (aiv_root / "out").mkdir(parents=True)
    make_video(aiv_root / "out" / "ep01.mp4")

    monkeypatch.setattr(cli, "AIV_ROOT", aiv_root)
    monkeypatch.setattr(epmeta, "PUBLISH_DIR", publish_dir)
    monkeypatch.setattr(snapshot, "OUTBOX_DIR", tmp_path / "outbox")

    out = tmp_path / "out"
    assert cli.main(["package", "ep01", "--out", str(out)]) == 0
    assert cli.main(["mark", "drafted", "ep01", "--out", str(out)]) == 0

    data = json.loads((out / "state.json").read_text(encoding="utf-8"))
    assert data["episodes"]["ep01"]["status"] == "drafted"
    assert data["episodes"]["ep01"]["published_url"] is None

    shot = json.loads((tmp_path / "outbox" / "ep01__channels.json")
                      .read_text(encoding="utf-8"))
    assert shot["status"] == "drafted"
    assert shot["published_url"] is None
    # 快照要入库：路径得是相对的
    assert not Path(shot["package_dir"]).is_absolute()


def test_the_cli_refuses_to_mark_published_without_a_url(tmp_path, capsys):
    """`published` 没有链接就是没发布——报错，不要默认成「已发布」。"""
    from channels import cli

    assert cli.main(["mark", "published", "ep01",
                     "--out", str(tmp_path / "out")]) == 1
    assert "url" in capsys.readouterr().err.lower()


def test_the_cli_does_not_write_a_snapshot_when_publishing_has_no_url(
        tmp_path, monkeypatch):
    """报错的时候不能顺手把快照写成「已发布」。"""
    from channels import cli

    monkeypatch.setattr(snapshot, "OUTBOX_DIR", tmp_path / "outbox")
    assert cli.main(["mark", "published", "ep01",
                     "--out", str(tmp_path / "out")]) == 1
    assert not (tmp_path / "outbox" / "ep01__channels.json").exists()
