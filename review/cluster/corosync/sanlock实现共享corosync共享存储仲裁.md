# 审校：sanlock实现共享corosync共享存储仲裁

- 原文：`docs/cluster/corosync/sanlock实现共享corosync共享存储仲裁.md`
- 范围：全文
- 目标读者：做数据库高可用集群选型的工程师（知道 corosync、qdevice、
  fence 这些词，但没读过 sanlock 源码）
- 一句话定位：一份「用 sanlock 给 corosync 做共享存储仲裁」的可行性评估——
  动机、sanlock 原理、编程步骤、移植代价
- 核心判断：**方案的核心收益被上游文档的边界条件削掉了一半**——
  sanlock 只让「普通应用进程 hang 住」免于整机复位，**sanlock 自己 hang 住
  仍然是 watchdog 复位主机**；而 sanlock 的 fence 路径同样依赖被 fence 节点
  自己被 watchdog 复位，所以「不依赖 fence 重启机器」这个目标在走 fence 时
  并不成立。另外「hosts_lease / resource_lease 两个文件」的存储模型与上游
  对不上，而文章的思路恰好建立在这个模型上
- 审校状态：建议中

## 优先修改

1. 位置：L35-L37（存储模型）
   - 问题：**「2 个文件」这个模型与 sanlock 上游对不上**，而文章的方案核心
     恰好建立在它上面。上游是**一块设备上的若干区域**，不是两个文件：
     - **lockspace 区**（offset 0）：2000 个 delta lease，占 1MB
       （上游：「A lockspace is a series of 2000 delta leases on disk, and
       requires 1MB of storage」）；
     - **resource index（rindex，可选）**：`rindex_offset` 必须是
       `area_size` 的倍数，rindex_header 占一个 sector，后面是
       `max_resources` 个 64 字节的 `rindex_entry`；
     - **resource lease 区**：`resource_leases_start = rindex_offset +
       2 * area_size`，每个 resource lease 占一个 `area_size`
       （上游 `src/rindex_disk.h` 的布局注释）。
     而且 **`hosts_lease`、`resource_lease` 这两个名字在上游根本不存在**——
     把上游源码整棵树取下来全量搜索 `hosts_lease|resource_lease|host_lease`，
     **唯一命中是 `src/rindex_disk.h` 注释里的一个符号 `resource_leases_start`**，
     没有任何地方把它当成文件名。
     这不是小节问题：L15 的第三步「读取所有 corosync 节点的 ring id，
     并根据 ring id 来区分网络分区」要求**原子地读出每个节点的身份**，
     而在 sanlock 模型里，**host 身份记录在 delta lease（lockspace 区）**，
     **资源锁在 paxos lease（resource 区）**——这是两套不同的算法、
     两类不同的租约。文章把它们当成一个可以一起读的文件，读不到。
   - 建议：按上游模型重写这一节，讲清三件事——
     (1) lockspace（2000 个 delta lease，每个 host 一个，用 host_id 定位）
     与 resource（paxos lease，名字 + offset + 对齐）**是两回事**；
     (2) 每个节点的 ring id 应当落在**自己那个 host_id 对应的 delta lease**
     里，而不是「一个 hosts 文件」；
     (3) 读 ring id 时要用 `sanlock direct dump` / `sanlock client host_status`
     这类现成接口，而不是自己解析磁盘布局。
   - 原因：涉及事实与实现，必须可回溯；存储模型错了，后面「怎么读 ring id」
     这步就无从谈起。README 的「机制解释」。

