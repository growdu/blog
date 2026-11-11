"""Category tags and collection (合集) plans.

WeChat's open API cannot create a 分类 or a 合集, and the limitation is
structural rather than a missing feature in this pipeline:

- ``draft/add`` has no category or album field.  The article payload
  offers exactly one place for a classification, and that place is the
  body text.
- ``api.weixin.qq.com`` exposes no endpoint for either.  Every
  plausible path probed against a live account answered "invalid url"
  or with an empty body.
- The page that manages 合集 lives at
  ``mp.weixin.qq.com/cgi-bin/appmsgalbummgr``.  That is a
  cookie-authenticated web route with a per-session token, not an
  ``access_token`` endpoint, and it may only hold *published* articles
  -- a draft cannot be added to a 合集.

So the platform-side relation is a human step, and this module
automates the content around it: the category tag printed on an
article, the ordered plan of articles that belong to a collection, and
the index article that leads into one.
"""

from __future__ import annotations

import html as html_lib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from .hexo import slugize
from .render import BODY_FONT, H2_STYLE, MUTED_STYLE, css

__all__ = [
    "ArticleRef",
    "Collection",
    "build_categories",
    "build_category_paths",
    "build_collections",
    "category_archive_url",
    "collection_digest",
    "load_spec",
    "render_category_tag",
    "render_collection_index",
    "render_collection_plan",
    "safe_name",
]

CATEGORY_TAG_STYLE = css("font-size: 13px", "color: #888", "margin: 0 0 18px")
CATEGORY_NAME_STYLE = css("color: #3d7ea6", "font-weight: 700")
COLLECTION_ITEM_STYLE = css("margin: 0 0 14px", "padding: 0 0 12px",
                            "border-bottom: 1px solid #eef0f2")
COLLECTION_TITLE_STYLE = css("font-size: 15px", "font-weight: 700", "margin: 0 0 4px")
COLLECTION_META_STYLE = css("font-size: 12px", "color: #999", "margin: 0")
COLLECTION_LINK_STYLE = css("font-size: 12px", "color: #888", "margin: 4px 0 0",
                             "word-break: break-all")

_UNSAFE_NAME_RE = re.compile(r"[\\/:*?\"<>|]+")


@dataclass(frozen=True)
class ArticleRef:
    """One article as it appears in a category list or a collection."""

    slug: str
    title: str
    digest: str
    permalink: str
    date: str

    @property
    def label(self) -> str:
        """The date as it should be printed: ``2026-01-02``."""
        return self.date[:10]


@dataclass(frozen=True)
class Collection:
    """A named group of articles, ready to become a WeChat 合集."""

    title: str
    description: str
    articles: tuple
    categories: tuple = ()
    path: str = ""

    @property
    def slug(self) -> str:
        """A filesystem-safe identifier for this collection."""
        return safe_name(self.title)

    @property
    def count(self) -> int:
        return len(self.articles)

    def archive_url(self, source_url: str) -> str:
        """The page that lists this collection's articles.

        A collection that maps to a single category points at that
        category's archive page on the blog.  A curated collection
        spans several categories and has no such page, so it points at
        the blog's home page instead.
        """
        if self.path:
            return category_archive_url(source_url, self.title, self.path)
        return source_url.rstrip("/") + "/"


def safe_name(title: str) -> str:
    """Turn a collection title into a name that is safe on disk and in a URL.

    Chinese titles stay as they are -- the filesystem and the blog both
    handle UTF-8 -- but path separators and the characters Windows
    rejects have to go, or the output directory cannot be created.
    """
    cleaned = _UNSAFE_NAME_RE.sub("-", title).strip().strip(".")
    return cleaned or "collection"


def _ref(post) -> ArticleRef:
    return ArticleRef(
        slug=post.slug,
        title=post.title,
        digest=post.digest,
        permalink=post.permalink,
        date=post.date,
    )


def build_categories(posts) -> dict:
    """Group the posts by their front-matter category.

    Ordered by size, largest first, so the tag printed on an article
    leads with the category that actually describes it.
    """
    buckets = {}
    for post in posts:
        ref = _ref(post)
        for name in post.categories:
            buckets.setdefault(name, []).append(ref)
    ordered = sorted(buckets.items(), key=lambda item: (-len(item[1]), item[0]))
    return {name: tuple(items) for name, items in ordered}


