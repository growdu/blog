"""发布计划：把「发布包」读成一份结构化的「要往页面上填什么」。

**为什么不在这里读元数据 JSON。** 元数据（`aiv/publish/<EP>.json`）是
**文案的事实**，发布包（`channels/out/<EP>/`、`bilibili/out/<EP>/`）是
**已经按平台限额裁好的产物**。
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


@dataclass
class BilibiliPlan:
    """一期内容在 B站 上的发布计划。

    **B站 的包结构与视频号不一样**（实测 2026-11-13）：

    | 项 | 视频号 | B站 |
    | --- | --- | --- |
    | 话题 | `topics.txt`，空格分隔 `#A #B` | `tags.txt`，**英文逗号分隔**（不带 `#`） |
    | 封面 | `cover-4x3.jpg` + `cover-3x4.jpg` | `cover.jpg`（1146×717） |
    | 字幕 | 无 | `subtitle.srt`（要传到「视频元素 → 字幕设置」） |

    所以 B站 不能直接复用 `PublishPlan`——字段名与语义都不一样。
    """

    episode: str
    package_dir: Path
    title: str
    description: str
    tags: list[str] = field(default_factory=list)
    video: Path | None = None
    cover: Path | None = None
    subtitle: Path | None = None
    status: str = "packaged"
    published_url: str | None = None

    def tags_as_csv(self) -> str:
        """标签拼成 B站 要的那一串：英文逗号分隔、**不带 # 号**。"""
        return ",".join(self.tags)

    def has_all_files(self) -> bool:
        """该有的文件是不是都在（成片与封面是硬要求，字幕是加分项）。"""
        return bool(
            self.video and self.video.is_file()
            and self.cover and self.cover.is_file()
        )


def load_bilibili_plan(package_dir: Path) -> BilibiliPlan:
    """从 B站 发布包目录读出发布计划。"""
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
    # B站 的标签是逗号分隔的一串；parse_topics 也能吃逗号，顺手复用。
    tags = parse_topics(_read_text(root / "tags.txt", required=False))

    video = root / "video.mp4"
    cover = root / "cover.jpg"
    subtitle = root / "subtitle.srt"

    if not title:
        raise PlanError(f"发布包里没有标题：{root / 'title.txt'}")

    return BilibiliPlan(
        episode=str(meta.get("episode") or root.name),
        package_dir=root,
        title=title,
        description=description,
        tags=tags,
        video=video if video.exists() else None,
        cover=cover if cover.exists() else None,
        subtitle=subtitle if subtitle.exists() else None,
        status=str(meta.get("status") or "packaged"),
        published_url=meta.get("published_url"),
    )


@dataclass
class ToutiaoImage:
    """正文里的一张图。

    ``number`` 是**切片器给的图号**（正文里占位符写的是【图N】），
    不是文件在包里的序号——外链图没有文件，但它的号照样占着。

    ``path`` 为 None 有两种原因：图本来就是外链（出包不下载外链图），
    或者本地图转不出来（Pillow 读不了 / 压不进上限）。
    两种都要人工补，草稿里那个占位符就该留着。
    """

    number: int
    path: Path | None = None
    source: str | None = None


@dataclass
class ToutiaoPlan:
    """一篇文章在头条号上的发布计划。

    **头条号的包结构与视频号、B站都不一样**（实测 2026-11-17）：

    | 项 | 视频号 | B站 | 头条号 |
    | --- | --- | --- | --- |
    | 正文 | `description.txt` | `description.txt` | **`article.html`**（带排版的 HTML） |
    | 图片 | 视频本身 | 封面 | **`images/NN.webp`**（正文图，按图号命名） |
    | 封面 | `cover-4x3.jpg` + `cover-3x4.jpg` | `cover.jpg` | **`cover.webp`**（单图，452:352） |
    | 机器可读信息 | `meta.json` | `meta.json` | **`meta.json`** |

    字数口径（平台的：非 ASCII 逐字 + ASCII 每两个折一个）由出包时算好放在
    ``meta.json`` 里——**执行器不重算**，那套口径只有 adapter 里有。
    """

    content_id: str
    package_dir: Path
    title: str
    digest: str = ""
    body_html: str = ""
    body_chars: int = 0
    platform_chars: int = 0
    images: tuple[ToutiaoImage, ...] = ()
    cover: Path | None = None

    def image_paths(self) -> dict[int, Path]:
        """图号 → 本地文件。只给真的有文件的那几张。"""
        return {
            image.number: image.path
            for image in self.images
            if image.path is not None and image.path.is_file()
        }

    def missing_images(self) -> list[int]:
        """哪些图号没有本地文件（外链图 / 转不出来的图）。"""
        return [
            image.number
            for image in self.images
            if image.path is None or not image.path.is_file()
        ]


def load_toutiao_plan(package_dir: Path) -> ToutiaoPlan:
    """从头条号发布包目录读出发布计划。"""
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

    # title.txt 是两行：第一行标题，第二行摘要（出包时写的）。
    title_file = root / "title.txt"
    if not title_file.is_file():
        raise PlanError(f"发布包里没有标题：{title_file}")
    title_lines = title_file.read_text(encoding="utf-8").splitlines()
    title = title_lines[0].strip() if title_lines else ""
    digest = title_lines[1].strip() if len(title_lines) > 1 else ""
    if not title:
        raise PlanError(f"发布包里没有标题：{title_file}")

    body_html = _read_text(root / "article.html", required=False)
    images: list[ToutiaoImage] = []
    for entry in meta.get("images") or []:
        number = int(entry.get("number") or 0)
        if number < 1:
            continue
        relative = entry.get("file")
        path = (root / relative) if relative else None
        images.append(
            ToutiaoImage(
                number=number,
                path=path if path is not None and path.is_file() else None,
                source=entry.get("source"),
            )
        )

    cover_relative = meta.get("cover")
    cover = (root / cover_relative) if cover_relative else None
    if cover is not None and not cover.is_file():
        cover = None

    return ToutiaoPlan(
        content_id=str(meta.get("content_id") or root.name),
        package_dir=root,
        title=title,
        digest=digest or str(meta.get("digest") or ""),
        body_html=body_html,
        body_chars=int(meta.get("body_chars") or 0),
        platform_chars=int(meta.get("platform_chars") or 0),
        images=tuple(sorted(images, key=lambda image: image.number)),
        cover=cover,
    )


