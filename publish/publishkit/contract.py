"""内容契约：母稿自己说了什么。

母稿（``docs/`` 下的 md）是唯一真相（``publish/spec/00-架构设计.md`` §三
不变量一）。内容契约规定母稿的 front matter 能写什么、怎么写、写到哪。

格式规则（§4.2）：只允许扁平的 ``key: value`` 与单层的 ``key:`` +
``  - item`` 列表，嵌套仅 ``cascade:`` 允许，多行值不支持。
这一套格式不是新发明——``weixin/wechat/posts.py`` 的 ``parse_front_matter()``
实现的正是同一套（``key: value`` 标量 + ``  - item`` 列表），规格 §4.2 明确要求
「契约与它逐条对齐，不是各写各的」。

所以这里的解析器与它在 **LF 输入下语义逐条一致**，但**代码是独立的**：契约层
不 import 平台 adapter 的任何模块（§11.1 的接缝原则）。想锁住两边不漂移，
靠的是 §5.3 那条兼容性测试，不是靠 import。

**口径差异有两处，都是有意为之**——一句话「逐条一致」因此不能说死，
每一条差异都由 ``publish/tests/test_contract.py`` 里的一条用例**显式钉住**，
不靠默契。

**一、CRLF。** 本层的 front matter 正则认 ``\r\n``
（``^---\r?\n(.*?)\r?\n---\r?\n``），weixin 那份只认 ``\n``
（``^---\n(.*?)\n---\n``）。同一段 CRLF 文本，契约层解析出
``{title, platforms}``，weixin 那份解析出 ``{}``。

**二、缩进标量。** ``platforms:`` 下面缩进一个非列表项（``  wechat``），
契约层按 YAML 的真实语义读成**标量** ``"wechat"``；weixin 那份把这一行
整行跳过，剩下一个空列表 ``[]``。空列表意味着「这篇不属于任何平台」→
不进发布候选集，而作者明明写了 platforms——这一层是唯一的闸门，
闸门不能自己把人放过去。

为什么不对称：契约层的读者不止 weixin 一个（还有未来的 B站 / 视频号 / 头条），
对母稿格式更宽容是实质性的健壮性；而「与 weixin 一致」这个承诺不该把两边
互相绑定（§11.1 的「各改各的」）。代价是两边对同一段文本给出不同答案
——所以那句话不能说「逐条一致」，差异钉在测试里。

（第二处差异在**生产链路上碰不到**：weixin 读的是 ``source/_posts/``，
那里的缩进标量已被 sync 折叠成单行 ``key: value``。它只在直接读作者原稿
``docs/`` 时才会出现——而那正是 ``read_contract()`` 承诺支持的用法。）

字段白名单（§4.1）与约束：

===========  ==============  ==========================================
字段          类型             约束
===========  ==============  ==========================================
title        str             ≤ 80 字
short_title  str             ≤ 32 字
tldr         str             ≤ 120 字
description  str             ≤ 150 字
difficulty   int             1–5
cover        str             相对文章目录
reprintPolicy str            主题支持的转载枚举
kind         str             ``post``（默认）/ ``video``
platforms    list[str]       平台 id 列表
publish_on   str             ``YYYY-MM-DD``
date         str             ``YYYY-MM-DD`` 或 ``YYYY-MM-DD HH:MM:SS``
===========  ==============  ==========================================

**``date`` 不是作者写的字段，是 sync 写进 ``source/_posts/`` 的那一个。**
调度层的选题规则要按日期排序（06 规格 §3.3「按 ``publish_on``（缺省用
``date``）升序」），所以这一层得认它。

但它**不在透传白名单里**：``PASSTHROUGH_FIELDS`` 是 sync 的白名单，
加进去会改变站点渲染结果（``tools/sync-hexo.py`` 写的 ``date`` 决定
permalink）。``date`` 只是被**读**，不被**搬**。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from . import PublishKitError
from .capability import PLATFORM_ID_RE

__all__ = [
    "CONTENT_KINDS",
    "PASSTHROUGH_FIELDS",
    "REPRINT_POLICIES",
    "ContentContract",
    "ContractError",
    "ContractFieldError",
    "ContractFileError",
    "contract_from_fields",
    "parse_content_date",
    "parse_front_matter",
    "read_contract",
    "validate_fields",
]

#: 内容单元类型（§4.1）。注意与能力模型的 ``kind``（document / video）
#: 不是同一套取值：这里说的是「这篇是什么」，那边说的是「这个平台发什么」。
CONTENT_KINDS = ("post", "video")

#: 主题（matery）支持的转载声明取值（``themes/matery/_config.yml``）。
REPRINT_POLICIES = (
    "cc_by",
    "cc_by_nd",
    "cc_by_sa",
    "cc_by_nc",
    "cc_by_nc_nd",
    "cc_by_nc_sa",
    "cc0",
    "noreprint",
    "pay",
)

#: 透传白名单（§4.1）。未声明的顶层字段一律丢弃——白名单透传，不做全文转储。
PASSTHROUGH_FIELDS = (
    "title",
    "short_title",
    "tldr",
    "description",
    "difficulty",
    "cover",
    "reprintPolicy",
    "kind",
    "platforms",
    "publish_on",
)

#: 长度约束（§4.1）。
_FIELD_MAX_CHARS = {
    "title": 80,
    "short_title": 32,
    "tldr": 120,
    "description": 150,
}

_FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
#: ``date`` 字段认两种形态：纯日期与带时分秒的日期。后者是
#: ``tools/sync-hexo.py`` 写进 ``source/_posts/`` 的形状。
_DATE_FIELD_RE = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}:\d{2})?$")
_INT_RE = re.compile(r"^-?\d+$")


class ContractError(PublishKitError):
    """内容契约读不了，或内容不合法。"""


class ContractFileError(ContractError):
    """母稿文件不存在或读不了。"""


class ContractFieldError(ContractError):
    """某个字段缺失、类型不对，或取值不在域内。"""


def _unquote(value: str) -> str:
    """Strip one layer of matching quotes."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_front_matter(text: str) -> tuple:
    """Split YAML-ish front-matter from the body.

    ``tools/sync-hexo.py`` generates the front-matter itself, so the shape is
    known and fixed: ``key: value`` scalars plus ``key:`` followed by
    ``  - item`` lists.  A tiny hand-written parser avoids adding a YAML
    dependency for a format we control.

    Returns ``(fields, body)``.  A list field maps to a list of strings;
    a single-item list is kept as a one-element list so callers do not have
    to guess the shape.  A ``key:`` with no items below it is an empty list
    (``cover:`` → ``[]``)——this matches ``weixin/wechat/posts.py`` field for
    field, so the two never disagree about what a draft said（LF 输入下；
    两处有意分歧见模块 docstring）。

    **缩进标量**：``key:`` 下面缩进一个非列表项（``  wechat``）时，按 YAML 的
    真实语义读成**标量** ``"wechat"``。这一形态不是 sync 产出的形状（sync
    把它折叠成单行 ``key: value``），只在直接读作者原稿时才会遇到。

    在 **LF 输入下**与 ``weixin/wechat/posts.py:82`` 的 ``parse_front_matter()``
    逐条对齐（缩进标量除外）；CRLF 输入下本层认 ``\r\n`` 而 weixin 那份不认
    ——这两处差异都是有意为之，见模块 docstring。代码独立：契约层不 import
    平台 adapter 的任何模块。
    """
    if not isinstance(text, str):
        raise ContractFieldError(
            "母稿内容必须是字符串，实际是 {}".format(type(text).__name__)
        )

    match = _FM_RE.match(text)
    if not match:
        return {}, text

    fields = {}
    list_key = None
    list_items = []

    def close_list():
        nonlocal list_key, list_items
        if list_key is not None:
            fields[list_key] = list(list_items)
        list_key = None
        list_items = []

    for raw in match.group(1).split("\n"):
        if not raw.strip():
            continue
        stripped = raw.lstrip()
        if stripped.startswith("- "):
            if list_key is not None:
                list_items.append(_unquote(stripped[2:]))
            continue
        if raw[:1] in (" ", "\t") and list_key is not None and ":" not in raw:
            # 缩进标量：``key:`` 下面缩进的、不是列表项的一行。
            #
            # 这一形态**不是** sync 产出的形状——sync 把它折叠成单行
            # ``key: value``——所以只有直接读作者原稿 ``docs/`` 时才会遇到。
            # 按 YAML 的真实语义它是**标量**：``platforms:`` 下面缩进的
            # ``wechat`` 是字符串 "wechat"，不是空列表。
            #
            # 为什么不能当空列表：空列表意味着「这篇不属于任何平台」→
            # ``is_publish_candidate`` 为 False → 这篇**静默**不进发布候选集，
            # 而作者明明写了 platforms。这一层是唯一的闸门，闸门不能自己把
            # 人放过去——响亮地报「platforms 必须是列表」才是它该做的。
            key = list_key
            close_list()
            fields[key] = _unquote(stripped)
            continue
        if ":" in raw:
            key, _, value = raw.partition(":")
            key = key.strip()
            value = value.strip()
            close_list()
            if value:
                fields[key] = _unquote(value)
            else:
                list_key = key
    close_list()

    return fields, text[match.end():]


