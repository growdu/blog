"""playwright 的导入入口——把「没装」变成一句能照着做的修复提示。

**为什么单独一个模块。** 整仓不是每台机器都装了浏览器：出片的机器只需要
ffmpeg 和字体，发帖的机器才需要 Chromium。如果在 `session.py` 顶部直接
`import playwright`，那么在一台没装 playwright 的机器上，
连 `python -m browser.cli doctor`（专门用来告诉用户缺什么）自己都会
ImportError 崩掉——问诊的科室先倒了。

所以这里把导入包起来，失败时抛一个带修复命令的异常。
"""

from __future__ import annotations


class BrowserUnavailable(RuntimeError):
    """playwright 不可用。消息里必须写清楚怎么补。"""


INSTALL_HINT = (
    "装它：\n"
    "  pip install -r browser/requirements.txt\n"
    "  python3 -m playwright install chromium        # 下载浏览器\n"
    "  python3 -m playwright install --with-deps chromium   # Linux 上还要补系统依赖（要 root）"
)


def import_playwright():
    """返回 `playwright.sync_api.sync_playwright`，装不上就抛 BrowserUnavailable。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:  # pragma: no cover - 取决于机器上装没装
        raise BrowserUnavailable(
            "没装 playwright。\n" + INSTALL_HINT
        ) from error
    return sync_playwright


def is_installed() -> bool:
    """playwright 包在不在。doctor 用它，不抛异常。"""
    try:
        import_playwright()
    except BrowserUnavailable:
        return False
    return True


def installed_version() -> str | None:
    """playwright 的版本号；没装返回 None。"""
    try:
        from importlib.metadata import version
    except ImportError:  # pragma: no cover - Python 3.8+
        return None
    try:
        return version("playwright")
    except Exception:
        return None
