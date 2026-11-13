"""2026-11-13 的实测结论必须留在试点记录里，并且和能力声明对得上。

两份文件在说同一件事：

* ``toutiao/docs/02-试点记录.md`` §R2 —— 实测看到的原话与数字；
* ``publish/capabilities/toutiao.toml`` —— 限额落在哪。

它们对不上，就是有人改了一边忘了另一边。而限额改错了**不会报错**：
平台不会提示「你把封面切竖了」，只会把封面再裁一次上下两半。

所以这里钉三件事：

* §R2 必须在（重写文档时，实测结论最容易整段丢）；
* 记录里的数字必须与声明里的值一致（同一个数，两处写法不能各说各话）；
* **没测到的项必须仍然写着没测到**。

最后一条是最要紧的：把「未测」写成「已测」，是这份文档最坏的一种错——
它不会立刻出事，它只是让下一个人以为那件事已经不需要再测了。
"""

import re

from toutiao.capability import default_capability_path, load_capability

PILOT_RELATIVE_PATH = ("toutiao", "docs", "02-试点记录.md")

#: 这一轮实测的日期。§R2 的小标题里带着它，全文里也必须能找到。
MEASUREMENT_DATE = "2026-11-13"

#: §R2 的小标题。只认这一串，免得「实测记录」三个字满篇都是。
R2_HEADING = "### R2 · 2026-11-13"

#: 没测到的那些项。键是能唯一认出那一行的话，值是这一行里必须出现的措辞。
#:
#: 键要够具体：「摘要」这种词满篇都是，按它找行会撞到小标题。
UNMEASURED_ITEMS = {
    "正文里的**外链图片**能不能显示": ("未测",),
    "**零封面**能不能发": ("未测",),
    "平台自动生成的**摘要**": ("未测",),
    "发表后有没有审核 / 审核要多久": ("未到达", "未测"),
    "正文图片**张数上限**": ("未测",),
}


def _text(repo_root):
    return repo_root.joinpath(*PILOT_RELATIVE_PATH).read_text(encoding="utf-8")


def _row_containing(text, needle):
    """找出包含 ``needle`` 的那一行（表格行按行拆）。

    找不到就返回空串——由调用方断言，让失败信息说清楚是「哪一行」。
    """
    for line in text.splitlines():
        if needle in line:
            return line
    return ""


def test_the_r2_measurement_is_recorded(repo_root):
    """§R2 与它的日期必须在。

    这条实测是限额的唯一出处。文档被重写时最容易丢的就是整段实测——
    剩下的表格看着还挺完整，人就以为还有依据。
    """
    text = _text(repo_root)

    assert R2_HEADING in text, "试点记录里没有 {} 这一节".format(R2_HEADING)
    assert MEASUREMENT_DATE in text, "试点记录里没有 {}".format(MEASUREMENT_DATE)


def test_the_cover_finding_is_recorded_as_landscape(repo_root):
    """封面结论要留下「横图」和面板原文里的那两个尺寸。

    旧假设是「3:4 竖图」。按旧假设切封面平台不报错，只是把宽图裁成窄条，
    所以这条结论一旦被改回去，没有任何机制会报警——只有文档记得。
    """
    text = _text(repo_root)

    assert "452*352" in text, "试点记录里没有封面下限 452*352"
    assert "672*462" in text, "试点记录里没有封面建议尺寸 672*462"
    assert "横图" in text, "试点记录里没有「封面是横图」这个结论"


def test_the_webp_finding_is_recorded_with_its_evidence(repo_root):
    """webp 能传，得连证据一起留。

    面板文案只列 jpg/jpeg/png，所以「webp 能传」这条结论如果只剩结论、
    没有「平台原样存原样吐」的证据，下一个人多半会当成笔误改回去。
    """
    text = _text(repo_root)

    assert "webp" in text
    assert "RIFF" in text, "试点记录里没有 webp 不转码的证据"
    assert "20MB" in text, "试点记录里没有图片大小上限"


def test_the_platform_word_count_formula_is_recorded(repo_root):
    """平台字数口径要写下公式。

    这是整个口径里最容易丢的一条：它不是「字数」，也不是「字符数」，
    写不出公式，下一个人就只能靠猜。
    """
    text = _text(repo_root)

    assert "非 ASCII" in text, "试点记录里没有平台字数的非 ASCII 那一半"
    assert "⌈ASCII/2⌉" in text, "试点记录里没有 ASCII 折半向上取整的公式"


