"""平台能力模型：读 ``publish/capabilities/<platform>.toml``。

能力声明是**数据**：平台规则变了改 TOML，不改 Python
（``publish/spec/00-架构设计.md`` §5、§5.2）。

**这份文件与平台 adapter 里的同名文件是两份，不是重复。**
边界见 §11.1「依赖方向：只有一处接缝」：

* 契约层这一份读**任意**平台（wechat / youtube / bilibili / toutiao /
  channels），所以顶层是「核心必填 + 平台扩展可选」，``[limits]`` 里
  平台自有的键原样保留、不做类型判断。
* adapter 那一份只读**自己**平台（``toutiao/toutiao/capability.py``），
  所以它那份的限额字段全是必填——缺一个就报错。
* 两边**互不 import**：契约层不 import 平台内部模块，平台也不 import
  契约层。它们认的是**同一份 TOML 文件**，不是同一份代码。

声明是外部输入，所以每个字段都严格校验：必填字段缺失、类型不对、
取值不在域内，一律抛 :class:`CapabilityFieldError` 并在消息里点名字段，
绝不漏出裸 KeyError / TypeError，也不与内建 ValueError 混用。

**这一层是唯一的闸门。** §11.1 的流程是「契约层先读 ``capabilities/*.toml``
→ 校验 → 再按 ``[adapter].command`` 调 adapter」，所以一份坏 TOML 在**派发
之前**就被这一层拦住了。adapter 自己那份 loader（``toutiao/toutiao/capability.py``）
更宽松，那条宽松路径只有在有人**直接跑 adapter CLI、绕过这一层**时才会生效
（§12 第 13 行的调度器若忘了先加载能力模型，也会踩到）。

**两边的解读严格度不一样，逐条列在这里**（同一份 TOML 喂两边的结论；adapter
那一列依据的是 ``feat/toutiao-adapter`` 分支上的
``toutiao/toutiao/capability.py``）：

=====================================  ==========  =====================
TOML 写法                                 契约层      toutiao adapter
=====================================  ==========  =====================
顶层未知键（``automaion =``）             REJECT      ACCEPT
``kind = "article"``（值域外）            REJECT      ACCEPT
``review = "human"``（值域外）            REJECT      ACCEPT
``verified = "last tuesday"``（非日期）   REJECT      ACCEPT
``requires_certificaton =``（拼错）      REJECT      ACCEPT → 门槛翻成 False
顶层缺 ``name``                          REJECT      ACCEPT（默认 ""）
顶层缺 ``review``                        REJECT      ACCEPT（默认 "platform"）
``kinds =``（拼错）                      REJECT      ACCEPT → kind 落到默认值
``automation = "api"``（值域外）         REJECT      REJECT
=====================================  ==========  =====================

最刺眼的一条是 ``requires_certificaton``（拼错）：adapter 接受它，并据此得出
「该平台不需要认证」——一个门槛开关被拼写错误静默翻成了 False。契约层拒绝
这种 TOML，所以只要走 §11.1 的流程就不会咬人。

**本轮不去改 adapter 那份 loader**：那要动 ``toutiao/``，越过 §11.1 的接缝，
也不在这一轮的范围内。要让两边对齐，正确的方向是在 adapter 侧对它**自己会
读到的字段**（kind / review / automation / verified / requires_certification）
也做值域校验——那是 toutiao 分支的事。契约层**不许**反过来 import adapter。
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import PublishKitError

__all__ = [
    "AUTOMATIONS",
    "KINDS",
    "PLATFORM_ID_RE",
    "REVIEWS",
    "Capability",
    "CapabilityError",
    "CapabilityFieldError",
    "CapabilityFileError",
    "available_platforms",
    "default_capabilities_dir",
    "list_capabilities",
    "load_capability",
    "load_capability_file",
]

#: 内容单元类型（§5）。
KINDS = ("document", "video")

#: 自动化停在哪一步（§5、§6.4「三档 automation」）。
AUTOMATIONS = ("api_draft", "api_publish", "manual")

#: 发布后要不要轮询审核状态（§5）。
REVIEWS = ("none", "platform", "precheck")

# 顶层必填字段：每个平台都必须说清楚自己是什么、自动化停在哪、审不审。
_REQUIRED_TOP_KEYS = ("id", "name", "kind", "automation", "review")

# 顶层全部合法字段。平台可以在 [limits] / [media] 里加自有键，
# 但顶层加键会让「这个平台到底是什么」变得不可控，所以顶层拒绝未知键。
_TOP_KEYS = _REQUIRED_TOP_KEYS + (
    "adapter",
    "auth",
    "ip_allowlist",
    "limits",
    "media",
    "requires_certification",
    "requires_min_followers",
    "verified",
)

#: ``verified`` 的取值域：实测日期；日期未定的那一天允许写 XX
#: （规格 §6.4 的示例就是 ``verified = "2026-11-XX"``）。
_VERIFIED_RE = re.compile(r"^\d{4}-\d{2}-(\d{2}|XX)$")

#: 平台 id 的取值域：小写字母开头，可含数字与下划线。
#: 内容契约的 ``platforms`` 字段用的是同一套词汇——一份词汇只在一个地方定义。
PLATFORM_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class CapabilityError(PublishKitError):
    """能力声明读不了，或内容不合法。"""


class CapabilityFileError(CapabilityError):
    """声明文件不存在、不是合法 TOML，或 id 与文件名对不上。"""


class CapabilityFieldError(CapabilityError):
    """某个字段缺失、类型不对，或取值不在域内。"""


@dataclass(frozen=True)
class Capability:
    """一个平台的完整能力声明。

    ``limits`` 与 ``adapter`` 保持成字典，字段名与 TOML 里写的一致——
    规格 §5.3 的兼容性测试就是这么用的：

    .. code-block:: python

        cap = load_capability("wechat")
        assert cap.limits["title_chars"] == posts.TITLE_LIMIT
    """

    id: str
    name: str
    kind: str
    automation: str
    review: str
    auth: str
    ip_allowlist: bool
    requires_certification: bool
    requires_min_followers: int
    verified: str | None
    limits: dict
    adapter: dict
    media: dict
    path: Path

    @property
    def adapter_package(self) -> str | None:
        """adapter 的 Python 包名（``[adapter].package``），没写就是 None。"""
        value = self.adapter.get("package")
        return value if isinstance(value, str) else None

    @property
    def adapter_command(self) -> tuple[str, ...]:
        """adapter 的调用命令（``[adapter].command``），没写就是空元组。

        这是契约层与平台实现之间的**唯一接缝**（§11.1）：调度器按这条命令
        去调 adapter 的 CLI，不 import 它的任何模块。
        """
        value = self.adapter.get("command")
        return tuple(value) if isinstance(value, list) else ()

    def to_dict(self) -> dict:
        """可 JSON 序列化的快照（供 CLI 打印与索引使用）。"""
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "automation": self.automation,
            "review": self.review,
            "auth": self.auth,
            "ip_allowlist": self.ip_allowlist,
            "requires_certification": self.requires_certification,
            "requires_min_followers": self.requires_min_followers,
            "verified": self.verified,
            "limits": dict(self.limits),
            "adapter": dict(self.adapter),
            "media": dict(self.media),
            "path": str(self.path),
        }


# --- 字段校验 -----------------------------------------------------------
#
# 能力声明是外部输入（一份别人会编辑的 TOML）。写错的值必须以
# CapabilityFieldError 拒绝，而且消息里要带字段全名（``limits.title_chars``）——
# 否则调用方的 except 会被 TypeError 穿透，报错也指不到是哪个字段的问题。


def _type_name(value: object) -> str:
    return type(value).__name__


def _field_path(parent: str, key: str) -> str:
    """Dotted field path: ``limits`` + ``title_chars`` -> ``limits.title_chars``."""
    return "{}.{}".format(parent, key) if parent else key


def _as_int(value: object) -> int:
    """A TOML integer.  A bool is not an int here, and a float is not truncated."""
    if isinstance(value, bool):
        raise TypeError("布尔值不是整数")
    if not isinstance(value, int):
        raise TypeError("不是整数")
    return value


def _as_str(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("不是字符串")
    return value


def _as_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise TypeError("不是布尔值")
    return value


def _as_str_list(value: object) -> list:
    if not isinstance(value, list):
        raise TypeError("不是字符串数组")
    for item in value:
        if not isinstance(item, str):
            raise TypeError("数组元素不是字符串")
    return list(value)


def _as_int_pair(value: object) -> list:
    if not isinstance(value, list):
        raise TypeError("不是数组")
    if len(value) != 2:
        raise ValueError("必须正好 2 个整数，实际有 {} 个".format(len(value)))
    return [_as_int(value[0]), _as_int(value[1])]


def _convert(value: object, path: str, converter):
    """Run one strict conversion; TypeError/ValueError become CapabilityFieldError."""
    try:
        return converter(value)
    except (TypeError, ValueError) as exc:
        raise CapabilityFieldError(
            "能力模型字段 {} 不合法：{}".format(path, exc)
        ) from exc


def _read(data: dict, key: str, parent: str):
    """Return ``(found, value)`` for one key of a table."""
    if key not in data:
        return False, None
    return True, data[key]


def _required(data: dict, key: str, parent: str, converter):
    """Read a required field and convert it strictly."""
    found, value = _read(data, key, parent)
    if not found:
        raise CapabilityFieldError(
            "能力模型缺少字段 {}".format(_field_path(parent, key))
        )
    return _convert(value, _field_path(parent, key), converter)


def _optional(data: dict, key: str, parent: str, converter, default):
    """Read an optional field; a missing key falls back to ``default``."""
    found, value = _read(data, key, parent)
    if not found:
        return default
    return _convert(value, _field_path(parent, key), converter)


def _table(data: dict, key: str, parent: str = "") -> dict:
    """Fetch an optional table; a present-but-not-a-table value is an error."""
    found, value = _read(data, key, parent)
    if not found:
        return {}
    if not isinstance(value, dict):
        raise CapabilityFieldError(
            "能力模型字段 {} 期望是表/映射，实际是 {}".format(
                _field_path(parent, key), _type_name(value)
            )
        )
    return value


def _reject_unknown(data: dict, allowed, parent: str) -> None:
    """未知顶层键一律拒绝——键名打错（``automaion``）必须当场发现。"""
    for key in data:
        if key not in allowed:
            raise CapabilityFieldError(
                "能力模型出现未知字段 {}".format(_field_path(parent, key))
            )


#: ``[limits]`` 里契约层认识的键及其类型。平台自有的键（视频平台的
#: ``description_chars`` 等）不在表里，原样保留在 ``limits`` 字典中，
#: 不做类型判断——契约层不认识具体平台，就不该替它猜字段含义。
_LIMIT_TYPES = {
    "title_chars": _as_int,
    "body_chars": _as_int,
    "digest_chars": _as_int,
    "image_bytes": _as_int,
    "max_body_images": _as_int,
    "image_formats": _as_str_list,
    "cover_ratio": _as_str,
    "cover_min_pixels": _as_int_pair,
}


def _validate_limits(limits_raw: dict) -> dict:
    """Validate the limits this layer knows; keep the rest verbatim."""
    limits = {}
    for key, value in limits_raw.items():
        converter = _LIMIT_TYPES.get(key)
        if converter is None:
            limits[key] = value
            continue
        limits[key] = _convert(value, _field_path("limits", key), converter)
    return limits


def _validate_adapter(adapter_raw: dict) -> dict:
    """``[adapter]`` 是接缝，字段固定：包名 + 调用命令。"""
    _reject_unknown(adapter_raw, ("package", "command"), "adapter")
    adapter = {}
    found, value = _read(adapter_raw, "package", "adapter")
    if found:
        adapter["package"] = _convert(value, "adapter.package", _as_str)
    found, value = _read(adapter_raw, "command", "adapter")
    if found:
        adapter["command"] = _convert(value, "adapter.command", _as_str_list)
        if not adapter["command"]:
            raise CapabilityFieldError("能力模型字段 adapter.command 不能是空数组")
    return adapter


def _validate_verified(value: object) -> str:
    """``verified`` 是一次实测的日期（§5）；日期未定的那天允许写 XX。"""
    text = _convert(value, "verified", _as_str)
    if not _VERIFIED_RE.match(text):
        raise CapabilityFieldError(
            "能力模型字段 verified 必须是 YYYY-MM-DD（未定的那天可写 XX），实际是 {!r}".format(
                text
            )
        )
    return text


def default_capabilities_dir() -> Path:
    """仓库里那份能力声明目录（``publish/capabilities/``）。"""
    return Path(__file__).resolve().parents[1] / "capabilities"


def load_capability_file(path) -> Capability:
    """Load and validate one capability declaration."""
    path = Path(path)
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise CapabilityFileError("能力声明文件不存在：{}".format(path)) from exc
    except OSError as exc:
        raise CapabilityFileError(
            "能力声明文件读不了：{}（{}）".format(path, exc)
        ) from exc
    except tomllib.TOMLDecodeError as exc:
        raise CapabilityFileError(
            "能力声明不是合法 TOML：{}（{}）".format(path, exc)
        ) from exc

    if not isinstance(data, dict):
        raise CapabilityFieldError("能力声明的顶层必须是表")

    _reject_unknown(data, _TOP_KEYS, "")

    platform_id = _required(data, "id", "", _as_str)
    if not PLATFORM_ID_RE.match(platform_id):
        raise CapabilityFieldError(
            "能力模型字段 id 不合法：{!r}（应为小写字母开头的标识符）".format(
                platform_id
            )
        )
    if path.stem != platform_id:
        # 文件名是注册表的名字，id 必须与它一致——否则「哪个平台」就有两个答案。
        raise CapabilityFileError(
            "能力声明 id 与文件名不一致：文件 {} 的 id 是 {!r}".format(
                path.name, platform_id
            )
        )

    name = _required(data, "name", "", _as_str)
    if not name.strip():
        raise CapabilityFieldError("能力模型字段 name 不能为空")

    kind = _required(data, "kind", "", _as_str)
    if kind not in KINDS:
        raise CapabilityFieldError(
            "能力模型字段 kind 必须是 {} 之一，实际是 {!r}".format(
                " / ".join(KINDS), kind
            )
        )

    automation = _required(data, "automation", "", _as_str)
    if automation not in AUTOMATIONS:
        raise CapabilityFieldError(
            "能力模型字段 automation 必须是 {} 之一，实际是 {!r}".format(
                " / ".join(AUTOMATIONS), automation
            )
        )

    review = _required(data, "review", "", _as_str)
    if review not in REVIEWS:
        raise CapabilityFieldError(
            "能力模型字段 review 必须是 {} 之一，实际是 {!r}".format(
                " / ".join(REVIEWS), review
            )
        )

    auth = _optional(data, "auth", "", _as_str, "none")
    if not auth.strip():
        raise CapabilityFieldError("能力模型字段 auth 不能为空")

    ip_allowlist = _optional(data, "ip_allowlist", "", _as_bool, False)
    requires_certification = _optional(
        data, "requires_certification", "", _as_bool, False
    )
    requires_min_followers = _optional(
        data, "requires_min_followers", "", _as_int, 0
    )
    if requires_min_followers < 0:
        raise CapabilityFieldError(
            "能力模型字段 requires_min_followers 不能为负，实际是 {}".format(
                requires_min_followers
            )
        )

    found, verified = _read(data, "verified", "")
    verified_value = _validate_verified(verified) if found else None

    limits = _validate_limits(_table(data, "limits"))
    adapter = _validate_adapter(_table(data, "adapter"))
    media = _table(data, "media")

    return Capability(
        id=platform_id,
        name=name,
        kind=kind,
        automation=automation,
        review=review,
        auth=auth,
        ip_allowlist=ip_allowlist,
        requires_certification=requires_certification,
        requires_min_followers=requires_min_followers,
        verified=verified_value,
        limits=limits,
        adapter=adapter,
        media=media,
        path=path,
    )


def load_capability(platform_id: str, *, capabilities_dir=None) -> Capability:
    """Load the capability declaration of one platform, by its id."""
    if not isinstance(platform_id, str) or not PLATFORM_ID_RE.match(platform_id):
        raise CapabilityFieldError(
            "平台 id 不合法：{!r}（应为小写字母开头的标识符）".format(platform_id)
        )
    directory = (
        Path(capabilities_dir)
        if capabilities_dir is not None
        else default_capabilities_dir()
    )
    path = directory / "{}.toml".format(platform_id)
    if not path.is_file():
        raise CapabilityFileError(
            "找不到平台 {!r} 的能力声明：{}".format(platform_id, path)
        )
    return load_capability_file(path)


def list_capabilities(*, capabilities_dir=None) -> list:
    """Load every ``*.toml`` under the capabilities directory, sorted by id."""
    directory = (
        Path(capabilities_dir)
        if capabilities_dir is not None
        else default_capabilities_dir()
    )
    if not directory.is_dir():
        return []
    capabilities = [
        load_capability_file(path) for path in sorted(directory.glob("*.toml"))
    ]
    return sorted(capabilities, key=lambda cap: cap.id)


def available_platforms(*, capabilities_dir=None) -> list:
    """The ids of every declared platform, sorted."""
    return [cap.id for cap in list_capabilities(capabilities_dir=capabilities_dir)]
