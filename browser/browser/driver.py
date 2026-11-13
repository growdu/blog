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

    def _locator(self, selector: Selector):
        """返回第一个能解析到的 locator；一个都解析不到就抛 ActionError。"""
        candidates = _as_list(selector)
        if not candidates:
            raise ActionError("没给选择器")
        last_error = None
        for candidate in candidates:
            try:
                locator = self.page.locator(candidate)
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
            try:
                self.page.locator(candidate).first.wait_for(
                    state=state, timeout=limit)
                return
            except Exception:
                continue
        raise self._fail(
            f"等了 {limit} ms，元素没等到「{state}」状态", candidates, "wait")

    def exists(self, selector: Selector) -> bool:
        """元素在不在（不抛异常）。"""
        for candidate in _as_list(selector):
            try:
                if self.page.locator(candidate).count() > 0:
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
        try:
            locator = self.page.locator(candidates[0])
            if locator.count() == 0:
                # 候选挨个试
                for candidate in candidates[1:]:
                    alt = self.page.locator(candidate)
                    if alt.count() > 0:
                        locator = alt
                        break
                else:
                    raise self._fail("找不到文件上传框", candidates, "upload-missing")
            locator.set_input_files(str(target))
        except ActionError:
            raise
        except Exception as error:
            raise self._fail(f"上传失败：{error}", candidates, "upload")

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

    def screenshot(self, path: Path | str, *, full_page: bool = True) -> Path:
        """截图存盘，返回路径。"""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(target), full_page=full_page)
        return target
