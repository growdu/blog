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


# --- IPv6 上网不稳定 ------------------------------------------------------

IPV6 = DOCS_ROOT / "network/从原理到实践，彻底告别 IPv6 上网不稳定的问题.md"


def test_the_ipv6_article_has_a_title_and_an_info_table():
    """单元：H1 标题 + 编写信息表。

    原文没有 H1，站点上标题会退化成「前言」（检查器 MET-02），
    而标题是读者唯一的导航。
    """
    text = article_text(IPV6)
    assert text.startswith("# 从原理到实践，彻底告别 IPv6 上网不稳定的问题\n"), (
        "正文开头不是与文件名一致的 H1 标题")
    assert "| 编写人 | 编写内容 | 编写时间 |" in text, "正文里没有编写信息表"


def test_the_mss_formula_covers_ipv4_ipv6_and_extension_headers():
    """单元：MSS 换算要给全三套。

    原文整篇讲 IPv6，公式却只给了 IPv4 那套（MSS=MTU−20−20）。
    IPv6 固定头是 40 字节，MSS=MTU−60；带扩展头还要再减。
    """
    text = article_text(IPV6)
    assert "MSS = MTU − 20（IP 头）− 20（TCP 头）" in text, "IPv4 的换算式不对"
    assert "MSS = MTU − 40（固定头）− 20（TCP 头）= MTU − 60" in text, (
        "IPv6 的换算式不对（IPv6 固定头是 40 字节）")
    assert "IPv6 带扩展头时，还要再减去扩展头占用的字节" in text, (
        "正文没提扩展头对 MSS 的影响")


def test_the_mtu_numbers_are_arithmetically_consistent():
    """单元：1368 那个算错的数不能回来，三组数还要互相自洽。

    原文写「MSS = 1300 或 MTU=1368」——IPv6 下 MSS=MTU−60，1300 对应的
    是 1360。文中实测的 WLAN MTU 1410 对应 1370 / 1350，两个都对得上，
    唯独 1368 对不上任何东西。
    """
    text = article_text(IPV6)
    assert "1368" not in text, "正文里又出现了算错的 MTU=1368"
    assert "1360" in text, "正文里没有正确的 MTU=1360"
    assert "1410 − 40 = 1370" in text, "1410 与 IPv4 MSS 的关系没写对"
    assert "1410 − 60 = 1350" in text, "1410 与 IPv6 MSS 的关系没写对"


def test_the_interface_scoped_rule_uses_postrouting():
    """单元：指定出接口的钳制规则必须走 POSTROUTING，文字也得跟上。

    PREROUTING 里没有出接口可言，指定 `-o` 必须走 POSTROUTING（或 OUTPUT）。
    原文文字说 PREROUTING、命令却写 POSTROUTING——读者照抄会踩坑。
    """
    text = article_text(IPV6)
    assert "-t mangle -A POSTROUTING" in text, "命令里没有 POSTROUTING"
    assert "必须用 POSTROUTING（或 OUTPUT）" in text, (
        "正文没有把指定 -o 的规则指向 POSTROUTING")
    assert "PREROUTING 里没有出接口可言" in text, (
        "正文没有解释为什么不是 PREROUTING")


def test_the_icmp_error_types_are_named():
    """单元：ICMP 差错报文的类型与代码必须写出来。

    原文「ping 程序的ICMP不可到达错误，就是采用PMTU动态探测的方法」
    读者看不出报文是什么、由谁发出。
    """
    text = article_text(IPV6)
    assert "类型是 3（目的不可达）、代码 4（需要分片）" in text, (
        "正文没写清 IPv4 的 ICMP 类型 3 / 代码 4")
    assert "Packet Too Big，ICMPv6 类型 2" in text, (
        "正文没写清 IPv6 的 Packet Too Big / 类型 2")