2. 位置：L21（挂死处理）
   - 问题：**「sanlock提供了租约过期kill进程的方式」与上游机制不符，
     而且掩盖了这个方案最关键的一条边界**。上游 README「Expiration」写的是
     **三种**停止本地进程的方法，按顺序升级：
     1. **Graceful shutdown**——执行应用事先指定的退出程序；没指定就发
        **SIGTERM**；
     2. **Forced shutdown**——发 **SIGKILL**；
     3. **Host reset**——触发本机 **watchdog** 强制复位；sanlock 会精确计时，
        让 watchdog 在别的节点可能接管租约**之前**触发。
     所以「租约过期 kill 进程」只是前两步，**兜底仍然是复位整机**。
     更要紧的是上游对「sanlock 自己 hang 住」有明确答案：
     「If the **sanlock daemon crashes or hangs**, it will not renew the expiry
     time of the per-lockspace connections it had to the wdmd daemon. This
     will lead to the expiration of the local watchdog device, and **the host
     will be reset**.」
     原文 L21 自己把「又会出现sanlock进程hang住的情况」当成一个**没解决的
     问题**列出来，上游其实回答了：**结果是机器被 watchdog 复位**。
     → 也就是说，sanlock 消除的是「**普通应用** hang → 重启机器」，
     **没有消除「sanlock 自身 hang → 重启机器」**。这个收益边界必须写清楚，
     否则 L60「能满足我们的需求」就站不住。
     另外上游还写明（这条原文也没写）：
     「If a process holding resource leases fails or exits without releasing
     its leases, sanlock will release the leases for it automatically
     (**unless persistent resource leases were used**).」——
     这正好回答了 L7 说的「进程非正常退出」，但也把「persistent lease」
     这个选择摆到了台面上（见第 9 条）。
   - 建议：把这一节改成「sanlock 能解决什么、不能解决什么」的对照：
     - 能：应用进程 hang/崩溃 → 优雅退出 / SIGKILL，**不复位整机**；
     - 不能：sanlock 守护进程 hang → **watchdog 复位整机**；
     - 前提：必须接 watchdog（上游用 `wdmd(8)` 复用 /dev/watchdog），
       且共享存储的 sanlock io 要能及时完成。
   - 原因：涉及技术结论与工程边界，必须可回溯。README 的「工程取舍」
     「踩坑与校验」。

3. 位置：L7（现有仲裁能力）
   - 问题：**上游的 corosync-qdevice 只有 net 一个模型**，
     「qdisk 共享存储仲裁」不是上游能力。
     - corosync **v2.4.6** 的 `qdevices/Makefile.am` 只列
       `qdevice-model-net.c`（没有 disk / heuristic），
       `man/corosync-qdevice.8` 写「Currently only **net** is supported」；
     - corosync-qdevice 上游 **master** 同样只有 `qdevice-model-net.c`，
       man page 同一句话。
     → 现场的 qdisk 只能来自厂商补丁或自研。这直接影响结论第 3 条
     （L62「现有qdisk方式基本可用，先以现有qdisk实现功能」）——
     那是在依赖一个**上游已不维护**的能力。上游 corosync-qdevice 最新发布是
     **3.0.5（2026-11-12）**，磁盘模型连 2.4.x 里都没有了。
   - 建议：正文写清 qdisk 的来源（厂商补丁 / 自研 / 旧版本 backport）、
     维护状态与已知问题；结论第 3 条相应加上「qdisk 的维护风险」这一条。
     顺带说明上游现在只有 net 模型，对读者理解「为什么上游不提供存储仲裁」
     也有价值——这正是 sanlock 方案存在的意义。
   - 原因：涉及版本与事实，必须可回溯；结论的可执行性依赖它。

4. 位置：L34（主机编号范围）
   - 问题：**「编号范围为1到2000」漏了决定性的前提**。上游 README
     「Storage」段给出的组合是：
     | sector_size | align_size | max_hosts |
     | --- | --- | --- |
     | 512 | 1M | 2000 |
     | 4096 | 1M | **250** |
     | 4096 | 2M | 500 |
     | 4096 | 4M | 1000 |
     | 4096 | 8M | 2000 |
     并且「The host_id of hosts using the lockspace can be **no larger than the
     max_hosts value** for the lockspace.」
     也就是说 **4K 扇区的共享存储用 1M align 时最多只能放 250 个 host**
     （云盘、LVM 很常见是 4K 扇区）。原文的「1 到 2000」只在
     512 扇区 + 1M align 或 4096 扇区 + 8M align 时成立。
   - 建议：把编号范围写成「1 到 max_hosts，max_hosts 由扇区大小与对齐大小
     决定（4K 扇区 + 1M 对齐时只有 250）」，并在方案里写明现场共享存储的
     扇区大小与打算用的 align size。
   - 原因：涉及数字与配置前提，必须可回溯；写错了会直接撞上限。

