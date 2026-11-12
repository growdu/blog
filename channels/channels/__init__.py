"""视频号 adapter。

视频号**没有面向普通创作者的公开发布接口**，所以这一档是 `manual`：
自动出包（成片 + 封面 + 文案 + 清单），人工点发布。

本包与 `bilibili/` 平级、互不引用，也不 import 契约层或 `weixin/` 的包。

`pyv` 住在 `aiv/pipeline/` 下面，没有装成 wheel，所以这里把它挂上 `sys.path`——
adapter 只**读** `pyv.epmeta` 与 `pyv.preflight`，不修改 aiv 侧的任何东西。
"""
from __future__ import annotations

import sys
from pathlib import Path

# channels/channels/__init__.py → parents[2] 是仓库根
REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_DIR = REPO_ROOT / "aiv" / "pipeline"

if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))
