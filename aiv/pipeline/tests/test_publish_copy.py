"""发布副本的守卫：docs/life/aiv/ 下的文档必须与 aiv/ 正本逐字节一致。

`aiv/` 在仓库根，不在 `docs/` 下面，而 `sync-hexo.py` 只扫 `docs/`——
所以博客上那几篇规范文档，实际发布出去的是 `docs/life/aiv/` 里的副本。

两份一旦漂移，线上内容就会和仓库里的规范对不上，而且没人会发现：
构建照常通过，测试照常全绿，只有读者看到的是旧版本。
"""
import importlib.util
import re
from pathlib import Path

from pyv import character

SCRIPT = character.AIV_ROOT / "scripts" / "sync_publish_docs.py"
PUBLISH_ROOT = character.REPO_ROOT / "docs" / "life" / "aiv"

# `sync-hexo.py` 重写站内相对链接用的正则（那边一个字都不能改，只能守自己）
LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")


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
        # 隐藏文件不发布——sync-hexo.py 也会跳过它们（.DS_Store 之类）
        if any(part.startswith('.') for part in path.relative_to(PUBLISH_ROOT).parts):
            continue
        rel = path.relative_to(PUBLISH_ROOT).as_posix()
        assert rel in allowed, f"{rel} 不该出现在发布目录里"


def test_published_docs_have_no_cross_paragraph_link_matches():
    """正文里不许出现会被链接重写误匹配的方括号。

    `sync-hexo.py` 用 `(?<!!)\\[([^\\]]*)\\]\\(([^)]+)\\)` 重写相对链接，
    它不认代码块：正文里任何**不成对的 `[`**（比如数学区间写法
    `` `[s, s+D)` ``）都会让它一路吃到后面某个 `](...)`，
    把中间整段包成一个链接——markdown 源码看着没变，渲染出来却是
    上千字的巨型蓝色链接。

    这条规则盯的是发布目录里的 AIV 文档：它们会被 `sync-hexo.py`
    重写链接，所以踩到就会直接出现在线上。
    """
    offenders = []
    for path in sorted(PUBLISH_ROOT.rglob("*.md")):
        content = path.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(content):
            text = match.group(1)
            if "\n" in text:
                line = content[: match.start()].count("\n") + 1
                offenders.append(
                    f"{path.relative_to(PUBLISH_ROOT).as_posix()}:{line} "
                    f"吞掉 {len(text)} 字 → {match.group(2)}"
                )
    assert not offenders, "以下位置有跨段误匹配（把方括号区间写法改掉）：\n" + \
        "\n".join(offenders)

