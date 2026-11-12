"""B站版的文案。

元数据里已经写好了这一期在B站上怎么自我介绍（`aiv/publish/<EP>.json`），
这里只做两件事：把它取出来、把它摆成发布包里的那几个文件。

**标签是英文逗号分隔的一串**（不是 `#` 井号）——平台收到的就是这个形状，
拼接时不要加井号。

**这里不判平台规则。** 「转载必须给 source」这条规矩由契约层
（`pyv.epmeta` 的 `required_when`）负责：adapter 自己再判一遍，
两个地方就可能给出两个结论（规格 §6.1.3）。
"""
from __future__ import annotations

from dataclasses import dataclass

from pyv import epmeta


@dataclass(frozen=True)
class BiliCopy:
    """一期在B站上的文案。"""

    title: str
    description: str
    tags: tuple[str, ...]
    tid: int
    copyright: int
    no_reprint: int
    source: str = ""
    cover_at: float = 0.0
    url: str = ""


def slice_copy(meta: epmeta.EpisodeMeta) -> BiliCopy:
    """取出B站版的文案。没配这一段就是配置错误。"""
    section = meta.platform("bilibili")
    if section is None:
        raise epmeta.MetaError(
            f"这一期没有配置B站文案：{meta.episode}")
    return BiliCopy(
        title=str(section.get("title", "")),
        description=str(section.get("description", "")),
        tags=tuple(str(t) for t in (section.get("tags") or [])),
        tid=int(section.get("tid", 0)),
        copyright=int(section.get("copyright", 1)),
        no_reprint=int(section.get("no_reprint", 0)),
        source=str(section.get("source", "") or ""),
        cover_at=meta.cover_at,
        url=meta.url,
    )


def tags_line(tags: tuple[str, ...]) -> str:
    """标签拼成平台要的那一串：数据库,源码"""
    return ",".join(tags)
