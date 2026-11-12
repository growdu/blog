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
import tempfile
import wave
from dataclasses import asdict, dataclass, field
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
    # 取用段落的电平（规范 §5.1）：推导把整曲平均当成取用段落的电平
    "bgm.take-level",
    # 成片级（混完之后）的判据，见规范 §5.7
    "bgm.mix-duck-depth",
    "bgm.mix-voice-to-bgm",
    "bgm.mix-true-peak",
    "bgm.mix-voice-gain",
    # 系列片头片尾的配乐窗口（见规范 §6 末条、§7）
    "bgm.brand-loop",
    "bgm.brand-track",
    "bgm.brand-window",
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


def measure_loudness(path: str | Path,
                    start_seconds: float | None = None,
                    duration_s: float | None = None) -> tuple[float, float]:
    """量整体响度（LUFS）与真峰值（dBTP）。

    给 `start_seconds` / `duration_s` 就只量那一段。
    """
    cmd = ["ffmpeg", "-hide_banner", "-nostats"]
    if start_seconds is not None:
        cmd += ["-ss", f"{start_seconds:.3f}"]
    cmd += ["-i", str(path)]
    if duration_s is not None:
        cmd += ["-t", f"{duration_s:.3f}"]
    cmd += ["-af", "ebur128=peak=true", "-f", "null", "-"]
    stderr = _run(cmd).stderr
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
    循环点找不到就等于没有），并且**取用段落**（前 required_duration_s 秒）
    的电平要过 `bgm.take-level`。
    """
    findings = check_profile(measure(path), required_duration_s)
    if required_duration_s:
        findings += check_take_level(path, required_duration_s)
    return findings


# ---------------------------------------------------------------- 取用段落

# 取用段落比整曲响多少算「推导失效」。
#
# 规范 §5.1 的电平推导把**整曲平均**当成取用段落的电平：
# 「母带归一化到 -20 LUFS → compose 基础增益 -15 dB → -35 LUFS」。
# 实际只用其中一段，这一段不一定等于整曲的平均。
#
# 取用段落更安静 → 推导偏保守（实际电平差更大，更安全）；
# 取用段落更响   → 推导偏乐观（实际电平差更小，可能压过旁白）。
# 所以上限取 0 dB：**取用段落不得比整曲响**，否则必须重新推导。
#
# 实测（2026-11-12）：
#   series-bed-01 前 33.156 s   -22.90 LUFS vs 整曲 -20.00 → -2.90 dB ✓
#   series-motif-01 5.900~11.566 s  -24.70 LUFS vs 整曲 -20.00 → -4.70 dB ✓
#   （旧口径的片头窗口 115.15 s 起   +1.20 dB ✗——顺带说明旧窗口选得也不对）
TAKE_LEVEL_MAX_DB = 0.0


def measure_take_level(path: str | Path, take_seconds: float,
                        start_seconds: float = 0.0) -> tuple[float, float]:
    """量「整曲」与「取用段落」的响度（LUFS），返回 (整曲, 取用段落)。

    取用段落就是实际会用到的那一截：
    正文铺底取母带的前 N 秒（`duck_bgm` 就是这么取的），
    品牌片头片尾取那两个紧挨着的窗口。
    """
    whole, _ = measure_loudness(path)
    take, _ = measure_loudness(path, start_seconds, take_seconds)
    return whole, take


def check_take_level(path: str | Path, take_seconds: float,
                     start_seconds: float = 0.0,
                     target: str = "") -> list[Finding]:
    """取用段落相对整曲的响度差（规范 §5.1）。"""
    whole, take = measure_take_level(path, take_seconds, start_seconds)
    diff = take - whole
    if diff > TAKE_LEVEL_MAX_DB:
        return [Finding(
            "bgm.take-level", ERROR,
            f"取用段落比整曲响 {diff:+.2f} dB"
            f"（整曲 {whole:.2f} LUFS / 取用 {take:.2f} LUFS）——"
            f"规范 §5.1 的推导把整曲平均当成取用段落的电平，"
            f"这里前提不成立，要按实测值重新推导", target)]
    return [Finding(
        "bgm.take-level", WARNING,
        f"取用段落比整曲安静 {-diff:.2f} dB"
        f"（整曲 {whole:.2f} LUFS / 取用 {take:.2f} LUFS）——"
        f"推导值偏保守，实际电平差比设计目标更宽", target)]


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
    """逐样本的增益因子（1.0 = 不压低，越小压得越狠）。

    返回长度**必须**与旁白逐样本相等：混音时增益曲线要盖在 BGM 上，
    两边长度差一个样本都广播不了。包络按 10 ms 窗算，末尾不足一窗的
    那截按最后一帧的值补齐（零阶保持），否则曲线会比旁白短最多 479 个样本。
    """
    activity = speech_activity(narration, sample_rate)
    if activity.size == 0:
        # 连一窗都不到，判断不出有人在说话：整段不压低。
        return np.ones(narration.size)
    window = max(1, int(sample_rate * ENVELOPE_WINDOW_MS / 1000))
    curve = np.repeat(activity, window)
    if curve.size < narration.size:
        curve = np.concatenate(
            [curve, np.full(narration.size - curve.size, curve[-1])])
    else:
        curve = curve[:narration.size]
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


# ---------------------------------------------------------------- 成片级判据
#
# 前面那些规则管的是「曲子本身」和「台账」。这里管的是**混完之后**：
# 整期片子做完了，旁白清不清楚、BGM 与旁白差多少、削没削顶——
# 这些以前只能靠耳朵（规范 §8 的待办）。

# 稳态 duck 深度的容差。设定值就是 DUCK_DEPTH_DB，判据与 §5.2 同源。
MIX_DUCK_DEPTH_TOLERANCE_DB = 0.5
# 旁白活跃段里，旁白至少要比 BGM 高多少。
# §5.1 的设计目标是 18.3 dB（LUFS 口径）；这里按同窗口径实测，
# 取同一个数当保守下界：实测口径下也不许比设计目标更挤。
MIX_VOICE_TO_BGM_MIN_DB = 18.3
# 成片真峰值上限：留 1 dB 余量，不许削顶。
MIX_TRUE_PEAK_MAX_DB = -1.0
# 旁白在成片里的增益偏差上限：混音不该动旁白的音量。
MIX_VOICE_GAIN_TOLERANCE_DB = 0.5
# 算「稳态」时，包络要爬到多高才算说完了。
# 上升沿是单极点（120 ms 时间常数），从 0 爬到 0.99 要 560 ms；
# 爬到 0.99 之后增益与设定值的偏差不超过 7×0.01 = 0.07 dB，
# 远小于 ±0.5 dB 的判据容差。
SATURATED_ENVELOPE = 0.99


@dataclass(frozen=True)
class MixReport:
    """成片混音的实测结果。"""

    duck_depth_db: float
    voice_to_bgm_db: float
    voice_rms_db: float
    bgm_rms_db: float
    true_peak_db: float
    voice_gain_db: float
    active_ratio: float
    body_start_s: float
    body_end_s: float

    def summary(self) -> str:
        return (
            f"稳态 duck 深度   {self.duck_depth_db:6.2f} dB\n"
            f"旁白活跃段旁白   {self.voice_rms_db:6.2f} dBFS\n"
            f"旁白活跃段 BGM   {self.bgm_rms_db:6.2f} dBFS\n"
            f"电平差           {self.voice_to_bgm_db:6.2f} dB\n"
            f"旁白增益偏差     {self.voice_gain_db:+6.2f} dB\n"
            f"成片真峰值       {self.true_peak_db:6.2f} dBTP\n"
            f"正文区间         {self.body_start_s:.3f} ~ {self.body_end_s:.3f} s\n"
            f"旁白活跃帧占比   {self.active_ratio * 100:6.1f} %"
        )


def _decode_stereo(path: str | Path, sample_rate: int = 48000) -> np.ndarray:
    """解码成立体声 float64 数组（形状 n×2）。"""
    raw = _run([
        "ffmpeg", "-v", "error", "-i", str(path),
        "-f", "f32le", "-ac", "2", "-ar", str(sample_rate), "-",
    ], text=False).stdout
    frames = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    if frames.size % 2:
        frames = frames[:-1]
    return frames.reshape(-1, 2)


def _to_mono(stereo: np.ndarray) -> np.ndarray:
    """立体声按等权平均下混成单声道。

    **不要用 ffmpeg 的 `-ac 1`**：它的下混系数是每声道 0.7071，
    对左右同相的信号整体高 3 dB（实测 L=R=0.5 解回来是 0.707）。
    这里要的是「和成片里那一路一样」的等权平均，否则量出来的差值会偏 3 dB。
    """
    if stereo.size == 0:
        return np.zeros(0)
    return (stereo[:, 0] + stereo[:, 1]) / 2


def _rms_db(samples: np.ndarray) -> float:
    """RMS 电平（dBFS）。"""
    if samples.size == 0:
        return -120.0
    value = float(np.sqrt(np.mean(samples ** 2)))
    return float(20 * np.log10(max(value, 1e-12)))


def saturated_mask(narration: np.ndarray, sample_rate: int = 48000) -> np.ndarray:
    """旁白「正在说话」的逐样本掩码（包络已到平台期的那些样本）。

    只取平台段：词间空隙处包络在回落，增益本来就在回升，
    拿它一起算会把压深算浅。上升沿有 120 ms 的时间常数，
    爬到 SATURATED_ENVELOPE 还要 560 ms，这段也不算。
    """
    activity = speech_activity(narration, sample_rate)
    window = max(1, int(sample_rate * ENVELOPE_WINDOW_MS / 1000))
    frames = np.repeat(activity, window)
    if frames.size == 0:
        return np.zeros(narration.size, dtype=bool)
    if frames.size < narration.size:
        frames = np.concatenate(
            [frames, np.full(narration.size - frames.size, frames[-1])])
    else:
        frames = frames[:narration.size]
    return frames >= SATURATED_ENVELOPE


def measure_duck_depth(bgm_path: str | Path, narration_path: str | Path,
                       duration_s: float | None = None) -> float:
    """量稳态 duck 深度（dB，正数）。

    跑一遍 duck，把母带与 duck 后的 BGM 在旁白**饱和帧**上比 RMS：
    饱和帧里包络恒为 1，增益恒为 10^(depth/20)，量出来的就是设定深度。
    """
    with tempfile.TemporaryDirectory() as tmp:
        ducked_path = Path(tmp) / "ducked.wav"
        duck_bgm(bgm_path, narration_path, ducked_path, duration_s=duration_s)
        master = decode_mono(bgm_path)
        ducked = decode_mono(ducked_path)
    narration = decode_mono(narration_path)
    mask = saturated_mask(narration)
    length = min(master.size, ducked.size, mask.size)
    mask = mask[:length]
    if not mask.any():
        raise ValueError("旁白里找不到持续说话段，量不出 duck 深度")
    return _rms_db(master[:length][mask]) - _rms_db(ducked[:length][mask])


def measure_mix(video: str | Path, narration: str | Path, music: str | Path,
                body_start: float, body_end: float,
                sample_rate: int = 48000) -> MixReport:
    """量成片的混音关系。

    做法：正文区间的混音 = 旁白 + BGM（`amix` 的 `normalize=0` 是纯求和），
    于是把旁白按正文起点摆回成片的时间轴、从成片里减掉，剩下的就是 BGM。
    两边用同一批样本、同一套统计量（RMS dBFS）比，差值就是「旁白高 BGM 多少」。
    """
    stereo = _decode_stereo(video, sample_rate)
    mix = _to_mono(stereo)
    voice = decode_mono(narration, sample_rate)
    delay = int(round(body_start * sample_rate))
    body0 = int(round(body_start * sample_rate))
    body1 = min(mix.size, int(round(body_end * sample_rate)))
    if body1 <= body0:
        raise ValueError("正文区间是空的，算不了混音关系")

    voice_at = np.zeros(mix.size)
    end = min(mix.size, delay + voice.size)
    voice_at[delay:end] = voice[:end - delay]
    bgm_only = mix - voice_at

    active = np.zeros(mix.size, dtype=bool)
    core = saturated_mask(voice, sample_rate)
    active[delay:end] = core[:end - delay]
    index = np.arange(mix.size)
    in_body = (index >= body0) & (index < body1)
    active = active & in_body
    if not active.any():
        raise ValueError("成片的正文区间里找不到旁白活跃段")

    voice_rms = _rms_db(voice_at[active])
    bgm_rms = _rms_db(bgm_only[active])

    segment_mix = mix[body0:body1]
    segment_voice = voice_at[body0:body1]
    denominator = float(segment_voice @ segment_voice)
    gain = float(segment_mix @ segment_voice / denominator) if denominator > 0 else 0.0

    _, true_peak = measure_loudness(video)

    return MixReport(
        duck_depth_db=measure_duck_depth(
            music, narration, duration_s=body_end - body_start),
        voice_to_bgm_db=voice_rms - bgm_rms,
        voice_rms_db=voice_rms,
        bgm_rms_db=bgm_rms,
        true_peak_db=true_peak,
        voice_gain_db=20 * math.log10(gain) if gain > 0 else -120.0,
        active_ratio=float(active.sum()) / float(int(in_body.sum())),
        body_start_s=body_start,
        body_end_s=body_end,
    )


def check_mix(report: MixReport) -> list[Finding]:
    """把实测结果变成判据。"""
    findings: list[Finding] = []
    depth = report.duck_depth_db
    if abs(depth - abs(DUCK_DEPTH_DB)) > MIX_DUCK_DEPTH_TOLERANCE_DB:
        findings.append(Finding(
            "bgm.mix-duck-depth", ERROR,
            f"稳态 duck 深度实测 {depth:.2f} dB，应为 "
            f"{abs(DUCK_DEPTH_DB):.1f} ± {MIX_DUCK_DEPTH_TOLERANCE_DB} dB",
        ))
    gap = report.voice_to_bgm_db
    if gap < MIX_VOICE_TO_BGM_MIN_DB:
        findings.append(Finding(
            "bgm.mix-voice-to-bgm", ERROR,
            f"旁白活跃段旁白只比 BGM 高 {gap:.2f} dB，"
            f"至少要 {MIX_VOICE_TO_BGM_MIN_DB} dB",
        ))
    if report.true_peak_db > MIX_TRUE_PEAK_MAX_DB:
        findings.append(Finding(
            "bgm.mix-true-peak", ERROR,
            f"成片真峰值 {report.true_peak_db:.2f} dBTP，"
            f"超过上限 {MIX_TRUE_PEAK_MAX_DB} dBTP",
        ))
    if abs(report.voice_gain_db) > MIX_VOICE_GAIN_TOLERANCE_DB:
        findings.append(Finding(
            "bgm.mix-voice-gain", ERROR,
            f"旁白在成片里的增益偏离 {report.voice_gain_db:+.2f} dB，"
            f"应在 ±{MIX_VOICE_GAIN_TOLERANCE_DB} dB 内",
        ))
    return findings


# ---------------------------------------------------------------- 品牌片窗口

# 系列片头片尾的配乐窗口。规范 §6 末条：每期开头与结尾的 motif 片段要
# **首尾相接（片尾接回片头）**，形成闭环。
#
# 口径（2026-11-12 定）：片头取 [s, s+D)，片尾取 [s-D, s)——
# 两段拼起来是同一段连续音乐，片尾结束时正好落在片头的起音点上。
#
# 早先的做法是片头片尾**各按能量评分各挑各的**窗口，intro 与 outro
# 互不相干：本期 intro 在 115.15 s、outro 在 31.80 s，实测两段的
# 相关系数只有 0.009，听上去基本是两首不同的音乐——这就是「结尾和片头
# 对不上」的原因。

BRAND_WINDOW_SECONDS = 2.833      # 与 render_brand.py 的帧数一致
BRAND_WINDOWS_PATH = AIV_ROOT / "brand" / "brand_windows.json"

# 起音比 = 窗口开头 50 ms 的能量 ÷ 紧邻之前 200 ms 的能量。
# 比值大 = 那里有个清楚的起音，片头才「起」得起来。
BRAND_ONSET_RATIO_MIN = 4.0
# 两段各自的能量下限（别挑到曲子头尾的静音）
BRAND_MIN_RMS = 0.02
# 峰值上限（削顶的窗口直接跳过）
BRAND_PEAK_MAX = 0.98


@dataclass(frozen=True)
class BrandWindows:
    """系列片头片尾的配乐窗口。

    两段取自同一条 motif，且首尾相接：`outro_start + duration == intro_start`。
    """

    duration_s: float
    intro_start_s: float
    outro_start_s: float
    track_id: str = ""
    track_sha256: str = ""
    onset_ratio: float = 0.0
    intro_rms: float = 0.0
    outro_rms: float = 0.0

    @property
    def intro_end_s(self) -> float:
        return self.intro_start_s + self.duration_s

    @property
    def outro_end_s(self) -> float:
        return self.outro_start_s + self.duration_s

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "BrandWindows":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        missing = {"duration_s", "intro_start_s", "outro_start_s"} - known
        if missing:
            raise ValueError(f"品牌片窗口缺字段：{sorted(missing)}")
        return cls(**{k: v for k, v in raw.items() if k in known})


def _rms(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples ** 2)))


def pick_brand_windows(music_path: str | Path,
                       duration_s: float = BRAND_WINDOW_SECONDS,
                       track_id: str = "",
                       track_sha256: str = "") -> BrandWindows:
    """挑片头与片尾的配乐窗口，两段首尾相接。

    片头 = [s, s+D)，片尾 = [s-D, s)。候选点 s 要同时满足：

    - 起音明显（开头 50 ms 比之前 200 ms 明显更响）
    - 两段的能量都不低（不能挑到静音）
    - 两段都不削顶

    评分用起音比：起音越明显，片头越「起」得住。
    """
    samples = _to_mono(_decode_stereo(music_path))
    sr = 48000
    win = int(duration_s * sr)
    step = int(0.05 * sr)
    head_n = int(0.05 * sr)
    pre_n = int(0.20 * sr)

    best: tuple | None = None
    for i in range(win, samples.size - win, step):
        pre = samples[i - win:i]
        post = samples[i:i + win]
        if float(np.abs(pre).max()) > BRAND_PEAK_MAX:
            continue
        if float(np.abs(post).max()) > BRAND_PEAK_MAX:
            continue
        r_pre = _rms(pre)
        r_post = _rms(post)
        if r_pre < BRAND_MIN_RMS or r_post < BRAND_MIN_RMS:
            continue
        onset = _rms(post[:head_n]) / (_rms(samples[i - pre_n:i]) + 1e-9)
        if onset < BRAND_ONSET_RATIO_MIN:
            continue
        if best is None or onset > best[0]:
            best = (onset, i / sr, r_pre, r_post)

    if best is None:
        raise ValueError(
            f"{Path(music_path).name} 里找不到合格的起音点"
            f"（起音比 ≥ {BRAND_ONSET_RATIO_MIN}、两段能量 ≥ {BRAND_MIN_RMS}、"
            f"峰值 ≤ {BRAND_PEAK_MAX}）"
        )
    onset, start, r_pre, r_post = best
    return BrandWindows(
        duration_s=duration_s,
        intro_start_s=round(start, 3),
        outro_start_s=round(start - duration_s, 3),
        track_id=track_id,
        track_sha256=track_sha256,
        onset_ratio=round(onset, 3),
        intro_rms=round(r_post, 6),
        outro_rms=round(r_pre, 6),
    )


def save_brand_windows(windows: BrandWindows,
                       path: str | Path | None = None) -> Path:
    """把选定的窗口写下来（入库：这是决策，不是产物）。"""
    target = Path(path) if path else BRAND_WINDOWS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "rule": "片尾接回片头：outro_start + duration == intro_start",
        **windows.as_dict(),
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target


def load_brand_windows(path: str | Path | None = None) -> BrandWindows:
    target = Path(path) if path else BRAND_WINDOWS_PATH
    if not target.is_file():
        raise FileNotFoundError(f"品牌片窗口文件不存在：{target}")
    return BrandWindows.from_dict(
        json.loads(target.read_text(encoding="utf-8"))
    )


def check_brand_windows(windows: BrandWindows,
                        music_path: str | Path | None = None) -> list[Finding]:
    """品牌片窗口是否满足规范 §6 末条。"""
    findings: list[Finding] = []

    def add(rule_id: str, level: str, message: str) -> None:
        findings.append(Finding(rule_id, level, message, windows.track_id))

    # ---- 首尾相接：片尾的结束点必须正好落在片头的起点
    gap = abs(windows.outro_end_s - windows.intro_start_s)
    if gap > 0.01:
        add("bgm.brand-loop", ERROR,
            f"片尾结束在 {windows.outro_end_s:.3f}s，片头起于 "
            f"{windows.intro_start_s:.3f}s，两者没有相接（差 {gap:.3f}s）——"
            f"规范 §6 要求「片尾接回片头」形成闭环")

    # ---- 两段必须取自同一条登记过的 motif
    if not windows.track_id:
        add("bgm.brand-track", ERROR, "窗口没记 motif 的 id")
    if music_path is not None:
        local = Path(music_path)
        if not local.is_file():
            add("bgm.brand-track", ERROR, f"配乐文件不存在：{local}")
        elif windows.track_sha256 and sha256_of(local) != windows.track_sha256:
            add("bgm.brand-track", ERROR,
                f"配乐指纹与窗口记录的不一致（{windows.track_sha256[:12]}…）——"
                f"换过曲子就要重挑窗口")

    if windows.onset_ratio and windows.onset_ratio < BRAND_ONSET_RATIO_MIN:
        add("bgm.brand-window", WARNING,
            f"片头起音比只有 {windows.onset_ratio:.2f}，"
            f"低于 {BRAND_ONSET_RATIO_MIN}——开场可能起不来")
    if windows.intro_rms and windows.intro_rms < BRAND_MIN_RMS:
        add("bgm.brand-window", ERROR,
            f"片头窗口能量只有 {windows.intro_rms:.4f}，低于 {BRAND_MIN_RMS}")
    if windows.outro_rms and windows.outro_rms < BRAND_MIN_RMS:
        add("bgm.brand-window", ERROR,
            f"片尾窗口能量只有 {windows.outro_rms:.4f}，低于 {BRAND_MIN_RMS}")

    # ---- 取用段落相对整曲的电平（规范 §5.1）
    # 品牌片的取用段落是「片尾起点 → 片头终点」这一整截
    # （两段在原曲里紧挨着，中间不断）。
    if music_path is not None and Path(music_path).is_file():
        span = windows.intro_end_s - windows.outro_start_s
        findings += check_take_level(music_path, span, windows.outro_start_s,
                                     windows.track_id)
    return findings