5. 位置：L5（共享存储作为仲裁）
   - 问题：**漏了 sanlock 对共享存储的两条硬性限制**，而这两条恰恰打在
     「存储仲裁」的前提上：
     - 「Using sanlock on shared block devices that **do host based mirroring
       or replication** is not likely to work correctly.」
     - 「When using sanlock on shared files, **all sanlock io should go to one
       file server**.」
     存储仲裁要成立，前提是「分区时共享存储仍然可用且状态一致」。
     如果共享存储本身在分区场景下被隔离、或者做的是主机级镜像复制
     （两边各一份），仲裁者看到的状态就不可信——它会在两个分区里都看到
     「另一半的 ring id 是旧的」，于是两边都自认多数派。
     原文完全没讨论这个张力。
   - 建议：补一段「共享存储本身在分区场景下的行为」——存储仲裁要求存储是
     **单写者、共享可见、不会脑裂**的那一类（典型是同一台存储控制器后面的
     共享 LUN，两节点挂同一个 VG/LV），并说明它与「主机级镜像存储」
     不兼容。
   - 原因：README 的「问题边界」与「工程取舍」——这是方案的成立前提，
     不是细节。

6. 位置：L11 与 L31、L55
   - 问题：**三处对 sanlock 的概括互相打架**。
     - L11「sanlock是基于disk-paxos（共享存储的一种一致性协议）实现的
       分布式锁」——不准确。上游是**两套**租约算法：
       **host 用 delta lease**（上游引用：Chockler & Malkhi,
       《Light-Weight Leases for Storage-Centric Coordination》），
       **resource 用 paxos lease**（上游引用：Gafni & Lamport,
       《Disk Paxos》）。Disk Paxos 只是其中之一。
     - L31「Sanlock使用的Disk Paxos算法和Delta Lease算法理解起来比较困难，
       但对于使用sanlock而言，只需要记住下面几个点即可，**无需对这两个算法
       进行深入的研究**」——
     - L55「若剥离sanlock中disk-paxos的代码直接移植到corosync-qdevice中，
       **需要详细分析sanlock的实现原理和机制**（耗时较长）」——
       L31 与 L55 是**方向相反**的判断，读者不知道该按哪个来。
     另外 L11 的「共享存储的一种一致性协议」把 Disk Paxos 说成一致性协议，
     容易让人以为它解决的是「多副本一致」，其实它解决的是「跨机器的互斥」。
   - 建议：统一口径——一句话说清「sanlock 用两套租约分别解决『host 身份唯一』
     和『资源互斥』，对外只暴露 lockspace 和 resource 两个概念」，
     然后删掉「无需深入研究」或删掉「需要详细分析」其中一句（按真正的
     结论留）。
   - 原因：README 的「术语一致」「保留人的声音」；检查器 AIF-03 命中 L25。

7. 位置：L56（fence）
   - 问题：**「需进一步分析」在这里不是一个可以推迟的问题，而是决定性约束**。
     上游 `fence_sanlock(8)` 写得很清楚：fence_sanlock 是**用 watchdog 和
     sanlock 租约去 fence 别人**的 agent，需要 fence_sanlockd + sanlock + wdmd
     三个守护进程协同；而且
     「When fence_sanlock fences a node, it tries to acquire that node's
     resource lease. **sanlock will not grant the lease until the owner
     (the node being fenced) has been reset by its watchdog device.** The time
     it takes to acquire the lease is **140 seconds** from the victim's last
     lockspace renewal timestamp on the shared storage.」
     → 走 sanlock 的 fence 路径，**被 fence 的节点仍然要靠 watchdog 复位
     （也就是重启机器）**，而且要等 140 秒。这与文章开头 L9 的目标
     「不依赖 fence 重启机器」**直接冲突**。
     也正因如此，L7 抱怨 qdisk「严重依赖于 fence 重启机器」时，
     sanlock 的 fence 机制本质上是同一类（都靠 watchdog 复位）；
     差别只在**主路径**（recovery mode → SIGTERM/SIGKILL）不需要复位。
   - 建议：直接给结论——「sanlock 的主路径不依赖复位整机；fence 路径仍然
     依赖 watchdog 复位，且需要约 140 秒。因此本方案的边界是：
     **仲裁进程之外的应用挂死可以不重启机器，仲裁进程本身挂死仍会重启机器**」。
     把这条写进结论，比留在「适配问题」里更有用。
   - 原因：涉及工程取舍与适用边界；README 的「工程取舍」。

