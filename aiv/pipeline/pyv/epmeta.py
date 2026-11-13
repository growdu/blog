"""每期的发布元数据：这一期在各个平台怎么自我介绍。

**入库的是事实**：元数据要评审、要版本化，所以进 `aiv/publish/<EP>.json`。
**不入库的是产物**：成片、发布包都留本机。

元数据只回答「这一期叫什么、封面取哪一帧、各平台的文案是什么」，
不回答「怎么发」——那是 adapter 的事。

平台段落里**缺一个字段就报错**，绝不静默补默认值：
补出来的默认值看起来能用，但它会让「作者忘了写」变得无声无息。
"""
from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

# aiv/ 是 pipeline/ 的上一级：pyv/epmeta.py → pyv → pipeline → aiv
AIV_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = AIV_ROOT.parent
PUBLISH_DIR = AIV_ROOT / "publish"
# 能力声明是契约层的数据文件。pyv 只**读**它，不 import 契约层的任何包。
CAPABILITIES_DIR = REPO_ROOT / "publish" / "capabilities"

ERROR = "error"
WARNING = "warning"

# 每个平台：必填字段、文本限额在 TOML 里的键名、列表限额、整数字段
#
# **列表限额的总限额怎么量，各平台不一样**，所以口径写在这里而不是靠键名猜：
#
# - 视频号 `topics_max`：话题**个数**的上限（5 个）。
# - B站 `tags_chars`：标签**英文逗号分隔后的总字符数**上限（199 字）。
# - 抖音 `topics_max`：话题**个数**的上限（5 个）——平台没文档化上限，
#   这条是我们的编辑预算，性质同视频号但出处不同（规格 §6.6.3）。
#
# 搞混的后果是方向相反的：视频号会把 5 个超长话题放过（真正该拦的是字数），
# B站会把 199 个标签放过（真正该拦的是总长）。规格 §4.3 有各自的定义。
PLATFORM_SPECS = {
    "channels": {
        "required": ("title", "description", "topics"),
        "text_limits": {"title": "title_chars", "description": "description_chars"},
        "list_limits": {
            "topics": {
                "total": "topics_max",
                "item": "topic_chars",
                "measure": "count",
            },
        },
        "int_fields": (),
        # 整数字段的取值域。平台只认这几个值，写别的平台会拒。
        "int_domains": {},
        # 条件必填：字段取到某个值时，另一个字段必须给。
        "required_when": {},
    },
    "bilibili": {
        "required": ("title", "description", "tags", "tid", "copyright", "no_reprint"),
        "text_limits": {"title": "title_chars", "description": "description_chars"},
        "list_limits": {
            "tags": {
                "total": "tags_chars",
                "item": "tag_chars",
                "measure": "joined",
                # B站的 tag 字段是英文逗号分隔的一串（不是 # 井号）。
                "separator": ",",
            },
        },
        "int_fields": ("tid", "copyright", "no_reprint"),
        # copyright：1 = 原创，2 = 转载；no_reprint：0 = 允许转载，1 = 不允许。
        "int_domains": {"copyright": (1, 2), "no_reprint": (0, 1)},
        # 转载必须给来源地址——平台会拒没有来源的转载（规格 §4.3）。
        "required_when": {"copyright": {2: ("source",)}},
    },
    "douyin": {
        # 抖音**没有独立的 description 字段**：标题、正文、话题全塞在一个
        # `text` 里。这一段是**三段拼一个字段**——adapter 拼好再去对
        # `text_chars` 查总量（规格 §6.6.3）。这里逐字段查的是各自的上限。
        "required": ("title", "description", "topics"),
        "text_limits": {"title": "title_chars", "description": "description_chars"},
        "list_limits": {
            "topics": {
                "total": "topics_max",
                "item": "topic_chars",
                "measure": "count",
                # 抖音的话题是 `#话题` 内嵌在 text 里，没有独立的列表字段。
                "separator": " ",
            },
        },
        "int_fields": (),
        "int_domains": {},
        "required_when": {},
    },
}


