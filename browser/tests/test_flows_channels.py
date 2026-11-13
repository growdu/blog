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
    """实测：视频号短标题上限是 **16 字**（投稿页标「标题超过16字限制」）。

    超限时「保存草稿」按钮直接变灰——所以这一步要在出包时就拦住。
    """
    problems = check_limits(_plan_with(title="标" * 17))
    assert any("标题" in p and "16" in p for p in problems)


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
    assert page.eval_on_selector("#cover-file", "el => el.files[0].name") == "cover-4x3.jpg"


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


# -- 视频还在处理中 ---------------------------------------------------------

def _with_mode(selectors_path, mode: str):
    """把夹具页面切到另一种模式（ready / never / dead）。"""
    raw = json.loads(selectors_path.read_text(encoding="utf-8"))
    raw["entry_url"] = f"{raw['entry_url']}?mode={mode}"
    selectors_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return selectors_path


def test_a_hidden_link_is_not_mistaken_for_the_published_url(page, fixture_selectors, package_dir):
    """**藏着的**链接不算「取到了链接」。

    Playwright 的 inner_text() 对 display:none 的元素返回的是 textContent，
    所以一条还没显示出来的链接也会被读出来——读出来就以为发布成功了，
    可页面上其实什么都没发生（2026-11-13 那次就是这样蒙混过去的）。
    """
    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(fixture_selectors))
    flow.prepare(plan)

    assert flow.read_published_url() is None


def test_prepare_waits_until_the_publish_button_is_actually_clickable(
        page, processing_selectors, package_dir):
    """上传完了 ≠ 平台处理完了。

    处理完之前「发表」是灰的。填完表不能就这么点——得等它能点。
    """
    import time

    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(processing_selectors))

    started = time.monotonic()
    flow.prepare(plan)
    waited = time.monotonic() - started

    # 假页面 1.2 秒后才把按钮变可点——等到了才算等到了
    assert waited >= 1.0
    assert page.eval_on_selector("#publish", "el => el.className") == \
        "weui-desktop-btn weui-desktop-btn_primary"


def test_prepare_refuses_to_go_on_while_the_video_is_still_processing(
        page, processing_selectors, package_dir):
    """按钮一直灰着就该报错——不能让流程带着一个点不动的按钮往下走。"""
    _with_mode(processing_selectors, "never")

    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(processing_selectors))

    with pytest.raises(FlowError) as error:
        flow.prepare(plan)
    assert "发表" in str(error.value)


def test_submit_never_clicks_a_gray_publish_button(page, processing_selectors, package_dir):
    """按钮没变可点之前，一次都不许点。

    2026-11-13 实测的坑：Playwright 点一个「只是样式变灰」的按钮，
    click() 正常返回，平台却什么也没做——稿件根本没发出去，
    而日志里看不出任何异常。
    """
    _with_mode(processing_selectors, "never")

    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(processing_selectors))

    with pytest.raises(FlowError):
        flow.prepare(plan)
    assert page.evaluate("() => window.__clicks()") == 0


def test_submit_fails_loudly_when_the_click_had_no_effect(
        page, processing_selectors, package_dir):
    """点得动，但点了页面什么反应也没有——要报错，不能装作成功。"""
    _with_mode(processing_selectors, "dead")

    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(processing_selectors))
    flow.prepare(plan)

    with pytest.raises(FlowError) as error:
        flow.submit()
    message = str(error.value)
    assert "没反应" in message
    # 报错要告诉人下一步怎么办：先核实，别急着重发
    assert "核实" in message


def test_submit_still_works_once_the_video_is_processed(
        page, processing_selectors, package_dir):
    """等完了以后该发还是要发——这条是防「修成永远发不出去」的。"""
    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(processing_selectors))
    flow.prepare(plan)

    url = flow.submit()

    assert url == "https://channels.weixin.qq.com/platform/post/fixture-1"
    assert page.evaluate("() => window.__clicks()") == 1


# -- 存草稿（不发表） -------------------------------------------------------

def _draft_mode(selectors_path, mode: str):
    """把草稿夹具切到另一种模式（ready / never / dead）。"""
    raw = json.loads(selectors_path.read_text(encoding="utf-8"))
    raw["entry_url"] = f"{raw['entry_url']}?mode={mode}"
    selectors_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return selectors_path


