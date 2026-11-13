"""B站 流程：选择器表、字数限制、以及跑在本地假页面上的完整「存草稿」。

**为什么要有这组测试。** 2026-11-13 实测踩出来的坑是：
B站 的上传失败时**页面上什么都不显示**——没有报错、没有进度条，
传完又回到「点击上传」的样子，但服务端一条都没收到。
只看页面的流程会把「没传上去」当成「传成功了」，
于是拿着一个不存在的视频去填表，最后存下一个空草稿。

所以这里有一条测试专门盯住这件事：**服务端拒绝 → 立刻报错**，
而且报错里要带服务端返回的原文。
"""

import json

import pytest

from browser.driver import PageDriver
from browser.flows import bilibili as flow_mod
from browser.flows.bilibili import BilibiliConfig, BilibiliFlow, FlowError, check_limits
from browser.plan import load_bilibili_plan

FIXTURES = flow_mod.Path(__file__).resolve().parent / "fixtures"
POST_PAGE = FIXTURES / "bilibili-post.html"
SELECTORS = FIXTURES / "bilibili-selectors.json"


# -- 本地假服务器 -----------------------------------------------------------

@pytest.fixture
def bili_server():
    """一个只做两件事的本地 HTTP 服务。

    1. 伺服夹具页面；
    2. 收「上传请求」：文件内容里带 `REJECT` 就返 400 + JSON 错误，
       否则返 200。

    **为什么上传要真的发一次请求**：流程是靠**上传接口的响应码**判断成败的，
    页面假数据不算——那就测不到「服务端拒绝」这条路径了。
    """
    import http.server
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.startswith("/bilibili-post.html"):
                body = POST_PAGE.read_bytes()
                self._send(200, body, "text/html; charset=utf-8")
                return
            self._send(404, b"not found", "text/plain")

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            if b"REJECT" in body:
                self._send(400, json.dumps(
                    {"code": -400, "message": "上传被拒绝"}).encode(), "application/json")
                return
            self._send(200, b"HCSGW_OK", "text/plain")

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def bili_selectors(tmp_path, bili_server):
    """指向本地假页面的选择器表。"""
    raw = json.loads(SELECTORS.read_text(encoding="utf-8"))
    raw["entry_url"] = f"{bili_server}/bilibili-post.html"
    target = tmp_path / "bilibili-selectors.json"
    target.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return target


@pytest.fixture
def bili_package(tmp_path):
    """一个假的 B站 发布包目录，结构照 bilibili/out/<EP>/ 来。"""
    root = tmp_path / "ep01"
    root.mkdir()
    (root / "title.txt").write_text("一个 64 位计数器，决定所有事务的提交顺序", encoding="utf-8")
    (root / "description.txt").write_text("并发时 commit 的先后是乱的。", encoding="utf-8")
    (root / "tags.txt").write_text("openGauss,数据库,源码", encoding="utf-8")
    (root / "video.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    (root / "cover.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 64)
    (root / "subtitle.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\n字幕\n",
                                       encoding="utf-8")
    (root / "meta.json").write_text(
        json.dumps({"episode": "ep01", "status": "packaged"}, ensure_ascii=False),
        encoding="utf-8")
    return root


# -- 选择器表 ---------------------------------------------------------------

def test_the_default_selectors_file_is_where_the_code_thinks_it_is():
    """默认选择器表的路径必须真的存在。

    这条测试挡的是一类很闷的错：路径少算一层目录，
    程序不报错，只是「选择器表不存在」——而那时人已经打开浏览器了。
    """
    assert flow_mod.DEFAULT_SELECTORS_PATH.is_file()
    assert flow_mod.DEFAULT_SELECTORS_PATH.name == "bilibili.json"
    assert flow_mod.DEFAULT_SELECTORS_PATH.parent.name == "selectors"


def test_missing_selectors_file_says_what_to_do(tmp_path):
    with pytest.raises(FlowError) as error:
        BilibiliConfig.load(tmp_path / "nope.json")
    assert "probe" in str(error.value)


