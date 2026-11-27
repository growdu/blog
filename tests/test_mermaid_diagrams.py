"""mermaid 图的守卫：别让渲染不出来的图悄悄留在站点上。

**背景**
------
mermaid 解析失败时，``themes/matery/layout/layout.ejs`` 会把那张图换成
一行「⚠ 此图语法错误，未能渲染」。从页面截图上看，那只是一块提示框，
不点开源码根本不知道原来画的是什么——于是「图坏了」这件事在站点上
一直是隐形的。

2026-11-16 实测：全站 **1304 张**唯一的 mermaid 图里，
**110 张（8.4%）渲染不出来**。

**mermaid 的一个词法坑**
----------------------
引号里的边标签以 ``...`` 结尾、紧接着一个 ``]`` 时，mermaid 会把它拆错：

===========================  ==========
写法                          结果
===========================  ==========
``A -->|"a..."| B["x"]``     ✅
``A -->|"a..."]| B["x"]``    ❌
``A -->|"a..."] B["x"]``     ❌
===========================  ==========

报错长这样::

    Parse error on line 8:
    ...er 的 pg_wal/0000..."]    A -->|"feedbac
    -----------------------^
    Expecting 'PIPE', 'TAGEND', 'UNICODE_TEXT', 'TEXT', 'TAGSTART', got 'SQE'

EP01 的首图（``postgresql-logical-replication-end-to-end-flow`` 的
「本期机制图」）就踩在这个坑上——它是 6 期播客的门面图，
渲染不出来就等于那一期的封面是空的。

**契约**
--------
1. ``docs/`` 里的 mermaid 图不许出现 ``-->|"..."]`` 这种写法
   （结尾的省略号后面紧跟 ``]``）。这条是纯文本规则，不需要浏览器。
2. ``tools/check-mermaid.py`` 必须用 ``mermaid.render()`` 检查，
   不能用 ``parse()``——``parse`` 只查语法，查不出布局期的错误
   （比如 gantt 的 ``Invalid date``），用它会漏掉 11 张。
3. 工具收集 mermaid 源码时要去重、并且把 HTML 实体还原
   （产物里 ``-->`` 被转义成 ``--&gt;``、``<br/>`` 被转义成
   ``&lt;br&#x2F;&gt;``，不还原的话量的是转义后的文本）。

放在根级 ``tests/``，随 ``site-guard.yml`` 进 CI（不构建产物）。
全站 110 张坏图的清单用 ``python3 tools/check-mermaid.py --list`` 现量，
不在这个测试里钉死——那是内容清理的活，不是契约。
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
TOOL = REPO / "tools" / "check-mermaid.py"

MERMAID_BLOCK = re.compile(r"```mermaid\n(.*?)```", re.S)

# 边标签以省略号结尾、紧接着方括号 —— mermaid 会在这里拆错。
# 只认**边标签**这种位置：节点标签 ``WAL["pg_wal/0000..."]`` 是合法的，
# 站点里有 27 张图是这么写的，它们都渲染正常。
BROKEN_EDGE_LABEL = re.compile(r'-->\|"[^"]*\.\.\."\s*\]')


def _load_tool():
    """按路径加载 ``tools/check-mermaid.py``。

    ``tools/`` 不是包，所以走文件加载。模块顶层没有副作用
    （Chrome 是用到才起的），import 不会拉起浏览器。
    """
    spec = importlib.util.spec_from_file_location("check_mermaid", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_mermaid = _load_tool()


def _mermaid_blocks() -> list[tuple[Path, str]]:
    out = []
    for path in sorted(DOCS.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for m in MERMAID_BLOCK.finditer(text):
            out.append((path, m.group(1)))
    return out


# --- 1. 契约：边标签不许以 "...\" ] 收尾 ------------------------------------


def test_no_mermaid_edge_label_ends_with_an_ellipsis_before_a_bracket():
    """``-->|"..."]`` 这种写法 mermaid 解析不出来。

    引号里的边标签以省略号结尾、紧接着 ``]`` 时，mermaid 的词法会拆错
    （报 ``got 'SQE'``）。EP01 的首图就栽在这里——它一坏，
    那一期的「本期机制图」就成了一行提示框。
    """
    offenders = []
    for path, block in _mermaid_blocks():
        for line in block.split("\n"):
            if BROKEN_EDGE_LABEL.search(line):
                offenders.append("{}: {}".format(path.relative_to(REPO), line.strip()))
    assert not offenders, (
        "mermaid 边标签以省略号结尾又紧跟方括号，mermaid 解析不了：\n"
        + "\n".join(offenders)
        + "\n把方括号去掉、补上结尾的 |，或者把省略号挪到标签中间。"
    )


def test_the_ep01_lead_diagram_is_intact():
    """EP01 那张「本期机制图」本身要在，且不能是坏写法。

    它是 ``postgresql-logical-replication-end-to-end-flow`` 的第一张图，
    被 ``post-detail.ejs`` 搬进期号区块当门面图。
    """
    path = (DOCS / "source-tracks" / "postgresql" / "L7-logical-replication"
           / "postgresql-logical-replication-end-to-end-flow" / "index.md")
    assert path.is_file(), "找不到 {}".format(path)
    text = path.read_text(encoding="utf-8")
    blocks = [m.group(1) for m in MERMAID_BLOCK.finditer(text)]
    assert blocks, "这篇文章里没有 mermaid 图了——首图是 EP01 的门面图"
    first = blocks[0]
    assert "flowchart LR" in first, "首图不是那张链路图"
    assert not BROKEN_EDGE_LABEL.search(first), "首图还是坏写法"


def test_the_docs_actually_have_mermaid_diagrams():
    """这个测试得真的有事可查。

    免得哪天正则或目录写错，测试一路绿着其实什么都没查。
    """
    blocks = _mermaid_blocks()
    assert len(blocks) > 1000, "只找到 {} 张 mermaid 图，正则或目录不对".format(len(blocks))


# --- 2. 契约：工具用的是 render，不是 parse --------------------------------


def test_the_tool_checks_with_render_not_parse():
    """``mermaid.parse()`` 只查语法，查不出布局期的错误。

    布局期的错误在站点的图里是真实存在的（gantt 的 ``Invalid date``）：
    用 parse 量出来是 99 张坏图，用 render 量出来是 110 张。
    工具用 parse 会漏掉 11 张，所以这里钉住用 render。
    """
    source = TOOL.read_text(encoding="utf-8")
    assert "mermaid.render(" in source, "工具没有用 mermaid.render() 检查"
    assert "mermaid.parse(" not in source, (
        "工具用了 mermaid.parse()——它查不出布局期的错误，会漏掉 11 张坏图"
    )


# --- 3. 契约：工具收集源码的方式 --------------------------------------------


def test_collect_sources_dedups_and_unescapes(tmp_path):
    """收集源码时要**去重**，并且把 HTML 实体还原。

    产物里 mermaid 的源码被转义过（``-->`` 变成 ``--&gt;``、
    ``<br/>`` 变成 ``&lt;br&#x2F;&gt;``）。不还原的话，
    量的是转义后的文本，跟浏览器真正拿去渲染的不是一回事。
    """
    (tmp_path / "a.html").write_text(
        '<div class="mermaid">flowchart LR\n    A --&gt; B</div>',
        encoding="utf-8",
    )
    (tmp_path / "b.html").write_text(
        '<div class="mermaid">flowchart LR\n    A --&gt; B</div>',
        encoding="utf-8",
    )
    (tmp_path / "c.html").write_text(
        '<div class="mermaid">flowchart TB\n    C["x"]</div>',
        encoding="utf-8",
    )

    sources = check_mermaid.collect_sources(str(tmp_path))

    assert len(sources) == 2, "同样的图出现在两个页面里，应该只算一张：{}".format(
        list(sources))
    assert "flowchart LR\n    A --> B" in sources, (
        "实体没还原：{}".format(list(sources)))
    assert len(sources["flowchart LR\n    A --> B"]) == 2, "两个页面都出现过它"


# --- 4. 契约：量不出来的时候必须大声失败 ------------------------------------


class _FakeChrome:
    """一个只会说「mermaid 没加载」的假 Chrome。

    它照着真实 JS 的语义回话：**``typeof x`` 回的是字符串**。
    这正是那个 bug 的要害——``"undefined"`` 在 Python 里是真值。
    """

    def __init__(self, ready: bool = False):
        self.ready = ready

    def cmd(self, *_args, **_kwargs):
        return {}

    def eval(self, expr):
        if expr == "typeof window.mermaid":
            return "undefined"          # JS 的真实返回：字符串，不是布尔
        if "window.mermaid" in expr:
            return self.ready           # 修好后的那个布尔判断
        if "__r" in expr and "done" in expr:
            return False                 # 渲染循环没跑完
        if "JSON.stringify" in expr:
            return json.dumps({"done": False, "ok": 0, "bad": [], "settled": 0})
        return None


def test_the_tool_refuses_to_report_a_clean_bill_when_mermaid_never_loads(monkeypatch):
    """mermaid 没加载时，工具必须**报错退出**，不能报「成功 0　失败 0」。

    2026-11-27 实测踩过：产物里缺 ``mermaid.min.js``（漏跑
    ``tools/copy-vendor.py``），页面里的 mermaid 加载失败。
    而工具的等待逻辑写的是 ``if chrome.eval("typeof window.mermaid"):`` ——
    ``eval`` 回的是**字符串** ``"undefined"`` 也是真值，于是等待第一轮就
    「通过」，工具拿着一份没有 mermaid 的页面继续跑，渲染全部失败，
    最后报出「渲染成功 0　渲染失败 0」。

    0 成功 0 失败和「一张都没测」在报告里长得一模一样 —— 那是一份
    **假的全清**，比坏图本身更危险。
    """
    monkeypatch.setattr(check_mermaid.time, "sleep", lambda *_a, **_k: None)

    with pytest.raises(SystemExit) as excinfo:
        check_mermaid.render_all(
            _FakeChrome(ready=False),
            ["flowchart LR\n    A --> B"],
            "http://127.0.0.1:1/boot.html",
            timeout_s=0,
        )
    # 必须是「mermaid 没加载」这一条，不许退化成别的失败 ——
    # 等待逻辑里的真值判断一旦写回 `if chrome.eval("typeof window.mermaid"):`，
    # 失败会挪到后面那条「渲染没跑完」上，读起来像是渲染慢，不像加载失败。
    assert "没加载起来" in str(excinfo.value), str(excinfo.value)


def test_the_tool_refuses_to_report_a_partial_run_as_a_result(monkeypatch):
    """渲染循环卡住（跑不完）时，工具必须报错，不能拿跑了一半的数字当结论。

    ok + bad 少于总数，就说明剩下的图卡住了。这次的数字不作数。
    """
    monkeypatch.setattr(check_mermaid.time, "sleep", lambda *_a, **_k: None)

    with pytest.raises(SystemExit):
        check_mermaid.render_all(
            _FakeChrome(ready=True),
            ["flowchart LR\n    A --> B"],
            "http://127.0.0.1:1/boot.html",
            timeout_s=0,
        )
