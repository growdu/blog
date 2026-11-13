"""页面动作原语：把「等元素、填字、上传文件、点按钮」包成会失败得很响的调用。

**为什么要自己包一层。** Playwright 的原生异常在排查时很难受：
`TimeoutError: Timeout 30000ms exceeded.` 不会告诉你**是哪个框没等到**，
也不会告诉你**页面上当时长什么样**。而投稿这件事最常见的问题恰恰是
「页面改版了，那个框改名了」——报错必须直接指向这个事实。

所以本模块的约定：

1. 每个动作失败都抛 `ActionError`，消息里写清楚：想要什么、试了哪些选择器、
   等了多久、失败时页面在哪个 URL。
2. 选择器可以给一个**候选列表**，挨个试——站点小改版时不用改代码。
3. `ActionError` 带上失败瞬间的截图路径（如果调用方给了截图目录）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

Selector = str | Sequence[str]


class ActionError(RuntimeError):
    """页面动作失败。消息要能让人一眼看出下一步该干什么。"""

    def __init__(self, message: str, *, selectors: Iterable[str] = (),
                 url: str | None = None, shot: Path | None = None) -> None:
        self.selectors = list(selectors)
        self.url = url
        self.shot = shot
        parts = [message]
        if self.selectors:
            parts.append("试过的选择器：" + " | ".join(self.selectors))
        if url:
            parts.append(f"失败时页面 URL：{url}")
        if shot:
            parts.append(f"失败时截图：{shot}")
        super().__init__("\n".join(parts))


def _as_list(selector: Selector) -> list[str]:
    if isinstance(selector, str):
        return [selector]
    return [s for s in selector if s]


class PageDriver:
    """在某个 page 上做事的薄封装。"""

    def __init__(self, page, *, timeout_ms: int = 20000,
                 shot_dir: Path | None = None) -> None:
        self.page = page
        self.timeout_ms = timeout_ms
        self.shot_dir = Path(shot_dir) if shot_dir else None
        self._shot_index = 0

    # -- 内部 ---------------------------------------------------------------

    def _url(self) -> str | None:
        try:
            return self.page.url
        except Exception:  # pragma: no cover - 页面已关
            return None

    def _shot(self, tag: str) -> Path | None:
        """失败时抓一张图。没有截图目录就返回 None。"""
        if self.shot_dir is None:
            return None
        try:
            self.shot_dir.mkdir(parents=True, exist_ok=True)
            self._shot_index += 1
            path = self.shot_dir / f"fail-{self._shot_index:02d}-{tag}.png"
            self.page.screenshot(path=str(path), full_page=True)
            return path
        except Exception:  # pragma: no cover - 截图失败不该盖掉真正的错误
            return None

    def _fail(self, message: str, selectors: Iterable[str], tag: str) -> "ActionError":
        return ActionError(message, selectors=selectors, url=self._url(),
                           shot=self._shot(tag))

    def _frames(self):
        """主文档 + 所有子 frame。

        **为什么不能只看主文档。** 视频号助手的投稿页是「主文档放上传区、
        micro frame 放表单」的结构，而且**同一个上传框有时挂在主文档、
        有时挂在 frame 里**（实测两次实测落在不同地方）。
        只在主文档里找，就会出现「明明页面上有这个框，代码却说找不到」。
        所以定位一律跨 frame 找。
        """
        frames = [self.page.main_frame]
        for frame in self.page.frames:
            if frame != self.page.main_frame:
                frames.append(frame)
        return frames

    def _locator(self, selector: Selector):
        """返回第一个能解析到的 locator；一个都解析不到就抛 ActionError。

        顺序是「先候选选择器、后 frame」：更具体的候选选择器优先，
        免得一个宽泛的选择器在某个 frame 里先撞上不相干的元素。
        """
        candidates = _as_list(selector)
        if not candidates:
            raise ActionError("没给选择器")
        last_error = None
        for candidate in candidates:
            for frame in self._frames():
                try:
                    locator = frame.locator(candidate)
                    if locator.count() > 0:
                        return locator.first
                except Exception as error:  # 选择器语法错等
                    last_error = error
                    continue
        detail = f"（最后一个错误：{last_error}）" if last_error else ""
        raise self._fail(
            f"页面上找不到任何匹配的元素：{', '.join(candidates)}{detail}",
            candidates, "not-found",
        )

    # -- 动作 ---------------------------------------------------------------

    def wait_for(self, selector: Selector, *, state: str = "visible",
                 timeout_ms: int | None = None) -> None:
        """等到某个元素达到指定状态（visible / attached / hidden）。"""
        candidates = _as_list(selector)
        limit = timeout_ms if timeout_ms is not None else self.timeout_ms
        for candidate in candidates:
            for frame in self._frames():
                try:
                    frame.locator(candidate).first.wait_for(state=state, timeout=limit)
                    return
                except Exception:
                    continue
        raise self._fail(
            f"等了 {limit} ms，元素没等到「{state}」状态", candidates, "wait")

    def exists(self, selector: Selector) -> bool:
        """元素在不在（不抛异常）。跨 frame 找。"""
        for candidate in _as_list(selector):
            for frame in self._frames():
                try:
                    if frame.locator(candidate).count() > 0:
                        return True
                except Exception:
                    continue
        return False

    def fill(self, selector: Selector, text: str) -> None:
        """往输入框里填字（先清空）。"""
        candidates = _as_list(selector)
        locator = self._locator(selector)
        try:
            locator.wait_for(state="visible", timeout=self.timeout_ms)
            locator.fill(text)
        except Exception as error:
            raise self._fail(f"填字失败：{error}", candidates, "fill")
        return None

    def upload(self, selector: Selector, path: Path | str) -> None:
        """把本地文件喂给 `<input type=file>`。

        **用真文件路径，不构造内存里的 File 对象。** 走
        `set_input_files(path)` 让浏览器自己去读磁盘——大文件（成片几十兆）
        不会被塞进 Python 内存，也不会出现「文件名对、大小是 0」的情况。
        """
        target = Path(path)
        if not target.is_file():
            raise ActionError(f"要上传的文件不存在：{target}")
        candidates = _as_list(selector)
        locator = self._locator(selector)
        try:
            locator.set_input_files(str(target))
        except Exception as error:
            raise self._fail(f"上传失败：{error}", candidates, "upload")

    def upload_via_chooser(self, selector: Selector, path: Path | str, *,
                           timeout_ms: int = 30000) -> None:
        """点一个会弹出**系统文件选择框**的按钮，把本地文件交给它。

        **什么时候要这个。** 有些上传入口不是 `<input type=file>`，
        而是一个按钮——点了才弹系统文件框（B站 的「上传字幕」就是这种）。
        这种入口没法用 `set_input_files` 直接喂文件，
        只能等文件框事件（`filechooser`）出来，再把文件塞给它。

        **为什么不能用「先点再等」的写法。** 文件框事件是**点击那一刻**
        触发的；先点完再开始等，就永远等不到——事件已经过去了。
        所以监听必须先挂上，点击动作包在监听里。
        """
        target = Path(path)
        if not target.is_file():
            raise ActionError(f"要上传的文件不存在：{target}")
        candidates = _as_list(selector)
        locator = self._locator(selector)
        try:
            with self.page.expect_file_chooser(timeout=timeout_ms) as waiter:
                locator.click(timeout=self.timeout_ms)
            waiter.value.set_files(str(target))
        except Exception as error:
            raise self._fail(f"文件选择框没出来：{error}", candidates, "chooser")

    def click(self, selector: Selector) -> None:
        """点一下。"""
        candidates = _as_list(selector)
        locator = self._locator(selector)
        try:
            locator.wait_for(state="visible", timeout=self.timeout_ms)
            locator.click()
        except Exception as error:
            raise self._fail(f"点击失败：{error}", candidates, "click")

    def text_of(self, selector: Selector) -> str:
        """读元素的文本。"""
        candidates = _as_list(selector)
        locator = self._locator(selector)
        try:
            return (locator.inner_text() or "").strip()
        except Exception as error:
            raise self._fail(f"读文本失败：{error}", candidates, "text")

    def value_of(self, selector: Selector) -> str:
        """读输入框的当前值。"""
        candidates = _as_list(selector)
        locator = self._locator(selector)
        try:
            return (locator.input_value() or "").strip()
        except Exception as error:
            raise self._fail(f"读值失败：{error}", candidates, "value")

    def is_checked(self, selector: Selector) -> bool:
        """勾选框当前是不是勾上了。

        **读的是 DOM 的 checked，不是「看起来是勾上的」。** 视频号的
        「声明原创」有两层勾选（主勾选框 + 弹窗里的同意框），
        视觉上勾着不等于状态真的落下了。
        """
        candidates = _as_list(selector)
        locator = self._locator(selector)
        try:
            return bool(locator.is_checked())
        except Exception as error:
            raise self._fail(f"读勾选状态失败：{error}", candidates, "checked")

    def is_visible(self, selector: Selector) -> bool:
        """元素在不在**并且看得见**。

        `exists()` 只数 DOM 里有没有——隐藏的成功提示也算「有」。
        判断「事情有没有发生」要用这个。
        """
        candidates = _as_list(selector)
        for candidate in candidates:
            for frame in self._frames():
                try:
                    if frame.locator(candidate).first.is_visible():
                        return True
                except Exception:
                    continue
        return False

    def is_enabled(self, selector: Selector) -> bool:
        """这个元素现在**点得动**吗。

        **Playwright 自带的 is_enabled() 在这里不够用。** 它只认
        `disabled` 属性与 `aria-disabled`；而视频号的「发表」两样都没有——
        视频还在平台处理时，它只是**换成了灰色样式**（类名带 disabled）。

        于是 Playwright 觉得它可点，`click()` 正常返回，
        而平台什么也不做：**事件派发出去了，稿件没发出去**，
        而且日志里看不出任何异常（2026-11-13 实测，EP06 第一次投稿丢在这里）。

        所以这里额外看三样：类名里带 disabled、`pointer-events: none`、
        以及不可见（display:none / visibility:hidden）。
        """
        candidates = _as_list(selector)
        locator = self._locator(selector)
        try:
            return bool(locator.evaluate(
                """(el) => {
                    if (el.disabled === true) return false;
                    if (el.getAttribute('aria-disabled') === 'true') return false;
                    const cls = (el.getAttribute('class') || '').toLowerCase();
                    if (cls.indexOf('disabled') >= 0) return false;
                    const style = window.getComputedStyle(el);
                    if (style.pointerEvents === 'none') return false;
                    if (style.display === 'none' || style.visibility === 'hidden') {
                        return false;
                    }
                    return true;
                }"""))
        except Exception as error:
            raise self._fail(f"读可点状态失败：{error}", candidates, "enabled")

    def body_text(self) -> str:
        """主文档 + 所有 frame 的可见文字，拼成一段。

        上传完成后要等「取消上传」这类提示消失，才知道处理完了。
        """
        parts: list[str] = []
        for frame in self._frames():
            try:
                parts.append(frame.evaluate(
                    "() => document.body ? document.body.innerText : ''") or "")
            except Exception:
                continue
        return "\n".join(parts)

    def wait_for_text_gone(self, text: str, *, timeout_ms: int = 120000,
                           interval: float = 1.0) -> None:
        """等到页面里不再出现某段文字。

        用来判断「上传/转码处理完了」——平台处理中会挂一个「取消上传」的按钮，
        它消失才算完。没等就往下填表，表单可能还锁着。
        """
        import time

        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            if text not in self.body_text():
                return
            time.sleep(interval)
        raise self._fail(
            f"等了 {timeout_ms} ms，「{text}」还在页面上（处理可能没结束）",
            [text], "text-gone")

    def count(self, selector: Selector) -> int:
        """数一数有多少个元素匹配。跨 frame 求和。"""
        total = 0
        for candidate in _as_list(selector):
            for frame in self._frames():
                try:
                    total += frame.locator(candidate).count()
                except Exception:
                    continue
        return total

    def links(self, *, containing: str = "") -> list[str]:
        """页面上所有 http 链接（可按子串过滤）。跨 frame。

        **兜底用的。** 平台的「分享」弹层常常把链接藏在图标菜单里，
        DOM 路径又深又脆；与其一条条猜选择器，不如把页面上的链接捞出来
        按特征挑。
        """
        found: list[str] = []
        for frame in self._frames():
            try:
                hrefs = frame.evaluate(
                    """(needle) => Array.from(document.querySelectorAll('a[href]'))
                        .map(a => a.href)
                        .filter(h => h && h.startsWith('http')
                                 && (!needle || h.includes(needle)))""",
                    containing,
                )
            except Exception:
                continue
            found.extend(hrefs or [])
        # 去重但保持顺序
        seen: set[str] = set()
        unique: list[str] = []
        for href in found:
            if href not in seen:
                seen.add(href)
                unique.append(href)
        return unique

    def texts_of(self, selector: Selector) -> list[str]:
        """页面上所有匹配元素的**可见**文本（跨 frame）。

        **只收看得见的。** 隐藏的元素不算——列表页常把同一份 DOM
        渲染两份（一份藏在折叠面板里），把隐藏的那份也算进来，
        就会「找到」一条其实没显示出来的内容。
        """
        found: list[str] = []
        for candidate in _as_list(selector):
            for frame in self._frames():
                try:
                    items = frame.locator(candidate)
                    count = items.count()
                except Exception:
                    continue
                for index in range(count):
                    item = items.nth(index)
                    try:
                        if not item.is_visible():
                            continue
                        text = (item.inner_text() or "").strip()
                    except Exception:
                        continue
                    if text:
                        found.append(text)
        return found

    def texts_of(self, selector: Selector) -> list[str]:
        """页面上所有匹配元素的**可见**文本（跨 frame）。

        **只收看得见的。** 隐藏的元素不算——列表页常把同一份 DOM
        渲染两份（一份藏在折叠面板里），把隐藏的那份也算进来，
        就会「找到」一条其实没显示出来的内容。
        """
        found: list[str] = []
        for candidate in _as_list(selector):
            for frame in self._frames():
                try:
                    items = frame.locator(candidate)
                    count = items.count()
                except Exception:
                    continue
                for index in range(count):
                    item = items.nth(index)
                    try:
                        if not item.is_visible():
                            continue
                        text = (item.inner_text() or "").strip()
                    except Exception:
                        continue
                    if text:
                        found.append(text)
        return found

    def screenshot(self, path: Path | str, *, full_page: bool = True) -> Path:
        """截图存盘，返回路径。"""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(target), full_page=full_page)
        return target

    def click_visible(self, selector: Selector) -> None:
        """点第一个**看得见**的匹配元素。

        **为什么不能直接用 click()**：页面常把同一份 DOM 渲染两遍
        （一份藏在折叠面板里），`click()` 拿 `.first` 可能是看不见的那份，
        于是干等超时。挨个试，碰到的第一个看得见的就点它。
        """
        candidates = _as_list(selector)
        for candidate in candidates:
            for frame in self._frames():
                try:
                    locator = frame.locator(candidate)
                    count = locator.count()
                except Exception:
                    continue
                for index in range(count):
                    item = locator.nth(index)
                    try:
                        if not item.is_visible():
                            continue
                        item.click(timeout=self.timeout_ms)
                        return
                    except Exception:
                        continue
        raise self._fail(
            f"页面上没有**看得见**的元素可以点：{', '.join(candidates)}",
            candidates, "click-visible")

    def hover(self, selector: Selector) -> None:
        """悬停在某个元素上。

        **为什么需要**：视频号助手左边的导航默认是收起来的，
        子菜单要 hover 父项才展开——不 hover 就点不到「视频」。
        """
        candidates = _as_list(selector)
        for candidate in candidates:
            for frame in self._frames():
                try:
                    locator = frame.locator(candidate)
                    if locator.count() == 0:
                        continue
                    locator.first.hover(timeout=self.timeout_ms)
                    return
                except Exception:
                    continue
        raise self._fail(
            f"页面上找不到可以悬停的元素：{', '.join(candidates)}",
            candidates, "hover")

    def clipboard_text(self) -> str:
        """读剪贴板里的文字。

        **要先授权**：页面上下文得拿到 `clipboard-read` 权限，
        否则读出来是空的（不是报错）。
        """
        try:
            value = self.page.evaluate("() => navigator.clipboard.readText()")
        except Exception as error:
            raise self._fail(f"读剪贴板失败：{error}", [], "clipboard")
        return (value or "").strip()
