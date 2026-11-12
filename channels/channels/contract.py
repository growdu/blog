"""视频号版的文案。

元数据里已经写好了这一期在视频号上怎么自我介绍（`aiv/publish/<EP>.json`），
这里只做两件事：把它取出来、把它摆成发布包里的那几个文件。

不静默截断：超限由 `pyv.epmeta` 报错让作者改元数据，不在这里悄悄裁一刀。
"""
from __future__ import annotations

from dataclasses import dataclass

from pyv import epmeta


@dataclass(frozen=True)
class ChannelsCopy:
    """一期在视频号上的文案。"""

    title: str
    description: str
    topics: tuple[str, ...]
    cover_at: float
    url: str = ""


def slice_copy(meta: epmeta.EpisodeMeta) -> ChannelsCopy:
    """取出视频号版的文案。没配这一段就是配置错误。"""
    section = meta.platform("channels")
    if section is None:
        raise epmeta.MetaError(
            f"这一期没有配置视频号文案：{meta.episode}")
    return ChannelsCopy(
        title=str(section.get("title", "")),
        description=str(section.get("description", "")),
        topics=tuple(str(t) for t in (section.get("topics") or [])),
        cover_at=meta.cover_at,
        url=meta.url,
    )


def topics_line(topics: tuple[str, ...]) -> str:
    """话题拼成一行：#数据库 #内核"""
    return " ".join(f"#{topic}" for topic in topics)
