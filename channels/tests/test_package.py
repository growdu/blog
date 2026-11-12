"""出包：产物结构、幂等、状态快照、两档预检。"""

import json
import os
from pathlib import Path

import pytest

from channels import package, snapshot


def test_build_package_writes_every_file(meta, video, tmp_path):
    result = package.build_package("ep01", meta, video, tmp_path / "out")
    for name in ("video.mp4", "cover-16x9.jpg", "cover-9x16.jpg",
                 "title.txt", "description.txt", "topics.txt", "publish.md"):
        assert name in result.files, f"发布包缺 {name}"
        assert result.files[name].exists()


def test_the_video_is_a_symlink_not_a_copy(meta, video, tmp_path):
    """成片软链过去，不重复占空间。"""
    result = package.build_package("ep01", meta, video, tmp_path / "out")
    link = result.files["video.mp4"]
    assert link.is_symlink()
    assert link.resolve() == video.resolve()


def test_the_title_file_holds_the_title(meta, video, tmp_path):
    result = package.build_package("ep01", meta, video, tmp_path / "out")
    assert result.files["title.txt"].read_text(encoding="utf-8").strip() == \
        "32 核机器，解码只占 1 核"


def test_the_checklist_says_pending_upload_not_published(meta, video, tmp_path):
    """「已发布」是发布场景里最贵的一种 bug——人以为发出去了，其实没有。"""
    result = package.build_package("ep01", meta, video, tmp_path / "out")
    checklist = result.files["publish.md"].read_text(encoding="utf-8")
    assert "待你上传" in checklist
    assert "已发布" not in checklist


def test_building_twice_with_the_same_video_is_idempotent(meta, video, tmp_path):
    out = tmp_path / "out"
    first = package.build_package("ep01", meta, video, out)
    second = package.build_package("ep01", meta, video, out)
    assert first.video_sha256 == second.video_sha256
    assert second.reused is True


def test_a_changed_video_rebuilds_the_package(meta, video, tmp_path, make_video):
    """成片变了就得重新出包——内容层键是成片的 sha256。"""
    out = tmp_path / "out"
    package.build_package("ep01", meta, video, out)

    # 重写成一段时长不同的合法视频（别往 mp4 里塞垃圾字节，抽帧会失败）
    make_video(video, seconds=2)

    again = package.build_package("ep01", meta, video, out)
    assert again.reused is False