def test_need_reports_the_missing_key_instead_of_doing_nothing(tmp_path):
    target = tmp_path / "s.json"
    target.write_text(json.dumps({"selectors": {"post": {}}}), encoding="utf-8")
    config = BilibiliConfig.load(target)
    with pytest.raises(FlowError) as error:
        config.need("post", "title_input")
    assert "title_input" in str(error.value)
    assert "probe" in str(error.value)


def test_config_reads_entry_url_and_timeouts(bili_selectors):
    config = BilibiliConfig.load(bili_selectors)
    assert config.entry_url.endswith("/bilibili-post.html")
    assert config.upload_ready_ms == 15000
    assert config.need("post", "video_file_input") == ["#video-file"]


def test_the_upload_response_is_matched_even_with_a_query_string():
    """真实上传那条 URL 后面挂着一长串签名参数。

    **实测 2026-11-13**：真正的上传是分片 PUT，
    URL 是 `…/ugcfxever/<biz>.mp4?X-Amz-Algorithm=…&partNumber=1&uploadId=…`。
    判据要是写成 `url.endswith(".mp4")`，**永远不成立**——
    流程会在 `expect_response` 上死等满 15 分钟，
    而视频其实早就传上去了（这一条就是这么浪费掉一整轮的）。
    """
    flow = BilibiliFlow(PageDriver(None), BilibiliConfig())
    assert flow._is_upload_response(
        "https://jscs-luffy-upcdntx.bilivideo.com/ugcfxever/abc.mp4"
        "?X-Amz-Algorithm=AWS4-HMAC-SHA256&partNumber=1&uploadId=51397800")
    # 「合并分片」那条也算上传相关的响应
    assert flow._is_upload_response(
        "https://member.bilibili.com/upload/multipart/complete")
    # 秒传探测那条不算：它不传文件
    assert not flow._is_upload_response(
        "https://member.bilibili.com/OK?bucket=upos")
    assert not flow._is_upload_response("https://member.bilibili.com/x/vupre/web/")


# -- 发布包读取 -------------------------------------------------------------

def test_the_bilibili_package_reader_picks_up_every_file(bili_package):
    plan = load_bilibili_plan(bili_package)
    assert plan.episode == "ep01"
    assert plan.title == "一个 64 位计数器，决定所有事务的提交顺序"
    assert plan.description == "并发时 commit 的先后是乱的。"
    assert plan.tags == ["openGauss", "数据库", "源码"]
    assert plan.video and plan.video.is_file()
    assert plan.cover and plan.cover.is_file()
    assert plan.subtitle and plan.subtitle.is_file()
    assert plan.has_all_files()


def test_bilibili_tags_are_csv_without_hash(bili_package):
    """B站 的标签是英文逗号分隔、**不带 # 号**（视频号是 `#A #B`）。"""
    plan = load_bilibili_plan(bili_package)
    assert plan.tags_as_csv() == "openGauss,数据库,源码"
    assert "#" not in plan.tags_as_csv()


def test_a_bilibili_package_without_tags_still_loads(tmp_path):
    root = tmp_path / "ep02"
    root.mkdir()
    (root / "title.txt").write_text("标题", encoding="utf-8")
    plan = load_bilibili_plan(root)
    assert plan.tags == []
    assert plan.tags_as_csv() == ""


# -- 字数限制 ---------------------------------------------------------------

def _plan_with(title="标题", description="正文", tags=None):
    from pathlib import Path

    from browser.plan import BilibiliPlan
    return BilibiliPlan(
        episode="ep01", package_dir=Path("."), title=title,
        description=description, tags=tags or [],
    )


def test_a_normal_plan_has_no_limit_problems():
    assert check_limits(_plan_with(title="一个 64 位计数器，决定所有事务的提交顺序",
                                   description="并发时 commit 的先后是乱的。",
                                   tags=["openGauss", "数据库"])) == []


