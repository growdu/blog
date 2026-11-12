"""outbox 状态快照：跨平台统一格式的公开状态。

**只含公开信息**：token、secret 永不入库。
格式由 `publish/spec/07-视频发布契约.md` §7.5 定死，
B站那边有一份形状一样的实现，契约测试盯着两边不漂。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

# 快照的字段就是这些，多一个少一个都会被契约测试抓住。
SNAPSHOT_KEYS = (
    "content_id",
    "platform",
    "kind",
    "status",
    "automation",
    "title",
    "published_url",
    "package_dir",
    "updated_at",
    "reason",
)

OUTBOX_DIR = Path(__file__).resolve().parents[2] / "publish" / "outbox"


def _now() -> datetime:
    """当前时间（UTC）。

    单独拎成一个函数，是为了让测试能控制它——
    `datetime` 是不可变类型，patch 不了它的 `now`。
    """
    return datetime.now(timezone.utc)


def write_snapshot(path: str | Path, *, episode: str, status: str, title: str,
                   package_dir: str, published_url: str | None = None,
                   reason: str = "") -> Path:
    """写一份状态快照。

    **内容没变就不重写**：`updated_at` 记的是「状态最后一次真的变了」的时间，
    不是「最后一次跑了这个命令」的时间。否则每次重跑都把工作树弄脏，
    而内容一个字都没变。
    """
    out = Path(path)
    payload = {
        "content_id": episode,
        "platform": "channels",
        "kind": "video",
        "status": status,
        "automation": "manual",
        "title": title,
        "published_url": published_url,
        "package_dir": package_dir,
        "updated_at": _now().isoformat(timespec="seconds"),
        "reason": reason,
    }
    assert set(payload) == set(SNAPSHOT_KEYS), "快照字段与契约不一致"
    if out.is_file():
        try:
            old = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            old = None
        if isinstance(old, dict) and \
                {k: v for k, v in old.items() if k != "updated_at"} == \
                {k: v for k, v in payload.items() if k != "updated_at"}:
            return out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return out
