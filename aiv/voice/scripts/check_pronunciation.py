#!/usr/bin/env python3
"""量一个词的首字声母——判断 TTS 把它念成了 háng 还是 xíng。

**为什么需要它**：ASR 不可信。同一段音频，ASR 在孤立语境里把「行锁」写成 `xing2 suo3`，
在整句语境里又写成 `hang2 suo3`——它按上下文归一化，所以「ASR 念成什么」不能当判据。
声学特征不会骗人：`[ɕ]`（西、xíng）的摩擦噪声集中在 4–6 kHz，`[x]`（好、háng）集中在 2–3 kHz。

**怎么量**（`pronunciation.py` 那张表就是这么来的）：
1. 前置静音结束处 = 词首；
2. 首字的声母突发**紧贴词首**（实测 +13 ~ +25 ms）；
   后一个字（如「锁」的 /s/）会晚 90 ms 以上才出现（实测 +126 ~ +164 ms）。
   所以「词首 100 ms 内有没有强摩擦突发」就能分开两种声母；
3. 有突发 → [ɕ]（xíng）；没有 → [x]（háng，这个音色里 [x] 非常弱，比值 ≈ 0.1）。

用法：
    # 比两个词（会合成探针，需要联网）
    python3 check_pronunciation.py --word 行锁 --samples 5
    python3 check_pronunciation.py --word 航锁 --samples 5

    # 量已有音频里的一段（离线）
    python3 check_pronunciation.py --audio 旁白.mp3 --from 13.0 --to 14.5
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ANALYSIS_SR = 16000
FRAME = 400          # 25 ms
HOP = 160            # 10 ms

BAND_HI = (2500, 8000)   # 摩擦噪声主要能量区
BAND_LO = (300, 900)     # 浊音/低频能量区

GAMMA_RATIO_MIN = 40.0       # 强摩擦突发的摩擦比门槛
GAMMA_CENTROID_MIN = 3500.0  # [ɕ] 的谱心门槛（Hz）
ONSET_WINDOW = 0.10          # 首字声母突发的判定窗口（秒）
SEARCH_WINDOW = 0.60         # 往前找第一个突发的范围（秒）

PROBE_TAIL = "PostgreSQL 在 MVCC 之上加了，一共 4 种模式。"


@dataclass
class Burst:
    t: float        # 中心时刻（秒）
    ratio: float    # 高频能量 / 低频能量
    centroid: float # 摩擦噪声的频谱重心（Hz）

    @property
    def is_gamma(self) -> bool:
        return self.ratio >= GAMMA_RATIO_MIN and self.centroid >= GAMMA_CENTROID_MIN


def _load(path: str | Path) -> np.ndarray:
    wav = str(path) + ".analysis.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path), "-ar", str(ANALYSIS_SR),
                    "-ac", "1", "-f", "wav", wav], check=True)
    try:
        with wave.open(wav, "rb") as w:
            n = w.getnframes()
            return np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float64) / 32768.0
    finally:
        Path(wav).unlink(missing_ok=True)


def _features(data: np.ndarray):
    winf = np.hanning(FRAME)
    nfr = 1 + max(0, (len(data) - FRAME) // HOP)
    S = np.zeros((nfr, FRAME // 2 + 1))
    for i in range(nfr):
        seg = data[i * HOP:i * HOP + FRAME]
        if len(seg) < FRAME:
            seg = np.pad(seg, (0, FRAME - len(seg)))
        S[i] = np.abs(np.fft.rfft(seg * winf)) ** 2
    freqs = np.fft.rfftfreq(FRAME, 1 / ANALYSIS_SR)
    hi = (freqs >= BAND_HI[0]) & (freqs <= BAND_HI[1])
    lo = (freqs >= BAND_LO[0]) & (freqs <= BAND_LO[1])
    ratio = S[:, hi].sum(axis=1) / (S[:, lo].sum(axis=1) + 1e-12)
    cent = (S[:, hi] * freqs[hi]).sum(axis=1) / (S[:, hi].sum(axis=1) + 1e-12)
    return ratio, cent


def leading_silence(path: str | Path) -> float:
    """前置静音的结束时刻 = 第一个音开始的位置。"""
    out = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-af", "silencedetect=noise=-28dB:d=0.05",
         "-f", "null", "-"], capture_output=True, text=True).stderr
    for line in out.splitlines():
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m:
            return float(m.group(1))
    return 0.0


def bursts(path: str | Path, t0: float = 0.0, t1: float | None = None) -> list[Burst]:
    """列出区间里的强摩擦噪声突发。"""
    ratio, cent = _features(_load(path))
    i0 = max(0, int(t0 * ANALYSIS_SR / HOP))
    i1 = len(ratio) if t1 is None else min(len(ratio), int(t1 * ANALYSIS_SR / HOP))
    out: list[Burst] = []
    i = i0
    while i < i1:
        if ratio[i] >= GAMMA_RATIO_MIN:
            j = i
            while j < i1 and ratio[j] >= GAMMA_RATIO_MIN:
                j += 1
            out.append(Burst(t=(i + j) / 2 * HOP / ANALYSIS_SR,
                             ratio=float(ratio[i:j].max()),
                             centroid=float(cent[i:j].mean())))
            i = j
        else:
            i += 1
    return out


def onset_burst(path: str | Path, start: float | None = None,
                window: float = ONSET_WINDOW) -> Burst | None:
    """首字的声母突发。

    只认落在词首 `window` 秒内的突发——再晚就是后一个字了。
    `start` 省略时用前置静音的结束时刻。
    """
    t0 = leading_silence(path) if start is None else start
    for b in bursts(path, t0, t0 + window):
        return b
    return None


def verdict(path: str | Path, start: float | None = None,
            window: float = ONSET_WINDOW) -> str:
    b = onset_burst(path, start, window)
    if b is None:
        return "[x] → háng（词首没有强摩擦突发）"
    return ("[ɕ] → xíng" if b.is_gamma else "[x] → háng")


def _synthesize(text: str, out: Path) -> None:
    """合成探针（需要 mcode-tools）。"""
    args = {
        "text": text,
        "voice_id": "Chinese (Mandarin)_Radio_Host",
        "pitch": -1,
        "speed": 1.33,
        "emotion": "neutral",
        "output_file": out.name,
    }
    args_file = out.with_suffix(".args.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    args_file.write_text(json.dumps(args, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(["mcode-tools", "connector", "call",
                           "connector__matrix__synthesize_speech", "--args-file", str(args_file)],
                          capture_output=True, text=True)
    args_file.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(f"合成失败：{proc.stderr[-400:]}")
    res = json.loads(proc.stdout[proc.stdout.index("{"):])
    if res.get("code") != 0:
        raise RuntimeError(f"合成返回错误：{res}")
    raw = subprocess.run(["mcode-tools", "get_asset_url", res["node_id"]],
                         capture_output=True, text=True).stdout
    url = json.loads(raw[raw.index("{"):])["download_url"]
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["curl", "-sfL", "-o", str(out), url], check=True)


def probe_word(word: str, samples: int = 5, workdir: Path | None = None) -> dict:
    """合成 N 次探针，统计首字声母。

    这个 TTS 每次合成都带随机性，所以必须多样本：
    实测「行锁」5/5 是 xíng、「航锁」5/5 是 háng。
    """
    workdir = workdir or Path("/tmp/pron-probe")
    offsets, verdicts = [], []
    for k in range(samples):
        p = workdir / f"{word}_{k}.mp3"
        if not p.exists():
            _synthesize(f"{word}。{PROBE_TAIL}", p)
        t0 = leading_silence(p)
        found = bursts(p, t0, t0 + SEARCH_WINDOW)
        first = found[0] if found else None
        offsets.append(None if first is None else round(first.t - t0, 3))
        v = verdict(p)
        verdicts.append(v)
    gamma = sum(1 for v in verdicts if v.startswith("[ɕ]"))
    return {
        "word": word,
        "samples": samples,
        "gamma": gamma,
        "offsets": offsets,
        "verdict": "可靠 xíng" if gamma == samples else ("可靠 háng" if gamma == 0 else "不稳定"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="量一个词的首字声母（háng / xíng）")
    ap.add_argument("--word", help="要量的词（会合成探针，需要联网）")
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--audio", help="已有音频路径（离线）")
    ap.add_argument("--from", dest="t0", type=float, help="起点（秒）")
    ap.add_argument("--to", dest="t1", type=float, help="终点（秒）")
    ap.add_argument("--calibrate", action="store_true", help="打印标定")
    args = ap.parse_args()

    if args.calibrate:
        # 判据的两端：原词念 xíng，替身念 háng。两边都必须稳定。
        expect = {"行锁": "可靠 xíng", "航锁": "可靠 háng"}
        bad = []
        for w, want in expect.items():
            r = probe_word(w, samples=3)
            print(f"  {w:6} {r['verdict']}  首突发偏移 {r['offsets']}")
            if r["verdict"] != want:
                bad.append(f"{w} 实测「{r['verdict']}」，期望「{want}」")
        if bad:
            print("读音验收不通过：" + "；".join(bad), file=sys.stderr)
            return 1
        print("  OK 读音验收通过（原词念 xíng、替身念 háng）")
        return 0

    if args.word:
        print(json.dumps(probe_word(args.word, samples=args.samples),
                         ensure_ascii=False, indent=2))
        return 0

    if args.audio:
        t0 = args.t0 if args.t0 is not None else 0.0
        t1 = args.t1
        print(f"区间 {t0}~{t1 if t1 is not None else '末尾'} s")
        for b in bursts(args.audio, t0, t1):
            tag = "[ɕ]" if b.is_gamma else "   "
            print(f"  {tag} t={b.t:6.3f}s  摩擦比={b.ratio:9.1f}  谱心={b.centroid:6.0f} Hz")
        if args.t0 is not None:
            print(f"  词首判定：{verdict(args.audio, args.t0)}")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
