"""中文字体解析：跨平台挑一款能用的中文字体。

macOS 自带 `PingFang SC`；Linux 上没有等价物——PingFang 是 Apple 的授权
字体，**不能随仓库分发**。Linux 上退到开源的 `Noto Sans CJK SC` /
`Source Han Sans SC`（思源黑体）。

**代价**：同一段文字在 macOS 与 Linux 上渲染出的像素不一样（字形不同）。
文案、字幕内容一字不变，视觉上仍是同一套现代无衬线黑体。
验收口径按「视觉等价」而不是「逐像素一致」，见《形象与音色规范》。

选中的字体族名由 `font_family()` 统一给出——渲染代码不要再各自硬编码
`PingFang SC`，否则换平台时会静默画成豆腐块。

优先级：

1. `AIV_FONT_FAMILY` 环境变量（显式指定族名，最高优先级）
2. 已知路径上的字体文件——**macOS 的 PingFang 排在 Linux 的 Noto 前面**，
   这样在 macOS 上出来的画面与历史版本逐像素一致
3. `fontconfig`（Linux 上 cairo 就是靠它按族名解析字体）：问它要一款
   支持中文（`:lang=zh`）的字体
4. 都没有 → 抛错，报错信息里给出安装命令
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache

# 环境变量：显式指定字体族名（CI、特殊机器用）
FONT_ENV = "AIV_FONT_FAMILY"

INSTALL_HINT = (
    "Debian/Ubuntu: sudo apt-get install -y fonts-noto-cjk\n"
    "  Fedora/RHEL:  sudo dnf install google-noto-sans-cjk-fonts\n"
    "  Arch:         sudo pacman -S noto-fonts-cjk\n"
    "  或自带字体：把 NotoSansCJK-Regular.ttc 放进 "
    "~/.local/share/fonts/ 后跑 fc-cache -f"
)

# 探测不到字形时的探针字符（Unicode 私有区，字体一般没有）
_MISSING_GLYPH = "\ue000"


@dataclass(frozen=True)
class FontCandidate:
    """一个候选字体：文件路径 → cairo 用的字体族名。"""

    path: str
    family: str
    label: str


@dataclass(frozen=True)
class ResolvedFont:
    """挑中的那款字体。"""

    family: str
    path: str | None
    label: str
    resolves: bool


# ---- macOS：系统自带 PingFang SC ----------------------------------------

MACOS_CANDIDATES = (
    FontCandidate("/System/Library/Fonts/PingFang.ttc",
                  "PingFang SC", "PingFang SC（macOS 自带）"),
    FontCandidate("/System/Library/Fonts/PingFang SC.ttc",
                  "PingFang SC", "PingFang SC（macOS 自带）"),
)

# macOS 新版把 PingFang 放进可下载资产目录，文件名带哈希，需 glob
MACOS_ASSET_GLOB = (
    "/System/Library/AssetsV2/com_apple_MobileAsset_Font8/*/AssetData/PingFang.ttc"
)

# ---- Linux：开源中文字体 --------------------------------------------------

LINUX_CANDIDATES = (
    FontCandidate("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                  "Noto Sans CJK SC", "Noto Sans CJK SC（fonts-noto-cjk）"),
    FontCandidate("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
                  "Noto Sans CJK SC", "Noto Sans CJK SC（fonts-noto-cjk）"),
    FontCandidate("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                  "Noto Sans CJK SC", "Noto Sans CJK SC（fonts-noto-cjk）"),
    FontCandidate("/usr/share/fonts/opentype/noto/NotoSansCJK-VF.ttc",
                  "Noto Sans CJK SC", "Noto Sans CJK SC（可变字重）"),
    FontCandidate("/usr/share/fonts/opentype/source-han-sans/SourceHanSansSC-Regular.otf",
                  "Source Han Sans SC", "思源黑体 Source Han Sans SC"),
    FontCandidate("/usr/share/fonts/truetype/source-han-sans/SourceHanSansSC-Regular.otf",
                  "Source Han Sans SC", "思源黑体 Source Han Sans SC"),
)

# 自己装到 home / /usr/local 下的
USER_FONT_GLOBS = (
    "~/.local/share/fonts/**/NotoSansCJK*",
    "~/.local/share/fonts/**/SourceHanSansSC*",
    "~/.fonts/**/NotoSansCJK*",
    "~/.fonts/**/SourceHanSansSC*",
    "/usr/local/share/fonts/**/NotoSansCJK*",
    "/usr/local/share/fonts/**/SourceHanSansSC*",
)

# fontconfig 兜底时优先问这些族名
FALLBACK_FAMILIES = (
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "PingFang SC",
    "Hiragino Sans GB",
    "Microsoft YaHei",
    "WenQuanYi Zen Hei",
)


def _expand(patterns: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for pattern in patterns:
        out.extend(sorted(glob.glob(os.path.expanduser(pattern), recursive=True)))
    return out


def _all_candidates() -> list[FontCandidate]:
    """所有候选，按优先级排：macOS 优先（画面与历史版本一致），再 Linux。"""
    candidates: list[FontCandidate] = list(MACOS_CANDIDATES)
    candidates.extend(
        FontCandidate(path, "PingFang SC", "PingFang SC（macOS 可下载资产）")
        for path in _expand((MACOS_ASSET_GLOB,))
    )
    candidates.extend(LINUX_CANDIDATES)
    candidates.extend(
        FontCandidate(path, "Noto Sans CJK SC", "Noto Sans CJK SC（用户自装）")
        for path in _expand(USER_FONT_GLOBS)
    )
    return candidates


def _resolved_width(family: str, sample: str = "并行解码") -> float:
    """cairo 实际解析该字体族后的文本宽度。"""
    import cairo

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    ctx = cairo.Context(surface)
    ctx.select_font_face(family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(40)
    return ctx.text_extents(sample).width


def family_resolves(family: str) -> bool:
    """这个族名能不能被 cairo 解析出来（而不是静默回退到默认字体）。

    判定方式：真字体族与不存在字体的文本宽度必然不同。
    """
    try:
        fallback = _resolved_width("__NoSuchFontFamily__")
        return abs(_resolved_width(family) - fallback) > 0.5
    except Exception:
        return False


def _fc_chinese_families() -> list[str]:
    """问 fontconfig 要支持中文的字体族名（Linux 上 cairo 靠它解析）。"""
    exe = shutil.which("fc-list")
    if not exe:
        return []
    try:
        proc = subprocess.run(
            [exe, ":lang=zh", "family"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    families: list[str] = []
    for line in proc.stdout.splitlines():
        for name in line.split(","):
            name = name.strip()
            if name and name not in families:
                families.append(name)
    return families


@lru_cache(maxsize=1)
def resolve_font() -> ResolvedFont:
    """挑一款可用的中文字体。找不到就返回 resolves=False 的占位结果。"""
    env = os.environ.get(FONT_ENV, "").strip()
    if env:
        return ResolvedFont(env, None, f"{env}（{FONT_ENV} 指定）",
                            family_resolves(env))

    for candidate in _all_candidates():
        if os.path.exists(candidate.path):
            return ResolvedFont(
                candidate.family, candidate.path, candidate.label,
                family_resolves(candidate.family),
            )

    # fontconfig 兜底：先问已知族名，再问系统里任何一款支持中文的字体
    tried: list[str] = []
    for family in list(FALLBACK_FAMILIES) + _fc_chinese_families():
        if family in tried:
            continue
        tried.append(family)
        if family_resolves(family):
            return ResolvedFont(family, None, f"{family}（fontconfig）", True)

    return ResolvedFont(MACOS_CANDIDATES[0].family, None,
                        "未找到中文字体", False)


def reset_font_cache() -> None:
    """改完环境变量或装完字体后，让下一次解析重新探测。"""
    resolve_font.cache_clear()


def font_family() -> str:
    """给 `ctx.select_font_face()` 用的字体族名。"""
    return resolve_font().family


def assert_font_available() -> None:
    """字体不可用时立即失败，避免跨机渲染出豆腐块。"""
    font = resolve_font()
    if font.resolves:
        return
    raise RuntimeError(
        f"找不到可用的中文字体（当前族名 {font.family}），拒绝渲染"
        f"（避免输出豆腐块）。\n"
        f"装一套开源中文字体即可：\n{INSTALL_HINT}\n"
        f"也可以用 {FONT_ENV}=<族名> 显式指定字体族。"
    )


def missing_glyph(ch: str) -> bool:
    """这个字符在当前字体里是不是画不出来（会变成豆腐块）。"""
    import cairo

    def pixels(text: str) -> bytes:
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 80, 80)
        ctx = cairo.Context(surface)
        ctx.select_font_face(font_family(), cairo.FONT_SLANT_NORMAL,
                             cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(40)
        ctx.set_source_rgb(0, 0, 0)
        ctx.move_to(4, 40)
        ctx.show_text(text)
        surface.flush()
        return bytes(surface.get_data())

    return pixels(ch) == pixels(_MISSING_GLYPH)
