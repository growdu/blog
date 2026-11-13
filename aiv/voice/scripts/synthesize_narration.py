#!/usr/bin/env python3
"""按规范合成 Growdu 视频旁白。

音色定稿（依据 aiv/形象与音色规范.md §2.2，对标 ddl-voiceover.mp3）：
  voice_id : Chinese (Mandarin)_Radio_Host
  pitch    : -1
  speed    : 1.33

⚠️ pitch / speed 是相对参照稿 ddl-voiceover.mp3 标定的。换稿后必须重新定标，
   方法见规范文档 §2.1（基频 F0 / 共振峰 F1,F2 / 频谱重心 / 语速 四项测量）。

用法：
  python3 scripts/synthesize_narration.py --text "大家好，我是growdu。"
  python3 scripts/synthesize_narration.py --script 字幕.md --out narration.mp3

依赖 mcode-tools CLI（mcode-tools-master skill）。

多音字：送进引擎前会按 `pronunciation.py` 的读音表做等音替换
（当前是「行锁」→「航锁」，因为这个音色把词首的「行」一律念成 xíng）。
口播稿本身不改，念出来的仍是「行锁」——见 `pronunciation.py` 的实测表。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pronunciation import PRONUNCIATION_SUBSTITUTIONS, apply_substitutions  # noqa: E402

# 定稿参数 —— 与规范文档 §2.2 一致
VOICE_ID = "Chinese (Mandarin)_Radio_Host"
VOICE_NAME = "电台男主播"
PITCH = -1
SPEED = 1.33
EMOTION = "neutral"


def run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"命令失败：{' '.join(cmd[:3])}\n{proc.stderr[-800:]}")
    return proc.stdout


def synthesize(text: str, output_file: str, emotion: str = EMOTION,
               pitch: int = PITCH, speed: float = SPEED) -> str:
    args = {
        "text": text,
        "voice_id": VOICE_ID,
        "pitch": pitch,
        "speed": speed,
        "emotion": emotion,
        "output_file": output_file,
    }
    args_file = Path(output_file).with_suffix(".args.json")
    args_file.write_text(json.dumps(args, ensure_ascii=False), encoding="utf-8")
    out = run(["mcode-tools", "connector", "call",
               "connector__matrix__synthesize_speech", "--args-file", str(args_file)])
    args_file.unlink(missing_ok=True)
    return json.loads(out[out.index("{"):])


def download(node_id: str, dest: Path) -> None:
    out = run(["mcode-tools", "get_asset_url", node_id])
    url = json.loads(out[out.index("{"):])["download_url"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["curl", "-sfL", "-o", str(dest), url], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="合成 Growdu 视频旁白")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="直接给出的口播文本")
    src.add_argument("--script", help="Markdown 口播稿文件（取第一个代码块）")
    parser.add_argument("--out", default="narration.mp3", help="输出音频路径")
    parser.add_argument("--emotion", default=EMOTION,
                        choices=["happy", "sad", "angry", "fearful",
                                 "disgusted", "surprised", "neutral"])
    parser.add_argument("--pitch", type=int, default=PITCH)
    parser.add_argument("--speed", type=float, default=SPEED)
    args = parser.parse_args()

    text = args.text
    if args.script:
        lines = Path(args.script).read_text(encoding="utf-8").splitlines()
        body, in_block = [], False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                in_block = not in_block
                continue
            if in_block and stripped:
                body.append(stripped)
        if not body:
            print("口播稿里没找到代码块", file=sys.stderr)
            return 1
        text = "".join(body)

    out = Path(args.out)
    spoken = apply_substitutions(text)
    if spoken != text:
        hits = [f"{w}→{r}" for w, r in PRONUNCIATION_SUBSTITUTIONS.items() if w in text]
        print(f"读音替换（只改送进引擎的文本，口播稿不动）：{', '.join(hits)}")
    # 旁本：把真正送进引擎的文本留一份下来，出片后可核对「念的到底是哪版」
    out.with_suffix(".spoken.txt").write_text(spoken + "\n", encoding="utf-8")
    res = synthesize(spoken, out.name, args.emotion, args.pitch, args.speed)
    if res.get("code") != 0:
        print(f"合成失败：{res}", file=sys.stderr)
        return 1
    download(res["node_id"], out)
    print(f"音色 {VOICE_NAME} (pitch={args.pitch}, speed={args.speed}) → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
