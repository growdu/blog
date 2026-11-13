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
    # 开了这个端口，别人就能用 CDP 挂到这个浏览器上（见 BrowserSession.attach）。
    # 端口用 0 = 让系统随机挑一个空闲端口。
    remote_debugging_port: int | None = None

    @classmethod
    def build(cls, profile_dir=None, headless=False, slow_mo=0,
              remote_debugging_port=None) -> "SessionConfig":
        return cls(
            profile_dir=Path(profile_dir).expanduser().resolve() if profile_dir
            else default_profile_dir(),
            headless=headless,
            slow_mo=slow_mo,
            remote_debugging_port=remote_debugging_port,
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
        self._attached = False

    # -- 生命周期 ------------------------------------------------------------

    def start(self) -> "BrowserSession":
        sync_playwright = pw.import_playwright()
        self.config.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        args = []
        if self.config.remote_debugging_port is not None:
            args.append(f"--remote-debugging-port={self.config.remote_debugging_port}")
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
            args=args or None,
        )
        # 持久化上下文自带一个空白页；用它，不额外开页。
        self._page = (self._context.pages or [None])[0]
        if self._page is None:
            self._page = self._context.new_page()
        return self

    @classmethod
    def attach(cls, cdp_url: str = "http://127.0.0.1:9333") -> "BrowserSession":
        """挂到一个**已经在跑**的浏览器上。

        **为什么要有这个。** 视频号助手的登录态很脆（实测 2026-11-13：
        本机微信授权后能用一阵，过一会儿就被踢掉）。如果每个脚本都自己开
        浏览器，就得反复重新授权；更糟的是，改一行脚本代码就得把浏览器
        重启一遍，登录态可能当场作废。

        所以：**浏览器用 `--remote-debugging-port` 起一次，脚本用 CDP 挂上去。**
        脚本随便重启，浏览器一直开着，登录态一直在。

        挂上来的会话 `close()` **不会关掉浏览器**——那是别人的东西。
        """
        sync_playwright = pw.import_playwright()
        self = cls(SessionConfig.build())
        self._playwright = sync_playwright().start()
        browser = self._playwright.chromium.connect_over_cdp(cdp_url)
        contexts = browser.contexts
        if not contexts:
            raise RuntimeError(f"那个浏览器上还没有上下文：{cdp_url}")
        self._context = contexts[0]
        self._attached = True
        self._page = (self._context.pages or [None])[0]
        if self._page is None:
            self._page = self._context.new_page()
        return self

    def grant_clipboard(self, origin: str) -> bool:
        """允许读剪贴板（只对这一个站点）。

        取公开链接要靠「复制视频链接」把链接写进剪贴板、再读回来。
        不授权的话读出来是空的——**不报错**，所以更得主动授权。
        """
        try:
            self.context.grant_permissions(
                ["clipboard-read", "clipboard-write"], origin=origin)
            return True
        except Exception:
            return False

    def close(self) -> None:
        if self._context is not None:
            if self._attached:
                # 挂上来的浏览器是常驻的，**不能关**——只断开自己的连接。
                pass
            else:
                self._context.close()
            self._context = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        self._page = None

    def __enter__(self) -> "BrowserSession":
        # attach() 造出来的会话已经就绪了，别再 start() 一次——
        # Playwright 的同步 API 一个进程只能有一个实例，
        # 再 start 一次会直接报「inside the asyncio loop」。
        if self._page is not None:
            return self
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
