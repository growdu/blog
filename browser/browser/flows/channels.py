"""视频号（微信）发布流程。

**页面结构不是猜的。** 视频号助手的投稿页在本仓库的作者没见过，
所以选择器表放在 `browser/selectors/channels.json`——**数据，不是代码**——
先跑 `python -m browser.cli probe` 把页面结构探出来，照着填 JSON，
再回来跑流程。页面改版时改 JSON，不用改 Python。

**流程分两段，是故意的。**

    prepare   上传视频 → 等处理完 → 填文案 → 选封面 → 勾原创 → 截图停在发布前
    submit    点「发表」→ 等结果 → 取回链接

分开是因为「发表」是不可逆的外部可见动作：填错了、发出去就收不回来。
`prepare` 跑完会留下截图与一份「填了什么」的清单，人能自己看一眼再决定发不发。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from browser.driver import ActionError, PageDriver
from browser.plan import PublishPlan

DEFAULT_SELECTORS_PATH = Path(__file__).resolve().parents[1] / "selectors" / "channels.json"

# 视频号的字数限制（公开口径，仓库既有的《从 Hexo 博客到公众号与视频号》取 22 字保守值）。
# **未实测**：见 publish/spec/07-视频发布契约.md §十四 第 1 条。
LIMITS = {
    "title_chars": 22,
    "description_chars": 1000,
    "topics_max": 5,
    "topic_chars": 15,
}


class FlowError(RuntimeError):
    """视频号流程跑不下去。消息里要说清下一步。"""


@dataclass
class ChannelsConfig:
    """选择器表 + 行为开关。"""

    entry_url: str = "https://channels.weixin.qq.com/platform"
    text_layout: str = "combined"       # "separate"（有独立标题框）/ "combined"（只有一个描述框）
    selectors: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> "ChannelsConfig":
        target = Path(path) if path else DEFAULT_SELECTORS_PATH
        if not target.is_file():
            raise FlowError(
                f"选择器表不存在：{target}\n"
                "先跑 `python -m browser.cli probe` 探一次页面结构，再照着填这张表。"
            )
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise FlowError(f"选择器表读不出来：{error}") from error
        return cls(
            entry_url=str(raw.get("entry_url") or cls.entry_url),
            text_layout=str(raw.get("text_layout") or "combined"),
            selectors=raw.get("selectors") or {},
        )

    def need(self, group: str, key: str) -> list[str]:
        """取一组候选选择器；一个都没有就报错并说清怎么补。"""
        values = (self.selectors.get(group) or {}).get(key) or []
        if isinstance(values, str):
            values = [values]
        if not values:
            raise FlowError(
                f"选择器表里没有 {group}.{key}。\n"
                "跑 `python -m browser.cli probe` 看页面结构，把候选选择器填进 "
                "browser/selectors/channels.json。"
            )
        return list(values)


class ChannelsFlow:
    """视频号助手的投稿流程。"""

    def __init__(self, driver: PageDriver, config: ChannelsConfig | None = None) -> None:
        self.driver = driver
        self.config = config or ChannelsConfig.load()

    # -- 登录 ---------------------------------------------------------------

    def open_entry(self) -> None:
        """打开视频号助手首页。"""
        self.driver.page.goto(self.config.entry_url, wait_until="domcontentloaded")

    def is_logged_in(self) -> bool:
        """当前页面是不是已登录状态。

        **判据要选「登录后一定在」的东西**，不能用「登录后可能不在」的东西。
        视频号助手登录后顶部有「发表视频」这类入口；未登录时是二维码。
        """
        logged_in = self.config.selectors.get("login", {}).get("logged_in_marker") or []
        if not logged_in:
            return False
        return self.driver.exists(logged_in)

    def wait_for_login(self, *, timeout_ms: int = 300000) -> bool:
        """等人扫码登录。

        **这一步必须由人完成。** 微信扫码是拿手机对着屏幕，
        自动化代替不了。超时返回 False，不抛异常——「没扫」不是错误。
        """
        import time

        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            if self.is_logged_in():
                return True
            time.sleep(2)
        return False

    # -- 投稿 ---------------------------------------------------------------

    def upload_video(self, path: Path) -> None:
        """上传成片。"""
        selectors = self.config.need("post", "video_file_input")
        self.driver.upload(selectors, path)

    def fill_text(self, title: str, description: str, topics: list[str]) -> None:
        """填文案。

        视频号有两种可能的表单：

        - `separate`：有独立的标题框与描述框，分别填；
        - `combined`：只有一个描述框，标题就是描述的第一行。

        哪一种由选择器表的 `text_layout` 决定——**靠探测得出，不靠猜**。
        """
        tags = " ".join(f"#{t}" for t in topics)
        if self.config.text_layout == "separate":
            self.driver.fill(self.config.need("post", "title_input"), title)
            body = f"{description}\n{tags}" if description else tags
            self.driver.fill(self.config.need("post", "description_input"), body)
        else:
            body = f"{title}\n\n{description}\n{tags}" if description else f"{title}\n{tags}"
            self.driver.fill(self.config.need("post", "description_input"), body)

    def set_cover(self, path: Path) -> None:
        """设封面。"""
        self.driver.upload(self.config.need("post", "cover_input"), path)

    def declare_original(self) -> None:
        """勾「原创声明」。已经勾上就当成功。"""
        selector = self.config.need("post", "original_checkbox")
        try:
            self.driver.click(selector)
        except ActionError:
            # 可能本来就已经勾着了
            if not self.driver.exists(selector):
                raise

    def prepare(self, plan: PublishPlan, *, cover: Path | None = None) -> dict:
        """把发布包里��东西都填进页面，**停在发表之前**。

        返回一份「填了什么」的清单，供人核对。
        """
        if not plan.video or not plan.video.is_file():
            raise FlowError(f"发布包里没有成片：{plan.package_dir}")
        cover_path = cover or plan.cover
        if not cover_path or not Path(cover_path).is_file():
            raise FlowError(f"发布包里没有封面：{plan.package_dir}")

        self.open_entry()
        self.upload_video(plan.video)
        self.fill_text(plan.title, plan.description, plan.topics)
        self.set_cover(Path(cover_path))
        self.declare_original()

        filled = {
            "title": plan.title,
            "description": plan.description,
            "topics": plan.topics,
            "video": str(plan.video),
            "cover": str(cover_path),
        }
        return filled

    def submit(self) -> str | None:
        """点「发表」，等结果。

        返回发布后的链接；**取不到就返回 None**，由调用方决定怎么办——
        不猜、不编。
        """
        self.driver.click(self.config.need("post", "submit_button"))

        marker = self.config.selectors.get("post", {}).get("published_marker") or []
        if marker:
            self.driver.wait_for(marker, timeout_ms=60000)

        return self._read_published_url()

    def _read_published_url(self) -> str | None:
        """从页面上把发布链接读出来。

        视频号后台给链接的方式不止一种（文本框 / 「复制链接」旁的地址 /
        详情页 URL）。挨个试，都不行就返回 None——让人自己复制。
        """
        for group, key in (("post", "published_url_text"), ("post", "published_url_input")):
            candidates = (self.config.selectors.get(group) or {}).get(key) or []
            if not candidates:
                continue
            for candidate in candidates:
                try:
                    if key.endswith("_input"):
                        value = self.driver.value_of(candidate)
                    else:
                        value = self.driver.text_of(candidate)
                except ActionError:
                    continue
                value = (value or "").strip()
                if value.startswith("http"):
                    return value
        return None


def check_limits(plan: PublishPlan, limits: dict | None = None) -> list[str]:
    """发布前再核一遍字数。

    出包时 `channels` adapter 已经核过一遍；这里再核一次是因为
    **浏览器的输入框可能有它自己的规则**（比如自动截断）。
    在填进去之前拦住，比发出去之后发现被截断强。

    返回问题清单，空清单表示没问题。
    """
    limits = limits or LIMITS
    problems: list[str] = []
    if len(plan.title) > limits["title_chars"]:
        problems.append(
            f"标题 {len(plan.title)} 字，超过上限 {limits['title_chars']} 字")
    body = plan.description_with_topics(separator="\n")
    if len(body) > limits["description_chars"]:
        problems.append(
            f"简介 {len(body)} 字，超过上限 {limits['description_chars']} 字")
    if len(plan.topics) > limits["topics_max"]:
        problems.append(
            f"话题 {len(plan.topics)} 个，超过上限 {limits['topics_max']} 个")
    for topic in plan.topics:
        if len(topic) > limits["topic_chars"]:
            problems.append(
                f"话题「{topic}」{len(topic)} 字，超过上限 {limits['topic_chars']} 字")
    return problems
