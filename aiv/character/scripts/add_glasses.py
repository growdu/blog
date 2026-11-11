#!/usr/bin/env python3
"""给 Growdu 的 3D 卡通小象戴上一副深藏蓝方形眼镜。

规范（见 `aiv/形象与音色规范.md` §1.1）：配饰新增**深藏蓝 #2B4C7E
方形细边框眼镜**，镜片透明——小象是数据库内核讲解者，一副方框眼镜强化
「技术宅」气质，同时和深藏蓝马甲同色，视觉系统统一。

为什么必须用 AI 重生成，不能用代码贴上去：
3D 渲染的眼镜要有镜框厚度、高光、镜腿在耳朵处的遮挡关系、镜片在皮肤上的
微弱反光——这些是二维贴片做不出来的，贴上去一眼假。

所以做法是**以现有素材为参考图做图生图**：角色、姿态、光照、构图全部照抄，
只多一副眼镜。参考图选「素材自己」而不是「形象原型」，是为了把角色漂移
压到最小。

用法：
  python3 scripts/add_glasses.py                        # 批次：4 个素材全部重生成
  python3 scripts/add_glasses.py --promote              # 把 staging 结果覆盖到正式路径
  python3 scripts/add_glasses.py <src.png> <dst.png>    # 单张：给任意素材戴眼镜
  python3 scripts/add_glasses.py <src.png> <dst.png> --transparent

批次流程是 生成 → 目视验收 → promote：
  - 参考图来自 `aiv/_staging/_base/`（首次运行时从正式素材复制一份留底），
    所以 promote 之后再跑一次不会「眼镜叠眼镜」；
  - 生成结果先落在 `aiv/_staging/`，确认没问题再 promote 覆盖正式素材。

依赖 mcode-tools CLI（先加载 `mcode-tools-master` skill）。
每次运行都会消耗生成额度，重复执行前先确认是否真的需要重做。
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _mcode import call, download, upload  # noqa: E402
from stamp_badge import stamp_badge        # noqa: E402

HERE = Path(__file__).resolve().parent
AIV = HERE.parent.parent                     # aiv
STAGING = AIV / "_staging"

# 眼镜规格：改这里等于改规范，生成 prompt 与测试都引用它
GLASSES_COLOR = "#2B4C7E"
GLASSES_STYLE = "方形细边框"

# 批次清单：(相对 aiv 的素材路径, 是否透明底, 宽高比)
BATCH: tuple[tuple[str, bool, str], ...] = (
    ("character/growdu_character_2k.png", False, "1:1"),
    ("brand/assets/growdu_pose_thumbsup_nobg.png", True, "1:1"),
    ("brand/assets/growdu_pose_wave_nobg.png", True, "1:1"),
    ("character/growdu_pose_sheet.png", False, "16:9"),
)

# 白底主形象派生出透明底版：抠一次背景得到，不单独生成
DERIVED = ("character/growdu_character_2k_nobg.png",)
MAIN_WHITE = "character/growdu_character_2k.png"

_SINGLE_PROMPT = f"""以图1（3D 渲染的可爱小象角色）为唯一原型，生成**同一只小象**的新画面。

