"""发布副本的守卫：docs/life/aiv/ 下的文档必须与 aiv/ 正本逐字节一致。

`aiv/` 在仓库根，不在 `docs/` 下面，而 `sync-hexo.py` 只扫 `docs/`——
所以博客上那几篇规范文档，实际发布出去的是 `docs/life/aiv/` 里的副本。

两份一旦漂移，线上内容就会和仓库里的规范对不上，而且没人会发现：
构建照常通过，测试照常全绿，只有读者看到的是旧版本。
"""
import importlib.util
from pathlib import Path

from pyv import character

SCRIPT = character.AIV_ROOT / "scripts" / "sync_publish_docs.py"
PUBLISH_ROOT = character.REPO_ROOT / "docs" / "life" / "aiv"


def _module():
    spec = importlib.util.spec_from_file_location("sync_publish_docs", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_publish_copies_match_the_canonical_docs():
    """发布副本与正本必须一致。"""
    module = _module()
    assert module.PUBLISH_DOCS, "白名单不能为空"
    for rel in module.PUBLISH_DOCS:
        canonical = character.AIV_ROOT / rel
        published = PUBLISH_ROOT / rel
        assert canonical.is_file(), f"正本不存在：{canonical}"
        assert published.is_file(), f"发布副本缺失：{published}"
        assert published.read_bytes() == canonical.read_bytes(), (
            f"{rel} 的发布副本与正本不一致——改完 aiv/ 里的文档后，"
            f"要跑 python3 aiv/scripts/sync_publish_docs.py"
        )


def test_publish_dir_contains_only_whitelisted_docs():
    """发布目录里只该有白名单里的文档。

    工程内部产物（内部设计、实施计划、测试夹具）留在 aiv/ 里，
    不能被带进发布目录——`persona_script_bad.md` 是故意写坏的样本，
    发到公网上就是事故。
    """
    module = _module()
    allowed = set(module.PUBLISH_DOCS)
    assert PUBLISH_ROOT.is_dir(), PUBLISH_ROOT
    for path in sorted(PUBLISH_ROOT.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(PUBLISH_ROOT).as_posix()
        assert rel in allowed, f"{rel} 不该出现在发布目录里"