def validate_fields(fields: dict) -> list:
    """Check front-matter fields against the content contract.

    Returns **all** violations (never raises) so the linter can report them
    in one pass; :func:`read_contract` turns a non-empty list into an error.
    """
    if not isinstance(fields, dict):
        raise ContractFieldError(
            "front matter 必须是映射，实际是 {}".format(type(fields).__name__)
        )

    violations = []

    for field, limit in _FIELD_MAX_CHARS.items():
        value = fields.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            violations.append("{} 必须是字符串".format(field))
        elif len(value) > limit:
            violations.append(
                "{} {} 字，超过上限 {} 字".format(field, len(value), limit)
            )

    violations.extend(_validate_difficulty(fields))
    violations.extend(_validate_kind(fields))
    violations.extend(_validate_reprint_policy(fields))
    violations.extend(_validate_platforms(fields))
    violations.extend(_validate_publish_on(fields))
    violations.extend(_validate_date(fields))

    return violations


def _validate_difficulty(fields: dict) -> list:
    value = fields.get("difficulty")
    if value is None:
        return []
    if not isinstance(value, str) or not _INT_RE.match(value.strip()):
        return ["difficulty 必须是 1–5 的整数，实际是 {!r}".format(value)]
    number = int(value.strip())
    if not 1 <= number <= 5:
        return ["difficulty {} 超出 1–5".format(number)]
    return []


