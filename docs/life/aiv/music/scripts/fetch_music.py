#!/usr/bin/env python3
"""按台账下载并处理背景音乐。

台账是人工确认过授权的曲子清单（`music/library.json`），脚本只负责
**下载 → 转规格 → 响度归一化 → 校验指纹 → 落盘**这四件事，
不替人判断授权。

下载源按站点分适配器（`SOURCES`）。没接的站点会直接报错，
不会去猜 URL。

处理链（顺序不能换）：

    原曲 → 48 kHz 立体声 wav → loudnorm 归一化到 -20 LUFS → 落盘

归一化是必须的：曲库母版的响度差能到 10 dB 以上，不拉平就没法用
固定增益混音（见《背景音乐规范》§4.1）。

用法：
    python3 scripts/fetch_music.py --id <台账里的 id>
    python3 scripts/fetch_music.py --all
    python3 scripts/fetch_music.py --list
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MUSIC = HERE.parent
AIV = MUSIC.parent
LIBRARY = MUSIC / "library.json"
TRACKS = MUSIC / "tracks"

# 与 pipeline/pyv/bgm.py 的常量保持一致（脚本独立运行，不 import 流水线）
MASTER_LUFS = -20.0
TARGET_PEAK_DB = -3.0
SAMPLE_RATE = 48000
CHANNELS = 2

# 下载源适配器：站点 → 取直链的函数。
# 各站点页面结构不同，一个站点写一个适配器，没接的站点不猜 URL。
SOURCES: dict[str, dict] = {
    "pixabay": {
        "note": "Pixabay Music；直链从页面取，页面结构随站点改版会变",
        "enabled": False,
    },
}


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"命令失败（{proc.returncode}）：{' '.join(cmd[:3])} ...\n"
            f"{(proc.stderr or '')[-1200:]}"
        )


def load_library() -> dict:
    if not LIBRARY.exists():
        raise FileNotFoundError(f"找不到台账：{LIBRARY}")
    return json.loads(LIBRARY.read_text(encoding="utf-8"))


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(src: Path, dst: Path) -> Path:
    """转规格 + 响度归一化。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y", "-v", "error", "-i", str(src),
        "-af", f"loudnorm=I={MASTER_LUFS}:TP={TARGET_PEAK_DB}:LRA=11",
        "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS),
        "-c:a", "pcm_s16le", str(dst),
    ])
    return dst


def fetch(entry: dict, workdir: Path) -> Path:
    """下载并处理一首曲子，返回落盘路径。"""
    source = entry.get("source", "")
    adapter = SOURCES.get(source)
    if adapter is None:
        raise RuntimeError(
            f"来源 {source!r} 没有接适配器。先在 scripts/fetch_music.py 的 "
            f"SOURCES 里补上这个站点的取直链逻辑。"
        )
    if not adapter.get("enabled"):
        raise RuntimeError(
            f"来源 {source!r} 的适配器还没启用（{adapter.get('note', '')}）"
        )
    raise RuntimeError(f"来源 {source!r} 的适配器尚未实现")


def main() -> int:
    parser = argparse.ArgumentParser(description="按台账下载并处理背景音乐")
    parser.add_argument("--id", help="只处理台账里这一首")
    parser.add_argument("--all", action="store_true", help="处理台账里全部")
    parser.add_argument("--list", action="store_true", help="列出台账")
    args = parser.parse_args()

    library = load_library()
    entries = library.get("tracks", [])

    if args.list:
        if not entries:
            print("台账是空的——先按《背景音乐规范》§2.2 登记曲子")
            return 0
        for entry in entries:
            print(f"{entry.get('id', '?'):24} {entry.get('series_role', '?'):6} "
                  f"{entry.get('license', '?'):22} {entry.get('title', '')}")
        return 0

    if args.id:
        entries = [e for e in entries if e.get("id") == args.id]
        if not entries:
            print(f"台账里没有 id={args.id}", file=sys.stderr)
            return 1
    elif not args.all:
        parser.error("要给 --id 或 --all（或用 --list 看台账）")

    workdir = TRACKS / "_download"
    workdir.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        try:
            raw = fetch(entry, workdir)
        except RuntimeError as exc:
            print(f"跳过 {entry.get('id', '?')}：{exc}", file=sys.stderr)
            continue
        target = AIV / entry["local_path"]
        normalize(raw, target)
        digest = sha256_of(target)
        if entry.get("sha256") and entry["sha256"] != digest:
            print(f"警告：{entry['id']} 的指纹与台账不一致\n"
                  f"  台账 {entry['sha256']}\n  实际 {digest}", file=sys.stderr)
        print(f"  → {target.relative_to(AIV)}  sha256={digest[:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
