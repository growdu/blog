"""品牌片头/片尾（brand plate）接入测试。"""
import json
import os
import subprocess
from pathlib import Path

import pytest

from pyv import brand, compose
from pyv.timeline import Storyboard

ROOT = Path(__file__).resolve().parents[2]
REAL_INTRO = brand.INTRO_CLIP
REAL_OUTRO = brand.OUTRO_CLIP


def _probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,codec_name,r_frame_rate,time_base,"
         "sample_rate,channels,duration:format=duration",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def _make_brand_clip(path: Path, seconds: float = 1.0, fps: int = 30) -> Path:
    """合成一段"品牌片"：30fps 视频 + 正弦音，用来跑通转码路径。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", f"color=c=navy:s=1920x1080:d={seconds}:r={fps}",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(path)],
        check=True, capture_output=True, text=True,
    )
    return path


def _write_storyboard(tmp_path: Path, scenes, duration: float,
                      subtitles=None) -> Path:
    raw = {
        "version": 1,
        "video": {"width": 1920, "height": 1080, "fps": 24, "duration": duration},
        "audio": {"narration": "tone.wav", "bgm": None},
        "subtitle_style": {"primary": "#1B2A47", "outline": "#FFFFFF",
                           "position": "bottom-center"},
        "scenes": scenes,
        "subtitles": subtitles if subtitles is not None else [],
    }
    path = tmp_path / "aligned.json"
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path


def _body_scenes():
    return [
        {"id": "s01", "start": 0.0, "end": 2.0, "type": "code",
         "renderer": "blank_scene", "subtitle": "第一句字幕"},
        {"id": "s02", "start": 2.0, "end": 4.0, "type": "code",
         "renderer": "blank_scene", "subtitle": "第二句字幕"},
    ]


def test_prepare_clips_transcodes_real_brand_asset(tmp_path):
    """真实品牌片必须被转成流水线规格：1920x1080 @24fps + 48k 立体声 wav。"""
    if not REAL_INTRO.exists():
        pytest.skip("品牌素材不在仓库中，跳过")

    prepared = brand.prepare_clips(tmp_path / "build")

    assert "intro" in prepared and "outro" in prepared
    info = prepared["intro"]
    assert info["clip"].exists() and info["audio"].exists()

    streams = _probe(info["clip"])["streams"]
    video = next(s for s in streams if s["codec_type"] == "video")
    assert video["width"] == 1920
    assert video["height"] == 1080
    assert video["r_frame_rate"] == "24/1"
    assert not [s for s in streams if s["codec_type"] == "audio"], \
        "转码后的视频片段必须没有音轨"

    audio = _probe(info["audio"])["streams"][0]
    assert audio["codec_name"] == "pcm_s16le"
    assert audio["sample_rate"] == "48000"
    assert audio["channels"] == 2

    assert info["duration"] == pytest.approx(2.833, abs=0.05)
    assert info["duration"] <= brand.MAX_BRAND_SECONDS, "片头必须 ≤3 秒"


def test_resolve_clip_prefers_3s_and_falls_back_to_legacy(tmp_path, monkeypatch):
    """定稿的 3 秒片优先；缺失时回退旧版并告警。"""
    legacy = tmp_path / "legacy.mp4"
    legacy.write_bytes(b"x")

    monkeypatch.setattr(brand, "INTRO_CLIP", tmp_path / "missing.mp4")
    monkeypatch.setattr(brand, "LEGACY_INTRO_CLIP", legacy)
    assert brand.resolve_clip("intro") == legacy

    primary = tmp_path / "primary.mp4"
    primary.write_bytes(b"x")
    monkeypatch.setattr(brand, "INTRO_CLIP", primary)
    assert brand.resolve_clip("intro") == primary


def test_resolve_clip_returns_none_when_no_asset(tmp_path, monkeypatch):
    """媒体产物不入库：一张都没有时返回 None，流水线照常出片。"""
    monkeypatch.setattr(brand, "INTRO_CLIP", tmp_path / "a.mp4")
    monkeypatch.setattr(brand, "LEGACY_INTRO_CLIP", tmp_path / "b.mp4")
    monkeypatch.setattr(brand, "OUTRO_CLIP", tmp_path / "c.mp4")
    monkeypatch.setattr(brand, "LEGACY_OUTRO_CLIP", tmp_path / "d.mp4")
    assert brand.resolve_clip("intro") is None
    assert brand.resolve_clip("outro") is None
    assert brand.prepare_clips(tmp_path / "build") == {}


def test_prepare_clips_reuses_fresh_outputs(tmp_path, monkeypatch):
    """产物比源文件新时不该重复转码。"""
    source = _make_brand_clip(tmp_path / "src" / "intro.mp4")
    monkeypatch.setattr(brand, "INTRO_CLIP", source)
    monkeypatch.setattr(brand, "OUTRO_CLIP", source)
    clip = tmp_path / "build" / "brand" / "intro.mp4"

    brand.prepare_clips(tmp_path / "build", fps=24)
    assert clip.exists()
    mtime = clip.stat().st_mtime_ns

    brand.prepare_clips(tmp_path / "build", fps=24)
    assert clip.stat().st_mtime_ns == mtime, "未过期时不该重新转码"

    # 源文件更新后必须重新转码
    future = source.stat().st_mtime + 60
    os.utime(source, (future, future))
    brand.prepare_clips(tmp_path / "build", fps=24)
    assert clip.stat().st_mtime_ns != mtime, "源文件更新后必须重新转码"


def test_apply_plates_inserts_intro_and_outro(tmp_path, monkeypatch):
    intro = _make_brand_clip(tmp_path / "src" / "intro.mp4", seconds=2.0)
    outro = _make_brand_clip(tmp_path / "src" / "outro.mp4", seconds=3.0)
    monkeypatch.setattr(brand, "INTRO_CLIP", intro)
    monkeypatch.setattr(brand, "OUTRO_CLIP", outro)

    aligned = _write_storyboard(
        tmp_path, _body_scenes(), 4.0,
        subtitles=[{"start": 0.0, "end": 2.0, "text": "第一句字幕"},
                   {"start": 2.0, "end": 4.0, "text": "第二句字幕"}],
    )
    out = brand.apply_plates(aligned, tmp_path / "branded.json",
                             tmp_path / "build")

    sb = Storyboard.load(out)
    assert sb.validate() == []

    assert sb.scenes[0].id == "brand_intro"
    assert sb.scenes[-1].id == "brand_outro"
    assert sb.scenes[0].type == "clip"
    assert sb.scenes[0].start == pytest.approx(0.0)
    assert sb.scenes[0].end == pytest.approx(2.0)
    assert sb.scenes[-1].end == pytest.approx(9.0)
    assert sb.video.duration == pytest.approx(9.0)

    # 正文整体后移 intro 时长
    body = sb.scenes[1:-1]
    assert [s.id for s in body] == ["s01", "s02"]
    assert body[0].start == pytest.approx(2.0)
    assert body[1].end == pytest.approx(6.0)

    # 字幕事件同步后移
    assert sb.subtitles[0].start == pytest.approx(2.0)
    assert sb.subtitles[1].end == pytest.approx(6.0)

    # 片段路径按 build 目录解析
    assert sb.scenes[0].clip == "brand/intro.mp4"
    assert sb.scenes[0].audio == "brand/intro.wav"
    assert sb.scenes[-1].clip == "brand/outro.mp4"


def test_apply_plates_is_idempotent(tmp_path, monkeypatch):
    intro = _make_brand_clip(tmp_path / "src" / "intro.mp4", seconds=2.0)
    outro = _make_brand_clip(tmp_path / "src" / "outro.mp4", seconds=3.0)
    monkeypatch.setattr(brand, "INTRO_CLIP", intro)
    monkeypatch.setattr(brand, "OUTRO_CLIP", outro)

    aligned = _write_storyboard(tmp_path, _body_scenes(), 4.0)
    once = brand.apply_plates(aligned, tmp_path / "once.json",
                              tmp_path / "build")
    twice = brand.apply_plates(once, tmp_path / "twice.json",
                               tmp_path / "build")

    first = json.loads(once.read_text(encoding="utf-8"))
    second = json.loads(twice.read_text(encoding="utf-8"))
    assert first == second
    assert len(second["scenes"]) == 4
    assert second["video"]["duration"] == pytest.approx(9.0)


def test_apply_plates_can_skip_brands(tmp_path, monkeypatch):
    intro = _make_brand_clip(tmp_path / "src" / "intro.mp4", seconds=2.0)
    outro = _make_brand_clip(tmp_path / "src" / "outro.mp4", seconds=3.0)
    monkeypatch.setattr(brand, "INTRO_CLIP", intro)
    monkeypatch.setattr(brand, "OUTRO_CLIP", outro)

    aligned = _write_storyboard(tmp_path, _body_scenes(), 4.0)
    out = brand.apply_plates(aligned, tmp_path / "plain.json",
                             tmp_path / "build",
                             intro=False, outro=False)

    sb = Storyboard.load(out)
    assert sb.validate() == []
    assert [s.id for s in sb.scenes] == ["s01", "s02"]
    assert sb.duration == pytest.approx(4.0)


def test_compose_includes_brand_clip_with_its_own_audio(tmp_path):
    """带 clip 场景的契约要产出有音轨的成片，时长等于各片段之和。"""
    build = tmp_path / "build"
    clip = build / "brand" / "intro.mp4"
    audio = build / "brand" / "intro.wav"
    _make_brand_clip(tmp_path / "src" / "intro.mp4", seconds=1.0)
    clip.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(tmp_path / "src" / "intro.mp4"),
         "-an", "-r", "24", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-video_track_timescale", "24000", str(clip)],
        check=True, capture_output=True, text=True,
    )
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(tmp_path / "src" / "intro.mp4"),
         "-vn", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(audio)],
        check=True, capture_output=True, text=True,
    )

    scenes = [
        {"id": "brand_intro", "start": 0.0, "end": 1.0, "type": "clip",
         "subtitle": "Growdu · 深入数据库", "renderer": None, "params": {},
         "h3": None, "clip": "brand/intro.mp4", "audio": "brand/intro.wav"},
        {"id": "s01", "start": 1.0, "end": 2.0, "type": "code",
         "renderer": "blank_scene", "subtitle": "正文一句"},
    ]
    aligned = _write_storyboard(tmp_path, scenes, 2.0,
                                subtitles=[{"start": 1.0, "end": 2.0,
                                            "text": "正文一句"}])
    sb = Storyboard.load(aligned)
    narration = tmp_path / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=1", str(narration)],
        check=True, capture_output=True, text=True,
    )
    out = tmp_path / "out" / "final.mp4"

    compose.compose(sb, build, out, narration=narration)

    info = _probe(out)
    types = {s["codec_type"] for s in info["streams"]}
    assert "video" in types
    assert "audio" in types
    assert float(info["format"]["duration"]) == pytest.approx(2.0, abs=0.15)


def test_real_brand_plates_compose_into_final_video(tmp_path):
    """端到端：真实 3 秒片头片尾接进契约 → 拼出成片。

    这条测试盯的是「真实素材 + 真实流水线」这一条链：
    总时长必须正好是 片头 + 正文 + 片尾，多一帧少一帧都不行。
    """
    if not REAL_INTRO.exists() or not REAL_OUTRO.exists():
        pytest.skip("品牌素材不在仓库中，跳过")

    build = tmp_path / "build"
    aligned = _write_storyboard(
        tmp_path, _body_scenes(), 4.0,
        subtitles=[{"start": 0.0, "end": 2.0, "text": "第一句字幕"},
                   {"start": 2.0, "end": 4.0, "text": "第二句字幕"}],
    )
    branded = brand.apply_plates(aligned, tmp_path / "branded.json", build)
    sb = Storyboard.load(branded)
    assert sb.validate() == []

    intro_dur = sb.scenes[0].duration
    outro_dur = sb.scenes[-1].duration
    assert intro_dur <= brand.MAX_BRAND_SECONDS
    assert outro_dur <= brand.MAX_BRAND_SECONDS

    narration = tmp_path / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=4", str(narration)],
        check=True, capture_output=True, text=True,
    )
    out = tmp_path / "out" / "final.mp4"

    compose.compose(sb, build, out, narration=narration)

    info = _probe(out)
    assert {s["codec_type"] for s in info["streams"]} == {"video", "audio"}
    expected = intro_dur + 4.0 + outro_dur
    assert float(info["format"]["duration"]) == pytest.approx(expected, abs=0.1)

    # 转码后的品牌片必须与正文片段时间基一致，否则 concat 后时长会漂
    for scene in (sb.scenes[0], sb.scenes[-1]):
        clip = build / scene.clip
        streams = _probe(clip)["streams"]
        video = next(s for s in streams if s["codec_type"] == "video")
        assert video["r_frame_rate"] == "24/1"
        assert video["time_base"] == "1/24000"
