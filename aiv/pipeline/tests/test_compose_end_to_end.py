"""End-to-end compose on a fresh clone -- the last mile of the Linux promise.

Why this test exists
--------------------
The AIV CI runs the whole suite on ubuntu, but the compose stage was never
*executed* there.  ``test_compose_integration.py`` needs a real
``storyboard_*.json``, and that is a **product**, not an input -- it is not
in the repository on purpose (see ``aiv/.gitignore``).  So on a fresh Linux
clone that test skips, and nothing on the CI ever ran

    ffmpeg -f concat ...  ->  ffmpeg mux (aac 48kHz stereo)  ->  mp4

which is the very last step of "clone and you can cut a video".  The CI
proved the *pieces* work on Linux (cairo drawing, ffmpeg encode, ffprobe,
font fallback, audio measurement) but not the *whole*.

This test closes that gap with a synthetic episode: two code scenes at the
real resolution, the real narration mp3 and the real BGM wav (both tracked
in git), composed into a real mp4.  The output is then checked against the
spec -- 1920x1080 / 24fps / h264 yuv420p / aac 48kHz stereo /
``video_track_timescale = 24000`` -- because "it produced a file" is not
the claim; "it produced a *broadcastable* file" is.

If a fresh clone cannot produce that file, this goes red.  That is exactly
the promise the "上机指南" makes, so it belongs in the suite that runs on
every Linux push.
"""

from __future__ import annotations

import json
import subprocess

from pyv import compose as compose_mod
from pyv import episodes
from pyv import fonts
from pyv.timeline import (
    Audio,
    Scene,
    Storyboard,
    SubtitleEvent,
    SubtitleStyle,
    Video,
)

AIV_ROOT = episodes.AIV_ROOT
BGM = AIV_ROOT / "music/tracks/series-bed-01.wav"

# 成片时长（秒）。三秒够走完「渲染 → 拼接 → 混音 → 封装」，
# 又不至于让 CI 多花一分钟。
DURATION = 3.0

# 字幕用一个别处不会出现的颜色：背景是白的，场景画的是深蓝块，
# 只有字幕会用洋红。这样「画面里确实有字幕」才能被像素判定认出来。
SUBTITLE_TEXT = "端到端合成冒烟"
SUBTITLE_FILL = "#FF00FF"


def _probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,"
         "time_base,sample_rate,channels:format=duration",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def _narration() -> "object":
    """一期**已入库**的旁白音频。"""
    for ep in episodes.EPISODE_ORDER:
        path = episodes.narration_path(ep)
        if path.is_file():
            return path
    raise AssertionError(
        "仓库里一期旁白都没有——「出片必需的输入要入库」这条口径坏了"
    )


def _storyboard(narration) -> Storyboard:
    """两段正文场景，规格与正式成片一致。"""
    half = DURATION / 2
    scenes = [
        Scene(id="s01", start=0.0, end=half, type="code",
              subtitle="第一段字幕", renderer="sample_scene"),
        Scene(id="s02", start=half, end=DURATION, type="code",
              subtitle="第二段字幕", renderer="sample_scene"),
    ]
    return Storyboard(
        version=1,
        video=Video(width=1920, height=1080, fps=24, duration=DURATION),
        audio=Audio(narration=str(narration), bgm=str(BGM)),
        subtitle_style=SubtitleStyle(primary=SUBTITLE_FILL, outline="#000000"),
        scenes=scenes,
        subtitles=[SubtitleEvent(start=0.0, end=DURATION, text=SUBTITLE_TEXT)],
    )


def _first_frame(path):
    """成片第一帧的像素。"""
    from PIL import Image

    frame = path.with_suffix(".frame.png")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vframes", "1", str(frame)],
        check=True, capture_output=True, text=True,
    )
    return list(Image.open(frame).convert("RGB").getdata())


def test_the_chinese_subtitle_has_real_glyphs_in_the_current_font():
    """中文不能是豆腐块。

    Linux 上字体是回退来的（macOS 是 PingFang SC，Linux 是 Noto/思源），
    这一条正是那道保险：如果回退字体里没有这些字，字幕会变成方框，
    而「文件生成成功」是发现不了的。
    """
    missing = [ch for ch in SUBTITLE_TEXT if fonts.missing_glyph(ch)]
    assert not missing, (
        f"这些字在当前字体（{fonts.font_family()}）里画不出来，会变成豆腐块：{missing}"
    )


def test_a_fresh_clone_can_produce_a_broadcastable_episode(tmp_path):
    """从入库素材直接合成出符合规格的成片。"""
    narration = _narration()
    storyboard = _storyboard(narration)
    assert storyboard.validate() == [], (
        f"合成的 storyboard 不合契约：{storyboard.validate()}"
    )
    assert BGM.is_file(), f"仓库里没有 BGM：{BGM}"

    out = tmp_path / "ep-smoke.mp4"
    compose_mod.compose(storyboard, tmp_path / "build", out,
                        narration=narration, bgm=BGM)

    assert out.is_file(), f"成片没生成：{out}"
    assert out.stat().st_size > 0, "成片是空的"

    info = _probe(out)
    streams = {s["codec_type"]: s for s in info["streams"]}
    assert set(streams) == {"video", "audio"}, f"成片里少了轨道：{list(streams)}"

    video = streams["video"]
    assert video["codec_name"] == "h264"
    assert video["pix_fmt"] == "yuv420p"
    assert (video["width"], video["height"]) == (1920, 1080)
    assert video["r_frame_rate"] == "24/1"
    # 规格钉死的时间基：concat 阶段要求各片段时间基一致
    assert video["time_base"] == "1/24000", (
        f"video_track_timescale 不对：{video['time_base']}"
    )

    audio = streams["audio"]
    assert audio["codec_name"] == "aac"
    assert audio["sample_rate"] == "48000"
    assert audio["channels"] == 2

    assert abs(float(info["format"]["duration"]) - DURATION) < 0.3, (
        f"成片时长不对：{info['format']['duration']}"
    )

    # 画面里必须有字幕的洋红色：白底 + 深蓝块里混进洋红，
    # 只可能是字幕烧上去了（也说明中文字形真的画出来了）。
    pixels = _first_frame(out)
    magenta = sum(1 for r, g, b in pixels if r > 200 and b > 200 and g < 100)
    assert magenta > 50, (
        f"成片第一帧里没有字幕的洋红色（{magenta} 个像素）——字幕没烧进去"
    )
