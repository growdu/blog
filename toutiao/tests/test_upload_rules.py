"""人工上传与发表的**操作规则**必须留在设计文档里。

2026-11-13 在真实头条号后台走完一整篇，踩出来的规则有八条。它们有两个特点：

* 每一条都是**平台行为**，不是我们的偏好——所以不会随版本消失，
  得一直留着；
* 每一条都对应一个**看得见的坑**。比如「保存失败」被读成「没发出去」，
  于是把同一篇重发了一次，账号里多出一篇重复稿。

设计文档是「规则该在的地方」，出包清单是「操作者真正会看的那一份」。
这两份都得有：规则只躺在设计文档里，操作的人看不到；
只躺在清单里，下一个改代码的人又会重新踩一遍。

所以这里钉住：八条规则一条都不能少，每条都得有「为什么」——
没有「为什么」的规则，下次有人会把它当成多余的规矩删掉。
"""

import re

DOC_RELATIVE_PATH = ("toutiao", "docs", "00-设计.md")

RULES_HEADING = "### 4.2 人工上传与发表：操作系统规则"

#: 规则号 → 必须能在文档里找到的关键词。
#:
#: 每条规则钉的是**结论**，不是原句——措辞可以改，结论不能变。
RULES = {
    "R1": ("save=0", "save=1", "≠「没发出去」"),
    "R2": ("预览并发布", "预览确认发布", "确认发布"),
    "R3": ("不要重发",),
    "R4": ("拦请求", "干跑"),
    "R5": ("byte-drawer-mask",),
    "R6": ("byte-checkbox-checked",),
    "R7": ("Meta+V",),
    "R8": ("平台字",),
}


def _text(repo_root):
    return repo_root.joinpath(*DOC_RELATIVE_PATH).read_text(encoding="utf-8")


def _rules_block(text):
    """切出规则表那一段（从标题到下一个二级/三级标题）。"""
    start = text.find(RULES_HEADING)
    assert start != -1, "设计文档里没有 {} 这一节".format(RULES_HEADING)
    rest = text[start + len(RULES_HEADING):]
    end = re.search(r"\n#{2,3} ", rest)
    return rest[: end.start()] if end else rest


def test_the_rules_section_exists(repo_root):
    """规则表必须在。"""
    text = _text(repo_root)

    assert RULES_HEADING in text, "设计文档里没有 {}".format(RULES_HEADING)


def test_every_rule_is_still_written_down(repo_root):
    """八条规则一条都不能少。

    少一条，就有一个坑在下一个人身上重新出现——这次是重发了两篇。
    """
    block = _rules_block(_text(repo_root))

    missing = []
    for number, keywords in RULES.items():
        for keyword in keywords:
            if keyword not in block:
                missing.append("{}/{}".format(number, keyword))
    assert not missing, "设计文档的规则表里缺这些：{}".format("、".join(missing))


def test_every_rule_says_why(repo_root):
    """每条规则都得有「为什么」。

    没有「为什么」的规则看起来像多余的规矩，下一个改代码的人会删掉它——
    然后坑重新出现。
    """
    block = _rules_block(_text(repo_root))

    rows = [
        line for line in block.splitlines()
        if re.match(r"\|\s*R\d+\s*\|", line)
    ]
    assert len(rows) == len(RULES), (
        "规则表里应该有 {} 行，实际 {} 行".format(len(RULES), len(rows))
    )

    for row in rows:
        number = re.match(r"\|\s*(R\d+)\s*\|", row).group(1)
        cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
        assert len(cells) == 3, "{} 这一行的列数不对：{}".format(number, row)
        rule, why = cells[1], cells[2]
        assert rule, "{} 没写规则是什么".format(number)
        assert len(why) >= 10, "{} 没写为什么（要长到能说明白）".format(number)


def test_the_operator_facing_rules_also_reach_the_checklist(repo_root):
    """R1~R3 必须同时出现在出包清单里。

    清单是操作者真正会看的那一份。规则只躺在设计文档里，
    等于**没写给要看它的人**——2026-11-13 的重复稿就是这么来的。
    """
    publish_module = repo_root.joinpath("toutiao", "toutiao", "publish.py").read_text(
        encoding="utf-8"
    )

    assert "预览确认发布" in publish_module, "出包清单里没有「预览确认发布」这一步"
    assert "自动存草稿" in publish_module, "出包清单里没有解释「保存失败」是什么"
    assert "重发" in publish_module, "出包清单里没有提醒别重发一遍"
