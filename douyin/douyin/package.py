"""出包：把一期变成一个「照着做就能发完」的目录。

**出包前有三道闸。** 文案层（`pyv.epmeta.check_meta`）、技术层
（`pyv.preflight.check_video`）与抖音专属层（`douyin.contract`）各出一份 finding：

- `error` 级别 → **报错并停止**。不静默出包——发不出去的包出了也是白出，
  问题会被推到人工点发布那一步才爆出来。
- `warning` 级别 → **告警但继续**，并且写进 `publish.md` 清单，
  让出包的人看得见。

抖音专属那两道闸为什么不能并进前两层：

- **拼装后的 `text` 总长**：`pyv.epmeta` 逐字段查，查不出「三段加起来超了」。
- **站外引流**：`pyv.epmeta` 不知道抖音禁这个。这是平台规则，不是元数据格式。

判定只有 `pyv` 那一份，adapter 不自己判技术门槛：两个地方各判一次会出现
两个结论，门槛数字也会漂（规格 §6.1.3）。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from pyv import epmeta, preflight

from douyin import assets, contract, snapshot, state

# 仓库根：douyin/douyin/package.py → douyin/douyin → douyin → 仓库根
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


def _checklist(episode: str, copy: contract.DouyinCopy,
               info: preflight.VideoInfo, text: str,
               warnings: list[str]) -> str:
    topics = contract.topics_line(copy.topics)
    lines = [
        f"# 待发布：{copy.title}（{episode}）",
        "",
        "| 项 | 值 |",
        "| --- | --- |",
        f"| 视频 | `video.mp4`（{info.duration:.1f} s，{info.width}×{info.height}，"
        f"**竖版 9:16 · 无品牌导流版**） |",
        f"| 标题 | {copy.title}（{len(copy.title)} 字） |",
        f"| 正文 | {len(copy.description)} 字 |",
        f"| 话题 | {topics or '（无）'} |",
        f"| 整段文案 | {len(text)} 字（上限 1000） |",
        "| 封面 | `cover.jpg`（与成片同比例） |",
        "",
        "## 步骤",
        "",
        "- [ ] 打开抖音创作者平台 → 发布视频",
        "- [ ] 上传 `video.mp4`",
        "- [ ] 粘贴 `text.txt` 的**整段内容**（标题、正文、话题已经拼好了）",
        "- [ ] 选封面：`cover.jpg`，或直接用平台自动生成的首帧",
        "- [ ] 发布",
        "- [ ] 回填链接："
        f"`python -m douyin.cli mark published {episode} --url \"<链接>\"`",
        "",
        "> **文案原样贴，别自己加东西。** 抖音禁站外引流与过度营销——"
        "在文案里加网址、微信号、QQ、电话，都是最常见的限流原因。"
        "要补充信息，发在评论区。",
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


def _douyin_limits_loader(capabilities_dir: str | Path | None):
    """能力声明的读法。默认读仓库里那份 `publish/capabilities/`。"""
    if capabilities_dir is None:
        return epmeta.load_limits
    base = Path(capabilities_dir)

    def load(platform: str) -> dict:
        return epmeta.load_limits(platform, base)

    return load


def _douyin_only(meta: epmeta.EpisodeMeta) -> epmeta.EpisodeMeta:
    """只留抖音那一段。

    `check_meta` 会把各平台都看一遍，但抖音的 adapter 只对抖音负责——
    「这一期没配 B站文案」不是抖音的发布问题，不该进抖音的清单。
    """
    return epmeta.EpisodeMeta(
        episode=meta.episode, title=meta.title, cover_at=meta.cover_at,
        url=meta.url, douyin=meta.douyin, path=meta.path)


def _for_douyin(findings: list) -> list:
    """只留抖音自己的 finding。"""
    kept = []
    for finding in findings:
        if (finding.rule_id == "epmeta.platform-missing"
                and "douyin" not in finding.message):
            continue
        kept.append(finding)
    return kept


def _douyin_rule_findings(text: str, limits: dict, episode: str) -> list:
    """抖音专属的两道闸。

    这两条是平台规则，`pyv.epmeta` 不知道——它管的是元数据的形状与各段上限，
    管不了「拼起来超了」与「文案里有站外引流」。
    """
    findings = []
    for message in contract.check_text_length(text, limits):
        findings.append(epmeta.Finding(
            "douyin.text-limit", epmeta.ERROR, message, episode))
    for message in contract.check_no_outbound(text):
        findings.append(epmeta.Finding(
            "douyin.outbound-link", epmeta.ERROR, message, episode))
    return findings


def _limits_or_empty(limits_loader, platform: str) -> dict:
    """读能力声明的 `[limits]`；读不到就当空。

    读不到时**已经**有 finding 报出来了（`check_meta` 里的 `epmeta.limits`），
    出包会被拦住。这里再抛一次异常只是把同一个问题报两遍——而且换个
    方式报（traceback 而不是 finding）。
    """
    try:
        return limits_loader(platform)
    except epmeta.MetaError:
        return {}


def preflight_findings(meta: epmeta.EpisodeMeta, info: preflight.VideoInfo,
                       episode: str,
                       capabilities_dir: str | Path | None = None) -> list:
    """出包前的预检：文案层 + 技术层 + 抖音专属层。

    返回的 finding 里 `error` 的必须先改，`warning` 的要写进清单。
    """
    limits_loader = _douyin_limits_loader(capabilities_dir)
    findings = epmeta.check_meta(
        _douyin_only(meta),
        contract_episode=episode,
        duration=info.duration,
        limits_loader=limits_loader,
    )
    findings = _for_douyin(findings)
    findings.extend(preflight.check_video(info, "douyin", capabilities_dir))

    copy = contract.slice_copy(meta)
    text = contract.build_text(copy)
    findings.extend(
        _douyin_rule_findings(
            text, _limits_or_empty(limits_loader, "douyin"), episode))
    return findings


def build_package(episode: str, meta: epmeta.EpisodeMeta, video: str | Path,
                  out_root: str | Path,
                  capabilities_dir: str | Path | None = None,
                  outbox_dir: str | Path | None = None) -> PackageResult:
    """出一期在抖音上的发布包。"""
    copy = contract.slice_copy(meta)
    text = contract.build_text(copy)
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
        assets.make_cover(video_path, copy.cover_at, target)
        link = target / "video.mp4"
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(video_path.resolve())

        names = ("video.mp4", "cover.jpg", "title.txt", "description.txt",
                 "topics.txt", "text.txt", "publish.md")
        files = {name: target / name for name in names}

    # **文案每次都按当前元数据重写。**
    # 成片没变 ≠ 文案没变：改了标题再重跑，必须出新标题。
    # 否则包里的文案停在旧版本，而命令还报「成功」——那是静默成功。
    (target / "title.txt").write_text(copy.title, encoding="utf-8")
    (target / "description.txt").write_text(copy.description, encoding="utf-8")
    (target / "topics.txt").write_text(
        contract.topics_line(copy.topics), encoding="utf-8")
    # text.txt 是平台真正要的那一个字段：标题、正文、话题拼好的整段。
    (target / "text.txt").write_text(text, encoding="utf-8")
    (target / "publish.md").write_text(
        _checklist(episode, copy, info, text, warnings), encoding="utf-8")

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
            "text_chars": len(text),
            # 人工发布这一步没做完，状态就只能是「待上传」。
            "status": status,
            "published_url": published_url,
        }, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    store.save(episode, state.DouyinState(
        episode=episode, video_sha256=digest, status=status,
        published_url=published_url,
    ))

    reason = {
        "packaged": "开放平台发布能力需企业主体，已出包待人工上传",
        "published": "人工发布后回填",
    }.get(status, "人工发布后回填")
    outbox = Path(outbox_dir) if outbox_dir else snapshot.OUTBOX_DIR
    snapshot.write_snapshot(
        outbox / f"{episode}__douyin.json",
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