def test_draft_stores_it_and_the_draft_box_shows_it(page, draft_selectors, package_dir):
    """存草稿的权威判据是**草稿箱里能看见这一条**。

    「点了没报错」不算存上了——得回读草稿箱。
    """
    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(draft_selectors))

    flow.prepare(plan, wait_for="draft")
    flow.save_draft()
    # 存草稿**不是发表**：「发表」一次都没点
    # （这一步要在回读草稿箱之前查——回读会跳到另一个页面）
    assert page.evaluate("() => window.__publishClicks()") == 0

    assert flow.verify_draft(plan.description[:12]) is True
    rows = flow.read_draft_rows()
    # 行里显示的是**简介**，不是短标题
    assert any("MVCC 只管读和写。" in row for row in rows)


def test_draft_never_clicks_a_gray_draft_button(page, draft_selectors, package_dir):
    """「保存草稿」还没变可点之前，一次都不许点。

    和「发表」同一个坑：灰按钮没有 disabled 属性，
    Playwright 的 click() 正常返回，而平台什么也不做——
    **草稿根本没存上**，而日志里看不出任何异常。
    """
    _draft_mode(draft_selectors, "never")

    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(draft_selectors))

    with pytest.raises(FlowError) as error:
        flow.draft(plan)
    assert "保存草稿" in str(error.value)
    assert page.evaluate("() => window.__clicks()") == 0


def test_save_draft_does_not_treat_a_silent_page_as_a_failure(
        page, draft_selectors, package_dir):
    """实测（2026-11-13）：点完「保存草稿」**页面上没有任何反应**。

    表单原样留在页面上，没有提示条、URL 也没变。
    所以「点完有没有反应」不能当判据——存没存上要看草稿箱。
    把一次成功的存草稿报成失败，比漏报更糟。
    """
    _draft_mode(draft_selectors, "dead")

    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(draft_selectors))
    flow.prepare(plan, wait_for="draft")

    result = flow.save_draft()

    assert result["draft_clicked"] is True
    assert result["notices"] == []
    assert result["url_changed"] is False


def test_draft_fails_loudly_when_the_draft_box_does_not_show_it(
        page, draft_selectors, package_dir):
    """点了但草稿箱里没有这一条——要报错，不能装作存上了。"""
    _draft_mode(draft_selectors, "dead")

    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(draft_selectors))

    with pytest.raises(FlowError) as error:
        flow.draft(plan)
    message = str(error.value)
    assert "草稿箱里找不到" in message
    # 报错要告诉人下一步：先自己看一眼，别急着再点一次
    assert "别急着再点一次" in message


def test_draft_reports_when_the_draft_box_does_not_show_it(page, draft_selectors,
                                                            package_dir, monkeypatch):
    """点了有反应，但草稿箱里没有这一条——要报错，不能当成存上了。"""
    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(draft_selectors))
    monkeypatch.setattr(PageDriver, "texts_of", lambda self, selector: [])

    with pytest.raises(FlowError) as error:
        flow.draft(plan)
    assert "草稿箱里找不到" in str(error.value)


def test_verify_draft_reads_the_description_not_the_short_title(page, draft_selectors,
                                                                package_dir):
    """草稿箱的行里显示的是简介——拿短标题去匹配会找不到。"""
    plan = load_plan(package_dir)
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(draft_selectors))
    flow.prepare(plan, wait_for="draft")
    flow.save_draft()

    assert flow.verify_draft(plan.description[:12]) is True


# -- 取公开链接 -------------------------------------------------------------

def test_collect_published_url_reads_it_out_of_the_clipboard(page, list_selectors):
    """链接是从分享菜单的「复制视频链接」里抄回来的。

    **菜单里三项**：复制视频ID / 下载视频二维码 / 复制视频链接。
    点错第一项抄回来的是视频ID，不是链接。
    """
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(list_selectors))
    flow.open_content_list()
    page.context.grant_permissions(["clipboard-read", "clipboard-write"],
                                   origin=page.url)

    url = flow.collect_published_url("两个事务改同一行")

    assert url == "https://weixin.qq.com/sph/fixture-1"


def test_collect_published_url_gives_up_instead_of_inventing_one(page, list_selectors,
                                                               monkeypatch):
    """剪贴板里没有链接就返回 None——不能编一个出来。"""
    flow = ChannelsFlow(PageDriver(page, timeout_ms=3000),
                        ChannelsConfig.load(list_selectors))
    monkeypatch.setattr(PageDriver, "clipboard_text", lambda self: "")

    assert flow.collect_published_url("两个事务改同一行") is None
