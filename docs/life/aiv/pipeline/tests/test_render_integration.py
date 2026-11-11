import json
import os
import subprocess

from pyv import character
from pyv import render
from pyv.timeline import Scene


def _probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=width,height,r_frame_rate,codec_name,pix_fmt:format=duration",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def test_render_scene_produces_expected_media(tmp_path):
    scene = Scene(id="s01", start=0.0, end=1.0, type="code",
                  subtitle="测试", renderer="sample_scene")
    out = tmp_path / "s01.mp4"
    render.render_scene(scene, out, width=320, height=180, fps=24)
    info = _probe(out)
    stream = info["streams"][0]
    assert stream["width"] == 320
    assert stream["height"] == 180
    assert stream["codec_name"] == "h264"
    assert stream["pix_fmt"] == "yuv420p"
    assert stream["r_frame_rate"] == "24/1"
    assert abs(float(info["format"]["duration"]) - 1.0) < 0.05


def test_render_scene_output_has_non_white_pixels(tmp_path):
    """场景必须真的画了东西，不能是一整块白底。"""
    from PIL import Image
    scene = Scene(id="s01", start=0.0, end=1.0, type="code",
                  subtitle="测试", renderer="sample_scene")
    out = tmp_path / "s01.mp4"
    render.render_scene(scene, out, width=320, height=180, fps=24)
    frame = tmp_path / "frame.png"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(out), "-vframes", "1", str(frame)],
        check=True, capture_output=True, text=True)
    pixels = list(Image.open(frame).convert("RGB").getdata())
    assert any(pixel != (255, 255, 255) for pixel in pixels)


def test_render_scene_requires_renderer(tmp_path):
    scene = Scene(id="s01", start=0.0, end=1.0, type="code", subtitle="测试", renderer=None)
    try:
        render.render_scene(scene, tmp_path / "x.mp4", width=64, height=64)
    except ValueError as exc:
        assert "renderer" in str(exc)
    else:
        raise AssertionError("缺少 renderer 时应当报错")


def test_clip_is_stale_when_the_character_asset_changes(tmp_path, monkeypatch):
    """换了形象素材，已经渲染好的片段必须作废重渲。

    只看 Python 模块的修改时间发现不了素材换掉了——小象重新生成、
    戴眼镜、换配色，模块一个字节没动，片段却还是旧形象。
    """
    asset = tmp_path / "mascot.png"
    asset.write_bytes(b"not-really-a-png")
    monkeypatch.setattr(character, "STATIC_IMAGE", asset)
    scene = Scene(id="s01", start=0.0, end=1.0, type="code",
                  subtitle="测试", renderer="sample_scene")
    out = tmp_path / "s01.mp4"
    out.write_bytes(b"old clip")

    fresh = max(render.newest_source_mtime(scene), asset.stat().st_mtime) + 10
    os.utime(out, (fresh, fresh))
    assert render.clip_is_fresh(out, scene), "片段比所有输入都新，应该复用"

    stale = asset.stat().st_mtime - 1
    os.utime(out, (stale, stale))
    assert not render.clip_is_fresh(out, scene), \
        "素材比片段新，片段必须作废重渲"
