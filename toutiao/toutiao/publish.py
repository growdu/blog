"""Produce the Toutiao publish package and the cross-platform status snapshot.

In ``manual`` mode nothing is uploaded: the package is written to disk and a
human uploads it.  That is the current state of affairs -- the account has
no open-platform API permission -- and it is enough to start publishing.

Two artefacts come out of here:

- the package (``<package_root>/<flatten_id>/``): the rendered article, the
  pictures as webp, the cover, the title, and the checklist the uploader
  works through;
- the snapshot (``<outbox_dir>/<flatten_id>__<platform>.json``): the public
  record the site index is built from.

The picture numbering is the delicate part.  A placeholder in the body is
``【图N】``, and ``N`` is the number the *slicer* gave that picture -- not
the position of the file in the package.  A picture that is remote, missing
or unreadable has no file, but it keeps its number: the gap in ``images/``
is the gap in the body, and the uploader has to see both.

A post whose body was cut by the 3000-character cap is the case that
breaks the naive reading: the slicer keeps the picture in
``article.images`` while the placeholder is gone from the body.  The
package therefore follows the placeholders that are *in the body* and packs
only those -- a file the body never refers to is a picture nobody asked
for.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .assets import (
    AssetNotFound,
    ImageTooLarge,
    RemoteAsset,
    UnreadableImage,
    can_make_cover,
    is_remote,
    make_cover,
    prepare_image,
    resolve_asset,
)
from .capability import Capability
from .contract import ToutiaoArticle
from .render import RenderResult, render

__all__ = [
    "PackageResult", "flatten_id", "snapshot_name", "write_package",
    "write_snapshot",
]

# The repository root -- the parent of the ``toutiao`` package directory.
# The snapshot is public, so the package path it carries has to be
# relative: an absolute path would publish the layout of the machine that
# produced it.
_REPO_ROOT = Path(__file__).resolve().parents[2]

# The picture placeholder the slicer leaves behind.
_MARKER = re.compile(r"【图(\d+)】")

# The head of the upload checklist.
README_HEAD = "# 上传清单：{}\n\n"

# 「没有封面」的三种原因，写法各不相同 —— 把「没有文件可裁」说成
# 「裁不出来」是错的：前者要人工下载，后者要人工另配。
#
# ① 正文里根本没有图。
NO_COVER_NOTE = (
    "这篇没有正文图：按头条的「无图」模式发布；若后台强制要封面，需人工另配"
)
# ② 正文图全是外链：出包不下载外链图，就没有本地文件可裁。
NO_COVER_REMOTE_ONLY_NOTE = (
    "正文图都是外链，出包不下载，没有本地文件可裁："
    "可按上面「远程图」那一行人工下载后自行裁成 {ratio}（≥{min_pixels}），"
    "或按头条的「无图」模式发布"
)
# ③ 有本地图，但一张都裁不出合规封面。
NO_COVER_UNCROPPABLE_NOTE = (
    "正文图都裁不出合规封面（{ratio} 且 ≥{min_pixels}）："
    "可人工另配，或按头条的「无图」模式发布"
)


@dataclass(frozen=True)
class PackageResult:
    """What the manual path produced for one article."""

    content_id: str
    platform: str
    automation: str
    status: str
    title: str
    package_dir: Path
    files: tuple[str, ...]
    reason: str | None = None


def flatten_id(content_id: str) -> str:
    """Turn a site slug into a filesystem- and filename-safe id.

    A content id is a path inside the site (``db/postgresql/demo``), and
    a path cannot go into a file name: the slashes would scatter the
    package into subdirectories and the snapshot into a tree.
    """
    return content_id.replace("/", "-")


def snapshot_name(content_id: str, platform: str) -> str:
    """The outbox file name for one content id on one platform."""
    return "{}__{}.json".format(flatten_id(content_id), platform)


def _marker_numbers(article: ToutiaoArticle, rendered: RenderResult) -> list[int]:
    """The picture numbers the body carries, ascending.

    ``render()`` reports the placeholders it saw, but it skips the ones
    inside a code span -- a ``【图1】`` between backticks reads as a
    sample of the placeholder syntax there.  The slicer numbered that
    picture all the same (``_replace_inline_images()`` runs before the
    code spans are protected), so the body scan is the wider set and the
    two are merged here.
    """
    numbers = {int(match.group(1)) for match in _MARKER.finditer(article.body)}
    for marker in rendered.image_markers:
        match = _MARKER.fullmatch(marker)
        if match:
            numbers.add(int(match.group(1)))
    return sorted(numbers)


def _reset_package(package_dir: Path, images_dir: Path) -> None:
    """Take the files of a previous run away.

    Re-packaging an article whose pictures shrank must not leave the old
    ones behind: a picture the body does not refer to is a picture the
    uploader would upload for nothing, and a leftover cover would claim a
    cover this version does not have.  Only the files this module writes
    are removed -- the package directory itself stays.
    """
    if images_dir.is_dir():
        for path in images_dir.glob("*.webp"):
            path.unlink()
    (package_dir / "cover.webp").unlink(missing_ok=True)


def _package_files(package_dir: Path) -> tuple[str, ...]:
    """Every file of the package, as a path relative to the package."""
    return tuple(sorted(
        path.relative_to(package_dir).as_posix()
        for path in package_dir.rglob("*")
        if path.is_file()
    ))


def _relative_package_dir(package_dir: Path) -> str:
    """The package directory as a path relative to the repository root.

    The snapshot is public, so an absolute path must never leave the
    machine that produced it.  Inside the repository the path reads
    ``toutiao/out/db-postgresql-demo``; outside it, only the directory
    name is kept.
    """
    package_dir = Path(package_dir)
    try:
        return package_dir.resolve().relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return package_dir.name


def write_package(
    article: ToutiaoArticle,
    capability: Capability,
    package_root: Path,
    posts_dir: Path,
    source_url: str = "https://growdu.cn",
) -> PackageResult:
    """Write the manual publish package for one article.

    A post without a body picture still gets a package: Toutiao has a
    no-picture mode, and 469 of the 542 publishable posts have no picture
    at all.  The checklist says so in as many words instead of pretending
    there is a cover.

    The pictures that need a human -- remote, missing, unreadable or too
    big -- never break the package.  They are listed in the checklist
    with their URL or path, and the article goes out anyway.
    """
    package_dir = Path(package_root) / flatten_id(article.content_id)
    images_dir = package_dir / "images"
    package_dir.mkdir(parents=True, exist_ok=True)
    _reset_package(package_dir, images_dir)

    limits = capability.limits
    site = source_url.split("://", 1)[-1].rstrip("/")

    rendered = render(article)
    (package_dir / "article.html").write_text(rendered.html + "\n", encoding="utf-8")
    (package_dir / "article.txt").write_text(rendered.text + "\n", encoding="utf-8")
    (package_dir / "title.txt").write_text(
        "{}\n{}\n".format(article.title, article.digest), encoding="utf-8"
    )

    # The pictures the body points at, in placeholder order.  ``article.images``
    # may hold more than the body refers to -- a body cut by the character
    # cap keeps the pictures but loses the placeholders -- and packing
    # those would put files in the package that nothing refers to.
    numbers = _marker_numbers(article, rendered)
    body_images: list[tuple[int, str]] = []
    missing: list[str] = []
    orphans: list[int] = []
    for number in numbers:
        if number > len(article.images):
            # A placeholder without a picture: the slicer does not do
            # this, but it must not be dropped silently either.
            orphans.append(number)
            continue
        body_images.append((number, article.images[number - 1]))

    prepared = []
    remote: list[str] = []
    unreadable: list[str] = []
    oversized: list[str] = []
    for number, relative in body_images:
        if is_remote(relative):
            # 外链图不下载 —— 出包不依赖网络，交给人工。
            remote.append(relative)
            continue
        try:
            source = resolve_asset(relative, posts_dir)
        except RemoteAsset:
            remote.append(relative)
            continue
        except AssetNotFound:
            # 找不到的图不静默丢：路径收进清单，附上路径。
            missing.append(relative)
            continue
        try:
            info = prepare_image(
                source, images_dir / "{:02d}.webp".format(number), limits.image_bytes
            )
        except UnreadableImage:
            # 读不了的格式（如 SVG）—— 不当失败，列进清单交给人工。
            unreadable.append(relative)
            continue
        except ImageTooLarge:
            # 压不进上限的图 —— 同样不当失败：这一篇照样能发。
            oversized.append(relative)
            continue
        prepared.append(info)

    # 封面取「第一张能裁出合规封面的正文图」—— 第一张裁不动、第二张能裁时
    # 要用第二张。判定用的是已转好的 webp：prepare_image() 压不进时会缩一半，
    # 原图能裁不代表 webp 能裁，拿 webp 判两边才一致。
    cover_written = False
    for info in prepared:
        try:
            if not can_make_cover(
                info.path, limits.cover_ratio, limits.cover_min_pixels
            ):
                continue
            make_cover(
                info.path,
                package_dir / "cover.webp",
                limits.cover_ratio,
                limits.cover_min_pixels,
            )
        except ValueError:
            # 判定与裁切用的是同一把尺子，这里不该再失败；失败就换下一张。
            continue
        cover_written = True
        break

    checklist = [
        "- [ ] 打开头条号后台 → 发文章",
        "- [ ] 标题：复制 `title.txt` 第一行（{} 字以内）".format(limits.title_chars),
        "- [ ] 正文：把 `article.html` 粘贴到编辑器（若排版丢失，改用 `article.txt`）",
    ]

    markers = "、".join("【图{}】".format(number) for number in numbers)
    if numbers:
        if prepared:
            picture_line = (
                "- [ ] 图片：上传 `images/` 里的 {} 张图，文件名 NN 对应正文里的【图NN】；"
                "正文里的占位符是 {}".format(len(prepared), markers)
            )
            if len(prepared) < len(numbers):
                picture_line += "（没有文件的占位符见下面几行）"
        else:
            picture_line = (
                "- [ ] 图片：出包没有备好图，正文里的占位符是 {}；"
                "按下面几行逐张人工处理".format(markers)
            )
        checklist.append(picture_line)

    local_images = [
        relative for _, relative in body_images if not is_remote(relative)
    ]
    if cover_written:
        checklist.append(
            "- [ ] 封面：上传 `cover.webp`（{}，不小于 {}）".format(
                limits.cover_ratio, "{0}×{1}".format(*limits.cover_min_pixels)
            )
        )
    elif not body_images:
        # ① 正文里根本没有图。
        checklist.append("- [ ] 封面：{}".format(NO_COVER_NOTE))
    elif not local_images:
        # ② 正文图全是外链：出包不下载外链图，没有本地文件可裁。
        checklist.append("- [ ] 封面：{}".format(NO_COVER_REMOTE_ONLY_NOTE.format(
            ratio=limits.cover_ratio,
            min_pixels="{0}×{1}".format(*limits.cover_min_pixels),
        )))
    else:
        # ③ 有本地图但一张都裁不出合规封面 —— 与前两种分开说。
        checklist.append("- [ ] 封面：{}".format(NO_COVER_UNCROPPABLE_NOTE.format(
            ratio=limits.cover_ratio,
            min_pixels="{0}×{1}".format(*limits.cover_min_pixels),
        )))

    if remote:
        checklist.append(
            "- [ ] 远程图（需人工下载）：出包不下载外链图，这 {} 张要人工下载后上传：{}".format(
                len(remote), "、".join(remote)
            )
        )
    if missing:
        checklist.append(
            "- [ ] 缺图（需人工核对）：出包时找不到这 {} 个文件，需人工核对路径：{}".format(
                len(missing), "、".join(missing)
            )
        )
    if unreadable:
        checklist.append(
            "- [ ] 读不了的图：出包时无法转换这 {} 个文件（Pillow 读不了，"
            "可能是 SVG 等格式），需人工处理：{}".format(
                len(unreadable), "、".join(unreadable)
            )
        )
    if oversized:
        checklist.append(
            "- [ ] 超限的图：出包时压不进 {} 字节上限，这 {} 个文件需人工处理：{}".format(
                limits.image_bytes, len(oversized), "、".join(oversized)
            )
        )

    checklist.append(
        "- [ ] 检查正文末尾是纯文本「完整版见 {}」，不是超链接".format(site)
    )
    checklist.append("- [ ] 发表")

    notes = list(article.notes)
    referenced = sum(1 for number in numbers if number <= len(article.images))
    if len(article.images) > referenced:
        notes.append(
            "另有 {} 张图没有进入正文（正文里没有它们的占位符），未打包".format(
                len(article.images) - referenced
            )
        )
    if orphans:
        notes.append(
            "正文里的 {} 在切片里没有对应的图".format(
                "、".join("【图{}】".format(number) for number in orphans)
            )
        )

    readme = README_HEAD.format(article.title) + "\n".join(checklist) + "\n"
    if notes:
        readme += "\n## 切片备注\n\n" + "\n".join("- " + note for note in notes) + "\n"
    (package_dir / "README.md").write_text(readme, encoding="utf-8")

    # 「packaged」不是「已发布」：manual 档下这一篇还在等一个人把它传上去，
    # 快照里要说清楚，免得站点索引把它当成已发。
    reason = None
    if capability.automation == "manual":
        reason = "manual 档：账号暂无开放平台 API 权限，已出包待人工上传"

    return PackageResult(
        content_id=article.content_id,
        platform=capability.id,
        automation=capability.automation,
        status="packaged",
        title=article.title,
        package_dir=package_dir,
        files=_package_files(package_dir),
        reason=reason,
    )


def write_snapshot(result: PackageResult, outbox_dir: Path) -> Path:
    """Write the cross-platform status snapshot for one article.

    The snapshot ends up in the site index, so it carries public
    information only: no token, no secret, and no absolute path of the
    machine that produced it.
    """
    outbox_dir = Path(outbox_dir)
    outbox_dir.mkdir(parents=True, exist_ok=True)
    path = outbox_dir / snapshot_name(result.content_id, result.platform)
    payload = {
        "content_id": result.content_id,
        "platform": result.platform,
        "status": result.status,
        "automation": result.automation,
        "title": result.title,
        "published_url": None,
        "package_dir": _relative_package_dir(result.package_dir),
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "reason": result.reason,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
