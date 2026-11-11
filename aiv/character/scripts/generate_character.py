#!/usr/bin/env python3
"""生成 Growdu 模型形象（3D 卡通小象）。

素材源：aiv/growdu2.jpeg（形象原型，唯一来源）。
产出：
  character/growdu_character_2k.png       主形象（白底）
  character/growdu_character_2k_nobg.png  透明底版（合成进视频用）
  character/growdu_pose_sheet.png          6 姿态设定表

依赖 mcode-tools CLI（mcode-tools-master skill）：
  mcode-tools upload_temp_url <file>              # 本地图片 → 临时 URL
  mcode-tools connector call connector__matrix__generate_image --args-file <json>
  mcode-tools connector call connector__matrix__remove_image_background --args <json>
  mcode-tools get_asset_url <node_id>             # node_id → 下载 URL

用法：
  python3 scripts/generate_character.py

注意：
  - 每次生成都会消耗生成额度，重复运行前先确认是否真的需要重做。
  - 铭牌必须显示 growdu（品牌标识），但**文字不能由模型生成**：模型的中英文会
    乱码（growdu 可能变成 giowdu / grawdu）。生成后统一跑一遍 stamp_badge.py，
    把铭牌刷成纯白再用 PingFang SC 写上 growdu。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _mcode import call, download, upload  # noqa: E402  同目录脚本
from _persona import PERSONA_PROMPT  # noqa: E402  人格气质唯一来源
from add_glasses import GLASSES_COLOR, GLASSES_STYLE  # noqa: E402  眼镜规格唯一来源
from stamp_badge import stamp_badge  # noqa: E402  同目录脚本

HERE = Path(__file__).resolve().parent
AIV = HERE.parent.parent           # aiv
CHAR_DIR = AIV / "character"
SOURCE_IMAGE = AIV / "growdu2.jpeg"   # 形象原型，唯一来源

GLASSES_PROMPT = f"""眼镜（必须戴）：
- 戴一副{GLASSES_STYLE}眼镜，镜框颜色深藏蓝 {GLASSES_COLOR}（与马甲同色），框条纤细规整，方形镜片带极小圆角
- 镜片完全透明，能清楚看到眼睛，不要镜片反光、不要镜片变色、不要墨镜遮眼
- 眼镜架在两只眼睛上，佩戴位置与角度自然，镜框总宽度与两只大眼睛的总跨度相称
- 镜腿从镜框两侧水平伸向两只耳朵"""

CHARACTER_PROMPT = f"""以图1（3D 渲染的可爱小象幼崽坐姿形象）为主体原型，生成一张专业的产品级角色设定图（character turnaround sheet）。

角色设定：一位讲解数据库内核技术的拟人化小象「Growdu」，定位是「专注数据库内核方向的独立开发者」的技术讲解者。

{PERSONA_PROMPT}

必须保留图1的视觉特征：
- 圆润饱满的浅蓝灰色皮肤，3D 卡通渲染质感，大眼、粉色面颊、小巧象牙
- 整体为正面坐姿、白色纯净背景
- 柔和均匀的棚拍打光，无强反光

