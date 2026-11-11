"""背景音乐检查测试。

两条线：

1. **规范与实现同步**——《背景音乐规范》§4、§5、§7 的阈值与规则编号，
   必须和 `pyv/bgm.py` 里的常量一一对应。规范改了代码没改（或者反过来），
   判据就跟规范说的不是一回事了。

2. **规则真的抓得住**——每条规则都要有正反用例；ducking 的深度要能
   量出确定值，而不是「大概是那么深」。
"""
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from pyv import bgm, cli

SR = 48000


# ---------------------------------------------------------------- 夹具


def _write_wav(path: Path, samples: np.ndarray, sample_rate: int = SR,
               channels: int = 2) -> Path:
    """写 16 bit wav。"""
    import wave

    data = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    if channels == 2:
        data = np.repeat(data, 2)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(data.tobytes())
    return path


def _dark_bgm(seconds: float = 6.0, sample_rate: int = SR) -> np.ndarray:
    """暗色的 ambient 质感：低通噪声 + 低频脉冲。

    低通到 900 Hz 保证频谱重心够低、1~4 kHz 占比够小——正是规范要的那种。
    """
    rng = np.random.default_rng(42)
    count = int(seconds * sample_rate)
    t = np.arange(count) / sample_rate
    noise = rng.normal(0, 1, count)
    spectrum = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(count, 1 / sample_rate)
    spectrum[freqs > 900] = 0
    noise = np.fft.irfft(spectrum, count)
    pulse = (np.sin(2 * np.pi * 80 * t) > 0.9).astype(float)
    return noise * 0.25 + pulse * 0.35


def _speech_like(seconds: float = 6.0, dbfs: float = -25.0,
                 sample_rate: int = SR) -> np.ndarray:
    """电平稳定的类语音信号（300~3400 Hz 带噪声）。"""
    rng = np.random.default_rng(7)
    count = int(seconds * sample_rate)
    noise = rng.normal(0, 1, count)
    spectrum = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(count, 1 / sample_rate)
    spectrum[(freqs < 300) | (freqs > 3400)] = 0
    band = np.fft.irfft(spectrum, count)
    band *= 10 ** (dbfs / 20) / np.sqrt(np.mean(band ** 2))
    return band


def _rms_db(samples: np.ndarray) -> float:
    return 20 * np.log10(np.sqrt(np.mean(samples ** 2)))


def _make_track(path: Path, seconds: float = 6.0, sample_rate: int = SR,
                channels: int = 2, lufs: float = -20.0,
                peak: float = -3.0) -> Path:
    """造一条母带（先归一化再改采样率/声道，模拟入库后的成品）。"""
    base = _write_wav(path.with_suffix(".raw.wav"), _dark_bgm(seconds, sample_rate),
                      sample_rate, 1)
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", str(base),
        "-af", f"loudnorm=I={lufs}:TP={peak}:LRA=11",
        "-ar", str(sample_rate), "-ac", str(channels),
        "-c:a", "pcm_s16le", str(path),
    ], check=True)
    base.unlink(missing_ok=True)
    return path


def _profile(**overrides) -> bgm.AudioProfile:
    """造一条实测特征（纯函数测试用，不必真造音频）。"""
    base = {
        "path": "fake.wav", "duration_s": 60.0, "sample_rate": 48000,
        "channels": 2, "lufs": -20.0, "true_peak_db": -6.0,
        "band_ratios": {"sub": 0.2, "bass": 0.4, "mid": 0.15, "voice": 0.1,
                        "presence": 0.1, "air": 0.05},
        "centroid_hz": 800.0,
    }
    base.update(overrides)
    return bgm.AudioProfile(**base)


# ---------------------------------------------------------------- 规范同步


def _spec_text() -> str:
    return (bgm.AIV_ROOT / "背景音乐规范.md").read_text(encoding="utf-8")


def _norm(text: str) -> str:
    """把 -3.0 归一成 -3，规范与代码的数值写法就能对上了。"""
    import re

    return re.sub(r"(\d)\.0(?!\d)", r"\1", text)


def test_spec_declares_every_rule():
    """规范 §7 的规则表必须覆盖代码里的每一条规则。"""
    spec = _spec_text()
    for rule_id in bgm.RULE_IDS:
        assert f"`{rule_id}`" in spec, f"规范里没有规则 {rule_id}"


def test_spec_declares_no_extra_rule():
    """规范里不能有代码里不存在的规则编号。"""
    import re

    spec_ids = set(re.findall(r"`(bgm\.[a-z]+-[a-z-]+)`", _spec_text()))
    assert spec_ids <= set(bgm.RULE_IDS), (
        f"规范里有代码里没有的规则：{sorted(spec_ids - set(bgm.RULE_IDS))}"
    )


