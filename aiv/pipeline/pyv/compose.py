"""片段拼接 + 混音 → 成片。

字幕已在渲染阶段由 cairo 直接烧进画面（本机 ffmpeg 未编译 libass，
`ass=` 滤镜不可用）；同时输出 ASS 副产物，供 MiniMax Design 导入时复用。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from pyv import bgm as bgm_rules  # compose() 的参数叫 bgm，会遮住同名模块
from pyv import render, subtitle
from pyv.timeline import Scene, Storyboard

# BGM 基础增益。默认按《背景音乐规范》§5.1 定的 -15 dB；
# 契约里的 bgm_gain_db 可以覆盖。
DEFAULT_BGM_GAIN_DB = bgm_rules.BGM_GAIN_DB

# 旁白与品牌片音轨的通道：上混成立体声，音量不动。
# pan 而不是 aformat=channel_layouts=stereo：后者把单声道上混时
# 会按功率衰减 3dB，旁白会比立体声的品牌音轨明显小声一截。
VOICE_CHAIN = r"aformat=sample_fmts=fltp,pan=stereo\|c0=c0\|c1=c0,volume=1.0"


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-1500:]
        raise RuntimeError(
            f"命令失败（退出码 {proc.returncode}）：{' '.join(cmd[:2])} ...\n{tail}"
        )


def _write_concat_list(clips: list[Path], list_path: Path) -> None:
    list_path.write_text(
        "".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8"
    )


def _resolve_asset(raw_path: str | None, build_dir: Path, label: str,
                   scene_id: str) -> Path:
    """素材路径：绝对路径直接用，相对路径按 build 目录解析。"""
    raw = Path(raw_path or "")
    path = raw if raw.is_absolute() else build_dir / raw
    if not path.exists():
        raise FileNotFoundError(f"场景 {scene_id} 缺少 {label} 片段：{path}")
    return path


def _resolve_h3_clip(scene: Scene, build_dir: Path) -> Path:
    return _resolve_asset(scene.clip, build_dir, "h3", scene.id)


def _resolve_brand_clip(scene: Scene, build_dir: Path) -> Path:
    return _resolve_asset(scene.clip, build_dir, "clip", scene.id)


def _resolve_brand_audio(scene: Scene, build_dir: Path) -> Path:
    return _resolve_asset(scene.audio, build_dir, "audio", scene.id)


def _newest_source_mtime(scene: Scene, extra_mtime: float | None) -> float:
    """渲染输入里最新的一个修改时间：场景源码 + 包内模块 + 契约文件。"""
    return render.newest_source_mtime(scene, extra_mtime)


def _clip_is_fresh(clip: Path, scene: Scene, extra_mtime: float | None) -> bool:
    """片段比所有渲染输入都新就可以复用，避免 render → compose 重复渲染。"""
    return render.clip_is_fresh(clip, scene, extra_mtime)


def _collect_clips(storyboard: Storyboard, build_dir: Path, burner,
                   reuse: bool = True, source_mtime: float | None = None) -> list[Path]:
    """按时间顺序收集待拼接片段：code 场景现场渲染，h3/clip 场景用现成素材。"""
    clips: list[Path] = []
    for scene in storyboard.scenes:
        if scene.type == "code":
            out = build_dir / f"{scene.id}.mp4"
            if reuse and _clip_is_fresh(out, scene, source_mtime):
                clips.append(out)
                continue
            render.render_scene(
                scene, out,
                storyboard.video.width, storyboard.video.height,
                storyboard.video.fps, burner=burner,
            )
            clips.append(out)
        elif scene.type == "clip":
            clips.append(_resolve_brand_clip(scene, build_dir))
        else:
            clips.append(_resolve_h3_clip(scene, build_dir))
    return clips


def _body_range(storyboard: Storyboard) -> tuple[float, float]:
    """正文区间：第一个 code 场景的起点到最后一个 code 场景的终点。

    BGM 只铺正文——片头片尾自带音乐，叠在一起只会糊（规范 §5.5）。
    """
    code_scenes = [scene for scene in storyboard.scenes if scene.type == "code"]
    if not code_scenes:
        return 0.0, storyboard.duration
    return code_scenes[0].start, code_scenes[-1].end


def _narration_delay(storyboard: Storyboard) -> float:
    """旁白要推迟到正文真正开始的位置（片头品牌片占着前几秒）。"""
    for scene in storyboard.scenes:
        if scene.type == "code":
            return scene.start
    return 0.0


def _mux_cmd(silent: Path, out_path: Path, storyboard: Storyboard,
             sources: list[tuple[Path, float, str]]) -> list[str]:
    """拼出「视频 + 多路音频」的 ffmpeg 命令。

    sources 每项是 (音频文件, 延迟秒数, 滤波链)；滤波链是这一路的完整
    音频处理（音量也在里面）。所有音频都在同一个 filter_complex 里用
    adelay 对齐后 amix（同一路流不能同时用 -af 与 -filter_complex）。
    """
    fps = storyboard.video.fps
    duration = storyboard.duration
    cmd = ["ffmpeg", "-y", "-i", str(silent)]
    for path, _, _ in sources:
        cmd += ["-i", str(path)]

    chains = []
    labels = []
    for index, (_, delay, chain) in enumerate(sources):
        ms = int(round(delay * 1000))
        chains.append(
            f"[{index + 1}:a]aresample=48000,{chain},adelay={ms}:all=1[a{index}]"
        )
        labels.append(f"[a{index}]")
    chains.append(
        "".join(labels)
        + f"amix=inputs={len(sources)}:duration=longest:"
        "dropout_transition=0:normalize=0,apad[mix]"
    )

    cmd += [
        "-filter_complex", ";".join(chains),
        "-map", "0:v:0", "-map", "[mix]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-video_track_timescale", str(fps * 1000),
    ]
    cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
    cmd += ["-t", f"{duration:.3f}", "-movflags", "+faststart", str(out_path)]
    return cmd


def compose(storyboard: Storyboard, build_dir: str | Path, out_path: str | Path,
            narration: str | Path | None = None,
            bgm: str | Path | None = None,
            bgm_gain_db: float | None = None,
            burn_subtitles: bool = True,
            reuse: bool = True,
            source_mtime: float | None = None) -> Path:
    """渲染全部片段 → 拼接 → 混入旁白 → 输出成片。

    narration 为空时产出无声成片（便于逐帧核对画面）。
    reuse 为真时复用 build 目录里未过期的片段，避免重复渲染。
    """
    build_dir = Path(build_dir)
    out_path = Path(out_path)
    build_dir.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    burner = None
    if burn_subtitles:
        burner = subtitle.SubtitleBurner(
            storyboard.subtitle_events(), storyboard.subtitle_style
        )

    clips = _collect_clips(storyboard, build_dir, burner, reuse=reuse,
                            source_mtime=source_mtime)
    if not clips:
        raise RuntimeError("没有可拼接的片段")

    list_path = build_dir / "concat.txt"
    _write_concat_list(clips, list_path)

    silent = build_dir / "silent.mp4"
    _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(storyboard.video.fps),
        "-video_track_timescale", str(storyboard.video.fps * 1000),
        "-an", str(silent),
    ])

    ass_path = build_dir / "subtitles.ass"
    ass_path.write_text(subtitle.build_ass(storyboard), encoding="utf-8")

    if narration is None:
        _run([
            "ffmpeg", "-y", "-i", str(silent),
            "-c:v", "copy", "-t", f"{storyboard.duration:.3f}",
            "-movflags", "+faststart", str(out_path),
        ])
        return out_path

    narration_path = Path(narration)
    if not narration_path.exists():
        raise FileNotFoundError(f"找不到旁白音频：{narration_path}")

    bgm_path = Path(bgm) if bgm else None
    if bgm_path is not None and not bgm_path.exists():
        raise FileNotFoundError(f"找不到 BGM：{bgm_path}")

    # 音频源：(文件, 延迟秒数, 滤波链)
    sources: list[tuple[Path, float, str]] = []
    # 旁白对齐到正文起点（前面有品牌片时整体后移）
    sources.append((narration_path, _narration_delay(storyboard), VOICE_CHAIN))
    for scene in storyboard.scenes:
        if scene.type == "clip":
            sources.append(
                (_resolve_brand_audio(scene, build_dir), scene.start, VOICE_CHAIN)
            )
    if bgm_path is not None:
        body_start, body_end = _body_range(storyboard)
        body_duration = max(0.0, body_end - body_start)
        gain_db = DEFAULT_BGM_GAIN_DB if bgm_gain_db is None else bgm_gain_db
        # ducking 按旁白包络算，深度是确定的数（规范 §5.2）；
        # 避让 EQ 与固定增益走 bgm.bgm_chain()（规范 §5.3、§5.4）。
        ducked = bgm_rules.duck_bgm(
            bgm_path, narration_path, build_dir / "_bgm_ducked.wav",
            duration_s=body_duration,
        )
        sources.append((ducked, body_start, bgm_rules.bgm_chain(gain_db)))

    _run(_mux_cmd(silent, out_path, storyboard, sources))
    return out_path
