import io

import pytest
from PIL import Image

from wechat.assets import prepare_image


def _png(width: int, height: int, color=(200, 30, 30)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _noise_png(width: int, height: int) -> bytes:
    """A noisy image: PNG cannot compress it, so it stays large."""
    import random
    random.seed(7)
    image = Image.new("RGB", (width, height))
    image.putdata([
        (random.randrange(256), random.randrange(256), random.randrange(256))
        for _ in range(width * height)
    ])
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_prepare_image_keeps_small_png(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(_png(100, 80))
    prepared = prepare_image(path)
    assert prepared.content_type == "image/png"
    assert prepared.width == 100
    assert prepared.height == 80
    assert len(prepared.data) < 1048576
    assert prepared.filename == "a.png"


def test_prepare_image_shrinks_wide_image_to_max_width(tmp_path):
    path = tmp_path / "wide.png"
    path.write_bytes(_png(2400, 1200))
    prepared = prepare_image(path, max_width=1080)
    assert prepared.width == 1080
    assert prepared.height == 540


def test_prepare_image_compresses_oversized_file(tmp_path):
    path = tmp_path / "big.png"
    path.write_bytes(_noise_png(400, 400))
    prepared = prepare_image(path, limit_bytes=50000)
    assert len(prepared.data) <= 50000


def test_prepare_image_falls_back_to_jpeg_when_png_is_too_big(tmp_path):
    path = tmp_path / "big.png"
    path.write_bytes(_noise_png(400, 400))
    prepared = prepare_image(path, limit_bytes=50000)
    assert prepared.content_type == "image/jpeg"
    assert prepared.filename == "big.jpg"


def test_prepare_image_shrinks_pathological_image_until_it_fits(tmp_path):
    """Pure noise cannot be compressed by quality alone: the picture shrinks."""
    path = tmp_path / "noise.png"
    path.write_bytes(_noise_png(400, 400))
    prepared = prepare_image(path, limit_bytes=20000)
    assert len(prepared.data) <= 20000
    assert prepared.width < 400


def test_prepare_image_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        prepare_image(tmp_path / "nope.png")


def test_prepare_image_reports_source_path(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(_png(10, 10))
    assert prepare_image(path).source == path


def test_prepare_image_handles_rgba_png(tmp_path):
    path = tmp_path / "alpha.png"
    buffer = io.BytesIO()
    Image.new("RGBA", (50, 50), (10, 20, 30, 128)).save(buffer, format="PNG")
    path.write_bytes(buffer.getvalue())
    prepared = prepare_image(path)
    assert len(prepared.data) > 0