角色必须与图1逐项保持一致：
- 同一只小象：同样的浅蓝灰色皮肤、同样的大眼与长睫毛、同样的粉色面颊、同样的小巧象牙、同样的头顶呆毛
- 同样的深藏蓝 (#2B4C7E) 技术工装马甲、胸口同样的琥珀黄 (#F5A623) 圆柱数据库图标
- 同样的黑色头戴式耳机 + 麦克风臂
- 同样的姿态、表情、视角、镜头、构图、主体位置与大小
- 同样的柔和均匀棚拍光、同样的干净产品级 3D 卡通渲染质感、同样的纯白背景 (#FFFFFF)

唯一新增元素：
- 给小象戴上一副**{GLASSES_STYLE}眼镜**，镜框颜色为深藏蓝 {GLASSES_COLOR}（与马甲同色），
  框条纤细规整，方形镜片（带极小圆角）
- 镜片**完全透明**：能清楚看到两只大眼睛，不要镜片反光、不要镜片变色、不要墨镜遮眼
- 眼镜架在两只眼睛上，佩戴位置与角度自然，镜框总宽度与两只大眼睛的总跨度相称
- 镜腿从镜框两侧水平伸向两只耳朵

严禁：
- 镜框、镜腿上不要出现任何白色标签、铭牌、贴纸、文字或符号（胸口那块白色铭牌是唯一的白块）
- 除眼镜外任何元素都不得改动：不要改肤色、不要改马甲颜色、不要改数据库图标、不要改耳机、
  不要改表情、不要改姿态、不要改背景、不要加别的配饰、不要改体型比例
- 胸口那块白色矩形铭牌必须保持**完全空白**，不要写任何文字、字母或符号"""

_SHEET_PROMPT = f"""以图1（3D 渲染的可爱小象角色 6 姿态设定表）为唯一原型，生成**同一只小象**的新设定表。

整张表必须与图1逐项保持一致：
- 同样是 3 列 × 2 行、共 6 个姿态、纯白背景 (#FFFFFF)、均匀排布、姿态之间留清晰白间隔
- 每个姿态都是同一只小象：同样的浅蓝灰色皮肤、大眼长睫毛、粉色面颊、小巧象牙、头顶呆毛
- 同样的深藏蓝 (#2B4C7E) 工装马甲、胸口琥珀黄 (#F5A623) 圆柱数据库图标、同样的黑色头戴式耳机
- 每个姿态的胸口都别着同样一块**白色小铭牌**（横向长方形，保持空白纯白，不写任何文字）
- 同样的六个姿态内容（正面坐姿 / 右手指向 / 手托下巴思考 / 举数字 2 / 低头 / 摊手收束）
- 同样的光线、材质与产品级 3D 卡通渲染质感

唯一新增元素：
- 六个姿态的小象**全部戴上一副{GLASSES_STYLE}眼镜**，镜框颜色为深藏蓝 {GLASSES_COLOR}
  （与马甲同色），框条纤细规整，方形镜片带极小圆角
- 镜片**完全透明**：能清楚看到眼睛，不要镜片反光、不要变色、不要墨镜遮眼
- 眼镜在每个姿态里的佩戴位置与角度都自然，镜框总宽度与两只大眼睛的总跨度相称
- 镜腿从镜框两侧水平伸向两只耳朵
- 镜框、镜腿上不要出现任何白色标签、铭牌、贴纸、文字或符号（胸口那块白色铭牌是唯一的白块）

严禁：
- 除眼镜外任何元素都不得改动：不要改肤色、不要改马甲、不要改数据库图标、不要改耳机、
  不要改表情、不要改姿态内容、不要改排版、不要改背景、不要加别的配饰
- 每个姿态胸口那块白色矩形铭牌必须保持**完全空白**，不要写任何文字、字母或数字
- 不要任何文字标签、边框、说明文字"""


def build_prompt(sheet: bool = False) -> str:
    """眼镜化 prompt。sheet=True 用于 6 姿态设定表。"""
    return _SHEET_PROMPT if sheet else _SINGLE_PROMPT


# 擦镜框杂物的补丁 prompt。
#
# 模型有个反复出现的毛病：戴上方形眼镜后，会在镜框或镜腿上贴一小块
# 白色铭牌（实测写着 growdu）。它既是视觉噪点，又会被铭牌检测当成
# 真正的铭牌——它四周全是镜框色，「马甲占比」比胸口那块真铭牌还高。
#
# 用模型做局部修补，而不是用代码涂抹：代码抹出来的色块是平的，一眼假；
# 模型能按周围的镜框与皮肤重新长出边缘。
CLEANUP_PROMPT = """以图1（3D 渲染的可爱小象，戴着深藏蓝方形细边框眼镜）为唯一原型，生成同一张图。

这是一次**局部修补**，只做一件事：
- 检查眼镜的镜框与镜腿。如果镜框或镜腿上贴着一小块**白色小铭牌**
  （白色小矩形，上面可能有几个模糊的深色字母），把它**彻底擦掉**，
  擦掉后该处恢复成原本的样子：镜框是连续平整的深藏蓝色，镜框下沿与
  镜片内是角色的浅蓝灰色皮肤，眉毛与睫毛保持原样，痕迹要完全看不出来。
- 如果镜框和镜腿上本来就没有任何白色小牌子，就**原样保持**，不要改动任何地方。

除这一处修补之外，整张图必须与图1保持一致：
- 同一只小象：同样的浅蓝灰色皮肤、大眼长睫毛、粉色面颊、小巧象牙、头顶呆毛
- 同样的深藏蓝 (#2B4C7E) 工装马甲、胸口同样的琥珀黄 (#F5A623) 圆柱数据库图标
- 同样的黑色头戴式耳机 + 麦克风臂、胸口那块白色小铭牌
- 同样的眼镜造型：深藏蓝方形细边框、透明镜片、镜腿
- 同样的姿态、表情、视角、镜头、构图、主体位置与大小
- 同样的柔和均匀棚拍光、同样的纯白背景 (#FFFFFF)

严禁：不要重新设计角色、不要改眼镜造型、不要在镜框或镜腿上留下任何白色标签或贴纸、不要改任何颜色。"""

CLEANUP_SHEET_PROMPT = """以图1（3D 渲染的可爱小象 6 姿态设定表，六个小象都戴着深藏蓝方形细边框眼镜）为唯一原型，生成同一张设定表。

这是一次**局部修补**，只做一件事：
- 检查六个姿态里每一副眼镜的镜框与镜腿。凡是镜框或镜腿上贴着一小块
  **白色小铭牌**（白色小矩形，上面可能有几个模糊的深色字母），都把它**彻底擦掉**，
  擦掉后该处恢复成原本的样子：镜框是连续平整的深藏蓝色，镜片内是角色的浅蓝灰色皮肤，
  眉毛与睫毛保持原样，痕迹要完全看不出来。
- 如果镜框和镜腿上本来就没有任何白色小牌子，就**原样保持**，不要改动任何地方。

除这一处修补之外，整张表必须与图1保持一致：
- 同样是 3 列 × 2 行共 6 个姿态、纯白背景 (#FFFFFF)、同样的排布与白间隔
- 同样的浅蓝灰色皮肤、大眼长睫毛、粉色面颊、小巧象牙、头顶呆毛
- 同样的深藏蓝 (#2B4C7E) 工装马甲、琥珀黄 (#F5A623) 圆柱数据库图标、黑色头戴式耳机
- 同样的六个姿态内容、表情、光线与产品级 3D 卡通渲染质感

严禁：不要重新设计角色、不要改眼镜造型、不要在镜框或镜腿上留下任何白色标签或贴纸、不要改排版、不要加任何文字。"""


def cleanup_glasses(src: Path, dst: Path, *, sheet: bool = False,
                    aspect_ratio: str = "1:1", area: str = "2K") -> Path:
    """局部修补：擦掉镜框上的白色小铭牌。"""
    mime = "image/png" if src.suffix.lower() == ".png" else "image/jpeg"
    ref = upload(src)
    res = call("connector__matrix__generate_image", {"requests": [{
        "prompt": CLEANUP_SHEET_PROMPT if sheet else CLEANUP_PROMPT,
        "reference_images": [{"url": ref, "mime_type": mime}],
        "aspect_ratio": aspect_ratio, "area": area,
        "output_format": "png", "output_file": dst.name, "n": 1,
    }]})
    items = res.get("success_items") or []
    if not items:
        raise RuntimeError(f"修补失败：{res}")
    download(items[0]["node_id"], dst)
    print(f"  → {dst}（已擦镜框杂物）")
    return dst


def generate_glasses(src: Path, dst: Path, *, transparent: bool = False,
                     aspect_ratio: str = "1:1", area: str = "2K",
                     sheet: bool = False) -> Path:
    """以 src 为参考图生成戴眼镜版本，写到 dst。

    transparent=True 时再走一次抠背景，保证输出带 alpha。
    """
    mime = "image/png" if src.suffix.lower() == ".png" else "image/jpeg"
    ref = upload(src)
    res = call("connector__matrix__generate_image", {"requests": [{
        "prompt": build_prompt(sheet),
        "reference_images": [{"url": ref, "mime_type": mime}],
        "aspect_ratio": aspect_ratio, "area": area,
        "output_format": "png", "output_file": dst.name, "n": 1,
    }]})
    items = res.get("success_items") or []
    if not items:
        raise RuntimeError(f"生成失败：{res}")
    download(items[0]["node_id"], dst)
    print(f"  → {dst}")

    if transparent:
        bg = call("connector__matrix__remove_image_background",
                  {"image_url": upload(dst)})
        download(bg["node_id"], dst)
        print(f"  → {dst}（已抠透明底）")
    return dst


def stamp(dst: Path) -> None:
    """给铭牌盖上 growdu（真实字体渲染，模型写的字一律不算数）。"""
    if stamp_badge(dst) is None:
        print(f"  ! {dst.name}：没找到铭牌，铭牌文字未盖章", file=sys.stderr)


def _cut_background(src: Path, dst: Path) -> None:
    """抠一次透明底，落到 dst。"""
    res = call("connector__matrix__remove_image_background",
               {"image_url": upload(src)})
    download(res["node_id"], dst)
    print(f"  → {dst}（已抠透明底）")


def _flatten_white(src: Path, mode: str = "RGBA") -> None:
    """把生成结果铺成纯白底，与现有素材的通道模式保持一致。

    mode 沿用原素材：主形象是 RGBA（alpha 全 255），姿态设定表是 RGB。
    """
    from PIL import Image

    image = Image.open(src).convert("RGBA")
    white = Image.new("RGBA", image.size, (255, 255, 255, 255))
    white.alpha_composite(image)
    white.convert(mode).save(src)
    print(f"  → {src}（已铺白底）")


def _batch(only: str | None, resume: bool = False) -> None:
    """批次：4 个素材重生成到 staging，参考图取自 staging/_base 的留底。

    resume=True 时，staging 里已经有的素材直接跳过——生成要花钱，
    中途连接器抽风时不该把已经做好的那几张重做一遍。
    """
    for rel, transparent, ratio in BATCH:
        if only and only not in rel:
            continue
        canonical = AIV / rel
        if not canonical.exists():
            print(f"跳过（素材不存在）：{rel}", file=sys.stderr)
            continue
        dst = STAGING / rel
        if resume and dst.exists():
            print(f"跳过（staging 里已有，resume）：{rel}")
        else:
            base = STAGING / "_base" / rel
            if not base.exists():
                base.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(canonical, base)
            print(f"生成 {rel} …")
            generate_glasses(base, dst, transparent=False,
                             aspect_ratio=ratio, sheet=ratio != "1:1")
            print(f"擦镜框杂物 {rel} …")
            cleanup_glasses(dst, dst, sheet=ratio != "1:1", aspect_ratio=ratio)
            if transparent:
                _cut_background(dst, dst)
            else:
                from PIL import Image

                mode = Image.open(canonical).mode
                _flatten_white(dst, mode)
            stamp(dst)
        # 白底主形象顺带抠一份透明底版，合成进视频用这个
        if rel == MAIN_WHITE:
            derived = STAGING / DERIVED[0]
            if not (resume and derived.exists()):
                _cut_background(dst, derived)
                stamp(derived)


def _promote(only: str | None = None) -> None:
    """把 staging 的结果覆盖到正式素材路径。"""
    if not STAGING.exists():
        print(f"没有 staging 目录：{STAGING}", file=sys.stderr)
        return
    for rel in [item[0] for item in BATCH] + list(DERIVED):
        if only and only not in rel:
            continue
        src = STAGING / rel
        if not src.exists():
            continue
        dst = AIV / rel
        shutil.copy2(src, dst)
        print(f"  → {dst.relative_to(AIV)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="给 Growdu 小象戴深藏蓝方形眼镜")
    parser.add_argument("src", nargs="?", help="源图（单张模式）")
    parser.add_argument("dst", nargs="?", help="目标图（单张模式）")
    parser.add_argument("--transparent", action="store_true",
                        help="输出抠透明底")
    parser.add_argument("--batch", action="store_true",
                        help="批次重生成全部素材到 staging")
    parser.add_argument("--only", help="批次里只做某个素材（按路径子串匹配）")
    parser.add_argument("--promote", action="store_true",
                        help="把 staging 结果覆盖到正式素材路径")
    parser.add_argument("--resume", action="store_true",
                        help="批次里跳过 staging 已经有的素材（断点续跑）")
    parser.add_argument("--no-stamp", action="store_true", help="不盖铭牌章")
    args = parser.parse_args(argv)

    if args.promote:
        _promote(args.only)
        return 0

    if args.batch or (not args.src and not args.dst):
        _batch(args.only, args.resume)
        return 0

    if not (args.src and args.dst):
        parser.error("单张模式需要同时给出 src 与 dst")

    src, dst = Path(args.src), Path(args.dst)
    if not src.exists():
        print(f"源图不存在：{src}", file=sys.stderr)
        return 1
    generate_glasses(src, dst, transparent=args.transparent)
    if not args.no_stamp:
        stamp(dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
