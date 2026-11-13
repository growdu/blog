#!/usr/bin/env python3
"""修复 Growdu 片头/片尾底板中被 16:9 画幅裁断的文字。

原始品牌分镜是更宽的画幅，裁到 16:9 (1920x1080) 时把右侧文字切断了：

* 片头底板：``Growdu`` 字标、``Database · Knowledge · Growth`` 标语被截断，
  中文标语药丸的右端也被切掉；
* 片尾底板：中文副标题左右溢出，第三个按钮（点赞）只剩半个。

做法
----
1. 用颜色阈值把被裁断的文字 / 描边圈成掩膜；
2. 只对掩膜像素做「按列线性初值 + 调和扩散」修复，背景渐变与辉光得以保留
   （比整块矩形填充自然，不会出现色块边界）；
3. 用系统真实字体重新排版文字（不做 AI 生成，避免中文乱码），
   按原图的比例、字重、字色还原，描边图形一并重画，并补上原片的光晕质感；
4. 全部文字完整落在 1920x1080 内，片尾的三个按钮整体重排到画幅内。

用法
----
    python3 scripts/fix_plates.py
"""

import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 底板目录：现在是 brand/plates/，早期版本在 brand/assets/plates/。
# 两个都认，免得脚本因为目录挪过家就直接崩。
PLATES = next((d for d in (os.path.join(ROOT, "plates"),
                            os.path.join(ROOT, "assets", "plates"))
               if os.path.isdir(d)), os.path.join(ROOT, "plates"))
BACKUP = os.path.join(PLATES, "original")


def pick_font(candidates):
    """挑一款存在的字体文件。

    candidates 是 (路径, 索引) 列表——macOS 的 .ttc 是字体集合，
    索引选字重；Linux 的替代品是单字体文件，索引恒为 0。

    找不到就报错并给出安装命令，不要静默画成豆腐块。
    """
    for path, index in candidates:
        if os.path.exists(path):
            return path, index
    raise RuntimeError(
        "找不到需要的字体文件，候选："
        + " / ".join(path for path, _ in candidates)
        + "。装一套字体即可（Debian/Ubuntu: "
        "apt-get install -y fonts-dejavu-core fonts-noto-cjk）"
    )


# 拉丁字标用 Avenir Next（macOS 自带），Linux 上退到 DejaVu Sans；
# 中文用 Hiragino Sans GB（macOS 自带），Linux 上退到 Noto Sans CJK SC。
# **字形因此不同**：Linux 上修复出来的底板与 macOS 版不是逐像素一致。
AVENIR_HEAVY = pick_font([
    ("/System/Library/Fonts/Avenir Next.ttc", 8),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
])
AVENIR_BOLD = pick_font([
    ("/System/Library/Fonts/Avenir Next.ttc", 0),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),
])
AVENIR_MEDIUM = pick_font([
    ("/System/Library/Fonts/Avenir Next.ttc", 5),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),
])
CJK_W6 = pick_font([
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 2),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0),
])

# 渲染时 zoompan 会放大约 6%，画面边缘约 3% 会被裁掉，文字右侧留到 1840 以内
MARGIN = 1840


# ---------------------------------------------------------------- 基础工具
def font(path, size, index=0):
    return ImageFont.truetype(path, size, index=index)


def text_width(draw, text, f, tracking=0):
    if not text:
        return 0.0
    return sum(draw.textlength(c, font=f) for c in text) + tracking * (len(text) - 1)


def draw_tracked(draw, xy, text, f, fill, tracking=0):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=f, fill=fill)
        x += draw.textlength(ch, font=f) + tracking
    return x


def fit_font(path, index, text, max_w, start, minimum=8, tracking=0):
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    lo, hi, best = minimum, start, minimum
    while lo <= hi:
        mid = (lo + hi) // 2
        f = font(path, mid, index)
        if text_width(probe, text, f, tracking) <= max_w:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return font(path, best, index), best


def dilate(mask, r=2):
    out = mask.copy()
    for _ in range(r):
        g = out.copy()
        g[1:, :] |= out[:-1, :]
        g[:-1, :] |= out[1:, :]
        g[:, 1:] |= out[:, :-1]
        g[:, :-1] |= out[:, 1:]
        out = g
    return out


