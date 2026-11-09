"""小象部件切分与 2D 动作。

形象原图唯一来源：项目根 growdu.png（1220×1289，RGBA 透明底）。

分区策略：先用颜色连通块定位头/双耳/双臂/腿的"填充区域"，
再按邻域把描边、眼睛、面颊、徽章、图标等非填充像素归到最近的部位，
保证每个部件都是完整的一小块（颜色不丢），可以独立旋转。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import cairo
import numpy as np
from PIL import Image
from scipy import ndimage

SKY_MIN_AREA = 1500
ARM_MIN_AREA = 8000
ARM_EDGE = 9       # 手臂描边离填充区的最大距离
HEAD_EDGE = 14     # 头部（含双耳）描边离填充区的最大距离
BODY_TOP = 700     # 低于该行属于躯干（背心、徽章、图标、腿）


@dataclass(frozen=True)
class Part:
    image: Image.Image
    crop_box: tuple[int, int, int, int]  # x0, y0, x1, y1（原图坐标）

    @property
    def size(self) -> tuple[int, int]:
        return self.image.size

    def local_pivot(self, pivot: tuple[float, float]) -> tuple[float, float]:
        """把原图坐标的枢轴换算成裁剪块内部坐标。"""
        return (pivot[0] - self.crop_box[0], pivot[1] - self.crop_box[1])


@dataclass(frozen=True)
class Parts:
    head: Part
    arm_left: Part
    arm_right: Part
    body: Part
    pivots: dict[str, tuple[float, float]]
    anchor: tuple[float, float]

    def surface(self, name: str) -> cairo.ImageSurface:
        return _pil_to_cairo(getattr(self, name).image)


@dataclass
class Pose:
    nod: float = 0.0
    wave: float = 0.0
    turn: float = 0.0
    point: float = 0.0


def _sky_mask(arr: np.ndarray) -> np.ndarray:
    alpha = arr[..., 3]
    r, g, b = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)
    return (alpha > 200) & (b > r + 30) & (b > 170) & (r > 90) & (r < 190) & (g > 150)


def _components(mask: np.ndarray, min_area: int) -> list[tuple[int, tuple[int, int, int, int], int]]:
    lab, n = ndimage.label(mask)
    out: list[tuple[int, tuple[int, int, int, int], int]] = []
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        size = int((lab[sl] == i).sum())
        if size < min_area:
            continue
        out.append((size, (int(sl[1].start), int(sl[0].start),
                           int(sl[1].stop), int(sl[0].stop)), i))
    out.sort(reverse=True, key=lambda item: item[0])
    return out


def _near(seed: np.ndarray, limit: float) -> np.ndarray:
    """距 seed 不超过 limit 的像素。"""
    distance = ndimage.distance_transform_edt(~seed)
    return distance <= limit


def _pil_to_cairo(image: Image.Image) -> cairo.ImageSurface:
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


def _part_from_mask(image: Image.Image, mask: np.ndarray) -> Part:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        raise ValueError("部件为空，无法切分")
    x0, y0 = int(xs.min()), int(ys.min())
    x1, y1 = int(xs.max()) + 1, int(ys.max()) + 1
    arr = np.array(image)
    arr[..., 3] = np.where(mask, arr[..., 3], 0)
    cropped = Image.fromarray(arr[y0:y1, x0:x1], "RGBA")
    return Part(image=cropped, crop_box=(x0, y0, x1, y1))


def load_parts(image_path: str | Path) -> Parts:
    """按颜色连通块定位部位，再按邻域归属把全部像素分给各部位。"""
    image = Image.open(image_path).convert("RGBA")
    arr = np.array(image)
    opaque = arr[..., 3] > 128
    sky = _sky_mask(arr)
    lab, _ = ndimage.label(sky)
    comps = _components(sky, SKY_MIN_AREA)
    if len(comps) < 6:
        raise ValueError(f"形象图连通块数量异常（{len(comps)}），请确认使用 growdu.png")

    head_size, head_box, head_index = comps[0]
    ears = [(box, index) for size, box, index in comps
            if box[3] < 600 and (box[0] < 500 or box[2] > 700)]
    if len(ears) < 2:
        raise ValueError("未能识别出双耳")
    ear_left_box, ear_left_index = min(ears, key=lambda item: item[0][0])
    ear_right_box, ear_right_index = max(ears, key=lambda item: item[0][2])

    arms = [
        (box, index) for size, box, index in comps
        if size >= ARM_MIN_AREA and box[1] > 600 and box[3] < 1000
        and (box[2] - box[0]) < 260 and (box[0] < 500 or box[2] > 700)
    ]
    if len(arms) < 2:
        raise ValueError("未能识别出双臂")
    arm_left_box, arm_left_index = min(arms, key=lambda item: item[0][0])
    arm_right_box, arm_right_index = max(arms, key=lambda item: item[0][2])

    head_fill = lab == head_index
    ear_left_fill = lab == ear_left_index
    ear_right_fill = lab == ear_right_index
    arm_left_fill = lab == arm_left_index
    arm_right_fill = lab == arm_right_index

    # 归属：手臂（连描边）→ 头部（脸 + 双耳 + 眼 + 面颊 + 耳麦）→ 躯干（背心/徽章/图标/腿）
    arm_left_mask = arm_left_fill | (opaque & _near(arm_left_fill, ARM_EDGE))
    arm_right_mask = arm_right_fill | (opaque & _near(arm_right_fill, ARM_EDGE))

    head_seed = head_fill | ear_left_fill | ear_right_fill
    head_candidate = head_seed | (opaque & _near(head_seed, HEAD_EDGE))

    # 肩线以下的非填充像素属于躯干（背心深蓝、徽章、图标），头部填充（含鼻尖）除外
    any_fill = head_fill | ear_left_fill | ear_right_fill | arm_left_fill | arm_right_fill
    below_shoulder = opaque & (np.arange(arr.shape[0])[:, None] >= BODY_TOP) & ~any_fill

    head_mask = head_candidate & ~arm_left_mask & ~arm_right_mask & ~below_shoulder
    body_mask = opaque & ~head_mask & ~arm_left_mask & ~arm_right_mask

    head_box = _bbox(head_mask)
    arm_left_box = _bbox(arm_left_mask)
    arm_right_box = _bbox(arm_right_mask)
    body_box = _bbox(body_mask)

    pivots = {
        "head": ((head_box[0] + head_box[2]) / 2, head_box[3] - 40),
        "arm_left": (arm_left_box[2] - 30, arm_left_box[1] + 10),
        "arm_right": (arm_right_box[0] + 30, arm_right_box[1] + 10),
    }
    anchor = ((body_box[0] + body_box[2]) / 2, body_box[3])

    return Parts(
        head=_part_from_mask(image, head_mask),
        arm_left=_part_from_mask(image, arm_left_mask),
        arm_right=_part_from_mask(image, arm_right_mask),
        body=_part_from_mask(image, body_mask),
        pivots=pivots,
        anchor=anchor,
    )


def _bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def _blit(ctx: cairo.Context, part: Part, surface: cairo.ImageSurface,
          pivot: tuple[float, float], angle_deg: float,
          dest: tuple[float, float], anchor: tuple[float, float], scale: float) -> None:
    """把部件按枢轴旋转后绘制；dest 是锚点在画布上的位置。"""
    local = part.local_pivot(pivot)
    base = (
        dest[0] + (pivot[0] - anchor[0]) * scale,
        dest[1] + (pivot[1] - anchor[1]) * scale,
    )
    ctx.save()
    ctx.translate(base[0], base[1])
    ctx.rotate(math.radians(angle_deg))
    ctx.scale(scale, scale)
    ctx.translate(-local[0], -local[1])
    ctx.set_source_surface(surface, 0, 0)
    ctx.paint()
    ctx.restore()


def draw_elephant(ctx: cairo.Context, parts: Parts, pose: Pose,
                   dest: tuple[float, float], scale: float,
                   alpha: float = 1.0) -> None:
    """按姿态绘制小象。dest 是脚底锚点位置，scale 是缩放比例。"""
    if alpha < 0.999:
        ctx.push_group()
        _draw_parts(ctx, parts, pose, dest, scale)
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(alpha)
    else:
        _draw_parts(ctx, parts, pose, dest, scale)


def _draw_parts(ctx: cairo.Context, parts: Parts, pose: Pose,
                dest: tuple[float, float], scale: float) -> None:
    nod = math.sin(pose.nod * math.pi) * 7.0
    turn = (pose.turn - 0.5) * 10.0
    wave = math.sin(pose.wave * math.pi * 4) * 20.0
    point = -30.0 * pose.point

    # 躯干打底（含背心、徽章、图标、腿）
    _blit(ctx, parts.body, parts.surface("body"), parts.anchor, 0.0,
          dest, parts.anchor, scale)
    # 左臂在身后，右臂在前
    _blit(ctx, parts.arm_left, parts.surface("arm_left"), parts.pivots["arm_left"],
          0.0, dest, parts.anchor, scale)
    # 头（含双耳）压在躯干之上
    _blit(ctx, parts.head, parts.surface("head"), parts.pivots["head"],
          nod + turn, dest, parts.anchor, scale)
    _blit(ctx, parts.arm_right, parts.surface("arm_right"), parts.pivots["arm_right"],
          wave + point, dest, parts.anchor, scale)
