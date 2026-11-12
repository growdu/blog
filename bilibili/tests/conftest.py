import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for extra in (REPO_ROOT / "bilibili", REPO_ROOT / "aiv" / "pipeline"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from pyv import epmeta  # noqa: E402


def _encode(path: Path, seconds: int = 3) -> Path:
    """造一段合法的小视频。

    参数按 B 站自己的门槛来（`publish/capabilities/bilibili.toml` 的 `[media]`）：
    B 站不设最小分辨率，但设了 `max_keyframe_gap_s = 10`。
    夹具自己不合格的话，测到的就只剩预检，而不是出包。
    """
    import subprocess

    proc = subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"testsrc=size=320x180:rate=24:duration={seconds}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-g", "48",
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
    from bilibili import snapshot

    target = tmp_path / "outbox"
    monkeypatch.setattr(snapshot, "OUTBOX_DIR", target)
    return target


@pytest.fixture
def meta():
    """一份合法的B站元数据。

    `cover_at` 落在成片时长之内——取帧点超出成片，ffmpeg 抽不出画面。
    """
    return epmeta.EpisodeMeta(
        episode="ep02",
        title="一个 64 位计数器，决定所有事务的提交顺序",
        cover_at=1.0,
        url="https://growdu.cn/2026/11/12/life/aiv/",
        bilibili={
            "title": "一个 64 位计数器，决定所有事务的提交顺序",
            "description": "并发时 commit 的先后是乱的。",
            "tags": ["openGauss", "数据库", "源码"],
            "tid": 231,
            "copyright": 1,
            "no_reprint": 1,
        },
    )


@pytest.fixture
def video(tmp_path, make_video):
    """现场造一段 3 秒的小视频当成片。"""
    return make_video(tmp_path / "ep02.mp4")


@pytest.fixture
def subtitle_events():
    """几条字幕事件。"""
    from bilibili import subtitle

    return [
        subtitle.SubtitleEvent(start=0.0, end=2.5, text="第一句"),
        subtitle.SubtitleEvent(start=2.5, end=5.0, text="第二句"),
    ]