def _validate_kind(fields: dict) -> list:
    value = fields.get("kind")
    if value is None:
        return []
    if not isinstance(value, str):
        return ["kind 必须是字符串"]
    if value not in CONTENT_KINDS:
        return [
            "kind 必须是 {} 之一，实际是 {!r}".format(" / ".join(CONTENT_KINDS), value)
        ]
    return []


def _validate_reprint_policy(fields: dict) -> list:
    value = fields.get("reprintPolicy")
    if value is None:
        return []
    if not isinstance(value, str):
        return ["reprintPolicy 必须是字符串"]
    if value not in REPRINT_POLICIES:
        return ["reprintPolicy {!r} 不在主题支持的枚举里".format(value)]
    return []


def _validate_platforms(fields: dict) -> list:
    value = fields.get("platforms")
    if value is None:
        return []
    if not isinstance(value, list):
        return ["platforms 必须是列表"]
    violations = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            violations.append("platforms 的元素必须是非空字符串")
        elif not PLATFORM_ID_RE.match(item):
            violations.append("platforms 里的平台 id {!r} 不合法".format(item))
    return violations


def _validate_publish_on(fields: dict) -> list:
    value = fields.get("publish_on")
    if value is None:
        return []
    if not isinstance(value, str):
        return ["publish_on 必须是字符串"]
    if not _DATE_RE.match(value.strip()):
        return ["publish_on {!r} 不是 YYYY-MM-DD 格式".format(value)]
    try:
        date.fromisoformat(value.strip())
    except ValueError:
        return ["publish_on {!r} 不是真实存在的日期".format(value)]
    return []


