"""抖音版文案：三段拼一个 text，以及抖音专属的两道闸。"""

import pytest

from douyin import contract
from pyv import epmeta

LIMITS = {"text_chars": 1000, "title_chars": 55, "description_chars": 500,
          "topics_max": 5, "topic_chars": 15}


# --- 切片 -------------------------------------------------------------------


def test_slice_copy_reads_the_douyin_section(meta):
    copy = contract.slice_copy(meta)
    assert copy.title == "32 核机器，解码只占 1 核"
    assert copy.topics == ("PostgreSQL", "逻辑复制", "数据库内核")
    assert copy.cover_at == 1.0


def test_slice_copy_without_a_douyin_section_raises():
    bare = epmeta.EpisodeMeta(episode="ep01", title="x", cover_at=1.0)
    with pytest.raises(epmeta.MetaError):
        contract.slice_copy(bare)


# --- 拼装 -------------------------------------------------------------------


def test_topics_line_uses_hash_prefixes():
    assert contract.topics_line(("数据库", "内核")) == "#数据库 #内核"


def test_topics_line_of_nothing_is_empty():
    assert contract.topics_line(()) == ""


def test_build_text_joins_the_three_parts():
    """抖音**只有**一个字段：标题、正文、话题全在里面。"""
    copy = contract.DouyinCopy(
        title="钩子", description="正文",
        topics=("数据库", "内核"), cover_at=1.0)
    text = contract.build_text(copy)
    assert text == "钩子\n正文\n#数据库 #内核"


def test_build_text_puts_the_hook_first():
    """信息流只露前几十个字，钩子必须在最前面。"""
    copy = contract.DouyinCopy(
        title="钩子", description="正文很长" * 20,
        topics=("数据库",), cover_at=1.0)
    assert contract.build_text(copy).startswith("钩子")


def test_build_text_without_topics_has_no_trailing_line():
    copy = contract.DouyinCopy(
        title="钩子", description="正文", topics=(), cover_at=1.0)
    assert contract.build_text(copy) == "钩子\n正文"


# --- 总量上限 ---------------------------------------------------------------


def test_a_text_within_the_limit_has_no_problem():
    copy = contract.DouyinCopy(title="钩子", description="正文", topics=(),
                              cover_at=1.0)
    text = contract.build_text(copy)
    assert contract.check_text_length(text, LIMITS) == []


def test_a_text_over_the_platform_limit_is_reported():
    """平台只有这一个字段，三段加起来超了就是超了。

    这条 `pyv.epmeta` 查不出来——它逐字段查，查不出「三段加起来超了」。
    """
    copy = contract.DouyinCopy(
        title="钩子", description="字" * 1000, topics=(), cover_at=1.0)
    text = contract.build_text(copy)
    problems = contract.check_text_length(text, LIMITS)
    assert problems
    assert "1000" in problems[0]


def test_the_length_check_is_skipped_when_the_capability_is_broken():
    """能力声明被改坏时，宁可不查也不要瞎报一个数。"""
    copy = contract.DouyinCopy(title="钩子", description="字" * 2000,
                              topics=(), cover_at=1.0)
    text = contract.build_text(copy)
    assert contract.check_text_length(text, {}) == []
    assert contract.check_text_length(text, {"text_chars": 0}) == []


# --- 站外引流 ---------------------------------------------------------------


def test_a_clean_text_has_no_outbound_problem():
    copy = contract.DouyinCopy(
        title="32 核机器，解码只占 1 核",
        description="默认发布端只有一个解码线程，串行处理。",
        topics=("PostgreSQL", "逻辑复制"), cover_at=1.0)
    assert contract.check_no_outbound(contract.build_text(copy)) == []


@pytest.mark.parametrize("offender", [
    "完整版见 https://growdu.cn/2026/",
    "官网 www.growdu.cn",
    "加微信 growdu",
    "加V: growdu",
    "QQ 群 123456",
    "手机号 13800138000",
])
def test_outbound_contact_is_reported(offender):
    """抖音禁站外引流与过度营销（规格 §6.6.4）。"""
    problems = contract.check_no_outbound(f"正文。{offender}")
    assert problems, f"{offender!r} 没被拦下来"


