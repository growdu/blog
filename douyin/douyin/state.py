"""抖音的幂等状态。

沿用 `channels/channels/state.py` 的形状，但有两处不同：

- **内容层键是成片的 sha256**——成片重出了就得重新出包
  （文案没变但成片变了很常见：重混音、修关键帧）。
- **档位只有两个**：`packaged`（出包待上传）与 `published`（已发布）。
  视频号有 `drafted`（草稿已在平台上）是因为视频号确实有草稿箱；
  **抖音创作者后台的草稿能力我们没核实过**，所以不设那一档——
  设一个没验证过的档位，等于给「其实存不下来」发一张通行证。

状态文件留在 `douyin/out/` 下，永不入库。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class DouyinState:
    """一期在抖音上发到哪一步了。"""

    episode: str = ""
    video_sha256: str | None = None
    # packaged（出包待上传）| published（已发布）
    status: str = "packaged"
    published_url: str | None = None
    updated_at: str | None = None


class StateStore:
    """一个 JSON 文件存着每一期的状态。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _load(self) -> dict:
        if not self.path.is_file():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        episodes = raw.get("episodes", {})
        return episodes if isinstance(episodes, dict) else {}

    def get(self, episode: str) -> DouyinState:
        entry = self._load().get(episode)
        if not isinstance(entry, dict):
            return DouyinState(episode=episode)
        known = {}
        for name, spec in DouyinState.__dataclass_fields__.items():
            known[name] = entry.get(name, spec.default)
        known["episode"] = episode
        return DouyinState(**known)

    def save(self, episode: str, state: DouyinState) -> None:
        episodes = self._load()
        state.episode = episode
        state.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        episodes[episode] = asdict(state)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"episodes": episodes}, ensure_ascii=False, indent=2,
                       sort_keys=True),
            encoding="utf-8",
        )
