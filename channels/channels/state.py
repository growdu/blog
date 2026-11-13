"""视频号的幂等状态。

沿用 `weixin/wechat/state.py` 的形状，但键换成了视频的东西：

- 内容层键是**成片的 sha256**——成片重出了就得重新出包
  （文案没变但成片变了很常见：重混音、修关键帧）。
- 视频号没有 API，拿不到平台返回的 id，所以对象层是空的，
  发布靠 `mark published` 显式回填。

状态文件留在 `channels/out/` 下，永不入库。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ChannelState:
    """一期在视频号上发到哪一步了。"""

    episode: str = ""
    video_sha256: str | None = None
    # packaged（出包待上传）| drafted（草稿已在平台上，等人点发表）| published（已发布）
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

    def get(self, episode: str) -> ChannelState:
        entry = self._load().get(episode)
        if not isinstance(entry, dict):
            return ChannelState(episode=episode)
        known = {}
        for name, spec in ChannelState.__dataclass_fields__.items():
            known[name] = entry.get(name, spec.default)
        known["episode"] = episode
        return ChannelState(**known)

    def save(self, episode: str, state: ChannelState) -> None:
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
