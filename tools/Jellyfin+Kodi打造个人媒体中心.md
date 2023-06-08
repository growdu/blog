# Jellyfin+Kodi打造个人媒体中心

「一台**7×24**小时运行的电脑可以用来做什么？」系列第二篇。作为一个数字收集癖和整理癖患者，从十几年前在VeryCD上用迅雷慢慢下载TLF组的奥斯卡全集，几KB的速度下几周，到现在对比不同的压制组作品的质量，千兆的网络压得磁盘跟不上下载速度，硬盘容量存不下想要收藏的电影。回望过去，观看的速度永远跟不上下载的速度，甚至现在都不再需要下载再看了，这个过程见证了一段网络、影视、数码的发展历史。

## Docker安装Jellyfin

> Jellyfin is the volunteer-built media solution that puts _you_ in control of your media. Stream to any device from your own server, with no strings attached. Your media, your server, your way.

Jellyfin的功能简单来说就是作为媒体服务器，统一管理影片，它的界面是这样的：

![](https://jellyfin.org/images/screenshots/home_full.png)

相比一堆乱七八糟的文件夹又清晰又高级。

我使用的主机是N1，搭载了荒野无灯开发的小钢炮ROM，已经自带了Jellyfin，不过更新会比较麻烦，因此重新使用Docker安装。

首先禁用自带的jellyfin：

```
# 禁用启动项mv /etc/init.d/S99jellyfin /etc/S99jellyfin.disabled# 关闭运行的jellyfinkillall jellyfin
```

我使用的是docker镜像是`jellyfin/jellyfin:nightly`。

新建Container，端口映射8096/tcp，然后设置/cache，/media和/config三个分区即可。

![](https://raw.githubusercontent.com/Igloo302/igloo302.github.io/master/images/dockerjellyfin.png)

使用指令一键安装：

```
docker run -d -p 8096:8096 -v /your/config:/config -v /your/media:/media -v /your/cache:/cache jellyfin/jellyfin:nightly
```

此外，也可以采用`linuxserver/jellyfin`的镜像：

```
docker create \  --name=jellyfin \  -e PUID=$(id -u jellyfin) \  -e PGID=$(cat /etc/group | grep -e '^users' | cut -d':' -f3) \  -e TZ=Europe/London \  -e UMASK_SET=022 `#optional` \  -p 8096:8096 \  -p 8920:8920 `#optional` \  -v /path/to/library:/config \  -v /path/to/tvseries:/data/tvshows \  -v /path/to/movies:/data/movies \  -v /opt/vc/lib:/opt/vc/lib `#optional` \  --device /dev/dri:/dev/dri `#optional` \  --device /dev/vchiq:/dev/vchiq `#optional` \  --device /dev/video10:/dev/video10 `#optional` \  --device /dev/video11:/dev/video11 `#optional` \  --device /dev/video12:/dev/video12 `#optional` \  --restart unless-stopped \  linuxserver/jellyfin
```

更详细的安装过程也可以参考这篇[教程](https://post.smzdm.com/p/a6lnxg3g/)。

## 整理电影资料库

把混乱的影片文件夹变成精美的海报墙，就需要去获取包括海报、同人画、片名、年份、剧情介绍、演员等等信息，称为「元数据」。

### 使用Jellyfin自带的元数据下载器

元数据下载器可以将电影信息从TheMovieDb等网站中自动下载下来，只需要在添加媒体库的时候，勾选元数据下载器：

![](https://raw.githubusercontent.com/Igloo302/igloo302.github.io/master/images/jellyfinmetadata.png)

除了自带的几个元数据下载器之外，还可以添加插件，如AniDB让其支持更多的影片数据网站。

如果片名识别出错，可以`右击-「识别」`输入片名搜索。

![](https://raw.githubusercontent.com/Igloo302/igloo302.github.io/master/images/jellyfin.png)

### tinyMediaManager

Jellyfin的元数据下载能力并不能让人满意。tinyMediaManager是一款非常优秀的元数据下载器，支持Windows、macOS和Linux。

![](https://raw.githubusercontent.com/Igloo302/igloo302.github.io/master/images/tmm.png)

在[官网](http://release.tinymediamanager.org/)下载最新版，解压后运行tinyMediaManagerUpd.exe打开。在`「设置」-「电影」-「媒体库目录」`和`「设置」-「电视节目」-「媒体库目录」`中添加媒体文件夹，点击上方的`「更新源」-「更新数据源」`，然后全选所有电影，右击选择`「搜索并刮削所选电影 - 自动匹配」`。

![](https://raw.githubusercontent.com/Igloo302/igloo302.github.io/master/images/tmm1.png)

![](https://raw.githubusercontent.com/Igloo302/igloo302.github.io/master/images/tmm2.png)

元数据将被保存为nfo文件和图片文件，Jellyfin会自动识别这些文件。

### R18 WARNING

我并没有收集X片的习惯，只是~出于好玩~尝试了一下用Jellyfin管理迷片。Pockies同学撰写了**2篇**非常详细可靠的文章：

> **Pockies** - [_利用AV Data Capture+Jellyfin+Kodi打造更优雅的本地AV（毛片）+普通影片媒体库_](https://pockies.github.io/2020/01/09/av-data-capture-jellyfin-kodi/) **Pockies** - [_利用EverAver+Emby+Kodi打造本地AV（毛片）媒体库_](https://pockies.github.io/2019/03/25/everaver-emby-kodi/)

和正经影片电视唯一的不同只有Capture Data（或者叫刮削），因为目前没有适用于迷片的Jellyfin的刮削插件，因此我们需要手动将迷片的信息，包括演员、车牌号、名称、剧情介绍和封面设置好。当然这个手动不是自己去网上收集，而是使用一些**爱心人士**开发的小软件将信息保存在NFO文件和JPG文件中，供Jellyfin识别。具体的使用方式就参考Pockies同学的文章吧。

![](https://raw.githubusercontent.com/Igloo302/igloo302.github.io/master/images/R18Library.png)

在Jellyfin中设置完片库之后，可以设置一张自定义的封面：

![](https://raw.githubusercontent.com/Igloo302/igloo302.github.io/master/images/R18Cover.png)

![](https://raw.githubusercontent.com/Igloo302/igloo302.github.io/master/images/R18Cover2.png)

除了在网页上直接播放外，Kodi的Jellyfin插件可以提供更好的观看体验，尤其是在Android电视盒子上。

在[GitHub](https://github.com/jellyfin/jellyfin-kodi/releases)下载最新的Jellyfin插件（不用解压），打开Kodi，插件-从ZIP文件安装-选择jellyfin-kodi-xxx.zip。安装成功后按照引导操作即可。

为了让插件自动同步服务器的媒体内容，可以在Jellyfin服务器安装Kodi Sync Quene插件，同时在Kodi的Jellyfin插件设置中打开Sync-Enable Kodi Sync Queue

![](https://raw.githubusercontent.com/Igloo302/igloo302.github.io/master/images/Kodi+Jellyfin.png)

Enjoy now!