8. 位置：L51-L55、L58-L62（体裁与定位）
   - 问题：**这两节是内部立项材料，不是对外文章**。「sanlock移植到
     corosync-qdevice能满足我们的需求」「其移植方式需要进一步讨论，
     但移植需要较多时间，短期内暂时无法实现」「先以现有qdisk实现功能，
     同时同步进行sanlock移植工作」——这是决策记录与排期。
     读者读完不知道文章替自己解决什么难题。README 的「检查定位」要求
     开头讲清「文章替读者解决什么难题、为什么值得现在读」。
   - 建议：两条路，请站长定：
     - 改成一篇**技术评估**——标题与定位改成「共享存储仲裁怎么做：
       sanlock 的能力边界与移植代价」，保留机制与代价，删掉内部排期，
       结论改成「什么情况下 sanlock 方案值得做」；
     - 或者整体移入内部文档（它现在更像内部选型备忘）。
   - 原因：README 的「按读者的阅读路径组织」；这条需要站长拍板，
     本轮不擅自处理。

9. 位置：L43-L49「## sanlock编程」
   - 问题：**三步都缺关键参数，而且漏了一个对仲裁场景致命的选择**。
     - L47「为主机分配一个1到2000的唯一编号」——没写 host_id 必须
       **全集群唯一且不超 max_hosts**，也没写冲突后果。上游原文：
       「If hosts are misconfigured and have the same host_id, the delta lease
       for that host_id is being renewed will prevent any other host from being
       able to acquire the delta lease for that host_id.」——
       编号撞车会让**另一个节点永远拿不到它的 delta lease**。
     - L48「将要运行的服务进程注册到sanlock中」——上游对应的概念是
       **resource**（在存储上创建，名字 + 路径 + 对齐大小 + 扇区大小），
       而且 resource lease 分普通与 **persistent** 两种：
       上游「If a process holding resource leases fails or exits without
       releasing its leases, sanlock will release the leases for it
       automatically (**unless persistent resource leases were used**)」。
       → 仲裁进程恰恰**应该用 persistent lease**：否则仲裁进程一崩，
       租约被自动释放，仲裁权就落到别的节点手里了——而仲裁进程崩掉
       正是本文要解决的那个场景。
     - L49「获取资源租期，获取成功则可执行，否则等待一定时间，再次尝试」
       ——上游的租期是**自动续租**的（L37 提到了），但续租周期、租期时长、
       graceful shutdown 超时（`-g`）这些参数没提，重试间隔也没给。
   - 建议：补成一段可执行的内容——resource 的创建命令
     （上游是 `sanlock client add_lockspace -s LOCKSPACE` /
     `sanlock client add_resource` 一类，参数含 align_size 与 sector_size）、
     **为什么仲裁进程要用 persistent lease**、续租与超时的参数含义，
     以及「拿到锁之后本节点才有投票权」这条与 L39 的呼应。
   - 原因：README 的「可复现证据」「踩坑与校验」。

10. 位置：L25（207 字一整段，检查器 AIF-03 命中）
    - 问题：一段里塞了「sanlock 是什么」「每个节点各跑一个服务」「锁状态写到
      共享存储」「磁盘 Paxos」「用锁保证领导节点唯一」「分布式锁不频繁获取
      释放」「虚拟机共享存储的例子」七件事。
    - 建议：拆成两段——「sanlock 是什么（一句话 + 落盘在哪）」和
      「它提供哪两种抽象（lockspace / resource）」，把虚拟机那个例子留到
      讲 resource 生命周期时再用。
    - 原因：README 的「让抽象话落地」；检查器 AIF-03 命中。

