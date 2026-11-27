"""`drafted` 档：草稿已在抖音后台，等人点发表。

**为什么要有第三档。** 只有「待上传」和「已发布」两个词是不够的：
草稿存到平台之后，它**既没发出去、也不在等人上传**——它在等人**点发表**。
这个状态说错了会有两种后果：

- 说成「已发布」→ 人以为发出去了，不再管；
- 说成「待上传」→ 人以为还没传，可能会**再传一遍**。

**这一档是 2026-11-15 实测出来的，不是拍脑袋设的**（规格 §6.6.7）：
点「暂存离开」之后，上传页弹出「你还有上次未发布的视频，是否继续编辑？」，
首页的作品发布卡片上也出现「继续编辑」；从入口进去的 URL 带
`?enter_from=draft` / `?enter_from=home_draft`，视频、标题、描述、话题、
两张封面全在原处。

⚠️ **但抖音没有「草稿箱」列表**——内容管理 → 作品的筛选只有
「全部 / 已发布 / 审核中 / 未通过」，上传页也没有草稿列表。
所以这一档比视频号窄，清单里必须写明入口在哪，
否则人找不到草稿会以为没存上。

⚠️ **而且草稿会消失。** 实测到一次：中途首页的「继续编辑」入口消失了，
直接开草稿编辑页 URL 得到的是空编辑器。所以清单必须写「当场确认」，
不能让人以为存了就完事。
"""

import json
from pathlib import Path

import pytest

from douyin import notify, package, snapshot, state


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
    package.mark_published(result.dir, "https://www.douyin.com/video/1")
    package.mark_drafted(result.dir)

    data = json.loads((result.dir / "meta.json").read_text(encoding="utf-8"))
    assert data["status"] == "drafted"
    assert data["published_url"] is None


def test_marking_drafted_without_a_package_is_an_error(tmp_path):
    """没有发布包就不许回填——没有那一版，就不能说「那一版存了草稿」。"""
    with pytest.raises(FileNotFoundError):
        package.mark_drafted(tmp_path / "nope")


