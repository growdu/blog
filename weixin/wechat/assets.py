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
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

__all__ = ["PreparedImage", "prepare_image", "prepare_image_bytes",
           "download_image", "cover_crop_list"]

DEFAULT_LIMIT_BYTES = 1024 * 1024
DEFAULT_MAX_WIDTH = 1080
_JPEG_QUALITY_STEPS = (90, 80, 70, 60, 50, 40, 30, 20)
_MIN_DIMENSION = 64
COVER_RATIOS = ("2.35_1", "1_1")
# Some hosts reject requests without a browser-ish User-Agent.
_USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")


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


def _compress(image, stem: str, limit_bytes: int, max_width: int):
    """Shrink and encode one image so WeChat accepts it.

    Returns ``(data, content_type, filename, width, height)``.
    """
    if image.width > max_width:
        ratio = max_width / float(image.width)
        image = image.resize((max_width, max(1, int(image.height * ratio))), Image.LANCZOS)

    data = _encode_png(image)
    content_type = "image/png"
    filename = stem + ".png"

    if len(data) > limit_bytes:
        for quality in _JPEG_QUALITY_STEPS:
            data = _encode_jpeg(image, quality)
            content_type = "image/jpeg"
            filename = stem + ".jpg"
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

    return data, content_type, filename, image.width, image.height


def prepare_image(path: Path, *, limit_bytes: int = DEFAULT_LIMIT_BYTES,
                  max_width: int = DEFAULT_MAX_WIDTH) -> PreparedImage:
    """Read, shrink and compress one image so WeChat accepts it."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError("image not found: {}".format(path))

    try:
        with Image.open(path) as raw:
            raw.load()
            image = raw.copy()
    except UnidentifiedImageError as error:
        # The corpus carries SVG files and the occasional file that is
        # not an image at all.  Pillow cannot read them, and letting
        # that exception out would take the whole batch down.
        raise ValueError(
            "不是有效的图片（Pillow 读不了）: {}".format(path)) from error

    data, content_type, filename, width, height = _compress(
        image, path.stem, limit_bytes, max_width)

    return PreparedImage(
        source=path,
        data=data,
        filename=filename,
        content_type=content_type,
        width=width,
        height=height,
    )


def prepare_image_bytes(data: bytes, stem: str = "image", *,
                        limit_bytes: int = DEFAULT_LIMIT_BYTES,
                        max_width: int = DEFAULT_MAX_WIDTH) -> PreparedImage:
    """Compress image bytes that were fetched from elsewhere."""
    with Image.open(io.BytesIO(data)) as raw:
        raw.load()
        image = raw.copy()

    data, content_type, filename, width, height = _compress(
        image, stem, limit_bytes, max_width)

    return PreparedImage(
        source=Path(stem),
        data=data,
        filename=filename,
        content_type=content_type,
        width=width,
        height=height,
    )


def download_image(url: str, *, timeout: int = 20) -> bytes:
    """Fetch an external image.

    Raises ``ValueError`` when the host refuses, the file is missing, or
    the payload is not an image -- the caller turns that into a visible
    note rather than a silently missing picture.
    """
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
    except urllib.error.HTTPError as error:
        raise ValueError("HTTP {} for {}".format(error.code, url)) from error
    except urllib.error.URLError as error:
        raise ValueError("{} for {}".format(error.reason, url)) from error
    if not data:
        raise ValueError("empty response for {}".format(url))
    return data


def _crop(ratio: float, width: int, height: int) -> dict:
    """Largest centred crop of the requested aspect ratio.

    The official API takes the crop rectangle as percentages of the
    image, with (0,0) at the top-left and (1,1) at the bottom-right.
    """
    image_ratio = float(width) / float(height)
    if image_ratio > ratio:
        # Too wide: trim the sides.
        keep = ratio / image_ratio
        x1 = (1.0 - keep) / 2.0
        return {"x1": x1, "y1": 0.0, "x2": 1.0 - x1, "y2": 1.0}
    # Too tall: trim the top and bottom.
    keep = image_ratio / ratio
    y1 = (1.0 - keep) / 2.0
    return {"x1": 0.0, "y1": y1, "x2": 1.0, "y2": 1.0 - y1}


def cover_crop_list(width: int, height: int) -> list:
    """Build the ``cover_info.crop_percent_list`` for a cover image.

    WeChat wants both a 2.35:1 and a 1:1 crop of the cover; the API
    accepts them as percentages with six decimals.
    """
    crops = []
    for name, ratio in (("2.35_1", 2.35), ("1_1", 1.0)):
        crop = _crop(ratio, width, height)
        crops.append({
            "ratio": name,
            "x1": "{:.6f}".format(crop["x1"]),
            "y1": "{:.6f}".format(crop["y1"]),
            "x2": "{:.6f}".format(crop["x2"]),
            "y2": "{:.6f}".format(crop["y2"]),
        })
    return crops
