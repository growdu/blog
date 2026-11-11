"""小象形象接入（统一入口）。

仓库里有两套形象素材：

| 素材 | 位置 | 是否入库 |
| --- | --- | --- |
| 新 3D 卡通形象 | `aiv/character/growdu_character_2k_nobg.png` | 否（媒体产物） |
| 旧 2D 扁平形象 | 仓库根 `growdu.png` | 是（1220×1289 RGBA） |

新 3D 形象是当前的品牌形象（片头/片尾用的就是它），但它不能喂进
`elephant.py` 的部件切分——连通块阈值与绝对坐标都是为 2D 扁平图硬编码的，
3D 渲染的渐变高光会直接破坏分割。按《形象与音色规范》§1.5 方案 A：

- 新形象：静帧素材 + 位移 / 缩放 / 淡入
- 旧 2D 形象：部件动画（挥手 / 点头）

降级策略：有新形象用新形象，没有则退回旧 2D 形象做动画，两者都没有就完全不画。
任何情况下都不抛异常——媒体产物不入库，缺素材是常态而不是错误。
"""
from __future__ import annotations

from pathlib import Path

import cairo
import numpy as np
from PIL import Image

from pyv import elephant

# aiv/ 是 pipeline/ 的上一级：pyv/character.py → pyv → pipeline → aiv
AIV_ROOT = Path(__file__).resolve().parents[2]
# aiv → life → docs → 仓库根
REPO_ROOT = AIV_ROOT.parents[2]

# 新 3D 形象（透明底，合成进视频用这个）
STATIC_IMAGE = AIV_ROOT / "character" / "growdu_character_2k_nobg.png"
# 旧 2D 形象（已入库，兜底）
LEGACY_IMAGE = REPO_ROOT / "growdu.png"
# 个人头像（已入库，用于落版；不使用任何公司 Logo）
AVATAR_IMAGE = REPO_ROOT / "themes" / "matery" / "source" / "medias" / "avatar.jpg"

# 旧 2D 素材的画布高，用来把「目标像素高」换算成 elephant.py 需要的缩放比
LEGACY_SOURCE_HEIGHT = 1289


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


def subject_box(image: Image.Image) -> tuple[int, int, int, int]:
    """非透明区域的包围盒（x0, y0, x1, y1）。

    透明底素材四周留白，画布底边 ≠ 脚底；接地阴影、锚点换算都要按主体算。
    """
    alpha = np.array(image.convert("RGBA"))[..., 3]
    rows = np.flatnonzero(alpha.max(axis=1) > 8)
    cols = np.flatnonzero(alpha.max(axis=0) > 8)
    if rows.size == 0 or cols.size == 0:
        return (0, 0, image.width, image.height)
    return (int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1)


class Mascot:
    """按可用素材自动降级的形象绘制器。

    绘制语义与 `elephant.draw_elephant` 一致：dest 是**脚底锚点**，
    x 为形象中心、y 为脚底，height 为主体像素高。
    """

    def __init__(self) -> None:
        self._mode = ""
        self._surface: cairo.ImageSurface | None = None
        self._box: tuple[int, int, int, int] = (0, 0, 0, 0)
        self._parts: elephant.Parts | None = None

    @property
    def mode(self) -> str:
        """当前用的是哪套形象：static / parts / none。"""
        self._load()
        return self._mode

    def _load(self) -> None:
        if self._mode:
            return
        if STATIC_IMAGE.exists():
            image = Image.open(STATIC_IMAGE).convert("RGBA")
            self._surface = pil_to_cairo(image)
            self._box = subject_box(image)
            self._mode = "static"
        elif LEGACY_IMAGE.exists():
            self._parts = elephant.load_parts(LEGACY_IMAGE)
            self._mode = "parts"
        else:
            self._mode = "none"

    def draw(self, ctx: cairo.Context, dest: tuple[float, float], height: float,
             alpha: float = 1.0, pose: elephant.Pose | None = None,
             slide: float = 0.0, scale: float = 1.0, bob: float = 0.0) -> None:
        """在 dest 处绘制形象。

        - pose：旧 2D 部件动画的姿势；静帧模式下忽略
        - slide：额外的水平位移（负值 = 从左边滑入）
        - scale：额外的缩放倍数（1.0 → 1.03 即轻微推近）
        - bob：额外的垂直位移（像素），用来做浮动
        """
        self._load()
        if self._mode == "static":
            self._draw_static(ctx, dest, height, alpha, slide, scale, bob)
        elif self._mode == "parts":
            self._draw_parts(ctx, dest, height, alpha, pose, slide, scale, bob)

    def _draw_static(self, ctx: cairo.Context, dest: tuple[float, float],
                     height: float, alpha: float, slide: float, scale: float,
                     bob: float) -> None:
        assert self._surface is not None
        x0, y0, x1, y1 = self._box
        subject_h = max(1, y1 - y0)
        subject_w = max(1, x1 - x0)
        k = (height / subject_h) * scale
        # 脚底锚点 → 贴图左上角
        dx = dest[0] - (x0 + subject_w / 2) * k + slide
        dy = dest[1] - y1 * k + bob
        ctx.save()
        ctx.translate(dx, dy)
        ctx.scale(k, k)
        ctx.set_source_surface(self._surface, 0, 0)
        ctx.paint_with_alpha(alpha)
        ctx.restore()

    def _draw_parts(self, ctx: cairo.Context, dest: tuple[float, float],
                    height: float, alpha: float, pose: elephant.Pose | None,
                    slide: float, scale: float, bob: float) -> None:
        assert self._parts is not None
        k = (height / LEGACY_SOURCE_HEIGHT) * scale
        elephant.draw_elephant(
            ctx, self._parts, pose or elephant.Pose(),
            (dest[0] + slide, dest[1] + bob), k, alpha,
        )


def avatar_path() -> Path | None:
    """个人头像（落版用）。没有就返回 None，调用方跳过整块。"""
    return AVATAR_IMAGE if AVATAR_IMAGE.exists() else None


def asset_mtimes() -> list[float]:
    """形象素材的修改时间。

    渲染的产物依赖这些素材：换了小象的图（重新生成、加眼镜……），
    已经渲染好的片段就该作废重渲，否则画面里还是旧形象。
    只看 Python 模块的修改时间是发现不了素材换了的。
    """
    times: list[float] = []
    for path in (STATIC_IMAGE, LEGACY_IMAGE, AVATAR_IMAGE):
        if path.exists():
            times.append(path.stat().st_mtime)
    return times
