"""守住「toutiao 的文档不绑定某台机器的绝对路径」。

计划文档是给执行者照着敲的说明书。里面原来 35 处写死
``cd /Users/growduduan/code/blog`` —— 那是**主检出目录**，
而实际干活在 worktree 里。照着敲就会在错误的目录跑测试，
而「在错误的目录跑 pytest」往往不是报错，是**静悄悄地什么都没测到**。

所以统一改成 ``cd "$(git rev-parse --show-toplevel)"``：
不管从哪个检出、哪个分支跑，都落在仓库根。

这个用例防的是「有人为了让某条命令好跑，又把绝对路径写回去」。
"""

import re

#: 会被检查的文档。路径相对仓库根。
DOCS = (
    ("toutiao", "docs", "11-实施计划.md"),
    ("toutiao", "docs", "00-设计.md"),
    ("toutiao", "README.md"),
)

#: 某台机器上的仓库绝对路径。
HARD_CODED_ROOT = "/Users/growduduan/code/blog"

#: 正确的写法：从当前检出推导仓库根。
DERIVED_ROOT = 'cd "$(git rev-parse --show-toplevel)"'

#: 合法的 cd 目标前缀。``/tmp/`` 是通用临时目录（干净检出验证自己建的那个），
#: 不属于「某台机器的固定路径」。
ALLOWED_PREFIXES = (DERIVED_ROOT, "cd /tmp/")

#: 计划文档里所有 ``cd `` 开头的命令行。
CD_COMMAND = re.compile(r"^cd .*$", re.MULTILINE)


def test_no_toutiao_doc_hard_codes_the_repo_path(repo_root):
    """toutiao 的文档里不得出现某台机器的绝对路径。"""
    for parts in DOCS:
        text = repo_root.joinpath(*parts).read_text(encoding="utf-8")
        assert HARD_CODED_ROOT not in text, (
            "{} 里又写死了绝对路径 {}——"
            "执行者照着敲会落到错误的目录，测试会静悄悄地什么都没测到。"
            .format("/".join(parts), HARD_CODED_ROOT)
        )


def test_plan_doc_commands_derive_the_repo_root(repo_root):
    """计划文档里每条 ``cd`` 命令都必须不依赖「当前目录恰好是仓库根」。

    两种合法的落点：从当前检出推导仓库根（可带子目录），
    或者自己刚建出来的临时目录（``/tmp/``）。
    """
    text = repo_root.joinpath("toutiao", "docs", "11-实施计划.md").read_text(encoding="utf-8")

    commands = CD_COMMAND.findall(text)
    assert commands, "计划文档里一条 cd 命令都没找到——解析方式失效了"

    for command in commands:
        assert command.startswith(ALLOWED_PREFIXES), (
            "计划文档里有 cd 命令既不推导仓库根、也不是临时目录：{}。"
            "它隐含假设「当前目录恰好是仓库根」，照着敲可能落到别的目录，"
            "而 pytest 在错误的目录里常常不是报错，是静悄悄地什么都没测到。"
            "应该写成 `{}` 或 `cd /tmp/...`".format(command, DERIVED_ROOT)
        )
