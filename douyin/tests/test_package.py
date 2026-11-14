"""出包：产物结构、幂等、以及抖音专属的两道闸真的会拦住出包。"""

import json
from pathlib import Path

import pytest

from douyin import package
from pyv import epmeta

FILES = ("video.mp4", "cover.jpg", "title.txt", "description.txt",
         "topics.txt", "text.txt", "publish.md")


def _package(meta, video, tmp_path, **kwargs):
    return package.build_package("ep01", meta, video, tmp_path / "out", **kwargs)


def test_the_package_has_every_file(meta, video, tmp_path):
    result = _package(meta, video, tmp_path)
    for name in FILES:
        assert (result.dir / name).is_file(), f"缺 {name}"
    assert (result.dir / "meta.json").is_file()


def test_the_video_is_a_symlink_to_the_real_file(meta, video, tmp_path):
    """包里存的是软链——成片是本机产物，不该被复制一份占地方。"""
    result = _package(meta, video, tmp_path)
    link = result.dir / "video.mp4"
    assert link.is_symlink()
    assert link.resolve() == Path(video).resolve()


def test_the_text_file_is_the_whole_field(meta, video, tmp_path):
    """抖音只有那一个字段——包里给的是拼好的整段，粘上去就对。"""
    result = _package(meta, video, tmp_path)
    text = (result.dir / "text.txt").read_text(encoding="utf-8")
    assert text == "32 核机器，解码只占 1 核\n默认发布端只有一个解码线程，串行处理。\n" \
                   "#PostgreSQL #逻辑复制 #数据库内核"


def test_the_checklist_warns_against_adding_contacts(meta, video, tmp_path):
    """清单里要写清楚「别自己加网址」——那是最常见的限流原因。"""
    result = _package(meta, video, tmp_path)
    checklist = (result.dir / "publish.md").read_text(encoding="utf-8")
    assert "站外引流" in checklist
    assert "text.txt" in checklist


def test_the_cover_keeps_the_video_aspect_ratio(meta, video, tmp_path):
    """抖音的封面比例未实测——先给与成片同比例的图，不猜。"""
    from PIL import Image

    result = _package(meta, video, tmp_path)
    with Image.open(result.dir / "cover.jpg") as cover:
        assert cover.size == (1920, 1080)


def test_the_same_video_reuses_the_package(meta, video, tmp_path):
    result = _package(meta, video, tmp_path)
    again = _package(meta, video, tmp_path)
    assert again.reused
    assert again.video_sha256 == result.video_sha256


def test_a_changed_video_makes_a_new_package(meta, video, tmp_path, make_video):
    """成片变了就是另一条片子，必须重出包。"""
    result = _package(meta, video, tmp_path)
    other = make_video(tmp_path / "ep01-v2.mp4", seconds=2)
    again = _package(meta, other, tmp_path)
    assert not again.reused
    assert again.video_sha256 != result.video_sha256


def test_the_copy_is_rewritten_even_when_the_video_is_unchanged(meta, video, tmp_path):
    """成片没变 ≠ 文案没变：改了标题再跑，包里的标题必须跟着变。"""
    result = _package(meta, video, tmp_path)
    changed = epmeta.EpisodeMeta(
        episode="ep01", title=meta.title, cover_at=meta.cover_at,
        url=meta.url, douyin=dict(meta.douyin, title="改了标题"))
    again = _package(changed, video, tmp_path)
    assert again.reused
    assert (again.dir / "title.txt").read_text(encoding="utf-8") == "改了标题"
    assert "改了标题" in (again.dir / "text.txt").read_text(encoding="utf-8")


def test_an_outbound_link_stops_the_package(meta, video, tmp_path):
    """带站外引流的文案**不出包**——出了也是发不出去（限流）。"""
    leaky = epmeta.EpisodeMeta(
        episode="ep01", title=meta.title, cover_at=meta.cover_at, url=meta.url,
        douyin=dict(meta.douyin, description="完整版见 https://growdu.cn/x"))
    with pytest.raises(package.PackageError) as error:
        _package(leaky, video, tmp_path)
    assert any(f.rule_id == "douyin.outbound-link" for f in error.value.findings)
    assert not (tmp_path / "out" / "ep01").exists()


def test_an_overlong_text_stops_the_package(meta, video, tmp_path):
    """三段加起来超过平台上限，就不该出包。"""
    long_text = epmeta.EpisodeMeta(
        episode="ep01", title=meta.title, cover_at=meta.cover_at, url=meta.url,
        douyin=dict(meta.douyin, description="字" * 1000))
    with pytest.raises(package.PackageError) as error:
        _package(long_text, video, tmp_path)
    assert any(f.rule_id == "douyin.text-limit" for f in error.value.findings)


def test_a_missing_douyin_section_stops_the_package(video, tmp_path):
    """没配抖音文案就是配置错误，不是「这一期不发抖音」。"""
    bare = epmeta.EpisodeMeta(episode="ep01", title="x", cover_at=1.0)
    with pytest.raises(epmeta.MetaError):
        _package(bare, video, tmp_path)


def test_other_platforms_missing_does_not_stop_the_douyin_package(video, tmp_path):
    """「这一期没配 B站文案」不是抖音的发布问题，不该拦住抖音出包。"""
    only_douyin = epmeta.EpisodeMeta(
        episode="ep01", title="x", cover_at=1.0,
        douyin={"title": "钩子", "description": "正文", "topics": ["数据库"]})
    result = _package(only_douyin, video, tmp_path)
    assert result.status == "packaged"


def test_the_snapshot_is_written_to_the_outbox(meta, video, tmp_path, outbox):
    """出包要写状态快照——跨平台对账靠它。"""
    result = _package(meta, video, tmp_path)
    snapshot = outbox / "ep01__douyin.json"
    assert snapshot.is_file()
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    assert data["platform"] == "douyin"
    assert data["status"] == "packaged"
    assert data["content_id"] == "ep01"
    assert data["published_url"] is None


def test_marking_published_updates_the_package_and_the_snapshot(meta, video, tmp_path, outbox):
    result = _package(meta, video, tmp_path)
    url = "https://www.douyin.com/video/1234567890"
    package.mark_published(result.dir, url)
    data = json.loads((result.dir / "meta.json").read_text(encoding="utf-8"))
    assert data["status"] == "published"
    assert data["published_url"] == url


def test_publishing_without_a_package_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        package.mark_published(tmp_path / "nope", "https://x")
