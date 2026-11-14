"""Turn the site's nginx soft-404 into a real 404.

The bug
-------
``try_files $uri $uri/ /index.html;`` is the SPA fallback.  On a static
site it means *every* unknown URL answers ``200`` with the homepage::

    $ curl -s -o /dev/null -w "%{http_code} %{size_download}" \\
        https://growdu.cn/this-page-does-not-exist-xyz/
    200 120526

The response is byte-identical to ``/`` -- same length, same etag -- so
there is nothing that distinguishes it from the real homepage.

Two consequences, both measured on 2026-11-14:

* **Search engines index the homepage under every wrong URL.**  Every
  typo'd link becomes a duplicate of ``/``.  A site whose whole value
  is search traffic cannot afford that.
* **Link rot is invisible.**  ``curl -o /dev/null -w "%{http_code}"``
  says ``200`` for a link that leads nowhere.  A reachability check
  that only looks at the status code **passes on a dead link** -- which
  is exactly how the podcast's dead landing URLs survived (see
  ``publish/spec/08-站点IP骨架.md`` §2.1: five of six episodes pointed
  at a path that answered 200 with the homepage).

The fix
-------
``try_files $uri $uri/ =404;`` plus ``error_page 404 /404.html;``.

Two details that matter:

* The ``$uri/`` element **stays**.  It is what makes directory
  permalinks (``/archives/``) resolve to their ``index.html`` -- drop
  it and every permalink 404s.
* ``error_page 404 /404.html;`` keeps the **404** status.  nginx
  preserves the original status for an ``error_page`` response unless
  the directive is written as ``error_page 404 =200 /404.html;`` --
  writing ``=200`` would re-introduce the soft-404 under a new name.

Where it lives
--------------
The nginx site config is documented in ``docs/blog/部署到服务器.md``
§2.4, and the running server's copy is ``/etc/nginx/conf.d/blog.conf``
(patched in place by ``tools/fix-soft-404.sh``).  The **document is the
fact source**; ``tests/test_soft_404.py`` keeps the two in step.
"""

from __future__ import annotations

import argparse
import difflib
import re
import shutil
import sys
from pathlib import Path

#: The SPA fallback that causes the soft-404.
SOFT_FALLBACK = "/index.html;"

#: The status-preserving 404 handler.
ERROR_PAGE_DIRECTIVE = "error_page 404 /404.html;"

#: A ``try_files`` line that falls back to the homepage.
#:
#: Matches ``try_files $uri $uri/ /index.html;`` and keeps the leading
#: indentation so the replacement lines up with its neighbours.
_TRY_FILES_RE = re.compile(
    r"^(?P<indent>[ \t]*)try_files[ \t]+(?P<elements>\$uri[ \t]+\$uri/)[ \t]+"
    r"/index\.html;[ \t]*$",
    re.MULTILINE,
)


class Soft404Error(Exception):
    """The config could not be patched -- and that is not a silent no-op."""


def soft_fallback_lines(text: str) -> list[str]:
    """The ``try_files`` lines that still fall back to the homepage."""
    return [m.group(0).strip() for m in _TRY_FILES_RE.finditer(text)]


def is_patched(text: str) -> bool:
    """True when ``text`` already answers unknown paths with a real 404.

    Both halves have to be there: the ``=404`` fallback *and* the
    ``error_page`` that renders the 404 page.  A config with only the
    first returns nginx's bare 404 body; one with only the second still
    serves the homepage with 200.
    """
    if soft_fallback_lines(text):
        return False
    return ERROR_PAGE_DIRECTIVE in text


def problems(text: str) -> list[str]:
    """Everything wrong with ``text`` as a soft-404-free config.

    Empty list means the config is fine.  Each entry says what to do,
    because this is shown to whoever is holding the server.
    """
    issues: list[str] = []
    fallbacks = soft_fallback_lines(text)
    if fallbacks:
        issues.append(
            "未知路径仍 fallback 到首页（软 404）："
            + "；".join(fallbacks)
            + " —— 改成 `try_files $uri $uri/ =404;`"
        )
    if ERROR_PAGE_DIRECTIVE not in text:
        issues.append(
            f"缺 `{ERROR_PAGE_DIRECTIVE}` —— 404 时会显示 nginx 默认页而不是站点的 404 页"
        )
    return issues


def patch(text: str) -> str:
    """Return ``text`` with the soft-404 replaced by a real 404.

    Idempotent: patching an already-patched config returns it unchanged.
    Raises :class:`Soft404Error` when the config does not look like the
    one we know -- a patch that silently does nothing is worse than one
    that refuses.
    """
    if is_patched(text):
        return text

    fallbacks = soft_fallback_lines(text)
    if not fallbacks:
        raise Soft404Error(
            "配置里找不到 `try_files ... /index.html;`，"
            "没有可打补丁的软 404 —— 请人工确认这份配置是不是已经改过"
        )
    if len(fallbacks) > 1:
        raise Soft404Error(
            f"配置里有 {len(fallbacks)} 处 fallback 到首页（{'；'.join(fallbacks)}），"
            "无法确定该改哪一处 —— 请人工确认"
        )

    def _replace(match: re.Match[str]) -> str:
        indent = match.group("indent")
        elements = match.group("elements")
        return (
            f"{indent}try_files {elements} =404;\n"
            f"{indent}{ERROR_PAGE_DIRECTIVE}"
        )

    patched = _TRY_FILES_RE.sub(_replace, text, count=1)
    if patched == text:
        raise Soft404Error("补丁没有改动任何内容 —— 请人工检查")
    return patched


def patch_file(path: Path, dry_run: bool = False) -> bool:
    """Patch the config at ``path`` in place.

    Returns True when the file was changed.  A backup is kept next to
    the original.  ``dry_run`` prints the diff and writes nothing.
    """
    original = path.read_text(encoding="utf-8")
    patched = patch(original)
    if patched == original:
        return False
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        patched.splitlines(keepends=True),
        fromfile=str(path),
        tofile=str(path) + " (patched)",
    )
    sys.stdout.write("".join(diff))
    if dry_run:
        return True
    backup = path.with_suffix(path.suffix + f".bak")
    shutil.copy2(path, backup)
    path.write_text(patched, encoding="utf-8")
    print(f"已打补丁：{path}（备份在 {backup}）")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="把 nginx 的软 404（未知路径回首页）改成真 404。",
    )
    parser.add_argument("conf", help="nginx 站点配置文件路径")
    parser.add_argument(
        "--check",
        action="store_true",
        help="只检查不打补丁；配置已修好时退出码 0，否则 1",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="打印 diff 但不写文件",
    )
    args = parser.parse_args(argv)

    path = Path(args.conf)
    if not path.exists():
        print(f"找不到配置文件：{path}", file=sys.stderr)
        return 3

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"读不了配置文件：{exc}", file=sys.stderr)
        return 3

    if args.check:
        issues = problems(text)
        if not issues:
            print(f"OK：{path} 已经回真 404")
            return 0
        for issue in issues:
            print(f"问题：{issue}", file=sys.stderr)
        return 1

    try:
        changed = patch_file(path, dry_run=args.dry_run)
    except Soft404Error as exc:
        print(f"没有打补丁：{exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"写不了配置文件：{exc}", file=sys.stderr)
        return 3

    if not changed:
        print(f"OK：{path} 已经回真 404，无需改动")
    elif args.dry_run:
        print("（dry-run：没有写文件）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