def test_an_over_long_title_is_reported():
    problems = check_limits(_plan_with(title="标" * 80))
    assert any("标题" in p and "79" in p for p in problems)


def test_an_over_long_description_is_reported():
    problems = check_limits(_plan_with(description="正" * 250))
    assert any("简介" in p and "249" in p for p in problems)


def test_an_over_long_tag_is_reported():
    problems = check_limits(_plan_with(tags=["标" * 21]))
    assert any("标签" in p and "20" in p for p in problems)


def test_over_long_tags_in_total_are_reported():
    problems = check_limits(_plan_with(tags=["标签" * 10] * 11))
    assert any("标签总长" in p and "199" in p for p in problems)


# -- 完整流程（跑在本地假页面上） -------------------------------------------

def test_draft_fills_the_form_and_saves_a_draft(page, bili_selectors, bili_package):
    """一条完整链路：传片 → 填表 → 选分区 → 传封面字幕 → 存草稿。"""
    flow = BilibiliFlow(PageDriver(page), BilibiliConfig.load(bili_selectors))
    plan = load_bilibili_plan(bili_package)

    filled = flow.draft(plan)

    assert filled["status"] == "drafted"
    assert filled["title"] == plan.title
    assert filled["description"] == plan.description
    assert filled["tags"] == plan.tags
    assert filled["partition"].startswith("科技数码")
    assert filled["creation_statement"] == "含AI生成内容"
    assert filled["copyright"] == "自制，禁止转载"
    assert filled["subtitle_uploaded"] is True
    assert "草稿保存成功" in filled["draft_notice"]

    # 页面上的实际内容也要对得上
    assert page.input_value("#title") == plan.title
    assert page.inner_text("#desc") == plan.description
    assert page.locator(".tag-pre-wrp .label-item-v2-container").count() == len(plan.tags)
    assert page.inner_text(".video-human-type p.select-item-cont") == "科技数码"
    assert page.input_value("#statement") == "含AI生成内容"
    assert page.input_value("#copyright-state") == "内容为自制：未经作者允许，禁止转载"


def test_the_blocking_notification_dialog_is_dismissed_before_filling(
        page, bili_selectors, bili_package):
    """上传完成后平台弹的通知权限框必须先关掉。

    **实测 2026-11-13**：那个框带着遮罩，不关掉它后面每一次点击
    都会被拦下来——表现是「元素明明在，Playwright 却说点不动」。
    """
    flow = BilibiliFlow(PageDriver(page), BilibiliConfig.load(bili_selectors))
    plan = load_bilibili_plan(bili_package)

    flow.open_entry()
    flow.upload_video(plan.video)
    flow.wait_form_ready()

    # 假页面上传完会弹这个框
    assert page.locator(".videoup-notification-dialog.open").count() == 1

    dismissed = flow.dismiss_blocking_dialogs()

    assert "notification" in dismissed
    assert page.locator(".videoup-notification-dialog.open").count() == 0
    # 通用弹窗（「定时发布时间不可用」那类）也要关
    assert page.locator("#generic-dialog.open").count() == 0


def test_the_platform_suggested_tags_are_removed_before_ours_are_added(
        page, bili_selectors, bili_package):
    """页面自带的推荐标签要先删干净。

    **实测**：分区=人工智能 时平台自动塞「生活记录/记录/剪辑」。
    不删就等于给每一期都贴上这三个。
    """
    flow = BilibiliFlow(PageDriver(page), BilibiliConfig.load(bili_selectors))
    plan = load_bilibili_plan(bili_package)
    _form_ready(page, flow, plan)

    flow.dismiss_blocking_dialogs()
    flow.set_partition()          # 换分区会带出推荐标签
    flow.fill_text(plan.title, plan.description, plan.tags)

    chips = page.locator(".tag-pre-wrp .label-item-v2-container")
    assert chips.count() == len(plan.tags)
    assert [chips.nth(i).inner_text() for i in range(chips.count())] == plan.tags


