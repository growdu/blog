#!/usr/bin/env python3
"""生成品牌片用的小象姿态素材（点赞 / 挥手）。

产出：
  brand/assets/growdu_pose_thumbsup_nobg.png   小象 · 点赞姿态（2048²，透明底）
  brand/assets/growdu_pose_wave_nobg.png         小象 · 挥手姿态（2048²，透明底）

参考图是主形象 `character/growdu_character_2k.png`，prompt 只描述姿态差异，
角色设定（浅蓝灰皮肤 / 深藏蓝马甲 / 琥珀黄数据库图标 / 黑色头戴耳机 /
深藏蓝方形细边框眼镜）原样继承，不重新发明。

铭牌上不写任何字：模型写的中英文会乱码，文字一律由
`character/scripts/stamp_badge.py` 用真实字体盖上 `growdu`。

依赖 mcode-tools CLI（先加载 `mcode-tools-master` skill）。
每次运行都会消耗生成额度，重复执行前先确认是否真的需要重做。

用法：
  python3 scripts/generate_poses.py              # 两个姿态都生成
  python3 scripts/generate_poses.py --thumbsup  # 只生成点赞
  python3 scripts/generate_poses.py --wave
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRAND = HERE.parent
AIV = BRAND.parent
CHARACTER_SCRIPTS = AIV / "character" / "scripts"
sys.path.insert(0, str(CHARACTER_SCRIPTS))

from _mcode import call, download, upload          # noqa: E402
from add_glasses import GLASSES_COLOR, GLASSES_STYLE  # noqa: E402
from stamp_badge import stamp_badge                # noqa: E402

CHARACTER = AIV / "character" / "growdu_character_2k.png"
ASSETS = BRAND / "assets"

IDENTITY = f"""角色设定与图1逐项保持一致：
- 同样的浅蓝灰色皮肤、大眼长睫毛、粉色面颊、小巧象牙、头顶一撮呆毛
- 同样的深藏蓝 (#2B4C7E) 技术工装马甲、胸口同样的琥珀黄 (#F5A623) 圆柱数据库图标
- 同样的黑色头戴式耳机 + 麦克风臂
- 同样的{GLASSES_STYLE}眼镜，镜框深藏蓝 {GLASSES_COLOR}（与马甲同色），镜片完全透明
- 同样的产品级 3D 卡通渲染质感、柔和均匀棚拍光、无强反光"""

COMMON_TAIL = """画面要求：
- 纯白背景 (#FFFFFF)，主体居中，四周留出充足白边
- 胸口那块白色矩形铭牌保持**完全空白**，不要写任何文字、字母或符号
- 不要任何文字标签、边框、说明文字
- 干净的产品级 3D 卡通渲染质感"""

THUMBSUP_PROMPT = f"""以图1（3D 渲染的可爱小象角色）为唯一原型，生成这只小象的「点赞」姿态。

{IDENTITY}

姿态：
- 正面站立，身体微微侧转
- 一只手（画面右侧）抬起并竖起大拇指，做「点赞」手势；另一只手自然垂在身侧
- 头微微歪向另一侧，睁大眼睛开心地看镜头
- 全身完整入画，脚底完整可见

{COMMON_TAIL}"""

WAVE_PROMPT = f"""以图1（3D 渲染的可爱小象角色）为唯一原型，生成这只小象的「挥手」姿态。

{IDENTITY}

姿态：
- 正面站立，身体略微侧转
- 一只手（画面右侧）举起到肩膀高度，掌心朝向镜头、手掌张开，做「挥手」打招呼的姿势
- 头微微歪向举起的那只手，看着镜头，表情亲切
- 全身完整入画，脚底完整可见

{COMMON_TAIL}"""

POSES = {
    "thumbsup": (THUMBSUP_PROMPT, ASSETS / "growdu_pose_thumbsup_nobg.png"),
    "wave": (WAVE_PROMPT, ASSETS / "growdu_pose_wave_nobg.png"),
}


def generate(prompt: str, dest: Path) -> None:
    """生成姿态图 → 抠透明底 → 盖铭牌章。"""
    ref = upload(CHARACTER)
    res = call("connector__matrix__generate_image", {"requests": [{
        "prompt": prompt,
        "reference_images": [{"url": ref, "mime_type": "image/png"}],
        "aspect_ratio": "1:1", "area": "2K", "output_format": "png",
        "output_file": dest.name, "n": 1,
    }]})
    items = res.get("success_items") or []
    if not items:
        raise RuntimeError(f"生成失败：{res}")
    download(items[0]["node_id"], dest)
    print(f"  → {dest}")

    bg = call("connector__matrix__remove_image_background",
              {"image_url": upload(dest)})
    download(bg["node_id"], dest)
    print(f"  → {dest}（已抠透明底）")

    stamp_badge(dest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成品牌片用的小象姿态素材")
    parser.add_argument("--thumbsup", action="store_true", help="只生成点赞姿态")
    parser.add_argument("--wave", action="store_true", help="只生成挥手姿态")
    args = parser.parse_args(argv)

    if not CHARACTER.exists():
        print(f"缺少主形象：{CHARACTER}", file=sys.stderr)
        return 1

    wanted = []
    if args.thumbsup or not args.wave:
        wanted.append("thumbsup")
    if args.wave or not args.thumbsup:
        wanted.append("wave")
    for name in wanted:
        prompt, dest = POSES[name]
        print(f"生成 {name} …")
        generate(prompt, dest)
    print("完成。规范见 aiv/形象与音色规范.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
