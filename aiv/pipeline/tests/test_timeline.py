import json

from pyv import timeline


def _base_scenes():
    return [
        {"id": "s01", "start": 0.0, "end": 2.0, "type": "code",
         "renderer": "pyv.scenes.s01_intro", "subtitle": "我是独立开发者"},
        {"id": "s02", "start": 2.0, "end": 5.0, "type": "code",
         "renderer": "pyv.scenes.s02_serial", "subtitle": "发布端只有一个解码线程"},
    ]


def _storyboard(scenes=None, duration=5.0, subtitles=None):
    data = {
        "version": 1,
        "video": {"width": 1920, "height": 1080, "fps": 24, "duration": duration},
        "audio": {"narration": "pa_decode_v2.mp3", "bgm": None},
        "subtitle_style": {"primary": "#1B2A47", "outline": "#FFFFFF",
                           "position": "bottom-center"},
        "scenes": scenes if scenes is not None else _base_scenes(),
    }
    if subtitles is not None:
        data["subtitles"] = subtitles
    return data


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
    assert any("不连续" in e for e in sb.validate())


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
    assert any("超过" in e for e in sb.validate())


def test_latin_subtitle_uses_display_width(tmp_path):
    scenes = _base_scenes()
    scenes[0]["subtitle"] = "openGauss 并行逻辑解码"
    sb = timeline.Storyboard.load(_write(tmp_path, _storyboard(scenes)))
    assert sb.validate() == []


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


def test_subtitle_events_are_validated_independently(tmp_path):
    subtitles = [
        {"start": 0.0, "end": 1.0, "text": "我是独立开发者"},
        {"start": 1.0, "end": 2.0, "text": "海量数据库的并行解码"},
    ]
    sb = timeline.Storyboard.load(_write(tmp_path, _storyboard(subtitles=subtitles)))
    assert any("禁止词" in e for e in sb.validate())


def test_subtitle_events_fall_back_to_scenes(tmp_path):
    sb = timeline.Storyboard.load(_write(tmp_path, _storyboard()))
    events = sb.subtitle_events()
    assert len(events) == 2
    assert events[0].text == "我是独立开发者"


def test_display_width_counts_cjk_as_one_and_latin_as_half():
    assert timeline.display_width("并行解码") == 4.0
    assert timeline.display_width("PG18") == 2.0
    assert timeline.display_width("PG18 并行解码") == 6.5
