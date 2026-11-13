"""封面：从成片里抽一帧，做成视频号要的两个尺寸。

**为什么是这两个尺寸。** 2026-11-13 在视频号助手的投稿页实测：
上传完视频，「封面预览」下面明摆着**两个槽位**——

| 槽位 | 比例 | 用在哪 |
| --- | --- | --- |
| 个人主页卡片 | **3:4** | 主页 |
| 分享卡片 | **4:3** | 朋友圈、聊天 |

公开口径里的 6:7 / 1080×1260 / 16:9 / 9:16 **一个都不对**（规格 §6.1.2）。
传 16:9 的图进 4:3 的槽位会被居中裁掉左右两边——实测传的 1080×608，
左右各少一块，画面里的字被切掉。

**为什么留白而不是裁。** AIV 的画面是内容很满的幻灯片：标题贴着左边缘，
四个色块铺满整宽。居中裁切会切掉字。所以按「等比缩放 + 白底留白」做——
内容一点不少，代价是 3:4 那张上下留白比较多。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image

# 视频号的两个封面槽位（实测 2026-11-13）
COVER_4X3 = (1080, 810)      # 分享卡片：朋友圈、聊天
COVER_3X4 = (1080, 1440)     # 个人主页卡片：主页
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


def fit_inside(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """等比缩放到刚好装进目标框——不裁切、不拉伸变形。"""
    target_width, target_height = size
    src_width, src_height = image.size
    scale = min(target_width / src_width, target_height / src_height)
    new_size = (max(1, round(src_width * scale)), max(1, round(src_height * scale)))
    return image.resize(new_size, Image.LANCZOS)


def letterbox(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """把画面等比缩放后居中放进目标尺寸的画布，多余的地方留白。

    **为什么留白而不是裁。** 见模块开头：成片是内容很满的幻灯片，
    裁左右会把字切掉。少一点画面总比少一半字强。
    """
    canvas = Image.new("RGB", size, PADDING_COLOR)
    inner = fit_inside(image, size)
    canvas.paste(inner, ((size[0] - inner.width) // 2, (size[1] - inner.height) // 2))
    return canvas


def make_covers(video: str | Path, at: float, out_dir: str | Path) -> dict[str, Path]:
    """抽一帧，做成分享卡片（4:3）与个人主页卡片（3:4）两张封面。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = extract_frame(video, at, out_dir / "_frame.png")
    with Image.open(raw) as frame:
        image = frame.convert("RGB")
        share = letterbox(image, COVER_4X3)
        share_path = out_dir / "cover-4x3.jpg"
        share.save(share_path, quality=92)

        profile = letterbox(image, COVER_3X4)
        profile_path = out_dir / "cover-3x4.jpg"
        profile.save(profile_path, quality=92)
    raw.unlink(missing_ok=True)
    return {"4x3": share_path, "3x4": profile_path}
