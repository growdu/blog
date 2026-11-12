"""品牌片头/片尾（brand plate）接入。

素材在 aiv/brand/ 下（品牌资源包），流水线只消费 brand/clips/*.mp4：
- prepare_clips：把品牌片统一转成流水线规格
  （1920x1080 @24fps、时间基 1/24000、无音轨视频 + 48k 立体声 wav）
- apply_plates：把品牌片作为 "clip" 场景插到契约首尾，正文整体后移

品牌片是"现成素材"，不经过 cairo 渲染，所以时间基/帧率必须和 code 片段
完全一致，否则 concat demuxer 拼接出来的时长会漂。

片头/片尾的定稿是 3 秒内的版本（brand/scripts/render_brand.py 渲染）：
  growdu_intro_3s_1080p.mp4 / growdu_outro_3s_1080p.mp4
旧的 8 秒版本只在 3 秒版缺失时兜底使用，并会打印告警。

媒体产物不入库（见 aiv/.gitignore），所以仓库里可能一张品牌片都没有；
这时 prepare_clips 返回空字典，流水线照常出片，只是不带品牌片头片尾。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# aiv/ 是 pipeline/ 的上一级：pyv/brand.py → pyv → pipeline → aiv
AIV_ROOT = Path(__file__).resolve().parents[2]
BRAND_ROOT = AIV_ROOT / "brand"
CLIPS_DIR = BRAND_ROOT / "clips"
INTRO_CLIP = CLIPS_DIR / "growdu_intro_3s_1080p.mp4"
OUTRO_CLIP = CLIPS_DIR / "growdu_outro_3s_1080p.mp4"
# 旧版 8 秒片：只在 3 秒版缺失时兜底（会告警，因为规格要求 ≤3 秒）
LEGACY_INTRO_CLIP = CLIPS_DIR / "growdu_intro_8s_1080p.mp4"
LEGACY_OUTRO_CLIP = CLIPS_DIR / "growdu_outro_8s_1080p.mp4"

INTRO_SUBTITLE = "Growdu · 深入数据库"
OUTRO_SUBTITLE = "Growdu.cn"

CLIP_PREFIX = "brand_"
BRAND_DIRNAME = "brand"
TIMESCALE_FACTOR = 1000
MAX_BRAND_SECONDS = 3.0


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-1500:]
        raise RuntimeError(
            f"命令失败（退出码 {proc.returncode}）：{' '.join(cmd[:2])} ...\n{tail}"
        )


def probe_duration(path: str | Path) -> float:
    """用 ffprobe 量时长。"""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return float(out)


def _is_fresh(target: Path, source: Path) -> bool:
    """产物比源文件新就可以复用。"""
    return target.exists() and target.stat().st_mtime >= source.stat().st_mtime


def _transcode(source: Path, target: Path, fps: int, width: int, height: int) -> None:
    """统一成流水线规格：无音轨、恒定帧率、固定时间基。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    _run([
        "ffmpeg", "-y", "-i", str(source), "-an",
        "-vf", f"fps={fps},scale={width}:{height}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-video_track_timescale", str(fps * TIMESCALE_FACTOR),
        str(target),
    ])