def test_the_pmtud_standards_are_cited():
    """单元：PMTUD 的结论要挂上规范依据。

    原文「目前IPv4网络其实没有有效手段来发现PMTU」说得太绝——
    IPv4 有 RFC 1191 的 PMTUD，只是沿途过滤 ICMP 让它经常失效。

    断言按**正文里的句子**写，不按「RFC 4890 这个串出现过」写：附录的
    参考资料里也有这几个号，只查全文的话，把正文那一句改错，守卫照样绿
    （这条就是这么漏过一次）。
    """
    text = article_text(IPV6)
    body = text.split("## 参考资料")[0]
    assert "IPv4 由 RFC 1191 定义，IPv6 由 RFC 1981 定义" in body, (
        "正文没写清 RFC 1191（IPv4）与 RFC 1981（IPv6）分别定义了 PMTUD")
    assert "RFC 4890 明确要求：ICMPv6 的 Packet Too Big 不得被过滤" in body, (
        "正文没写清 RFC 4890 对 Packet Too Big 的要求")
    assert "RFC 4884 则规定了 ICMP 承载 PMTU 信息的扩展格式" in body, (
        "正文没写清 RFC 4884 扩展的是什么")
    assert "IPv4 有这个机制，只是经常用不上" in body, (
        "正文没有把 IPv4 的 PMTUD 改成「有机制但常失效」")


def test_the_uncertain_wording_is_gone():
    """单元：三处没有依据的断言不能回来。

    「胡扯！」「80% 的把握」「多么完美的一个机制！」分别是空泛断言、
    没有依据的百分比、和紧接着就被作者自己推翻的赞美。
    """
    text = article_text(IPV6)
    for phrase in ("胡扯", "80% 的把握", "多么完美", "牛逼"):
        assert phrase not in text, f"正文里又出现了「{phrase}」"


def test_the_mtu_mismatch_failure_mode_is_documented():
    """单元：调 MTU 的失败模式与检查方法要写出来。

    「尽量把 MTU 配大一些」是操作性很强的建议，不写配错的后果，
    读者会一路踩到「配置完反而全断了」。
    """
    text = article_text(IPV6)
    assert "停在 ExStart 或 Init" in text, "正文没写 MTU 不一致的失败模式"
    assert "先确认对端能接受同一个值" in text, "「把 MTU 配大」的前提没写出来"


def test_the_reference_links_are_direct():
    """单元：附录的参考必须是指向原文的直链。

    `link.zhihu.com/?target=…` 现在返回知乎安全中心页、不再跳转，
    12 条参考在站点上等于全部失效；`↩︎` 是当年发表在
    doc.envview.com 时留下的脚注残留。

    （可达性是手工实测的，不适合放进 CI——见审校记录的「事实待核」：
    那三条 403 是访问路径被拦，页面本身在线。）
    """
    text = article_text(IPV6)
    assert "link.zhihu.com" not in text, "参考里还有知乎跳转服务链接"
    assert "↩︎" not in text, "参考里还有 ↩︎ 回跳锚点"
    assert "doc.envview.com" not in text, "参考里还有 doc.envview.com 残留"
    urls = re.findall(r"\]\((https?://[^)]+)\)", text)
    assert len(urls) >= 12, f"参考条目太少（{len(urls)} 条）"
    for url in urls:
        assert url.startswith(("http://", "https://")), f"参考链接不是直链：{url}"


def test_all_images_are_local_and_present():
    """单元：图片必须是仓库里的本地文件，且一个都不多。

    原文 16 张图全外链知乎图床，实测不带浏览器头一律返回 403/567，
    策略一收紧读者看到的就是满屏裂图。
    """
    text = article_text(IPV6)
    refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    assert refs, "正文里一张图都没有了"
    for ref in refs:
        assert not ref.startswith(("http://", "https://")), f"还有外链图片：{ref}"
        assert (IPV6.parent / ref).is_file(), f"图片文件不存在：{ref}"
    # 目录里的每一张都要被引用——多出来的文件是上一轮下载的残留
    used = {Path(r).name for r in refs}
    on_disk = {p.name for p in (IPV6.parent / "ipv6_img").iterdir() if p.is_file()}
    assert on_disk == used, (
        f"目录里的图与正文引用的对不上：多出来 {sorted(on_disk - used)}，"
        f"缺 {sorted(used - on_disk)}")