def parse_content_date(value: str) -> date:
    """把 front matter 的 ``date`` 解析成 :class:`datetime.date`。

    认两种形态：``YYYY-MM-DD`` 与 ``YYYY-MM-DD HH:MM:SS``——后者是
    ``tools/sync-hexo.py`` 写进 ``source/_posts/`` 的形状（它把 git 的
    时间戳去掉时区偏移后原样写下来）。

    解析不了就抛 :class:`ContractFieldError`：``date`` 是外部输入，
    坏日期必须**指名道姓**地报出来，不能漏出裸 ``ValueError``。
    """
    if not isinstance(value, str):
        raise ContractFieldError(
            "date 必须是字符串，实际是 {}".format(type(value).__name__)
        )
    text = value.strip()
    if not _DATE_FIELD_RE.match(text):
        raise ContractFieldError(
            "date {!r} 不是 YYYY-MM-DD[ HH:MM:SS] 格式".format(value)
        )
    try:
        return datetime.fromisoformat(text).date()
    except ValueError as exc:
        raise ContractFieldError(
            "date {!r} 不是真实存在的日期".format(value)
        ) from exc


def _validate_date(fields: dict) -> list:
    value = fields.get("date")
    if value is None:
        return []
    try:
        parse_content_date(value)
    except ContractFieldError as exc:
        return [str(exc)]
    return []


@dataclass(frozen=True)
class ContentContract:
    """What one master draft says about itself."""

    path: Path | None
    title: str
    kind: str
    platforms: tuple
    publish_on: str | None
    date: str | None
    short_title: str | None
    tldr: str | None
    description: str | None
    difficulty: int | None
    cover: str | None
    reprint_policy: str | None

    @property
    def is_publish_candidate(self) -> bool:
        """``platforms`` 非空即进入发布候选集（06 规格 §3.2）。"""
        return bool(self.platforms)


def contract_from_fields(fields: dict, *, path=None) -> ContentContract:
    """Build a :class:`ContentContract` from parsed front-matter fields.

    Raises :class:`ContractFieldError` when the fields violate the contract.
    """
    violations = validate_fields(fields)
    if violations:
        where = "{} ".format(path) if path is not None else ""
        raise ContractFieldError(
            "{}不满足内容契约：{}".format(where, "；".join(violations))
        )

    def text(field):
        value = fields.get(field)
        return value if isinstance(value, str) else None

    platforms = fields.get("platforms")
    difficulty = fields.get("difficulty")

    return ContentContract(
        path=Path(path) if path is not None else None,
        title=text("title") or "",
        kind=text("kind") or "post",
        platforms=tuple(platforms) if isinstance(platforms, list) else (),
        publish_on=text("publish_on"),
        date=text("date"),
        short_title=text("short_title"),
        tldr=text("tldr"),
        description=text("description"),
        difficulty=int(difficulty.strip()) if isinstance(difficulty, str) else None,
        cover=text("cover"),
        reprint_policy=text("reprintPolicy"),
    )


def read_contract(path) -> ContentContract:
    """Read one master draft and return its content contract.

    母稿可以是 ``docs/`` 下的原稿，也可以是 ``source/_posts/`` 下的内容单元
    ——两者的 front matter 是同一套。

    有一处例外：**缩进标量**（``platforms:`` 下面缩进一个非列表项）在原稿
    里是作者写的，在 ``source/_posts/`` 里已被 sync 折叠成单行
    ``platforms: wechat``。同一份内容，两条路径给出的**判定不同**：原稿那条
    路径报「platforms 必须是列表」（响亮失败），sync 那条路径也是同一条报错
    ——所以这里不会出现「同一篇文章，一个说不发、另一个说发」的分裂。
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ContractFileError("母稿文件不存在：{}".format(path)) from exc
    except OSError as exc:
        raise ContractFileError("母稿文件读不了：{}（{}）".format(path, exc)) from exc

    fields, _body = parse_front_matter(text)
    return contract_from_fields(fields, path=path)
