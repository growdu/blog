"""契约七（站点 IP 骨架）的规格漂移守卫。

规格里的每一个实测数字都是**手写的事实源**——它不该跟着生产代码变，
所以这里从仓库现状**重新算一遍**，再跟规格里的字面值逐条对。

判据是反向的：**仓库变了、规格没改 → 测试红。**

两份事实源各管各的：

- 规格（`publish/spec/08-站点IP骨架.md`）写「现状是什么、目标是多少」；
- 本文件写「怎么从仓库现状把这些数字重新算出来」。

阈值**不从被测代码 import**（`aiv/pipeline/pyv/` 里没有这些常量，
也不该有）——那样守卫就变成自证，永远是绿的。

放在根级 `tests/`，随 `site-guard.yml` 进 CI。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "publish" / "spec" / "08-站点IP骨架.md"

# --- 期 → 主母稿的映射 ---------------------------------------------------
#
# 这张表是**手写的事实源**：哪一期的底稿是哪一篇，是选题时定下的事实，
# 不是代码算出来的。出处见 `aiv/选题库.md` 各 EP 段的「选题依据」。
#
# 主母稿 = 该期篇幅最大、承载本期机制的那一篇。
EPISODE_DRAFTS = {
    "pg-parallel-decode": "docs/database/postgresql-logical-replication-end-to-end-flow/index.md",
    "csn-total-ordering": "docs/db/opengauss-csn-total-ordering/index.md",
    "wal-interleave": "docs/database/postgresql-logical-replication-worker-model/index.md",
    "parallel-apply": "docs/database/postgresql-logical-replication-ddl-trigger-apply-worker/index.md",
    "structured-ddl": "docs/database/postgresql-logical-replication-ddl-dml-ordering/index.md",
    "row-lock": "docs/database/postgresql-row-lock-deep-dive/index.md",
}

# 期号标签的固定顺序。规格 §2.1 的表里期号与 slug 同行，
# 测试从那里读映射，这里只固定「哪一行是第几期」。
EP_LABEL_ORDER = ["EP01", "EP02", "EP03", "EP04", "EP05", "EP06"]

# 六期的实测成片时长（秒），来自 `aiv/storyboard_<EP>__nobrand.json`。
# 这里写成字面值而不是从 JSON 读——JSON 是**产物**，规格要对齐的是
# 「已确认的实测值」，产物随时可能被重跑覆盖。
EPISODE_DURATION_S = {
    "pg-parallel-decode": 32.436,
    "csn-total-ordering": 35.316,
    "wal-interleave": 34.596,
    "parallel-apply": 35.424,
    "structured-ddl": 34.128,
    "row-lock": 35.172,
}

# 口播稿的**非空白正文字数**。实测值，与各 `aiv/字幕-*.md` 的元数据一致。
EPISODE_SPOKEN_CHARS = {
    "pg-parallel-decode": 241,
    "csn-total-ordering": 254,
    "wal-interleave": 241,
    "parallel-apply": 244,
    "structured-ddl": 252,
    "row-lock": 256,
}

# 规格里写死的阈值（EV 表）。这些是**独立取值**，
# 一致性由 `test_evidence_threshold_table_matches_the_independent_values` 单独钉住。
EV_SOURCE_PATH_MIN = 6
EV_FUNCTION_REF_MIN = 1
EV_DIAGRAM_MIN = 1
EV_SPEECH_RATE = 7.19
EV_DRAFT_P90 = 23_583

# 规格里引用、但**尚未创建**的路径（本期要新增的）。
# 实施对应 commit 时从这里移除——移除的那一刻就是该模块真的落地了。
PLANNED_PATHS = {
    "publish/publishkit/episode.py",
    "publish/publishkit/evidence.py",
    "publish/publishkit/linkcheck.py",
    "publish/tests/test_episode.py",
    "publish/tests/test_evidence.py",
    "publish/tests/test_episode_page.py",
    "source/_data/",
    "source/_data/podcast_index.json",
    "source/podcast/index.md",
    "source/feed.xml",
    "aiv/pipeline/scripts/episode-baseline.py",
}

# 仓库的顶层目录。只有**顶层目录开头**的 token 才可能被当成仓库路径——
# 否则 `publishkit/episode.py`（模块记法）、`/feed.xml`（站点 URL）、
# `:year/:month/:day/:title/`（permalink 模板）都会被误判。
REPO_TOP_DIRS = {
    "aiv", "bilibili", "browser", "channels", "docs", "douyin",
    "public", "publish", "review", "scripts", "source", "tests",
    "tools", "toutiao", "weixin",
}

# **生成目录**：`.gitignore` 里的 `/source/`（只放行 `source/all/` 与
# `source/recommended/`）与 `public/`。它们的内容由 `sync-hexo.py` 与
# `hexo generate` 编译出来，**干净检出里不存在**。
#
# 这条守卫若把它们当普通路径要求存在，**在干净检出上必然红**——
# 那不是规格错了，是守卫把构建产物当成了仓库事实。
GENERATED_PREFIXES = ("source/", "public/")

SRC_PATH_RE = re.compile(
    r"(?:docs|src|include|backend)/[A-Za-z0-9_\-/]*\.(?:c|h|cc|cpp|hpp|py|go|rs|java|sql)"
)
FUNC_REF_RE = re.compile(r"`[A-Za-z_][A-Za-z0-9_]*\s*\([^`]*\)`")


# --- 小工具 ---------------------------------------------------------------


def _spec_text() -> str:
    return SPEC.read_text(encoding="utf-8")


def _body_of(path: Path) -> str:
    """读 Markdown 正文，剥掉 front matter。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    return re.sub(r"^---\n[\s\S]*?\n---\n", "", text)


