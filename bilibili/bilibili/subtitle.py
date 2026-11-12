"""字幕：storyboard 的字幕事件 → SRT。

时间轴是本机产物（跟着本机旁白走），所以字幕文件也是本地产物，不入库。

**不 import `pyv.timeline`**：adapter 只认 `pyv.epmeta` 与 `pyv.preflight`
两个契约层模块（规格 §3.3）。这里用结构化类型描述「一个有 start/end/text 的事件」，
这样字幕生成器不依赖时间轴模块的具体实现。

代价是「storyboard 里的字幕从哪来」这条规则写了两遍（这里 + `pyv.timeline`）。
**两边不许漂**：`publish/tests/test_bilibili_subtitle_contract.py` 拿真实的
storyboard 对照两边结果，规则一改就会红。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable


@runtime_checkable
class SubtitleEventLike(Protocol):
    """字幕事件：只要有起点、终点与文本。"""

    start: float
    end: float
    text: str


@dataclass(frozen=True)
class SubtitleEvent:
    """adapter 自带的字幕事件。"""

    start: float
    end: float
    text: str


def events_from_storyboard(raw: dict) -> list[SubtitleEvent]:
    """从 storyboard 的原始 JSON 里取字幕事件。

    规则与 `pyv.timeline.Storyboard.subtitle_events()` 一致：
    **有 `subtitles` 用 `subtitles`，没有就退化成按场景出字幕**
    （一个场景一段，文本取场景的 `subtitle`）。

    同样的规则在 `pyv.timeline` 里也有一份——那边是 storyboard 格式的
    主人，这份是 adapter 自己的一份拷贝。两边不许漂，漂了会有测试红。
    """
    events: list[SubtitleEvent] = []
    for item in raw.get("subtitles") or []:
        events.append(SubtitleEvent(
            start=float(item["start"]),
            end=float(item["end"]),
            text=str(item.get("text", "")),
        ))
    if events:
        return events
    for scene in raw.get("scenes") or []:
        events.append(SubtitleEvent(
            start=float(scene["start"]),
            end=float(scene["end"]),
            text=str(scene.get("subtitle", "")),
        ))
    return events


def format_timestamp(seconds: float) -> str:
    """秒 → SRT 的 HH:MM:SS,mmm。"""
    total_ms = int(round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, ms = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def build_srt(events: Sequence[SubtitleEventLike]) -> str:
    """字幕事件 → SRT 文本。

    块之间空一行、文件末尾一个换行——这是 SRT 的标准形状。
    """
    blocks = []
    for index, event in enumerate(events, start=1):
        blocks.append(
            f"{index}\n"
            f"{format_timestamp(event.start)} --> {format_timestamp(event.end)}\n"
            f"{event.text}\n"
        )
    return "\n".join(blocks)
