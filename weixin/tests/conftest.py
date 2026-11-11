import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "weixin") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "weixin"))

SOURCE_POSTS = REPO_ROOT / "source" / "_posts"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def source_posts() -> Path:
    return SOURCE_POSTS
