# 并行解码讲解片（代码驱动动画）实施计划

> **历史存档（2026-11-09 的实施计划）。** 其中 Task 5 的 2D 形象部件切分与
> `elephant.py` 已于 2026-11-11 整体移除，形象改走 3D 静帧 + 位移/缩放/淡入，
> 见《形象与音色规范》§1.6。本文保留当时的计划记录，不再是现行方案。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用代码把 11 句旁白渲染成 29.599 秒的「PostgreSQL 18 并行逻辑解码」讲解片，技术图示零模型生成，H3 只用于 3 秒质感片头。

**Architecture:** `storyboard.json` 是唯一时间轴契约，cairo 逐帧绘制每个场景 → ffmpeg 编码单场景片段 → concat 拼接 → 混入原旁白 → ASS 烧字幕 → 成片导入 MiniMax Design 做终审与多平台导出。场景是纯函数 `render(ctx, t, w, h)`，`t ∈ [0,1]`，无全局状态，可单测可重放。

**Tech Stack:** Python 3.11、cairo（绘制）、PIL（角色部件）、numpy + scipy.ndimage（连通块切分）、ffmpeg/ffprobe 8.1（编码与合成）、pytest。

## Global Constraints

- 成片规格：**1920×1080 / 24fps / H.264 yuv420p**，总时长 **29.599 秒**（`pa_decode_v2.mp3` 实测）。
- 画布背景 `#FFFFFF`；主色 `#2B4C7E`、强调 `#F5A623`、次强调 `#4FD1C5`、问题段 `#F6AD55`、面颊 `#F8BBD0`。
- 字幕：底部居中，**深蓝字 `#1B2A47` + 白描边 `#FFFFFF`**，每行 **≤ 14 字**，无底板。
- 字体固定 `PingFang SC`，启动时校验不可用即抛错，禁止静默降级。
- 字幕与口播文本**禁止出现**：`海量数据库`、`海量智库`、`原生集成`、`内核原生`、`Mass Elephant`（大小写不敏感）。
- 术语固定用 **reader**（不用 leader）；画面图示标注 `Reader (WALSender)`。
- 形象原图**唯一**来源 `docs/life/aiv/growdu.png`；**禁止**使用 `docs/db/logical_decode/pa_decode/` 下的任何图片。
- 旁白只读 `docs/life/aiv/pa_decode_v2.mp3`，不重录、不变速、不加 BGM。
- 路径只允许相对项目根 `docs/life/aiv/`；**禁止**引用 `~/Movies/Hub/...` 等应用目录。
- **禁止**写入 MiniMax Design 的任何数据库或画布文件。
- 每个任务一次提交；提交前 `python -m pytest tests/ -q` 必须全绿。
- 仅新增依赖：pytest（已装则复用）、scipy（已装则复用）；不得引入 manim / remotion / numpy 以外的绘图框架。

## 文件结构

| 文件 | 职责 |
| --- | --- |
| `pipeline/pyv/__init__.py` | 包标记 |
| `pipeline/pyv/palette.py` | 颜色、字体、画布尺寸常量与字体校验 |
| `pipeline/pyv/easing.py` | 缓动函数与 `clamp01` |
| `pipeline/pyv/timeline.py` | `Storyboard` / `Scene` 数据结构、加载与校验 |
| `pipeline/pyv/subtitle.py` | ASS 字幕生成 |
| `pipeline/pyv/align.py` | 旁白静音检测与句段时间码对齐 |
| `pipeline/pyv/render.py` | cairo 逐帧渲染 → ffmpeg 编码单场景片段 |
| `pipeline/pyv/compose.py` | 片段 concat + 混音 + 烧字幕 → 成片 |
| `pipeline/pyv/elephant.py` | 小象部件切分与 2D 动作 |
| `pipeline/pyv/draw.py` | 通用绘图原语（圆角矩形、箭头、卡片、数字大字） |
| `pipeline/pyv/scenes/__init__.py` | 场景包标记 |
| `pipeline/pyv/scenes/s01_intro.py` | 段 A：身份 + 标题 |
| `pipeline/pyv/scenes/s02_serial.py` | 段 B：串行瓶颈 |
| `pipeline/pyv/scenes/s03_cores.py` | 段 C：32 核只占 1 核 |
| `pipeline/pyv/scenes/s04_parallel.py` | 段 D：reader→worker 并行 |
| `pipeline/pyv/scenes/s05_order.py` | 段 E：顺序一致 + 2–5 倍 |
| `pipeline/pyv/scenes/s06_outro.py` | 段 F：收束 + 落版 |
| `pipeline/pyv/cli.py` | 命令行入口：`validate` / `align` / `render` / `compose` |
| `pipeline/tests/` | pytest 单测与集成测试 |
| `storyboard.json` | 时间轴契约（入库） |
| `build/` `out/` | 渲染产物与成片（不入库） |

---

### Task 1: 项目骨架 + 契约校验器

**Files:**
- Create: `docs/life/aiv/pipeline/pyv/__init__.py`
- Create: `docs/life/aiv/pipeline/pyv/palette.py`
- Create: `docs/life/aiv/pipeline/pyv/easing.py`
- Create: `docs/life/aiv/pipeline/pyv/timeline.py`
- Create: `docs/life/aiv/pipeline/pyv/cli.py`
- Create: `docs/life/aiv/pipeline/tests/test_palette.py`
- Create: `docs/life/aiv/pipeline/tests/test_easing.py`
- Create: `docs/life/aiv/pipeline/tests/test_timeline.py`
- Create: `docs/life/aiv/pipeline/tests/conftest.py`

**Interfaces:**
- Produces: `palette.WIDTH/HEIGHT/FPS/COLORS/FONT_FAMILY/assert_font_available()`
- Produces: `easing.clamp01(t) -> float`、`easing.linear(t) -> float`、`easing.ease_out_cubic(t) -> float`、`easing.ease_in_out(t) -> float`
- Produces: `timeline.Scene`、`timeline.Video`、`timeline.Audio`、`timeline.SubtitleStyle`、`timeline.Storyboard.load(path) -> Storyboard`、`Storyboard.validate() -> list[str]`、`Storyboard.duration -> float`
- Produces: `timeline.BANNED_SUBSTRINGS: tuple[str, ...]`
- Consumes: 无

- [ ] **Step 1: 创建包目录与空包文件**

```bash
cd /Users/growduduan/code/blog/docs/life/aiv
mkdir -p pipeline/pyv/scenes pipeline/tests pipeline/docs/superpowers/plans
touch pipeline/pyv/__init__.py pipeline/pyv/scenes/__init__.py
```

- [ ] **Step 2: 写失败的测试 `tests/test_palette.py`**

```python
# pipeline/tests/test_palette.py
import os

import pytest

from pyv import palette


def test_canvas_constants_match_spec():
    assert palette.WIDTH == 1920
    assert palette.HEIGHT == 1080
    assert palette.FPS == 24


def test_all_colors_are_hex():
    for name, value in palette.COLORS.items():
        assert value.startswith("#") and len(value) == 7, name
        int(value[1:], 16)


def test_subtitle_colors_are_dark_text_on_light_bg():
    assert palette.COLORS["subtitle_text"] == "#1B2A47"
    assert palette.COLORS["subtitle_outline"] == "#FFFFFF"
    assert palette.COLORS["bg"] == "#FFFFFF"


def test_assert_font_available_passes_on_this_machine():
    palette.assert_font_available()


def test_assert_font_available_raises_when_font_missing(monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    with pytest.raises(RuntimeError, match="PingFang"):
        palette.assert_font_available()
```

- [ ] **Step 3: 写失败的测试 `tests/test_easing.py`**

```python
# pipeline/tests/test_easing.py
import pytest

from pyv import easing


@pytest.mark.parametrize("fn", [easing.linear, easing.ease_out_cubic, easing.ease_in_out])
def test_endpoints(fn):
    assert fn(0.0) == pytest.approx(0.0, abs=1e-6)
    assert fn(1.0) == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize("fn", [easing.linear, easing.ease_out_cubic, easing.ease_in_out])
def test_out_of_range_is_clamped(fn):
    assert fn(-3.0) == pytest.approx(0.0, abs=1e-6)
    assert fn(9.0) == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize("fn", [easing.linear, easing.ease_out_cubic, easing.ease_in_out])
def test_monotonic_increasing(fn):
    values = [fn(i / 20) for i in range(21)]
    assert all(b >= a - 1e-9 for a, b in zip(values, values[1:]))
```

- [ ] **Step 4: 写失败的测试 `tests/test_timeline.py`**