def test_the_cover_goes_through_the_cover_editor_dialog(
        page, bili_selectors, bili_package):
    """封面不是两个 input，是一个「封面制作」弹层。

    流程必须：点「添加封面」→ 传图 → 点「完成」→ **处理「同步 16:9」的
    确认框** → 再点「完成」→ 封面上传接口有 200。
    """
    flow = BilibiliFlow(PageDriver(page), BilibiliConfig.load(bili_selectors))
    plan = load_bilibili_plan(bili_package)
    _form_ready(page, flow, plan)
    flow.dismiss_blocking_dialogs()

    steps = flow.set_cover(plan.cover)

    assert steps == ["open", "upload", "saved"]
    assert page.locator(".cover-editor.open").count() == 0
    assert page.locator(".cover .cover-preview").count() == 1


def test_the_cover_cannot_be_confirmed_before_the_picture_is_actually_uploaded(
        page, bili_selectors, bili_package):
    """传完图但平台还没收好，「完成」点不动 → 要报错，别硬点。

    **静默跳过会让人以为封面设好了**，其实那还是平台自动截的图。
    """
    raw = json.loads(bili_selectors.read_text(encoding="utf-8"))
    raw["timeouts"] = dict(raw.get("timeouts") or {})
    raw["timeouts"]["cover_effect_ms"] = 3000
    target = bili_selectors.parent / "cover-stuck.json"
    target.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    flow = BilibiliFlow(PageDriver(page), BilibiliConfig.load(target))
    plan = load_bilibili_plan(bili_package)
    _form_ready(page, flow, plan)
    flow.dismiss_blocking_dialogs()

    # 把「完成」按钮卡成不可点，模拟平台没收好
    page.evaluate("() => { window.__coverStuck = true; }")
    with pytest.raises(FlowError) as error:
        flow.set_cover(plan.cover)
    assert "封面" in str(error.value)


def test_a_rejected_upload_fails_loudly_instead_of_pretending(page, bili_selectors,
                                                              bili_package):
    """服务端拒收 → 立刻报错，**不往下填表**。

    这条挡的是 2026-11-13 实测的那个坑：页面上一片风平浪静，
    视频其实根本没传上去。代码要是只看页面，就会以为成功了。

    **判据是状态码，不是服务端返回的原文**——响应体被渲染进程读走后
    就取不到了（Chromium 会把它从 network cache 里清掉），
    所以流程里正文只是「有就带上」的加分项。
    """
    (bili_package / "video.mp4").write_bytes(b"REJECT" + b"\x00" * 32)
    flow = BilibiliFlow(PageDriver(page), BilibiliConfig.load(bili_selectors))
    plan = load_bilibili_plan(bili_package)

    with pytest.raises(FlowError) as error:
        flow.draft(plan)

    message = str(error.value)
    assert "400" in message
    assert "服务端拒绝" in message
    assert "页面不会显示这个错误" in message
    # 表单还没填：不能拿着一个没传上去的视频去填表
    assert page.locator("#post-form").is_visible() is False


def _form_ready(page, flow, plan):
    """传片 + 等表单出现。

    **表单是传完片才解锁的**（真实站也要等平台转码完），
    所以测「填进去的东西对不对」之前，先把这一步走完。
    """
    flow.open_entry()
    flow.upload_video(plan.video)
    flow.wait_form_ready()


def test_verify_filled_catches_a_title_that_did_not_land(page, bili_selectors,
                                                          bili_package):
    flow = BilibiliFlow(PageDriver(page), BilibiliConfig.load(bili_selectors))
    plan = load_bilibili_plan(bili_package)
    _form_ready(page, flow, plan)
    with pytest.raises(FlowError) as error:
        flow.verify_filled("想填的标题", "正文", [])
    assert "标题没填对" in str(error.value)