def test_the_symptom_table_is_there():
    """单元：结尾要给一份可带走的产物。

    检查器 STR-03 盯的就是这个：读者读完得能带走一张「症状 → 怎么确认
    → 怎么处置」的对照表。
    """
    text = article_text(IPV6)
    assert "| 症状 | 怎么确认 | 怎么处置 |" in text, "结尾没有症状处置表"
    assert "ping -f -l" in text, "症状处置表里没有 PMTU 的确认方法"


def test_the_ipv6_article_has_no_warn_signal():
    """集成：合入后这篇不该再被检查器报 warn。

    原文有 3 条 warn：AIF-02（空泛评价）/ AIF-03（超长段落）/
    AIF-05（近似重复句）。
    """
    report = run_checker(IPV6)
    warns = [s for s in report["signals"] if s["severity"] == "warn"]
    assert not warns, f"合入后仍有 warn 信号：{warns}"


def test_only_one_ipv6_article_with_this_title():
    """集成：站点上不能出现同标题的第二篇。"""
    title = "从原理到实践，彻底告别 IPv6 上网不稳定的问题"
    same = []
    for path in sorted(DOCS_ROOT.rglob("*.md")):
        match = re.search(r"^#\s+(.*\S)\s*$",
                          path.read_text(encoding="utf-8", errors="replace"), re.M)
        if match and match.group(1).strip() == title:
            same.append(path.relative_to(REPO_ROOT).as_posix())
    assert same == ["docs/network/从原理到实践，彻底告别 IPv6 上网不稳定的问题.md"], (
        f"全树有多篇同名文章：{same}")


# --- PostgreSQL 存储、索引及系统优化、主备切换 -----------------------------

PG_SWITCH = DOCS_ROOT / "pgsql/replication/Postgresql存储、索引及系统优化、主备切换/index.md"


def test_the_pg_article_has_a_clean_title_and_a_visible_version_baseline():
    """单元：H1 标题 + 编写信息表 + 显眼的版本基线块。

    原文 H1 是「# 0 Postgresql存储…」——开头那个「0 」像是从别的文档
    复制来的编号残留；版本声明是夹在一级标题与正文之间的一行红字，
    读者多半会滑过去，而版本边界恰恰是这类参考手册最要命的东西。
    """
    text = article_text(PG_SWITCH)
    assert text.startswith("# PostgreSQL存储、索引及系统优化、主备切换\n"), (
        "正文开头不是去掉编号残留后的 H1")
    assert "| 编写人 | 编写内容 | 编写时间 |" in text, "正文里没有编写信息表"
    assert "> **版本基线**：本文以PostgreSQL 12为基线。" in text, (
        "开头没有显眼的版本基线说明块")
    assert "本文讲三件事：" in text, "开头没有一句话定位"


def test_the_pg_article_section_numbers_never_collide():
    """单元：章节编号不能撞号。

    原文 `### 1.2` 出现两次、`#### 1.2.1/1.2.2/1.2.3` 各出现两次、
    `##### 3.3.2.1` 与 `##### 3.3.2.5` 各出现两次——这种稿子里，
    读者说的「见 1.2.2」指向两个地方，等于没说。
    """
    numbers = []
    for line in article_text(PG_SWITCH).split("\n"):
        match = re.match(r"^#{2,6}\s+([0-9]+(?:\.[0-9]+)*)\s", line)
        if match:
            numbers.append(match.group(1))
    dupes = sorted({n for n in numbers if numbers.count(n) > 1})
    assert not dupes, f"章节编号撞号了：{dupes}"


