"""守卫「行锁」那期旁白里「行」的读音。

这个音色的 TTS 会把**词首**的「行」念成 xíng（实测 5/5 样本），
而「行锁」正是词首「行」——所以这一期的旁白必须经过读音替换表。

这里钉三件事：

1. 每期口播稿里出现的每一个「行」字词，读音都**已实测归档**——
   新出现一个没归档的「行」字词，就必须先量它的读音再入库。
2. 「行锁」在替换表里，且替换成的是**等音字**。
3. 替换只动合成文本：口播稿本身仍然是「行锁」，
   字幕表、画面契约一个字都不改。
4. 本机有旁白成品时，直接量成片旁白里那个字——不信 ASR，信声学。

**为什么不用 ASR**：同一段音频，ASR 在孤立语境里把「行锁」写成 `xing2 suo3`，
在整句语境里又写成 `hang2 suo3`——它按上下文归一化，测不出真实读音。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

VOICE_SCRIPTS = Path(__file__).resolve().parents[2] / "voice" / "scripts"
if str(VOICE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(VOICE_SCRIPTS))

from pronunciation import (  # noqa: E402
    HANG_WORDS,
    PRONUNCIATION_SUBSTITUTIONS,
    XING_WORDS,
    apply_substitutions,
    find_hang_words,
    standalone_occurrences,
    unverified_hang_words,
)

ROOT = Path(__file__).resolve().parents[2]

from pyv import episodes as episodes_mod


SCRIPTS = {
    episodes_mod.EP_NUMBERS[ep]: episodes_mod.EPISODES[ep]
    for ep in episodes_mod.EPISODE_ORDER
}


def _script_text(name: str) -> str:
    """口播稿里的正文（第一个代码块）——只有它会被念出来。"""
    from pyv import align
    return "\n".join(align.parse_script(ROOT / name))


# ---------------------------------------------------------------- 读音表


def test_the_misread_word_is_mapped_to_a_substitute():
    """「行锁」必须在替换表里，且替身是等音字。"""
    assert "行锁" in PRONUNCIATION_SUBSTITUTIONS, (
        "「行锁」的「行」在这个音色里被念成 xíng（实测 5/5 样本），"
        "必须留在读音替换表里"
    )
    substitute = PRONUNCIATION_SUBSTITUTIONS["行锁"]
    assert substitute == "航锁", (
        f"「行锁」的替身是 {substitute}——实测只有「航」是可靠 háng 的等音字"
    )
    assert len(substitute) == len("行锁"), "替身必须等长等音，不能改变时长"


def test_every_substitute_is_also_a_verified_word():
    """替身本身也要在已归档词表里——不能拿没量过的字当替身。"""
    for wrong, right in PRONUNCIATION_SUBSTITUTIONS.items():
        assert right in HANG_WORDS | XING_WORDS | set(PRONUNCIATION_SUBSTITUTIONS.values()), (
            f"替身「{right}」没有实测读音"
        )


@pytest.mark.parametrize("episode", sorted(SCRIPTS))
def test_every_hang_word_in_every_script_is_measured(episode):
    """每期口播稿里的每一个「行」字词，读音都必须已经实测归档。

    新写进稿子的「行」字词如果不在这三张表里，就说明它的读音还没量过——
    那个字很可能被念错。
    """
    text = _script_text(SCRIPTS[episode])
    unknown = unverified_hang_words(text)
    assert not unknown, (
        f"{SCRIPTS[episode]} 里出现了没实测过读音的「行」字词：{unknown}——"
        f"先用 voice/scripts/check_pronunciation.py 量出 háng / xíng，"
        f"再补进 pronunciation.py 的词表或替换表"
    )


@pytest.mark.parametrize("episode", sorted(SCRIPTS))
def test_the_script_itself_is_never_rewritten(episode):
    """替换只发生在送进 TTS 的那份文本上——口播稿本身保持原样。"""
    text = _script_text(SCRIPTS[episode])
    spoken = apply_substitutions(text)
    # 幂等：替换过一遍之后，不该再有独立成词的待替换词
    assert apply_substitutions(spoken) == spoken, (
        f"合成文本里还留着没替换干净的词：{spoken}"
    )
    for wrong, right in PRONUNCIATION_SUBSTITUTIONS.items():
        if standalone_occurrences(text, wrong) == 0:
            continue
        assert wrong in text, "口播稿必须保留原词"
        assert standalone_occurrences(spoken, wrong) == 0, (
            f"合成文本里还留着独立成词的「{wrong}」"
        )
        assert right in spoken, f"合成文本里该出现「{right}」"


def test_the_compound_words_are_left_alone():
    """「每一行」「哪一行」「同一行」里含「一行」，但它们是别的词。

    那三个词实测本来就读 háng（0/5 样本出错）——
    要是被替换成「每壹行」，就把对的改错了。
    """
    for compound in ("每一行", "哪一行", "同一行", "这一行"):
        spoken = apply_substitutions(f"两个事务改{compound}，凭什么不能都改？")
        assert compound in spoken, f"「{compound}」被误替换了：{spoken}"
        assert "壹行" not in spoken, f"「{compound}」被误替换了：{spoken}"


def test_the_standalone_one_hang_word_is_replaced():
    """独立成词的「一行」必须替换——它实测 5 个样本里 2 个念成 xíng。"""
    spoken = apply_substitutions("WAL 是操作级记录，一行只写一个动作。")
    assert "壹行只写一个动作" in spoken
    assert "一行只写一个动作" not in spoken


def test_the_row_lock_script_still_says_the_word_itself():
    """这一期的口播稿必须仍然写着「行锁」——观众看到、字幕表里都是它。"""
    text = _script_text(SCRIPTS["ep06"])
    assert "行锁" in text, "口播稿里的「行锁」被改掉了？不应该改"
    spoken = apply_substitutions(text)
    assert "航锁" in spoken and "行锁" not in spoken


def test_the_find_helper_catches_word_initial_hang():
    """「行锁」是词首「行」，「同一行」是词尾——检测器要能分开。"""
    assert "行锁" in find_hang_words("在 MVCC 之上加了行锁，一共 4 种模式。")
    assert "同一行" in find_hang_words("两个事务改同一行，凭什么不能都改？")
    assert "并行" in find_hang_words("上游的并行 apply 是单事务内多流并行。")


# ---------------------------------------------------------------- 成品旁白


@pytest.mark.skipif(not (ROOT / "narration_row-lock.spoken.txt").is_file(),
                    reason="旁本不在本机，跳过")
def test_the_shipped_narration_was_synthesized_from_the_substituted_text():
    """本机有旁白成品时，核对**真正送进 TTS 的那份文本**。

    旁本（`*.spoken.txt`）是合成脚本写下的留底——它就是引擎听到的字。
    """
    spoken = (ROOT / "narration_row-lock.spoken.txt").read_text(encoding="utf-8")
    assert "航锁" in spoken, "旁白不是用替换后的文本合成的"
    assert "行锁" not in spoken, "替换后的文本里不该还留着「行锁」"


def test_the_pronunciation_judgement_constants_are_consistent():
    """判据本身的常量不能自相矛盾——阈值漂了就等于没判。"""
    from check_pronunciation import (  # noqa: E402
        GAMMA_CENTROID_MIN,
        GAMMA_RATIO_MIN,
        ONSET_WINDOW,
    )
    assert GAMMA_RATIO_MIN >= 20, "摩擦比门槛太低，浊音段会被当成摩擦噪声"
    assert GAMMA_CENTROID_MIN >= 3500, "谱心门槛低于 [ɕ] 的实测下沿（4419 Hz）"
    assert ONSET_WINDOW <= 0.10, (
        "词首窗口大于 100 ms 就会扫到后一个字（实测「锁」的 /s/ 在 +126 ms 以后）"
    )
