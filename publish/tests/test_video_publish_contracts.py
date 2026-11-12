"""跨平台的收口检查：两个平台的契约不许各自漂。

这一层是**契约层**（`publish/`），所以它可以同时看见两个平台——
adapter 之间仍然互不引用（规格 §3.3）。
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for extra in (REPO_ROOT / "channels", REPO_ROOT / "bilibili",
              REPO_ROOT / "aiv" / "pipeline"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from bilibili import snapshot as bili_snapshot       # noqa: E402
from channels import snapshot as channels_snapshot   # noqa: E402


def test_the_two_platforms_write_the_same_snapshot_shape():
    """字段完全一致，只有 platform 不同（规格 §7.5）。

    两个平台的快照靠 `content_id` 对接，谁改了字段另一个就接不上——
    这种错只有契约测试能抓。
    """
    assert set(bili_snapshot.SNAPSHOT_KEYS) == set(channels_snapshot.SNAPSHOT_KEYS)


def test_the_bilibili_subtitle_events_match_the_timeline_owner():
    """adapter 自己读 storyboard，规则不许和 `pyv.timeline` 漂。

    adapter 只能 import `epmeta` 与 `preflight`（规格 §3.3），
    所以「字幕从哪来」这条规则写了两遍：一份在 `pyv.timeline`（storyboard
    格式的主人），一份在 `bilibili/subtitle.py`。这条测试拿真实 storyboard
    对照两边，规则一改就会红。
    """
    from bilibili import subtitle
    from pyv.timeline import Storyboard

    boards = sorted((REPO_ROOT / "aiv").glob("storyboard_*.json"))
    if not boards:
        pytest.skip("本机没有 storyboard（它们是 gitignore 的本地产物）")

    for path in boards:
        raw = json.loads(path.read_text(encoding="utf-8"))
        mine = [(e.start, e.end, e.text)
                for e in subtitle.events_from_storyboard(raw)]
        theirs = [(e.start, e.end, e.text)
                  for e in Storyboard.load(path).subtitle_events()]
        assert mine == theirs, f"{path.name} 的字幕事件两边不一致"
