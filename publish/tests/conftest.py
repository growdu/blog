import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# 仓库根：让 publish/tests 下的测试能按仓库路径定位资源
# （master 上 video-publish 的能力声明测试用它算 CAPABILITIES 目录）。
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# publish/ 目录：publishkit 是挂在 publish/ 下的包（publish/ 本身不是包），
# 契约层的测试用 `import publishkit` 拿到它。
if str(REPO_ROOT / "publish") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "publish"))