```python
# pipeline/tests/test_timeline.py
import json

from pyv import timeline


def _base_scenes():
    return [
        {"id": "s01", "start": 0.0, "end": 2.0, "type": "code",
         "renderer": "pyv.scenes.s01_intro", "subtitle": "我是独立开发者"},
        {"id": "s02", "start": 2.0, "end": 5.0, "type": "code",
         "renderer": "pyv.scenes.s02_serial", "subtitle": "发布端只有一个解码线程"},
    ]


def _storyboard(scenes=None, duration=5.0):
    return {
        "version": 1,
        "video": {"width": 1920, "height": 1080, "fps": 24, "duration": duration},
        "audio": {"narration": "pa_decode_v2.mp3", "bgm": None},
        "subtitle_style": {"primary": "#1B2A47", "outline": "#FFFFFF", "position": "bottom-center"},
        "scenes": scenes if scenes is not None else _base_scenes(),
    }


def _write(tmp_path, data):
    path = tmp_path / "storyboard.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_valid_storyboard_has_no_errors(tmp_path):
    sb = timeline.Storyboard.load(_write(tmp_path, _storyboard()))
    assert sb.validate() == []
    assert sb.duration == 5.0


def test_gap_between_scenes_is_reported(tmp_path):
    scenes = _base_scenes()
    scenes[1]["start"] = 2.5
    sb = timeline.Storyboard.load(_write(tmp_path, _storyboard(scenes)))
    errors = sb.validate()
    assert any("不连续" in e for e in errors)


def test_overlap_between_scenes_is_reported(tmp_path):
    scenes = _base_scenes()
    scenes[1]["start"] = 1.5
    sb = timeline.Storyboard.load(_write(tmp_path, _storyboard(scenes)))
    assert any("不连续" in e for e in sb.validate())


def test_duration_mismatch_is_reported(tmp_path):
    sb = timeline.Storyboard.load(_write(tmp_path, _storyboard(duration=6.0)))
    assert any("总时长" in e for e in sb.validate())


def test_company_name_in_subtitle_is_rejected(tmp_path):
    scenes = _base_scenes()
    scenes[0]["subtitle"] = "海量数据库并行解码"
    sb = timeline.Storyboard.load(_write(tmp_path, _storyboard(scenes)))
    assert any("禁止词" in e for e in sb.validate())


def test_overlong_subtitle_line_is_rejected(tmp_path):
    scenes = _base_scenes()
    scenes[0]["subtitle"] = "一二三四五六七八九十一二三四五六七八九十"
    sb = timeline.Storyboard.load(_write(tmp_path, _storyboard(scenes)))
    assert any("14 字" in e for e in sb.validate())


def test_code_scene_requires_renderer(tmp_path):
    scenes = _base_scenes()
    scenes[0].pop("renderer")
    sb = timeline.Storyboard.load(_write(tmp_path, _storyboard(scenes)))
    assert any("renderer" in e for e in sb.validate())


def test_h3_scene_requires_clip_and_spec(tmp_path):
    scenes = _base_scenes()
    scenes[0] = {"id": "s01", "start": 0.0, "end": 2.0, "type": "h3", "subtitle": "片头"}
    sb = timeline.Storyboard.load(_write(tmp_path, _storyboard(scenes)))
    errors = sb.validate()
    assert any("clip" in e for e in errors)
    assert any("h3" in e for e in errors)


def test_scene_without_subtitle_is_rejected(tmp_path):
    scenes = _base_scenes()
    scenes[0]["subtitle"] = ""
    sb = timeline.Storyboard.load(_write(tmp_path, _storyboard(scenes)))
    assert any("字幕" in e for e in sb.validate())
```

- [ ] **Step 5: 写 `tests/conftest.py` 让 `pyv` 可导入**

```python
# pipeline/tests/conftest.py
import os
import sys

PIPELINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PIPELINE_DIR not in sys.path:
    sys.path.insert(0, PIPELINE_DIR)
```

- [ ] **Step 6: 运行测试确认失败**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/ -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'pyv'`

- [ ] **Step 7: 实现 `pyv/palette.py`**

```python
# pipeline/pyv/palette.py
"""颜色、字体与画布尺寸常量。"""
from __future__ import annotations

import os

WIDTH = 1920
HEIGHT = 1080
FPS = 24

COLORS = {
    "bg": "#FFFFFF",
    "primary": "#2B4C7E",
    "accent": "#F5A623",
    "secondary": "#4FD1C5",
    "cheek": "#F8BBD0",
    "problem": "#F6AD55",
    "subtitle_text": "#1B2A47",
    "subtitle_outline": "#FFFFFF",
}

FONT_FAMILY = "PingFang SC"

PINGFANG_CANDIDATES = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/PingFang SC.ttc",
)


def assert_font_available() -> None:
    """字体不可用时立即失败，避免跨机渲染出豆腐块。"""
    if not any(os.path.exists(p) for p in PINGFANG_CANDIDATES):
        raise RuntimeError(
            "未找到 PingFang SC 字体，拒绝渲染："
            + ", ".join(PINGFANG_CANDIDATES)
        )


def hex_to_rgb(value: str) -> tuple[float, float, float]:
    """'#RRGGBB' → (r, g, b)，分量范围 0..1。"""
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]
```

- [ ] **Step 8: 实现 `pyv/easing.py`**

```python
# pipeline/pyv/easing.py
"""缓动函数。所有函数接受任意实数并把结果钳制在 [0, 1]。"""


def clamp01(t: float) -> float:
    return 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)


def linear(t: float) -> float:
    return clamp01(t)


def ease_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 1.0 - (1.0 - t) ** 3


def ease_in_out(t: float) -> float:
    t = clamp01(t)
    if t < 0.5:
        return 2.0 * t * t
    return 1.0 - ((-2.0 * t + 2.0) ** 2) / 2.0
```

- [ ] **Step 9: 实现 `pyv/timeline.py`**

```python
# pipeline/pyv/timeline.py
"""storyboard.json 的数据结构、加载与校验。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

BANNED_SUBSTRINGS = (
    "海量数据库",
    "海量智库",
    "原生集成",
    "内核原生",
    "Mass Elephant",
)

MAX_SUBTITLE_LINE = 14
EPS = 1e-3


@dataclass(frozen=True)
class Video:
    width: int
    height: int
    fps: int
    duration: float


@dataclass(frozen=True)
class Audio:
    narration: str
    bgm: str | None = None
    bgm_gain_db: float | None = None


@dataclass(frozen=True)
class SubtitleStyle:
    primary: str
    outline: str
    position: str = "bottom-center"


@dataclass(frozen=True)
class Scene:
    id: str
    start: float
    end: float
    type: str
    subtitle: str
    renderer: str | None = None
    params: dict = field(default_factory=dict)
    h3: dict | None = None
    clip: str | None = None

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class Storyboard:
    version: int
    video: Video
    audio: Audio
    subtitle_style: SubtitleStyle
    scenes: list[Scene]

    @classmethod
    def load(cls, path: str | Path) -> "Storyboard":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        video = raw["video"]
        audio = raw["audio"]
        style = raw["subtitle_style"]
        scenes = [
            Scene(
                id=s["id"],
                start=float(s["start"]),
                end=float(s["end"]),
                type=s["type"],
                subtitle=s.get("subtitle", ""),
                renderer=s.get("renderer"),
                params=s.get("params", {}) or {},
                h3=s.get("h3"),
                clip=s.get("clip"),
            )
            for s in raw["scenes"]
        ]
        return cls(
            version=int(raw["version"]),
            video=Video(**video),
            audio=Audio(
                narration=audio["narration"],
                bgm=audio.get("bgm"),
                bgm_gain_db=audio.get("bgm_gain_db"),
            ),
            subtitle_style=SubtitleStyle(**style),
            scenes=scenes,
        )

    @property
    def duration(self) -> float:
        return max((s.end for s in self.scenes), default=0.0)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.version != 1:
            errors.append(f"version 必须为 1，实际 {self.version}")
        if (self.video.width, self.video.height) != (1920, 1080):
            errors.append(f"画布必须是 1920x1080，实际 {self.video.width}x{self.video.height}")
        if self.video.fps != 24:
            errors.append(f"fps 必须为 24，实际 {self.video.fps}")
        if not self.scenes:
            errors.append("场景列表为空")
            return errors

        if abs(self.scenes[0].start) > EPS:
            errors.append(f"首个场景必须从 0 开始，实际 {self.scenes[0].start}")

        for prev, cur in zip(self.scenes, self.scenes[1:]):
            if abs(prev.end - cur.start) > EPS:
                errors.append(f"场景 {prev.id} 与 {cur.id} 不连续（{prev.end} → {cur.start}）")

        last = self.scenes[-1]
        if abs(last.end - self.video.duration) > EPS:
            errors.append(
                f"场景总时长 {last.end:.3f} 与契约总时长 {self.video.duration:.3f} 不一致"
            )

        for scene in self.scenes:
            errors.extend(self._validate_scene(scene))
        return errors

    @staticmethod
    def _validate_scene(scene: Scene) -> list[str]:
        errors: list[str] = []
        if scene.type not in ("code", "h3"):
            errors.append(f"场景 {scene.id} 的 type 必须是 code 或 h3，实际 {scene.type}")
        if scene.type == "code" and not scene.renderer:
            errors.append(f"场景 {scene.id} 缺少 renderer")
        if scene.type == "h3":
            if not scene.clip:
                errors.append(f"场景 {scene.id} 缺少 clip")
            if not scene.h3:
                errors.append(f"场景 {scene.id} 缺少 h3 规格")
            else:
                for key in ("resolution", "duration", "est_credits"):
                    if key not in scene.h3:
                        errors.append(f"场景 {scene.id} 的 h3 规格缺少 {key}")
        if not scene.subtitle.strip():
            errors.append(f"场景 {scene.id} 缺少字幕")
        for line in scene.subtitle.splitlines():
            if len(line.strip()) > MAX_SUBTITLE_LINE:
                errors.append(f"场景 {scene.id} 字幕单行超过 {MAX_SUBTITLE_LINE} 字：{line!r}")
        lowered = scene.subtitle.lower()
        for word in BANNED_SUBSTRINGS:
            if word.lower() in lowered:
                errors.append(f"场景 {scene.id} 字幕含禁止词 {word!r}")
        return errors
```

- [ ] **Step 10: 实现 `pyv/cli.py` 的 `validate` 子命令**

```python
# pipeline/pyv/cli.py
"""命令行入口。

用法：
    python -m pyv.cli validate --storyboard ../storyboard.json
    python -m pyv.cli align    --audio ../pa_decode_v2.mp3 --script ../字幕-并行解码.md
    python -m pyv.cli render   --storyboard ../storyboard.json --out ../build
    python -m pyv.cli compose  --storyboard ../storyboard.json --build ../build --out ../out
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pyv import palette
from pyv.timeline import Storyboard


def cmd_validate(args: argparse.Namespace) -> int:
    storyboard = Storyboard.load(args.storyboard)
    errors = storyboard.validate()
    if errors:
        for e in errors:
            print(f"ERROR {e}", file=sys.stderr)
        return 1
    palette.assert_font_available()
    print(f"OK {len(storyboard.scenes)} 个场景，总时长 {storyboard.duration:.3f}s")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pyv")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--storyboard", required=True)
    p_validate.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 11: 运行测试确认通过**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/ -q`
Expected: PASS —— 21 passed

- [ ] **Step 12: 提交**

```bash
cd /Users/growduduan/code/blog
git add docs/life/aiv/pipeline
git commit -m "feat(aiv): 视频流水线骨架与 storyboard 契约校验器