def category_archive_url(source_url: str, category: str, path: str = None) -> str:
    """The blog's own archive page for a category.

    Hexo's category generator is enabled with unlimited paging, so the
    page lists every article of that category.  It is the one clickable
    target a WeChat reader can reach from an article, because
    「阅读原文」 is the only link WeChat keeps in the body.
    """
    if path is None:
        path = slugize(category)
    return "{}/categories/{}/".format(source_url.rstrip("/"), quote(path))


def build_category_paths(posts) -> dict:
    """The site's archive path for every category in the corpus.

    A post's categories run from the root of the tree to the leaf, and
    Hexo puts the archive page of a category under its ancestors: a
    post filed under 「数据库深入 / 数据库 / PostgreSQL 源码修炼之路」
    has its page at
    ``/categories/数据库深入/数据库/PostgreSQL-源码修炼之路/``.

    The same name can sit at two depths -- 「数据库」 is a root
    category in its own right and a child of 「数据库深入」 -- so the
    shallowest path is kept: that is the page listing the most
    articles, and the one the site's own category index links to.
    """
    candidates = {}
    for post in posts:
        chain = list(post.categories)
        for index, name in enumerate(chain):
            path = "/".join(slugize(part) for part in chain[:index + 1])
            current = candidates.get(name)
            if current is None or path.count("/") < current.count("/"):
                candidates[name] = path
    return candidates


def load_spec(path: Path) -> list:
    """Read the optional collection specification.

    The file is optional: without it the collections are derived from
    the front-matter categories.  A malformed file is an error rather
    than a fallback -- the user wrote it on purpose, and silently
    publishing different groups would be worse than refusing to start.
    """
    path = Path(path)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("合集配置读取失败: {} ({})".format(path, error)) from error
    if not isinstance(data, dict) or not isinstance(data.get("collections"), list):
        raise ValueError('合集配置格式错误: 需要 {"collections": [...]} 的 JSON 对象')
    return data["collections"]


def build_collections(posts, spec=None, min_articles: int = 2) -> list:
    """Build the collections.

    With a specification the collections are exactly what it says.
    Without one, every category holding at least ``min_articles``
    articles becomes a collection: a category with a single article is
    a tag, not a series.
    """
    if spec:
        return _collections_from_spec(posts, spec)
    return _collections_from_categories(posts, min_articles)


def _collections_from_categories(posts, min_articles: int) -> list:
    paths = build_category_paths(posts)
    collections = []
    for name, refs in build_categories(posts).items():
        if len(refs) < min_articles:
            continue
        # Chronological order: a 合集 is read in sequence, so the
        # articles have to be lined up by date, not by file path.
        ordered = tuple(sorted(refs, key=lambda ref: (ref.date, ref.slug)))
        collections.append(Collection(
            title=name,
            description="「{}」分类下的 {} 篇文章。".format(name, len(refs)),
            articles=ordered,
            categories=(name,),
            path=paths.get(name, ""),
        ))
    return collections


def _collections_from_spec(posts, spec) -> list:
    by_slug = {post.slug: post for post in posts}
    categories_of = {post.slug: set(post.categories) for post in posts}
    collections = []
    seen_titles = set()

    for entry in spec:
        if not isinstance(entry, dict):
            raise ValueError("合集配置项必须是对象: {!r}".format(entry))

        title = str(entry.get("title") or "").strip()
        if not title:
            raise ValueError("合集配置项缺少 title")
        if title in seen_titles:
            raise ValueError("合集标题重复: {}".format(title))
        seen_titles.add(title)

        wanted = {str(name) for name in entry.get("categories", [])}
        extra = [str(slug) for slug in entry.get("slugs", [])]
        exclude = {str(slug) for slug in entry.get("exclude", [])}

        unknown = [slug for slug in extra if slug not in by_slug]
        if unknown:
            raise ValueError("合集「{}」引用了不存在的文章: {}".format(
                title, ", ".join(unknown)))

        selected = {}
        for post in posts:
            if post.slug in exclude:
                continue
            if wanted & categories_of[post.slug]:
                selected[post.slug] = _ref(post)
        for slug in extra:
            if slug not in exclude:
                selected[slug] = _ref(by_slug[slug])

        articles = sorted(selected.values(), key=lambda ref: (ref.date, ref.slug))
        if str(entry.get("order", "asc")).lower() == "desc":
            articles = list(reversed(articles))

        path = str(entry.get("path") or "").strip()
        if not path:
            path = _path_for_chain(posts, wanted, selected)

        collections.append(Collection(
            title=title,
            description=str(entry.get("description") or ""),
            articles=tuple(articles),
            categories=tuple(sorted(wanted)),
            path=path,
        ))

    return collections


