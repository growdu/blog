"""字幕：storyboard 的字幕事件 → SRT。"""

from bilibili import subtitle


def test_timestamp_format():
    assert subtitle.format_timestamp(0.0) == "00:00:00,000"
    assert subtitle.format_timestamp(2.833) == "00:00:02,833"
    assert subtitle.format_timestamp(61.5) == "00:01:01,500"
    assert subtitle.format_timestamp(3661.25) == "01:01:01,250"


def test_build_srt_writes_one_block_per_event():
    events = (
        subtitle.SubtitleEvent(start=0.0, end=2.5, text="第一句"),
        subtitle.SubtitleEvent(start=2.5, end=5.0, text="第二句"),
    )
    srt = subtitle.build_srt(events)
    assert srt.startswith("1\n00:00:00,000 --> 00:00:02,500\n第一句\n")
    assert "2\n00:00:02,500 --> 00:00:05,000\n第二句" in srt
    assert srt.endswith("\n")


def test_build_srt_of_nothing_is_empty():
    assert subtitle.build_srt(()) == ""


def test_build_srt_accepts_anything_with_start_end_and_text():
    """鸭子类型：只要有 start/end/text 就能用，不必是某个具体的类。"""

    class Duck:
        def __init__(self, start, end, text):
            self.start = start
            self.end = end
            self.text = text

    srt = subtitle.build_srt([Duck(0.0, 1.0, "鸭子")])
    assert srt == "1\n00:00:00,000 --> 00:00:01,000\n鸭子\n"


# --- 从 storyboard 取事件 ----------------------------------------------------


def test_events_from_storyboard_prefers_the_subtitles():
    raw = {
        "subtitles": [{"start": 1.0, "end": 2.0, "text": "一句话"}],
        "scenes": [{"start": 0.0, "end": 3.0, "subtitle": "场景字幕"}],
    }
    events = subtitle.events_from_storyboard(raw)
    assert [(e.start, e.end, e.text) for e in events] == [(1.0, 2.0, "一句话")]


def test_events_from_storyboard_falls_back_to_the_scenes():
    """storyboard 里没有逐句字幕时，退化成按场景出字幕。"""
    raw = {"scenes": [{"start": 0.0, "end": 3.0, "subtitle": "场景字幕"}]}
    events = subtitle.events_from_storyboard(raw)
    assert [(e.start, e.end, e.text) for e in events] == [(0.0, 3.0, "场景字幕")]


def test_events_from_storyboard_of_nothing_is_empty():
    assert subtitle.events_from_storyboard({}) == []
