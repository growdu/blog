#!/usr/bin/env bash
# 在一台干净的 Linux 机器上装齐「浏览器投稿」要的东西。
#
#   sudo bash browser/scripts/bootstrap_linux.sh
#
# 装完先自检：
#
#   cd browser && python3 -m browser.cli doctor
#
# 装的是：
#   * 系统工具：python3 + pip、make（可选）、xvfb（纯服务器上跑无头时用）
#   * Python 依赖：playwright
#   * 浏览器本体：chromium（连同它需要的系统库）
#
# **为什么浏览器单独一个脚本，不并进 aiv/pipeline 的 bootstrap。**
# 出片的机器需要 ffmpeg 与中文字体，发帖的机器需要 chromium——
# 两台机器的依赖不一样，捆在一起会让「只想出片」的人被迫装一个几百兆的浏览器。
set -euo pipefail

SYS_PKGS_COMMON=(
  python3
  python3-pip
)

SYS_PKGS_HEADLESS=(
  xvfb
)

PY_DEPS=(
  playwright
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

echo "== 系统工具 =="
install_pkgs "${SYS_PKGS_COMMON[@]}"

echo "== 无头服务器用的 xvfb =="
# 纯服务器上没���显示器，扫码登录又必须要有窗口——xvfb 给一个虚拟显示器。
install_pkgs "${SYS_PKGS_HEADLESS[@]}" || echo "  (装不上也不影响有桌面环境的机器)"

echo "== Python 依赖（playwright） =="
python3 -m pip install --upgrade "${PY_DEPS[@]}"

echo "== chromium 与它的系统库 =="
# --with-deps 会按 playwright 的版本去装对应版本的浏览器，
# 并补上 chromium 需要的系统库（libnss3、libgbm1 之类）。
python3 -m playwright install --with-deps chromium

echo
echo "== 自检 =="
cd "$(dirname "$0")/.." || exit 1
python3 -m browser.cli doctor || true

cat <<'EOF'

装完了。下一步：

  # 1. 扫码登录（在有显示器的机器上，或用 xvfb-run）
  cd browser && python3 -m browser.cli probe

  # 2. 照着探出来的结构填 browser/selectors/channels.json

  # 3. 填表（不发表）
  cd browser && python3 -m browser.cli prepare row-lock

  # 4. 发表
  cd browser && python3 -m browser.cli submit row-lock

纯服务器（没有显示器）上用 xvfb-run 包一层：

  xvfb-run -a python3 -m browser.cli submit row-lock

EOF