def find_toutiao_plan(packages_dir: Path, content_id: str) -> ToutiaoPlan:
    """在发布包目录里按 content id 找一篇。

    **为什么扫目录而不是按名字拼路径**：content id 里带斜杠（``source-tracks/ai-tools/L2-toolbox/claude安装教程``），
    包目录名是它把斜杠换成横杠的结果——那条规则是 adapter 的知识，
    执行器不 import adapter，所以这里读每个包的 ``meta.json`` 来认。
    """
    root = Path(packages_dir)
    if not root.is_dir():
        raise PlanError(f"发布包目录不存在：{root}")
    for candidate in sorted(root.iterdir()):
        if not candidate.is_dir():
            continue
        meta_path = candidate / "meta.json"
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if meta.get("content_id") == content_id:
            return load_toutiao_plan(candidate)
    raise PlanError(
        f"发布包里没有这一篇：{content_id}\n"
        f"先出包：python3 -m toutiao.cli convert --all --packages-only（目录 {root}）"
    )


@dataclass
class DouyinPlan:
    """一期内容在抖音上的发布计划。

    **抖音的包结构（实测 2026-11-17）**：

    | 项 | 视频号 | B站 | 抖音 |
    | --- | --- | --- | --- |
    | 标题 | `title.txt` | `title.txt` | `title.txt`（**只有标题**，没有摘要行） |
    | 描述 | `description.txt` | `description.txt` | `description.txt` |
    | 话题 | `topics.txt`，空格分隔 `#A #B` | `tags.txt`，逗号分隔、不带 `#` | `topics.txt`，空格分隔 `#A #B` |
    | 封面 | `cover-4x3.jpg` + `cover-3x4.jpg` | `cover.jpg` | **`cover_3x4.jpg`（竖）+ `cover_4x3.jpg`（横）** |
    | 成片 | `video.mp4` | `video.mp4` | `video.mp4`（**竖版 9:16 无品牌版**） |

    抖音这一档要用**竖版无导流版**成片：带品牌字标与 ``growdu.cn`` 胶囊的那版
    会撞在抖音「过度营销 + 站外引流」两条规则上（见 ``douyin/douyin/cli.py``）。
    """

    episode: str
    package_dir: Path
    title: str
    description: str
    topics: list[str] = field(default_factory=list)
    video: Path | None = None
    cover_vertical: Path | None = None
    cover_horizontal: Path | None = None
    status: str = "packaged"
    published_url: str | None = None

    def description_with_topics(self, *, separator: str = "\n") -> str:
        """描述框里那一整段：正文 + 换行 + 话题。

        抖音的网页后台是**两个框**（作品标题 / 作品描述），话题不是独立字段，
        只能以 ``#话题`` 的形式写进描述框。
        """
        if not self.topics:
            return self.description
        tags = " ".join(f"#{topic}" for topic in self.topics)
        if not self.description:
            return tags
        return f"{self.description}{separator}{tags}"

    def has_all_files(self) -> bool:
        """该有的文件是不是都在（成片是硬要求，封面是加分项）。"""
        return bool(self.video and self.video.is_file())


def load_douyin_plan(package_dir: Path) -> DouyinPlan:
    """从抖音发布包目录读出发布计划。"""
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
    # 抖音有两个封面槽位（实测 2026-11-15）：竖封面 3:4、横封面 4:3。
    cover_vertical = root / "cover_3x4.jpg"
    cover_horizontal = root / "cover_4x3.jpg"

    if not title:
        raise PlanError(f"发布包里没有标题：{root / 'title.txt'}")

    return DouyinPlan(
        episode=str(meta.get("episode") or root.name),
        package_dir=root,
        title=title,
        description=description,
        topics=topics,
        video=video if video.exists() else None,
        cover_vertical=cover_vertical if cover_vertical.exists() else None,
        cover_horizontal=cover_horizontal if cover_horizontal.exists() else None,
        status=str(meta.get("status") or "packaged"),
        published_url=meta.get("published_url"),
    )


def find_douyin_plan(packages_dir: Path, episode: str) -> DouyinPlan:
    """在发布包目录里按期号找一期。

    目录名就是期号（``csn-total-ordering``），但这里仍然逐个读 ``meta.json``
    来认——**目录名不是契约**，元数据才是。
    """
    root = Path(packages_dir)
    if not root.is_dir():
        raise PlanError(f"发布包目录不存在：{root}")
    for candidate in sorted(root.iterdir()):
        if not candidate.is_dir():
            continue
        meta_path = candidate / "meta.json"
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if meta.get("episode") == episode or candidate.name == episode:
            return load_douyin_plan(candidate)
    raise PlanError(
        f"发布包里没有这一期：{episode}\n"
        f"先出包：python3 -m douyin.cli package {episode}（目录 {root}）"
    )


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
    # 视频号的两个封面槽位（实测 2026-11-13）：分享卡片 4:3、个人主页卡片 3:4
    cover = root / "cover-4x3.jpg"
    cover_alt = root / "cover-3x4.jpg"

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