11. 位置：L1 开头 / L62 结尾
    - 问题：开头没有一句话定位（检查器 STR-02 命中）；结尾停在内部排期，
      没有可带走的产物（检查器 STR-03 命中）；缺本仓库其它文章都有的
      「编写人／编写内容／编写时间」表（检查器 MET-01 命中）。
      检查器 DEP-00 也命中——五要素只命中 1 个。
    - 建议：开头补定位与编写信息；结尾给两张表——
      「sanlock 能力 → 本方案需要什么 → 差距/代价」，
      以及「移植要改 qdevice 的哪几处 → 依赖 → 怎么验证」；
      再链到同目录 `corosync-qdevice使用.md`、
      `corosync qnet挂死场景分析解决.md`。
    - 原因：README 的「一句话定位」「一份可带走的产物」「一条自然的内容路径」。

12. 位置：L64-L67「# reference」
    - 问题：两条参考都是**二手解读**，而且第一条状态可疑——
      实测 `https://read01.com/0zdOno.html` 对自动化请求返回 **403**
      （浏览器里是否可读未验证）；`https://cloud.tencent.com/developer/article/1651000`
      返回 200。更要紧的是**没给 sanlock 的上游地址**：上游已经不在 GitHub，
      `https://github.com/ClusterLabs/sanlock` 现在 **404**，
      README.rst 第一行就写着「See https://pagure.io/sanlock」。
      读者按文章去找 sanlock 源码会直接撞空。
    - 建议：参考列表加上上游一手源——
      sanlock 官方文档 `https://pagure.io/sanlock`（README.rst 有完整的
      租约、存储布局、过期处理说明）、corosync-qdevice 的 man page；
      二手文章只作补充。
    - 原因：涉及链接与可回溯性；上游迁址这件事不写，读者找不到源头。

13. 位置：L9、L21、L53
    - 问题：几处语言问题——
      L9「其不**依赖与**fence重启机器」应为「不**依赖**fence 重启机器」；
      L21「进程**hangz**住」多了个 z；
      L53「（耗时相对来说较短）」括号里的内容与句子重复，直接删；
      L9「或依赖较小，非必须，可配置」三个并列项之间用顿号连排，读起来像
      三种配置项，其实是一个「非必须、可配置」的修饰，语序要理顺。
    - 建议：逐处改正。
    - 原因：基础校对。

## 事实待核

- [x] sanlock 上游已迁出 GitHub —— `https://github.com/ClusterLabs/sanlock`
  返回 **404**；sanlock 的 README.rst 第一行即
  「See https://pagure.io/sanlock」；`https://pagure.io/sanlock/` 返回 200。
  （本条核对用的是 GitHub 镜像 `vjuranek/sanlock`，其描述为
  「Mirror of https://pagure.io/sanlock」，内容与 pagure 一致。）
- [x] sanlock 的磁盘布局 —— 上游 `src/rindex_disk.h` 的布局注释：
  `rindex_header.rindex_offset` 是 rindex 头相对设备起点的位置，
  **必须是 area_size 的倍数**；
  `resource_leases_start = rindex_offset + (2 * area_size)`；
  「resource lease N offset = resource_leases_start + (N * area_size)」；
  `rindex_entry` 固定 64 字节，`rindex_header.max_resources` 默认 4096。
  README「Storage」段另给出：
  「A lockspace is a series of **2000 delta leases** on disk, and requires
  **1MB** of storage」「A **paxos lease** exists on shared storage and
  requires **1MB** of space」，示例里「the lockspace needs 1MB and each
  resource needs 1MB」。
- [x] `hosts_lease` / `resource_lease` 在上游不存在 —— 把上游源码整棵树
  取下来（GitHub 镜像 `vjuranek/sanlock` 的 master tarball）全量搜索
  `hosts_lease|resource_lease|host_lease`，**唯一命中是
  `src/rindex_disk.h` 第 63/65/68 行的注释符号 `resource_leases_start`**，
  全树没有任何地方把它当作文件名使用。
- [x] host_id 范围与 max_hosts —— 上游 README：
  「host_id」（an integer host identifier from **1-2000**）；
  「A lockspace can support up to **2000** concurrent hosts using it」；
  「The 2000 individual delta leases in a lockspace are identified by number:
  1,2,3,...,2000」；以及「The host_id of hosts using the lockspace can be
  **no larger than the max_hosts value** for the lockspace」。
  max_hosts 与扇区/对齐的对应见「优先修改」第 4 条的表。
