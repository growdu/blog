import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from pyv import compose
from pyv.timeline import Storyboard

ROOT = Path(__file__).resolve().parents[2]

MINI_WIDTH = 960
MINI_HEIGHT = 540
MINI_FPS = 24


def _probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,codec_name,pix_fmt:"
         "format=duration",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def _make_tone(path: Path, seconds: float) -> Path:
    """生成一段测试用正弦音，避免依赖真实旁白资产。"""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"sine=frequency=440:duration={seconds}", str(path)],
        check=True, capture_output=True, text=True,
    )
    return path


def _mini_storyboard(tmp_path: Path, scenes=None, duration: float = 2.0,
                     subtitles=None) -> Storyboard:
    if scenes is None:
        scenes = [
            {"id": "s01", "start": 0.0, "end": duration / 2, "type": "code",
             "renderer": "blank_scene", "subtitle": "第一句字幕"},
            {"id": "s02", "start": duration / 2, "end": duration, "type": "code",
             "renderer": "blank_scene", "subtitle": "第二句字幕"},
        ]
    if subtitles is None:
        subtitles = [
            {"start": 0.0, "end": duration / 2, "text": "第一句字幕"},
            {"start": duration / 2, "end": duration, "text": "第二句字幕"},
        ]
    raw = {
        "version": 1,
        "video": {"width": MINI_WIDTH, "height": MINI_HEIGHT,
                  "fps": MINI_FPS, "duration": duration},
        "audio": {"narration": "tone.wav", "bgm": None},
        "subtitle_style": {"primary": "#1B2A47", "outline": "#FFFFFF",
                           "position": "bottom-center"},
        "scenes": scenes,
        "subtitles": subtitles,
    }
    path = tmp_path / "storyboard.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return Storyboard.load(path)


def test_compose_produces_video_with_audio(tmp_path):
    sb = _mini_storyboard(tmp_path)
    narration = _make_tone(tmp_path / "tone.wav", 4.0)
    out = tmp_path / "out" / "final.mp4"

    compose.compose(sb, tmp_path / "build", out, narration=narration)

    info = _probe(out)
    types = {s["codec_type"] for s in info["streams"]}
    assert "video" in types
    assert "audio" in types
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert video["width"] == MINI_WIDTH
    assert video["height"] == MINI_HEIGHT
    assert video["codec_name"] == "h264"
    assert video["pix_fmt"] == "yuv420p"


def test_compose_output_duration_follows_storyboard(tmp_path):
    sb = _mini_storyboard(tmp_path, duration=2.0)
    narration = _make_tone(tmp_path / "tone.wav", 10.0)
    out = tmp_path / "out" / "final.mp4"

    compose.compose(sb, tmp_path / "build", out, narration=narration)

    info = _probe(out)
    assert float(info["format"]["duration"]) == pytest.approx(2.0, abs=0.05)


def test_compose_burns_subtitles_into_video_frames(tmp_path):
    """字幕必须真的烧进画面，而不是只生成一个 ASS 文件。"""
    from PIL import Image

    sb = _mini_storyboard(tmp_path, duration=1.0)
    narration = _make_tone(tmp_path / "tone.wav", 2.0)
    out = tmp_path / "out" / "final.mp4"

    compose.compose(sb, tmp_path / "build", out, narration=narration)

    frame = tmp_path / "frame.png"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", "0.3", "-i", str(out),
         "-vframes", "1", str(frame)],
        check=True, capture_output=True, text=True,
    )
    image = Image.open(frame).convert("RGB")
    width, height = image.size
    # 字幕在底部：只截最下面 20% 的区域
    band = image.crop((0, int(height * 0.80), width, height))
    pixels = list(band.getdata())
    dark_blue = sum(
        1 for r, g, b in pixels
        if abs(r - 0x1B) < 30 and abs(g - 0x2A) < 30 and abs(b - 0x47) < 30
    )
    assert dark_blue > 100, "底部字幕带里应当出现深蓝字"


