"""回归锁：阶段 B 合入的正文，关键结论不能被改坏。

检查器盯的是**机械指标**（段落太长、句子重复、链接断开）。它盯不着的是
另一类问题：**结论本身被改错**。这类改动在正文里往往只是「顺手改一下」——
把 PR 686 写回 685、把版本前提删掉、把判定标准写反——改完文章照样通顺、
照样没有信号，但读者照着做会出事。

所以这里给每篇合入的文章钉几条「不许改坏」的断言。它们是回归锁：
改正文时红的是它们，而不是读者的集群。

另外一条守卫盯的是渲染层：**裸 URL 后面紧跟中文**，marked 的 GFM autolink
会把后面的一整段中文吞进 href，读者点进去是一个不存在的地址。本轮修掉了
corosync 那两处，全树还剩 13 篇——列在 `KNOWN_BARE_URL_ARTICLES` 里，
那是待办清单，不是「允许有问题」的名单：清单外的文章一旦中招，这条会红。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO_ROOT / "docs"
REVIEW_ROOT = REPO_ROOT / "review"
TOOL = REPO_ROOT / "tools" / "review-check.py"

COROSYNC = DOCS_ROOT / "cluster/corosync/corosync-down网卡仍处于多数派/index.md"

# 已知的「裸 URL 吞中文」文章清单：这些还没修，是后续批次的待办。
# 清单里的文章修好了，这条守卫照样绿（子集判断）；清单外的文章中招，这条会红。
KNOWN_BARE_URL_ARTICLES = frozenset({
    "docs/chatgpt/chatgpt使用.md",
    "docs/cluster/DCF/一文读懂openguass dcf网络模块.md",
    "docs/database/database-specialization-taxonomy/index.md",
    "docs/db/postgresql/postgresql-community-gems/index.md",
    "docs/life/road/左耳朵耗子的话——关于技术的一些思考.md",
    "docs/linux/ebpf/rust-ebpf编程基础.md",
    "docs/linux/linux下RANDOM和uuid的区别.md",
    "docs/linux/linux内存管理指北.md",
    "docs/linux/linux系统接口.md",
    "docs/network/【网络】MTU相关网络丢包问题分析处理.md",
    "docs/tools/clash-meta-mihomo-install-guide.md",
    "docs/tools/clash-meta-user-guide.md",
    "docs/vue/html简单教程.md",
})

# 扫描用的三个正则。顺序有讲究：先去掉围栏代码块与行内代码（里面的 URL
# 是示例，不是正文里的链接），再去掉 markdown 链接，最后剩下的才是「裸 URL」。
FENCE_RE = re.compile(r"```[\s\S]*?```")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")
URL_RE = re.compile(r"https?://\S+")


def article_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def paragraphs(text: str) -> list[str]:
    """空行分段——用来把「提到某件事的段落」单独取出来。"""
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def bare_url_offenders(text: str) -> list[str]:
    """裸 URL 把非 ASCII 字符吞进了自己的那一批。

    marked 的 GFM autolink 从 ``https://`` 一直吃到下一个空白字符为止。
    中文没有空格，于是 URL 后面跟着的整段中文会变成 href 的一部分。
    判据：**一个裸 URL 里出现了非 ASCII 字符，就是中招了。**
    """
    stripped = FENCE_RE.sub(" ", text)
    stripped = INLINE_CODE_RE.sub(" ", stripped)
    stripped = MD_LINK_RE.sub(" ", stripped)
    hits = []
    for match in URL_RE.finditer(stripped):
        url = match.group(0)
        if any(ord(ch) > 127 for ch in url):
            hits.append(url[:80])
    return hits


def run_checker(path: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(TOOL), str(path), "--json"],
        capture_output=True, encoding="utf-8", errors="replace", cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)["docs"][0]


# --- corosync down网卡仍处于多数派（两版合并后） ---------------------------


def body_paragraphs(text: str) -> list[str]:
    """正文段落（去掉标题行）。"""
    return [p for p in paragraphs(text) if not p.startswith("#")]


def test_the_fix_points_at_pr_686_and_its_commit():
    """单元：修复必须指向 PR 686 与 commit 8b638e98。

    PR 685 从未合入——读者照着它 cherry-pick 会白忙一场。
    """
    text = article_text(COROSYNC)
    assert "https://github.com/corosync/corosync/pull/686" in text, (
        "正文里没有 PR 686 的链接")
    assert "8b638e989c391860d0e0f8bcd83fed1ac0b50992" in text, (
        "正文里没有修复 commit 的完整 sha")
    attributed = [p for p in body_paragraphs(text) if "PR 686" in p and "修复" in p]
    assert attributed, "正文里没有把「修复」归到 PR 686"


def test_pr_685_is_flagged_as_never_merged():
    """单元：PR 685 必须被明确标成「从未合入」。

    守的是「只留下 PR 号、删掉后半句」这种改法——那句话一删，读者就会
    以为 685 才是修复。
    """
    text = article_text(COROSYNC)
    flagged = [p for p in body_paragraphs(text) if "685" in p and "从未合入" in p]
    assert flagged, "正文里没有把 PR 685 标成「从未合入」——读者会以为它是修复"


def test_switching_to_knet_carries_the_version_precondition():
    """单元：换 knet 的前提是 corosync 3.x。

    在 2.x 上写 ``transport: knet`` 不但不生效，还会**静默退化成组播 UDP**——
    读者以为绕过了问题，实际把集群换成了另一种传输层。
    """
    text = article_text(COROSYNC)
    assert "静默退化成组播 UDP" in text, (
        "正文里没有「在 2.x 上会静默退化成组播 UDP」这条警告")
    assert "corosync 3.x" in text, "正文里没有写明前提是 corosync 3.x"


def test_the_quorum_expectation_names_the_isolated_node():
    """单元：判定标准的主体不能写反。

    该转成非 quorate 的是**被隔离的那台自己**；剩下两个节点仍然满足多数派、
    仍然该是 quorate。写反了读者会去停一个本来好好的集群。

    判据落在**同一段**上：三样东西必须出现在一起——被隔离的那台、非 quorate、
    以及其余节点把它视为 offline。少一样就是主体被写反了。
    """
    text = article_text(COROSYNC)
    complete = [p for p in body_paragraphs(text)
                if "被隔离的那台" in p and "非 quorate" in p and "offline" in p]
    assert complete, (
        "正文里没有一段同时说清「被隔离的那台应为非 quorate」与"
        "「其余节点把它视为 offline」——判定标准的主体可能被写反了")


def test_the_merged_article_does_not_swallow_chinese_into_a_url():
    """单元：本篇不能出现「裸 URL 吞中文」。"""
    offenders = bare_url_offenders(article_text(COROSYNC))
    assert not offenders, f"有 URL 把中文吞进了 href：{offenders}"


def test_the_merged_article_has_no_warn_signal():
    """集成：合入后这篇不该再被检查器报 warn。

    合并前是 3 条（AIF-03、AIF-05 等）；合入后要干净。
    """
    report = run_checker(COROSYNC)
    warns = [s for s in report["signals"] if s["severity"] == "warn"]
    assert not warns, f"合入后仍有 warn 信号：{warns}"


def test_the_merged_article_is_the_only_one_with_this_title():
    """集成：站点上不能重新出现同标题的第二篇。

    合并前 `corosync-down网卡仍处于多数派` 与 `-1` 两篇 H1 一模一样，
    站点上是两篇几乎一样的文章。
    """
    title = "corosync down网卡仍处于多数派问题分析"
    same = []
    for path in sorted(DOCS_ROOT.rglob("*.md")):
        match = re.search(r"^#\s+(.*\S)\s*$",
                          path.read_text(encoding="utf-8", errors="replace"), re.M)
        if match and match.group(1).strip() == title:
            same.append(path.relative_to(REPO_ROOT).as_posix())
    assert same == [COROSYNC.relative_to(REPO_ROOT).as_posix()], (
        f"全树有多篇同名文章：{same}")

    # -1 的目录、审校记录与索引行都不能回来
    assert not (DOCS_ROOT / "cluster/corosync/corosync-down网卡仍处于多数派-1").exists(), (
        "-1 的 docs 目录又被建回来了")
    assert not (REVIEW_ROOT / "cluster/corosync/corosync-down网卡仍处于多数派-1.md").exists(), (
        "-1 的审校记录又被建回来了")
    index = (REVIEW_ROOT / "INDEX.md").read_text(encoding="utf-8")
    assert "corosync-down网卡仍处于多数派-1" not in index, (
        "INDEX 里又出现了 -1 那一行")


def test_no_new_article_swallows_chinese_into_a_url():
    """集成：全树不许新增「裸 URL 吞中文」的文章。

    这条判据是从站点实际渲染链复刻的：marked 的 GFM autolink 会从
    ``https://`` 吃到下一个空白为止，中文没有空格，于是整段中文被吞进 href。
    本轮修掉了 corosync 那两处（合并后是 1 篇 2 处），剩下的列在
    ``KNOWN_BARE_URL_ARTICLES`` 里——那是待办清单，不是白名单。
    """
    offenders = {}
    for path in sorted(DOCS_ROOT.rglob("*.md")):
        hits = bare_url_offenders(path.read_text(encoding="utf-8", errors="replace"))
        if hits:
            offenders[path.relative_to(REPO_ROOT).as_posix()] = hits
    unknown = sorted(set(offenders) - KNOWN_BARE_URL_ARTICLES)
    assert not unknown, (
        f"这些文章出现了裸 URL 吞中文（已知的待办清单之外）：{unknown}")


# --- 两地三中心（tptc.md 与 tptc_improve.md 合并后） ------------------------

TPTC = DOCS_ROOT / "cluster/kingbase/tptc.md"


def test_the_disaster_recovery_levels_match_the_standard():
    """单元：分级表必须与 JR/T 0044-2008 附录 B 的数值一致。

    5 级是监管底线（RTO 数分钟至 2 天、RPO 0 至 30 分钟），
    6 级是业界实际做的（RTO 数分钟、RPO=0）。把两者写反，读者按 5 级
    去对标就会错——这是原文最实质的一处错。
    """
    text = article_text(TPTC)
    assert "JR/T 0044-2008" in text, "正文里没有点名分级所依据的标准"
    # 分级表里的两行要逐格对上：5 级是监管底线，6 级是业界实际做的。
    # 数值在正文别处也出现过，所以这里按表行断言——改了一格就要红。
    assert "| 5 级 | 数分钟至 2 天 | 0 至 30 分钟 |" in text, (
        "分级表里 5 级那一行不对")
    assert "| 6 级 | 数分钟 | 0 |" in text, "分级表里 6 级那一行不对"
    assert "⌊总票数 / 2⌋ + 1" in text, "正文里没有写清多数派的计数口径"


def test_the_regulatory_documents_are_named():
    """单元：标准沿革必须点名文件与文号。

    这是全文最容易变成资产的部分——读者要知道去哪查。只写年份等于没写。
    """
    text = article_text(TPTC)
    for doc in ("银发〔2006〕123号", "银监发〔2006〕63号", "GB/T 20988-2007",
                "JR/T 0044-2008", "银监办发〔2010〕114号", "银监发〔2011〕104号"):
        assert doc in text, f"正文里没有点名 {doc}"


def test_no_availability_percentage_is_claimed():
    """单元：可用性百分比一个都不能出现在正文里。

    原文写了 99.99%、姊妹篇写了 99%、厂商博客里有 99.99% 与 99.999%
    四个互相矛盾的数字，而且都查不到出处。核不到就不写——这一条比写准更重要。
    """
    text = article_text(TPTC)
    assert "99.99" not in text, "正文里出现了没有出处的可用性百分比"
    assert "99%" not in text, "正文里出现了没有出处的可用性百分比"
    assert "99.999" not in text, "正文里出现了没有出处的可用性百分比"


def test_the_classification_criterion_is_time_sensitivity():
    """单元：JR/T 0044-2008 的分类依据是**时间敏感性**，不是「重要程度」。

    原文写「按重要程度划分为 A、B、C 类系统」，既用错了标准里的词，
    也用错了分类依据。
    """
    text = article_text(TPTC)
    assert "按**时间敏感性**把信息系统分成三类" in text, (
        "正文里没有写明分类依据是时间敏感性")
    assert "A、B、C 类" not in text, "正文里又出现了「A、B、C 类系统」的说法"


def test_the_arbitration_vote_count_carries_its_precondition():
    """单元：仲裁票数的口径必须带着它的配置前提。

    「仲裁投 N-1 票」对应 corosync-qdevice 的 lms；ffsplit 的默认是每节点 1 票，
    而两者前提相反（`quorum.device.votes` 删掉 vs 显式设为 1）。
    只写票数不写前提，读者照着配必然配错，要到分区时才发现。
    """
    text = article_text(TPTC)
    assert "总票数 = 节点票 + 仲裁票" in text, "正文里没有写清总票数的构成"
    for needle in ("lms", "ffsplit", "quorum.device.votes"):
        assert needle in text, f"正文里没有提到 {needle}"


def test_the_pseudo_primary_topology_is_the_correct_one():
    """单元：同城灾备中心是**伪主节点**代表本中心，不是「备节点直连生产主库」。

    原文写的是「同城灾备中心的其中一个备节点与生产中心的主节点采用同步的方式
    与主库连接」——那与真正的拓扑是两回事，读者照着设计就错了。
    """
    text = article_text(TPTC)
    assert "代表整个同城灾备中心" in text, (
        "正文里没有说清伪主节点是代表整个中心的")
    assert "不是「每个备节点直连生产主库」" in text, (
        "正文里没有点破「备节点直连生产主库」这个错误拓扑")


def test_the_merged_tptc_article_has_no_warn_signal():
    """集成：合入后这篇不该再被检查器报 warn。

    合并前两篇合计 5 条 warn（AIF-02 / AIF-03 / AIF-05）；合入后要干净。
    """
    report = run_checker(TPTC)
    warns = [s for s in report["signals"] if s["severity"] == "warn"]
    assert not warns, f"合入后仍有 warn 信号：{warns}"


def test_the_two_tptc_articles_are_merged_into_one():
    """集成：站点上不能重新出现同标题的第二篇「两地三中心」。"""
    title = "两地三中心"
    same = []
    for path in sorted(DOCS_ROOT.rglob("*.md")):
        match = re.search(r"^#\s+(.*\S)\s*$",
                          path.read_text(encoding="utf-8", errors="replace"), re.M)
        if match and match.group(1).strip() == title:
            same.append(path.relative_to(REPO_ROOT).as_posix())
    assert same == ["docs/cluster/kingbase/tptc.md"], f"全树有多篇同名文章：{same}"

    assert not (DOCS_ROOT / "cluster/kingbase/tptc_improve.md").exists(), (
        "tptc_improve.md 又被建回来了")
    assert not (REVIEW_ROOT / "cluster/kingbase/tptc_improve.md").exists(), (
        "tptc_improve 的审校记录又被建回来了")
    # 只看进度表的**行**——正文里提到「并掉了 tptc_improve」是说明，不是条目。
    index = (REVIEW_ROOT / "INDEX.md").read_text(encoding="utf-8")
    rows = [line for line in index.split("\n") if line.strip().startswith("| [")]
    assert not [r for r in rows if "tptc_improve" in r], (
        f"INDEX 的进度表里又出现了 tptc_improve 那一行：{rows}")
