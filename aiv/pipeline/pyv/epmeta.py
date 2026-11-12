"""每期的发布元数据：这一期在各个平台怎么自我介绍。

**入库的是事实**：元数据要评审、要版本化，所以进 `aiv/publish/<EP>.json`。
**不入库的是产物**：成片、发布包都留本机。

元数据只回答「这一期叫什么、封面取哪一帧、两个平台的文案是什么」，
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
PLATFORM_SPECS = {
    "channels": {
        "required": ("title", "description", "topics"),
        "text_limits": {"title": "title_chars", "description": "description_chars"},
        "list_limits": {"topics": ("topics_max", "topic_chars")},
        "int_fields": (),
    },
    "bilibili": {
        "required": ("title", "description", "tags", "tid", "copyright", "no_reprint"),
        "text_limits": {"title": "title_chars", "description": "description_chars"},
        "list_limits": {"tags": ("tags_chars", "tag_chars")},
        "int_fields": ("tid", "copyright", "no_reprint"),
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
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise MetaError(f"发布元数据必须是对象：{path}")
    channels = raw.get("channels")
    bilibili = raw.get("bilibili")
    return EpisodeMeta(
        episode=str(raw.get("episode", "")),
        title=str(raw.get("title", "")),
        cover_at=float(raw.get("cover_at", -1.0)),
        url=str(raw.get("url", "")),
        channels=channels if isinstance(channels, dict) else None,
        bilibili=bilibili if isinstance(bilibili, dict) else None,
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

    for field_name, (total_key, item_key) in spec["list_limits"].items():
        total_limit = limits.get(total_key)
        item_limit = limits.get(item_key)
        if total_limit is None or item_limit is None:
            findings.append(Finding(
                "epmeta.limits", ERROR,
                f"{platform} 的能力声明缺少 {total_key} / {item_key}", target))
            continue
        items = section.get(field_name) or []
        if not isinstance(items, list):
            findings.append(Finding(
                "epmeta.platform-required", ERROR,
                f"{platform} 的 {field_name} 必须是列表", target))
            continue
        if len(items) > total_limit:
            findings.append(Finding(
                "epmeta.list-limit", ERROR,
                f"{platform} 的 {field_name} 有 {len(items)} 项，超过上限 {total_limit}",
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
    return findings
