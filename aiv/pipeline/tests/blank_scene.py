"""空白场景：只出白底，用来隔离验证字幕烧录。"""
from __future__ import annotations


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    """什么都不画。"""
    return None
