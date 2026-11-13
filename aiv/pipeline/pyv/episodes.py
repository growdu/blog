"""期号登记表：EP 号 → 口播稿 / 契约 / 旁白。

**这里是 Python 侧唯一的登记表。** Makefile 里另有一份（shell 读不了
Python 模块），两份必须永远一致——漂移由 `tests/test_makefile.py` 盯着。

期号用**英文 id**（`row-lock`）而不是序号（`ep06`）：id 出现在文件名、
契约、发布元数据里，换期不改文件名；序号只是播放顺序，
在 `EP_NUMBERS` 里单独映射。
"""
from __future__ import annotations

from pathlib import Path

AIV_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = AIV_ROOT / "contracts"

#: EP 号 → 口播稿文件名（相对 aiv/）
EPISODES: dict[str, str] = {
    "pg-parallel-decode": "字幕-并行解码.md",
    "csn-total-ordering": "字幕-CSN全序.md",
    "wal-interleave": "字幕-WAL顺序.md",
    "parallel-apply": "字幕-并行apply.md",
    "structured-ddl": "字幕-结构化DDL.md",
    "row-lock": "字幕-行锁.md",
}

#: 播出顺序 → EP 号。序号只表示「第几期」，不进任何文件名。
EPISODE_ORDER: tuple[str, ...] = (
    "pg-parallel-decode",
    "csn-total-ordering",
    "wal-interleave",
    "parallel-apply",
    "structured-ddl",
    "row-lock",
)

#: EP 号 → 期号标签（ep01 …）
EP_NUMBERS: dict[str, str] = {
    ep: f"ep{index:02d}" for index, ep in enumerate(EPISODE_ORDER, start=1)
}

DEFAULT_EP = EPISODE_ORDER[0]


def script_path(ep: str) -> Path:
    """这一期的口播稿。"""
    return AIV_ROOT / EPISODES[ep]


def contract_path(ep: str) -> Path:
    """这一期的视觉分镜契约。"""
    return CONTRACTS_DIR / f"{ep}.json"


def narration_path(ep: str) -> Path:
    """这一期的旁白音频（媒体产物，不入库）。"""
    return AIV_ROOT / f"narration_{ep}.mp3"


def storyboard_path(ep: str) -> Path:
    """这一期的时间轴（媒体产物，不入库，由 align 算出）。"""
    return AIV_ROOT / f"storyboard_{ep}.json"


def known_eps() -> list[str]:
    return list(EPISODES)