def test_spec_and_code_agree_on_thresholds():
    """阈值：规范里写的和代码里的一致。"""
    spec = _norm(_spec_text())
    assert f"{bgm.MASTER_LUFS:g} LUFS" in spec
    assert f"{bgm.MAX_TRUE_PEAK_DB:g} dBTP" in spec
    assert f"{bgm.MAX_VOICE_BAND:.0%}" in spec
    assert f"{bgm.MAX_AIR_BAND:.0%}" in spec
    assert f"{bgm.MAX_CENTROID_HZ:.0f} Hz" in spec
    assert f"{bgm.BGM_GAIN_DB:g} dB" in spec
    assert f"{bgm.DUCK_DEPTH_DB:g} dB" in spec
    assert f"{bgm.EQ_BELL_HZ} Hz" in spec
    assert f"{bgm.EQ_BELL_DB:g} dB" in spec
    assert f"{bgm.HIGHPASS_HZ} Hz" in spec


def test_spec_lists_every_allowed_license():
    """授权白名单：规范 §2.1 的表格和代码一致。"""
    spec = _spec_text()
    for license_name in bgm.ALLOWED_LICENSES:
        assert license_name in spec, f"规范里没有授权 {license_name}"


def test_spec_has_no_broken_characters():
    assert "�" not in _spec_text()


# ---------------------------------------------------------------- 测量


def test_measure_reads_a_real_file(tmp_path):
    """实测：时长、采样率、声道、响度都对得上。"""
    path = _make_track(tmp_path / "track.wav", seconds=4.0)
    profile = bgm.measure(path)
    assert profile.sample_rate == 48000
    assert profile.channels == 2
    assert abs(profile.duration_s - 4.0) < 0.2
    assert abs(profile.lufs - bgm.MASTER_LUFS) < 1.5


def test_band_ratios_add_up():
    """各频段占比加起来接近 1。"""
    ratios = bgm.band_ratios(_dark_bgm(2.0))
    total = sum(v for k, v in ratios.items() if not k.startswith("_"))
    assert 0.95 < total < 1.05


def test_dark_music_has_a_lower_centroid_than_bright():
    """频谱重心要能区分暗色与亮色。"""
    rng = np.random.default_rng(1)
    bright = rng.normal(0, 1, SR * 2)
    dark = bgm.band_ratios(_dark_bgm(2.0))["_centroid_hz"]
    light = bgm.band_ratios(bright)["_centroid_hz"]
    assert dark < light


# ---------------------------------------------------------------- 选曲规则


def test_wrong_sample_rate_is_rejected():
    findings = bgm.check_profile(_profile(sample_rate=44100))
    assert any(f.rule_id == "bgm.sample-rate" for f in findings)


def test_mono_is_rejected():
    findings = bgm.check_profile(_profile(channels=1))
    assert any(f.rule_id == "bgm.channels" for f in findings)


def test_short_track_is_rejected():
    findings = bgm.check_profile(_profile(duration_s=10.0), required_duration_s=30.0)
    assert any(f.rule_id == "bgm.duration" for f in findings)


def test_hot_true_peak_is_rejected():
    findings = bgm.check_profile(_profile(true_peak_db=1.5))
    assert any(f.rule_id == "bgm.true-peak" for f in findings)


def test_too_much_voice_band_is_rejected():
    ratios = dict(_profile().band_ratios)
    ratios["voice"] = 0.55
    findings = bgm.check_profile(_profile(band_ratios=ratios))
    assert any(f.rule_id == "bgm.voice-band" for f in findings)


def test_too_much_air_is_rejected():
    ratios = dict(_profile().band_ratios)
    ratios["air"] = 0.3
    findings = bgm.check_profile(_profile(band_ratios=ratios))
    assert any(f.rule_id == "bgm.air-band" for f in findings)


def test_bright_music_is_rejected():
    findings = bgm.check_profile(_profile(centroid_hz=6000.0))
    assert any(f.rule_id == "bgm.centroid" for f in findings)


def test_a_compliant_track_passes(tmp_path):
    """造一条合规曲子，应该一条规则都不触发。"""
    path = _make_track(tmp_path / "good.wav", seconds=5.0)
    findings = bgm.check_track(path)
    assert findings == [], [str(f) for f in findings]


# ---------------------------------------------------------------- 台账


