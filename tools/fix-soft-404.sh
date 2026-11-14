#!/usr/bin/env bash
# Turn the site's nginx soft-404 into a real 404 on the server.
#
# Run this on the server (root required):
#
#   bash tools/fix-soft-404.sh
#
# What it does:
#   1. rewrites `try_files $uri $uri/ /index.html;` into
#      `try_files $uri $uri/ =404;` + `error_page 404 /404.html;`
#   2. runs `nginx -t` and reloads only if the config is valid
#
# Idempotent: re-running just no-ops.  The script prints what it changed
# and keeps a `.bak` next to the original.
#
# Why this matters is in tools/nginx_soft404.py's docstring -- in one
# line: with the SPA fallback, every unknown URL answers 200 with the
# homepage, so link rot is invisible and search engines index duplicates.

set -euo pipefail

CONF="${BLOG_CONF:-/etc/nginx/conf.d/blog.conf}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATCHER="${REPO_ROOT}/tools/nginx_soft404.py"

if [[ ! -f "$CONF" ]]; then
    echo "FATAL: $CONF not found" >&2
    exit 1
fi

if [[ ! -f "$PATCHER" ]]; then
    echo "FATAL: $PATCHER not found" >&2
    exit 1
fi

# --check first: already fixed means there is nothing to reload.
if python3 "$PATCHER" "$CONF" --check; then
    echo "patch already applied, nothing to do"
    exit 0
fi

python3 "$PATCHER" "$CONF"

# 没有 nginx 可执行文件时（本地与容器里常见）只改文件、不校验也不 reload。
# 服务器上 nginx 在 PATH 上，走下面的正常路径。
#
# 注意：**CI runner 上有 nginx**。GitHub 的 ubuntu-24.04 镜像预装了
# nginx 1.24.0（见 actions/runner-images 的 Ubuntu2404-Readme），所以
# 「CI 里没有 nginx」这个假设不成立——CI 上会走进下面的 nginx 分支，
# 而 `nginx -t` 校验的是 runner 上 nginx 的主配置，对着一份片段配置
# 必然失败，脚本会按设计回滚备份并退出 1。测试因此必须自己控制 PATH。
if ! command -v nginx >/dev/null 2>&1; then
    echo "WARNING: nginx 不在 PATH 上，已改配置但没有校验也没有 reload"
    echo "         请在服务器上手动跑： nginx -t && systemctl reload nginx"
    exit 0
fi

# A broken config must never reach nginx: validate, and restore if the
# validation fails.  Reloading a bad config takes the site down.
if nginx -t >/dev/null 2>&1; then
    echo "nginx config OK"
    if command -v systemctl >/dev/null 2>&1; then
        systemctl reload nginx
        echo "nginx reloaded"
    else
        echo "WARNING: systemctl 不可用，请手动 nginx -s reload"
    fi
else
    echo "nginx config INVALID, restoring backup" >&2
    for backup in "${CONF}".bak*; do
        if [[ -f "$backup" ]]; then
            cp -a "$backup" "$CONF"
            echo "restored from $backup" >&2
            break
        fi
    done
    nginx -t || true
    exit 1
fi
