"""浏览器会话：持久化 profile、远程调试端口、以及「挂到已经在跑的浏览器上」。"""

import socket
from pathlib import Path

import pytest

from browser.session import BrowserSession, SessionConfig

BROWSER_ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    """找一个空闲端口。"""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_the_profile_dir_can_be_overridden_by_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("BROWSER_PROFILE_DIR", str(tmp_path / "elsewhere"))
    from browser.session import default_profile_dir

    assert default_profile_dir() == (tmp_path / "elsewhere").resolve()


def test_a_script_can_attach_to_a_browser_that_is_already_running(tmp_path):
    """挂上去的脚本能驱动那个浏览器，而且**关不掉它**。

    **为什么需要这个**：视频号助手的登录态很脆——授权后能用一阵就被踢。
    每个脚本都自己开浏览器，就得反复重新授权；改一行代码重启脚本，
    也可能把登录态一起作废。

    所以浏览器起一次（带 --remote-debugging-port），脚本用 CDP 挂上去。

    挂在**另一个进程**上测：Playwright 的同步 API 一个进程只能有一个实例，
    而真实用法本来就是「另起一个脚本挂上去」。
    """
    import subprocess
    import sys

    port = _free_port()
    owner = BrowserSession(SessionConfig.build(
        profile_dir=tmp_path / "profile", headless=True,
        remote_debugging_port=port))

    with owner:
        owner.page.goto("data:text/html,<h1 id='x'>hello</h1>")

        code = (
            "import sys\n"
            f"sys.path.insert(0, {str(BROWSER_ROOT)!r})\n"
            "from browser.session import BrowserSession\n"
            f"s = BrowserSession.attach('http://127.0.0.1:{port}')\n"
            "print(s.page.inner_text('#x'))\n"
            "s.close()\n"
        )
        done = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, timeout=90)

        assert done.returncode == 0, done.stderr
        assert "hello" in done.stdout
        # 挂上来的那个脚本退出了，浏览器还活着——东西是常驻的，不是它的
        assert owner.page.inner_text("#x") == "hello"


def test_attaching_to_a_browser_that_is_not_there_says_so():
    with pytest.raises(Exception):
        BrowserSession.attach(f"http://127.0.0.1:{_free_port()}")
