Shadowsocks 中文名称影梭，是一个跨平台软件、基于 Apache 许可证的开放源代码软件，用于保护网络流量、加密数据传输。

Shadowsocks 使用 Socks5 代理方式，Shadowsocks 分为服务器端和客户端。

Shadowsocks 影梭是一个可帮助一些国家的网络用户访问受地理限制的软件，从而可以使他们能够访问一些正常情况下无法访问的网站。

诸如谷歌，Instagram 等等。在最近几年，Shadowsocks 的使用在变得非常流行，主要归因于它良好的稳定性，以及比使用 VPN 更低的使用成本。

本篇教程将向你展示 Shadowsocks 服务器的搭建过程，按照此教程的步骤操作之后，你就可以下载一个影梭客户端尝试连接你新搭建的影梭服务器并开始使用影梭自由访问各大全球网站。

## 选购服务器

你将使用你计算机上的命令行界面来完成服务器的搭建，需要输入一系列 Linux 命令。

在开始搭建影梭服务器前，我们必须先获取一个位于海外的远程服务器，然后在那个服务器安装影梭程序。

获取服务器并不难，只要选一个海外的 VPS 供应商到它的网站上租用服务器，价格一般是每月 $5。

目前比较流行的 VPS 供应商是总部位于美国纽约的 DigitalOcean 和佛罗里达的[Vultr](https://www.vultr.com/?ref=9174156-8H)，这里[建议选择Vultr](https://www.vultr.com/?ref=9174156-8H)。

因为 DigitalOcean 只支持海外的支付方法，如 Visa 信用卡和 PayPal，而 Vultr 支持支付宝、微信等支付方式。

另外最重要的是 Vultr 的服务器分布更广泛，有很多位于亚洲地区的服务器，亚洲地区的服务器离大陆近所以速度快，而 DigitalOcean 在亚洲的服务器太少。

首先前往 [Vultr 的官方网站](https://www.vultr.com/?ref=9174156-8H)，在那里用你的电子邮箱地址注册一个新用户账户。  
注册完成后要为你的 Vult r账户充值，可以选择支付宝、银行卡、PayPal等方式支付。

![](https://www.myfreax.com/content/images/2022/09/image-2.png)

然后在界面的边栏切换到 `Products` 产品页面，开始创建服务器，这个页面分几个部分，每部分有不同选择和设置，建议按照如下所示选择和设置。

第一步是选择 Cloud Compute，第二步是选择 CPU & Storage technolog。第三步选择 `Server location`。

![](https://www.myfreax.com/content/images/2022/09/image.png)

![](https://www.myfreax.com/content/images/2022/09/image-1.png)

选择自己想要的服务器位置，建议选像日本、新加坡这些离大陆相对比较近的地方。

![](https://www.myfreax.com/content/images/2022/09/image-3.png)

`Server image` 建议选 Ubuntu 最新版本。以下的影梭服务器搭建教程里用的是 Ubuntu 22.04，如果你是新手请选择 Ubuntu 22.04。

![](https://www.myfreax.com/content/images/2022/09/image-4.png)

`Server size` 建议选择 5 美元每月的，3.5 美元每月的服务器只有美国纽约的，离得较远速度可能会比较慢。

![](https://www.myfreax.com/content/images/2022/09/image-5.png)

`Add auto backups` 意思是添加自动备份，我们使用影梭一般不需要这项，可点击取消。`Additional features` 不需改动。

![](https://www.myfreax.com/content/images/2022/09/image-6.png)

`SSH Keys` 不需添加SSH Keys。SSH keys 可代替密码在登录服务器时使用，如果你是新手可以直接使用密码登录。`Server hostname & label` 不需改动。

![](https://www.myfreax.com/content/images/2022/09/image-8.png)

选择完成后就可以点击页面右下角的 `Deploy Now` 按钮创建服务器。服务器需要约十几秒到几分钟时间完成创建。

完成后你可以找到它的 IP 地址和密码复制下来，之后会在下面连接服务器的时候使用到。

![](https://www.myfreax.com/content/images/2022/09/image-9.png)

## Mac SSH 连接到服务器

现在服务器创建好，接下来用 SSH 连接到新创建的服务器，SSH 的使用方法根据你的电脑的操作系统略有不同。

如果你用的是苹果 Mac 系统，你可以直接打开系统内置的 ****Terminal**** 命令行界面建立SSH 会话，不需要安装额外程序。

打开 Terminal 后，输入命令 ssh root@your\_server\_ip 连接到服务器。注意把`your_server_ip` 替换成你的服务器的IP。

```
ssh root@your_server_ip
```

## Windows SSH 连接到服务器

如果你是Windows用户，你需要安装额外的程序，因为 Windows 没有内置用于建立SSH 会话的命令行程序。

你需要安装的应用是一款名为 PuTTY 的软件，你可以点击[这里](https://the.earth.li/~sgtatham/putty/latest/w64/putty-64bit-0.77-installer.msi)下载 PuTTY 软件。

PuTTY 的用法非常简单，只要打开软件找到相应位置输入你的服务器 IP 地址再点下面的连接按钮也就是 Start 按钮，就可连接到服务器。

![](https://www.myfreax.com/content/images/2022/09/putty-tutorial-1.webp)

SSH 连接端口不用修改，SSH端口是 22，注意第一次连接一个新的服务器时会跳出来一个对话框，需要点击是 Yes 才能连接。

![](https://www.myfreax.com/content/images/2022/09/putty-tutorial-2.webp)

![](https://www.myfreax.com/content/images/2022/09/putty-tutorial-3.webp)

## 输入 SSH 密码

无论你使用上面哪种方法连接服务器，你需要以 root 用户登录服务器，命令行界面会显示 login as。

```
login as： root
root@123.457.145.36's password: 
```

然后命令行界面会询问你的密码，输入密码并回车后就可以登录。注意输入密码时命令行界面里不会显示你输入的字符，不用担心，输入完成后按回车即可。

成功登录后，光标会出现在下面一行之后。注意 `@` 后面是你服务器的主机名称。类似于这样 `root@the-hostname-of-your-server:~#`。

## 安装影梭

现在影梭有多个版本供选择，最初的版本的名称就是 Shadowsocks，本教程将选用 Shadowsocks。

之所以没有使用 ShadowsocksR 是因为 ShadowsocksR 已经不再更新，另外Shadowsocks 也在不断更进加密的算法，安全程度也已经超过 SSR。

安装 Shadowsocks 非常简单，运行命令 `sudo apt install shadowsocks-libev -y`。等待安装完成即可。

```
sudo apt install shadowsocks-libev -y
```

Shadowsocks 安装完成后，我们只需要简单修改默认的影梭配置文件即可完成配置。这里需要设置自己的密码。

修改密码的方法很简单，你不需要编辑任何文件，只需要修改下面命令里面的 `你的密码` 就可以。

```
sudo bash -c 'cat << "EOF" > /etc/shadowsocks-libev/config.json
{
    "server":"0.0.0.0",
    "mode":"tcp_and_udp",
    "server_port":8388,
    "local_port":1080,
    "password":"你的密码",
    "timeout":60,
    "method":"chacha20-ietf-poly1305"
}
EOF'
```

然后将这个命令复制到服务器上运行，命令将会替换默认的影梭配置文件。最后每次修改这个命令中内容你都需要重新启动 Shadowsocks。

运行命令 `sudo systemctl restart shadowsocks-libev.service`。除了重启Shadowsocks 服务，还需要禁用防火墙运行命令 sudo ufw disable && sudo ufw allow 8388。

```
sudo systemctl restart shadowsocks-libev.service
sudo ufw disable && sudo ufw allow 8388
```

现在你已经完成服务器端的配置，接下来就可以配置客户端。

## ****客户端APP****

要使用影梭，你需要安装影梭的客户端APP到你的电脑或移动设备上来连接到你搭建的影梭服务器。

这是是用于不同操作系统的Shadowsocks客户端APP。 [Shadowsocks Mac客户端](https://github.com/shadowsocks/ShadowsocksX-NG/releases/download/v1.9.4/ShadowsocksX-NG.1.9.4.zip)，[Shadowsocks Windows客户端](https://github.com/shadowsocks/shadowsocks-windows/releases/download/4.4.1.0/Shadowsocks-4.4.1.0.zip)，[Shadowsocks安卓客户端](https://github.com/shadowsocks/shadowsocks-android/releases/download/v5.3.1-preview/shadowsocks--universal-5.3.1-preview.apk)。

这个下载地址适合手机上没有Google Play服务的安卓用户，其他人可以直接在Google Play应用商店安装ShadowsocksAPP。

苹果手机用户可以到App Store下载Potatso Lite或Shadowrocket，Potatso Lite免费下载使用，Shadowrocket APP是付费应用，要使用需要购买。

苹果手机用户需要注册一个海外iTunes账号，要下载上面那两种影梭app必须用海外iTunes账号才能在App Store里找到。

影梭客户端APP使用方法非常简单，只需要在APP界面里的输入你搭建影梭服务器时设置的那些参数IP，端口，密码，加密方式。

然后点击连接按钮，你的设备就会连接到影梭服务器，之后就可以离开app，让它在后台运行。用浏览器自由访问Google网站。