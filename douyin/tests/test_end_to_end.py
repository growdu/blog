"""端到端：真实成片 + 真实元数据走完整条出包链路。

**为什么单��立这一层。** 单元测试用的是合成的 fixture：它能验「出包这个
函数怎么工作」，验不了「真实的成片和真实的文案凑在一起还成立」。

这一层用**仓库里真实的东西**：
- 成片 `aiv/out/<EP>.mp4`（本机产物，不入库，所以没有就跳过）
- 元数据 `aiv/publish/<EP>.json`（入库的事实）

跑的是真正的 `build_package`，不是拼出来的假象。
"""

import json
from pathlib import Path

import pytest

from douyin import contract, package
from pyv import epmeta

AIV_ROOT = Path(__file__).resolve().parents[2] / "aiv"
EPISODES = ("csn-total-ordering", "parallel-apply", "pg-parallel-decode",
            "row-lock", "structured-ddl", "wal-interleave")


def _real_video(episode: str) -> Path | None:
    path = AIV_ROOT / "out" / f"{episode}.mp4"
    return path if path.is_file() else None


@pytest.fixture(scope="module")
def long_video(tmp_path_factory):
    """一段够长的合成成片。

    **必须够长**：真实元数据的 `cover_at` 在 16~20 秒之间，抽帧点超出成片
    时预检会正确报错（`epmeta.cover-at`）——那条闸不是要被绕过去的，
    是要保留的。所以这里造 25 秒，而不是把 `cover_at` 改小。

    模块级：造一次，六期共用——ffmpeg 编一次比编六次省得多。
    """
    from conftest import _encode

    return _encode(tmp_path_factory.mktemp("video") / "long.mp4", seconds=25)


# --- 真实成片 ---------------------------------------------------------------


@pytest.mark.parametrize("episode", EPISODES)
def test_a_real_episode_packages_end_to_end(episode, tmp_path, outbox):
    """真实成片 + 真实元数据 → 出包 → 快照。

    成片是本机产物，不在仓库里——没有就跳过，不假装验过。
    """
    video = _real_video(episode)
    if video is None:
        pytest.skip(f"本机没有成片 {video}（成片是 gitignore 的本地产物）")

    meta = epmeta.load_meta(episode)
    result = package.build_package(episode, meta, video, tmp_path / "out")

    # 包里的东西都在
    for name in ("video.mp4", "cover.jpg", "title.txt", "description.txt",
                 "topics.txt", "text.txt", "publish.md", "meta.json"):
        assert (result.dir / name).is_file(), f"{episode} 缺 {name}"

    # 软链指向真实成片，不是复制品
    assert (result.dir / "video.mp4").resolve() == video.resolve()

    # text.txt 是元数据拼出来的那一段，一个字不差
    copy = contract.slice_copy(meta)
    assert (result.dir / "text.txt").read_text(encoding="utf-8") == \
        contract.build_text(copy)

    # 快照写对了，而且写进的是本次测试的临时目录（没往仓库里写）
    snapshot = outbox / f"{episode}__douyin.json"
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    assert data["platform"] == "douyin"
    assert data["content_id"] == episode
    assert data["status"] == "packaged"
    assert data["published_url"] is None


@pytest.mark.parametrize("episode", EPISODES)
def test_a_real_cover_is_actually_a_frame(episode, tmp_path):
    """封面得是**有内容**的一帧，不能是一张纯色图。

    「文件生成了」不等于「画面里真有东西」：抽帧点算错、ffmpeg 只输出了
    一个空帧，文件照样在。这条断言用的是**像素本身有变化**——
    纯色图（黑帧、白帧、纯色底）的像素方差接近 0。
    """
    from PIL import Image, ImageStat

    video = _real_video(episode)
    if video is None:
        pytest.skip(f"本机没有成片 {video}")

    meta = epmeta.load_meta(episode)
    result = package.build_package(episode, meta, video, tmp_path / "out")
    with Image.open(result.dir / "cover.jpg") as cover:
        cover = cover.convert("RGB")
        stat = ImageStat.Stat(cover)
        spread = max(stat.stddev)
        assert spread > 5, (
            f"{episode} 的封面几乎是纯色（最大通道标准差 {spread:.2f}）——"
            f"抽到的不是有画面的那一帧"
        )


# --- 六期元数据全量 ---------------------------------------------------------


@pytest.mark.parametrize("episode", EPISODES)
def test_every_real_episode_packages_with_a_synthetic_video(episode, tmp_path,
                                                            long_video):
    """成片换成合成的，六期真实元数据都得能出包。

    这一条不依赖本机成片，所以**在 CI 上也真的跑**——
    证明的是「元数据 + 能力声明 + 预检」这一段链路是通的。
    """
    meta = epmeta.load_meta(episode)
    result = package.build_package(episode, meta, long_video, tmp_path / "out")
    assert result.status == "packaged"
    assert result.warnings == []


@pytest.mark.parametrize("episode", EPISODES)
def test_the_packaged_text_never_carries_an_outbound_link(episode, tmp_path,
                                                          long_video):
    """出包里的整段文案不得有站外引流。

    这是抖音最容易踩的雷：文案粘到平台上才被限流，
    而那时已经发出去了，只能删了重发。
    """
    meta = epmeta.load_meta(episode)
    result = package.build_package(episode, meta, long_video, tmp_path / "out")
    text = (result.dir / "text.txt").read_text(encoding="utf-8")
    assert contract.check_no_outbound(text) == [], episode
