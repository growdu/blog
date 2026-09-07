---
title: "Clash Meta(mihomo)客户端全平台安装与订阅配置教程"
date: 2026-09-07
author: growdu
categories:
  - 工具
tags:
  - clash
  - mihomo
  - 代理
  - 网络
---

# Clash Meta(mihomo)客户端全平台安装与订阅配置教程

> ⚠️ **免责声明**:该篇文章内容仅用于技术交流和学习,切勿用作其他用途。

> 本教程涵盖 Windows、macOS、Linux、Android、iOS 五个平台的 Clash Meta(mihomo)客户端安装、配置、以及订阅端连接。
>
> 订阅端(本教程示例):`http://onetear.fun:8080/clash-meta.yaml`
>
> 客户端安装包镜像(Wind / macOS / Android):`http://onetear.fun:18089/clash_client/`

---

## 一、为什么是 Clash Meta(mihomo)?

Clash 是一个基于 Go 实现的代理客户端，凭借规则分流、YAML 配置、TUN 模式、relay（链式代理）等特性，长期是代理工具的事实标准。原始 Clash 项目自 2023 年作者删库后，社区分叉出三个主流分支：

| 分支 | 状态 | 特点 |
| --- | --- | --- |
| **Clash.Meta(后改名 mihomo)** | 活跃 | 持续维护、新协议支持最全、TUN 增强、规则更灵活 |
| Clash for Windows | 停止维护 | 仓库已 archive，但二进制仍可下载 |
| Clash Verge | 活跃 | 桌面 GUI 客户端，传统 Clash 内核 |
| **Clash Verge Rev** | 活跃 | Clash Verge 的分叉，**默认使用 mihomo 内核**，最推荐 |

本教程统一推荐使用 **mihomo 内核** + **Clash Verge Rev** 桌面客户端 / **Clash Meta for Android** / **Stash**(iOS)。订阅端链接 `clash-meta.yaml` 已经表明是 mihomo 格式——其他传统 Clash 内核可能无法解析。

---

## 二、平台安装

### 2.1 Windows

#### 推荐:Clash Verge(国内镜像)

**安装步骤**:

1. 直接下载安装包:<http://onetear.fun:18089/clash_client/Clash.Verge_2.5.2_x64-setup.exe>(约 45 MB,Windows 10 / 11 64-bit)
2. 双击安装包,按向导完成
3. 启动后右下角托盘出现图标

> 💡 镜像说明:安装包来自国内 CDN 镜像 `http://onetear.fun:18089/clash_client/`,下载速度快、不易断流。如需最新 dev 版本也可去 GitHub:<https://github.com/clash-verge-rev/clash-verge-rev/releases>

**验证安装**:
```powershell
# PowerShell(可选,适合习惯包管理的同学)
winget install ClashVergeRev.ClashVergeRev
# 或 scoop
scoop install clash-verge-rev
```

#### 备选:mihomo Party

- GitHub:<https://github.com/mihomo-party-org/mihomo-party/releases>
- 下载 `mihomo-party_*_x64-setup.exe`
- 界面更现代，支持 TUN 模式可视化

#### 命令行版本:mihomo 二进制

```powershell
# 1. 下载
$ver = "1.19.0"   # 替换为最新版本
Invoke-WebRequest -Uri "https://github.com/MetaCubeX/mihomo/releases/download/v$ver/mihomo-windows-amd64-$ver.zip" `
    -OutFile "mihomo.zip"
Expand-Archive mihomo.zip -DestinationPath C:\mihomo

# 2. 添加到 PATH
[Environment]::SetEnvironmentVariable("Path", "$env:Path;C:\mihomo", "User")

# 3. 验证
mihomo -v
```

---

### 2.2 macOS

#### 推荐:Clash Verge(国内镜像)

| 芯片 | 下载链接 |
| --- | --- |
| **Apple Silicon**(M1 / M2 / M3 / M4) | <http://onetear.fun:18089/clash_client/Clash.Verge_2.5.2_aarch64.dmg>(约 58 MB) |
| **Intel**(2019 年前 Mac) | <http://onetear.fun:18089/clash_client/Clash.Verge_2.5.2_x64.dmg>(约 63 MB) |

**安装步骤**:

1. 根据芯片选上面对应的链接下载 `.dmg`
2. 双击 .dmg,把 Clash Verge 拖到 Applications
3. **首次启动需要授权**:系统设置 → 隐私与安全性 → 仍要打开

或者用 Homebrew(从 GitHub 拉):

```bash
brew install --cask clash-verge-rev
```

#### 命令行:mihomo 二进制(Apple Silicon)

```bash
# 1. Apple Silicon (M1/M2/M3)
curl -L -o mihomo.gz "https://github.com/MetaCubeX/mihomo/releases/download/v1.19.0/mihomo-darwin-arm64-1.19.0.gz"
gunzip mihomo.gz
chmod +x mihomo
sudo mv mihomo /usr/local/bin/