def test_the_pg_article_heading_levels_line_up_with_their_numbers():
    """单元：4.3.x 那一节的层级要齐平。

    原文 `## 4.3.4` 用了 H2、`### 4.3.5` 用了 H3，而同级的
    `#### 4.3.6` 是 H4——目录里它们会浮到不同层级，读者点进来不知道
    自己到了哪一步。
    """
    text = article_text(PG_SWITCH)
    for number in ("4.3.4", "4.3.5", "4.3.6"):
        assert re.search(rf"^####\s+{number}\s", text, re.M), (
            f"{number} 这一节的标题层级不对，应该是 H4")
    assert not re.search(r"^#{2,3}\s+4\.3\.\d", text, re.M), (
        "4.3.x 里又出现了 H2/H3 标题")


def test_the_pg_article_reference_headings_are_named():
    """单元：「reference」当标题，读者不知道里面是什么。

    参考出处？还是本节小结？三处都改成「参考资料」。
    """
    text = article_text(PG_SWITCH)
    assert not re.search(r"^#{2,6}\s+.*\breference\b", text, re.M | re.I), (
        "正文里还有 reference 标题")
    assert text.count("参考资料") >= 3, "三处 reference 没有都改成「参考资料」"


def test_the_pg_article_standby_setup_uses_the_pg12_mechanism():
    """单元：4.1.5 不能同时教两套互斥的做法。

    原文 4.1.5 写的是 PG ≤ 11 的 recovery.conf 与 pg_start_backup()，
    而同一节的 L1386 已经按 PG 12 写了——读者照 4.1.5 做就错。
    """
    text = article_text(PG_SWITCH)
    section = text.split("#### 4.1.5")[1].split("### 4.2")[0]
    assert "standby.signal" in section, "4.1.5 没写 PG 12 的 standby.signal"
    assert "primary_conninfo" in section, "4.1.5 没写 primary_conninfo"
    assert "restore_command" in section, "4.1.5 没写从归档取 WAL 的 restore_command"
    assert "pg_backup_start" in section, (
        "4.1.5 没标注 PG 15 起 pg_start_backup 改名为 pg_backup_start")


def test_the_pg_article_basebackup_r_option_matches_pg12():
    """单元：`-R` 在 PG 12 起不再生成 recovery.conf。

    原文那句是 PG ≤ 11 的行为，连文章自己声明的 PG 12 基线都不符合。
    """
    text = article_text(PG_SWITCH)
    assert "参数表示在备份中会生成standby.signal文件" in text, (
        "正文没写 -R 会生成 standby.signal")
    assert "postgresql.auto.conf" in text, (
        "正文没写 -R 会把连接信息写进 postgresql.auto.conf")


def test_the_pg_article_wal_keep_and_vacuum_defer_carry_version_marks():
    """单元：两个跨版本改名的参数必须带版本标注。

    `wal_keep_segments` 在 PG 13 改名 `wal_keep_size`（单位也变了）；
    `vacuum_defer_cleanup_age` 在 PG 16 被移除。读者照着配会直接报错。
    """
    text = article_text(PG_SWITCH)
    assert "#### 4.7.1 wal_keep_size参数的配置" in text, (
        "4.7.1 的标题还写着跟正文不是一回事的 min_wal_size")
    assert "wal_keep_segements" not in text, "参数名又拼错了"
    assert "PostgreSQL 13起`wal_keep_segments`改名为`wal_keep_size`" in text, (
        "wal_keep_size 的改名版本没标出来")
    assert "复制槽" in text.split("#### 4.7.1")[1].split("#### 4.7.2")[0], (
        "4.7.1 没补上比猜 wal_keep_size 更稳妥的复制槽")
    section = text.split("#### 4.7.2")[1].split("### 4.8")[0]
    assert "PostgreSQL 16" in section and "移除" in section, (
        "4.7.2 没标出 PG 16 起该参数已被移除")
    assert "hot_standby_feedback" in section, "4.7.2 没写替代方案"


