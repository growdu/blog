"""发布计划：把「发布包」读成一份结构化的「要往页面上填什么」。

**为什么不在这里读元数据 JSON。** 元数据（`aiv/publish/<EP>.json`）是
**文案的事实**，发布包（`channels/out/<EP>/`）是**已经按平台限额裁好的产物**。
浏览器该填的是后者——标题多少字、简介带不带话题、封面选哪张，
出包的时候都定过了。这里只负责把定好的东西读出来，不再做判断。

**这一层不认识任何平台。** 平台特有的规则（标题上限、话题怎么拼、
封面选横版还是竖版）都在 `flows/<平台>.py` 里。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


class PlanError(RuntimeError):
    """发布包读不出来，或包里的东西缺了。"""


@dataclass
class PublishPlan:
    """一期内容在某个平台上的发布计划。"""

    episode: str
    package_dir: Path
    title: str
    description: str
    topics: list[str] = field(default_factory=list)
    video: Path | None = None
    cover: Path | None = None
    cover_alt: Path | None = None
    status: str = "packaged"
    published_url: str | None = None

    def description_with_topics(self, *, separator: str = "\n") -> str:
        """简介 + 话题拼成一段。

        视频号的简介是**一个输入框**，话题不是独立字段——只能拼进正文里。
        所以「怎么拼」是平台知识，调用方（flows/channels.py）决定分隔符，
        这里只提供最朴素的一种拼法。
        """
        if not self.topics:
            return self.description
        tags = " ".join(f"#{t}" for t in self.topics)
        if not self.description:
            return tags
        return f"{self.description}{separator}{tags}"

    def has_all_files(self) -> bool:
        """该有的文件是不是都在。"""
        return bool(
            self.video and self.video.is_file()
            and self.cover and self.cover.is_file()
        )


def _read_text(path: Path, *, required: bool = True, default: str = "") -> str:
    if not path.is_file():
        if required:
            raise PlanError(f"发布包缺文件：{path}")
        return default
    return path.read_text(encoding="utf-8").strip()


def parse_topics(raw: str) -> list[str]:
    """把 `#A #B #C` 解析成 `["A", "B", "C"]`。

    容忍三种写法：空格分隔、换行分隔、逗号分隔；每个话题前面的 `#` 可有可无。
    """
    tokens: list[str] = []
    for chunk in raw.replace(",", " ").replace("，", " ").split():
        token = chunk.strip().lstrip("#").strip()
        if token:
            tokens.append(token)
    return tokens


def load_plan(package_dir: Path) -> PublishPlan:
    """从一个发布包目录读出发布计划。"""
    root = Path(package_dir)
    if not root.is_dir():
        raise PlanError(f"发布包目录不存在：{root}")

    meta: dict = {}
    meta_path = root / "meta.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise PlanError(f"meta.json 读不出来：{error}") from error

    title = _read_text(root / "title.txt")
    description = _read_text(root / "description.txt", required=False)
    topics = parse_topics(_read_text(root / "topics.txt", required=False))

    video = root / "video.mp4"
    cover = root / "cover-16x9.jpg"
    cover_alt = root / "cover-9x16.jpg"

    if not title:
        raise PlanError(f"发布包里没有标题：{root / 'title.txt'}")

    return PublishPlan(
        episode=str(meta.get("episode") or root.name),
        package_dir=root,
        title=title,
        description=description,
        topics=topics,
        video=video if video.exists() else None,
        cover=cover if cover.exists() else None,
        cover_alt=cover_alt if cover_alt.exists() else None,
        status=str(meta.get("status") or "packaged"),
        published_url=meta.get("published_url"),
    )
