很多小伙伴在开了 IPv6 后，发现很多网页有时或经常加载慢、打不开，视频卡顿看不了，手机 App 也不流畅。本文将从原理上分析这个问题，让你彻底明白为什么会这样，要怎样才能彻底解决这个问题。

## 前言

现在流行的私有云 NAS 部署在家里，而一般家庭/企业宽带并没有公网IP，在外访问 NAS 只能通过 NAS 或第三方提供的服务器进行中转，他们给的带宽一般都很小，根本比不上公有云（各种网盘）提供的带宽，所以我们在外面并不能通畅上传或下载 NAS 中的文件，大大限制了 NAS 的应用范围。

感谢国家大力推广 IPv6， 目前（2023年）各大电信运营商已经在局端默认给终端用户开通了公网 IPv6 ，只是因为接入路由器的多样性和技术复杂性，运营商的安装维护师傅没有在拨号路由器上启用 IPv6 ，对外也通常宣称是不支持公网 IPv6。很多愿意折腾的小伙伴登录光猫，自行更改为桥接并让其支持v4/v6双协议，然后在自己路由器上启用 IPv6，NAS 也成功地获得了一个公网 IPv6 地址，在外面终于可以全速使用 NAS 了。

但是很快发现，家里的网络也变慢了，具体表现在，有些网页有时加载很慢或根本打不开，视频也经常卡顿甚至停播，手机 App 也出现一样的问题。上路由器把 IPv6 关了后，又一切正常。打电话给运营商的安装师傅，直接建议关闭 IPv6，理由是目前的 IPv6 不成熟。上网查资料找到一大堆文章，讲解得不全面，很多概念似是而，跟着做了也没见效。

其实根本原因还是 PMTU 分片缺陷，本文尝试从原理上分析讲解这个问题，尽量做到深入浅出，让你彻底明白为什么会这样，要怎么样才能有效解决这个问题。

阅读本文需要掌握一点点网络知识，知道 TCP/IP/以太网 分层模型及相关概念。

## 为什么 IPv4 没有这个问题？

真的是 IPv6 还不成熟吗？胡扯！IPv6已经推广运行了这么多年，整个骨干网和城域网都已经很稳定了，业务端各大互联网公司均支持 IPv6 的访问，至少在普通的互联网应用上已经很成熟了，我们手机上默认都是开了 IPv6，也不见得不稳定。如果硬要说不成熟，那也是最后一公里不成熟，翻译成人话就是，你家的拨号路由器不成熟，或者接入的第三方宽带不成熟（非直接接入三大运营商），要么 IPv6 的功能不完善，要么技术不过关配置不正确，没有解决 PMTU 分片缺陷问题。

那为什么 IPv4 就没有这个问题呢？

其实 IPv4 也有这个问题，不少网友都说自己搭的软路由访问某些网站变慢，而换回硬路由就正常，主要原因就在于：

1.  IPv4 支持分片，让大部分（允许分片的）互联网应用都能正常运行，虽然因为分片效率下降了一些；
2.  大多数家用路由器默认对 IPv4 开启了 MSS Clamping，但对 IPv6 却没有；

所以，想办法打开 MSS Clamping 就行了。

## 怎么判断 PMTU 分片缺陷问题？

如果你的网络开启 IPv6 后出现我描述的问题，虽然我有 80% 的把握是PMTU 分片缺陷，但是要准确定位和诊断问题，我们还需要做一些功课。

