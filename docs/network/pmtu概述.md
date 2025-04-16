发表于 2017-12-19 更新于 2019-04-17 分类于 [c](http://sunyongfeng.com/categories/c/) 评论数： [0 Comments](http://sunyongfeng.com/201712/networks/path_mtu.html#comments)

Path MTU 简述。

## [](http://sunyongfeng.com/201712/networks/path_mtu#%E7%BB%93%E8%AE%BA "结论")结论

-   概念
    
    -   PMTU，Path MTU，以路由为单位，作为路由表的属性信息缓存于路由表。
    -   PMTU发现机制，若网络设备收到超MTU IP报文且该IP报文不允许分片，则返回一个ICMP type 3 code 4报文（`The datagram is too big. Packet fragmentation is required but the 'don't fragment' (DF) flag is on.`），将网络设备支持的MTU大小附在ICMP报文中，返回给报文源主机，由报文源主机调整该路径的PMTU。该机制利用IP头部`flags`中的`Don't fragment`位，为1时表示不允许分片。
-   影响。在GRE IP隧道叠加网中，报文将在IP头部后添加上24字节GRE IP头部。以默认IP MTU为1500字节为例，原先一个1514字节大小的报文（IP头部 + 数据刚好为IP MTU 1500字节）在公网上可以正常传输，若此时将路径切换到GRE IP隧道叠加网，则报文长度将变成1528字节（IP头部 + 数据 = 1524字节），将超过默认IP MTU。  
    详见 H3C 文章 [看招MTU!!!——高端路由器GRE组网中需要注意的问题](http://www.h3c.com/cn/d_201411/921527_30005_0.htm)。
    
    -   如果分片发生在旁挂设备，则将导致GRE IP报文被分片，无法在隧道终结处重组，因为第二个分片不带GRE头部。
    -   IP报文不允许分片
        -   对于TCP报文
            -   将通过PMTU发现机制，调整主机PMTU
            -   通过快速重传机制，迅速恢复
            -   主机调整TCP报文大小，以适应PMTU
        -   对于UDP报文
            -   将通过PMTU发现机制，调整主机PMTU
            -   **丢弃该报文**
            -   后续传输时，对超过PMTU的报文，在主机处主动进行分片。
            -   若有需要，超时重传、调整报文大小的机制由UDP的上层协议支持。
        -   对于其他IP报文（以ping报文为例）
            -   将通过PMTU发现机制，调整主机PMTU
            -   **丢弃该报文**
            -   后续传输时，在主机处主动分片（以Linux为例）
    -   IP报文允许分片
        -   如果业务开始前，主机已经调整PMTU，则分片在主机进行，业务可正常运行。
        -   **如果主机未调整PMTU，则分片在旁挂设备进行，将导致业务中断**。此问题将影响整个方案。
-   规避手段
    
    -   规避目标：将分片的行为转移至主机上，不允许旁挂设备上进行任何分片行为。
    -   方案：对所有超IP MTU送旁挂设备CPU的报文，皆返回ICMP type 3 code 4。需验证此规避对允许分片IP报文的影响。
    -   风险：对控制面和管理面的影响待评估。
-   分析
    
    -   Linux
        
        -   PMTU发现机制默认为`IP_PMTUDISC_WANT`，如果报文不超过PMTU，默认开启PMTU发现机制，如果报文超过PMTU，则主动在终端进行分片处理。（`will fragment a datagram if needed according to the path MTU, or will set the don’t-fragment flag otherwise.`）
    -   Windows
        
        -   TCP报文，默认不允许分片
        -   其他报文，默认允许分片
        -   对允许分片的报文，如果报文长度超过PMTU，则主动在终端处进行分片
    -   不能假定网络上的所有的TCP报文都不允许分片（如新浪网，默认TCP报文允许分片）
        

## [](http://sunyongfeng.com/201712/networks/path_mtu#%E5%AE%9E%E9%AA%8C%E7%BB%93%E6%9E%9C "实验结果")实验结果

| 系统 | 协议 | 默认是否加DF | 默认对超PMTU的处理 |
| --- | --- | --- | --- |
| Linux | TCP | 是 | 调整TCP段长度 |
| Linux | UDP | 是 | 不做处理，用户程序处理 |
| Linux | RTSP（UDP） | 是 | 丢掉ICMP packet too big的那几个包，后续分片 |
| Linux | TFTP（UDP） | 是 | 等不到ACK，timeout退出 |
| Linux | ping | 是 | 不重传报文，主机提示`From 3.3.3.3 icmp_seq=93 Frag needed and DF set (mtu = 0)`，后开始在主机对ping报文进行分片，分片后的报文DF=0；如果强制设置DF：`-M = do`，则提示`ping: local error: Message too long, mtu=552` |
| Linux | TCP(自己构造) | 否 | 默认在交换机中送CPU分片，如果此时有一个ICMP packet too big返回至主机（比如由ping触发），则会转在主机分片 |
| Windows | TCP | 是 | 调整TCP段长度 |
| Windows | UDP | 否 | 被路由器分片或被主机分片 |
| Windows | ping | 否 | 无处理，在交换机中分片，如果此时有ICMP packet too big（如TCP触发），则会主动在终端分片。如果强制设置DF：`-f`，则提示`Packet needs to be fragmented but DF set.` |

如上实验结果，得出以下结论：

1.  Linux下，TCP/UDP报文默认都置上DF位；
2.  Windows下，TCP报文默认置上DF位，UDP报文默认不置DF位；
3.  Linux下，UDP的对ICMP packet too big报文的处理取决于用户，Linux内核不进行处理
4.  不管Linux还是Windows下，如果要发出的UDP报文大于PMTU，则会主动在HOST端进行分片。
5.  PMTU以路由（SIP + DIP + TOS）为单位影响系统，UDP虽然没有主动调整数据报的大小，但是因UDP报文返回的ICMP packet too big报文会影响对应路由的PMTU。

## [](http://sunyongfeng.com/201712/networks/path_mtu#%E6%A0%87%E5%87%86 "标准")标准

-   [RFC 1191 Path MTU Discovery](http://tools.ietf.org/html/rfc1191)
-   [RFC 4821 Packetization Layer Path MTU Discovery](http://tools.ietf.org/html/rfc4821)

按RFC 1191的定义，PMTU发现机制为Packetization Protocol服务，TCP是这种可调节报文大小的协议，因此可直接使用；而UDP协议需要靠上层协议来实现报文大小调整。

RFC 1191 第6章“Host Implementation”讲述PMTU Discovery对终端的建议（仅仅是suggestion，不是specification）：

-   在哪个或哪些层次实现PMTU发现机制；
    -   由IP以上层次决定报文要发多大；
    -   Pakcetization Protocol必须能影响PMTU变化，含更新报文大小、控制DF位。（IP层不控制DF位）
-   PMTU信息缓存在哪；
    -   把PMTU做为路由表项的一个属性成员。
    -   对于UDP这种无连接的报文，若返回ICMP packet too big，需要其上层协议通过超时重传机制，重传被dropped的报文。
-   旧PMTU信息如何被老化；
-   PMTU如何上涨；

## [](http://sunyongfeng.com/201712/networks/path_mtu#Linux%E7%9A%84%E5%A4%84%E7%90%86 "Linux的处理")Linux的处理

Linux Kernel的实现参考：[man 7 ip](http://linux.die.net/man/7/ip) 中关于`IP_MTU_DISCOVER`的描述。

IP\_MTU\_DISCOVER (since Linux 2.2)  
Set or receive the Path MTU Discovery setting for a socket. **When enabled, Linux will perform Path MTU Discovery as defined in RFC 1191 on SOCK\_STREAM sockets. For non-SOCK\_STREAM sockets, IP\_PMTUDISC\_DO forces the don’t-fragment flag to be set on all outgoing packets. It is the user’s responsibility to packetize the data in MTU-sized chunks and to do the retransmits if necessary. The kernel will reject (with EMSGSIZE) datagrams that are bigger than the known path MTU. IP\_PMTUDISC\_WANT will fragment a datagram if needed according to the path MTU, or will set the don’t-fragment flag otherwise.**  
The system-wide default can be toggled between IP\_PMTUDISC\_WANT and IP\_PMTUDISC\_DONT by writing (respectively, zero and nonzero values) to the /proc/sys/net/ipv4/ip\_no\_pmtu\_disc file.

**When PMTU discovery is enabled, the kernel automatically keeps track of the path MTU per destination host.** When it is connected to a specific peer with connect(2), the currently known path MTU can be retrieved conveniently using the IP\_MTU socket option (e.g., after an EMSGSIZE error occurred). The path MTU may change over time. For connectionless sockets with many destinations, the new MTU for a given destination can also be accessed using the error queue (see IP\_RECVERR). A new error will be queued for every incoming MTU update.

While MTU discovery is in progress, initial packets from datagram sockets may be dropped. Applications using UDP should be aware of this and not take it into account for their packet retransmit strategy.

To bootstrap the path MTU discovery process on unconnected sockets, it is possible to start with a big datagram size (up to 64K-headers bytes long) and let it shrink by updates of the path MTU.

To get an initial estimate of the path MTU, connect a datagram socket to the destination address using connect(2) and retrieve the MTU by calling getsockopt(2) with the IP\_MTU option.

It is possible to implement RFC 4821 MTU probing with SOCK\_DGRAM or SOCK\_RAW sockets by setting a value of IP\_PMTUDISC\_PROBE (available since Linux 2.6.22). This is also particularly useful for diagnostic tools such as tracepath(8) that wish to deliberately send probe packets larger than the observed Path MTU.