"""守住 README 里的三样会漂移的东西。

README 是这套工具的门面，但它写的是**手抄的清单**和**手写的数字**：
用例条数、CLI 子命令、CLI 选项。

- **条数**每加一条用例就旧一格。而且「多少条通过」根本不是稳定口径：
  母稿 ``source/_posts`` 不入库，两条语料级用例在没有母稿的检出里是
  ``skipped``（321 passed），有母稿时才是 323 passed。
  README 里曾一直写着 321——那个数在干净检出里没错，但它同时**漏掉了
  那两条用例存在**这件事，而它们恰恰是最贵的那两条。
  所以比的是「收集到多少条」，那个数与母稿在不在无关。
- **子命令与选项**每加一个就少一格。加进代码时**不会让任何既有用例变红**，
  只有这份清单能发现。

子命令和选项都**从 CLI 的解析器里读**，不抄一份到测试里——
抄一份的话，测试会和 README 一起过期。
"""

import re
import subprocess
import sys

from toutiao.cli import build_parser

README_RELATIVE_PATH = ("toutiao", "README.md")

TEST_COUNT_PATTERN = re.compile(r"(\d+)\s*条用例")
COLLECTED_PATTERN = re.compile(r"(\d+)\s+tests?\s+collected")

# ``--help`` 是 argparse 自带的，README 不写它也不会有人踩空。
IMPLICIT_OPTIONS = frozenset({"--help"})


def _readme(repo_root):
    return repo_root.joinpath(*README_RELATIVE_PATH).read_text(encoding="utf-8")


def _subparsers(parser):
    """解析器里的子命令表：``{名字: 子解析器}``。"""
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict) and choices:
            return choices
    return {}


def _option_names(parser):
    """CLI 接受的全部选项名（不含 argparse 自带的 ``--help``）。

    顶层解析器和每个子命令都要看：公共选项挂在父解析器上，
    子命令自己的选项（比如 ``convert`` 的 ``slug``）只挂在子解析器上。
    """
    names = set()
    for sub in [parser] + list(_subparsers(parser).values()):
        for action in sub._actions:
            for option in action.option_strings:
                if option.startswith("--") and option not in IMPLICIT_OPTIONS:
                    names.add(option)
    return sorted(names)


def _collected_count(repo_root):
    """实际收集到的用例条数。

    跑的是 ``--collect-only``：它不执行任何用例，也不碰语料，
    所以这个数与母稿在不在检出里无关——这正是它能当基准的原因。
    """
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest", "toutiao/tests",
            "--collect-only", "-q", "-p", "no:cacheprovider",
        ],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    match = COLLECTED_PATTERN.search(result.stdout)
    assert match, (
        "pytest --collect-only 没有给出收集条数，退出码 {}：\n{}".format(
            result.returncode, result.stdout[-2000:]
        )
    )
    return int(match.group(1))


def test_readme_states_the_real_number_of_tests(repo_root):
    """README 说的用例条数必须等于实际收集到的条数。

    加了用例要回来改这个数——这是这个用例存在的全部理由。
    """
    text = _readme(repo_root)

    matches = TEST_COUNT_PATTERN.findall(text)
    assert len(matches) == 1, (
        "README 里应当只有一处用例条数，实际找到 {} 处".format(len(matches))
    )

    stated = int(matches[0])
    collected = _collected_count(repo_root)
    assert stated == collected, (
        "README 写 {} 条用例，实际收集到 {} 条 —— 加了用例要回来改这个数".format(
            stated, collected
        )
    )


def test_readme_documents_every_subcommand(repo_root):
    """CLI 的每个子命令都要在 README 里出现。

    读者照 README 敲命令；命令名在代码里加了而 README 没跟上，
    文档就开始骗人。
    """
    text = _readme(repo_root)

    subcommands = sorted(_subparsers(build_parser()))
    assert subcommands, "没能从 CLI 解析器里读出子命令"

    missing = [name for name in subcommands if name not in text]
    assert not missing, "README 里没有这些子命令：{}".format("、".join(missing))


def test_readme_documents_every_option(repo_root):
    """CLI 的每个选项都要在 README 里出现。

    选项比子命令更容易漏：它们散在 ``_add_common_options`` 里，
    加一个 ``--notify-xxx`` 不会让任何既有用例变红——只有这份清单能发现。
    """
    text = _readme(repo_root)

    options = _option_names(build_parser())
    assert options, "没能从 CLI 解析器里读出选项"

    missing = [name for name in options if name not in text]
    assert not missing, "README 里没有这些选项：{}".format("、".join(missing))
