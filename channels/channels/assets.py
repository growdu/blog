"""封面：从成片里抽一帧，裁成两个尺寸。

**为什么出两张。** 公开口径对「横版视频的封面会不会被裁」互相矛盾：
一说视频号封面比例是竖版 6:7（1080×1260）与横版 16:9（1080×608），
一说朋友圈卡片、聊天窗口、主页、发现页全部以 9:16 竖屏展示封面，
传 16:9 会被裁左右或加黑边。

既然是人工发布，两张都给、让人在真实界面上看一眼，
比赌哪个口径对更省事（规格 §6.1.2）。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image

# 视频号封面尺寸
COVER_16X9 = (1080, 608)
COVER_9X16 = (1080, 1920)
# 品牌背景是白色，留白就用白色，视觉上不突兀。
PADDING_COLOR = (255, 255, 255)


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


def make_covers(video: str | Path, at: float, out_dir: str | Path) -> dict[str, Path]:
    """抽一帧，裁成横版与竖框版两张封面。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = extract_frame(video, at, out_dir / "_frame.png")
    with Image.open(raw) as frame:
        image = frame.convert("RGB")
        wide = fit_cover(image, COVER_16X9)
        wide_path = out_dir / "cover-16x9.jpg"
        wide.save(wide_path, quality=92)

        canvas = Image.new("RGB", COVER_9X16, PADDING_COLOR)
        canvas.paste(wide, (0, (COVER_9X16[1] - COVER_16X9[1]) // 2))
        tall_path = out_dir / "cover-9x16.jpg"
        canvas.save(tall_path, quality=92)
    raw.unlink(missing_ok=True)
    return {"16x9": wide_path, "9x16": tall_path}
