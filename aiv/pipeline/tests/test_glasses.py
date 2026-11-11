"""眼镜相关测试。

两条线：

1. **规格与生成脚本同步**——规范里写的眼镜（深藏蓝 #2B4C7E 方形细边框、
   镜片透明），生成脚本的 prompt 里必须写的是同一件事。规范和 prompt
   漂移了，下一次重生成就会得到一只没戴眼镜或戴错色的小象。

2. **本机素材确实戴了眼镜**——不是看 prompt，是看像素：脸的区域里得有
   深藏蓝的方框眼镜。
"""
import importlib.util
import sys

import numpy as np
import pytest

from pyv import character


def _load(name: str, relative: str):
    """加载 character/scripts/ 下的脚本（不在 pipeline 包内，按路径载入）。"""
    path = character.AIV_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # 必须先注册进 sys.modules：模块里有 dataclass，dataclass 机制要回查
    # sys.modules[cls.__module__]
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _add_glasses():
    return _load("add_glasses", "character/scripts/add_glasses.py")


def _generate_character():
    return _load("generate_character", "character/scripts/generate_character.py")


# ---------------------------------------------------------------- 规格同步

def test_spec_declares_the_glasses():
    """规范 §1.1 必须把眼镜写进配饰。"""
    spec = (character.AIV_ROOT / "形象与音色规范.md").read_text(encoding="utf-8")
    assert "眼镜" in spec
    assert "2B4C7E" in spec
    # 方形 + 镜片透明，两个要点都要在
    assert "方形" in spec
    assert "透明" in spec


def test_generation_prompt_uses_the_specified_glasses():
    """生成 prompt 里的眼镜，必须和规范是同一副（颜色码 + 方形 + 透明）。"""
    glasses = _add_glasses()
    prompt = glasses.build_prompt()
    assert glasses.GLASSES_COLOR in prompt
    assert "方形" in prompt
    assert "透明" in prompt
    # 不许在镜框镜腿上贴白牌——模型的老毛病
    assert "不要出现任何白色标签" in prompt


def test_character_generation_prompt_uses_the_specified_glasses():
    """从原型全量重生成的 prompt，也得戴上同一副眼镜。"""
    glasses = _add_glasses()
    generator = _generate_character()
    for prompt in (generator.CHARACTER_PROMPT, generator.POSE_PROMPT):
        assert glasses.GLASSES_COLOR in prompt
        assert "眼镜" in prompt


def test_cleanup_prompt_targets_the_glasses_nameplate():
    """擦镜框杂物的 prompt 得说清楚擦什么。"""
    glasses = _add_glasses()
    assert "白色小铭牌" in glasses.CLEANUP_PROMPT
    assert "白色小铭牌" in glasses.CLEANUP_SHEET_PROMPT


# ---------------------------------------------------------------- 像素验收

# 镜框色 #2B4C7E = (43, 76, 126)。
# 判据要卡得够死：小象的**虹膜也是蓝色**（约 #4A8FC0）、耳朵内壁与阴影是
# 蓝灰色。只按「暗 + 偏蓝」去筛，虹膜和阴影会混进来，测不出眼镜。
# 所以用「够暗 + 蓝红差够大」：虹膜亮、蓝红差也没这么大；阴影则是灰的，
# 蓝红差不够。
NAVY_MAX_RED = 95           # 镜框最亮处也不超过这个红通道
NAVY_MIN_BLUE_GAP = 70      # 蓝通道要比红通道高这么多，才算深藏蓝而不是灰


def _subject_box(rgb: np.ndarray, alpha: np.ndarray | None):
    """主体包围盒（透明底按 alpha；白底按「不是白」）。"""
    if alpha is not None and alpha.min() < 250:
        mask = alpha > 8
    else:
        mask = ~((rgb[..., 0] > 245) & (rgb[..., 1] > 245) & (rgb[..., 2] > 245))
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    if rows.size == 0 or cols.size == 0:
        return None
    return int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1


def _navy(rgb: np.ndarray) -> np.ndarray:
    """深藏蓝镜框的像素。"""
    r = rgb[..., 0].astype(int)
    b = rgb[..., 2].astype(int)
    return (r < NAVY_MAX_RED) & ((b - r) >= NAVY_MIN_BLUE_GAP)


def _longest_run(row: np.ndarray) -> int:
    """一行里最长的连续 True 段。"""
    idx = np.flatnonzero(row)
    if idx.size == 0:
        return 0
    best = 0
    start = 0
    for end in list(np.flatnonzero(np.diff(idx) > 1)) + [idx.size - 1]:
        best = max(best, int(idx[end]) - int(idx[start]) + 1)
        start = end + 1
    return best


def _face_band(box, height: int):
    """脸所在的那一段行：主体上部 18% ~ 42%。

    眼镜在眼睛上；这个区间的上方是头顶呆毛，下方是耳机与马甲。
    """
    x0, y0, x1, y1 = box
    subject_h = y1 - y0
    return int(y0 + subject_h * 0.18), int(y0 + subject_h * 0.42)


@pytest.mark.parametrize("relative", [
    "character/growdu_character_2k_nobg.png",
    "brand/assets/growdu_pose_thumbsup_nobg.png",
    "brand/assets/growdu_pose_wave_nobg.png",
])
def test_real_assets_wear_navy_square_glasses(relative):
    """本机素材：小象脸上得有深藏蓝的方框眼镜。

    判据不是「脸里有深藏蓝」——眉毛也是深色的；而是：
    - 眼镜框是**横向长条**（每片镜片上下都有边），所以脸区里要能找到
      若干行「横着走很长一段」的深藏蓝；
    - 框有**高度**，不是一根线；
    - 两片镜片横跨整张脸，深藏蓝的横向跨度要够宽。
    """
    from PIL import Image

    path = character.AIV_ROOT / relative
    if not path.exists():
        pytest.skip("素材不在本机，跳过")

    image = Image.open(path).convert("RGBA")
    arr = np.array(image)
    rgb = arr[..., :3]
    alpha = arr[..., 3]
    box = _subject_box(rgb, alpha)
    assert box is not None, f"{relative}：找不到主体"
    x0, y0, x1, y1 = box
    subject_w = x1 - x0
    subject_h = y1 - y0

    top, bottom = _face_band(box, subject_h)
    navy = _navy(rgb)[top:bottom]
    assert navy.sum() > 0, f"{relative}：脸区里没有深藏蓝像素，眼镜没戴上"

    # 关键判据：镜框是**横着走的长条**（镜片的上沿 / 下沿），
    # 虹膜和阴影都是圆疙瘩，产生不出这么长的连续段。
    #
    # 实测（2048 画布的主体宽）：
    #   戴眼镜的主形象   最长横段 ≈ 12.6% 主体宽（挥手姿态最窄，约 7.2%）
    #   没戴眼镜的旧素材 最长横段 ≤  3.4% 主体宽
    # 所以 6% 是安全的分界线：旧素材最高才 3.4%，新素材最低 7.2%。
    longest = max((_longest_run(row) for row in navy), default=0)
    assert longest >= subject_w * 0.06, (
        f"{relative}：脸区里没有横跨的深藏蓝镜框（最长 {longest}px，"
        f"主体宽 {subject_w}px，不到 6%）"
    )

    # 框要有高度：不是一根线
    navy_rows = int(navy.any(axis=1).sum())
    assert navy_rows >= subject_h * 0.03, (
        f"{relative}：深藏蓝只有 {navy_rows} 行，不像镜框"
    )
