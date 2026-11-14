"""封面：抽一帧。

**抖音的封面规格没有公开文档，我们也没投过一条，所以这里不猜比例。**

短视频平台的信息流是 9:16 全屏，但主页卡片与列表缩略图的比例各家不一样；
抖音创作者后台的封面槽位长什么样、会不会裁，公开资料里查不到。
猜一个比例去做版式，猜错了就是白做——而且错的那版会混进发布包，
让人以为「封面已经做好了」。

所以这一版出**与成片同比例**的一张图：不缩放、不裁切，就是那一帧。
清单里会写明「比例未实测，投完一条看后台实际怎么裁再定」。

真到了要出竖版封面那天，改的是这里的一个常量，不是重写这一层。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image


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


def make_cover(video: str | Path, at: float, out_dir: str | Path) -> Path:
    """抽一帧，存成 `cover.jpg`。

    **保持成片的原始比例**——见模块开头：抖音的封面规格未实测，
    猜比例不如先给原图。
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = extract_frame(video, at, out_dir / "_frame.png")
    cover = out_dir / "cover.jpg"
    with Image.open(raw) as frame:
        frame.convert("RGB").save(cover, quality=92)
    raw.unlink(missing_ok=True)
    return cover
