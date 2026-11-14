"""nginx 软 404 的守卫与补丁。

**软 404** 指的是：站点上任何不存在的 URL 都返回 ``200`` + 首页正文。
实测 2026-11-14：未知路径 200 / 120526 字节，与 ``/`` 逐字节相同。

它有两个后果，都在这里守住：

* 搜索引擎把首页按每个错 URL 收录成重复页；
* **链接坏没看不出来**——只看状态码的可达性检查会对着死链返回 200。

所以这里有三组断言：

* **单元**：补丁函数本身的行为（幂等、不误伤、找不到锚点就报错）；
* **文档**：``docs/blog/部署到服务器.md`` 里的 nginx 配置**就是**修好之后的形态
  —— 文档是手写的事实源，代码向它对齐；
* **集成**：把文档里的配置反向还原成未打补丁的形态，跑一遍补丁，
  结果必须与文档逐字节一致；再验 CLI 与服务器脚本的行为。

放在根级 ``tests/``，随 ``site-guard.yml`` 进 CI。
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "docs" / "blog" / "部署到服务器.md"
PATCHER_PATH = REPO / "tools" / "nginx_soft404.py"
WRAPPER = REPO / "tools" / "fix-soft-404.sh"


def _load_module():
    """Import ``tools/nginx_soft404.py`` by path.

    ``tools/`` is not a package (no ``__init__.py``), so the module is
    loaded from its file.  It is loaded once per session -- the module
    has no state.
    """
    spec = importlib.util.spec_from_file_location("nginx_soft404", PATCHER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


soft404 = _load_module()


# --- 从文档里取 nginx 配置块 ---------------------------------------------


def _nginx_blocks(text: str) -> list[str]:
    return re.findall(r"```nginx\n(.*?)```", text, re.DOTALL)


def _site_config() -> str:
    """The nginx config block from the deployment doc.

    It is the block that carries the ``try_files`` rule -- i.e. the one
    that decides what an unknown path answers.
    """
    blocks = _nginx_blocks(DOC.read_text(encoding="utf-8"))
    matched = [b for b in blocks if "try_files" in b]
    assert len(matched) == 1, f"文档里应当只有一处 try_files，实际 {len(matched)} 处"
    return matched[0]


# --- 单元：补丁函数 --------------------------------------------------------


def test_patch_replaces_the_fallback_with_a_real_404():
    config = "    location / {\n        try_files $uri $uri/ /index.html;\n    }\n"
    patched = soft404.patch(config)

    assert "try_files $uri $uri/ =404;" in patched
    assert "error_page 404 /404.html;" in patched
    assert "/index.html;" not in patched


def test_patch_keeps_the_directory_element():
    """``$uri/`` 必须留着。

    目录式 permalink（``/archives/``）靠它找到自己的 ``index.html``。
    把它删掉会让**每一个** permalink 都 404。
    """
    config = "    location / {\n        try_files $uri $uri/ /index.html;\n    }\n"
    patched = soft404.patch(config)

    assert "$uri/" in patched
    assert "try_files $uri $uri/ =404;" in patched


def test_patch_is_idempotent():
    config = "    location / {\n        try_files $uri $uri/ /index.html;\n    }\n"
    once = soft404.patch(config)
    twice = soft404.patch(once)

    assert once == twice
    assert soft404.is_patched(once)
    assert soft404.is_patched(twice)


def test_patch_refuses_when_there_is_nothing_to_patch():
    """找不到锚点要报错，不许静默通过。

    一个什么都不做的补丁，比一个报错的补丁糟糕得多。
    """
    with pytest.raises(soft404.Soft404Error):
        soft404.patch("server { listen 80; }\n")


def test_patch_refuses_when_there_are_several_candidates():
    """多处 fallback 时不猜——报错让人工确认改哪一处。"""
    config = (
        "    location / {\n        try_files $uri $uri/ /index.html;\n    }\n"
        "    location /old {\n        try_files $uri $uri/ /index.html;\n    }\n"
    )
    with pytest.raises(soft404.Soft404Error):
        soft404.patch(config)


def test_patch_leaves_other_try_files_alone():
    """别的 try_files 规则不受影响。"""
    config = (
        "    location = /healthz {\n        try_files $uri =412;\n    }\n"
        "    location / {\n        try_files $uri $uri/ /index.html;\n    }\n"
    )
    patched = soft404.patch(config)

    assert "try_files $uri =412;" in patched
    assert "try_files $uri $uri/ =404;" in patched


def test_is_patched_needs_both_halves():
    """只有一半不算修好。

    只有 ``=404`` → nginx 默认 404 页；只有 ``error_page`` → 仍然回首页 200。
    """
    only_404 = "    location / {\n        try_files $uri $uri/ =404;\n    }\n"
    only_error_page = (
        "    location / {\n        try_files $uri $uri/ /index.html;\n"
        "        error_page 404 /404.html;\n    }\n"
    )

    assert not soft404.is_patched(only_404)
    assert not soft404.is_patched(only_error_page)
    assert soft404.problems(only_404)
    assert soft404.problems(only_error_page)


def test_problems_is_empty_on_a_good_config():
    config = (
        "    location / {\n        try_files $uri $uri/ =404;\n"
        "        error_page 404 /404.html;\n    }\n"
    )
    assert soft404.problems(config) == []


# --- 文档：事实源 ----------------------------------------------------------


def test_doc_config_is_already_patched():
    """部署文档里的 nginx 配置**就是**修好之后的形态。

    文档是手写的事实源；代码向它对齐，不反过来。
    """
    config = _site_config()

    assert "try_files $uri $uri/ =404;" in config, "文档里的配置还没改成真 404"
    assert "error_page 404 /404.html;" in config, "文档里缺 error_page 404"
    assert "try_files $uri $uri/ /index.html;" not in config, "文档里还留着 SPA fallback"


def test_doc_config_does_not_use_error_page_equals_200():
    """``error_page 404 =200`` 会把状态码改回 200——那是换个名字的软 404。"""
    config = _site_config()
    assert "error_page 404 =200" not in config


def test_patch_reproduces_the_documented_config():
    """把文档反向还原成未打补丁的形态，跑一遍补丁，结果必须逐字节一致。

    这条把「文档」与「脚本」钉在一起：改了文档没改脚本，或者反过来，
    都会红。
    """
    config = _site_config()
    reverted = config.replace(
        "        try_files $uri $uri/ =404;\n        error_page 404 /404.html;\n",
        "        try_files $uri $uri/ /index.html;\n",
    )
    assert reverted != config, "反向还原没匹配上，文档的写法变了"

    assert soft404.patch(reverted) == config


# --- 集成：CLI 与服务器脚本 ------------------------------------------------


def _write_conf(tmp_path: Path, content: str) -> Path:
    conf = tmp_path / "blog.conf"
    conf.write_text(content, encoding="utf-8")
    return conf


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(PATCHER_PATH), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_cli_check_reports_unpatched_then_patched(tmp_path: Path):
    conf = _write_conf(tmp_path, "    location / {\n        try_files $uri $uri/ /index.html;\n    }\n")

    unpatched = _run_cli(str(conf), "--check")
    assert unpatched.returncode == 1, "未打补丁时 --check 应当返回 1"
    assert "问题" in unpatched.stderr

    assert _run_cli(str(conf)).returncode == 0
    assert _run_cli(str(conf), "--check").returncode == 0


def test_cli_dry_run_writes_nothing(tmp_path: Path):
    original = "    location / {\n        try_files $uri $uri/ /index.html;\n    }\n"
    conf = _write_conf(tmp_path, original)

    result = _run_cli(str(conf), "--dry-run")
    assert result.returncode == 0
    assert conf.read_text(encoding="utf-8") == original, "--dry-run 不该写文件"
    assert not list(tmp_path.glob("*.bak")), "--dry-run 不该留备份"


def test_cli_patch_is_idempotent_on_disk(tmp_path: Path):
    conf = _write_conf(tmp_path, "    location / {\n        try_files $uri $uri/ /index.html;\n    }\n")

    assert _run_cli(str(conf)).returncode == 0
    first = conf.read_text(encoding="utf-8")
    assert "=404" in first
    assert list(tmp_path.glob("*.bak")), "应当留一份备份"

    assert _run_cli(str(conf)).returncode == 0
    assert conf.read_text(encoding="utf-8") == first, "第二次跑不该再改"


def test_cli_refuses_a_config_it_does_not_understand(tmp_path: Path):
    conf = _write_conf(tmp_path, "server { listen 80; }\n")
    result = _run_cli(str(conf))
    assert result.returncode == 2, "看不懂的配置应当返回 2，不是悄悄改点什么"


def _hermetic_env(tmp_path: Path, conf: Path, *, with_nginx: bool) -> dict[str, str]:
    """一条只含脚本真正用到的命令的 PATH，外加 nginx/systemctl 的替身。

    这条测试以前只在 macOS 上绿过。``tools/fix-soft-404.sh`` 里写着
    「没有 nginx 可执行文件时（本地、CI、容器里）只改文件、不校验也不
    reload」——但 GitHub 的 ubuntu runner **预装 nginx 1.24.0**
    （见 actions/runner-images 的 Ubuntu2404-Readme）。于是 CI 上脚本走进
    ``nginx -t`` 分支，而 ``nginx -t`` 校验的是 runner 上 nginx 的主配置，
    对着一份片段配置当然失败，脚本按设计回滚备份并退出 1。
    本地 macOS 没有 nginx，走的是「不在 PATH 上」那条分支，所以本地绿。

    差的就是「这台机器上有没有 nginx」。所以这里把 PATH 收窄成脚本真正
    用到的三个命令（bash / python3 / dirname），再按需放进两个**必定成功**
    的 nginx 与 systemctl 替身：脚本的完整路径照走，结果不再取决于宿主
    装了什么。
    """
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    for name in ("bash", "python3", "dirname", "cp"):
        real = shutil.which(name)
        assert real, f"PATH 上找不到 {name}，这条测试没法构造一个受控的环境"
        (bindir / name).symlink_to(real)
    if with_nginx:
        for name in ("nginx", "systemctl"):
            stub = bindir / name
            stub.write_text("#!/bin/sh\n# 测试替身：永远成功\nexit 0\n",
                            encoding="utf-8")
            stub.chmod(0o755)
    return {
        "PATH": str(bindir),
        "HOME": str(tmp_path),
        "BLOG_CONF": str(conf),
    }


def test_server_wrapper_patches_and_is_idempotent(tmp_path: Path):
    """服务器脚本：BLOG_CONF 指向一份 fixture，跑两遍。

    第二遍必须说「already applied」并且**文件内容不变**。

    脚本在「机器上有 nginx」时还要做 ``nginx -t`` 与 reload，所以这里把
    nginx 与 systemctl 换成必定成功的替身——脚本的完整路径照走，但结果
    不再取决于宿主装没装 nginx（GitHub 的 runner 装了，macOS 没装）。
    """
    conf = _write_conf(tmp_path, "    location / {\n        try_files $uri $uri/ /index.html;\n    }\n")

    env = _hermetic_env(tmp_path, conf, with_nginx=True)
    first = subprocess.run(
        ["bash", str(WRAPPER)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert first.returncode == 0, first.stderr
    patched = conf.read_text(encoding="utf-8")
    assert "=404" in patched

    second = subprocess.run(
        ["bash", str(WRAPPER)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert second.returncode == 0, second.stderr
    assert "already applied" in second.stdout
    assert conf.read_text(encoding="utf-8") == patched, "第二遍不该再改文件"


def test_server_wrapper_patches_even_without_nginx_on_the_path(tmp_path: Path):
    """机器上没有 nginx 时，脚本也要把文件改好并正常退出。

    这是本地与容器里的路径，也是脚本注释里写的那条。把它单独钉住，
    免得有人为了「简化」把「nginx 不在 PATH 上」那个分支删掉。
    """
    conf = _write_conf(tmp_path, "    location / {\n        try_files $uri $uri/ /index.html;\n    }\n")

    env = _hermetic_env(tmp_path, conf, with_nginx=False)
    result = subprocess.run(
        ["bash", str(WRAPPER)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "=404" in conf.read_text(encoding="utf-8")
    assert "nginx 不在 PATH 上" in result.stdout
