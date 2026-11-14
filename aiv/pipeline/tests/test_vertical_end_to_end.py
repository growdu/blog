"""竖版（1080×1920）端到端：真的合成出一条符合规格的竖版成片。

为什么要有这条
--------------
横版的端到端冒烟（`test_compose_end_to_end.py`）证明的是「渲染 → 拼接 →
混音 → 封装」这条链路本身能跑。竖版要证明的是**另一件事**：

1. **画幅真的是竖的**。竖版不是把横版转 90°——它另有一套版式、
   另一套字幕排布（`palette.VERTICAL_UI_BOTTOM`、按短边缩放的字号）。
   所以「1080×1920」这条规格得在**真的 mp4** 上量，不是看 JSON。
2. **字幕没掉进平台 UI 区**。抖音的导航栏与文案区盖在画面下缘，
   字幕压在那底下等于没写。横版的冒烟测不出这条——横版字幕本来就贴着
   底边，是对的。

**「文件生成了」不等于「成片是对的」**：所以这里不只查文件在不在，
而是查分辨率、帧率、编码、时间基、音频参数、快起（faststart），
最后还把成片第一帧解出来数像素——字幕必须烧在画面里，
而且必须整个落在平台 UI 区**之上**。

素材是**已入库**的真实旁白与真实 BGM：产物不入库、输入才入库。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from pyv import compose as compose_mod
from pyv import episodes
from pyv import fonts
from pyv import palette
from pyv.timeline import (
    Audio,
    Scene,
    Storyboard,
    SubtitleEvent,
    SubtitleStyle,
    Video,
)

AIV_ROOT = episodes.AIV_ROOT
BGM = AIV_ROOT / "music/tracks/series-bed-01.wav"

#: 竖版画布
WIDTH, HEIGHT = 1080, 1920

#: 成片时长（秒）。三秒够走完「渲染 → 拼接 → 混音 → 封装」。
DURATION = 3.0

#: 字幕用一个别处不会出现的颜色：背景是白的，场景画的是深蓝块，
#: 只有字幕会用洋红。这样「画面里确实有字幕」才能被像素判定认出来。
SUBTITLE_TEXT = "竖版端到端冒烟"
SUBTITLE_FILL = "#FF00FF"

#: 平台 UI 区的高度（画面下缘这一段会被抖音自己的控件盖住）。
#: 字幕的墨迹一个像素都不许掉进去。
#:
#: **这个数字是独立取值，不许从 `palette` import。**
#: 从那儿 import 就成了自证：生产代码把 UI 预留改小，守卫跟着改小，
#: 永远是绿的——注入缺陷验过，改成 0 都能过。
#: 两者的一致性由下面那条「预留不许漂移」单独钉住。
UI_TOP = 1500

#: 平台 UI 预留高度（`palette.VERTICAL_UI_BOTTOM`）的定稿值。
UI_RESERVE = 420


def _probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,"
         "time_base,sample_rate,channels:format=duration",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def _narration() -> Path:
    """一期**已入库**的旁白音频。"""
    for ep in episodes.EPISODE_ORDER:
        path = episodes.narration_path(ep)
        if path.is_file():
            return path
    raise AssertionError(
        "仓库里一期旁白都没有——「出片必需的输入要入库」这条口径坏了"
    )


def _storyboard(narration: Path) -> Storyboard:
    """两段正文场景，画布是竖版。"""
    half = DURATION / 2
    scenes = [
        Scene(id="s01", start=0.0, end=half, type="code",
              subtitle="第一段字幕", renderer="sample_scene"),
        Scene(id="s02", start=half, end=DURATION, type="code",
              subtitle="第二段字幕", renderer="sample_scene"),
    ]
    return Storyboard(
        version=1,
        video=Video(width=WIDTH, height=HEIGHT, fps=24, duration=DURATION),
        audio=Audio(narration=str(narration), bgm=str(BGM)),
        subtitle_style=SubtitleStyle(primary=SUBTITLE_FILL, outline="#000000"),
        scenes=scenes,
        subtitles=[SubtitleEvent(start=0.0, end=DURATION, text=SUBTITLE_TEXT)],
    )


def _first_frame(path: Path) -> np.ndarray:
    """成片第一帧的像素（RGB）。"""
    from PIL import Image

    frame = path.with_suffix(".frame.png")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vframes", "1", str(frame)],
        check=True, capture_output=True, text=True,
    )
    with Image.open(frame) as img:
        return np.asarray(img.convert("RGB"), dtype=np.int16)


def _magenta_mask(pixels: np.ndarray) -> np.ndarray:
    """字幕的洋红色掩码。"""
    r, g, b = pixels[..., 0], pixels[..., 1], pixels[..., 2]
    return (r > 200) & (b > 200) & (g < 100)


def test_the_chinese_subtitle_has_real_glyphs_in_the_current_font():
    """中文不能是豆腐块。

    Linux 上字体是回退来的（macOS 是 PingFang SC，Linux 是 Noto/思源），
    这一条正是那道保险：回退字体里没有这些字，字幕会变成方框，
    而「文件生成成功」是发现不了的。
    """
    missing = [ch for ch in SUBTITLE_TEXT if fonts.missing_glyph(ch)]
    assert not missing, (
        f"这些字在当前字体（{fonts.font_family()}）里画不出来，会变成豆腐块：{missing}"
    )


def _top_level_boxes(path: Path) -> list[str]:
    """按文件顺序读出 mp4 顶层盒子的类型。

    **自己读，不借用 `preflight` 的那份**：守卫不能拿被测对象自己的
    工具来判，否则工具错了两边一起错，守卫就是假绿。

    mp4 是「盒子套盒子」：顶层盒头 8 字节 = 4 字节长度（含头）+ 4 字节类型；
    长度 1 表示真实长度在后面 8 字节（64 位扩展），此时盒头共 **16 字节**。
    """
    boxes: list[str] = []
    with open(path, "rb") as handle:
        while True:
            header = handle.read(8)
            if len(header) < 8:
                break
            size = int.from_bytes(header[:4], "big")
            box = header[4:8].decode("latin-1")
            header_size = 8
            if size == 1:
                extra = handle.read(8)
                if len(extra) < 8:
                    break
                size = int.from_bytes(extra, "big")
                header_size = 16
            boxes.append(box)
            if size == 0 or size < header_size:
                break
            handle.seek(size - header_size, 1)
    return boxes


def test_a_fresh_clone_can_produce_a_broadcastable_vertical_episode(tmp_path):
    """从入库素材直接合成出符合规格的竖版成片。"""
    narration = _narration()
    storyboard = _storyboard(narration)
    assert storyboard.validate() == [], (
        f"合成的竖版 storyboard 不合契约：{storyboard.validate()}"
    )
    assert BGM.is_file(), f"仓库里没有 BGM：{BGM}"

    out = tmp_path / "ep-vertical-smoke.mp4"
    compose_mod.compose(storyboard, tmp_path / "build", out,
                        narration=narration, bgm=BGM)

    assert out.is_file(), f"竖版成片没生成：{out}"
    assert out.stat().st_size > 0, "竖版成片是空的"

    info = _probe(out)
    streams = {s["codec_type"]: s for s in info["streams"]}
    assert set(streams) == {"video", "audio"}, f"竖版成片里少了轨道：{list(streams)}"

    video = streams["video"]
    assert video["codec_name"] == "h264"
    assert video["pix_fmt"] == "yuv420p"
    assert (video["width"], video["height"]) == (WIDTH, HEIGHT), (
        f"画幅不是竖版 1080×1920，而是 "
        f"{video['width']}×{video['height']}"
    )
    assert video["r_frame_rate"] == "24/1"
    # 规格钉死的时间基：concat 阶段要求各片段时间基一致
    assert video["time_base"] == "1/24000", (
        f"video_track_timescale 不对：{video['time_base']}"
    )

    audio = streams["audio"]
    assert audio["codec_name"] == "aac"
    assert audio["sample_rate"] == "48000"
    assert audio["channels"] == 2

    assert abs(float(info["format"]["duration"]) - DURATION) < 0.3, (
        f"竖版成片时长不对：{info['format']['duration']}"
    )


def test_the_vertical_episode_is_faststart(tmp_path):
    """moov 在 mdat 之前——不等整个文件下完就能播。

    竖版是抖音那一档的产物，手机上看是边下边播；moov 垫在后面的话，
    首屏要等整个文件下完。
    """
    narration = _narration()
    storyboard = _storyboard(narration)
    out = tmp_path / "ep-vertical-faststart.mp4"
    compose_mod.compose(storyboard, tmp_path / "build", out,
                        narration=narration, bgm=BGM)

    raw = out.read_bytes()
    moov = raw.find(b"moov")
    mdat = raw.find(b"mdat")
    assert moov != -1 and mdat != -1, f"成片里找不到 moov/mdat：{out}"
    assert moov < mdat, (
        f"moov 在 mdat 之后（moov@{moov}, mdat@{mdat}）——不是 faststart"
    )

    # 字节扫描会被 mdat 载荷里偶然出现的 "moov" 字样骗到，
    # 所以真正的判据是**顶层盒子的顺序**。
    boxes = _top_level_boxes(out)
    assert "moov" in boxes and "mdat" in boxes, (
        f"成片的顶层盒子不对：{boxes}"
    )
    assert boxes.index("moov") < boxes.index("mdat"), (
        f"顶层盒子顺序里 moov 在 mdat 之后：{boxes}——不是 faststart"
    )


def test_the_platform_ui_reserve_has_not_drifted():
    """平台 UI 预留高度不许偷偷变小。

    行为测试里的边界是**写死的 1500**（不许从 `palette` import，否则
    生产代码一改，守卫跟着改，永远是绿的）。代价是：改预留高度时，
    这里会红，提醒人把两处一起改。

    1920 - 420 = 1500。
    """
    assert palette.VERTICAL_UI_BOTTOM == UI_RESERVE, (
        f"平台 UI 预留从 {UI_RESERVE} 变成了 {palette.VERTICAL_UI_BOTTOM}——"
        f"要么改回定稿值，要么同步改这条测试与 UI_TOP={UI_TOP}"
    )
    assert HEIGHT - UI_RESERVE == UI_TOP, (
        f"UI_TOP（{UI_TOP}）与预留高度对不上：{HEIGHT} - {UI_RESERVE}"
    )


def test_the_vertical_subtitle_is_burned_in_and_above_the_platform_ui(tmp_path):
    """字幕烧进去了，而且整个落在平台 UI 区之上。

    这条是竖版**独有**的判据：横版字幕贴着底边是对的，竖版贴着底边
    就会被抖音的导航栏盖住。横版的冒烟测不出这条。
    """
    narration = _narration()
    storyboard = _storyboard(narration)
    out = tmp_path / "ep-vertical-subtitle.mp4"
    compose_mod.compose(storyboard, tmp_path / "build", out,
                        narration=narration, bgm=BGM)

    pixels = _first_frame(out)
    assert pixels.shape[:2] == (HEIGHT, WIDTH), (
        f"解出来的第一帧尺寸不对：{pixels.shape}"
    )

    mask = _magenta_mask(pixels)
    count = int(mask.sum())
    assert count > 50, (
        f"成片第一帧里没有字幕的洋红色（{count} 个像素）——字幕没烧进去"
    )

    rows = np.nonzero(mask.any(axis=1))[0]
    assert rows.min() >= 0 and rows.max() < UI_TOP, (
        f"字幕墨迹掉到 y={rows.max()}，平台 UI 区从 y={UI_TOP} 开始——"
        f"字幕会被抖音的控件盖住"
    )