def _mark_drafted(out, episode):
    """模拟 `douyin.cli mark drafted`：状态与包内快照一起更新。

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
    shot = json.loads((outbox / "ep01__douyin.json").read_text(encoding="utf-8"))
    assert shot["status"] == "drafted"


def test_a_changed_video_goes_back_to_packaged(meta, tmp_path, make_video,
                                               outbox):
    """成片变了就是另一条片子——之前那条草稿跟它无关，状态回到「待上传」。"""
    out = tmp_path / "out"
    package.build_package("ep01", meta, make_video(tmp_path / "v1.mp4"), out)
    _mark_drafted(out, "ep01")

    other = make_video(tmp_path / "v2.mp4", seconds=2)
    result = package.build_package("ep01", meta, other, out)

    assert result.status == "packaged"
    shot = json.loads((outbox / "ep01__douyin.json").read_text(encoding="utf-8"))
    assert shot["status"] == "packaged"


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


def test_the_drafted_phrase_does_not_say_it_is_still_waiting_to_upload():
    """说成「待上传」会让人**再传一遍**——草稿已经在平台上了。"""
    text = notify.phrase("drafted")
    assert "待你上传" not in text


# --- 清单：草稿在哪、怎么确认 ------------------------------------------------


def test_the_checklist_says_where_the_draft_is(meta, video, tmp_path):
    """抖音没有草稿箱——清单必须写明入口在哪。

    人按清单存完草稿，回头找不到，就会以为没存上，接着去传第二遍。
    """
    result = package.build_package("ep01", meta, video, tmp_path / "out")
    checklist = (result.dir / "publish.md").read_text(encoding="utf-8")
    assert "继续编辑" in checklist
    assert "内容管理" in checklist          # 说清楚「草稿不在这里」
    assert "home_draft" in checklist


def test_the_checklist_lists_both_draft_entries(meta, video, tmp_path):
    """草稿有两个入口（2026-11-15 实测），两个都要写出来。

    只写首页那个，人在上传页看到「你还有上次未发布的视频」的提示时
    会以为存失败了，又传一遍。
    """
    result = package.build_package("ep01", meta, video, tmp_path / "out")
    checklist = (result.dir / "publish.md").read_text(encoding="utf-8")
    assert "home_draft" in checklist         # 首页「作品发布」卡片
    assert "enter_from=draft" in checklist   # 上传页提示里的「继续编辑」


def test_the_checklist_warns_against_opening_the_draft_url_directly(meta, video, tmp_path):
    """直接开草稿编辑页 URL 会得到**空编辑器**——清单必须写这条。

    实测（2026-11-15）：直接开 `?enter_from=draft` 得到 0/30、0/1000、
    无视频。人照着 URL 自己开一次，会以为草稿丢了，然后重传一遍。
    """
    result = package.build_package("ep01", meta, video, tmp_path / "out")
    checklist = (result.dir / "publish.md").read_text(encoding="utf-8")
    assert "别直接打开" in checklist
    assert "空编辑器" in checklist


def test_the_checklist_says_to_verify_the_draft_right_away(meta, video, tmp_path):
    """草稿实测会消失——清单必须让人当场确认，不能「存了就当成了」。"""
    result = package.build_package("ep01", meta, video, tmp_path / "out")
    checklist = (result.dir / "publish.md").read_text(encoding="utf-8")
    assert "会消失" in checklist


def test_the_checklist_says_the_two_cover_slots_need_two_uploads(meta, video, tmp_path):
    """两个封面槽位要**分别上传两张图**——只传一张后台会提示「双封面缺失」。

    实测（2026-11-15）：封面弹窗顶部是「设置竖封面 / 设置横封面」两个页签，
    各自有自己的上传区；两张都传完，发文助手才从「横/竖双封面缺失」
    变成「封面效果检测通过」。
    """
    result = package.build_package("ep01", meta, video, tmp_path / "out")
    checklist = (result.dir / "publish.md").read_text(encoding="utf-8")
    assert "cover_3x4.jpg" in checklist
    assert "cover_4x3.jpg" in checklist
    assert "分别上传" in checklist


def test_the_checklist_tells_you_to_verify_the_draft(meta, video, tmp_path):
    """存完草稿要**回首页确认**，才算存成功。"""
    result = package.build_package("ep01", meta, video, tmp_path / "out")
    checklist = (result.dir / "publish.md").read_text(encoding="utf-8")
    assert "mark drafted" in checklist


# --- 清单的措辞要跟着状态走 --------------------------------------------------


def test_the_checklist_follows_the_state(meta, video, tmp_path):
    """清单写着「待你上传」而 `meta.json` 写着「已存草稿」，人会**再传一遍**。

    人只看 `publish.md`——它和 `meta.json` 说的不是一回事，就是在平台上
    多出一条重复的作品。状态一变，清单的抬头与状态说明就得跟着变。
    """
    out = tmp_path / "out"
    package.build_package("ep01", meta, video, out)
    checklist = (out / "ep01" / "publish.md").read_text(encoding="utf-8")
    assert checklist.startswith("# 待发布：")
    assert "待你上传" in checklist

    _mark_drafted(out, "ep01")
    checklist = (out / "ep01" / "publish.md").read_text(encoding="utf-8")
    assert checklist.startswith("# 已存草稿，待发表：")
    assert "待你上传" not in checklist
    assert "已存草稿，待你点发表" in checklist


def test_the_checklist_says_published_after_publishing(meta, video, tmp_path):
    """发出去之后清单也不能还写「待你上传」。"""
    out = tmp_path / "out"
    package.build_package("ep01", meta, video, out)
    package.mark_published(out / "ep01", "https://www.douyin.com/video/1")

    checklist = (out / "ep01" / "publish.md").read_text(encoding="utf-8")
    assert checklist.startswith("# 已发布：")
    assert "待你上传" not in checklist


def test_the_checklist_does_not_claim_more_than_one_draft_was_tested(meta, video,
                                                                    tmp_path):
    """同时能留几条草稿**没实测**——清单不能替平台打包票。"""
    result = package.build_package("ep01", meta, video, tmp_path / "out")
    checklist = (result.dir / "publish.md").read_text(encoding="utf-8")
    assert "没实测" in checklist


# --- 命令行 -----------------------------------------------------------------


def _publish_meta(tmp_path) -> Path:
    publish_dir = tmp_path / "publish"
    publish_dir.mkdir()
    (publish_dir / "ep01.json").write_text(json.dumps({
        "episode": "ep01",
        "title": "PostgreSQL 18 并行逻辑解码",
        "cover_at": 1.0,
        "url": "https://growdu.cn/2026/11/12/source-tracks/blogging/L4-video-pipeline/aiv/",
        "douyin": {
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

    from douyin import cli

    publish_dir = _publish_meta(tmp_path)
    aiv_root = tmp_path / "aiv"
    (aiv_root / "out").mkdir(parents=True)
    make_video(aiv_root / "out" / "ep01__vertical.mp4", size="1080x1920")

    monkeypatch.setattr(cli, "AIV_ROOT", aiv_root)
    monkeypatch.setattr(epmeta, "PUBLISH_DIR", publish_dir)
    monkeypatch.setattr(snapshot, "OUTBOX_DIR", tmp_path / "outbox")

    out = tmp_path / "out"
    assert cli.main(["package", "ep01", "--out", str(out)]) == 0
    assert cli.main(["mark", "drafted", "ep01", "--out", str(out)]) == 0

    data = json.loads((out / "state.json").read_text(encoding="utf-8"))
    assert data["episodes"]["ep01"]["status"] == "drafted"
    assert data["episodes"]["ep01"]["published_url"] is None

    shot = json.loads((tmp_path / "outbox" / "ep01__douyin.json")
                      .read_text(encoding="utf-8"))
    assert shot["status"] == "drafted"
    assert shot["published_url"] is None
    # 快照要入库：路径得是相对的
    assert not Path(shot["package_dir"]).is_absolute()


def test_the_cli_refuses_to_mark_published_without_a_url(tmp_path, capsys):
    """`published` 没有链接就是没发布——报错，不要默认成「已发布」。"""
    from douyin import cli

    assert cli.main(["mark", "published", "ep01",
                     "--out", str(tmp_path / "out")]) == 1
    assert "url" in capsys.readouterr().err.lower()


def test_marking_drafted_does_not_ask_for_a_url(tmp_path, monkeypatch, capsys):
    """草稿档没有链接可填——**不能**因为缺 `--url` 就拒绝它。

    这里的失败理由必须是「发布包不存在」，不是「缺 --url」——
    后者说明命令把草稿档当成了 published 档。
    """
    from pyv import epmeta

    from douyin import cli

    publish_dir = _publish_meta(tmp_path)
    monkeypatch.setattr(epmeta, "PUBLISH_DIR", publish_dir)

    assert cli.main(["mark", "drafted", "ep01",
                     "--out", str(tmp_path / "out")]) == 1
    err = capsys.readouterr().err
    assert "--url" not in err
    assert "发布包不存在" in err


def test_the_cli_does_not_write_a_snapshot_when_publishing_has_no_url(
        tmp_path, monkeypatch):
    """报错的时候不能顺手把快照写成「已发布」。"""
    from douyin import cli

    monkeypatch.setattr(snapshot, "OUTBOX_DIR", tmp_path / "outbox")
    assert cli.main(["mark", "published", "ep01",
                     "--out", str(tmp_path / "out")]) == 1
    assert not (tmp_path / "outbox" / "ep01__douyin.json").exists()


def test_the_cli_does_not_write_a_snapshot_when_marking_draft_has_no_package(
        tmp_path, monkeypatch):
    """没有发布包就不许回填草稿——也不许留下状态与快照。"""
    from pyv import epmeta

    from douyin import cli

    publish_dir = _publish_meta(tmp_path)
    monkeypatch.setattr(epmeta, "PUBLISH_DIR", publish_dir)
    monkeypatch.setattr(snapshot, "OUTBOX_DIR", tmp_path / "outbox")

    out = tmp_path / "out"
    assert cli.main(["mark", "drafted", "ep01", "--out", str(out)]) == 1
    assert not (out / "state.json").exists()
    assert not (tmp_path / "outbox" / "ep01__douyin.json").exists()
