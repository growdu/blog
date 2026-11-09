"""视觉段与口播句的映射。

契约分两层：
- 视觉段（Scene）—— 一个 renderer 覆盖一段时间，段间必须首尾相接无缝
- 字幕事件（SubtitleEvent）—— 逐句对齐旁白，精确到静音点

两者不等长：一段视觉可以覆盖 1~2 句旁白。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    id: str
    renderer: str
    sentences: tuple[int, ...]


SEGMENTS: tuple[Segment, ...] = (
    Segment("s01", "pyv.scenes.s01_intro", (0, 1)),
    Segment("s02", "pyv.scenes.s02_serial", (2, 3)),
    Segment("s03", "pyv.scenes.s03_cores", (4, 5)),
    Segment("s04", "pyv.scenes.s04_parallel", (6,)),
    Segment("s05", "pyv.scenes.s05_order", (7, 8)),
    Segment("s06", "pyv.scenes.s06_outro", (9,)),
)


def sentence_count() -> int:
    """口播稿应有的句数。"""
    return sum(len(s.sentences) for s in SEGMENTS)
