import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for extra in (REPO_ROOT / "douyin", REPO_ROOT / "aiv" / "pipeline"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from pyv import epmeta  # noqa: E402


def _encode(path: Path, seconds: int = 3) -> Path:
    """造一段合法的小视频。

    尺寸、像素格式与 faststart 都按视频平台自己的门槛来
    （`publish/capabilities/douyin.toml` 的 `[media]`）：
    出包前要过技术预检，fixture 自己不合规的话，
    测到的就只剩预检，而不是出包。
    """
    import subprocess

    proc = subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"testsrc=size=1920x1080:rate=24:duration={seconds}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(path),
    ], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-500:]
    return path


@pytest.fixture
def make_video():
    """给一个路径，在那儿造一段合规的小视频。"""
    def _make(path, seconds: int = 3) -> Path:
        return _encode(Path(path), seconds)
    return _make


@pytest.fixture(autouse=True)
def outbox(tmp_path, monkeypatch):
    """测试期间状态快照写进临时目录。

    默认位置是 `publish/outbox/`（规格 §7.5），那是仓库里的一个目录——
    测试不该往仓库里写东西，出了包也说不清是哪次跑的。
    """
    from douyin import snapshot

    target = tmp_path / "outbox"
    monkeypatch.setattr(snapshot, "OUTBOX_DIR", target)
    return target


@pytest.fixture
def meta():
    """一份合法的抖音元数据。

    `cover_at` 落在成片时长之内——取帧点超出成片，ffmpeg 抽不出画面。
    """
    return epmeta.EpisodeMeta(
        episode="ep01",
        title="PostgreSQL 18 并行逻辑解码",
        cover_at=1.0,
        url="https://growdu.cn/2026/11/12/life/aiv/",
        douyin={
            "title": "32 核机器，解码只占 1 核",
            "description": "默认发布端只有一个解码线程，串行处理。",
            "topics": ["PostgreSQL", "逻辑复制", "数据库内核"],
        },
    )


@pytest.fixture
def video(tmp_path, make_video):
    """现场造一段 3 秒的小视频当成片。"""
    return make_video(tmp_path / "ep01.mp4")
