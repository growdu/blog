"""旁白对齐：静音检测 → 句段时间码 → storyboard.json。

流程：
1. 用 ffmpeg silencedetect 把音频切成有声片段
2. 与口播稿逐句配对（句数不一致直接报错，不猜）
3. 按视觉分镜契约把句子归入视觉段，段间首尾相接
4. 写出 storyboard.json：scenes[] 是视觉段（带画面内容 params），
   subtitles[] 是逐句字幕

**时间轴来自旁白，画面内容来自契约**——两者分开，谁也不绑架谁：
换旁白只改音频，换文案只改契约。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from pyv.contract import Contract, load_contract
from pyv import palette
from pyv.timeline import (
    Audio,
    Scene,
    Storyboard,
    SubtitleEvent,
    SubtitleStyle,
    Video,
    display_width,
)

DEFAULT_THRESHOLD_DB = -32
DEFAULT_MIN_SILENCE = 0.25
SCRIPT_KEYWORD = "口播稿"
SUBTITLE_KEYWORD = "字幕文本"


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


def _speech_offset_to_time(spans: list[tuple[float, float]], offset: float) -> float:
    """把"已发音时长"换算成绝对时间轴位置。"""
    remaining = offset
    for start, end in spans:
        length = end - start
        if remaining <= length:
            return start + remaining
        remaining -= length
    return spans[-1][1]


def align_by_weight(spans: list[tuple[float, float]],
                     texts: list[str],
                     weights: list[float] | None = None) -> list[tuple[float, float, str]]:
    """把语音片段最优地分配给各句：每句时长尽量贴近"文本占比 × 总语音时长"。

    TTS 在逗号处也会停顿，直接按静音长度切会切出十几段；
    这里用动态规划在"所有连续分组方案"里挑误差最小的一组，
    边界必然落在语音片段之间，既不切在词中间，也比就近吸附均匀得多。
    """
    if len(texts) < 2:
        raise ValueError("至少需要两句才能计算边界")
    if weights is None:
        weights = [display_width(t) for t in texts]
    if len(weights) != len(texts):
        raise ValueError("权重数量与句子数量不一致")
    if len(spans) < len(texts):
        raise ValueError(
            f"语音片段数 {len(spans)} 少于句子数 {len(texts)}，无法逐句对齐"
        )

    total_speech = sum(e - s for s, e in spans)
    total_weight = sum(weights)
    if total_weight <= 0:
        raise ValueError("文本权重总和为 0，无法对齐")

    # 每句的目标语音时长（增量，不是累计）
    targets: list[float] = []
    cumulative_weight = 0.0
    previous_cumulative = 0.0
    for weight in weights:
        cumulative_weight += weight
        cumulative_time = total_speech * cumulative_weight / total_weight
        targets.append(cumulative_time - previous_cumulative)
        previous_cumulative = cumulative_time

    # 片段长度前缀和，便于 O(1) 求任意片段组的语音时长
    prefix = [0.0]
    for s, e in spans:
        prefix.append(prefix[-1] + (e - s))

    n_spans, n_sent = len(spans), len(texts)
    inf = float("inf")
    # dp[k][j] = 前 k 句用掉前 j 个片段时的最小平方误差
    dp = [[inf] * (n_spans + 1) for _ in range(n_sent + 1)]
    back = [[0] * (n_spans + 1) for _ in range(n_sent + 1)]
    dp[0][0] = 0.0
    for k in range(1, n_sent + 1):
        target = targets[k - 1]
        for j in range(k, n_spans + 1):
            for i in range(k - 1, j):
                if dp[k - 1][i] == inf:
                    continue
                group = prefix[j] - prefix[i]
                cost = (group - target) ** 2
                total = dp[k - 1][i] + cost
                if total < dp[k][j]:
                    dp[k][j] = total
                    back[k][j] = i

    if dp[n_sent][n_spans] == inf:
        raise ValueError("无法把语音片段分配给各句")

    # 回溯分组
    groups: list[tuple[int, int]] = []
    j = n_spans
    for k in range(n_sent, 0, -1):
        i = back[k][j]
        groups.append((i, j))
        j = i
    groups.reverse()

    result: list[tuple[float, float, str]] = []
    for index, (first, last) in enumerate(groups):
        result.append((spans[first][0], spans[last - 1][1], texts[index]))
    return result


def _section_body(lines: list[str], keyword: str) -> list[str]:
    """取包含关键字的二级标题之后、下一个二级标题之前的行。"""
    start = None
    for i, line in enumerate(lines):
        if line.startswith("## ") and keyword in line:
            start = i
            break
    if start is None:
        raise ValueError(f"契约缺少包含「{keyword}」的二级标题")
    body: list[str] = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        body.append(line)
    return body


def parse_script(md_path: str | Path) -> list[str]:
    """从口播稿小节的代码块里提取句子，每行一句。"""
    lines = Path(md_path).read_text(encoding="utf-8").splitlines()
    body = _section_body(lines, SCRIPT_KEYWORD)
    sentences: list[str] = []
    in_block = False
    for line in body:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_block = not in_block
            continue
        if not in_block:
            continue
        if stripped:
            sentences.append(stripped)
    if not sentences:
        raise ValueError("口播稿小节里没有找到代码块")
    return sentences


def parse_subtitle_table(md_path: str | Path) -> list[str]:
    """从字幕文本小节的表格里提取字幕文案，按行序返回。"""
    lines = Path(md_path).read_text(encoding="utf-8").splitlines()
    body = _section_body(lines, SUBTITLE_KEYWORD)
    texts: list[str] = []
    for line in body:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if cells[0] in ("#", "序号") or set(cells[0]) <= {"-", " "}:
            continue
        if cells[1]:
            texts.append(cells[1])
    if not texts:
        raise ValueError("字幕文本小节里没有找到表格")
    return texts


def build_storyboard(audio_path: str | Path,
                      script_md: str | Path,
                      out_path: str | Path,
                      contract_path: str | Path | None = None,
                      canvas: str = "horizontal") -> Storyboard:
    """对齐旁白与口播稿，写出 storyboard.json 并返回其内容。

    `contract_path` 是视觉分镜契约：句到视觉段的映射 + 画面上的文案。
    省略时用默认契约（`aiv/contracts/pg-parallel-decode.json`）。

    `canvas` 是画布档位（`horizontal` / `vertical`，见 `palette.CANVASES`）。
    **默认横版**——竖版是抖音那一档的另一个产物，不是替换。
    """
    contract = load_contract(contract_path)
    canvas_width, canvas_height = palette.canvas(canvas)
    sentences = parse_script(script_md)
    subtitle_texts = parse_subtitle_table(script_md)
    if len(sentences) != len(subtitle_texts):
        raise ValueError(
            f"口播稿 {len(sentences)} 句与字幕表 {len(subtitle_texts)} 行不一致"
        )
    if len(sentences) != contract.sentence_count:
        raise ValueError(
            f"口播稿 {len(sentences)} 句与契约期望的 "
            f"{contract.sentence_count} 句不一致"
        )

    spans = detect_sentences(audio_path)
    if len(spans) == len(sentences):
        pairs = assign_sentences(spans, sentences)
    else:
        pairs = align_by_weight(spans, sentences)
    duration = probe_duration(audio_path)

    # 视觉段边界：首段从 0 开始，其余从本段首句的起点开始，末段到音频结尾
    boundaries: list[float] = [0.0]
    for segment in contract.segments[1:]:
        boundaries.append(round(pairs[segment.sentences[0]][0], 3))
    boundaries.append(round(duration, 3))

    scenes: list[Scene] = []
    for index, segment in enumerate(contract.segments):
        start = boundaries[index]
        end = boundaries[index + 1]
        covered = [pairs[i][2] for i in segment.sentences]
        scenes.append(Scene(
            id=segment.id,
            start=start,
            end=end,
            type="code",
            subtitle="\n".join(subtitle_texts[i] for i in segment.sentences),
            renderer=segment.renderer,
            params=dict(segment.params),
            sentences=segment.sentences,
        ))

    subtitles = [
        SubtitleEvent(start=round(start, 3), end=round(end, 3),
                      text=subtitle_texts[i])
        for i, (start, end, _) in enumerate(pairs)
    ]

    raw = {
        "version": 1,
        "video": {"width": canvas_width, "height": canvas_height,
                  "fps": 24, "duration": round(duration, 3)},
        "audio": {"narration": Path(audio_path).name, "bgm": None},
        "subtitle_style": {"primary": "#1B2A47", "outline": "#FFFFFF",
                           "position": "bottom-center"},
        "scenes": [
            {
                "id": s.id, "start": s.start, "end": s.end, "type": s.type,
                "subtitle": s.subtitle, "renderer": s.renderer,
                "params": s.params, "sentences": list(s.sentences),
            }
            for s in scenes
        ],
        "subtitles": [
            {"start": e.start, "end": e.end, "text": e.text} for e in subtitles
        ],
    }
    Path(out_path).write_text(
        json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return Storyboard.load(out_path)
