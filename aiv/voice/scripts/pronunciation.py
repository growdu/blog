#!/usr/bin/env python3
"""多音字读音规则——这个音色的 TTS 会把「行锁」的「行」念成 xíng。

实测（2026-11-13，MiniMax `Chinese (Mandarin)_Radio_Host`，pitch −1 / speed 1.33），
用 `check_pronunciation.py` 量摩擦噪声谱心（[ɕ] 高频强、 [x] 低频弱）：

| 词 | 首字声母 | 实测 |
| --- | --- | --- |
| 西 | [ɕ] | 摩擦比 725.8、谱心 4419–4566 Hz |
| 好 / 航 | [x] | 摩擦比 ≈ 0.1、谱心 2900–3300 Hz |
| 行锁 | [ɕ] | **5/5 样本都念成 xíng** ❌ |
| 同一行 / 每一行 / 每行 / 哪一行 / 行号 | [x] | 0/5 样本念错 ✅ |
| 一行 | [ɕ] | 5 个样本里 2 个念成 xíng ❌（不稳定） |

**规律**：「行」在**词尾**（数量词组、动宾结构里）大多念 háng，但「一行」会漏；
在**词首**构成复合词时（行锁）念 xíng——连「行号」这种行 = row 的词也会被念错。

**怎么绕**：连接器封装会**丢掉** MiniMax 的 `pronunciation_dict`
（`行锁/pinganpingan` 实测仍念成 `xing2 suo3`），`<phoneme>` 标签会被**念出来**，
括号里的拼音也会被念出来。所以唯一可靠的办法是**换等音字**：

| 原词 | 替身 | 为什么等音 |
| --- | --- | --- |
| 行锁 | 航锁 | 航 = háng，无歧义，声母 [x]、韵母 [ɑŋ]、阳平；整句只差 0.093 s |
| 一行 | 壹行 | 壹 = yī，与「一」同声同调；行跟着读成 háng（实测 5/5） |

**只作用于合成文本**：口播稿、字幕表、画面契约一个字都不改，观众听到的仍是「行锁」「一行」。
"""
from __future__ import annotations

import re

# 会念错的词 → 等音替代字（只用于合成文本，不改口播稿）
PRONUNCIATION_SUBSTITUTIONS = {
    "行锁": "航锁",   # 行锁 → 航锁：航 是无歧义的 háng，声母 [x]、韵母 [ɑŋ]、阳平，与目标读音一致
    "一行": "壹行",   # 一行 → 壹行：壹 = yī，与「一」同声同调；「行」跟着读成 háng（实测 5/5）
}

# 实测念 háng（行 = row）的词
HANG_WORDS = frozenset({"同一行", "每一行", "每行", "哪一行", "行号"})

# 实测念 xíng 的词——这些地方 xíng 本来就是对的（并行 / 串行 / 执行）
XING_WORDS = frozenset({"并行", "串行", "执行"})

# 「一行」只有在独立成词时才替换。
# 「每一行」「哪一行」「同一行」「这一行」里它是词的一部分，
# 而那些词实测本来就念 háng（0/5 样本出错）——碰了就把对的改成错的。
_COMPOUND_PREFIX = "每哪同这那某上好另第整"


def _replace_standalone(text: str, wrong: str, right: str) -> str:
    """只替换独立成词的那个词。"""
    if wrong == "一行":
        pattern = re.compile(f"(?<![{_COMPOUND_PREFIX}]){re.escape(wrong)}")
        return pattern.sub(right, text)
    return text.replace(wrong, right)

# 全部已归档的「行」字词，供最长匹配使用
_ARCHIVED = HANG_WORDS | XING_WORDS | frozenset(PRONUNCIATION_SUBSTITUTIONS)
_VOCAB = sorted(_ARCHIVED | frozenset(PRONUNCIATION_SUBSTITUTIONS.values()), key=len, reverse=True)

_HAN = re.compile(r"[一-鿿]")


def standalone_occurrences(text: str, word: str) -> int:
    """数一数 `word` 在 text 里独立成词地出现了几次。

    「每一行」里也有「一行」，但那不是独立成词——替换与核对都要分清。
    """
    if word == "一行":
        pattern = re.compile(f"(?<![{_COMPOUND_PREFIX}]){re.escape(word)}")
    else:
        pattern = re.compile(re.escape(word))
    return len(pattern.findall(text))


def apply_substitutions(text: str) -> str:
    """把口播文本换成 TTS 念得对的等音写法。

    只影响送进合成引擎的那份文本；口播稿、字幕表、画面契约都保持原样。
    """
    for wrong, right in PRONUNCIATION_SUBSTITUTIONS.items():
        text = _replace_standalone(text, wrong, right)
    return text


def find_hang_words(text: str) -> list[str]:
    """找出文本里所有含「行」的词。

    先用已归档词表做最长匹配；表里没有的，取「行」起的一段连续汉字当作待核词——
    待核词必须先实测读音，再补进词表或补进替换表。
    """
    n = len(text)
    matched: list[str | None] = [None] * n
    i = 0
    while i < n:
        hit = next((w for w in _VOCAB if text.startswith(w, i)), None)
        if hit:
            for k in range(i, i + len(hit)):
                matched[k] = hit
            i += len(hit)
        else:
            i += 1

    out: list[str] = []
    i = 0
    while i < n:
        if text[i] != "行":
            i += 1
            continue
        if matched[i]:
            word = matched[i]
        else:
            j = i
            while j < n and _HAN.match(text[j]):
                j += 1
            word = text[i:j] or "行"
        if word not in out:
            out.append(word)
        i += len(word)
    return out


def unverified_hang_words(text: str) -> list[str]:
    """没被任何读音记录覆盖的「行」字词——这些必须先实测再入库。"""
    out = []
    for word in find_hang_words(text):
        if word in _ARCHIVED:
            continue
        if word not in out:
            out.append(word)
    return out
