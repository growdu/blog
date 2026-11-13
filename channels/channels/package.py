"""出包：把一期变成一个「照着做就能发完」的目录。

产物结构见规格 §6.1.2。幂等靠成片的 sha256——
成片没变就不重出，成片变了就重出。

**出包前有两道闸。** 文案层（`pyv.epmeta.check_meta`）与技术层
（`pyv.preflight.check_video`）各出一份 finding：

- `error` 级别 → **报错并停止**。不静默出包——发不出去的包出了也是白出，
  问题会被推到人工点发布那一步才爆出来。
- `warning` 级别 → **告警但继续**，并且写进 `publish.md` 清单，
  让出包的人看得见。

判定只有 `pyv` 那一份，adapter 不自己判：两个地方各判一次会出现两个结论，
门槛数字也会漂（规格 §6.1.3）。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from pyv import epmeta, preflight

from channels import assets, contract, snapshot, state

# 仓库根：channels/channels/package.py → channels/channels → channels → 仓库根
REPO_ROOT = Path(__file__).resolve().parents[2]


def repo_relative(path: str | Path, root: str | Path | None = None) -> str:
    """把路径写成相对仓库根的形式。

    快照要入库。绝对路径换台机器就对不上，还把本机信息带进了库。
    """
    base = Path(root) if root else REPO_ROOT
    return os.path.relpath(Path(path).resolve(), base.resolve())


class PackageError(RuntimeError):
    """出不了包：有硬约束违规（预检里 error 级别的 finding）。"""

    def __init__(self, findings):
        self.findings = list(findings)
        detail = "；".join(str(f) for f in self.findings)
        super().__init__(f"预检未通过（{len(self.findings)} 条）：{detail}")


@dataclass
class PackageResult:
    """一次出包的结果。"""

    episode: str
    dir: Path
    files: dict[str, Path] = field(default_factory=dict)
    video_sha256: str = ""
    status: str = "packaged"
    reason: str = ""
    reused: bool = False
    warnings: list[str] = field(default_factory=list)


def _checklist(episode: str, copy: contract.ChannelsCopy,
               info: preflight.VideoInfo, warnings: list[str]) -> str:
    topics = contract.topics_line(copy.topics)
    lines = [
        f"# 待发布：{copy.title}（{episode}）",
        "",
        "| 项 | 值 |",
        "| --- | --- |",
        f"| 视频 | `video.mp4`（{info.duration:.1f} s，{info.width}×{info.height}） |",
        f"| 标题 | {copy.title}（{len(copy.title)} 字） |",
        f"| 话题 | {topics or '（无）'} |",
        "| 封面 | `cover-4x3.jpg`（分享卡片）/ `cover-3x4.jpg`（个人主页卡片） |",
        "| 原创声明 | 勾选 |",
        "",
        "## 步骤",
        "",
        "- [ ] 打开视频号助手 → 发布视频",
        "- [ ] 上传 `video.mp4`",
        "- [ ] 粘贴短标题与简介，补上 # 话题",
        "- [ ] 选封面（分享卡片用 `cover-4x3.jpg`，个人主页卡片用 `cover-3x4.jpg`；"
        "也可以直接用平台自动生成的那两张）",
        "- [ ] 勾选「声明原创」",
        "- [ ] 发表",
        "- [ ] 回填链接："
        f"`python -m channels.cli mark published {episode} --url \"<链接>\"`",
        "",
    ]
    if warnings:
        lines += ["## 预检告警", ""]
        lines += [f"- ⚠️ {warning}" for warning in warnings]
        lines += [""]
    lines += [
        "> **待你上传。** 这一步没做完之前，状态只能写「待上传」。",
        "",
    ]
    return "\n".join(lines)


def _channels_limits_loader(capabilities_dir: str | Path | None):
    """能力声明的读法。默认读仓库里那份 `publish/capabilities/`。"""
    if capabilities_dir is None:
        return epmeta.load_limits
    base = Path(capabilities_dir)

    def load(platform: str) -> dict:
        return epmeta.load_limits(platform, base)

    return load


def _channels_only(meta: epmeta.EpisodeMeta) -> epmeta.EpisodeMeta:
    """只留视频号那一段。

    `check_meta` 会把两个平台都看一遍，但视频号的 adapter 只对视频号负责——
    「这一期没配 B 站文案」不是视频号的发布问题，不该进视频号的清单。
    """
    return epmeta.EpisodeMeta(
        episode=meta.episode, title=meta.title, cover_at=meta.cover_at,
        url=meta.url, channels=meta.channels, bilibili=None, path=meta.path)


def _for_channels(findings: list) -> list:
    """只留视频号自己的 finding。"""
    kept = []
    for finding in findings:
        if (finding.rule_id == "epmeta.platform-missing"
                and "channels" not in finding.message):
            continue
        kept.append(finding)
    return kept


def preflight_findings(meta: epmeta.EpisodeMeta, info: preflight.VideoInfo,
                       episode: str,
                       capabilities_dir: str | Path | None = None) -> list:
    """出包前的预检：文案层 + 技术层。

    返回的 finding 里 `error` 的必须先改，`warning` 的要写进清单。
    """
    findings = epmeta.check_meta(
        _channels_only(meta),
        contract_episode=episode,
        duration=info.duration,
        limits_loader=_channels_limits_loader(capabilities_dir),
    )
    findings = _for_channels(findings)
    findings.extend(preflight.check_video(info, "channels", capabilities_dir))
    return findings


def build_package(episode: str, meta: epmeta.EpisodeMeta, video: str | Path,
                  out_root: str | Path,
                  capabilities_dir: str | Path | None = None,
                  outbox_dir: str | Path | None = None) -> PackageResult:
    """出一期在视频号上的发布包。"""
    copy = contract.slice_copy(meta)
    video_path = Path(video)
    if not video_path.is_file():
        raise FileNotFoundError(f"成片不存在：{video_path}")

    info = preflight.probe(video_path)
    findings = preflight_findings(meta, info, episode, capabilities_dir)
    errors = [f for f in findings if f.level == epmeta.ERROR]
    if errors:
        # 有硬约束违规就不出包——宁可现在报错，也不要出一个发不出去的包。
        raise PackageError(errors)
    warnings = [str(f) for f in findings if f.level != epmeta.ERROR]

    out_root = Path(out_root)
    target = out_root / episode
    store = state.StateStore(out_root / "state.json")
    previous = store.get(episode)
    digest = preflight.file_sha256(video_path)

    files: dict[str, Path] = {}
    reused = False
    if previous.video_sha256 == digest and (target / "meta.json").is_file():
        # 成片没变：抽帧与软链复用，不重做费事的那部分。
        reused = True
        meta_file = json.loads((target / "meta.json").read_text(encoding="utf-8"))
        files = {name: target / name for name in meta_file["files"]}
    else:
        target.mkdir(parents=True, exist_ok=True)
        assets.make_covers(video_path, copy.cover_at, target)
        link = target / "video.mp4"
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(video_path.resolve())

        names = ("video.mp4", "cover-4x3.jpg", "cover-3x4.jpg",
                 "title.txt", "description.txt", "topics.txt", "publish.md")
        files = {name: target / name for name in names}

    # **文案每次都按当前元数据重写。**
    # 成片没变 ≠ 文案没变：改了标题再重跑，必须出新标题。
    # 否则包里的文案停在旧版本，而命令还报「成功」——那是静默成功。
    (target / "title.txt").write_text(copy.title, encoding="utf-8")
    (target / "description.txt").write_text(copy.description, encoding="utf-8")
    (target / "topics.txt").write_text(
        contract.topics_line(copy.topics), encoding="utf-8")
    (target / "publish.md").write_text(
        _checklist(episode, copy, info, warnings), encoding="utf-8")

    # 人工回填的发布状态不能被出包抹掉。
    # 成片没变 → 之前发出去的就是这一条，状态保留；
    # 成片变了 → 发出去的是另一条片子，状态回到「待上传」。
    if reused:
        status = previous.status
        published_url = previous.published_url
    else:
        status = "packaged"
        published_url = None

    (target / "meta.json").write_text(
        json.dumps({
            "episode": episode,
            "video_sha256": digest,
            "files": sorted(files),
            "cover_at": copy.cover_at,
            # 人工发布这一步没做完，状态就只能是「待上传」。
            "status": status,
            "published_url": published_url,
        }, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    store.save(episode, state.ChannelState(
        episode=episode, video_sha256=digest, status=status,
        published_url=published_url,
    ))

    reason = {
        "packaged": "视频号无公开发布接口，已出包待人工上传",
        "drafted": "已存草稿，待人工发表",
    }.get(status, "人工发布后回填")
    outbox = Path(outbox_dir) if outbox_dir else snapshot.OUTBOX_DIR
    snapshot.write_snapshot(
        outbox / f"{episode}__channels.json",
        episode=episode, status=status, title=copy.title,
        package_dir=repo_relative(target), published_url=published_url,
        reason=reason,
    )
    return PackageResult(
        episode=episode, dir=target, files=files, video_sha256=digest,
        status=status, reason=reason, reused=reused, warnings=warnings,
    )


def mark_published(target: str | Path, url: str) -> Path:
    """回填发布链接：包里的机器可读快照也跟着更新。"""
    directory = Path(target)
    path = directory / "meta.json"
    if not path.is_file():
        raise FileNotFoundError(f"发布包不存在：{directory}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = "published"
    data["published_url"] = url
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def mark_drafted(target: str | Path) -> Path:
    """回填「已存草稿」：草稿已在平台上，等人点发表。

    **和 `published` 是两回事。** 草稿还没发出去，所以 `published_url` 要清掉——
    留着旧链接会让人以为这条已经发出去了（头条号那边就踩过同一个坑：
    `drafted` 被读成「还没发」或「已发」都会导致重发）。
    """
    directory = Path(target)
    path = directory / "meta.json"
    if not path.is_file():
        raise FileNotFoundError(f"发布包不存在：{directory}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = "drafted"
    data["published_url"] = None
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path
