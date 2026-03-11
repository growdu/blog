# claude安装教程

## 安装claude

当前openclaw（龙虾）比较火，但是配置比较复杂，可以先安装claude进行体验。

Windows 10/11 或 Linux/macOS(Windows 需要额外安装 Git bash， 后续所有命令默认在git-bash中执行)。

nodejs安装地址点击[这里](https://nodejs.org/en/download/current).

git-bash安装地址点击[这里](https://git-scm.com/install/)

安装nodejs和git后，打开cmd执行如下命令验证：

```shell
node --version
npm --version
git --version
```

上述命令没有报错说明安装完成。

## 安装claude

```shell
# 配置 npm 国内镜像（可选，用于加速下载）
npm config set registry HTTPS://registry.npmmirror.com/

# 全局安装 Claude Code
npm install -g @anthropic-ai/claude-code

# 验证安装
claude  --version
```

刚开始登陆由于没有配置api key，所以无法使用。需要注册购买api key。

## 注册购买deepseek

登录deepseek[官网](https://platform.deepseek.com/usage)。

![alt text](image.png)

充值10块钱就可以玩很久了。

充值完成后点击生成api key并记录下来，后面会用到。

![alt text](image-1.png)

## 配置cluade的api key

### 命令行配置

可以使用环境变量的方式设置，就是打开编辑用户环境变量的方式。

或者打开cmd执行如下命令：

```cmd
$env:ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
$env:ANTHROPIC_AUTH_TOKEN=$env:DEEPSEEK_API_KEY
$env:API_TIMEOUT_MS="600000"
$env:ANTHROPIC_MODEL="deepseek-chat"
$env:ANTHROPIC_SMALL_FAST_MODEL="deepseek-chat"
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1"
```

可以参考这个[文档](https://api-docs.deepseek.com/zh-cn/guides/anthropic_api)。

### 下载cc switch

点击[这里](https://doget-api.oopscloud.xyz/api/download?token=eyJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJodHRwczovL2dpdGh1Yi5jb20vZmFyaW9uMTIzMS9jYy1zd2l0Y2gvcmVsZWFzZXMvZG93bmxvYWQvdjMuMTIuMC9DQy1Td2l0Y2gtdjMuMTIuMC1XaW5kb3dzLVBvcnRhYmxlLnppcCJ9.AQT41YJaemMztYiT_b1Y18gx2yMLjMDPwXoa7ru45D8)下载工具。

双击安装后可以在界面配置。

选择claude。

![alt text](image-2.png)

选择deepseek。

![alt text](image-3.png)

这里填api key。

![alt text](image-4.png)

## 开始对话

```shell
cluade
```

![alt text](fc31c7efa4cd0f07ccc5938624cb8065.png)

## 安装龙虾

龙虾权限比较高，建议在虚拟机或者不重要的机器上试玩。

```shell
npm i -g openclaw
```

需要自行去了解配置。