新增元素（技术博主属性）：
- 脖子佩戴细黑色头戴式耳机 + 麦克风臂
- 胸前佩戴深藏蓝色 (#2B4C7E) 技术围裙 / 工装马甲，胸口有一个圆柱形数据库磁盘图标，颜色为琥珀黄 (#F5A623)
- 马甲上别一块白色小铭牌

{GLASSES_PROMPT}

画面要求：
- 纯白背景 (#FFFFFF)，无投影或极淡的接触阴影
- 主体居中，留出充足白边，适合后续做二次合成与局部抠图
- 造型干净、克制，不要拟人化过度（不要人类表情、不要多余肢体）
- 右侧留一小块空白区域用于后续叠加文字

风格：干净的 3D 卡通渲染，产品级质感，类似现代科技品牌的吉祥物设计。"""

POSE_PROMPT = f"""以图1（3D 渲染的可爱小象角色，穿深藏蓝色工装马甲、佩戴黑色头戴耳机、胸口有琥珀黄圆柱数据库图标）为唯一原型，生成一张角色姿态设定表。

IMPORTANT — 铭牌上绝对不要有任何文字：胸口那块白色矩形铭牌必须是完全空白的纯白色，没有任何字母、汉字、符号、条纹或任何类似文字的痕迹。

{PERSONA_PROMPT}

排版：3 列 × 2 行网格，共 6 个姿态，均匀排列在纯白背景 (#FFFFFF) 上，每个姿态之间有清晰的白色间隔，风格与光完全一致。

六个姿态依次为：
1. 正面坐姿微笑、双手放在身前（中性/默认姿态）
2. 右臂抬起指向右方，示意为正在讲解某个技术概念
3. 右手抬到下巴处作思考状，微微侧头
4. 双手举起做出「数字 2」的手势
5. 正面坐姿但头微微低，看向下方（沉思/讲解细节）
6. 身体略微后仰、双手摊开，表情豁达（收束/总结姿态）

{GLASSES_PROMPT}
- 六个姿态里的小象全都戴着这副眼镜，佩戴位置与角度各自自然

硬性要求：
- 严格保持图1的角色设定不变：同一只小象、同样的浅蓝灰色皮肤、同样的圆眼与粉色面颊、同样的深藏蓝 (#2B4C7E) 马甲、同样的琥珀黄 (#F5A623) 圆柱数据库图标、同样的黑色头戴耳机
- 每个姿态的胸口都别着一块横向长方形的**白色小铭牌**（与图1同款）
- 铭牌严格空白纯白，无任何文字或类似文字的图案
- 六个姿态是同一个角色的不同动作，不是不同的角色；体型比例、颜色、光照完全统一
- 纯白背景，无投影，无场景道具
- 不要任何文字标签、边框、说明文字、字母或数字
- 干净的产品级 3D 卡通渲染质感"""


def main() -> int:
    if not SOURCE_IMAGE.exists():
        print(f"缺少形象原型：{SOURCE_IMAGE}", file=sys.stderr)
        return 1
    CHAR_DIR.mkdir(parents=True, exist_ok=True)
    ref = upload(SOURCE_IMAGE)
    print(f"已上传形象原型：{SOURCE_IMAGE.name}")

    print("生成主形象（白底）…")
    res = call("connector__matrix__generate_image", {"requests": [{
        "prompt": CHARACTER_PROMPT,
        "reference_images": [{"url": ref, "mime_type": "image/jpeg"}],
        "aspect_ratio": "1:1", "area": "2K", "output_format": "png",
        "output_file": "growdu_character_2k.png", "n": 1,
    }]})
    node = res["success_items"][0]["node_id"]
    main_png = CHAR_DIR / "growdu_character_2k.png"
    download(node, main_png)
    print(f"  → {main_png.relative_to(AIV)}")

    print("抠透明底…")
    res = call("connector__matrix__remove_image_background", {"image_url": upload(main_png)})
    download(res["node_id"], CHAR_DIR / "growdu_character_2k_nobg.png")
    print(f"  → {(CHAR_DIR / 'growdu_character_2k_nobg.png').relative_to(AIV)}")

    print("生成 6 姿态设定表…")
    res = call("connector__matrix__generate_image", {"requests": [{
        "prompt": POSE_PROMPT,
        "reference_images": [{"url": upload(main_png), "mime_type": "image/png"}],
        "aspect_ratio": "16:9", "area": "2K", "output_format": "png",
        "output_file": "growdu_pose_sheet.png", "n": 1,
    }]})
    download(res["success_items"][0]["node_id"], CHAR_DIR / "growdu_pose_sheet.png")
    print(f"  → {(CHAR_DIR / 'growdu_pose_sheet.png').relative_to(AIV)}")

    print("给铭牌印上 growdu（真实字体渲染）…")
    for target in (main_png, CHAR_DIR / "growdu_character_2k_nobg.png"):
        stamp_badge(target)

    print("完成。规范见 aiv/形象与音色规范.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