@pytest.mark.parametrize("offender", [
    "加wx growdu",           # 微信号：wx
    "VX: growdu",            # 微信号：大写 VX
    "vx:growdu",             # 微信号：小写 vx
    "加 WX: growdu",         # 微信号：加 WX
    "qq123456",              # QQ：小写，后面直接跟数字
    "QQ 123456",
    "扣扣 123456",
    "手机号13800138000",      # 手机号：中文与数字之间**没有词边界**
    "联系 13800138000",
    "138-0013-8000",         # 手机号：带分隔符
    "见 claude.ai",          # 域名：白名单之外的后缀
    "见 foo.xyz",
    "见 example.io",
])
def test_every_shape_of_outbound_is_reported(offender):
    """**每一种形态都得拦得住**，不只是列出来的那几个。

    上一版规则漏了一大截：`vx` 没带 `IGNORECASE`（`VX:` 直接放行）、
    没有 `wx`、手机号靠 `\b` 而中文与数字之间根本没有词边界
    （`手机号13800138000` 放行）、域名只有八个后缀的白名单——
    而模块注释却自称「拦的是形态，不是白名单」，两处说法打架。

    这里逐条钉住：**规则按形态写，就得每种形态都拦得住。**
    """
    problems = contract.check_no_outbound(f"正文。{offender}")
    assert problems, f"{offender!r} 没被拦下来"


@pytest.mark.parametrize("ordinary", [
    "看 README.md 的说明",       # 文件后缀不是域名
    "node.js 的文档",            # 同上
    "gpt-4o.mini 这个模型",      # 产品词不是域名
    "用 3.5 版本",               # 数字不是后缀
    "U.S.A 的格式",              # 单字母不是后缀
    "i.e. 就是这个",             # 同上
    "wxPython 这个库",           # 库名不是微信号
    "Python 3 与 PostgreSQL 18",
    "有问题欢迎私信我",
])
def test_ordinary_words_are_not_outbound(ordinary):
    """**误伤也是错**——闸太宽会把正常的文案也拦住，人就得改稿。

    拦的是站外引流，不是「句子里有个点」。
    """
    assert contract.check_no_outbound(ordinary) == [], ordinary


def test_private_messages_are_not_outbound():
    """私信是**站内**功能，不是站外引流——不能误伤。"""
    assert contract.check_no_outbound("有问题欢迎私信我") == []


def test_ordinary_technical_words_are_not_domains():
    """「PostgreSQL」「WAL」里没有点号，不会被当成域名。"""
    assert contract.check_no_outbound(
        "PostgreSQL 18 的并行逻辑解码，WAL 交错着写") == []


# --- 入库的真实元数据 ------------------------------------------------------


def test_every_stored_episode_passes_the_douyin_gates():
    """六期入库的抖音文案必须过两道闸。

    闸不是给测试用的——它是真的会在出包时拦住东西。
    真实文案就躺在仓库里，在这里跑一遍，就不用等到出包那天才发现。
    """
    limits = epmeta.load_limits("douyin")
    for path in sorted(epmeta.PUBLISH_DIR.glob("*.json")):
        meta = epmeta.load_meta(path.stem)
        copy = contract.slice_copy(meta)
        text = contract.build_text(copy)
        assert contract.check_text_length(text, limits) == [], path.name
        assert contract.check_no_outbound(text) == [], path.name


def test_no_stored_episode_leaks_the_site_domain_into_the_douyin_copy():
    """**站点地址不能进抖音文案**——那是站外引流（规格 §6.6.4）。

    元数据顶层有个 `url` 字段（站点详情页），别的平台会把它附在文案末尾。
    抖音不行：这一栏留着但 `build_text` 不用它。这条测试守着这个区别。
    """
    for path in sorted(epmeta.PUBLISH_DIR.glob("*.json")):
        meta = epmeta.load_meta(path.stem)
        copy = contract.slice_copy(meta)
        assert meta.url not in contract.build_text(copy), path.name