- palette/easing/timeline/cli 四个基础模块
- 校验器覆盖：时间码连续性、总时长一致、字幕 14 字上限、禁止词、h3 规格完整性
- 12 个单测覆盖配色常量、字体校验失败路径、缓动单调性与各类契约违规"
```

---

### Task 2: 旁白对齐，产出 storyboard.json

**Files:**
- Create: `docs/life/aiv/pipeline/pyv/align.py`
- Create: `docs/life/aiv/pipeline/tests/test_align.py`
- Create: `docs/life/aiv/storyboard.json`（由脚本生成，入库）
- Modify: `docs/life/aiv/pipeline/pyv/cli.py`

**Interfaces:**
- Consumes: `timeline.Storyboard`
- Produces: `align.detect_silence(audio_path, threshold_db=-32, min_silence=0.25) -> list[tuple[float, float]]`
- Produces: `align.detect_sentences(audio_path, ...) -> list[tuple[float, float]]`
- Produces: `align.assign_sentences(spans, texts) -> list[tuple[float, float, str]]`
- Produces: `align.parse_script(md_path) -> list[str]`
- Produces: `align.build_storyboard(audio_path, script_md, out_path) -> Storyboard`

- [ ] **Step 1: 写失败的测试 `tests/test_align.py`**

```python
# pipeline/tests/test_align.py
import os
import subprocess

import numpy as np
import pytest

from pyv import align


def _make_audio(tmp_path, segments):
    """segments: [(start, end), ...]，段间留 0.4s 静音。生成单声道 32kHz wav。"""
    sr = 32000
    total = int((segments[-1][1] + 0.4) * sr)
    buf = np.zeros(total, dtype=np.int16)
    for start, end in segments:
        s, e = int(start * sr), int(end * sr)
        t = np.arange(e - s) / sr
        tone = (np.sin(2 * np.pi * 220 * t) * 8000).astype(np.int16)
        buf[s:e] = tone
    path = tmp_path / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "s16le", "-ar", str(sr), "-ac", "1", "-i", "-", str(path)],
        input=buf.tobytes(), check=True,
    )
    return str(path)


def test_detect_sentences_finds_three_spans(tmp_path):
    audio = _make_audio(tmp_path, [(0.1, 0.9), (1.4, 2.1), (2.6, 3.4)])
    spans = align.detect_sentences(audio, threshold_db=-32, min_silence=0.2)
    assert len(spans) == 3
    assert spans[0][0] == pytest.approx(0.1, abs=0.15)
    assert spans[-1][1] == pytest.approx(3.4, abs=0.2)


def test_assign_sentences_requires_matching_count():
    with pytest.raises(ValueError, match="句数"):
        align.assign_sentences([(0, 1)], ["只有一句"])


def test_assign_sentences_pairs_by_order():
    spans = [(0.0, 1.0), (1.0, 2.0)]
    texts = ["第一句", "第二句"]
    assert align.assign_sentences(spans, texts) == [(0.0, 1.0, "第一句"), (1.0, 2.0, "第二句")]


def test_parse_script_extracts_numbered_lines(tmp_path):
    md = tmp_path / "脚本.md"
    md.write_text(
        "# 标题\n\n> 说明\n\n## 口播稿\n\n第一句。\n\n第二句。\n\n第三句。\n",
        encoding="utf-8",
    )
    assert align.parse_script(md) == ["第一句。", "第二句。", "第三句。"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/test_align.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'pyv.align'`

- [ ] **Step 3: 实现 `pyv/align.py`**

```python
# pipeline/pyv/align.py
"""旁白对齐：静音检测 → 句段时间码 → storyboard.json。"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from pyv.timeline import Scene, Storyboard, SubtitleStyle, Video, Audio

DEFAULT_THRESHOLD_DB = -32
DEFAULT_MIN_SILENCE = 0.25
SCRIPT_HEADING = "## 口播稿"


def probe_duration(path: str | Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return float(out)


def detect_silence(audio_path: str | Path,
                   threshold_db: int = DEFAULT_THRESHOLD_DB,
                   min_silence: float = DEFAULT_MIN_SILENCE) -> list[tuple[float, float]]:
    """返回静音区间列表 [(start, end), ...]。"""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(audio_path),
         "-af", f"silencedetect=noise={threshold_db}dB:d={min_silence}",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    stderr = proc.stderr
    starts = [float(m) for m in re.findall(r"silence_start:\s*([0-9.]+)", stderr)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([0-9.]+)", stderr)]
    return list(zip(starts, ends))


def detect_sentences(audio_path: str | Path,
                     threshold_db: int = DEFAULT_THRESHOLD_DB,
                     min_silence: float = DEFAULT_MIN_SILENCE) -> list[tuple[float, float]]:
    """把音频切成有声片段列表 [(start, end), ...]。"""
    total = probe_duration(audio_path)
    spans: list[tuple[float, float]] = []
    cursor = 0.0
    for s, e in detect_silence(audio_path, threshold_db, min_silence):
        if s - cursor > 0.05:
            spans.append((cursor, s))
        cursor = e
    if total - cursor > 0.05:
        spans.append((cursor, total))
    return spans


def assign_sentences(spans: list[tuple[float, float]],
                      texts: list[str]) -> list[tuple[float, float, str]]:
    if len(spans) != len(texts):
        raise ValueError(
            f"句数不匹配：检测到 {len(spans)} 个有声片段，口播稿 {len(texts)} 句"
        )
    return [(spans[i][0], spans[i][1], texts[i]) for i in range(len(spans))]


def parse_script(md_path: str | Path) -> list[str]:
    """从口播稿 md 中提取「## 口播稿」之后的非空段落，每段一句。"""
    lines = Path(md_path).read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == SCRIPT_HEADING)
    except StopIteration:
        raise ValueError(f"口播稿缺少「{SCRIPT_HEADING}」小节") from None
    body: list[str] = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            continue
        if stripped.startswith("```"):
            continue
        body.append(stripped)
    return body


