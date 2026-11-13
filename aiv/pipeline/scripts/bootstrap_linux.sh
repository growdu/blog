#!/usr/bin/env bash
# 在一台干净的 Linux 机器上装齐「出片流水线」要的东西。
#
#   sudo bash aiv/pipeline/scripts/bootstrap_linux.sh
#
# 装完先自检：
#
#   cd aiv/pipeline && make doctor
#
# 装的是：
#   * 系统工具：ffmpeg（含 libx264 与原生 aac）、fontconfig、make、python3
#   * 中文字体：Noto Sans CJK（PingFang 是 Apple 授权字体，不能随仓库分发）
#   * Python 依赖：pycairo / numpy / Pillow / scipy / pytest
#
# 已经装过的会被跳过（apt/dnf 本身幂等）。
set -euo pipefail

SYS_PKGS_COMMON=(
  ffmpeg
  fontconfig
  make
  python3
  python3-pip
)

SYS_PKGS_FONT=(
  fonts-noto-cjk
)

SYS_PKGS_PY=(
  python3-cairo
  python3-numpy
  python3-pil
  python3-scipy
  python3-pytest
)

PY_DEPS=(
  pycairo
  numpy
  Pillow
  scipy
  pytest
)

if [ "$(id -u)" -ne 0 ]; then
  echo "需要 root（装系统包）。请用：sudo bash $0" >&2
  exit 1
fi

# ---- 选包管理器 ------------------------------------------------------------

if command -v apt-get >/dev/null 2>&1; then
  PM=apt
  install_pkgs() {
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
  }
elif command -v dnf >/dev/null 2>&1; then
  PM=dnf
  install_pkgs() { dnf install -y "$@"; }
elif command -v pacman >/dev/null 2>&1; then
  PM=pacman
  install_pkgs() { pacman -Sy --noconfirm "$@"; }
elif command -v zypper >/dev/null 2>&1; then
  PM=zypper
  install_pkgs() { zypper install -y "$@"; }
else
  echo "没认出包管理器（apt/dnf/pacman/zypper），手工装这些：${SYS_PKGS_COMMON[*]}" >&2
  exit 1
fi

echo "== 包管理器：$PM =="

# 字体包名各家不一样
case "$PM" in
  apt) FONT_PKGS=("${SYS_PKGS_FONT[@]}") ;;
  dnf) FONT_PKGS=(google-noto-sans-cjk-fonts) ;;
  pacman) FONT_PKGS=(noto-fonts-cjk) ;;
  zypper) FONT_PKGS=(noto-cjk-fonts) ;;
esac

echo "== 系统工具 =="
install_pkgs "${SYS_PKGS_COMMON[@]}"

echo "== 中文字体 =="
install_pkgs "${FONT_PKGS[@]}"
fc-cache -f >/dev/null 2>&1 || true

echo "== Python 依赖（系统包优先） =="
if ! install_pkgs "${SYS_PKGS_PY[@]}"; then
  echo "  系统包装不上，改走 pip"
  python3 -m pip install --user "${PY_DEPS[@]}"
fi

echo
echo "== 自检 =="
cd "$(dirname "$0")/../.." || exit 1
if command -v make >/dev/null 2>&1; then
  make -C pipeline doctor || true
else
  echo "make 没装上，手动跑：cd aiv/pipeline && python3 -m pyv.cli doctor"
fi

echo
echo "装完了。下一步：cd aiv/pipeline && make EP=row-lock align validate brand render compose mix-verify"