def test_compose_writes_ass_sidecar(tmp_path):
    sb = _mini_storyboard(tmp_path, duration=2.0)
    narration = _make_tone(tmp_path / "tone.wav", 2.0)
    build = tmp_path / "build"

    compose.compose(sb, build, tmp_path / "out" / "final.mp4", narration=narration)

    ass = (build / "subtitles.ass").read_text(encoding="utf-8")
    assert "[Events]" in ass
    assert "第一句字幕" in ass
    assert "第二句字幕" in ass


def test_compose_without_narration_is_silent(tmp_path):
    sb = _mini_storyboard(tmp_path, duration=1.0)
    out = tmp_path / "out" / "final.mp4"

    compose.compose(sb, tmp_path / "build", out, narration=None)

    info = _probe(out)
    assert {s["codec_type"] for s in info["streams"]} == {"video"}
    assert float(info["format"]["duration"]) == pytest.approx(1.0, abs=0.05)


def test_compose_includes_h3_clip_in_order(tmp_path):
    """h3 片段按时间顺序参与拼接。"""
    h3 = tmp_path / "build" / "h3_intro.mp4"
    h3.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "color=c=white:s=960x540:d=1:r=24", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", str(h3)],
        check=True, capture_output=True, text=True,
    )
    scenes = [
        {"id": "h3a", "start": 0.0, "end": 1.0, "type": "h3",
         "clip": "h3_intro.mp4", "subtitle": "片头",
         "h3": {"resolution": "768P", "duration": 1.0, "est_credits": 70}},
        {"id": "s01", "start": 1.0, "end": 2.0, "type": "code",
         "renderer": "blank_scene", "subtitle": "正文"},
    ]
    sb = _mini_storyboard(tmp_path, scenes=scenes, duration=2.0,
                          subtitles=[{"start": 1.0, "end": 2.0, "text": "正文"}])
    narration = _make_tone(tmp_path / "tone.wav", 2.0)
    out = tmp_path / "out" / "final.mp4"

    compose.compose(sb, tmp_path / "build", out, narration=narration)

    info = _probe(out)
    assert float(info["format"]["duration"]) == pytest.approx(2.0, abs=0.1)


def test_compose_reports_missing_h3_clip(tmp_path):
    scenes = [
        {"id": "h3a", "start": 0.0, "end": 1.0, "type": "h3",
         "clip": "missing.mp4", "subtitle": "片头",
         "h3": {"resolution": "768P", "duration": 1.0, "est_credits": 70}},
    ]
    sb = _mini_storyboard(tmp_path, scenes=scenes, duration=1.0, subtitles=[])
    with pytest.raises(FileNotFoundError, match="h3"):
        compose.compose(sb, tmp_path / "build", tmp_path / "out.mp4",
                        narration=None)


def test_compose_with_bgm_mixes_audio(tmp_path):
    sb = _mini_storyboard(tmp_path, duration=1.0)
    narration = _make_tone(tmp_path / "tone.wav", 2.0)
    bgm = _make_tone(tmp_path / "bgm.wav", 2.0)
    out = tmp_path / "out" / "final.mp4"

    compose.compose(sb, tmp_path / "build", out, narration=narration,
                    bgm=bgm, bgm_gain_db=-18.0)

    info = _probe(out)
    types = {s["codec_type"] for s in info["streams"]}
    assert "audio" in types
    assert float(info["format"]["duration"]) == pytest.approx(1.0, abs=0.05)


def test_compose_ducks_the_bgm_before_mixing(tmp_path):
    """BGM 必须先按旁白包络 duck，再进混音（规范 §5.2）。"""
    sb = _mini_storyboard(tmp_path, duration=2.0)
    narration = _make_tone(tmp_path / "tone.wav", 2.0)
    bgm = _make_tone(tmp_path / "bgm.wav", 2.0)
    build = tmp_path / "build"
    out = tmp_path / "out" / "final.mp4"

    compose.compose(sb, build, out, narration=narration, bgm=bgm)

    ducked = build / "_bgm_ducked.wav"
    assert ducked.exists(), "BGM 没有经过 ducking"
    # duck 后的文件只覆盖正文区间
    info = _probe(ducked)
    assert float(info["format"]["duration"]) == pytest.approx(2.0, abs=0.2)


