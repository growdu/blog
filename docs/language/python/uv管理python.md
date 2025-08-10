# uv管理python

## 安装 uv

首先需要安装 uv 工具：
1. 在 Linux/macOS 上安装

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. 在 Windows 上安装

使用 PowerShell：

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

安装完成后，验证是否成功：

```bash
uv --version
```

## 查看可用的 Python 版本

uv 可以列出支持安装的 Python 版本：

```bash
uv python list
```

该命令会显示所有可通过 uv 安装的 Python 版本（包括 3.8+ 的各个版本）。

uv默认把下载的包保存在用户目录下，windows会保存在C盘上，配置环境变量UV_PYTHON_CACHE_DIR ，指向自定义目录。

## 安装指定版本的 Python

使用 uv python install 命令安装特定版本，例如：

```bash
# 安装最新的 Python 3.12
uv python install 3.12

# 安装指定小版本（如 3.11.6）
uv python install 3.11.6

# 安装最新的补丁版本（如 3.10 的最新版）
uv python install 3.10
```

国内下载速度会有点慢，设置国内镜像地址。添加环境变量UV_PYTHON_MIRROR，设置镜像地址为https://mirrors.tuna.tsinghua.edu.cn/python

uv 会自动下载并安装指定版本的 Python，存储在用户目录下（默认路径：~/.cache/uv/python），无需管理员权限。

## 查看已安装的 Python 版本
```bash
uv python list
```

## 在项目中指定 Python 版本
uv 可以为每个项目指定特定的 Python 版本，通过 pyproject.toml 配置：
初始化项目（如果还没有 pyproject.toml）：

```bash
uv init
```


生成虚拟环境时，uv 会自动使用指定版本：

```bash
uv venv  # 基于配置的 Python 版本创建虚拟环境
```

添加需要的依赖或者使用requirements.txt来下载：

```shell
uv pip install -r .\requirements.txt --index-url https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
```

执行前需要激活虚拟环境：

```shell
.\.venv\Scripts\activate  
```

或者：

```shell
source venv/bin/activate
```

## 切换 Python 版本

如果需要为当前项目临时切换 Python 版本，可以：
安装目标版本（如 3.10）：

```bash
uv python install 3.10
```
修改 pyproject.toml 中的 python-version 为目标版本。
重新创建虚拟环境：

```bash
uv venv --force  # 强制覆盖现有虚拟环境
```

## 卸载 Python 版本

如果某个版本不再需要，可以卸载：

```bash
uv python uninstall 3.10.13
```