def test_the_pg_article_cmax_belongs_to_the_deleting_transaction():
    """单元：删除元组的命令标识属于「删除方事务」。

    原文两句长得几乎一样（检查器报 0.93 的近似重复句），但第二句把
    删除说成了「插入事务」——它指的是删除发生在哪个事务里。
    """
    text = article_text(PG_SWITCH)
    assert "删除该元组的命令在删除方事务中的命令标识" in text, (
        "删除元组的命令标识又写回「插入事务」了")
    assert "删除该元组的命令在插入事务中的命令标识" not in text, (
        "删除元组的命令标识又写回「插入事务」了")


def test_the_pg_article_spelling_and_typos_stay_fixed():
    """单元：术语统一 + 三处错字。

    官方写法是 PostgreSQL；「业内」「VACCUM」「它的的」是校对时抓到的错字。
    """
    text = article_text(PG_SWITCH)
    assert "Postgresql" not in text, "正文里还有 Postgresql 的写法"
    for wrong in ("业内", "VACCUM", "它的的"):
        assert wrong not in text, f"错字「{wrong}」又出现了"


def test_the_pg_article_has_the_preconditions_and_the_takeaways():
    """单元：结尾要有可带走的产物（STR-03 盯的就是这个）。

    原文以两个参数的说明结束：读者读完了带不走任何东西。
    """
    text = article_text(PG_SWITCH)
    assert "| 要求 | 在哪配 | 漏了会怎样 |" in text, "开头没有前置条件清单表"
    assert "### 4.8 主备切换巡检清单" in text, "结尾没有巡检清单"
    assert "### 4.9 延伸阅读" in text, "结尾没有延伸阅读"


def test_the_pg_article_extension_links_all_resolve():
    """单元：延伸阅读的链接不能是死链。

    bundle 里的相对链接按 bundle 自己的目录解析，所以 `../X.md` 指的是
    bundle 所在目录的上一级。
    """
    text = article_text(PG_SWITCH)
    section = text.split("### 4.9 延伸阅读")[1]
    links = re.findall(r"\]\(([^)]+)\)", section)
    assert len(links) >= 5, f"延伸阅读条目太少（{len(links)} 条）"
    for link in links:
        target = (PG_SWITCH.parent / link).resolve()
        assert target.is_file(), f"延伸阅读的链接指向不存在的文件：{link}"


def test_the_pg_article_html_attributes_are_not_broken():
    """单元：HTML 属性的引号被换成中文弯引号，标签就不生效了。

    `<font color=“red”>` 不是一个合法的属性值，红字就没了——而且
    页面看上去一点异常都没有。
    """
    text = article_text(PG_SWITCH)
    assert not re.search(r'=\s*“', text), "有 HTML 属性被写成了中文弯引号"


def test_the_pg_article_keeps_only_the_intentional_warn_signal():
    """集成：合入后只剩那一条刻意的平行示例。

    原文是 3 条 warn（AIF-02 空泛评价 / AIF-03 超长段落 /
    AIF-05 近似重复句）。剩下的 AIF-05 是「表」与「索引」两段刻意
    平行句式，审校记录里写明**不要为了消信号去改**——所以这里把它
    钉住：有人顺手把它「改顺」了，这条会红。
    """
    report = run_checker(PG_SWITCH)
    warns = [s for s in report["signals"] if s["severity"] == "warn"]
    assert [s["rule"] for s in warns] == ["AIF-05"], (
        f"合入后的 warn 信号不对：{warns}")
    infos = [s for s in report["signals"] if s["severity"] == "info"]
    assert not infos, f"合入后还有 info 信号：{infos}"


def test_only_one_pg_article_with_this_title():
    """集成：站点上不能出现同标题的第二篇。"""
    title = "PostgreSQL存储、索引及系统优化、主备切换"
    same = []
    for path in sorted(DOCS_ROOT.rglob("*.md")):
        match = re.search(r"^#\s+(.*\S)\s*$",
                          path.read_text(encoding="utf-8", errors="replace"), re.M)
        if match and match.group(1).strip() == title:
            same.append(path.relative_to(REPO_ROOT).as_posix())
    assert same == [
        "docs/pgsql/replication/Postgresql存储、索引及系统优化、主备切换/index.md",
    ], f"全树有多篇同名文章：{same}"
