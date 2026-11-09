"""cairo 逐帧绘制 → ffmpeg 编码。"""
from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import cairo

from pyv.palette import COLORS, FPS, HEIGHT, WIDTH, hex_to_rgb
from pyv.timeline import Scene, Storyboard


# 只有这些模块会改变画面内容，改动它们才需要重渲染
RENDER_INPUT_MODULES = (
    "draw.py", "easing.py", "elephant.py", "palette.py", "subtitle.py",
    "timeline.py",
)


def newest_source_mtime(scene: Scene, extra_mtime: float | None = None) -> float:
    """渲染输入里最新的一个修改时间：场景源码 + 绘图模块 + 契约文件。

    片段只要比这个时间新，就可以认为没过期、直接复用。
    """
    package = Path(__file__).resolve().parent
    candidates = [
        (package / name).stat().st_mtime
        for name in RENDER_INPUT_MODULES
        if (package / name).exists()
    ]
    if extra_mtime:
        candidates.append(extra_mtime)
    # 只看这个场景自己的源码：改一个场景不该作废其它场景的片段
    module = importlib.import_module(scene.renderer or "")
    source = Path(module.__file__ or "")
    if source.exists():
        candidates.append(source.stat().st_mtime)
    return max(candidates)


def clip_is_fresh(clip: Path, scene: Scene,
                  extra_mtime: float | None = None) -> bool:
    """片段比所有渲染输入都新就可以复用。"""
    if not clip.exists():
        return False
    return clip.stat().st_mtime >= newest_source_mtime(scene, extra_mtime)


def _frame_bytes(surface: cairo.ImageSurface) -> bytes:
    """提取 cairo RGB24 表面数据（每像素 4 字节，BGRX 小端序）。

    cairo 的 FORMAT_RGB24 与 ffmpeg 的 bgr0 内存布局一致，
    注意它不是每像素 3 字节，按 rgb24 喂给 ffmpeg 会导致帧数错乱。
    """
    stride = surface.get_stride()
    width = surface.get_width()
    height = surface.get_height()
    data = surface.get_data()
    if stride == width * 4:
        return bytes(data)
    return b"".join(
        bytes(data[y * stride:y * stride + width * 4]) for y in range(height)
    )


def render_scene(scene: Scene, out_path: str | Path,
                 width: int = WIDTH, height: int = HEIGHT, fps: int = FPS,
                 burner=None) -> None:
    """把一个场景渲染成无声 mp4。

    burner 非空时，字幕在渲染阶段直接烧进画面（本机 ffmpeg 无 libass）。
    """
    if not scene.renderer:
        raise ValueError(f"场景 {scene.id} 缺少 renderer")
    module = importlib.import_module(scene.renderer)
    total = max(1, int(round(scene.duration * fps)))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "bgr0",
        "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for i in range(total):
            t = i / (total - 1) if total > 1 else 0.0
            surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
            ctx = cairo.Context(surface)
            ctx.set_source_rgb(*hex_to_rgb(COLORS["bg"]))
            ctx.paint()
            module.render(ctx, t, width, height)
            if burner is not None:
                # 用真实帧时间定位字幕，避免逐场景取整带来的漂移
                burner.draw(ctx, scene.start + i / fps, width, height)
            proc.stdin.write(_frame_bytes(surface))
            surface.flush()
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 渲染失败：{out_path}")


def render_storyboard(storyboard: Storyboard, build_dir: str | Path,
                      burner=None, reuse: bool = False,
                      source_mtime: float | None = None) -> list[Path]:
    """渲染全部 code 场景，返回片段路径列表。

    reuse 为真时，build 目录里未过期的片段会被跳过。
    """
    build_dir = Path(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for scene in storyboard.scenes:
        if scene.type != "code":
            continue
        out = build_dir / f"{scene.id}.mp4"
        if reuse and clip_is_fresh(out, scene, source_mtime):
            outputs.append(out)
            continue
        render_scene(
            scene, out,
            storyboard.video.width, storyboard.video.height, storyboard.video.fps,
            burner=burner,
        )
        outputs.append(out)
    return outputs
