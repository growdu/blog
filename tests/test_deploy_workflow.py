"""Contract tests for the deployment workflow (``.github/workflows/hexo.yml``).

Why this file exists
--------------------
On 2026-11-13 the site froze.  ``growdu.cn`` stopped at a commit from 12:02
and ``growdu.github.io/blog`` at 12:26, and stayed there for the better part
of an hour while dozens of commits were pushed.  Two independent causes were
involved, and **both are silent** -- the workflow file stays valid, the
test suite stays green, the site just quietly stops moving:

1. **A job that never returns.**  ``deploy-server``'s ssh had no
   ``BatchMode``, so a rejected key turned into "waiting for a password
   prompt" instead of an error.  A workflow run only finishes when *every*
   job finishes, and the concurrency group is only released when the run
   finishes -- so one stuck job parks every later push in ``pending`` and
   the whole queue stops draining.  The cure is a timeout on every job, so
   the stuck job dies and the queue resumes.

2. **Cancelling the in-flight run.**  ``cancel-in-progress: true`` looks
   like "latest push wins", but during a burst of pushes it kills every run
   before ``build`` can finish, so nothing is ever published.  GitHub's
   concurrency already collapses the *pending* queue down to the newest
   run, so ``false`` gives "latest push wins" without the starvation.

Neither property is visible when you read the YAML, so both are pinned here.

The workflow is parsed textually rather than with PyYAML: the suite then
keeps running with nothing but pytest installed.  The parsing helpers below
are therefore part of the contract -- every scanning test asserts the
*scope* of its scan (how many jobs / how many ssh calls it found) so that a
parser that quietly stops matching cannot turn these checks into green
no-ops.

Nothing here talks to the network: these are contract tests over a file.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github/workflows/hexo.yml"

# A job key sits at two-space indentation under ``jobs:``.
_JOB_KEY = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
# ``timeout-minutes`` sits at four-space indentation, right under the job key.
_TIMEOUT = re.compile(r"^    timeout-minutes:\s*([0-9]+)\s*$", re.M)
_NEEDS = re.compile(r"^    needs:\s*(.*)$", re.M)
# ``ssh -p PORT ...``.  Deliberately does not match ``ssh-keyscan -T 10 -p``,
# which is a different program (and does not authenticate).
_SSH_CALL = re.compile(r"ssh -p ")

REQUIRED_JOBS = {"build", "deploy-server", "build-github-pages", "deploy-github-pages"}


def _workflow_text() -> str:
    assert WORKFLOW.is_file(), f"找不到部署工作流：{WORKFLOW}"
    return WORKFLOW.read_text(encoding="utf-8")


def _jobs(text: str) -> dict[str, str]:
    """Split the ``jobs:`` section into one text block per job."""
    lines = text.splitlines()
    try:
        start = lines.index("jobs:")
    except ValueError:
        return {}
    blocks: dict[str, str] = {}
    name: str | None = None
    buf: list[str] = []
    for line in lines[start + 1:]:
        match = _JOB_KEY.match(line)
        if match:
            if name is not None:
                blocks[name] = "\n".join(buf)
            name = match.group(1)
            buf = []
            continue
        if name is None:
            continue
        if line.strip() and not line.startswith("  ") and not line.startswith("#"):
            break  # left the jobs: section
        buf.append(line)
    if name is not None:
        blocks[name] = "\n".join(buf)
    return blocks


def _needs_of(block: str) -> list[str]:
    match = _NEEDS.search(block)
    if not match:
        return []
    raw = match.group(1).strip()
    if not raw:
        return []
    if raw.startswith("["):
        return [d.strip().strip("'\"") for d in raw.strip("[]").split(",") if d.strip()]
    return [d.strip() for d in raw.split(",") if d.strip()]


def test_workflow_shape_is_recognised() -> None:
    """Scan-scope self-check: the parser must find the whole job set."""
    jobs = _jobs(_workflow_text())
    assert len(jobs) >= len(REQUIRED_JOBS), (
        f"只认出 {len(jobs)} 个 job（期望至少 {len(REQUIRED_JOBS)}），解析多半坏了"
    )
    assert REQUIRED_JOBS <= set(jobs), (
        f"少了这些 job：{sorted(REQUIRED_JOBS - set(jobs))}；"
        "两个发布出口（自建服务器 + GitHub Pages）都要有人在"
    )


def test_every_job_is_bounded_by_a_timeout() -> None:
    """A job without a timeout can hold the concurrency group forever."""
    jobs = _jobs(_workflow_text())
    assert len(jobs) >= len(REQUIRED_JOBS)
    missing = sorted(name for name, block in jobs.items() if not _TIMEOUT.search(block))
    assert not missing, (
        f"这些 job 没有 timeout-minutes：{missing}。"
        "job 挂死不退出 → run 不结束 → 并发组不释放 → 后面所有推送全卡在 pending"
    )
    for name, block in jobs.items():
        minutes = int(_TIMEOUT.search(block).group(1))
        assert 1 <= minutes <= 60, f"job {name} 的 timeout-minutes={minutes} 不合理"


def test_concurrency_keeps_the_running_run_and_collapses_the_queue() -> None:
    """``false`` is what makes this converge -- see the module docstring."""
    text = _workflow_text()
    block = re.search(r"^concurrency:\n((?:[ \t]+.*\n)+)", text, re.M)
    assert block, "找不到 concurrency 段"
    body = block.group(1)
    # 设置项固定在两空格缩进上。注释行开头是 '#'，匹配不上——
    # 这样「注释里写了 cancel-in-progress: false」不会被误当成真设置。
    assert re.search(r"^  group:\s*\S+\s*$", body, re.M), "concurrency 段里没有 group"
    assert re.search(r"^  cancel-in-progress:\s*false\s*$", body, re.M), (
        "cancel-in-progress 必须保持 false：GitHub 本来就会把 pending 队列收敛成最新一个，"
        "设成 true 反而会在推送密集时把每次 run 在 build 完之前砍掉，站点永远停在旧版本"
    )


def test_ssh_calls_are_non_interactive() -> None:
    """ssh must never wait for input: waiting == job hangs == queue stalls."""
    lines = [line for line in _workflow_text().splitlines() if _SSH_CALL.search(line)]
    assert len(lines) >= 3, (
        f"只认出 {len(lines)} 处 ssh 调用（期望至少 3：rsync 的 -e、"
        "切 symlink、清理旧 release），扫描多半没生效"
    )
    for line in lines:
        stripped = line.strip()
        assert "BatchMode=yes" in line, f"这处 ssh 会去等密码提示：{stripped}"
        assert "ConnectTimeout=" in line, f"这处 ssh 没有连接超时：{stripped}"


def test_known_hosts_is_verified_before_use() -> None:
    """An empty known_hosts turns ssh into a "trust this host?" prompt."""
    text = _workflow_text()
    assert "ssh-keyscan" in text, "Setup SSH 步骤不写 known_hosts"
    assert re.search(r"ssh-keyscan\s+-T\s+\d+", text), "ssh-keyscan 自己也要有超时"
    assert "! -s ~/.ssh/known_hosts" in text, (
        "known_hosts 为空时 ssh 会卡在「是否信任这个主机」的问句上，"
        "必须在连接之前判死，并把最可能的原因写进报错里"
    )


def test_job_graph_has_no_dangling_edges_and_no_cycles() -> None:
    """Integration-level: ``needs`` must point at real jobs, and the graph must be acyclic."""
    jobs = _jobs(_workflow_text())
    assert len(jobs) >= len(REQUIRED_JOBS)
    graph = {name: _needs_of(block) for name, block in jobs.items()}
    for name, deps in graph.items():
        for dep in deps:
            assert dep in jobs, f"job {name} 依赖了不存在的 job {dep}"

    state: dict[str, int] = {}

    def visit(node: str, path: list[str]) -> None:
        assert state.get(node, 0) != 1, f"job 依赖成环了：{' -> '.join(path + [node])}"
        if state.get(node) == 2:
            return
        state[node] = 1
        for dep in graph[node]:
            visit(dep, path + [node])
        state[node] = 2

    for name in graph:
        visit(name, [])


def test_workflow_triggers_on_push_to_master() -> None:
    text = _workflow_text()
    assert re.search(r"^on:", text, re.M), "工作流没有 on: 触发器"
    assert re.search(r"^\s*push:", text, re.M), "工作流不由 push 触发"
    assert re.search(r"^\s*-\s*master\s*$", text, re.M), "push 触发器里没有 master 分支"