你需要下载一个抓包工具 Wireshark，以捕获自己电脑上网的那个网络连接上的数据包。为了便于查看，我们仅仅捕获自己电脑访问服务器一刹那的 TCP 连接建立的过程即可，先 ping 一下某个 IPv6 服务器（如知乎 [http://www.zhihu.com](http://www.zhihu.com/) 将在 IPv6 DNS 优先解析出 IPv6 地址），查出它的 IPv6 地址，然后【捕获】【选项】中的过滤器填写 `src host [你电脑IP] || dst host [服务器IP]` ，开始捕获，如果 `[SYN, ACK]` 回包的 MSS 值比 `[SYN]` 去包小 8 字节，就像下图这样，那么恭喜你，你的路由器已经正确配置了 MSS Clamping；如果捕获到的回包的 MSS 值与去包一致，都是 1440，那么就是 PMTU 分片问题了，你需要想办法配置，最后达到下图这样：

![](https://pic4.zhimg.com/v2-db461f4d3a4496f08d67114b49a3c8f7_b.jpg)

那什么是 MSS Clamping？什么是 PMTU 分片缺陷？为什么要分片？为什么 IPv6 不支持分片？我要如果配置 MSS 值？要想弄清楚这一切，还得从 MTU 说起。

## 从 MTU 说起

最大传输单元MTU（Maximum Transmission Unit，MTU），是指某一网络能够传输的最大数据包大小，以字节为单位。MTU的大小决定了发送端一次能够发送报文的最大字节数。如果MTU超过了接收端所能够承受的最大值，或者是超过了发送路径上途经的某台设备所能够承受的最大值，就会造成报文分片甚至丢弃，加重网络传输的负担。如果太小，那实际传送的数据量就会过小，影响传输效率。\[1\]

MTU描述了数据链路层的收发能力，IP层也需要知道它进行正确的分片逻辑，所以MTU是链路层和IP层之间的一种约定，它的意思是从网络层发到二层的数据（IP头 + IP Payload），不能大于MTU，如果大了就会丢弃，这就要求数据包在网络层要把数据包分成符合MTU大小的分片包。

之所以需要 MTU 来约束 IP 协议，是因为我们的二层网络信道的多样性，每种2层网络所能传输的最大有效载荷都是不同的。例如，常规以太网数据包最长可达 1500 字节的有效负载；为了提高传输效率，出现了增强版的以太网巨型帧，最大帧长扩展到了9K；令牌环和 FDDI 能够传输更大的数据包，并且有时使用更大的数据包来减少高速或大容量数据传输的开销。

还有一种场景是隧道技术的应用，也会影响 MTU 的大小。所谓隧道技术，是指网关设备把一种协议的数据包封装到另一个协议中以跨过网络传送到另一个网关的处理过程。 隧道技术本质是一种数据包封装技术，在底层协议MTU未改变的情况，被封装的协议因为加了额外的报文头部，其支持的数据净荷必然会相应减小。常见的隧道技术如 xDSL 的 PPPoE、IPSec/L2TP等VPN、通用路由封装 (GRE)协议等。

比如最常见的 PPPoE 拨号，就在以太网帧中插入了8个字节的PPP头部，导致以太网能传输的有效负载减少了8字节，为第3层仅保留了 1492 字节的传输空间。同样，通用路由封装 (GRE) 使用 24 字节头部，将 GRE 隧道上的 MTU 减少到 1476 字节。显然，各种封装技术的组合会进一步减小 MTU 大小，如 ADSL 上运行的 GRE 隧道的 MTU 仅为 1468 字节。

Linux 上的 ifconfig 命令可以查看某个网络接口的 MTU 大小，如：

```
# ifconfig
ppp0      Link encap:Point-to-Point Protocol  
          inet addr:112.91.246.207  P-t-P:113.90.244.1  Mask:255.255.255.255
          UP POINTOPOINT RUNNING NOARP MULTICAST  MTU:1492  Metric:1
          RX packets:339211 errors:0 dropped:0 overruns:0 frame:0
          TX packets:352650 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:3 
          RX bytes:165885364 (158.2 MiB)  TX bytes:78543988 (74.9 MiB)
eth2      Link encap:Ethernet  HWaddr 20:76:93:53:E0:93  
          UP BROADCAST RUNNING MULTICAST  MTU:1500  Metric:1
          RX packets:2732205 errors:0 dropped:0 overruns:0 frame:0
          TX packets:2311855 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:1000 
          RX bytes:2931869236 (2.7 GiB)  TX bytes:1896190225 (1.7 GiB)
          Interrupt:11
```

Windows 上查看网络接口 MTU 的命令如下：

```
C:\> netsh interface ipv4 show subinterfaces

   MTU  MediaSenseState   传入字节  传出字节      接口
------  ---------------  ---------  ---------  -------------
4294967295                1          0    1039833  Loopback Pseudo-Interface 1
  1500                2  116351254   52169177  WLAN
  1500                1   29136662    9016213  以太网
```

Windows 上设置 MTU 的命令为 (需要管理员身份运行命令提示符)：

```
netsh interface ipv4 set subinterface "需修改的连接名" mtu=值 store=persistent
```

其中，需修改的连接名 和 值 要用相应的值来代替。例如，我这里需要输入：

```
netsh interface ipv4 set subinterface "WLAN" mtu=1492 store=persistent
```

## MTU 与 IP 分片

IPv4 的分片现象发生在网络层，是网络层重要的功能。当源节点收到上层下发的IP 包，或者中间路由器收到要转发的IP包，如果包大小大于设定的 MTU 时，需要对这个IP包进行分片，分成两个或多个IP包依次发送。每个分片所承载数据的首字节在原包的索引都要记录到包头的偏移字段中（以8字节为单位），而且只要不是最后一片，包头的 MF (More Fragment) 标记都应设为 1，以方便目标端对这些分片进行正确重组。

一个分片过的IP包，如果继续遇到更小MTU的节点，还会进行二次分片或多次分片，通信效率进一步下降，如下图 \[2\]：

![](https://pic3.zhimg.com/v2-e7464e9a0d13a0d3301117c963c9c526_b.jpg)

多次分片

这里举一个较为普通的两次分片的场景，假如源端PC网卡的MTU为1500，经过家用路由器拨号（MTU为1492）连接到城域网，最后经过某机房的路由器接入到服务器。因为该机房采用了某种隧道技术，机房的路由器 MTU 被设置成 1484。假设源端要发送一个1500字节的IP数据包，这个数据包到达家用路由器后被分片成 1492B 和 28B（IP头部加了20B） 两个IP包，1492B的包到过机房路由器后进一步分片为 1484B 和 28B 两个IP包，最后三个IP到达服务器后进行重组，解析出上层 TCP 报文。从数据效率看，经过两次分片，多传输了40个字节，好像也没什么大不了的。但是，从一个包变成3个包，中间的每个路由器都要分出计算资源进行解析、选路和转发，目标服务器端也要进行重组，这都是额外开销。如果源端发一个大文件，被分段成1万个1500B的IP包，那么整个网络就要额外多承载2万个小包。

有两种情况不允许分片：

-   发送方应用程序设置了不允许分片（如ICMP 的 PMTU 探测报文）
-   IPv6数据包不允许任何中间路径节点分片，只允许源节点分片

正常情况下，IPv4包大于MTU是会被分片的。但是有的上层报文（如ICMP、TCP、UDP）为了数据的完整性，并不想在网络层由于MTU的关系而进行分片，它宁愿丢弃，也不愿意分片后发送，比如下文会提及的 ICMP 的 PMTU 动态探测技术就是利用这一点。因此，IPv4 包头部的标志位除了上述的 MF，还有一位是 DF (Don’t Fragment)，如果发送端不希望报文被分片，可设置为1，以阻止IP节点对IP包进行分片。下图为IPv4的包头格式\[3\]：

![](https://pic2.zhimg.com/v2-38be0eb910e224e7dba9d0a151b81239_b.jpg)

IP包头

IPv6报文的基本头部没有分片标记和分片偏移字段，这些字段被移到了扩展头部，而中间路由器不会处理扩展头部（有1个例外），所以IPv6不允许任何中间节点对其进行分片。通过分段扩展首部，IPv6允许源节点在发送时分片，经过中间节点的直接路由转发后，在目标节点对这些分片进行重组，这过程与IPv4类似。下图描述了IPv6的包头相对IPv4的变化：

![](https://pic1.zhimg.com/v2-40cd99079857f132de2b900eb2d68354_b.jpg)

为什么 IPv6 被设计为不支持中间节点分片？主要原因有：

1.  **提升效率**：在 IPv4 当中，中间路由器的分片功能对路由器来说较为复杂和耗时，分成多片后也显著增加了后续所有路由器的转发开销，这对整个网络的通信效率产生了一定程度的影响。IPv6 作为IPv4的升级协议，自然考虑到了这一点，把它移到源端和目标端进行分片重组，能有效地提升中间路由器的转发效率。
2.  **提升安全性**：分片一直是 IPv4 中安全漏洞的常见来源。对于分片的 IPv4 数据包，第 4 层报头信息（如TCP）在第2个到最后一个分片中不可用。分片和分片重组的过程可能会在中间节点（如防火墙和路由器）和终端节点（如用户计算机）中产生意外和有害的行为。

## PMTU (Path MTU) 及动态探测

顾名思义，Path MTU就是指传输路径的MTU，无需分片就能穿过某路径的数据包最大长度。在从发送端到接收端的传输路径上，如果网元的MTU设置不一致，则决定该路径可用MTU的，其实是整条路径上的最小MTU值。以Path MTU作为IP包长发送数据，既高效又能避免分片，如下图\[4\]：

![](https://pic4.zhimg.com/v2-c582c1e56069c2f3bfb708b044c0d493_b.jpg)

Path MTU示意图

PMTU是一个动态的概念，互联网上两台主机之间的 PMTU 并不是一个常数，它取决于当时所选择的路径，而且路由选择也不一定是对称的(从A到B的路由可能与从B到A的路由不同)，因此，PMTU在两个方向上不一定是一致的。

RFC 1191(IPv4)和RFC 1981(IPv6)定义了动态探测PMTU的技术 —— PMTUD (Path MTU Discovery)，用于确定两个IP主机之间的Path MTU。首先源节点假设Path MTU就是其出接口的MTU，发出一个试探性的报文，并设置该报文不允许被分片。当转发路径上存在一个小于当前假设的Path MTU时，转发设备就会向源节点发送回应的 ICMP 报文，并且携带自己的MTU值，此后源节点将Path MTU的假设值更改为新收到的MTU值继续发送报文。如此反复，直到报文到达目的地之后，源节点就能知道到达目的地的Path MTU了。

![](https://pic1.zhimg.com/v2-71b533bdf24e95b10234b6cf8eaa9948_b.jpg)

Path MTU探测

目前IPv4网络其实没有有效手段来发现PMTU 。主要原因是：

-   某些运营商或网站考虑网络安全或其他需要，把ICMP探测报文过滤掉了。
-   Path MTU需要主机和互联网上的各种网络设备（交换机、路由器、防火墙等）的配合，但有些网络设备不遵从RFC 1191协议。

IPv6 因为不支持中间路由节点分片，PMTU 发现机制就显得至关重要了。如果源节点不执行 PMTU 发现，它必须发送不大于 1280 字节的最小 IPv6 MTU 大小的数据包。如果【数据包过大】的 ICMPv6 回传报文被某一路由器过滤掉，源节点将无法获知数据包被丢，这对于 IPv6 来说是致命的打击。

ping 程序的ICMP不可到达错误，就是采用PMTU动态探测的方法， traceroute 程序也是用这种方法来确定到达目的节点的PMT的。

我们可以使用 `ping -f -l [SIZE] [目标IP或域名]` 命令来探测到指定目的节点的PMTU，其中 -f 表示强制不分片，-l 用于指定 ping 数据包的大小，最大能正常ping 通的 SIZE 加上ICMP包头的28字节即为 MTU，如：

```
C:\> ping -f -l 1465 www.baidu.com
正在 Ping www.a.shifen.com [14.119.104.254] 具有 1465 字节的数据:
需要拆分数据包但是设置 DF。
……

C:\> ping -f -l 1464 www.baidu.com
正在 Ping www.a.shifen.com [14.119.104.254] 具有 1464 字节的数据:
来自 14.119.104.254 的回复: 字节=1464 时间=7ms TTL=56
```

实际环境下捕获的ICMP需要分片但DF位置一的差错报文，下图为其解码格式\[5\]：

![](https://pic4.zhimg.com/v2-55785c722b16f0e38c16d2ae7a25c4cb_b.jpg)

ICMP需要分片但DF为1

我们可以看到其差错类型为3，代码为4，并且告知了下一跳的MTU值为1478。在ICMP差错报文里封装导致此差错的原始IP报文的报头（包含IP报头和四层报头）。

## PMTU 黑洞

综上所述，在整个互联网网络上，虽然上层运行的都是 TCP/IP 协议，但是，由于底层的通信媒介的多样性（以太网、无线、PPPoE等）、核心路由器和各级接入路由器的配置也各不相同（可以理解为每个网元的链路层收发能力（MTU）都有差异）；而客户端PC到服务器之间的路由选路每次都可能不一样，数据包在去的时候和回来的时候也可能不同（非对称），自然而然，每次路由的PMTU也不尽相同。

如果源发送端的 MTU 设置得过大，某次路由路径中的某个中间节点的MTU过小，而数据包又恰好被应用层设置了不允许分片，又或者这是一个IPv6数据包，那么这个节点只好把这个包丢弃，同时产生一条【数据包过大】的 ICMP 报文，告知源端自己能处理的 MTU。

不幸的是，这个ICMP报文不一定能回传到源端，因为回程的某个中间节点可能因为安全原因禁用了ICMP，被它丢弃了。最终的结果是，源发送端的上层不知道数据被丢，只能尝试通过超时重传来解决。然而发送端判断超时的时间都比较长，这一个报文没发完，后续的所有报文都得等待。更加糟糕的是，发送端即使超时重传了，重传的数据包很大可能仍走同一条路，同样被那个节点丢弃，最终后果是，上层业务被阻塞，要打开的网页或视频一直转圈圈。什么时候路由选路能避开那个节点（看你的人品运气），什么时候就能恢复。

这个节点就像黑洞一样，隐藏在网络深处，悄悄地吞噬掉过路的大数据包，造成上层通信业务的灾难性后果。这个黑洞对于 IPv6 尤为明显，因为所有的 IPv6 数据包都不允许路由器分片，而 IPv4 不是所有，只有一小部分应用不允许分片。

## 如何正确配置 MTU

MTU 不能设置得过大，过大造成分片影响传输效率，甚至形成的PMTU黑洞，但也不能过小，过小会造成通信效率的下降。要根据不同场景不同设备（源端、接入网络、骨干网、城域网络），配置一个合适的值。

需要特别注意的是，MTU大小的选择与 IPv6 无关，因为 MTU 是数据链接层（二层）对上层的约束，无论第三层使用的是IPv4还是IPv6，都需要遵守这个同样的 MTU，而不是因为上层使用 IPv6，包头比IPv4大20字节，MTU就要相应减小。至于后面会说到的防火墙的 –clamp-mss-to-pmtu 选项，那是 iptalbes 把 MSS 修改为MTU，属于强行关联到 MTU，概念不可混淆。

MTU大小选择的一个最基本的原则是，对接的两个三层设备以太网接口MTU配置需要保持一致。同时还需要考虑多种场景下各种封装标签对报文大小的影响，例如封装MPLS标签，每层标签会增加4字节，增加MPLS标签后，报文长度也可能超过链路层允许发送的范围，导致报文无法转发。

![](https://pic3.zhimg.com/v2-ea0261b2a22e84206ddbcba0711b208e_b.jpg)

两端MTU保持一致

### 骨干/城域/接入网络MTU的配置

作为普通用户，我们可以信任骨干网、城域网和国内三大运营商提供的接入网络都配置了靠谱的路由设备，由靠谱的工程师进行了靠谱的配置，最低能保证最小 1500 的 MTU 设置。

为保证骨干网络、城域网络、接入网络的完美工作，MTU 通常被设置为远大于以太网标准的基本要求1500字节。通常现有的大型路由器、交换机设备，都可以支持到9000以上的大数据报文，但缺省配置各厂商并不相同，很多厂商设备的缺省MTU配置仍然是1500字节。并且因为网络中很可能运行OSPF、ISIS等需要协商MTU的路由协议，所以互相对接的不同厂商的设备的MTU也要调整为相同。因此，在满足网络和运营商规范且各个厂商都支持的情况下，尽量将MTU配置的大一些 \[6\]。

有一些小的接入网络服务提供商或者个人提供的接入服务，由于技术水平参差不齐，所配置的 MTU 有可能小于1500字节。

### 数据中心/机房等服务器网络MTU的配置

作为服务器端的运维工程师，你也需要注意MTU的配置。在数据中心等网络的建设中，需要确定MTU的配置规范，在各个厂商都支持的情况下，尽量将MTU配置的大一些。

在目前大规模建设的数据中心等网络中，通常没有对MTU进行统一调整。随着新技术的应用，MTU的问题会逐步暴露出来。比如为进行大二层扩展进行的各类隧道技术的使用，VPLS、VXLAN等。这些技术无一例外的都使用了额外的封装，形成了超大报文，例如VXLAN会在原始报文基础上增加50字节。如不统一进行MTU的规划，会导致传输效率低下，或者业务中断。\[7\]

### 家庭/企业终端网络MTU的配置

对于普通家庭/企业网络这些终端网络的配置来说，路由器的配置要与接入网端设备相对应，如国内常用的 PPPoE 拨号接入，路由器MTU配置为 1492 ，比以太网少8字节即可。

如果局域网上的PC主要是访问公网，那么把这些PC的MTU设置为跟拨号路由器一致，能避免拨号路由器的IP分片。因为PC默认是1500，比PPPoE多8字节。

下面的情况可以设置更小的MTU，以提升通信效率，否则尽量保持默认或最大：

1.  通过`ping -f -l 14xx [IP]` 确定了到某一服务器的PMTU为更小值；
2.  使用了L2TP、IPSec等VPN隧道，需要减去新增字段的大小；

### 为什么 IPv6 路由器不能随意减小 MTU

网上有不少文章似懂非懂，根据IPv6包头多20字节的事实，就要在路由器上设置更小的MTU（比如 1432 / 1452 / 1472），这是解决不了问题的。

我们知道，MTU 是第二层数据链路层定义的规范，表征的是数据链路层的数据收发能力，是对第三层的约束，与第三层使用的协议无关。单纯在路由器减小MTU是解决不了 IPv6 访问不稳定的问题的（除非防火墙还开了MSS钳制为PMTU，见下文），反而可能加重问题，比如拨号路由器被设置成1432，而你的PC还是默认的1500，那么大数据包到达你自己的路由器时就被丢弃了，因为 IPv6 不支持中间路由器分片。

当然，如果在源端PC上减小MTU到合适的大小，是能解决问题。因为数据包在源端就被分成小片，中间路由器无需要分片。

## MSS 与 TCP报文分段

MSS (Maximum Segment Size，最大报文长度)，是 TCP 提交给 IP 层的最大数据段大小，不包含 TCP Header 和 TCP Option，仅指 TCP Payload 的字节数。因此，MSS 是 TCP 用来限制应用层最大的发送字节数。

在TCP连接建立时，收发双方将协商后续通信时用的 MSS （附在 SYN/ACK报文头部的 可选字段中），指示每一个报文段所能承载的最大数据长度。

在以太网环境下，MSS=MTU-20字节TCP报头-20字节IP报头，PPPoE还要再减8字节帧头。 MSS值只会出现在SYN报文中，即SYN=1时，才会有MSS字段值。

PC访问某网站时进行TCP三次握手流程如下图：

![](https://pic4.zhimg.com/v2-db461f4d3a4496f08d67114b49a3c8f7_b.jpg)

1.  首先客户端会发送一个SYN请求报文，这个SYN报文的“选项”字段中会有MSS值（MSS = MUT - IP首部长度 - TCP首部长度）。该MSS值是为了告知对方最大的发送数据大小。
2.  当服务器端收到SYN报文后，会向请求端返回SYN+ACK（同步确认报文）报文，其中的“选项”字段也会有MSS值。
3.  通信双方选择SYN和SYN+ACK报文中最小的MSS最为此次TCP连接的MSS，从而达到通信双发协商MSS的效果。

双方在后续通信时，如果上层（应用层）下发的数据过长，超过 MSS，将按 MSS 的长度进行TCP报文的分段，分段后的报文再提交给IP层。由于MSS仅仅是源端和目标端双方协商的（还在第四层），它们并不清楚中间节点的PMTU，所以 MSS 也只是描述通信双方在TCP层的收发能力。源端和目标端之间的所有中间路由节点，对这个上层协商的MSS也都是不清楚的，所以在源端按MSS进行TCP报文分段后，如果IP报文长度超过 MTU，IP层协议仍然会对其进行分片。分段和分片是独立的。

可见， MSS 并不能根本解决 PMTU 黑洞问题，也不能解决因底层（IP）分片造成的传输效率问题。

## MTU和MSS的联系与区别

它们的相同点均是用来约束或协商通信双方的最大数据包长度的。虽然MSS和MTU没有必然的相互关系，但是，对于通信发起方的源站点来说，为了在本机追求最大的效率，MSS 应设置为本机 MTU - IP-Header(20) - TCP-Headerr(20) ，这样能在最大长度的情况下，避免同一TCP报文不会被分成多片IP包 —— 但这也仅仅是本机，中间路由节点该分片还是得分片。

以太网中，本机 MTU 与 MSS 的最佳关系如下图 \[8\]：

![](https://pic3.zhimg.com/v2-e576fd51779414d87e96422278f4e94e_b.jpg)

本机MTU与MSS的关系

MTU和MSS的主要区别在于：

1.  协议层次不同：MTU 表征 OSI 模型的第二层数据链接层的通信能力，而 MSS 表征第四层传输层TCP的通信能力；
2.  实现方式不同：MTU 仅仅是一个规范，一个第二层对第三层的约束，而 MSS 除了约束，还定义了TCP连接建立时的关于收发能力协商过程；
3.  影响范围不同：MSS仅影响了源端和目标端，而MTU影响了整个路由路径上的所有节点；

## 绝招： MSS Clamping

由上文可知，我们想设置一个理想的 PMTU 几乎是不可能的，因为每次路由路径都可能不同，自然不可能有一个固定的理想值，最多我们根据经验设置一个相对合适的值，让分片或丢失的机率尽可能小；MSS只用于通信双方的协商，中间节点毫不知情，也不能解决本质问题；本来 PMTUD（PMTU探测）机制有望能很好的解决这个问题，奈何网络上关闭ICMP的节点一大把，整个机制形同虚设。

MSS 最大的优势在于，它有一个连接建立时的协商机制，能约束源端高层（TCP）发送数据段大小，只是仅限于双方协商出的值不准确，不能反映整个路由路径的传输能力，大大影响了其效能。假如这个数值能由整个路由路径上的每一节点参与协商，这样得出的MSS值将与PMTU一样准确，再由源端高层就按这个数值进行TCP分段，那么可以预见，源端发出的每一个IP包的大小都是刚刚好的，只要不改变路由路径，其发出的IP包都将被正确转发且不被分片。

MSS Clamping （MSS 钳制）就是这样一个打破层级界限的绝招，它工作在路由器上，对路过的每一个包（不管是转发还是上层提交的包）进行嗅探，如果发现某一包是TCP连接建立的握手包，就去偷窥人家正在协商的MSS值（SYN/ACK包中的MSS字段），一旦发现该值比本机的MTU换算出来的MSS值还大，还要去偷偷修改包中的MSS，把它修改为本机换算的MSS值（即：本机MTU-IP头-TCP头）。然而通信双方并不清楚这点，他们还傻傻的以为包中的MSS值就是对方的MSS，赶紧把本次连接的MSS修改为这个更小的值。如果路过的所有路由器都开了 MSS 钳制，那么，到达源端/终端的SYN/ACK包中的MSS值就一定是整个路由路径中所有节点最小的PMTU了，多么完美的一个机制！

下图详细解释了MSS Clamping的整个流程，以及后续的数据收发细节\[9\]：

![](https://pic2.zhimg.com/v2-02339e3bfdcf0ebd0297b959b4558ebd_b.jpg)

MSS 钳制

从通信协议设计的角度来看，MSS Clamping 是一个不安分的破坏分子。整个TCP/IP协议栈都是分层设计的，而它工作在第三层，却强行去修改第四层的数据包；关键是，MSS 协商机制本来只是给 **通信双方** 交流收发能力用的，没想到路过的关卡竟然胆敢偷看甚至纂改！但我们站在更高的层次看问题，古今中外那些牛逼洪洪的人物，不都是拥有这种打破层级思维界限、敢于推翻旧秩序，建立新秩序的改革者（破坏分子）吗？

看到这里，你应该有一个疑惑。TCP连接建立后，路由路径不可能一直保持不变，那么连接建立时钳制出来的 MSS，后续就不准确了，看起来 MSS Clamping 仍然没有根本解决问题，最多只是缓解了问题。理论上是这样的，但实际应用上，骨干/城域/接入网络都能保障MTU ≥ 1500，互联网服务商的路由设备也由专业的网管人员维护，一般也能 ≥ 1500。问题更多出现在用户端的内部设备和拨号出口路由，这些网络设备大都是中低端，拥有整条链路几乎最小的 MTU（PPPoE的1492），另外它们功能能否保障，技术人员是否足够专业，都要打大大的问题。因此，PMTU 黑洞问题看起来没有想像中的那么难搞，只要搞定最后一公里即可。

我们现在再回过头来看看整个路由路径，可能改变路径的地方恰恰是最复杂也最有保障（MTU ≥ 1500）的骨干网、城域网和运营商的接入网，而没技术保障的用户端路径和服务器端IDC机房路径又几乎是必经之路，因此，MSS Clamping 方案仍然是最接地气、最能解决PMTU分片和IPv6黑洞问题的最佳方案。

还有一个问题，怎么保证TCP通信途经的所有路由器都开启了 MSS Clamping ？不然钳制出来的 MSS 就不是 PMTU 了，不是吗？确实。但我们并不追求一定要得到绝对理想的 PMTU，根据木桶理论，最短的木板还是在最没技术保障的用户端设备（也是路由选路的必经之路），那里的接入路由器通常使用了PPPoE，几乎是整条链路最小的 MTU， 只要在那里正确配置了 MSS Clamping，就能保证所钳制的MSS全路径最小。

## 哪些设备需要开启 MSS Clamping

从上文可知，骨干网、城域网、运营商的接入网络和IDC机房的内部网络，其二层运行的太部分都是以太网，都能保证 ≥ 1500 的有效负载。即使这些网络使用了不同的二层网络，或者使用了复杂的隧道技术，因为有专业技术人员的支持，即使达不到 1500 的MTU，也会配置正确的 MSS Clamping，作为普通用户，我们无需操心。我们关注自己这边的通信设施就好。

引起 PMTU 变化的关键节点，是那些连接不同网络进行转换的网关路由器，包括使用了隧道封装技术的各种网关（ 如IPSec、L2TP等VPN、IPv6-over-IPv4 或 IPv4-over-IPv6 等），我们要特别关注的这些设备，要为其配置正确的 MSS Clamping。

比如典型的 PPPoE 拨号的路由器，它一端是 MTU= 1500 的内网以太网，一端是 MTU= 1492 的PPPoE链路，如果没有配置正确的 MSS，没有开启 MSS Clamping，我们在内网 PC 上发出的 IPv6 数据包必须会被它丢弃。

## 正确设置 MSS Clamping

专业的路由器一般都支持 MSS Clamping，如 Cisco 路由器的配置命令为 `ip tcp adjust-mss [size]`，注意该命令是双向的 —— 在所配置接口的入站和出站的 SYN / ACK 数据包中都将进行钳制 \[10\]。

家用路由器如果是拨号上网，厂商为了网络稳定，一般默认就开启 MSS Clamping，如基于华硕系统修改的 Padavan ，执行命令 `iptables -L` 可以看到这样一条转发规则：

```
[XXX-Router /home/root]# iptables -L
...
Chain FORWARD (policy DROP)
...
TCPMSS   tcp  --  anywhere      anywhere      tcp flags:SYN,RST/SYN TCPMSS clamp to PMTU
```

Linux 的 iptables / ip6tables 也支持 MSS Clamping，可以创建基于 mangle 表的 forward 链 `--set-mss [size]` 或 `--clamp-mss-to-pmtu` 选项的规则来启用 MSS 钳制，可以指定具体的 MSS 值，也可以直接钳制到 PMTU（其实就是本机的MTU），如 \[11\]：

```
# 下面命令钳制到 1452，适合 PPPoE 用户
iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss 1452
ip6tables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss 1452

# 下面命令是自动钳制到PMTU，此时应设置本机正确的 MTU，如 PPPoE 为1492
iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
ip6tables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
```

如果要指定只对某一网络接口进行钳制，而不是对所有转发的包都钳制，可以操作 PREROUTING 表，并指定拨号的接口名称（ppp0），如：

```
ip6tables -t mangle -A POSTROUTING -p tcp --tcp-flags SYN,RST SYN -o ppp0 -j TCPMSS --clamp-mss-to-pmtu
```

注意IPv4 和 IPv6 要分别配置。其它基于 iptables 的路由器（如 Padavan）都可以参考这个方法。

在 OpenWrt 路由器上，除了上面的通过修改 iptables 规则的方法，还可以通过 Luci 界面进行配置：在【网络】【防火墙】【基本设置】【区域】处，在对应接口上勾选【MSS 钳制】即可。

RouterOS 路由器设置MSS Clamping 的命令如下(其中pppoe-out1是wan口，1432是要MSS值，请根据需要修改)：

```
/ipv6 firewall mangle add chain=forward out-interface=pppoe-out1 protocol=tcp tcp-flags=syn action=change-mss new-mss=1432
```

UBNT Edgerouter 系列设备 设置 MSS Clamping 的命令如下：

```
set firewall options mss-clamp6 interface-type pppoe
set firewall options mss-clamp6 mss 1432
```

其它中低端的路由器，配置界面上可能看不到相关信息，但 IPv4 一般都默认开启了 MSS Clamping，而 IPv6 就不一定了。

## 蜂窝 4G 网络的 MSS 的分析

我们知道，手机上的数据网络早就用上了 IPv6 ，而且默认就是 IPv6 优先，上网却一直很稳定流畅，那移动运营商的 4G 网关到底是怎么处理 IPv6 碎片问题的呢？为了弄清楚这个问题，我特意用我的电信手机（MIUI系统、4G数据）开热点，电脑（Windows 10）连接上去，用 Wireshark 抓包。

这是 4G 网络下访问知乎 IPv6 服务器的截图：

![](https://pic2.zhimg.com/v2-2617882c6e81b29cd5f3d11b1bf40cc5_b.jpg)

这是 4G 网络下访问百度 IPv4 服务器的截图：

![](https://pic1.zhimg.com/v2-a3c5f91706f9242ec3302ef7f412b014_b.jpg)

此时 Windows 电脑上 WLAN 连接的 MTU 被改为 1410：

```
C:\> netsh interface ipv6 show subinterfaces
   MTU  MediaSenseState   传入字节  传出字节      接口
------  ---------------  ---------  ---------  -------------
  1410                1  117539374   58911024  WLAN
  1500                5          0        152  本地连接* 1
```

作为对比，这是同一台电脑用连接PPPoE拨号路由器的WIFI后，访问知乎 IPv6 服务器的截图：

![](https://pic4.zhimg.com/v2-db461f4d3a4496f08d67114b49a3c8f7_b.jpg)

这是宽带PPPoE拨号访问百度 IPv4 服务器的截图：

![](https://pic2.zhimg.com/v2-2fa9c26810683bb28bed62f7fc512561_b.jpg)

此时 Windows 电脑上 WLAN 连接的 MTU 恢复为正常的 1500：

```
C:\> netsh interface ipv6 show subinterfaces
   MTU  MediaSenseState   传入字节  传出字节      接口
------  ---------------  ---------  ---------  -------------
  1500                1  118029364   62131090  WLAN
  1500                5          0        152  本地连接* 1
```

可以看到，安卓系统AP程序 或运营商的 4G 网关把 IPv6 的 MSS 砍到了 1300，把 IPv4 的 MSS 也砍到了 1370，比我们 PPPoE 拨号网络小很多。

这里有几个疑惑没有弄懂：

1.  电脑连上手机热点后，电脑的 MTU 被调为 1410，比正常的 1500 少了 90 字节。手机热点是怎么更改电脑 MTU 的？通过 DHCP？
2.  安卓系统AP程序或运营商的 4G 网关为什么使用更小的 MSS？是蜂窝网络的 MTU 本身就更小，还是4G接入网络使用了其它隧道技术，又或者特意调小以提高 IPv6 的适应性？结合其它网友的实验，不同品牌手机的MTU各不相同，有的是1432，而 iPhone 的MTU 只有1280，由此推断，更大可能是手机为了提升IPv6 的适应性，特意把 MSS 调小了。

不管怎样，如果我们的拨号路由器上开了 MSS Clamping 的情况下，MTU 设为 1492 仍然不够稳定的话，可以考虑照搬 4G 网络，把 IPv6 也砍到 MSS = 1300 或 MTU=1368 。

## 双栈 DNS 优化

那么，在双栈环境下到底使用哪个协议栈？有没有优先顺序可供我们设置？是客户应用程序、底层操作系统、还是DNS服务器决定优先走哪个协议栈？

答案是应用程序自己决策。标准的DNS服务器没有能力控制程序优先使用哪个协议，它只能同时提供IPv4和IPv6的域名记录供客户端查询。客户端应用程序在建立TCP连接前，首先要把域名转换为IP地址，这通过向域名服务器发起DNS查询请求实现，在DNS请求时需要指定查询的类型，IPv4地址是A类型，IPv6地址是AAAA类型，应用程序既可只查其一，也可同时查询两种地址，然后根据程序自身的逻辑来选择使用哪个。对于绝大多数使用 BSD socket API 的应用程序，会使用getaddrinfo函数来解析域名，然后依次尝试连接，此时优先使用哪种协议就是由底层系统控制的了，getaddrinfo把哪个协议排在前面，程序就会优先连接哪个。还有一些经过特殊设计的程序，比如curl以及各种浏览器，则会有其他逻辑。比如会先检查本机的IPv6地址，如果是内网地址则会放弃使用IPv6，如果是公网地址，会同时解析IPv4和IPv6地址，然后优先连接IPv6，如果在一个较短的时间内(如1秒)还未连接成功，则会继续尝试连接IPv4，最后使用最早建立的那个连接。【本段内容摘自 Richard Yu 的评论，感谢】

目前的终端设备，不管是 PC 还是手机，大部分知名应用程序（如浏览器）和操作系统默认都开启了 IPv6 的支持，能同时运行 v4/v6 双栈网络。如果路由器开了 IPv6 DHCP，终端设备就能自动获取运营商提供的 IPv6 DNS 服务器的地址，这个 DNS 服务器除了传统的 IPv4 记录外，还有 IPv6 记录，而应用程序（getaddrinfo函数）通常将优先查到 IPv6 地址，使用 IPv6 地址建议TCP连接，数据自然走的是 IPv6 协议栈。

比如，我们访问知乎，因为知乎服务器开启了双栈支持，在 IPv6 DNS 上，域名 `www.zhihu.com` 同时指向了知乎的 IPv6 和 IPv4 的服务器地址，所以浏览器在解析时将同时获得两个地址，且通常优先使用 IPv6 地址建立连接，所以接下来的 Web 流量自然走的是 IPv6 协议栈。

这种 IPv6 优先的策略本身是无可厚非的，只是当前的互联网环境，多数互联网服务（网站）的 IPv4 网络会好于IPv6，少数互联网服务则可能会出现 IPv6 网络优于 IPv4 的情况。如果有这样一个 DNS 服务器，它可以由我们自己指定 IPv4 优先，或者 IPv6优先，甚至更加智能地，不管是几个 IPv4 还是 IPv6， 统统都要，给我选出一个最快的 IP 就行。

SmartDNS 就是这么一个神器，它是一个运行在本地的 DNS 服务器，能接受本地客户端的 DNS 查询请求，然后从多个上游 DNS 服务器获取 DNS 查询结果，并将访问速度最快的结果返回给客户端，以此提高网络访问速度。

SmartDNS 架构和运行原理如下 \[12\]：

1.  SmartDNS 接收本地网络设备的DNS 查询请求，如 PC、手机的查询请求；
2.  然后将查询请求发送到多个上游 DNS 服务器，可支持 UDP 标准端口或非标准端口查询，以及 TCP 查询；
3.  上游 DNS 服务器返回域名对应的服务器 IP 地址列表，SmartDNS 则会检测从本地网络访问速度最快的服务器 IP；
4.  最后将访问速度最快的服务器 IP 返回给本地客户端。

![](https://pic3.zhimg.com/v2-8ca83408f06469140a04cc3286b6f98e_b.jpg)

利用 SmartDNS，我们也可以在本地搭建自己的智能 DNS 服务器，来优化我们的网络。比如可以以插件的形式安装在 OpenWRT 路由器上，具体过程不在本文赘述。

## 总结

综上所述，IPv6 开启后网络出现种种不稳定的问题，很大可能是 PMTU 黑洞造成的，解决的办法是在拨号路由器上开启 MSS Clamping，在传输层即把数据分段到最合适的大小，避免中间路由器进行 IP 分片。

## 附录

本文内容参考了以下的文章：

1.  华为IP百科 [什么是MTU](https://link.zhihu.com/?target=https%3A//info.support.huawei.com/info-finder/encyclopedia/zh/MTU.html)[↩︎](https://link.zhihu.com/?target=http%3A//doc.envview.com/ipv6.html%23fnref1)
2.  小菜学编程 [IP分片](https://link.zhihu.com/?target=https%3A//fasionchan.com/network/ip/fragmentation/)[↩︎](https://link.zhihu.com/?target=http%3A//doc.envview.com/ipv6.html%23fnref2)
3.  小菜学编程 [IP分片](https://link.zhihu.com/?target=https%3A//fasionchan.com/network/ip/fragmentation/)[↩︎](https://link.zhihu.com/?target=http%3A//doc.envview.com/ipv6.html%23fnref3)
4.  华为IP百科 [什么是MTU](https://link.zhihu.com/?target=https%3A//info.support.huawei.com/info-finder/encyclopedia/zh/MTU.html)[↩︎](https://link.zhihu.com/?target=http%3A//doc.envview.com/ipv6.html%23fnref4)
5.  大西洋里的鱼 [MTU TCP-MSS详解](https://zhuanlan.zhihu.com/p/139537936)[↩︎](https://link.zhihu.com/?target=http%3A//doc.envview.com/ipv6.html%23fnref5)
6.  华为IP百科 [什么是MTU](https://link.zhihu.com/?target=https%3A//info.support.huawei.com/info-finder/encyclopedia/zh/MTU.html)[↩︎](https://link.zhihu.com/?target=http%3A//doc.envview.com/ipv6.html%23fnref6)
7.  华为IP百科 [什么是MTU](https://link.zhihu.com/?target=https%3A//info.support.huawei.com/info-finder/encyclopedia/zh/MTU.html)[↩︎](https://link.zhihu.com/?target=http%3A//doc.envview.com/ipv6.html%23fnref7)
8.  CISCO [PPPoE连接的以太网MTU和TCP MSS调整概念](https://link.zhihu.com/?target=https%3A//www.cisco.com/c/zh_cn/support/docs/ip/transmission-control-protocol-tcp/200932-Ethernet-MTU-and-TCP-MSS-Adjustment-Conc.html)[↩︎](https://link.zhihu.com/?target=http%3A//doc.envview.com/ipv6.html%23fnref8)
9.  大西洋里的鱼 [MTU TCP-MSS详解](https://zhuanlan.zhihu.com/p/139537936)[↩︎](https://link.zhihu.com/?target=http%3A//doc.envview.com/ipv6.html%23fnref9)
10.  ipspace [TCP MSS Clamping – What Is It and Why Do We Need It?](https://link.zhihu.com/?target=https%3A//blog.ipspace.net/2013/01/tcp-mss-clamping-what-is-it-and-why-do.html)[↩︎](https://link.zhihu.com/?target=http%3A//doc.envview.com/ipv6.html%23fnref10)
11.  raysonx [开启 IPv6 后网速变得很慢？可能是 PMTU 黑洞的问题](https://link.zhihu.com/?target=https%3A//www.v2ex.com/t/800024)[↩︎](https://link.zhihu.com/?target=http%3A//doc.envview.com/ipv6.html%23fnref11)
12.  SmartDNS [SmartDNS (pymumu.github.io)](https://link.zhihu.com/?target=https%3A//pymumu.github.io/smartdns/)[↩︎](https://link.zhihu.com/?target=http%3A//doc.envview.com/ipv6.html%23fnref12)