# 2. Intel
curl -L -o mihomo.gz "https://github.com/MetaCubeX/mihomo/releases/download/v1.19.0/mihomo-darwin-amd64-1.19.0.gz"
gunzip mihomo.gz
chmod +x mihomo
sudo mv mihomo /usr/local/bin/

# 3. 验证
mihomo -v
```

---

### 2.3 Linux

> ℹ️ 国内镜像 `http://onetear.fun:18089/clash_client/` **暂未收录 Linux 包**(只有 Windows / macOS / Android 安装包)。Linux 桌面用户请继续走 GitHub Release 或系统包管理器。

#### Debian / Ubuntu

```bash
# 方法 1:Clash Verge Rev (.deb 包)
wget https://github.com/clash-verge-rev/clash-verge-rev/releases/download/v1.7.2/clash-verge-rev_1.7.2_amd64.deb
sudo apt install ./clash-verge-rev_1.7.2_amd64.deb

# 方法 2:mihomo 命令行(推荐服务器)
wget https://github.com/MetaCubeX/mihomo/releases/download/v1.19.0/mihomo-linux-amd64-v1.19.0.gz
gunzip mihomo-linux-amd64-v1.19.0.gz
chmod +x mihomo-linux-amd64
sudo mv mihomo-linux-amd64 /usr/local/bin/mihomo
mihomo -v
```

#### Arch / Manjaro

```bash
yay -S clash-verge-rev-bin
# 或
yay -S mihomo
```

#### Fedora / RHEL

```bash
sudo dnf install ./clash-verge-rev-*.rpm
```

#### 桌面图标(可选)

```bash
# Clash Verge Rev 启动后会自动创建 .desktop
ls ~/.local/share/applications/ | grep clash
```

---

### 2.4 Android

#### 推荐:Clash Meta for Android(国内镜像)

| 设备 | 下载链接 |
| --- | --- |
| **真机**(绝大多数 Android 手机) | <http://onetear.fun:18089/clash_client/cmfa-2.11.33-meta-universal-release.apk>(约 104 MB,通用包) |
| **x86 模拟器**(夜神/雷电/MuMu 等) | <http://onetear.fun:18089/clash_client/cmfa-2.11.33-meta-x86-release.apk>(约 45 MB) |

**安装步骤**:

1. 点击上面链接下载 APK
2. 手机打开"未知来源应用"权限
3. 点击 APK 安装
4. 首次启动会请求 VPN 权限,授权

或者通过 F-Droid:

```bash
# 搜索 "Clash Meta for Android" 安装
```

#### 命令行替代

```bash
# Termux 上安装 mihomo(需要 root)
pkg install golang git
go install github.com/metacubex/mihomo/cmd/mihomo@latest
```

---

### 2.5 iOS

iOS 因 Apple 政策,**国内镜像 `http://onetear.fun:18089/clash_client/` 无法分发 iOS 安装包**(`.ipa` 必须走 App Store)。下面按 **是否愿意花钱** 分两类方案。

#### 方案 A:免费方案(0 元)

##### A1. **V2Box** — 最推荐,App Store 直接搜

- **价格**:完全免费(有广告,但不影响代理功能)
- **mihomo 兼容**:**支持直接粘贴 `clash-meta.yaml` 订阅链接**
- **下载**:App Store 搜索 **"V2Box"** → 直接安装,无需付费
- **添加订阅**:打开 App → 顶部 `+` → `Subscribe` → 粘贴 `http://onetear.fun:8080/clash-meta.yaml` → 保存 → 选节点 → 启动开关

##### A2. **sing-box** — 开源免费,适合折腾