def _dense_chars(text: str) -> int:
    """去掉所有空白后的字符数——规格里「字数」一律指这个。"""
    return len(re.sub(r"\s+", "", text))


def _is_separator(line: str) -> bool:
    if not line.startswith("|"):
        return False
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return bool(cells) and all(c and set(c) <= set("-: ") for c in cells)


def _markdown_table(text: str, header_keyword: str) -> list[list[str]]:
    """按表头关键词定位一张 markdown 表，返回逐行单元格的文本。

    只认**真正的表头**（下一行是 `|---|` 分隔行）——否则正文里随便一行
    含有那个关键词也会被当成表头，定位就飘了。
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("|") or header_keyword not in line:
            continue
        if index + 1 >= len(lines) or not _is_separator(lines[index + 1]):
            continue  # 不是表头
        rows: list[list[str]] = []
        for row in lines[index:]:
            if not row.startswith("|"):
                break
            if _is_separator(row):
                continue
            rows.append([c.strip() for c in row.strip().strip("|").split("|")])
        return rows
    raise AssertionError(f"规格里找不到表头含 {header_keyword!r} 的表")


def _row_with(rows: list[list[str]], column: int, needle: str) -> list[str]:
    for row in rows:
        if len(row) > column and needle in row[column]:
            return row
    raise AssertionError(f"表里找不到第 {column} 列含 {needle!r} 的行")


def _number(cell: str) -> float:
    """从单元格里取第一个数字（容忍 `` `32.436` `` 与 `` 337:1 `` 这类写法）。"""
    match = re.search(r"-?\d+(?:\.\d+)?", cell.replace(",", ""))
    assert match, f"单元格里没有数字：{cell!r}"
    return float(match.group(0))


def _slug_of(cell: str) -> str:
    """从单元格里取出反引号包着的 slug。"""
    match = re.search(r"`([^`]+)`", cell)
    assert match, f"单元格里没有反引号 slug：{cell!r}"
    return match.group(1)


def _episode_map() -> dict[str, str]:
    """从规格 §2.1 的表读出「期号 → slug」。

    这张表是规格里唯一同时写着两者的表，读它就不会有第二份真源。
    """
    rows = _markdown_table(_spec_text(), "manifest 里的")
    mapping: dict[str, str] = {}
    for row in rows[1:]:
        mapping[row[0].split()[0]] = _slug_of(row[0])
    return mapping


# --- 契约编号 -------------------------------------------------------------


def test_spec_declares_contract_seven():
    """契约编号不与既有规格冲突。"""
    text = _spec_text()
    assert text.lstrip().startswith("# 契约七："), "规格标题必须是「契约七」"

    # 既有规格各自占用的编号
    assert "契约一：" in (REPO / "publish/spec/00-架构设计.md").read_text(encoding="utf-8")
    assert "契约五：" in (REPO / "publish/spec/06-发布计划与调度.md").read_text(encoding="utf-8")
    assert "契约六：" in (REPO / "publish/spec/07-视频发布契约.md").read_text(encoding="utf-8")

    # 契约七只能出现在这一份规格里
    for path in sorted((REPO / "publish/spec").glob("*.md")):
        if path == SPEC:
            continue
        assert "契约七" not in path.read_text(encoding="utf-8"), (
            f"{path.name} 里也出现了「契约七」，编号冲突"
        )


# --- 路径引用 -------------------------------------------------------------


def test_referenced_repo_paths_exist():
    """规格引用的每个仓库路径都真实存在。

    文档里的**计划新增**路径在 `PLANNED_PATHS` 里显式列出——
    实施对应 commit 时移除，那一刻就是模块真的落地了。
    """
    text = _spec_text()
    candidates: set[str] = set()

    def _accept(token: str) -> None:
        token = token.strip()
        if not token or "://" in token or " " in token:
            return
        if any(ch in token for ch in "<>*{}…"):
            return  # 占位符或通配
        if token.startswith("/") or token.startswith(":"):
            return  # 站点 URL / permalink 模板
        head = token.split("/", 1)[0]
        if head not in REPO_TOP_DIRS:
            return  # 模块记法（publishkit/episode.py）之类
        if not re.search(r"\.[A-Za-z0-9]+$", token) and not token.endswith("/"):
            return
        candidates.add(token)

    for token in re.findall(r"`([^`\n]+)`", text):
        _accept(token)

    # markdown 链接的目标（相对 publish/spec/）
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if "://" in target or target.startswith("#"):
            continue
        resolved = (SPEC.parent / target).resolve()
        try:
            candidates.add(str(resolved.relative_to(REPO)))
        except ValueError:
            continue  # 指向仓库外

    missing = sorted(
        p for p in candidates
        if p not in PLANNED_PATHS
        and not p.startswith(GENERATED_PREFIXES)
        and not (REPO / p).exists()
    )
    assert not missing, f"规格引用了不存在的路径：{missing}"


def test_generated_prefixes_are_really_gitignored():
    """`source/` 与 `public/` 确实是生成目录——干净检出里没有它们。

    这条断言把「生成目录」这个前提钉住：哪天有人把 `/source/` 从
    `.gitignore` 里放出来，守卫会提醒重新审视 GENERATED_PREFIXES。
    """
    gitignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert "/source/" in gitignore, "/source/ 应当仍在 .gitignore 里"
    assert "public/" in gitignore, "public/ 应当仍在 .gitignore 里"


def test_planned_paths_are_actually_missing():
    """计划新增的路径现在应当还不存在。

    哪天它们被创建了，这条测试会红——那是提醒把路径从 `PLANNED_PATHS`
    移走（移除即承认它已经落地），不是失败。
    """
    already = sorted(p for p in PLANNED_PATHS if (REPO / p).exists())
    assert not already, (
        f"这些路径已经存在了，请从 PLANNED_PATHS 移除：{already}"
    )


# --- 期号表与仓库现状 -----------------------------------------------------


def test_episode_table_covers_exactly_the_six_contracts():
    """规格 §2.1 的期号表与 `aiv/contracts/` 的集合完全相等。

    不多不少：少一期 = 规格漏了；多一期 = 规格写错了 slug。
    """
    contract_slugs = {
        json.loads(p.read_text(encoding="utf-8"))["episode"]
        for p in sorted((REPO / "aiv/contracts").glob("*.json"))
    }
    assert contract_slugs == set(EPISODE_DRAFTS), "契约集合与期→母稿映射不一致"

    mapping = _episode_map()
    assert set(mapping) == set(EP_LABEL_ORDER), (
        f"规格期号表的期号标签不对：{sorted(mapping)}"
    )
    assert set(mapping.values()) == contract_slugs, (
        f"规格期号表与契约集合不一致："
        f"规格 {sorted(mapping.values())}，契约 {sorted(contract_slugs)}"
    )


def test_manifest_urls_quoted_in_the_spec_match_reality():
    """规格 §2.1 表里抄的 `url` 必须与 `aiv/publish/<EP>.json` 一致。

    这张表记录的是**现状**（链接是死的），所以它必须跟着 manifest 变；
    改动 manifest 而不改规格，就是规格漂移了。
    """
    rows = _markdown_table(_spec_text(), "manifest 里的")
    for row in rows[1:]:
        slug = _slug_of(row[0])
        manifest = json.loads(
            (REPO / "aiv/publish" / f"{slug}.json").read_text(encoding="utf-8")
        )
        assert manifest["url"] in row[1], (
            f"{slug} 的 manifest url 与规格表不一致："
            f"manifest={manifest['url']!r}，规格表={row[1]!r}"
        )


# --- §2.3 深度损耗表 ------------------------------------------------------


def test_depth_baseline_table_matches_reality():
    """规格 §2.3 的母稿字数 / 压缩比 / 图数必须能重算出来。"""
    mapping = _episode_map()
    rows = _markdown_table(_spec_text(), "母稿字数")
    # 表头 + 六期 + 合计行
    assert len(rows) - 1 == len(EPISODE_DRAFTS) + 1, "基线表的行数与六期不符"

    for row in rows[1:]:
        if "合计" in row[0]:
            continue  # 合计行由 test_total_compression_ratio_matches_reality 管
        label = row[0].split()[0]
        slug = mapping[label]
        draft = REPO / EPISODE_DRAFTS[slug]
        assert draft.exists(), f"{slug} 的母稿不存在：{draft}"

        body = _body_of(draft)
        actual_chars = _dense_chars(body)
        assert _number(row[1]) == actual_chars, (
            f"{slug} 母稿字数漂移：规格 {_number(row[1])}，实际 {actual_chars}"
        )

        actual_ratio = actual_chars / EPISODE_SPOKEN_CHARS[slug]
        assert _number(row[3]) == pytest.approx(actual_ratio, abs=1), (
            f"{slug} 压缩比漂移：规格 {_number(row[3])}，实际 {actual_ratio:.0f}"
        )

        actual_diagrams = len(re.findall(r"```mermaid", body))
        assert _number(row[4]) == actual_diagrams, (
            f"{slug} 机制图数漂移：规格 {_number(row[4])}，实际 {actual_diagrams}"
        )


def test_total_compression_ratio_matches_reality():
    """规格 §2.3 合计行的 179:1 必须能重算出来。"""
    rows = _markdown_table(_spec_text(), "母稿字数")
    total_row = _row_with(rows, 0, "合计")

    total_chars = sum(
        _dense_chars(_body_of(REPO / path)) for path in EPISODE_DRAFTS.values()
    )
    total_spoken = sum(EPISODE_SPOKEN_CHARS.values())

    assert _number(total_row[1]) == total_chars, (
        f"母稿合计漂移：规格 {_number(total_row[1])}，实际 {total_chars}"
    )
    assert _number(total_row[2]) == total_spoken, (
        f"口播合计漂移：规格 {_number(total_row[2])}，实际 {total_spoken}"
    )
    assert _number(total_row[3]) == pytest.approx(total_chars / total_spoken, abs=1)


# --- EV 阈值 --------------------------------------------------------------


def test_evidence_thresholds_are_met_by_the_existing_drafts():
    """EV-01 / EV-02 / EV-04 是**存量达标线**：六期母稿必须全部满足。

    取值来自六期现状的最小值，所以上线时不会把已有资产判红。
    """
    for slug, draft_path in EPISODE_DRAFTS.items():
        body = _body_of(REPO / draft_path)
        sources = len(set(SRC_PATH_RE.findall(body)))
        functions = len(set(FUNC_REF_RE.findall(body)))
        diagrams = len(re.findall(r"```mermaid", body))

        assert sources >= EV_SOURCE_PATH_MIN, (
            f"{slug} 源码路径只有 {sources} 个，低于存量达标线 {EV_SOURCE_PATH_MIN}"
        )
        assert functions >= EV_FUNCTION_REF_MIN, (
            f"{slug} 函数引用只有 {functions} 处，低于存量达标线 {EV_FUNCTION_REF_MIN}"
        )
        assert diagrams >= EV_DIAGRAM_MIN, (
            f"{slug} 机制图只有 {diagrams} 张，低于存量达标线 {EV_DIAGRAM_MIN}"
        )


def test_evidence_threshold_table_matches_the_independent_values():
    """规格 EV 表里写的阈值必须与本文件的独立取值一致。"""
    rows = _markdown_table(_spec_text(), "指标")
    assert _number(_row_with(rows, 0, "EV-01")[2]) == EV_SOURCE_PATH_MIN
    assert _number(_row_with(rows, 0, "EV-02")[2]) == EV_FUNCTION_REF_MIN
    assert _number(_row_with(rows, 0, "EV-04")[2]) == EV_DIAGRAM_MIN


def test_speech_rate_constant_matches_the_six_episodes():
    """EV-05 的语速常数必须等于六期实测均值。

    语速是「口播字数 ÷ 实测时长」的均值，规格里写 7.19 字/秒。
    """
    rates = [
        EPISODE_SPOKEN_CHARS[slug] / EPISODE_DURATION_S[slug]
        for slug in EPISODE_DRAFTS
    ]
    mean_rate = sum(rates) / len(rates)
    assert mean_rate == pytest.approx(EV_SPEECH_RATE, abs=0.01), (
        f"语速漂移：规格 {EV_SPEECH_RATE}，实测 {mean_rate:.4f}"
    )

    rows = _markdown_table(_spec_text(), "指标")
    row = _row_with(rows, 0, "EV-05")
    assert "7.19" in row[3], f"EV-05 的依据栏必须写出语速 7.19，实为：{row[3]!r}"


def test_draft_p90_constant_matches_the_docs_distribution():
    """EV-06 的 p90 必须等于 `docs/` 全树字数的实际 p90。"""
    lengths = sorted(
        _dense_chars(_body_of(path))
        for path in (REPO / "docs").rglob("*.md")
    )
    assert len(lengths) > 100, "docs/ 语料异常少，分布不可信"
    p90 = lengths[int(len(lengths) * 0.9)]
    assert p90 == EV_DRAFT_P90, (
        f"p90 漂移：规格 {EV_DRAFT_P90}，实测 {p90}（共 {len(lengths)} 篇）"
    )

    rows = _markdown_table(_spec_text(), "指标")
    row = _row_with(rows, 0, "EV-06")
    assert "23,583" in row[3], f"EV-06 的依据栏必须写出 23,583，实为：{row[3]!r}"


# --- 平台矩阵 -------------------------------------------------------------


def test_platform_capabilities_referenced_in_the_matrix_exist():
    """§9 平台形态矩阵里点名的平台，都必须有能力声明。"""
    rows = _markdown_table(_spec_text(), "时长")
    platform_names = {"B站", "视频号", "抖音", "头条号", "公众号", "YouTube"}
    mentioned = set()
    for row in rows[1:]:
        for column in (0, 3):  # 形态列 + 落点列
            if len(row) > column:
                for name in platform_names:
                    if name in row[column]:
                        mentioned.add(name)

    assert {"B站", "视频号", "抖音", "头条号"} <= mentioned, (
        f"矩阵里应当点到四个已接平台，实际点到：{sorted(mentioned)}"
    )

    for capability in ("bilibili", "channels", "douyin", "toutiao"):
        assert (REPO / "publish/capabilities" / f"{capability}.toml").exists(), (
            f"能力声明缺失：{capability}.toml"
        )


def test_spec_marks_youtube_as_not_yet_supported():
    """YouTube 没有能力声明，规格里必须把它标成未接入，不能当成已有渠道。"""
    assert not (REPO / "publish/capabilities/youtube.toml").exists(), (
        "若已接入 YouTube，请先更新本守卫与规格的矩阵"
    )
    text = _spec_text()
    assert "YouTube 接入" in text, "非目标里应当列出「YouTube 接入」"
