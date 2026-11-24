#!/usr/bin/env python3
"""把 Font Awesome 的字体裁剪到本站真正用到的那些图标。

为什么值得做
------------
``fa-solid-900.woff2`` 151 KB、``fa-brands-400.woff2`` 103 KB。浏览器第一次
访问时会把它们整个拉下来——woff2 本身已经压过一轮，再上 gzip 也省不下几个
字节。而本站实际用到的图标只有 90 个上下（模板里 96 个 class，正文里 2 个），
裁剪之后两个字体加起来只剩十几 KB。

比"少引几个图标类"更值的地方在于：图标少不等于字体小。字体里装的是
Font Awesome 全集几千个字形，一个图标少一个，文件大小几乎不变。

三个容易踩的坑，这里都处理了
----------------------------
1. **一条规则里有多个图标类**。Font Awesome 6 的 CSS 是这样写的：
   ``.fa-bolt:before,.fa-zap:before{content:"\\f0e7"}``——别名（alias）
   和主名共用一条规则。只认第一个就会漏掉别名，站点用别名时图标变空白。
2. **图标类本身不带字体信息**。字体是由同一段 class 里的族前缀决定的
   （``fab`` 是 brands，``far`` 是 regular，其余按 solid 算）。认错族，
   码位就会被裁进错误的字体——不报错，只是空白。
3. **裁剪器不会告诉你码位本来就不在这个字体里**。把 brands 图标的码位
   裁进 solid 字体，fontTools 会给它补一个 .notdef 字形，cmap 里也有这个
   码位了，看起来一切正常，页面上却是个豆腐块。所以这里在裁之前先拿
   **原字体**的 cmap 对一遍：码位本来就不在这个字体里，就是族判错了，
   直接报错退出。
4. **有些图标只出现在脚本里**。白天/黑夜那个切换按钮，HTML 里写的是
   ``<i id="sum-moon-icon" class="fas fa-sun">``，可脚本会把它换成
   ``fa-moon``——``fa-moon`` 从来没进过任何 ``class="..."`` 属性。
   只扫 class 属性的做法会把它漏掉，码位被裁掉，线上那个按钮就是一个
   豆腐块（框里一个叉）。所以这里除了 class 属性，还把文本里出现的
   图标类一并收进来（族靠码位反查：哪个字体的 cmap 里有这个码位就是
   哪个族）。

怎么做
------
1. 从 ``all.min.css`` 里读出每个图标类的码位——以 CSS 为准，不依赖
   fontawesome 的 metadata，两者版本对不上时 CSS 才是浏览器真正认的东西；
2. 从构建产物 ``public/**/*.html`` 和主题模板里找出真正用到的图标类，
   并从**同一段 class** 里认出字体族；
3. 把脚本里动态换上去的图标（class 属性里扫不到的那些）补进来；
4. 用 fontTools 把每个字体裁到用到的码位，原地替换 ``public`` 里的字体文件。

用法::

    python3 tools/subset-icons.py --public public
    python3 tools/subset-icons.py --public public --dry-run

依赖 fontTools（裁 woff2 还需要 brotli）。CI 里现装现用，不进仓库依赖。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# 一条图标规则：.fa-a:before,.fa-b:before{content:"\fYYY"}
_ICON_RULE = re.compile(
    r'((?:\.[a-z0-9-]+:before)(?:,\.[a-z0-9-]+:before)*)'
    r'\{content:"\\([0-9a-fA-F]+)\s?"\}'
)
# CSS 里出现过的所有 class（用来区分"图标类"和"修饰类"）
_ANY_CLASS = re.compile(r'\.([a-z][a-z0-9-]*)')
# 一段 class 属性
_CLASS_ATTR = re.compile(r'class\s*=\s*["\']([^"\']*)["\']')
# class 里的图标类
_ICON_CLASS = re.compile(r'\bfa-[a-z0-9-]+\b')

# 字体族 -> 字体文件名前缀
_FAMILY_FILES = {
    "brands": "fa-brands-400",
    "regular": "fa-regular-400",
    "solid": "fa-solid-900",
}


def _family_of(class_attr: str) -> str:
    """从一段 class 里认出字体族。

    Font Awesome 的图标类本身不带字体信息，字体是由同段的族前缀
    （``fab`` / ``far`` / ``fas``）决定的。认错了族，图标就会去错误的
    字体里找码位——不报错，只是变空白。
    """
    classes = set(class_attr.split())
    if "fab" in classes or "fa-brands" in classes:
        return "brands"
    if "far" in classes or "fa-regular" in classes:
        return "regular"
    return "solid"


def _parse_css(css_text: str) -> tuple[dict[str, int], set[str]]:
    """返回 (图标类 -> 码位, 修饰类集合)。

    修饰类是 CSS 里有规则、但没有 ``:before`` 内容的那些 class
    （``fa-fw``、``fa-spin``、``fa-3x``……），它们不是图标，不需要字形。
    从 CSS 自己推出来，比手写一张白名单可靠——版本升级也不会漏。
    """
    icons: dict[str, int] = {}
    for match in _ICON_RULE.finditer(css_text):
        try:
            code = int(match.group(2), 16)
        except ValueError:
            continue
        for selector in match.group(1).split(","):
            name = selector.strip().lstrip(".").replace(":before", "")
            if name:
                icons[name] = code

    all_classes = set(_ANY_CLASS.findall(css_text))
    modifiers = {c for c in all_classes if c not in icons}
    return icons, modifiers


def _used_icons(texts: list[str]) -> dict[str, set[str]]:
    """扫描文本，返回 {字体族: {图标类}}。"""
    used: dict[str, set[str]] = {"brands": set(), "regular": set(), "solid": set()}
    for text in texts:
        for attr in _CLASS_ATTR.findall(text):
            icons = _ICON_CLASS.findall(attr)
            if not icons:
                continue
            family = _family_of(attr)
            used[family].update(icons)
    return used


def _loose_icons(texts: list[str], modifiers: set[str]) -> set[str]:
    """文本里出现过的所有图标类 —— 不管它出现在哪儿。

    只认 ``class="..."`` 属性会漏掉一类图标：脚本里 ``addClass('fa-moon')``
    换上去的。它们从来没进过 class 属性，码位被裁掉之后页面上就是一个
    豆腐块（框里一个叉），不报任何错。
    """
    names: set[str] = set()
    for text in texts:
        for name in _ICON_CLASS.findall(text):
            if name not in modifiers:
                names.add(name)
    return names


def _add_script_icons(
    texts: list[str],
    used: dict[str, set[str]],
    codepoints: dict[str, int],
    modifiers: set[str],
    original_cmaps: dict[str, set[int]],
) -> list[str]:
    """把脚本里动态换上去的图标补进 ``used``，返回补进去的图标名。

    这些图标没有同段的族前缀（``addClass('fa-moon')`` 里只有图标名），
    族靠码位反查：哪个字体的 cmap 里有这个码位，就是哪个族；solid 和
    regular 都有的话算 solid；反查不了就先按 solid 算 —— 真裁错了，
    裁之前那道「码位本来就不在这个字体里」的核对会兜住（宁可放弃裁剪，
    也不上线空白图标）。
    """
    already: set[str] = set()
    for names in used.values():
        already |= names

    added: list[str] = []
    for icon in sorted(_loose_icons(texts, modifiers)):
        if icon in already:
            continue
        code = codepoints.get(icon)
        if code is None:
            continue
        candidates = [f for f, cps in original_cmaps.items() if code in cps]
        if candidates and "solid" not in candidates:
            family = candidates[0]
        else:
            family = "solid"
        used[family].add(icon)
        already.add(icon)
        added.append(icon)
    return added


def _read_texts(root: Path, suffixes: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for suffix in suffixes:
        for path in root.rglob("*" + suffix):
            try:
                out.append(path.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
    return out


def _subset_font(src: Path, dst: Path, codepoints: set[int]) -> None:
    """把一个字体裁到给定码位。"""
    from fontTools import subset  # 延迟导入：没装 fontTools 时报错更直白

    options = subset.Options()
    options.layout_features = ["*"]
    options.drop_tables += ["DSIG"]
    options.notdef_outline = True
    options.recalc_bounds = True
    # woff2 需要 brotli；ttf 不需要。
    options.flavor = "woff2" if dst.suffix.lower() == ".woff2" else None

    font = subset.load_font(str(src), options)
    try:
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(unicodes=codepoints)
        subsetter.subset(font)
        subset.save_font(font, str(dst), options)
    finally:
        # 必须显式关掉：fontTools 默认惰性加载，文件句柄还开着的话，
        # Windows 上 os.replace 会报 [WinError 5] 拒绝访问。
        font.close()


def _cmap_codepoints(path: Path) -> set[int]:
    from fontTools.ttLib import TTFont

    with TTFont(str(path), lazy=True) as font:
        codepoints: set[int] = set()
        for table in font["cmap"].tables:
            if table.isUnicode():
                codepoints.update(table.cmap.keys())
        return codepoints


def _original_codepoints(webfonts: Path) -> dict[str, set[int]]:
    """每个字体族原始 TTF 里的码位（用来反查一个图标属于哪个族）。"""
    out: dict[str, set[int]] = {}
    for family, name in _FAMILY_FILES.items():
        path = webfonts / (name + ".ttf")
        if path.is_file():
            out[family] = _cmap_codepoints(path)
    return out


def _import_module(name: str):
    """单独抽出来，方便测试把"缺依赖"这条路径走一遍。"""
    return __import__(name)


def _fonttools_ready() -> bool:
    """裁剪要 fontTools。

    缺了就明说，而不是让构建以一句看不懂的 ImportError 收场——CI 里这一步
    失败不影响发布，但得让人一眼看出是"没装上"而不是"裁不动"。

    只依赖 fontTools 本身：2026-11-15 实测 runner 上的 brotli 解 woff2 会
    报 "brotli: decoder failed"，所以这里改为裁 TTF（fontTools 原生支持，
    不需要 brotli），再把 CSS 里的 woff2 引用摘掉，让浏览器用裁过的 TTF。
    """
    try:
        _import_module("fontTools")
    except ImportError:
        print(
            "::warning::字体裁剪跳过：缺少 fontTools"
            "（CI 里用 pip install fonttools 装）"
        )
        return False
    return True


def _patch_css(css_path: Path, names: list[str]) -> int:
    """把 @font-face 里指向 woff2 的那一条引用摘掉。

    CSS 的 ``src`` 列表是"按顺序挑第一个支持的格式"，所以浏览器会一直
    优先用 woff2——只裁 TTF 的话，浏览器还是去下那个完整的大 woff2，省不到
    任何东西。摘掉之后浏览器才会用裁过的 TTF。

    留着的 woff2 文件本身不删（只是没人引用了）：万一补丁没生效，浏览器拿到
    的仍然是一个能用的字体，不会变成方块。

    带 ``unicode-range`` 的块不动——那是给 Font Awesome 3/4 时代的老类名
    准备的兼容块，那些码位本来就不在裁剪范围里，动了它们老图标就废了。
    """
    text = css_path.read_text(encoding="utf-8")
    total = 0

    def strip_woff2(match):
        nonlocal total
        block = match.group(0)
        if "unicode-range" in block:
            return block
        for name in names:
            pattern = re.compile(
                r"url\(\.\./webfonts/" + re.escape(name) + r"\.woff2\)\s*"
                r"format\(\"woff2\"\)\s*,\s*"
            )
            block, count = pattern.subn("", block)
            total += count
        return block

    text = re.sub(r"@font-face\{[^}]*\}", strip_woff2, text)
    if total:
        css_path.write_text(text, encoding="utf-8")
    return total



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--public", default="public", help="构建产物目录（默认 public）"
    )
    parser.add_argument(
        "--theme",
        default=os.path.join("themes", "matery"),
        help="主题目录，用来补扫模板里动态插入的图标",
    )
    parser.add_argument(
        "--css", default=None, help="Font Awesome 的 all.min.css（默认在 --public 里找）"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="只报告，不改文件"
    )
    args = parser.parse_args()

    public = Path(args.public)
    if not public.is_dir():
        print(f"找不到构建产物目录：{public}", file=sys.stderr)
        return 1

    css_path = Path(args.css) if args.css else None
    if css_path is None:
        for candidate in (
            public / "libs" / "awesome" / "css" / "all.min.css",
            public / "lib" / "awesome" / "css" / "all.min.css",
        ):
            if candidate.is_file():
                css_path = candidate
                break
    if css_path is None or not css_path.is_file():
        print(
            "找不到 Font Awesome 的 all.min.css——没法知道每个图标类的码位",
            file=sys.stderr,
        )
        return 1

    css_text = css_path.read_text(encoding="utf-8")
    codepoints, modifiers = _parse_css(css_text)
    if not codepoints:
        print(f"{css_path} 里没解析出任何图标规则", file=sys.stderr)
        return 1

    # 用到的图标：构建产物里的（真正渲染出来的）+ 主题模板里的（脚本动态插入的）
    html_texts = _read_texts(public, (".html",))
    template_texts: list[str] = []
    theme = Path(args.theme)
    if theme.is_dir():
        template_texts = _read_texts(theme, (".ejs", ".js"))

    used = _used_icons(html_texts + template_texts)

    webfonts = css_path.parent.parent / "webfonts"
    if not webfonts.is_dir():
        webfonts = public / "libs" / "awesome" / "webfonts"

    # 脚本里动态换上去的图标（class 属性里扫不到的那些）也得留着 ——
    # 白天/黑夜那个按钮就是 ``fa-moon``，2026-11-24 上线后它是个豆腐块。
    original_cmaps = _original_codepoints(webfonts) if _fonttools_ready() else {}
    added = _add_script_icons(
        html_texts + template_texts, used, codepoints, modifiers, original_cmaps
    )

    per_family: dict[str, set[int]] = {}
    unknown: set[str] = set()
    for family, icons in used.items():
        keep: set[int] = set()
        for icon in sorted(icons):
            code = codepoints.get(icon)
            if code is None:
                if icon not in modifiers:
                    unknown.add(icon)
                continue
            keep.add(code)
        per_family[family] = keep

    print(f"Font Awesome 图标清单（来自 {css_path.name}）：")
    for family in ("solid", "regular", "brands"):
        print(f"  {family:8s} 用到 {len(used[family]):3d} 个图标类")
    if added:
        print(
            "  脚本里动态换上去的图标（class 属性里扫不到，也得留着）："
            + " ".join(added)
        )
    if unknown:
        print(
            "  ! 以下 class 在 CSS 里没有对应规则，图标本来就是空的（不是本次裁剪造成的）："
            + " ".join(sorted(unknown))
        )

    if args.dry_run:
        for family, keep in per_family.items():
            name = _FAMILY_FILES[family]
            path = webfonts / (name + ".ttf")
            if path.is_file():
                print(f"  [dry-run] {path.name} 保留 {len(keep)} 个码位")
        return 0

    if not _fonttools_ready():
        print("  字体文件保持原样，站点不受影响。")
        return 0

    total_before = 0
    total_after = 0
    staged: list[tuple[Path, Path]] = []
    subsetted: list[str] = []
    try:
        for family, keep in per_family.items():
            name = _FAMILY_FILES[family]
            if not keep:
                print(f"  {name}: 没用到，字体文件保持原样")
                continue
            # 只裁 TTF：fontTools 原生支持，不需要 brotli；woff2 的解码在
            # runner 上出过 "brotli: decoder failed"，不值得为省几 KB 去赌。
            # CSS 里对应的 woff2 引用会在裁完后摘掉，浏览器于是用裁过的 TTF。
            src = webfonts / (name + ".ttf")
            if not src.is_file():
                continue

            # 裁之前先拿原字体对一遍：码位本来就不在这个字体里，说明字体族
            # 判错了（brands 的码位被当成 solid 的）。裁剪器会默默补一个
            # .notdef 字形，裁完 cmap 里也有这个码位了——不提前拦，页面上
            # 就是个豆腐块。
            original = _cmap_codepoints(src)
            missing_in_original = sorted(keep - original)
            if missing_in_original:
                raise RuntimeError(
                    f"{src.name} 有 {len(missing_in_original)} 个码位本来就不在这个字体里"
                    f"（例如 {[hex(c) for c in missing_in_original[:5]]}）"
                    f"——字体族判断错了，裁下去只会得到空白图标"
                )

            tmp = src.with_suffix(src.suffix + ".subset")
            _subset_font(src, tmp, keep)

            # 自检：裁完的字体里必须真的有每个用到的码位
            available = _cmap_codepoints(tmp)
            missing = sorted(keep - available)
            if missing:
                raise RuntimeError(
                    f"{src.name} 裁完还缺 {len(missing)} 个码位"
                    f"（例如 {[hex(c) for c in missing[:5]]}）"
                    f"——宁可放弃裁剪，也不要上线空白图标"
                    )

            staged.append((src, tmp))

            #  sanity: 裁完不应该比原来还大（除非只剩一两个字形，
            # 那时字体头本身的占比就上去了，留着原文件反而更稳）
            if tmp.stat().st_size >= src.stat().st_size:
                raise RuntimeError(
                    f"{src.name} 裁完没有变小（{src.stat().st_size} -> "
                    f"{tmp.stat().st_size}），保留原文件"
                )
            subsetted.append(name)

        # 全部裁成功才替换：半套字体（一套裁了、一套没裁）虽然也能跑，
        # 但排查起来很难看出是哪一步出了问题。
        for src, tmp in staged:
            before = src.stat().st_size
            after = tmp.stat().st_size
            os.replace(tmp, src)
            total_before += before
            total_after += after
            print(
                f"  {src.name}: {before / 1024:.1f} KB -> {after / 1024:.1f} KB"
                f"（{len(_cmap_codepoints(src))} 个字形）"
            )

        # 字体换成裁过的 TTF 之后，CSS 里得把 woff2 那条引用摘掉，否则
        # 浏览器还是去下完整的大 woff2，等于没裁。woff2 文件本身留着
        # （没人引用了而已）：万一补丁没生效，浏览器拿到的仍然是一个
        # 能用的字体，不会变成方块。
        if subsetted:
            patched = _patch_css(css_path, subsetted)
            print(
                f"  {css_path.name}: 摘掉 {patched} 处 woff2 引用，"
                "浏览器改用裁过的 TTF"
            )
    except Exception as exc:  # noqa: BLE001 - 构建期要给出可读的失败原因
        for _, tmp in staged:
            if tmp.exists():
                tmp.unlink()
        print(f"::warning::字体裁剪放弃：{exc}")
        print("  字体文件保持原样，站点不受影响。", file=sys.stderr)
        return 1

    if total_before:
        print(
            f"字体总体积 {total_before / 1024:.1f} KB -> {total_after / 1024:.1f} KB"
            f"（省 {(total_before - total_after) / 1024:.1f} KB）"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