- **价格**:App Store 完全免费,无广告
- **mihomo 兼容**:**需要把 YAML 手动转成 JSON**(配置稍微复杂)
- **下载**:App Store 搜索 **"sing-box"** → 安装
- **配置转换**:可使用在线工具 [subconverter](https://github.com/tindy2013/subconverter) 把 `clash-meta.yaml` 转成 sing-box 出站格式

##### A3. **共享代理**(适合已有 Android / Mac / Windows 的同学)

不装任何 iOS 客户端,让其它设备的代理透给 iPhone:

| 共享端 | iPhone 怎么连 |
| --- | --- |
| Android(已开代理) | 设置 → 移动网络 → 个人热点 → 打开,**iPhone 连这个 Wi-Fi 即可走代理** |
| Mac(已开代理) | 系统设置 → 通用 → 共享 → 互联网共享(勾选 Wi-Fi)→ iPhone 连 Mac 的 Wi-Fi |
| Windows(已开代理) | Windows 设置 → 移动热点 → 打开,或装 [Clash Verge 的 Allow LAN](http://127.0.0.1:9090) → iPhone Wi-Fi 代理手动填 PC 的 IP + 7890 端口 |

#### 方案 B:付费方案(¥18-¥55 一次性买断)

| 工具 | 价格 | mihomo 兼容 | 备注 |
| --- | --- | --- | --- |
| **Stash** | $3.99(约 ¥25) | ✅ 完全兼容 | iOS 最主流,功能最强 |
| Shadowrocket | $2.99 | 部分兼容 | 俗称"小火箭" |
| Loon | $5.99 | 部分兼容 | |
| Quantumult X | $7.99 | 部分兼容 | |

**Stash 安装**(推荐):App Store 搜索 "Stash" → 购买 → 打开。

> ⚠️ **大陆 App Store 搜不到这些付费 App**。需要:
>
> - 自备一个**美区 / 港区 / 日区**的 Apple ID(免费注册教程:[appleid.apple.com](https://appleid.apple.com))
> - 或者淘宝/闲鱼租一个**共享账号**(临时登录用,几块钱一次)

---

## 三、配置订阅端

以本教程提供的订阅端为例:

```
http://onetear.fun:8080/clash-meta.yaml
```

这是一个 **Clash Meta(mihomo) 格式** 的订阅端点。

### 3.1 Clash Verge Rev(桌面端)

1. 启动 Clash Verge Rev
2. 左侧菜单 → **Profiles**(订阅)
3. 点击 **From URL**(从 URL 导入)
4. 在输入框填入:`http://onetear.fun:8080/clash-meta.yaml`
5. 名称(Name)自定义，比如 `my-sub`
6. 点击 **Import**(导入)
7. 等待 5-10 秒，下载完成后会出现在列表里
8. 点击该 profile 让其激活(高亮)
9. 顶部 **System Proxy**(系统代理)开关打开
10. 可选:打开 **TUN Mode**(TUN 模式) — 接管所有流量

**验证**:
- 浏览器打开 <https://www.google.com> 应该能访问
- Clash Verge Rev 主界面会显示实时流量

### 3.2 mihomo 命令行(服务器 / Linux 桌面)

**创建配置文件目录**:

```bash
mkdir -p ~/.config/mihomo
```

**下载订阅**到 `config.yaml`:

```bash
curl -L -o ~/.config/mihomo/config.yaml "http://onetear.fun:8080/clash-meta.yaml"
```

**启动 mihomo**(以 daemon 模式):

```bash
# 前台运行(调试用)
mihomo -d ~/.config/mihomo

# 后台运行
nohup mihomo -d ~/.config/mihomo > /var/log/mihomo.log 2>&1 &

# 用 systemd 托管
sudo tee /etc/systemd/system/mihomo.service << 'EOF'
[Unit]
Description=mihomo Daemon
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/mihomo -d /etc/mihomo
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo mkdir -p /etc/mihomo
sudo cp ~/.config/mihomo/config.yaml /etc/mihomo/
sudo systemctl daemon-reload
sudo systemctl enable --now mihomo
```

**验证**:

```bash
# 1. mihomo 启动日志
journalctl -u mihomo -f

# 2. 测试 HTTP 代理(mihomo 默认 7890 端口)
curl -x http://127.0.0.1:7890 https://www.google.com
```

**TUN 模式(接管所有流量)**:

mihomo 的 TUN 模式需要 root 或 CAP_NET_ADMIN 权限:

```bash
# Linux 桌面开启 TUN
sudo mihomo -d ~/.config/mihomo

# 配置文件 config.yaml 里的 tun 配置(订阅端一般已开启)
# tun:
#   enable: true
#   stack: system
#   dns-hijack:
#     - any:53
```

### 3.3 Clash Meta for Android(Android)

1. 启动 Clash Meta for Android
2. 点击右下角 **+**(添加配置)
3. 选择 **URL Import**(URL 导入)
4. 填入:`http://onetear.fun:8080/clash-meta.yaml`
5. 点击 **Download**
6. 等待下载完成
7. 点击配置 → 进入主界面
8. 点击底部 **▶** 启动 VPN
9. 首次启动会请求 VPN 权限

**Android 注意事项**:

- VPN 模式 = TUN 模式，会接管所有流量
- 关闭后回到系统默认网络

### 3.4 Stash(iOS)

1. 启动 Stash
2. 底部菜单 → **Settings**(设置)→ **Profiles**(订阅)
3. 点击 **+** → **URL**
4. 填入:`http://onetear.fun:8080/clash-meta.yaml`
5. 点击 **Download**
6. 下载完成后回到主界面
7. 选择刚下载的 profile
8. 顶部开关打开(变为连接状态)

---

## 四、订阅链接管理

### 4.1 订阅文件格式

mihomo 订阅文件本质是 YAML，核心字段:

```yaml
port: 7890
socks-port: 7891
mixed-port: 7893
allow-lan: false
mode: rule
log-level: info

proxies:
  - name: "节点 1"
    type: ss
    server: example.com
    port: 8388
    cipher: aes-256-gcm
    password: "xxx"
  - name: "节点 2"
    type: vmess
    server: example.com
    port: 443
    uuid: xxx
    alterId: 0
    cipher: auto

proxy-groups:
  - name: "PROXY"
    type: select
    proxies:
      - "节点 1"
      - "节点 2"
      - DIRECT

rules:
  - DOMAIN-SUFFIX,google.com,PROXY
  - GEOIP,CN,DIRECT
  - MATCH,PROXY
```

### 4.2 自动更新订阅

#### Clash Verge Rev

- 订阅 profile 上右键 → **Update**(立即更新)
- 设置定时:Profile → ⋯ → **Update Interval**(建议 24h)

#### mihomo 命令行(脚本)

```bash
#!/bin/bash
# ~/bin/update-mihomo-sub.sh
SUB_URL="http://onetear.fun:8080/clash-meta.yaml"
CONFIG_DIR="$HOME/.config/mihomo"
CONFIG_FILE="$CONFIG_DIR/config.yaml"

curl -L -o "$CONFIG_FILE" "$SUB_URL"

# 通知 mihomo 重载
curl -X PUT "http://127.0.0.1:9090/configs?force=true" \
    -H "Content-Type: application/json" \
    -d "{\"path\":\"$CONFIG_FILE\"}"
```

加到 crontab 每天 6 点更新:

```bash
chmod +x ~/bin/update-mihomo-sub.sh
crontab -e
# 加一行:
0 6 * * * /root/bin/update-mihomo-sub.sh
```

#### Clash Meta for Android

- Profile 列表里点 ⋯ → **Update**
- 设置 → **Update Subscription at**(定时)

### 4.3 多订阅合并

如果想合并多个订阅端，可以用 mihomo 的 `proxy-providers` 字段:

```yaml
proxy-providers:
  provider1:
    type: http
    url: "http://onetear.fun:8080/clash-meta.yaml"
    interval: 86400
    path: ./provider1.yaml
  provider2:
    type: http
    url: "http://other-provider.com/sub.yaml"
    interval: 86400
    path: ./provider2.yaml
```

这样 mihomo 会**自动拉取并合并**多个订阅源。

---

## 五、常见问题

### 5.1 启动后无法访问 Google

**排查步骤**:

1. 确认 profile 已激活(高亮)
2. 确认 System Proxy 开关打开
3. 终端验证代理:

```bash
# macOS / Linux
curl -x http://127.0.0.1:7890 https://www.google.com

# Windows PowerShell
curl.exe -x http://127.0.0.1:7890 https://www.google.com
```

4. 看 mihomo 日志:

```bash
# 桌面端
journalctl -u mihomo -f

# Clash Verge Rev
Settings → Logs → 实时查看
```

5. 测速节点:Profile → 节点 → 右键 → **Test Latency**

### 5.2 TUN 模式 vs System Proxy

| 模式 | 范围 | 优势 | 劣势 |
| --- | --- | --- | --- |
| **System Proxy** | 走系统代理的应用 | 简单、低权限 | 命令行 / 容器 / 部分应用不走 |
| **TUN 模式** | **所有流量** | 全面、Docker 也走 | 需 root / 管理员权限 |

**建议**:日常使用 System Proxy 足够;开发 / Docker / 服务器场景用 TUN。

### 5.3 mihomo 启动失败

```bash
# 1. 检查配置语法
mihomo -d ~/.config/mihomo -t   # test 模式

# 2. 看错误日志
mihomo -d ~/.config/mihomo 2>&1 | head -50

# 3. 端口冲突
lsof -i :7890   # macOS / Linux
ss -tlnp | grep 7890   # Linux
netstat -ano | findstr :7890   # Windows
```

### 5.4 订阅更新失败

```bash
# 1. 手动测试订阅可达性
curl -v "http://onetear.fun:8080/clash-meta.yaml" | head -20

# 2. 检查返回内容是否是 YAML
curl -s "http://onetear.fun:8080/clash-meta.yaml" | head -1
# 应该输出: port: 7890  或  # ...

# 3. 客户端里:Profile 重新 Import
```

### 5.5 macOS 提示"无法打开，因为开发者无法验证"

```bash
# 解决:系统设置 → 隐私与安全性 → 仍要打开
# 或命令行:
sudo xattr -dr com.apple.quarantine /Applications/Clash\ Verge\ Rev.app
```

### 5.6 iOS 无法搜索到 Stash

需要海外区 App Store 账号(美区/港区/日区)，中国大陆账号搜不到。可以租共享账号或自行注册。

### 5.7 Linux 启动 mihomo 报 "operation not permitted"

```bash
# TUN 模式需要 CAP_NET_ADMIN
sudo setcap cap_net_admin,cap_net_bind_service=ep /usr/local/bin/mihomo

# 或者用 root
sudo mihomo -d /etc/mihomo
```

---

## 六、附录:可执行命令汇总

```bash
# ============ Linux 服务器一键安装 mihomo ============
ver="1.19.0"
arch=$(uname -m)
case "$arch" in
    x86_64)  bin="mihomo-linux-amd64" ;;
    aarch64) bin="mihomo-linux-arm64" ;;
    *)       echo "Unsupported arch: $arch"; exit 1 ;;
esac

wget -O /tmp/mihomo.gz "https://github.com/MetaCubeX/mihomo/releases/download/v${ver}/${bin}-v${ver}.gz"
gunzip /tmp/mihomo.gz
chmod +x /tmp/mihomo
sudo mv /tmp/mihomo /usr/local/bin/mihomo

mkdir -p ~/.config/mihomo
curl -L -o ~/.config/mihomo/config.yaml "http://onetear.fun:8080/clash-meta.yaml"
mihomo -d ~/.config/mihomo
```

```bash
# ============ macOS 一键安装(Apple Silicon) ============
ver="1.19.0"
curl -L -o /tmp/mihomo.gz "https://github.com/MetaCubeX/mihomo/releases/download/v${ver}/mihomo-darwin-arm64-${ver}.gz"
gunzip /tmp/mihomo.gz
chmod +x /tmp/mihomo
sudo mv /tmp/mihomo /usr/local/bin/
mkdir -p ~/.config/mihomo
curl -L -o ~/.config/mihomo/config.yaml "http://onetear.fun:8080/clash-meta.yaml"
mihomo -d ~/.config/mihomo
```

```powershell
# ============ Windows PowerShell 一键安装 ============
$ver = "1.19.0"
$dest = "$env:LOCALAPPDATA\mihomo"
New-Item -ItemType Directory -Force -Path $dest
Invoke-WebRequest -Uri "https://github.com/MetaCubeX/mihomo/releases/download/v$ver/mihomo-windows-amd64-$ver.zip" -OutFile "$dest\mihomo.zip"
Expand-Archive "$dest\mihomo.zip" -DestinationPath $dest
[Environment]::SetEnvironmentVariable("Path", "$env:Path;$dest", "User")
Invoke-WebRequest -Uri "http://onetear.fun:8080/clash-meta.yaml" -OutFile "$dest\config.yaml"
mihomo -d $dest
```

---

## 七、参考

- **国内客户端镜像(Wind / macOS / Android)**:<http://onetear.fun:18089/clash_client/>
- mihomo 官方仓库:<https://github.com/MetaCubeX/mihomo>
- Clash Verge Rev:<https://github.com/clash-verge-rev/clash-verge-rev>
- mihomo Party:<https://github.com/mihomo-party-org/mihomo-party>
- Clash Meta for Android:<https://github.com/MetaCubeX/ClashMetaForAndroid>
- V2Box(iOS 免费):<https://apps.apple.com/app/v2box/id6446812418>
- sing-box(iOS 免费开源):<https://apps.apple.com/app/sing-box/id1642689768>
- Stash(iOS 付费):<https://apps.apple.com/app/stash/id1596063349>
- 文档:<https://wiki.metacubex.one/>

---

> 订阅端地址 `http://onetear.fun:8080/clash-meta.yaml` 是 mihomo 格式的订阅——务必使用支持 mihomo 内核的客户端(Clash Verge Rev / mihomo Party / Stash 等)，传统 Clash 客户端可能无法解析。
