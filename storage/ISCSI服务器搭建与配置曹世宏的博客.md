发表于 2018-10-23 | 分类于 [Linux](https://cshihong.github.io/categories/Linux/) | 阅读次数： 5299 | 字数： 4,474 | 阅读时长： 19

## [](https://cshihong.github.io/2018/10/23/ISCSI%E6%9C%8D%E5%8A%A1%E5%99%A8%E6%90%AD%E5%BB%BA%E4%B8%8E%E9%85%8D%E7%BD%AE/#ISCSI%E6%9C%8D%E5%8A%A1%E7%AE%80%E4%BB%8B "ISCSI服务简介")ISCSI服务简介

## [](https://cshihong.github.io/2018/10/23/ISCSI%E6%9C%8D%E5%8A%A1%E5%99%A8%E6%90%AD%E5%BB%BA%E4%B8%8E%E9%85%8D%E7%BD%AE/#ISCSI%E7%AE%80%E4%BB%8B%EF%BC%9A "ISCSI简介：")ISCSI简介：

iSCSI( Internet Small Computer System Interface 互联网小型计算机系统接口) 技术是一种新存储技术，该技术是将现有的SCSI接口与以太网技术相结合，使服务器可与使用IP网络的存储装置互相交换资料。

iscsi 结构基于客户/服务器模型，其主要功能是在TCP/IP网络上的主机系统（启动器initlator）和存储设备（目标 target） 之间进行大量的数据封装和可靠传输过程，此外，iscsi 提供了在IP网络封装SCSI命令，切运行在TCP上。

实际生产环境中，一般都是使用集群搭建服务器，如果两台或多台服务器都是使用独立磁盘，使用ISCSI 技术，实现远程磁盘的使用，集群的服务器都挂在同一个远程存储设备到本地实现数据读写，这样也就减少了一个同步数据的任务，大大减轻了服务器的资源消耗

作为服务器的系统通常需要存储设备的，而存储设备除了可以使用系统內间的磁盘之外，如果內间的磁盘容量不够大，而且没有额外的磁盘插槽（SATA 或IDE）可用时，常见的解决方案是增加NAS（网络附加存储服务器）或外接式存储设备高档一点的，可能会用到SAN（存储局域网络）。

## [](https://cshihong.github.io/2018/10/23/ISCSI%E6%9C%8D%E5%8A%A1%E5%99%A8%E6%90%AD%E5%BB%BA%E4%B8%8E%E9%85%8D%E7%BD%AE/#NAS%E4%B8%8ESAN%E7%AE%80%E4%BB%8B%EF%BC%9A "NAS与SAN简介：")NAS与SAN简介：

**NAS （network attached storage，网络附加存储服务器）**  
NAS是一部客制化好的主机，只要将NAS链接上网络，那么网络上面的其他主机就能够存取NSA上头的数据了，简单的说，NAS 就是一部file server，NAS 由于是接在网络上面，所以如果网络上有某个用户大量存取NAS上头的数据时，很容易造成网络停顿问题，此外BAS 也通常支持TCP/IP，并会提供NFS,SAMA,FTP等常见的通讯协议来提供客户端取得文件系统

**SAN （storage area networks，存储局域网络）**  
NAS 就是一部可以提供大量容量文件系统的主机，我们知道单个主机能够提供的插槽时有限的，所以不能无限制的安插磁盘在同一部实体主机上，因此便有了SAN  
SAN 视为一个外接式的存储设备，可以透过某些特殊的接口或信道来提供局域网络内的所有机器进行磁盘存取， SAN是提供磁盘给主机用，而不是像NAS 提供的是\[网络协议的文件系统（NFS SMB）\]，因此挂载SAN的主机会多出一个大磁盘，并可针对SAN提供的磁盘进行分割与格式化等动作，而NAS则不能，另外NAS可以透过网络使用SAN，

NAS和SAN的更多介绍可以参考：

**[NAS技术及应用：](https://cshihong.github.io/2018/04/12/NAS%E6%8A%80%E6%9C%AF%E5%8F%8A%E5%BA%94%E7%94%A8/)**

**[SAN技术及应用：](https://cshihong.github.io/2018/04/12/SAN%E6%8A%80%E6%9C%AF%E5%8F%8A%E5%BA%94%E7%94%A8/)**

## [](https://cshihong.github.io/2018/10/23/ISCSI%E6%9C%8D%E5%8A%A1%E5%99%A8%E6%90%AD%E5%BB%BA%E4%B8%8E%E9%85%8D%E7%BD%AE/#ISCSI%E5%8E%86%E5%8F%B2%EF%BC%9A "ISCSI历史：")ISCSI历史：

早期的企业使用的服务器若有大容量的磁盘的需求时，通常是透过SCSI来串接SCSI磁盘，因此服务器上必须要加装SCSI适配卡，而且这个SCSI是专属于该服务器的，后来这个外接式的SCSI设备被SAN的架构取代，SAN的一个缺点是要使用光纤信道，而光纤信道贵，很多中小型企业不能普及。

后期IP封包为基础的LAN技术普及，以太网速度加快，所以就有厂商将SAN的链接方式改为利用IP技术来处理，人后再透过一些标准指定，得到了ISCSI。  
ISCSI 主要是透过TCP/IP的技术，将存储设备端透过ISCSI target (ISCSI目标）功能，做成可以提供磁盘的服务器端，再透过ISCSI initator（ISCSI初始化用户）功能，做成能够挂载使用ISCSI target的客户端，如此便能透过ISCSI协议来进行磁盘的应用了。

ISCSI 这个架构主要将存储装置与使用的主机分别为两部分，分别是：

-   ISCSI target ：就是存储设备端，存放磁盘或RAID的设备，目前也能够将Linux主机仿真成ISCSI target了，目的在提供其他主机使用的磁盘。
    
-   ISCSI inITiator： 就是能够使用target的客户端，通常是服务器，只有装有iscsi initiator的相关功能后才能使用ISCSI target 提供的磁盘。
    

**服务器取得磁盘或者文件系统的方式**

1.  直接存取：在本机上的磁盘，就是直接存取设备
2.  透过存储局域网络（SAN），来自区网内的其他设备提供的磁盘。
3.  网络文件系统NAS（：来自NAS提供的文件系统）只能立即使用，不能进行格式化。

## [](https://cshihong.github.io/2018/10/23/ISCSI%E6%9C%8D%E5%8A%A1%E5%99%A8%E6%90%AD%E5%BB%BA%E4%B8%8E%E9%85%8D%E7%BD%AE/#Linux%E4%B8%8BISCSI%E6%9C%8D%E5%8A%A1%E6%90%AD%E5%BB%BA "Linux下ISCSI服务搭建")Linux下ISCSI服务搭建

## [](https://cshihong.github.io/2018/10/23/ISCSI%E6%9C%8D%E5%8A%A1%E5%99%A8%E6%90%AD%E5%BB%BA%E4%B8%8E%E9%85%8D%E7%BD%AE/#%E7%AE%80%E4%BB%8B%EF%BC%9A "简介：")简介：

iSCSI技术在工作形式上分为服务端（target）与客户端（initiator）。iSCSI服务端即用于存放硬盘存储资源的服务器，它作为前面创建的RAID磁盘阵列的存储端，能够为用户提供可用的存储资源。iSCSI客户端则是用户使用的软件，用于访问远程服务端的存储资源。

1.  iscsi server被称为target server，模拟scsi设备，后端存储设备可以使用文件/LVM/磁盘/RAID等不同类型的设备；启动设备（initiator）：发起I/O请求的设备，需要提供iscsi服务，比如PC机安装iscsi-initiator-utils软件实现，或者通过网卡自带的PXE启动。esp+ip+scsi
    
2.  iscsi再传输数据的时候考虑了安全性，可以通过IPSEC 对流量加密，并且iscsi提供CHAP认证机制以及ACL访问控制，但是在访问iscsi-target的时候需要IQN（iscsi完全名称，区分唯一的initiator和target设备），格式iqn.年月.域名后缀(反着写)：\[target服务器的名称或IP地址\]
    
3.  iscsi使用TCP端口3260提供服务
    

## [](https://cshihong.github.io/2018/10/23/ISCSI%E6%9C%8D%E5%8A%A1%E5%99%A8%E6%90%AD%E5%BB%BA%E4%B8%8E%E9%85%8D%E7%BD%AE/#ISCSI%E6%9C%8D%E5%8A%A1%E7%AB%AF%E9%85%8D%E7%BD%AE%EF%BC%9A "ISCSI服务端配置：")ISCSI服务端配置：

**第一步：安装服务端程序target**，**添加要一块磁盘分区。**

<table><tbody><tr><td><pre><span>1</span><br><span>2</span><br><span>3</span><br><span>4</span><br><span>5</span><br><span>6</span><br><span>7</span><br><span>8</span><br><span>9</span><br><span>10</span><br><span>11</span><br><span>12</span><br><span>13</span><br><span>14</span><br><span>15</span><br><span>16</span><br><span>17</span><br><span>18</span><br><span>19</span><br><span>20</span><br><span>21</span><br><span>22</span><br><span>23</span><br><span>24</span><br><span>25</span><br><span>26</span><br><span>27</span><br><span>28</span><br><span>29</span><br><span>30</span><br><span>31</span><br><span>32</span><br><span>33</span><br><span>34</span><br></pre></td><td><pre><span>[root@localhost ~]<span># yum -y install targetd targetcli</span></span><br><span>[root@localhost ~]<span># systemctl restart targetd</span></span><br><span>[root@localhost ~]<span># systemctl enable targetd </span></span><br><span>Created symlink from /etc/systemd/system/multi-user.target.wants/targetd.service to /usr/lib/systemd/system/targetd.service.</span><br><span></span><br><span>[root@localhost ~]<span># fdisk /dev/sdb</span></span><br><span>欢迎使用 fdisk (util-linux 2.23.2)。</span><br><span></span><br><span>更改将停留在内存中，直到您决定将更改写入磁盘。</span><br><span>使用写入命令前请三思。</span><br><span></span><br><span></span><br><span>命令(输入 m 获取帮助)：n</span><br><span>Partition <span>type</span>:</span><br><span>   p   primary (0 primary, 0 extended, 4 free)</span><br><span>   e   extended</span><br><span>Select (default p): </span><br><span>Using default response p</span><br><span>分区号 (1-4，默认 1)：</span><br><span>起始 扇区 (2048-20971519，默认为 2048)：</span><br><span>将使用默认值 2048</span><br><span>Last 扇区, +扇区 or +size{K,M,G} (2048-20971519，默认为 20971519)：+2G</span><br><span>分区 1 已设置为 Linux 类型，大小设为 2 GiB</span><br><span></span><br><span>命令(输入 m 获取帮助)：w</span><br><span>The partition table has been altered!</span><br><span></span><br><span>Calling ioctl() to re-read partition table.</span><br><span></span><br><span>WARNING: Re-reading the partition table failed with error 16: 设备或资源忙.</span><br><span>The kernel still uses the old table. The new table will be used at</span><br><span>the next reboot or after you run partprobe(8) or kpartx(8)</span><br><span>正在同步磁盘。</span><br><span>[root@localhost ~]<span># partprobe</span></span><br></pre></td></tr></tbody></table>

**第二步：配置iSCSI服务端共享资源**

targetcli是用于管理iSCSI服务端存储资源的专用配置命令，它能够提供类似于fdisk命令的交互式配置功能，将iSCSI共享资源的配置内容抽象成“目录”的形式，我们只需将各类配置信息填入到相应的“目录”中即可。这里的难点主要在于认识每个“参数目录”的作用。当把配置参数正确地填写到“目录”中后，iSCSI服务端也可以提供共享资源服务了。

在执行targetcli命令后就能看到交互式的配置界面了。在该界面中可以使用很多Linux命令，比如利用ls查看目录参数的结构，使用cd切换到不同的目录中。/backstores/block是iSCSI服务端配置共享设备的位置。我们需要把刚刚创建的磁盘分区文件加入到配置共享设备的“资源池”中，并将该文件重新命名为block1，这样用户就不会知道是由服务器中的哪块硬盘来提供共享存储资源，而只会看到一个名为block1的存储设备。

<table><tbody><tr><td><pre><span>1</span><br><span>2</span><br><span>3</span><br><span>4</span><br><span>5</span><br><span>6</span><br><span>7</span><br><span>8</span><br><span>9</span><br><span>10</span><br><span>11</span><br><span>12</span><br><span>13</span><br><span>14</span><br><span>15</span><br><span>16</span><br><span>17</span><br><span>18</span><br></pre></td><td><pre><span>[root@localhost ~]<span># targetcli </span></span><br><span>targetcli shell version 2.1.fb41</span><br><span>Copyright 2011-2013 by Datera, Inc and others.</span><br><span>For <span>help</span> on commands, <span>type</span> <span>'help'</span>.</span><br><span></span><br><span>/&gt; </span><br><span>/&gt; ls</span><br><span>o- / ...................................................... [...]</span><br><span>  o- backstores ........................................... [...]</span><br><span>  | o- block ............................... [Storage Objects: 0]</span><br><span>  | o- fileio .............................. [Storage Objects: 0]</span><br><span>  | o- pscsi ............................... [Storage Objects: 0]</span><br><span>  | o- ramdisk ............................. [Storage Objects: 0]</span><br><span>  o- iscsi ......................................... [Targets: 0]</span><br><span>  o- loopback ...................................... [Targets: 0]</span><br><span>/&gt; /&gt; <span>cd</span> backstores/block    <span>#创建一个名为block1的存储块</span></span><br><span>/backstores/block&gt; create name=block1 dev=/dev/sdb1 </span><br><span>Created block storage object block1 using /dev/sdb1.</span><br></pre></td></tr></tbody></table>

**第三步：创建iSCSI target名称及配置共享资源。**

iSCSI target名称是由系统自动生成的，这是一串用于描述共享资源的唯一字符串。稍后用户在扫描iSCSI服务端时即可看到这个字符串，因此我们不需要记住它。系统在生成这个target名称后，还会在/iscsi参数目录中创建一个与其字符串同名的新“目录”用来存放共享资源。我们需要把前面加入到iSCSI共享资源池中的硬盘设备添加到这个新目录中，这样用户在登录iSCSI服务端后，即可默认使用这硬盘设备提供的共享存储资源了。

<table><tbody><tr><td><pre><span>1</span><br><span>2</span><br><span>3</span><br><span>4</span><br><span>5</span><br><span>6</span><br><span>7</span><br><span>8</span><br><span>9</span><br><span>10</span><br><span>11</span><br><span>12</span><br><span>13</span><br><span>14</span><br><span>15</span><br><span>16</span><br><span>17</span><br><span>18</span><br><span>19</span><br></pre></td><td><pre><span>/&gt; <span>cd</span> iscsi </span><br><span>/iscsi&gt; ls</span><br><span>o- iscsi ........................................... [Targets: 0]</span><br><span>/iscsi&gt; create wwn=iqn.2018-10.com.example:server</span><br><span>Created target iqn.2018-10.com.example:server.</span><br><span>Created TPG 1.</span><br><span>Global pref auto_add_default_portal=<span>true</span></span><br><span>Created default portal listening on all IPs (0.0.0.0), port 3260.</span><br><span>/iscsi&gt; <span>cd</span> iqn.2018-10.com.example:server/</span><br><span>/iscsi/iqn.20...xample:server&gt; ls</span><br><span>o- iqn.2018-10.com.example:server ..................... [TPGs: 1]</span><br><span>  o- tpg1 ................................ [no-gen-acls, no-auth]</span><br><span>    o- acls ........................................... [ACLs: 0]</span><br><span>    o- luns ........................................... [LUNs: 0]</span><br><span>    o- portals ..................................... [Portals: 1]</span><br><span>      o- 0.0.0.0:3260 ...................................... [OK]</span><br><span>&gt;/iscsi/iqn.20...ver/tpg1/luns&gt; create /backstores/block/block1 </span><br><span>Created LUN 0.</span><br><span><span>#创建需要共享的设备</span></span><br></pre></td></tr></tbody></table>

**第四步：设置访问控制列表（ACL）。**

iSCSI协议是通过客户端名称进行验证的，也就是说，用户在访问存储共享资源时不需要输入密码，只要iSCSI客户端的名称与服务端中设置的访问控制列表中某一名称条目一致即可，因此需要在iSCSI服务端的配置文件中写入一串能够验证用户信息的名称。acls参数目录用于存放能够访问iSCSI服务端共享存储资源的客户端名称。推荐在刚刚系统生成的iSCSI target后面追加上类似于:client的参数，这样既能保证客户端的名称具有唯一性，又非常便于管理和阅读。

<table><tbody><tr><td><pre><span>1</span><br><span>2</span><br><span>3</span><br><span>4</span><br><span>5</span><br></pre></td><td><pre><span>/iscsi/iqn.20...ver/tpg1/luns&gt; <span>cd</span> ..</span><br><span>/iscsi/iqn.20...e:server/tpg1&gt; <span>cd</span> acls </span><br><span>/iscsi/iqn.20...ver/tpg1/acls&gt; create iqn.2018-10.com.example:client</span><br><span>Created Node ACL <span>for</span> iqn.2018-10.com.example:client</span><br><span>Created mapped LUN 0.</span><br></pre></td></tr></tbody></table>

**第五步：设置iSCSI服务端的监听IP地址和端口号。**

位于生产环境中的服务器上可能有多块网卡，那么到底是由哪个网卡或IP地址对外提供共享存储资源呢？这就需要我们在配置文件中手动定义iSCSI服务端的信息，即在portals参数目录中写上服务器的IP地址。接下来将由系统自动开启服务器192.168.245.128的3260端口将向外提供iSCSI共享存储资源服务：

<table><tbody><tr><td><pre><span>1</span><br><span>2</span><br><span>3</span><br><span>4</span><br><span>5</span><br></pre></td><td><pre><span>/iscsi/iqn.20...d80/tpg1/acls&gt; <span>cd</span> ..</span><br><span>/iscsi/iqn.20...c356ad80/tpg1&gt; <span>cd</span> portals </span><br><span>/iscsi/iqn.20.../tpg1/portals&gt; create 192.168.245.128 ip_port=3260</span><br><span>Using default IP port 3260</span><br><span>Created network portal 192.168.245.128:3260.</span><br></pre></td></tr></tbody></table>

**第六步：配置妥当后检查配置信息，重启iSCSI服务端程序并配置防火墙策略。**

在参数文件配置妥当后，可以浏览刚刚配置的信息，确保与下面的信息基本一致。在确认信息无误后输入exit命令来退出配置。注意，千万不要习惯性地按Ctrl + C组合键结束进程，这样不会保存配置文件，我们的工作也就白费了。最后重启iSCSI服务端程序，再设置firewalld防火墙策略，使其放行3260/tcp端口号的流量。

![target](https://cshihong.github.io/2018/10/23/ISCSI%E6%9C%8D%E5%8A%A1%E5%99%A8%E6%90%AD%E5%BB%BA%E4%B8%8E%E9%85%8D%E7%BD%AE/target.png)

图：target服务端配置

<table><tbody><tr><td><pre><span>1</span><br><span>2</span><br><span>3</span><br><span>4</span><br><span>5</span><br></pre></td><td><pre><span>[root@localhost ~]<span># systemctl restart targetd</span></span><br><span>[root@localhost ~]<span># firewall-cmd --permanent --add-port=3260/tcp</span></span><br><span>success</span><br><span>[root@localhost ~]<span># firewall-cmd --reload</span></span><br><span>success</span><br></pre></td></tr></tbody></table>

## [](https://cshihong.github.io/2018/10/23/ISCSI%E6%9C%8D%E5%8A%A1%E5%99%A8%E6%90%AD%E5%BB%BA%E4%B8%8E%E9%85%8D%E7%BD%AE/#%E9%85%8D%E7%BD%AELinux%E5%AE%A2%E6%88%B7%E7%AB%AF%EF%BC%9A "配置Linux客户端：")配置Linux客户端：

在RHEL 7系统中，已经默认安装了iSCSI客户端服务程序initiator。如果您的系统没有安装的话，可以使用Yum软件仓库手动安装。

<table><tbody><tr><td><pre><span>1</span><br></pre></td><td><pre><span>[root@localhost ~]<span># yum -y install iscsi-initiator-utils.i686</span></span><br></pre></td></tr></tbody></table>

iSCSI协议是通过客户端的名称来进行验证，而该名称也是iSCSI客户端的唯一标识，而且必须与服务端配置文件中访问控制列表中的信息一致，否则客户端在尝试访问存储共享设备时，系统会弹出验证失败的保存信息。

下面我们编辑iSCSI客户端中的initiator名称文件，把服务端的访问控制列表名称填写进来，然后重启客户端iscsid服务程序并将其加入到开机启动项中：

<table><tbody><tr><td><pre><span>1</span><br><span>2</span><br><span>3</span><br><span>4</span><br><span>5</span><br><span>6</span><br></pre></td><td><pre><span>[root@localhost ~]<span># vim /etc/iscsi/initiatorname.iscsi </span></span><br><span>InitiatorName=iqn.2018-10.com.example:client</span><br><span>[root@localhost ~]<span># systemctl restart iscsid</span></span><br><span>Warning: iscsid.service changed on disk. Run <span>'systemctl daemon-reload'</span> to reload units.</span><br><span>[root@localhost ~]<span># systemctl enable iscsid</span></span><br><span>Created symlink from /etc/systemd/system/multi-user.target.wants/iscsid.service to /usr/lib/systemd/system/iscsid.service.</span><br></pre></td></tr></tbody></table>

iscsiadm是用于管理、查询、插入、更新或删除iSCSI数据库配置文件的命令行工具，用户需要先使用这个工具扫描发现远程iSCSI服务端，然后查看找到的服务端上有哪些可用的共享存储资源。其中，-m discovery参数的目的是扫描并发现可用的存储资源，-t st参数为执行扫描操作的类型，-p 192.168.245.128参数为iSCSI服务端的IP地址.可通过 `man iscsiadm | grep \\-mode` 来查看帮助。

<table><tbody><tr><td><pre><span>1</span><br><span>2</span><br><span>3</span><br><span>4</span><br><span>5</span><br><span>6</span><br><span>7</span><br><span>8</span><br><span>9</span><br><span>10</span><br><span>11</span><br><span>12</span><br><span>13</span><br><span>14</span><br></pre></td><td><pre><span>[root@localhost ~]<span># man iscsiadm | grep \\-mode</span></span><br><span>   -m, --mode op</span><br><span>            iscsiadm --mode discoverydb --<span>type</span> sendtargets --portal 192.168.1.10 --discover</span><br><span>            iscsiadm --mode node --targetname iqn.2001-05.com.doe:<span>test</span> --portal 192.168.1.1:3260 --login</span><br><span>            iscsiadm --mode node --targetname iqn.2001-05.com.doe:<span>test</span> --portal 192.168.1.1:3260 --<span>logout</span></span><br><span>            iscsiadm --mode node</span><br><span>            iscsiadm --mode node --targetname iqn.2001-05.com.doe:<span>test</span> --portal 192.168.1.1:3260</span><br><span>[root@localhost ~]<span># iscsiadm --mode discoverydb --type sendtargets --portal 192.168.245.128 --discover</span></span><br><span><span>#通过该命令可发现指定IP地址的iSCSI服务</span></span><br><span>192.168.245.128:3260,1 iqn.2018-10.com.example:server   </span><br><span>[root@localhost ~]<span>#  iscsiadm --mode node --targetname iqn.2018-10.com.example:server --portal 192.168.245.128:3260 --login        </span></span><br><span><span>#使用该命令进行登录</span></span><br><span>Logging <span>in</span> to [iface: default, target: iqn.2018-10.com.example:server, portal: 192.168.245.128,3260] (multiple)</span><br><span>Login to [iface: default, target: iqn.2018-10.com.example:server, portal: 192.168.245.128,3260] successful.</span><br></pre></td></tr></tbody></table>

登录成功后，会发现在该客户端下多出一个/dev/sdb的设备文件。通过格式化分区挂载即可使用该硬盘。

<table><tbody><tr><td><pre><span>1</span><br><span>2</span><br><span>3</span><br><span>4</span><br><span>5</span><br><span>6</span><br><span>7</span><br><span>8</span><br><span>9</span><br><span>10</span><br><span>11</span><br><span>12</span><br><span>13</span><br><span>14</span><br><span>15</span><br><span>16</span><br><span>17</span><br><span>18</span><br><span>19</span><br><span>20</span><br><span>21</span><br><span>22</span><br><span>23</span><br><span>24</span><br><span>25</span><br><span>26</span><br><span>27</span><br><span>28</span><br><span>29</span><br><span>30</span><br><span>31</span><br><span>32</span><br><span>33</span><br><span>34</span><br><span>35</span><br><span>36</span><br><span>37</span><br><span>38</span><br><span>39</span><br><span>40</span><br></pre></td><td><pre><span>[root@localhost ~]<span># file /dev/sdb</span></span><br><span>/dev/sdb: block special</span><br><span>[root@localhost ~]<span># mkfs.ext4 /dev/sdb</span></span><br><span>mke2fs 1.42.9 (28-Dec-2013)</span><br><span>/dev/sdb is entire device, not just one partition!</span><br><span>Proceed anyway? (y,n) y</span><br><span>Filesystem label=</span><br><span>OS <span>type</span>: Linux</span><br><span>Block size=4096 (<span>log</span>=2)</span><br><span>Fragment size=4096 (<span>log</span>=2)</span><br><span>Stride=0 blocks, Stripe width=1024 blocks</span><br><span>196608 inodes, 786432 blocks</span><br><span>39321 blocks (5.00%) reserved <span>for</span> the super user</span><br><span>First data block=0</span><br><span>Maximum filesystem blocks=805306368</span><br><span>24 block groups</span><br><span>32768 blocks per group, 32768 fragments per group</span><br><span>8192 inodes per group</span><br><span>Superblock backups stored on blocks: </span><br><span>        32768, 98304, 163840, 229376, 294912</span><br><span></span><br><span>Allocating group tables: <span>done</span>                            </span><br><span>Writing inode tables: <span>done</span>                            </span><br><span>Creating journal (16384 blocks): <span>done</span></span><br><span>Writing superblocks and filesystem accounting information: <span>done</span> </span><br><span></span><br><span>[root@localhost ~]<span># mkdir /mnt/iscsi</span></span><br><span>[root@localhost ~]<span># mount /dev/sdb /mnt/iscsi/</span></span><br><span>[root@localhost ~]<span># df -Th</span></span><br><span>Filesystem            Type      Size  Used Avail Use% Mounted on</span><br><span>/dev/mapper/rhel-root xfs        17G  3.2G   14G  19% /</span><br><span>devtmpfs              devtmpfs  1.4G     0  1.4G   0% /dev</span><br><span>tmpfs                 tmpfs     1.4G   88K  1.4G   1% /dev/shm</span><br><span>tmpfs                 tmpfs     1.4G  9.1M  1.4G   1% /run</span><br><span>tmpfs                 tmpfs     1.4G     0  1.4G   0% /sys/fs/cgroup</span><br><span>/dev/sr0              iso9660   3.6G  3.6G     0 100% /mnt/cdrom</span><br><span>/dev/sda1             xfs      1014M  173M  842M  18% /boot</span><br><span>tmpfs                 tmpfs     280M   12K  280M   1% /run/user/0</span><br><span>/dev/sdb              ext4      2.9G  9.0M  2.8G   1% /mnt/iscsi</span><br><span>[root@localhost ~]<span>#</span></span><br></pre></td></tr></tbody></table>

> 注意：
> 
> 由于udev服务是按照系统识别硬盘设备的顺序来命名硬盘设备的，当客户端主机同时使用多个远程存储资源时，如果下一次识别远程设备的顺序发生了变化，则客户端挂载目录中的文件也将随之混乱。为了防止发生这样的问题，我们应该在/etc/fstab配置文件中使用设备的UUID唯一标识符进行挂载，这样，不论远程设备资源的识别顺序再怎么变化，系统也能正确找到设备所对应的目录。
> 
> blkid命令用于查看设备的名称、文件系统及UUID
> 
> **由于/dev/sdb是一块网络存储设备，而iSCSI协议是基于TCP/IP网络传输数据的，因此必须在/etc/fstab配置文件中添加上\_netdev参数，表示当系统联网后再进行挂载操作，以免系统开机时间过长或开机失败：**

当不在需要使用该硬盘时，可通过iscsiadm命令-u卸载：

<table><tbody><tr><td><pre><span>1</span><br><span>2</span><br><span>3</span><br><span>4</span><br></pre></td><td><pre><span>[root@localhost ~]<span># iscsiadm -m node -T iqn.2018-10.com.example:server -u</span></span><br><span>Logging out of session [sid: 1, target: iqn.2018-10.com.example:server, portal: 192.168.245.128,3260]</span><br><span>Logout of [sid: 1, target: iqn.2018-10.com.example:server, portal: 192.168.245.128,3260] successful.</span><br><span>[root@localhost ~]<span>#</span></span><br></pre></td></tr></tbody></table>

## [](https://cshihong.github.io/2018/10/23/ISCSI%E6%9C%8D%E5%8A%A1%E5%99%A8%E6%90%AD%E5%BB%BA%E4%B8%8E%E9%85%8D%E7%BD%AE/#%E9%85%8D%E7%BD%AEWindows%E5%AE%A2%E6%88%B7%E7%AB%AF%E8%BF%9E%E6%8E%A5iSCSI%E8%AE%BE%E5%A4%87%EF%BC%9A "配置Windows客户端连接iSCSI设备：")配置Windows客户端连接iSCSI设备：

第一步：运行iSCSI发起程序。上

控制面板–>系统和安全–>管理工具–>iSCSI发起程序。

![win](https://cshihong.github.io/2018/10/23/ISCSI%E6%9C%8D%E5%8A%A1%E5%99%A8%E6%90%AD%E5%BB%BA%E4%B8%8E%E9%85%8D%E7%BD%AE/win.png)

第二步：更改客户端iqn属性：

![属性](https://cshihong.github.io/2018/10/23/ISCSI%E6%9C%8D%E5%8A%A1%E5%99%A8%E6%90%AD%E5%BB%BA%E4%B8%8E%E9%85%8D%E7%BD%AE/%E5%B1%9E%E6%80%A7.png)

第三步：点击连接，就会在本次磁盘新加一款硬盘。

![连接](https://cshihong.github.io/2018/10/23/ISCSI%E6%9C%8D%E5%8A%A1%E5%99%A8%E6%90%AD%E5%BB%BA%E4%B8%8E%E9%85%8D%E7%BD%AE/%E8%BF%9E%E6%8E%A5.png)

第四步：通过格式化新建卷就可使用该硬盘。

![存储](https://cshihong.github.io/2018/10/23/ISCSI%E6%9C%8D%E5%8A%A1%E5%99%A8%E6%90%AD%E5%BB%BA%E4%B8%8E%E9%85%8D%E7%BD%AE/%E5%AD%98%E5%82%A8.png)