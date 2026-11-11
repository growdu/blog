#!/usr/bin/env python3
"""为 Growdu 片头/片尾合成成品音轨（旁白 + 配乐）。

MiniMax 生成的配乐是完整曲目（60~75 秒），片头片尾只要 3 秒，
所以这里从曲目里挑一个最合适的 3 秒窗口：

  - 片头：挑「能量高 + 开头有明确起音」的位置，用作有冲击力的开场
  - 片尾：挑「能量高 + 结尾自然收束」的位置，用作有余韵的收尾

窗口按 RMS 能量排序后，再按首尾包络做二次筛选：
  head = 前 0.2s 的 RMS（起音强度）
  tail = 后 0.3s 的 RMS（收束强度）
片头要 head 大（听上去像「起」），片尾要 tail 相对低（听上去像「收」）。

产出：
  brand/audio/intro_mix.wav   旁白 + 配乐，3 秒
  brand/audio/outro_mix.wav   旁白 + 配乐，3 秒

用法：
  python3 scripts/make_audio_brand.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BRAND = HERE.parent
AUDIO = BRAND / "audio"

DURATION = 2.833          # 与 render_brand.py 的帧数一致
VOICE_GAIN = 1.0
BGM_GAIN_DB = -19.0       # 配乐压到旁白之下
SR = 48000


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True).stdout.strip()
    return float(out)


def pick_window(bgm: Path, mode: str) -> tuple[float, dict]:
    """在配乐里挑一个 DURATION 秒的窗口。mode ∈ {intro, outro}。"""
    wav = AUDIO / "_probe.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(bgm),
                    "-ac", "1", "-ar", str(SR), str(wav)], check=True)
    import wave
    w = wave.open(str(wav))
    n = w.getnframes()
    data = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float64) / 32768.0
    total = len(data) / SR
    win = int(DURATION * SR)
    step = int(0.05 * SR)
    head_n = int(0.2 * SR)
    tail_n = int(0.3 * SR)

    best = None
    for i in range(0, max(1, len(data) - win), step):
        seg = data[i:i + win]
        if len(seg) < win:
            break
        rms = float(np.sqrt(np.mean(seg ** 2)))
        if rms < 1e-4:
            continue
        head = float(np.sqrt(np.mean(seg[:head_n] ** 2)))
        tail = float(np.sqrt(np.mean(seg[-tail_n:] ** 2)))
        peak = float(np.abs(seg).max())
        if peak > 0.98:          # 削顶的窗口跳过
            continue
        if mode == "intro":
            # 开场要「起」：能量高 + 起音明显
            score = rms * 1.0 + head * 1.6
        else:
            # 收尾要「收」：能量高但尾部明显衰减
            score = rms * 1.0 - abs(tail - rms * 0.55) * 0.9
        if best is None or score > best[0]:
            best = (score, i / SR, {
                "rms": rms, "head": head, "tail": tail, "peak": peak})

    wav.unlink(missing_ok=True)
    if best is None:
        raise RuntimeError(f"在 {bgm.name} 里找不到可用窗口")
    return best[1], best[2]


def build_mix(which: str, voice: Path, bgm: Path, out: Path) -> None:
    start, info = pick_window(bgm, which)
    dur = probe_duration(bgm)
    print(f"  配乐窗口 {which}: {start:.2f}s 起（曲目长 {dur:.1f}s）"
          f" rms={info['rms']:.4f} head={info['head']:.4f} tail={info['tail']:.4f}")

    # 切出窗口 → 旁白对齐到 0.15s → 混音
    bgm_clip = AUDIO / f"_bgm_{which}.wav"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-i", str(bgm),
        "-t", f"{DURATION:.3f}", "-ac", "2", "-ar", str(SR), str(bgm_clip),
    ], check=True)

    # 旁白：从 0.10s 起，给提示音留出前置空间
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", str(voice),
        "-af", f"adelay=100|100,volume={VOICE_GAIN}",
        "-ac", "2", "-ar", str(SR), "-t", f"{DURATION:.3f}",
        str(AUDIO / f"_voice_{which}.wav"),
    ], check=True)

    bgm_gain = 10 ** (BGM_GAIN_DB / 20)
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-i", str(AUDIO / f"_voice_{which}.wav"),
        "-i", str(bgm_clip),
        "-filter_complex",
        f"[0:a]volume={VOICE_GAIN}[v];"
        f"[1:a]volume={bgm_gain:.6f},afade=t=in:st=0:d=0.08,"
        f"afade=t=out:st={DURATION - 0.30:.3f}:d=0.30[b];"
        f"[v][b]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,"
        f"alimiter=limit=0.95,afade=t=out:st={DURATION - 0.15:.3f}:d=0.15[m]",
        "-map", "[m]", "-ac", "2", "-ar", str(SR),
        "-t", f"{DURATION:.3f}", str(out),
    ], check=True)

    bgm_clip.unlink(missing_ok=True)
    (AUDIO / f"_voice_{which}.wav").unlink(missing_ok=True)
    print(f"  → {out.name}（{probe_duration(out):.3f}s）")


def main() -> int:
    for which, voice, bgm, out in [
        ("intro", AUDIO / "voice_intro.mp3", AUDIO / "bgm_intro.wav",
         AUDIO / "intro_mix.wav"),
        ("outro", AUDIO / "voice_outro.mp3", AUDIO / "bgm_outro.wav",
         AUDIO / "outro_mix.wav"),
    ]:
        for p in (voice, bgm):
            if not p.exists():
                print(f"缺少素材：{p}", file=sys.stderr)
                return 1
        print(f"混音 {which} …")
        build_mix(which, voice, bgm, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
