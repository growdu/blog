#!/usr/bin/env python3
"""为 Growdu 片头/片尾合成成品音轨（旁白 + 配乐）。

配乐窗口**不再各挑各的**。

规范 §6 末条：每期开头与结尾的 motif 片段要**首尾相接（片尾接回片头）**，
形成闭环。早先的做法是片头片尾各按能量评分各挑各的窗口——intro 在
115.15 s、outro 在 31.80 s，两段互不相干，实测相关系数只有 0.009，
听上去基本是两首不同的音乐。

现在的口径：片头取 [s, s+D)，片尾取 [s-D, s)，两段拼起来是同一段连续
音乐，片尾结束时正好落在片头的起音点上。

窗口由 `pipeline/pyv/bgm.py` 挑好后写进 `brand/brand_windows.json`
（入库——那是决策），这里只负责按那个文件切片、混音。换曲子时重跑
`python -m pyv.cli bgm windows` 即可，不必改这个脚本。

产出：
  brand/audio/intro_mix.wav   旁白 + 配乐，2.833 秒
  brand/audio/outro_mix.wav   旁白 + 配乐，2.833 秒

用法：
  python3 scripts/make_audio_brand.py
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRAND = HERE.parent
AIV = BRAND.parent
AUDIO = BRAND / "audio"
LIBRARY = AIV / "music" / "library.json"
# 窗口文件默认是已入库的那份；环境变量只是给测试与临时实验用。
WINDOWS = Path(os.environ.get("BRAND_WINDOWS_PATH")
               or (BRAND / "brand_windows.json"))

DURATION = 2.833          # 与 render_brand.py 的帧数一致
VOICE_GAIN = 1.0
BGM_GAIN_DB = -19.0       # 配乐压到旁白之下
SR = 48000

# 淡出时长。**要短**：片尾的音乐是片头那段的前一截，末尾淡出 0.3 秒
# 会把刚接上的闭环淡没了——片尾应当保持满能量到最后一刻，只留极短的
# 收尾避免爆音（0.08 秒 = 不到 2 帧，听不出来）。
FADE_OUT = 0.08
# 片头从零起（视频一开始就是黑的，音乐升上来）；片尾不淡入——
# 它的窗口是曲子中段的接缝，淡入反而像另起一段。
FADE_IN_INTRO = 0.08
# 混音成品层面的收尾淡出：只用来压住旁白尾音的爆点，0.05 秒。
MIX_FADE_OUT = 0.05


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True).stdout.strip()
    return float(out)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_windows() -> dict:
    """读入已入库的窗口决定。"""
    if not WINDOWS.is_file():
        print(
            f"缺少 {WINDOWS}——先跑 `python -m pyv.cli bgm windows` 挑窗口",
            file=sys.stderr,
        )
        raise SystemExit(1)
    data = json.loads(WINDOWS.read_text(encoding="utf-8"))
    for key in ("duration_s", "intro_start_s", "outro_start_s", "track_id"):
        if key not in data:
            print(f"{WINDOWS} 缺少字段 {key!r}", file=sys.stderr)
            raise SystemExit(1)
    return data


def resolve_track(track_id: str) -> Path:
    """按台账里的 id 找到配乐文件，并核对指纹。"""
    entries = json.loads(LIBRARY.read_text(encoding="utf-8"))["tracks"]
    for entry in entries:
        if entry.get("id") != track_id:
            continue
        path = AIV / entry["local_path"]
        if not path.is_file():
            print(f"配乐文件不在：{path}", file=sys.stderr)
            raise SystemExit(1)
        expected = entry.get("sha256", "")
        if expected and sha256_of(path) != expected:
            print(f"{path.name} 的指纹与台账不符——曲子换过了，"
                  f"要重挑窗口（bgm windows）", file=sys.stderr)
            raise SystemExit(1)
        return path
    print(f"台账里没有 id 为 {track_id!r} 的曲子", file=sys.stderr)
    raise SystemExit(1)


def build_mix(which: str, voice: Path, bgm: Path, out: Path,
              start: float, duration: float, fade_in: float) -> None:
    """切窗口 → 对齐旁白 → 混音。

    `fade_in` 是**配乐层面**的淡入：片头给一个极短的淡入（视频从黑场起
    音），片尾不给——片尾的窗口是曲子中段的接缝，淡入像另起一段。
    """
    # 切出窗口 → 旁白对齐到 0.10s → 混音
    bgm_clip = AUDIO / f"_bgm_{which}.wav"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-i", str(bgm),
        "-t", f"{duration:.3f}", "-ac", "2", "-ar", str(SR), str(bgm_clip),
    ], check=True)

    # 旁白：从 0.10s 起，给提示音留出前置空间
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", str(voice),
        "-af", f"adelay=100|100,volume={VOICE_GAIN}",
        "-ac", "2", "-ar", str(SR), "-t", f"{duration:.3f}",
        str(AUDIO / f"_voice_{which}.wav"),
    ], check=True)

    bgm_gain = 10 ** (BGM_GAIN_DB / 20)
    fade_in_chain = f"afade=t=in:st=0:d={fade_in:.3f}," if fade_in > 0 else ""
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-i", str(AUDIO / f"_voice_{which}.wav"),
        "-i", str(bgm_clip),
        "-filter_complex",
        f"[0:a]volume={VOICE_GAIN}[v];"
        f"[1:a]volume={bgm_gain:.6f},{fade_in_chain}"
        f"afade=t=out:st={duration - FADE_OUT:.3f}:d={FADE_OUT:.3f}[b];"
        f"[v][b]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,"
        f"alimiter=limit=0.95,afade=t=out:st={duration - MIX_FADE_OUT:.3f}:d={MIX_FADE_OUT:.3f}[m]",
        "-map", "[m]", "-ac", "2", "-ar", str(SR),
        "-t", f"{duration:.3f}", str(out),
    ], check=True)

    bgm_clip.unlink(missing_ok=True)
    (AUDIO / f"_voice_{which}.wav").unlink(missing_ok=True)
    print(f"  → {out.name}（{probe_duration(out):.3f}s）")


def main() -> int:
    windows = load_windows()
    duration = float(windows["duration_s"])
    intro_start = float(windows["intro_start_s"])
    outro_start = float(windows["outro_start_s"])

    # 首尾相接：片尾的结束点必须正好是片头的起点（规范 §6 末条）
    if abs(outro_start + duration - intro_start) > 0.01:
        print(
            f"窗口不相接：片尾结束于 {outro_start + duration:.3f}s，"
            f"片头起于 {intro_start:.3f}s——重跑 `bgm windows` 挑一对",
            file=sys.stderr,
        )
        return 1

    track = resolve_track(windows["track_id"])
    total = probe_duration(track)
    print(f"motif {windows['track_id']}（{track.name}，{total:.1f}s）")
    print(f"  片头 {intro_start:.3f}~{intro_start + duration:.3f}s")
    print(f"  片尾 {outro_start:.3f}~{outro_start + duration:.3f}s")

    for which, voice, out, start, fade_in in [
        ("intro", AUDIO / "voice_intro.mp3", AUDIO / "intro_mix.wav",
         intro_start, FADE_IN_INTRO),
        ("outro", AUDIO / "voice_outro.mp3", AUDIO / "outro_mix.wav",
         outro_start, 0.0),
    ]:
        if not voice.exists():
            print(f"缺少素材：{voice}", file=sys.stderr)
            return 1
        print(f"混音 {which} …")
        build_mix(which, voice, track, out, start, duration, fade_in)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
