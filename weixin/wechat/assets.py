"""Prepare local images for WeChat.

WeChat's body-image endpoint accepts JPG/PNG only and caps a file at
1 MB; anything larger is rejected outright.  Screenshots in this blog
routinely exceed that, so every image is measured and compressed before
it is uploaded.

Images wider than the WeChat body width (1080 logical pixels) are
scaled down: WeChat would scale them anyway, and downscaling here keeps
text in screenshots legible.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

__all__ = ["PreparedImage", "prepare_image"]

DEFAULT_LIMIT_BYTES = 1024 * 1024
DEFAULT_MAX_WIDTH = 1080
_JPEG_QUALITY_STEPS = (90, 80, 70, 60, 50, 40, 30, 20)
_MIN_DIMENSION = 64


@dataclass(frozen=True)
class PreparedImage:
    """An image ready to be uploaded to WeChat."""

    source: Path
    data: bytes
    filename: str
    content_type: str
    width: int
    height: int


def _encode_png(image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _encode_jpeg(image, quality: int) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def prepare_image(path: Path, *, limit_bytes: int = DEFAULT_LIMIT_BYTES,
                  max_width: int = DEFAULT_MAX_WIDTH) -> PreparedImage:
    """Read, shrink and compress one image so WeChat accepts it."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError("image not found: {}".format(path))

    with Image.open(path) as raw:
        raw.load()
        image = raw.copy()

    if image.width > max_width:
        ratio = max_width / float(image.width)
        image = image.resize((max_width, max(1, int(image.height * ratio))), Image.LANCZOS)

    data = _encode_png(image)
    content_type = "image/png"
    filename = path.stem + ".png"

    if len(data) > limit_bytes:
        for quality in _JPEG_QUALITY_STEPS:
            data = _encode_jpeg(image, quality)
            content_type = "image/jpeg"
            filename = path.stem + ".jpg"
            if len(data) <= limit_bytes:
                break

    # A pathological image (pure noise) stays too big at every quality.
    # Shrink the picture until it fits: a slightly blurry picture is
    # better than a rejected upload.
    while len(data) > limit_bytes and min(image.size) > _MIN_DIMENSION:
        image = image.resize(
            (max(1, int(image.width * 0.75)), max(1, int(image.height * 0.75))),
            Image.LANCZOS,
        )
        data = _encode_jpeg(image, 60)

    return PreparedImage(
        source=path,
        data=data,
        filename=filename,
        content_type=content_type,
        width=image.width,
        height=image.height,
    )