class MetaError(ValueError):
    """发布元数据本身坏了（文件读不了、不是对象）。"""


@dataclass(frozen=True)
class Finding:
    """一条检查结果。"""

    rule_id: str
    level: str
    message: str
    target: str = ""

    def __str__(self) -> str:
        where = f"[{self.target}] " if self.target else ""
        return f"{where}{self.rule_id} {self.message}"


@dataclass(frozen=True)
class EpisodeMeta:
    """一期的发布元数据。"""

    episode: str
    title: str
    cover_at: float
    url: str = ""
    channels: dict | None = None
    bilibili: dict | None = None
    douyin: dict | None = None
    path: Path | None = None

    def platform(self, name: str) -> dict | None:
        """某个平台的文案段落；没配就是 None（那一期不发这个平台）。"""
        if name not in PLATFORM_SPECS:
            raise KeyError(name)
        return getattr(self, name)


def meta_path(episode: str, root: Path | None = None) -> Path:
    base = Path(root) if root else PUBLISH_DIR
    return base / f"{episode}.json"


def load_meta(episode: str, root: Path | None = None) -> EpisodeMeta:
    path = meta_path(episode, root)
    if not path.is_file():
        raise MetaError(f"发布元数据不存在：{path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise MetaError(f"发布元数据不是合法 JSON：{path}（{error}）") from error
    if not isinstance(raw, dict):
        raise MetaError(f"发布元数据必须是对象：{path}")
    channels = raw.get("channels")
    bilibili = raw.get("bilibili")
    douyin = raw.get("douyin")
    # cover_at 写成非数字时要说人话——`float("x")` 抛的裸 ValueError
    # 会被 CLI 漏出去变成 traceback，而 CLI 只认 MetaError。
    try:
        cover_at = float(raw.get("cover_at", -1.0))
    except (TypeError, ValueError) as error:
        raise MetaError(
            f"cover_at 必须是数字，实际 {raw.get('cover_at')!r}：{path}") from error
    return EpisodeMeta(
        episode=str(raw.get("episode", "")),
        title=str(raw.get("title", "")),
        cover_at=cover_at,
        url=str(raw.get("url", "")),
        channels=channels if isinstance(channels, dict) else None,
        bilibili=bilibili if isinstance(bilibili, dict) else None,
        douyin=douyin if isinstance(douyin, dict) else None,
        path=path,
    )


def load_limits(platform: str, capabilities_dir: Path | None = None) -> dict:
    """读平台能力声明的 [limits] 段。"""
    base = Path(capabilities_dir) if capabilities_dir else CAPABILITIES_DIR
    path = base / f"{platform}.toml"
    if not path.is_file():
        raise MetaError(f"能力声明不存在：{path}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return data.get("limits", {}) or {}


def check_meta(meta: EpisodeMeta, contract_episode: str | None = None,
               duration: float | None = None,
               limits_loader=load_limits) -> list[Finding]:
    """校验一期元数据。返回的 Finding 里 level=error 的必须先改。"""
    findings: list[Finding] = []
    target = meta.episode or (meta.path.name if meta.path else "")

    if not meta.episode:
        findings.append(Finding("epmeta.episode", ERROR, "缺少 episode", target))
    elif contract_episode and meta.episode != contract_episode:
        findings.append(Finding(
            "epmeta.episode", ERROR,
            f"元数据的 episode 是 {meta.episode!r}，契约里是 {contract_episode!r}",
            target))

    if not meta.title:
        findings.append(Finding("epmeta.required", ERROR, "缺少 title", target))

    if meta.cover_at < 0:
        findings.append(Finding("epmeta.cover-at", ERROR,
                                "缺少 cover_at 或取值为负", target))
    elif duration is not None and meta.cover_at > duration:
        findings.append(Finding(
            "epmeta.cover-at", ERROR,
            f"cover_at {meta.cover_at:.3f}s 超出成片时长 {duration:.3f}s", target))

    for platform, spec in PLATFORM_SPECS.items():
        section = meta.platform(platform)
        if section is None:
            findings.append(Finding(
                "epmeta.platform-missing", WARNING,
                f"没有配置 {platform} 的文案，这一期不发这个平台", target))
            continue
        findings.extend(
            _check_platform(platform, section, spec, limits_loader, target))
    return findings


def _check_platform(platform, section, spec, limits_loader, target):
    findings: list[Finding] = []
    for key in spec["required"]:
        if key not in section or section[key] in (None, ""):
            findings.append(Finding(
                "epmeta.platform-required", ERROR,
                f"{platform} 的文案缺少 {key!r}", target))
    if findings:
        # 缺字段的时候先报缺字段，别同时报出一堆长度错误。
        return findings

    try:
        limits = limits_loader(platform)
    except MetaError as exc:
        findings.append(Finding("epmeta.limits", ERROR, str(exc), target))
        return findings

    for field_name, limit_key in spec["text_limits"].items():
        limit = limits.get(limit_key)
        if limit is None:
            findings.append(Finding(
                "epmeta.limits", ERROR,
                f"{platform} 的能力声明缺少 limits.{limit_key}", target))
            continue
        value = str(section.get(field_name, ""))
        if len(value) > limit:
            findings.append(Finding(
                "epmeta.text-limit", ERROR,
                f"{platform} 的 {field_name} 有 {len(value)} 字，超过上限 {limit}",
                target))

    for field_name, list_spec in spec["list_limits"].items():
        total_limit = limits.get(list_spec["total"])
        item_limit = limits.get(list_spec["item"])
        if total_limit is None or item_limit is None:
            findings.append(Finding(
                "epmeta.limits", ERROR,
                f"{platform} 的能力声明缺少 {list_spec['total']} / {list_spec['item']}",
                target))
            continue
        items = section.get(field_name) or []
        if not isinstance(items, list):
            findings.append(Finding(
                "epmeta.platform-required", ERROR,
                f"{platform} 的 {field_name} 必须是列表", target))
            continue
        # 总限额怎么量，两个平台不一样（见 PLATFORM_SPECS 的说明）。
        if list_spec["measure"] == "count":
            total = len(items)
            total_text = f"{total} 项"
        else:
            joined = list_spec["separator"].join(str(item) for item in items)
            total = len(joined)
            total_text = f"{total} 字（逗号分隔后）"
        if total > total_limit:
            findings.append(Finding(
                "epmeta.list-limit", ERROR,
                f"{platform} 的 {field_name} 共 {total_text}，超过上限 {total_limit}",
                target))
        for item in items:
            if len(str(item)) > item_limit:
                findings.append(Finding(
                    "epmeta.list-limit", ERROR,
                    f"{platform} 的 {field_name} 里 {item!r} 有 {len(str(item))} 字，"
                    f"超过单项上限 {item_limit}", target))

    for field_name in spec["int_fields"]:
        value = section.get(field_name)
        if not isinstance(value, int) or isinstance(value, bool):
            findings.append(Finding(
                "epmeta.int-field", ERROR,
                f"{platform} 的 {field_name} 必须是整数，实际 {value!r}", target))
            continue
        allowed = spec["int_domains"].get(field_name)
        if allowed is not None and value not in allowed:
            findings.append(Finding(
                "epmeta.int-domain", ERROR,
                f"{platform} 的 {field_name} 只能是 {list(allowed)} 之一，"
                f"实际 {value!r}", target))

    # 条件必填：B站转载（copyright = 2）必须给 source。
    for field_name, mapping in spec["required_when"].items():
        value = section.get(field_name)
        for needed_value, other_fields in mapping.items():
            if value != needed_value:
                continue
            for other in other_fields:
                if not str(section.get(other) or "").strip():
                    findings.append(Finding(
                        "epmeta.conditional-required", ERROR,
                        f"{platform} 的 {field_name} = {needed_value} 时必须给 "
                        f"{other}（平台会拒没有来源的转载）", target))
    return findings