def test_the_snapshot_has_the_contract_shape(tmp_path):
    path = snapshot.write_snapshot(
        tmp_path / "outbox" / "ep01__channels.json",
        episode="ep01", status="packaged", title="短标题",
        package_dir="channels/out/ep01", published_url=None,
        reason="视频号无公开发布接口，已出包待人工上传",
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == set(snapshot.SNAPSHOT_KEYS)
    assert data["platform"] == "channels"
    assert data["kind"] == "video"
    assert data["status"] == "packaged"


def test_the_snapshot_records_a_relative_package_dir(tmp_path):
    """快照要入库——绝对路径换台机器就对不上，还带本机信息。"""
    target = tmp_path / "out" / "ep01"
    target.mkdir(parents=True)
    relative = package.repo_relative(target)
    assert not Path(relative).is_absolute()
    assert relative.endswith(os.path.join("out", "ep01"))


def test_repo_relative_strips_the_workspace_prefix():
    """在仓库里出包时，写出来的是 channels/out/<EP> 这种相对形式。"""
    target = package.REPO_ROOT / "channels" / "out" / "ep01"
    assert package.repo_relative(target) == os.path.join("channels", "out", "ep01")


def test_the_package_meta_says_packaged_not_published(meta, video, tmp_path):
    """机器可读的快照也一样：没发就是没发。"""
    result = package.build_package("ep01", meta, video, tmp_path / "out")
    data = json.loads((result.dir / "meta.json").read_text(encoding="utf-8"))
    assert data["status"] == "packaged"
    assert data["published_url"] is None


def test_the_package_writes_an_outbox_snapshot(meta, video, tmp_path):
    outbox = tmp_path / "outbox"
    package.build_package("ep01", meta, video, tmp_path / "out", outbox_dir=outbox)
    data = json.loads((outbox / "ep01__channels.json").read_text(encoding="utf-8"))
    assert data["status"] == "packaged"
    assert data["published_url"] is None
    # 快照要入库——package_dir 必须是相对路径，不能是本机绝对路径
    assert not Path(data["package_dir"]).is_absolute(), (
        f"package_dir 是绝对路径：{data['package_dir']}")


# --- 两档预检：error 停止，warning 继续但要写进清单 ------------------------


def test_a_hard_violation_stops_the_package(meta, video, tmp_path, monkeypatch):
    """预检里 error 级别的要报错并停止——不能静默出一个发不出去的包。"""
    from pyv import epmeta

    def fake_check_meta(*args, **kwargs):
        return [epmeta.Finding("epmeta.text-limit", epmeta.ERROR,
                                "channels 的 title 太长", "ep01")]

    monkeypatch.setattr(package.epmeta, "check_meta", fake_check_meta)
    out = tmp_path / "out"
    with pytest.raises(package.PackageError):
        package.build_package("ep01", meta, video, out)
    assert not (out / "ep01").exists(), "出包失败了就不该留下半个包"


def test_a_warning_is_written_into_the_checklist(meta, video, tmp_path, monkeypatch):
    """warning 级别的要告警但继续，而且要让人在清单里看得见。"""
    from pyv import epmeta

    def fake_check_meta(*args, **kwargs):
        return [epmeta.Finding("epmeta.cover-at", epmeta.WARNING,
                                "封面帧取在片尾", "ep01")]

    monkeypatch.setattr(package.epmeta, "check_meta", fake_check_meta)
    result = package.build_package("ep01", meta, video, tmp_path / "out")
    checklist = result.files["publish.md"].read_text(encoding="utf-8")
    assert "封面帧取在片尾" in checklist
    assert result.warnings, "告警不能吞掉"


def test_a_clean_package_has_no_warnings(meta, video, tmp_path):
    result = package.build_package("ep01", meta, video, tmp_path / "out")
    assert result.warnings == []


@pytest.mark.parametrize("section", [
    {"title": "标" * 23, "description": "短", "topics": ["a"]},          # 标题 > 22 字
    {"title": "短", "description": "字" * 1001, "topics": ["a"]},         # 简介 > 1000 字
    {"title": "短", "description": "短", "topics": ["a", "b", "c", "d", "e", "f"]},  # 话题 > 5 个
    {"title": "短", "description": "短", "topics": ["标" * 16]},           # 单个话题 > 15 字
])
def test_the_limits_are_errors_not_truncations(meta, video, tmp_path, section):
    """超限要报错，不能悄悄裁一刀（规格 §6.1.3）。"""
    from pyv import epmeta

    broken = epmeta.EpisodeMeta(
        episode="ep01", title=meta.title, cover_at=meta.cover_at, url=meta.url,
        channels=section,
    )
    out = tmp_path / "out"
    with pytest.raises(package.PackageError):
        package.build_package("ep01", broken, video, out)
    assert not (out / "ep01").exists()


# --- 回填 -------------------------------------------------------------------


def test_marking_published_updates_the_package_meta(meta, video, tmp_path):
    result = package.build_package("ep01", meta, video, tmp_path / "out")
    package.mark_published(result.dir, "https://channels.weixin.qq.com/x")
    data = json.loads((result.dir / "meta.json").read_text(encoding="utf-8"))
    assert data["status"] == "published"
    assert data["published_url"] == "https://channels.weixin.qq.com/x"


# --- 命令行端到端 -----------------------------------------------------------


def test_the_cli_packages_and_marks_an_episode(tmp_path, monkeypatch, make_video):
    """期号 → 元数据 → 发布包 → 回填链接，一条线走完。"""
    from pyv import epmeta

    from channels import cli

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

    aiv_root = tmp_path / "aiv"
    (aiv_root / "out").mkdir(parents=True)
    make_video(aiv_root / "out" / "ep01.mp4")

    monkeypatch.setattr(cli, "AIV_ROOT", aiv_root)
    monkeypatch.setattr(epmeta, "PUBLISH_DIR", publish_dir)
    monkeypatch.setattr(snapshot, "OUTBOX_DIR", tmp_path / "outbox")

    out = tmp_path / "out"
    assert cli.main(["package", "ep01", "--out", str(out)]) == 0
    checklist = (out / "ep01" / "publish.md").read_text(encoding="utf-8")
    assert "待你上传" in checklist
    assert "已发布" not in checklist

    url = "https://channels.weixin.qq.com/x"
    assert cli.main(["mark", "published", "ep01", "--url", url,
                     "--out", str(out)]) == 0
    assert cli.main(["status", "ep01", "--out", str(out)]) == 0

    state = json.loads((out / "state.json").read_text(encoding="utf-8"))
    assert state["episodes"]["ep01"]["status"] == "published"
    assert state["episodes"]["ep01"]["published_url"] == url

    shot = json.loads((tmp_path / "outbox" / "ep01__channels.json")
                      .read_text(encoding="utf-8"))
    assert shot["status"] == "published"
    assert shot["published_url"] == url


# --- 通知 -------------------------------------------------------------------


def test_the_phrases_distinguish_the_two_states():
    from channels import notify

    assert "待你上传" in notify.phrase("packaged")
    assert notify.phrase("published") == "已发布"


def test_a_failing_webhook_does_not_break_the_run(capsys):
    """通知推送失败只告警，不崩——发布本身不能被一条通知带崩。"""
    from channels import notify

    text = notify.notify("ep01", "packaged", "标题", "channels/out/ep01",
                          webhook="not-a-url")
    assert "待你上传" in text
    assert "WARNING" in capsys.readouterr().out
