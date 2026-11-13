"""视频号流程：选择器表、字数限制、以及跑在本地假页面上的完整填表。"""

import json

import pytest

from browser.driver import PageDriver
from browser.flows import channels as flow_mod
from browser.flows.channels import ChannelsConfig, ChannelsFlow, FlowError, check_limits
from browser.plan import load_plan


# -- 选择器表 ---------------------------------------------------------------

def test_missing_selectors_file_says_what_to_do(tmp_path):
    with pytest.raises(FlowError) as error:
        ChannelsConfig.load(tmp_path / "nope.json")
    assert "probe" in str(error.value)


def test_need_reports_the_missing_key_instead_of_doing_nothing(tmp_path):
    target = tmp_path / "s.json"
    target.write_text(json.dumps({"selectors": {"post": {}}}), encoding="utf-8")
    config = ChannelsConfig.load(target)
    with pytest.raises(FlowError) as error:
        config.need("post", "title_input")
    assert "title_input" in str(error.value)
    assert "probe" in str(error.value)


def test_config_reads_entry_url_and_text_layout(fixture_selectors):
    config = ChannelsConfig.load(fixture_selectors)
    assert config.text_layout == "combined"
    assert config.entry_url.startswith("file://")
    assert config.need("post", "video_file_input") == ["#video-file"]


# -- 字数限制 ---------------------------------------------------------------

def _plan_with(title="标题", description="正文", topics=None):
    from browser.plan import PublishPlan
    from pathlib import Path
    return PublishPlan(
        episode="ep01", package_dir=Path("."), title=title,
        description=description, topics=topics or [],
    )


def test_a_normal_plan_has_no_limit_problems():
    assert check_limits(_plan_with(title="两个事务改同一行，谁先谁后",
                                   description="MVCC 只管读和写。",
                                   topics=["PostgreSQL", "行锁"])) == []


def test_an_over_long_title_is_reported():
    problems = check_limits(_plan_with(title="标" * 23))
    assert any("标题" in p and "22" in p for p in problems)


def test_an_over_long_description_is_reported():
    problems = check_limits(_plan_with(description="正" * 1001))
    assert any("简介" in p for p in problems)


def test_too_many_topics_are_reported():
    problems = check_limits(_plan_with(topics=[f"t{i}" for i in range(6)]))
    assert any("话题" in p and "5" in p for p in problems)


def test_an_over_long_topic_is_reported():
    problems = check_limits(_plan_with(topics=["话" * 16]))
    assert any("行锁" in p or "话" in p for p in problems)


# -- 完整流程（本地假页面） --------------------------------------------------

def test_prepare_fills_the_form_from_the_package(page, fixture_selectors, package_dir):
    plan = load_plan(package_dir)
    config = ChannelsConfig.load(fixture_selectors)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000), config)

    filled = flow.prepare(plan)

    assert filled["title"] == "两个事务改同一行，谁先谁后"
    assert filled["topics"] == ["PostgreSQL", "行锁"]
    # combined 布局：标题是描述框的第一行，后面是正文与话题
    body = page.input_value("#desc")
    assert body.splitlines()[0] == "两个事务改同一行，谁先谁后"
    assert "MVCC 只管读和写。" in body
    assert "#PostgreSQL #行锁" in body
    # 视频与封面都真的进了文件框
    assert page.eval_on_selector("#video-file", "el => el.files[0].name") == "video.mp4"
    assert page.eval_on_selector("#cover-file", "el => el.files[0].name") == "cover-16x9.jpg"
    # 原创声明勾上了
    assert page.is_checked("#original")


def test_prepare_uses_the_alternative_cover_when_asked(page, fixture_selectors, package_dir):
    plan = load_plan(package_dir)
    config = ChannelsConfig.load(fixture_selectors)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000), config)

    flow.prepare(plan, cover=plan.cover_alt)

    assert page.eval_on_selector("#cover-file", "el => el.files[0].name") == "cover-9x16.jpg"


def test_prepare_refuses_a_package_without_a_video(page, fixture_selectors, package_dir):
    (package_dir / "video.mp4").unlink()
    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(fixture_selectors))
    with pytest.raises(FlowError) as error:
        flow.prepare(plan)
    assert "成片" in str(error.value)


def test_submit_clicks_and_returns_the_published_url(page, fixture_selectors, package_dir):
    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(fixture_selectors))
    flow.prepare(plan)

    url = flow.submit()

    assert url == "https://channels.weixin.qq.com/platform/post/fixture-1"


def test_a_separate_layout_fills_two_boxes(page, fixture_selectors, package_dir):
    raw = json.loads(fixture_selectors.read_text(encoding="utf-8"))
    raw["text_layout"] = "separate"
    fixture_selectors.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(fixture_selectors))
    flow.prepare(plan)

    assert page.input_value("#title") == "两个事务改同一行，谁先谁后"
    body = page.input_value("#desc")
    assert "两个事务改同一行，谁先谁后" not in body
    assert body.startswith("MVCC 只管读和写。")


def test_submit_reports_no_url_instead_of_inventing_one(page, fixture_selectors, package_dir):
    raw = json.loads(fixture_selectors.read_text(encoding="utf-8"))
    raw["selectors"]["post"]["published_url_text"] = []
    fixture_selectors.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(fixture_selectors))
    flow.prepare(plan)

    assert flow.submit() is None
