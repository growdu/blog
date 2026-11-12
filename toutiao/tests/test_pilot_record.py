"""守住「阶段一不能被 API 权限依赖污染」。

2026-11-12，用户照着 Phase 0 阶段一的清单去头条号后台找「开放平台」入口，
**找不到**——因为未达门槛的账号，那个入口整个不渲染（不是灰掉、不是报错）。

根因不是路径写错，是**这一步被放错了阶段**：它依赖认证，本该属于阶段二。
原来的清单却把它排在阶段一第 1 项，于是用户第一件事就撞墙。

这类错配一旦发生过一次，就会被再犯一次——清单是给人照着走的，
让人照着走到死路，比少写一条更糟。所以用测试把阶段边界钉死：

* 阶段一里不得出现 ``API 权限管理``（那个具体页面名）
* 阶段二里必须出现 ``API 权限管理``（不能把这件事整个丢掉）
* 这次实测的结论必须留在文档里（否则重写文档时会被抹掉，
  下一个人又会照着一个从没验证过的清单去找入口）

另外锁住入口的正确名字：正式名字是「开放平台」，
「开发平台」只允许以「不是它」的否定形式出现。
"""

import re

PILOT_RELATIVE_PATH = ("toutiao", "docs", "02-试点记录.md")
SPEC_RELATIVE_PATH = ("publish", "spec", "06-发布计划与调度.md")

STAGE_ONE_MARK = "## 阶段一"
STAGE_TWO_MARK = "## 阶段二"

#: 「设置 → 开放平台 → API 权限管理」这个页面的名字。
#: 只用这一串做判定，避免「本阶段不依赖任何 API 权限」这类否定句被误伤。
API_PERMISSION_PAGE = "API 权限管理"

#: 正式入口名。
ENTRY_NAME = "开放平台"

#: 常见误称。它不是入口名，只能以否定形式出现。
WRONG_ENTRY_NAME = "开发平台"

#: 这次实测的日期与结论要点。
FINDING_DATE = "2026-11-12"
FINDING_MARK = "不渲染"


def _split_stages(text):
    """把文档切成 ``(阶段一正文, 阶段二正文)``。

    阶段边界取二级标题里的 ``## 阶段一`` / ``## 阶段二``。
    找不到边界就让用例红——边界没了，说明文档被改坏了。
    """
    one = text.find(STAGE_ONE_MARK)
    two = text.find(STAGE_TWO_MARK)
    assert one != -1, "试点记录里找不到 {} 标题".format(STAGE_ONE_MARK)
    assert two != -1, "试点记录里找不到 {} 标题".format(STAGE_TWO_MARK)
    assert one < two, "阶段一 / 阶段二的顺序反了"
    return text[one:two], text[two:]


def _spec_stage_blocks(text):
    """从 spec 06 的 Phase 0 代码块里切出两个阶段。

    块里的阶段标题是 ``── 阶段一：… ──`` / ``── 阶段二：… ──``。
    """
    one = text.find("阶段一：")
    two = text.find("阶段二：")
    assert one != -1, "spec 06 的 Phase 0 清单里找不到阶段一"
    assert two != -1, "spec 06 的 Phase 0 清单里找不到阶段二"
    assert one < two, "spec 06 的阶段顺序反了"
    return text[one:two], text[two:]


def test_pilot_stage_one_has_no_api_permission_dependency(repo_root):
    """阶段一不得出现 API 权限管理——它依赖认证，属于阶段二。"""
    text = repo_root.joinpath(*PILOT_RELATIVE_PATH).read_text(encoding="utf-8")
    stage_one, _ = _split_stages(text)

    assert API_PERMISSION_PAGE not in stage_one, (
        "阶段一里出现了「{}」——这一步依赖账号认证，只能放阶段二。"
        "2026-11-12 用户照着阶段一清单去后台找入口，根本找不到。"
        .format(API_PERMISSION_PAGE)
    )


def test_pilot_stage_two_keeps_the_api_permission_step(repo_root):
    """阶段二必须留着「开放平台 → API 权限管理」这一步。

    挪走不等于取消：认证之后还是要去看这个页面，
    「认证能不能顺带满足粉丝条件」这个核心问题就靠这一步回答。
    """
    text = repo_root.joinpath(*PILOT_RELATIVE_PATH).read_text(encoding="utf-8")
    _, stage_two = _split_stages(text)

    assert API_PERMISSION_PAGE in stage_two, (
        "阶段二里找不到「{}」——认证之后仍要去看这个页面。"
        .format(API_PERMISSION_PAGE)
    )
    assert ENTRY_NAME in stage_two, (
        "阶段二里连「{}」都没提，入口名写错就找不到页面了。".format(ENTRY_NAME)
    )


def test_spec_phase_one_has_no_api_permission_dependency(repo_root):
    """spec 06 的 Phase 0 阶段一同样不得被 API 权限污染。

    这份清单是上位文档，试点记录是它的执行副本；
    两边必须一致，否则执行的人照着哪份都可能走错。
    """
    text = repo_root.joinpath(*SPEC_RELATIVE_PATH).read_text(encoding="utf-8")
    stage_one, _ = _spec_stage_blocks(text)

    assert API_PERMISSION_PAGE not in stage_one, (
        "spec 06 的 Phase 0 阶段一里出现了「{}」，这一步属于阶段二。"
        .format(API_PERMISSION_PAGE)
    )


def test_spec_phase_two_keeps_the_api_permission_step(repo_root):
    """spec 06 的阶段二必须留着这一步。"""
    text = repo_root.joinpath(*SPEC_RELATIVE_PATH).read_text(encoding="utf-8")
    _, stage_two = _spec_stage_blocks(text)

    assert API_PERMISSION_PAGE in stage_two, (
        "spec 06 的阶段二里找不到「{}」。".format(API_PERMISSION_PAGE)
    )


def test_the_finding_is_recorded(repo_root):
    """2026-11-12 的实测结论必须留在文档里。

    这条实测值两样东西：一是入口的正式名字，
    二是「未达门槛的账号连菜单项都不渲染」——
    后者解释了为什么找不到，也解释了为什么这一步得等认证。
    """
    text = repo_root.joinpath(*PILOT_RELATIVE_PATH).read_text(encoding="utf-8")

    assert FINDING_DATE in text, "试点记录里没有 {} 的实测记录".format(FINDING_DATE)
    assert FINDING_MARK in text, (
        "试点记录里没有「{}」这个结论——"
        "「找不到入口」和「入口不渲染」是两回事，前者会让人一直找。"
        .format(FINDING_MARK)
    )


def test_entry_name_is_not_misremembered(repo_root):
    """入口名是「开放平台」；「开发平台」只允许出现在否定句里。"""
    text = repo_root.joinpath(*PILOT_RELATIVE_PATH).read_text(encoding="utf-8")

    assert ENTRY_NAME in text, "文档里没有正确的入口名「{}」。".format(ENTRY_NAME)

    for match in re.finditer(re.escape(WRONG_ENTRY_NAME), text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        line = text[line_start:line_end if line_end != -1 else len(text)]
        assert "不是" in line, (
            "「{}」出现在没有否定的句子里：{}"
            .format(WRONG_ENTRY_NAME, line.strip())
        )
