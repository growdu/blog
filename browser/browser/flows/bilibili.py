"""B站（哔哩哔哩）投稿流程：传片 → 填表 → 存草稿。

**这个流程只到「存草稿」为止，不点「立即投稿」。**
「立即投稿」是把视频公开给所有人看的不可逆动作；「存草稿」只存在自己的
创作中心里，随时能改、随时能删。本流程的目标就是后者。

**页面结构不是猜的。** 2026-11-13 用真实账号（growdu）实测过投稿页，
选择器表放在 `browser/selectors/bilibili.json`——**数据，不是代码**——
页面改版时改 JSON，不用改 Python。

**实测拿到的几条平台规则**（都写进了代码，不是写在注释里）：

1. **分区是「人选分区」灰测体系**：下拉里是 31 个**扁平**项
   （`human_type2` id 1001–1031），「科技数码」= 1012。
   规格里写的二级分区「计算机技术」（tid=231）**在下拉里根本选不到**。
2. **封面不是两个上传框，而是一个弹层**：点「添加封面」打开「封面制作」，
   里面上传一张图，平台自己按 4:3（首页推荐）和 16:9（个人空间）
   两个比例裁。
3. **创作声明和内容授权在同一个下拉里**：中间用分隔线隔开。
   选完创作声明下拉会收起，选内容授权要**重新打开**。
4. **标签要一个一个回车**：塞一整串逗号分隔的进去，回车只会落成一个标签。
   而且页面上会**自带几个推荐标签**（跟着分区走），填之前要先删干净。
5. **字幕**在「更多设置 → 字幕设置 → 上传字幕」，是个**按钮**而不是
   `<input type=file>`——点了才弹系统文件框。传完就已经生效，
   **不用再去字幕管理页提交**。
6. **上传完成后平台会弹通知权限询问框**，挡在页面上，
   不关掉它后面什么都点不动。
7. **上传文件的成败不写在页面上**：实测 B站 的 upos 接口会直接返回
   400 + JSON 业务错误，页面上既不报错也不留痕迹（见浏览器/docs/00-设计.md
   「为什么内置浏览器传不了 B站」）。所以这里**盯网络回读上传请求的状态码**，
   400 就立刻报错，别带着一个没传上去的视频往下填表。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from browser.driver import ActionError, PageDriver
from browser.plan import BilibiliPlan

# 选择器表的默认位置：browser/selectors/bilibili.json。
# 注意是 parents[2]——本文件在 browser/browser/flows/ 下，
# parents[0]=flows、parents[1]=browser 包、parents[2]=browser/ 顶层目录。
DEFAULT_SELECTORS_PATH = Path(__file__).resolve().parents[2] / "selectors" / "bilibili.json"

# B站 的字数限制（数字来自 publish/capabilities/bilibili.toml 的 [limits]，
# 口径是「小于 N 字」，所以上限取 N-1）。
LIMITS = {
    "title_chars": 79,
    "description_chars": 249,
    "tags_chars": 199,
    "tag_chars": 20,
}

# 平台默认值（实测 2026-11-13）。
PARTITION_NAME = "科技数码"
CREATION_STATEMENT = "含AI生成内容"
COPYRIGHT_TEXT = "内容为自制：未经作者允许，禁止转载"


class FlowError(RuntimeError):
    """B站 流程跑不下去。消息里要说清下一步。"""


def _normalize(text: str) -> str:
    """把连续空白压成单个空格。

    **为什么要压。** 简介是 Quill 富文本：段落之间的换行，
    页面读回来是**三个**换行，原文是**两个**——
    字符数差了 6，内容一个字没变（实测 2026-11-13）。
    直接比字符串会把它误判成「被平台改写了」，
    于是明明填对了，流程却在存草稿之前自己报错。
    """
    return " ".join(text.split())


@dataclass
class BilibiliConfig:
    """选择器表 + 行为开关。"""

    entry_url: str = "https://member.bilibili.com/platform/upload/video/frame"
    selectors: dict = field(default_factory=dict)
    # 等成片上传完成（平台转码、取封面），最多等多久（毫秒）。
    upload_ready_ms: int = 900_000
    # 点完「存草稿」，最多等多久看页面有没有反应（毫秒）。
    draft_effect_ms: int = 60_000
    # 传完封面，等平台出预览最多等多久（毫秒）。
    cover_effect_ms: int = 60_000

    @classmethod
    def load(cls, path: Path | None = None) -> "BilibiliConfig":
        target = Path(path) if path else DEFAULT_SELECTORS_PATH
        if not target.is_file():
            raise FlowError(
                f"选择器表不存在：{target}\n"
                "先跑 `python3 -m browser.cli probe-bilibili` 探一次页面结构，"
                "再照着填这张表。"
            )
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise FlowError(f"选择器表读不出来：{error}") from error
        timeouts = raw.get("timeouts") or {}
        return cls(
            entry_url=str(raw.get("entry_url") or cls.entry_url),
            selectors=raw.get("selectors") or {},
            upload_ready_ms=int(timeouts.get("upload_ready_ms", cls.upload_ready_ms)),
            draft_effect_ms=int(timeouts.get("draft_effect_ms", cls.draft_effect_ms)),
            cover_effect_ms=int(timeouts.get("cover_effect_ms", cls.cover_effect_ms)),
        )

    def need(self, group: str, key: str) -> list[str]:
        """取一组候选选择器；一个都没有就报错并说清怎么补。"""
        values = (self.selectors.get(group) or {}).get(key) or []
        if isinstance(values, str):
            values = [values]
        if not values:
            raise FlowError(
                f"选择器表里没有 {group}.{key}。\n"
                "跑 `python3 -m browser.cli probe-bilibili` 看页面结构，把候选选择器填进 "
                "browser/selectors/bilibili.json。"
            )
        return list(values)

    def maybe(self, group: str, key: str) -> list[str]:
        """取候选选择器；没有就返回空列表（这一步是可选的）。"""
        values = (self.selectors.get(group) or {}).get(key) or []
        if isinstance(values, str):
            values = [values]
        return list(values)


class BilibiliFlow:
    """B站 创作中心的投稿流程。"""

    def __init__(self, driver: PageDriver, config: BilibiliConfig | None = None) -> None:
        self.driver = driver
        self.config = config or BilibiliConfig.load()

    # -- 登录 ---------------------------------------------------------------

    def open_entry(self) -> None:
        """打开 B站 投稿页。"""
        self.driver.page.goto(self.config.entry_url, wait_until="domcontentloaded")

    def is_logged_in(self) -> bool:
        """当前页面是不是已登录状态。

        **判据要选「登录后一定在」的东西。** 未登录时投稿页会跳到
        `passport.bilibili.com/login`，URL 变了就是没登录——这条比找页面元素稳。
        """
        url = self.driver.page.url or ""
        if "passport.bilibili.com" in url:
            return False
        markers = self.config.maybe("login", "logged_in_marker")
        if not markers:
            return True
        return self.driver.exists(markers)

    def wait_for_login(self, *, timeout_ms: int = 300000) -> bool:
        """等人扫码登录。

        **这一步必须由人完成。** 扫码是拿手机对着屏幕，自动化代替不了。
        超时返回 False，不抛异常——「没扫」不是错误。
        """
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            if self.is_logged_in():
                return True
            time.sleep(2)
        return False

    # -- 传片 ---------------------------------------------------------------

    def upload_video(self, path: Path) -> None:
        """上传成片，并盯住上传请求的成败。

        **为什么要盯网络而不是看页面。** 实测（2026-11-13）：B站 的上传
        失败时**页面上什么都不显示**——没有报错、没有进度条、传完又回到
        「点击上传」的样子，但服务端一条都没收到。之前一轮就是靠
        「页面上没报错」当成「传成功了」，白跑一轮。

        所以这里等**上传接口的响应**：拿到 2xx 才算传上去，
        拿到 4xx/5xx 立刻报错，并把服务端返回的错误原文带出来。

        **为什么用「挂监听器 + 轮询」而不是 `expect_response`。**
        Playwright 的同步 API 只在**调用 Playwright 接口时**才派发网络事件；
        而**上传响应可能在 `set_input_files` 还没返回时就到了**——
        `expect_response` 的等待器会漏掉这种「调用期间到达」的事件
        （实测 2026-11-13：封面上传早就成功了，流程却白等了 60 秒；
        成片上传因为响应慢，反而是好的——差别就藏在这里）。
        """
        selector = self.config.need("post", "video_file_input")
        # 上传框是 display:none 的，所以等「attached」而不是「visible」
        self.driver.wait_for(selector, state="attached", timeout_ms=60000)

        response = self.driver.upload_and_watch_response(
            selector, path, self._is_upload_response,
            timeout_ms=self.config.upload_ready_ms)
        if response is None:
            raise FlowError(
                f"等了 {self.config.upload_ready_ms // 1000} 秒，页面没有发出上传请求——"
                "文件没被浏览器交出去。先确认上传框是不是选中了成片。"
            )

        status = response.status
        body = ""
        try:
            body = (response.text() or "")[:400]
        except Exception:  # noqa: BLE001 - 读不到正文不算失败
            body = ""
        if not (200 <= status < 300):
            detail = f"，服务端返回：{body}" if body else ""
            raise FlowError(
                f"成片上传被服务端拒绝（HTTP {status}）{detail}\n"
                "**页面不会显示这个错误**，只看页面会误判成「传成功了」。"
            )

    def _is_upload_response(self, url: str) -> bool:
        """这个响应是不是「成片上传」那一条。

        B站 的上传接口长这样：`https://upos-xxx.bilivideo.com/ugcfxever/<biz>.mp4`。
        而 `/OK`（秒传探测）不传文件，别把它算成上传结果。

        **必须先把查询串去掉再比扩展名。** 实测 2026-11-13：真正上传那一条
        是分片 PUT，URL 后面挂着一长串签名参数——
        `…/ugcfxever/<biz>.mp4?X-Amz-Algorithm=…&partNumber=1&uploadId=…`。
        直接 `url.endswith(".mp4")` **永远不成立**，
        于是流程在 `expect_response` 上死等满 `upload_ready_ms`（15 分钟），
        而视频其实早就传上去了。

        **「合并分片」那条也算。** 上传实际是两步：PUT 传字节，
        再 POST `/upload/multipart/complete` 告诉服务端「拼好了」。
        两条都算上传相关的响应，**先到的先算**——通常就是 PUT。
        真正的「服务端拼好了」的判据是**表单解锁**，
        那是 `wait_form_ready` 负责的，两道闸门互补。
        """
        if "/upload/multipart/complete" in url:
            return True
        if "/ugcfxever/" not in url:
            return False
        path = url.split("?", 1)[0]
        return path.endswith(".mp4") or path.endswith(".flv") or path.endswith(".mkv")

    def wait_form_ready(self, *, timeout_ms: int = 120000) -> None:
        """等投稿表单出现（标题框可填）。

        成片传上去之后，平台还要转码、取封面，表单这时才解锁。
        """
        title_selector = self.config.need("post", "title_input")
        self.driver.wait_for(title_selector, state="visible", timeout_ms=timeout_ms)

    # -- 挡路的弹窗 ---------------------------------------------------------

    def dismiss_blocking_dialogs(self, *, limit: int = 6) -> list[str]:
        """关掉挡在页面上、不关就点不动别的的弹窗。

        **实测 2026-11-13**：上传完成后平台会弹一个「开启后视频上传完成
        第一时间通知」的权限询问框（`.videoup-notification-dialog`），
        它带着遮罩，**后面的每一次点击都会被它拦下来**——表现是
        「元素明明在，Playwright 却一直说点不动」。

        所以每次填表前先清一遍。返回关掉了哪些弹窗（给日志看）。
        """
        dismissed: list[str] = []
        notice = self.config.maybe("post", "notification_dismiss")
        cancel = self.config.maybe("post", "dialog_cancel")
        for _ in range(limit):
            progressed = False
            for kind, candidates in (("notification", notice), ("dialog", cancel)):
                if not candidates or not self.driver.is_visible(candidates):
                    continue
                try:
                    self.driver.click_visible(candidates)
                except ActionError:
                    # 弹窗互相盖着时，Playwright 的点击会被上面那层拦下来。
                    # 这时改用 DOM 级的 click：它不走命中测试，
                    # 点到的就是**这个**元素自己。
                    try:
                        self.driver.js_click(candidates)
                    except ActionError:
                        continue
                dismissed.append(kind)
                progressed = True
                break
            if not progressed:
                break
        return dismissed

    # -- 下拉 ---------------------------------------------------------------

    def choose_option(self, trigger_key: str, option_text: str, *,
                      group: str = "post") -> None:
        """下拉选一项。

        B站 的分区与创作声明都是自绘下拉：先点开，再点选项。

        **选项选择器里可以写 `{text}`**，流程会用实际要选的文字替换它——
        这样选择器表既能圈住选项所在的区域，又能指定选哪一项，
        不用把文字硬编在代码里。
        """
        trigger = self.config.need(group, trigger_key)
        self.driver.click_visible(trigger)
        options = self.config.maybe(group, f"{trigger_key}_option")
        if options:
            candidates = [option.format(text=option_text) for option in options]
        else:
            candidates = [f"text={option_text}"]
        self.driver.wait_for(candidates, state="visible", timeout_ms=30000)
        self.driver.click_visible(candidates)

    def set_partition(self, name: str = PARTITION_NAME) -> None:
        """选分区。

        **实测：投稿页跑的是「人选分区」灰测体系**，下拉是 31 个扁平项。
        选「科技数码」投稿后，B站 落库成「科技 → 软件应用」，
        稿件接口回读的是 `tid = 230`（父分区 188 科技）。

        **注意选分区会换掉页面自带的推荐标签**（标签跟着分区走），
        所以填标签必须在选分区**之后**。
        """
        self.choose_option("partition_trigger", name)

    def set_creation_statement(self, name: str = CREATION_STATEMENT) -> None:
        """选创作声明。"""
        self.choose_option("creation_statement_trigger", name)

    def set_copyright(self, text: str = COPYRIGHT_TEXT) -> None:
        """内容授权：内容为自制 + 禁止转载。

        实测回读是 `copyright=1` + `no_reprint=1`。

        **它和创作声明在同一个下拉里**（中间隔一条分隔线），
        所以选完创作声明要把下拉**重新打开**再点。
        """
        options = self.config.maybe("post", "copyright_option")
        if not options:
            return
        trigger = self.config.maybe("post", "creation_statement_trigger")
        if trigger:
            self.driver.click_visible(trigger)
        candidates = [option.format(text=text) for option in options]
        self.driver.wait_for(candidates, state="visible", timeout_ms=30000)
        self.driver.click_visible(candidates)

    # -- 填表 ---------------------------------------------------------------

    def fill_text(self, title: str, description: str, tags: list[str]) -> None:
        """填标题、简介、标签。

        **简介是 Quill 富文本**（`div[contenteditable]`），不是 textarea；
        Playwright 的 `fill()` 对 contenteditable 一样管用。

        **标签一个一个来**：塞一整串逗号分隔的进去，回车只会落成一个
        「a,b,c」这样的标签。而页面上还会自带几个推荐标签，
        填之前先删干净。
        """
        title_selector = self.config.need("post", "title_input")
        desc_selector = self.config.need("post", "description_input")
        self.driver.wait_for(title_selector, timeout_ms=60000)
        self.driver.fill(title_selector, title)
        self.driver.fill(desc_selector, description)

        tag_selector = self.config.maybe("post", "tags_input")
        if not tag_selector or not tags:
            return
        self.clear_tags()
        chip_selector = self.config.maybe("post", "tag_chip")
        for tag in tags:
            self._add_tag(tag_selector, chip_selector, tag)

    def _add_tag(self, tag_selector: list[str], chip_selector: list[str],
                 tag: str, *, attempts: int = 4) -> None:
        """加一个标签，并且**确认它真的落成了芯片**。

        **为什么要确认。** 实测 2026-11-13：填完标签按回车，
        **只有第一个标签落成了芯片**，后面的就没了——页面把输入框重渲染了，
        焦点丢了，回车落到 body 上，什么都没发生。

        看起来像「标签没加上」，其实是**没按到那个框上**。
        所以这里每加一个都数一遍芯片：没多就重填重按，
        重试几次都不行才报错。
        """
        before = self.driver.count(chip_selector) if chip_selector else 0
        for _ in range(attempts):
            self.driver.fill(tag_selector, tag)
            # 给页面一点时间把输入同步进它自己的状态机
            time.sleep(0.4)
            # 按键要发给**这个输入框**，不能发给「当前焦点」
            self.driver.press_key(tag_selector, "Enter")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if chip_selector and self.driver.count(chip_selector) > before:
                    return
                time.sleep(0.2)
        raise FlowError(
            f"标签「{tag}」没落成芯片（重试了 {attempts} 次）。\n"
            "标签框可能是被页面重渲染了，焦点丢了——"
            "这时候回车是落到页面上的，不会变成标签。")

    def clear_tags(self) -> int:
        """删掉页面上自带的标签芯片，返回删了几个。

        **平台会按分区自动塞几个推荐标签**（分区=人工智能时是
        「生活记录/记录/剪辑」）。不删掉就等于给每期都贴上这些。

        **删除按钮要用 DOM 级的事件派发。** 那个「×」是个 9×9 像素的
        `<svg>`，Playwright 的真点击会判成「不稳定」然后超时；
        而 `el.click()` 又不行——**SVG 元素没有 click() 方法**。
        """
        chips = self.config.maybe("post", "tag_chip")
        remove = self.config.maybe("post", "tag_chip_remove")
        if not chips or not remove:
            return 0
        removed = 0
        for _ in range(12):
            if not self.driver.exists(chips):
                break
            try:
                self.driver.js_click(remove)
            except ActionError:
                break
            removed += 1
        return removed

    # -- 封面 ---------------------------------------------------------------

    def set_cover(self, path: Path) -> list[str]:
        """传封面。

        **实测：不是两个 input，而是一个「封面制作」弹层。**
        点「添加封面」→ 弹层里上传一张图 → 平台按 4:3（首页推荐）
        和 16:9（个人空间）两个比例裁。

        **「完成」要点两次**（实测 2026-11-13）：第一次点会弹出
        「检测到个人空间封面（16:9）未修改，是否将 4:3 的改动同步到 16:9？」
        ——因为上传只改了 4:3 那张，16:9 还是空的（canvas 全黑）。
        选「确认同步」之后弹层**不会自己关**，要**再点一次「完成」**。

        封面的上传接口是 `POST https://archive.biliimg.com/bfs/archive/<hash>.jpg`
        ——注意**不是** `/upload/file`（那条是页面加载时 AI 自动封面上传用的）。

        返回实际用到的步骤（给日志看）。
        """
        steps: list[str] = []
        button = self.config.maybe("post", "cover_button")
        if not button:
            raise FlowError(
                "选择器表里没有 post.cover_button——封面入口变了？\n"
                "跑 `python3 -m browser.cli probe-bilibili` 看现在的结构。"
            )
        self.driver.click_visible(button)
        steps.append("open")

        dialog = self.config.maybe("post", "cover_dialog")
        if dialog:
            self.driver.wait_for(dialog, state="visible", timeout_ms=30000)

        cover_input = self.config.maybe("post", "cover_input")
        if not cover_input:
            raise FlowError(
                "选择器表里没有 post.cover_input——封面弹层里找不到上传口。\n"
                "跑 `python3 -m browser.cli probe-bilibili` 看现在的结构。"
            )
        self.driver.upload(cover_input, path)
        steps.append("upload")

        # 上传是点最后那次「完成」时才发出去的，所以监听器先挂上。
        watcher = self.driver.watch_response(self._is_cover_response)
        try:
            self._confirm_cover()
            response = watcher.wait(timeout_ms=self.config.cover_effect_ms)
        finally:
            watcher.close()

        if response is None:
            raise FlowError(
                f"等了 {self.config.cover_effect_ms // 1000} 秒，平台没发出封面上传请求——"
                "这张封面没被交上去。\n"
                "**页面上不会显示这个错误**，别以为封面已经设好了。"
            )
        if not (200 <= response.status < 300):
            raise FlowError(
                f"封面被服务端拒绝（HTTP {response.status}）\n"
                "**页面不会显示这个错误**，别以为封面已经设好了。")
        steps.append("saved")
        return steps

    def _confirm_cover(self, *, rounds: int = 4) -> None:
        """点「完成」，必要时处理「同步 16:9」的确认框。

        **实测：完成要点两次。** 第一次点完会问
        「是否将 4:3 封面的改动同步到 16:9 封面」——
        不同步的话 16:9 那张是全黑的（页面上看不出来，只有 canvas 能看出来）。
        选「确认同步」之后弹层不会自己关，**要再点一次「完成」**。
        """
        confirm = self.config.maybe("post", "cover_confirm")
        sync_modal = self.config.maybe("post", "cover_sync_modal")
        sync_confirm = self.config.maybe("post", "cover_sync_confirm")
        dialog = self.config.maybe("post", "cover_dialog")

        for _ in range(rounds):
            if dialog and not self.driver.is_visible(dialog):
                return          # 弹层关了 = 封面应用完了
            if confirm:
                self.driver.click_visible(confirm)
            time.sleep(1.5)
            if sync_modal and self.driver.is_visible(sync_modal):
                if sync_confirm:
                    self.driver.click_visible(sync_confirm)
                time.sleep(1.5)
                continue
        if dialog and self.driver.is_visible(dialog):
            raise FlowError(
                "封面弹层点了「完成」也没关上——"
                "多半是那个「是否同步 16:9」的确认框还在，"
                "同步没选成，封面没生效。")

    def _is_cover_response(self, url: str) -> bool:
        """这个响应是不是「封面图上传」那一条。

        实测 2026-11-13：封面走
        `POST https://archive.biliimg.com/bfs/archive/<hash>.jpg`。

        **别用 `/upload/file` 判**——那条是页面加载时
        「AI 自动生成封面」用的，和我们自己传的封面不是一回事；
        拿它当判据，就会把 AI 那次上传误认成「我们的封面上传成功了」。
        """
        if "/bfs/archive/" not in url:
            return False
        path = url.split("?", 1)[0]
        return path.endswith(".jpg") or path.endswith(".jpeg") or path.endswith(".png")

    # -- 字幕 ---------------------------------------------------------------

    def upload_subtitle(self, path: Path) -> bool:
        """传字幕（`.srt`）。

        **实测 2026-11-13：「上传字幕」不是系统文件框，是B站 自己的弹窗。**
        入口在「更多设置 → 视频元素 → 字幕设置 → 上传字幕」，
        点开是一个弹窗：语言选「中文」、一个「+ 上传文件」按钮，
        以及「取消 / 确认」——**「确认」在选文件之前是灰的，点不动**。

        所以要三步：打开弹窗 → 点「+ 上传文件」（这时才弹系统文件框）
        → 点「确认」。

        **传完就已经生效**，不用再去字幕管理页提交
        （实测：字幕管理页那行直接显示「已发布」）。
        """
        if not path.is_file():
            return False
        more = self.config.maybe("post", "more_settings_button")
        if more:
            try:
                self.driver.click_visible(more)
            except ActionError:
                pass
        # 面板是折叠的，给它一点展开时间
        time.sleep(1.0)

        button = self.config.maybe("post", "subtitle_button")
        if not button:
            return False
        try:
            self.driver.click_visible(button)
        except ActionError:
            return False
        # 弹窗要弹出来才有点里面的东西
        time.sleep(1.0)
        self._dump_dialogs("subtitle-dialog")

        file_button = self.config.maybe("post", "subtitle_file_button")
        uploaded = False
        if file_button:
            try:
                self.driver.upload_via_chooser(file_button, path)
                uploaded = True
            except ActionError:
                uploaded = False
        if not uploaded:
            # 少数版本直接给一个隐藏的 input，两条路都试一下
            fallback = self.config.maybe("post", "subtitle_input")
            if fallback:
                try:
                    self.driver.upload(fallback, path)
                    uploaded = True
                except ActionError:
                    uploaded = False
        if not uploaded:
            self._close_subtitle_dialog()
            return False

        # 选完文件，「确认」才可点
        confirm = self.config.maybe("post", "subtitle_confirm")
        if confirm:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                try:
                    if self.driver.is_enabled(confirm):
                        self.driver.click_visible(confirm)
                        break
                except ActionError:
                    pass
                time.sleep(0.5)
        return uploaded

    def _close_subtitle_dialog(self) -> None:
        """把「上传字幕」弹窗关掉。

        **必须关。** 这个弹窗带遮罩，不关它的话后面点「存草稿」
        会被拦下来——表现是「按钮明明在，却点不动」。
        """
        cancel = self.config.maybe("post", "subtitle_cancel")
        if cancel:
            try:
                self.driver.click_visible(cancel)
                return
            except ActionError:
                pass
        try:
            self.driver.page.keyboard.press("Escape")
        except Exception:  # noqa: BLE001
            pass

    def _dump_dialogs(self, name: str) -> None:
        """把当前可见的弹窗结构 dump 到临时目录（调试用）。

        **为什么要有。** B站 的弹窗结构没有稳定类名，
        照着 dump 出来的 HTML 填选择器，比一次次猜快得多。
        """
        import os

        if not os.environ.get("BROWSER_DEBUG_DOM"):
            return
        try:
            html = self.driver.page.evaluate(
                """() => Array.from(document.querySelectorAll('.bcc-dialog__wrap-mask'))
                    .filter(el => getComputedStyle(el).display !== 'none')
                    .map(el => el.outerHTML).join('\n---\n')""")
            target = Path(f"/tmp/mcode-upload-probe/{name}.html")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(html or "", encoding="utf-8")
        except Exception:  # noqa: BLE001 - 调试功能不该影响主流程
            pass

    # -- 核对 ---------------------------------------------------------------

    def verify_filled(self, title: str, description: str, tags: list[str]) -> dict:
        """把页面上**实际的**内容读回来核对。

        **填进去 ≠ 页面收下了。** 输入框可能被限长截断、被平台改写；
        标签也可能只落成了一串普通文字。存草稿之前读回来核一遍，
        比存完才发现被截断强。
        """
        actual_title = self.driver.value_of(self.config.need("post", "title_input"))
        if actual_title != title:
            hint = ""
            if not actual_title:
                hint = ("\n页面上标题是**空的**——多半是中途刷新过页面"
                        "（表单内容全丢了）。重跑一次，别在这个状态上接着点。")
            raise FlowError(
                f"标题没填对：想填「{title}」，页面上是「{actual_title}」{hint}")

        actual_desc = self._read_field(self.config.need("post", "description_input"))
        if description and _normalize(description) not in _normalize(actual_desc):
            raise FlowError(
                "简介没完整填进去（可能被截断或被平台改写）："
                f"想填 {len(description)} 字，页面上是 {len(actual_desc)} 字")

        tag_selector = self.config.maybe("post", "tag_chip")
        tag_count = self.driver.count(tag_selector) if tag_selector else 0
        if tags and tag_selector and tag_count < len(tags):
            raise FlowError(
                f"标签只成了 {tag_count} 个（要 {len(tags)} 个）——"
                "回车没把标签变成真标签")

        return {
            "title_in_page": actual_title,
            "description_chars_in_page": len(actual_desc),
            "tag_chips_in_page": tag_count,
        }

    def _read_field(self, selector: list[str]) -> str:
        """读一个输入区的当前内容。

        **简介框是 contenteditable，不是 textarea。**
        textarea 的 `input_value()` 读的是当前值，但 contenteditable
        只能读 `inner_text()`——所以两个都试，哪个有值用哪个。
        """
        try:
            value = self.driver.value_of(selector)
            if value:
                return value
        except ActionError:
            pass
        return self.driver.text_of(selector)

    # -- 存草稿 -------------------------------------------------------------

    def save_draft(self) -> str | None:
        """点「存草稿」，等页面有反应。

        返回页面上读到的提示文本（没有就返回 None）。

        **不点「立即投稿」。** 存草稿只进自己的创作中心；
        立即投稿会把视频公开出去，是不可逆的外部可见动作。

        **点完会跳页，Playwright 却把这次点击报成失败。**
        实测 2026-11-13：点「存草稿」→ 页面跳去草稿箱 →
        元素被卸载 → Playwright 的点击后置检查失败、抛异常。
        看着像「点不动」，其实**草稿已经存下来了**。
        所以这里要分清两种情况：**页面跳走了 = 存成功了**。
        """
        selector = self.config.need("post", "draft_button")
        if not self.driver.is_enabled(selector):
            raise FlowError(
                "「存草稿」按钮点不动——平台可能还在处理视频。\n"
                "这种按钮点了也不会生效，所以这里不点。"
                "先去创作中心看这条视频的状态，再决定要不要重来。"
            )

        before_url = self.driver.page.url
        try:
            self.driver.click_visible(selector)
        except ActionError:
            # 页面跳走了 = 草稿存下来了（点击其实成功了，
            # 只是元素被卸载，Playwright 把它报成了失败）
            if self.driver.page.url == before_url:
                raise
            return "已跳转草稿箱"

        deadline = time.monotonic() + self.config.draft_effect_ms / 1000
        while time.monotonic() < deadline:
            notice = self.read_draft_notice()
            if notice:
                return notice
            if self.driver.page.url != before_url:
                return "已跳转草稿箱"
            time.sleep(1)

        raise FlowError(
            "点了「存草稿」，但页面没反应——既没有提示，URL 也没变。\n"
            "**不要直接重发**，先去创作中心的稿件管理里核实："
            "草稿可能已经存下来了。"
        )

    def read_draft_notice(self) -> str | None:
        """读「存草稿」之后的提示文本（看得见的才算）。"""
        for candidate in self.config.maybe("post", "draft_notice"):
            try:
                if not self.driver.is_visible(candidate):
                    continue
                text = (self.driver.text_of(candidate) or "").strip()
                if text:
                    return text
            except ActionError:
                continue
        return None

    # -- 串起来 -------------------------------------------------------------

    def draft(self, plan: BilibiliPlan, *, cover: Path | None = None,
              subtitle: Path | None = None) -> dict:
        """把发布包里的东西都填进页面，然后**存草稿**。

        返回一份「填了什么 + 存成什么」的清单，供人核对。
        """
        if not plan.video or not plan.video.is_file():
            raise FlowError(f"发布包里没有成片：{plan.package_dir}")

        self.open_entry()
        self.upload_video(plan.video)
        self.wait_form_ready()

        # 上传完成后平台会弹权限询问框，不关就什么都点不动
        dismissed = self.dismiss_blocking_dialogs()

        filled: dict = {
            "episode": plan.episode,
            "title": plan.title,
            "description": plan.description,
            "tags": plan.tags,
            "video": str(plan.video),
            "dismissed_dialogs": dismissed,
        }

        # **顺序有讲究**：分区会换掉页面自带的推荐标签，
        # 所以先选分区，再填标签。
        self.set_partition()
        filled["partition"] = f"{PARTITION_NAME}（落库 tid=230）"

        self.set_creation_statement()
        filled["creation_statement"] = CREATION_STATEMENT

        self.set_copyright()
        filled["copyright"] = "自制，禁止转载"

        self.fill_text(plan.title, plan.description, plan.tags)

        cover_path = Path(cover) if cover else plan.cover
        if cover_path and cover_path.is_file():
            filled["cover"] = str(cover_path)
            filled["cover_steps"] = self.set_cover(cover_path)
        else:
            filled["cover"] = "（没有封面文件，用平台自动生成的）"

        subtitle_path = Path(subtitle) if subtitle else plan.subtitle
        if subtitle_path and subtitle_path.is_file():
            filled["subtitle"] = str(subtitle_path)
            filled["subtitle_uploaded"] = self.upload_subtitle(subtitle_path)
        else:
            filled["subtitle"] = "（没有字幕文件）"
            filled["subtitle_uploaded"] = False

        filled.update(self.verify_filled(plan.title, plan.description, plan.tags))

        notice = self.save_draft()
        filled["draft_notice"] = notice or "（页面没有给出提示文本）"
        filled["status"] = "drafted"
        return filled


def check_limits(plan: BilibiliPlan, limits: dict | None = None) -> list[str]:
    """发布前再核一遍字数与符号。

    出包时 `bilibili` adapter 已经核过一遍；这里再核一次是因为
    **浏览器的输入框有它自己的规则**。在填进去之前拦住，
    比存完草稿才发现被拒强。

    返回问题清单，空清单表示没问题。
    """
    limits = limits or LIMITS
    problems: list[str] = []
    if len(plan.title) > limits["title_chars"]:
        problems.append(
            f"标题 {len(plan.title)} 字，超过上限 {limits['title_chars']} 字")
    if len(plan.description) > limits["description_chars"]:
        problems.append(
            f"简介 {len(plan.description)} 字，超过上限 {limits['description_chars']} 字")
    tags_csv = plan.tags_as_csv()
    if len(tags_csv) > limits["tags_chars"]:
        problems.append(
            f"标签总长 {len(tags_csv)} 字，超过上限 {limits['tags_chars']} 字")
    for tag in plan.tags:
        if len(tag) > limits["tag_chars"]:
            problems.append(
                f"标签「{tag}」{len(tag)} 字，超过上限 {limits['tag_chars']} 字")
    return problems