def _path_for_chain(posts, wanted, selected) -> str:
    """The archive path of a curated collection.

    The collection has no page of its own, so it borrows the one of the
    first category it covers: the path of that category in the chain of
    the first article that carries it.
    """
    chosen = set(selected)
    for post in posts:
        if post.slug not in chosen:
            continue
        chain = list(post.categories)
        for index, name in enumerate(chain):
            if name in wanted:
                return "/".join(slugize(part) for part in chain[:index + 1])
    return ""


def render_category_tag(categories) -> str:
    """Render the category line printed above an article.

    The names are plain text on purpose: WeChat strips anchors from the
    body, so a link to the category archive would not survive the
    sanitiser.  The reader gets the 「阅读原文」 link instead.
    """
    names = [str(name) for name in categories if name]
    if not names:
        return ""
    tags = " · ".join(
        '<span style="%s">%s</span>' % (CATEGORY_NAME_STYLE, html_lib.escape(name))
        for name in names
    )
    return '<p style="%s">分类 · %s</p>' % (CATEGORY_TAG_STYLE, tags)


def collection_digest(collection: Collection) -> str:
    """The summary of the index article, capped at WeChat's 120 characters."""
    text = "「{}」合集目录，共 {} 篇文章。".format(collection.title, collection.count)
    if collection.description:
        text += collection.description
    return text[:120]


def render_collection_index(collection: Collection, source_url: str) -> str:
    """Render the index article that leads into a collection.

    The article links are printed as text, not as anchors: WeChat
    removes anchors that point outside the account, so a clickable link
    to an article is not available.  The one link that survives is
    「阅读原文」, which the publisher points at the blog's own category
    archive.
    """
    root = source_url.rstrip("/")
    parts = []

    if collection.description:
        parts.append('<p style="%s">%s</p>' % (
            BODY_FONT, html_lib.escape(collection.description)))
    parts.append('<p style="%s">共 %d 篇，按发布时间排列。</p>' % (
        MUTED_STYLE, collection.count))

    for index, ref in enumerate(collection.articles, 1):
        parts.append((
            '<section style="%s">'
            '<p style="%s">%d. %s</p>'
            '<p style="%s">%s</p>'
            '<p style="%s">%s</p>'
            '</section>'
        ) % (
            COLLECTION_ITEM_STYLE,
            COLLECTION_TITLE_STYLE, index, html_lib.escape(ref.title),
            COLLECTION_META_STYLE,
            html_lib.escape(ref.label + ("　" + ref.digest if ref.digest else "")),
            COLLECTION_LINK_STYLE,
            html_lib.escape(root + ref.permalink),
        ))

    return "".join(parts)


def render_collection_plan(collection: Collection, source_url: str) -> str:
    """Render the checklist used to fill the 合集 in the backend.

    The backend's "添加已有内容" picker searches published articles by
    title, so the checklist lists exactly what has to be ticked and in
    which order.  It is the one artefact that turns a collection from a
    plan into a real 合集.
    """
    root = source_url.rstrip("/")
    lines = [
        "# 合集「{}」勾选清单".format(collection.title),
        "",
    ]
    if collection.description:
        lines.extend([collection.description, ""])
    lines.extend([
        "文章数：{}".format(collection.count),
        "",
        "## 勾选顺序",
        "",
    ])
    for index, ref in enumerate(collection.articles, 1):
        lines.append("{}. [ ] {}".format(index, ref.title))
        lines.append("   - 日期：{}".format(ref.label))
        lines.append("   - 原文：{}{}".format(root, ref.permalink))
    lines.extend([
        "",
        "## 后台操作",
        "",
        "1. 登录 mp.weixin.qq.com → 内容与互动 → 合集 → 新建合集",
        "2. 名称填「{}」，简介与封面按需填写".format(collection.title),
        "3. 点「添加已有内容」，按上面的顺序逐条勾选（只列得出已发表的文章）",
        "4. 排序与上面的顺序保持一致，开启「连续阅读」",
        "5. 保存，合集会自动显示在公众号主页",
        "",
    ])
    return "\n".join(lines)
