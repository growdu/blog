"""红线守卫的红-绿验证。

每一条守卫测试都必须是**真的会红**的：把违反口径的内容注入进去，
对应的测试必须失败；还原之后必须重新变绿。

一条永远不会红的测试等于没有测试——所以这里逐条注入、逐条还原。

用法：
    python3 scripts/redgreen_check.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # aiv/
PIPELINE = ROOT / "pipeline"

# 每条：名字 / 目标文件（相对 aiv/）/ 注入与还原用的一对文本 / 期望失败的测试
CASES: list[dict] = [
    {
        "name": "EP03 画面/口播出现 PostgreSQL 18",
        "file": "字幕-WAL顺序.md",
        "old": "WAL 是操作级记录，一行只写一个动作。",
        "new": "WAL 是操作级记录，PostgreSQL 18 一行只写一个动作。",
        "test": "tests/test_episode_boundaries.py::test_ep03_does_not_claim_postgresql_18",
    },
    {
        "name": "EP03 选题库把文档举例说成实测",
        "file": "选题库.md",
        "old": "**示意例子，要说明是举例**",
        "new": "**真实实测值**",
        "test": "tests/test_episode_boundaries.py::test_ep03_marks_the_lsn_example_as_an_illustration",
    },
    {
        "name": "EP04 去掉「我自己的设计方案」",
        "file": "字幕-并行apply.md",
        "old": "边界很清楚：这是我自己的设计方案，还没合进上游主线。",
        "new": "边界很清楚：这是上游已经有的能力。",
        "test": "tests/test_episode_boundaries.py::test_ep04_says_it_is_my_own_design",
    },
    {
        "name": "EP04 画面放上内部代号 TWPA",
        "file": "contracts/parallel-apply.json",
        "old": '"title": "按图的顺序分发，最后统一提交"',
        "new": '"title": "TWPA 按图的顺序分发，最后统一提交"',
        "test": "tests/test_episode_boundaries.py::test_ep04_keeps_internal_codenames_off_screen",
    },
    {
        "name": "EP05 去掉「社区还在讨论」",
        "file": "字幕-结构化DDL.md",
        "old": "边界要说清：社区还在讨论，还没有合入主线的版本。",
        "new": "边界要说清：这是 PostgreSQL 18 已经具备的能力。",
        "test": "tests/test_episode_boundaries.py::test_ep05_says_it_is_a_community_discussion",
    },
    {
        "name": "EP05 画面放上拟议的 WAL 记录名",
        "file": "contracts/structured-ddl.json",
        "old": '"mid_label": "按语义执行"',
        "new": '"mid_label": "按语义执行 xl_logical_ddl_message"',
        "test": "tests/test_episode_boundaries.py::test_ep05_keeps_proposed_record_names_off_screen",
    },
    {
        "name": "EP03 口播多加一句，契约没跟着改",
        "file": "字幕-WAL顺序.md",
        "old": "上游靠事务号攒成组，CSN 那一套是 openGauss 额外加的。",
        "new": "上游靠事务号攒成组，CSN 那一套是 openGauss 额外加的。\n这一句是后来加的。",
        "test": "tests/test_episode_boundaries.py::test_script_and_contract_agree_on_the_sentence_count",
    },
    {
        "name": "EP04 分发顺序颠倒（T2 排在 T1 前面）",
        "file": "contracts/parallel-apply.json",
        "old": '"dispatch": [["T1", 0], ["T3", 1], ["T2", 0], ["T4", 1]]',
        "new": '"dispatch": [["T2", 0], ["T1", 0], ["T3", 1], ["T4", 1]]',
        "test": "tests/test_scenes.py::test_ep04_scheduler_respects_the_dependency_edges",
    },
    {
        "name": "EP04 提交顺序违反依赖（T2 先于 T1 提交）",
        "file": "contracts/parallel-apply.json",
        "old": '"commit_order": ["T1", "T3", "T2", "T4"]',
        "new": '"commit_order": ["T2", "T1", "T3", "T4"]',
        "test": "tests/test_scenes.py::test_ep04_scheduler_respects_the_dependency_edges",
    },
    {
        "name": "EP03 s02 与 s03 画的不是同一组 WAL 记录",
        "file": "contracts/wal-interleave.json",
        "old": '"xid_prefix": "xid",\n        "records": [\n          ["100", "T1", "INSERT"],\n          ["110", "T2", "INSERT"],\n          ["120", "T1", "UPDATE"],\n          ["130", "T3", "DELETE"],\n          ["140", "T2", "UPDATE"],\n          ["150", "T1", "COMMIT"]\n        ],',
        "new": '"xid_prefix": "xid",\n        "records": [\n          ["100", "T1", "INSERT"],\n          ["110", "T2", "INSERT"],\n          ["120", "T1", "UPDATE"],\n          ["130", "T3", "DELETE"],\n          ["140", "T2", "UPDATE"],\n          ["151", "T1", "COMMIT"]\n        ],',
        "test": "tests/test_scenes.py::test_ep03_two_scenes_tell_the_same_story",
    },
    {
        "name": "EP06 去掉「上游的公开机制」",
        "file": "字幕-行锁.md",
        "old": "这是上游的公开机制，别把它当成谁家的私有扩展。",
        "new": "这是每家都能自己加的能力，别把它当成谁家的私有扩展。",
        "test": "tests/test_episode_boundaries.py::test_ep06_says_it_is_an_upstream_mechanism",
    },
    {
        "name": "EP06 提到 PostgreSQL 18 却不说那指的是源码版本",
        "file": "字幕-行锁.md",
        "old": "PostgreSQL 18 源码里，锁藏在元组的 t_infomask 和 xmax 里。",
        "new": "PostgreSQL 18 里，锁藏在元组的 t_infomask 和 xmax 里。",
        "test": "tests/test_episode_boundaries.py::test_ep06_marks_postgresql_18_as_the_source_version",
    },
    {
        "name": "EP06 说行锁是 PostgreSQL 18 新增的",
        "file": "字幕-行锁.md",
        "old": "PostgreSQL 在 MVCC 之上加了行锁，一共 4 种模式。",
        "new": "PostgreSQL 18 新增的行锁，一共 4 种模式。",
        "test": "tests/test_episode_boundaries.py::test_ep06_does_not_claim_row_lock_is_new_in_18",
    },
    {
        "name": "EP06 选题库把源码里的位定义说成实测",
        "file": "选题库.md",
        "old": "**源码里的位定义**，不是实测数据",
        "new": "**本机实测值**",
        "test": "tests/test_episode_boundaries.py::test_ep06_marks_the_bit_values_as_source_definitions",
    },
    {
        "name": "EP06 矩阵抄错一格（不再对称）",
        "file": "contracts/row-lock.json",
        "old": "[true, true, true, false],",
        "new": "[true, true, false, false],",
        "test": "tests/test_row_lock_matrix.py::test_the_matrix_is_symmetric",
    },
    {
        "name": "EP06 矩阵把最弱那一行改错",
        "file": "contracts/row-lock.json",
        "old": "[true, true, true, false],",
        "new": "[false, true, true, false],",
        "test": "tests/test_row_lock_matrix.py::test_the_weakest_mode_only_conflicts_with_the_strongest",
    },
    {
        "name": "EP06 挪用 EP01 的压测数字",
        "file": "字幕-行锁.md",
        "old": "PostgreSQL 在 MVCC 之上加了行锁，一共 4 种模式。",
        "new": "PostgreSQL 在 MVCC 之上加了行锁，性能提升 2 到 5 倍。",
        "test": "tests/test_episode_boundaries.py::test_new_episodes_do_not_reuse_the_ep01_benchmark[ep06]",
    },
    {
        "name": "把「行锁」从读音替换表里删掉",
        "file": "voice/scripts/pronunciation.py",
        "old": '    "行锁": "航锁",   # 行锁 → 航锁：航 是无歧义的 háng，声母 [x]、韵母 [ɑŋ]、阳平，与目标读音一致\n',
        "new": "",
        "test": "tests/test_voice_pronunciation.py::test_the_misread_word_is_mapped_to_a_substitute",
    },
    {
        "name": "把「一行」的替换改成不分词（会误伤「每一行」）",
        "file": "voice/scripts/pronunciation.py",
        "old": '    if wrong == "一行":\n'
               '        pattern = re.compile(f"(?<![{_COMPOUND_PREFIX}]){re.escape(wrong)}")\n'
               '        return pattern.sub(right, text)\n'
               '    return text.replace(wrong, right)\n',
        "new": '    return text.replace(wrong, right)\n',
        "test": "tests/test_voice_pronunciation.py::test_the_compound_words_are_left_alone",
    },
    {
        "name": "口播稿里塞进一个没实测过读音的「行」字词",
        "file": "字幕-行锁.md",
        "old": "PostgreSQL 在 MVCC 之上加了行锁，一共 4 种模式。",
        "new": "PostgreSQL 在 MVCC 之上加了行锁，行首也有锁，一共 4 种模式。",
        "test": "tests/test_voice_pronunciation.py::test_every_hang_word_in_every_script_is_measured",
    },
]


def _run(test: str) -> tuple[bool, str]:
    """跑一条测试，返回（是否通过，输出尾部）。"""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", test, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=PIPELINE, capture_output=True, text=True,
    )
    return proc.returncode == 0, (proc.stdout or proc.stderr)[-1200:]


def _inject(case: dict) -> Path:
    """注入违规内容，返回被改动的文件路径。"""
    path = ROOT / case["file"]
    text = path.read_text(encoding="utf-8")
    assert case["old"] in text, f"注入目标没找到：{case['name']}（{case['file']}）"
    path.write_text(text.replace(case["old"], case["new"], 1), encoding="utf-8")
    return path


def main() -> int:
    failures: list[str] = []

    with tempfile.TemporaryDirectory(prefix="redgreen-bk-") as tmp:
        backup = Path(tmp)
        for index, case in enumerate(CASES, 1):
            path = ROOT / case["file"]
            bak = backup / f"{index:02d}_{path.name}"
            shutil.copy(path, bak)

            try:
                _inject(case)
                passed, output = _run(case["test"])
                if passed:
                    failures.append(case["name"])
                    print(f"[FAIL] {index:02d} {case['name']} —— 注入后测试仍然通过（守卫没抓住）")
                else:
                    print(f"[ ok ] {index:02d} {case['name']}")
            finally:
                shutil.copy(bak, path)

            # 还原之后必须重新变绿
            passed, output = _run(case["test"])
            if not passed:
                failures.append(f"{case['name']}（还原后仍然红）")
                print(f"[FAIL] {index:02d} {case['name']} —— 还原后测试仍然失败\n{output}")
            else:
                print(f"[ ok ] {index:02d} {case['name']} —— 还原后恢复绿色")

    print()
    if failures:
        print(f"红-绿验证失败：{len(failures)} 条")
        for item in failures:
            print(f"  - {item}")
        return 1
    print(f"红-绿验证通过：{len(CASES)} 条守卫全部既能变红、也能还原变绿")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
