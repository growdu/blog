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
import json
import os
import sys
from pathlib import Path

from . import assets as assets_module
from . import audit as audit_module
from . import mermaid as mermaid_module
from . import publish as publish_module
from . import render as render_module
from .mdparse import parse
from .posts import (AUTHOR_LIMIT, BODY_LIMIT, CONTENT_BYTES_LIMIT, CONTENT_LIMIT,
                    TITLE_LIMIT, check_eligibility, discover, load_post)
from .state import StateStore, needs_draft, needs_submit

DEFAULT_POSTS_DIR = Path(__file__).resolve().parents[2] / "source" / "_posts"
DEFAULT_OUT_DIR = Path(__file__).resolve().parents[1] / "out"
DEFAULT_SOURCE_URL = "https://growdu.cn"
DEFAULT_SECRETS_FILE = Path(__file__).resolve().parents[1] / "secrets.json"

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


def _prepare(post, args, resolver=None, highlight: bool = True):
    """Render one post and return the render result."""
    blocks = parse(post.body)
    result = render_module.render(blocks, resolver=resolver, highlight=highlight)
    target_dir = Path(args.out_dir) / post.slug
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "article.html").write_text(result.html, encoding="utf-8")
    return result


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
    print("三层闸门（逐层收紧，每层只数上一层放行的文章）:")
    print("  标题 <= {} 字符         放行 {:>4}  拦下 {:>4}".format(
        TITLE_LIMIT, report.title_ok, report.title_over))
    print("  原始正文 <= {} 字       放行 {:>4}  拦下 {:>4}".format(
        BODY_LIMIT, report.raw_ok, report.raw_over))
    print("  渲染后 <= {} 字符       放行 {:>4}  拦下 {:>4}".format(
        CONTENT_LIMIT, report.render_ok, report.render_over))
    print()
    print("可发布: {} 篇 ({:.1f}%)，跳过 {} 篇".format(
        report.publishable, report.publishable_ratio,
        report.posts - report.publishable))
    print("  其中只有关掉代码高亮才放得下: {} 篇".format(report.needs_plain_only))
    print()
    print("全语料口径:")
    print("  原始正文 <= {} 字       {:>4} 篇".format(BODY_LIMIT, report.raw_within))
    print("  渲染后放得下（带高亮）  {:>4} 篇".format(report.fit_highlight))
    print("  渲染后放得下（关高亮）  {:>4} 篇".format(report.fit_plain))
    print("  正文长度中位            带高亮 {} 字符, 关高亮 {} 字符".format(
        report.median_highlight, report.median_plain))
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
    print("  标题: {} ({} 字符)".format(post.title, len(post.title)))
    print("  摘要: {}".format(post.digest))
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
        prepared = assets_module.prepare_image(resolved)
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
    """
    urls = []
    failures = []
    for url in result.external_images:
        try:
            data = assets_module.download_image(url)
            prepared = assets_module.prepare_image_bytes(data, stem="ext")
            urls.append(client.upload_body_image(prepared.data, prepared.filename))
        except (ValueError, OSError, publish_module.WeChatError) as error:
            urls.append(None)
            failures.append((url, str(error)))
    return urls, failures


def _upload_cover(client, result, args):
    """Upload the cover image and return ``(media_id, crop_percent_list)``.

    WeChat requires a cover.  Without a configured cover the article's
    first image is used; an article with neither cannot be published.
    """
    cover_path = args.cover
    if not cover_path and result.assets:
        cover_path = result.assets[0]
    if not cover_path:
        raise CoverRequired(
            "文章没有图片，也没有指定封面图：请用 --cover 或 WX_COVER 指定一张封面")
    resolved = _resolve_asset(cover_path, args.posts_dir)
    if not resolved.is_file():
        raise AssetNotFound("封面图不存在: {}".format(resolved))
    prepared = assets_module.prepare_image(resolved)
    media_id = client.upload_cover(prepared.data, prepared.filename)
    return media_id, assets_module.cover_crop_list(prepared.width, prepared.height)


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

    assets = _mermaid_assets(post, args)
    result = _prepare(post, args, resolver=_Resolver(assets))

    # The raw-body check above is only a pre-gate: the length WeChat
    # enforces is the length of the rendered content, which is larger
    # than the markdown because every element carries inline styles.
    if result.content_length > CONTENT_LIMIT:
        plain = _prepare(post, args, resolver=_Resolver(assets), highlight=False)
        if plain.content_length < result.content_length:
            result = plain

    if result.content_length > CONTENT_LIMIT:
        print("渲染后正文 {} 字符，超过上限 {} 字符，已拒绝发布".format(
            result.content_length, CONTENT_LIMIT), file=sys.stderr)
        print("提示：这类文章需要拆成多篇，或在公众号发摘要版并把全文放在阅读原文", file=sys.stderr)
        return EXIT_REJECTED

    if len(result.html.encode("utf-8")) >= CONTENT_BYTES_LIMIT:
        print("渲染后正文 {} 字节，超过上限 {} 字节，已拒绝发布".format(
            len(result.html.encode("utf-8")), CONTENT_BYTES_LIMIT), file=sys.stderr)
        return EXIT_REJECTED

    client = publish_module.WeChatClient(
        args.appid, args.appsecret, base_url=args.api_base)

    store = StateStore(Path(args.out_dir) / "state.json")
    state = store.get(post.slug)

    urls = _upload_assets(client, result, args)
    html = result.substitute(urls)

    external_failures = []
    if result.external_images:
        external_urls, external_failures = _fetch_external_images(client, result)
        html = result.substitute_external(
            external_urls, fallback=EXTERNAL_IMAGE_FALLBACK, html=html)

    cover_media_id, crop_list = _upload_cover(client, result, args)

    article = {
        "article_type": "news",
        "title": post.title,
        "author": args.author,
        "digest": post.digest,
        "content": html,
        "content_source_url": args.source_url.rstrip("/") + post.permalink,
        "thumb_media_id": cover_media_id,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
        "cover_info": {"crop_percent_list": crop_list},
    }

    if needs_draft(post.fingerprint, state):
        state.media_id = client.add_draft(article)
        state.fingerprint = post.fingerprint
        state.publish_id = None
        state.publish_status = None
        store.save(post.slug, state)
    else:
        print("内容未变，复用已有草稿 {}".format(state.media_id))

    if args.publish and needs_submit(state):
        state.publish_id = client.freepublish_submit(state.media_id)
        store.save(post.slug, state)

    print("已建草稿: {}".format(post.slug))
    print("  media_id: {}".format(state.media_id))
    print("  正文长度: {} 字符".format(result.content_length))
    print("  阅读原文: {}{}".format(args.source_url.rstrip("/"), post.permalink))
    if result.external_images:
        fetched = len(result.external_images) - len(external_failures)
        print("  外链图转存: {} / {} 张".format(fetched, len(result.external_images)))
    for url, error in external_failures:
        print("    ! 原图未能转存: {} -> {}".format(url, error))
    if state.publish_id:
        print("  publish_id: {}".format(state.publish_id))
    else:
        print("  未提交发表（如需自动发表请加 --publish）")
    return EXIT_OK


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wechat", description="博客到公众号的转换与发布")
    _add_common_options(parser, suppress=False)

    common = argparse.ArgumentParser(add_help=False)
    _add_common_options(common, suppress=True)

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

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.appid = args.appid or os.environ.get("WX_APPID", "")
    args.appsecret = args.appsecret or os.environ.get("WX_APPSECRET", "")
    args.source_url = os.environ.get("WX_SOURCE_URL", args.source_url)
    args.cover = args.cover or os.environ.get("WX_COVER", "")
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
