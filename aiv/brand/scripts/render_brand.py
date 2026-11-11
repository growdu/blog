#!/usr/bin/env python3
"""Growdu 专属片头 / 片尾渲染。

产出 1920×1080 / 24fps / 时长 < 3 秒 的两支品牌片：
  brand/clips/growdu_intro_3s_1080p.mp4
  brand/clips/growdu_outro_3s_1080p.mp4

技术路线（与 pipeline/pyv/render.py 一致的 cairo 逐帧渲染）：

    AI 生成的纯环境背景底板（无角色、无文字）
      + canonical 小象姿态图（透明底 PNG，代码合成）
      + 真实字体绘制的文字（cairo + PingFang SC）
      → rawvideo 管道 → ffmpeg 编码

为什么不用 H3 视频生成：H3 最短 4 秒，做不出 3 秒以内的片头。
为什么文字用代码渲染：模型生成的中英文会乱码（见 brand/scripts/fix_plates.py）。

素材：
  brand/assets/bg_intro.png              AI 背景（深蓝数据中心）
  brand/assets/bg_outro.png              AI 背景（蓝调城市天际线）
  brand/assets/growdu_pose_thumbsup_nobg.png   小象 · 点赞姿态（透明底）
  brand/assets/growdu_pose_wave_nobg.png       小象 · 挥手姿态（透明底）
  brand/audio/voice_intro.mp3           片头旁白（定稿音色）
  brand/audio/voice_outro.mp3           片尾旁白（定稿音色）
  brand/audio/intro_mix.wav             片头成品音轨（旁白+配乐）
  brand/audio/outro_mix.wav             片尾成品音轨（旁白+配乐）

用法：
  python3 scripts/render_brand.py            # 渲染两支片子
  python3 scripts/render_brand.py --intro    # 只渲染片头
  python3 scripts/render_brand.py --outro    # 只渲染片尾
"""
from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

import cairo
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
BRAND = HERE.parent
AIV = BRAND.parent
ASSETS = BRAND / "assets"
CLIPS = BRAND / "clips"

W, H = 1920, 1080
FPS = 24
DURATION = 2.833          # 68 帧 ≈ 2.833 秒，留出淡出余量
FRAMES = int(round(DURATION * FPS))
TIMESCALE = FPS * 1000    # 与流水线一致：concat 要求各片段时间基相同

# 片头 / 片尾的文案。文字一律用真实字体在 cairo 阶段渲染，模型不碰。
# 片尾副标题按《人格规范》§8 改写过——原「与你一起探索数据库的无边世界」
# 是营销腔，换成「把踩过的坑写成方法」，同时命中「现场验证者」与「方法论者」。
INTRO_TAGLINE = "Database · Knowledge · Growth"
INTRO_CAPTION = "深入数据库 · 分享技术之美"
OUTRO_SUBTITLE = "Growdu · 把踩过的坑写成方法"

# 旁白台词。音色与参数见《形象与音色规范》§2.2；
# 重新合成：python3 ../voice/scripts/synthesize_narration.py --text "<台词>" --out <路径>
INTRO_NARRATION = "欢迎来到 growdu，深入数据库。"
OUTRO_NARRATION = "下次卡住的时候，记得回来。"

FONT = "PingFang SC"
WHITE = (1.0, 1.0, 1.0)
AMBER = (245 / 255, 166 / 255, 35 / 255)
DEEP = (43 / 255, 76 / 255, 126 / 255)
LIGHT = (214 / 255, 233 / 255, 250 / 255)


# ---------------------------------------------------------------- 工具

