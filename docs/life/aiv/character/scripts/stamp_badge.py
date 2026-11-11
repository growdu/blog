#!/usr/bin/env python3
"""给胸口铭牌印上 growdu（真实字体渲染）。

规范：铭牌**必须**显示 growdu——那是品牌标识，不能空着。但文字**不能**交给
模型生成：模型的中英文会乱码（growdu 可能变成 giowdu / grawdu）。

所以生成之后统一做一次后处理：

  1. 自动定位胸口那块白铭牌（不硬编码坐标，重生成后依然有效）
  2. 把铭牌刷成纯白，抹掉模型写的任何字
  3. 用 PingFang SC 写上 growdu

文字来源于是从「模型碰运气」变成「代码确定」：模型这次碰巧写对了也不算数，
下次重新生成时铭牌照样是对的。

铭牌定位：
  1. 铭牌在马甲上，所以先取最大一块马甲色连通块的包围盒，只在这块区域里找
     「近白色」的连通块——这一条约束同时挡掉了白底图里的大片背景
  2. 候选必须是横向长方形、边长与面积都够大
  3. 铭牌是「被深藏蓝马甲围住的一小块白」，所以四周一圈马甲色占比最高的那个
     就是它

用法：
  python3 scripts/stamp_badge.py                  # 处理默认素材
  python3 scripts/stamp_badge.py <png> [png...]   # 处理指定文件
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import cairo
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
AIV = HERE.parent.parent                     # docs/life/aiv
CHAR_DIR = AIV / "character"
BRAND_ASSETS = AIV / "brand" / "assets"

FONT = "PingFang SC"
TEXT = "growdu"
TEXT_COLOR = (0x1B, 0x2A, 0x47)          # 深藏蓝，跟字幕主色一致
TEXT_WIDTH_RATIO = 0.76                  # 文字宽度占铭牌宽度的比例
TEXT_HEIGHT_RATIO = 0.52                 # 文字高度占铭牌高度的比例

NEAR_WHITE = 205          # 近白阈值
VEST_MAX = (110, 140, 175)   # 深藏蓝马甲的 r/g/b 上限
VEST_BLUE_MARGIN = 20       # 马甲还要满足 b > r + 该值
MIN_SIDE = 8                # 铭牌最小边长（像素）
# 铭牌是横向长方形。实测长宽比在 1.8 ~ 2.4 之间（盖章后白色块会略微
# 上下扩展一点），所以卡 1.5 留足余量。
MIN_ASPECT = 1.5            # 铭牌是横向长方形
MAX_AREA_RATIO = 0.004      # 铭牌面积不超过画布的 0.4%
# 铭牌四周一圈的「马甲占比」随生成批次波动很大（实测 0.17 ~ 0.74：
# 铭牌有时紧贴马甲边沿，有时旁边是角色的浅色身体），所以这个值只当
# 兜底门槛，真正的判据是尺寸 + 长宽比。
MIN_VEST_FRACTION = 0.08    # 四周一圈必须是马甲色
# 铭牌是服装上固定尺寸的道具，所有素材同一比例，所以按画布比例卡下限。
# 这一条是眼镜带来的：镜腿末端模型偶尔会贴一块小白牌，它四周全是镜框色，
# 「马甲占比」接近 1.0，比真正的铭牌还高——只有「够大」才分得开。
MIN_WIDTH_RATIO = 0.035     # 铭牌宽度至少占画布宽 3.5%（2048 画布 ≈ 72px）
MIN_HEIGHT_RATIO = 0.015    # 铭牌高度至少占画布高 1.5%（2048 画布 ≈ 31px）
# 铭牌在**胸口**，不在脸上。实测铭牌的上沿都在主体高度的 62%~68% 处
# （主形象 68%、点赞姿态 62%），而眼镜上的白牌在 30% 上下。
# 这条约束挡的是「镜框上的白牌把真铭牌挤掉」——那块白牌四周全是深藏蓝的
# 镜框，「马甲占比」比胸口那块真铭牌还高，光看颜色分不开。
MIN_BADGE_SUBJECT_Y = 0.45  # 铭牌上沿必须低于主体高度的 45%
# 铭牌是**纯白**的塑料牌，而小象的脚趾是奶油色、眼睛是高光：
# 实测铭牌区域「三个通道都 ≥ 240」的像素占 85%~89%，
# 脚趾只有 21%，眼睛 1%。这条把「胸口的白块」和「脚上的白块」分开。
WHITE_CHANNEL_MIN = 240
MIN_WHITE_FRACTION = 0.55

DEFAULT_TARGETS = (
    CHAR_DIR / "growdu_character_2k.png",
    CHAR_DIR / "growdu_character_2k_nobg.png",
    BRAND_ASSETS / "growdu_pose_thumbsup_nobg.png",
    BRAND_ASSETS / "growdu_pose_wave_nobg.png",
)


@dataclass(frozen=True)
class Badge:
    """铭牌的几何信息。origin 是文字基线起点（相对铭牌左上角）。"""
    box: tuple[int, int, int, int]
    size: int
    origin: tuple[float, float]


def _vest_regions(vest: np.ndarray) -> list[tuple[int, int, int, int]]:
    """马甲区域的候选包围盒，按优先级排列。

    先用**最大连通块**的包围盒，再退回「所有马甲色像素」的包围盒。

    为什么不能只用后者：眼镜的镜框和马甲是同一个深藏蓝 #2B4C7E。眼镜一戴上，
    「所有马甲色像素」就把脸上那副镜框也算了进去，搜索区域被撑到整个上半身——
    脸上的一小块高光会被误判成铭牌（实测就翻车了：真正的铭牌在胸口，
    检测器却抓到了鼻梁上的一小条反光）。

    为什么还要留个退路：马甲有渐变阴影，可能被切碎成几块，最大那块未必
    包住铭牌。真到那一步，退回全图马甲包围盒比什么都找不到强。
    """
    regions: list[tuple[int, int, int, int]] = []
    labels, count = ndimage.label(vest)
    blob_top = 0
    if count:
        sizes = ndimage.sum(vest, labels, range(1, count + 1))
        sl = ndimage.find_objects(labels)[int(np.argmax(sizes))]
        blob_top = sl[0].start
        regions.append((sl[1].start, sl[0].start, sl[1].stop, sl[0].stop))
    ys, xs = np.nonzero(vest)
    if len(xs):
        # 退路：所有马甲像素的包围盒，但**上沿不许高过衣服上沿**。
        # 衣服上沿以上是脸——眼镜的镜腿也在那儿，模型偶尔会在镜腿上贴一块
        # 小白铭牌，那块白四周全是镜框颜色，「马甲占比」高达 1.0，
        # 不夹住上沿它就会把脸上那块抢走。
        fallback = (int(xs.min()), max(int(ys.min()), blob_top),
                    int(xs.max()) + 1, int(ys.max()) + 1)
        if fallback not in regions:
            regions.append(fallback)
    return regions


def find_badge(image: Image.Image) -> tuple[int, int, int, int] | None:
    """返回铭牌矩形 (x0, y0, x1, y1)；找不到返回 None。

    铭牌在马甲上，所以只在**马甲区域内**找白块——这一条约束同时挡掉了
    白底图里的大片背景，避免白色连通块被误当成铭牌。
    """
    arr = np.array(image.convert("RGBA"))
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    alpha = arr[..., 3]
    near_white = (r > NEAR_WHITE) & (g > NEAR_WHITE) & (b > NEAR_WHITE)
    if alpha.min() < 250:
        near_white &= alpha > 200      # 透明底版：先把背景剔掉
    vest = (
        (r < VEST_MAX[0]) & (g < VEST_MAX[1]) & (b < VEST_MAX[2])
        & (b > r + VEST_BLUE_MARGIN)
    )
    if not vest.any():
        return None

    labels, _ = ndimage.label(near_white)
    height, width = arr.shape[:2]
    subject = _subject_box(arr)
    # 纯白像素：三个通道都足够高。铭牌是白塑料牌，脚趾是奶油色。
    solid_white = (r >= WHITE_CHANNEL_MIN) & (g >= WHITE_CHANNEL_MIN) \
        & (b >= WHITE_CHANNEL_MIN)
    for region in _vest_regions(vest):
        best = _best_badge_in(near_white, vest, labels, region, width, height,
                              subject, solid_white)
        if best is not None:
            return best
    return None


def _subject_box(arr: np.ndarray) -> tuple[int, int, int, int] | None:
    """主体包围盒，用来判断某个白块在「脸上」还是「胸口」。"""
    rgb = arr[..., :3]
    alpha = arr[..., 3]
    if alpha.min() < 250:
        mask = alpha > 8
    else:
        mask = ~((rgb[..., 0] > 240) & (rgb[..., 1] > 240) & (rgb[..., 2] > 240))
        # 白底图：画布最外圈可能有压缩杂色，清掉
        mask[:2, :] = False
        mask[-2:, :] = False
        mask[:, :2] = False
        mask[:, -2:] = False
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    if rows.size == 0 or cols.size == 0:
        return None
    return int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1


def _best_badge_in(near_white: np.ndarray, vest: np.ndarray,
                   labels: np.ndarray, region: tuple[int, int, int, int],
                   width: int, height: int,
                   subject: tuple[int, int, int, int] | None,
                   solid_white: np.ndarray | None = None,
                   ) -> tuple[int, int, int, int] | None:
    """在 region 这块马甲区域里找最像铭牌的白块。"""
    vx0, vy0, vx1, vy1 = region
    best: tuple[tuple[int, int, int, int], float] | None = None
    for sl in ndimage.find_objects(labels):
        y0, y1 = sl[0].start, sl[0].stop
        x0, x1 = sl[1].start, sl[1].stop
        if x0 == 0 or y0 == 0 or x1 == width or y1 == height:
            continue                    # 与画布边缘相连 → 那是背景
        if x0 < vx0 or x1 > vx1 or y0 < vy0 or y1 > vy1:
            continue                    # 不在马甲上 → 不是铭牌
        if subject is not None:
            subject_h = subject[3] - subject[1]
            if subject_h > 0 and (y0 - subject[1]) < MIN_BADGE_SUBJECT_Y * subject_h:
                continue                # 太靠上 → 脸上的东西（眼镜上的白牌）
        box_w, box_h = x1 - x0, y1 - y0
        if min(box_w, box_h) < MIN_SIDE:
            continue
        if box_w < MIN_WIDTH_RATIO * width or box_h < MIN_HEIGHT_RATIO * height:
            continue                    # 太小 → 是零碎高光，不是铭牌
        if box_w < MIN_ASPECT * box_h:
            continue                    # 铭牌是横向长方形
        if box_w * box_h > MAX_AREA_RATIO * width * height:
            continue
        # 纯白度：铭牌是白塑料牌，脚趾是奶油色，眼睛是高光
        if solid_white is None:
            continue
        white_fraction = float(solid_white[y0:y1, x0:x1].mean())
        if white_fraction < MIN_WHITE_FRACTION:
            continue
        ring = np.zeros_like(near_white)
        ring[max(0, y0 - 4):y1 + 4, max(0, x0 - 4):x1 + 4] = True
        ring[y0:y1, x0:x1] = False
        fraction = float(vest[ring].mean()) if ring.any() else 0.0
        if fraction < MIN_VEST_FRACTION:
            continue
        if best is None or fraction > best[1]:
            best = ((x0, y0, x1, y1), fraction)
    return best[0] if best else None


def _measure(ctx: cairo.Context, text: str, size: float):
    ctx.set_font_size(size)
    return ctx.text_extents(text)


def _fit_text(ctx: cairo.Context, text: str, box_w: int, box_h: int) -> int:
    """挑一个既放得下、又尽量大的字号。

    cairo 的 text_extents 依次是
    (x_bearing, y_bearing, width, height, x_advance, y_advance)，
    其中 height 就是墨迹高度。
    """
    max_w = box_w * TEXT_WIDTH_RATIO
    max_h = box_h * TEXT_HEIGHT_RATIO
    ext = _measure(ctx, text, 100.0)
    width, height = ext[2], ext[3]
    # 两个方向的缩放都从基准字号 100 算，否则会连乘、字号被压到极小
    size = 100.0
    if width > 0:
        size = min(size, 100.0 * max_w / width)
    if height > 0:
        size = min(size, 100.0 * max_h / height)
    size = int(max(6, round(size)))
    while size > 6:
        ext = _measure(ctx, text, float(size))
        if ext[2] <= max_w and ext[3] <= max_h:
            break
        size -= 1
    return size


def render_text_mask(text: str, size: int, origin: tuple[float, float],
                     width: int, height: int) -> np.ndarray:
    """把一段文字渲染成 alpha 掩膜（供合成与测试比对）。"""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(float(size))
    ctx.set_source_rgba(0.0, 0.0, 0.0, 1.0)
    ctx.move_to(origin[0], origin[1])
    ctx.show_text(text)
    surface.flush()
    stride = surface.get_stride()
    data = bytes(surface.get_data())
    arr = np.frombuffer(data, dtype=np.uint8).reshape(height, stride // 4, 4)
    return arr[:, :width, 3].copy()


def plan_badge(image: Image.Image) -> Badge | None:
    """算出铭牌矩形、字号与文字基线起点。"""
    box = find_badge(image)
    if box is None:
        return None
    x0, y0, x1, y1 = box
    box_w, box_h = x1 - x0, y1 - y0
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    ctx = cairo.Context(surface)
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    size = _fit_text(ctx, TEXT, box_w, box_h)
    ext = _measure(ctx, TEXT, float(size))
    x_bearing, y_bearing = ext[0], ext[1]
    width, ink_height = ext[2], ext[3]
    x = (box_w - width) / 2 - x_bearing
    baseline = (box_h - ink_height) / 2 - y_bearing
    return Badge(box=box, size=size, origin=(x, baseline))


def stamp_badge(path: str | Path) -> Badge | None:
    """把铭牌刷白并印上 growdu。返回铭牌信息；没找到铭牌返回 None。"""
    path = Path(path)
    if not path.exists():
        print(f"  - {path.name}：文件不存在，跳过", file=sys.stderr)
        return None
    image = Image.open(path).convert("RGBA")
    badge = plan_badge(image)
    if badge is None:
        print(f"  - {path.name}：没找到铭牌，跳过")
        return None
    x0, y0, x1, y1 = badge.box
    box_w, box_h = x1 - x0, y1 - y0

    arr = np.array(image)
    # 1. 抹掉模型写的任何字，整块刷成纯白
    arr[y0:y1, x0:x1, :3] = 255
    # 2. 用真实字体写上 growdu
    mask = render_text_mask(TEXT, badge.size, badge.origin, box_w, box_h)
    alpha = (mask.astype(np.uint16) / 255.0)[..., None]
    color = np.array(TEXT_COLOR, dtype=np.float64)[None, None, :]
    region = arr[y0:y1, x0:x1, :3].astype(np.float64)
    arr[y0:y1, x0:x1, :3] = np.clip(
        region * (1 - alpha) + color * alpha, 0, 255
    ).astype(np.uint8)

    Image.fromarray(arr, "RGBA").save(path)
    print(f"  → {path.name}：铭牌 {badge.box} 已印上 {TEXT}（{badge.size}px）")
    return badge


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    targets = [Path(a) for a in argv] if argv else list(DEFAULT_TARGETS)
    for target in targets:
        stamp_badge(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