def _entry(**overrides) -> bgm.TrackEntry:
    base = {
        "id": "motif-01", "title": "Deep Blue", "artist": "Someone",
        "source": "pixabay", "source_url": "https://example.invalid/x",
        "license": "CC0-1.0", "series_role": "motif",
        "local_path": "music/tracks/motif-01.wav",
        "sha256": "a" * 64, "downloaded_at": "2026-11-11",
    }
    base.update(overrides)
    return bgm.TrackEntry(**base)


def test_unknown_license_is_rejected():
    findings = bgm.check_library([_entry(license="CC-BY-NC-4.0")],
                                 verify_fingerprint=False)
    assert any(f.rule_id == "bgm.license" for f in findings)


def test_missing_attribution_is_rejected():
    findings = bgm.check_library(
        [_entry(license="CC-BY-4.0", attribution_required=True,
                attribution_text="")],
        verify_fingerprint=False,
    )
    assert any(f.rule_id == "bgm.attribution" for f in findings)


def test_missing_fingerprint_is_rejected():
    findings = bgm.check_library([_entry(sha256="")], verify_fingerprint=False)
    assert any(f.rule_id == "bgm.fingerprint" for f in findings)


def test_mismatched_fingerprint_is_rejected(tmp_path):
    track = tmp_path / "t.wav"
    track.write_bytes(b"not the real file")
    entry = _entry(local_path=f"music/tracks/{track.name}")
    # 让路径能解析到真实文件
    entry = bgm.TrackEntry(**{**entry.to_dict(), "local_path": str(track)})
    findings = bgm.check_library([entry])
    assert any(f.rule_id == "bgm.fingerprint" for f in findings)


def test_two_motifs_are_rejected():
    findings = bgm.check_library(
        [_entry(id="m1"), _entry(id="m2")], verify_fingerprint=False)
    assert any(f.rule_id == "bgm.series-role" for f in findings)


def test_illegal_series_role_is_rejected():
    findings = bgm.check_library([_entry(series_role="jingle")],
                                 verify_fingerprint=False)
    assert any(f.rule_id == "bgm.series-role" for f in findings)


def test_clean_library_passes():
    findings = bgm.check_library([_entry()], verify_fingerprint=False)
    assert findings == [], [str(f) for f in findings]


def test_library_round_trip(tmp_path):
    """台账写入再读出来，内容不变。"""
    path = tmp_path / "library.json"
    bgm.save_library([_entry()], path)
    loaded = bgm.load_library(path)
    assert len(loaded) == 1
    assert loaded[0].id == "motif-01"
    assert loaded[0].license == "CC0-1.0"


def test_shipped_library_is_valid():
    """仓库里的台账本身要自洽。"""
    assert bgm.LIBRARY_PATH.exists()
    findings = bgm.check_library()
    assert findings == [], [str(f) for f in findings]


def test_attribution_lines_only_for_required():
    entries = [
        _entry(id="a", license="CC-BY-4.0", attribution_required=True,
               attribution_text="Deep Blue by Someone (CC-BY 4.0)"),
        _entry(id="b"),
    ]
    assert bgm.attribution_lines(entries) == [
        "Deep Blue by Someone (CC-BY 4.0)"]


# ---------------------------------------------------------------- ducking


def test_duck_depth_is_exact(tmp_path):
    """持续旁白下，BGM 正好压低 DUCK_DEPTH_DB。

    这是 ducking 规则的机器判据：深度必须是确定的数。
    """
    bgm_path = _make_track(tmp_path / "bgm.wav", seconds=6.0)
    narration = _write_wav(tmp_path / "narr.wav", _speech_like(6.0), SR, 1)
    out = bgm.duck_bgm(bgm_path, narration, tmp_path / "ducked.wav")

    before = bgm.decode_mono(bgm_path)
    after = bgm.decode_mono(out)
    depth = _rms_db(before) - _rms_db(after)
    assert abs(depth - abs(bgm.DUCK_DEPTH_DB)) < 0.5, f"实测压深 {depth:.2f} dB"


def test_duck_leaves_silence_alone(tmp_path):
    """没有旁白的地方，BGM 一分不压。"""
    bgm_path = _make_track(tmp_path / "bgm.wav", seconds=6.0)
    silence = _write_wav(tmp_path / "narr.wav", np.zeros(SR * 6), SR, 1)
    out = bgm.duck_bgm(bgm_path, silence, tmp_path / "ducked.wav")
    before = bgm.decode_mono(bgm_path)
    after = bgm.decode_mono(out)
    assert abs(_rms_db(before) - _rms_db(after)) < 0.2


def test_speech_activity_detects_speech():
    """包络要能认出「有人在说话」。"""
    narration = _speech_like(2.0)
    activity = bgm.speech_activity(narration)
    assert activity.mean() > 0.9


