"""系列片头片尾的配乐窗口：闭环口径、选窗判据与混音脚本的契约。

这一组测试盯的是「片尾接回片头」这条口径（规范 §6 末条、§7 `bgm.brand-*`）。
它曾经被违反过：片头片尾各挑各的窗口，实测片头在 115.15 s、片尾在 31.80 s，
两段互不相干，听上去基本是两首不同的音乐。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from pyv import bgm

ROOT = Path(__file__).resolve().parents[2]
WINDOWS_PATH = ROOT / "brand" / "brand_windows.json"
SCRIPT = ROOT / "brand" / "scripts" / "make_audio_brand.py"
MOTIF = ROOT / "music" / "tracks" / "series-motif-01.wav"

SR = 48000

# 曲库音频是媒体产物，不入库——依赖它的用例要优雅跳过。
requires_motif = pytest.mark.skipif(
    not MOTIF.is_file(), reason="曲库音频不在仓库中，跳过"
)


# ---------------------------------------------------------------- 夹具


def _write_wav(path: Path, samples: np.ndarray, sample_rate: int = SR) -> Path:
    import wave

    data = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    data = np.repeat(data, 2)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(data.tobytes())
    return path


def _track_with_onset(path: Path, onset_index: int,
                      seconds: float = 20.0) -> Path:
    """造一条只有一个清楚起音的曲子。

    背景是低电平噪声（RMS 0.03），起音点是一段 0.5 秒的 220 Hz 音，
    幅度 0.5。候选点按 0.05 秒步进扫，所以把起音点放在**候选点本身**
    上，好让「谁被选中」是确定的。
    """
    count = int(seconds * SR)
    rng = np.random.default_rng(11)
    # 高斯噪声的 RMS 就等于标准差：背景 RMS 取 0.03（高于 BRAND_MIN_RMS）
    samples = rng.normal(0.0, 0.03, count)
    burst = int(0.5 * SR)
    t = np.arange(burst) / SR
    samples[onset_index:onset_index + burst] = 0.5 * np.sin(2 * np.pi * 220 * t)
    return _write_wav(path, samples)


def _load_script():
    """把混音脚本当模块加载（它不能 import pyv，否则成环）。"""
    spec = importlib.util.spec_from_file_location("make_audio_brand", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------- 已入库的窗口


def test_shipped_windows_exist():
    assert WINDOWS_PATH.is_file(), f"缺少 {WINDOWS_PATH}"


def test_shipped_windows_connect():
    """已入库的窗口必须首尾相接：片尾结束点 == 片头起点。"""
    raw = json.loads(WINDOWS_PATH.read_text(encoding="utf-8"))
    duration = float(raw["duration_s"])
    intro_start = float(raw["intro_start_s"])
    outro_start = float(raw["outro_start_s"])
    assert outro_start + duration == pytest.approx(intro_start, abs=0.01), (
        f"片尾结束在 {outro_start + duration:.3f}s，片头起于 {intro_start:.3f}s——"
        f"没有相接"
    )


@requires_motif
def test_shipped_windows_pass_the_check():
    """入库的窗口要过 `bgm brand-check` 的全部硬判据。"""
    windows = bgm.load_brand_windows(WINDOWS_PATH)
    findings = bgm.check_brand_windows(windows, MOTIF)
    errors = [f for f in findings if f.level == bgm.ERROR]
    assert not errors, [str(f) for f in errors]


@requires_motif
def test_brand_windows_report_the_take_level():
    """品牌片的取用段落（两个窗口合成的那一截）也要量相对整曲的电平。

    旧口径的片头窗口（115.15 s）取用段落比整曲响 1.30 dB ——
    推导的前提不成立，所以这条判据能顺带把那种窗口挑出来。
    """
    windows = bgm.load_brand_windows(WINDOWS_PATH)
    findings = bgm.check_brand_windows(windows, MOTIF)
    take = [f for f in findings if f.rule_id == "bgm.take-level"]
    assert take, "应该报出取用段落的电平差"
    assert take[0].level == bgm.WARNING
    assert "安静" in str(take[0])


def test_shipped_windows_name_a_registered_motif():
    """窗口记的曲子 id 要在曲库台账里，而且指纹对得上。"""
    windows = bgm.load_brand_windows(WINDOWS_PATH)
    entries = {e.id: e for e in bgm.load_library()}
    assert windows.track_id in entries, f"台账里没有 {windows.track_id}"
    entry = entries[windows.track_id]
    assert entry.series_role == "motif"
    assert entry.sha256 == windows.track_sha256


# ---------------------------------------------------------------- 判据


def _windows(**overrides) -> bgm.BrandWindows:
    base = dict(
        duration_s=bgm.BRAND_WINDOW_SECONDS,
        intro_start_s=8.733,
        outro_start_s=8.733 - bgm.BRAND_WINDOW_SECONDS,
        track_id="series-motif-01",
        track_sha256="",
    )
    base.update(overrides)
    return bgm.BrandWindows(**base)


def test_windows_that_do_not_connect_are_an_error():
    windows = _windows(outro_start_s=31.8)
    findings = bgm.check_brand_windows(windows)
    rules = {f.rule_id for f in findings if f.level == bgm.ERROR}
    assert "bgm.brand-loop" in rules


def test_windows_without_a_track_id_are_an_error():
    windows = _windows(track_id="")
    findings = bgm.check_brand_windows(windows)
    rules = {f.rule_id for f in findings if f.level == bgm.ERROR}
    assert "bgm.brand-track" in rules


@requires_motif
def test_windows_with_a_stale_fingerprint_are_an_error():
    windows = _windows(track_sha256="0" * 64)
    findings = bgm.check_brand_windows(windows, MOTIF)
    rules = {f.rule_id for f in findings if f.level == bgm.ERROR}
    assert "bgm.brand-track" in rules


def test_quiet_windows_are_an_error():
    windows = _windows(intro_rms=0.001, outro_rms=0.001)
    findings = bgm.check_brand_windows(windows)
    rules = {f.rule_id for f in findings if f.level == bgm.ERROR}
    assert "bgm.brand-window" in rules


def test_a_weak_onset_is_only_a_warning():
    """起音比不够高只是提示——起不来而已，不是硬错。"""
    windows = _windows(onset_ratio=1.2)
    findings = bgm.check_brand_windows(windows)
    weak = [f for f in findings if f.rule_id == "bgm.brand-window"]
    assert weak and all(f.level == bgm.WARNING for f in weak)


# ---------------------------------------------------------------- 选窗


def test_picked_windows_are_adjacent(tmp_path):
    """挑出来的两段必须紧挨着——这才是「片尾接回片头」。"""
    win = int(bgm.BRAND_WINDOW_SECONDS * SR)
    step = int(0.05 * SR)
    onset_index = win + 44 * step          # 落在一个候选点上
    track = _track_with_onset(tmp_path / "track.wav", onset_index)

    windows = bgm.pick_brand_windows(track, track_id="synthetic")

    assert windows.outro_end_s == pytest.approx(windows.intro_start_s, abs=1e-6)
    assert windows.intro_start_s == pytest.approx(onset_index / SR, abs=0.01)
    assert windows.onset_ratio >= bgm.BRAND_ONSET_RATIO_MIN


def test_a_track_without_an_onset_is_rejected(tmp_path):
    """没有清楚起音的曲子挑不出窗口——宁可报错，也不要挑个不像样的。"""
    rng = np.random.default_rng(3)
    track = _write_wav(tmp_path / "flat.wav",
                       rng.normal(0.0, 0.05, int(20 * SR)))
    with pytest.raises(ValueError):
        bgm.pick_brand_windows(track)


def test_windows_round_trip(tmp_path):
    windows = _windows(onset_ratio=13.712)
    target = bgm.save_brand_windows(windows, tmp_path / "w.json")
    loaded = bgm.load_brand_windows(target)
    assert loaded == windows


# ---------------------------------------------------------------- 混音脚本的契约


def test_the_script_reads_the_shipped_window_file(monkeypatch):
    """脚本必须读已入库的窗口文件，而不是自己挑。"""
    monkeypatch.delenv("BRAND_WINDOWS_PATH", raising=False)
    module = _load_script()
    assert module.WINDOWS == WINDOWS_PATH


def test_the_script_refuses_to_produce_when_windows_do_not_connect(tmp_path):
    """窗口不相接就拒产——不能让错口径流到成片。"""
    raw = json.loads(WINDOWS_PATH.read_text(encoding="utf-8"))
    raw["outro_start_s"] = 31.8
    broken = tmp_path / "brand_windows.json"
    broken.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        check=False, capture_output=True, text=True,
        env={**__import__("os").environ,
             "BRAND_WINDOWS_PATH": str(broken)},
    )
    assert proc.returncode != 0, "窗口不相接时脚本竟然产出了成品"
    assert "不相接" in (proc.stdout + proc.stderr)


def test_fades_stay_short():
    """淡出要短：太长会把刚接上的闭环淡没。"""
    module = _load_script()
    assert module.FADE_OUT <= 0.1, "片尾淡出过长，会把闭环淡没"
    assert module.FADE_IN_INTRO <= 0.1
    assert module.MIX_FADE_OUT <= 0.1


def test_the_spec_and_the_code_agree_on_the_brand_thresholds():
    """阈值：规范里写的和代码里的一致。"""
    spec = (ROOT / "背景音乐规范.md").read_text(encoding="utf-8")
    assert f"{bgm.BRAND_WINDOW_SECONDS:g} 秒" in spec
    assert f"{bgm.BRAND_ONSET_RATIO_MIN:g}" in spec
    assert f"{bgm.BRAND_MIN_RMS:g}" in spec
    assert f"{bgm.BRAND_PEAK_MAX:g}" in spec
    for rule_id in ("bgm.brand-loop", "bgm.brand-track", "bgm.brand-window"):
        assert f"`{rule_id}`" in spec