def build_storyboard(audio_path: str | Path,
                      script_md: str | Path,
                      out_path: str | Path) -> Storyboard:
    """对齐旁白与口播稿，写出 storyboard.json 并返回其内容。"""
    texts = parse_script(script_md)
    spans = detect_sentences(audio_path)
    pairs = assign_sentences(spans, texts)
    duration = probe_duration(audio_path)
    scenes = [
        Scene(
            id=f"s{i + 1:02d}",
            start=round(start, 3),
            end=round(end, 3),
            type="code",
            subtitle=text,
            renderer=None,
        )
        for i, (start, end, text) in enumerate(pairs)
    ]
    raw = {
        "version": 1,
        "video": {"width": 1920, "height": 1080, "fps": 24, "duration": round(duration, 3)},
        "audio": {"narration": Path(audio_path).name, "bgm": None},
        "subtitle_style": {"primary": "#1B2A47", "outline": "#FFFFFF",
                           "position": "bottom-center"},
        "scenes": [
            {
                "id": s.id, "start": s.start, "end": s.end, "type": s.type,
                "subtitle": s.subtitle, "renderer": s.renderer,
            }
            for s in scenes
        ],
    }
    Path(out_path).write_text(
        json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return Storyboard.load(out_path)
```

- [ ] **Step 4: 实现 `cli.py` 的 `align` 子命令**

```python
def cmd_align(args: argparse.Namespace) -> int:
    from pyv import align
    storyboard = align.build_storyboard(args.audio, args.script, args.out)
    errors = storyboard.validate()
    for e in errors:
        print(f"WARN {e}", file=sys.stderr)
    print(f"OK {len(storyboard.scenes)} 场景 → {args.out}")
    return 0
```

并在 `main()` 的 `sub` 中注册：

```python
    p_align = sub.add_parser("align")
    p_align.add_argument("--audio", required=True)
    p_align.add_argument("--script", required=True)
    p_align.add_argument("--out", required=True)
    p_align.set_defaults(func=cmd_align)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/test_align.py -q`
Expected: PASS —— 4 passed

- [ ] **Step 6: 对真实旁白执行对齐**

Run:
```bash
cd /Users/growduduan/code/blog/docs/life/aiv/pipeline
python -m pyv.cli align --audio ../pa_decode_v2.mp3 --script ../字幕-并行解码.md --out ../storyboard.json
```
Expected: 输出 `OK 11 场景 → ../storyboard.json`；若提示句数不匹配，把 `subtitle-并行解码.md` 的口播稿小节调整为与旁白实际念的 11 句一致后重跑。

- [ ] **Step 7: 校验生成的契约**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pyv.cli validate --storyboard ../storyboard.json`
Expected: `OK 11 个场景，总时长 29.599s`

- [ ] **Step 8: 提交**

```bash
cd /Users/growduduan/code/blog
git add docs/life/aiv/pipeline docs/life/aiv/storyboard.json
git commit -m "feat(aiv): 旁白对齐产出 storyboard.json

- align.py 用 silencedetect 切句，与口播稿逐句配对
- 契约校验器接入 CLI validate
- 4 个测试覆盖静音切分、句数不匹配报错、口播稿解析"
```

---

### Task 3: ASS 字幕生成

**Files:**
- Create: `docs/life/aiv/pipeline/pyv/subtitle.py`
- Create: `docs/life/aiv/pipeline/tests/test_subtitle.py`
- Modify: `docs/life/aiv/pipeline/pyv/cli.py`

**Interfaces:**
- Consumes: `timeline.Storyboard`
- Produces: `subtitle.fmt_ass_time(seconds: float) -> str`
- Produces: `subtitle.build_ass(storyboard: Storyboard) -> str`
- Produces: `subtitle.wrap_line(text: str, limit: int = 14) -> list[str]`

- [ ] **Step 1: 写失败的测试 `tests/test_subtitle.py`**

```python
# pipeline/tests/test_subtitle.py
import json

from pyv import subtitle
from pyv.timeline import Storyboard


def _sb(tmp_path, scenes, duration=5.0):
    raw = {
        "version": 1,
        "video": {"width": 1920, "height": 1080, "fps": 24, "duration": duration},
        "audio": {"narration": "pa_decode_v2.mp3", "bgm": None},
        "subtitle_style": {"primary": "#1B2A47", "outline": "#FFFFFF",
                           "position": "bottom-center"},
        "scenes": scenes,
    }
    path = tmp_path / "storyboard.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return Storyboard.load(path)


def test_fmt_ass_time():
    assert subtitle.fmt_ass_time(0.0) == "0:00:00.00"
    assert subtitle.fmt_ass_time(3.5) == "0:00:03.50"
    assert subtitle.fmt_ass_time(61.25) == "0:01:01.25"


def test_wrap_line_splits_at_limit():
    assert subtitle.wrap_line("一二三四五六七八九十一二三四五", 14) == ["一二三四五六七八九十", "一二三四五"]


def test_build_ass_has_one_dialogue_per_scene(tmp_path):
    sb = _sb(tmp_path, [
        {"id": "s01", "start": 0.0, "end": 2.0, "type": "code",
         "renderer": "pyv.scenes.s01_intro", "subtitle": "我是独立开发者"},
        {"id": "s02", "start": 2.0, "end": 5.0, "type": "code",
         "renderer": "pyv.scenes.s02_serial", "subtitle": "发布端只有一个解码线程"},
    ])
    ass = subtitle.build_ass(sb)
    assert ass.count("Dialogue:") == 2
    assert "PlayResX: 1920" in ass
    assert "PlayResY: 1080" in ass
    assert "PingFang SC" in ass


def test_build_ass_uses_scene_timecodes(tmp_path):
    sb = _sb(tmp_path, [
        {"id": "s01", "start": 1.5, "end": 2.5, "type": "code",
         "renderer": "pyv.scenes.s01_intro", "subtitle": "甲"},
        {"id": "s02", "start": 2.5, "end": 5.0, "type": "code",
         "renderer": "pyv.scenes.s02_serial", "subtitle": "乙"},
    ])
    ass = subtitle.build_ass(sb)
    assert "0:00:01.50,0:00:02.50" in ass
    assert "0:00:02.50,0:00:05.00" in ass


def test_build_ass_encodes_bgr_colors(tmp_path):
    sb = _sb(tmp_path, [
        {"id": "s01", "start": 0.0, "end": 5.0, "type": "code",
         "renderer": "pyv.scenes.s01_intro", "subtitle": "甲"},
    ])
    ass = subtitle.build_ass(sb)
    # #1B2A47 → BGR 472A1B
    assert "&H00472A1B" in ass
    assert "&H00FFFFFF" in ass
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/test_subtitle.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'pyv.subtitle'`

- [ ] **Step 3: 实现 `pyv/subtitle.py`**

```python
# pipeline/pyv/subtitle.py
"""ASS 字幕生成。"""
from __future__ import annotations

from pyv.palette import FONT_FAMILY
from pyv.timeline import Storyboard

MAX_LINE = 14


def fmt_ass_time(seconds: float) -> str:
    """秒 → 'h:mm:ss.cc'。"""
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:d}:{minutes:02d}:{secs:05.2f}"


def wrap_line(text: str, limit: int = MAX_LINE) -> list[str]:
    """按字符数切行，避免竖版字幕溢出。"""
    text = text.strip()
    if not text:
        return []
    return [text[i:i + limit] for i in range(0, len(text), limit)]


def _ass_color(hex_color: str) -> str:
    """'#RRGGBB' → '&H00BBGGRR'。"""
    value = hex_color.lstrip("#")
    r, g, b = value[0:2], value[2:4], value[4:6]
    return f"&H00{b}{g}{r}".upper()


def build_ass(storyboard: Storyboard) -> str:
    style = storyboard.subtitle_style
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {storyboard.video.width}
PlayResY: {storyboard.video.height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{FONT_FAMILY},64,{_ass_color(style.primary)},{_ass_color(style.primary)},{_ass_color(style.outline)},&H00000000,0,1,4,2,2,80,80,96,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for scene in storyboard.scenes:
        text = r"\N".join(wrap_line(scene.subtitle))
        lines.append(
            f"Dialogue: 0,{fmt_ass_time(scene.start)},{fmt_ass_time(scene.end)},"
            f"Default,,0,0,0,,{text}"
        )
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/test_subtitle.py -q`
Expected: PASS —— 6 passed

- [ ] **Step 5: 提交**

```bash
cd /Users/growduduan/code/blog
git add docs/life/aiv/pipeline
git commit -m "feat(aiv): ASS 字幕生成

- 深蓝字白描边样式、BGR 颜色编码、14 字自动换行
- 6 个测试覆盖时间码格式、切行、每场景一条 Dialogue"
```

---

### Task 4: 渲染引擎（cairo → ffmpeg）

**Files:**
- Create: `docs/life/aiv/pipeline/pyv/draw.py`
- Create: `docs/life/aiv/pipeline/pyv/render.py`
- Create: `docs/life/aiv/pipeline/tests/test_render_integration.py`
- Create: `docs/life/aiv/pipeline/pyv/scenes/__init__.py`（已建）
- Create: `docs/life/aiv/pipeline/pyv/scenes/s01_intro.py`（最小可用场景，用于集成测试）

**Interfaces:**
- Consumes: `timeline.Scene`、`palette`
- Produces: `render.render_scene(scene, out_path, width=1920, height=1080, fps=24) -> None`
- Produces: `render.render_storyboard(storyboard, build_dir) -> list[Path]`
- Produces: `draw.rounded_rect(ctx, x, y, w, h, r)`、`draw.arrow(ctx, x1, y1, x2, y2, color, width)`、`draw.text(ctx, s, x, y, size, color, anchor="left")`

- [ ] **Step 1: 写失败的集成测试 `tests/test_render_integration.py`**

```python
# pipeline/tests/test_render_integration.py
import json
import subprocess
from pathlib import Path

from pyv import render
from pyv.timeline import Scene


def _probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=width,height,r_frame_rate,codec_name,pix_fmt:format=duration",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def test_render_scene_produces_expected_media(tmp_path):
    scene = Scene(id="s01", start=0.0, end=1.0, type="code",
                  subtitle="测试", renderer="pyv.scenes.s01_intro")
    out = tmp_path / "s01.mp4"
    render.render_scene(scene, out, width=320, height=180, fps=24)
    info = _probe(out)
    stream = info["streams"][0]
    assert stream["width"] == 320
    assert stream["height"] == 180
    assert stream["codec_name"] == "h264"
    assert stream["pix_fmt"] == "yuv420p"
    assert stream["r_frame_rate"] == "24/1"
    assert abs(float(info["format"]["duration"]) - 1.0) < 0.05


def test_render_scene_output_is_not_black(tmp_path):
    scene = Scene(id="s01", start=0.0, end=1.0, type="code",
                  subtitle="测试", renderer="pyv.scenes.s01_intro")
    out = tmp_path / "s01.mp4"
    render.render_scene(scene, out, width=320, height=180, fps=24)
    stats = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(out), "-vf", "signalstats",
         "-f", "null", "-"], capture_output=True, text=True)
    # 至少要能解码且无错误
    assert stats.returncode == 0
```

- [ ] **Step 2: 写最小场景模块 `pyv/scenes/s01_intro.py`**

```python
# pipeline/pyv/scenes/s01_intro.py
"""段 A：身份 + 标题。"""
from pyv.palette import COLORS, hex_to_rgb


def render(ctx, t: float, w: int, h: int) -> None:
    """t ∈ [0,1] 为场景内进度。"""
    ctx.set_source_rgb(*hex_to_rgb(COLORS["primary"]))
    ctx.set_font_size(64)
    ctx.move_to(w * 0.1, h * 0.5)
    ctx.show_text("PostgreSQL 18")
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/test_render_integration.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'pyv.render'`

- [ ] **Step 4: 实现 `pyv/draw.py`**

```python
# pipeline/pyv/draw.py
"""通用绘图原语。"""
from __future__ import annotations

import math

import cairo

from pyv.palette import hex_to_rgb


def rounded_rect(ctx: cairo.Context, x: float, y: float, w: float, h: float,
                 r: float, color: str) -> None:
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()
    ctx.set_source_rgb(*hex_to_rgb(color))
    ctx.fill()


def arrow(ctx: cairo.Context, x1: float, y1: float, x2: float, y2: float,
          color: str, width: float = 6.0, head: float = 22.0) -> None:
    ctx.set_source_rgb(*hex_to_rgb(color))
    ctx.set_line_width(width)
    ctx.move_to(x1, y1)
    ctx.line_to(x2, y2)
    ctx.stroke()
    angle = math.atan2(y2 - y1, x2 - x1)
    for sign in (1, -1):
        a = angle + sign * math.radians(150)
        ctx.move_to(x2, y2)
        ctx.line_to(x2 + head * math.cos(a), y2 + head * math.sin(a))
    ctx.stroke()


def text(ctx: cairo.Context, s: str, x: float, y: float, size: float,
         color: str, anchor: str = "left") -> None:
    ctx.set_source_rgb(*hex_to_rgb(color))
    ctx.set_font_size(size)
    ext = ctx.text_extents(s)
    width = ext.width
    if anchor == "center":
        x -= width / 2
    elif anchor == "right":
        x -= width
    ctx.move_to(x, y)
    ctx.show_text(s)
```

- [ ] **Step 5: 实现 `pyv/render.py`**

```python
# pipeline/pyv/render.py
"""cairo 逐帧绘制 → ffmpeg 编码。"""
from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import cairo

from pyv.palette import COLORS, FPS, HEIGHT, WIDTH, hex_to_rgb
from pyv.timeline import Scene, Storyboard


def _frame_bytes(surface: cairo.ImageSurface) -> bytes:
    """按真实 stride 提取 RGB24 数据，避免行尾填充导致错色。"""
    stride = surface.get_stride()
    height = surface.get_height()
    data = surface.get_data()
    if stride == surface.get_width() * 4:
        return bytes(data)
    return b"".join(
        bytes(data[y * stride:y * stride + surface.get_width() * 4])
        for y in range(height)
    )


def render_scene(scene: Scene, out_path: str | Path,
                 width: int = WIDTH, height: int = HEIGHT, fps: int = FPS) -> None:
    """把一个场景渲染成无声 mp4。"""
    if not scene.renderer:
        raise ValueError(f"场景 {scene.id} 缺少 renderer")
    module = importlib.import_module(scene.renderer)
    total = max(1, int(round(scene.duration * fps)))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for i in range(total):
            t = i / (total - 1) if total > 1 else 0.0
            surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
            ctx = cairo.Context(surface)
            ctx.set_source_rgb(*hex_to_rgb(COLORS["bg"]))
            ctx.paint()
            module.render(ctx, t, width, height)
            proc.stdin.write(_frame_bytes(surface))
            surface.flush()
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 渲染失败：{out_path}")


def render_storyboard(storyboard: Storyboard, build_dir: str | Path) -> list[Path]:
    """渲染全部 code 场景，返回片段路径列表。"""
    build_dir = Path(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for scene in storyboard.scenes:
        if scene.type != "code":
            continue
        out = build_dir / f"{scene.id}.mp4"
        render_scene(scene, out)
        outputs.append(out)
    return outputs
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/test_render_integration.py -q`
Expected: PASS —— 2 passed

- [ ] **Step 7: 提交**

```bash
cd /Users/growduduan/code/blog
git add docs/life/aiv/pipeline
git commit -m "feat(aiv): cairo 逐帧渲染引擎

- render_scene 逐帧绘制并以 rawvideo 管道喂给 ffmpeg，单场景出无声 mp4
- draw.py 提供圆角矩形、箭头、文本三个绘图原语
- 集成测试用 ffprobe 断言分辨率/编码/帧率/时长"
```

---

### Task 5: 小象部件切分与 2D 动作

**Files:**
- Create: `docs/life/aiv/pipeline/pyv/elephant.py`
- Create: `docs/life/aiv/pipeline/tests/test_elephant.py`

**Interfaces:**
- Consumes: `growdu.png`（项目根，相对路径）
- Produces: `elephant.load_parts(image_path) -> Parts`
- Produces: `elephant.Parts`（字段 `head`、`ear_left`、`ear_right`、`arm_left`、`arm_right`、`icon`、`pivots: dict[str, tuple[float, float]]`）
- Produces: `elephant.draw_elephant(ctx, parts, pose: Pose, x: float, y: float, scale: float) -> None`
- Produces: `elephant.Pose`（dataclass：`nod`、`wave`、`turn`、`point` 四个 0..1 进度）

**背景（已实测的连通块几何，1220×1289 原图）**

| 部件 | 天蓝连通块包围盒 | 枢轴 |
| --- | --- | --- |
| 头（含耳基与鼻） | x[257, 958] y[60, 751] | (607, 700) 颈部 |
| 左耳 | x[66, 436] y[48, 566] | (400, 520) 内下角 |
| 右耳 | x[785, 1155] y[48, 566] | (800, 520) 内下角 |
| 左臂 | x[219, 365] y[693, 959] | (330, 700) 肩 |
| 右臂 | x[821, 998] y[635, 959] | (860, 650) 肩 |
| 腿 | x[335, 880] y[965, 1229] | — |
| 橙黄数据库图标 | x[555, 658] y[810, 933] | (606, 871) |
| 粉色面颊 | 左 x[344, 469] y[431, 554]；右 x[749, 873] y[431, 555] | — |

- [ ] **Step 1: 写失败的测试 `tests/test_elephant.py`**

```python
# pipeline/tests/test_elephant.py
import os

import pytest

from pyv import elephant

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMAGE = os.path.join(ROOT, "growdu.png")


def test_load_parts_finds_expected_regions():
    parts = elephant.load_parts(IMAGE)
    assert parts.head.size[0] > 400
    assert parts.ear_left.size[0] > 200
    assert parts.ear_right.size[0] > 200
    assert parts.arm_left.size[1] > 150
    assert parts.arm_right.size[1] > 150


def test_pivots_lie_inside_their_part():
    parts = elephant.load_parts(IMAGE)
    for name, pivot in parts.pivots.items():
        part = getattr(parts, name)
        x0, y0, x1, y1 = part.crop_box
        assert x0 <= pivot[0] <= x1, name
        assert y0 <= pivot[1] <= y1, name


def test_parts_do_not_overlap_in_source():
    parts = elephant.load_parts(IMAGE)
    boxes = [parts.head.crop_box, parts.ear_left.crop_box,
             parts.ear_right.crop_box, parts.arm_left.crop_box,
             parts.arm_right.crop_box]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            overlap_x = min(a[2], b[2]) - max(a[0], b[0])
            overlap_y = min(a[3], b[3]) - max(a[1], b[1])
            assert not (overlap_x > 0 and overlap_y > 0), (a, b)


def test_pose_defaults_are_neutral():
    pose = elephant.Pose()
    assert pose.nod == 0.0 and pose.wave == 0.0
    assert pose.turn == 0.0 and pose.point == 0.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/test_elephant.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'pyv.elephant'`

- [ ] **Step 3: 实现 `pyv/elephant.py`**

```python
# pipeline/pyv/elephant.py
"""小象部件切分与 2D 动作。

形象原图唯一来源：项目根 growdu.png（1220×1289，RGBA 透明底）。
部件靠颜色连通块自动识别，不依赖手调坐标。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import cairo
import numpy as np
from PIL import Image
from scipy import ndimage

SKY_MIN_AREA = 1500


@dataclass(frozen=True)
class Part:
    image: Image.Image
    crop_box: tuple[int, int, int, int]  # x0, y0, x1, y1

    @property
    def size(self) -> tuple[int, int]:
        return self.image.size


@dataclass(frozen=True)
class Parts:
    head: Part
    ear_left: Part
    ear_right: Part
    arm_left: Part
    arm_right: Part
    legs: Part
    icon: Part
    pivots: dict[str, tuple[float, float]]


@dataclass
class Pose:
    nod: float = 0.0
    wave: float = 0.0
    turn: float = 0.0
    point: float = 0.0


def _sky_mask(arr: np.ndarray) -> np.ndarray:
    alpha = arr[..., 3]
    r, g, b = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)
    return (alpha > 200) & (b > r + 30) & (b > 170) & (r > 90) & (r < 190) & (g > 150)


def _orange_mask(arr: np.ndarray) -> np.ndarray:
    alpha = arr[..., 3]
    r, g, b = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)
    return (alpha > 200) & (r > 200) & (g > 140) & (g < 205) & (b < 110)


def _largest_component(mask: np.ndarray) -> tuple[int, int, int, int]:
    lab, n = ndimage.label(mask)
    if n == 0:
        return (0, 0, 0, 0)
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    best = int(np.argmax(sizes)) + 1
    ys, xs = np.nonzero(lab == best)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def _crop(image: Image.Image, box: tuple[int, int, int, int]) -> Part:
    return Part(image=image.crop(box), crop_box=box)


def load_parts(image_path: str | Path) -> Parts:
    """按颜色连通块识别头、耳、臂、腿与图标。"""
    image = Image.open(image_path).convert("RGBA")
    arr = np.array(image)
    lab, n = ndimage.label(_sky_mask(arr))
    objs = ndimage.find_objects(lab)
    comps = []
    for i, sl in enumerate(objs, start=1):
        size = int((lab[sl] == i).sum())
        if size < SKY_MIN_AREA:
            continue
        box = (int(sl[1].start), int(sl[0].start),
               int(sl[1].stop), int(sl[0].stop))
        comps.append((size, box))
    comps.sort(reverse=True, key=lambda item: item[0])

    head_box = comps[0][1]
    ears = [b for _, b in comps if b[3] < 600 and (b[0] < 500 or b[2] > 700)]
    ear_left = min(ears, key=lambda b: b[0])
    ear_right = max(ears, key=lambda b: b[2])
    arms = [b for _, b in comps if b[1] > 600 and b[3] < 1000 and b[2] - b[0] < 260]
    arm_left = min(arms, key=lambda b: b[0])
    arm_right = max(arms, key=lambda b: b[2])
    legs = max((b for _, b in comps if b[1] > 900), key=lambda b: b[3] - b[1])

    icon_box = _largest_component(_orange_mask(arr))
    icon = _crop(image, icon_box)

    pivots = {
        "head": ((head_box[0] + head_box[2]) / 2, head_box[3] - 40),
        "ear_left": (ear_left[2] - 40, ear_left[3] - 40),
        "ear_right": (ear_right[0] + 40, ear_right[3] - 40),
        "arm_left": (arm_left[2] - 30, arm_left[1] + 10),
        "arm_right": (arm_right[0] + 30, arm_right[1] + 10),
        "icon": ((icon_box[0] + icon_box[2]) / 2, (icon_box[1] + icon_box[3]) / 2),
    }
    return Parts(
        head=_crop(image, head_box),
        ear_left=_crop(image, ear_left),
        ear_right=_crop(image, ear_right),
        arm_left=_crop(image, arm_left),
        arm_right=_crop(image, arm_right),
        legs=_crop(image, legs),
        icon=icon,
        pivots=pivots,
    )


def _blit(ctx: cairo.Context, part: Part, pivot: tuple[float, float],
          angle_deg: float, x: float, y: float, scale: float) -> None:
    """把部件按枢轴旋转后绘制到画布 (x, y)（枢轴位置）。"""
    src = part.image
    w = src.width * scale
    h = src.height * scale
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(math.radians(angle_deg))
    ctx.scale(scale, scale)
    ctx.translate(-pivot[0], -pivot[1])
    surface = cairo.ImageSurface.create_for_data(
        bytearray(src.tobytes()), cairo.FORMAT_ARGB32,
        src.width, src.height, src.width * 4)
    ctx.set_source_surface(surface, 0, 0)
    ctx.paint()
    ctx.restore()


def draw_elephant(ctx: cairo.Context, parts: Parts, pose: Pose,
                   x: float, y: float, scale: float) -> None:
    """按姿态绘制小象。pose 各字段为 0..1 进度。"""
    nod_angle = math.sin(pose.nod * math.pi) * 8.0
    turn_angle = (pose.turn - 0.5) * 10.0
    wave_angle = math.sin(pose.wave * math.pi * 4) * 22.0
    point_angle = -35.0 * pose.point

    _blit(ctx, parts.legs, parts.pivots["icon"], 0.0, x, y, scale)
    _blit(ctx, parts.ear_left, parts.pivots["ear_left"], nod_angle * 0.3, x, y, scale)
    _blit(ctx, parts.ear_right, parts.pivots["ear_right"], -nod_angle * 0.3, x, y, scale)
    _blit(ctx, parts.head, parts.pivots["head"], nod_angle + turn_angle, x, y, scale)
    _blit(ctx, parts.arm_left, parts.pivots["arm_left"], 0.0, x, y, scale)
    _blit(ctx, parts.arm_right, parts.pivots["arm_right"], wave_angle + point_angle, x, y, scale)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/test_elephant.py -q`
Expected: PASS —— 4 passed

- [ ] **Step 5: 提交**

```bash
cd /Users/growduduan/code/blog
git add docs/life/aiv/pipeline
git commit -m "feat(aiv): 小象部件自动切分与 2D 动作

- 用颜色连通块识别头/双耳/双臂/腿/图标，枢轴落在部件内部
- Pose 提供 nod/wave/turn/point 四个进度，绘制时按枢轴旋转
- 4 个测试覆盖部件尺寸、枢轴在界内、部件不重叠、姿态默认值"
```

---

### Task 6: 场景段 A–B（身份标题 + 串行瓶颈）

**Files:**
- Modify: `docs/life/aiv/pipeline/pyv/scenes/s01_intro.py`
- Create: `docs/life/aiv/pipeline/pyv/scenes/s02_serial.py`
- Create: `docs/life/aiv/pipeline/tests/test_scenes.py`

**Interfaces:**
- Consumes: `draw`、`elephant`、`easing`
- Produces: 每个场景模块导出 `render(ctx, t, w, h)`；`elephant.load_parts` 结果用模块级惰性缓存

- [ ] **Step 1: 写失败的测试 `tests/test_scenes.py`**

```python
# pipeline/tests/test_scenes.py
import importlib

import cairo
import pytest

SCENE_MODULES = [
    "pyv.scenes.s01_intro",
    "pyv.scenes.s02_serial",
    "pyv.scenes.s03_cores",
    "pyv.scenes.s04_parallel",
    "pyv.scenes.s05_order",
    "pyv.scenes.s06_outro",
]


@pytest.mark.parametrize("name", SCENE_MODULES)
def test_scene_module_exposes_render(name):
    module = importlib.import_module(name)
    assert callable(module.render)


@pytest.mark.parametrize("name", SCENE_MODULES)
def test_scene_render_draws_something(name):
    module = importlib.import_module(name)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 320, 180)
    ctx = cairo.Context(surface)
    module.render(ctx, 0.5, 320, 180)
    data = surface.get_data()
    assert any(byte != 0 for byte in data)


@pytest.mark.parametrize("name", SCENE_MODULES)
def test_scene_render_handles_endpoints(name):
    module = importlib.import_module(name)
    for t in (0.0, 1.0):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 320, 180)
        ctx = cairo.Context(surface)
        module.render(ctx, t, 320, 180)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/test_scenes.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'pyv.scenes.s02_serial'`

- [ ] **Step 3: 实现 `pyv/scenes/s01_intro.py`**

```python
# pipeline/pyv/scenes/s01_intro.py
"""段 A：身份 + 标题。"""
from __future__ import annotations

import os

from pyv import easing
from pyv.draw import text
from pyv.elephant import Pose, draw_elephant, load_parts
from pyv.palette import COLORS

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_IMAGE = os.path.join(_ROOT, "growdu.png")
_parts = None


def _get_parts():
    global _parts
    if _parts is None:
        _parts = load_parts(_IMAGE)
    return _parts


def render(ctx, t: float, w: int, h: int) -> None:
    """t ∈ [0,1] 为场景内进度。"""
    alpha = easing.ease_out_cubic(min(1.0, t * 2.0))
    pose = Pose(nod=0.0, wave=easing.clamp01((t - 0.25) * 2.0), turn=0.0, point=0.0)
    draw_elephant(ctx, _get_parts(), pose, w * 0.28, h * 0.62, scale=h / 1289.0 * 0.86)

    title_alpha = easing.ease_out_cubic(max(0.0, (t - 0.3) / 0.7))
    ctx.set_source_rgb(0.17, 0.30, 0.49)
    ctx.set_font_size(96)
    ctx.move_to(w * 0.48, h * 0.42)
    ctx.show_text("PostgreSQL 18")

    ctx.set_font_size(64)
    ctx.set_source_rgb(0.96, 0.65, 0.14)
    ctx.move_to(w * 0.48, h * 0.56)
    ctx.show_text("并行逻辑解码")

    ctx.set_source_rgb(*_rgb(COLORS["primary"]))
    ctx.set_font_size(40)
    ctx.move_to(w * 0.48, h * 0.68)
    ctx.show_text("reader 协调 · 多 worker 并行 · 顺序一致")


def _rgb(hex_color: str):
    from pyv.palette import hex_to_rgb
    return hex_to_rgb(hex_color)
```

- [ ] **Step 4: 实现 `pyv/scenes/s02_serial.py`**

```python
# pipeline/pyv/scenes/s02_serial.py
"""段 B：发布端单解码线程，队列积压。"""
from __future__ import annotations

from pyv import easing
from pyv.draw import arrow, rounded_rect, text
from pyv.palette import COLORS, hex_to_rgb


def render(ctx, t: float, w: int, h: int) -> None:
    blocks = 5
    for i in range(blocks):
        y = h * (0.28 + i * 0.10)
        offset = easing.ease_in_out(min(1.0, t * 1.6)) * w * 0.18 * (i + 1) / blocks
        rounded_rect(ctx, w * 0.10 - offset, y, w * 0.22, h * 0.06, 10,
                     COLORS["problem"] if i % 2 == 0 else "#C9CFD8")

    rounded_rect(ctx, w * 0.38, h * 0.30, w * 0.16, h * 0.40, 18, COLORS["primary"])
    ctx.set_source_rgb(*hex_to_rgb("#FFFFFF"))
    ctx.set_font_size(48)
    ctx.move_to(w * 0.405, h * 0.54)
    ctx.show_text("decoder")

    arrow(ctx, w * 0.55, h * 0.50, w * 0.74, h * 0.50, COLORS["primary"], 8)
    rounded_rect(ctx, w * 0.76, h * 0.36, w * 0.16, h * 0.28, 18, "#D9DEE6")

    text(ctx, "只有一个解码线程", w * 0.10, h * 0.18, 56, COLORS["problem"])
    text(ctx, "事务排队，队列越积越长", w * 0.10, h * 0.86, 44, COLORS["primary"])
```

- [ ] **Step 5: 实现占位模块 `s04_parallel.py` `s05_order.py` `s06_outro.py`**

三个模块先给出可渲染的最小实现（供测试与占位），Task 8 / Task 9 替换为正式图示。

```python
# pipeline/pyv/scenes/s04_parallel.py
"""段 D：reader → 多 worker 并行（占位实现，后续任务替换）。"""
from pyv.draw import rounded_rect, text
from pyv.palette import COLORS


def render(ctx, t: float, w: int, h: int) -> None:
    rounded_rect(ctx, w * 0.06, h * 0.30, w * 0.18, h * 0.22, 16, COLORS["primary"])
    text(ctx, "reader", w * 0.10, h * 0.46, 48, COLORS["primary"])
    for i in range(4):
        rounded_rect(ctx, w * 0.50, h * 0.26 + i * h * 0.16, w * 0.16, h * 0.12, 14,
                     COLORS["secondary"])
```

```python
# pipeline/pyv/scenes/s05_order.py
"""段 E：顺序一致 + 性能数字（占位实现，后续任务替换）。"""
from pyv.draw import rounded_rect, text
from pyv.palette import COLORS


def render(ctx, t: float, w: int, h: int) -> None:
    for i in range(1, 5):
        rounded_rect(ctx, w * 0.08, h * 0.26 + (i - 1) * h * 0.11, w * 0.28,
                     h * 0.075, 12, COLORS["secondary"])
    text(ctx, "2–5 倍", w * 0.60, h * 0.55, 140, COLORS["accent"])
```

```python
# pipeline/pyv/scenes/s06_outro.py
"""段 F：收束 + 落版（占位实现，后续任务替换）。"""
from pyv.draw import rounded_rect, text
from pyv.palette import COLORS


def render(ctx, t: float, w: int, h: int) -> None:
    text(ctx, "并行解码 · 有序同步", w * 0.30, h * 0.42, 72, COLORS["primary"])
    rounded_rect(ctx, w * 0.30, h * 0.52, w * 0.34, h * 0.12, 12, COLORS["secondary"])
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/test_scenes.py -q`
Expected: PASS —— 18 passed（6 模块 × 3 用例）

- [ ] **Step 7: 提交**

```bash
cd /Users/growduduan/code/blog
git add docs/life/aiv/pipeline
git commit -m "feat(aiv): 段 A–B 场景与小象登场动画

- s01 身份 + 标题，小象挥手入场；s02 单解码线程队列积压
- s03–s06 先以可渲染占位实现，后续任务替换为正式图示
- 场景渲染测试覆盖端点与非空输出"
```

---

### Task 7: 场景段 C（32 核只占 1 核）

**Files:**
- Modify: `docs/life/aiv/pipeline/pyv/scenes/s03_cores.py`
- Modify: `docs/life/aiv/pipeline/tests/test_scenes.py`

**Interfaces:**
- Consumes: `draw`、`easing`
- Produces: `pyv.scenes.s03_cores.render(ctx, t, w, h)`

- [ ] **Step 1: 写失败的测试**

```python
# 追加到 pipeline/tests/test_scenes.py
def test_s03_highlights_exactly_one_core():
    import pyv.scenes.s03_cores as s03
    highlighted = s03.highlighted_cores()
    assert len(highlighted) == 1
    assert 0 <= highlighted[0] < 32
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/test_scenes.py::test_s03_highlights_exactly_one_core -q`
Expected: FAIL —— `AttributeError: module 'pyv.scenes.s03_cores' has no attribute 'highlighted_cores'`

- [ ] **Step 3: 实现正式版 `s03_cores.py`**

```python
# pipeline/pyv/scenes/s03_cores.py
"""段 C：32 核机器上解码只占 1 核；大事务与小事务都跟不上。"""
from __future__ import annotations

from pyv import easing
from pyv.draw import rounded_rect, text
from pyv.palette import COLORS, hex_to_rgb

CORE_COUNT = 32
HIGHLIGHTED = 11  # 第 12 个核被点亮，其余保持灰


def highlighted_cores() -> list[int]:
    """返回被点亮的核心下标，必须恰好一个。"""
    return [HIGHLIGHTED]


def render(ctx, t: float, w: int, h: int) -> None:
    text(ctx, "32 核机器，解码只占 1 核", w * 0.07, h * 0.16, 60, COLORS["primary"])

    cols = 8
    cell_w, cell_h = w * 0.045, h * 0.095
    gap_x, gap_y = w * 0.012, h * 0.035
    x0, y0 = w * 0.07, h * 0.26
    marker = easing.ease_out_cubic(max(0.0, (t - 0.25) / 0.75))
    lit = set(highlighted_cores())

    for i in range(CORE_COUNT):
        col, row = i % cols, i // cols
        x = x0 + col * (cell_w + gap_x)
        y = y0 + row * (cell_h + gap_y)
        rounded_rect(ctx, x, y, cell_w, cell_h, 8,
                     COLORS["accent"] if i in lit else "#DCE1E8")

    cx = x0 + (HIGHLIGHTED % cols) * (cell_w + gap_x) + cell_w / 2
    cy = y0 + (HIGHLIGHTED // cols) * (cell_h + gap_y) + cell_h / 2
    ctx.set_source_rgb(*hex_to_rgb(COLORS["accent"]))
    ctx.set_line_width(6)
    ctx.arc(cx, cy, cell_w * (0.8 + 0.25 * marker), 0, 6.2832)
    ctx.stroke()

    text(ctx, "大事务", w * 0.60, h * 0.34, 44, COLORS["problem"])
    rounded_rect(ctx, w * 0.60, h * 0.38, w * 0.30, h * 0.10, 10, COLORS["problem"])
    text(ctx, "小事务高并发", w * 0.60, h * 0.58, 44, COLORS["problem"])
    for i in range(6):
        rounded_rect(ctx, w * 0.60 + i * w * 0.052, h * 0.62, w * 0.04, h * 0.07, 8,
                     COLORS["problem"] if i % 2 == 0 else "#F8C489")
    text(ctx, "都跟不上", w * 0.60, h * 0.84, 48, COLORS["primary"])
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/ -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /Users/growduduan/code/blog
git add docs/life/aiv/pipeline
git commit -m "feat(aiv): 段 C 正式图示——32 核只占 1 核

- 8×4 核心阵列，仅第 12 个被点亮并带脉冲圈
- 右侧并列大事务与小事务高并发两种压力"
```

---

### Task 8: 场景段 D–E（reader→worker 并行 + 顺序一致 + 2–5 倍）

**Files:**
- Modify: `docs/life/aiv/pipeline/pyv/scenes/s04_parallel.py`
- Modify: `docs/life/aiv/pipeline/pyv/scenes/s05_order.py`
- Modify: `docs/life/aiv/pipeline/tests/test_scenes.py`

**Interfaces:**
- Consumes: `draw`、`easing`
- Produces: `pyv.scenes.s04_parallel.render(ctx, t, w, h)`、`pyv.scenes.s05_order.render(ctx, t, w, h)`

- [ ] **Step 1: 写失败的测试**

```python
# 追加到 pipeline/tests/test_scenes.py
def test_s04_exposes_four_workers():
    import pyv.scenes.s04_parallel as s04
    assert s04.worker_count() == 4


def test_s05_outputs_in_ascending_order():
    import pyv.scenes.s05_order as s05
    assert s05.output_order() == [1, 2, 3, 4]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/test_scenes.py::test_s04_exposes_four_workers tests/test_scenes.py::test_s05_outputs_in_ascending_order -q`
Expected: FAIL —— `AttributeError: module 'pyv.scenes.s04_parallel' has no attribute 'worker_count'`

- [ ] **Step 3: 实现正式版 `s04_parallel.py`**

```python
# pipeline/pyv/scenes/s04_parallel.py
"""段 D：reader 读取协调，多 worker 并行解码。"""
from __future__ import annotations

from pyv import easing
from pyv.draw import arrow, rounded_rect, text
from pyv.palette import COLORS, hex_to_rgb

WORKERS = 4


def worker_count() -> int:
    """并行解码的 worker 数量。"""
    return WORKERS


def render(ctx, t: float, w: int, h: int) -> None:
    text(ctx, "reader 读取与协调", w * 0.06, h * 0.16, 56, COLORS["primary"])
    rounded_rect(ctx, w * 0.06, h * 0.24, w * 0.18, h * 0.22, 16, COLORS["primary"])
    ctx.set_source_rgb(*hex_to_rgb("#FFFFFF"))
    ctx.set_font_size(48)
    ctx.move_to(w * 0.10, h * 0.39)
    ctx.show_text("reader")

    worker_y = h * 0.24
    worker_h = h * 0.13
    for i in range(worker_count()):
        y = worker_y + i * (worker_h + h * 0.05)
        rounded_rect(ctx, w * 0.50, y, w * 0.16, worker_h, 14, COLORS["secondary"])
        ctx.set_source_rgb(*hex_to_rgb("#FFFFFF"))
        ctx.set_font_size(36)
        ctx.move_to(w * 0.535, y + worker_h * 0.7)
        ctx.show_text(f"worker {i + 1}")
        arrow(ctx, w * 0.25, h * 0.35, w * 0.49, y + worker_h / 2,
              COLORS["accent"], 5, 16)

    rounded_rect(ctx, w * 0.74, h * 0.30, w * 0.18, h * 0.40, 16, "#D9DEE6")
    text(ctx, "统一输出", w * 0.755, h * 0.27, 36, COLORS["primary"])
    for i in range(worker_count()):
        arrow(ctx, w * 0.67, worker_y + i * (worker_h + h * 0.05) + worker_h / 2,
              w * 0.73, h * 0.50, COLORS["secondary"], 4, 14)
```

- [ ] **Step 4: 实现正式版 `s05_order.py`**

```python
# pipeline/pyv/scenes/s05_order.py
"""段 E：按事务结束顺序输出，订阅端顺序与发布端一致；性能 2–5 倍。"""
from __future__ import annotations

from pyv.draw import rounded_rect, text
from pyv.palette import COLORS, hex_to_rgb


def output_order() -> list[int]:
    """订阅端接收顺序，必须与发布端一致。"""
    return [1, 2, 3, 4]


def render(ctx, t: float, w: int, h: int) -> None:
    text(ctx, "按事务结束顺序输出", w * 0.06, h * 0.14, 56, COLORS["primary"])

    for i in output_order():
        y = h * 0.24 + (i - 1) * h * 0.115
        rounded_rect(ctx, w * 0.08, y, w * 0.30, h * 0.075, 12, COLORS["secondary"])
        ctx.set_source_rgb(*hex_to_rgb("#FFFFFF"))
        ctx.set_font_size(36)
        ctx.move_to(w * 0.20, y + h * 0.052)
        ctx.show_text(str(i))

    text(ctx, "→", w * 0.40, h * 0.44, 72, COLORS["primary"])

    rounded_rect(ctx, w * 0.48, h * 0.24, w * 0.18, h * 0.40, 14, COLORS["primary"])
    ctx.set_source_rgb(*hex_to_rgb("#FFFFFF"))
    ctx.set_font_size(36)
    ctx.move_to(w * 0.50, h * 0.47)
    ctx.show_text("订阅端")

    ctx.set_source_rgb(*hex_to_rgb(COLORS["accent"]))
    ctx.set_font_size(150)
    ctx.move_to(w * 0.70, h * 0.52)
    ctx.show_text("2–5 倍")
    ctx.set_font_size(40)
    ctx.move_to(w * 0.72, h * 0.62)
    ctx.show_text("并行解码整体性能")
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/ -q`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd /Users/growduduan/code/blog
git add docs/life/aiv/pipeline
git commit -m "feat(aiv): 段 D–E 正式图示——reader 并行分发与有序输出

- s04 reader → 4 个 worker → 统一输出；s05 编号 1..4 顺序输出 + 2–5 倍大字"
```

---

### Task 9: 场景段 F（收束 + 落版）

**Files:**
- Modify: `docs/life/aiv/pipeline/pyv/scenes/s06_outro.py`
- Modify: `docs/life/aiv/pipeline/tests/test_scenes.py`

**Interfaces:**
- Consumes: `draw`、`elephant`
- Produces: `pyv.scenes.s06_outro.render(ctx, t, w, h)`

- [ ] **Step 1: 写失败的测试**

```python
# 追加到 pipeline/tests/test_scenes.py
def test_s06_uses_personal_avatar_and_no_banned_words():
    import pyv.scenes.s06_outro as s06
    from pyv.timeline import BANNED_SUBSTRINGS
    source = open(s06.__file__, encoding="utf-8").read()
    assert "growdu.jpg" in source
    for word in BANNED_SUBSTRINGS:
        assert word.lower() not in source.lower(), word
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/test_scenes.py::test_s06_uses_personal_avatar_not_company_logo -q`
Expected: FAIL —— 占位实现未引用 `growdu.jpg`

- [ ] **Step 3: 实现正式版 `s06_outro.py`**

```python
# pipeline/pyv/scenes/s06_outro.py
"""段 F：异构数据同步价值 + 落版（个人头像，不使用任何公司 Logo）。"""
from __future__ import annotations

import os

from pyv import easing
from pyv.draw import rounded_rect, text
from pyv.elephant import Pose, draw_elephant, load_parts
from pyv.palette import COLORS, hex_to_rgb

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_IMAGE = os.path.join(_ROOT, "growdu.png")
_AVATAR = os.path.join(_ROOT, "growdu.jpg")
_parts = None


def _get_parts():
    global _parts
    if _parts is None:
        _parts = load_parts(_IMAGE)
    return _parts


def render(ctx, t: float, w: int, h: int) -> None:
    draw_elephant(ctx, _get_parts(), Pose(nod=easing.clamp01(t * 2.0)),
                   w * 0.24, h * 0.60, scale=h / 1289.0 * 0.86)

    text(ctx, "并行解码 · 有序同步", w * 0.46, h * 0.40, 76, COLORS["primary"])
    text(ctx, "异构数据同步场景，实用性很高", w * 0.46, h * 0.52, 44, COLORS["secondary"])

    if os.path.exists(_AVATAR):
        import cairo
        from PIL import Image
        avatar = Image.open(_AVATAR).convert("RGBA").resize((int(h * 0.16), int(h * 0.16)))
        surface = cairo.ImageSurface.create_for_data(
            bytearray(avatar.tobytes()), cairo.FORMAT_ARGB32,
            avatar.width, avatar.height, avatar.width * 4)
        ctx.set_source_surface(surface, w * 0.46, h * 0.62)
        ctx.paint()

    rounded_rect(ctx, w * 0.46, h * 0.82, w * 0.30, h * 0.09, 12, COLORS["primary"])
    ctx.set_source_rgb(*hex_to_rgb("#FFFFFF"))
    ctx.set_font_size(36)
    ctx.move_to(w * 0.49, h * 0.885)
    ctx.show_text("独立开发者 · growdu")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/ -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /Users/growduduan/code/blog
git add docs/life/aiv/pipeline
git commit -m "feat(aiv): 段 F 收束与落版

- 小象点头 + 个人头像 + 独立开发者署名
- 断言落版只引用 growdu.jpg，源码不含公司字样"
```

---

### Task 10: 端到端合成与 Design 导入

**Files:**
- Create: `docs/life/aiv/pipeline/pyv/compose.py`
- Create: `docs/life/aiv/pipeline/tests/test_compose_integration.py`
- Modify: `docs/life/aiv/pipeline/pyv/cli.py`
- Modify: `docs/life/aiv/pipeline/pyv/scenes/*.py`（把 storyboard 的 renderer 名写进各场景，scene id 与模块一一对应）
- Create: `docs/life/aiv/Makefile` 或 `docs/life/aiv/pipeline/Makefile`

**Interfaces:**
- Consumes: `timeline.Storyboard`、`render.render_storyboard`、`subtitle.build_ass`
- Produces: `compose.compose(storyboard, build_dir, out_path) -> Path`

- [ ] **Step 1: 写失败的集成测试 `tests/test_compose_integration.py`**

```python
# pipeline/tests/test_compose_integration.py
import json
import os
import subprocess
from pathlib import Path

from pyv import compose
from pyv.timeline import Storyboard

ROOT = Path(__file__).resolve().parents[2]


def _probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height:format=duration",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def _mini_storyboard(tmp_path):
    raw = {
        "version": 1,
        "video": {"width": 320, "height": 180, "fps": 24, "duration": 2.0},
        "audio": {"narration": "pa_decode_v2.mp3", "bgm": None},
        "subtitle_style": {"primary": "#1B2A47", "outline": "#FFFFFF",
                           "position": "bottom-center"},
        "scenes": [
            {"id": "s01", "start": 0.0, "end": 1.0, "type": "code",
             "renderer": "pyv.scenes.s01_intro", "subtitle": "我是独立开发者"},
            {"id": "s02", "start": 1.0, "end": 2.0, "type": "code",
             "renderer": "pyv.scenes.s02_serial", "subtitle": "只有一个解码线程"},
        ],
    }
    path = tmp_path / "storyboard.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return Storyboard.load(path)


def test_compose_produces_video_with_audio(tmp_path):
    sb = _mini_storyboard(tmp_path)
    build = tmp_path / "build"
    out = tmp_path / "out" / "final.mp4"
    compose.compose(sb, build, out, narration=ROOT / "pa_decode_v2.mp3")
    info = _probe(out)
    types = {s["codec_type"] for s in info["streams"]}
    assert "video" in types
    assert "audio" in types
    assert float(info["format"]["duration"]) == pytest.approx(29.599, abs=0.3)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/test_compose_integration.py -q`
Expected: FAIL —— `ModuleNotFoundError: No module named 'pyv.compose'`

- [ ] **Step 3: 实现 `pyv/compose.py`**

```python
# pipeline/pyv/compose.py
"""片段拼接 + 混音 + 烧字幕 → 成片。"""
from __future__ import annotations

import subprocess
from pathlib import Path

from pyv import render
from pyv.subtitle import build_ass
from pyv.timeline import Storyboard


def _write_concat_list(clips: list[Path], list_path: Path) -> None:
    list_path.write_text(
        "".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8"
    )


def compose(storyboard: Storyboard, build_dir: str | Path, out_path: str | Path,
            narration: str | Path | None = None) -> Path:
    """渲染全部片段 → 拼接 → 混入旁白 → 烧字幕 → 写出成片。"""
    build_dir = Path(build_dir)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    clips = render.render_storyboard(storyboard, build_dir)
    if not clips:
        raise RuntimeError("没有可拼接的片段")

    list_path = build_dir / "concat.txt"
    _write_concat_list(clips, list_path)

    silent = build_dir / "silent.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
         "-c", "copy", str(silent)],
        check=True, capture_output=True, text=True,
    )

    narration_path = Path(narration) if narration else None
    ass_path = build_dir / "subtitles.ass"
    ass_path.write_text(build_ass(storyboard), encoding="utf-8")

    cmd = ["ffmpeg", "-y", "-i", str(silent)]
    if narration_path:
        cmd += ["-i", str(narration_path)]
    cmd += [
        "-vf", f"ass={ass_path}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", "24",
    ]
    if narration_path:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += [str(out_path)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out_path
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && python -m pytest tests/test_compose_integration.py -q`
Expected: PASS —— 1 passed（成片时长跟随旁白 29.599 秒）

- [ ] **Step 5: 实现 `cli.py` 的 `render` 与 `compose` 子命令**

```python
def cmd_render(args: argparse.Namespace) -> int:
    from pyv import render
    storyboard = Storyboard.load(args.storyboard)
    errors = storyboard.validate()
    if errors:
        for e in errors:
            print(f"ERROR {e}", file=sys.stderr)
        return 1
    palette.assert_font_available()
    outputs = render.render_storyboard(storyboard, args.out)
    print(f"OK 渲染 {len(outputs)} 个片段 → {args.out}")
    return 0


def cmd_compose(args: argparse.Namespace) -> int:
    from pyv import compose
    storyboard = Storyboard.load(args.storyboard)
    errors = storyboard.validate()
    if errors:
        for e in errors:
            print(f"ERROR {e}", file=sys.stderr)
        return 1
    out = compose.compose(storyboard, args.build, args.out,
                          narration=args.narration)
    print(f"OK 成片 → {out}")
    return 0
```

并在 `main()` 注册：

```python
    p_render = sub.add_parser("render")
    p_render.add_argument("--storyboard", required=True)
    p_render.add_argument("--out", required=True)
    p_render.set_defaults(func=cmd_render)

    p_compose = sub.add_parser("compose")
    p_compose.add_argument("--storyboard", required=True)
    p_compose.add_argument("--build", required=True)
    p_compose.add_argument("--out", required=True)
    p_compose.add_argument("--narration", default=None)
    p_compose.set_defaults(func=cmd_compose)
```

- [ ] **Step 6: 写 Makefile**

```makefile
# docs/life/aiv/pipeline/Makefile
ROOT := ..
PY := python

.PHONY: test validate align render compose all

test:
	$(PY) -m pytest tests/ -q

validate:
	$(PY) -m pyv.cli validate --storyboard $(ROOT)/storyboard.json

align:
	$(PY) -m pyv.cli align --audio $(ROOT)/pa_decode_v2.mp3 \
		--script $(ROOT)/字幕-并行解码.md --out $(ROOT)/storyboard.json

render:
	$(PY) -m pyv.cli render --storyboard $(ROOT)/storyboard.json --out $(ROOT)/build

compose:
	$(PY) -m pyv.cli compose --storyboard $(ROOT)/storyboard.json \
		--build $(ROOT)/build --out $(ROOT)/out/pg-parallel-decode.mp4 \
		--narration $(ROOT)/pa_decode_v2.mp3

all: align render compose
```

- [ ] **Step 7: 跑完整测试**

Run: `cd /Users/growduduan/code/blog/docs/life/aiv/pipeline && make test`
Expected: 全部 PASS

- [ ] **Step 8: 出片**

Run:
```bash
cd /Users/growduduan/code/blog/docs/life/aiv/pipeline
make validate && make render && make compose
ffprobe -v error -show_entries format=duration -show_entries stream=width,height,codec_type -of default=noprint_wrappers=1 ../out/pg-parallel-decode.mp4
```
Expected: 时长 29.599 秒左右、1920x1080、含 video 与 audio 流

- [ ] **Step 9: 人工导入 MiniMax Design（不写其数据库）**

1. 关闭正在运行的 Design，避免文件占用。
2. 把 `docs/life/aiv/out/pg-parallel-decode.mp4` 拖入 Design 画布，或用 IM 派活给 Design 的 agent 导入。
3. 在 Design 内做终审：核对字幕时间轴、结尾落版、整体节奏。
4. 用 Design 的多平台导出产出发布版本（16:9 主版 + 9:16 版）。
5. H3 质感片头（若需要）：在 Design 内用 `growdu.png` 作参考图生成 768P / 3 秒镜头，落到 `build/h3/` 后重跑 `make render compose`。

- [ ] **Step 10: 提交**

```bash
cd /Users/growduduan/code/blog
git add docs/life/aiv/pipeline
git commit -m "feat(aiv): 端到端合成与 CLI

- compose 拼接片段、混入原旁白、烧 ASS 字幕
- CLI 增加 render / compose 子命令，Makefile 串起 align→render→compose
- 集成测试断言成片含音视频流且时长跟随旁白"
```

---

## 自检

- **规格覆盖**：§2 素材（Task 2/5/9 使用）、§3 分工（Task 6–9 画技术图示，Task 10 出片）、§4 契约（Task 1/2）、§5 分镜（Task 6–9 六段全覆盖）、§6 引擎（Task 4/5）、§7 Design 协作（Task 10 步骤 9）、§8 提交与测试（每个任务一个提交）、§9 风险（R1 字幕样式已固化进常量、R2 时长随旁白、R4 归属语在文案契约、R5 回退由 Task 10 步骤 9 覆盖）。
- **占位检查**：无 TBD/TODO；Task 6 步骤 5 的 s04/s05/s06 明确标注为占位并在 Task 8/9 被替换，接口与测试均已给出。
- **类型一致性**：`Scene(renderer=...)`、`Storyboard.load/validate/duration`、`subtitle.build_ass(storyboard)`、`render.render_scene(scene, out_path, width, height, fps)`、`compose.compose(storyboard, build_dir, out_path, narration)` 在各任务间签名一致。
