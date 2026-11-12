import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "toutiao") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "toutiao"))

SOURCE_POSTS = REPO_ROOT / "source" / "_posts"
CAPABILITIES = REPO_ROOT / "publish" / "capabilities"

#: The directories inside the repository that the commands write into when
#: they are not told otherwise.  ``publish/outbox/`` holds tracked
#: snapshots; ``toutiao/out/`` holds the Phase 0 packages the pilot work
#: depends on.  A test that forgets one of the options writes here.
WRITABLE_IN_THE_REPOSITORY = (
    REPO_ROOT / "publish" / "outbox",
    REPO_ROOT / "toutiao" / "out",
)


@pytest.fixture(scope="session", autouse=True)
def the_repository_is_never_written_to():
    """No test may leave anything behind in the repository.

    The comparison is against the snapshot taken at the **start of the
    session**, not "before and after this test": the second kind cannot
    see what the previous test left behind, so a test that wrote into
    ``publish/outbox/`` was followed by a test that compared the
    repository against itself and reported everything was fine.
    """
    def snapshot():
        seen = {}
        for directory in WRITABLE_IN_THE_REPOSITORY:
            if directory.is_dir():
                seen[directory] = {p.name for p in directory.iterdir()}
            else:
                seen[directory] = set()
        return seen

    before = snapshot()
    yield
    after = snapshot()
    for directory, names in after.items():
        added = names - before[directory]
        assert not added, (
            "有测试往仓库的 {} 里写了东西：{}".format(
                directory.relative_to(REPO_ROOT), "、".join(sorted(added))
            )
        )


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
    # The scheduling layer's variables: they decide where the snapshot
    # goes, so a leftover one in the developer's shell would change what
    # a test writes.
    monkeypatch.delenv("PUBLISH_OUTBOX_DIR", raising=False)
    monkeypatch.delenv("PUBLISH_REPO", raising=False)
    monkeypatch.delenv("PUBLISH_STATE_DIR", raising=False)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def source_posts() -> Path:
    return SOURCE_POSTS


@pytest.fixture(scope="session")
def capabilities() -> Path:
    return CAPABILITIES
