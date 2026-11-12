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


def write_snapshot(path: str | Path, *, episode: str, status: str, title: str,
                   package_dir: str, published_url: str | None = None,
                   reason: str = "") -> Path:
    """写一份状态快照。"""
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
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reason": reason,
    }
    assert set(payload) == set(SNAPSHOT_KEYS), "快照字段与契约不一致"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return out