def inpaint(im, mask, iterations=420):
    """调和扩散修复：列向线性初值 + 拉普拉斯迭代，边缘与原背景自然衔接。"""
    arr = np.asarray(im).astype(np.float64)
    ys, xs = np.where(mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    sub = arr[y0:y1, x0:x1].copy()
    m = mask[y0:y1, x0:x1]
    h, w = m.shape

    guess = sub.copy()
    rows = np.arange(h)
    for x in range(w):
        known = np.where(~m[:, x])[0]
        if len(known) == 0:
            continue
        for c in range(sub.shape[2]):
            guess[:, x, c] = np.interp(rows, known, sub[known, x, c])
    sub = guess

    for _ in range(iterations):
        p = np.pad(sub, ((1, 1), (1, 1), (0, 0)), mode="edge")
        sub[m] = ((p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 4.0)[m]
    arr[y0:y1, x0:x1] = sub
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def sample_color(im, region, predicate):
    x0, y0, x1, y1 = region
    crop = np.asarray(im.crop((x0, y0, x1, y1)).convert("RGB")).reshape(-1, 3)
    sel = crop[predicate(crop)]
    if len(sel) == 0:
        return (255, 255, 255)
    return tuple(int(v) for v in np.median(sel, axis=0))


def is_white(px):
    return (px.min(axis=1) > 185) & ((px.max(axis=1) - px.min(axis=1)) < 55)


def is_gold(px):
    return (px[:, 0] > 185) & (px[:, 1] > 120) & (px[:, 2] < 115)


def is_cyan(px):
    return (px[:, 2] > 185) & (px[:, 1] > 125) & (px[:, 0] < 175)


def is_navy(px):
    return (px[:, 0] < 85) & (px[:, 2] > px[:, 0] + 55) & (px[:, 1] < 125)


def is_stroke(px):
    """深蓝描边（按钮边框 / 图标），排除浅蓝天空。"""
    return (px[:, 2] > 185) & (px[:, 0] < 145) & (px[:, 1] > 80) & (px[:, 1] < 205)


def is_darkgray(px):
    return ((px.max(axis=1) - px.min(axis=1)) < 45) & (px.max(axis=1) < 115)


def region_mask(im, box, predicate):
    x0, y0, x1, y1 = box
    patch = np.asarray(im.crop((x0, y0, x1, y1)).convert("RGB")).reshape(-1, 3)
    m = predicate(patch).reshape(y1 - y0, x1 - x0)
    full = np.zeros(im.size[::-1], dtype=bool)
    full[y0:y1, x0:x1] = m
    return full


# ---------------------------------------------------------------- 图标
def draw_globe(draw, box, color, width=4):
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    r = (x1 - x0) / 2
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=width)
    draw.ellipse([cx - r * 0.42, cy - r, cx + r * 0.42, cy + r], outline=color, width=width)
    draw.line([cx - r, cy, cx + r, cy], fill=color, width=width)


def draw_thumb(draw, box, color, width=4):
    x0, y0, x1, y1 = box
    sx, sy = (x1 - x0) / 48.0, (y1 - y0) / 48.0

    def p(px, py):
        return (x0 + px * sx, y0 + py * sy)

    outline = [p(6, 44), p(6, 18), p(16, 18), p(23, 5), p(30, 4), p(30, 13),
               p(25, 21), p(24, 24), p(41, 24), p(45, 28), p(45, 40), p(41, 44), p(6, 44)]
    draw.line(outline, fill=color, width=width, joint="curve")
    draw.line([p(16, 18), p(16, 44)], fill=color, width=width)


def draw_pill(draw, box, color, width=3):
    x0, y0, x1, y1 = box
    draw.rounded_rectangle([x0, y0, x1, y1], radius=(y1 - y0) / 2, outline=color, width=width)


def draw_play(draw, box, color):
    """圆角方块 + 白色三角（订阅按钮图标）。"""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    draw.rounded_rectangle([x0, y0, x1, y1], radius=w * 0.28, fill=color)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    tw, th = w * 0.34, h * 0.40
    draw.polygon([(cx - tw * 0.55, cy - th / 2), (cx - tw * 0.55, cy + th / 2),
                  (cx + tw * 0.75, cy)], fill=(255, 255, 255))


def draw_block(im, items, glow_radius=18, glow_color=(150, 226, 255), glow_alpha=0.42):
    """先画光晕层（模糊后按固定色叠加），再画清晰层，还原原片的发光质感。"""
    size = im.size

    def render(colorize):
        layer = Image.new("RGBA", size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for fn, col in items:
            fn(d, glow_color if colorize else col)
        return layer

    glow = render(True).filter(ImageFilter.GaussianBlur(glow_radius))
    a = glow.split()[3].point(lambda v: int(v * glow_alpha))
    arr = np.asarray(im.convert("RGB")).astype(np.float64)
    m = (np.asarray(a).astype(np.float64) / 255.0)[..., None]
    gc = np.array(glow_color, dtype=np.float64)[None, None, :]
    out = arr * (1 - m) + gc * m
    base = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).convert("RGBA")
    base.alpha_composite(render(False))
    return base.convert("RGB")


# ---------------------------------------------------------------- 片头
def fix_intro(path):
    im = Image.open(path).convert("RGB")
    white = sample_color(im, (1100, 380, 1920, 560), is_white)
    cyan = sample_color(im, (1000, 690, 1500, 710), is_cyan)
    gold = sample_color(im, (1620, 740, 1880, 812), is_gold)
    print("  采样颜色 白=%s 青=%s 金=%s" % (white, cyan, gold))

    # 字标 + 英文标语 + 中文药丸：连同原文字的描边/光晕一起圈成掩膜后修复
    mask = np.zeros(im.size[::-1], dtype=bool)
    mask |= region_mask(im, (1080, 370, 1920, 566), is_white)
    mask |= region_mask(im, (1060, 570, 1920, 664), is_white)
    mask |= region_mask(im, (990, 690, 1920, 836), is_white)
    mask |= region_mask(im, (990, 690, 1920, 836), is_gold)
    mask |= region_mask(im, (985, 690, 1920, 838), is_cyan)
    im = inpaint(im, dilate(mask, 12))

    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    items = []

    f_wm, size = fit_font(AVENIR_HEAVY[0], AVENIR_HEAVY[1], "Growdu", MARGIN - 1112, 230)
    bb = probe.textbbox((0, 0), "Growdu", font=f_wm)
    items.append((lambda d, c: draw_tracked(d, (1112, 396 - bb[1]), "Growdu", f_wm, c), white))
    print("  字标字号 %d" % size)

    f_tag, size = fit_font(AVENIR_MEDIUM[0], AVENIR_MEDIUM[1], "Database · Knowledge · Growth",
                           MARGIN - 1078, 90, tracking=2)
    bb = probe.textbbox((0, 0), "D", font=f_tag)
    items.append((lambda d, c: draw_tracked(d, (1078, 596 - bb[1]),
                                            "Database · Knowledge · Growth", f_tag, c, tracking=2), white))
    print("  英文标语字号 %d" % size)

    pill = (995, 696, MARGIN, 830)
    items.append((lambda d, c: draw_pill(d, pill, c, width=3), cyan))
    w_txt, g_txt = "深入数据库 · 分享", "技术之美"
    f_cn, size = fit_font(CJK_W6[0], CJK_W6[1], w_txt + g_txt, pill[2] - pill[0] - 100, 90)
    bb = probe.textbbox((0, 0), "深", font=f_cn)
    total = text_width(probe, w_txt, f_cn) + text_width(probe, g_txt, f_cn)
    tx = pill[0] + (pill[2] - pill[0] - total) / 2
    ty = 763 - (bb[3] + bb[1]) / 2

    def cn_text(d, c):
        x = draw_tracked(d, (tx, ty), w_txt, f_cn, c)
        draw_tracked(d, (x, ty), g_txt, f_cn, gold if c == white else c)

    items.append((cn_text, white))
    print("  中文标语字号 %d" % size)

    im = draw_block(im, items)
    im.save(path)


# ---------------------------------------------------------------- 片尾
def fix_outro(path):
    im = Image.open(path).convert("RGB")
    navy = sample_color(im, (840, 440, 1920, 508), is_navy)
    print("  采样颜色 深蓝=%s" % (navy,))

    # 副标题整行 + 按钮整排（含被裁掉的第三个按钮）全部抹掉重排
    mask = region_mask(im, (820, 425, 1920, 520), is_navy)
    mask |= region_mask(im, (780, 550, 1920, 692), is_stroke)
    mask |= region_mask(im, (780, 550, 1920, 692), is_navy)
    im = inpaint(im, dilate(mask, 6))

    d = ImageDraw.Draw(im)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))

    # 副标题：右对齐到 1860（与「感谢观看！」同一右边界）
    latin, cjk = "Growdu · ", "与你一起，探索数据库的无边世界"
    best = None
    for size in range(84, 30, -1):
        fl, fc = font(AVENIR_BOLD[0], size, AVENIR_BOLD[1]), font(CJK_W6[0], size, CJK_W6[1])
        if text_width(probe, latin, fl) + text_width(probe, cjk, fc) <= MARGIN - 870:
            best = (fl, fc, size)
            break
    fl, fc, size = best
    bb = probe.textbbox((0, 0), "与", font=fc)
    y = 474 - (bb[3] + bb[1]) / 2
    total = text_width(probe, latin, fl) + text_width(probe, cjk, fc)
    x = draw_tracked(d, (MARGIN - total, y), latin, fl, navy)
    draw_tracked(d, (x, y), cjk, fc, navy)
    print("  副标题字号 %d（宽 %d）" % (size, total))

    # 三个按钮整体右对齐到 1860，按内容宽度排布
    H = 96
    gap = 44
    pad_l, pad_r, icon_gap = 30, 34, 18
    icon = 52
    specs = [
        ("growdu.cn", "globe", AVENIR_MEDIUM, 0),
        ("订阅关注", "play", CJK_W6, 0),
        ("点赞支持", "thumb", CJK_W6, 0),
    ]
    f_btn = font(CJK_W6[0], 40, CJK_W6[1])
    f_lat = font(AVENIR_MEDIUM[0], 40, AVENIR_MEDIUM[1])
    widths = []
    for label, kind, fpath, idx in specs:
        f = f_lat if kind == "globe" else f_btn
        widths.append(pad_l + icon + icon_gap + text_width(probe, label, f) + pad_r)
    right = MARGIN
    x = right - sum(widths) - gap * (len(widths) - 1)
    for (label, kind, fpath, idx), w in zip(specs, widths):
        pill = (x, 618 - H / 2, x + w, 618 + H / 2)
        draw_pill(d, pill, navy, width=3)
        iy = 618 - icon / 2
        if kind == "globe":
            draw_globe(d, (x + pad_l, iy, x + pad_l + icon, iy + icon), navy, width=4)
        elif kind == "play":
            draw_play(d, (x + pad_l, iy, x + pad_l + icon, iy + icon), navy)
        else:
            draw_thumb(d, (x + pad_l, iy + 6, x + pad_l + icon, iy + icon - 6), navy, width=4)
        f = f_lat if kind == "globe" else f_btn
        tx = x + pad_l + icon + icon_gap
        bb = probe.textbbox((0, 0), label[0], font=f)
        draw_tracked(d, (tx, 618 - (bb[3] + bb[1]) / 2), label, f, navy)
        x += w + gap
    print("  按钮宽度 %s" % widths)

    im.save(path)


def main():
    os.makedirs(BACKUP, exist_ok=True)
    for name, fn in (("growdu_intro_1080p.png", fix_intro),
                     ("growdu_outro_1080p.png", fix_outro)):
        path = os.path.join(PLATES, name)
        bak = os.path.join(BACKUP, name)
        if not os.path.exists(bak):
            Image.open(path).convert("RGB").save(bak)
        else:
            Image.open(bak).convert("RGB").save(path)   # 始终基于原始图重跑
        print("修复 %s" % name)
        fn(path)
    print("完成。")


if __name__ == "__main__":
    main()
