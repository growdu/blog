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
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

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
    "archive.org": {
        "note": "Internet Archive；直链由 metadata 接口算，页面结构稳定",
        "enabled": True,
    },
}


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"命令失败（{proc.returncode}）：{' '.join(cmd[:3])} ...\n"
            f"{(proc.stderr or '')[-1200:]}"
        )


def curl_json(url: str) -> dict:
    out = subprocess.run(["curl", "-sfL", "--max-time", "60", url],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"取不到 {url}：{out.stderr[-300:]}")
    return json.loads(out.stdout)


def _normalize_name(text: str) -> str:
    """把曲名归一成可比对的键：去扩展名、大小写与空白差异。"""
    stem = Path(text).stem
    stem = re.sub(r"\s*[_(].*$", "", stem)
    return re.sub(r"[\s\-]+", " ", stem).strip().lower()


def _archive_org_file(entry: dict) -> tuple[str, str]:
    """archive.org 的直链：metadata → 找到台账点名的那一轨。

    返回 (直链, 文件名)。
    """
    identifier = entry["source_url"].rstrip("/").split("/")[-1]
    meta = curl_json(f"https://archive.org/metadata/{identifier}")
    server = meta.get("server") or "archive.org"
    dirn = meta.get("dir") or ""

    wanted = _normalize_name(entry.get("title", ""))
    candidates = []
    for f in meta.get("files", []):
        name = f.get("name", "")
        if not name.lower().endswith(".mp3"):
            continue
        if f.get("source") not in ("original", None):
            continue
        try:
            length = float(f.get("length"))
        except (TypeError, ValueError):
            length = 0.0
        candidates.append((length, name))
    if not candidates:
        raise RuntimeError(f"{identifier} 里没有可下载的原音频")

    # 先按台账里的曲名精确匹配；台账写的是曲名，档案里的文件名常带轨号前缀
    # （台账「Subdued」↔ 档案「B3 Subdued.mp3」），所以再试一次后缀匹配；
    # 都匹配不上就取最长的一轨。
    for _length, name in candidates:
        if _normalize_name(name) == wanted:
            return f"https://{server}{dirn}/{quote(name)}", name
    for _length, name in candidates:
        if _normalize_name(name).endswith(" " + wanted):
            return f"https://{server}{dirn}/{quote(name)}", name
    length, name = max(candidates)
    return f"https://{server}{dirn}/{quote(name)}", name


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(["curl", "-sfL", "--max-time", "900", "-o", str(dest), url],
                          capture_output=True, text=True)
    if proc.returncode != 0 or not dest.exists() or dest.stat().st_size < 100000:
        raise RuntimeError(f"下载失败：{url}\n{proc.stderr[-300:]}")
    return dest


def fetch_archive_org(entry: dict, workdir: Path) -> Path:
    url, name = _archive_org_file(entry)
    print(f"    直链 {url}")
    return download(url, workdir / name)


ADAPTERS = {
    "archive.org": fetch_archive_org,
}


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
    handler = ADAPTERS.get(source)
    if handler is None:
        raise RuntimeError(f"来源 {source!r} 的适配器尚未实现")
    return handler(entry, workdir)


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
    """转规格 + 响度归一化（两遍 loudnorm）。

    单遍 loudnorm 是动态压缩，**落不到目标响度**：实测同一批素材单遍出来的
    是 -18.5 ~ -19.1 LUFS，而不是 -20。而《背景音乐规范》§5.1 的混音推导
    （BGM 比旁白低 11.3 dB）是从 -20 LUFS 算出来的，差 1.5 dB 整条推导就偏。

    两遍是 ffmpeg 的标准做法：第一遍量出这条曲子的真实值，
    第二遍带着测量值线性归一化，才能真正落到 -20。
    """
    dst.parent.mkdir(parents=True, exist_ok=True)

    measured = _loudnorm_measure(src)
    af = (f"loudnorm=I={MASTER_LUFS}:TP={TARGET_PEAK_DB}:LRA=11:"
          f"measured_I={measured['input_i']}:"
          f"measured_TP={measured['input_tp']}:"
          f"measured_LRA={measured['input_lra']}:"
          f"measured_thresh={measured['input_thresh']}:"
          f"offset={measured['target_offset']}:linear=true")
    run([
        "ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", af,
        "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS),
        "-c:a", "pcm_s16le", str(dst),
    ])
    return dst


def _loudnorm_measure(src: Path) -> dict:
    """第一遍：量出这条曲子的真实响度、峰值、LRA 与阈值。"""
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "info", "-i", str(src),
         "-af", f"loudnorm=I={MASTER_LUFS}:TP={TARGET_PEAK_DB}:LRA=11:"
                "print_format=json",
         "-f", "null", "-"],
        capture_output=True, text=True)
    text = proc.stderr
    start = text.rfind("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"量不出响度：{text[-500:]}")
    try:
        raw = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"响度测量结果解析失败：{exc}") from exc
    needed = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    missing = [k for k in needed if k not in raw]
    if missing:
        raise RuntimeError(f"响度测量结果缺字段：{missing}")
    return raw


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
