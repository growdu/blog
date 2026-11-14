"""出包：把一期变成一个「照着做就能发完」的目录。

产物结构见规格 §6.3。幂等靠成片的 sha256。

**出包前有两道闸。** 文案层（`pyv.epmeta.check_meta`）与技术层
（`pyv.preflight.check_video`）各出一份 finding：

- `error` 级别 → **报错并停止**。不静默出包——发不出去的包出了也是白出，
  问题会被推到人工点发布那一步才爆出来。
- `warning` 级别 → **告警但继续**，并且写进 `publish.md` 清单，
  让出包的人看得见。

判定只有 `pyv` 那一份，adapter 不自己判：两个地方各判一次会出现两个结论，
门槛数字也会漂（规格 §5.2）。

**幂等的三件事**（规格 §7.1）：抽帧与软链绑成片 sha256（复用），
文案绑当前元数据（每次重写），发布状态绑成片 sha256（保留）。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from pyv import epmeta, preflight

from bilibili import assets, contract, snapshot, state, subtitle

# 仓库根：bilibili/bilibili/package.py → bilibili/bilibili → bilibili → 仓库根
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


def _checklist(episode: str, copy: contract.BiliCopy,
               info: preflight.VideoInfo, warnings: list[str]) -> str:
    tags = contract.tags_line(copy.tags)
    lines = [
        f"# 待发布：{copy.title}（{episode}）",
        "",
        "| 项 | 值 |",
        "| --- | --- |",
        f"| 视频 | `video.mp4`（{info.duration:.1f} s，{info.width}×{info.height}） |",
        f"| 标题 | {copy.title}（{len(copy.title)} 字） |",
        f"| 分区 | tid = {copy.tid} |",
        f"| 标签 | {tags} |",
        f"| 简介 | {copy.description[:40]}… |" if len(copy.description) > 40
        else f"| 简介 | {copy.description} |",
        "| 封面 | `cover.jpg` |",
        "| 字幕 | `subtitle.srt`（有的话一起传） |",
        f"| 原创 | {'原创' if copy.copyright == 1 else '转载'} |",
        f"| 允许转载 | {'否' if copy.no_reprint == 1 else '是'} |",
        "",
        "## 步骤",
        "",
        "- [ ] 打开B站创作中心 → 投稿",
        "- [ ] 上传 `video.mp4`",
        "- [ ] 填标题、简介、标签，选对分区",
        "- [ ] 上传 `cover.jpg` 作封面",
        "- [ ] 有 `subtitle.srt` 的话传上字幕",
        "- [ ] 声明原创，确认不允许转载",
        "- [ ] 提交投稿",
        "- [ ] 回填链接："
        f"`python -m bilibili.cli mark published {episode} --url \"<链接>\"`",
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


def _bilibili_limits_loader(capabilities_dir: str | Path | None):
    """能力声明的读法。默认读仓库里那份 `publish/capabilities/`。"""
    if capabilities_dir is None:
        return epmeta.load_limits
    base = Path(capabilities_dir)

    def load(platform: str) -> dict:
        return epmeta.load_limits(platform, base)

    return load


def _bilibili_only(meta: epmeta.EpisodeMeta) -> epmeta.EpisodeMeta:
    """只留B站那一段。

    `check_meta` 会把两个平台都看一遍，但B站的 adapter 只对B站负责——
    「这一期没配视频号文案」不是B站的发布问题，不该进B站的清单。
    """
    return epmeta.EpisodeMeta(
        episode=meta.episode, title=meta.title, cover_at=meta.cover_at,
        url=meta.url, channels=None, bilibili=meta.bilibili, path=meta.path)


def _for_bilibili(findings: list) -> list:
    """只留B站自己的 finding。"""
    kept = []
    for finding in findings:
        if (finding.rule_id == "epmeta.platform-missing"
                and "bilibili" not in finding.message):
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
        _bilibili_only(meta),
        contract_episode=episode,
        duration=info.duration,
        limits_loader=_bilibili_limits_loader(capabilities_dir),
    )
    findings = _for_bilibili(findings)
    findings.extend(preflight.check_video(info, "bilibili", capabilities_dir))
    return findings


def build_package(episode: str, meta: epmeta.EpisodeMeta, video: str | Path,
                  out_root: str | Path,
                  subtitle_events: Sequence[subtitle.SubtitleEventLike] | None = None,
                  capabilities_dir: str | Path | None = None,
                  outbox_dir: str | Path | None = None) -> PackageResult:
    """出一期在B站上的发布包。

    `subtitle_events` 给了就把字幕转成 `subtitle.srt` 一并放进包里。

    **参数是字幕事件，不是 storyboard 对象**：adapter 只能 import
    `pyv.epmeta` 与 `pyv.preflight`（规格 §3.3），碰不到 `pyv.timeline`。
    读 storyboard 的活儿由调用方（CLI）用 `subtitle.events_from_storyboard()` 做。
    """
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
    # 包里该有的东西。**清单、封面、软链一样都不能少**——少了就是
    # 一个发不出去的包，而命令会报「成功」。
    names = ["video.mp4", "cover.jpg", "title.txt", "description.txt",
             "tags.txt", "publish.md", "meta.json"]
    files = {name: target / name for name in names}

    reused = False
    if previous.video_sha256 == digest and (target / "meta.json").is_file():
        # 成片没变：抽帧与软链复用，不重做费事的那部分。
        # **但要复查包里东西还在不在**：软链会悬空（成片被删了/换了），
        # 别的文件也会被人手删。少了任何一件就重出——复用不是
        # 「目录还在就算数」。
        missing = sorted(name for name, path in files.items()
                         if not path.exists())
        if not missing:
            reused = True
    if not reused:
        target.mkdir(parents=True, exist_ok=True)
        assets.make_cover(video_path, copy.cover_at, target / "cover.jpg")
        link = target / "video.mp4"
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(video_path.resolve())
    else:
        # 封面重抽一次：包里那张是上一次抽的，而元数据里的取帧点可能改了。
        # 封面与 `meta.json` 记的 `cover_at` 对不上，人按清单选封面就会
        # 选错那一帧（清单说 1.0 秒，包里那张是 3 秒的）。
        assets.make_cover(video_path, copy.cover_at, target / "cover.jpg")

    # **文案每次都按当前元数据重写。**
    # 成片没变 ≠ 文案没变：改了标题再重跑，必须出新标题。
    # 否则包里的文案停在旧版本，而命令还报「成功」——那是静默成功。
    (target / "title.txt").write_text(copy.title, encoding="utf-8")
    (target / "description.txt").write_text(copy.description, encoding="utf-8")
    (target / "tags.txt").write_text(
        contract.tags_line(copy.tags), encoding="utf-8")
    (target / "publish.md").write_text(
        _checklist(episode, copy, info, warnings), encoding="utf-8")

    # 字幕跟着 storyboard 走：**有就每次重写**。
    # 字幕是本地产物，但清单里说「有的话一起传」——
    # 清单说有、包里没有，人传了个空字幕上去。
    # 反过来也一样：storyboard 没了却还留着旧字幕，人会传一个对不上的版本。
    if subtitle_events:
        srt_path = target / "subtitle.srt"
        srt_path.write_text(subtitle.build_srt(subtitle_events), encoding="utf-8")
        files["subtitle.srt"] = srt_path
    else:
        (target / "subtitle.srt").unlink(missing_ok=True)
        files.pop("subtitle.srt", None)

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

    store.save(episode, state.BiliState(
        episode=episode, video_sha256=digest, status=status,
        resource_id=previous.resource_id,
        published_url=published_url,
    ))

    reason = ("B站 ARC_BASE 权限未开通，已出包待人工上传" if status == "packaged"
              else "人工发布后回填")
    outbox = Path(outbox_dir) if outbox_dir else snapshot.OUTBOX_DIR
    snapshot.write_snapshot(
        outbox / f"{episode}__bilibili.json",
        episode=episode, status=status, title=copy.title,
        package_dir=repo_relative(target), published_url=published_url,
        reason=reason,
        # 档位从**同一份**能力声明里读——写死的话，改完 TOML 快照还在说旧档位。
        automation=snapshot.automation_of(capabilities_dir),
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
