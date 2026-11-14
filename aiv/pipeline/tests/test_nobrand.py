"""无品牌导流版：抖音这一档的成片。

抖音禁「过度营销信息」与站外引流（规格 §6.6.4）。我们的片头是整屏
「Growdu」字标、片尾是 `growdu.cn` / 订阅关注 / 点赞支持三胶囊——正好撞上。
所以抖音这一档**不能**直接用带品牌的成片，要另出一版。

这一层测两件事：

1. **storyboard 层**：去品牌片 + 落版去品牌名 + 时间码回退
2. **成片层**：画面里不得出现品牌片的画面

第 2 条是**像素级**的，不是「storyboard 里没有 brand 场景」那种 JSON 级检查——
JSON 说没有、画面里有，是最难发现的一种错（文件在、时长对、命令报成功，
只有投出去才知道）。所以这里真的抽帧、真的比像素。
"""
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from pyv import brand
from pyv.timeline import Storyboard

AIV_ROOT = Path(__file__).resolve().parents[2]
CLIPS_DIR = AIV_ROOT / "brand" / "clips"
INTRO_CLIP = CLIPS_DIR / "growdu_intro_3s_1080p.mp4"
OUTRO_CLIP = CLIPS_DIR / "growdu_outro_3s_1080p.mp4"

#: 画面相似度阈值（0~255 的平均像素差）。
#:
#: 实测：无品牌成片的帧与品牌片帧的**最小**距离是 61.79，中位 180.87。
#: 而品牌片真的在片子里时，距离 ≈ 0（同一帧、同一编码器）。
#: 所以 25 离两侧都很远：既能抓住「品牌片混进来了」，又不误伤正文画面。
BRAND_FRAME_DISTANCE = 25

#: 品牌片的采样时间点（秒）。取片头片尾各几帧，避开转场瞬间。
BRAND_SAMPLE_TIMES = (0.3, 1.0, 1.8, 2.5)

#: 无品牌成片的采样时间点（秒）。覆盖首尾与中间。
BODY_SAMPLE_TIMES = (0.5, 2.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 34.0)


# --- 剥品牌词 ---------------------------------------------------------------


def test_the_brand_word_is_dropped_from_the_signature():
    """落版标签「独立开发者 · growdu」→「独立开发者」。"""
    assert brand.strip_brand_word("独立开发者 · growdu") == "独立开发者"


def test_the_brand_word_is_dropped_case_insensitively():
    assert brand.strip_brand_word("独立开发者 · Growdu") == "独立开发者"


def test_a_text_without_the_brand_word_is_untouched():
    assert brand.strip_brand_word("独立开发者") == "独立开发者"


def test_the_remaining_segments_keep_their_order():
    """分段丢掉含品牌词的那一段，**其余按原顺序**保留。"""
    assert brand.strip_brand_word("Growdu · 深入数据库 · 分享技术之美") == \
        "深入数据库 · 分享技术之美"


def test_a_text_that_is_only_the_brand_word_falls_back():
    """剥完空了不能留个空标签——用中性兜底。"""
    assert brand.strip_brand_word("growdu") == brand.NEUTRAL_LABEL


# --- storyboard 层 ----------------------------------------------------------


def _storyboard(episode: str = "row-lock") -> dict:
    path = AIV_ROOT / f"storyboard_{episode}.json"
    if not path.is_file():
        pytest.skip(f"本机没有 storyboard（{path} 是 gitignore 的本地产物）")
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_nobrand_storyboard_has_no_brand_plates(tmp_path):
    raw = _storyboard()
    source = tmp_path / "in.json"
    source.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    out = brand.make_nobrand(source, tmp_path / "out.json")
    result = json.loads(out.read_text(encoding="utf-8"))
    assert [s["id"] for s in result["scenes"] if s["id"].startswith("brand_")] == []


