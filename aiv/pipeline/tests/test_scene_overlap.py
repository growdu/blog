"""元素级遮挡守卫：画面里不许有两处字互相压住。

**为什么帧级守卫不够。** `test_vertical_layout.py` 那种守卫只看**整帧**
墨迹的外接矩形——「A 芯片盖住 B 芯片的字」「箭头从字中间穿过去」「两个字
糊成一团」这类缺陷，帧的外接矩形完全正常，守卫全绿。EP03 那 0.4 秒就是这么
漏过去的：竖版 396 次渲染全部合规，逐帧看图才发现飞行中的橙色 INSERT 压住
了蓝色 DELETE 的字。

**怎么查。** 插桩 `pyv.draw.text` 与 `pyv.draw.arrow`：
每次画字记下它的**墨迹包围盒**（`text_path` + `path_extents`，不是字号的行高），
每次画箭头记下线段与箭头头部，两两求交。

**覆盖。** 六期契约里的**全部 26 个场景模块**（`test_every_scene_module_is_
covered` 钉住这一点），横竖两个画幅，每个模块扫 **21 个时刻**（0.00 到 1.00，
步长 0.05）——动画的中间态才是出事的地方，只看首帧和末帧等于没看。

**半透明的字不算遮挡。** 淡到 0.6 以下的是背景（让位、影子、幽灵），
它跟别的东西压在一起是故意的。
"""
from __future__ import annotations

import importlib
import math
from pathlib import Path

import cairo
import pytest

from pyv import contract as contract_mod
from pyv import draw, episodes as episodes_mod, fonts, scene_layout

ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = Path(contract_mod.__file__).parent / "scenes"

#: 画幅
LANDSCAPE = (1920, 1080)
PORTRAIT = (1080, 1920)

#: 扫的时刻：0.00 到 1.00，步长 0.05。
#:
#: 一段动画的中间态才是出事的地方——EP03 那处遮挡发生在 t=0.55 附近，
#: 只看首帧末帧是碰不到的。
TIMES = tuple(round(i * 0.05, 2) for i in range(21))

#: 淡到多少以下就不算「可见的字」。
#:
#: 让位、影子、幽灵这些是背景，它跟别的东西压在一起是**故意**的。
#: 0.6 是「还看得清」与「已经退成背景」的分界。
VISIBLE_ALPHA = 0.6

#: 包围盒往里收几像素再判相交。
#:
#: 两行字挨着但没压上时，包围盒可能刚好边缘相接——那不是遮挡。
INSET = 1.0


class Box:
    """一处墨迹的包围盒。"""

    def __init__(self, label: str, x0: float, y0: float, x1: float, y1: float):
        self.label = label
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1

    def shrunk(self, inset: float = INSET) -> "Box":
        return Box(self.label, self.x0 + inset, self.y0 + inset,
                   self.x1 - inset, self.y1 - inset)

    def __repr__(self) -> str:
        return f"<{self.label} {self.x0:.0f},{self.y0:.0f}→{self.x1:.0f},{self.y1:.0f}>"


def _ink_box(ctx, s: str, x: float, y: float, size: float,
             anchor: str, bold: bool) -> Box:
    """量出这行字的**墨迹**包围盒。

    用 `text_path` + `path_extents` 而不是 `text_extents` 的高：
    后者给的是字体的行高（ascent+descent），比实际墨迹高一大截——
    两行上下相邻的字会被算成「压住了」。

    横向偏移要跟 `draw.text` 算的一模一样（它用 `.width` 而不是步进宽度
    来居中），不然量出来的位置跟画出来的位置对不上。
    """
    ctx.select_font_face(
        fonts.font_family(),
        cairo.FONT_SLANT_NORMAL,
        cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL,
    )
    ctx.set_font_size(size)
    width = ctx.text_extents(s).width
    if anchor == "center":
        origin = x - width / 2
    elif anchor == "right":
        origin = x - width
    else:
        origin = x
    ctx.new_path()
    ctx.move_to(origin, y)
    ctx.text_path(s)
    x0, y0, x1, y1 = ctx.path_extents()
    ctx.new_path()
    return Box(s, x0, y0, x1, y1)


def _segment_crosses(x1: float, y1: float, x2: float, y2: float,
                     box: Box) -> bool:
    """线段是否穿过矩形（Liang–Barsky 裁剪）。"""
    dx, dy = x2 - x1, y2 - y1
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x1 - box.x0), (dx, box.x1 - x1),
                 (-dy, y1 - box.y0), (dy, box.y1 - y1)):
        if p == 0:
            if q < 0:
                return False
        else:
            r = q / p
            if p < 0:
                if r > t1:
                    return False
                if r > t0:
                    t0 = r
            else:
                if r < t0:
                    return False
                if r < t1:
                    t1 = r
    return True


