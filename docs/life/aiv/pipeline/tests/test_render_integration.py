import json
import subprocess

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
