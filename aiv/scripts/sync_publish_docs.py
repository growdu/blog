#!/usr/bin/env python3
"""把要发到博客的文档同步一份到 docs/life/aiv/。

`aiv/` 是仓库根级模块（与 `weixin/` 同级），整个目录不在 `docs/` 下面，
而 `sync-hexo.py` 只扫 `docs/`——所以要发布的文档必须在 `docs/life/aiv/`
留一份，否则那些规范页面会从 growdu.cn 上消失。

这里是「哪些文档要发布」的唯一真相：

- 专题页 + 三篇规范 + 各模块 README：面向读者的内容，继续发
- 不含 `pipeline/` 下的内部设计、实施计划与测试夹具：
  那是工程内部产物，不是文章。尤其是 `persona_script_bad.md`
  ——它是故意写坏的测试样本，绝不能发到公网上。

改完 `aiv/` 里的文档后跑一次：

    python3 aiv/scripts/sync_publish_docs.py

`pipeline/tests/test_publish_copy.py` 盯着两份是否一致，漂了会红。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

AIV_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AIV_ROOT.parent
PUBLISH_DIR = REPO_ROOT / "docs" / "life" / "aiv"

# 要在 docs/life/aiv/ 留一份的文档（相对 aiv/）
PUBLISH_DOCS = (
    "index.md",
    "人格规范.md",
    "形象与音色规范.md",
    "背景音乐规范.md",
    "brand/README.md",
    "brand/scripts/README.md",
    "character/README.md",
    "music/README.md",
    "voice/README.md",
)


def copy_all() -> list[str]:
    """把白名单里的文档复制到发布目录，返回复制了哪些。"""
    copied: list[str] = []
    for rel in PUBLISH_DOCS:
        src = AIV_ROOT / rel
        if not src.is_file():
            raise SystemExit(f"缺少文档：{src}")
        dst = PUBLISH_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)
    return copied


if __name__ == "__main__":
    done = copy_all()
    for rel in done:
        print(f"已同步 → docs/life/aiv/{rel}")
    print(f"共 {len(done)} 篇")
    sys.exit(0)