class Probe:
    """插桩：把这一帧画过的字与箭头都记下来。"""

    def __init__(self):
        self.texts: list[Box] = []
        self.arrows: list[tuple] = []

    # -- 记录 ----------------------------------------------------------
    def text(self, ctx, s, x, y, size, color, anchor="left", bold=False,
             alpha=1.0):
        if alpha >= VISIBLE_ALPHA and s.strip():
            self.texts.append(_ink_box(ctx, s, x, y, size, anchor, bold))
        return None

    def arrow(self, ctx, x1, y1, x2, y2, color, width=6.0, head=22.0,
              alpha=1.0):
        if alpha >= VISIBLE_ALPHA:
            self.arrows.append((x1, y1, x2, y2, width, head))
        return None

    # -- 判据 ----------------------------------------------------------
    def text_over_text(self) -> list[tuple[Box, Box, float]]:
        """两处可见的字互相压住。"""
        hits = []
        for i in range(len(self.texts)):
            a = self.texts[i].shrunk()
            for j in range(i + 1, len(self.texts)):
                b = self.texts[j].shrunk()
                ox = min(a.x1, b.x1) - max(a.x0, b.x0)
                oy = min(a.y1, b.y1) - max(a.y0, b.y0)
                if ox > 0 and oy > 0:
                    hits.append((self.texts[i], self.texts[j], ox * oy))
        return hits

    def arrow_over_text(self) -> list[tuple[tuple, Box]]:
        """箭头从字里穿过去。

        箭杆有粗细（`width`），所以判的是**两条平行线**围成的带子；
        箭头头部是一个以箭头尖为心的圆。
        """
        hits = []
        for (x1, y1, x2, y2, width, head) in self.arrows:
            dx, dy = x2 - x1, y2 - y1
            length = math.hypot(dx, dy) or 1.0
            px = -dy / length * width / 2
            py = dx / length * width / 2
            for box in self.texts:
                inner = box.shrunk()
                if (_segment_crosses(x1 + px, y1 + py, x2 + px, y2 + py, inner)
                        or _segment_crosses(x1 - px, y1 - py, x2 - px, y2 - py,
                                            inner)):
                    hits.append(((x1, y1, x2, y2), box))
                    continue
                if (inner.x0 <= x2 <= inner.x1 and inner.y0 <= y2 <= inner.y1
                        and (x2 - inner.x0) ** 2 + (y2 - inner.y0) ** 2 <= head ** 2):
                    hits.append(((x1, y1, x2, y2), box))
        return hits


def _probe_frame(renderer, params, t, w, h, monkeypatch, modules=()) -> Probe:
    """画一帧，把这一帧的字与箭头都记下来。

    **场景模块各自绑着 `draw.text` / `draw.arrow`**（`from pyv.draw import …`
    是在导入时绑定的），所以只补 `pyv.draw` 是不够的——每个用到的模块都要
    单独补一遍。
    """
    probe = Probe()
    original_text = draw.text
    original_arrow = draw.arrow

    def recording_text(ctx, s, x, y, size, color, anchor="left", bold=False,
                       alpha=1.0):
        probe.text(ctx, s, x, y, size, color, anchor=anchor, bold=bold,
                   alpha=alpha)
        return original_text(ctx, s, x, y, size, color, anchor=anchor,
                             bold=bold, alpha=alpha)

    def recording_arrow(ctx, x1, y1, x2, y2, color, width=6.0, head=22.0,
                        alpha=1.0):
        probe.arrow(ctx, x1, y1, x2, y2, color, width=width, head=head,
                    alpha=alpha)
        return original_arrow(ctx, x1, y1, x2, y2, color, width=width,
                              head=head, alpha=alpha)

    monkeypatch.setattr(draw, "text", recording_text)
    monkeypatch.setattr(draw, "arrow", recording_arrow)
    monkeypatch.setattr(scene_layout, "text", recording_text)
    if hasattr(scene_layout, "arrow"):
        monkeypatch.setattr(scene_layout, "arrow", recording_arrow)
    for module in modules:
        if hasattr(module, "text"):
            monkeypatch.setattr(module, "text", recording_text)
        if hasattr(module, "arrow"):
            monkeypatch.setattr(module, "arrow", recording_arrow)

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surface)
    renderer(ctx, t, w, h, params)
    return probe


def _segments():
    """六期契约里的全部场景段（带契约里的真实文案）。"""
    for episode in episodes_mod.EPISODE_ORDER:
        contract = contract_mod.load_contract(
            ROOT / "contracts" / f"{episode}.json")
        for segment in contract.segments:
            yield episode, segment


