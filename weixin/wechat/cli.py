"""Command line entry point for the WeChat publishing pipeline.

Commands:

    scan                        list every post and whether it may be published
    audit                       recompute the corpus statistics in weixin/docs/
    convert <slug>              convert one post, write the HTML, touch no network
    publish <slug>              convert, upload, and create a draft
    publish <slug> --publish    also submit the draft for publishing
    status                      show the recorded state of every post

The default target is the draft box on purpose.  WeChat revoked the
freepublish endpoint for some account types in July 2025, and the draft
box is a useful human review gate either way.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import os
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import assets as assets_module
from . import audit as audit_module
from . import brand as brand_module
from . import collection as collection_module
from . import cover as cover_module
from . import digest as digest_module
from . import mermaid as mermaid_module
from . import notify as notify_module
from . import publish as publish_module
from . import render as render_module
from . import split as split_module
from . import titles as titles_module
from . import version as version_module
from .mdparse import parse
from .posts import (AUTHOR_LIMIT, BODY_LIMIT, CONTENT_BYTES_LIMIT, CONTENT_LIMIT,
                    DIGEST_LIMIT, TITLE_LIMIT, check_eligibility, discover, load_post)
from .state import PublishState, StateStore, needs_submit

DEFAULT_POSTS_DIR = Path(__file__).resolve().parents[2] / "source" / "_posts"
DEFAULT_OUT_DIR = Path(__file__).resolve().parents[1] / "out"
DEFAULT_SOURCE_URL = "https://growdu.cn"
DEFAULT_SECRETS_FILE = Path(__file__).resolve().parents[1] / "secrets.json"
DEFAULT_COLLECTIONS_FILE = Path(__file__).resolve().parents[1] / "collections.json"
DEFAULT_REPO_DIR = Path(__file__).resolve().parents[2]
DEFAULT_STAMP_FILE = Path(__file__).resolve().parents[1] / "out" / ".auto-draft-stamp"
# The cover used when an article has no picture of its own.  Most of
# this corpus has none, and a draft with no cover is not something
# WeChat accepts.
DEFAULT_COVER = Path(__file__).resolve().parents[1] / "assets" / "default-cover.png"

EXIT_OK = 0
EXIT_NOT_FOUND = 1
EXIT_REJECTED = 2
EXIT_API_ERROR = 3

# Stands in for an externally hosted picture that could not be fetched and
# re-hosted on WeChat.  WeChat removes such pictures silently, so the
# reader gets a note instead of a paragraph that stops for no reason.
EXTERNAL_IMAGE_FALLBACK = (
    "<p style=\"color:#888;font-size:13px;\">"
    "（此处的原图未能转存，点击「阅读原文」查看完整图文）</p>"
)


def _resolve_post(posts_dir: Path, slug: str):
    """Find a post by slug, tolerating a missing or extra ``.md``."""
    path = posts_dir / (slug + ".md")
    if path.is_file():
        return load_post(path, posts_dir)
    matches = sorted(posts_dir.rglob(slug + ".md"))
    if matches:
        return load_post(matches[0], posts_dir)
    matches = sorted(posts_dir.rglob(slug))
    if matches:
        return load_post(matches[0], posts_dir)
    return None


def _category_tag(post, args) -> str:
    """The category line printed on an article, per ``--category-tag``.

    WeChat has no field for a category, so this line is the only place
    the classification can live.  With ``--category-tag none`` the
    article keeps exactly the body it had before.
    """
    if getattr(args, "category_tag", "top") == "none":
        return ""
    return collection_module.render_category_tag(post.categories)


@dataclass
class Branding:
    """The parts of a draft that say who wrote it.

    The title page the author wrote is lifted out of the body and
    becomes a card; the summary is taken from what the author wrote
    about the article; every part ends with a signature.  The preview
    and the drafts are made from the same one, so the two never
    disagree.
    """

    blocks: list
    card: str
    signature: str
    summary: str


def _branding(post, args) -> Branding:
    """The body of an article and the brand elements that go with it."""
    blocks = parse(post.body)
    byline = brand_module.title_page_of(blocks)
    summary = digest_module.article_digest(blocks)
    blocks = brand_module.strip_title_page(blocks)
    return Branding(
        blocks=blocks,
        card=brand_module.byline_html(byline),
        signature=brand_module.signature_html(args.author),
        summary=summary,
    )


def _prepare(post, args, resolver=None, highlight: bool = True):
    """Render one post and return the render result."""
    branding = _branding(post, args)
    tag = _category_tag(post, args)
    position = getattr(args, "category_tag", "top")
    result = render_module.render(
        branding.blocks, resolver=resolver, highlight=highlight,
        head_html=branding.card + (tag if position == "top" else ""),
        tail_html=tag if position == "bottom" else "",
    )
    result = replace(result, html=result.html + branding.signature)
    target_dir = Path(args.out_dir) / post.slug
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "article.html").write_text(result.html, encoding="utf-8")
    return result


def _effective_title(post) -> str:
    """The title the draft will carry.

    The editor takes 64 characters; a split article's parts are titled
    「标题（一）」, so the title they share leaves room for the suffix.
    A title that is too long is cut at a boundary that keeps the topic
    -- see ``wechat/titles``.
    """
    return titles_module.effective_title(post.title)


def _fingerprint(post, tag_html: str) -> str:
    """Content hash covering everything that ends up in the published body.

    The markdown on its own is not enough: the category tag is part of
    the content WeChat stores, so a changed tag has to invalidate the
    draft.  Otherwise the draft would be reused and the change would
    silently never reach the reader.

    The title counts too -- a split article is published under
    「标题（一）」, so renaming the article has to reach the drafts.
    The shortened title counts as well, but **only when it differs
    from the original**: adding it unconditionally would change the
    hash of every article, and the 463 drafts already in the box would
    all have to be re-sent for no change in their content.
    """
    digest = hashlib.sha256()
    digest.update(post.fingerprint.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(post.title.encode("utf-8"))
    digest.update(b"\x00")
    effective = _effective_title(post)
    if effective != post.title:
        digest.update(effective.encode("utf-8"))
        digest.update(b"\x00")
    digest.update(tag_html.encode("utf-8"))
    return digest.hexdigest()


def _mermaid_assets(post, args):
    blocks = parse(post.body)
    return mermaid_module.render_mermaid(blocks, Path(args.out_dir) / "mermaid")


class _Resolver:
    """Resolve a mermaid key to the PNG that was rendered for it."""

    def __init__(self, assets):
        self._assets = assets

    def mermaid_path(self, key):
        asset = self._assets.get(key)
        return asset.png if asset else None


def cmd_scan(args) -> int:
    posts = discover(args.posts_dir)
    eligible = 0
    print("共 {} 篇文章\n".format(len(posts)))
    for post in posts:
        result = check_eligibility(post)
        if result.ok:
            eligible += 1
            print("  [OK]   {}  ({} 字)".format(post.slug, len(post.body)))
        else:
            print("  [跳过] {}  -> {}".format(post.slug, "; ".join(result.reasons)))
    print("\n可发布 {} 篇，跳过 {} 篇".format(eligible, len(posts) - eligible))
    print("（预检只看标题与原始正文字数；渲染后仍可能超限，publish 时会再卡一次）")
    return EXIT_OK


def cmd_audit(args) -> int:
    """Recompute every number quoted in weixin/docs/."""
    report = audit_module.audit_corpus(args.posts_dir)

    print("语料: {} 篇, {} 个分类".format(report.posts, report.categories))
    print()
    print("闸门（逐层收紧，每层只数上一层放行的文章）:")
    print("  标题 <= {} 字符         放行 {:>4}  需要裁剪 {:>4}   ← 超长不再拦下，改裁剪".format(
        TITLE_LIMIT, report.title_ok, report.title_shortened))
    print("  原始正文 <= {} 字       放行 {:>4}  超长 {:>4}   ← 超长不再拦下，改拆分".format(
        BODY_LIMIT, report.raw_ok, report.raw_over))
    print("  渲染后 <= {} 字符       单篇放得下 {:>4}  需要拆 {:>4}".format(
        CONTENT_LIMIT, report.render_ok, report.render_over))
    print()
    print("可发布: {} 篇 ({:.1f}%)，草稿总数 {} 篇".format(
        report.publishable, report.publishable_ratio, report.split_parts))
    print("  其中需要拆成多篇: {} 篇".format(report.split_posts))
    print("  其中拆不开（单块就超限）: {} 篇".format(report.unsplittable))
    print("  其中只有关掉代码高亮才放得下: {} 篇".format(report.needs_plain_only))
    print()
    print("全语料口径:")
    print("  原始正文 <= {} 字       {:>4} 篇".format(BODY_LIMIT, report.raw_within))
    print("  渲染后放得下（带高亮）  {:>4} 篇".format(report.fit_highlight))
    print("  渲染后放得下（关高亮）  {:>4} 篇".format(report.fit_plain))
    print("  正文长度中位            带高亮 {} 字符, 关高亮 {} 字符".format(
        report.median_highlight, report.median_plain))
    print()
    print("（拆分数字按「无 mermaid 渲染器」估算：图按源码算，比真实流水线偏大）")
    print()
    print("字数分布:")
    for name, count in report.buckets.items():
        print("  {:<12} {:>4} 篇".format(name, count))
    print()
    if report.violations:
        print("HTML 合规问题 {} 篇:".format(len(report.violations)))
        for slug, problems in report.violations:
            print("  ! {} -> {}".format(slug, ", ".join(problems)))
    else:
        print("HTML 合规: {} 篇全部通过（无 class 属性、无 script/style/iframe、无外链锚点）".format(
            report.posts))
    return EXIT_OK


def cmd_convert(args) -> int:
    post = _resolve_post(args.posts_dir, args.slug)
    if post is None:
        print("找不到文章: {}".format(args.slug), file=sys.stderr)
        return EXIT_NOT_FOUND

    eligibility = check_eligibility(post)
    if not eligibility.ok:
        print("文章不合规: {}".format("; ".join(eligibility.reasons)), file=sys.stderr)
        return EXIT_REJECTED

    assets = _mermaid_assets(post, args)
    result = _prepare(post, args, resolver=_Resolver(assets))
    degraded = False

    # Syntax colouring costs one <span> per token.  On a code-heavy
    # article that is a quarter of the character budget, so when the
    # highlighted version does not fit, plain code is used instead:
    # readable content beats colourful content.
    if result.content_length > CONTENT_LIMIT:
        plain = _prepare(post, args, resolver=_Resolver(assets), highlight=False)
        if plain.content_length < result.content_length:
            result = plain
            degraded = True

    failures = [asset for asset in assets.values() if asset.png is None]

    print("已转换: {}".format(post.slug))
    title = _effective_title(post)
    if title != post.title:
        print("  标题: {} ({} 字符，裁剪自「{}」)".format(
            title, len(title), post.title))
    else:
        print("  标题: {} ({} 字符)".format(title, len(title)))
    print("  摘要: {}".format(_branding(post, args).summary or post.digest))
    print("  阅读原文: {}{}".format(args.source_url.rstrip("/"), post.permalink))
    print("  HTML: {}".format(
        (Path(args.out_dir) / post.slug / "article.html").as_posix()))
    print("  正文长度: {} 字符 (上限 {}){}".format(
        result.content_length, CONTENT_LIMIT,
        "  [已关闭代码高亮以压缩体积]" if degraded else ""))
    print("  待上传图片: {}".format(len(result.assets)))
    if result.external_images:
        print("  外链图片: {} 张（发布时会下载并转存到微信）".format(len(result.external_images)))
    print("  站外链接: {}".format(len(result.external_links)))
    print("  mermaid: {} 个 (渲染失败 {} 个)".format(len(assets), len(failures)))
    for asset in failures:
        print("    ! {} -> {}".format(asset.key, asset.error))
    return EXIT_OK


class AssetNotFound(RuntimeError):
    """A local image referenced by the article does not exist on disk."""


class CoverRequired(RuntimeError):
    """The article has no image and no cover was configured."""


def _resolve_asset(path: str, posts_dir: Path) -> Path:
    """Resolve an asset path from the article to a real file.

    ``tools/sync-hexo.py`` rewrites every image reference to
    ``images/<path relative to docs/>``, and those files are copied to
    ``source/images/`` by the same script.  So an asset path is resolved
    against the ``source/`` root, which is the parent of ``_posts/``.
    """
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    site_root = Path(posts_dir).parent
    resolved = site_root / candidate
    if resolved.is_file():
        return resolved
    return candidate


def _upload_assets(client, result, args):
    """Upload every local asset and return the URLs in placeholder order."""
    urls = []
    for asset_path in result.assets:
        resolved = _resolve_asset(asset_path, args.posts_dir)
        if not resolved.is_file():
            raise AssetNotFound("图片不存在: {} (文章引用 {})".format(resolved, asset_path))
        try:
            prepared = assets_module.prepare_image(resolved)
        except ValueError as error:
            # An SVG or a file that is not an image at all: WeChat only
            # accepts JPG and PNG, so this article cannot be drafted.
            raise AssetNotFound(str(error)) from error
        urls.append(client.upload_body_image(prepared.data, prepared.filename))
    return urls


def _fetch_external_images(client, result):
    """Download externally hosted images and store them on WeChat.

    WeChat drops any image whose URL does not come from
    ``media/uploadimg`` -- it removes the element without leaving a
    trace, so the reader sees a paragraph that simply stops.  Fetching
    the picture and uploading it keeps the article whole.

    A picture that cannot be fetched is reported and replaced by a
    visible note, never dropped silently.

    Returns ``(urls, failures, first_prepared)``.  The third value is
    the first picture that was fetched successfully, which is what the
    cover falls back to when the article has no local picture.
    """
    urls = []
    failures = []
    first_prepared = None
    for url in result.external_images:
        try:
            data = assets_module.download_image(url)
            prepared = assets_module.prepare_image_bytes(data, stem="ext")
            urls.append(client.upload_body_image(prepared.data, prepared.filename))
            if first_prepared is None:
                first_prepared = prepared
        except (ValueError, OSError, publish_module.WeChatError) as error:
            urls.append(None)
            failures.append((url, str(error)))
    return urls, failures, first_prepared


def _upload_cover(client, result, args, external_prepared=None, card=None):
    """Upload the cover image and return ``(media_id, crop_percent_list)``.

    WeChat requires a cover, so there is always an answer:

    1. the cover the user named (``--cover`` / ``WX_COVER``)
    2. the article's first **local** picture
    3. the article's first **external** picture, already re-hosted on
       WeChat -- it was fetched anyway, so it is free to reuse
    4. a card drawn for this part -- its topic on a background of its
       own colour
    5. the default cover that ships with this tool

    The last two matter more than they look: 549 of the 766 parts in
    the box have no picture at all, and 39 more have only external
    ones.  Without a fallback those articles could never become a
    draft, and a draft with no cover is not something WeChat accepts.

    The card is drawn only when it is going to be used -- an article
    with a picture of its own keeps that picture -- and a machine that
    cannot draw one falls through to the cover that ships here.
    """
    if args.cover:
        resolved = _resolve_asset(args.cover, args.posts_dir)
        if not resolved.is_file():
            raise AssetNotFound("封面图不存在: {}".format(resolved))
        prepared = _prepare_cover_image(resolved)
    elif result.assets:
        resolved = _resolve_asset(result.assets[0], args.posts_dir)
        if not resolved.is_file():
            raise AssetNotFound("图片不存在: {}".format(resolved))
        prepared = _prepare_cover_image(resolved)
    elif external_prepared is not None:
        prepared = external_prepared
    else:
        prepared = assets_module.prepare_image(card or DEFAULT_COVER)
    media_id = client.upload_cover(prepared.data, prepared.filename)
    return media_id, assets_module.cover_crop_list(prepared.width, prepared.height)


def _cover_card(post, part, args):
    """The cover card of one part, or None when it cannot be drawn.

    The card is drawn lazily: it is only worth the work when the
    article has no picture to use instead.  It carries the title the
    parts share, not the numbered title of this part -- the number is
    added by the card itself.
    """
    if getattr(args, "cover", ""):
        return None
    categories = [str(name) for name in post.categories if name]
    category = categories[0] if categories else "技术笔记"
    try:
        return cover_module.cover_card(
            post.slug, _effective_title(post), category, Path(args.out_dir),
            part_index=part.index, part_total=part.total)
    except (OSError, RuntimeError) as error:
        # A machine without a usable font cannot draw a card.  That is
        # not a reason to lose the article.
        print("  ! 封面卡画不出来，改用默认封面: {}".format(error), file=sys.stderr)
        return None


def _prepare_cover_image(resolved: Path):
    """Read a cover image, or say clearly that it is not one.

    An SVG cannot be uploaded to WeChat -- only JPG and PNG are
    accepted -- so the article is skipped instead of the whole batch
    going down with it.
    """
    try:
        return assets_module.prepare_image(resolved)
    except ValueError as error:
        raise AssetNotFound(str(error)) from error


def _notify(args, title: str, length: int, source_url: str, state, *,
            action: str, published: bool) -> None:
    """Tell the phone that something is waiting, if a channel is set up.

    A failed notification is a warning, never a failure: the draft is
    already in the box, and that is what matters.  A draft that was
    merely reused does not notify again -- nobody needs to be told
    twice about the same article.
    """
    backend, key = args.notify, args.notify_key
    if not backend or not key:
        return
    if published:
        heading = "公众号文章已提交发表"
        body = "《{}》\npublish_id: {}".format(title, state.publish_id)
    elif action == DRAFT_UPDATED:
        heading = "公众号草稿已更新"
        body = (
            "《{}》\n"
            "正文 {} 字符\n"
            "阅读原文: {}\n"
            "\n"
            "去公众号后台点「发表」即可发布：{}"
        ).format(
            title,
            length,
            source_url,
            notify_module.DRAFT_BOX_URL,
        )
    elif action == DRAFT_CREATED:
        heading = "公众号草稿已就绪"
        body = (
            "《{}》\n"
            "正文 {} 字符\n"
            "阅读原文: {}\n"
            "\n"
            "去公众号后台点「发表」即可发布：{}"
        ).format(
            title,
            length,
            source_url,
            notify_module.DRAFT_BOX_URL,
        )
    else:
        return
    try:
        notify_module.send(backend, key, heading, body)
    except notify_module.NotifyError as error:
        print("  通知发送失败: {}".format(error), file=sys.stderr)
        return
    print("  已通知: {}".format(notify_module.describe(backend, key)))


class RejectedPost(Exception):
    """This post cannot be drafted.

    A rejection is not a failure: an over-long article is skipped and
    the rest of a batch carries on.  It is the same policy the single
    article command follows -- record the reason, publish nothing.
    """


@dataclass
class DraftResult:
    """What happened to one post when it was put into the draft box."""

    state: PublishState
    action: str
    content_length: int = 0
    external_total: int = 0
    external_failures: list = field(default_factory=list)
    key: str = ""


DRAFT_CREATED = "created"
DRAFT_REUSED = "reused"
DRAFT_UPDATED = "updated"


def _create_draft(client, store, key: str, fingerprint: str, article: dict,
                   parts: int = 1):
    """Put an article into the draft box, creating or updating as needed.

    Returns ``(state, action)``.  ``action`` is ``created`` for a new
    draft, ``updated`` when an existing draft was brought up to date,
    and ``reused`` when nothing had changed.

    A changed article is **updated in place**: ``draft/add`` would
    create a second copy and leave the old one in the box for the
    reader to trip over.

    One case cannot be updated in place: the WAF behind the API
    refuses ``draft/update`` when the body carries a SQL pattern such
    as ``CREATE TABLE`` -- which a code block full of DDL always does.
    Then the article is added again and the old draft is deleted, and
    the end state is the same: one draft, the current content.

    ``parts`` records how many parts the article was split into, so a
    later run can tell whether every part is really there.
    """
    state = store.get(key)
    if not state.media_id:
        state.media_id = client.add_draft(article)
        state.fingerprint = fingerprint
        state.publish_id = None
        state.publish_status = None
        state.parts = parts
        state.pipeline = version_module.PIPELINE_VERSION
        store.save(key, state)
        return state, DRAFT_CREATED

    if (state.fingerprint == fingerprint
            and state.pipeline == version_module.PIPELINE_VERSION):
        print("内容未变，复用已有草稿 {}".format(state.media_id))
        return state, DRAFT_REUSED

    try:
        client.update_draft(state.media_id, article)
    except publish_module.WeChatError as error:
        if error.errcode != publish_module.WAF_BLOCKED:
            raise
        # The WAF behind the API checks the body of ``draft/update``
        # for SQL patterns and answers with a web page when it finds
        # one.  A code block full of DDL is ordinary in this corpus;
        # ``draft/add`` has looser rules and takes the same body.
        # Adding the article again and deleting the old draft reaches
        # the same end state -- one draft, the current content.
        new_media_id = client.add_draft(article)
        try:
            client.delete_draft(state.media_id)
        except publish_module.WeChatError as delete_error:
            raise publish_module.WeChatError(
                delete_error.errcode,
                "新草稿 {} 已建好，但旧草稿 {} 删不掉：{}。"
                "草稿箱里现在是两份，下次 reconcile 会清掉多出来的那份".format(
                    new_media_id, state.media_id, delete_error.errmsg),
                delete_error.endpoint) from delete_error
        state.media_id = new_media_id
        print("  ! 该内容被 WAF 拦下了 draft/update，"
              "改用新建加删除完成更新 {}".format(new_media_id))
    state.fingerprint = fingerprint
    state.publish_id = None
    state.publish_status = None
    state.parts = parts
    state.pipeline = version_module.PIPELINE_VERSION
    store.save(key, state)
    print("内容已变，草稿就地更新 {}".format(state.media_id))
    return state, DRAFT_UPDATED


def _submit(client, store, key: str, state, publish: bool) -> bool:
    """Submit the draft for publishing, when asked to."""
    if not publish or not needs_submit(state):
        return False
    state.publish_id = client.freepublish_submit(state.media_id)
    store.save(key, state)
    return True


@dataclass
class Part:
    """One draft's worth of an article.

    Most articles are a single part.  An article whose rendered body
    does not fit WeChat's limit becomes several, each with its own
    title, its own transitions and its own reference links.
    """

    index: int
    total: int
    blocks: list
    result: render_module.RenderResult
    title: str
    key: str
    digest: str = ""


def _fits(result) -> bool:
    """True when WeChat would accept this content as it is."""
    return (result.content_length <= CONTENT_LIMIT
            and len(result.html.encode("utf-8")) < CONTENT_BYTES_LIMIT)


# How often a part that does not fit may be cut again.  Each pass
# renders the whole article, so the number is kept small.
MAX_SPLIT_PASSES = 3


def _render_parts(post, args) -> list:
    """Render one post into the drafts it needs.

    Most articles fit into a single draft.  One that does not is split
    into several -- at heading boundaries where possible -- and every
    part becomes a draft of its own, numbered and connected so that
    the reader can follow the thread.

    Raises :class:`RejectedPost` when a part cannot be brought under
    the limit even on its own; the article is then skipped, never
    truncated.
    """
    branding = _branding(post, args)
    blocks = branding.blocks
    card = branding.card
    signature = branding.signature
    summary = branding.summary
    assets = _mermaid_assets(post, args)
    resolver = _Resolver(assets)
    tag = _category_tag(post, args)
    position = getattr(args, "category_tag", "top")
    head = tag if position == "top" else ""
    tail = tag if position == "bottom" else ""
    # Every part speaks of the article by the title the reader will
    # see, so the shortened title is the one that goes everywhere.
    base_title = _effective_title(post)

    def part_head(index: int, total: int) -> str:
        """The lines that open a part.

        The card belongs to the first part only: it is the article's
        title page, and the later parts continue the text, not the
        introduction.
        """
        return (card if index == 1 else "") + head + \
            split_module.transition_head_html(base_title, index, total)

    def build(group, index, total, highlight):
        """Render one part, with its opening and closing lines in place."""
        result = render_module.render(
            group, resolver=resolver, highlight=highlight,
            head_html=part_head(index, total),
            tail_html=tail,
        )
        # The line that closes a part comes after the reference links:
        # the links are where the article ends.  The signature comes
        # after that: it is the last thing the reader reads.
        result = replace(result, html=result.html
                         + split_module.transition_tail_html(base_title, index, total)
                         + signature)
        return result

    def save(group, result, index, total):
        """Keep the rendered HTML on disk, one file per part.

        The file of the other shape is removed: an article that is
        whole again must not keep the parts of an older split, and an
        article that is split must not keep the single file of an older
        whole run.  A leftover would look like the current product.
        """
        target_dir = Path(args.out_dir) / post.slug
        target_dir.mkdir(parents=True, exist_ok=True)
        if total == 1:
            name = "article.html"
            for old in target_dir.glob("part-*.html"):
                old.unlink()
        else:
            name = "part-{}.html".format(index)
            single = target_dir / "article.html"
            if single.is_file():
                single.unlink()
        (target_dir / name).write_text(result.html, encoding="utf-8")

    def measure(group, highlight=True):
        """The size a group contributes: its body plus the links it brings."""
        result = render_module.render(group, resolver=resolver, highlight=highlight)
        body = len(result.html) - len(render_module.links_html(result.external_links))
        return body + len(render_module.links_items_html(result.external_links))

    def room_for(group, index, total):
        """The room the body of a part may take.

        The framing is measured, not estimated: the transition lines,
        the category tag, the card, the signature and the
        reference-links wrapper are what the body has to fit between,
        and a part that ignores them does not fit.
        """
        result = render_module.render(group, resolver=resolver)
        framing = (len(part_head(index, total)) + len(tail)
                   + len(split_module.transition_tail_html(base_title, index, total))
                   + len(signature)
                   + len(render_module.links_html(result.external_links)))
        return CONTENT_LIMIT - framing

    # The card and the signature are paid for out of the body, so they
    # are part of the reserve.  The reserve is the same for every part
    # even though the card only opens the first one: a reserve that is
    # too small does not make a part shorter, it makes the whole
    # article unpublishable.
    reserve = split_module.framing_reserve(base_title, tag,
                                           extra=card + signature)
    groups = split_module.plan_parts(
        blocks, CONTENT_LIMIT, measure,
        plain_measure=lambda group: measure(group, highlight=False),
        reserve=reserve)

    # The plan is an estimate; the render is the truth.  A part that
    # still does not fit is cut once more instead of taking the whole
    # article down with it -- an article that is a few dozen
    # characters too long is a split, not a refusal.
    #
    # The cut is driven by the measured overflow rather than by the
    # estimate: the room the part needs is known once it is rendered,
    # and a reserve that was too small is exactly what the overflow
    # says.
    rendered = []
    for attempt in range(MAX_SPLIT_PASSES):
        total = len(groups)
        rendered = [(build(group, index, total, not use_plain), group, use_plain)
                    for index, (group, use_plain) in enumerate(groups, 1)]
        overflow = {index: max(result.content_length - CONTENT_LIMIT, 1)
                    for index, (result, _, _) in enumerate(rendered)
                    if not _fits(result)}
        if not overflow or attempt == MAX_SPLIT_PASSES - 1:
            break
        rebuilt = []
        broken = False
        for index, (group, use_plain) in enumerate(groups):
            over = overflow.get(index)
            if over is not None:
                room = room_for(group, index, total) - over
                if room > 0:
                    pieces = split_module.split_blocks(group, room, measure)
                    if len(pieces) > 1:
                        rebuilt.extend(
                            (piece, use_plain or measure(piece) > room)
                            for piece in pieces)
                        broken = True
                        continue
            rebuilt.append((group, use_plain))
        groups = rebuilt
        if not broken:
            break

    total = len(groups)
    parts = []
    for index, (result, group, _use_plain) in enumerate(rendered, 1):
        if not _fits(result):
            raise RejectedPost(
                "第 {} 部分渲染后正文 {} 字符，超过上限 {} 字符，已拒绝发布\n"
                "提示：这一部分单独放也放不下，只能人工拆得更细".format(
                    index, result.content_length, CONTENT_LIMIT))
        save(group, result, index, total)
        part_title = (base_title if total == 1
                      else split_module.part_title(base_title, index))
        key = post.slug if index == 1 else "{}#{}".format(post.slug, index)
        # The first part carries the summary of the whole article -- the
        # one the author wrote about it.  The later parts describe
        # themselves, so the draft box does not show the same line
        # again and again.
        part_summary = (summary if index == 1
                        else digest_module.part_digest(group))
        parts.append(Part(index=index, total=total, blocks=group, result=result,
                           title=part_title, key=key, digest=part_summary))
    return parts


def _part_keys(slug: str, count: int) -> list:
    """The ledger keys of an article's parts.

    The first part keeps the plain slug, so an article that was never
    split keeps the entry it always had.  The rest are numbered.
    """
    return [slug if index == 1 else "{}#{}".format(slug, index)
            for index in range(1, count + 1)]


def _parts_present(store, slug: str, count: int) -> bool:
    """True when every part of the article has a draft."""
    return all(store.get(key).media_id for key in _part_keys(slug, count))


def _draft_parts(client, store, post, args) -> list:
    """Put one post into the draft box -- one draft per part.

    The uploads only happen when the content actually changed: an
    unchanged article is recognised by its fingerprint before a single
    image is sent, which is what makes re-running a batch over the
    whole corpus cheap.
    """
    tag = _category_tag(post, args)
    fingerprint = _fingerprint(post, tag)

    state = store.get(post.slug)
    if (state.media_id and state.fingerprint == fingerprint
            and state.pipeline == version_module.PIPELINE_VERSION
            and _parts_present(store, post.slug, state.parts or 1)):
        print("内容未变，复用已有草稿 {}".format(state.media_id))
        return [DraftResult(state=store.get(key), action=DRAFT_REUSED, key=key)
                for key in _part_keys(post.slug, state.parts or 1)]

    parts = _render_parts(post, args)
    results = []
    for part in parts:
        results.append(_draft_part(client, store, post, part, fingerprint, args))
    _drop_extra_parts(client, store, post, len(parts))
    return results


def _draft_part(client, store, post, part, fingerprint, args) -> DraftResult:
    """Put one part of an article into the draft box."""
    result = part.result

    urls = _upload_assets(client, result, args)
    html = result.substitute(urls)

    external_failures = []
    external_prepared = None
    if result.external_images:
        external_urls, external_failures, external_prepared = \
            _fetch_external_images(client, result)
        html = result.substitute_external(
            external_urls, fallback=EXTERNAL_IMAGE_FALLBACK, html=html)

    card = _cover_card(post, part, args)
    cover_media_id, crop_list = _upload_cover(client, result, args, external_prepared,
                                               card)

    # Every part describes itself: the same summary on every row of the
    # draft box would tell the reader nothing.
    digest = part.digest or post.digest
    if _effective_title(post) != post.title:
        # The title was shortened.  The original one goes into the
        # summary, so the draft box still says what the article is
        # called on the site.  A title that was only numbered for a
        # split does not need this: the row already carries it.
        digest = "{}｜{}".format(post.title, digest)[:DIGEST_LIMIT]
    article = {
        "article_type": "news",
        "title": part.title,
        "author": args.author,
        "digest": digest,
        "content": html,
        "content_source_url": args.source_url.rstrip("/") + post.permalink,
        "thumb_media_id": cover_media_id,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
        "cover_info": {"crop_percent_list": crop_list},
    }

    state, action = _create_draft(client, store, part.key, fingerprint, article,
                                   parts=part.total)
    return DraftResult(
        state=state,
        action=action,
        content_length=result.content_length,
        external_total=len(result.external_images),
        external_failures=external_failures,
        key=part.key,
    )


def _drop_extra_parts(client, store, post, count: int) -> None:
    """Delete the drafts of parts that no longer exist.

    An article that got shorter may need fewer parts than it did
    before.  The drafts of the parts that are gone would stay in the
    box looking like current content, so they are removed.
    """
    prefix = post.slug + "#"
    for key in list(store.all()):
        if not key.startswith(prefix):
            continue
        suffix = key[len(prefix):]
        if not suffix.isdigit() or int(suffix) <= count:
            continue
        state = store.get(key)
        if state.media_id:
            try:
                client.delete_draft(state.media_id)
                print("  已删除多余草稿 {} ({})".format(post.slug, suffix))
            except publish_module.WeChatError as error:
                print("  ! 删除多余草稿失败: {}".format(error), file=sys.stderr)
        store.remove(key)


def cmd_publish(args) -> int:
    post = _resolve_post(args.posts_dir, args.slug)
    if post is None:
        print("找不到文章: {}".format(args.slug), file=sys.stderr)
        return EXIT_NOT_FOUND

    eligibility = check_eligibility(post)
    if not eligibility.ok:
        print("文章不合规: {}".format("; ".join(eligibility.reasons)), file=sys.stderr)
        return EXIT_REJECTED

    if not args.appid or not args.appsecret:
        print("缺少 WX_APPID / WX_APPSECRET 环境变量", file=sys.stderr)
        return EXIT_REJECTED

    if len(args.author) > AUTHOR_LIMIT:
        print("作者 {} 超过上限 {} 字符".format(args.author, AUTHOR_LIMIT), file=sys.stderr)
        return EXIT_REJECTED

    client = publish_module.WeChatClient(
        args.appid, args.appsecret, base_url=args.api_base)
    store = StateStore(Path(args.out_dir) / "state.json")

    try:
        drafts = _draft_parts(client, store, post, args)
    except RejectedPost as error:
        print(str(error), file=sys.stderr)
        return EXIT_REJECTED

    published = False
    for draft in drafts:
        published = _submit(client, store, draft.key, draft.state, args.publish) or published

    for draft in drafts:
        print("已建草稿: {}".format(draft.key))
        print("  media_id: {}".format(draft.state.media_id))
        print("  正文长度: {} 字符".format(draft.content_length))
        print("  阅读原文: {}{}".format(args.source_url.rstrip("/"), post.permalink))
        if draft.external_total:
            fetched = draft.external_total - len(draft.external_failures)
            print("  外链图转存: {} / {} 张".format(fetched, draft.external_total))
        for url, error in draft.external_failures:
            print("    ! 原图未能转存: {} -> {}".format(url, error))
        if draft.state.publish_id:
            print("  publish_id: {}".format(draft.state.publish_id))
        else:
            print("  未提交发表（如需自动发表请加 --publish）")

    _notify(args, post.title, sum(draft.content_length for draft in drafts),
            args.source_url.rstrip("/") + post.permalink, drafts[0].state,
            action=_overall_action(drafts), published=published)
    return EXIT_OK


def _overall_action(drafts) -> str:
    """The action that describes a whole article, not just one part."""
    actions = {draft.action for draft in drafts}
    if DRAFT_CREATED in actions:
        return DRAFT_CREATED
    if DRAFT_UPDATED in actions:
        return DRAFT_UPDATED
    return DRAFT_REUSED


def _git(*args, cwd: Path):
    """Run a git command in the repository and return ``(code, output)``."""
    result = subprocess.run(
        ["git"] + list(args), cwd=str(cwd), capture_output=True, text=True)
    return result.returncode, result.stdout.strip()


def _docs_changed(repo_dir: Path, stamp_path: Path) -> bool:
    """Has ``docs/`` changed since the last run?

    Two things count: commits made since the last run, and edits in
    the working tree.  The working tree is checked with
    ``git status --porcelain`` rather than ``git diff`` because
    ``git diff`` does not see files that were never added -- and a new
    article that has not been committed yet is exactly the case this
    job exists for.
    """
    code, head = _git("rev-parse", "HEAD", cwd=repo_dir)
    if code != 0:
        return True

    previous = ""
    if stamp_path.is_file():
        previous = stamp_path.read_text(encoding="utf-8").strip()

    if previous and previous != head:
        code, _ = _git("diff", "--quiet", previous, "HEAD", "--", "docs", cwd=repo_dir)
        if code != 0:
            return True

    code, out = _git("status", "--porcelain", "--", "docs", cwd=repo_dir)
    if code != 0:
        return True
    return bool(out.strip())


def _run_sync(repo_dir: Path) -> int:
    """Rebuild ``source/_posts/`` from ``docs/``.

    Returns the exit code of ``sync-hexo.py``.  It takes about three
    minutes and rebuilds everything from scratch, which is why it only
    runs when ``docs/`` actually changed.
    """
    script = repo_dir / "tools" / "sync-hexo.py"
    if not script.is_file():
        print("找不到 {}".format(script), file=sys.stderr)
        return EXIT_NOT_FOUND
    result = subprocess.run([sys.executable, str(script)], cwd=str(repo_dir))
    return result.returncode


def cmd_auto_draft(args) -> int:
    """Put newly added articles into the draft box.

    The trigger is a scheduled job on the machine that holds the
    credentials: WeChat's API requires the caller's IP in the
    account's allowlist, and a hosted CI runner has a changing one.

    ``sync-hexo.py`` takes three minutes and rebuilds everything, so
    the job only runs it when ``docs/`` changed.  The batch always
    runs: it is free when there is nothing to do, and it is what
    picks up whatever a previous run left half-finished.
    """
    repo_dir = Path(args.repo_dir)
    stamp_path = Path(args.stamp_file)

    changed = args.force or _docs_changed(repo_dir, stamp_path)
    if changed:
        print("docs/ 有变化，重新生成 source/_posts/ ...")
        code = _run_sync(repo_dir)
        if code != 0:
            print("sync-hexo.py 失败，退出码 {}".format(code), file=sys.stderr)
            return EXIT_REJECTED
        stamp_path.parent.mkdir(parents=True, exist_ok=True)
        _, head = _git("rev-parse", "HEAD", cwd=repo_dir)
        stamp_path.write_text(head + "\n", encoding="utf-8")
    else:
        print("docs/ 自上次运行没有变化，跳过重新生成")

    print("推进草稿箱 ...")
    return cmd_batch(args)


def _batch_lock_path(out_dir) -> Path:
    """Where the lock that keeps two batches apart lives."""
    return Path(out_dir) / "batch.lock"


def _pid_alive(pid: int) -> bool:
    """True when a process with that pid is still running."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _take_batch_lock(out_dir) -> bool:
    """Take the batch lock, or report that somebody else holds it.

    A batch and the scheduled job can otherwise run at the same time.
    Both would decide that an article has no draft yet -- the ledger
    says so -- and both would create one, leaving two copies of the
    same article in the box.

    The lock is a file that holds the pid of the process that took it.
    A lock whose process is gone was left behind by a crash, and the
    next run takes it over.
    """
    path = _batch_lock_path(out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(3):
        try:
            handle = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                pid = int(path.read_text(encoding="utf-8").strip() or "0")
            except (OSError, ValueError):
                pid = 0
            if pid and pid != os.getpid() and _pid_alive(pid):
                return False
            try:
                path.unlink()
            except OSError:
                return False
            continue
        with os.fdopen(handle, "w") as out:
            out.write(str(os.getpid()))
        return True
    return False


def _drop_batch_lock(out_dir) -> None:
    """Give the lock back, but only if this process is the one holding it."""
    path = _batch_lock_path(out_dir)
    try:
        pid = int(path.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        pid = 0
    if pid == os.getpid():
        try:
            path.unlink()
        except OSError:
            pass


def cmd_batch(args) -> int:
    """Put many posts into the draft box.

    One broken article must not cost the other hundreds their draft,
    so a failure is recorded and the run carries on.  The run is
    resumable: an article whose content has not changed keeps its
    draft and costs nothing, because the fingerprint settles it
    before a single image is uploaded.

    WeChat's daily call budget is about 2000 and a full backfill of
    this corpus spends most of it, so ``--limit`` lets a backfill be
    spread over several runs.
    """
    posts = discover(args.posts_dir)
    store = StateStore(Path(args.out_dir) / "state.json")

    selected = []
    ineligible = 0
    unchanged = 0
    for post in posts:
        eligibility = check_eligibility(post)
        if not eligibility.ok:
            ineligible += 1
            continue
        fingerprint = _fingerprint(post, _category_tag(post, args))
        state = store.get(post.slug)
        drafted = bool(state.media_id)
        # A split article has several drafts; the article counts as done
        # only when every one of them is there.
        complete = drafted and _parts_present(store, post.slug, state.parts or 1)
        same = (complete and state.fingerprint == fingerprint
                and state.pipeline == version_module.PIPELINE_VERSION)
        if args.new_only and complete:
            continue
        if args.changed_only and (not complete or same):
            continue
        if same:
            unchanged += 1
            continue
        selected.append(post)

    # Newest first: with a limited budget the recent articles are the
    # ones most likely to be published next.
    selected.sort(key=lambda post: (post.date, post.slug), reverse=True)

    if args.limit and len(selected) > args.limit:
        print("本轮只处理 {} 篇（共 {} 篇待处理）".format(args.limit, len(selected)))
        selected = selected[:args.limit]

    if args.dry_run:
        print("预检：将处理 {} 篇（不改数据、不调接口）".format(len(selected)))
        print("不合规跳过 {} 篇，内容未变跳过 {} 篇".format(ineligible, unchanged))
        print("（预检只看标题与原始正文字数；渲染后超限的会在实际运行时跳过，"
              "所以这里的篇数是上界）")
        for post in selected:
            print("  {}".format(post.slug))
        return EXIT_OK

    if not selected:
        print("没有需要处理的文章（不合规 {} 篇，内容未变 {} 篇）".format(
            ineligible, unchanged))
        return EXIT_OK

    if not args.appid or not args.appsecret:
        print("缺少 WX_APPID / WX_APPSECRET 环境变量", file=sys.stderr)
        return EXIT_REJECTED

    # From here on the run writes to the ledger and to the draft box, so
    # only one of them may be going at a time.
    if not _take_batch_lock(args.out_dir):
        print("另一个批量任务正在运行（{}），本次跳过".format(
            _batch_lock_path(args.out_dir)))
        return EXIT_OK
    atexit.register(_drop_batch_lock, args.out_dir)

    client = publish_module.WeChatClient(
        args.appid, args.appsecret, base_url=args.api_base)

    created = updated = rejected = failed = 0
    failures = []
    stopped_early = False

    for index, post in enumerate(selected, 1):
        print("[{}/{}] {} ({})".format(index, len(selected), post.title, post.slug))
        try:
            drafts = _draft_parts(client, store, post, args)
        except RejectedPost as error:
            rejected += 1
            reason = str(error).splitlines()[0]
            failures.append({"slug": post.slug, "title": post.title,
                             "kind": "rejected", "reason": reason})
            print("  ! 已跳过: {}".format(reason), file=sys.stderr)
            continue
        except (AssetNotFound, CoverRequired) as error:
            failed += 1
            failures.append({"slug": post.slug, "title": post.title,
                             "kind": "failed", "reason": str(error)})
            print("  ! 资源缺失: {}".format(error), file=sys.stderr)
            continue
        except publish_module.WeChatError as error:
            failed += 1
            failures.append({"slug": post.slug, "title": post.title,
                             "kind": "failed", "reason": str(error)})
            print("  ! 接口报错: {}".format(error), file=sys.stderr)
            if error.errcode == 45009:
                print("  触发接口调用上限，本轮到此为止；"
                      "已建的草稿不会丢，下次接着跑即可", file=sys.stderr)
                stopped_early = True
                break
            continue

        for draft in drafts:
            if draft.action == DRAFT_CREATED:
                created += 1
            elif draft.action == DRAFT_UPDATED:
                updated += 1

        if args.delay and index < len(selected):
            time.sleep(args.delay)

    _write_batch_report(args, selected, created, updated, failures)

    print()
    print("本轮完成: 新建 {} 篇，就地更新 {} 篇，跳过 {} 篇（超限），失败 {} 篇".format(
        created, updated, rejected, failed))
    if failures:
        print("明细:")
        for failure in failures:
            print("  ! {} ({}) -> {}".format(
                failure["title"], failure["slug"], failure["reason"]))
    if stopped_early:
        print("（因接口调用上限提前结束，剩余 {} 篇下次继续）".format(
            len(selected) - created - updated - rejected - failed))
    if created or updated:
        _notify_batch(args, created, updated, rejected, failed)
    # The lock is given back here, not only when the process exits, so
    # that the next run can start right away.
    _drop_batch_lock(args.out_dir)
    return EXIT_API_ERROR if failed else EXIT_OK


def _notify_batch(args, created, updated, rejected, failed) -> None:
    """Announce what a batch put into the draft box.

    One message for the whole run: a notification per article would be
    a flood, and the point is to say "there is something waiting for
    you in the box".
    """
    if not args.notify or not args.notify_key:
        return
    heading = "公众号草稿已就绪"
    body = (
        "本轮新建 {} 篇，就地更新 {} 篇，跳过 {} 篇（超限），失败 {} 篇\n"
        "\n"
        "去公众号后台点「发表」即可发布：{}"
    ).format(created, updated, rejected, failed, notify_module.DRAFT_BOX_URL)
    try:
        notify_module.send(args.notify, args.notify_key, heading, body)
    except notify_module.NotifyError as error:
        print("  通知发送失败: {}".format(error), file=sys.stderr)
        return
    print("  已通知: {}".format(notify_module.describe(args.notify, args.notify_key)))


def _write_batch_report(args, selected, created, updated, failures):
    """Write what the run did, so a long backfill can be reviewed later.

    ``failures`` holds both kinds of problem, so the counts are derived
    from the entries themselves: an article that was too long was
    *skipped*, not *failed*, and a report that calls it a failure makes
    the run look broken when it was not.
    """
    report = {
        "total_selected": len(selected),
        "created": created,
        "updated": updated,
        "rejected": sum(1 for item in failures if item.get("kind") == "rejected"),
        "failed": sum(1 for item in failures if item.get("kind") == "failed"),
        "failures": failures,
    }
    target = Path(args.out_dir) / "batch-report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                      encoding="utf-8")


def _display_width(text: str) -> int:
    """The width of a string as it appears in a terminal.

    A Chinese character takes two columns, so padding by ``len`` would
    leave the list ragged.
    """
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    """Pad a string to a terminal width."""
    return text + " " * max(0, width - _display_width(text))


def cmd_categories(args) -> int:
    """List the categories of the corpus, or the articles of one."""
    posts = discover(args.posts_dir)
    categories = collection_module.build_categories(posts)

    if args.name:
        refs = categories.get(args.name)
        if refs is None:
            print("找不到分类: {}".format(args.name), file=sys.stderr)
            return EXIT_NOT_FOUND
        print("分类「{}」共 {} 篇\n".format(args.name, len(refs)))
        for ref in refs:
            print("  {}  {}".format(ref.label, ref.title))
        print("\n归档页: {}".format(
            collection_module.category_archive_url(args.source_url, args.name)))
        return EXIT_OK

    total = sum(len(refs) for refs in categories.values())
    print("共 {} 个分类，{} 篇文章（分类计数 {} 次，一篇文章可有多个分类）\n".format(
        len(categories), len(posts), total))
    width = max((_display_width(name) for name in categories), default=0)
    for name, refs in categories.items():
        print("  {}  {:>4} 篇".format(_pad(name, width), len(refs)))
    return EXIT_OK


def _find_collection(collections, name: str):
    """Look a collection up by title or by its filesystem-safe slug."""
    for collection in collections:
        if name in (collection.title, collection.slug):
            return collection
    return None


def _collection_archive_url(collection, source_url: str) -> str:
    """Where the index article's 「阅读原文」 points.

    A collection that maps to a single category points at that
    category's archive page on the blog -- the one clickable target a
    reader has inside a WeChat article.  A curated collection spans
    several categories and has no such page, so it points at the blog's
    home page instead.
    """
    return collection.archive_url(source_url)


def _write_collection(collection, args) -> Path:
    """Write the index article and the backend checklist of a collection."""
    target = Path(args.out_dir) / "collections" / collection.slug
    target.mkdir(parents=True, exist_ok=True)
    index_html = collection_module.render_collection_index(collection, args.source_url)
    (target / "article.html").write_text(index_html, encoding="utf-8")
    plan = collection_module.render_collection_plan(collection, args.source_url)
    (target / "plan.md").write_text(plan, encoding="utf-8")
    return target


def cmd_collections(args) -> int:
    """List the collections, or write the artefacts of one."""
    posts = discover(args.posts_dir)
    spec = collection_module.load_spec(args.collections_file)
    collections = collection_module.build_collections(posts, spec)

    if args.name:
        collection = _find_collection(collections, args.name)
        if collection is None:
            print("找不到合集: {}".format(args.name), file=sys.stderr)
            return EXIT_NOT_FOUND
        print("合集「{}」共 {} 篇".format(collection.title, collection.count))
        if collection.description:
            print("简介: {}".format(collection.description))
        print("归档页: {}\n".format(_collection_archive_url(collection, args.source_url)))
        for index, ref in enumerate(collection.articles, 1):
            print("  {}. {}  {}".format(index, ref.label, ref.title))
        if args.write:
            target = _write_collection(collection, args)
            print("\n已写出: {}".format(target.as_posix()))
        return EXIT_OK

    if not collections:
        print("没有可用的合集")
        print("（默认把文章数 >= 2 的分类当成合集；"
              "也可以写 weixin/collections.json 手工指定）")
        return EXIT_OK

    print("共 {} 个合集\n".format(len(collections)))
    width = max(_display_width(c.title) for c in collections)
    for collection in collections:
        print("  {}  {:>4} 篇".format(_pad(collection.title, width), collection.count))
    return EXIT_OK


def _collection_cover(collection, posts, args) -> str:
    """Find the cover image of a collection's index article.

    The collection's own articles supply it: the first picture of the
    first article that has one.  A diagram rendered from mermaid counts
    as a picture -- for the learning-path series it is the only one
    there is.

    The search stops at the first article that yields a picture, so a
    collection whose leading articles are text-only costs nothing.
    Falls back to the default cover.
    """
    if args.cover:
        return args.cover
    by_slug = {post.slug: post for post in posts}
    for ref in collection.articles:
        post = by_slug.get(ref.slug)
        if post is None:
            continue
        assets = _mermaid_assets(post, args)
        result = render_module.render(
            parse(post.body), resolver=_Resolver(assets), highlight=False)
        if result.assets:
            return result.assets[0]
    return str(DEFAULT_COVER)


def cmd_publish_collection(args) -> int:
    """Push the index article of a collection into the draft box."""
    posts = discover(args.posts_dir)
    spec = collection_module.load_spec(args.collections_file)
    collections = collection_module.build_collections(posts, spec)
    collection = _find_collection(collections, args.name)
    if collection is None:
        print("找不到合集: {}".format(args.name), file=sys.stderr)
        return EXIT_NOT_FOUND
    if not collection.articles:
        print("合集「{}」没有文章".format(collection.title), file=sys.stderr)
        return EXIT_REJECTED

    title = "「{}」合集目录".format(collection.title)
    if len(title) > TITLE_LIMIT:
        print("合集标题过长：{}（{} 字符，上限 {}）".format(
            title, len(title), TITLE_LIMIT), file=sys.stderr)
        return EXIT_REJECTED

    if not args.appid or not args.appsecret:
        print("缺少 WX_APPID / WX_APPSECRET 环境变量", file=sys.stderr)
        return EXIT_REJECTED

    html = collection_module.render_collection_index(collection, args.source_url)
    if len(html) > CONTENT_LIMIT:
        print("合集导览正文 {} 字符，超过上限 {} 字符，已拒绝发布".format(
            len(html), CONTENT_LIMIT), file=sys.stderr)
        return EXIT_REJECTED

    client = publish_module.WeChatClient(
        args.appid, args.appsecret, base_url=args.api_base)

    key = "collection/{}".format(collection.slug)
    store = StateStore(Path(args.out_dir) / "state.json")
    fingerprint = hashlib.sha256(html.encode("utf-8")).hexdigest()
    archive = _collection_archive_url(collection, args.source_url)

    # The cover is uploaded only when the index actually changed: the
    # upload is the expensive part and the fingerprint settles it.
    existing = store.get(key)
    if existing.media_id and existing.fingerprint == fingerprint:
        print("内容未变，复用已有草稿 {}".format(existing.media_id))
        state, action = existing, DRAFT_REUSED
        published = _submit(client, store, key, state, args.publish)
        _report_collection(collection, title, len(html), archive, state, action, published, args)
        return EXIT_OK

    cover_path = _resolve_asset(_collection_cover(collection, posts, args), args.posts_dir)
    if not cover_path.is_file():
        raise AssetNotFound("封面图不存在: {}".format(cover_path))
    prepared = _prepare_cover_image(cover_path)
    cover_media_id = client.upload_cover(prepared.data, prepared.filename)

    article = {
        "article_type": "news",
        "title": title,
        "author": args.author,
        "digest": collection_module.collection_digest(collection),
        "content": html,
        "content_source_url": archive,
        "thumb_media_id": cover_media_id,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
        "cover_info": {"crop_percent_list": assets_module.cover_crop_list(
            prepared.width, prepared.height)},
    }

    state, action = _create_draft(client, store, key, fingerprint, article)
    published = _submit(client, store, key, state, args.publish)

    _report_collection(collection, title, len(html), archive, state, action, published, args)
    return EXIT_OK


def _report_collection(collection, title, length, archive, state, action, published, args):
    """Print what happened to a collection's index article."""
    print("已建合集导览草稿: {}".format(collection.title))
    print("  media_id: {}".format(state.media_id))
    print("  正文长度: {} 字符".format(length))
    print("  阅读原文: {}".format(archive))
    print("  合集文章: {} 篇（平台上的合集仍需在后台手工勾选）".format(
        collection.count))
    _notify(args, title, length, archive, state,
            action=action, published=published)
    if state.publish_id:
        print("  publish_id: {}".format(state.publish_id))
    else:
        print("  未提交发表（如需自动发表请加 --publish）")


def cmd_status(args) -> int:
    store = StateStore(Path(args.out_dir) / "state.json")
    entries = store.all()
    if not entries:
        print("没有已发布的记录")
        return EXIT_OK
    for slug in sorted(entries):
        state = store.get(slug)
        print("  {}".format(slug))
        print("    media_id:   {}".format(state.media_id))
        print("    publish_id: {}".format(state.publish_id))
        print("    status:     {}".format(state.publish_status))
        print("    updated_at: {}".format(state.updated_at))
    return EXIT_OK


def cmd_reconcile(args) -> int:
    """Compare the ledger with the drafts that are actually in the box.

    The ledger is the only thing that stops this tool from creating
    the same draft twice.  But a human can delete a draft in the WeChat
    backend, and then the ledger still claims the draft exists -- the
    article would never be drafted again, silently, forever.

    This command closes that gap: it walks the draft box, compares it
    with the ledger and forgets the entries whose draft is gone, so the
    next ``batch --new-only`` picks those articles up again.
    """
    store = StateStore(Path(args.out_dir) / "state.json")
    entries = store.all()
    ledger = {slug: entry for slug, entry in entries.items()
              if isinstance(entry, dict) and entry.get("media_id")}

    if not ledger:
        print("账本里没有已建草稿的记录，无需对账")
        return EXIT_OK

    if not args.appid or not args.appsecret:
        print("缺少 WX_APPID / WX_APPSECRET 环境变量", file=sys.stderr)
        return EXIT_REJECTED

    client = publish_module.WeChatClient(
        args.appid, args.appsecret, base_url=args.api_base)
    drafts = client.list_drafts()
    in_box = {draft["media_id"]: draft for draft in drafts}

    missing = []
    for slug in sorted(ledger):
        media_id = ledger[slug].get("media_id")
        if media_id not in in_box:
            missing.append({"slug": slug, "media_id": media_id})

    orphans = [
        {"media_id": draft["media_id"], "title": draft["title"]}
        for draft in drafts if draft["media_id"] not in
        {entry.get("media_id") for entry in ledger.values()}
    ]

    # An empty box next to a non-empty ledger is far more likely to be
    # a wrong account or a token problem than a human who really
    # deleted every single draft.  Pruning then would throw the whole
    # ledger away and the next batch would rebuild all of it.
    if not drafts and ledger and not args.force:
        print("草稿箱是空的，但账本里有 {} 条记录——这更像是账号或凭据不对，"
              "不是草稿真的被删光了".format(len(ledger)), file=sys.stderr)
        print("确认要清空的话加 --force", file=sys.stderr)
        return EXIT_REJECTED

    if args.dry_run:
        print("预检：草稿箱 {} 篇，账本 {} 条，将清理 {} 条（不写盘）".format(
            len(drafts), len(ledger), len(missing)))
    else:
        for item in missing:
            store.forget_draft(item["slug"])
        print("草稿箱 {} 篇，账本 {} 条，已清理 {} 条".format(
            len(drafts), len(ledger), len(missing)))

    for item in missing:
        print("  - 草稿已不存在: {} ({})".format(item["slug"], item["media_id"]))
    for item in orphans:
        print("  ? 草稿箱里有但账本没记: {} ({})".format(
            item["title"] or "(无标题)", item["media_id"]))

    report = {
        "drafts_in_box": len(drafts),
        "ledger_entries": len(ledger),
        "missing": missing,
        "orphans": orphans,
        "pruned": bool(missing) and not args.dry_run,
    }
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "reconcile-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8")
    return EXIT_OK


def _load_secrets(path: Path) -> dict:
    """Read optional local credentials from a JSON file.

    The file is optional: the environment variables win, and a missing
    file is not an error.  A malformed file *is* worth reporting -- the
    user probably meant to put credentials there and would otherwise get
    a confusing "missing WX_APPID" further down.
    """
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        print("读取凭据文件失败: {}".format(error), file=sys.stderr)
        return {}
    except json.JSONDecodeError as error:
        print("凭据文件不是合法 JSON: {} ({})".format(path, error), file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        print("凭据文件应为 JSON 对象: {}".format(path), file=sys.stderr)
        return {}
    return data


def _add_common_options(parser, *, suppress: bool) -> None:
    """Add the options every command understands.

    They are registered twice: once on the top-level parser (where they
    may appear before the command) and once on each sub-command (where
    they may appear after it).  The sub-command copies default to
    ``SUPPRESS`` so that an option given before the command is not
    overwritten by the sub-parser's default.
    """
    def default(value):
        return argparse.SUPPRESS if suppress else value

    parser.add_argument("--posts-dir", type=Path, default=default(DEFAULT_POSTS_DIR),
                        help="Hexo 文章目录，默认 source/_posts")
    parser.add_argument("--out-dir", type=Path, default=default(DEFAULT_OUT_DIR),
                        help="产物目录，默认 out")
    parser.add_argument("--source-url", default=default(DEFAULT_SOURCE_URL),
                        help="站点根 URL，用于拼「阅读原文」")
    parser.add_argument("--api-base", default=default(publish_module.DEFAULT_BASE_URL),
                        help="微信接口地址")
    parser.add_argument("--appid", default=default(""), help="公众号 AppID，默认取环境变量")
    parser.add_argument("--appsecret", default=default(""), help="公众号 AppSecret，默认取环境变量")
    parser.add_argument("--author", default=default("growdu"), help="作者署名")
    parser.add_argument("--cover", default=default(""), help="封面图路径，默认取文章首图")
    parser.add_argument("--secrets-file", type=Path, default=default(DEFAULT_SECRETS_FILE),
                        help="本地凭据 JSON，默认 weixin/secrets.json")
    parser.add_argument("--collections-file", type=Path, default=default(DEFAULT_COLLECTIONS_FILE),
                        help="合集配置 JSON，默认 weixin/collections.json")
    parser.add_argument("--category-tag", choices=("top", "bottom", "none"),
                        default=default("top"),
                        help="分类标签位置: top / bottom / none，默认 top")
    parser.add_argument("--notify", default=default(""),
                        help="通知通道: serverchan / wechat_work / webhook，默认取环境变量 WX_NOTIFY")
    parser.add_argument("--notify-key", default=default(""),
                        help="通知凭据（SendKey / webhook key / URL），默认取环境变量 WX_NOTIFY_KEY")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wechat", description="博客到公众号的转换与发布")
    _add_common_options(parser, suppress=False)

    common = argparse.ArgumentParser(add_help=False)
    _add_common_options(common, suppress=True)

    # The options that shape a batch run are shared by ``batch`` and by
    # ``auto-draft``, which ends up calling the batch.
    batch_common = argparse.ArgumentParser(add_help=False)
    batch_common.add_argument("--dry-run", action="store_true", help="只预检，不调接口")
    batch_common.add_argument("--new-only", action="store_true", help="只处理从未建过草稿的")
    batch_common.add_argument("--changed-only", action="store_true", help="只处理内容有变化的")
    batch_common.add_argument("--limit", type=int, default=0, help="本轮最多处理多少篇")
    batch_common.add_argument("--delay", type=float, default=0.0, help="每篇之间的间隔秒数")

    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="盘点文章", parents=[common])
    scan.set_defaults(func=cmd_scan)

    audit = sub.add_parser("audit", help="复算全语料统计", parents=[common])
    audit.set_defaults(func=cmd_audit)

    convert = sub.add_parser("convert", help="转换一篇（不调接口）", parents=[common])
    convert.add_argument("slug", help="文章 slug，例如 database/demo")
    convert.set_defaults(func=cmd_convert)

    publish = sub.add_parser("publish", help="转换并推到草稿箱", parents=[common])
    publish.add_argument("slug", help="文章 slug，例如 database/demo")
    publish.add_argument("--publish", action="store_true", help="额外提交发表")
    publish.set_defaults(func=cmd_publish)

    status = sub.add_parser("status", help="查看发布状态", parents=[common])
    status.set_defaults(func=cmd_status)

    reconcile = sub.add_parser(
        "reconcile", help="对账：账本与草稿箱对齐，清理已删草稿的记录",
        parents=[common])
    reconcile.add_argument("--dry-run", action="store_true", help="只报告，不写盘")
    reconcile.add_argument("--force", action="store_true",
                           help="草稿箱为空时也照常清理")
    reconcile.set_defaults(func=cmd_reconcile)

    categories = sub.add_parser("categories", help="列出分类", parents=[common])
    categories.add_argument("name", nargs="?", default="", help="只看某一个分类")
    categories.set_defaults(func=cmd_categories)

    collections = sub.add_parser("collections", help="列出合集", parents=[common])
    collections.add_argument("name", nargs="?", default="", help="只看某一个合集")
    collections.add_argument("--write", action="store_true",
                             help="写出导览文章与后台勾选清单")
    collections.set_defaults(func=cmd_collections)

    publish_collection = sub.add_parser(
        "publish-collection", help="把合集导览文章推到草稿箱", parents=[common])
    publish_collection.add_argument("name", help="合集标题")
    publish_collection.add_argument("--publish", action="store_true", help="额外提交发表")
    publish_collection.set_defaults(func=cmd_publish_collection)

    batch = sub.add_parser("batch", help="批量把文章推进草稿箱",
                           parents=[common, batch_common])
    batch.set_defaults(func=cmd_batch)

    auto = sub.add_parser("auto-draft", help="新文档自动进草稿箱（定时任务用）",
                          parents=[common, batch_common])
    auto.add_argument("--repo-dir", default=str(DEFAULT_REPO_DIR),
                      help="仓库根目录，默认是本仓库")
    auto.add_argument("--stamp-file", default=str(DEFAULT_STAMP_FILE),
                      help="记录上次同步到哪个 commit 的文件")
    auto.add_argument("--force", action="store_true", help="不管 docs/ 变没变都重新生成")
    auto.set_defaults(func=cmd_auto_draft)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.appid = args.appid or os.environ.get("WX_APPID", "")
    args.appsecret = args.appsecret or os.environ.get("WX_APPSECRET", "")
    args.source_url = os.environ.get("WX_SOURCE_URL", args.source_url)
    args.cover = args.cover or os.environ.get("WX_COVER", "")
    args.notify = args.notify or os.environ.get("WX_NOTIFY", "")
    args.notify_key = args.notify_key or os.environ.get("WX_NOTIFY_KEY", "")
    if not (args.appid and args.appsecret):
        secrets = _load_secrets(args.secrets_file)
        args.appid = args.appid or secrets.get("appid", "")
        args.appsecret = args.appsecret or secrets.get("appsecret", "")
    try:
        return args.func(args)
    except publish_module.WeChatError as error:
        print("微信接口报错: {}".format(error), file=sys.stderr)
        return EXIT_API_ERROR
    except (AssetNotFound, CoverRequired) as error:
        print("资源缺失: {}".format(error), file=sys.stderr)
        return EXIT_REJECTED


if __name__ == "__main__":
    raise SystemExit(main())
