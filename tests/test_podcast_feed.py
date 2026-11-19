"""播客 feed 的契约测试（契约七 §八）。

feed 是「订阅」这条链路的末端，也是**唯一**能把内容送到读者播放器里的东西。
它坏掉的方式很隐蔽：XML 还是合法的、页面还是 200，只是订阅器里**收不到新一期**。

所以这里盯四件事：

1. **结构**：RSS 2.0，``<enclosure>`` 的三个属性（url / length / type）齐全；
2. **稳定**：``<guid>`` 不含日期——重发同一期不能变成新条目；
3. **托管**：旁白 mp3 真的被复制到站点托管的目录，字节数与仓库里那份一致；
4. **地址**：绝对地址带域名，挂载点前缀**只加一次**（镜像站的经典 bug）。
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPO_ROOT / "tools"

sys.path.insert(0, str(TOOLS))
import site_root  # noqa: E402


def load_tool(name):
    spec = importlib.util.spec_from_file_location(
        "tool_under_test_{}".format(name.replace("-", "_")), TOOLS / (name + ".py")
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


feed_tool = load_tool("build-podcast-feed")


def _index():
    return {
        "series": {"name": "数据库内核机制", "tagline": "数据库内核机制，讲到源码那一行"},
        "episodes": [
            {
                "episode": "csn-total-ordering",
                "episode_no": 2,
                "episode_label": "EP02",
                "title": "一个 64 位计数器",
                "hook": "并发提交的时间是乱的",
                "duration_s": 35.316,
                "date": "2026-10-19",
                "content_id": "source-tracks/postgresql/logical-replication/opengauss-csn-total-ordering",
                "video_date": "2026-11-12",
                "video_content_id": "video/csn-total-ordering",
                "platforms": [],
            },
            {
                "episode": "row-lock",
                "episode_no": 6,
                "episode_label": "EP06",
                "title": "两个事务改同一行，谁先谁后",
                "hook": "MVCC 让读不挡写",
                "duration_s": 35.172,
                "date": "2026-10-15",
                "content_id": "source-tracks/postgresql/transaction-mvcc/postgresql-row-lock-deep-dive",
                "video_date": "2026-11-12",
                "video_content_id": "video/row-lock",
                "platforms": [],
            },
        ],
    }


def _write_index(tmp_path, index=None):
    path = tmp_path / "podcast_index.json"
    path.write_text(
        json.dumps(index if index is not None else _index(), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _build(tmp_path, monkeypatch, index=None):
    """跑一次 feed 生成，返回 (feed 文本, 输出路径)。"""
    index_path = _write_index(tmp_path, index)
    audio_dir = tmp_path / "audio"
    monkeypatch.setattr(feed_tool, "PODCAST_INDEX", index_path)
    monkeypatch.setattr(feed_tool, "AUDIO_DIR", audio_dir)
    out = tmp_path / "feed.xml"
    assert feed_tool.main(["--out", str(out)]) == 0
    return out.read_text(encoding="utf-8"), out


# --- 1. 结构 ---------------------------------------------------------------


def test_the_feed_is_rss_two_with_a_channel(tmp_path, monkeypatch):
    text, _out = _build(tmp_path, monkeypatch)
    root = ET.fromstring(text)

    assert root.tag == "rss"
    assert root.get("version") == "2.0"
    channel = root.find("channel")
    assert channel is not None
    assert channel.findtext("title") == "数据库内核机制"
    assert channel.findtext("language") == "zh-cn"
    itunes = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
    assert channel.findtext(itunes + "author") == "growdu"


def test_every_item_carries_an_enclosure_with_all_three_attributes(tmp_path, monkeypatch):
    """``<enclosure>`` 三个属性缺一，部分阅读器会拒收。"""
    text, _out = _build(tmp_path, monkeypatch)
    root = ET.fromstring(text)

    items = root.findall("./channel/item")
    assert len(items) == 2
    for item in items:
        enclosure = item.find("enclosure")
        assert enclosure is not None, "条目缺少 enclosure"
        assert enclosure.get("url")
        assert enclosure.get("type") == "audio/mpeg"
        assert int(enclosure.get("length")) > 0


def test_the_guid_is_stable_and_carries_no_date(tmp_path, monkeypatch):
    """重发同一期不能变成新条目——guid 里不能有日期。"""
    text, _out = _build(tmp_path, monkeypatch)
    root = ET.fromstring(text)

    guids = [item.findtext("guid") for item in root.findall("./channel/item")]
    assert guids == ["growdu.cn/podcast/row-lock", "growdu.cn/podcast/csn-total-ordering"]
    for guid in guids:
        assert not re.search(r"\d{4}-\d{2}-\d{2}", guid)


def test_the_feed_holds_at_most_twenty_items(tmp_path, monkeypatch):
    """与 ``atom.xml`` 的 ``limit: 20`` 一致。"""
    rows = []
    for number in range(1, 26):
        rows.append(
            {
                "episode": "ep{:02d}".format(number),
                "episode_no": number,
                "episode_label": "EP{:02d}".format(number),
                "title": "第 {} 期".format(number),
                "hook": "钩子",
                "duration_s": 30.0,
                "date": "2026-01-{:02d}".format(number),
                "content_id": "database/ep{:02d}".format(number),
                "video_date": "2026-01-{:02d}".format(number),
                "video_content_id": "video/ep{:02d}".format(number),
                "platforms": [],
            }
        )
    index = {"series": _index()["series"], "episodes": rows}
    text, _out = _build(tmp_path, monkeypatch, index=index)

    root = ET.fromstring(text)
    assert len(root.findall("./channel/item")) == 20


def test_the_newest_episode_comes_first(tmp_path, monkeypatch):
    text, _out = _build(tmp_path, monkeypatch)
    root = ET.fromstring(text)

    titles = [item.findtext("title") for item in root.findall("./channel/item")]
    assert titles[0].startswith("EP06")
    assert titles[1].startswith("EP02")


def test_the_item_links_to_the_full_article(tmp_path, monkeypatch):
    """条目链到**母稿页**（完整版），不是口播稿页。"""
    text, _out = _build(tmp_path, monkeypatch)
    root = ET.fromstring(text)

    link = root.find("./channel/item/link").text
    assert link.endswith("/2026/10/15/source-tracks/postgresql/transaction-mvcc/postgresql-row-lock-deep-dive/")


# --- 2. 托管 ---------------------------------------------------------------


def test_the_narration_audio_is_hosted_on_the_site(tmp_path, monkeypatch):
    """旁白 mp3 要被复制到站点托管的目录——``<enclosure>`` 指的就是它。"""
    _text, _out = _build(tmp_path, monkeypatch)

    hosted = tmp_path / "audio" / "narration_row-lock.mp3"
    assert hosted.is_file()
    original = REPO_ROOT / "aiv" / "narration_row-lock.mp3"
    assert hosted.stat().st_size == original.stat().st_size


def test_the_enclosure_length_matches_the_hosted_audio(tmp_path, monkeypatch):
    text, _out = _build(tmp_path, monkeypatch)
    root = ET.fromstring(text)

    enclosure = root.find("./channel/item/enclosure")
    hosted = tmp_path / "audio" / "narration_row-lock.mp3"
    assert int(enclosure.get("length")) == hosted.stat().st_size


# --- 3. 地址 ---------------------------------------------------------------


def test_the_enclosure_url_is_absolute(tmp_path, monkeypatch):
    text, _out = _build(tmp_path, monkeypatch)
    root = ET.fromstring(text)

    url = root.find("./channel/item/enclosure").get("url")
    assert url.startswith("https://growdu.cn/audio/")


def test_the_mount_point_is_not_added_twice(tmp_path, monkeypatch):
    """镜像站的经典 bug：域名里已经有 /blog，路径里再加一次就成了 /blog/blog/。

    ``config.url`` 在镜像构建里是 ``https://growdu.github.io/blog``，
    所以绝对地址 = 域名 + **不带挂载点前缀**的站内路径。
    """
    monkeypatch.setattr(
        site_root, "site_url", lambda config_path=None: "https://growdu.github.io/blog"
    )
    monkeypatch.setattr(site_root, "site_root", lambda config_path=None: "/blog")
    text, _out = _build(tmp_path, monkeypatch)
    root = ET.fromstring(text)

    url = root.find("./channel/item/enclosure").get("url")
    assert url == "https://growdu.github.io/blog/audio/narration_row-lock.mp3"
    assert "/blog/blog/" not in url


def test_the_episode_page_points_at_the_feed():
    """订阅入口要指向 feed——带挂载点前缀。

    2026-11-19：系列页（/videos/）退休了，订阅入口跟着搬进文章页顶部的
    期号区块。feed 本身还在，订阅链路不能断。
    """
    partial = (
        REPO_ROOT / "themes" / "matery" / "layout" / "_partial" / "episode-block.ejs"
    ).read_text(encoding="utf-8")

    assert "/feed.xml" in partial, "文章页的期号区块里没有指向 feed 的链接"
    assert "订阅" in partial, "订阅入口的字样不见了"


# --- 4. 装配 ---------------------------------------------------------------


def test_the_ci_builds_the_feed():
    workflow = (REPO_ROOT / ".github" / "workflows" / "hexo.yml").read_text(
        encoding="utf-8"
    )

    assert workflow.count("python3 tools/build-podcast-feed.py") == 2
    for build in workflow.split("- name: Build publish index")[1:]:
        segment = build.split("- name: Apply theme patches")[0]
        assert "tools/build-podcast-index.py" in segment
        assert "tools/build-podcast-feed.py" in segment


def test_an_empty_index_does_not_wipe_the_feed(tmp_path, monkeypatch):
    """一期都没有就别覆盖——空 feed 比旧 feed 更糟。"""
    index_path = _write_index(tmp_path, {"series": {}, "episodes": []})
    monkeypatch.setattr(feed_tool, "PODCAST_INDEX", index_path)
    out = tmp_path / "feed.xml"
    out.write_text("<rss><!-- 旧的 --></rss>", encoding="utf-8")

    assert feed_tool.main(["--out", str(out)]) == 0
    assert "旧的" in out.read_text(encoding="utf-8")
