"""视频号流程：选择器表、字数限制、以及跑在本地假页面上的完整填表。"""

import json

import pytest

from browser.driver import PageDriver
from browser.flows import channels as flow_mod
from browser.flows.channels import ChannelsConfig, ChannelsFlow, FlowError, check_limits
from browser.plan import load_plan


# -- 选择器表 ---------------------------------------------------------------

def test_the_default_selectors_file_is_where_the_code_thinks_it_is():
    """默认选择器表的路径必须真的存在。

    这条测试挡的是一类很闷的错：路径少算一层目录，
    程序不报错，只是「选择器表不存在」——而那时人已经打开浏览器了。
    """
    assert flow_mod.DEFAULT_SELECTORS_PATH.is_file()
    assert flow_mod.DEFAULT_SELECTORS_PATH.name == "channels.json"
    assert flow_mod.DEFAULT_SELECTORS_PATH.parent.name == "selectors"


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
    assert config.text_layout == "separate"
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
    assert check_limits(_plan_with(title="两个事务改同一行 谁先谁后",
                                   description="MVCC 只管读和写。",
                                   topics=["PostgreSQL", "行锁"])) == []


def test_a_chinese_comma_in_the_title_is_rejected():
    """实测：视频号短标题不收中文逗号，报「标题包含特殊字符……逗号可用空格代替」。"""
    problems = check_limits(_plan_with(title="两个事务改同一行，谁先谁后"))
    assert any("「，」" in p and "空格" in p for p in problems)


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
    # separate 布局：标题进短标题框，描述进 contenteditable
    assert page.input_value("#title") == "两个事务改同一行，谁先谁后"
    body = page.inner_text("#desc")
    assert "MVCC 只管读和写。" in body
    assert "#PostgreSQL #行锁" in body
    # 话题被编辑器变成了真话题 chip（不是普通文字）
    assert filled["topic_chips_in_page"] == 2
    # 读回校验的结论也记下来了
    assert filled["title_in_page"] == "两个事务改同一行，谁先谁后"
    # 视频与封面都真的进了文件框
    assert page.eval_on_selector("#video-file", "el => el.files[0].name") == "video.mp4"
    # 声明原创：两层勾选都走通了
    assert page.is_checked(".declare-original-checkbox input[type=checkbox]")


def test_verify_filled_catches_a_title_that_did_not_land(page, fixture_selectors, package_dir):
    """填进去 ≠ 页面收下了——短标题被改了就必须报错。"""
    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(fixture_selectors))
    flow.prepare(plan)
    # 模拟平台把短标题截断了
    page.eval_on_selector("#title", "el => { el.value = '被截断'; }")
    with pytest.raises(FlowError) as error:
        flow.verify_filled(plan.title, plan.description, plan.topics)
    assert "短标题没填对" in str(error.value)


def test_verify_filled_catches_topics_that_are_just_text(page, fixture_selectors, package_dir):
    """话题没变成真话题也要报错——那等于话题根本没加上。"""
    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(fixture_selectors))
    flow.prepare(plan)
    # 把话题 chip 拆回普通文字
    page.eval_on_selector("#desc", "el => { el.innerHTML = el.innerText; }")
    with pytest.raises(FlowError) as error:
        flow.verify_filled(plan.title, plan.description, plan.topics)
    assert "话题" in str(error.value)


def test_prepare_reports_that_the_cover_is_the_platform_one(page, fixture_selectors, package_dir):
    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(fixture_selectors))
    filled = flow.prepare(plan)
    assert "自动生成" in filled["cover"]


def test_prepare_uploads_the_cover_when_one_is_given(page, fixture_selectors, package_dir):
    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(fixture_selectors))
    flow.prepare(plan, cover=plan.cover)
    assert page.eval_on_selector("#cover-file", "el => el.files[0].name") == "cover-16x9.jpg"


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
    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(fixture_selectors))
    flow.prepare(plan)

    assert page.input_value("#title") == "两个事务改同一行，谁先谁后"
    body = page.inner_text("#desc")
    assert "两个事务改同一行，谁先谁后" not in body
    assert body.startswith("MVCC 只管读和写。")


def test_declare_original_goes_through_the_terms_dialog(page, fixture_selectors, package_dir):
    """勾主勾选框会弹「原创权益」，得在弹窗里再勾一次同意、再点确认。"""
    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(fixture_selectors))
    flow.prepare(plan)

    # 弹窗里的同意框勾上了
    assert page.is_checked(".declare-original-dialog input.agree")
    # 弹窗关掉了
    hidden = page.evaluate(
        "() => getComputedStyle(document.querySelector("
        "'.declare-original-dialog .weui-desktop-dialog__wrp')).display")
    assert hidden == "none"


def test_declare_original_fails_loudly_when_it_does_not_stick(page, fixture_selectors,
                                                             package_dir, monkeypatch):
    """勾不上就要报错——不能把「没声明」当成「声明了」。"""
    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(fixture_selectors))

    def never_checked(self, selector):
        return False

    monkeypatch.setattr(PageDriver, "is_checked", never_checked)
    with pytest.raises(FlowError) as error:
        flow.prepare(plan)
    assert "声明原创" in str(error.value)


def test_submit_reports_no_url_instead_of_inventing_one(page, fixture_selectors, package_dir):
    raw = json.loads(fixture_selectors.read_text(encoding="utf-8"))
    raw["selectors"]["post"]["published_url_text"] = []
    fixture_selectors.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(fixture_selectors))
    flow.prepare(plan)

    assert flow.submit() is None
