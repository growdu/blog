"""成片技术门槛预检。

预检要能**抓得出问题**，所以测试里现造一段有问题的视频，
而不是只测一段好视频通过。

成片本身不入库（`aiv/out/` 是 gitignore 的产物目录），
所以这里用 ffmpeg 现场生成 12 秒的小视频——
既不把媒体塞回仓库，又能在干净检出上跑通。
"""
import struct
import subprocess

import pytest

from pyv import preflight


def _make_video(path, seconds=12, gop=None, faststart=False):
    """现场造一段小视频。

    gop 决定关键帧间隔，faststart 决定 moov 排不排在 mdat 前面。
    """
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"testsrc=size=320x180:rate=24:duration={seconds}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
    ]
    if gop is not None:
        cmd += ["-g", str(gop)]
    if faststart:
        cmd += ["-movflags", "+faststart"]
    cmd += [str(path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-500:]
    return path


def test_probe_reads_the_technical_parameters(tmp_path):
    video = _make_video(tmp_path / "probe.mp4", seconds=2, gop=48)
    info = preflight.probe(video)
    assert info.width == 320
    assert info.height == 180
    assert round(info.fps) == 24
    assert 1.5 < info.duration < 2.5
    assert info.pix_fmt == "yuv420p"


def test_probe_of_a_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        preflight.probe(tmp_path / "nope.mp4")


def test_keyframe_gaps_are_measured(tmp_path):
    video = _make_video(tmp_path / "kf.mp4", seconds=12, gop=48)
    gaps = preflight.keyframe_gaps(video)
    assert gaps
    assert max(gaps) <= 2.5


def test_a_ten_second_gop_passes_the_bilibili_rule(tmp_path):
    """-g 240 @24fps = 每 10 秒一个关键帧，刚好压线通过。"""
    video = _make_video(tmp_path / "ok.mp4", seconds=12, gop=240)
    info = preflight.probe(video)
    findings = preflight.check_video(info, "bilibili")
    assert [f for f in findings if f.rule_id == "preflight.keyframe"] == []


def test_a_long_gop_fails_the_bilibili_rule(tmp_path):
    video = _make_video(tmp_path / "bad.mp4", seconds=12, gop=1000)
    info = preflight.probe(video)
    findings = preflight.check_video(info, "bilibili")
    keyframes = [f for f in findings if f.rule_id == "preflight.keyframe"]
    assert len(keyframes) == 1
    assert keyframes[0].level == preflight.ERROR
    # 报错要给出修复命令，不能只说一句「不合格」
    assert "-g 240" in keyframes[0].message


def test_channels_has_no_keyframe_rule(tmp_path):
    video = _make_video(tmp_path / "bad2.mp4", seconds=12, gop=1000)
    info = preflight.probe(video)
    findings = preflight.check_video(info, "channels")
    assert [f for f in findings if f.rule_id == "preflight.keyframe"] == []


def test_too_small_a_resolution_is_an_error(tmp_path):
    video = _make_video(tmp_path / "small.mp4", seconds=1, gop=24)
    info = preflight.probe(video)
    findings = preflight.check_video(info, "channels")
    assert any(f.rule_id == "preflight.resolution" for f in findings)


def test_file_sha256_changes_with_the_content(tmp_path):
    one = tmp_path / "one.bin"
    one.write_bytes(b"hello")
    two = tmp_path / "two.bin"
    two.write_bytes(b"hellp")
    assert preflight.file_sha256(one) != preflight.file_sha256(two)
    assert preflight.file_sha256(one) == preflight.file_sha256(one)


def test_a_video_without_faststart_fails_the_channels_rule(tmp_path):
    """视频号要求 moov 前置——不然手机端要等整片下完才起播。"""
    video = _make_video(tmp_path / "slow.mp4", seconds=1)
    assert preflight.has_faststart(video) is False
    info = preflight.probe(video)
    findings = preflight.check_video(info, "channels")
    assert any(f.rule_id == "preflight.faststart" for f in findings)


def test_a_faststart_video_passes_the_channels_rule(tmp_path):
    video = _make_video(tmp_path / "quick.mp4", seconds=1, faststart=True)
    assert preflight.has_faststart(video) is True
    info = preflight.probe(video)
    findings = preflight.check_video(info, "channels")
    assert [f for f in findings if f.rule_id == "preflight.faststart"] == []


def test_the_box_parser_handles_a_64_bit_extended_size(tmp_path):
    """盒子超过 4 GiB 时必须用 64 位扩展长度。

    扩展形式的盒头是 16 字节（8 字节头 + 8 字节扩展长度）——
    按 8 字节跳会把下一个盒头错位 8 字节，读到垃圾盒子，
    faststart 的结论就跟着错（真 faststart 的文件会被判成不是）。
    """
    def box(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", 8 + len(payload)) + kind + payload

    def box64(kind: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", 1) + kind
                + struct.pack(">Q", 16 + len(payload)) + payload)

    path = tmp_path / "wide.mp4"
    # ftyp + free(64 位扩展) + moov + mdat —— moov 在 mdat 之前，是 faststart
    path.write_bytes(
        box(b"ftyp", b"") + box64(b"free", b"\x00" * 64)
        + box(b"moov", b"") + box(b"mdat", b"\x00" * 16)
    )
    assert preflight._top_level_boxes(path) == ["ftyp", "free", "moov", "mdat"]
    assert preflight.has_faststart(path) is True


def test_a_non_h264_video_fails_the_codec_rule():
    """平台只要 H.264——HEVC 在部分安卓机上放不出来。

    这里直接造 VideoInfo，不去编 HEVC：那台机器的 ffmpeg 未必带 libx265。
    """
    info = preflight.VideoInfo(
        width=1920, height=1080, fps=24.0, duration=38.0,
        video_codec="hevc", pix_fmt="yuv420p", audio_codec="aac",
        sample_rate=48000, channels=2, audio_bitrate=192000,
        video_bitrate=864000, size_bytes=5_000_000,
    )
    findings = preflight.check_video(info, "channels")
    assert any(f.rule_id == "preflight.codec" for f in findings)


def test_an_excessive_bitrate_fails_the_bilibili_rule():
    info = preflight.VideoInfo(
        width=1920, height=1080, fps=24.0, duration=38.0,
        video_codec="h264", pix_fmt="yuv420p", audio_codec="aac",
        sample_rate=48000, channels=2, audio_bitrate=192000,
        video_bitrate=90_000_000, size_bytes=5_000_000,
    )
    findings = preflight.check_video(info, "bilibili")
    assert any(f.rule_id == "preflight.video-bitrate" for f in findings)
