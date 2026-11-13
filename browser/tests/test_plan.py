"""发布计划读取。"""

import json

import pytest

from browser.plan import PlanError, load_plan, parse_topics


def test_parse_topics_splits_on_whitespace():
    assert parse_topics("#PostgreSQL #数据库内核 #行锁 #MVCC") == [
        "PostgreSQL", "数据库内核", "行锁", "MVCC"]


def test_parse_topics_tolerates_missing_hash_and_mixed_separators():
    assert parse_topics("PostgreSQL, 行锁\nMVCC") == ["PostgreSQL", "行锁", "MVCC"]


def test_parse_topics_drops_empty_pieces():
    assert parse_topics("  #A   #  #B ") == ["A", "B"]


def test_load_plan_reads_the_package(package_dir):
    plan = load_plan(package_dir)
    assert plan.episode == "ep01"
    assert plan.title == "两个事务改同一行，谁先谁后"
    assert plan.description == "MVCC 只管读和写。"
    assert plan.topics == ["PostgreSQL", "行锁"]
    assert plan.status == "packaged"
    assert plan.has_all_files() is True


def test_load_plan_rejects_a_missing_directory(tmp_path):
    with pytest.raises(PlanError):
        load_plan(tmp_path / "nope")


def test_load_plan_rejects_a_package_without_a_title(package_dir):
    (package_dir / "title.txt").unlink()
    with pytest.raises(PlanError) as error:
        load_plan(package_dir)
    assert "title.txt" in str(error.value)


def test_load_plan_rejects_an_empty_title(package_dir):
    (package_dir / "title.txt").write_text("   ", encoding="utf-8")
    with pytest.raises(PlanError) as error:
        load_plan(package_dir)
    assert "标题" in str(error.value)


def test_load_plan_rejects_a_broken_meta_json(package_dir):
    (package_dir / "meta.json").write_text("{ not json", encoding="utf-8")
    with pytest.raises(PlanError):
        load_plan(package_dir)


def test_missing_video_shows_up_as_missing_not_as_a_crash(package_dir):
    (package_dir / "video.mp4").unlink()
    plan = load_plan(package_dir)
    assert plan.video is None
    assert plan.has_all_files() is False


def test_description_with_topics_appends_the_tags(package_dir):
    plan = load_plan(package_dir)
    body = plan.description_with_topics()
    assert body == "MVCC 只管读和写。\n#PostgreSQL #行锁"


def test_description_with_topics_without_description(package_dir):
    (package_dir / "description.txt").unlink()
    plan = load_plan(package_dir)
    assert plan.description_with_topics() == "#PostgreSQL #行锁"
