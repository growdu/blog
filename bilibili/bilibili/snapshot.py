"""outbox 状态快照：与视频号那边**字段完全一致**，只有 platform 不同。

形状由 `publish/spec/07-视频发布契约.md` §7.5 定死，
契约测试盯着两边不漂。

**只含公开信息**：token、secret 永不入库。
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
# 仓库根：bilibili/bilibili/snapshot.py → bilibili/bilibili → bilibili → 仓库根
REPO_ROOT = Path(__file__).resolve().parents[2]


def _now() -> datetime:
    """当前时间（UTC）。

    单独拎成一个函数，是为了让测试能控制它——
    `datetime` 是不可变类型，patch 不了它的 `now`。
    """
    return datetime.now(timezone.utc)


def automation_of(capabilities_dir: str | Path | None = None) -> str:
    """当前档位：从能力声明的顶层 `automation` 读。

    **不写死 "manual"**——档位由 `publish/capabilities/bilibili.toml` 说了算，
    写死的话，改完 TOML 快照还在说旧档位，那是静默的假话。
    """
    import tomllib

    base = Path(capabilities_dir) if capabilities_dir else (
        REPO_ROOT / "publish" / "capabilities")
    path = base / "bilibili.toml"
    if not path.is_file():
        raise RuntimeError(f"能力声明不存在：{path}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return str(data.get("automation", "manual"))


def write_snapshot(path: str | Path, *, episode: str, status: str, title: str,
                   package_dir: str, published_url: str | None = None,
                   reason: str = "",
                   automation: str | None = None) -> Path:
    """写一份状态快照。

    **内容没变就不重写**：`updated_at` 记的是「状态最后一次真的变了」的时间，
    不是「最后一次跑了这个命令」的时间。否则每次重跑都把工作树弄脏，
    而内容一个字都没变。
    """
    out = Path(path)
    payload = {
        "content_id": episode,
        "platform": "bilibili",
        "kind": "video",
        "status": status,
        "automation": automation if automation is not None else automation_of(),
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
