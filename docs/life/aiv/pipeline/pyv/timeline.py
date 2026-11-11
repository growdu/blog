"""storyboard.json 的数据结构、加载与校验。

契约里区分两层：
- scenes[]  —— 视觉段，一个 renderer 覆盖一段时间
- subtitles[] —— 字幕事件，逐句对齐旁白，可与视觉段一一不等长
"""
from __future__ import annotations

import json
import unicodedata
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


def char_width(ch: str) -> float:
    """全角字符算 1，半角算 0.5。"""
    return 1.0 if unicodedata.east_asian_width(ch) in ("W", "F") else 0.5


def display_width(text: str) -> float:
    """字幕行的视觉宽度，用于判断是否溢出。"""
    return sum(char_width(ch) for ch in text)


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
class SubtitleEvent:
    start: float
    end: float
    text: str


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
    audio: str | None = None

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
    subtitles: list[SubtitleEvent] = field(default_factory=list)

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
                audio=s.get("audio"),
            )
            for s in raw["scenes"]
        ]
        subtitles = [
            SubtitleEvent(
                start=float(e["start"]),
                end=float(e["end"]),
                text=e.get("text", ""),
            )
            for e in raw.get("subtitles", []) or []
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
            subtitles=subtitles,
        )

    @property
    def duration(self) -> float:
        return max((s.end for s in self.scenes), default=0.0)

    def subtitle_events(self) -> list[SubtitleEvent]:
        """契约里没有 subtitles 时，退化为按场景出字幕。"""
        if self.subtitles:
            return self.subtitles
        return [
            SubtitleEvent(start=s.start, end=s.end, text=s.subtitle)
            for s in self.scenes
        ]

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.version != 1:
            errors.append(f"version 必须为 1，实际 {self.version}")
        if (self.video.width, self.video.height) != (1920, 1080):
            errors.append(
                f"画布必须是 1920x1080，实际 {self.video.width}x{self.video.height}"
            )
        if self.video.fps != 24:
            errors.append(f"fps 必须为 24，实际 {self.video.fps}")
        if not self.scenes:
            errors.append("场景列表为空")
            return errors

        if abs(self.scenes[0].start) > EPS:
            errors.append(f"首个场景必须从 0 开始，实际 {self.scenes[0].start}")

        for prev, cur in zip(self.scenes, self.scenes[1:]):
            if abs(prev.end - cur.start) > EPS:
                errors.append(
                    f"场景 {prev.id} 与 {cur.id} 不连续（{prev.end} → {cur.start}）"
                )

        last = self.scenes[-1]
        if abs(last.end - self.video.duration) > EPS:
            errors.append(
                f"场景总时长 {last.end:.3f} 与契约总时长 {self.video.duration:.3f} 不一致"
            )

        for scene in self.scenes:
            errors.extend(self._validate_scene(scene))

        for event in self.subtitle_events():
            errors.extend(self._validate_text(event.text, "字幕"))
        return errors

    @staticmethod
    def _validate_scene(scene: Scene) -> list[str]:
        errors: list[str] = []
        if scene.type not in ("code", "h3", "clip"):
            errors.append(
                f"场景 {scene.id} 的 type 必须是 code、h3 或 clip，实际 {scene.type}"
            )
        if scene.type == "code" and not scene.renderer:
            errors.append(f"场景 {scene.id} 缺少 renderer")
        if scene.type == "clip":
            if not scene.clip:
                errors.append(f"场景 {scene.id} 缺少 clip")
            if not scene.audio:
                errors.append(f"场景 {scene.id} 缺少 audio")
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
        errors.extend(Storyboard._validate_text(scene.subtitle, f"场景 {scene.id} 字幕"))
        return errors

    @staticmethod
    def _validate_text(text: str, label: str) -> list[str]:
        errors: list[str] = []
        if not text.strip():
            errors.append(f"{label} 为空")
            return errors
        for line in text.splitlines():
            stripped = line.strip()
            if display_width(stripped) > MAX_SUBTITLE_LINE:
                errors.append(
                    f"{label} 单行超过 {MAX_SUBTITLE_LINE} 宽：{stripped!r}"
                )
        lowered = text.lower()
        for word in BANNED_SUBSTRINGS:
            if word.lower() in lowered:
                errors.append(f"{label} 含禁止词 {word!r}")
        return errors