def _render_segment(segment):
    """场景的画法 + 它自己绑着的模块（补桩要用）。"""
    module = importlib.import_module(segment.renderer)

    def renderer(ctx, t, w, h, params):
        module.render(ctx, t, w, h, params)

    return renderer, (module,)


SEGMENTS = list(_segments())
ORIENTATIONS = (("横版", LANDSCAPE), ("竖版", PORTRAIT))


@pytest.mark.parametrize("episode,segment", SEGMENTS,
                         ids=[f"{ep}-{s.renderer.split('.')[-1]}"
                              for ep, s in SEGMENTS])
@pytest.mark.parametrize("orientation,canvas", ORIENTATIONS,
                         ids=[o for o, _ in ORIENTATIONS])
def test_no_two_texts_overlap(episode, segment, orientation, canvas,
                               monkeypatch):
    """一处字不许压住另一处字。"""
    renderer, modules = _render_segment(segment)
    w, h = canvas
    findings = []
    for t in TIMES:
        probe = _probe_frame(renderer, segment.params, t, w, h, monkeypatch,
                             modules)
        for a, b, area in probe.text_over_text():
            findings.append(f"t={t}  {a} 压住 {b}（重叠 {area:.0f} px²）")
    assert not findings, (
        f"{episode} 的 {segment.renderer} 在{orientation}有两处字压在一起：\n  "
        + "\n  ".join(findings)
    )


@pytest.mark.parametrize("episode,segment", SEGMENTS,
                         ids=[f"{ep}-{s.renderer.split('.')[-1]}"
                              for ep, s in SEGMENTS])
@pytest.mark.parametrize("orientation,canvas", ORIENTATIONS,
                         ids=[o for o, _ in ORIENTATIONS])
def test_no_arrow_crosses_a_text(episode, segment, orientation, canvas,
                                 monkeypatch):
    """箭头不许从字里穿过去。

    「整组发出」那条箭头与飞出去的芯片同在一条通道上：芯片飞过去时箭头
    会从字里穿出来，看着像字被箭头劈开了。
    """
    renderer, modules = _render_segment(segment)
    w, h = canvas
    findings = []
    for t in TIMES:
        probe = _probe_frame(renderer, segment.params, t, w, h, monkeypatch,
                             modules)
        for arrow, box in probe.arrow_over_text():
            findings.append(
                f"t={t}  箭头 {arrow} 从 {box} 里穿过去")
    assert not findings, (
        f"{episode} 的 {segment.renderer} 在{orientation}有箭头穿过字：\n  "
        + "\n  ".join(findings)
    )


def test_every_scene_module_is_covered():
    """守卫声称覆盖全部场景模块——那就钉住这个声称。

    新加一个场景模块却没进契约，守卫就扫不到它，而文档还在说「全部覆盖」。
    """
    used = {segment.renderer.split(".")[-1] for _, segment in SEGMENTS}
    on_disk = {path.stem for path in SCENES_DIR.glob("*.py")
               if path.stem != "__init__"}
    assert used == on_disk, (
        f"契约里用到的场景模块与目录里的对不上："
        f"目录有契约没用 {sorted(on_disk - used)}；"
        f"契约用了目录没有 {sorted(used - on_disk)}"
    )
    assert len(used) == 26, f"场景模块数变了：{len(used)}"


def test_the_probe_can_see_an_overlap(monkeypatch):
    """**守卫自己得会报警**，不然它只是一段永远绿的代码。

    画两处故意压在一起的字，探针必须报出来。写死了判据却没有这条自检，
    探针坏掉时守卫会一直绿着。
    """
    def renderer(ctx, t, w, h, params):
        draw.text(ctx, "第一处", 200, 200, 48, "#000000")
        draw.text(ctx, "第二处", 220, 210, 48, "#000000")

    probe = _probe_frame(renderer, {}, 0.0, 800, 600, monkeypatch)
    hits = probe.text_over_text()
    assert hits, "两处压在一起的字，探针居然没报出来——守卫是瞎的"
    assert hits[0][2] > 0


def test_the_probe_can_see_an_arrow_over_a_text(monkeypatch):
    """箭头压字这条判据也得会报警。"""
    def renderer(ctx, t, w, h, params):
        draw.text(ctx, "被穿过的字", 200, 200, 48, "#000000")
        draw.arrow(ctx, 100, 190, 400, 190, "#000000", 8, 24)

    probe = _probe_frame(renderer, {}, 0.0, 800, 600, monkeypatch)
    hits = probe.arrow_over_text()
    assert hits, "箭头从字里穿过去，探针居然没报出来——判据是瞎的"
