"""封面：从成片里抽一帧，裁成B站要的尺寸。

B站《封面上传》：jpeg/png、≤ 5 MB、**建议 ≥ 1146×717、最低 ≥ 960×600**。

**按比例居中裁切再缩放，不拉伸变形。** 直接 `resize` 到目标尺寸会把
16:9 的画面横向压扁——封面变形在信息流里一眼就能看出来。

裁的方向由两个比例决定：源比目标**宽**（16:9 = 1.78 > 1146:717 = 1.60）
时切左右两边，源比目标**窄**时切上下。切错方向会切掉画面主体。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image

# B站建议尺寸（同时满足「最低 960×600」）
COVER_SIZE = (1146, 717)
COVER_MIN = (960, 600)
# 《封面上传》：封面 ≤ 5 MB
COVER_MAX_BYTES = 5 * 1024 * 1024


def extract_frame(video: str | Path, at: float, out_path: str | Path) -> Path:
    """抽出某一时刻的一帧。"""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([
        "ffmpeg", "-y", "-ss", f"{at:.3f}", "-i", str(video),
        "-frames:v", "1", str(out),
    ], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"抽帧失败：{(proc.stderr or '')[-400:]}")
    if not out.is_file():
        # ffmpeg 定位到成片末尾之后会「成功」但一个画面也不输出。
        # 那时候它退出码是 0，不检查文件的话就会把一个不存在的路径交给下一步。
        raise RuntimeError(
            f"抽帧失败：{at:.3f}s 处没有画面（取帧点超出成片时长？）")
    return out


def fit_cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """按目标比例居中裁切再缩放——不拉伸变形。"""
    target_width, target_height = size
    src_width, src_height = image.size
    scale = max(target_width / src_width, target_height / src_height)
    crop_width = min(src_width, max(1, round(target_width / scale)))
    crop_height = min(src_height, max(1, round(target_height / scale)))
    left = (src_width - crop_width) // 2
    top = (src_height - crop_height) // 2
    cropped = image.crop((left, top, left + crop_width, top + crop_height))
    return cropped.resize(size, Image.LANCZOS)


def make_cover(video: str | Path, at: float, out_path: str | Path) -> Path:
    """抽一帧，裁成B站要的尺寸，写成 jpeg。"""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = extract_frame(video, at, out.parent / "_frame.png")
    try:
        with Image.open(raw) as frame:
            image = fit_cover(frame.convert("RGB"), COVER_SIZE)
            image.save(out, format="JPEG", quality=92)
    finally:
        raw.unlink(missing_ok=True)
    if out.stat().st_size > COVER_MAX_BYTES:
        raise RuntimeError(
            f"封面 {out.stat().st_size} 字节，超过平台上限 {COVER_MAX_BYTES}")
    return out