def _extract_audio(source: Path, target: Path) -> None:
    """抽出品牌片自己的音轨（人声 + 环境 BGM），48k 立体声 wav。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    _run([
        "ffmpeg", "-y", "-i", str(source), "-vn",
        "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
        str(target),
    ])


def _resolve_audio_source(name: str, clip: Path) -> Path:
    """片头片尾的音轨来源：优先用混好的成品音轨，mp4 只作兜底。

    mp4 里也烘焙了一份音轨，但那是渲染那一刻的版本——换了配乐又没重渲
    3D 形象的话，片头片尾就会用回旧音乐（2026-11-12 就踩过：motif 的
    成品音轨做出来了，却没接进成片，片头片尾用的还是旧 AI 配乐）。

    `make_audio_brand.py` 产出的 `{intro,outro}_mix.wav` 才是音轨的正本。
    """
    mix = BRAND_ROOT / "audio" / f"{name}_mix.wav"
    if mix.is_file():
        return mix
    return clip


def resolve_clip(name: str) -> Path | None:
    """按优先级挑一张存在的品牌片。

    优先定稿的 3 秒版；缺失时回退旧 8 秒版并告警（规格要求 ≤3 秒）。
    一张都没有时返回 None —— 媒体产物不入库，流水线可以不带品牌片出片。
    """
    primary, legacy = {
        "intro": (INTRO_CLIP, LEGACY_INTRO_CLIP),
        "outro": (OUTRO_CLIP, LEGACY_OUTRO_CLIP),
    }[name]
    if primary.exists():
        return primary
    if legacy.exists():
        print(
            f"告警 {name} 品牌片缺少定稿版 {primary.name}，"
            f"回退到旧版 {legacy.name}（超过 {MAX_BRAND_SECONDS:.0f} 秒上限）",
            file=sys.stderr,
        )
        return legacy
    return None


def prepare_clips(build_dir: str | Path, fps: int = 24,
                  width: int = 1920, height: int = 1080) -> dict:
    """准备品牌片：转码视频 + 抽音频。

    返回 {"intro": {"clip": Path, "audio": Path, "duration": float}, ...}，
    只包含素材确实存在的品牌片。
    """
    build_dir = Path(build_dir)
    out_dir = build_dir / BRAND_DIRNAME
    out_dir.mkdir(parents=True, exist_ok=True)

    prepared: dict = {}
    for name in ("intro", "outro"):
        source = resolve_clip(name)
        if source is None:
            continue
        clip = out_dir / f"{name}.mp4"
        audio = out_dir / f"{name}.wav"
        if not _is_fresh(clip, source):
            _transcode(source, clip, fps, width, height)
        # 音轨以成品混音为准：换音乐不必重渲 3D 形象
        audio_source = _resolve_audio_source(name, source)
        if not _is_fresh(audio, audio_source):
            _extract_audio(audio_source, audio)
        prepared[name] = {
            "clip": clip,
            "audio": audio,
            "duration": round(probe_duration(clip), 3),
        }
    return prepared


def _relative_to_build(path: Path, build_dir: Path) -> str:
    """优先写成相对 build 目录的路径，compose 按 build 目录解析。"""
    try:
        return os.path.relpath(str(path.resolve()), str(Path(build_dir).resolve()))
    except ValueError:
        return str(path)


def _brand_scene(scene_id: str, start: float, info: dict, subtitle: str,
                 build_dir: Path) -> dict:
    return {
        "id": scene_id,
        "start": round(start, 3),
        "end": round(start + info["duration"], 3),
        "type": "clip",
        "subtitle": subtitle,
        "renderer": None,
        "params": {},
        "h3": None,
        "clip": _relative_to_build(info["clip"], build_dir),
        "audio": _relative_to_build(info["audio"], build_dir),
    }


def _shift(raw: dict, scenes: list[dict], delta: float) -> None:
    """整体平移场景与字幕事件的时间码。"""
    if not delta:
        return
    for scene in scenes:
        scene["start"] = round(float(scene["start"]) + delta, 3)
        scene["end"] = round(float(scene["end"]) + delta, 3)
    for event in raw.get("subtitles", []) or []:
        event["start"] = round(float(event["start"]) + delta, 3)
        event["end"] = round(float(event["end"]) + delta, 3)


def apply_plates(storyboard_path: str | Path, out_path: str | Path,
                 build_dir: str | Path, intro: bool = True,
                 outro: bool = True) -> Path:
    """给对齐好的契约套上品牌片头/片尾。

    - 先移除已有的品牌场景并撤销上一次引入的位移（可重复执行）
    - 有片头时：正文整体后移 intro_duration，再插入 brand_intro
    - 有片尾时：追加 brand_outro
    - 契约总时长跟着最后一段走
    """
    storyboard_path = Path(storyboard_path)
    out_path = Path(out_path)
    build_dir = Path(build_dir)

    raw = json.loads(storyboard_path.read_text(encoding="utf-8"))
    all_scenes = list(raw.get("scenes", []))

    # 移除旧品牌场景，并记下上次片头引入的位移量
    old_shift = 0.0
    scenes: list[dict] = []
    for scene in all_scenes:
        scene_id = scene.get("id", "")
        if scene_id.startswith(CLIP_PREFIX):
            if scene_id == "brand_intro":
                old_shift = float(scene.get("end", 0)) - float(scene.get("start", 0))
            continue
        scenes.append(scene)
    _shift(raw, scenes, -old_shift)

    prepared = prepare_clips(build_dir)

    if intro and "intro" in prepared:
        info = prepared["intro"]
        _shift(raw, scenes, info["duration"])
        scenes.insert(
            0, _brand_scene("brand_intro", 0.0, info, INTRO_SUBTITLE, build_dir)
        )

    if outro and "outro" in prepared:
        info = prepared["outro"]
        start = float(scenes[-1]["end"]) if scenes else 0.0
        scenes.append(
            _brand_scene("brand_outro", start, info, OUTRO_SUBTITLE, build_dir)
        )

    raw["scenes"] = scenes
    if scenes:
        raw.setdefault("video", {})["duration"] = round(float(scenes[-1]["end"]), 3)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(raw, ensure_ascii=False, indent=2) + "\n"
    # 内容没变就别改文件时间戳，否则 render 会无谓地重渲染所有片段
    if out_path.resolve() == storyboard_path.resolve() and \
            out_path.exists() and out_path.read_text(encoding="utf-8") == payload:
        return out_path
    out_path.write_text(payload, encoding="utf-8")
    return out_path
