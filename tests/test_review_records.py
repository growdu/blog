"""契约测试：审校记录、进度索引与 docs/ 纯净性。

这些是 review/README.md 流程的「不可绕过」部分。规范写在纸上没有约束力，
能让人绕过规范的是「反正没人查」——所以这里把规范里最容易被绕过的几条
钉成断言：

1. 记录必须落在受审支柱目录下（审校范围不扩散）；
2. 记录必须齐全 README 模板的每个小节（半截记录等于没记录）；
3. 记录里引用的原文必须真实存在（原文改名了，记录就成了孤儿）；
4. 索引与记录目录必须双向一致（进度表不能骗人）；
5. 状态取值必须在状态机内，且「已合入」必须真有对应提交、该提交确实改了正文；
6. 「已合入」的记录不能还留着没销掉的待核事实；
7. docs/ 下不得出现审校记录——docs/ 会被 sync-hexo.py 发布成站点文章，
   内部流程漏到线上就是事故。
8. 契约检查本身不能依赖本机 git 配置——GitHub runner 和开发机的 git
   环境并不相同，本地全绿不代表 CI 全绿。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_ROOT = REPO_ROOT / "review"
DOCS_ROOT = REPO_ROOT / "docs"

# 首轮审校范围：数据库内核四支柱。
REVIEWED_PILLARS = ("database", "db", "pgsql", "cluster")

STATES = ("待审", "审校中", "建议中", "已确认", "已合入")

# 事实待核的三种标记。契约测试认得它们，README 也必须写明它们——
# 规范与实现不许各说一套（README 里漏了一种标记，审校的人就照着写，
# 写出来的记录通不过契约测试）。
FACT_DONE = "- [x]"
FACT_NA = "- [不适用]"

# README 模板里的小节标题，一个都不能少。
TEMPLATE_SECTIONS = (
    "## 优先修改",
    "## 事实待核",
    "## 可补的技术证据或产物",
    "## 已确认的改动",
)

INDEX_ROW_RE = re.compile(r"^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|(.*)\|\s*$")

# GitHub runner 的 git 环境：没有开发者的全局 git 配置，core.quotePath
# 取默认值（true）。开发机常常把它关掉，于是同一个提交在两台机器上
# 报出来的路径文本不一样——本地绿、CI 红就是这么来的。
CI_LIKE_GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "core.quotePath",
    "GIT_CONFIG_VALUE_0": "true",
}

# 子进程标记：契约检查会在子进程里再跑一遍自己，没有这个标记就会无限递归。
CHILD_MARKER = "REVIEW_RECORDS_CONTRACT_CHILD"


def record_files() -> list[Path]:
    return sorted(p for p in REVIEW_ROOT.rglob("*.md")
                  if p.name not in ("README.md", "INDEX.md")
                  and "specs" not in p.parts and "plans" not in p.parts)


def parse_record(path: Path) -> dict:
    """Pull the machine-readable lines out of a review record."""
    text = path.read_text(encoding="utf-8")
    info = {"source": "", "scope": "", "status": "", "text": text}
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- 原文："):
            info["source"] = stripped[len("- 原文："):].strip().strip("`")
        elif stripped.startswith("- 范围："):
            info["scope"] = stripped[len("- 范围："):].strip()
        elif stripped.startswith("- 审校状态："):
            info["status"] = stripped[len("- 审校状态："):].strip()
    return info


def section_text(text: str, heading: str) -> str:
    """正文里某个二级标题下的内容（到下一个二级标题为止）。

    不能用 ``split("##")`` 截——记录里出现三级标题（``###``）时会被
    提前截断，挂在后面的条目就看不见了。契约测试「看不见问题」比报错
    更糟，所以这里按标题层级逐行判断。
    """
    lines: list[str] = []
    inside = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## "):
            if inside:
                break
            inside = stripped == heading
            continue
        if inside:
            lines.append(line)
    return "\n".join(lines)


def fact_items(text: str) -> list[str]:
    """「事实待核」段落里的条目行。"""
    return [line.strip() for line in section_text(text, "## 事实待核").split("\n")
            if line.strip().startswith("- ")]


def open_fact_items(text: str) -> list[str]:
    """还没销掉的待核事实条目（既没标 [x]，也没标 [不适用]）。"""
    return [item for item in fact_items(text)
            if not item.startswith(FACT_DONE)
            and not item.startswith(FACT_NA)]


def naive_fact_items(text: str) -> list[str]:
    """标了「不适用」的待核事实条目。"""
    return [item for item in fact_items(text)
            if item.startswith(FACT_NA)]


def index_table() -> tuple[list[str], dict[Path, dict[str, str]]]:
    """进度表的表头与各行内容，按列名取值（不靠位置猜）。

    返回 ``(列名列表, {记录路径: {列名: 值}})``。
    """
    text = (REVIEW_ROOT / "INDEX.md").read_text(encoding="utf-8")
    columns: list[str] = []
    rows: dict[Path, dict[str, str]] = {}
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and cells[0] == "记录":
            columns = cells
            continue
        match = INDEX_ROW_RE.match(stripped)
        if not match:
            continue
        assert columns, "review/INDEX.md 里找不到表头"
        assert len(cells) == len(columns), (
            f"索引行的列数与表头对不上：{stripped}")
        # cells[0] 是记录链接，与表头第一列「记录」一一对应。
        rows[(REVIEW_ROOT / match.group(2)).resolve()] = dict(zip(columns, cells))
    assert columns, "review/INDEX.md 里找不到表头"
    return columns, rows


def git(*args: str, extra_env: dict[str, str] | None = None) -> str:
    """Run git and return its stdout, decoded as UTF-8.

    The encoding is pinned on purpose: ``text=True`` follows the machine
    locale, and a runner with a POSIX locale would mangle the Chinese
    paths this file is about.  ``extra_env`` lets a caller reproduce a
    different machine's git configuration.
    """
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, env=env,
                            capture_output=True, encoding="utf-8",
                            errors="replace")
    return result.stdout


def history_is_shallow() -> bool:
    """Whether this checkout can see the whole commit history.

    A shallow clone (``git clone --depth 1``, which is what
    ``actions/checkout`` does by default) only carries the tip commit, so
    ``git log --all`` cannot show the merge commits of articles that were
    merged earlier.  Without the history, the check below cannot make a
    truthful verdict -- it must be skipped, not failed.
    """
    shallow = REPO_ROOT / ".git" / "shallow"
    if shallow.exists():
        return True
    result = subprocess.run(["git", "rev-parse", "--is-shallow-repository"],
                            cwd=REPO_ROOT, capture_output=True, text=True)
    return result.stdout.strip() == "true"


def merged_commit_for(slug: str) -> list[str]:
    """Commits whose subject is exactly ``docs(review): <slug>``."""
    out = git("log", "--format=%H%x00%s", "--all")
    shas = []
    for line in out.split("\n"):
        if "\x00" not in line:
            continue
        sha, subject = line.split("\x00", 1)
        if subject.strip() == f"docs(review): {slug}":
            shas.append(sha)
    return shas


def changed_paths(sha: str, *, extra_env: dict[str, str] | None = None) -> list[str]:
    """The raw paths a commit touched.

    ``git show --name-only`` C-quotes non-ASCII pathnames unless
    ``core.quotePath`` is false -- and that setting lives in the
    machine's git config: a developer often has it off, a CI runner
    keeps the default (true).  The same commit then reports
    ``docs/cluster/分布式一致性协议.md`` on one machine and
    ``"docs/cluster/\\350\\276\\205..."`` on the other, so comparing the
    record's path against that output matches on one machine and not on
    the other.  ``-z`` pins the output to raw bytes with NUL separators,
    independent of any git configuration.
    """
    out = git("show", "--name-only", "--pretty=format:", "-z", sha,
              extra_env=extra_env)
    return [p for p in out.split("\0") if p]


def test_records_live_under_a_reviewed_pillar():
    for path in record_files():
        rel = path.relative_to(REVIEW_ROOT)
        assert rel.parts[0] in REVIEWED_PILLARS, f"{rel} 不在首轮审校范围内"


def test_record_has_all_template_sections():
    for path in record_files():
        text = path.read_text(encoding="utf-8")
        for section in TEMPLATE_SECTIONS:
            assert section in text, f"{path.name} 缺少小节 {section}"


def test_record_source_file_exists():
    for path in record_files():
        info = parse_record(path)
        assert info["source"], f"{path.name} 没写原文路径"
        source = REPO_ROOT / info["source"]
        assert source.exists(), f"{path.name} 的原文不存在: {info['source']}"


def test_index_matches_record_directory():
    index = REVIEW_ROOT / "INDEX.md"
    assert index.exists(), "缺少 review/INDEX.md"
    listed = set()
    for line in index.read_text(encoding="utf-8").split("\n"):
        match = INDEX_ROW_RE.match(line.strip())
        if not match:
            continue
        listed.add((REVIEW_ROOT / match.group(2)).resolve())
    on_disk = {p.resolve() for p in record_files()}
    assert listed == on_disk, (
        f"索引与记录不一致：索引多 {sorted(str(p) for p in listed - on_disk)}，"
        f"索引缺 {sorted(str(p) for p in on_disk - listed)}"
    )


def test_record_status_is_valid():
    for path in record_files():
        info = parse_record(path)
        assert info["status"] in STATES, f"{path.name} 的状态非法: {info['status']}"


def test_merged_record_has_a_matching_commit():
    if history_is_shallow():
        pytest.skip("浅克隆看不到历史，跳过「已合入提交」检查")
    for path in record_files():
        info = parse_record(path)
        if info["status"] != "已合入":
            continue
        slug = path.stem
        shas = merged_commit_for(slug)
        assert shas, f"{slug} 标了已合入，但没有 docs(review): {slug} 提交"
        touched = False
        for sha in shas:
            if info["source"] in changed_paths(sha):
                touched = True
        assert touched, f"{slug} 的合入提交没有改动 {info['source']}"


def test_merged_record_has_no_open_facts():
    """已合入的记录不能还留着「与本次改动相关」的未核事实。

    三种写法算销掉：
    - ``- [x] ...``   已核实，依据写在条目里
    - ``- [不适用] ...`` 该事实涉及的正文本次没改，原文保留，不构成合入阻塞
    - 空段落          没有待核事实

    仍算未销掉的是普通的 ``- ...`` 条目。
    """
    for path in record_files():
        info = parse_record(path)
        if info["status"] != "已合入":
            continue
        text = path.read_text(encoding="utf-8")
        open_items = open_fact_items(text)
        assert not open_items, f"{path.name} 仍留着未核实的待核事实: {open_items}"


def test_docs_tree_has_no_review_leakage():
    """docs/ 会被发布成站点文章，审校记录绝不能漏进去。"""
    offenders = [p for p in DOCS_ROOT.rglob("*")
                 if p.is_dir() and p.name in ("review", "reviews")]
    assert not offenders, f"docs/ 下出现了审校目录: {offenders}"
    records = [p for p in DOCS_ROOT.rglob("*.md")
               if p.name.startswith("审校") or "审校记录" in p.name]
    assert not records, f"docs/ 下出现了审校记录: {records}"


def test_changed_paths_are_raw_even_when_git_quotes_non_ascii_paths():
    """单元：取「提交改了哪些文件」不能受 git 的路径转义影响。

    ``git show --name-only`` 默认把非 ASCII 路径 C 转义成
    ``"docs/cluster/\\350\\276\\205..."``，除非 ``core.quotePath`` 是 false。
    那是**每台机器自己的** git 配置：开发机常关掉，CI runner 保持默认。
    两边对同一个提交给出的文本不同，路径比对必然一边成一边败。
    """
    chinese = [p for p in record_files()
               if not p.stem.isascii() and parse_record(p)["source"]]
    assert chinese, "没有中文路径的记录，测不到路径转义这个坑"
    record = chinese[0]
    info = parse_record(record)
    shas = merged_commit_for(record.stem)
    assert shas, f"{record.stem} 找不到对应的合入提交"
    paths = changed_paths(shas[0], extra_env=CI_LIKE_GIT_ENV)
    assert info["source"] in paths, (
        f"{info['source']} 不在提交的改动列表里：{paths}")


def test_readme_documents_the_fact_markers_the_contract_enforces():
    """单元：README 得写明契约认得的那几种标记。

    README 是审校的人照着写的规范，契约测试是机器照着判的。两边各说
    一套时，人照规范写出来的记录反而过不了自己的测试。
    """
    readme = (REVIEW_ROOT / "README.md").read_text(encoding="utf-8")
    for marker in (FACT_DONE, FACT_NA):
        assert marker in readme, f"README 里没写明事实待核的标记 {marker!r}"


def test_fact_items_survive_a_subheading_inside_the_section():
    """单元：事实待核段落里出现三级标题时，后面的条目不能被漏掉。

    截段落时按 ``split("##")`` 的话，``###`` 会被当成二级标题的起点，
    挂在它下面的未销掉条目就整段消失——契约测试「看不见问题」比报错
    更糟。
    """
    text = (
        "# 标题\n\n"
        "## 事实待核\n\n"
        "- [x] 已核实\n\n"
        "### 补充说明\n\n"
        "- 还没销掉的条目\n\n"
        "## 下一节\n\n"
        "- 不该被算进来的条目\n"
    )
    items = fact_items(text)
    assert "- 还没销掉的条目" in items, "三级标题后面的条目被漏掉了"
    assert "- 不该被算进来的条目" not in items, "跨小节的条目被算进来了"


def test_index_counts_match_the_records():
    """进度表里的「待确认」必须等于记录里真没销掉的条目数。

    进度表是给人看进度的，数字跟记录对不上就是在骗人。已合入的记录
    「待确认」必须是 0；标了「不适用」的条目单列一栏——事实本身还没
    核实，但本次改动没碰它，不该混进「待确认」里卡住合并。
    """
    columns, rows = index_table()
    assert "待确认" in columns, "进度表少了「待确认」列"
    assert "不阻塞" in columns, "进度表少了「不阻塞」列"
    for path in record_files():
        info = parse_record(path)
        text = path.read_text(encoding="utf-8")
        open_items = open_fact_items(text)
        naive_items = naive_fact_items(text)
        row = rows[path.resolve()]
        assert row["待确认"] == str(len(open_items)), (
            f"{path.name} 的待确认数对不上：索引写 {row['待确认']}，"
            f"记录里真没销掉的有 {len(open_items)} 条")
        assert row["不阻塞"] == str(len(naive_items)), (
            f"{path.name} 的「不适用」数对不上：索引写 {row['不阻塞']}，"
            f"记录里有 {len(naive_items)} 条")
        if info["status"] == "已合入":
            assert not open_items, (
                f"{path.name} 标了已合入，却还有 {len(open_items)} 条没销掉")


def test_contract_file_passes_in_a_ci_like_git_environment():
    """集成：把整套契约检查放进「像 CI runner 一样」的 git 环境里再跑一遍。

    CI runner 没有开发者的全局 git 配置，core.quotePath 取默认 true；
    开发机常常关掉它。这条测试把两者拉平：契约检查在 CI 样的环境里
    也必须全绿。否则就是「本地绿、CI 红」，而 CI 红了没人看得到原因。
    """
    if os.environ.get(CHILD_MARKER) == "1":
        pytest.skip("子进程里不再递归跑这份契约")
    env = os.environ.copy()
    env[CHILD_MARKER] = "1"
    env.update(CI_LIKE_GIT_ENV)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_review_records.py", "-q"],
        cwd=REPO_ROOT, capture_output=True, encoding="utf-8", errors="replace",
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