def test_the_nobrand_storyboard_drops_the_brand_word_from_the_signature(tmp_path):
    raw = _storyboard()
    source = tmp_path / "in.json"
    source.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    out = brand.make_nobrand(source, tmp_path / "out.json")
    result = json.loads(out.read_text(encoding="utf-8"))
    for scene in result["scenes"]:
        badge = (scene.get("params") or {}).get("badge")
        if isinstance(badge, str):
            assert "growdu" not in badge.lower(), scene["id"]


def test_the_nobrand_storyboard_still_validates(tmp_path):
    """去掉品牌片之后，时间码必须还是连着的、时长自洽。"""
    raw = _storyboard()
    source = tmp_path / "in.json"
    source.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    out = brand.make_nobrand(source, tmp_path / "out.json")
    errors = Storyboard.load(out).validate()
    assert errors == [], errors


def test_making_it_twice_gives_the_same_thing(tmp_path):
    """可重复执行：跑两遍结果必须一样（幂等）。"""
    raw = _storyboard()
    source = tmp_path / "in.json"
    source.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    first = brand.make_nobrand(source, tmp_path / "a.json").read_text(encoding="utf-8")
    second = brand.make_nobrand(source, tmp_path / "b.json").read_text(encoding="utf-8")
    assert first == second


def test_the_nobrand_storyboard_can_start_from_a_branded_one(tmp_path):
    """带品牌的 storyboard 当输入也行——时间码要能回到原样。

    流水线里 `make brand` 是就地改写 storyboard 的，所以无品牌版拿到的
    往往已经是带品牌的那份。这条守住「套上去再摘下来能回到原样」。
    """
    raw = _storyboard()
    source = tmp_path / "in.json"
    source.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    branded = tmp_path / "branded.json"
    brand.apply_plates(source, branded, tmp_path / "build")
    result = json.loads(
        brand.make_nobrand(branded, tmp_path / "out.json").read_text(encoding="utf-8"))
    assert [s["id"] for s in result["scenes"] if s["id"].startswith("brand_")] == []
    assert abs(result["scenes"][0]["start"]) < 1e-3


# --- 成片层（像素级） -------------------------------------------------------


def _signature(video: Path, times) -> list:
    """抽几帧，压成 32×32 的灰度签名。"""
    from PIL import Image

    signatures = []
    with tempfile.TemporaryDirectory() as work:
        for index, at in enumerate(times):
            out = Path(work) / f"f{index}.png"
            subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{at:.3f}",
                            "-i", str(video), "-frames:v", "1", "-y", str(out)],
                           check=True, capture_output=True)
            if out.is_file():
                signatures.append(Image.open(out).convert("L").resize((32, 32)))
    return signatures


def _distance(a, b) -> float:
    """两帧的平均像素差（0~255）。"""
    left = list(a.getdata())
    right = list(b.getdata())
    return sum(abs(x - y) for x, y in zip(left, right)) / len(left)


def test_the_nobrand_video_shows_no_brand_frames(tmp_path):
    """成片的每一帧都离品牌片足够远。

    **这是像素级检查**：storyboard 里没有 brand 场景，不等于画面里没有那几秒。
    """
    video = AIV_ROOT / "out" / "row-lock__nobrand.mp4"
    if not video.is_file():
        pytest.skip(f"本机没有无品牌成片 {video}（成片是 gitignore 的本地产物）")
    if not INTRO_CLIP.is_file() or not OUTRO_CLIP.is_file():
        pytest.skip("本机没有品牌片素材，比不了")

    brand_frames = (_signature(INTRO_CLIP, BRAND_SAMPLE_TIMES)
                    + _signature(OUTRO_CLIP, BRAND_SAMPLE_TIMES))
    body_frames = _signature(video, BODY_SAMPLE_TIMES)
    assert brand_frames and body_frames

    closest = min(_distance(b, f) for b in brand_frames for f in body_frames)
    assert closest > BRAND_FRAME_DISTANCE, (
        f"成片里出现了品牌片的画面（最近距离 {closest:.2f}，"
        f"阈值 {BRAND_FRAME_DISTANCE}）——无品牌版里混进了品牌片"
    )
