import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "toutiao") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "toutiao"))

SOURCE_POSTS = REPO_ROOT / "source" / "_posts"
CAPABILITIES = REPO_ROOT / "publish" / "capabilities"


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch):
    """Keep the developer's own credentials out of every test.

    A real ``TT_CLIENT_ID`` in the developer's shell, or a real
    ``toutiao/secrets.json``, must never change what a test does -- and
    must never be sent to a test's fake server.  Tests that need
    credentials set their own.
    """
    monkeypatch.delenv("TT_CLIENT_ID", raising=False)
    monkeypatch.delenv("TT_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("TT_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TT_SOURCE_URL", raising=False)
    monkeypatch.delenv("TT_NOTIFY", raising=False)
    monkeypatch.delenv("TT_NOTIFY_KEY", raising=False)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def source_posts() -> Path:
    return SOURCE_POSTS


@pytest.fixture(scope="session")
def capabilities() -> Path:
    return CAPABILITIES
