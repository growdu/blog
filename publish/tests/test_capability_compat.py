"""能力模型与 weixin/ 常量的一致性（规格 §5.3）。

能力模型的 ``limits`` 与 ``weixin/wechat/posts.py`` 的 ``TITLE_LIMIT`` /
``BODY_LIMIT`` / ``DIGEST_LIMIT`` 描述的是同一批数字，会漂移。

**解法不是改 weixin/，而是在契约层加这条兼容性测试**（规格 §5.3）——
它**只读** weixin/，不改它一个字节；任一边漂移，测试立刻红。

今天它还 skip：``publish/capabilities/wechat.toml`` 还没进仓库——平台能力
声明分散在几个分支上（规格 §12）。那份文件落地的那一刻，这条测试开始生效。

> **落地那份文件的人请先看这里**：规格 §5 的示例里写的是 ``title_chars = 32``，
> 但 ``weixin/wechat/titles.py:36`` 的 ``TITLE_LIMIT`` 是 **64**（公众号编辑器的
> 真实上限）。规格 §5.3 自己那条断言（``== posts.TITLE_LIMIT``）与 §5 的示例
> TOML 是互相矛盾的——示例照抄进来，这条测试会立刻变红。取值以 weixin/ 的
> 常量为准。
"""

import sys
from pathlib import Path

import pytest

from publishkit import load_capability_file

REPO_ROOT = Path(__file__).resolve().parents[2]
WEIXIN_DIR = REPO_ROOT / "weixin"
CAPABILITIES_DIR = REPO_ROOT / "publish" / "capabilities"
WECHAT_CAPABILITY = CAPABILITIES_DIR / "wechat.toml"


def _wechat_posts():
    """Import ``wechat.posts`` without importing it at module level.

    weixin/ 正在被并行开发，它挪目录或改导入路径时本条自动 skip，
    不给别人的工作添麻烦。
    """
    if not WEIXIN_DIR.is_dir():
        return None
    if str(WEIXIN_DIR) not in sys.path:
        sys.path.insert(0, str(WEIXIN_DIR))
    try:
        from wechat import posts
    except Exception:  # pragma: no cover - weixin 那边在并行开发
        return None
    return posts


def test_wechat_limits_match_the_weixin_constants():
    posts = _wechat_posts()
    if posts is None:
        pytest.skip("weixin/ 不可用，跳过与 wechat.posts 的对照")

    if not WECHAT_CAPABILITY.is_file():
        pytest.skip(
            "publish/capabilities/wechat.toml 还没进仓库（平台能力声明分散在"
            "几个分支上，见规格 §12）——那份文件落地后本条开始生效"
        )

    cap = load_capability_file(WECHAT_CAPABILITY)

    assert cap.limits["title_chars"] == posts.TITLE_LIMIT
    assert cap.limits["body_chars"] == posts.BODY_LIMIT
    assert cap.limits["digest_chars"] == posts.DIGEST_LIMIT


def test_the_weixin_constants_are_readable_at_all():
    """对照的前提是三个常量都在。少了任何一个，这条对照就名存实亡。"""
    posts = _wechat_posts()
    if posts is None:
        pytest.skip("weixin/ 不可用")

    assert isinstance(posts.TITLE_LIMIT, int)
    assert isinstance(posts.BODY_LIMIT, int)
    assert isinstance(posts.DIGEST_LIMIT, int)