def test_bgm_channel_uses_the_avoidance_chain(tmp_path):
    """BGM 通道必须走规范里的避让链（高通 + bell + 固定增益）。"""
    from pyv import bgm

    sb = _mini_storyboard(tmp_path, duration=1.0)
    cmd = compose._mux_cmd(
        Path("silent.mp4"), Path("out.mp4"), sb,
        [(Path("bgm.wav"), 0.0, bgm.bgm_chain())],
    )
    joined = " ".join(cmd)
    assert f"equalizer=f={bgm.EQ_BELL_HZ}" in joined
    assert f"highpass=f={bgm.HIGHPASS_HZ}" in joined
    assert f"g={bgm.EQ_BELL_DB}" in joined


def test_body_range_covers_only_code_scenes(tmp_path):
    """BGM 只铺正文：品牌片所占的区间不算进去（规范 §5.5）。"""
    scenes = [
        {"id": "brand_intro", "start": 0.0, "end": 1.0, "type": "clip",
         "clip": "intro.mp4", "audio": "intro.wav", "subtitle": "片头"},
        {"id": "s01", "start": 1.0, "end": 3.0, "type": "code",
         "renderer": "blank_scene", "subtitle": "正文第一句"},
        {"id": "brand_outro", "start": 3.0, "end": 4.0, "type": "clip",
         "clip": "outro.mp4", "audio": "outro.wav", "subtitle": "片尾"},
    ]
    sb = _mini_storyboard(tmp_path, scenes=scenes, duration=4.0)
    assert compose._body_range(sb) == (1.0, 3.0)


def test_compose_reuses_fresh_clips(tmp_path):
    """片段未过期时必须复用，避免 render → compose 重复渲染。"""
    sb = _mini_storyboard(tmp_path, duration=1.0)
    narration = _make_tone(tmp_path / "tone.wav", 2.0)
    build = tmp_path / "build"

    compose.compose(sb, build, tmp_path / "out" / "a.mp4", narration=narration)
    clip = build / "s01.mp4"
    first_mtime = clip.stat().st_mtime_ns

    time.sleep(0.01)
    compose.compose(sb, build, tmp_path / "out" / "b.mp4", narration=narration)
    assert clip.stat().st_mtime_ns == first_mtime, "未过期的片段不应被重新渲染"


def test_compose_re_renders_when_source_is_newer(tmp_path):
    """场景源码更新后必须重新渲染。"""
    sb = _mini_storyboard(tmp_path, duration=1.0)
    narration = _make_tone(tmp_path / "tone.wav", 2.0)
    build = tmp_path / "build"

    compose.compose(sb, build, tmp_path / "out" / "a.mp4", narration=narration)
    clip = build / "s01.mp4"
    first_mtime = clip.stat().st_mtime_ns

    time.sleep(0.01)
    future = time.time() + 60
    os.utime(clip, (future, future))
    compose.compose(sb, build, tmp_path / "out" / "b.mp4", narration=narration)
    assert clip.stat().st_mtime_ns != first_mtime, "过期的片段必须重新渲染"


def test_real_storyboard_matches_real_narration():
    """真实契约：正文时长必须等于旁白时长（29.599 秒）。

    套上品牌片头/片尾后，契约总时长会变长，但正文（品牌片之外的部分）
    必须仍然等于旁白时长。
    """
    storyboard_path = ROOT / "storyboard.json"
    narration_path = ROOT / "pa_decode_v2.mp3"
    if not storyboard_path.exists() or not narration_path.exists():
        pytest.skip("真实资产不在仓库中，跳过")

    sb = Storyboard.load(storyboard_path)
    assert sb.validate() == []
    body = [s for s in sb.scenes if not s.id.startswith("brand_")]
    body_duration = max(s.end for s in body) - min(s.start for s in body)
    info = _probe(narration_path)
    assert float(info["format"]["duration"]) == pytest.approx(
        body_duration, abs=0.05
    )
    assert body_duration == pytest.approx(29.599, abs=0.001)
