"""Prepare images for Toutiao.

Toutiao will not render an external image: every picture has to be uploaded
into the editor by hand.  That is why the Toutiao version keeps at most
three of them.  This module does the part a machine can do -- convert to
webp, squeeze under the size cap, crop a cover to 3:4.

Only local images are handled.  A remote URL is never fetched: the package
must not depend on the network, and the uploader has to download such a
picture by hand anyway.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "AssetNotFound", "ImageTooLarge", "PreparedImage", "RemoteAsset",
    "can_make_cover", "is_remote", "make_cover", "prepare_image",
    "resolve_asset",
]

# The quality ladder ``prepare_image()`` walks down when the picture is too
# big.  The cover gets its own quality: it is the one image the reader sees
# first, and it is cropped down afterwards.
_QUALITIES = (85, 75, 65, 55)
_COVER_QUALITY = 88


class ImageTooLarge(ValueError):
    """The image cannot be squeezed under the platform limit."""


class RemoteAsset(ValueError):
    """The asset path is a remote URL -- there is no local file."""


class AssetNotFound(ValueError):
    """The asset path does not resolve to a file inside the site."""


@dataclass(frozen=True)
class PreparedImage:
    """One image that is ready to upload."""

    source: str
    path: Path
    width: int
    height: int
    size_bytes: int


def is_remote(path: str) -> bool:
    """Whether an asset path points at a remote file.

    Toutiao will not render an external image anyway, and the package
    must not depend on the network: a remote image is a manual step for
    the person uploading, not something this module fetches.

    Takes the path as it was written in the post -- a ``str``.  A ``Path``
    would have swallowed the ``//`` of the scheme on the way in, so it is
    not accepted here.
    """
    return path.strip().lower().startswith(("http://", "https://"))


def resolve_asset(path: str, posts_dir: Path) -> Path:
    """Resolve an asset path from a post to a real file.

    ``tools/sync-hexo.py`` rewrites every image reference to
    ``images/<path relative to docs/>`` and copies the files to
    ``source/images/``.  So an asset path resolves against the ``source/``
    root -- the parent of ``_posts/``.

    Three things are refused here, and each of them says what went wrong:

    - a remote URL: the package must not depend on the network;
    - a path that resolves to no file: a silent fallback would ship a
      package with a missing picture and no word about it;
    - a path that leaves the site root: an asset path is a relative path
      inside the site, never a way out of it.
    """
    if is_remote(path):
        raise RemoteAsset("外链图不在本地：{}".format(path))
    site_root = Path(posts_dir).parent.resolve()
    candidate = Path(path)
    resolved = candidate.resolve() if candidate.is_absolute() else (site_root / candidate).resolve()
    if resolved != site_root and site_root not in resolved.parents:
        raise AssetNotFound(
            "图路径跑出了站点根目录 {}：{}".format(site_root, path)
        )
    if not resolved.is_file():
        raise AssetNotFound("找不到图文件：{}（按 {} 解析）".format(path, site_root))
    return resolved


def prepare_image(src: Path, dst: Path, max_bytes: int) -> PreparedImage:
    """Convert an image to webp, shrinking until it fits ``max_bytes``.

    Two levers are pulled, in this order: the quality of the webp, and --
    when even the lowest quality is too big -- the size of the picture
    itself.  When neither is enough the picture is refused rather than
    written out over the limit: a package that ships an oversized image is
    a package the platform will reject at upload time.
    """
    from PIL import Image

    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src) as opened:
        image = opened.convert("RGB")
        for quality in _QUALITIES:
            image.save(dst, "WEBP", quality=quality, method=6)
            if dst.stat().st_size <= max_bytes:
                break
        else:
            image.thumbnail((max(image.width // 2, 1), max(image.height // 2, 1)))
            image.save(dst, "WEBP", quality=_QUALITIES[-1], method=6)
        # ``image.size`` is read after the shrink, so the reported size is
        # the size of the file that was actually written.
        width, height = image.size

    size = dst.stat().st_size
    if size > max_bytes:
        # Do not leave the oversized file behind: it would sit in the
        # output directory looking like a finished picture.
        dst.unlink(missing_ok=True)
        raise ImageTooLarge(
            "{} 压缩后仍有 {} 字节，超过上限 {}".format(src.name, size, max_bytes)
        )
    return PreparedImage(source=str(src), path=dst, width=width, height=height, size_bytes=size)


def _parse_ratio(ratio: str) -> tuple[int, int]:
    """The ``W:H`` of a ratio, as two positive integers."""
    parts = ratio.split(":")
    if len(parts) != 2:
        raise ValueError("封面比例必须是 W:H，实际是 {!r}".format(ratio))
    try:
        width, height = (int(part) for part in parts)
    except ValueError:
        raise ValueError("封面比例必须是两个整数，实际是 {!r}".format(ratio)) from None
    if width <= 0 or height <= 0:
        raise ValueError("封面比例必须为正数，实际是 {!r}".format(ratio))
    return width, height


def _cover_box(width: int, height: int, target_width: int, target_height: int) -> tuple:
    """The centre crop of ``width`` x ``height`` at the given ratio.

    The crop is an exact multiple of the ratio -- ``target_width * k`` by
    ``target_height * k`` -- because rounding the crop size instead leaves
    an off-by-one ratio behind: a 640x960 picture cropped to 640x853 is
    2560:2559, not 3:4.
    """
    scale = min(width // target_width, height // target_height)
    crop_width = target_width * scale
    crop_height = target_height * scale
    left = (width - crop_width) // 2
    top = (height - crop_height) // 2
    return (left, top, left + crop_width, top + crop_height)


def _cover_plan(src: Path, ratio: str, min_pixels: tuple) -> tuple:
    """The crop box for the cover of ``src`` -- the one ruler.

    ``can_make_cover()`` and ``make_cover()`` both go through this, so the
    two can never disagree about whether a picture can be a cover: the
    crop is what counts, because a 3:4 crop of a wide picture throws away
    part of its width and the leftover can fall under the platform
    minimum even when the source cleared it.
    """
    from PIL import Image

    target_width, target_height = _parse_ratio(ratio)
    with Image.open(src) as image:
        width, height = image.size
    return _cover_box(width, height, target_width, target_height)


def can_make_cover(src: Path, ratio: str, min_pixels: tuple) -> bool:
    """Whether this image can produce a valid cover of ``ratio``."""
    left, top, right, bottom = _cover_plan(Path(src), ratio, min_pixels)
    min_width, min_height = min_pixels
    return right - left >= min_width and bottom - top >= min_height


def make_cover(src: Path, dst: Path, ratio: str, min_pixels: tuple) -> PreparedImage:
    """Crop the centre of ``src`` to ``ratio`` and save it as webp.

    The cover has to clear the platform minimum *after* the crop: a 3:4
    crop of a small picture is smaller than the picture.

    The picture handed in is the webp that ``prepare_image()`` produced --
    cropping the original would work on a file the platform never sees,
    and would drop the size cap that file was already squeezed under.
    """
    from PIL import Image

    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    left, top, right, bottom = _cover_plan(src, ratio, min_pixels)
    min_width, min_height = min_pixels
    crop_width, crop_height = right - left, bottom - top
    if crop_width < min_width or crop_height < min_height:
        raise ValueError(
            "裁完的封面只有 {}×{}，小于下限 {}×{}".format(
                crop_width, crop_height, min_width, min_height
            )
        )

    with Image.open(src) as opened:
        image = opened.convert("RGB")
        cropped = image.crop((left, top, right, bottom))
        cropped.save(dst, "WEBP", quality=_COVER_QUALITY, method=6)

    return PreparedImage(
        source=str(src),
        path=dst,
        width=crop_width,
        height=crop_height,
        size_bytes=dst.stat().st_size,
    )
