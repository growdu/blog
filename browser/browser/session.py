"""浏览器会话：把「扫码登录一次」这件事活到以后每一次。

**为什么用持久化 profile，不用 storage_state。**
`storage_state` 是「导出一次、导入一次」的一对文件，得有人负责同步；
持久化 profile 就是一个浏览器用户目录，跟人自己用浏览器登录一次
是同一个心智模型——登录一次，之后每次跑都带着这份登录态。
视频号助手是微信扫码登录，扫码这件事本来就必须在真实窗口里完成，
持久化 profile 正好承接这个窗口。

**profile 目录不进版本库。** 里面是 cookie 与 localStorage，
等同于凭据（契约 §7.5：token 与 secret 永不入库）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from browser import pw

# 默认放在包目录旁边的 profile/，由 browser/.gitignore 挡掉。
DEFAULT_PROFILE_DIR = Path(__file__).resolve().parents[1] / "profile"

# 换机器、换用户时可以指到别处（Linux 上更常见的做法是放 ~/.config/blog-browser）。
PROFILE_ENV = "BROWSER_PROFILE_DIR"


def default_profile_dir() -> Path:
    """profile 目录：优先看环境变量，其次用包旁边的 profile/。"""
    override = os.environ.get(PROFILE_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return DEFAULT_PROFILE_DIR


@dataclass
class SessionConfig:
    """一次浏览器会话的配置。"""

    profile_dir: Path
    headless: bool = False
    slow_mo: int = 0
    viewport_width: int = 1440
    viewport_height: int = 960
    locale: str = "zh-CN"
    timezone: str = "Asia/Shanghai"

    @classmethod
    def build(cls, profile_dir=None, headless=False, slow_mo=0) -> "SessionConfig":
        return cls(
            profile_dir=Path(profile_dir).expanduser().resolve() if profile_dir
            else default_profile_dir(),
            headless=headless,
            slow_mo=slow_mo,
        )


class BrowserSession:
    """持久化 profile 的 Chromium 会话。

    用法：

        with BrowserSession(SessionConfig.build()) as session:
            session.page.goto("https://example.com")
    """

    def __init__(self, config: SessionConfig | None = None) -> None:
        self.config = config or SessionConfig.build()
        self._playwright = None
        self._context = None
        self._page = None

    # -- 生命周期 ------------------------------------------------------------

    def start(self) -> "BrowserSession":
        sync_playwright = pw.import_playwright()
        self.config.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.config.profile_dir),
            headless=self.config.headless,
            slow_mo=self.config.slow_mo,
            locale=self.config.locale,
            timezone_id=self.config.timezone,
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
        )
        # 持久化上下文自带一个空白页；用它，不额外开页。
        self._page = (self._context.pages or [None])[0]
        if self._page is None:
            self._page = self._context.new_page()
        return self

    def close(self) -> None:
        if self._context is not None:
            self._context.close()
            self._context = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        self._page = None

    def __enter__(self) -> "BrowserSession":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # -- 访问器 --------------------------------------------------------------

    @property
    def context(self):
        if self._context is None:
            raise RuntimeError("会话还没启动，先用 with BrowserSession(...) 或调用 start()")
        return self._context

    @property
    def page(self):
        if self._page is None:
            raise RuntimeError("会话还没启动，先用 with BrowserSession(...) 或调用 start()")
        return self._page


def login_state_present(profile_dir: Path | None = None) -> bool:
    """这个 profile 里有没有留过登录态。

    **这是启发式判断，不是登录验证。** Chromium 把 cookie 放在
    profile 目录下的 `Default/Cookies`（Linux 上路径一样）。文件存在
    只说明「登录过」，不说明「现在还登录着」——token 过期了文件照样在。
    真正的登录验证要看页面：见 flows/channels.py 的 `is_logged_in`。
    """
    root = Path(profile_dir) if profile_dir else default_profile_dir()
    return (root / "Default" / "Cookies").is_file() or (root / "Cookies").is_file()
