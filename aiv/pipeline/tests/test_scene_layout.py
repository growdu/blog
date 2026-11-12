"""场景版式：说明不能压到字幕，芯片不能互相压字。

这两条都是「画面上看得见」的问题，靠肉眼看渲染图抓不住——
渲染图只给你一张快照，动画中间某一帧的压字就漏了。
所以这里把布局算成可测的数，用测试盯住。

**说明与字幕为什么必须分开**：字幕是烧进画面的一行白字，
场景说明是画面左下角的一行深字。两行都在下缘，
位置一近就会绞在一起——实测出现过说明的「响」和字幕的「攒」
笔画互咬。所以规则定成：说明的**墨迹下沿**必须高于字幕带的**上沿**。
"""
from __future__ import annotations

import re
from pathlib import Path

import cairo
import pytest

from pyv import align
from pyv import contract as contract_mod
from pyv import subtitle as subtitle_mod
from pyv.inkbox import ink_bottom
from pyv.scenes import s04_spill

ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = Path(s04_spill.__file__).parent

EPISODES = {
    "pg-parallel-decode": ("字幕-并行解码.md", "pg-parallel-decode.json"),
    "csn-total-ordering": ("字幕-CSN全序.md", "csn-total-ordering.json"),
    "wal-interleave": ("字幕-WAL顺序.md", "wal-interleave.json"),
    "parallel-apply": ("字幕-并行apply.md", "parallel-apply.json"),
    "structured-ddl": ("字幕-结构化DDL.md", "structured-ddl.json"),
}

# 场景说明画在画面高度的几分之几处。EP01 定下来的规矩是 0.86。
CAPTION_RATIO = 0.86
CAPTION_X_RATIO = 0.06
CAPTION_SIZE = 44


def _subtitle_band_top() -> float:
    """字幕带的最高点——任何一行字幕都不可能高过这里。

    用字体度量算，不用墨迹：拉丁小写字母的墨迹上沿比汉字低得多，
    拿墨迹算会漏掉「只有小写字母的那行字幕」。
    """
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1920, 1080)
    ctx = cairo.Context(surface)
    ctx.select_font_face("PingFang SC")
    ctx.set_font_size(subtitle_mod.BURN_FONT_SIZE)
    ascent = ctx.font_extents()[0]
    baseline = 1080 - subtitle_mod.BURN_MARGIN_V - ctx.font_extents()[1]
    return baseline - ascent


def _caption_ratio(module_path: Path) -> float | None:
    """这个场景把说明画在画面高度的几分之几处。"""
    source = module_path.read_text(encoding="utf-8")
    match = re.search(
        r'text\(ctx,\s*p\["caption"\][^)]*?h\s*\*\s*([0-9.]+)', source
    )
    return float(match.group(1)) if match else None


@pytest.mark.parametrize("module_path", sorted(SCENES_DIR.glob("*.py")),
                         ids=lambda p: p.stem)
def test_the_caption_is_placed_at_the_series_position(module_path):
    """所有场景的说明都画在同一个高度。

    位置各写各的，就会出现某一期比别的期低一截、
    压到烧录字幕上的情况。
    """
    ratio = _caption_ratio(module_path)
    if ratio is None:
        pytest.skip("这个场景没有画说明")
    assert ratio == pytest.approx(CAPTION_RATIO), (
        f"{module_path.stem} 的说明画在 h*{ratio}，"
        f"全季统一是 h*{CAPTION_RATIO}"
    )


@pytest.mark.parametrize("episode", sorted(EPISODES))
def test_the_caption_ink_stays_above_the_subtitle_band(episode):
    """说明的墨迹下沿必须高于字幕带上沿。"""
    script, contract_name = EPISODES[episode]
    contract = contract_mod.load_contract(ROOT / "contracts" / contract_name)
    band_top = _subtitle_band_top()

    for segment in contract.segments:
        caption = segment.params.get("caption")
        if not caption:
            continue
        module_path = SCENES_DIR / f"{segment.renderer.split('.')[-1]}.py"
        ratio = _caption_ratio(module_path)
        assert ratio is not None, f"{module_path.name} 里找不到说明的画法"
        bottom = ink_bottom(caption, CAPTION_X_RATIO * 1920,
                            ratio * 1080, CAPTION_SIZE)
        assert bottom < band_top, (
            f"{episode} 的 {segment.renderer} 说明墨迹下沿在 y={bottom:.0f}，"
            f"字幕带从 y={band_top:.0f} 开始，两行会绞在一起"
        )


@pytest.mark.parametrize("episode", sorted(EPISODES))
def test_every_episode_has_subtitles_to_collide_with(episode):
    """字幕表要是空的，这条守卫就等于没守。"""
    script, _ = EPISODES[episode]
    assert align.parse_subtitle_table(ROOT / script), f"{episode} 没有字幕"


# ---------------------------------------------------------------- spill 场景


def _overlap(a: tuple[float, float, float, float],
             b: tuple[float, float, float, float]) -> float:
    """两个矩形重叠的面积（不相交为 0）。"""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    dx = min(ax + aw, bx + bw) - max(ax, bx)
    dy = min(ay + ah, by + bh) - max(ay, by)
    return dx * dy if dx > 0 and dy > 0 else 0.0


def _chips(count: int = 6):
    return ["INSERT", "INSERT", "UPDATE", "UPDATE", "DELETE", "INSERT"][:count]


@pytest.mark.parametrize("t", [i / 40 for i in range(41)])
def test_no_two_chips_ever_overlap(t):
    """任何时刻，两块芯片都不能叠在一起。

    叠在一起的后果是后一块把前一块的字盖住，
    画面上会读成半个单词（实测出现过「SERT」）。
    """
    layout = s04_spill.chip_layout(_chips(), 4, t)
    chip_w, chip_h = 1920 * s04_spill.CHIP_W_RATIO, 1080 * s04_spill.CHIP_H_RATIO
    for i, first in enumerate(layout):
        for second in layout[i + 1:]:
            a = (first.x, first.y, chip_w, chip_h)
            b = (second.x, second.y, chip_w, chip_h)
            assert _overlap(a, b) == 0, (
                f"t={t:.3f} 时第 {first.index} 块与第 {second.index} 块重叠了"
            )


def test_the_spilled_chips_end_up_on_the_disk():
    """搬完的芯片要落在磁盘那块区域里，不能停在半路上。"""
    layout = s04_spill.chip_layout(_chips(), 4, t=1.0)
    disk_x = 1920 * s04_spill.DISK_X_RATIO
    disk_w = 1920 * s04_spill.DISK_W_RATIO
    spilled = [c for c in layout if c.index < 4]
    staying = [c for c in layout if c.index >= 4]
    assert len(spilled) == 4 and len(staying) == 2
    for chip in spilled:
        assert chip.progress == pytest.approx(1.0), "搬走的芯片应当已经落盘"
        assert disk_x <= chip.x <= disk_x + disk_w, "落点应当在磁盘区里"
    for chip in staying:
        assert chip.progress == 0.0, "留在内存里的芯片不该动"


def test_only_one_chip_is_in_flight_at_a_time():
    """一次只搬一块：几块同时飞，路径会交叉。"""
    for i in range(0, 41):
        t = i / 40
        moving = [c for c in s04_spill.chip_layout(_chips(), 4, t)
                  if 0.0 < c.progress < 1.0]
        assert len(moving) <= 1, f"t={t:.3f} 时有 {len(moving)} 块同时在飞"
