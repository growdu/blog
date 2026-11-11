#!/usr/bin/env python3
"""实测旁白的音色特征，给「换稿重新定标」用。

《形象与音色规范》§2.1 的五项指标：

| 指标 | 怎么测 |
| --- | --- |
| 基频 F0 | 逐帧自相关求基频，取中位与 p5/p95 |
| F1 / F2 | LPC 求根，取共振峰频率 |
| 频谱重心 | FFT 功率加权平均 |
| 语速 | 字数 ÷ 时长 |
| 时长 | ffprobe |

**绝对值不可信，差值才可信**：本脚本的测量方法与当初定标时用的方法未必完全一致，
所以定标时只认「同一把尺子量出来的相对差」——参照稿与候选稿都用本脚本测，
再看差多少。规范 §2.2 的表就是这种用法。

已知的口径差异（不要拿本脚本的绝对值去对 §2.1 表里的数）：

| 指标 | 本脚本 | §2.1 记录 | 说明 |
| --- | --- | --- | --- |
| F0 中位 | 自相关 | 116.7 Hz | 本脚本量参照得 118.1 Hz，差 0.13 半音——可信 |
| 语速 | 字数 ÷ 时长 | 7.72 字/秒 | 完全一致——可信 |
| 频谱重心 | 帧均幅度加权 | 1222 Hz | 本脚本量参照得 1184 Hz——接近，定义不同 |
| F1 / F2 | LPC 求根 | 273 / 961 Hz | 定义不同，数值差得远，**只当参考** |

F1/F2 是声道长度决定的，同一个音色下不随 pitch / speed 变化，
所以选 speed×pitch 网格时它对排序没有影响——真正起作用的是语速与基频。

用法：
    python3 measure_voice.py --path 旁白.mp3 --chars 255
    python3 measure_voice.py --path 参照.mp3 --chars 226
    python3 measure_voice.py --path 候选.mp3 --chars 255 --ref 参照.mp3 --ref-chars 226
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy.linalg import solve_toeplitz

ANALYSIS_SR = 32000       # F0 与频谱重心用这个，保证和参照稿同带宽
FORMANT_SR = 16000       # 共振峰分析用这个（LPC 阶数可控）

F0_MIN = 60.0            # 男声下限
F0_MAX = 400.0
VOICED_RMS = 0.01        # 低于这个能量视为静音，不参与 F0 统计
F0_CONFIDENCE = 0.30     # 自相关峰 / r[0] 的下限，低于它算清音
LPC_ORDER = 16
FRAME_SEC = 0.040
HOP_SEC = 0.010
CENTROID_FRAME = 512     # 频谱重心的帧长（16 ms @ 32 kHz）
CENTROID_HOP = 256


@dataclass
class VoiceProfile:
    path: str
    duration_s: float
    chars: int
    speech_rate: float      # 字/秒
    f0_median: float
    f0_p5: float
    f0_p95: float
    f0_span: float
    f1: float
    f2: float
    centroid_hz: float
    f0_frames: int

    def as_dict(self) -> dict:
        return asdict(self)


def decode(path: str | Path, sample_rate: int) -> np.ndarray:
    """解成单声道 float32。"""
    cmd = [
        "ffmpeg", "-v", "error", "-i", str(path),
        "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "-",
    ]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype="<f4").astype(np.float64)


def duration_of(path: str | Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True).stdout.strip()
    return float(out)


def _frames(signal: np.ndarray, frame_len: int, hop: int) -> np.ndarray:
    if len(signal) < frame_len:
        return np.empty((0, frame_len))
    n = 1 + (len(signal) - frame_len) // hop
    strides = (signal.strides[0] * hop, signal.strides[0])
    return np.lib.stride_tricks.as_strided(
        signal, shape=(n, frame_len), strides=strides, writeable=False)


def measure_f0(signal: np.ndarray, sr: int) -> np.ndarray:
    """逐帧自相关求基频，返回有效帧的 F0 序列（Hz）。"""
    frame_len = int(FRAME_SEC * sr)
    hop = int(HOP_SEC * sr)
    lag_min = int(sr / F0_MAX)
    lag_max = int(sr / F0_MIN)
    window = np.hanning(frame_len)

    out: list[float] = []
    for frame in _frames(signal, frame_len, hop):
        x = (frame - frame.mean()) * window
        if np.sqrt(np.mean(x ** 2)) < VOICED_RMS:
            continue
        corr = np.correlate(x, x, mode="full")[frame_len - 1:]
        if corr[0] <= 0:
            continue
        peak = lag_min + int(np.argmax(corr[lag_min:lag_max]))
        if corr[peak] / corr[0] < F0_CONFIDENCE:
            continue
        out.append(sr / peak)
    return np.asarray(out)


def measure_formants(signal: np.ndarray, sr: int) -> tuple[float, float]:
    """LPC 求根，取中位 F1 / F2。"""
    frame_len = int(0.025 * sr)
    hop = int(0.010 * sr)
    order = LPC_ORDER
    window = np.hamming(frame_len)

    f1_list: list[float] = []
    f2_list: list[float] = []
    for frame in _frames(signal, frame_len, hop):
        x = frame - frame.mean()
        if np.sqrt(np.mean(x ** 2)) < VOICED_RMS:
            continue
        # 预加重：抵消声门波 -12 dB/oct 的倾斜
        x = np.append(x[0], x[1:] - 0.97 * x[:-1])
        x = x * window
        r = np.correlate(x, x, mode="full")[frame_len - 1:]
        if r[0] <= 0:
            continue
        try:
            a = solve_toeplitz(r[:order], -r[1:order + 1])
        except np.linalg.LinAlgError:
            continue
        if not np.all(np.isfinite(a)):
            continue
        roots = np.roots(np.concatenate(([1.0], a)))
        roots = roots[np.imag(roots) > 0]
        if roots.size == 0:
            continue
        freqs = np.angle(roots) * sr / (2 * np.pi)
        bandwidths = -0.5 * sr / np.pi * np.log(np.maximum(np.abs(roots), 1e-12))
        keep = (freqs > 90) & (freqs < sr / 2 - 100) & (bandwidths < 400)
        freqs = np.sort(freqs[keep])
        if freqs.size < 2:
            continue
        f1_list.append(float(freqs[0]))
        f2_list.append(float(freqs[1]))

    if not f1_list:
        return 0.0, 0.0
    return float(np.median(f1_list)), float(np.median(f2_list))


def measure_centroid(signal: np.ndarray, sr: int) -> float:
    """频谱重心（Hz）：逐帧幅度谱求平均，再按幅度加权求均值。

    幅度加权而不是功率加权：语音的能量集中在低频，功率加权会把重心压到
    几百 Hz，跟「听起来的明亮度」对不上。逐帧平均是因为整段 FFT 会被
    句子间的停顿稀释。
    """
    if len(signal) < CENTROID_FRAME:
        return 0.0
    acc = None
    count = 0
    window = np.hanning(CENTROID_FRAME)
    for frame in _frames(signal, CENTROID_FRAME, CENTROID_HOP):
        spectrum = np.abs(np.fft.rfft(frame * window))
        acc = spectrum if acc is None else acc + spectrum
        count += 1
    if acc is None or count == 0:
        return 0.0
    mean_spectrum = acc / count
    freqs = np.fft.rfftfreq(CENTROID_FRAME, 1.0 / sr)
    total = mean_spectrum.sum()
    if total <= 0:
        return 0.0
    return float((freqs * mean_spectrum).sum() / total)


def measure(path: str | Path, chars: int) -> VoiceProfile:
    path = Path(path)
    dur = duration_of(path)
    signal = decode(path, ANALYSIS_SR)
    f0 = measure_f0(signal, ANALYSIS_SR)
    centroid = measure_centroid(signal, ANALYSIS_SR)

    low = decode(path, FORMANT_SR)
    f1, f2 = measure_formants(low, FORMANT_SR)

    if f0.size:
        f0_med = float(np.median(f0))
        f0_p5 = float(np.percentile(f0, 5))
        f0_p95 = float(np.percentile(f0, 95))
    else:
        f0_med = f0_p5 = f0_p95 = 0.0

    return VoiceProfile(
        path=str(path),
        duration_s=dur,
        chars=chars,
        speech_rate=chars / dur if dur else 0.0,
        f0_median=f0_med,
        f0_p5=f0_p5,
        f0_p95=f0_p95,
        f0_span=f0_p95 - f0_p5,
        f1=f1,
        f2=f2,
        centroid_hz=centroid,
        f0_frames=int(f0.size),
    )


def semitone_gap(a: float, b: float) -> float:
    """两个基频相差多少半音。"""
    if a <= 0 or b <= 0:
        return 0.0
    return float(12.0 * np.log2(a / b))


def score(candidate: VoiceProfile, reference: VoiceProfile) -> tuple[float, dict]:
    """按规范 §2.1 的排序公式打分，越小越接近参照。"""
    d_f0 = semitone_gap(candidate.f0_median, reference.f0_median)
    d_f1 = candidate.f1 - reference.f1
    d_f2 = candidate.f2 - reference.f2
    d_centroid = (candidate.centroid_hz - reference.centroid_hz) / reference.centroid_hz * 100
    d_rate = (candidate.speech_rate - reference.speech_rate) / reference.speech_rate * 100

    total = (abs(d_f0) * 3 + abs(d_f1) / 30 + abs(d_f2) / 120
             + abs(d_centroid) / 5 + abs(d_rate) / 4)
    return total, {
        "d_f0_semitone": d_f0,
        "d_f1_hz": d_f1,
        "d_f2_hz": d_f2,
        "d_centroid_pct": d_centroid,
        "d_rate_pct": d_rate,
    }


def show(p: VoiceProfile) -> None:
    print(f"{p.path}")
    print(f"  时长      {p.duration_s:.2f} s")
    print(f"  语速      {p.speech_rate:.2f} 字/秒（{p.chars} 字）")
    print(f"  F0 中位   {p.f0_median:.1f} Hz"
          f"（p5 {p.f0_p5:.0f} / p95 {p.f0_p95:.0f}，跨度 {p.f0_span:.0f} Hz，"
          f"{p.f0_frames} 帧）")
    print(f"  F1 / F2   {p.f1:.0f} Hz / {p.f2:.0f} Hz")
    print(f"  频谱重心  {p.centroid_hz:.0f} Hz")


def main() -> int:
    parser = argparse.ArgumentParser(description="实测旁白音色特征")
    parser.add_argument("--path", required=True, help="待测音频")
    parser.add_argument("--chars", type=int, required=True, help="对应的口播稿字数")
    parser.add_argument("--ref", help="参照音频（给了就算差值与排序分）")
    parser.add_argument("--ref-chars", type=int, help="参照稿字数")
    parser.add_argument("--json", action="store_true", help="只输出 JSON")
    args = parser.parse_args()

    profile = measure(args.path, args.chars)
    if args.ref:
        reference = measure(args.ref, args.ref_chars or args.chars)
        total, deltas = score(profile, reference)
        if args.json:
            print(json.dumps({"candidate": profile.as_dict(),
                              "reference": reference.as_dict(),
                              "deltas": deltas, "score": total},
                             ensure_ascii=False, indent=2))
            return 0
        show(reference)
        print()
        show(profile)
        print()
        print("差值：")
        print(f"  ΔF0        {deltas['d_f0_semitone']:+.2f} 半音")
        print(f"  ΔF1        {deltas['d_f1_hz']:+.0f} Hz")
        print(f"  ΔF2        {deltas['d_f2_hz']:+.0f} Hz")
        print(f"  Δ重心      {deltas['d_centroid_pct']:+.1f} %")
        print(f"  Δ语速      {deltas['d_rate_pct']:+.1f} %")
        print(f"  排序分     {total:.2f}（越小越接近参照）")
        return 0

    if args.json:
        print(json.dumps(profile.as_dict(), ensure_ascii=False, indent=2))
    else:
        show(profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