def test_an_empty_title_says_the_page_may_have_reloaded(page, bili_selectors,
                                                         bili_package):
    """页面中途刷新 → 表单内容全丢 → 标题是空的。

    **错误消息要能一眼看出是这个原因**，不然会被当成「平台把标题吃了」。
    """
    flow = BilibiliFlow(PageDriver(page), BilibiliConfig.load(bili_selectors))
    plan = load_bilibili_plan(bili_package)
    _form_ready(page, flow, plan)
    with pytest.raises(FlowError) as error:
        flow.verify_filled("想填的标题", "正文", [])
    assert "刷新" in str(error.value)


def test_the_description_check_ignores_extra_blank_lines(page, bili_selectors,
                                                         bili_package):
    """简介是 Quill 富文本，段落换行会从 2 个变成 3 个。

    **实测 2026-11-13**：内容一个字没变，字符数却差了 6——
    直接比字符串会误判成「被平台改写了」，明明填对了也报错。
    """
    flow = BilibiliFlow(PageDriver(page), BilibiliConfig.load(bili_selectors))
    plan = load_bilibili_plan(bili_package)
    _form_ready(page, flow, plan)

    description = "第一段。\n\n第二段。"
    page.fill("#title", "标题")
    page.fill("#desc", description)
    # 富文本编辑器把段落换行渲染成更多空行——内容一样
    page.evaluate(
        """(text) => {
            const el = document.querySelector('#desc');
            el.innerHTML = text.split('\\n\\n').map(p => '<p>' + p + '</p>').join('');
        }""",
        description)

    result = flow.verify_filled("标题", description, [])
    assert result["description_chars_in_page"] > 0


def test_a_truncated_description_is_still_caught(page, bili_selectors,
                                                  bili_package):
    """归一化不能把「真被截断」也放过。"""
    flow = BilibiliFlow(PageDriver(page), BilibiliConfig.load(bili_selectors))
    plan = load_bilibili_plan(bili_package)
    _form_ready(page, flow, plan)

    page.fill("#title", "标题")
    page.fill("#desc", "只剩开头")
    with pytest.raises(FlowError) as error:
        flow.verify_filled("标题", "完整的一大段简介，后面都被截掉了", [])
    assert "简介" in str(error.value)


def test_tags_that_stay_plain_text_are_reported(page, bili_selectors, bili_package):
    """标签没被回车变成真标签，要报错。"""
    flow = BilibiliFlow(PageDriver(page), BilibiliConfig.load(bili_selectors))
    plan = load_bilibili_plan(bili_package)
    _form_ready(page, flow, plan)
    # 标题与简介先对得上，轮到标签这一项报错
    page.fill("#title", "标题")
    page.fill("#desc", "正文")
    with pytest.raises(FlowError) as error:
        flow.verify_filled("标题", "正文", ["数据库"])
    assert "标签" in str(error.value)


def test_a_package_without_a_video_is_refused(page, bili_selectors, bili_package):
    (bili_package / "video.mp4").unlink()
    flow = BilibiliFlow(PageDriver(page), BilibiliConfig.load(bili_selectors))
    plan = load_bilibili_plan(bili_package)
    with pytest.raises(FlowError) as error:
        flow.draft(plan)
    assert "成片" in str(error.value)


def test_save_draft_reports_when_the_page_had_no_reaction(page, bili_selectors,
                                                          bili_package):
    """点了「存草稿」但页面没反应 → 报错，不要假装存下来了。

    **静默返回 None 会让人以为只差一步**，其实草稿压根没存上。
    """
    raw = json.loads(bili_selectors.read_text(encoding="utf-8"))
    raw["timeouts"] = {"draft_effect_ms": 1200}
    raw["selectors"]["post"]["draft_notice"] = ["#never-appears"]
    target = bili_selectors.parent / "no-reaction.json"
    target.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    flow = BilibiliFlow(PageDriver(page), BilibiliConfig.load(target))
    plan = load_bilibili_plan(bili_package)
    _form_ready(page, flow, plan)
    flow.dismiss_blocking_dialogs()
    with pytest.raises(FlowError) as error:
        flow.save_draft()
    assert "没反应" in str(error.value)