def test_the_paragraph_threshold_is_recorded(repo_root):
    """单段阈值要同时记「不告警」和「告警」两头的数。

    只记 200 的话，下一个人会以为「≤200 都行、>200 都报」——
    201 与 200 的差别恰恰是实测出来的东西。
    """
    text = _text(repo_root)

    assert "200 平台字不告警" in text, "试点记录里没有单段 200 平台字不告警的结论"
    assert "1 处段落字数过多" in text, "试点记录里没有平台告警的原文"


def test_the_7050_blocker_is_recorded_with_its_control(repo_root):
    """7050 与它的对照实验必须一起留着。

    只有「保存失败」没有「最小草稿也失败」，下一个人会以为是自己这篇文章
    的问题，然后去改稿子——改到天亮也修不好一个账号侧的问题。
    """
    text = _text(repo_root)

    assert "7050" in text, "试点记录里没有 7050 这个码"
    assert "最小草稿" in text, "试点记录里没有「最小草稿也失败」这条对照"
    assert "与内容无关" in text, "试点记录里没有把 7050 与内容区分开的结论"


def test_the_title_limit_is_not_claimed_as_save_verified(repo_root):
    """标题上限的依据是占位符原文，**不是**「保存被拒」。

    超限时保存确实弹了「保存失败」，但那次保存本身也是账号侧 7050
    （而且正文还是空的），两条原因混在一起，分不开。
    把没验成的事写成验过了，下一个人就会以为标题上限是硬拦的——
    实际它现在只是平台自己写的那个数。
    """
    text = _text(repo_root)

    assert "2～30个字" in text, "试点记录里没有标题占位符的原文"
    assert "没验成" in text or "没单独验成" in text, (
        "试点记录里没有「标题超限的保存侧没单独验成」这条说明"
    )


def test_the_unmeasured_items_are_still_marked_unmeasured(repo_root):
    """没测到的项必须仍然写着没测到。

    这些行现在写的是「未测」。哪天有人把它们改成「可以」或者干脆删掉，
    就会有下一个人以为那件事已经不需要再测了——而它其实一次都没测过。
    """
    text = _text(repo_root)

    for item, marks in UNMEASURED_ITEMS.items():
        line = _row_containing(text, item)
        assert line, "试点记录里找不到「{}」这一项".format(item)
        assert any(mark in line for mark in marks), (
            "「{}」这一行不再写着没测到：{}\n"
            "——把它改成「测过了」等于伪造一次观测。".format(item, line.strip())
        )


def test_the_article_was_not_published(repo_root):
    """这份实测停在发表前，文档必须这么写。

    文章**没有发表**（保存就没存进去）。把记录改成「已发表」会让下一个人
    以为这篇已经发出去了，去重发一遍。
    """
    text = _text(repo_root)

    assert "停在发表前" in text, "试点记录里没有说明文章停在发表前"


def test_the_recorded_numbers_match_the_declaration(repo_root):
    """记录里的数字必须与能力声明一致（同一个数，两处不能各说各话）。

    这是本文件真正的集成测试：试点记录（人读的）与能力声明（代码读的）
    读的是同一批限额，任何一边被单独改掉，这里立刻红。
    """
    text = _text(repo_root)
    limits = load_capability(default_capability_path()).limits

    # 图片大小：面板原文写的是 MB，声明里是字节。
    match = re.search(r"单张图片最大支持\s*\**\s*(\d+)MB", text)
    assert match, "试点记录里找不到图片大小上限的原文"
    assert int(match.group(1)) * 1024 * 1024 == limits.image_bytes

    # 封面下限：面板原文「不可小于 452*352」。
    match = re.search(r"不可小于\s*`?(\d+)\*(\d+)`?", text)
    assert match, "试点记录里找不到封面下限的原文"
    assert (int(match.group(1)), int(match.group(2))) == tuple(limits.cover_min_pixels)

    # 封面比例：实测与面板原文吻合的那个比例。
    match = re.search(r"与\s*(\d+):(\d+)\s*吻合", text)
    assert match, "试点记录里找不到封面比例的结论"
    assert "{}:{}".format(match.group(1), match.group(2)) == limits.cover_ratio

    # 标题：占位符原文「2～30个字」。
    match = re.search(r"占位符原文「2～(\d+)个字」", text)
    assert match, "试点记录里找不到标题占位符的原文"
    assert int(match.group(1)) == limits.title_chars

    # 单段：平台字数口径下的阈值。
    match = re.search(r"(\d+)\s*平台字不告警", text)
    assert match, "试点记录里找不到单段阈值的结论"
    assert int(match.group(1)) == limits.paragraph_words