def test_speech_activity_ignores_silence():
    activity = bgm.speech_activity(np.zeros(SR * 2))
    assert activity.max() == 0.0


def test_duck_curve_is_bounded():
    """增益曲线取值在 (0, 1]：说话时 < 1，安静时 = 1。"""
    narration = _speech_like(2.0)
    curve = bgm.duck_curve(narration)
    assert 0 < curve.min() <= 1
    assert curve.max() <= 1.0


def test_duck_curve_covers_every_sample():
    """曲线要逐样本对齐旁白：末尾不足一窗也得补齐。

    旁白解码长度常常不是 10 ms 窗的整数倍（mp3 解码会裁掉尾部样本），
    曲线若按整窗截断就会比旁白短一截，混音时两边长度对不上。
    """
    narration = _speech_like(4.0)[:144336]
    assert narration.size % 480 != 0, "这个用例要的就是非整窗长度"
    curve = bgm.duck_curve(narration)
    assert curve.size == narration.size


def test_duck_bgm_handles_partial_window(tmp_path):
    """旁白长度不是整窗时，ducking 也要照常出片，且不吞样本。"""
    bgm_path = _make_track(tmp_path / "bgm.wav", seconds=6.0)
    samples = 144336
    narration = _write_wav(tmp_path / "narr.wav", _speech_like(4.0)[:samples], SR, 1)
    out = bgm.duck_bgm(bgm_path, narration, tmp_path / "ducked.wav")
    assert bgm.decode_mono(out).size == samples


# ---------------------------------------------------------------- 成片级判据


def test_to_mono_is_an_equal_weight_average():
    """立体声下混要等权平均，不能用 ffmpeg 的 `-ac 1`。

    `-ac 1` 的系数是每声道 0.7071，对左右同相的信号整体高 3 dB；
    用它量电平差会凭空多出 3 dB。
    """
    stereo = np.stack([np.full(100, 0.5), np.full(100, 0.5)], axis=1)
    mono = bgm._to_mono(stereo)
    assert np.allclose(mono, 0.5), f"下混成了 {mono[0]:.4f}，应为 0.5"


def test_saturated_mask_picks_only_speaking_frames():
    """饱和掩码只圈出「正在说话」的帧。

    静音段也要在掩码外：那里 duck 增益正在回升，算进去会把压深算浅。
    说话段开头有一段不算：上升沿有 120 ms 时间常数，爬到平台还要 560 ms。
    """
    speaking = _speech_like(4.0)
    silence = np.zeros(SR)
    narration = np.concatenate([silence, speaking])
    mask = bgm.saturated_mask(narration)
    assert not mask[:SR].any(), "静音段不该被圈进去"
    plateau = mask[int(SR + 0.6 * SR):]
    assert plateau.mean() > 0.9, f"平台段只圈到 {plateau.mean() * 100:.1f}%"


def test_measure_duck_depth_is_exact_on_synthetic(tmp_path):
    """稳态 duck 深度量出来就是设定的那个数。"""
    bgm_path = _make_track(tmp_path / "bgm.wav", seconds=6.0)
    narration = _write_wav(tmp_path / "narr.wav", _speech_like(4.0), SR, 1)
    depth = bgm.measure_duck_depth(bgm_path, narration)
    assert abs(depth - abs(bgm.DUCK_DEPTH_DB)) < 0.5, f"实测压深 {depth:.2f} dB"


def test_measure_mix_reads_the_level_gap(tmp_path):
    """成片级测量：旁白与 BGM 的电平差要被量出来。

    这里手工造一条「成片」：旁白延迟到正文起点，BGM 按 duck 后的电平铺底。
    """
    body_start, body_end = 1.0, 5.0
    bgm_path = _make_track(tmp_path / "bgm.wav", seconds=8.0)
    voice = _speech_like(4.0)
    narration = _write_wav(tmp_path / "narr.wav", voice, SR, 1)

    bed = bgm.decode_mono(bgm_path)
    delay = int(body_start * SR)
    span = int((body_end - body_start) * SR)
    gain = 10 ** ((bgm.BGM_GAIN_DB + bgm.DUCK_DEPTH_DB) / 20)
    mix = np.zeros(delay + span)
    mix[delay:delay + voice.size] = voice
    mix[delay:delay + span] += bed[:span] * gain
    video = _write_wav(tmp_path / "film.wav", mix, SR, 2)

    report = bgm.measure_mix(video, narration, bgm_path, body_start, body_end)
    assert abs(report.voice_gain_db) < 0.2, f"旁白增益偏差 {report.voice_gain_db:.2f} dB"
    assert abs(report.duck_depth_db - abs(bgm.DUCK_DEPTH_DB)) < 0.5
    # 手工算一遍期望值
    active = bgm.saturated_mask(voice)
    expected = (_rms_db(voice[active])
                - _rms_db(bed[:span][active[:span]] * gain))
    assert abs(report.voice_to_bgm_db - expected) < 1.0, (
        f"实测差值 {report.voice_to_bgm_db:.2f} dB，期望 {expected:.2f} dB")


