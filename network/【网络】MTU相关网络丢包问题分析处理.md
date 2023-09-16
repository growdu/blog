## 【网络】MTU相关网络丢包问题分析处理

[![](https://cdn2.jianshu.io/assets/default_avatar/1-04bbeead395d74921af6a4e8214b4f61.jpg)](https://www.jianshu.com/u/e65f29d9cfe1)

0.1082022.09.17 15:09:12字数 2,097阅读 655

## 一、 MTU MSS 概念

什么是MTU？

MTU是数据链路层的概念，限制的是数据链路层payload的大小，即上层协议大小(包括上层协议头)

例如设置主机接口mtu为1450。则在一个TCP报文中，1450 = 20字节IP头 + 20字节TCP头 + 1410TCP数据。

什么是MSS？

MSS最大报文段，是TCP中一个选项，用于在TCP连接建立时，收发双方协商通信时每一个报文段所能承载的最大数据长度(注意不包含TCP头部大小)

如何探测路径MTU值？

Linux主机中: 执行ping x.x.x.x -s 1422 -M do ，x.x.x.x是目标地址，-s指明icmp报文的数据部分大小(不包含icmp 8字节头部)。  
\-M do 表示不允许分片。多试几次，找到临界点。  
以mtu为1450为例，1450 = 20字节IP头 + 8字节icmp头 + 1422数据，则-s指定为1422可以正常通过

Windows主机中: 执行ping x.x.x.x -l 1472 -f ，x.x.x.x是目标地址，-l指明icmp报文的数据部分大小(不包含icmp 8字节头部)，-f表示不允许分片。

## 二、案例分析

从路径上看，丢包点大致可以有下面几个位置：

```
1. 数据中心外部丢包

2. 数据中心内部丢包

3. 主机内部丢包
```

对于数据中心内部丢包问题，最重要的是能 “界定问题边界”，换句话说，这是谁的锅？  
拥有自己数据中心的，往往会由网络工程师负责配置网络，系统工程师管理主机/虚拟化环境。界定的边界办法可以是：

```

1）长ping 网关地址，如果出现丢包，十有八九是网络设备有问题。

2）使用MTR看路径上丢包点。

3）抓包分析

```

MTU丢包

```
1.检查接口MTU配置，ifconfig eth1/eth0，默认是1500；

2.进行MTU探测，然后设置接口对应的MTU值；
```

![](https://upload-images.jianshu.io/upload_images/12979420-0581f0cf5a955a5f.png?imageMogr2/auto-orient/strip|imageView2/2/w/1080/format/webp)

image.png

解决方案：

```
1. 根据实际情况，设置正确MTU值；

2. 设置合理的tcp mss，启用TCP MTU Probe
```

```
# cat /proc/sys/net/ipv4/tcp_mtu_probing

tcp_mtu_probing - INTEGER Controls TCP Packetization-Layer Path MTU Discovery.
Takes three values:
0 - Disabled 
1 - Disabled by default, enabled when an ICMP black hole detected
2 - Always enabled, use initial MSS of tcp_base_mss.
```

![](https://upload-images.jianshu.io/upload_images/12979420-de7e38b913fab5d3.png?imageMogr2/auto-orient/strip|imageView2/2/w/1129/format/webp)

image.png

![](https://upload-images.jianshu.io/upload_images/12979420-c071608d37c1d702.png?imageMogr2/auto-orient/strip|imageView2/2/w/470/format/webp)

image.png

MTU带来的问题实在太多了，但凡做过运维、实施或者技术支持的工程师，或多或少都会遇到。  
一个典型的MTU问题发生在类似图1的环境中，即两个子网的MTU大小不一样。

![](https://upload-images.jianshu.io/upload_images/12979420-3fb85becd6c4c5b1.png?imageMogr2/auto-orient/strip|imageView2/2/w/640/format/webp)

image.png

当客户端发给服务器的巨帧经过路由器时，或者被丢包，或者被分片。  
这取决于该巨帧是否在网络层携带了DF（Don’t fragment）标志。  
如果带了就被丢弃，如果没带就被分片。

从Wireshark上很容易看到DF标志，如图2中的方框内所示。  
分片的情况往往被忽略，因为它只影响一点点性能，大多数时候甚至察觉不出。  
丢包的情况就无法忽略了，因为丢包之后再重传多少遍都没用，会一直丢，整个传输就像掉进了黑洞，所以往往会导致严重的后果。

![](https://upload-images.jianshu.io/upload_images/12979420-440d68631109c1e6.png?imageMogr2/auto-orient/strip|imageView2/2/w/624/format/webp)

image.png

对于 TCP来说，要尽量避免分片。  
因为必须所有分片都到达才能重组成一个包，其中任何一个分片丢失了，都必须重发所有分片。  
分片会增大丢包和乱序的概率，同时也会增加时延。

如果在TCP报文经过的传输网络中有某个设备的MTU设置得太小， 则它会将收到的IP报文进行分片。  
分片会增大丢包和乱序的概率， 同时也会增加时延。

MTU不等，大的数据包就被拆开来传送，这样会产生很多数据包碎片，增加丢包率，降低网络速度。  
不同设备和不同网络对接一定要注意一下MTU值，设置一定要相同，就可以减少丢包，否则会降低网络速度或打不开网页，无法上传数据甚至业务不通。

为什么说 MTU 值会影响网速呢？

在 Win 系统中，MTU 值默认是 1500。假设我们现在要传输 3000 字节的数据，只需要拆分成 2 个数据包就行了。  
而如果是 ADSL 接入方式，它的 MTU 值是 1492 的话，则 3000 字节的数据需要分为 3 个数据包传送。  
由于数据包的数量增多了，同时拆包组包都需要额外消耗时间，因此网速变慢也就不足为奇了。

  

![](https://upload-images.jianshu.io/upload_images/12979420-da0ab50dce20e977.png?imageMogr2/auto-orient/strip|imageView2/2/w/640/format/webp)

image.png

一次MTU问题导致的RDS访问故障  
[https://mp.weixin.qq.com/s/b2bk1dRDJwHCWp7cN\_Vy1Q](https://links.jianshu.com/go?to=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2Fb2bk1dRDJwHCWp7cN_Vy1Q)  

![](https://upload-images.jianshu.io/upload_images/12979420-2a34d3877e2facaf.png?imageMogr2/auto-orient/strip|imageView2/2/w/1200/format/webp)

image.png

```
1. 在DF位没有置1情况下，IP数据包大小超过接口MTU值时，IP数据包会切片(framed)

2. 在DF位没有置1情况下，已经切片的IP数据包在转发过程中不会组装

注：如直连的2个接口，一个MTU为1500，另一个MTU不是1500，可能会产生丢包
（原因：MTU就是MRU；切片发生在数据包发出时，不发生在接收时）

```

MTU一经确定不再改变？

实际上MTU并不是确定了之后就一直不变的，每个端上查看到的MTU并非是最终的MTU大小，这个怎么理解呢？

大部情况下，网络发送端都需要经过各种中间设备才能到达目标机器，这些中间设备可能是路由器、交换机、中间代理服务器等等，这些设备的MTU大小可能有大有小，更糟糕的是，每次走的路径不一样MTU大小可能也不一样。

那么，假如我们的发送端的MTU是1500，中间某个交换机或者路由器的MTU是200字节，当数据包到达这个设备的时候IP层就会触发拆包，很明显如果出现这种情况网络传输效率会大幅降低。  
那么有什么办法可以解决这个问题呢？

我们可以思考一下，要解决这个问题其实只要找到链路中最小的MTU就可以了，那么，我们如何感知中间设备的MTU呢？  
有一个叫ICMP的协议可以在中间设备出现异常的时候将异常返回，从而发送端可以感知到，关于ICMP协议这里不展开，有兴趣可以自行去了解。

实际上，TCP协议已经实现了链路MTU的探测，叫做PMTU，原理就是设置IP报头DF不分片位置为不分片，这样当遇到比MSS小的MTU的设备，这个设备就会返回一个ICMP报文，里面携带了错误消息和可接受的MTU大小。

## 三、参考

什么是MTU值，MTU值有什么用？  
[https://mp.weixin.qq.com/s/gruLG48W7KEJ\_BQJ8tooDQ](https://links.jianshu.com/go?to=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2FgruLG48W7KEJ_BQJ8tooDQ)

GaussDB网络重传/丢包问题定位总结  
[https://bbs.huaweicloud.com/blogs/235237](https://links.jianshu.com/go?to=https%3A%2F%2Fbbs.huaweicloud.com%2Fblogs%2F235237)

网络中一些丢包场景  
[https://mp.weixin.qq.com/s/FdoDfchrYC0H-Rd0wRm4gg](https://links.jianshu.com/go?to=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2FFdoDfchrYC0H-Rd0wRm4gg)

网络延时大，丢包，卡顿，不好用，时断时续找原因  
[https://mp.weixin.qq.com/s/IX8Q8yAdII962r2p8Yd8lw](https://links.jianshu.com/go?to=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2FIX8Q8yAdII962r2p8Yd8lw)

云网络丢包故障定位全景指南  
[https://mp.weixin.qq.com/s/kkn72wtKvjIopySE5VMnbA](https://links.jianshu.com/go?to=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2Fkkn72wtKvjIopySE5VMnbA)

案例分享：MTU值导致视频丢包故障分析  
[https://mp.weixin.qq.com/s/VGtGwtzz2eKTIG3QtwgwkA](https://links.jianshu.com/go?to=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2FVGtGwtzz2eKTIG3QtwgwkA)

MTU导致的悲剧  
[https://mp.weixin.qq.com/s/hRhpwZge\_LEmDfJINp-oyQ](https://links.jianshu.com/go?to=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2FhRhpwZge_LEmDfJINp-oyQ)

解决网络丢包问题及故障判断方法  
[https://mp.weixin.qq.com/s/Zt2SRnbRLHwIbDzErRdxXw](https://links.jianshu.com/go?to=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2FZt2SRnbRLHwIbDzErRdxXw)

一次MTU问题导致的RDS访问故障  
[https://mp.weixin.qq.com/s/b2bk1dRDJwHCWp7cN\_Vy1Q](https://links.jianshu.com/go?to=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2Fb2bk1dRDJwHCWp7cN_Vy1Q)

网速慢？改下MTU值试试  
[https://mp.weixin.qq.com/s/LHAuRMf72J6zm\_hOffW3rA](https://links.jianshu.com/go?to=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2FLHAuRMf72J6zm_hOffW3rA)

案例分享：MTU值对传输网络对接的影响  
[https://mp.weixin.qq.com/s/J6-uG2mY4bGQcU5s-oU-Aw](https://links.jianshu.com/go?to=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2FJ6-uG2mY4bGQcU5s-oU-Aw)

丢包问题研究  
[https://mp.weixin.qq.com/s/GRmqu1xcNZ7wRNjYrrHFCQ](https://links.jianshu.com/go?to=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2FGRmqu1xcNZ7wRNjYrrHFCQ)

MTU系列实验（1）——IP MTU  
[https://mp.weixin.qq.com/s/66sXXTt3B0A8zt8CgB4iug](https://links.jianshu.com/go?to=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2F66sXXTt3B0A8zt8CgB4iug)

TCP问题定界六大方向分析总结  
[https://mp.weixin.qq.com/s/IE2dkmYd0etmlK7G\_wVIHA](https://links.jianshu.com/go?to=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2FIE2dkmYd0etmlK7G_wVIHA)

某局MTU问题导致手机无法上网故障排查过程  
[https://mp.weixin.qq.com/s/HPNPa4IfCnCaU3h4rwNtUg](https://links.jianshu.com/go?to=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2FHPNPa4IfCnCaU3h4rwNtUg)

为什么MSS都小于MTU？  
[https://mp.weixin.qq.com/s/BDsI33nRsZHCx1VhJtyzcA](https://links.jianshu.com/go?to=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2FBDsI33nRsZHCx1VhJtyzcA)

设置路由器MTU与操作系统的MTU值相同，可提升网速  
[https://mp.weixin.qq.com/s/QRdbLdiG3jDc1H8x8sVnjA](https://links.jianshu.com/go?to=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2FQRdbLdiG3jDc1H8x8sVnjA)

更多精彩内容，就在简书APP

![](https://upload.jianshu.io/images/js-qrc.png)

"小礼物走一走，来简书关注我"

还没有人赞赏，支持一下

[![  ](https://cdn2.jianshu.io/assets/default_avatar/1-04bbeead395d74921af6a4e8214b4f61.jpg)](https://www.jianshu.com/u/e65f29d9cfe1)

总资产372共写了114.6W字获得1,861个赞共533个粉丝

-   序言：七十年代末，一起剥皮案震惊了整个滨河市，随后出现的几起案子，更是在滨河造成了极大的恐慌，老刑警刘岩，带你破解...
    
-   1\. 周嘉洛拥有一个不好说有没有用的异能。 异能管理局的人给他的异能起名为「前方高能预警」。 2. 周嘉洛第一次发...
    
-   序言：滨河连续发生了三起死亡事件，死亡现场离奇诡异，居然都是意外死亡，警方通过查阅死者的电脑和手机，发现死者居然都...
    
-   文/潘晓璐 我一进店门，熙熙楼的掌柜王于贵愁眉苦脸地迎上来，“玉大人，你说我怎么就摊上这事。” “怎么了？”我有些...
    
-   文/不坏的土叔 我叫张陵，是天一观的道长。 经常有香客问我，道长，这世上最难降的妖魔是什么？ 我笑而不...
    
-   正文 为了忘掉前任，我火速办了婚礼，结果婚礼上，老公的妹妹穿的比我还像新娘。我一直安慰自己，他们只是感情好，可当我...
    
    [![](https://upload.jianshu.io/users/upload_avatars/4790772/388e473c-fe2f-40e0-9301-e357ae8f1b41.jpeg)茶点故事](https://www.jianshu.com/u/0f438ff0a55f)阅读 7773评论 0赞 65
    
-   文/花漫 我一把揭开白布。 她就那样静静地躺着，像睡着了一般。 火红的嫁衣衬着肌肤如雪。 梳的纹丝不乱的头发上，一...
    
-   那天，我揣着相机与录音，去河边找鬼。 笑死，一个胖子当着我的面吹牛，可吹牛的内容都是我干的。 我是一名探鬼主播，决...
    
-   文/苍兰香墨 我猛地睁开眼，长吁一口气：“原来是场噩梦啊……” “哼！你这毒妇竟也来了？” 一声冷哼从身侧响起，我...
    
-   序言：老挝万荣一对情侣失踪，失踪者是张志新（化名）和其女友刘颖，没想到半个月后，有当地人在树林里发现了一具尸体，经...
    
-   正文 独居荒郊野岭守林人离奇死亡，尸身上长有42处带血的脓包…… 初始之章·张勋 以下内容为张勋视角 年9月15日...
    
    [![](https://upload.jianshu.io/users/upload_avatars/4790772/388e473c-fe2f-40e0-9301-e357ae8f1b41.jpeg)茶点故事](https://www.jianshu.com/u/0f438ff0a55f)阅读 3888评论 1赞 66
    
-   男人动作激烈，情到浓时诛心的话脱口而出，后来他抱着我的骨灰盒说想我…… 1. 双人床上，我在陆翊身下，承受他凶猛的...
    
-   正文 我和宋清朗相恋三年，在试婚纱的时候发现自己被绿了。 大学时的朋友给我发了我未婚夫和他白月光在一起吃饭的照片。...
    
    [![](https://upload.jianshu.io/users/upload_avatars/4790772/388e473c-fe2f-40e0-9301-e357ae8f1b41.jpeg)茶点故事](https://www.jianshu.com/u/0f438ff0a55f)阅读 4156评论 0赞 52
    
-   序言：一个原本活蹦乱跳的男人离奇死亡，死状恐怖，灵堂内的尸体忽然破棺而出，到底是诈尸还是另有隐情，我是刑警宁泽，带...
    
-   正文 年R本政府宣布，位于F岛的核电站，受9级特大地震影响，放射性物质发生泄漏。R本人自食恶果不足惜，却给世界环境...
    
    [![](https://upload.jianshu.io/users/upload_avatars/4790772/388e473c-fe2f-40e0-9301-e357ae8f1b41.jpeg)茶点故事](https://www.jianshu.com/u/0f438ff0a55f)阅读 4005评论 2赞 56
    
-   文/蒙蒙 一、第九天 我趴在偏房一处隐蔽的房顶上张望。 院中可真热闹，春花似锦、人声如沸。这庄子的主人今日做“春日...
    
-   文/苍兰香墨 我抬头看了看天上的太阳。三九已至，却和暖如春，着一层夹袄步出监牢的瞬间，已是汗流浃背。 一阵脚步声响...
    
-   文/米丘 我家的后院里埋着一具尸体，是被我官人打死的。这成了我俩的心病，时不时要去坟头那棵树下拜拜，祈祷着这棵树千...
    
-   我被黑心中介骗来泰国打工， 没想到刚下飞机就差点儿被人妖公主榨干…… 1. 我叫王不留，地道东北人。 一个月前我还...
    
-   正文 我出身青楼，却偏偏与公主长得像，于是被迫代替她去往敌国和亲。 传闻我的和亲对象是个残疾皇子，可洞房花烛夜当晚...
    
    [![](https://upload.jianshu.io/users/upload_avatars/4790772/388e473c-fe2f-40e0-9301-e357ae8f1b41.jpeg)茶点故事](https://www.jianshu.com/u/0f438ff0a55f)阅读 5064评论 0赞 72
    

### 推荐阅读[更多精彩内容](https://www.jianshu.com/)

-   我们一起学习了文件系统和磁盘 I/O 的工作原理，以及相应的性能分析和优化方法。接下来，我们将进入下一个重要模块—...
    
-   本文是作为一个测试或者是互联网从业者必须知道的一些知识，面试的时候大概率会问到，对理解网络、分析网络相关的问题有很...
    
-   很难找到一款完全不需要网络的应用，即使是单机应用，也会存在数据上报、广告等各种各样的网络请求 网络基础 Http ...
    
    [![](https://upload.jianshu.io/users/upload_avatars/6446331/c70b4c9d-a6ee-42d3-bbd8-db29ee692492.jpg?imageMogr2/auto-orient/strip|imageView2/1/w/48/h/48/format/webp)今阳说](https://www.jianshu.com/u/06f6a534adf4)阅读 1,875评论 0赞 12
    
-   作为移动端开发，我们常常需要与后台进行网络数据的通信，在我们开发的过程中，常常只是通过一个url+参数，然后...
    
-   参考解密：腾讯如何打造一款实时对战手游从《王者荣耀》来聊聊游戏的帧同步《王者荣耀》技术总监复盘回炉历程：没跨过这三...
    
    [![](https://upload.jianshu.io/users/upload_avatars/2354823/53f9a93e-87d9-48b7-a968-d3e8e142c6a8.png?imageMogr2/auto-orient/strip|imageView2/1/w/48/h/48/format/webp)合肥黑](https://www.jianshu.com/u/50e1d98d51ac)阅读 21,326评论 3赞 41