def pil_to_cairo(image: Image.Image) -> cairo.ImageSurface:
    """PIL RGBA（直通 alpha）→ cairo ARGB32（预乘 + BGRA 字节序）。"""
    arr = np.array(image.convert("RGBA"))
    alpha = arr[..., 3:4].astype(np.uint16)
    rgb = (arr[..., :3].astype(np.uint16) * alpha // 255).astype(np.uint8)
    bgra = np.concatenate(
        [rgb[..., 2:3], rgb[..., 1:2], rgb[..., 0:1], arr[..., 3:4]], axis=2
    ).astype(np.uint8)
    return cairo.ImageSurface.create_for_data(
        bgra, cairo.FORMAT_ARGB32, image.width, image.height, image.width * 4
    )


def subject_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    """取非透明区域的包围盒，用来定位角色的真实脚底。

    AI 生成的透明底素材四周会留白（画布底边 != 脚底），
    直接用画布高度算接地阴影会错位，必须按主体实际像素来。
    """
    alpha = np.array(image.convert("RGBA"))[..., 3]
    rows = np.flatnonzero(alpha.max(axis=1) > 8)
    cols = np.flatnonzero(alpha.max(axis=0) > 8)
    if rows.size == 0 or cols.size == 0:
        return (0, 0, image.width, image.height)
    return (int(cols[0]), int(rows[0]), int(cols[-1]), int(rows[-1]))


def surface_bytes(surface: cairo.ImageSurface) -> bytes:
    """提取 RGB24 表面数据（每像素 4 字节，BGRX 小端序）。

    cairo 的 FORMAT_RGB24 与 ffmpeg 的 bgr0 内存布局一致。
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


def clamp01(t: float) -> float:
    return 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)


def ease_out(t: float) -> float:
    t = clamp01(t)
    return 1.0 - (1.0 - t) ** 3


def ease_in_out(t: float) -> float:
    t = clamp01(t)
    if t < 0.5:
        return 2 * t * t
    return 1.0 - ((-2 * t + 2) ** 2) / 2


def text(ctx, s: str, x: float, y: float, size: float, color,
         anchor: str = "left", bold: bool = False, alpha: float = 1.0) -> None:
    ctx.set_source_rgba(color[0], color[1], color[2], alpha)
    ctx.select_font_face(
        FONT, cairo.FONT_SLANT_NORMAL,
        cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL,
    )
    ctx.set_font_size(size)
    width = ctx.text_extents(s).width
    if anchor == "center":
        x -= width / 2
    elif anchor == "right":
        x -= width
    ctx.move_to(x, y)
    ctx.show_text(s)


def draw_contact_shadow(ctx, cx: float, base_y: float, width: float,
                        color, alpha: float) -> None:
    """接地阴影：椭圆软阴影，让角色「站」在地面上而不是浮着。"""
    if alpha <= 0.001:
        return
    height = width * 0.13
    ctx.save()
    grad = cairo.RadialGradient(cx, base_y, 0, cx, base_y, width * 0.5)
    grad.add_color_stop_rgba(0.0, color[0], color[1], color[2], alpha)
    grad.add_color_stop_rgba(0.6, color[0], color[1], color[2], alpha * 0.45)
    grad.add_color_stop_rgba(1.0, color[0], color[1], color[2], 0.0)
    ctx.set_source(grad)
    ctx.translate(cx, base_y)
    ctx.scale(1.0, height / (width * 0.5))
    ctx.translate(-cx, -base_y)
    ctx.arc(cx, base_y, width * 0.5, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()


def draw_scrim(ctx, color, start_x: float, end_x: float,
               max_alpha: float) -> None:
    """横向渐变遮罩：文字区一侧逐渐压暗/压亮，保证文字可读。

    AI 背景的亮部（服务器灯带、天际线）会吃掉文字对比度，
    这里在文字区铺一层单向渐变，既不遮挡形象，也保证字幕读得清。
    """
    grad = cairo.LinearGradient(start_x, 0, end_x, 0)
    grad.add_color_stop_rgba(0.0, color[0], color[1], color[2], 0.0)
    grad.add_color_stop_rgba(0.35, color[0], color[1], color[2], max_alpha * 0.55)
    grad.add_color_stop_rgba(1.0, color[0], color[1], color[2], max_alpha)
    ctx.set_source(grad)
    ctx.rectangle(start_x, 0, end_x - start_x, H)
    ctx.fill()


def draw_cover(ctx, image: Image.Image, zoom: float, focus_x: float,
               focus_y: float, alpha: float = 1.0) -> None:
    """把图片按 cover 方式铺满画布，支持缩放与焦点偏移。"""
    iw, ih = image.size
    scale = max(W / iw, H / ih) * zoom
    dw, dh = iw * scale, ih * scale
    dx = (W - dw) * focus_x
    dy = (H - dh) * focus_y
    tmp = image.resize((max(1, int(dw)), max(1, int(dh))), Image.LANCZOS)
    surf = pil_to_cairo(tmp)
    if alpha >= 1.0:
        ctx.set_source_surface(surf, dx, dy)
    else:
        ctx.push_group()
        ctx.set_source_surface(surf, dx, dy)
        ctx.paint()
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(alpha)
    ctx.paint()


# ---------------------------------------------------------------- 片头

def render_intro_frame(t: float, bg: Image.Image,
                       char: cairo.ImageSurface,
                       foot_ratio: float) -> cairo.ImageSurface:
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    ctx = cairo.Context(surface)

    # 背景：缓慢推近，焦点偏右（把左侧留给角色）
    zoom = 1.0 + 0.07 * ease_in_out(t)
    draw_cover(ctx, bg, zoom, 0.72, 0.5)

    # 遮罩：右侧压暗，保证白字可读（服务器灯带很亮）
    draw_scrim(ctx, (0.02, 0.06, 0.16), W * 0.30, W, 0.62)

    # 角色：从左侧滑入 + 淡入，带轻微上下浮动
    appear = ease_out((t - 0.06) / 0.34)
    ch_h = H * 0.80
    ch_w = char.get_width() * ch_h / char.get_height()
    bob = math.sin(t * math.pi * 1.6) * H * 0.012
    ch_x = -ch_w * 0.30 + (W * 0.02 + ch_w * 0.30) * appear
    # 让「脚底」落在地平线上，而不是让图片画布底边落在地平线上
    ground_y = H * 0.95
    ch_y = ground_y - ch_h * foot_ratio + bob * appear
    foot_y = ch_y + ch_h * foot_ratio
    draw_contact_shadow(ctx, ch_x + ch_w * 0.5, foot_y,
                        ch_w * 0.62, (0.01, 0.03, 0.10), 0.62 * appear)
    if appear > 0.001:
        ctx.push_group()
        ctx.translate(ch_x, ch_y)
        ctx.scale(ch_w / char.get_width(), ch_h / char.get_height())
        ctx.set_source_surface(char, 0, 0)
        ctx.paint()
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(appear)

    # 文字组：主标 + 标语 + 胶囊标签
    tw = ease_out((t - 0.22) / 0.40)
    tx = W * 0.475 + (1 - tw) * W * 0.03
    ty = H * 0.355 + (1 - tw) * H * 0.022

    text(ctx, "Growdu", tx, ty, 142, WHITE, bold=True, alpha=tw)

    # 标语：说明文字
    text(ctx, INTRO_TAGLINE, tx, ty + 64, 40,
         LIGHT, alpha=tw * 0.95)

    # 胶囊标签：深色底 + 亮蓝边，保证在深背景上清晰可读
    cap = ease_out((t - 0.42) / 0.40)
    cap_text = INTRO_CAPTION
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(42)
    cap_w = ctx.text_extents(cap_text).width
    pad = 38
    bx, by = tx - pad, ty + 104
    bw, bh = cap_w + pad * 2, 82
    ctx.set_source_rgba(0.02, 0.12, 0.30, 0.55 * cap)
    ctx.rectangle(bx, by, bw, bh)
    ctx.fill()
    ctx.set_source_rgba(0.35, 0.78, 1.0, 0.95 * cap)
    ctx.set_line_width(3.0)
    ctx.rectangle(bx, by, bw, bh)
    ctx.stroke()
    text(ctx, cap_text, bx + pad, by + 55, 42, WHITE, bold=True, alpha=cap)

    # 整体淡入 / 淡出
    fade_in = clamp01(t / 0.10)
    fade_out = clamp01((1.0 - t) / 0.12)
    fade = min(fade_in, fade_out)
    if fade < 1.0:
        ctx.set_source_rgba(0, 0, 0, 1 - fade)
        ctx.paint()
    return surface


# ---------------------------------------------------------------- 片尾

def render_outro_frame(t: float, bg: Image.Image,
                       char: cairo.ImageSurface,
                       foot_ratio: float) -> cairo.ImageSurface:
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    ctx = cairo.Context(surface)

    # 背景：缓慢拉远，焦点偏右
    zoom = 1.06 - 0.05 * ease_in_out(t)
    draw_cover(ctx, bg, zoom, 0.70, 0.42)

    # 遮罩：右侧压白（背景本身是浅蓝天空，天际线会吃掉深蓝字的对比度）
    draw_scrim(ctx, (0.88, 0.94, 1.0), W * 0.30, W, 0.80)

    # 角色：挥手，从左侧滑入
    appear = ease_out((t - 0.05) / 0.32)
    ch_h = H * 0.72
    ch_w = char.get_width() * ch_h / char.get_height()
    sway = math.sin(t * math.pi * 2.2) * W * 0.004
    ch_x = -ch_w * 0.28 + (W * 0.02 + ch_w * 0.28) * appear
    # 脚底落在地平线上（而非图片画布底边），接地阴影才能对上脚
    ground_y = H * 0.93
    ch_y = ground_y - ch_h * foot_ratio
    foot_y = ch_y + ch_h * foot_ratio
    draw_contact_shadow(ctx, ch_x + ch_w * 0.5, foot_y,
                        ch_w * 0.66, (0.02, 0.10, 0.24), 0.60 * appear)
    if appear > 0.001:
        ctx.push_group()
        ctx.translate(ch_x + sway * appear, ch_y)
        ctx.scale(ch_w / char.get_width(), ch_h / char.get_height())
        ctx.set_source_surface(char, 0, 0)
        ctx.paint()
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(appear)

    # 文字组
    tw = ease_out((t - 0.20) / 0.40)
    tx = W * 0.455 + (1 - tw) * W * 0.03
    ty = H * 0.325 + (1 - tw) * H * 0.022

    text(ctx, "感谢观看", tx, ty, 126, DEEP, bold=True, alpha=tw)
    text(ctx, OUTRO_SUBTITLE, tx, ty + 64, 38,
         DEEP, alpha=tw * 0.92)

    # 三个胶囊按钮
    items = ["growdu.cn", "订阅关注", "点赞支持"]
    delays = [0.00, 0.07, 0.14]
    gap = 22
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(36)
    widths = [ctx.text_extents(t).width + 70 for t in items]
    cap_x = tx
    for i, (txt, delay) in enumerate(zip(items, delays)):
        cap = ease_out((t - 0.38 - delay) / 0.38)
        bw = widths[i]
        bx = cap_x
        by = ty + 106
        bh = 68
        ctx.set_source_rgba(1.0, 1.0, 1.0, 0.88 * cap)
        ctx.rectangle(bx, by, bw, bh)
        ctx.fill()
        ctx.set_source_rgba(0.16, 0.30, 0.49, 0.85 * cap)
        ctx.set_line_width(2.6)
        ctx.rectangle(bx, by, bw, bh)
        ctx.stroke()
        text(ctx, txt, bx + 35, by + 46, 36, DEEP, bold=True, alpha=cap)
        cap_x += bw + gap

    fade_in = clamp01(t / 0.10)
    fade_out = clamp01((1.0 - t) / 0.14)
    fade = min(fade_in, fade_out)
    if fade < 1.0:
        ctx.set_source_rgba(1, 1, 1, 1 - fade)
        ctx.paint()
    return surface


# ---------------------------------------------------------------- 编码

def stamp_badge(char_path: Path) -> None:
    """给胸口铭牌印上 growdu（真实字体渲染）。

    铭牌是品牌标识，必须显示 growdu；但文字不能交给模型生成——模型的中英文
    会乱码。所以合成前统一盖一次章：刷白铭牌，再用 PingFang SC 写上 growdu。
    幂等：已经盖过章再盖一次结果完全一致。
    """
    script = AIV / "character" / "scripts" / "stamp_badge.py"
    if not script.exists():
        print(f"  - 找不到铭牌盖章脚本 {script}，跳过", file=sys.stderr)
        return
    subprocess.run(
        [sys.executable, str(script), str(char_path)],
        check=True, cwd=str(script.parent),
    )


def verify_frames(path: Path, expected: int) -> None:
    """校验成片帧数。

    丢帧会让 concat 之后的总时长漂移（时间基一致但帧数不对），
    所以渲染完必须当场数一遍，不能等到成片才发现。
    """
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    frames = int(out)
    if frames != expected:
        raise RuntimeError(
            f"{path.name} 帧数不符：期望 {expected} 帧，实际 {frames} 帧"
        )


def render(which: str, bg_path: Path, char_path: Path, out_path: Path,
           audio_path: Path | None) -> None:
    bg = Image.open(bg_path).convert("RGBA")
    # 铭牌盖章要在把形象读进 cairo 之前
    stamp_badge(char_path)
    char_img = Image.open(char_path).convert("RGBA")
    # 脚底在素材画布中的相对位置（透明留白不算），决定接地阴影落在哪
    foot_ratio = subject_bbox(char_img)[3] / char_img.height
    char = pil_to_cairo(char_img)
    renderer = render_intro_frame if which == "intro" else render_outro_frame

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "bgr0",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-video_track_timescale", str(TIMESCALE),
        str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for i in range(FRAMES):
            t = i / (FRAMES - 1)
            surface = renderer(t, bg, char, foot_ratio)
            proc.stdin.write(surface_bytes(surface))
            surface.flush()
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 渲染失败：{out_path}")

    # 混入音轨
    if audio_path is not None:
        tmp = out_path.with_suffix(".video.mp4")
        out_path.rename(tmp)
        # 不用 -shortest：AAC 编码器会引入延迟，-shortest 会按音频的结束点
        # 反过来把视频截短（实测 68 帧被截成 64 帧，concat 后时长就漂了）。
        # 改成按帧数精确截断，音频短则补静音。
        duration = FRAMES / FPS
        subprocess.run([
            "ffmpeg", "-y", "-i", str(tmp), "-i", str(audio_path),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-ar", "48000", "-ac", "2",
            "-af", "apad",
            "-t", f"{duration:.6f}",
            "-movflags", "+faststart", str(out_path),
        ], check=True)
        tmp.unlink()
    verify_frames(out_path, FRAMES)
    print(f"  → {out_path.name}（{FRAMES} 帧 / {FRAMES / FPS:.3f}s）")


def main() -> int:
    parser = argparse.ArgumentParser(description="渲染 Growdu 专属片头/片尾")
    parser.add_argument("--intro", action="store_true", help="只渲染片头")
    parser.add_argument("--outro", action="store_true", help="只渲染片尾")
    args = parser.parse_args()
    do_intro = args.intro or not args.outro
    do_outro = args.outro or not args.intro

    jobs = [
        ("intro", ASSETS / "bg_intro.png",
         ASSETS / "growdu_pose_thumbsup_nobg.png",
         CLIPS / "growdu_intro_3s_1080p.mp4",
         BRAND / "audio" / "intro_mix.wav"),
        ("outro", ASSETS / "bg_outro.png",
         ASSETS / "growdu_pose_wave_nobg.png",
         CLIPS / "growdu_outro_3s_1080p.mp4",
         BRAND / "audio" / "outro_mix.wav"),
    ]
    for which, bg, char, out, audio in jobs:
        if which == "intro" and not do_intro:
            continue
        if which == "outro" and not do_outro:
            continue
        for p in (bg, char):
            if not p.exists():
                print(f"缺少素材：{p}", file=sys.stderr)
                return 1
        print(f"渲染 {which} …")
        render(which, bg, char, out, audio if audio.exists() else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
