"""Clean up the drafts that empty articles left behind.

Run from the repository root:

    python3 weixin/tools/prune-empty-drafts.py [--dry-run]

Some articles in the corpus carry nothing but their front matter -- a
page with a title and no text.  The pipeline does not draft those any
more, but the shells they used to produce are still in the draft box:
a title, a category line and a signature around no article at all.

This tool finds them and removes them.  Before removing anything it
reads the draft back: a draft whose body has grown since it was
created is **not** a shell any more -- the author wrote into it -- and
it is left alone and reported.

The ledger is cleaned up as well, so the next batch does not try to
refresh a draft that is no longer there.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "weixin"))

from wechat.posts import discover, is_empty, is_empty_shell  # noqa: E402
from wechat.publish import WeChatClient  # noqa: E402
from wechat.state import StateStore  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="清理空文章留下的草稿")
    parser.add_argument("--dry-run", action="store_true",
                        help="只报告，不删也不改账本")
    parser.add_argument("--posts-dir", type=Path,
                        default=ROOT / "source" / "_posts",
                        help="文章目录，默认 source/_posts")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "weixin" / "out",
                        help="产物目录，默认 weixin/out")
    parser.add_argument("--secrets-file", type=Path,
                        default=ROOT / "weixin" / "secrets.json",
                        help="本地凭据 JSON，默认 weixin/secrets.json")
    args = parser.parse_args(argv)

    posts = discover(args.posts_dir)
    empty_slugs = {post.slug for post in posts if is_empty(post)}

    store = StateStore(Path(args.out_dir) / "state.json")
    ledger = store.all()
    candidates = [key for key in sorted(ledger)
                  if key.split("#")[0] in empty_slugs
                  and ledger[key].get("media_id")]

    if not candidates:
        print("没有空文章留下的草稿")
        return 0

    secrets = json.loads(Path(args.secrets_file).read_text(encoding="utf-8"))
    client = WeChatClient(secrets["appid"], secrets["appsecret"])

    removed = []
    kept = []
    for key in candidates:
        media_id = ledger[key]["media_id"]
        try:
            draft = client.get_draft(media_id)
            article = draft["news_item"][0]
        except Exception as error:  # noqa: BLE001 - 只报告，不中断
            kept.append((key, "回读失败: {}".format(error)))
            continue
        content = article.get("content", "")
        if not is_empty_shell(content):
            # The author wrote into it.  It is an article now.
            kept.append((key, "正文 {} 字符，已经不是空壳了".format(len(content))))
            continue
        if args.dry_run:
            removed.append((key, media_id))
            continue
        try:
            client.delete_draft(media_id)
        except Exception as error:  # noqa: BLE001
            kept.append((key, "删除失败: {}".format(error)))
            continue
        store.forget_draft(key)
        removed.append((key, media_id))

    print("空文章 {} 篇，账本里对应的草稿 {} 个".format(len(empty_slugs), len(candidates)))
    print()
    if removed:
        print("{} {} 个:".format("将要删除" if args.dry_run else "已删除", len(removed)))
        for key, media_id in removed:
            print("  - {} ({})".format(key, media_id))
    if kept:
        print("跳过 {} 个:".format(len(kept)))
        for key, reason in kept:
            print("  ? {} -> {}".format(key, reason))
    if not args.dry_run:
        print()
        print("账本已更新")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
