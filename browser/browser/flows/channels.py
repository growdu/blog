"""视频号（微信）发布流程。

**页面结构不是猜的。** 2026-11-13 用真实账号（growdu）探过视频号助手的投稿页，
选择器表放在 `browser/selectors/channels.json`——**数据，不是代码**——
页面改版时改 JSON，不用改 Python。

**流程分两段，是故意的。**

    prepare   上传视频 → 等处理完 → 填文案 → 勾原创 → 截图停在发布前
    submit    点「发表」→ 等结果 → 取回链接

分开是因为「发表」是不可逆的外部可见动作：填错了、发出去就收不回来。
`prepare` 跑完会留下截图与一份「填了什么」的清单，人能自己看一眼再决定发不发。

**实测拿到的四条平台规则**（都写进了代码，不是写在注释里）：

1. **短标题有独立输入框**（`填写短标题有机会获得更多流量`），
   与描述框分开——所以 `text_layout = "separate"`。
2. **描述框是 contenteditable**，在里面打 `#话题` 会被编辑器**自动变成真话题**
   （`<span class="hl topic">`），不需要点「#话题」按钮去搜索。
3. **短标题不收中文逗号**。原话：「标题包含特殊字符，符号仅支持书名号、引号、
   冒号、加号、问号、百分号、摄氏度，逗号可用空格代替」。
4. **「发表」在视频处理完之前是灰的**。上传完成后平台还要处理视频
   （转码、取封面），这期间按钮点不动——而且它**没有 `disabled` 属性**，
   只是样式变灰。于是 Playwright 的 click() 正常返回，平台却什么也不做：
   **事件派发出去了，稿件没发出去**（2026-11-13 实测，EP06 第一次投稿丢在这里）。

**还有一条实测出来的麻烦**：勾「声明原创」会弹一个「原创权益」弹窗，
要在弹窗里再勾一次同意、再点一次「声明原创」，主勾选框才算真的勾上。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from browser.driver import ActionError, PageDriver
from browser.plan import PublishPlan

# 选择器表的默认位置：browser/selectors/channels.json。
# 注意是 parents[2]——本文件在 browser/browser/flows/ 下，
# parents[0]=flows、parents[1]=browser 包、parents[2]=browser/ 顶层目录。
DEFAULT_SELECTORS_PATH = Path(__file__).resolve().parents[2] / "selectors" / "channels.json"

# 视频号的字数限制（公开口径，仓库既有的《从 Hexo 博客到公众号与视频号》取 22 字保守值）。
# **字数上限本身仍未实测**；见 publish/spec/07-视频发布契约.md §十四 第 1 条。
LIMITS = {
    "title_chars": 22,
    "description_chars": 1000,
    "topics_max": 5,
    "topic_chars": 15,
}

# 短标题里视频号**明确拒收**的符号 → 该换成什么。
# 实测 2026-11-13：填「两个事务改同一行，谁先谁后」，页面直接报
# 「标题包含特殊字符，符号仅支持书名号、引号、冒号、加号、问号、百分号、
#   摄氏度，逗号可用空格代替」；把「，」换成空格后同一条文案通过。
# 只收**实测过**的符号——没试过的字符不列进来，免得把合法文案误判成非法。
TITLE_REJECTED = {"，": "空格"}


class FlowError(RuntimeError):
    """视频号流程跑不下去。消息里要说清下一步。"""


@dataclass
class ChannelsConfig:
    """选择器表 + 行为开关。"""

    entry_url: str = "https://channels.weixin.qq.com/platform/post/create"
    text_layout: str = "separate"      # "separate"（有独立标题框）/ "combined"（只有一个描述框）
    selectors: dict = field(default_factory=dict)
    # 等「发表」按钮变可点，最多等多久（毫秒）。真实站上视频处理要几分钟，给得宽。
    publish_ready_ms: int = 900_000
    # 点完「发表」，最多等多久看页面有没有反应（毫秒）。这一步要么很快有反应，要么就是没反应。
    publish_effect_ms: int = 60_000

    @classmethod
    def load(cls, path: Path | None = None) -> "ChannelsConfig":
        target = Path(path) if path else DEFAULT_SELECTORS_PATH
        if not target.is_file():
            raise FlowError(
                f"选择器表不存在：{target}\n"
                "先跑 `python3 -m browser.cli probe` 探一次页面结构，再照着填这张表。"
            )
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise FlowError(f"选择器表读不出来：{error}") from error
        timeouts = raw.get("timeouts") or {}
        return cls(
            entry_url=str(raw.get("entry_url") or cls.entry_url),
            text_layout=str(raw.get("text_layout") or "separate"),
            selectors=raw.get("selectors") or {},
            publish_ready_ms=int(timeouts.get("publish_ready_ms",
                                              cls.publish_ready_ms)),
            publish_effect_ms=int(timeouts.get("publish_effect_ms",
                                               cls.publish_effect_ms)),
        )

    def need(self, group: str, key: str) -> list[str]:
        """取一组候选选择器；一个都没有就报错并说清怎么补。"""
        values = (self.selectors.get(group) or {}).get(key) or []
        if isinstance(values, str):
            values = [values]
        if not values:
            raise FlowError(
                f"选择器表里没有 {group}.{key}。\n"
                "跑 `python3 -m browser.cli probe` 看页面结构，把候选选择器填进 "
                "browser/selectors/channels.json。"
            )
        return list(values)

    def maybe(self, group: str, key: str) -> list[str]:
        """取候选选择器；没有就返回空列表（这一步是可选的）。"""
        values = (self.selectors.get(group) or {}).get(key) or []
        if isinstance(values, str):
            values = [values]
        return list(values)


class ChannelsFlow:
    """视频号助手的投稿流程。"""

    def __init__(self, driver: PageDriver, config: ChannelsConfig | None = None) -> None:
        self.driver = driver
        self.config = config or ChannelsConfig.load()

    # -- 登录 ---------------------------------------------------------------

    def open_entry(self) -> None:
        """打开视频号投稿页。"""
        self.driver.page.goto(self.config.entry_url, wait_until="domcontentloaded")

    def is_logged_in(self) -> bool:
        """当前页面是不是已登录状态。

        **判据要选「登录后一定在」的东西**，不能用「登录后可能不在」的东西。
        登录后左侧导航会带上 `finder-ui-desktop-menu__link_current`。
        """
        markers = self.config.maybe("login", "logged_in_marker")
        if not markers:
            return False
        return self.driver.exists(markers)

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
        """上传成片，并等平台处理完。

        **两处都要等。**
        一是页面刚打开时上传框还没渲染出来（视频号的投稿页是 Vue 现搭的）；
        二是平台处理中会挂一个「取消上传」的按钮，它消失才算传完——
        不等就往下填表，描述框与短标题框可能还锁着，填不进去。
        """
        selector = self.config.need("post", "video_file_input")
        # 上传框是 display:none 的，所以等「attached」而不是「visible」
        self.driver.wait_for(selector, state="attached", timeout_ms=60000)
        self.driver.upload(selector, path)
        self.driver.wait_for_text_gone("取消上传", timeout_ms=300000)

    def wait_publish_ready(self, *, timeout_ms: int | None = None) -> None:
        """等「发表」按钮真的点得动。

        **上传完了 ≠ 平台处理完了。** 实测 2026-11-13：上传完成后平台还要
        处理视频（转码、取封面），这期间「发表」是灰的。灰按钮没有
        `disabled` 属性，Playwright 的 click() 会正常返回，平台却什么也不做——
        **稿件根本没发出去**，日志里也看不出任何异常。

        所以这里轮询到按钮真的可点为止；等不到就报错，
        绝不带着一个点不动的按钮往下走。
        """
        import time

        selector = self.config.need("post", "submit_button")
        limit = timeout_ms if timeout_ms is not None else self.config.publish_ready_ms
        deadline = time.monotonic() + limit / 1000
        while True:
            try:
                if self.driver.is_enabled(selector):
                    return
            except ActionError:
                pass  # 按钮还没渲染出来，继续等
            if time.monotonic() >= deadline:
                raise FlowError(
                    f"等了 {limit // 1000} 秒，「发表」按钮还是点不动——"
                    "视频可能还在平台处理中，或者处理失败了。\n"
                    "这种按钮点了也不会发出去，所以这里不点。"
                    "先去内容管理页看这条视频的状态，再决定要不要重发。"
                )
            time.sleep(2)

    def fill_text(self, title: str, description: str, topics: list[str]) -> None:
        """填文案。

        视频号有两种可能的表单：

        - `separate`：有独立的短标题框与描述框，分别填（实测是这个）；
        - `combined`：只有一个描述框，标题就是描述的第一行。

        **话题直接写进描述框就行**——编辑器会把 `#XXX` 自动变成真话题
        （`<span class="hl topic">`），实测 2026-11-13。
        """
        tags = " ".join(f"#{t}" for t in topics)
        if self.config.text_layout == "separate":
            title_selector = self.config.need("post", "title_input")
            desc_selector = self.config.need("post", "description_input")
            # 表单是在视频处理完之后才可填的，等它们出现再动
            self.driver.wait_for(title_selector, timeout_ms=60000)
            self.driver.wait_for(desc_selector, timeout_ms=60000)
            self.driver.fill(title_selector, title)
            body = f"{description}\n{tags}" if description else tags
            self.driver.fill(desc_selector, body)
        else:
            desc_selector = self.config.need("post", "description_input")
            self.driver.wait_for(desc_selector, timeout_ms=60000)
            body = f"{title}\n\n{description}\n{tags}" if description else f"{title}\n{tags}"
            self.driver.fill(desc_selector, body)

    def set_cover(self, path: Path) -> None:
        """设封面。

        **实测：视频号的封面槽位是 3:4（个人主页卡片）与 4:3（分享卡片）**，
        不是 16:9 也不是 9:16——传 16:9 的图会被居中裁掉左右两边。
        这个方法只负责把图**传进**编辑器的图片框，裁剪由平台自己做。
        """
        self.driver.upload(self.config.need("post", "cover_input"), path)

    def declare_original(self) -> bool:
        """勾「声明原创」。

        实测：勾主勾选框会弹「原创权益」弹窗，要在弹窗里**再勾一次同意**、
        **再点一次「声明原创」**，才算真的声明了。返回是否最终勾上。
        """
        selector = self.config.need("post", "original_checkbox")
        self.driver.click(selector)

        agree = self.config.maybe("original_dialog", "agree_checkbox")
        confirm = self.config.maybe("original_dialog", "confirm_button")
        if agree and confirm:
            try:
                self.driver.click(agree)
                self.driver.click(confirm)
            except ActionError:
                pass  # 没有弹窗（可能已经勾上了），下面统一核对

        checked = self.driver.is_checked(selector)
        if not checked:
            raise FlowError(
                "「声明原创」没勾上。视频号会弹「原创权益」弹窗，"
                "要在弹窗里勾同意、再点「声明原创」——这一步没走通。"
            )
        # 弹窗是带淡出动画的，等它真的消失，免得截图拍在动画中间
        if agree and confirm:
            try:
                self.driver.wait_for(confirm, state="hidden", timeout_ms=15000)
            except ActionError:
                pass
        return True

    def verify_filled(self, title: str, description: str, topics: list[str]) -> dict:
        """把页面上**实际的**内容读回来核对。

        **填进去 ≠ 页面收下了。** 输入框可能被限长截断、被平台改写，
        话题也可能只是普通文字而不是真话题。发表之前读回来核一遍，
        比发出去之后才发现被截断强。

        返回核对结果；不一致就抛 FlowError。
        """
        actual_title = self.driver.value_of(self.config.need("post", "title_input"))
        if actual_title != title:
            raise FlowError(
                f"短标题没填对：想填「{title}」，页面上是「{actual_title}」")

        actual_desc = self.driver.text_of(self.config.need("post", "description_input"))
        if description and description not in actual_desc:
            raise FlowError(
                "简介没完整填进去（可能被截断或被平台改写）："
                f"想填 {len(description)} 字，页面上是 {len(actual_desc)} 字")

        # 话题必须是真话题：编辑器会把 #XXX 变成 <span class="hl topic">
        topic_selector = self.config.maybe("post", "topic_chip")
        topic_count = self.driver.count(topic_selector) if topic_selector else 0
        if topics and topic_selector and topic_count < len(topics):
            raise FlowError(
                f"话题只成了 {topic_count} 个（要 {len(topics)} 个）——"
                "编辑器没把它们变成真话题")

        return {
            "title_in_page": actual_title,
            "description_chars_in_page": len(actual_desc),
            "topic_chips_in_page": topic_count,
        }

    def prepare(self, plan: PublishPlan, *, cover: Path | None = None) -> dict:
        """把发布包里的东西都填进页面，**停在发表之前**。

        返回一份「填了什么」的清单，供人核对。
        """
        if not plan.video or not plan.video.is_file():
            raise FlowError(f"发布包里没有成片：{plan.package_dir}")

        self.open_entry()
        self.upload_video(plan.video)
        # 上传完了平台还要处理视频。处理完之前「发表」是灰的——
        # 点了也不会发出去，所以这里先等它真的可点。
        self.wait_publish_ready()
        self.fill_text(plan.title, plan.description, plan.topics)

        filled = {
            "title": plan.title,
            "description": plan.description,
            "topics": plan.topics,
            "video": str(plan.video),
        }

        if cover is not None:
            self.set_cover(Path(cover))
            filled["cover"] = str(cover)
        else:
            filled["cover"] = "（用平台自动生成的封面）"

        self.declare_original()
        filled["original_declared"] = True

        verified = self.verify_filled(plan.title, plan.description, plan.topics)
        filled.update(verified)
        return filled

    def submit(self) -> str | None:
        """点「发表」，等结果。

        返回发布后的链接。三种结局：

        - 拿到链接 → 返回链接；
        - 确实有反应、但没拿到链接 → 返回 None，交给人手动回填；
        - **点了没反应** → 抛 FlowError。

        最后一条是 2026-11-13 实测踩出来的坑：那次点了「发表」，
        页面其实什么都没发生（视频还在处理，按钮是灰的），
        而代码只返回 None，看起来像「只是没拿到链接」。
        **静默返回 None 会让人以为只差一个链接，其实稿件压根没发出去。**
        """
        import time

        selector = self.config.need("post", "submit_button")
        if not self.driver.is_enabled(selector):
            raise FlowError(
                "「发表」按钮点不动——视频可能还在平台处理中。\n"
                "这种按钮点了也不会发出去，所以这里不点。"
                "先等平台处理完，或者去内容管理页看这条视频的状态。"
            )

        before_url = self.driver.page.url
        self.driver.click(selector)

        deadline = time.monotonic() + self.config.publish_effect_ms / 1000
        reacted = False
        while True:
            url = self.read_published_url()
            if url:
                return url
            if self._has_effect(before_url, selector):
                reacted = True
            if time.monotonic() >= deadline:
                break
            time.sleep(1)

        if reacted:
            # 发出去了，只是链接没拿到——交给人手动回填
            return None
        raise FlowError(
            "点了「发表」，但页面没反应——既没有成功提示，URL 也没变。\n"
            "稿件很可能没发出去。**先到内容管理页核实**，确认没发再重发；"
            "别直接重发，可能已经发出去了。"
        )

    def _has_effect(self, before_url: str, submit_selector: list[str]) -> bool:
        """点了之后，页面有反应吗。

        四样都算反应：

        1. 选择器表里说的「成功标记」出现了（且看得见）；
        2. 「成功提示」（toast）出现了；
        3. 页面 URL 变了（跳到内容列表或成功页）；
        4. **「发表」自己变灰了**——平台开始处理这次发表了。
           （点之前它是可点的，否则这里根本不会点。）
        """
        for key in ("published_marker", "published_notice"):
            for candidate in self.config.maybe("post", key):
                try:
                    if self.driver.is_visible(candidate):
                        return True
                except ActionError:
                    continue
        try:
            if not self.driver.is_enabled(submit_selector):
                return True
        except ActionError:
            return True  # 按钮没了 = 页面已经变了
        try:
            return self.driver.page.url != before_url
        except Exception:  # pragma: no cover - 页面已关
            return False

    def read_published_url(self) -> str | None:
        """从页面上把发布链接读出来。

        **只看得见的东西才算。** Playwright 的 `inner_text()` 对
        `display:none` 的元素返回的是 textContent——也就是说，
        一条**还藏着的**链接也会被读出来。读出来就以为「发布成功了」，
        可页面上其实什么都没发生（2026-11-13 那次就是这样蒙混过去的）。

        三层尝试，从确定到碰运气：

        1. 选择器表里明确指定的文本框 / 输入框（且看得见）；
        2. 页面上按特征匹配的链接（`published_url_contains`）；
        3. 都没有 → 返回 None，**不猜、不编**。
        """
        for key in ("published_url_text", "published_url_input"):
            candidates = self.config.maybe("post", key)
            for candidate in candidates:
                try:
                    if not self.driver.is_visible(candidate):
                        continue
                    if key.endswith("_input"):
                        value = self.driver.value_of(candidate)
                    else:
                        value = self.driver.text_of(candidate)
                except ActionError:
                    continue
                value = (value or "").strip()
                if value.startswith("http"):
                    return value

        for needle in self.config.maybe("post", "published_url_contains"):
            for href in self.driver.links(containing=needle):
                if href.startswith("http"):
                    return href
        return None


def check_limits(plan: PublishPlan, limits: dict | None = None) -> list[str]:
    """发布前再核一遍字数与符号。

    出包时 `channels` adapter 已经核过一遍；这里再核一次是因为
    **浏览器的输入框有它自己的规则**（比如短标题拒收中文逗号）。
    在填进去之前拦住，比发出去之后发现被拒强。

    返回问题清单，空清单表示没问题。
    """
    limits = limits or LIMITS
    problems: list[str] = []
    if len(plan.title) > limits["title_chars"]:
        problems.append(
            f"标题 {len(plan.title)} 字，超过上限 {limits['title_chars']} 字")
    for char, fix in TITLE_REJECTED.items():
        if char in plan.title:
            problems.append(
                f"标题里有「{char}」，视频号短标题会拒（实测），请改成{fix}")
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
