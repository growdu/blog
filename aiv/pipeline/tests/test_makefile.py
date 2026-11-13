"""Makefile 的期号分流。

`make EP=<期号>` 是换一期的唯一入口。它**错得很安静**比报错更糟——
拿上一期的契约出片，成片看着一切正常，只有内容不对。
所以这条守卫盯住两件事：

1. 未知 EP 必须当场报错，不能静悄悄地用默认那一期；
2. 每个已登记的 EP 必须指向自己的口播稿与契约，不能串。
"""
import re
import subprocess
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1]
MAKEFILE = PIPELINE / "Makefile"

from pyv import episodes as episodes_mod


# 已登记的期号 → (口播稿, 契约)。登记表在 pyv/episodes.py；
# Makefile 里另有一份（shell 读不了 Python 模块），两边的漂移由下面
# 那两条测试抓住。
KNOWN_EPS = {
    ep: (episodes_mod.EPISODES[ep], f"{ep}.json")
    for ep in episodes_mod.EPISODE_ORDER
}

#: 只看口播稿（Makefile 里登记的就是它）
KNOWN_EPS_SCRIPTS = {ep: script for ep, (script, _) in KNOWN_EPS.items()}


def _make(*args):
    return subprocess.run(
        ["make", *args], cwd=PIPELINE, capture_output=True, text=True
    )


def test_unknown_ep_fails_loudly():
    """未知 EP 必须报错退出，不能拿默认那一期硬出片。"""
    result = _make("-n", "EP=definitely-not-an-episode", "align")
    assert result.returncode != 0, "未知 EP 竟然没有报错"
    assert "未知 EP" in result.stderr + result.stdout


def test_makefile_registers_exactly_the_known_eps():
    """Makefile 里登记的期号必须与这张表一致。"""
    text = MAKEFILE.read_text(encoding="utf-8")
    registered = set(
        re.findall(r"ifeq\s+\(\$\(EP\),([^)]+)\)", text)
    )
    assert registered == set(KNOWN_EPS)


def test_makefile_points_each_ep_at_the_registered_script():
    """Makefile 里的口播稿路径必须与登记表一致——两处漂移就出错片。"""
    text = MAKEFILE.read_text(encoding="utf-8")
    found = dict(
        re.findall(r"ifeq\s+\(\$\(EP\),([^)]+)\)\s*\nSCRIPT\s*:=\s*\$\(ROOT\)/(.+?)\n",
                   text)
    )
    assert found == KNOWN_EPS_SCRIPTS


def test_each_registered_ep_resolves_its_own_files():
    """每一期都必须指向自己的口播稿与契约。"""
    for episode, (script, contract) in KNOWN_EPS.items():
        result = _make("-n", f"EP={episode}", "align")
        assert result.returncode == 0, result.stderr
        out = result.stdout
        assert script in out, f"{episode} 的口播稿指错了"
        assert contract in out, f"{episode} 的契约指错了"
        assert f"storyboard_{episode}.json" in out, f"{episode} 的时间轴名不对"
        assert f"narration_{episode}.mp3" in out, f"{episode} 的旁白名不对"


def test_ep_is_optional_and_defaults_to_the_first_episode():
    """不写 EP 也能出片——默认就是第一期。"""
    default_ep = next(iter(KNOWN_EPS))
    result = _make("-n", "align")
    assert result.returncode == 0, result.stderr
    script, _ = KNOWN_EPS[default_ep]
    assert script in result.stdout
