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
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_ROOT = REPO_ROOT / "review"
DOCS_ROOT = REPO_ROOT / "docs"

# 首轮审校范围：数据库内核四支柱。
REVIEWED_PILLARS = ("database", "db", "pgsql", "cluster")

STATES = ("待审", "审校中", "建议中", "已确认", "已合入")

# README 模板里的小节标题，一个都不能少。
TEMPLATE_SECTIONS = (
    "## 优先修改",
    "## 事实待核",
    "## 可补的技术证据或产物",
    "## 已确认的改动",
)

INDEX_ROW_RE = re.compile(r"^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|(.*)\|\s*$")


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


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT,
                            capture_output=True, text=True)
    return result.stdout


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
    for path in record_files():
        info = parse_record(path)
        if info["status"] != "已合入":
            continue
        slug = path.stem
        shas = merged_commit_for(slug)
        assert shas, f"{slug} 标了已合入，但没有 docs(review): {slug} 提交"
        touched = False
        for sha in shas:
            names = git("show", "--name-only", "--pretty=format:", sha)
            if info["source"] in names:
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
        section = text.split("## 事实待核", 1)[1].split("##", 1)[0]
        open_items = [line for line in section.split("\n")
                      if line.strip().startswith("- ")
                      and not line.strip().startswith("- [x]")
                      and not line.strip().startswith("- [不适用]")]
        assert not open_items, f"{path.name} 仍留着未核实的待核事实: {open_items}"


def test_docs_tree_has_no_review_leakage():
    """docs/ 会被发布成站点文章，审校记录绝不能漏进去。"""
    offenders = [p for p in DOCS_ROOT.rglob("*")
                 if p.is_dir() and p.name in ("review", "reviews")]
    assert not offenders, f"docs/ 下出现了审校目录: {offenders}"
    records = [p for p in DOCS_ROOT.rglob("*.md")
               if p.name.startswith("审校") or "审校记录" in p.name]
    assert not records, f"docs/ 下出现了审校记录: {records}"
