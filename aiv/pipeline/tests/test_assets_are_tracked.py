"""出片必需的素材必须**在仓库里**。

一条规矩：**入库的是事实，不入库的是产物**。

但「出片必需的输入」是另一回事——旁白、曲库、形象素材、品牌片不是为了
「留个档」，而是**没有它们就出不了片**。它们必须跟着仓库走，
另一台机器（尤其是 Linux）clone 完就能直接 `make` 出片。

这条守卫盯两件事：

1. 白名单里的素材**确实被 git 跟踪**——`.gitignore` 改错一个字、
   或者有人 `git rm --cached` 了一下，素材就会在别人的机器上凭空消失；
2. 产物目录（`out/`、`build/`）里**没有**被跟踪的文件——产物一旦入库，
   仓库就会开始长，而且每个 commit 都要背着它。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AIV_ROOT = REPO_ROOT / "aiv"

#: 出片必需的素材：相对仓库根的路径 → 为什么需要它
REQUIRED_ASSETS = {
    "aiv/narration_pg-parallel-decode.mp3": "EP01 旁白",
    "aiv/narration_csn-total-ordering.mp3": "EP02 旁白",
    "aiv/narration_wal-interleave.mp3": "EP03 旁白",
    "aiv/narration_parallel-apply.mp3": "EP04 旁白",
    "aiv/narration_structured-ddl.mp3": "EP05 旁白",
    "aiv/narration_row-lock.mp3": "EP06 旁白",
    "aiv/ddl-voiceover.mp3": "音色定标的参照稿",
    "aiv/growdu2.jpeg": "形象原型（重新生成立绘的唯一来源）",
    "aiv/character/growdu_character_2k_nobg.png": "小象立绘（渲染必需）",
    "aiv/brand/clips/growdu_intro_3s_1080p.mp4": "品牌片头",
    "aiv/brand/clips/growdu_outro_3s_1080p.mp4": "品牌片尾",
    "aiv/brand/audio/intro_mix.wav": "片头成品音轨",
    "aiv/brand/audio/outro_mix.wav": "片尾成品音轨",
    "aiv/music/tracks/series-bed-01.wav": "正文铺底 BGM",
    "aiv/music/tracks/series-motif-01.wav": "片头片尾闭环的 motif",
}

#: 产物目录：里面不许有被跟踪的文件
PRODUCT_DIRS = ("aiv/out", "aiv/build", "aiv/frames")


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True
    )


@pytest.fixture(scope="module", autouse=True)
def _require_git_repo():
    if _git("rev-parse", "--git-dir").returncode != 0:
        pytest.skip("不在 git 仓库里，跳过")


@pytest.mark.parametrize("relative", sorted(REQUIRED_ASSETS))
def test_required_asset_is_tracked(relative):
    """必需素材必须在版本控制里，否则别的机器上会凭空消失。"""
    assert (REPO_ROOT / relative).is_file(), f"{relative} 本机就没有"
    result = _git("ls-files", "--error-unmatch", relative)
    assert result.returncode == 0, (
        f"{relative} 没被 git 跟踪（{REQUIRED_ASSETS[relative]}）——"
        f"别的机器 clone 完会缺这一件"
    )


@pytest.mark.parametrize("relative", sorted(REQUIRED_ASSETS))
def test_required_asset_is_not_ignored(relative):
    """`.gitignore` 的放行清单必须真的放行了它。"""
    result = _git("check-ignore", "-q", relative)
    assert result.returncode != 0, f"{relative} 被 .gitignore 拦着"


@pytest.mark.parametrize("directory", PRODUCT_DIRS)
def test_product_directory_has_no_tracked_files(directory):
    """产物目录里不许有被跟踪的文件——成片一入库，仓库就开始长。"""
    result = _git("ls-files", directory)
    tracked = [line for line in result.stdout.splitlines() if line.strip()]
    assert tracked == [], f"{directory} 里有被跟踪的文件：{tracked}"


def test_no_tracked_media_outside_the_allowlist():
    """入库的媒体文件只有白名单里那些。"""
    result = _git("ls-files", "aiv")
    media_suffixes = (".mp3", ".mp4", ".wav", ".png", ".jpg", ".jpeg")
    allowed = set(REQUIRED_ASSETS)
    unexpected = [
        path for path in result.stdout.splitlines()
        if path.endswith(media_suffixes) and path not in allowed
    ]
    assert unexpected == [], f"有媒体文件没走白名单就入库了：{unexpected}"