- [x] host_id 冲突的后果 —— 上游 README：
  「If hosts are misconfigured and have the same host_id, the delta lease
  for that host_id is being renewed will prevent any other host from being
  able to acquire the delta lease for that host_id.」
- [x] 两套租约算法及其出处 —— 上游 README：
  「delta leases are slow to acquire and demand regular i/o to shared
  storage. sanlock only uses them internally to hold a lease on its "host_id"…
  （"Light-Weight Leases for Storage-Centric Coordination", Chockler and
  Malkhi）」；「paxos leases are fast to acquire and sanlock makes them
  available to the application…（"Disk Paxos", Eli Gafni and Leslie Lamport）」。
  原文 L11「基于 disk-paxos 实现」的概括与上游的两租约模型不符。
- [x] 租约过期的三种处理方式 —— 上游 README「Expiration」：
  「sanlock uses **three methods** to stop local processes that are using
  expiring leases: 1. **Graceful shutdown**…（应用未指定退出程序时 sanlock
  发送 **SIGTERM**）2. **Forced shutdown**（发送 **SIGKILL**）3. **Host
  reset**（触发本机 watchdog 设备强制复位，sanlock 精确计时使其在别的
  host 可能接管租约之前触发）」。
- [x] sanlock 守护进程自身 hang 的后果 —— 上游 README「Failures」：
  「If the **sanlock daemon crashes or hangs**, it will not renew the expiry
  time of the per-lockspace connections it had to the wdmd daemon. This will
  lead to the expiration of the local watchdog device, and **the host will be
  reset**.」
- [x] 进程异常退出时的租期释放 —— 上游 README「Failures」：
  「If a process holding resource leases fails or exits without releasing
  its leases, sanlock will release the leases for it automatically
  (**unless persistent resource leases were used**.)」
- [x] watchdog 的接线方式 —— 上游 README「Watchdog」：
  「sanlock uses the **wdmd(8)** daemon to access /dev/watchdog. wdmd
  multiplexes multiple timeouts onto the single watchdog timer… If wdmd finds
  any connection expired, it will not renew the /dev/watchdog timer. Given
  enough successive failed renewals, **the watchdog device will fire and
  reset the host**.」
- [x] fence_sanlock 的机制 —— 上游 `fence_sanlock/fence_sanlock.8`：
  「fence_sanlock uses the watchdog device to reset nodes, in conjunction with
  three daemons: fence_sanlockd, sanlock, and wdmd.」
  「When fence_sanlock fences a node, it tries to acquire that node's resource
  lease. **sanlock will not grant the lease until the owner (the node being
  fenced) has been reset by its watchdog device.** The time it takes to
  acquire the lease is **140 seconds** from the victim's last lockspace
  renewal timestamp on the shared storage.」
  原文 L56「sanlock 也支持 fence 功能」这一句本身没错，但机制与代价没写。
- [x] corosync-qdevice 只有 net 模型 —— corosync **v2.4.6**：
  `qdevices/Makefile.am` 的源文件列表里只有
  `qdevice-model.c`、`qdevice-model-net.c`、`qdevice-model-type.h`、
  `qdevice-advanced-settings.c`（**没有** disk / heuristic）；
  `man/corosync-qdevice.8`：「The model basically defines what type of
  arbitrator is used. **Currently only net is supported.**」
  corosync-qdevice 上游 **master**：`qdevices/` 目录下同样只有
  `qdevice-model-net.c`，`man/corosync-qdevice.8` 同一句。
  → 磁盘（qdisk）仲裁不是上游能力。
- [x] corosync-qdevice 的版本现状 —— GitHub Releases：最新为 **v3.0.5
  (2026-11-12)**，此前 v3.0.4 (2025-11-24)、v3.0.3 (2023-03-22)、
  v3.0.2 (2022-11-03)、v3.0.1 (2020-11-23)、v3.0.0 (2018-12-12)。
- [x] sanlock 对共享存储的限制 —— 上游 README「Storage」：
  「Using sanlock on shared block devices that **do host based mirroring or
  replication** is not likely to work correctly. When using sanlock on shared
  files, **all sanlock io should go to one file server**.」