def test_check_mix_flags_each_violation():
    """四条判据各自都要能抓到违规。"""
    good = bgm.MixReport(
        duck_depth_db=abs(bgm.DUCK_DEPTH_DB), voice_to_bgm_db=20.0,
        voice_rms_db=-25.0, bgm_rms_db=-45.0, true_peak_db=-3.0,
        voice_gain_db=0.0, active_ratio=0.5, body_start_s=0.0, body_end_s=5.0)
    assert bgm.check_mix(good) == []

    bad_depth = bgm.MixReport(**{**good.__dict__, "duck_depth_db": 3.0})
    assert any(f.rule_id == "bgm.mix-duck-depth" for f in bgm.check_mix(bad_depth))

    bad_gap = bgm.MixReport(**{**good.__dict__, "voice_to_bgm_db": 8.0})
    assert any(f.rule_id == "bgm.mix-voice-to-bgm" for f in bgm.check_mix(bad_gap))

    bad_peak = bgm.MixReport(**{**good.__dict__, "true_peak_db": -0.2})
    assert any(f.rule_id == "bgm.mix-true-peak" for f in bgm.check_mix(bad_peak))

    bad_gain = bgm.MixReport(**{**good.__dict__, "voice_gain_db": -6.0})
    assert any(f.rule_id == "bgm.mix-voice-gain" for f in bgm.check_mix(bad_gain))


# ---------------------------------------------------------------- 混音链


def test_bgm_chain_has_the_documented_filters():
    """通道链里必须有高通、避让 bell 和固定增益。"""
    chain = bgm.bgm_chain()
    assert f"highpass=f={bgm.HIGHPASS_HZ}" in chain
    assert f"equalizer=f={bgm.EQ_BELL_HZ}" in chain
    assert f"g={bgm.EQ_BELL_DB}" in chain
    assert f"volume={10 ** (bgm.BGM_GAIN_DB / 20):.6f}" in chain


def test_eq_filter_notches_the_voice_band(tmp_path):
    """避让滤波要真的削掉 1~4 kHz。"""
    rng = np.random.default_rng(11)
    count = SR * 4
    noise = rng.normal(0, 1, count)
    spectrum = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(count, 1 / SR)
    spectrum /= np.sqrt(freqs + 1e-3)  # 粉噪近似
    pink = np.fft.irfft(spectrum, count)
    pink *= 10 ** (-20 / 20) / np.sqrt(np.mean(pink ** 2))
    src = _write_wav(tmp_path / "pink.wav", pink, SR, 1)
    dst = tmp_path / "pink_eq.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
                    "-af", bgm.eq_filter(), "-c:a", "pcm_s16le", str(dst)],
                   check=True)
    before = bgm.band_ratios(bgm.decode_mono(src))
    after = bgm.band_ratios(bgm.decode_mono(dst))
    assert after["voice"] < before["voice"] * 0.6, (
        f"1~4 kHz 只从 {before['voice']:.1%} 降到 {after['voice']:.1%}")


# ---------------------------------------------------------------- 命令行


def test_cli_bgm_check_passes_on_good_track(tmp_path, capsys):
    path = _make_track(tmp_path / "good.wav", seconds=4.0)
    code = cli.main(["bgm", "check", "--music", str(path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "合格" in out


def test_cli_bgm_check_fails_on_bad_track(tmp_path, capsys):
    path = _make_track(tmp_path / "bad.wav", seconds=4.0, sample_rate=44100)
    code = cli.main(["bgm", "check", "--music", str(path)])
    captured = capsys.readouterr()
    assert code == 1
    assert "bgm.sample-rate" in captured.out


def test_cli_bgm_mix_prints_parameters(capsys):
    code = cli.main(["bgm", "mix"])
    out = capsys.readouterr().out
    assert code == 0
    assert str(bgm.EQ_BELL_HZ) in out
    assert str(bgm.DUCK_DEPTH_DB) in out


def test_cli_bgm_library_on_empty_library(tmp_path, capsys):
    path = tmp_path / "library.json"
    path.write_text(json.dumps({"version": 1, "tracks": []}), encoding="utf-8")
    code = cli.main(["bgm", "library", "--library", str(path)])
    assert code == 0
    assert "0 个问题" in capsys.readouterr().out
