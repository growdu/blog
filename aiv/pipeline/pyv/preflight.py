"""成片技术门槛预检：这条片子能不能传上去。

「成片合不合格」是**生产者**的责任，不是平台的。
两个平台各判一遍会出现两个结论，门槛数字也会漂。
所以判定只有这一份，adapter 拿结果，不自己判。

硬门槛（平台会拒）→ 报错并给出修复命令；
建议门槛（平台接受但会降质）→ 告警，继续出包。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import tomllib
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from pyv.epmeta import CAPABILITIES_DIR, Finding, MetaError

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class VideoInfo:
    """一条视频的技术参数。"""

    width: int
    height: int
    fps: float
    duration: float
    video_codec: str
    pix_fmt: str
    audio_codec: str
    sample_rate: int
    channels: int
    audio_bitrate: int
    video_bitrate: int
    size_bytes: int
    keyframe_gaps: tuple[float, ...] = ()
    faststart: bool = False

    @property
    def max_keyframe_gap(self) -> float:
        return max(self.keyframe_gaps) if self.keyframe_gaps else 0.0

    @property
    def avg_bitrate(self) -> int:
        """平均码率（bps）。

        ffprobe 的流级 `bit_rate` 常常缺，退回「文件大小 × 8 ÷ 时长」——
        这个值永远算得出来，也是判定峰值码率门槛时的代理。
        """
        if self.duration <= 0:
            return 0
        return int(self.size_bytes * 8 / self.duration)


def _run_ffprobe(args: list[str]) -> str:
    proc = subprocess.run(["ffprobe", "-v", "error", *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe 失败：{(proc.stderr or '')[-500:]}")
    return proc.stdout


def keyframe_gaps(video: str | Path) -> tuple[float, ...]:
    """相邻关键帧之间的间隔（秒），末尾还接一段到片尾。

    B站《文件上传预处理》要求「视频关键帧至少 10 秒一个」，
    也就是**间隔不得超过 10 秒**。
    """
    out = _run_ffprobe([
        "-select_streams", "v:0", "-skip_frame", "nokey",
        "-show_entries", "frame=pts_time", "-of", "csv=p=0", str(video),
    ])
    times: list[float] = []
    for line in out.splitlines():
        line = line.strip().rstrip(",")
        if not line or line == "N/A":
            continue
        try:
            times.append(float(line))
        except ValueError:
            continue
    times.sort()
    gaps = [round(b - a, 3) for a, b in zip(times, times[1:])]
    if times:
        # 这里不能调 probe()：probe() 会反过来调 keyframe_gaps()，两者互递归
        # 会一路 RecursionError 炸到底。时长单独取。
        tail = round(_probe_duration(video) - times[-1], 3)
        if tail > 0:
            gaps.append(tail)
    return tuple(gaps)


def _probe_duration(video: str | Path) -> float:
    """只要时长。

    单独拎出来，是为了断开 `probe()` ↔ `keyframe_gaps()` 的互递归：
    probe() 要调 keyframe_gaps()，keyframe_gaps() 就不能再调 probe()。
    """
    raw = _run_ffprobe(["-of", "json", "-show_format", str(video)])
    data = json.loads(raw or "{}")
    return float(data.get("format", {}).get("duration", 0.0))


def _parse_fps(value: str) -> float:
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return 0.0


def probe(video: str | Path) -> VideoInfo:
    """用 ffprobe 读一条视频的技术参数。"""
    path = Path(video)
    if not path.is_file():
        raise FileNotFoundError(f"成片不存在：{path}")
    raw = _run_ffprobe(["-of", "json", "-show_format", "-show_streams", str(path)])
    data = json.loads(raw or "{}")
    streams = data.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video_stream is None:
        raise RuntimeError(f"这不是一条视频：{path}")
    fmt = data.get("format", {})
    return VideoInfo(
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        fps=_parse_fps(video_stream.get("r_frame_rate", "0/1")),
        duration=float(fmt.get("duration", 0.0)),
        video_codec=str(video_stream.get("codec_name", "")),
        pix_fmt=str(video_stream.get("pix_fmt", "")),
        audio_codec=str((audio_stream or {}).get("codec_name", "")),
        sample_rate=int((audio_stream or {}).get("sample_rate", 0)),
        channels=int((audio_stream or {}).get("channels", 0)),
        audio_bitrate=int((audio_stream or {}).get("bit_rate", 0)),
        video_bitrate=int(video_stream.get("bit_rate", 0)),
        size_bytes=int(fmt.get("size", path.stat().st_size)),
        keyframe_gaps=keyframe_gaps(path),
        faststart=has_faststart(path),
    )


def _top_level_boxes(path: Path) -> list[str]:
    """按文件顺序读出 mp4 顶层盒子的类型。

    mp4 是「盒子套盒子」：每个顶层盒子头 8 字节 = 4 字节长度（含头）+ 4 字节类型。
    长度 1 表示真实长度在后面 8 字节（64 位扩展），此时盒头共 **16 字节**；
    长度 0 表示这个盒子到文件尾。

    盒头长度必须记清楚：按 8 字节跳会把下一个盒头**错位 8 字节**，读到的是垃圾盒子——
    faststart 的结论就跟着错（一个真 faststart 的文件会被判成不是）。
    """
    boxes: list[str] = []
    with open(path, "rb") as handle:
        while True:
            header = handle.read(8)
            if len(header) < 8:
                break
            size = int.from_bytes(header[:4], "big")
            box = header[4:8].decode("latin-1")
            header_size = 8
            if size == 1:
                extra = handle.read(8)
                if len(extra) < 8:
                    break
                size = int.from_bytes(extra, "big")
                header_size = 16
            boxes.append(box)
            if size == 0 or size < header_size:
                break
            handle.seek(size - header_size, 1)
    return boxes


def has_faststart(video: str | Path) -> bool:
    """moov 是否排在 mdat 之前。

    ffprobe 报不出这个——它只解封装，不报盒子在文件里的位置。
    视频号要求 moov 前置：不前置的片子，手机端要等整片下完才起播。
    """
    boxes = _top_level_boxes(Path(video))
    if "moov" not in boxes:
        return False
    if "mdat" not in boxes:
        return True
    return boxes.index("moov") < boxes.index("mdat")


def _load_media(platform: str, capabilities_dir: Path | None) -> dict:
    base = Path(capabilities_dir) if capabilities_dir else CAPABILITIES_DIR
    path = base / f"{platform}.toml"
    if not path.is_file():
        raise MetaError(f"能力声明不存在：{path}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return data.get("media", {}) or {}


def check_video(info: VideoInfo, platform: str,
                capabilities_dir: Path | None = None) -> list[Finding]:
    """按平台能力声明判定一条成片。"""
    media = _load_media(platform, capabilities_dir)
    findings: list[Finding] = []
    target = platform

    def fail(rule_id, message):
        findings.append(Finding(rule_id, ERROR, message, target))

    if "min_width" in media and info.width < media["min_width"]:
        fail("preflight.resolution",
             f"宽度 {info.width} 低于平台要求的 {media['min_width']}")
    if "min_height" in media and info.height < media["min_height"]:
        fail("preflight.resolution",
             f"高度 {info.height} 低于平台要求的 {media['min_height']}")
    if "max_width" in media and info.width > media["max_width"]:
        fail("preflight.resolution",
             f"宽度 {info.width} 超过平台上限 {media['max_width']}")
    if "max_height" in media and info.height > media["max_height"]:
        fail("preflight.resolution",
             f"高度 {info.height} 超过平台上限 {media['max_height']}")
    if "max_fps" in media and info.fps > media["max_fps"] + 0.01:
        fail("preflight.fps",
             f"帧率 {info.fps:.3f} 超过平台上限 {media['max_fps']}")
    if "require_pix_fmt" in media and info.pix_fmt != media["require_pix_fmt"]:
        fail("preflight.pix-fmt",
             f"像素格式 {info.pix_fmt!r}，平台要求 {media['require_pix_fmt']!r}")
    if "max_duration_s" in media and info.duration > media["max_duration_s"]:
        fail("preflight.duration",
             f"时长 {info.duration:.1f}s 超过平台上限 {media['max_duration_s']}s")
    if "max_bytes" in media and info.size_bytes > media["max_bytes"]:
        fail("preflight.size",
             f"文件 {info.size_bytes} 字节，超过平台上限 {media['max_bytes']}")
    if "max_audio_bitrate" in media and info.audio_bitrate > media["max_audio_bitrate"]:
        fail("preflight.audio",
             f"音频码率 {info.audio_bitrate} 超过平台上限 {media['max_audio_bitrate']}")
    if "max_audio_channels" in media and info.channels > media["max_audio_channels"]:
        fail("preflight.audio",
             f"声道数 {info.channels} 超过平台上限 {media['max_audio_channels']}")
    if "max_sample_rate" in media and info.sample_rate > media["max_sample_rate"]:
        fail("preflight.audio",
             f"采样率 {info.sample_rate} 超过平台上限 {media['max_sample_rate']}")
    if "require_video_codec" in media and info.video_codec != media["require_video_codec"]:
        fail("preflight.codec",
             f"视频编码 {info.video_codec!r}，平台要求 {media['require_video_codec']!r}。"
             f"修复：ffmpeg -i <成片> -c:v libx264 -preset medium -crf 18 "
             f"-c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart <输出>")
    if "require_faststart" in media and media["require_faststart"] and not info.faststart:
        fail("preflight.faststart",
             "moov 不在 mdat 之前（没有 faststart），平台要等整片下完才起播。"
             "修复：ffmpeg -i <成片> -c copy -movflags +faststart <输出>")
    if "max_video_bitrate" in media:
        bitrate = max(info.video_bitrate, info.avg_bitrate)
        if bitrate > media["max_video_bitrate"]:
            fail("preflight.video-bitrate",
                 f"视频码率 {bitrate} bps 超过平台上限 {media['max_video_bitrate']} bps")
    if "max_keyframe_gap_s" in media and info.max_keyframe_gap > media["max_keyframe_gap_s"]:
        fail("preflight.keyframe",
             f"关键帧最大间隔 {info.max_keyframe_gap:.3f}s 超过 "
             f"{media['max_keyframe_gap_s']}s。修复："
             f"ffmpeg -i <成片> -c:v libx264 -preset medium -crf 18 -g 240 "
             f"-c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart <输出>")
    return findings


def file_sha256(path: str | Path) -> str:
    """成片的指纹。成片变了就重新出包。"""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
