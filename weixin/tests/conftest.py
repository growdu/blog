import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "weixin") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "weixin"))

SOURCE_POSTS = REPO_ROOT / "source" / "_posts"


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch):
    """Keep the developer's own credentials out of every test.

    A real ``WX_APPID`` in the developer's shell, or a real
    ``weixin/secrets.json``, must never change what a test does -- and
    must never be sent to a test's fake server.  Tests that need
    credentials set their own.
    """
    monkeypatch.delenv("WX_APPID", raising=False)
    monkeypatch.delenv("WX_APPSECRET", raising=False)
    monkeypatch.delenv("WX_SOURCE_URL", raising=False)
    monkeypatch.delenv("WX_COVER", raising=False)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def source_posts() -> Path:
    return SOURCE_POSTS
