"""人格规则：把《人格规范》变成能跑的检查。

规范文档说「说什么」，这里说「怎么判」。两者必须同步——
规则编号（`RULE_IDS`）与《人格规范》§7 的表格一一对应，
由 `pipeline/tests/test_persona.py` 盯着。

判定分两类：

- **硬约束（error）**：违反就不像 growdu，出片前必须改；
- **倾向（warning）**：不算错，但提示这一期没把人格透出来。

用法：

    python -m pyv.cli persona check --script ../字幕-并行解码.md

能力域的划分依据是博客文章的真实覆盖范围（规范 §3.1），
越界主题的依据是博客里没有实现记录的方向（规范 §3.3）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pyv.timeline import display_width

# aiv/ 是 pipeline/ 的上一级：pyv/persona.py → pyv → pipeline → aiv
AIV_ROOT = Path(__file__).resolve().parents[2]
PERSONA_SPEC = AIV_ROOT / "人格规范.md"

ERROR = "error"
WARNING = "warning"

# 规则编号。顺序与《人格规范》§7 的表格一致。
RULE_IDS = (
    "persona.no-hype",
    "persona.no-brand-self",
    "persona.no-absolute",
    "persona.domain",
    "persona.evidence",
    "persona.boundary",
    "persona.method",
    "persona.short-sentence",
    "persona.sentence-length",
)

# ---------------------------------------------------------------- 词表

# 营销腔（《人格规范》§5.4）
HYPE_WORDS = (
    "震撼", "颠覆", "碾压", "秒杀", "吊打", "神级", "yyds", "史上最", "必看",
    "一文读懂", "深度揭秘", "惊天内幕", "私藏", "干货满满", "强烈推荐",
    "错过后悔", "赶紧收藏", "革命性", "史诗级", "王炸", "降维打击",
)

# 机构 / 平台自称
BRAND_SELF_WORDS = (
    "本公众号", "本号", "小程序", "小编", "笔者", "笔者的", "我们团队",
    "公司内部", "客户现场", "本团队",
)

# 绝对化断言——人格的核心是给边界，不是把话说满
ABSOLUTE_WORDS = (
    "一定", "必然", "100%", "绝对", "永远不会", "完全不可能", "百分之百",
    "无一例外", "任何情况下都",
)

# 能力域关键词。键名与《人格规范》§3.1 表格的第一列同名。
CAPABILITY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "PostgreSQL 内核机制": (
        "postgres", "postgresql", "pgsql", "pgbench", "mvcc", "latch",
        "multixact", "btree", "toast", "catalog", "vacuum", "xid", "wal",
        "逻辑复制", "物理复制", "流复制", "复制槽", "逻辑解码", "解码",
        "事务", "谓词锁", "隔离级别", "查询计划", "explain", "元组",
        "回放", "checkpoint", "归档", "死锁", "索引", "快照", "分区",
        "共享内存", "缓冲区", "热更新", "备库", "主库", "扩展", "数据库",
    ),
    "逻辑复制与解码": (
        "reorderbuffer", "snapbuild", "pgoutput", "apply worker",
        "并行apply", "槽", "copy data", "流式解码", "spill",
    ),
    "扩展与第三方深潜": (
        "citus", "pgvector", "timescaledb", "pg_stat_statements",
        "pgduckdb", "postgis", "pgbackrest", "pgcrypto", "cstore_fdw",
        "deep-dive", "深度剖析",
    ),
    "分布式与高可用": (
        "raft", "仲裁", "quorum", "脑裂", "splitbrain", "corosync",
        "qdevice", "pacemaker", "patroni", "repmgr", "etcd", "zookeeper",
        "双中心", "三中心", "多中心", "同城", "容灾", "高可用", "failover",
        "选主", "仲裁员", "paxos", "故障转移", "一致性", "两地三中心",
    ),
    "Linux 系统与内核": (
        "linux", "系统调用", "syscall",
        "内存管理", "巨页", "hugepage", "页表", "mmap", "字符设备",
        "块设备", "驱动", "ebpf", "bpf", "tracepoint", "kprobe", "coredump",
        "ioctl", "调度", "中断", "dmesg", "vmstat", "iostat", "strace",
        "内核态", "用户态", "内核模块", "互斥", "条件变量", "信号量", "shell",
    ),
    "网络与用户态协议栈": (
        "tcp", "udp", "ipv4", "ipv6", "mtu", "pmtu", "分片", "dpdk", "vpp",
        "vlib", "rte_ring", "kni", "uio", "vfio", "抓包", "pktgen",
        "pcap", "协议栈", "socket", "keepalive", "重传", "拥塞", "带宽",
        "线速", "时延", "网卡", "tcpdump", "用户态",
    ),
    "性能与可观测": (
        "性能", "压测", "基准", "benchmark", "火焰图", "flame graph",
        "perf", "profiling", "吞吐", "tps", "qps", "p99", "监控",
        "可观测", "链路追踪", "tracing", "opentelemetry", "prometheus",
        "grafana", "慢查询", "火焰", "耗时",
    ),
    "工程与工具链": (
        "c++", "rust", "python", "golang", "cmake", "autoconf", "automake",
        "meson", "makefile", "单元测试", "cunit", "pytest", "gdb", "调试",
        "交叉编译", "docker", "容器", "持续集成", "git", "svn", "编译",
        "c语言", "c代码",
    ),
    "存储与文件": (
        "nfs", "samba", "sshfs", "存储", "磁盘", "文件系统", "fs m",
        "checksum", "校验和", "落盘", "刷脏", "页空间",
    ),
    "自建平台与内容链路": (
        "elasticsearch", "lucene", "倒排", "全文检索", "oh-my-search",
        "oh-my-code", "sphinx", "hexo", "公众号", "视频号", "markdown",
        "字幕", "流水线", "出片", "博客",
    ),
    "AI（认知层）": (
        "大模型", "llm", "chatgpt", "claude", "提示词", "prompt", "幻觉",
        "人工智能", "智能体", "agent", "上下文", "token", "涌现",
    ),
}

# 零覆盖方向。键名与《人格规范》§3.3 表格的第一列同名。
# 博客里没有任何实现记录，讲了就是编——硬约束。
ZERO_COVERAGE: dict[str, tuple[str, ...]] = {
    "模型训练与微调实现": (
        "pytorch", "tensorflow", "深度学习框架", "训练框架", "推理框架",
        "分布式训练", "lora", "sft", "vllm", "huggingface", "transformers",
    ),
    "芯片与新兴技术方向": (
        "芯片设计", "数字电路", "区块链", "智能驾驶", "元宇宙", "量子计算",
    ),
}

# 浅覆盖方向。键名同上。
# 博客里有一两篇，讲的时候要克制——倾向。
SHALLOW_COVERAGE: dict[str, tuple[str, ...]] = {
    "前端框架深度": ("小程序开发", "vue源码", "react源码", "angular", "跨端框架"),
    "荐股与量化交易": ("量化交易", "期货", "荐股", "选股", "股票筛选", "炒股"),
}

# 量化依据：数字 + 单位，或版本号
_EVIDENCE_PATTERNS = (
    re.compile(r"\d+(?:\.\d+)?\s*(?:核|倍|%|毫秒|秒|分钟|小时|行|条|万|亿"
               r"|字节|MB|GB|TB|KB|TPS|QPS|ms|us)"),
    re.compile(r"(?:postgresql|postgres|golang|rust|linux|kernel|vpp|dpdk)"
               r"\s*v?\d+(?:\.\d+)*", re.IGNORECASE),
)

# 边界 / 代价表达
BOUNDARY_WORDS = (
    "不要", "别在", "别把", "别用", "前提", "代价", "注意", "适合",
    "不适合", "除非", "坑", "误区", "反模式", "边界", "限制", "权衡",
    "取舍", "什么时候", "瓶颈", "风险", "上限", "适用",
)

# 方法论表达（升维 / 归纳 / 类推 / 试错 / 总结）
METHOD_WORDS = (
    "升维", "归纳", "类推", "试错", "总结", "提炼", "抽象", "规律",
    "心智模型", "地图", "换个层次", "一层层剥开", "下次",
)

# 比较句：拿越界主题做对比时不算越界（"这跟大模型训练不一样"）
COMPARISON_MARKERS = ("不像", "不同", "区别", "而不是", "并非", "不一样")

# 一口气念完的句子宽度上限；口播单句的宽度上限
SHORT_SENTENCE_WIDTH = 28
SHORT_SENTENCE_RATIO = 0.6
MAX_SENTENCE_WIDTH = 40

_LATIN_TOKEN = re.compile(r"[a-z0-9_]+")


@dataclass(frozen=True)
class Finding:
    """一条检查结果。"""

    rule_id: str
    level: str
    message: str
    sentence: int | None = None  # 1 起的句序；整篇级问题为 None


@dataclass(frozen=True)
class Report:
    """一份口播稿的检查结果。"""

    sentences: tuple[str, ...]
    findings: tuple[Finding, ...]
    domains: tuple[str, ...] = ()

    @property
    def domain_label(self) -> str:
        """这一期落在哪些能力域里。"""
        return "、".join(self.domains) if self.domains else "未识别"

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.level == WARNING]

    @property
    def ok(self) -> bool:
        """没有硬约束违规就算通过。"""
        return not self.errors

    def by_rule(self, rule_id: str) -> list[Finding]:
        return [f for f in self.findings if f.rule_id == rule_id]


# ---------------------------------------------------------------- 工具


def _hits(text: str, words: tuple[str, ...]) -> int:
    """统计关键词命中次数。英文按词边界匹配，中文按子串。"""
    lowered = text.lower()
    tokens = set(_LATIN_TOKEN.findall(lowered))
    count = 0
    for word in words:
        if word.isascii():
            if word in tokens:
                count += 1
        elif word in lowered:
            count += 1
    return count


def _plain_sentences(text: str) -> list[str]:
    """把纯文本稿拆成句子：每个非空行一句，跳过标题与代码围栏。"""
    sentences: list[str] = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped or stripped.startswith("#"):
            continue
        sentences.append(stripped)
    return sentences


def extract_sentences(path: str | Path) -> list[str]:
    """从口播稿里取出句子，每句一行。

    支持两种格式：

    - 带「口播稿」小节的 Markdown（与 `align.parse_script` 同格式）
    - 纯文本，每行一句
    """
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    try:
        from pyv import align

        sentences = align.parse_script(file)
    except (ValueError, OSError):
        sentences = []
    if sentences:
        return sentences
    return _plain_sentences(text)


# ---------------------------------------------------------------- 规则


def _rule_no_hype(sentences: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for index, sentence in enumerate(sentences, 1):
        lowered = sentence.lower()
        for word in HYPE_WORDS:
            if word in lowered:
                findings.append(Finding(
                    "persona.no-hype", ERROR,
                    f"第 {index} 句含营销腔禁词「{word}」", index,
                ))
                break  # 一句只报一次，够指认问题了
    return findings


def _rule_no_brand_self(sentences: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for index, sentence in enumerate(sentences, 1):
        lowered = sentence.lower()
        for word in BRAND_SELF_WORDS:
            if word in lowered:
                findings.append(Finding(
                    "persona.no-brand-self", ERROR,
                    f"第 {index} 句以机构/平台自称「{word}」——growdu 自称「我」", index,
                ))
                break
    return findings


def _rule_no_absolute(sentences: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for index, sentence in enumerate(sentences, 1):
        lowered = sentence.lower()
        for word in ABSOLUTE_WORDS:
            if word in lowered:
                findings.append(Finding(
                    "persona.no-absolute", ERROR,
                    f"第 {index} 句是绝对化断言「{word}」——人格是给边界，不是把话说满",
                    index,
                ))
                break
    return findings


def _rule_domain(sentences: list[str]) -> list[Finding]:
    """技术主题必须落在能力边界之内。

    - **零覆盖方向**（博客里没有任何实现记录）：句子命中就是硬约束违规。
    - **浅覆盖方向**（博客里只有一两篇）：命中是倾向，提醒讲的时候要克制。
    - 整期都在能力边界外：硬约束违规。

    整段比较句不算——"这跟量子计算不一样"只是拿来做对比，
    不是要讲这个主题。
    """
    findings: list[Finding] = []
    zero_words = [w for words in ZERO_COVERAGE.values() for w in words]
    shallow_words = [w for words in SHALLOW_COVERAGE.values() for w in words]

    any_zero = False
    any_in_domain = False
    for index, sentence in enumerate(sentences, 1):
        lowered = sentence.lower()
        if _domain_hit_count(lowered):
            any_in_domain = True
        if any(marker in lowered for marker in COMPARISON_MARKERS):
            continue
        zero = [w for w in zero_words if w in lowered]
        if zero:
            any_zero = True
            findings.append(Finding(
                "persona.domain", ERROR,
                f"第 {index} 句讲的是零覆盖方向（{'、'.join(zero[:3])}）"
                f"——博客里没有任何实现记录，growdu 讲不了这个深度", index,
            ))
        shallow = [w for w in shallow_words if w in lowered]
        if shallow:
            findings.append(Finding(
                "persona.domain", WARNING,
                f"第 {index} 句碰到覆盖很浅的方向（{'、'.join(shallow[:3])}）"
                f"——博客里只有一两篇，讲的时候要克制", index,
            ))

    if any_zero and not any_in_domain:
        findings.append(Finding(
            "persona.domain", ERROR,
            "整期都在讲能力边界外的主题——growdu 讲不了这个深度",
        ))
    return findings


def _domain_hit_count(text: str) -> int:
    """这段文字命中了多少个能力域关键词。"""
    return sum(_hits(text, words) for words in CAPABILITY_KEYWORDS.values())


def detect_domains(sentences: list[str]) -> tuple[str, ...]:
    """这一期落在哪些能力域里（按命中数排序）。"""
    text = " ".join(sentences).lower()
    scored: list[tuple[int, str]] = []
    for name, words in CAPABILITY_KEYWORDS.items():
        hits = _hits(text, words)
        if hits:
            scored.append((hits, name))
    scored.sort(reverse=True)
    return tuple(name for _, name in scored)


def _rule_evidence(sentences: list[str]) -> list[Finding]:
    for index, sentence in enumerate(sentences, 1):
        if any(pattern.search(sentence) for pattern in _EVIDENCE_PATTERNS):
            return []
    return [Finding(
        "persona.evidence", WARNING,
        "全篇没有量化的可验证依据（数字 + 单位，或版本号）——数字说话是人格底色",
    )]


def _rule_boundary(sentences: list[str]) -> list[Finding]:
    text = " ".join(sentences)
    for word in BOUNDARY_WORDS:
        if word in text:
            return []
    return [Finding(
        "persona.boundary", WARNING,
        "全篇没有边界或代价的表达——只讲优点，不讲什么时候不该用",
    )]


def _rule_method(sentences: list[str]) -> list[Finding]:
    text = " ".join(sentences)
    for word in METHOD_WORDS:
        if word in text:
            return []
    return [Finding(
        "persona.method", WARNING,
        "全篇没有方法论表达（升维 / 归纳 / 类推 / 试错）——"
        "「持续总结方法」的人格没透出来",
    )]


def _rule_short_sentence(sentences: list[str]) -> list[Finding]:
    if not sentences:
        return []
    short = sum(
        1 for s in sentences if display_width(s) <= SHORT_SENTENCE_WIDTH
    )
    ratio = short / len(sentences)
    if ratio >= SHORT_SENTENCE_RATIO:
        return []
    return [Finding(
        "persona.short-sentence", WARNING,
        f"能一口气念完的句子（宽度 ≤ {SHORT_SENTENCE_WIDTH}）只占 {ratio:.0%}，"
        f"低于 {SHORT_SENTENCE_RATIO:.0%}",
    )]


def _rule_sentence_length(sentences: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for index, sentence in enumerate(sentences, 1):
        width = display_width(sentence)
        if width > MAX_SENTENCE_WIDTH:
            findings.append(Finding(
                "persona.sentence-length", WARNING,
                f"第 {index} 句宽度 {width:.0f} 超过 {MAX_SENTENCE_WIDTH}，"
                f"一句塞了太多信息", index,
            ))
    return findings


_RULES = (
    _rule_no_hype,
    _rule_no_brand_self,
    _rule_no_absolute,
    _rule_domain,
    _rule_evidence,
    _rule_boundary,
    _rule_method,
    _rule_short_sentence,
    _rule_sentence_length,
)


# ---------------------------------------------------------------- 入口


def check_sentences(sentences: list[str]) -> Report:
    """检查一批句子，返回报告。"""
    findings: list[Finding] = []
    for rule in _RULES:
        findings.extend(rule(sentences))
    return Report(
        sentences=tuple(sentences),
        findings=tuple(findings),
        domains=detect_domains(sentences),
    )


def check_file(path: str | Path) -> Report:
    """检查一份口播稿（Markdown 或纯文本）。"""
    return check_sentences(extract_sentences(path))
