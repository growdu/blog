import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for extra in (REPO_ROOT / "douyin", REPO_ROOT / "aiv" / "pipeline"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from pyv import epmeta  # noqa: E402


def _encode(path: Path, seconds: int = 3, size: str = "1920x1080") -> Path:
    """造一段合法的小视频。

    尺寸、像素格式与 faststart 都按视频平台自己的门槛来
    （`publish/capabilities/douyin.toml` 的 `[media]`）：
    出包前要过技术预检，fixture 自己不合规的话，
    测到的就只剩预检，而不是出包。

    `size` 默认横版；抖音那一档实际发的是竖版 9:16，所以这里要能造竖版。
    """
    import subprocess

    proc = subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"testsrc=size={size}:rate=24:duration={seconds}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(path),
    ], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-500:]
    return path


@pytest.fixture
def make_video():
    """给一个路径，在那儿造一段合规的小视频。"""
    def _make(path, seconds: int = 3, size: str = "1920x1080") -> Path:
        return _encode(Path(path), seconds, size)
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


@pytest.fixture(autouse=True, scope="session")
def _the_repo_outbox_stays_untouched():
    """测试不许往仓库里的 `publish/outbox` 写东西。

    **基准是会话起点，不是每个测试的前后。** 前后比对看不见**上一个
    测试**留下的东西——那个文件在本次起点就已经存在了，于是「前后一样」，
    守卫报一切正常。而脏文件恰恰会活过整个 session，最后混进提交。

    再补一条判据：**入库目录里只允许有 git 跟踪的文件**。测试写出来的
    文件一定是未跟踪的，`git ls-files` 是唯一能发现「上个 session
    遗留」的办法。

    踩过的坑：命令行测试是**另一个进程**，conftest 里把快照目录改到
    临时区拦不住它——它把 `publish/outbox/structured-ddl__douyin.json`
    写成了指向 pytest 临时目录的垃圾：文件在、JSON 合法、看着像真的
    状态，下一个人读到的是假的。
    """
    repo_outbox = REPO_ROOT / "publish" / "outbox"

    def _on_disk():
        if not repo_outbox.is_dir():
            return {}
        return {path.name: path.read_bytes()
                for path in sorted(repo_outbox.glob("*.json"))}

    def _tracked():
        import subprocess

        probe = subprocess.run(["git", "rev-parse", "--git-dir"],
                               cwd=REPO_ROOT, capture_output=True, text=True)
        if probe.returncode != 0:
            return None                      # 不在 git 仓库里，跳过这条判据
        result = subprocess.run(["git", "ls-files", "publish/outbox"],
                                cwd=REPO_ROOT, capture_output=True, text=True)
        return {line.strip() for line in result.stdout.splitlines() if line.strip()}

    before = _on_disk()
    yield
    after = _on_disk()

    changed = sorted(
        name for name in set(before) | set(after)
        if before.get(name) != after.get(name)
    )
    assert not changed, f"测试往仓库的 publish/outbox 写了东西：{changed}"

    tracked = _tracked()
    if tracked is not None:
        untracked = sorted(
            name for name in after
            if f"publish/outbox/{name}" not in tracked
        )
        assert not untracked, (
            f"publish/outbox 里有没被 git 跟踪的文件：{untracked}"
            f"（上个 session 留下的脏文件，或本次测试写的）"
        )


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
