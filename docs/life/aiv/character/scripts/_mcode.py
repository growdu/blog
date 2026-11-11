#!/usr/bin/env python3
"""mcode-tools CLI 的薄封装：上传参考图、调用连接器、下载产物。

形象生成类的脚本（`generate_character.py` / `add_glasses.py`）共用这一层，
免得每个脚本各抄一遍 subprocess 与 JSON 解析。

依赖 mcode-tools CLI（先加载 `mcode-tools-master` skill）：

    mcode-tools upload_temp_url <file>                          # 本地文件 → 临时 URL
    mcode-tools connector call <tool> --args-file <json>        # 调连接器
    mcode-tools get_asset_url <node_id>                         # node_id → 下载 URL
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path


class MCodeError(RuntimeError):
    """mcode-tools 调用失败。"""


# 连接器忙是临时状态（实测批量生成时会撞上），重试几次即可。
BUSY_MARKERS = ("connector_busy", "provider is busy", "rate_limit",
                "too many requests", "tools_list_failed",
                "temporarily unavailable", "service unavailable")


def run(cmd: list[str], retries: int = 3, wait: float = 5.0) -> str:
    """执行命令，失败时把 stderr 尾巴带出来。

    连接器忙 / 限流属于临时故障，退避后重试；其它错误直接抛。
    """
    last = ""
    for attempt in range(retries + 1):
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            return proc.stdout
        last = (proc.stderr or proc.stdout or "").strip()[-800:]
        busy = any(marker in last for marker in BUSY_MARKERS)
        if not busy or attempt == retries:
            break
        time.sleep(wait * (attempt + 1))
    raise MCodeError(f"命令失败：{' '.join(cmd[:3])}\n{last}")


def _json_from(out: str) -> dict:
    """CLI 输出里可能夹着警告行，从第一个 '{' 开始截 JSON。"""
    start = out.find("{")
    if start < 0:
        raise MCodeError(f"输出里没有 JSON：{out[-400:]}")
    return json.loads(out[start:])


def upload(path: Path, mime_type: str | None = None) -> str:
    """上传本地文件，返回可用的临时 URL。"""
    cmd = ["mcode-tools", "upload_temp_url", str(path)]
    if mime_type:
        cmd += ["--mime-type", mime_type]
    return _json_from(run(cmd))["temp_url"]


def call(tool: str, args: dict) -> dict:
    """调用连接器工具。

    参数走临时文件而不是 `--args` 内联 JSON：prompt 里有中文、引号、
    换行，内联容易踩 shell 转义的坑。
    """
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", encoding="utf-8", delete=False
    ) as fh:
        json.dump(args, fh, ensure_ascii=False)
        args_file = fh.name
    try:
        out = run(["mcode-tools", "connector", "call", tool,
                   "--args-file", args_file])
    finally:
        Path(args_file).unlink(missing_ok=True)
    return _json_from(out)


def download(node_id: str, dest: Path) -> Path:
    """按 node_id 取下载地址并下载到本地。"""
    url = _json_from(run(["mcode-tools", "get_asset_url", node_id]))["download_url"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["curl", "-sfL", "-o", str(dest), url], check=True)
    return dest
