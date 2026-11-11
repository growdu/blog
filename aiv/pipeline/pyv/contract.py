"""视觉分镜契约：这一期的段落划分与画面内容。

一份契约 = 一期视频的分镜，里面有两样东西：

- `segments[]`——句到视觉段的映射（哪几句配哪张图）
- `segments[].params`——这张图上要写的字与数字

**时间轴不在契约里**：时间轴由旁白决定，由 `align` 按静音点算出来。
契约只回答「讲什么、图上写什么」，不回答「什么时候出现」。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# aiv/ 是 pipeline/ 的上一级：pyv/contract.py → pyv → pipeline → aiv
AIV_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = AIV_ROOT / "contracts"
DEFAULT_CONTRACT = CONTRACTS_DIR / "pg-parallel-decode.json"


@dataclass(frozen=True)
class Segment:
    """一个视觉段：覆盖哪几句旁白，用哪个渲染器，画面上写什么。"""

    id: str
    renderer: str
    sentences: tuple[int, ...]
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Contract:
    """一期视频的视觉分镜。"""

    version: int
    episode: str
    title: str
    segments: tuple[Segment, ...]
    path: Path | None = None

    @property
    def sentence_count(self) -> int:
        """这一期口播稿应有的句数。"""
        return sum(len(s.sentences) for s in self.segments)

    def segment_for_sentence(self, index: int) -> Segment | None:
        for segment in self.segments:
            if index in segment.sentences:
                return segment
        return None


def load_contract(path: str | Path | None = None) -> Contract:
    """读取并校验视觉分镜契约。"""
    target = Path(path) if path else DEFAULT_CONTRACT
    if not target.is_file():
        raise FileNotFoundError(f"视觉分镜契约不存在：{target}")
    raw = json.loads(target.read_text(encoding="utf-8"))
    return parse_contract(raw, path=target)


def parse_contract(raw: dict, path: Path | None = None) -> Contract:
    """校验契约结构，构造 Contract。"""
    version = int(raw.get("version", 0))
    if version != 1:
        raise ValueError(f"契约 version 必须为 1，实际 {version}")

    raw_segments = raw.get("segments") or []
    if not raw_segments:
        raise ValueError("契约的 segments 为空")

    segments: list[Segment] = []
    seen_ids: set[str] = set()
    for item in raw_segments:
        sid = item.get("id")
        if not sid:
            raise ValueError("契约里有段没有 id")
        if sid in seen_ids:
            raise ValueError(f"契约里有重复的段 id：{sid}")
        seen_ids.add(sid)
        renderer = item.get("renderer")
        if not renderer:
            raise ValueError(f"段 {sid} 缺少 renderer")
        sentences = tuple(int(i) for i in item.get("sentences") or ())
        if not sentences:
            raise ValueError(f"段 {sid} 没有分配任何句子")
        params = item.get("params") or {}
        if not isinstance(params, dict):
            raise ValueError(f"段 {sid} 的 params 必须是对象")
        segments.append(Segment(id=sid, renderer=renderer,
                                sentences=sentences, params=params))

    _check_sentence_coverage(segments)

    return Contract(
        version=version,
        episode=str(raw.get("episode", "")),
        title=str(raw.get("title", "")),
        segments=tuple(segments),
        path=path,
    )


def _check_sentence_coverage(segments: list[Segment]) -> None:
    """句子必须被分镜恰好覆盖一次：漏了、重了都不行。"""
    seen: dict[int, str] = {}
    for segment in segments:
        for index in segment.sentences:
            if index in seen:
                raise ValueError(
                    f"第 {index} 句被分到两个段：{seen[index]} 与 {segment.id}"
                )
            seen[index] = segment.id
    expected = set(range(len(seen)))
    actual = set(seen)
    if actual != expected:
        missing = sorted(expected - actual)
        raise ValueError(f"分镜漏掉了第 {missing} 句")
