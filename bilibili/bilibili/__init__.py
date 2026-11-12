"""B站 adapter。

两档：现在跑的是 `manual`（出包 + 人工上传），
`ARC_BASE` 权限开通后同一套代码改一档到 `api_publish`（直接投稿）。

本包与 `channels/` 平级、互不引用，也不 import 契约层或 `weixin/` 的包。
只读 `aiv/publish/<EP>.json`（这一期怎么自我介绍）与
`publish/capabilities/bilibili.toml`（平台认什么）。

`pyv` 住在 `aiv/pipeline/` 下面，没有装成 wheel，所以这里把它挂上 `sys.path`——
adapter 只**读** `pyv.epmeta` 与 `pyv.preflight`，不修改 aiv 侧的任何东西。
不挂的话，`python3 -m bilibili.cli` 会直接报
`ModuleNotFoundError: No module named 'pyv'`——规格里写着的调用方式根本用不了。
"""
from __future__ import annotations

import sys
from pathlib import Path

# bilibili/bilibili/__init__.py → parents[2] 是仓库根
REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_DIR = REPO_ROOT / "aiv" / "pipeline"

if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))