- [x] 参考链接的可达性 —— 实测（2026-11）：
  `https://read01.com/0zdOno.html` 返回 **403**（对自动化请求拒绝，
  浏览器中是否可读未验证）；`https://cloud.tencent.com/developer/article/1651000`
  返回 200。
- corosync 2.3.x 的 qdevice 是否还带 disk / heuristic 模型 —— 本轮核到
  v2.3.6 的 `qdevices/Makefile.am` 结构与 2.4.x 不同，未逐项比对；
  已知的是 2.4.x 起上游只剩 net 模型。现场用的是哪个版本需补。
- 现场 qdisk（磁盘仲裁）的来源与维护状态 —— 既然上游 2.4.x 起就没有这个
  模型，现场的 qdisk 只能是厂商补丁或自研；这决定结论第 3 条
  「先以现有 qdisk 实现功能」的可持续性，需作者说明。
- 现场共享存储的**扇区大小**与打算使用的 **align_size** —— 直接决定
  max_hosts（4K 扇区 + 1M 对齐只有 250），需补。
- 现场共享存储在**网络分区场景**下的行为 —— 是同一台控制器后的共享 LUN
  （两节点挂同一 VG/LV），还是主机级镜像/复制？后者与 sanlock 不兼容，
  且会让存储仲裁失去意义。需补。
- 「sanlock 进程 hang 住 → 主机被 watchdog 复位」这个边界，作者是否接受
  作为方案的收益边界 —— 若不接受，方案与 qdisk 的差别就只剩「应用进程
  hang 时不复位整机」，结论需要相应收紧。
- 仲裁进程是否使用 **persistent resource lease** —— 按上游语义，
  不用 persistent lease 的话仲裁进程一崩租约就被自动释放，
  仲裁权会落到别的节点；这个选择需作者确认。
- sanlock 版本 —— 上游最新版本号需确认（镜像仓库的 VERSION 文件未逐一核对），
  正文「原理」一节写的是哪一版的行为需补。

## 可补的技术证据或产物

- 机制 / 源码入口：上游 `src/rindex_disk.h`（磁盘布局常量与注释）、
  `src/lockspace.c` 与 `src/resource.c`（lockspace / resource 两套抽象）、
  `src/delta_lease.c` 与 `src/paxos_lease.c`（两种租约算法的实现）、
  `src/watchdog.c`（watchdog 接线与 recovery mode）、
  `src/client.c`（`sanlock client` 侧的命令）、`src/sanlock.8`（手册）、
  `fence_sanlock/fence_sanlockd.c`（watchdog 与 fence 协同）。
  文章讲的两处机制——「谁在什么时候有权投票」和「进程挂住时谁来收权」——
  分别对应 `paxos_lease.c` / `delta_lease.c` 与 `watchdog.c`。
- 实验或观测：一条能直接验证收益边界的实验——在共享存储上起 sanlock，
  然后分别 (a) SIGSTOP 住仲裁进程、(b) 挂死普通应用进程，观察：
  - (a) 的 watchdog 是否按时复位主机（上游说会）；
  - (b) 是否只发 SIGTERM/SIGKILL 而**不复位整机**（上游说会）。
  这两条一跑，「sanlock 能不能替代 fence」就有答案了，而不是靠推断。
  再补一条：把存储断掉，看 recovery mode 的时间线。
- 工程取舍：把「存储仲裁 vs 网络仲裁（qnet）vs 共享存储仲裁 + fence」
  摆在一起逐项比——脑裂风险、共享存储本身的可靠性要求、额外组件数量、
  挂死时的恢复动作（复位整机 vs 优雅退出）、140 秒的 fence 等待、
  共享存储脑裂时的仲裁失效模式。这张表是本文最该交付的东西。
- 结尾清单或下一篇链接：一页「共享存储仲裁 checklist」——
  存储类型与扇区大小 / align size / max_hosts、host_id 分配与唯一性、
  persistent lease 的选择、watchdog 接线、recovery mode 的时间预算、
  故障注入清单（拔网线、kill 仲裁进程、kill 应用进程、断存储）；
  再链到同目录 `corosync-qdevice使用.md`、
  `corosync qnet挂死场景分析解决.md`。

## 已确认的改动

- （本轮只出审校记录，正文改动待确认后执行。）
