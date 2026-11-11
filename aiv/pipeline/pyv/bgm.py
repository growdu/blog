"""背景音乐规则：获取、选曲、规格、混音。

规范见 `aiv/背景音乐规范.md`。这里是规范的**可执行部分**：
把「什么样的曲子算合格」「怎么混」变成能跑的判据。

三块：

1. **台账**（`aiv/music/library.json`）——曲库下载的曲子逐首登记授权，
   音频本身不入库（媒体产物留本机），台账是事实，必须入库。
2. **选曲与规格**——测 LUFS / 真峰值 / 频段占比 / 频谱重心，定出阈值。
3. **混音**——固定参数的 ducking 与 EQ 避让。

**为什么 ducking 不用 ffmpeg 的 sidechaincompress**：实测下来，压缩器的
压深依赖语音包络与 attack/release 的耦合，同一组参数在不同语音上能差
2 dB 以上（标定记录见规范 §5.2）。规则要能被机器判定，深度就得是确定的
数，所以这里按旁白包络自己算增益曲线，深度精确可控。
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# aiv/ 是 pipeline/ 的上一级：pyv/bgm.py → pyv → pipeline → aiv
AIV_ROOT = Path(__file__).resolve().parents[2]
MUSIC_ROOT = AIV_ROOT / "music"
LIBRARY_PATH = MUSIC_ROOT / "library.json"
TRACKS_DIR = MUSIC_ROOT / "tracks"

# ---------------------------------------------------------------- 选曲与规格

# 入库时统一归一化到的响度。曲库母带的响度差能到 10 dB 以上，
# 不统一就没法用固定增益混音（这是本规范最重要的一条）。
MASTER_LUFS = -20.0
# 归一化后源文件的真峰值上限（留混音余量）
MAX_TRUE_PEAK_DB = -3.0
# 1~4 kHz 是旁白清晰度区，BGM 在这一段占得越少越不抢
MAX_VOICE_BAND = 0.30
# >10 kHz 占比上限（刺耳）
MAX_AIR_BAND = 0.10
# 频谱重心上限（暗色 ambient；亮音乐会像广告）
MAX_CENTROID_HZ = 2000.0
REQUIRED_SAMPLE_RATE = 48000
REQUIRED_CHANNELS = 2

# 频段划分（Hz）
BANDS = {
    "sub": (20, 100),
    "bass": (100, 400),
    "mid": (400, 1000),
    "voice": (1000, 4000),
    "presence": (4000, 10000),
    "air": (10000, 20000),
}

# ---------------------------------------------------------------- 混音参数

# 这些是**固定写死**的：同样的输入必须出同样的片，所以一个都不能是自适应值。
BGM_GAIN_DB = -15.0        # 基础增益：BGM 落到 -35 LUFS，比旁白低约 11 dB
DUCK_DEPTH_DB = -7.0       # 旁白段额外压低（旁白段共低约 18 dB，句间停顿回升）
DUCK_ATTACK_MS = 120       # 跟着语音起落，又不能抖
DUCK_RELEASE_MS = 600
EQ_BELL_HZ = 1800          # 避让中心：旁白清晰度区
EQ_BELL_DB = -6.0
EQ_BELL_Q = 1.0
HIGHPASS_HZ = 30           # 砍掉无用的超低频，给旁白腾动态余量

# 旁白包络阈值（dBFS）：高于 ON 算「有人在说话」，低于 OFF 才算停
SPEECH_ON_DB = -45.0
SPEECH_OFF_DB = -50.0
ENVELOPE_WINDOW_MS = 10.0

# 台账里的授权类型白名单
ALLOWED_LICENSES = (
    "CC0-1.0",
    "CC-BY-4.0",
    "CC-BY-3.0",
    "Pixabay Content License",
    "YouTube Audio Library",
    "Public Domain",
)

# 系列里的角色：motif 每期最多 1 首（系列听觉标识），bed 每期最多 2 首
SERIES_ROLES = ("motif", "bed", "sting")
MAX_MOTIF_TRACKS = 1
MAX_BED_TRACKS = 2

RULE_IDS = (
    "bgm.sample-rate",
    "bgm.channels",
    "bgm.duration",
    "bgm.true-peak",
    "bgm.voice-band",
    "bgm.air-band",
    "bgm.centroid",
    "bgm.license",
    "bgm.attribution",
    "bgm.fingerprint",
    "bgm.series-role",
)

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    """一条检查结果。"""

    rule_id: str
    level: str
    message: str
    target: str = ""

    def __str__(self) -> str:
        where = f"[{self.target}] " if self.target else ""
        return f"{where}{self.rule_id} {self.message}"


@dataclass(frozen=True)
class AudioProfile:
    """一条音频的实测特征。"""

    path: str
    duration_s: float
    sample_rate: int
    channels: int
    lufs: float
    true_peak_db: float
    band_ratios: dict = field(default_factory=dict)
    centroid_hz: float = 0.0

    @property
    def voice_band(self) -> float:
        return self.band_ratios.get("voice", 0.0)

    @property
    def air_band(self) -> float:
        return self.band_ratios.get("air", 0.0)


@dataclass(frozen=True)
class TrackEntry:
    """台账里的一首曲子。"""

    id: str
    title: str
    artist: str
    source: str
    source_url: str
    license: str
    series_role: str
    local_path: str
    attribution_required: bool = False
    attribution_text: str = ""
    bpm: float | None = None
    duration_s: float | None = None
    sha256: str = ""
    downloaded_at: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, raw: dict) -> "TrackEntry":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in raw.items() if k in known})

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "artist": self.artist,
            "source": self.source, "source_url": self.source_url,
            "license": self.license, "series_role": self.series_role,
            "local_path": self.local_path,
            "attribution_required": self.attribution_required,
            "attribution_text": self.attribution_text,
            "bpm": self.bpm, "duration_s": self.duration_s,
            "sha256": self.sha256, "downloaded_at": self.downloaded_at,
            "notes": self.notes,
        }


# ---------------------------------------------------------------- 测量


def _run(cmd: list[str], text: bool = True, **kwargs) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=text, **kwargs)
    if proc.returncode != 0:
        tail = proc.stderr if text else proc.stderr.decode(errors="replace")
        raise RuntimeError(
            f"命令失败（{proc.returncode}）：{' '.join(cmd[:3])} ...\n"
            f"{(tail or '')[-1200:]}"
        )
    return proc


def probe(path: str | Path) -> tuple[float, int, int]:
    """量时长（秒）、采样率、声道数。"""
    out = _run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration:stream=sample_rate,channels",
        "-of", "json", str(path),
    ]).stdout
    data = json.loads(out)
    streams = data.get("streams") or []
    if not streams:
        raise ValueError(f"{path} 里没有音频流")
    stream = streams[0]
    return (
        float(data["format"]["duration"]),
        int(stream.get("sample_rate", 0)),
        int(stream.get("channels", 0)),
    )


def measure_loudness(path: str | Path) -> tuple[float, float]:
    """量整体响度（LUFS）与真峰值（dBTP）。"""
    stderr = _run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
        "-af", "ebur128=peak=true", "-f", "null", "-",
    ]).stderr
    tail = stderr[stderr.rindex("Summary:"):]
    lufs_line = [ln for ln in tail.splitlines() if " I:" in ln]
    peak_line = [ln for ln in tail.splitlines() if "Peak:" in ln]
    if not lufs_line or not peak_line:
        raise ValueError(f"量不出 {path} 的响度")
    lufs = float(lufs_line[-1].split("I:")[1].split()[0])
    peak = float(peak_line[-1].split("Peak:")[1].split()[0])
    return lufs, peak


def decode_mono(path: str | Path, sample_rate: int = 48000) -> np.ndarray:
    """解码成单声道 float64 数组。"""
    raw = _run([
        "ffmpeg", "-v", "error", "-i", str(path),
        "-f", "f32le", "-ac", "1", "-ar", str(sample_rate), "-",
    ], text=False).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def band_ratios(samples: np.ndarray, sample_rate: int = 48000) -> dict:
    """各频段的能量占比与频谱重心。"""
    if samples.size == 0:
        return {}
    centred = samples - samples.mean()
    power = np.abs(np.fft.rfft(centred)) ** 2
    freqs = np.fft.rfftfreq(centred.size, 1 / sample_rate)
    total = power.sum()
    if total <= 0:
        return {name: 0.0 for name in BANDS}
    ratios = {}
    for name, (low, high) in BANDS.items():
        mask = (freqs >= low) & (freqs < high)
        ratios[name] = float(power[mask].sum() / total)
    centroid = float((freqs * power).sum() / total)
    ratios["_centroid_hz"] = centroid
    return ratios


def measure(path: str | Path) -> AudioProfile:
    """量一条音频的全部特征。"""
    duration, rate, channels = probe(path)
    lufs, peak = measure_loudness(path)
    samples = decode_mono(path)
    ratios = band_ratios(samples)
    centroid = ratios.pop("_centroid_hz", 0.0)
    return AudioProfile(
        path=str(path), duration_s=duration, sample_rate=rate, channels=channels,
        lufs=lufs, true_peak_db=peak, band_ratios=ratios, centroid_hz=centroid,
    )


# ---------------------------------------------------------------- 选曲规则


def check_profile(profile: AudioProfile,
                  required_duration_s: float | None = None) -> list[Finding]:
    """按实测特征判一条曲子合不合格（纯函数，便于测）。"""
    target = Path(profile.path).name
    findings: list[Finding] = []

    def add(rule_id: str, level: str, message: str) -> None:
        findings.append(Finding(rule_id, level, message, target))

    if profile.sample_rate != REQUIRED_SAMPLE_RATE:
        add("bgm.sample-rate", ERROR,
            f"采样率 {profile.sample_rate} Hz，必须是 {REQUIRED_SAMPLE_RATE} Hz")
    if profile.channels < REQUIRED_CHANNELS:
        add("bgm.channels", ERROR,
            f"只有 {profile.channels} 声道，必须是立体声")
    if required_duration_s is not None and profile.duration_s < required_duration_s:
        add("bgm.duration", ERROR,
            f"时长 {profile.duration_s:.1f}s，不够 {required_duration_s:.1f}s")
    if profile.true_peak_db > MAX_TRUE_PEAK_DB:
        add("bgm.true-peak", ERROR,
            f"真峰值 {profile.true_peak_db:.1f} dBTP，超过上限 {MAX_TRUE_PEAK_DB:.1f}")
    if profile.voice_band > MAX_VOICE_BAND:
        add("bgm.voice-band", ERROR,
            f"1~4 kHz 占 {profile.voice_band:.0%}，超过 {MAX_VOICE_BAND:.0%}"
            f"——这一段是旁白的清晰度区")
    if profile.air_band > MAX_AIR_BAND:
        add("bgm.air-band", ERROR,
            f">10 kHz 占 {profile.air_band:.0%}，超过 {MAX_AIR_BAND:.0%}——刺耳")
    if profile.centroid_hz > MAX_CENTROID_HZ:
        add("bgm.centroid", ERROR,
            f"频谱重心 {profile.centroid_hz:.0f} Hz，超过 {MAX_CENTROID_HZ:.0f} Hz"
            f"——亮音乐会像广告")
    return findings


def check_track(path: str | Path, required_duration_s: float | None = None) -> list[Finding]:
    """检查一条曲子合不合格。

    required_duration_s 给定时，曲子必须够长（短了要循环，
    循环点找不到就等于没有）。
    """
    return check_profile(measure(path), required_duration_s)


# ---------------------------------------------------------------- 台账


def load_library(path: str | Path = LIBRARY_PATH) -> list[TrackEntry]:
    """读台账。文件不存在返回空列表。"""
    file = Path(path)
    if not file.exists():
        return []
    raw = json.loads(file.read_text(encoding="utf-8"))
    return [TrackEntry.from_dict(item) for item in raw.get("tracks", [])]


def save_library(entries: list[TrackEntry], path: str | Path = LIBRARY_PATH) -> Path:
    """写台账。"""
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "tracks": [entry.to_dict() for entry in entries],
    }
    file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return file


def sha256_of(path: str | Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_library(entries: list[TrackEntry] | None = None,
                  path: str | Path = LIBRARY_PATH,
                  verify_fingerprint: bool = True) -> list[Finding]:
    """检查台账自身是否自洽。"""
    if entries is None:
        entries = load_library(path)
    findings: list[Finding] = []

    def add(rule_id: str, level: str, message: str, target: str = "") -> None:
        findings.append(Finding(rule_id, level, message, target))

    seen_ids: set[str] = set()
    roles: dict[str, int] = {}
    for entry in entries:
        target = entry.id or entry.title
        if entry.id in seen_ids:
            add("bgm.fingerprint", ERROR, f"台账里 id 重复：{entry.id}", target)
        seen_ids.add(entry.id)
        if entry.license not in ALLOWED_LICENSES:
            add("bgm.license", ERROR,
                f"授权类型 {entry.license!r} 不在白名单里", target)
        if entry.attribution_required and not entry.attribution_text.strip():
            add("bgm.attribution", ERROR,
                "需要署名的曲子必须写清 attribution_text", target)
        if entry.series_role not in SERIES_ROLES:
            add("bgm.series-role", ERROR,
                f"角色 {entry.series_role!r} 非法，应为 {'/'.join(SERIES_ROLES)}", target)
        else:
            roles[entry.series_role] = roles.get(entry.series_role, 0) + 1
        if not entry.sha256:
            add("bgm.fingerprint", ERROR, "缺 sha256 指纹", target)
        elif verify_fingerprint:
            local = AIV_ROOT / entry.local_path
            if local.exists() and sha256_of(local) != entry.sha256:
                add("bgm.fingerprint", ERROR,
                    "本地文件与台账里的 sha256 对不上", target)

    if roles.get("motif", 0) > MAX_MOTIF_TRACKS:
        add("bgm.series-role", ERROR,
            f"motif 有 {roles['motif']} 首，系列只能有 {MAX_MOTIF_TRACKS} 首"
            f"——多首就没有系列标识了")
    if roles.get("bed", 0) > MAX_BED_TRACKS:
        add("bgm.series-role", WARNING,
            f"bed 有 {roles['bed']} 首，每期最多用 {MAX_BED_TRACKS} 首")
    return findings


# ---------------------------------------------------------------- ducking


def speech_activity(narration: np.ndarray, sample_rate: int = 48000) -> np.ndarray:
    """旁白的「有人在说话」包络，取值 0~1。

    做法：10 ms 窗 RMS → dB → 双阈值迟滞（高于 ON 算起，低于 OFF 才算停）
    → 单极点平滑（起落用不同时间常数）。迟滞是为了不在句子边界上抖。
    """
    if narration.size == 0:
        return np.zeros(0)
    window = max(1, int(sample_rate * ENVELOPE_WINDOW_MS / 1000))
    frames = narration.size // window
    if frames == 0:
        return np.zeros(0)
    trimmed = narration[:frames * window].reshape(frames, window)
    rms = np.sqrt((trimmed ** 2).mean(axis=1))
    with np.errstate(divide="ignore"):
        level_db = 20 * np.log10(np.maximum(rms, 1e-12))

    activity = np.zeros(frames)
    speaking = False
    for index, level in enumerate(level_db):
        if speaking:
            if level < SPEECH_OFF_DB:
                speaking = False
        elif level > SPEECH_ON_DB:
            speaking = True
        activity[index] = 1.0 if speaking else 0.0

    # 单极点平滑：上升用 attack，下降用 release
    # 时间常数按「帧」算：每秒 1000/ENVELOPE_WINDOW_MS 帧
    frames_per_second = 1000.0 / ENVELOPE_WINDOW_MS
    attack = math.exp(-1.0 / max(1e-6, frames_per_second * DUCK_ATTACK_MS / 1000))
    release = math.exp(-1.0 / max(1e-6, frames_per_second * DUCK_RELEASE_MS / 1000))
    smoothed = np.zeros(frames)
    previous = 0.0
    for index, value in enumerate(activity):
        coefficient = attack if value > previous else release
        previous = coefficient * previous + (1 - coefficient) * value
        smoothed[index] = previous
    return smoothed


def duck_curve(narration: np.ndarray, depth_db: float = DUCK_DEPTH_DB,
               sample_rate: int = 48000) -> np.ndarray:
    """逐样本的增益因子（1.0 = 不压低，越小压得越狠）。"""
    activity = speech_activity(narration, sample_rate)
    if activity.size == 0:
        return np.ones(0)
    window = max(1, int(sample_rate * ENVELOPE_WINDOW_MS / 1000))
    curve = np.repeat(activity, window)[:narration.size]
    # depth_db 是负数：曲线为 1（有人说话）时增益 < 1（压低），为 0 时增益 = 1
    return 10 ** (depth_db * curve / 20)


def _write_wav(path: str | Path, samples: np.ndarray, sample_rate: int = 48000) -> Path:
    """写 16 bit 立体声 wav。"""
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(samples, -1.0, 1.0)
    data = (clipped * 32767).astype("<i2")
    with wave.open(str(file), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(data.tobytes())
    return file


def duck_bgm(bgm_path: str | Path, narration_path: str | Path,
             out_path: str | Path, depth_db: float = DUCK_DEPTH_DB,
             sample_rate: int = 48000,
             duration_s: float | None = None) -> Path:
    """按旁白包络压低 BGM，输出处理后的 wav。

    深度是**精确**的：旁白持续段正好压 `depth_db` dB，句间停顿处回到 0 dB。
    这正是不用 sidechaincompress 的原因——压缩器的压深随语音包络浮动，
    同一个参数在不同稿子上能差 2 dB 以上，规则就没法机器判定了。
    """
    raw = _run([
        "ffmpeg", "-v", "error", "-i", str(bgm_path),
        "-f", "f32le", "-ac", "2", "-ar", str(sample_rate), "-",
    ], text=False).stdout
    frames = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    if frames.size % 2:
        frames = frames[:-1]
    bgm = frames.reshape(-1, 2)

    narration = decode_mono(narration_path, sample_rate)
    if duration_s is not None:
        limit = int(duration_s * sample_rate)
        bgm = bgm[:limit]
        narration = narration[:limit]
    length = min(bgm.shape[0], narration.size)
    bgm = bgm[:length]
    curve = duck_curve(narration[:length], depth_db, sample_rate)
    ducked = bgm * curve[:length, None]
    return _write_wav(out_path, ducked, sample_rate)


# ---------------------------------------------------------------- 混音链


def eq_filter() -> str:
    """避让用的 bell 滤波器。"""
    return (f"equalizer=f={EQ_BELL_HZ}:t=q:w={EQ_BELL_Q}:g={EQ_BELL_DB}")


def bgm_chain(gain_db: float = BGM_GAIN_DB) -> str:
    """BGM 通道的滤镜链（不含 ducking，ducking 在 numpy 里做掉了）。"""
    return (
        "aformat=sample_fmts=fltp,pan=stereo\\|c0=c0\\|c1=c0,"
        f"highpass=f={HIGHPASS_HZ},{eq_filter()},"
        f"volume={10 ** (gain_db / 20):.6f}"
    )


def duck_depth_db_default() -> float:
    """旁白段的额外压低量。"""
    return DUCK_DEPTH_DB


def attribution_lines(entries: list[TrackEntry]) -> list[str]:
    """需要署名的曲子，给出署名串。"""
    return [entry.attribution_text.strip()
            for entry in entries if entry.attribution_required
            and entry.attribution_text.strip()]


def parse_bpm(text: str) -> float | None:
    """从「92 BPM」「92bpm」这类文本里取 BPM。"""
    match = re.search(r"(\d+(?:\.\d+)?)\s*bpm", text, re.IGNORECASE)
    return float(match.group(1)) if match else None
