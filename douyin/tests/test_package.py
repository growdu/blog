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


def test_a_vertical_video_gives_a_vertical_cover(meta, tmp_path, make_video):
    """竖版成片的封面也是竖版。

    抖音这一档发的是竖版 9:16（规格 §6.6.5）。封面跟着成片走，
    比例未实测不猜，但**同比例**这条得守住——横版封面配竖版成片，
    后台裁起来会切掉画面中间的内容。
    """
    from PIL import Image

    video = make_video(tmp_path / "ep01-vertical.mp4", size="1080x1920")
    result = _package(meta, video, tmp_path)
    with Image.open(result.dir / "cover.jpg") as cover:
        assert cover.size == (1080, 1920)


def test_the_checklist_says_which_aspect_ratio_it_is(meta, tmp_path, make_video):
    """清单里要写明画幅。

    出包的人照着清单在后台上传——清单上写着尺寸，才知道发出去的是 9:16。
    """
    video = make_video(tmp_path / "ep01-vertical.mp4", size="1080x1920")
    result = _package(meta, video, tmp_path)
    checklist = (result.dir / "publish.md").read_text(encoding="utf-8")
    assert "1080×1920" in checklist
    assert "竖版" in checklist


def test_the_checklist_does_not_call_a_horizontal_video_vertical(meta, tmp_path,
                                                                  make_video):
    """清单的画幅**跟着成片走**，不写死。

    写死「竖版 9:16」的话，`--video` 指向横版成片时，清单里就会出现
    「1920×1080，竖版 9:16」这种自相矛盾的一行——而这份清单正是人
    照着去发布的那份说明。
    """
    video = make_video(tmp_path / "ep01-horizontal.mp4", size="1920x1080")
    result = _package(meta, video, tmp_path)
    checklist = (result.dir / "publish.md").read_text(encoding="utf-8")
    assert "1920×1080" in checklist
    assert "横版" in checklist
    assert "竖版" not in checklist, (
        "横版成片的清单里写着「竖版」——清单写错，人就把错的东西发出去了"
    )


def test_the_checklist_states_the_no_brand_requirement(meta, video, tmp_path):
    """「无品牌」写成**要求**，不是替素材打包票。

    adapter 看不见成片里有没有品牌字标与站外域名，所以清单不能声称
    「这一版是无品牌导流版」——那是在替素材打包票。它得写清楚要求，
    让人自己对。
    """
    result = _package(meta, video, tmp_path)
    checklist = (result.dir / "publish.md").read_text(encoding="utf-8")
    assert "无品牌导流版" in checklist
    assert "限流" in checklist


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


def test_a_missing_file_in_the_package_forces_a_rebuild(meta, video, tmp_path):
    """**复用不是「目录还在就算数」。**

    上一版的复用分支只看「成片没变」和「meta.json 在」，包里少了东西
    （软链悬空、封面被人删了）照样报「复用成功」——而那个包根本发不出去。

    这里把封面删掉再出一次包：包里必须又是齐的。
    """
    result = _package(meta, video, tmp_path)
    (result.dir / "cover.jpg").unlink()

    again = _package(meta, video, tmp_path)
    assert not again.reused, "包里缺了封面还报复用"
    for name in FILES:
        assert (again.dir / name).is_file(), f"缺 {name}"


def test_a_dangling_video_symlink_forces_a_rebuild(meta, video, tmp_path):
    """软链悬空也要重出——成片被挪走或删了，那个包发不出去。"""
    result = _package(meta, video, tmp_path)
    (result.dir / "video.mp4").unlink()

    again = _package(meta, video, tmp_path)
    assert not again.reused
    assert (again.dir / "video.mp4").is_symlink()
    assert (again.dir / "video.mp4").exists()


def test_the_cover_is_re_extracted_when_the_frame_moves(meta, video, tmp_path):
    """封面与 `meta.json` 记的取帧点必须对得上。

    上一版复用时不重抽封面：元数据里的 `cover_at` 从 1.0 改成 2.0，
    清单与 `meta.json` 都写着 2.0，包里那张封面却还是 1.0 秒那一帧——
    人按清单选封面，选到的是另一帧。
    """
    first = _package(meta, video, tmp_path)
    cover_before = (first.dir / "cover.jpg").read_bytes()

    moved = epmeta.EpisodeMeta(
        episode="ep01", title=meta.title, cover_at=2.0, url=meta.url,
        douyin=meta.douyin)
    again = _package(moved, video, tmp_path)
    cover_after = (again.dir / "cover.jpg").read_bytes()

    assert cover_after != cover_before, "换了取帧点，封面还是原来那张"
    data = json.loads((again.dir / "meta.json").read_text(encoding="utf-8"))
    assert data["cover_at"] == 2.0


def test_the_checklist_uses_the_limit_from_the_capability_file(meta, video,
                                                               tmp_path):
    """清单里的上限**跟着能力声明走**，不写死 1000。

    写死的话，改了 `publish/capabilities/douyin.toml` 的 `text_chars`，
    清单还在说 1000——两处数字打架，人照着清单发，文案却被闸门拦下。
    """
    capabilities = tmp_path / "capabilities"
    capabilities.mkdir()
    (capabilities / "douyin.toml").write_text(
        "[limits]\n"
        "text_chars = 300\n"
        "title_chars = 55\n"
        "description_chars = 500\n"
        "topics_max = 5\n"
        "topic_chars = 15\n",
        encoding="utf-8")

    result = _package(meta, video, tmp_path, capabilities_dir=capabilities)
    checklist = (result.dir / "publish.md").read_text(encoding="utf-8")
    assert "上限 300" in checklist
    assert "1000" not in checklist
