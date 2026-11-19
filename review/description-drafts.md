# 摘要复核表

这是 `tools/draft-descriptions.py` 从正文里起草的文章摘要
（front matter 的 `description`）。**请过目。**

- 「现在的摘要」= 现在 front matter 里生效的值。空 = 这篇文章还没有摘要，
  卡片摘要退回正文的前 80 个字。
- 「起草的摘要」= 工具从正文里抽的第一段真正的段落。

两列不一样，说明那一条是**人工改过的**——以「现在的摘要」为准。

确认过的那些，把 ☐ 改成 ☑；`tools/draft-descriptions.py --write`
会把「起草的摘要」写进 `docs/` 的 front matter（sync 以源为准，不覆盖）。

⚠️ `--write` **不覆盖**已经写了摘要的文章（人工稿留着）。
真要盖，显式加 `--overwrite`。

| 文章 | 现在的摘要 | 起草的摘要 | 确认 |
| --- | --- | --- | --- |
| `source-tracks/linux/daily-ops/centos搭建离线仓库.md` | 我们知道centos是通过yum来下载和管理软件，通过yum工具我们可以直接将rpm软件包下载下来安装到系统，是管理和安装软件非常便捷的一个工具。 | 我们知道centos是通过yum来下载和管理软件，通过yum工具我们可以直接将rpm软件包下载下来安装到系统，是管理和安装软件非常便捷的一个工具。 | ☐ |
| `source-tracks/linux/kernel-internals/gcc attribute指北.md` | align属性不仅可以修饰变量，类型， 还可以修饰函数，用于地址对齐。 | align属性不仅可以修饰变量，类型， 还可以修饰函数，用于地址对齐。 | ☐ |
| `source-tracks/linux/daily-ops/git指北.md` | git 使用备忘：git bash 里 git status 显示不了中文时该配什么。 | （没抽出来） | ☐ |
| `source-tracks/linux/daily-ops/git高级指北.md` | git 进阶用法：分支之间的合并与冲突解决，以及那些容易把人绕进去的高级操作。 | logc参数说明如下： | ☐ |
| `source-tracks/linux/kernel-internals/kconfig和kbuild指北.md` | kconfig和kbuild是linux用来辅助配置和编译的工具。 | kconfig和kbuild是linux用来辅助配置和编译的工具。 | ☐ |
| `source-tracks/linux/memory-and-linking/linux cache指北.md` | 计算机中数据存取满足“二八定律”(局部性原理)，为了以较低的成本大幅提高性能，现代cpu都有cache。cpu cache已经发展到了三级缓存结构，基本上现在买的个人电脑都是L3结构。其中L1和L2cache为每个核独有，L3则所有核共享。 | 计算机中数据存取满足“二八定律”(局部性原理)，为了以较低的成本大幅提高性能，现代cpu都有cache。cpu cache已经发展到了三级缓存结构，基本上现在买的个人电脑都是L3结构。其中L1和L2cache为每个核独有，L3则所有核共享。 | ☐ |
| `source-tracks/linux/kernel-internals/linux ptp指北.md` | PTP（Precision Time Protocol）精确时间协议，由IEEE1588规定，用于同步网络中两台机器的时间。1558使用延时-请求测量机制达到主从时间同步。 | PTP（Precision Time Protocol）精确时间协议，由IEEE1588规定，用于同步网络中两台机器的时间。1558使用延时-请求测量机制达到主从时间同步。 | ☐ |
| `source-tracks/linux/kernel-internals/linux socket编程指北.md` | 以下server和client的c代码均拷贝自博客，详细内容请阅读原文。在其上添加了错误码打印，修改了服务端ip和端口，并增加了makefile脚本。 | 以下server和client的c代码均拷贝自博客，详细内容请阅读原文。在其上添加了错误码打印，修改了服务端ip和端口，并增加了makefile脚本。 | ☐ |
| `source-tracks/linux/kernel-internals/linuxUIO指北.md` | 在基于kernel的IO模型中，所有的设备IO都要经过内核处理，在高并发的网络数据包收发的情况下，大量硬件中断会降低内核数据包处理能力，内核和用户空间的数据拷贝也会造成大量的计算资源浪费。所以，作为高并发大流量网络开发框架的DPDK，必须要找到一个能够避免内核中断爆炸和大量数据拷贝的方法，在用户空… | 在基于kernel的IO模型中，所有的设备IO都要经过内核处理，在高并发的网络数据包收发的情况下，大量硬件中断会降低内核数据包处理能力，内核和用户空间的数据拷贝也会造成大量的计算资源浪费。所以，作为高并发大流量网络开发框架的DPDK，必须要找到一个能够避免内核中断爆炸和大量数据拷贝的方法，在用户空… | ☐ |
| `source-tracks/linux/daily-ops/linux下RANDOM和uuid的区别.md` | $RANDOM 和 uuid 有什么区别：一个生成 0 到 32767 的随机整数，一个保证分布式系统里的全局唯一。 | （没抽出来） | ☐ |
| `source-tracks/linux/daily-ops/linux下svn吐血指北.md` | 在 Linux 上用 svn 的踩坑记录：安装、配置默认编辑器为 vim，以及日常使用里那些容易出错的地方。 | 设置默认编辑器为vim | ☐ |
| `source-tracks/linux/memory-and-linking/linux内存管理指北.md` | 内存是一段连续的地址单元，linux内核接管内存管理后，会将内存划分为内核区和用户区。因而内存管理就分为两个层面： | 内存是一段连续的地址单元，linux内核接管内存管理后，会将内存划分为内核区和用户区。因而内存管理就分为两个层面： | ☐ |
| `source-tracks/linux/kernel-internals/linux内核指北.md` | Linux 内核相关资料的索引（内容还在整理）。 | （没抽出来） | ☐ |
| `source-tracks/linux/kernel-internals/linux内核模块指北.md` | linux内核提供在运行时可进行扩展的特性，这意味着当系统启动并运行时，我们可以向内核添加或移除部分功能。我们在运行时添加到内核中的代码就被成为动态可加载内核模块，我们简称为内核模块。可以将内核模块模块简单理解为linux内核的插件。 | linux内核提供在运行时可进行扩展的特性，这意味着当系统启动并运行时，我们可以向内核添加或移除部分功能。我们在运行时添加到内核中的代码就被成为动态可加载内核模块，我们简称为内核模块。可以将内核模块模块简单理解为linux内核的插件。 | ☐ |
| `source-tracks/linux/kernel-internals/linux字符设备指北.md` | 在Linux系统中，存在一类字符设备，它们拥有相同的主设备号（10），但次设备号不同，我们称这类设备为混杂设备(miscdevice)。所有的混杂设备形成一个链表，对设备访问时内核根据次设备号查找到相应的混杂设备。 | 在Linux系统中，存在一类字符设备，它们拥有相同的主设备号（10），但次设备号不同，我们称这类设备为混杂设备(miscdevice)。所有的混杂设备形成一个链表，对设备访问时内核根据次设备号查找到相应的混杂设备。 | ☐ |
| `source-tracks/linux/memory-and-linking/linux巨页内存指北.md` | 巨页的实现，涉及到两个模块：hugetlb和hugetlbfs。 | 巨页的实现，涉及到两个模块：hugetlb和hugetlbfs。 | ☐ |
| `source-tracks/linux/daily-ops/linux常用高级命令.md` | Linux 常用进阶命令速查：统计文件总数之类的组合用法。 | （没抽出来） | ☐ |
| `source-tracks/linux/kernel-internals/linux数据预取.md` | Linux 数据预取相关的资料索引（内容还在整理）。 | （没抽出来） | ☐ |
| `source-tracks/linux/daily-ops/linux目录介绍.md` | sysfs是一种基于ram的文件系统，和proc一样。Sysfs文件系统是一个类似于proc文件系统的特殊文件系统，用于将系统中的设备组织成层次结构，并向用户模式程序提供详细的内核数据结构信息。其实，就是在用户态可以通过对sys文件系统的访问，来看内核态的一些驱动或者设备等。 | sysfs是一种基于ram的文件系统，和proc一样。Sysfs文件系统是一个类似于proc文件系统的特殊文件系统，用于将系统中的设备组织成层次结构，并向用户模式程序提供详细的内核数据结构信息。其实，就是在用户态可以通过对sys文件系统的访问，来看内核态的一些驱动或者设备等。 | ☐ |
| `source-tracks/linux/kernel-internals/linux系统接口.md` | open可以打开文件，读取文件内容。特别的，读取一些特别的文件可以获取一些系统信息。 | open可以打开文件，读取文件内容。特别的，读取一些特别的文件可以获取一些系统信息。 | ☐ |
| `source-tracks/linux/kernel-internals/linux锁指北.md` | 锁一般用于解决资源竞争，比如多进程或者多线程场景下。锁主要是为了保证同一个资源在同一时间只能被一名修改者修改。 | 锁一般用于解决资源竞争，比如多进程或者多线程场景下。锁主要是为了保证同一个资源在同一时间只能被一名修改者修改。 | ☐ |
| `source-tracks/linux/daily-ops/logrotate机制详解.md` | logrotate 是一个 linux 系统日志的管理工具。可以对单个日志文件或者某个目录下的文件按时间 / 大小进行切割，压缩操作；指定日志保存数量；还可以在切割之后运行自定义命令。 | logrotate 是一个 linux 系统日志的管理工具。可以对单个日志文件或者某个目录下的文件按时间 / 大小进行切割，压缩操作；指定日志保存数量；还可以在切割之后运行自定义命令。 | ☐ |
| `source-tracks/linux/filesystem/lvm详解.md` | LVM（Logical Volume Manager）逻辑卷管理，是在硬盘分区和文件系统之间添加的一个逻辑层，为文件系统屏蔽下层硬盘分区布局，并提供一个抽象的盘卷，在盘卷上建立文件系统。它提供了一种灵活的方式来管理和操作磁盘空间，使管理员能够动态地创建、调整大小、合并和移动逻辑卷，而无需中断系统。 | LVM（Logical Volume Manager）逻辑卷管理，是在硬盘分区和文件系统之间添加的一个逻辑层，为文件系统屏蔽下层硬盘分区布局，并提供一个抽象的盘卷，在盘卷上建立文件系统。它提供了一种灵活的方式来管理和操作磁盘空间，使管理员能够动态地创建、调整大小、合并和移动逻辑卷，而无需中断系统。 | ☐ |
| `source-tracks/linux/daily-ops/shell使用.md` | shell 使用备忘：字符串比较等基础判断的写法。 | （没抽出来） | ☐ |
| `source-tracks/linux/kernel-internals/uboot指北.md` | U-Boot 相关资料的索引（内容还在整理）。 | （没抽出来） | ☐ |
| `source-tracks/linux/networking/vlan使用指北.md` | vlan详细内容请参考博客。 | vlan详细内容请参考博客。 | ☐ |
| `source-tracks/linux/memory-and-linking/不得不知道的linux库的装载、链接.md` | 在计算机世界里，一直有一个和现实世界一样非常重要的概念，那就是地址。就像是某个国家某个地点，才能找到某个人一样。 同样地，在计算机世界里，同样需要地址，在这样的地址能够找到某个文件或者某个符号。 换句话说，在计算机世界里，你要找到某个文件、某个进程、某个函数做某件事情，都需要知道他的地址。 在最上… | 在计算机世界里，一直有一个和现实世界一样非常重要的概念，那就是地址。就像是某个国家某个地点，才能找到某个人一样。 同样地，在计算机世界里，同样需要地址，在这样的地址能够找到某个文件或者某个符号。 换句话说，在计算机世界里，你要找到某个文件、某个进程、某个函数做某件事情，都需要知道他的地址。 在最上… | ☐ |
| `source-tracks/linux/memory-and-linking/内存管理之dlmalloc.md` | 内存管理之 dlmalloc：allocator 与系统堆的关系，以及一块内存从申请到映射上物理页的全过程。 | （没抽出来） | ☐ |
| `source-tracks/linux/networking/抓包指北.md` | Mergecap 从名字上 可以看出该命令的功能是合并多个报文为一个报文。 | Mergecap 从名字上 可以看出该命令的功能是合并多个报文为一个报文。 | ☐ |
| `source-tracks/linux/daily-ops/本地git仓库.md` | 本地搭一个 git 远程仓库：git init --bare 建库，再用 ssh 地址 clone 下来。 | （没抽出来） | ☐ |
| `source-tracks/linux/daily-ops/解决SSH连接Linux超时自动断开.md` | 现在无论空闲多久，SSH客户端都不会自动断开了。 | 现在无论空闲多久，SSH客户端都不会自动断开了。 | ☐ |
| `source-tracks/linux/daily-ops/银河麒麟V10 远程桌面_银河麒麟v10远程桌面-CSDN博客.md` | 运行命令然后输入口令，并且确认。 | 运行命令然后输入口令，并且确认。 | ☐ |
| `linux/cpu-affinity-top-guide/index.md` | Linux CFS(Completely Fair Scheduler)在多核系统上默认自由调度: | Linux CFS(Completely Fair Scheduler)在多核系统上默认自由调度: | ☐ |
| `source-tracks/linux/memory-and-linking/ebpf/ebpf基础.md` | 使用下面的makefile进行编译： | 使用下面的makefile进行编译： | ☐ |
| `source-tracks/linux/memory-and-linking/ebpf/oltp.md` | otlp，全称是opentelemetry protocol，主要用于可观测性领域。（trace、metrics、logs） | otlp，全称是opentelemetry protocol，主要用于可观测性领域。（trace、metrics、logs） | ☐ |
| `source-tracks/linux/memory-and-linking/ebpf/pg-ferret.md` | pg-ferret主要跟踪如下信息： | pg-ferret主要跟踪如下信息： | ☐ |
| `source-tracks/linux/memory-and-linking/ebpf/rust-ebpf编程基础.md` | 用 Rust 写 eBPF 程序：aya 框架的下载依赖、编译与加载，一步步走通。 | rust中有一个ebpf编程框架aya，其地址为https://github.com/aya-rs/aya。 | ☐ |
| `source-tracks/linux/kernel-internals/kernel/qemu-busybox调试linux.md` | 用 QEMU 和 BusyBox 搭建 Linux 内核的调试环境：下载源码、编译内核、启动调试。 | 执行如下命令进行编译： | ☐ |
| `ai/01-ai常用工具和开发框架.md` | MCP的目标，就是让AI像访问网页一样，轻松访问各种数据和功能。 | MCP的目标，就是让AI像访问网页一样，轻松访问各种数据和功能。 | ☐ |
| `ai/01_开场白目录.md` | 你让 ChatGPT 帮你写一封邮件。 | 你让 ChatGPT 帮你写一封邮件。 | ☐ |
| `ai/02_AI到底聪明在哪从手机人脸识别说起.md` | 每天早上，你拿起手机，看一眼屏幕，解锁。 | 每天早上，你拿起手机，看一眼屏幕，解锁。 | ☐ |
| `ai/03_AI怎么读懂文字国王减去男人等于什么.md` | 你对 ChatGPT 说”苹果”。 | 你对 ChatGPT 说”苹果”。 | ☐ |
| `ai/04_AI是怎么突然变厉害的2012所有人以为他们作弊了.md` | 如果 AI 的历史是一部电影，2012 年 10 月就是高潮。 | 如果 AI 的历史是一部电影，2012 年 10 月就是高潮。 | ☐ |
| `ai/05_神经网络到底是什么6000万个旋钮的真相.md` | “神经网络”可能是 AI 领域最吓人的一个词。 | “神经网络”可能是 AI 领域最吓人的一个词。 | ☐ |
| `ai/06_AI是怎么学会的从做错一道题说起.md` | 想象你面前有 6000 万个旋钮。 | 想象你面前有 6000 万个旋钮。 | ☐ |
| `ai/07_ChatGPT为什么能对话一篇引用17万次的论文.md` | 2017 年，Google 的一个团队发表了一篇论文。 | 2017 年，Google 的一个团队发表了一篇论文。 | ☐ |
| `ai/08_AI为什么会撒谎一个律师被ChatGPT骗了.md` | 2023 年 5 月，纽约南区联邦法院。 | 2023 年 5 月，纽约南区联邦法院。 | ☐ |
| `ai/09_ChatGPT回答你的三秒钟里发生了什么.md` | 如果你从第 1 篇读到这里，恭喜——你现在对 AI 的理解，已经超过了绝大多数人。 | 如果你从第 1 篇读到这里，恭喜——你现在对 AI 的理解，已经超过了绝大多数人。 | ☐ |
| `ai/10_AI 到底有多聪明一份让 AI 研究者也困惑的成绩单.md` | 上一章我们拆开了 AI 的黑箱，得到了一个核心结论：AI 是超级模式匹配器。 但这个结论到底有多大的解释力？先做一个测试。 | 上一章我们拆开了 AI 的黑箱，得到了一个核心结论：AI 是超级模式匹配器。 但这个结论到底有多大的解释力？先做一个测试。 | ☐ |
| `ai/11_AI 能创造吗从一团噪声到一幅画.md` | 上一篇结尾，我留了一个让我自己困惑了很久的问题： | 上一篇结尾，我留了一个让我自己困惑了很久的问题： | ☐ |
| `ai/12_为什么 AI 能赢世界冠军却开不好车一条藏在所有 AI 背后的分界线.md` | 上一篇结尾，我留了一个矛盾： | 上一篇结尾，我留了一个矛盾： | ☐ |
| `ai/13_这个框架会过时吗AI 的天花板和你的判断力.md` | 2025 年 12 月，GPT-5.2 发布。我打开新闻，看到标题——“数学竞赛满分”。 | 2025 年 12 月，GPT-5.2 发布。我打开新闻，看到标题——“数学竞赛满分”。 | ☐ |
| `ai/14_怎么让AI听懂你的话同一个AI为什么他用得比你好10倍.md` | 同一个 ChatGPT，同一个问题： | 同一个 ChatGPT，同一个问题： | ☐ |
| `ai/15_怎么跟AI协作不翻车AI说的话你该信几分.md` | 上一篇我们搞清楚了一件事：Prompt Engineering 不是玄学，而是给 AI 更精准的上下文，让它的模式匹配更精准。 | 上一篇我们搞清楚了一件事：Prompt Engineering 不是玄学，而是给 AI 更精准的上下文，让它的模式匹配更精准。 | ☐ |
| `ai/16_AI 写代码有多厉害快了 55但错多了 75.md` | 上一篇，我们总结了四条和 AI 协作的原则——让 AI 做它擅长的事、验证大于信任、迭代而非一次到位、用 AI 放大你的优势而非替代你的思考。 | 上一篇，我们总结了四条和 AI 协作的原则——让 AI 做它擅长的事、验证大于信任、迭代而非一次到位、用 AI 放大你的优势而非替代你的思考。 | ☐ |
| `ai/17_AI会取代我们吗它不懂孤独是什么意思.md` | 从第 1 篇”你的手机是怎么认出你的脸”到现在，我们一起走过了 16 篇。 | 从第 1 篇”你的手机是怎么认出你的脸”到现在，我们一起走过了 16 篇。 | ☐ |
| `ai/18_AI是你的杠杆但前提是你自己得会.md` | 听起来像老生常谈。但写代码这件事，我越做越发现，很多人用 AI 的姿势是完全反的——把不会的交给 AI，把自己变成 AI 的附庸。 | 听起来像老生常谈。但写代码这件事，我越做越发现，很多人用 AI 的姿势是完全反的——把不会的交给 AI，把自己变成 AI 的附庸。 | ☐ |
| `ai/19_AI是你的杠杆普通人也能用的AI实战教程.md` | 不是吓你 —— 是事实。这不是程序员才要面对的事,而是每一个会用电脑、会用手机、会用 Office 的人,都会被卷入的浪潮。 | 不是吓你 —— 是事实。这不是程序员才要面对的事,而是每一个会用电脑、会用手机、会用 Office 的人,都会被卷入的浪潮。 | ☐ |
| `ai/20_外网与AI工具使用指南.md` | 在展开之前,先把七个工具的定位摆清楚,免得你装了一堆结果不知道该用哪个。 | 在展开之前,先把七个工具的定位摆清楚,免得你装了一堆结果不知道该用哪个。 | ☐ |
| `ai/22_普通人谷歌与AI使用培训教程.md` | 这一讲的目的不是让大家懂技术,而是让学员理解\"为什么\",后面学 Clash 时才不会觉得是在做一件 mysteriously 的事。 | 这一讲的目的不是让大家懂技术,而是让学员理解"为什么",后面学 Clash 时才不会觉得是在做一件 mysteriously 的事。 | ☐ |
| `ai/ai_video/AI Video Orchestrator 平台总体架构设计.md` | VideoFlow Studio 是面向个人创作者、MCN机构、短剧团队、影视公司的一站式 AI 影视协同创作平台。 | VideoFlow Studio 是面向个人创作者、MCN机构、短剧团队、影视公司的一站式 AI 影视协同创作平台。 | ☐ |
| `ai/ai_video/AI Video Orchestrator 技术选型文档.md` | AI 视频编排平台的技术选型文档：跨平台优先、Agent 优先、插件化优先三条原则，以及每一层的具体技术选型。 | Client Layer | ☐ |
| `ai/ai_video/AI Video Orchestrator 概要设计.md` | VideoFlow Studio 的概要设计：十一个微服务如何划分，数据模型、Provider 架构、Workflow DSL、协作与调度、权限和可观测性怎么设计。 | Writer Agent | ☐ |
| `ai/ai_video/AI一镜到底视频平台竞品拆解与产品定位报告.md` | 打造全球领先的AI导演平台，让用户通过自然语言即可生成电影级一镜到底视频。 | 打造全球领先的AI导演平台，让用户通过自然语言即可生成电影级一镜到底视频。 | ☐ |
| `ai/ai_video/AI一镜到底视频生成平台市场调研与可行性分析报告.md` | 随着生成式AI技术快速发展，视频生成已经成为继大语言模型之后增长最快的AI赛道之一。 | 随着生成式AI技术快速发展，视频生成已经成为继大语言模型之后增长最快的AI赛道之一。 | ☐ |
| `ai/claude/claude配置.md` | Claude Code 的插件配置：怎么用 marketplace 添加插件源、怎么安装 superpowers，以及常用的插件命令。 | （没抽出来） | ☐ |
| `ai/claude安装教程/index.md` | 当前openclaw（龙虾）比较火，但是配置比较复杂，可以先安装claude进行体验。 | 当前openclaw（龙虾）比较火，但是配置比较复杂，可以先安装claude进行体验。 | ☐ |
| `alg/B-树如何使查询更快/index.md` | 本文翻译自How does B-tree make your queries fast?,部分内容翻译可能不准确，请以原文为准。 | 本文翻译自How does B-tree make your queries fast?,部分内容翻译可能不准确，请以原文为准。 | ☐ |
| `engineering/foundations/data-struct.md` | 数据结构按照视点不同可分为：逻辑结构和物理结构 | 数据结构按照视点不同可分为：逻辑结构和物理结构 | ☐ |
| `engineering/foundations/design-pattern.md` | 设计模式针对变化：哪些东西是变的、哪些是不变的，以及变化与稳定之间该怎么取舍。 | 变化意味着灵活，不稳定。 | ☐ |
| `engineering/foundations/file.md` | 文件操作看着是四门语言各自的 API，底下却是同一套机制：文件描述符、缓冲、原子性。 本文会把这三件事摊开说，再把 C、Java、C#、Python、shell、bat 的调用摆在一起对照—— 重点不在「有哪些函数」，而在「哪些坑会让你以为写对了、其实没写对」。 | 文件操作看着是四门语言各自的 API，底下却是同一套机制：文件描述符、缓冲、原子性。 本文会把这三件事摊开说，再把 C、Java、C#、Python、shell、bat 的调用摆在一起对照—— 重点不在「有哪些函数」，而在「哪些坑会让你以为写对了、其实没写对」。 | ☐ |
| `engineering/foundations/network.md` | 逐步检查网络的各个层次：物理链接、链路层、网络层直到应用层，熟悉使用各种如下的工具，包括 | 逐步检查网络的各个层次：物理链接、链路层、网络层直到应用层，熟悉使用各种如下的工具，包括 | ☐ |
| `engineering/foundations/normal.md` | 该目录下主要存放所有支撑编程的材料，即编程的理论基础和编程逻辑。如： | 该目录下主要存放所有支撑编程的材料，即编程的理论基础和编程逻辑。如： | ☐ |
| `engineering/foundations/process.md` | 程序是指令的集合，而进程则是程序执行的基本单元。程序运行起来成为进程，进而利用处理器资源、内存资源，进行各种I/O操作，从而完成特定任务。 | 程序是指令的集合，而进程则是程序执行的基本单元。程序运行起来成为进程，进而利用处理器资源、内存资源，进行各种I/O操作，从而完成特定任务。 | ☐ |
| `engineering/foundations/sql.md` | 结论：union all的性能大约是union的好几倍。 | 结论：union all的性能大约是union的好几倍。 | ☐ |
| `engineering/foundations/string.md` | 在 C 语言中，字符串实际上是使用 null 字符 '\\0' 终止的一维字符数组。因此，一个以 null 结尾的字符串，包含了组成字符串的字符。 | 在 C 语言中，字符串实际上是使用 null 字符 '\0' 终止的一维字符数组。因此，一个以 null 结尾的字符串，包含了组成字符串的字符。 | ☐ |
| `engineering/foundations/use-tools/download.md` | 常用下载工具清单：Linux 下的 flareget、xdm、uget，以及 Windows 下的 idm。 | （没抽出来） | ☐ |
| `engineering/foundations/use-tools/git.md` | 常用 git 命令速查：add、commit、push、pull、checkout、branch、tag 的日常用法。 | `` git add filename git commit -m "description" git push git pull git checkhout git branch git tag | ☐ |
| `engineering/foundations/use-tools/google.md` | Google 浏览器扩展清单：油猴、广告拦截、二维码、右键搜索、octotree 等等，每一条是什么用途。 | （没抽出来） | ☐ |
| `engineering/foundations/use-tools/other.md` | 几个日常小工具的用途速查：文本比较合并的 meld、跟踪系统调用的 strace，以及 man 的八章结构。 | （没抽出来） | ☐ |
| `engineering/foundations/use-tools/vim.md` | vim 常用操作速查：横竖分屏、换屏、撤销、复制、删除分别按什么键。 | （没抽出来） | ☐ |
| `blog/博客搭建指南.md` | 日常维护手册。仓库的总体布局、一次 push 之后的构建链路、各模块职责，详见 架构.md。本文只讲怎么动。 | 日常维护手册。仓库的总体布局、一次 push 之后的构建链路、各模块职责，详见 架构.md。本文只讲怎么动。 | ☐ |
| `blog/同名文章-html-与-md-版本管理.md` | 仓库偶尔会出现 xxx.md 和 xxx.html 两个同主题、不同表达形式的源文件（一个 markdown 版、一个带丰富排版的 HTML 版）。本文说明 sync-hexo.py 处理这种情况的约定，为什么必须遵守，以及怎么做。 | 仓库偶尔会出现 xxx.md 和 xxx.html 两个同主题、不同表达形式的源文件（一个 markdown 版、一个带丰富排版的 HTML 版）。本文说明 sync-hexo.py 处理这种情况的约定，为什么必须遵守，以及怎么做。 | ☐ |
| `blog/同步到公众号方案.md` | 把博客内容自动/半自动地发布到「growdu」微信公众号。本文先讲清楚微信公众号生态对程序化发布的硬约束，再给两套技术路线对比，最后给推荐方案与具体实施步骤。 | 把博客内容自动/半自动地发布到「growdu」微信公众号。本文先讲清楚微信公众号生态对程序化发布的硬约束，再给两套技术路线对比，最后给推荐方案与具体实施步骤。 | ☐ |
| `blog/架构.md` | 加新文章、换样式、修构建，先看这份再下手。 | 加新文章、换样式、修构建，先看这份再下手。 | ☐ |
| `blog/视频嵌入指南.md` | matery 主题自带的视频能力盘点 + 4 种主流嵌入方式的一步步操作。所有改动都在仓库里 git commit + push 后，CI 自动构建并部署到 growdu.cn。 | matery 主题自带的视频能力盘点 + 4 种主流嵌入方式的一步步操作。所有改动都在仓库里 git commit + push 后，CI 自动构建并部署到 growdu.cn。 | ☐ |
| `blog/部署到服务器.md` | 把博客从 GitHub Pages 迁移到个人服务器 growdu.cn，CI 自动构建并通过 rsync over SSH 部署。总体布局、构建链路见 架构.md，日常维护见 博客搭建指南.md。本文只讲部署。 | 把博客从 GitHub Pages 迁移到个人服务器 growdu.cn，CI 自动构建并通过 rsync over SSH 部署。总体布局、构建链路见 架构.md，日常维护见 博客搭建指南.md。本文只讲部署。 | ☐ |
| `blog/重构方案.md` | 站点要同时服务两类消费： | 站点要同时服务两类消费： | ☐ |
| `blog/阿里云ECS选购指南.md` | 云服务器（Elastic Compute Service，简称 ECS）是云厂商卖给你的虚拟服务器。和传统物理机相比，它的好处是： | 云服务器（Elastic Compute Service，简称 ECS）是云厂商卖给你的虚拟服务器。和传统物理机相比，它的好处是： | ☐ |
| `blog/mermaid/mermaid图渲染问题诊断与修复.md` | 本文所有数字都来自真实渲染测量（headless Chrome + 生产环境 SVG 尺寸），不是估算。 | 本文所有数字都来自真实渲染测量（headless Chrome + 生产环境 SVG 尺寸），不是估算。 | ☐ |
| `chatgpt/chatgpt使用.md` | ChatGPT 是什么、能用来干什么：代码相关的问题怎么问它，以及日常把它当助手用的几种典型场景。 | 可点击(高效率工具——chatgpt使用_growdu_real的博客-CSDN博客)在网络上访问本文。 | ☐ |
| `chatgpt/newbing使用教程/index.md` | New Bing 使用教程：下载 Edge Dev、修改默认搜索引擎，让新版 Bing 的 AI 搜索在国内也能用。 | 点击这里下载edge dev。 | ☐ |
| `distributed/foundations/C语言实现分布式自增有序的唯一ID生成算法-snowflake算法.md` | 之前有人问我设计一个分布式的递增的唯一id生成。想了半天不知道，偶然一个同事说起snowflake算法，我百度了一下，很简单高效。 | 之前有人问我设计一个分布式的递增的唯一id生成。想了半天不知道，偶然一个同事说起snowflake算法，我百度了一下，很简单高效。 | ☐ |
| `distributed/foundations/C语言雪花算法,记一次雪花算法的实现.md` | 作者最近在实现雪花算法生成主键，看了不少文章。个人觉得雪花算法的最大的优点是有序(减少数据库的页分裂页合并)。雪花算法本身很简单，但他依赖于时间，也就是机器或容器的时间一回拨就出现问题了。网上也出现了不少关于如何解决回拨的问题。我记录一下本次实现雪花主键的过程。 | 作者最近在实现雪花算法生成主键，看了不少文章。个人觉得雪花算法的最大的优点是有序(减少数据库的页分裂页合并)。雪花算法本身很简单，但他依赖于时间，也就是机器或容器的时间一回拨就出现问题了。网上也出现了不少关于如何解决回拨的问题。我记录一下本次实现雪花主键的过程。 | ☐ |
| `distributed/ha-and-dr/Patroni详解.md` | Patroni 笔记：PostgreSQL 高可用方案里负责选主、故障切换与配置同步的那个组件（内容还在整理）。 | （没抽出来） | ☐ |
| `distributed/consensus/raft协议动态调整quorum.md` | 按照当前raft协议实现，当n个节点的集群超过n/2个节点宕机时，集群将无法提供服务。如5个节点的集群，当有3个节点宕机时，集群将无法提供服务。 | 按照当前raft协议实现，当n个节点的集群超过n/2个节点宕机时，集群将无法提供服务。如5个节点的集群，当有3个节点宕机时，集群将无法提供服务。 | ☐ |
| `distributed/field-notes/repmgr网络割裂问题.md` | repmgr 在网络割裂场景下的问题：分布式存储里，主备之间失联时该由谁说了算。 | （没抽出来） | ☐ |
| `distributed/ha-and-dr/两地三中心技术指标分析.md` | 延迟主要和网络系统（网络硬件等）以及距离有关。 | 延迟主要和网络系统（网络硬件等）以及距离有关。 | ☐ |
| `distributed/selection/主流分布式高可用方案.md` | 主流分布式高可用方案的分类与取舍（内容还在整理）。 | （没抽出来） | ☐ |
| `distributed/distributed-storage/从两地三中心到OceanBase的多地多中心 - 墨天轮.md` | 在金融行业，“两地三中心”是一个基本的合规要求，本文简单介绍一下金融行业容灾架构的\"两地三中心\"究竟是指什么，然后说明OceanBase实现的\"两地三中心\"甚至\"多地多中心\"有什么特点。 | 在金融行业，“两地三中心”是一个基本的合规要求，本文简单介绍一下金融行业容灾架构的"两地三中心"究竟是指什么，然后说明OceanBase实现的"两地三中心"甚至"多地多中心"有什么特点。 | ☐ |
| `distributed/foundations/分布式一致性协议.md` | 当前业界主流的分布式一致性协议主要有下面这几个。本文回答两个问题：它们各自解决的是 同一类问题的哪一部分，以及选型时该看哪个。它们不是同一层次的替代品——先看清各自 解决的是问题的哪一部分： | 当前业界主流的分布式一致性协议主要有下面这几个。本文回答两个问题：它们各自解决的是 同一类问题的哪一部分，以及选型时该看哪个。它们不是同一层次的替代品——先看清各自 解决的是问题的哪一部分： | ☐ |
| `distributed/foundations/分布式存储需要解决的问题.md` | 分布式存储绕不开的几个问题：数据一致性怎么保证、ACID 在多副本下还成不成立。 | （没抽出来） | ☐ |
| `distributed/selection/分布式数据库高可用方案设计.md` | 通俗的来说，分布式数据库高可用要求即使仅存一个集群节点，也需要对外提供服务。 | 通俗的来说，分布式数据库高可用要求即使仅存一个集群节点，也需要对外提供服务。 | ☐ |
| `distributed/foundations/分布式系统设计必知必会.md` | 分布式系统设计的几个必知问题：并发、串行与并行、时序，以及数据一致性。 | （没抽出来） | ☐ |
| `distributed/consensus/分布式集群动态调整quorum值方案对比.md` | 举例来说，一个包含5个节点的数据库集群，当集群挂掉3个节点后，因为不符合半数以上节点正常原则，数据库集群将无法对外提供服务，需要人为介入。但在数据库的实际使用场景中，我们期望即使只剩下一个节点也能对外提供服务。实际上，当5个集群节点挂掉2个节点后，应将剩下3个节点看成一个3节点的集群，动态调整对应… | 举例来说，一个包含5个节点的数据库集群，当集群挂掉3个节点后，因为不符合半数以上节点正常原则，数据库集群将无法对外提供服务，需要人为介入。但在数据库的实际使用场景中，我们期望即使只剩下一个节点也能对外提供服务。实际上，当5个集群节点挂掉2个节点后，应将剩下3个节点看成一个3节点的集群，动态调整对应… | ☐ |
| `distributed/selection/基于corosync的分布式应用程序开发方案分析.md` | 综上所述，并结合实际使用场景中遇到的各种问题，可得出如下结论： | 综上所述，并结合实际使用场景中遇到的各种问题，可得出如下结论： | ☐ |
| `distributed/foundations/常用分布式实现架构.md` | 分布式架构根据各个分布式节点共享的内容分为如下几种： | 分布式架构根据各个分布式节点共享的内容分为如下几种： | ☐ |
| `distributed/foundations/常用分布式解决方案.md` | c-raft集群开发需处理问题： | c-raft集群开发需处理问题： | ☐ |
| `distributed/consensus/corosy-qdevice源码阅读.md` | corosync-qdevice 源码阅读笔记：qdevice 的投票与仲裁是怎么实现的（内容还在整理）。 | （没抽出来） | ☐ |
| `distributed/field-notes/corosync qnet挂死场景分析解决.md` | qnet挂死场景的矛盾点： | qnet挂死场景的矛盾点： | ☐ |
| `distributed/field-notes/corosync-cmap使用指南.md` | cmap是corosync的内存key/value存储。cmap提供了如下功能： | cmap是corosync的内存key/value存储。cmap提供了如下功能： | ☐ |
| `distributed/consensus/corosync-qdevice中ffsplit与lsm算法的区别.md` | corosync-qdevice目前支持两种算法来设置corosync-qnetd如何为给定的节点或者分区提供投票的行为。 | corosync-qdevice目前支持两种算法来设置corosync-qnetd如何为给定的节点或者分区提供投票的行为。 | ☐ |
| `distributed/field-notes/corosync-qdevice使用.md` | qdevice要用途是让群集能够承受大于标准仲裁规则所允许的节点故障数量。在分布式一致性协议中，基于多数派quorum的协议解决脑裂等问题，因而当集群存活节点挂死超过一半时，集群将无法对外提供服务。qdevice提供仲裁机制，使集群在多数节点挂掉后仍然能提供服务。典型的如双节点集群发生网络分区后，… | qdevice要用途是让群集能够承受大于标准仲裁规则所允许的节点故障数量。在分布式一致性协议中，基于多数派quorum的协议解决脑裂等问题，因而当集群存活节点挂死超过一半时，集群将无法对外提供服务。qdevice提供仲裁机制，使集群在多数节点挂掉后仍然能提供服务。典型的如双节点集群发生网络分区后，… | ☐ |
| `distributed/consensus/corosync-qdevice源码阅读.md` | corosync-qdevice 源码阅读笔记：网络投票算法、消息类型与 qnetd 仲裁的注册流程。 | （没抽出来） | ☐ |
| `distributed/consensus/corosync-qdevice详解.md` | corosync-qdevice是corosync集群工具的一个组件，用于提供第三方仲裁服务。corosync-qdevice需与corosync-qnetd和corosync一起使用，无法单独运行。 | corosync-qdevice是corosync集群工具的一个组件，用于提供第三方仲裁服务。corosync-qdevice需与corosync-qnetd和corosync一起使用，无法单独运行。 | ☐ |
| `distributed/field-notes/corosync-qnetd投票机制.md` | corosync-qnetd是corosync的第三方仲裁机制，当corosync出现网络分区时，集群内部无法选择出quorate一方时，就会借助corosync-qnetd来进行辅助投票。 | corosync-qnetd是corosync的第三方仲裁机制，当corosync出现网络分区时，集群内部无法选择出quorate一方时，就会借助corosync-qnetd来进行辅助投票。 | ☐ |
| `distributed/field-notes/corosync使用.md` | corosync编译依赖libqb和kronosnet。 | corosync编译依赖libqb和kronosnet。 | ☐ |
| `distributed/consensus/corosync多仲裁方案设计.md` | 当前corosync仲裁方式qnetd的现状如下： | 当前corosync仲裁方式qnetd的现状如下： | ☐ |
| `distributed/consensus/corosync源码阅读.md` | corosync采用服务的方式设计，使用totem协议作为分布式一致性协议，使用libqb库进行进程间通信。 | corosync采用服务的方式设计，使用totem协议作为分布式一致性协议，使用libqb库进行进程间通信。 | ☐ |
| `distributed/field-notes/corosync编程指南.md` | corosync编译依赖libqb和kronosnet。基于ubuntu20.04编译。 | corosync编译依赖libqb和kronosnet。基于ubuntu20.04编译。 | ☐ |
| `distributed/consensus/disk-paxos详解.md` | Disk Paxos使用处理器和磁盘网络实现可靠的分布式系统。 与原始 Paxos 算法一样，Disk Paxos 可以保证在任意非拜占庭故障的情况下保持一致性。 只要大多数磁盘可用，即使仅剩下一个节点也能保证进程可用，且保持一致性。 | Disk Paxos使用处理器和磁盘网络实现可靠的分布式系统。 与原始 Paxos 算法一样，Disk Paxos 可以保证在任意非拜占庭故障的情况下保持一致性。 只要大多数磁盘可用，即使仅剩下一个节点也能保证进程可用，且保持一致性。 | ☐ |
| `distributed/consensus/libqb源码详解.md` | libqb分为客户端和服务端，除了网络通信外，如udp/tcp，libqb还支持本地ipc通信。 | libqb分为客户端和服务端，除了网络通信外，如udp/tcp，libqb还支持本地ipc通信。 | ☐ |
| `distributed/field-notes/sanlock实现共享corosync共享存储仲裁.md` | 为了使corosync集群支持少数派运行模式，需要引入第三方仲裁，同时为了节约机器资源，使用共享存储作为第三方仲裁。需要一种基于共享存储的算法机制来保证在corosync集群出现网络分区或者故障时，仲裁能给其中一个分区投票，使corosync集群继续供服务，并保证数据一致性。 | 为了使corosync集群支持少数派运行模式，需要引入第三方仲裁，同时为了节约机器资源，使用共享存储作为第三方仲裁。需要一种基于共享存储的算法机制来保证在corosync集群出现网络分区或者故障时，仲裁能给其中一个分区投票，使corosync集群继续供服务，并保证数据一致性。 | ☐ |
| `distributed/consensus/totem协议详解.md` | 这个阶段是集群组建完成正常工作的状态，这个状态一个节点发送的消息其它节点都会全部有序提交给上层 | 这个阶段是集群组建完成正常工作的状态，这个状态一个节点发送的消息其它节点都会全部有序提交给上层 | ☐ |
| `distributed/field-notes/一台主机运行多个corosync代码分析.md` | corosync当前设计为一台机器只能运行一个corosyc实例，无法部署多个，是由如下两个部分决定的： | corosync当前设计为一台机器只能运行一个corosyc实例，无法部署多个，是由如下两个部分决定的： | ☐ |
| `distributed/field-notes/corosync-down网卡仍处于多数派/index.md` | 网卡 down 掉以后，corosync 已经和另外两个节点失去联系，却仍然报告自己是 quorate。 于是 fence 不动作，主库不停，跨中心的 observer 又把主库切到了灾备中心； 等网络恢复，两个中心各有一个主库。 | 网卡 down 掉以后，corosync 已经和另外两个节点失去联系，却仍然报告自己是 quorate。 于是 fence 不动作，主库不停，跨中心的 observer 又把主库切到了灾备中心； 等网络恢复，两个中心各有一个主库。 | ☐ |
| `distributed/consensus/dcf写入机制.md` | dcf提供如下两个写入接口： | dcf提供如下两个写入接口： | ☐ |
| `distributed/consensus/dcf投票系统详解.md` | DCF 投票系统详解：节点角色与投票模式的枚举定义，以及投票初始化的完整调用流程。 | （没抽出来） | ☐ |
| `distributed/consensus/dcf运行机制.md` | dcf通过stream的概念来运行分布式协议，每个stream是一个完整的分布式实例。 每个stream可以由多个节点组成。 | dcf通过stream的概念来运行分布式协议，每个stream是一个完整的分布式实例。 每个stream可以由多个节点组成。 | ☐ |
| `distributed/consensus/openguass dcf源码阅读.md` | openGauss DCF 源码阅读笔记：从 main 到 dcf_start、init_main_threads 的启动流程梳理。 | （没抽出来） | ☐ |
| `distributed/consensus/一文读懂openguass dcf网络模块.md` | 通信模块主要是基于MEC实现（Message Exchange Component），提供整个DCF组件实例间通信能力，以及异步事件处理框架。主要功能有：可扩展的多种通信协议，单播、广播、环回的发送接口，消息异步处理的框架，支持多channel机制和多优先级队列，支持压缩和批量发送等mec主要通过… | 通信模块主要是基于MEC实现（Message Exchange Component），提供整个DCF组件实例间通信能力，以及异步事件处理框架。主要功能有：可扩展的多种通信协议，单播、广播、环回的发送接口，消息异步处理的框架，支持多channel机制和多优先级队列，支持压缩和批量发送等mec主要通过… | ☐ |
| `distributed/consensus/常用压缩算法编程.md` | 压缩算法选择主要考虑三个方面： | 压缩算法选择主要考虑三个方面： | ☐ |
| `distributed/selection/业界高可用解决方案.md` | 业界主流高可用方案的横向对照：Oracle RAC、Amazon Aurora、OceanBase 各自怎么做多活与容灾。 | （没抽出来） | ☐ |
| `distributed/ha-and-dr/ha元信息常见存储方式/index.md` | mysql MHA(Master High Availability)是mysql高可用一套相对成熟的解决方案。MHA 由 MHA 管理器和 MHA 节点组成。 | mysql MHA(Master High Availability)是mysql高可用一套相对成熟的解决方案。MHA 由 MHA 管理器和 MHA 节点组成。 | ☐ |
| `distributed/ha-and-dr/中移动数据库停库问题分析/index.md` | 同城双中心，主中心数据库停库，且未触发中心间切换。 | 同城双中心，主中心数据库停库，且未触发中心间切换。 | ☐ |
| `distributed/ha-and-dr/调整corosync网络波动时间操作文档/index.md` | 调整允许的corosync网络波动时间仅需修改repmgr.conf配置文件，重启kbha和repmgrd进程，无需停止数据库，也不影响上层业务运行。按如下步骤修改配置并重启服务，经过本次修改重启后，允许的网络波动时间将从20秒增加到50秒。 | 调整允许的corosync网络波动时间仅需修改repmgr.conf配置文件，重启kbha和repmgrd进程，无需停止数据库，也不影响上层业务运行。按如下步骤修改配置并重启服务，经过本次修改重启后，允许的网络波动时间将从20秒增加到50秒。 | ☐ |
| `distributed/ha-and-dr/kingbase两地三中心日常巡检.md` | 两地三中心运行一段时间后，需要定期巡检，观察集群状态是否正常，若有异常，需确认异常原因并及时处理。 ## 确认集群是否正常 | 两地三中心运行一段时间后，需要定期巡检，观察集群状态是否正常，若有异常，需确认异常原因并及时处理。 ## 确认集群是否正常 | ☐ |
| `distributed/ha-and-dr/tptc.md` | 一个中心整个机房被一束光纤挖断，数据库集群还在，数据也还在，客户端却连不上了； 或者反过来——中心之间那条链路抖动了一下，两个中心都认为自己还是主库， 于是同一个库同时有了两个写入方。前一种是「少了一半」，后一种是「多了半个」。 | 一个中心整个机房被一束光纤挖断，数据库集群还在，数据也还在，客户端却连不上了； 或者反过来——中心之间那条链路抖动了一下，两个中心都认为自己还是主库， 于是同一个库同时有了两个写入方。前一种是「少了一半」，后一种是「多了半个」。 | ☐ |
| `distributed/field-notes/多地多中心方案调研/index.md` | 商业银行数据中心监管指引明确规定了商业银行数据中心的要求。 | 商业银行数据中心监管指引明确规定了商业银行数据中心的要求。 | ☐ |
| `distributed/ha-and-dr/oracle_maa架构详解/index.md` | oracle maa架构分为青铜、白银、黄金、铂金四个级别，其中黄金又有四种实现方式。这里按照az（可用区，一般是同一个机房，组成一个数据库集群）、region（区域，一般是不同的城市，可能会有多个可用区）、rto、rpo来进行统计，其统计结果如下（从现有架构图中来看，oracle最多有4个可用区… | oracle maa架构分为青铜、白银、黄金、铂金四个级别，其中黄金又有四种实现方式。这里按照az（可用区，一般是同一个机房，组成一个数据库集群）、region（区域，一般是不同的城市，可能会有多个可用区）、rto、rpo来进行统计，其统计结果如下（从现有架构图中来看，oracle最多有4个可用区… | ☐ |
| `distributed/ha-and-dr/oracle_site_guard详解/index.md` | Oracle Site Guard 是一个数据保护解决方案，用于实现数据中心级别的灾难恢复和故障转移。它可以保护 Oracle 数据库、应用服务器、中间件以及整个操作系统。 | Oracle Site Guard 是一个数据保护解决方案，用于实现数据中心级别的灾难恢复和故障转移。它可以保护 Oracle 数据库、应用服务器、中间件以及整个操作系统。 | ☐ |
| `distributed/distributed-storage/haproxy使用extern-check支持伪双写配置验证.md` | 将如下配置文件添加到postgresql.conf, | 将如下配置文件添加到postgresql.conf, | ☐ |
| `distributed/distributed-storage/haproxy支持postgresql伪双写.md` | 要达到双写，其实就是把备库收到的请求都转发或者路由到主库，这又分为两种方式: | 要达到双写，其实就是把备库收到的请求都转发或者路由到主库，这又分为两种方式: | ☐ |
| `distributed/distributed-storage/postgresql伪双写.md` | 选择haproxy来实现。 | 选择haproxy来实现。 | ☐ |
| `distributed/distributed-storage/事务管理.md` | 事务并发引发的问题如下： | 事务并发引发的问题如下： | ☐ |
| `distributed/consensus/c-raft分布式存储方案.md` | RAFT中将节点状态分为： | RAFT中将节点状态分为： | ☐ |
| `distributed/consensus/c-rart.md` | raft协议的完全异步C语言实现。 | raft协议的完全异步C语言实现。 | ☐ |
| `distributed/consensus/raft协议动态调整quorum.md` | 按照当前raft协议实现，当n个节点的集群超过n/2个节点宕机时，集群将无法提供服务。如5个节点的集群，当有3个节点宕机时，集群将无法提供服务。 | 按照当前raft协议实现，当n个节点的集群超过n/2个节点宕机时，集群将无法提供服务。如5个节点的集群，当有3个节点宕机时，集群将无法提供服务。 | ☐ |
| `distributed/consensus/raft重要概念.md` | raft将分布式一致性问题分解成两个独立的问题，分成两个大的步骤来进行数据处理。 | raft将分布式一致性问题分解成两个独立的问题，分成两个大的步骤来进行数据处理。 | ☐ |
| `distributed/consensus/zookeeperC语言API编程指南.md` | zookeeper是用java语言编写的分布式集群，我们可以基于zookeeper搭建分布式应用。通常zookeeper作为服务器运行，分布式应用需要使用客户端API与zookeeper进行通信。 | zookeeper是用java语言编写的分布式集群，我们可以基于zookeeper搭建分布式应用。通常zookeeper作为服务器运行，分布式应用需要使用客户端API与zookeeper进行通信。 | ☐ |
| `distributed/consensus/zookeeper主备集群demo.md` | 使用zookeeper搭建主备集群，要求实现如下功能： | 使用zookeeper搭建主备集群，要求实现如下功能： | ☐ |
| `distributed/consensus/zookeeper使用说明文档.md` | 需对每一台zookeeper集群节点做如下操作： | 需对每一台zookeeper集群节点做如下操作： | ☐ |
| `distributed/consensus/zookeeper安装部署教程.md` | 需对每一台zookeeper集群节点做如下操作： | 需对每一台zookeeper集群节点做如下操作： | ☐ |
| `engineering/engineering-practice/code/assemble-work/readme.md` | This is about assemble. | This is about assemble. | ☐ |
| `engineering/engineering-practice/code/c-sharp-work/readme.md` | This is some code using C#. | This is some code using C#. | ☐ |
| `engineering/engineering-practice/code/c-work/readme.md` | This directory include some works using C. | This directory include some works using C. | ☐ |
| `engineering/engineering-practice/code/c-work/simple-editor/preview.md` | 插入、删除、保存为基本的文件读写功能，回退、前进要求可以在当前状态之前的各状态之间来回切换。 | 插入、删除、保存为基本的文件读写功能，回退、前进要求可以在当前状态之前的各状态之间来回切换。 | ☐ |
| `engineering/engineering-practice/code/c-work/ticket/readme.md` | This is code. | This is code. | ☐ |
| `engineering/engineering-practice/code/gui-work/readme.md` | This is GUI program. | This is GUI program. | ☐ |
| `engineering/engineering-practice/code/html-work/readme.md` | This is about html. | This is about html. | ☐ |
| `engineering/engineering-practice/code/java-work/readme.md` | This directory include some code using java. | This directory include some code using java. | ☐ |
| `engineering/engineering-practice/code/JavaScript-work/readme.md` | This is about JavaScript. | This is about JavaScript. | ☐ |
| `engineering/engineering-practice/code/shell-work/readme.md` | This directory include some code using shell. | This directory include some code using shell. | ☐ |
| `engineering/engineering-practice/code/shell-work/vim/readme.md` | vim 配置使用vimplus. | vim 配置使用vimplus. | ☐ |
| `computer_communication/现代信息查询与检索技巧.md` | vfox是一个版本管理工具，可以方便的管理各种开发环境的版本，比如go、python、nodejs。 | vfox是一个版本管理工具，可以方便的管理各种开发环境的版本，比如go、python、nodejs。 | ☐ |
| `source-tracks/postgresql/extensions-perf/polardb竞争力分析.md` | 云原生数据库 PolarDB 是阿里云自研产品，在存储计算分离架构下，利用了软硬件结合的优势，100%兼容 MySQL 和 PostgreSQL 生态，为用户提供秒级弹性、高性能、海量存储、安全可靠的数据库服务。PolarDB 分布式版历经十余年淬炼，始终保持对阿里集团“双十一购物狂欢节”所有相关… | 云原生数据库 PolarDB 是阿里云自研产品，在存储计算分离架构下，利用了软硬件结合的优势，100%兼容 MySQL 和 PostgreSQL 生态，为用户提供秒级弹性、高性能、海量存储、安全可靠的数据库服务。PolarDB 分布式版历经十余年淬炼，始终保持对阿里集团“双十一购物狂欢节”所有相关… | ☐ |
| `source-tracks/postgresql/extensions-perf/citus-columnar-deep-dive/index.md` | 本文回答 4 个问题： | 本文回答 4 个问题： | ☐ |
| `source-tracks/postgresql/extensions-perf/citus-deep-dive/index.md` | 把 PG 变成\"分布式 OLTP\"是 14 年来业界最大野心之一。Citus 用 PG 扩展的方式实现了分布式——不 fork 内核、不重写 parser、不破坏 SQL 兼容性，只是把 SQL 通过 plan / execute 路由到 worker 节点。 | 把 PG 变成"分布式 OLTP"是 14 年来业界最大野心之一。Citus 用 PG 扩展的方式实现了分布式——不 fork 内核、不重写 parser、不破坏 SQL 兼容性，只是把 SQL 通过 plan / execute 路由到 worker 节点。 | ☐ |
| `source-tracks/postgresql/extensions-perf/cstore-fdw-deep-dive/index.md` | PG 生态里最早做\"列存\"的扩展是 Hydra 商业版（2014），后来开源为 cstore_fdw（2016），又被 Citus 5.0+ 集成进 columnar extension（2017）。它是 PG 列存 FDW 的鼻祖。 | PG 生态里最早做"列存"的扩展是 Hydra 商业版（2014），后来开源为 cstore_fdw（2016），又被 Citus 5.0+ 集成进 columnar extension（2017）。它是 PG 列存 FDW 的鼻祖。 | ☐ |
| `source-tracks/postgresql/getting-started/database-selection-dimensions/index.md` | 上一篇我们列了 PG 给你的 5 + 7 + 8 张清单——能存能取、能查能改、能事务能复制能扩展。但这其实是所有数据库都能给到你的\"地板能力\"。MySQL 能、Oracle 能、SQL Server 能、MongoDB 能（某种程度）、甚至 SQLite 都能。 | 上一篇我们列了 PG 给你的 5 + 7 + 8 张清单——能存能取、能查能改、能事务能复制能扩展。但这其实是所有数据库都能给到你的"地板能力"。MySQL 能、Oracle 能、SQL Server 能、MongoDB 能（某种程度）、甚至 SQLite 都能。 | ☐ |
| `source-tracks/postgresql/getting-started/database-specialization-taxonomy/index.md` | 上一篇我们说：所有数据库都能给\"基础能力\"——CRUD、事务、索引、复制。那为什么我们还需要时序数据库、图数据库、文档数据库、向量数据库这一大堆\"专用数据库\"？ | 上一篇我们说：所有数据库都能给"基础能力"——CRUD、事务、索引、复制。那为什么我们还需要时序数据库、图数据库、文档数据库、向量数据库这一大堆"专用数据库"？ | ☐ |
| `source-tracks/postgresql/extensions-perf/pg-challahscript-tips/index.md` | 我在 Web 应用行业摸爬滚打了快十年，期间用过很多系统和工具。说实话，官方文档通常是最好的学习资料——除了 PostgreSQL。 | 我在 Web 应用行业摸爬滚打了快十年，期间用过很多系统和工具。说实话，官方文档通常是最好的学习资料——除了 PostgreSQL。 | ☐ |
| `source-tracks/postgresql/extensions-perf/pg-dont-do-this/index.md` | 这是一份常见错误的清单——按主题分章，每条都说清楚\"为什么不要\"和\"什么时候才可以用\"。 | 这是一份常见错误的清单——按主题分章，每条都说清楚"为什么不要"和"什么时候才可以用"。 | ☐ |
| `source-tracks/postgresql/extensions-perf/pg-duckdb-deep-dive/index.md` | PG + DuckDB 是 2024 年最热的\"hybrid OLTP/OLAP\"组合——MotherDuck / Hydra 联合开发的 pg_duckdb 让 PG 进程内嵌 DuckDB 列存引擎，对外提供统一 SQL。 | PG + DuckDB 是 2024 年最热的"hybrid OLTP/OLAP"组合——MotherDuck / Hydra 联合开发的 pg_duckdb 让 PG 进程内嵌 DuckDB 列存引擎，对外提供统一 SQL。 | ☐ |
| `source-tracks/postgresql/extensions-perf/pg-stat-statements-deep-dive/index.md` | pg_stat_statements 是 PG 8.0 (2005) 进入 contrib 的官方统计扩展，到现在仍是 99% PG 监控工具的\"数据源\"。它是 PG 自己的\"slow query log + 性能数据采集\"。 | pg_stat_statements 是 PG 8.0 (2005) 进入 contrib 的官方统计扩展，到现在仍是 99% PG 监控工具的"数据源"。它是 PG 自己的"slow query log + 性能数据采集"。 | ☐ |
| `source-tracks/postgresql/extensions-perf/pgaudit-deep-dive/index.md` | 合规要求下，PG 必须能回答 3 个问题：谁在什么时间做了什么、数据被谁修改、谁访问了敏感字段。pgAudit 把 PG 自带的 log_statement = all 升级为细粒度审计扩展。 | 合规要求下，PG 必须能回答 3 个问题：谁在什么时间做了什么、数据被谁修改、谁访问了敏感字段。pgAudit 把 PG 自带的 log_statement = all 升级为细粒度审计扩展。 | ☐ |
| `source-tracks/postgresql/extensions-perf/pgbackrest-deep-dive/index.md` | PG 自带 pg_basebackup + pg_dump 能解决 70% 的备份需求。剩下 30%（增量备份 + 并行恢复 + 加密 + S3 + 监控）要靠 pgBackRest——它是 PG 备份领域事实标准，Crunchy Data / EDB / AWS RDS 都用它。 | PG 自带 pg_basebackup + pg_dump 能解决 70% 的备份需求。剩下 30%（增量备份 + 并行恢复 + 加密 + S3 + 监控）要靠 pgBackRest——它是 PG 备份领域事实标准，Crunchy Data / EDB / AWS RDS 都用它。 | ☐ |
| `source-tracks/postgresql/extensions-perf/pgbench-internals/index.md` | 提到 PostgreSQL 的压测工具，几乎所有人第一反应都是 pgbench。但 pgbench 到底是什么？它如何跑起来？它在客户端到底干了什么？它怎么用三套不同的 libpq API 把 SQL 扔给 server？它的状态机长什么样？ | 提到 PostgreSQL 的压测工具，几乎所有人第一反应都是 pgbench。但 pgbench 到底是什么？它如何跑起来？它在客户端到底干了什么？它怎么用三套不同的 libpq API 把 SQL 扔给 server？它的状态机长什么样？ | ☐ |
| `source-tracks/postgresql/extensions-perf/pgcrypto-deep-dive/index.md` | PG 8.0 (2005) 之前没有内置加密函数。pgcrypto 是 2000 年进入 contrib 的\"安全工具箱\"，25 年演化到 v1.3，对接 OpenSSL 3.x，是 99% PG 部署的加密核心。 | PG 8.0 (2005) 之前没有内置加密函数。pgcrypto 是 2000 年进入 contrib 的"安全工具箱"，25 年演化到 v1.3，对接 OpenSSL 3.x，是 99% PG 部署的加密核心。 | ☐ |
| `source-tracks/postgresql/extensions-perf/pgvector-deep-dive/index.md` | 2024 年开始，\"AI 数据库\"成为新热点：Qdrant、Milvus、Weaviate、Pinecone 这些专用向量数据库 vs PG + pgvector 的\"一库多用\"模型，争论不下。 | 2024 年开始，"AI 数据库"成为新热点：Qdrant、Milvus、Weaviate、Pinecone 这些专用向量数据库 vs PG + pgvector 的"一库多用"模型，争论不下。 | ☐ |
| `source-tracks/postgresql/extensions-perf/postgis-deep-dive/index.md` | PostGIS 不是简单的\"PG 加几何函数\"，而是 PG 历史上第一个非贡献者、内核之外的\"超级扩展\"——它有自己的数据类型、自己的索引、自己的函数库、自己的类型转换、自己的栅格子系统、自己的拓扑子系统、自己的点云子系统。 | PostGIS 不是简单的"PG 加几何函数"，而是 PG 历史上第一个非贡献者、内核之外的"超级扩展"——它有自己的数据类型、自己的索引、自己的函数库、自己的类型转换、自己的栅格子系统、自己的拓扑子系统、自己的点云子系统。 | ☐ |
| `source-tracks/postgresql/getting-started/postgresql-background-worker/index.md` | BackgroundWorker 是 PostgreSQL 中所有非 client 进程的统一抽象——逻辑复制的 launcher / apply worker / tablesync worker、流复制的 walsender、自动 vacuum、并行查询 worker、autovacuum l… | BackgroundWorker 是 PostgreSQL 中所有非 client 进程的统一抽象——逻辑复制的 launcher / apply worker / tablesync worker、流复制的 walsender、自动 vacuum、并行查询 worker、autovacuum l… | ☐ |
| `source-tracks/postgresql/storage-engine/postgresql-catalog-snapshot-deep-dive/index.md` | 先看一段看起来平平无奇、但每个 PG 内核开发者都踩过的代码： | 先看一段看起来平平无奇、但每个 PG 内核开发者都踩过的代码： | ☐ |
| `source-tracks/postgresql/storage-engine/postgresql-catalog-storage/index.md` | PG 里\"一张表的元数据\"听起来像一个很小的概念——无非是列名、类型、所有者。但只要你打开 src/include/catalog/ 看一下 60 多个 pg_*.dat / pg_*.h 文件，就会发现这是整个 PostgreSQL 内核里最大的一坨代码：从磁盘到内存，从冷启动到热运行，从一… | PG 里"一张表的元数据"听起来像一个很小的概念——无非是列名、类型、所有者。但只要你打开 src/include/catalog/ 看一下 60 多个 pg_*.dat / pg_*.h 文件，就会发现这是整个 PostgreSQL 内核里最大的一坨代码：从磁盘到内存，从冷启动到热运行，从一… | ☐ |
| `source-tracks/postgresql/getting-started/postgresql-core-features/index.md` | 很多人会问：PostgreSQL 现在到底有什么功能？ | 很多人会问：PostgreSQL 现在到底有什么功能？ | ☐ |
| `source-tracks/postgresql/getting-started/postgresql-for-everything/index.md` | \"宇宙的终极答案不是 42，而是 PostgreSQL。\ | "宇宙的终极答案不是 42，而是 PostgreSQL。" | ☐ |
| `source-tracks/postgresql/getting-started/postgresql-history/index.md` | 很多人对 PostgreSQL 的印象是\"那个比 MySQL 更严肃的 SQL 数据库\"。但如果你只看版本号，会以为它就是从 1996 年某个 1.0 起步的普通开源项目。事实上，PostgreSQL 是从 1970s 数据库研究浪潮中走出来的一条\"主线程\"，跟 System R、Ingr… | 很多人对 PostgreSQL 的印象是"那个比 MySQL 更严肃的 SQL 数据库"。但如果你只看版本号，会以为它就是从 1996 年某个 1.0 起步的普通开源项目。事实上，PostgreSQL 是从 1970s 数据库研究浪潮中走出来的一条"主线程"，跟 System R、Ingr… | ☐ |
| `source-tracks/postgresql/transaction-mvcc/postgresql-latch-mechanism/index.md` | 想象一下，PostgreSQL 里有 200 个 backend 同时挤在 shared_buffers 上抢同一个热点 page。某个 backend 在等 WALFlush，另一个在等 LockManager，还有一个在等客户端的下一条 SQL。它们都在睡觉，但都不能用 sleep(1)——一… | 想象一下，PostgreSQL 里有 200 个 backend 同时挤在 shared_buffers 上抢同一个热点 page。某个 backend 在等 WALFlush，另一个在等 LockManager，还有一个在等客户端的下一条 SQL。它们都在睡觉，但都不能用 sleep(1)——一… | ☐ |
| `source-tracks/postgresql/getting-started/postgresql-libpq-mechanism/index.md` | 想象你正坐在一家只能容纳一桌客人的小餐厅里。厨房只有一个炉子，但每天要接待几十位客人。老板不愿意花大钱雇十个厨师，于是发明了一套\"接力\"流程：客人坐下前先填一份菜单，写好之后交给厨房；厨房不是一道菜做完再接下一道，而是把今天的菜单攒成一摞，按\"出餐顺序\"一份一份炒；炒好了用小窗口递出去；客… | 想象你正坐在一家只能容纳一桌客人的小餐厅里。厨房只有一个炉子，但每天要接待几十位客人。老板不愿意花大钱雇十个厨师，于是发明了一套"接力"流程：客人坐下前先填一份菜单，写好之后交给厨房；厨房不是一道菜做完再接下一道，而是把今天的菜单攒成一摞，按"出餐顺序"一份一份炒；炒好了用小窗口递出去；客… | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-ddl-dml-ordering/index.md` | 我先给你看一个会让你半夜被报警叫醒的场景： | 我先给你看一个会让你半夜被报警叫醒的场景： | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-ddl-trigger-apply-worker/index.md` | 主要源码路径： - ~/cwork/postgresql/src/backend/replication/logical/worker.c - ~/cwork/postgresql/src/backend/replication/logical/tablesync.c - ~/cwork/post… | 主要源码路径： - ~/cwork/postgresql/src/backend/replication/logical/worker.c - ~/cwork/postgresql/src/backend/replication/logical/tablesync.c - ~/cwork/post… | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-docker-setup/index.md` | PostgreSQL 的逻辑复制（Logical Replication）自 10.0 起成为内核能力，基于 发布（Publication）/ 订阅（Subscription） 模型，把发布端表的 WAL 解码为逻辑变更（pgoutput 插件），由订阅端 apply worker 回放。 | PostgreSQL 的逻辑复制（Logical Replication）自 10.0 起成为内核能力，基于 发布（Publication）/ 订阅（Subscription） 模型，把发布端表的 WAL 解码为逻辑变更（pgoutput 插件），由订阅端 apply worker 回放。 | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-monitoring/index.md` | 监控逻辑复制这件事，\"看 pg_stat_subscription 一眼够不够？\"——不够。原因有三： | 监控逻辑复制这件事，"看 pg_stat_subscription 一眼够不够？"——不够。原因有三： | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-options/index.md` | CREATE SUBSCRIPTION 那一长串 WITH (...) 参数，每个都对应 pg_subscription 系统表里的一列，背后是 apply worker 一段真实的代码分支。 | CREATE SUBSCRIPTION 那一长串 WITH (...) 参数，每个都对应 pg_subscription 系统表里的一列，背后是 apply worker 一段真实的代码分支。 | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-parallel-worker/index.md` | 看到\"PG 逻辑复制并行\"这几个字，很多人会想到两种东西： | 看到"PG 逻辑复制并行"这几个字，很多人会想到两种东西： | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-partitioned-insert-flow/index.md` | 主要源码路径： - ~/cwork/postgresql/src/backend/replication/pgoutput/pgoutput.c - ~/cwork/postgresql/src/backend/replication/logical/proto.c - ~/cwork/postg… | 主要源码路径： - ~/cwork/postgresql/src/backend/replication/pgoutput/pgoutput.c - ~/cwork/postgresql/src/backend/replication/logical/proto.c - ~/cwork/postg… | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-publish-via-partition-root/index.md` | 主要源码路径： - ~/cwork/postgresql/src/include/catalog/pg_publication.h - ~/cwork/postgresql/src/backend/catalog/pg_publication.c - ~/cwork/postgresql/src/… | 主要源码路径： - ~/cwork/postgresql/src/include/catalog/pg_publication.h - ~/cwork/postgresql/src/backend/catalog/pg_publication.c - ~/cwork/postgresql/src/… | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-reorderbuffer-transaction/index.md` | 很多人以为逻辑复制就是\"publisher 解码 WAL → subscriber 重放\"——把它想成一份 tcpdump -X + psql -f。但只要你想过一次\"如果事务在 publisher 上回滚了，subscriber 怎么办？\"、\"如果 publisher 写到一半崩了，重… | 很多人以为逻辑复制就是"publisher 解码 WAL → subscriber 重放"——把它想成一份 tcpdump -X + psql -f。但只要你想过一次"如果事务在 publisher 上回滚了，subscriber 怎么办？"、"如果 publisher 写到一半崩了，重… | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-spill-deep-dive/index.md` | 在逻辑复制的生态里，spill 是一个高频混淆词。试图搜过 PostgreSQL 官方文档的读者会发现一个尴尬的事实： | 在逻辑复制的生态里，spill 是一个高频混淆词。试图搜过 PostgreSQL 官方文档的读者会发现一个尴尬的事实： | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-streaming-spill/index.md` | \"我的 pg_replslot/<slot>/ 目录下堆了 500 多万个 .spill 文件，磁盘快炸了；监控看到 streaming=on/parallel 已经开了，我以为 streaming 就是流式，就不会 spill。\ | "我的 pg_replslot/<slot>/ 目录下堆了 500 多万个 .spill 文件，磁盘快炸了；监控看到 streaming=on/parallel 已经开了，我以为 streaming 就是流式，就不会 spill。" | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-tables-lifecycle/index.md` | 如果你正处理\"我这表卡在 i 状态好久没动了\"、\"apply worker 看 pg_stat_subscription 但表就是不同步\"、\"库里堆了一堆 sub_xxx_sync_xxxx slot 怎么办\"这些事——本文就是给你写的。 | 如果你正处理"我这表卡在 i 状态好久没动了"、"apply worker 看 pg_stat_subscription 但表就是不同步"、"库里堆了一堆 sub_xxx_sync_xxxx slot 怎么办"这些事——本文就是给你写的。 | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-throughput-benchmark/index.md` | 想测 PostgreSQL 逻辑复制的吞吐率，第一直觉是\"找一个叫 logical-replication-benchmark 的工具\"——没有。PostgreSQL 官方仓库里没有这种独立 benchmark；pg_logicalbench / logical-replication-ben… | 想测 PostgreSQL 逻辑复制的吞吐率，第一直觉是"找一个叫 logical-replication-benchmark 的工具"——没有。PostgreSQL 官方仓库里没有这种独立 benchmark；pg_logicalbench / logical-replication-ben… | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-with-partitioned-tables/index.md` | 主要源码路径： - ~/cwork/postgresql/src/backend/replication/logical/worker.c - ~/cwork/postgresql/src/backend/replication/logical/tablesync.c - ~/cwork/post… | 主要源码路径： - ~/cwork/postgresql/src/backend/replication/logical/worker.c - ~/cwork/postgresql/src/backend/replication/logical/tablesync.c - ~/cwork/post… | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-worker-model/index.md` | 主要源码路径： - ~/cwork/postgresql/src/backend/replication/logical/launcher.c - ~/cwork/postgresql/src/backend/replication/logical/worker.c - ~/cwork/postg… | 主要源码路径： - ~/cwork/postgresql/src/backend/replication/logical/launcher.c - ~/cwork/postgresql/src/backend/replication/logical/worker.c - ~/cwork/postg… | ☐ |
| `source-tracks/postgresql/getting-started/postgresql-module-architecture/index.md` | 打开终端敲一行 pg_ctl start，几秒后看到 database system is ready to accept connections。这几秒钟里，一台进程工厂刚刚开业： | 打开终端敲一行 pg_ctl start，几秒后看到 database system is ready to accept connections。这几秒钟里，一台进程工厂刚刚开业： | ☐ |
| `source-tracks/postgresql/transaction-mvcc/postgresql-mvcc/index.md` | 想象一下，你正坐在一家 24 小时营业的自助图书馆里。顾客们进进出出，有人想改书里的一段话，有人想删掉某一页。如果每改一次都要把整本书收回柜台、贴上封条、再发出去，那这家图书馆基本就瘫痪了。 | 想象一下，你正坐在一家 24 小时营业的自助图书馆里。顾客们进进出出，有人想改书里的一段话，有人想删掉某一页。如果每改一次都要把整本书收回柜台、贴上封条、再发出去，那这家图书馆基本就瘫痪了。 | ☐ |
| `source-tracks/postgresql/transaction-mvcc/postgresql-parallel-worker/index.md` | 提到 PostgreSQL 并行，第一反应往往是\"加 max_parallel_workers_per_gather 就完事了\"。但实际生产里我们会遇到一堆反直觉的问题： | 提到 PostgreSQL 并行，第一反应往往是"加 max_parallel_workers_per_gather 就完事了"。但实际生产里我们会遇到一堆反直觉的问题： | ☐ |
| `source-tracks/postgresql/index-and-query/postgresql-partition-handling/index.md` | 想象你是一家快递公司的调度总监。每天有几百万个包裹要按目的地分拣。一开始你让所有快递员把包裹堆在一张巨大的桌子上，靠肉眼找路线——等找到时客户已经催单催到爆。 | 想象你是一家快递公司的调度总监。每天有几百万个包裹要按目的地分拣。一开始你让所有快递员把包裹堆在一张巨大的桌子上，靠肉眼找路线——等找到时客户已经催单催到爆。 | ☐ |
| `source-tracks/postgresql/index-and-query/postgresql-rangevar-and-data-structures/index.md` | PG 内核的代码风格和\"面向对象/面向接口\"的现代语言不一样——它用 C 写，几乎没有继承、没有接口，每个子系统就是一组紧密耦合的结构体 + 一组函数。所有模块的边界都靠结构体字段来划。 | PG 内核的代码风格和"面向对象/面向接口"的现代语言不一样——它用 C 写，几乎没有继承、没有接口，每个子系统就是一组紧密耦合的结构体 + 一组函数。所有模块的边界都靠结构体字段来划。 | ☐ |
| `source-tracks/postgresql/index-and-query/postgresql-read-a-row-deep-dive/index.md` | 想象你在一家极简的图书馆。规则很怪： | 想象你在一家极简的图书馆。规则很怪： | ☐ |
| `source-tracks/postgresql/index-and-query/postgresql-read-catalog-table/index.md` | PostgreSQL 内核开发中最常见的任务之一是：\"在某段 C 代码里读一张表（多半是 catalog 表）的几行 tuple\"。这听起来简单，实际上涉及事务控制、MVCC 快照、relation cache、catalog cache、AM 抽象、heap scan、buffer pin、… | PostgreSQL 内核开发中最常见的任务之一是："在某段 C 代码里读一张表（多半是 catalog 表）的几行 tuple"。这听起来简单，实际上涉及事务控制、MVCC 快照、relation cache、catalog cache、AM 抽象、heap scan、buffer pin、… | ☐ |
| `source-tracks/postgresql/transaction-mvcc/postgresql-row-lock-deep-dive/index.md` | PostgreSQL 用 MVCC（Multi-Version Concurrency Control）解决读-写冲突： | PostgreSQL 用 MVCC（Multi-Version Concurrency Control）解决读-写冲突： | ☐ |
| `source-tracks/postgresql/transaction-mvcc/postgresql-running-xacts-snapshot/index.md` | 逻辑复制里最容易出 bug 的事不是 decode（pgoutput 已经写得相当稳定），也不是 apply（无脑 INSERT/UPDATE/DELETE），而是 snapshot 怎么从 WAL 里\"长\"出来——也就是 RUNNING_XACTS + SnapBuild 状态机 + xmi… | 逻辑复制里最容易出 bug 的事不是 decode（pgoutput 已经写得相当稳定），也不是 apply（无脑 INSERT/UPDATE/DELETE），而是 snapshot 怎么从 WAL 里"长"出来——也就是 RUNNING_XACTS + SnapBuild 状态机 + xmi… | ☐ |
| `source-tracks/postgresql/getting-started/postgresql-schema-search-path/index.md` | schema 常被理解为“表的目录”。这不够准确。 | schema 常被理解为“表的目录”。这不够准确。 | ☐ |
| `source-tracks/postgresql/getting-started/postgresql-senior-kernel-developer/index.md` | 先定义 \"资深\"——不要被 \"老员工 / 工龄 10 年\" 等同。 | 先定义 "资深"——不要被 "老员工 / 工龄 10 年" 等同。 | ☐ |
| `source-tracks/postgresql/index-and-query/postgresql-stream-execution-logic/index.md` | 普通（非流式）逻辑复制的复制单位是事务： | 普通（非流式）逻辑复制的复制单位是事务： | ☐ |
| `source-tracks/postgresql/storage-engine/postgresql-toast-deep-dive/index.md` | PostgreSQL 的 Heap Page 默认 8KB（BLCKSZ）。一个 tuple 必须完整 fit 在单个 page 内。但变长字段（varlena：text / varchar / bytea / jsonb / array / numeric）理论上无大小限制。 | PostgreSQL 的 Heap Page 默认 8KB（BLCKSZ）。一个 tuple 必须完整 fit 在单个 page 内。但变长字段（varlena：text / varchar / bytea / jsonb / array / numeric）理论上无大小限制。 | ☐ |
| `source-tracks/postgresql/transaction-mvcc/postgresql-transaction-lifecycle/index.md` | 如果你只学过 SQL，看到事务大概是这样的： | 如果你只学过 SQL，看到事务大概是这样的： | ☐ |
| `source-tracks/postgresql/getting-started/postgresql-user-capabilities/index.md` | 打开 psql，输入 \\?，屏幕会列出几十个反斜杠命令；输入 \\d 能看表，输入 SELECT version(); 能拿到版本号。这些动作背后是一台正在等你下命令的\"机器\"——但它到底是什么？ | 打开 psql，输入 \?，屏幕会列出几十个反斜杠命令；输入 \d 能看表，输入 SELECT version(); 能拿到版本号。这些动作背后是一台正在等你下命令的"机器"——但它到底是什么？ | ☐ |
| `source-tracks/postgresql/index-and-query/postgresql-vs-sqlserver-partitioning/index.md` | 不管你最终用 PostgreSQL 还是 SQL Server，分区的根本动机都一样：单表太大带来的连锁反应。 | 不管你最终用 PostgreSQL 还是 SQL Server，分区的根本动机都一样：单表太大带来的连锁反应。 | ☐ |
| `source-tracks/postgresql/wal-and-recovery/postgresql-wal-record-types/index.md` | 很多人学 PostgreSQL 都会\"听说过 WAL\"，但真正翻开源码看 WAL 的人很少——因为 WAL 是个\"超长尾\"的子系统：80+ 种记录类型散落在 21 个 RMGR、20+ 个 _xlog.h 头文件里。每一类只占 1~3 个函数，但互相耦合：一条 COMMIT 涉及 5 个… | 很多人学 PostgreSQL 都会"听说过 WAL"，但真正翻开源码看 WAL 的人很少——因为 WAL 是个"超长尾"的子系统：80+ 种记录类型散落在 21 个 RMGR、20+ 个 _xlog.h 头文件里。每一类只占 1~3 个函数，但互相耦合：一条 COMMIT 涉及 5 个… | ☐ |
| `source-tracks/postgresql/extensions-perf/timescaledb-columnstore-deep-dive/index.md` | TimescaleDB 2.10 (2023) 引入了 hypercore columnar storage——把\"行存 + 列存\"在同一张 hypertable 上混合：最近数据行存快速写入，老数据列存压缩查询。这是PG 时序生态里最聪明的 hybrid 引擎。 | TimescaleDB 2.10 (2023) 引入了 hypercore columnar storage——把"行存 + 列存"在同一张 hypertable 上混合：最近数据行存快速写入，老数据列存压缩查询。这是PG 时序生态里最聪明的 hybrid 引擎。 | ☐ |
| `source-tracks/postgresql/extensions-perf/timescaledb-deep-dive/index.md` | 时序数据是 PG 最不擅长的一类：写入密集、范围查询、按时间衰减、聚合占比高。10 年前要写时序就得选 InfluxDB / OpenTSDB。 | 时序数据是 PG 最不擅长的一类：写入密集、范围查询、按时间衰减、聚合占比高。10 年前要写时序就得选 InfluxDB / OpenTSDB。 | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-end-to-end-flow/index.md` | 本文很长，推荐读法： | 本文很长，推荐读法： | ☐ |
| `source-tracks/postgresql/storage-engine/postgresql-memory-management/index.md` | PostgreSQL 启动时申请的 shared_buffers 那一大段内存，其实只是冰山一角。整座数据库的\"内存世界\"由三层拼起来： | PostgreSQL 启动时申请的 shared_buffers 那一大段内存，其实只是冰山一角。整座数据库的"内存世界"由三层拼起来： | ☐ |
| `source-tracks/postgresql/logical-replication/ddl同步架构.md` | 逻辑复制同步 DDL 的整体架构：发布端怎么捕获 DDL、怎么过滤、怎么落到订阅端。 | （没抽出来） | ☐ |
| `source-tracks/postgresql/getting-started/命名空间.md` | 本文档对比主流数据库（PostgreSQL、Oracle、MySQL、SQL Server）的 schema/命名空间机制。 | 本文档对比主流数据库（PostgreSQL、Oracle、MySQL、SQL Server）的 schema/命名空间机制。 | ☐ |
| `source-tracks/postgresql/getting-started/多数据库模式命名空间问题.md` | PostgreSQL 的 search_path 可以设置多个 schema，但其他数据库如 Oracle 的 ALTER SESSION SET CURRENT_SCHEMA = ZXF 只能设置一个。这在一条 SQL 包含多个 schema 的场景下，无法进行直接转换。 | PostgreSQL 的 search_path 可以设置多个 schema，但其他数据库如 Oracle 的 ALTER SESSION SET CURRENT_SCHEMA = ZXF 只能设置一个。这在一条 SQL 包含多个 schema 的场景下，无法进行直接转换。 | ☐ |
| `source-tracks/postgresql/extensions-perf/benchmarksql使用教程.md` | BenchmarkSQL 是一个基于 Java 的数据库基准测试工具，主要用于模拟 TPC-C 规范定义的电商订单处理业务。它通过 JDBC 驱动连接数据库，因此除了 PostgreSQL，也可以通过适配驱动测试其他关系型数据库。 | BenchmarkSQL 是一个基于 Java 的数据库基准测试工具，主要用于模拟 TPC-C 规范定义的电商订单处理业务。它通过 JDBC 驱动连接数据库，因此除了 PostgreSQL，也可以通过适配驱动测试其他关系型数据库。 | ☐ |
| `source-tracks/postgresql/storage-engine/linux-shared-memory/index.md` | 但共享内存没有同步机制(没有锁、没有顺序保证),所以一般要配合 信号量 / futex / eventfd / 自旋锁 一起用。 | 但共享内存没有同步机制(没有锁、没有顺序保证),所以一般要配合 信号量 / futex / eventfd / 自旋锁 一起用。 | ☐ |
| `source-tracks/postgresql/logical-replication/DDL.md` | 数据定义语言（DDL）是SQL（结构化查询语言）的一部分，它用于定义、管理和控制数据库的结构和元素。 | 数据定义语言（DDL）是SQL（结构化查询语言）的一部分，它用于定义、管理和控制数据库的结构和元素。 | ☐ |
| `source-tracks/postgresql/logical-replication/LogLogicalMessage详解.md` | 本文面向需要理解 PostgreSQL 逻辑复制/逻辑解码链路的开发人员，解释 LogLogicalMessage 的定位、内部实现、设计初衷和工程使用方式。 | 本文面向需要理解 PostgreSQL 逻辑复制/逻辑解码链路的开发人员，解释 LogLogicalMessage 的定位、内部实现、设计初衷和工程使用方式。 | ☐ |
| `source-tracks/postgresql/logical-replication/ai逻辑解码.md` | 基于对PolarDB源码和PostgreSQL LogLogicalMessage 机制的分析，以下是DDL自动传输的实现原理详解： | 基于对PolarDB源码和PostgreSQL LogLogicalMessage 机制的分析，以下是DDL自动传输的实现原理详解： | ☐ |
| `source-tracks/postgresql/logical-replication/logical_use.md` | 本文通过实际操作演示 PostgreSQL 15 逻辑复制的完整流程，重点展示： - WAL（Write-Ahead Logging）日志的生成与解析 - LSN（Log Sequence Number）的推进机制 - 事务（Transaction）与 WAL 的关系 - 快照（Snapshot）… | 本文通过实际操作演示 PostgreSQL 15 逻辑复制的完整流程，重点展示： - WAL（Write-Ahead Logging）日志的生成与解析 - LSN（Log Sequence Number）的推进机制 - 事务（Transaction）与 WAL 的关系 - 快照（Snapshot）… | ☐ |
| `source-tracks/postgresql/logical-replication/pg15逻辑复制支持DDL.md` | 那么可以设计一套 “最小侵入内核”的实现方案。我按 接口层 → catalog → WAL → decoding → apply worker → 执行DDL 的完整链路讲清楚。 | 那么可以设计一套 “最小侵入内核”的实现方案。我按 接口层 → catalog → WAL → decoding → apply worker → 执行DDL 的完整链路讲清楚。 | ☐ |
| `source-tracks/postgresql/logical-replication/pglogical.so.md` | pglogical.so是pglogical中的数据库扩展（extension），负责管理复制拓扑、节点、replication set、apply worker 等控制逻辑。 | pglogical.so是pglogical中的数据库扩展（extension），负责管理复制拓扑、节点、replication set、apply worker 等控制逻辑。 | ☐ |
| `source-tracks/postgresql/logical-replication/pglogical支持DDL搭建教程.md` | 使用如下命令初始化数据库： | 使用如下命令初始化数据库： | ☐ |
| `source-tracks/postgresql/logical-replication/指定列同步对逻辑复制支持DDL的影响.md` | 在逻辑复制支持DDL的需求分析中，需要考虑如下场景： | 在逻辑复制支持DDL的需求分析中，需要考虑如下场景： | ☐ |
| `source-tracks/postgresql/logical-replication/支持ddl评审相关问题.md` | 下面进行具体分析 ### 跨事务DDL | 下面进行具体分析 ### 跨事务DDL | ☐ |
| `db/logical_decode/逻辑复制支持DDL开发交付计划.md` | 逻辑复制支持 DDL 的开发交付计划：用户接口、系统表、DDL 捕获与发送、订阅端 apply，以及测试与自验证文档的进度。 | （没抽出来） | ☐ |
| `source-tracks/postgresql/logical-replication/逻辑复制支持DDL需求分析.md` | postgresql当前的逻辑复制仅支持复制DML，不支持复制DDL，需要手动在目标端执行DDL。 | postgresql当前的逻辑复制仅支持复制DML，不支持复制DDL，需要手动在目标端执行DDL。 | ☐ |
| `source-tracks/postgresql/logical-replication/逻辑复制支持ddl问题.md` | 黎哥， 目前apply的流程基本跑通了。但是在做的过程中发现使用新增系统表这种方式总感觉比较奇怪，侵入性修改很严重。 然后后面我又查了下资料和社区的讨论，发现社区之前就预留了写逻辑日志的接口LogLogicalMessage，可以直接利用LogLogicalMessage来写入自定义的wal日志，… | 黎哥， 目前apply的流程基本跑通了。但是在做的过程中发现使用新增系统表这种方式总感觉比较奇怪，侵入性修改很严重。 然后后面我又查了下资料和社区的讨论，发现社区之前就预留了写逻辑日志的接口LogLogicalMessage，可以直接利用LogLogicalMessage来写入自定义的wal日志，… | ☐ |
| `source-tracks/postgresql/logical-replication/逻辑复制源码分析.md` | 逻辑复制与物理复制使用相同的发送框架，都在walsender中进行发送。整体流程大致如下： | 逻辑复制与物理复制使用相同的发送框架，都在walsender中进行发送。整体流程大致如下： | ☐ |
| `source-tracks/postgresql/logical-replication/逻辑复制解惑.md` | 在初次写入数据的时候，ddl写到了系统表，dml先写入日志，然后apply成数据。 当前逻辑复制的原理是根据lsn读取wal日志，将wal日志decode成sql，然后发送目标端。 | 在初次写入数据的时候，ddl写到了系统表，dml先写入日志，然后apply成数据。 当前逻辑复制的原理是根据lsn读取wal日志，将wal日志decode成sql，然后发送目标端。 | ☐ |
| `db/logical_decode/逻辑复制验证步骤.md` | 后续操作都需要切换到dys用户执行。 | 后续操作都需要切换到dys用户执行。 | ☐ |
| `source-tracks/postgresql/logical-replication/逻辑解码ddl replay支持sqlserver模式.md` | 当前 PostgreSQL Logical Replication 仅支持 DML 同步。 | 当前 PostgreSQL Logical Replication 仅支持 DML 同步。 | ☐ |
| `source-tracks/postgresql/logical-replication/ai_coding/ddl_design_improve.md` | 逻辑复制当前仅支持同步DML操作。为了提升用户使用体验和增强逻辑复制功能，需要扩展支持DDL（数据定义语言）的自动同步。 | 逻辑复制当前仅支持同步DML操作。为了提升用户使用体验和增强逻辑复制功能，需要扩展支持DDL（数据定义语言）的自动同步。 | ☐ |
| `source-tracks/postgresql/logical-replication/ai_coding/ddl写入wal日志的影响.md` | 这个问题非常关键，而且是内核方案必须回答清楚的两个核心风险： | 这个问题非常关键，而且是内核方案必须回答清楚的两个核心风险： | ☐ |
| `source-tracks/postgresql/logical-replication/ai_coding/ddl存储生命周期.md` | 可以，下面我直接给你一版接近 PostgreSQL patch 风格的 LogLogicalDDLMessage() 实现草稿。它的设计核心是：复用 PostgreSQL 现有 generic logical decoding message 的 WAL 记录格式与写入路径。现有源码里，xl_lo… | 可以，下面我直接给你一版接近 PostgreSQL patch 风格的 LogLogicalDDLMessage() 实现草稿。它的设计核心是：复用 PostgreSQL 现有 generic logical decoding message 的 WAL 记录格式与写入路径。现有源码里，xl_lo… | ☐ |
| `source-tracks/postgresql/logical-replication/ai_coding/新增逻辑复制同步系统表.md` | 本设计的目标不是实现完整 DDL 自动复制链路，而是先补齐以下两项基础能力： | 本设计的目标不是实现完整 DDL 自动复制链路，而是先补齐以下两项基础能力： | ☐ |
| `source-tracks/postgresql/logical-replication/ai_coding/逻辑复制支持DDLAI提示词.md` | 逻辑复制需要支持自动同步DDL。 | 逻辑复制需要支持自动同步DDL。 | ☐ |
| `source-tracks/postgresql/logical-replication/ai_coding/逻辑复制支持DDL概要设计.md` | PostgreSQL 当前内建逻辑复制主要覆盖表级 DML 复制。logical decoding 的本质是从 WAL 中提取持久化变更，转成更高层可理解的变更流；复制槽保证“按源端发生顺序”向客户端提供变化序列。([PostgreSQL][1]) | PostgreSQL 当前内建逻辑复制主要覆盖表级 DML 复制。logical decoding 的本质是从 WAL 中提取持久化变更，转成更高层可理解的变更流；复制槽保证“按源端发生顺序”向客户端提供变化序列。([PostgreSQL][1]) | ☐ |
| `source-tracks/postgresql/logical-replication/ai_coding/逻辑复制支持ddl ai配置流程.md` | 用 AI 编码实现逻辑复制支持 DDL 的配置流程记录（内容还在整理）。 | （没抽出来） | ☐ |
| `source-tracks/postgresql/logical-replication/ai_coding/逻辑复制支持同步系统表概要设计.md` | 下面给你一份基于 PG18 的“逻辑复制支持系统表同步”完整设计文档（可直接用于研发/评审）。我会严格结合你前面分析的源码链路来设计，重点保证： | 下面给你一份基于 PG18 的“逻辑复制支持系统表同步”完整设计文档（可直接用于研发/评审）。我会严格结合你前面分析的源码链路来设计，重点保证： | ☐ |
| `source-tracks/postgresql/logical-replication/logical_parallel_apply/逻辑复制并行apply依赖冲突检测设计文档.md` | 定义 TWPA 中依赖冲突检测的算法、数据结构、调度策略,包括: | 定义 TWPA 中依赖冲突检测的算法、数据结构、调度策略,包括: | ☐ |
| `source-tracks/postgresql/logical-replication/logical_parallel_apply/逻辑复制并行apply接口文档.md` | 本文档定义 TWPA(Transaction Window Parallel Apply,事务窗口并行 Apply) 用户可见的接口规范,包括: | 本文档定义 TWPA(Transaction Window Parallel Apply,事务窗口并行 Apply) 用户可见的接口规范,包括: | ☐ |
| `source-tracks/postgresql/logical-replication/logical_parallel_apply/逻辑复制并行apply概要设计文档.md` | 定义 TWPA(Transaction Window Parallel Apply)的总体架构、核心数据流、组件交互与状态机。本文不展开: | 定义 TWPA(Transaction Window Parallel Apply)的总体架构、核心数据流、组件交互与状态机。本文不展开: | ☐ |
| `source-tracks/postgresql/logical-replication/pa_decode/概要设计说明书-v2.md` | PostgreSQL 逻辑复制由发布端逻辑解码、逻辑复制协议、网络传输和订阅端逻辑复制应用组成。 | PostgreSQL 逻辑复制由发布端逻辑解码、逻辑复制协议、网络传输和订阅端逻辑复制应用组成。 | ☐ |
| `source-tracks/postgresql/logical-replication/pa_decode/概要设计说明书.md` | 逻辑复制并行解码的核心目的是：通过将发布端的逻辑解码由单进程串行处理改造为多进程并行处理，提高逻辑复制整体同步速率。 | 逻辑复制并行解码的核心目的是：通过将发布端的逻辑解码由单进程串行处理改造为多进程并行处理，提高逻辑复制整体同步速率。 | ☐ |
| `source-tracks/postgresql/logical-replication/pa_decode/逻辑复制发布端现状.md` | 逻辑复制发布端解码运行在一个叫LogicalDecodingContext的上下文里，该上下文主要包含如下几个核心部分： | 逻辑复制发布端解码运行在一个叫LogicalDecodingContext的上下文里，该上下文主要包含如下几个核心部分： | ☐ |
| `source-tracks/postgresql/logical-replication/pglogical详解/index.md` | pglogical 是 PostgreSQL 的拓展模块, 为 PostgreSQL 数据库提供了逻辑流复制发布和订阅的功能。 | pglogical 是 PostgreSQL 的拓展模块, 为 PostgreSQL 数据库提供了逻辑流复制发布和订阅的功能。 | ☐ |
| `source-tracks/postgresql/logical-replication/polardb逻辑解码源码解读/index.md` | 在原生的pg中，逻辑复制只会解析wal日志，而DDL语句是不会生成可解析的逻辑WAL。 | 在原生的pg中，逻辑复制只会解析wal日志，而DDL语句是不会生成可解析的逻辑WAL。 | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql逻辑复制-DML/index.md` | postgresql逻辑复制采用发布者订阅者模式，并且发布者和订阅者之间是多对多的关系。 | postgresql逻辑复制采用发布者订阅者模式，并且发布者和订阅者之间是多对多的关系。 | ☐ |
| `source-tracks/postgresql/logical-replication/逻辑解码/index.md` | 逻辑解码（Logical Decoding）是 PostgreSQL（及其扩展版本）提供的一套机制，用来将 WAL（物理日志）中的数据修改恢复成“逻辑级别”的变更事件： | 逻辑解码（Logical Decoding）是 PostgreSQL（及其扩展版本）提供的一套机制，用来将 WAL（物理日志）中的数据修改恢复成“逻辑级别”的变更事件： | ☐ |
| `source-tracks/postgresql/logical-replication/逻辑解码DDL-Replay框架设计/index.md` | 当前逻辑复制支持DDL同步功能已适配PG模式，其整体流程如下： | 当前逻辑复制支持DDL同步功能已适配PG模式，其整体流程如下： | ☐ |
| `source-tracks/postgresql/logical-replication/逻辑解码支持DDL/index.md` | 逻辑解码需要源端数据库把DDL转换成某一种格式存储，可以是某种数据库语法格式的sql或者其他格式的文本文件，比如json。 | 逻辑解码需要源端数据库把DDL转换成某一种格式存储，可以是某种数据库语法格式的sql或者其他格式的文本文件，比如json。 | ☐ |
| `source-tracks/postgresql/extensions-perf/macos安装mysql.md` | 在 macOS 上用 Homebrew 安装 MySQL 8.4：安装、安全初始化和后台服务启动。 | （没抽出来） | ☐ |
| `source-tracks/postgresql/logical-replication/opengauss-csn-total-ordering/index.md` | CommitSeqNo 是 openGauss 在 src/include/c.h:528 定义的核心类型: | CommitSeqNo 是 openGauss 在 src/include/c.h:528 定义的核心类型: | ☐ |
| `source-tracks/postgresql/logical-replication/opengauss-parallel-decoding-design/index.md` | PG 原版逻辑复制采用单线程顺序解码(参考 ~/cwork/postgresql/src/backend/replication/logical/reorderbuffer.c 5615 行、decode.c 1316 行): | PG 原版逻辑复制采用单线程顺序解码(参考 ~/cwork/postgresql/src/backend/replication/logical/reorderbuffer.c 5615 行、decode.c 1316 行): | ☐ |
| `source-tracks/postgresql/extensions-perf/flame-graph-analysis/index.md` | 火焰图(Flame Graph)是 Brendan Gregg 在 2011 年提出的一种调用栈可视化方式。它把 profiler(perf、async-profiler、bpftrace...)采样的调用栈数据,渲染成一张\"金字塔\": | 火焰图(Flame Graph)是 Brendan Gregg 在 2011 年提出的一种调用栈可视化方式。它把 profiler(perf、async-profiler、bpftrace...)采样的调用栈数据,渲染成一张"金字塔": | ☐ |
| `source-tracks/postgresql/getting-started/part1.md` | 这个代码片段的主要目的是在程序启动时进行一些特定平台的初始化，并保存原始的 argv[] 数组以便在设置进程标题时使用。以下是详细解析： | 这个代码片段的主要目的是在程序启动时进行一些特定平台的初始化，并保存原始的 argv[] 数组以便在设置进程标题时使用。以下是详细解析： | ☐ |
| `source-tracks/postgresql/index-and-query/pg常用函数.md` | 在 PostgreSQL 扩展开发中，DefineCustom*Variable 系列函数用于 注册自定义 GUC（Grand Unified Configuration）参数。 | 在 PostgreSQL 扩展开发中，DefineCustom*Variable 系列函数用于 注册自定义 GUC（Grand Unified Configuration）参数。 | ☐ |
| `source-tracks/postgresql/getting-started/使用meson编译pg.md` | 一般在build目录下进行编译，先生成编译需要文件： | 一般在build目录下进行编译，先生成编译需要文件： | ☐ |
| `source-tracks/postgresql/logical-replication/逻辑复制性能测试.md` | 可以。这里先把范围严格限定为一个独立的 PostgreSQL 逻辑复制 Benchmark Suite，不包含 pg_replication_trace，也不依赖任何自研 PostgreSQL Extension。 | 可以。这里先把范围严格限定为一个独立的 PostgreSQL 逻辑复制 Benchmark Suite，不包含 pg_replication_trace，也不依赖任何自研 PostgreSQL Extension。 | ☐ |
| `source-tracks/postgresql/extensions-perf/postgresql-injection-points-test-unreachable/index.md` | 先理解为什么会存在无法到达的 if 分支: | 先理解为什么会存在无法到达的 if 分支: | ☐ |
| `source-tracks/postgresql/getting-started/learning-path/01-build-and-codebase.md` | PG 18 已默认走 meson。文档与脚本也都在跟进。 | PG 18 已默认走 meson。文档与脚本也都在跟进。 | ☐ |
| `source-tracks/postgresql/getting-started/learning-path/02-process-architecture.md` | 入口：src/backend/main/main.c:main()。 | 入口：src/backend/main/main.c:main()。 | ☐ |
| `source-tracks/postgresql/index-and-query/learning-path/03-query-pipeline.md` | src/backend/tcop/postgres.c:exec_simple_query(const char *query_string) 是简单查询协议（Q 消息）的入口。流程： | src/backend/tcop/postgres.c:exec_simple_query(const char *query_string) 是简单查询协议（Q 消息）的入口。流程： | ☐ |
| `source-tracks/postgresql/storage-engine/learning-path/04-storage-abstraction.md` | 理论上，backend 可以直接 open() / read() / write() 关系文件。但 PG 把这层抽出来有三点好处： | 理论上，backend 可以直接 open() / read() / write() 关系文件。但 PG 把这层抽出来有三点好处： | ☐ |
| `source-tracks/postgresql/storage-engine/learning-path/05-buffer-manager.md` | 整个 buffer pool 用 hash 表 LookupBufHash(tag) -> buf_id 找到候选 buffer，hash 表在 buf_table.c 里。 | 整个 buffer pool 用 hash 表 LookupBufHash(tag) -> buf_id 找到候选 buffer，hash 表在 buf_table.c 里。 | ☐ |
| `source-tracks/postgresql/transaction-mvcc/learning-path/06-heap-and-mvcc.md` | t_xmin 是 创建事务，t_xmax 是 删除/锁事务。当 t_xmax != 0 且对应事务未提交时，tuple 还在；提交后才真正“死掉”。 | t_xmin 是 创建事务，t_xmax 是 删除/锁事务。当 t_xmax != 0 且对应事务未提交时，tuple 还在；提交后才真正“死掉”。 | ☐ |
| `source-tracks/postgresql/index-and-query/learning-path/07-btree-index.md` | PG 的 IndexTuple 是 按需长度，根据 key 个数和大小决定。INDEXTUPLE_SIZE / index_deform_tuple 负责序列化与反序列化。 | PG 的 IndexTuple 是 按需长度，根据 key 个数和大小决定。INDEXTUPLE_SIZE / index_deform_tuple 负责序列化与反序列化。 | ☐ |
| `source-tracks/postgresql/transaction-mvcc/learning-path/08-locks-and-concurrency.md` | src/backend/access/transam/xact.c 维护一个当前 backend 的 MyXactFlags 和状态： | src/backend/access/transam/xact.c 维护一个当前 backend 的 MyXactFlags 和状态： | ☐ |
| `source-tracks/postgresql/wal-and-recovery/learning-path/09-wal-and-recovery.md` | 每个数据页面的修改，必须在写盘前先写 WAL。原因： - crash recovery：磁盘 page 可能落后于内存 page - 流复制：standby 通过 replay WAL 跟上 primary - 时间旅行 / PITR：基础是 WAL 流 | 每个数据页面的修改，必须在写盘前先写 WAL。原因： - crash recovery：磁盘 page 可能落后于内存 page - 流复制：standby 通过 replay WAL 跟上 primary - 时间旅行 / PITR：基础是 WAL 流 | ☐ |
| `source-tracks/postgresql/extensions-perf/learning-path/10-advanced-topics.md` | PG 10+ 是 linear hash（按 bucket 顺序扩展）： | PG 10+ 是 linear hash（按 bucket 顺序扩展）： | ☐ |
| `source-tracks/postgresql/wal-and-recovery/learning-path/11-crash-recovery.md` | PG 的 WAL 只 redo 不 undo。这意味着： - 已 WAL 化的事务 ⇒ 一定要 redo - 未 WAL 化的事务 ⇒ 丢失（即\"提交前 crash\"） - 未提交但已 WAL 化的 ⇒ 通过 clog 标 ABORTED + vacuum 回收 | PG 的 WAL 只 redo 不 undo。这意味着： - 已 WAL 化的事务 ⇒ 一定要 redo - 未 WAL 化的事务 ⇒ 丢失（即"提交前 crash"） - 未提交但已 WAL 化的 ⇒ 通过 clog 标 ABORTED + vacuum 回收 | ☐ |
| `source-tracks/postgresql/replication-ha/learning-path/12-physical-replication.md` | 每个 standby 都： 1. wal receiver 连到 primary（PG 17+ 默认连 5432；早期连单独的 replication 端口） 2. 接收 WAL，流式写到本地 pg_wal 3. startup process replay WAL（与 crash recover… | 每个 standby 都： 1. wal receiver 连到 primary（PG 17+ 默认连 5432；早期连单独的 replication 端口） 2. 接收 WAL，流式写到本地 pg_wal 3. startup process replay WAL（与 crash recover… | ☐ |
| `source-tracks/postgresql/logical-replication/learning-path/13-logical-replication.md` | 物理复制的限制（见 12.11）让逻辑复制成为必然： - 跨大版本：物理格式不兼容（pg_upgrade 也不支持跨多版本）；逻辑只关心 row data - 表级粒度：只想复制某些表 - 异构数据：要把变化同步到 Kafka / Redis / Snowflake - 双向同步：多写模型（log… | 物理复制的限制（见 12.11）让逻辑复制成为必然： - 跨大版本：物理格式不兼容（pg_upgrade 也不支持跨多版本）；逻辑只关心 row data - 表级粒度：只想复制某些表 - 异构数据：要把变化同步到 Kafka / Redis / Snowflake - 双向同步：多写模型（log… | ☐ |
| `source-tracks/postgresql/extensions-perf/learning-path/14-column-store.md` | PG 的设计目标是 通用 OLTP： - 单条 SQL 经常涉及多列 - 高并发更新 - MVCC per-tuple | PG 的设计目标是 通用 OLTP： - 单条 SQL 经常涉及多列 - 高并发更新 - MVCC per-tuple | ☐ |
| `source-tracks/postgresql/logical-replication/pgoutput_change到HeapTupleSatisfiesVisibility调用栈分析/index.md` | 逻辑复制的工作流是一个三层流水线： | 逻辑复制的工作流是一个三层流水线： | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-apply-leader-worker-code-analysis/index.md` | applyparallelworker.c 表面上是一个 1646 行的文件,但里面同时承载了 两套截然不同的角色: | applyparallelworker.c 表面上是一个 1646 行的文件,但里面同时承载了 两套截然不同的角色: | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-apply-parallel-lock-stream/index.md` | 源码位置:src/backend/replication/logical/applyparallelworker.c:1598。 | 源码位置:src/backend/replication/logical/applyparallelworker.c:1598。 | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-apply-parallel-worker/index.md` | PG 16 引入的 streaming=parallel 选项允许单个大事务在 apply 阶段被切分为多个 stream,并行地由多个 worker 进程同时处理,极大加速大事务的同步延迟。 | PG 16 引入的 streaming=parallel 选项允许单个大事务在 apply 阶段被切分为多个 stream,并行地由多个 worker 进程同时处理,极大加速大事务的同步延迟。 | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-apply-parallel-worker-code-analysis/index.md` | 源码位置:src/backend/replication/logical/applyparallelworker.c(1646 行)。 | 源码位置:src/backend/replication/logical/applyparallelworker.c(1646 行)。 | ☐ |
| `source-tracks/postgresql/extensions-perf/postgresql-community-gems/index.md` | PostgreSQL 社区经过 30+ 年沉淀 留下来的精华资源:每一个都经历过时间检验、每一个都在新人邮件列表里被一而再、再而三地引用。我按照\"内核开发者视角\"把它们分类好,每条资源给出: | PostgreSQL 社区经过 30+ 年沉淀 留下来的精华资源:每一个都经历过时间检验、每一个都在新人邮件列表里被一而再、再而三地引用。我按照"内核开发者视角"把它们分类好,每条资源给出: | ☐ |
| `source-tracks/postgresql/replication-ha/postgresql-create-replication-slot-deep-dive/index.md` | CREATE_REPLICATION_SLOT 在 PostgreSQL 中有 两条完全不同的代码路径,使用场景截然不同: | CREATE_REPLICATION_SLOT 在 PostgreSQL 中有 两条完全不同的代码路径,使用场景截然不同: | ☐ |
| `source-tracks/postgresql/extensions-perf/postgresql-flame-graph/index.md` | 性能问题五花八门 ——\"慢\"可能意味着完全不同的东西。先把\"性能\"分清楚: | 性能问题五花八门 ——"慢"可能意味着完全不同的东西。先把"性能"分清楚: | ☐ |
| `source-tracks/postgresql/extensions-perf/postgresql-injection-points/index.md` | Injection Point 是 PG 17/18 强化的 运行时测试钩子(runtime test hook)。它让测试代码可以在内核的 指定代码路径 上,触发 任意自定义回调——而且这一切都在生产代码路径中,零侵入、可移除、可控制。 | Injection Point 是 PG 17/18 强化的 运行时测试钩子(runtime test hook)。它让测试代码可以在内核的 指定代码路径 上,触发 任意自定义回调——而且这一切都在生产代码路径中,零侵入、可移除、可控制。 | ☐ |
| `source-tracks/postgresql/extensions-perf/postgresql-injection-points-test-framework/index.md` | PG 的测试框架是 分层 的,各有侧重: | PG 的测试框架是 分层 的,各有侧重: | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-add-guc/index.md` | PG 的 GUC(Grand Unified Configuration)是 一切配置参数的总称。在内核开发者眼里,一个 GUC 由 5 部分组成: | PG 的 GUC(Grand Unified Configuration)是 一切配置参数的总称。在内核开发者眼里,一个 GUC 由 5 部分组成: | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-apply-parallel-tuning/index.md` | PG 16 引入 streaming=parallel 之后,逻辑复制的吞吐上了一个量级,但随之而来的是大量可调旋钮——开多了打爆内存、抢占锁导致死锁、Worker 池溢出、spill 文件暴涨……这篇文章把 PG 18 上 Apply Parallel Worker(以下简称 PA)涉及的所有可… | PG 16 引入 streaming=parallel 之后,逻辑复制的吞吐上了一个量级,但随之而来的是大量可调旋钮——开多了打爆内存、抢占锁导致死锁、Worker 池溢出、spill 文件暴涨……这篇文章把 PG 18 上 Apply Parallel Worker(以下简称 PA)涉及的所有可… | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-catalog-visibility/index.md` | PostgreSQL 逻辑复制的 catalog 改动如何影响可见性判定，以及 xmin/xmax 是怎么推进的——一篇源码级的全景分析。 | 源码全部基于 PostgreSQL 18 仓库 ~/cwork/postgresql/src(src/backend/{replication/logical,access/heap,access/transam})。所有函数均带 文件:行号 标注,辅助图共 9 张。 | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-end-to-end/index.md` | 逻辑复制的本质是:把 publisher 的 WAL 字节流,通过一系列\"翻译\",变成订阅者能直接 apply 的 SQL 操作流。翻译过程涉及 6 层协作。 | 逻辑复制的本质是:把 publisher 的 WAL 字节流,通过一系列"翻译",变成订阅者能直接 apply 的 SQL 操作流。翻译过程涉及 6 层协作。 | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-lsn-flow/index.md` | 每个 segment 16MB(wal_segment_size,默认)。段文件名编码 LSN 的高地址: - 000000010000000000000003 表示 timeline 1,起始 LSN 0/03000000 | 每个 segment 16MB(wal_segment_size,默认)。段文件名编码 LSN 的高地址: - 000000010000000000000003 表示 timeline 1,起始 LSN 0/03000000 | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-logical-replication-stream-publisher/index.md` | 源码位置:src/backend/utils/misc/guc_tables.c:2604,src/include/replication/reorderbuffer.h:27。 | 源码位置:src/backend/utils/misc/guc_tables.c:2604,src/include/replication/reorderbuffer.h:27。 | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-reorder-buffer-code-analysis/index.md` | PostgreSQL 的逻辑复制链路: | PostgreSQL 的逻辑复制链路: | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-reorderbuffer-c-function-reference/index.md` | 为能读懂本文: - 看完 postgresql-reorder-buffer-code-analysis 这篇 1321 行架构综述,可以建立顶层心智模型 - SnapshotData、pairingheap、HTAB、Slab、GenerationMemoryContext、dlist_*、dc… | 为能读懂本文: - 看完 postgresql-reorder-buffer-code-analysis 这篇 1321 行架构综述,可以建立顶层心智模型 - SnapshotData、pairingheap、HTAB、Slab、GenerationMemoryContext、dlist_*、dc… | ☐ |
| `source-tracks/postgresql/transaction-mvcc/postgresql-row-lock/index.md` | 和其他数据库(InnoDB 的 record lock)不同,PG 的行锁不是一个独立的数据结构,而是建立在 MVCC 多版本之上的\"乐观锁\": | 和其他数据库(InnoDB 的 record lock)不同,PG 的行锁不是一个独立的数据结构,而是建立在 MVCC 多版本之上的"乐观锁": | ☐ |
| `source-tracks/postgresql/storage-engine/postgresql-shared-memory/index.md` | PostgreSQL 是多进程架构:一个 postmaster 守护进程 + N 个 backend 子进程(每个客户端连接一个)。多进程比多线程麻烦的地方在于 —— 进程间内存默认是隔离的,但 PG 有很多状态必须所有进程都看见: | PostgreSQL 是多进程架构:一个 postmaster 守护进程 + N 个 backend 子进程(每个客户端连接一个)。多进程比多线程麻烦的地方在于 —— 进程间内存默认是隔离的,但 PG 有很多状态必须所有进程都看见: | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-snapbuild-deep-dive/index.md` | 逻辑解码的核心矛盾:我们要在 WAL 记录中\"还原\"当时的元组,但元组中的 tid 是 catalog 表的(系统表),而 catalog 表本身也在被并发修改。要读 catalog 的历史版本,只能靠 MVCC 快照。 | 逻辑解码的核心矛盾:我们要在 WAL 记录中"还原"当时的元组,但元组中的 tid 是 catalog 表的(系统表),而 catalog 表本身也在被并发修改。要读 catalog 的历史版本,只能靠 MVCC 快照。 | ☐ |
| `source-tracks/postgresql/logical-replication/postgresql-snapbuild-find-snapshot-deep-dive/index.md` | 由 LogStandbySnapshot()(standby.c:1282)周期生成: - bgwriter 周期 15s(默认) - checkpointer 在 CHECKPOINT 之前 - SnapBuildWaitSnapshot 等老 xid 结束后主动调一次 | 由 LogStandbySnapshot()(standby.c:1282)周期生成: - bgwriter 周期 15s(默认) - checkpointer 在 CHECKPOINT 之前 - SnapBuildWaitSnapshot 等老 xid 结束后主动调一次 | ☐ |
| `source-tracks/postgresql/index-and-query/postgresql-syscache-deep-dive/index.md` | PostgreSQL 内核有几大缓存模块,职责分明: | PostgreSQL 内核有几大缓存模块,职责分明: | ☐ |
| `source-tracks/postgresql/logical-replication/sqlserver/babelfish ddl已知限制.md` | 本文档汇总 Babelfish 插件在 SQL Server 模式下使用逻辑复制 DDL 自动同步时的已知限制，并按客户使用影响给出分级和建议做法。 | 本文档汇总 Babelfish 插件在 SQL Server 模式下使用逻辑复制 DDL 自动同步时的已知限制，并按客户使用影响给出分级和建议做法。 | ☐ |
| `source-tracks/postgresql/logical-replication/sqlserver/bbf创建分区表.md` | 问题原因：逻辑复制同步DDL在sqlserver模式下不支持分区表同步，根本原因为分区表创建依赖于Partition Function 、Partition Scheme，但这两个语句不走PG标准的执行流程（ProcessUtility），无法被捕获。 | 问题原因：逻辑复制同步DDL在sqlserver模式下不支持分区表同步，根本原因为分区表创建依赖于Partition Function 、Partition Scheme，但这两个语句不走PG标准的执行流程（ProcessUtility），无法被捕获。 | ☐ |
| `source-tracks/postgresql/logical-replication/sqlserver/sqlserver模式逻辑复制支持ddl.md` | 当前数据库使用babelfish插件（bbf）来支持sqlserver模式，bbf采用双端口的设计： 即数据库在启动时会监听多个端口，一般是pg原生的端口和tsql端口，比如5432和1433. | 当前数据库使用babelfish插件（bbf）来支持sqlserver模式，bbf采用双端口的设计： 即数据库在启动时会监听多个端口，一般是pg原生的端口和tsql端口，比如5432和1433. | ☐ |
| `source-tracks/postgresql/logical-replication/sqlserver/内核执行babelfish上下文需要考虑的问题.md` | SQL Server 和 PG 本身在数据库架构层面 schema 的含义就不一致： | SQL Server 和 PG 本身在数据库架构层面 schema 的含义就不一致： | ☐ |
| `source-tracks/postgresql/logical-replication/sqlserver/支持逻辑复制同步ddl适配sqlserver方案.md` | Babelfish 是 PostgreSQL 的一个扩展，通过双端口设计支持 SQL Server 协议： | Babelfish 是 PostgreSQL 的一个扩展，通过双端口设计支持 SQL Server 协议： | ☐ |
| `source-tracks/postgresql/logical-replication/sqlserver/逻辑复制同步ddl适配bbf面临的挑战.md` | 逻辑复制同步 DDL 适配 Babelfish（SQL Server 模式）时遇到的能力边界问题，以及为什么需要把需求拆开。 | （没抽出来） | ☐ |
| `source-tracks/postgresql/extensions-perf/taos基本使用.md` | taos是一个开源的时序数据库，目前发展势头较好，走的开源路线。 | taos是一个开源的时序数据库，目前发展势头较好，走的开源路线。 | ☐ |
| `engineering/containers/docker compose管理容器.md` | 使用docker-compose部署code-server容器开发环境。 | 使用docker-compose部署code-server容器开发环境。 | ☐ |
| `engineering/containers/docker_communication_with_host.md` | docker中的进程要与宿主机使用共享内存通信，需要在启动容器的时候指定<font color=\"red\">“--ipc=host”</font>选项。然后再编写相应的共享内存的程序，一个跑在宿主机上，另一个跑在docker上面。 | docker中的进程要与宿主机使用共享内存通信，需要在启动容器的时候指定<font color="red">“--ipc=host”</font>选项。然后再编写相应的共享内存的程序，一个跑在宿主机上，另一个跑在docker上面。 | ☐ |
| `engineering/containers/docker基础指北.md` | docker的实现主要依赖于linux内核提供的如下功能： | docker的实现主要依赖于linux内核提供的如下功能： | ☐ |
| `engineering/containers/docker安装talebook.md` | 官方Github： https://github.com/talebook/talebook | 官方Github： https://github.com/talebook/talebook | ☐ |
| `engineering/containers/docker容器权限设置--cap-add  --cap-drop  privileged - 进击的davis - 博客园.md` | Dcoker容器在使用的过程中，默认的docker run时都是以普通方式启动的，有的时候是需要使用在容器中使用iptables进行启动的，没有使用iptables的权限，那么怎样才能在容器中使用iptables呢？要如何开启权限呢？ | Dcoker容器在使用的过程中，默认的docker run时都是以普通方式启动的，有的时候是需要使用在容器中使用iptables进行启动的，没有使用iptables的权限，那么怎样才能在容器中使用iptables呢？要如何开启权限呢？ | ☐ |
| `engineering/containers/docker搭建C语言开发环境.md` | 无网络环境下使用本地文件作为基础镜像： | 无网络环境下使用本地文件作为基础镜像： | ☐ |
| `engineering/containers/docker搭建个人镜像仓库.md` | docker-compose.yml的内容如下： | docker-compose.yml的内容如下： | ☐ |
| `engineering/containers/docker设置容器独立ip.md` | 在linux要设置容器或者其他虚拟机独立ip，需要如下步骤： | 在linux要设置容器或者其他虚拟机独立ip，需要如下步骤： | ☐ |
| `engineering/containers/kali搭建docker.md` | 在 Kali Linux 上搭建 Docker 的过程记录：更新软件源、安装 Docker 并验证是否成功。 | 查看一下是否安装成功 | ☐ |
| `engineering/containers/使用github作为docker镜像存储仓库.md` | docker因为其便利性和隔离性已经成为日常开发中非常常见的技术，使用docker可以把我们的编译开发环境打包，在任何机器上只要把docker镜像来取下来运行，不需要重复搭建编译开发环境。 | docker因为其便利性和隔离性已经成为日常开发中非常常见的技术，使用docker可以把我们的编译开发环境打包，在任何机器上只要把docker镜像来取下来运行，不需要重复搭建编译开发环境。 | ☐ |
| `docker/docker与宿主机共享内存通信/index.md` | docker中的进程要与宿主机使用共享内存通信，需要在启动容器的时候指定<font color=\"red\">“--ipc=host”</font>选项。然后再编写相应的共享内存的程序，一个跑在宿主机上，另一个跑在docker上面。 | docker中的进程要与宿主机使用共享内存通信，需要在启动容器的时候指定<font color="red">“--ipc=host”</font>选项。然后再编写相应的共享内存的程序，一个跑在宿主机上，另一个跑在docker上面。 | ☐ |
| `dpdk/day1.md` | VFIO是一个可以安全的把设备I/O、中断、DMA等暴露到用户空间（userspace），从而可以在用户空间完成设备驱动的框架。用户空间直接设备访问，虚拟机设备分配可以获得更高的IO性能。 | VFIO是一个可以安全的把设备I/O、中断、DMA等暴露到用户空间（userspace），从而可以在用户空间完成设备驱动的框架。用户空间直接设备访问，虚拟机设备分配可以获得更高的IO性能。 | ☐ |
| `dpdk/dpdk之kni使用.md` | 和igb uio模块一样，kni模块分成内核以及用户态代码，内核模块在编译出来之后为rte_kni.ko，首先插入内核，dpdk提供了一个用户态的例子。首先看下kni内核模块代码,在kni_misc.c中，ko代码入口为 | 和igb uio模块一样，kni模块分成内核以及用户态代码，内核模块在编译出来之后为rte_kni.ko，首先插入内核，dpdk提供了一个用户态的例子。首先看下kni内核模块代码,在kni_misc.c中，ko代码入口为 | ☐ |
| `dpdk/dpdk常用接口指北.md` | 基于dpdk18.11版本，其他版本注意区别。 | 基于dpdk18.11版本，其他版本注意区别。 | ☐ |
| `dpdk/dpdk无锁队列实现.md` | rte_ring是dpdk内部提供的一种无锁队列实现。 | rte_ring是dpdk内部提供的一种无锁队列实现。 | ☐ |
| `dpdk/fastupkni功能测试.md` | scl保持多版本gcc兼容，并支持切换gcc版本进行编译。 | scl保持多版本gcc兼容，并支持切换gcc版本进行编译。 | ☐ |
| `dpdk/fastup时间规划.md` | fastup测试优化具体划分为如下步骤： | fastup测试优化具体划分为如下步骤： | ☐ |
| `dpdk/fastup模拟UE测试.md` | 先在同一个docker上启动模拟phy和模拟UE，同时抓下一个全流程的包，后续用于pktgen打流回放。 | 先在同一个docker上启动模拟phy和模拟UE，同时抓下一个全流程的包，后续用于pktgen打流回放。 | ☐ |
| `dpdk/fastup测试优化完成情况.md` | fastup 性能测试与优化的进度表：每项任务的计划用时、实际完成时间与完成情况。 | （没抽出来） | ☐ |
| `dpdk/linux大页内存.md` | HugePages是通过使用大页内存来取代传统的4kb内存页面，使得管理虚拟地址数变少，加快了从虚拟地址到物理地址的映射以及通过摒弃内存页面的换入换出以提高内存的整体性能。 | HugePages是通过使用大页内存来取代传统的4kb内存页面，使得管理虚拟地址数变少，加快了从虚拟地址到物理地址的映射以及通过摒弃内存页面的换入换出以提高内存的整体性能。 | ☐ |
| `dpdk/nxp运行vpp.md` | 运行成功，但存在如下报错： | 运行成功，但存在如下报错： | ☐ |
| `dpdk/pktgen.md` | DPDK 的 pktgen 怎么用：拉源码、按 x86 与 arm64-dpaa2 两套环境编译，以及把脚本和二进制部署到目标板子。 | （没抽出来） | ☐ |
| `dpdk/pktgen编译使用.md` | pktgen 的编译步骤：x86 与 arm 两条交叉编译链路的环境变量与 make config 用法。 | （没抽出来） | ☐ |
| `dpdk/ptpclient.md` | ptpclient 的功能边界：目前实现了哪些 PTP 能力，以及基站设备侧和完整功能各自要求什么。 | （没抽出来） | ☐ |
| `dpdk/vpp.md` | VPP(Vector Packet Processing )(向量包处理)库。 | VPP(Vector Packet Processing )(向量包处理)库。 | ☐ |
| `dpdk/vpp与dpdk的关系.md` | dpdk作为vpp的一个插件，主要用来从网卡收发包。 | dpdk作为vpp的一个插件，主要用来从网卡收发包。 | ☐ |
| `dpdk/vpp使用.md` | vpp通过文件读取配置，通过-c指定文件名称读取。 | vpp通过文件读取配置，通过-c指定文件名称读取。 | ☐ |
| `dpdk/vpp使用kni.md` | 在dpdk插件的main.c通过判断/dev/kni是否存在来确定rte_kni模块是否加载。 | 在dpdk插件的main.c通过判断/dev/kni是否存在来确定rte_kni模块是否加载。 | ☐ |
| `dpdk/vpp插件开发.md` | vpp 插件开发笔记（内容还在整理）。 | （没抽出来） | ☐ |
| `dpdk/交叉编译.md` | 交叉编译实践：以 gdb 为例，从 x86 编到 arm32/arm64 的 configure 参数怎么写。 | （没抽出来） | ☐ |
| `dpdk/抓包.md` | 编译完成后在arm64-dpaa-linuxapp-gcc目录下生成库和二进制。 | 编译完成后在arm64-dpaa-linuxapp-gcc目录下生成库和二进制。 | ☐ |
| `dpdk/dpdk相关/index.md` | DPDK全称为Date planedevelopment kit，是一个用来进行包数据处理加速的软件库 | DPDK全称为Date planedevelopment kit，是一个用来进行包数据处理加速的软件库 | ☐ |
| `dpdk/fastup测试报告/index.md` | 需要使用专门的交叉工具编译，交叉编译工具文件为fsl-qoriq-glibc-x86_64-fsl-toolchain-aarch64-toolchain-2.5.sh，使用如下命令安装： | 需要使用专门的交叉工具编译，交叉编译工具文件为fsl-qoriq-glibc-x86_64-fsl-toolchain-aarch64-toolchain-2.5.sh，使用如下命令安装： | ☐ |
| `dpdk/l3fwd/index.md` | 核心网（x86机器）使用pktgen发包到nxpls2160（arm机器），nxp通过dpdk l3fwd进行转发。 | 核心网（x86机器）使用pktgen发包到nxpls2160（arm机器），nxp通过dpdk l3fwd进行转发。 | ☐ |
| `dpdk/lx2160使用dpdk/index.md` | 底层驱动同事负责在操作系统启动的时候同时启动网卡，其中dpni.3为对外的10G网卡，是我们需要使用的网卡。 | 底层驱动同事负责在操作系统启动的时候同时启动网卡，其中dpni.3为对外的10G网卡，是我们需要使用的网卡。 | ☐ |
| `dpdk/nxp测试报告/index.md` | 测试验证fastup在nxp2160 10G网口上的收发包能力。 | 测试验证fastup在nxp2160 10G网口上的收发包能力。 | ☐ |
| `dpdk/用户态驱动-UIOVFIO/index.md` | 硬件设备可以根据功能分为网络设备，块设备，字符设备，或者根据与CPU相连的方式分为PCI设备，USB设备等。它们被不同的内核子系统支持。这些标准的设备的驱动编写较为容易而且容易维护。很容易加入主内核源码树。但是，又有很多设备难以划分到这些子系统中，比如I/O卡，现场总线接口或者定制的FPGA。 | 硬件设备可以根据功能分为网络设备，块设备，字符设备，或者根据与CPU相连的方式分为PCI设备，USB设备等。它们被不同的内核子系统支持。这些标准的设备的驱动编写较为容易而且容易维护。很容易加入主内核源码树。但是，又有很多设备难以划分到这些子系统中，比如I/O卡，现场总线接口或者定制的FPGA。 | ☐ |
| `engineering/engineering-practice/docusaurus文档编译为pdf.md` | docusaurus是一个基于markdown的现代化文档框架，可以基于makrdown编写产品的手册并发布。 | docusaurus是一个基于markdown的现代化文档框架，可以基于makrdown编写产品的手册并发布。 | ☐ |
| `engineering/engineering-practice/docusaurus自定义渲染内容.md` | 使用docusaurus编写文档时，docusaurus仅支持编译成网页，在编译成pdf时需要做一些特殊处理。 | 使用docusaurus编写文档时，docusaurus仅支持编译成网页，在编译成pdf时需要做一些特殊处理。 | ☐ |
| `engineering/engineering-practice/texlive安装.md` | TeX Live 的安装步骤：下载 iso、挂载、安装以及配置环境变量。 | （没抽出来） | ☐ |
| `edit/pandoc自定义过滤器/index.md` | pandoc是一个强大的文本转换工具，可以实现各种文本格式的互相转换。 | pandoc是一个强大的文本转换工具，可以实现各种文本格式的互相转换。 | ☐ |
| `engineering/web-and-frontend/Search UI with Elasticsearch  Elastic docs --- 使用 Elasticsearch 的搜索用户界面 弹性文档.md` | Elasticsearch connector for Search UI is currently in technical preview status. It is not ready for production use. 适用于搜索 UI 的 Elasticsearch 连接器目前处于技… | Elasticsearch connector for Search UI is currently in technical preview status. It is not ready for production use. 适用于搜索 UI 的 Elasticsearch 连接器目前处于技… | ☐ |
| `engineering/web-and-frontend/es_search_ui.md` | 用 ElasticSearch、FSCrawler 和 SearchUI 搭建文件搜索引擎：从需求分析到运行测试的完整步骤。 | ©著作权归作者所有：来自51CTO博客作者zhuhuix的原创作品，请联系作者获取转载授权，否则将追究法律责任 | ☐ |
| `engineering/web-and-frontend/oh-my-search.md` | 使用elasticsearch和search-ui搭建自己的搜索引擎，快速查找资源和文件。如果对代码感兴趣，相关代码已在github上开源，欢迎fork代码。 | 使用elasticsearch和search-ui搭建自己的搜索引擎，快速查找资源和文件。如果对代码感兴趣，相关代码已在github上开源，欢迎fork代码。 | ☐ |
| `engineering/web-and-frontend/手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎.md` | 用 ElasticSearch、FSCrawler 和 SearchUI 搭建文件搜索引擎：从需求分析到运行测试的完整步骤。 | ©著作权归作者所有：来自51CTO博客作者zhuhuix的原创作品，请联系作者获取转载授权，否则将追究法律责任 | ☐ |
| `engineering/cheatsheets/faq汇总.md` | 开发中遇到的零碎问题与解法汇总，比如 git status 里中文文件名乱码怎么解决。 | （没抽出来） | ☐ |
| `engineering/web-and-frontend/go_web.md` | Go Web 开发笔记：用 gin 框架写 REST API，以及 cors 中间件解决跨域问题的配置。 | https://github.com/gin-contrib/cors | ☐ |
| `engineering/foundations/C语言内存使用血与泪教训.md` | C 语言内存管理的教训：malloc 的正确用法、常见的内存错误，以及写 C 时必须遵守的原则。 | malloc函数原型返回值为void*， | ☐ |
| `engineering/foundations/autoconf使用.md` | 使用autoconf的最终目的是生成能够根据不同系统生成Makefile的configure文件，一般情况下我们需要准备如下内容： | 使用autoconf的最终目的是生成能够根据不同系统生成Makefile的configure文件，一般情况下我们需要准备如下内容： | ☐ |
| `engineering/foundations/cmake使用指南.md` | CMake 使用指南：常用变量、list 的操作，以及添加库、可执行程序、头文件路径和链接库的写法。 | （没抽出来） | ☐ |
| `engineering/foundations/c语言变长数组.md` | C99支持变长数组，定义时可以不指定数组长度，分配时再根据实际长度进行分配。 | C99支持变长数组，定义时可以不指定数组长度，分配时再根据实际长度进行分配。 | ☐ |
| `engineering/foundations/如何阅读autotool管理的C语言项目.md` | autotool管理C语言项目的流程请参考autoconf使用. | autotool管理C语言项目的流程请参考autoconf使用. | ☐ |
| `engineering/foundations/程序基本构造.md` | 程序的目的就是等待输入，进行处理，完成后输出。 | 程序的目的就是等待输入，进行处理，完成后输出。 | ☐ |
| `engineering/foundations/词法分析与语法分析教程.md` | 在如下网址下载flex和bison，安装后将其bin目录配置到环境变量，在shell中能正确使用这两个命令表示配置成功。 | 在如下网址下载flex和bison，安装后将其bin目录配置到环境变量，在shell中能正确使用这两个命令表示配置成功。 | ☐ |
| `engineering/foundations/软件质量.md` | 软件质量分为内在质量和外在质量。 | 软件质量分为内在质量和外在质量。 | ☐ |
| `engineering/foundations/python/pytest自动化测试.md` | 用 pytest 写自动化测试：yaml 配置文件的语法规则，以及测试用例的组织方式。 | 使用如下命令下载安装： | ☐ |
| `engineering/foundations/python/python爬虫教程.md` | 可以使用fake_useragent构建user-agent。 | 可以使用fake_useragent构建user-agent。 | ☐ |
| `engineering/foundations/python/python跨平台下载离线安装包.md` | 以allure-pytest为例 | 以allure-pytest为例 | ☐ |
| `engineering/foundations/python/uv管理python.md` | 首先需要安装 uv 工具： 1. 在 Linux/macOS 上安装 | 首先需要安装 uv 工具： 1. 在 Linux/macOS 上安装 | ☐ |
| `engineering/foundations/python/pytest/pytest进阶.md` | pytest 的进阶用法：fixture、allure 报告，以及与命令行交互的方式。 | （没抽出来） | ☐ |
| `engineering/foundations/rust/rust设计原则.md` | Rust 的设计原则：没有 GC、所有权、借用，以及同一生命周期内只能有一个可变借用。 | （没抽出来） | ☐ |
| `engineering/foundations/rust/使用mdbook编译html和pdf.md` | 往book.toml里添加如下内容： | 往book.toml里添加如下内容： | ☐ |
| `engineering/foundations/rust/搭建内网rust仓库.md` | 此时会在项目目录下生成vendor目录，里面存放了相关依赖。 | 此时会在项目目录下生成vendor目录，里面存放了相关依赖。 | ☐ |
| `life/aiv/index.md` | 这条线要解决的问题只有一个： | 这条线要解决的问题只有一个： | ☐ |
| `life/aiv/人格规范.md` | Growdu 是小象，也是这个站点的作者。本文规定他是谁、怎么想、怎么讲。 | Growdu 是小象，也是这个站点的作者。本文规定他是谁、怎么想、怎么讲。 | ☐ |
| `life/aiv/形象与音色规范.md` | 后续视频统一使用这套「模型形象」与「音色」。本文记录规范本身（入库、可评审）， 图像与音频成品留本机（character/、voice/，不入库）。 | 后续视频统一使用这套「模型形象」与「音色」。本文记录规范本身（入库、可评审）， 图像与音频成品留本机（character/、voice/，不入库）。 | ☐ |
| `life/aiv/背景音乐规范.md` | 后续系列视频统一用这套背景音乐。本文记录规则本身（入库、可评审）， 音乐成品留本机（music/tracks/，不入库），授权台账入库（music/library.json）。 | 后续系列视频统一用这套背景音乐。本文记录规则本身（入库、可评审）， 音乐成品留本机（music/tracks/，不入库），授权台账入库（music/library.json）。 | ☐ |
| `life/aiv/brand/README.md` | Growdu 专属的两支品牌片：片头 Growdu 字标 + 数据库标语；片尾 感谢观看 + 落版三胶囊。 两支都是 2.833 秒（68 帧 @ 24fps），都在 3 秒上限内，都带 growdu 小象形象。 | Growdu 专属的两支品牌片：片头 Growdu 字标 + 数据库标语；片尾 感谢观看 + 落版三胶囊。 两支都是 2.833 秒（68 帧 @ 24fps），都在 3 秒上限内，都带 growdu 小象形象。 | ☐ |
| `life/aiv/brand/scripts/README.md` | 需要 FFmpeg（7.x 或兼容版本）、Python 3（cairo / numpy / Pillow / scipy）。 | 需要 FFmpeg（7.x 或兼容版本）、Python 3（cairo / numpy / Pillow / scipy）。 | ☐ |
| `life/aiv/character/README.md` | 后续视频统一使用的讲解者形象。规范见 ../形象与音色规范.md。 | 后续视频统一使用的讲解者形象。规范见 ../形象与音色规范.md。 | ☐ |
| `life/aiv/music/README.md` | 曲库下载的背景音乐放这里，音频不入库（媒体产物留本机）， 授权台账入库（library.json）——台账是事实，不是产物。 | 曲库下载的背景音乐放这里，音频不入库（媒体产物留本机）， 授权台账入库（library.json）——台账是事实，不是产物。 | ☐ |
| `life/aiv/voice/README.md` | 后续视频旁白统一使用这套音色。规范见 ../形象与音色规范.md §2。 | 后续视频旁白统一使用这套音色。规范见 ../形象与音色规范.md §2。 | ☐ |
| `life/blog-to-wechat/index.md` | 改造之前，得先承认一件事：这个博客的发布链路已经是一条完整的 CI 流水线，不是\"手动 hexo g\"。搞清楚了这一点，才知道该往哪里接。 | 改造之前，得先承认一件事：这个博客的发布链路已经是一条完整的 CI 流水线，不是"手动 hexo g"。搞清楚了这一点，才知道该往哪里接。 | ☐ |
| `life/daxue/电子科技大学-计算机-自考-复习计划/index.md` | 你的核心约束（先把这些写死）： | 你的核心约束（先把这些写死）： | ☐ |
| `life/daxue/腾冲事业编-公务员备考计划/index.md` | ❌ 慎报：外交部、商务部、中央办公厅（400:1） | ❌ 慎报：外交部、商务部、中央办公厅（400:1） | ☐ |
| `life/doctor_test/寻康杯备战方案.md` | 关键结构判断：70% 的分在沙盘里，且必须进前 8 名才有资格打答辩分。 答辩满分救不了沙盘失分——沙盘排不进前 8，30% 直接归零。优先级必须是沙盘 >> 答辩。 | 关键结构判断：70% 的分在沙盘里，且必须进前 8 名才有资格打答辩分。 答辩满分救不了沙盘失分——沙盘排不进前 8，30% 直接归零。优先级必须是沙盘 >> 答辩。 | ☐ |
| `life/doctor_test/寻康杯实战操作手册.md` | 三人三系统 = 结构性地互相看不见对方在干什么。佘山社区案例里已经验证过：健管端单方面上激进减重，医院端照旧开促泌剂，五期后三人低血糖、指数断崖。 | 三人三系统 = 结构性地互相看不见对方在干什么。佘山社区案例里已经验证过：健管端单方面上激进减重，医院端照旧开促泌剂，五期后三人低血糖、指数断崖。 | ☐ |
| `life/gaokao/biology-methods/index.md` | 生物是再选科目，走等级赋分——和化学同一套规则。 | 生物是再选科目，走等级赋分——和化学同一套规则。 | ☐ |
| `life/gaokao/chemistry-methods/index.md` | 化学、生物、思想政治、地理是再选科目，成绩按等级赋分计入总分： | 化学、生物、思想政治、地理是再选科目，成绩按等级赋分计入总分： | ☐ |
| `life/gaokao/english-roots/index.md` | 以新高考卷结构为例（满分 150 分）： | 以新高考卷结构为例（满分 150 分）： | ☐ |
| `life/gaokao/geography-methods/index.md` | 选择 48 分考的是读图与定位：从等高线、剖面图、流程图、坐标图里抠出信息，判断「是什么、在哪里、为什么」。 | 选择 48 分考的是读图与定位：从等高线、剖面图、流程图、坐标图里抠出信息，判断「是什么、在哪里、为什么」。 | ☐ |
| `life/gaokao/math-methods/index.md` | \"中等水平\"不是一个统一的人，三种中等生的提分路径完全不同。先做诊断，再选方法，否则会用错力气。 | "中等水平"不是一个统一的人，三种中等生的提分路径完全不同。先做诊断，再选方法，否则会用错力气。 | ☐ |
| `life/gaokao/math-paper2/index.md` | 2026 全国二卷，19 题，150 分，120 分钟： | 2026 全国二卷，19 题，150 分，120 分钟： | ☐ |
| `life/gaokao/physics-methods/index.md` | 这是本篇最重要的一句话，不理解它，后面的方法全是隔靴搔痒。 | 这是本篇最重要的一句话，不理解它，后面的方法全是隔靴搔痒。 | ☐ |
| `life/gaokao/politics-methods/index.md` | 数学要算、物理要算、化学要配平、生物要写遗传图解、地理要算数——政治一分都不用算。这意味着它的每一个失分点，都只能由「表达」来解释。别的科失分你会说「我算错了」「我没想到」，政治失分你只能承认一件事：我没把答案写成它要的那个样子。 | 数学要算、物理要算、化学要配平、生物要写遗传图解、地理要算数——政治一分都不用算。这意味着它的每一个失分点，都只能由「表达」来解释。别的科失分你会说「我算错了」「我没想到」，政治失分你只能承认一件事：我没把答案写成它要的那个样子。 | ☐ |
| `life/gaokao/yunnan-apply/index.md` | 大多数考生把\"报考\"理解成一道题：我考了多少分，能上哪所学校。这个模型漏掉了至少一半的变量。真实的报考是三笔账同时结算。 | 大多数考生把"报考"理解成一道题：我考了多少分，能上哪所学校。这个模型漏掉了至少一半的变量。真实的报考是三笔账同时结算。 | ☐ |
| `life/gaokao/yunnan-policy/index.md` | 把每门再选科目全体考生的原始分从高到低排序，划成 5 个等级，按比例分配人数，再线性转换到分数区间： | 把每门再选科目全体考生的原始分从高到低排序，划成 5 个等级，按比例分配人数，再线性转换到分数区间： | ☐ |
| `life/hometown/家中对联.md` | 年少时只知山是山，水是水。 出去久了才知道，山不是山，水不是水。 挣扎过后才明白，山还是山，水还是水。 | 年少时只知山是山，水是水。 出去久了才知道，山不是山，水不是水。 挣扎过后才明白，山还是山，水还是水。 | ☐ |
| `life/road/00-intro.md` | growdu 的编程之路：从 C 语言、数学建模竞赛，到阅读、文本自动化提取、DPDK/VPP 和分布式系统。 | 关于growdu本人。 | ☐ |
| `life/road/01-how_to_learn_program.md` | 编程是信息科学，处理对象是抽象出来的数据； 编程是抽象科学，处理对象是前辈已经抽象好的数据； 编程是解决问题的科学，分为两步： | 编程是信息科学，处理对象是抽象出来的数据； 编程是抽象科学，处理对象是前辈已经抽象好的数据； 编程是解决问题的科学，分为两步： | ☐ |
| `life/road/02-elevate_thinking.md` | 不是那种\"我没天赋\"的慢，而是那种——明明每天都花了不少时间，回头一看，发现自己其实还在原地打转的慢。 | 不是那种"我没天赋"的慢，而是那种——明明每天都花了不少时间，回头一看，发现自己其实还在原地打转的慢。 | ☐ |
| `life/road/左耳朵耗子的话——关于技术的一些思考.md` | 昨天，一整天都不开心。朋友圈里，几乎每翻一屏，都能看到有人在转左耳朵耗子离世的消息。作为一名创造者，左耳朵耗子为这个世界留下了很多作品，比如他的博客 CoolShell、他的极客时间专栏左耳听风，以及他的公司 MegaEase。感慨世事无常的同时，我也在回忆，左耳朵耗子讲过的那些有分量的话。 | 昨天，一整天都不开心。朋友圈里，几乎每翻一屏，都能看到有人在转左耳朵耗子离世的消息。作为一名创造者，左耳朵耗子为这个世界留下了很多作品，比如他的博客 CoolShell、他的极客时间专栏左耳听风，以及他的公司 MegaEase。感慨世事无常的同时，我也在回忆，左耳朵耗子讲过的那些有分量的话。 | ☐ |
| `life/shehui/area.md` | 自建房玻璃窗户面积汇总：每扇窗的长宽数量与面积换算，公式是面积(cm²) = 长 × 宽 × 数量。 | （没抽出来） | ☐ |
| `life/shehui/zhuangxiu.md` | 装修款项统计：材料费、油漆、雕刻、玻璃、木工工钱等各项开销的明细。 | （没抽出来） | ☐ |
| `life/shehui/economic-downturn-deep-dive/index.md` | 写经济分析不是我的专业。写内核才是。 | 写经济分析不是我的专业。写内核才是。 | ☐ |
| `life/shehui/economic-downturn-strategy/index.md` | 我不想预测 GDP 明年是 4.2% 还是 3.8%，那种精确度是假的。我只说我能观察到的结构。 | 我不想预测 GDP 明年是 4.2% 还是 3.8%，那种精确度是假的。我只说我能观察到的结构。 | ☐ |
| `life/shehui/media-account/index.md` | 运营的第一步不是\"我想做什么内容\"，是把已有的东西数一遍。很多人做自媒体失败在第一步就错了——从零想选题，结果想出来的东西和自己已有的 100 篇文档毫无关系，做不到 50 篇就放弃了。 | 运营的第一步不是"我想做什么内容"，是把已有的东西数一遍。很多人做自媒体失败在第一步就错了——从零想选题，结果想出来的东西和自己已有的 100 篇文档毫无关系，做不到 50 篇就放弃了。 | ☐ |
| `life/shehui/self-host/index.md` | 原文最有价值的不是那 28 个服务清单，而是他反复强调的 4 条判断原则。清单会过时，原则不会。 | 原文最有价值的不是那 28 个服务清单，而是他反复强调的 4 条判断原则。清单会过时，原则不会。 | ☐ |
| `source-tracks/linux/networking/C语言网络编程库选择.md` | C 语言网络编程库怎么选：libqb、libevent、libcurl、libev、libuv 各自的定位。 | （没抽出来） | ☐ |
| `source-tracks/linux/networking/mtu路径发现pmtu详解.md` | 路径 MTU 发现的详解（内容还在整理）。 | （没抽出来） | ☐ |
| `source-tracks/linux/networking/pmtu概述.md` | Path MTU 简述：PMTU 是什么、PMTU 发现机制怎么工作，以及它对报文传输（尤其是 GRE 隧道叠加）的影响。 | 发表于 2017-12-19 更新于 2019-04-17 分类于 c 评论数： 0 Comments | ☐ |
| `source-tracks/linux/networking/【网络】MTU相关网络丢包问题分析处理.md` | MTU 与 MSS 的概念辨析，以及线上遇到 MTU 导致的网络丢包问题该怎么分析和处理。 | MTU是数据链路层的概念，限制的是数据链路层payload的大小，即上层协议大小(包括上层协议头) | ☐ |
| `source-tracks/linux/networking/从原理到实践，彻底告别 IPv6 上网不稳定的问题.md` | 开了 IPv6 之后，家里网络跟着变慢：网页有时加载很慢甚至打不开，视频卡顿，手机 App 也不流畅。把 IPv6 关掉，一切又正常。装宽带的师傅给的建议是「IPv6 不成熟，关掉吧」。 | 开了 IPv6 之后，家里网络跟着变慢：网页有时加载很慢甚至打不开，视频卡顿，手机 App 也不流畅。把 IPv6 关掉，一切又正常。装宽带的师傅给的建议是「IPv6 不成熟，关掉吧」。 | ☐ |
| `source-tracks/linux/networking/如何安装Shadowsocks 影梭.md` | Shadowsocks 中文名称影梭，是一个跨平台软件、基于 Apache 许可证的开放源代码软件，用于保护网络流量、加密数据传输。 | Shadowsocks 中文名称影梭，是一个跨平台软件、基于 Apache 许可证的开放源代码软件，用于保护网络流量、加密数据传输。 | ☐ |
| `source-tracks/linux/networking/网络编程注意事项.md` | 当我们使用原生socket编程时，需要自己处理send/recv的行为，需要自己定义超时，并管理链路的生命周期。 | 当我们使用原生socket编程时，需要自己处理send/recv的行为，需要自己定义超时，并管理链路的生命周期。 | ☐ |
| `source-tracks/linux/networking/vpn/MonoCloudios使用教程.md` | Rule-Based：常规代理模式，会依据代理规则进行分流代理，除国内 IP 都会走代理进行连接。 | Rule-Based：常规代理模式，会依据代理规则进行分流代理，除国内 IP 都会走代理进行连接。 | ☐ |
| `source-tracks/linux/networking/vpn/MonoCloud安卓使用教程.md` | 请注意，知识库内提供的客户端版本可能不是最新的，且我们只提供了 arm64-v8a 版本（适用于目前市面上的绝大多数 Android 设备），若上述客户端不适合您的手机使用或者我们提供的文件版本较旧您需要更新的版本，可以在 Clash For Android 官方项目页内找到最新的最全版本的安装包… | 请注意，知识库内提供的客户端版本可能不是最新的，且我们只提供了 arm64-v8a 版本（适用于目前市面上的绝大多数 Android 设备），若上述客户端不适合您的手机使用或者我们提供的文件版本较旧您需要更新的版本，可以在 Clash For Android 官方项目页内找到最新的最全版本的安装包… | ☐ |
| `engineering/engineering-practice/opc.md` | 继续开发完善，边实现过程记录到code.md，需要记录设计决策、偏离、权衡和待确认问题。 | 继续开发完善，边实现过程记录到code.md，需要记录设计决策、偏离、权衡和待确认问题。 | ☐ |
| `distributed/consensus/opengauss dcf搭建 - 墨天轮.md` | openGauss 的搭建记录：不用 om 工具安装，以及 DCF 集群的 iplist、端口和数据目录怎么配。 | （没抽出来） | ☐ |
| `distributed/consensus/openguass dcf启动详解.md` | dcf收到消息处理函数如下： | dcf收到消息处理函数如下： | ☐ |
| `distributed/consensus/openguass升级机制.md` | openGauss 的升级机制：集群配置文件 cluster_config.xml 里都有哪些参数。 | （没抽出来） | ☐ |
| `distributed/consensus/openguass架构详解.md` | openguass从postgresql演化而来，最主要的区别为：openguass是多线程架构，postgresql是多进程架构。除此而外，openguass还支持paxos分布式一致性协议。 | openguass从postgresql演化而来，最主要的区别为：openguass是多线程架构，postgresql是多进程架构。除此而外，openguass还支持paxos分布式一致性协议。 | ☐ |
| `engineering/cheatsheets/Csharp.md` | sender最终会被转换为触发该事件的控件。 | sender最终会被转换为触发该事件的控件。 | ☐ |
| `engineering/cheatsheets/devExpress.md` | 对于各种控件的使用，需掌握以下几点： | 对于各种控件的使用，需掌握以下几点： | ☐ |
| `engineering/cheatsheets/gui.md` | 在 Ubuntu 上换主题和图标的步骤：下载主题与图标，再放进 /usr/share/themes 和 /usr/share/icons。 | （没抽出来） | ☐ |
| `engineering/foundations/how-to-learn-program.md` | 基础是指一些计算机基础知识，如计算机组成原理、数据结构、操作系统、C语言等基础知识。 | 基础是指一些计算机基础知识，如计算机组成原理、数据结构、操作系统、C语言等基础知识。 | ☐ |
| `engineering/cheatsheets/java.md` | 在Java中，final关键字可以用来修饰类、方法和变量（包括成员变量和局部变量）。 | 在Java中，final关键字可以用来修饰类、方法和变量（包括成员变量和局部变量）。 | ☐ |
| `engineering/cheatsheets/pdf-coordinate.md` | 一个变换矩阵指定了2个坐标空间之间的关系。通过修改变换矩阵，对象可以缩放、旋转、平移等等。 | 一个变换矩阵指定了2个坐标空间之间的关系。通过修改变换矩阵，对象可以缩放、旋转、平移等等。 | ☐ |
| `engineering/cheatsheets/pdf.md` | 按照PDF格式规范的规定，内嵌字体可以采用自己的编码，这个编码可以与常规字符编码不一样。 而在复制、另存为文本的时候，需要能够将自定义编码转换成Unciode，才能正常复制、另存为，否则直接用自己的编码，到了别的程序后就是所谓的“乱码”。 | 按照PDF格式规范的规定，内嵌字体可以采用自己的编码，这个编码可以与常规字符编码不一样。 而在复制、另存为文本的时候，需要能够将自定义编码转换成Unciode，才能正常复制、另存为，否则直接用自己的编码，到了别的程序后就是所谓的“乱码”。 | ☐ |
| `engineering/cheatsheets/pdfParse.md` | 根据坐标来判断表格，主要是根据坐标的对应关系，而坐标的对应关系最终落实在单元格起始和结束。 | 根据坐标来判断表格，主要是根据坐标的对应关系，而坐标的对应关系最终落实在单元格起始和结束。 | ☐ |
| `engineering/cheatsheets/python.md` | Find path the pip install package uses follow code: | Find path the pip install package uses follow code: | ☐ |
| `engineering/cheatsheets/read-pdfbox-source-code.md` | pdfbox 源码阅读笔记（内容还在整理）。 | （没抽出来） | ☐ |
| `engineering/cheatsheets/regexp.md` | 普通字符包括没有显式指定为元字符的所有可打印和不可打印字符。这包括所有大写和小写字母、所有数字、所有标点符号和一些其他符号。 | 普通字符包括没有显式指定为元字符的所有可打印和不可打印字符。这包括所有大写和小写字母、所有数字、所有标点符号和一些其他符号。 | ☐ |
| `engineering/cheatsheets/ssh.md` | ssh is remote connect tools which has rsa and dsa. | ssh is remote connect tools which has rsa and dsa. | ☐ |
| `source-tracks/postgresql/wal-and-recovery/PostgreSQL 时间线解析.md` | “时间线”（Timeline）是PG一个很有特色的概念，在备份恢复方面的文档里面时有出现。但针对这个概念的详细解释却很少，也让人不太好理解。我们在此仔细解析一下。 | “时间线”（Timeline）是PG一个很有特色的概念，在备份恢复方面的文档里面时有出现。但针对这个概念的详细解释却很少，也让人不太好理解。我们在此仔细解析一下。 | ☐ |
| `source-tracks/postgresql/getting-started/Postgres中postmaster代码解析(--boot和--single).md` | 之前我的一些文章都是在说Postgres的一些查询相关的代码。但是对于Postgres服务端是如何启动，后台进程是如何加载，服务端在哪里以及如何监听客户端的连接都没有一个清晰的逻辑。那么今天我来说说Postgres中的postmaster模块的代码，试着解答这些问题。 | 之前我的一些文章都是在说Postgres的一些查询相关的代码。但是对于Postgres服务端是如何启动，后台进程是如何加载，服务端在哪里以及如何监听客户端的连接都没有一个清晰的逻辑。那么今天我来说说Postgres中的postmaster模块的代码，试着解答这些问题。 | ☐ |
| `source-tracks/postgresql/wal-and-recovery/checkpoint机制浅析.md` | 上一篇《WAL 机制浅析》简单介绍了 PostgreSQL 中的 WAL 机制，其中讲到创建 checkpoint 会触发刷新 xlog 日志页到磁盘。本文接着讲 checkpoint 机制本身。 | 上一篇《WAL 机制浅析》简单介绍了 PostgreSQL 中的 WAL 机制，其中讲到创建 checkpoint 会触发刷新 xlog 日志页到磁盘。本文接着讲 checkpoint 机制本身。 | ☐ |
| `source-tracks/postgresql/index-and-query/insert_data.md` | 一条数据插入的流程如下： | 一条数据插入的流程如下： | ☐ |
| `source-tracks/postgresql/getting-started/pg_complie_and_run.md` | 若要编译调试版本的话，先执行如下命令： | 若要编译调试版本的话，先执行如下命令： | ☐ |
| `source-tracks/postgresql/extensions-perf/pg_io_调优.md` | 检查点是数据库的关键行为，同时也是IO敏感的；其保证了数据库的一致性状态，定期执行检查点是很重要的，确保数据变化持久保存到磁盘中并且数据库的状态是一致的。不当的检查点配置会导致IO性能问题。我们需要关注检查点的配置，确保没有任何IO的尖刺(这同样也取决于磁盘性能的好坏，以及数据文件的组织)。 | 检查点是数据库的关键行为，同时也是IO敏感的；其保证了数据库的一致性状态，定期执行检查点是很重要的，确保数据变化持久保存到磁盘中并且数据库的状态是一致的。不当的检查点配置会导致IO性能问题。我们需要关注检查点的配置，确保没有任何IO的尖刺(这同样也取决于磁盘性能的好坏，以及数据文件的组织)。 | ☐ |
| `source-tracks/postgresql/replication-ha/pg_replication.md` | 逻辑复制是将数据重新执行一次insert、update或delete。逻辑复制则允许在数据层面复制，并在安全性上提供更细粒度的控制。 | 逻辑复制是将数据重新执行一次insert、update或delete。逻辑复制则允许在数据层面复制，并在安全性上提供更细粒度的控制。 | ☐ |
| `source-tracks/postgresql/getting-started/pgsql_main_structure.md` | pgsql采用C/S架构（客户端/服务端）模式。应用层通过INET或者Unix Socket利用既定的协议与数据库服务器进行通信。 | pgsql采用C/S架构（客户端/服务端）模式。应用层通过INET或者Unix Socket利用既定的协议与数据库服务器进行通信。 | ☐ |
| `source-tracks/postgresql/storage-engine/pg源码对象管理.md` | pg中对于xlog、buffer等均采用全局变量的方式进行管理。 | pg中对于xlog、buffer等均采用全局变量的方式进行管理。 | ☐ |
| `source-tracks/postgresql/replication-ha/postgresql——流复制和wal日志（八）.md` | PostgreSQL通过wal日志来传送的方式有两种：基于文件的日志传送和流复制。 不同于基于文件的日志传送，流复制的关键在于“流”，所谓流，就是没有界限的一串数据，类似于合理的水流，是连成一片的。因此流复制允许一台后备服务器比使用基于文件的日志传送更能保持为最新的状态。 比如我们有一个大文件要从… | PostgreSQL通过wal日志来传送的方式有两种：基于文件的日志传送和流复制。 不同于基于文件的日志传送，流复制的关键在于“流”，所谓流，就是没有界限的一串数据，类似于合理的水流，是连成一片的。因此流复制允许一台后备服务器比使用基于文件的日志传送更能保持为最新的状态。 比如我们有一个大文件要从… | ☐ |
| `source-tracks/postgresql/getting-started/postgresql启动流程.md` | postgresql数据库在启动之前需要先初始化数据库目录，创建目录文件和模板。 | postgresql数据库在启动之前需要先初始化数据库目录，创建目录文件和模板。 | ☐ |
| `source-tracks/postgresql/getting-started/postgresql基操.md` | 对于客户端来说，通过库-->表-->sql的方式操作数据。 | 对于客户端来说，通过库-->表-->sql的方式操作数据。 | ☐ |
| `source-tracks/postgresql/getting-started/postgresql源码编译.md` | PostgreSQL 源码编译：拉源码、装依赖（icu、readline、zlib、bison、flex）到 configure、make、make install。 | （没抽出来） | ☐ |
| `source-tracks/postgresql/extensions-perf/sql_test.md` | TPC(事务处理性能委员会：Transaction Processing Performance Council)，是由数 10 家会员公司创建的非盈利组织，总部设在美国。TPC 的主要成员是计算机软硬件厂家，其主要成员包括 IBM，HP，Oracle，Microsoft 等。TPC 的功能是制定… | TPC(事务处理性能委员会：Transaction Processing Performance Council)，是由数 10 家会员公司创建的非盈利组织，总部设在美国。TPC 的主要成员是计算机软硬件厂家，其主要成员包括 IBM，HP，Oracle，Microsoft 等。TPC 的功能是制定… | ☐ |
| `source-tracks/postgresql/wal-and-recovery/wal机制浅析.md` | WAL即 Write-Ahead Logging，是一种实现事务日志的标准方法。WAL 的中心思想是先写日志，再写数据，数据文件的修改必须发生在这些修改已经记录在日志文件中之后。采用WAL日志的数据库系统在事务提交时，WAL机制可以从两个方面来提高性能： | WAL即 Write-Ahead Logging，是一种实现事务日志的标准方法。WAL 的中心思想是先写日志，再写数据，数据文件的修改必须发生在这些修改已经记录在日志文件中之后。采用WAL日志的数据库系统在事务提交时，WAL机制可以从两个方面来提高性能： | ☐ |
| `source-tracks/postgresql/wal-and-recovery/数据库崩溃恢复.md` | 为了合并I/O提高性能，PostgreSQL数据库引入了共享缓冲区，当数据库非正常关闭，比如服务器断电时，共享缓冲区即内存中的数据就会丢失，这个时候数据库操作系统重启时就需要从非正常状态中恢复过来，继续提供服务。本文将具体分析在这种情况下，PostgreSQL数据库如何从崩溃状态中恢复。 | 为了合并I/O提高性能，PostgreSQL数据库引入了共享缓冲区，当数据库非正常关闭，比如服务器断电时，共享缓冲区即内存中的数据就会丢失，这个时候数据库操作系统重启时就需要从非正常状态中恢复过来，继续提供服务。本文将具体分析在这种情况下，PostgreSQL数据库如何从崩溃状态中恢复。 | ☐ |
| `source-tracks/postgresql/getting-started/code-server调试postgresql.md` | 用 code-server 在容器里搭建 PostgreSQL 的远程调试环境。 | 从这里下载插件安装。 | ☐ |
| `source-tracks/postgresql/index-and-query/PostgreSQL的insert语句执行过程分析 - 墨天轮.md` | 用 gdb 断点演示一条 insert 语句在 PostgreSQL 里的完整执行流程：解析、执行计划，到真正写进堆文件。 | 首页 / PostgreSQL的insert语句执行过程分析 | ☐ |
| `source-tracks/postgresql/extensions-perf/pgsql扩展.md` | pg提供了扩展机制可以在不动postgresql源代码的情况下，增强postgresql的一些功能。 | pg提供了扩展机制可以在不动postgresql源代码的情况下，增强postgresql的一些功能。 | ☐ |
| `source-tracks/postgresql/replication-ha/repmgr实现原理.md` | repmgr分为三部分，其主要功能如下： | repmgr分为三部分，其主要功能如下： | ☐ |
| `source-tracks/postgresql/index-and-query/Postgresql触发器详解.md` | 触发器（Trigger）是与表相关联的一种数据库对象，它可以在特定的表上定义，以在表上执行自定义的操作。 当指定的事件（如插入、更新或删除）发生时，触发器会自动触发，并执行预定义的操作。 | 触发器（Trigger）是与表相关联的一种数据库对象，它可以在特定的表上定义，以在表上执行自定义的操作。 当指定的事件（如插入、更新或删除）发生时，触发器会自动触发，并执行预定义的操作。 | ☐ |
| `source-tracks/postgresql/getting-started/meson-pg/index.md` | PostgreSQL 自 16 起把构建系统从 autotools 迁到了 Meson + Ninja。如果你还在用 ./configure && make，新版本会直接劝退——configure 文件已经没了。这一篇把\"用 Meson 把 PostgreSQL 17/18 源码变成可用二进制、… | PostgreSQL 自 16 起把构建系统从 autotools 迁到了 Meson + Ninja。如果你还在用 ./configure && make，新版本会直接劝退——configure 文件已经没了。这一篇把"用 Meson 把 PostgreSQL 17/18 源码变成可用二进制、… | ☐ |
| `source-tracks/postgresql/getting-started/initdb.md` | 可以看到，initdb最终会调用postgres来初始化数据库。 | 可以看到，initdb最终会调用postgres来初始化数据库。 | ☐ |
| `source-tracks/postgresql/getting-started/pg_ctl.md` | 用 gdb 跟踪 pg_ctl 启停 PostgreSQL 的过程：fork 出来的子进程里发生了什么。 | （没抽出来） | ☐ |
| `source-tracks/postgresql/wal-and-recovery/BgWriter.md` | Bgwriter是一个Background Writer进程的简称，Bgwriter会定时将缓存中一些已经更改的数据(脏缓冲区)写入到磁盘。 | Bgwriter是一个Background Writer进程的简称，Bgwriter会定时将缓存中一些已经更改的数据(脏缓冲区)写入到磁盘。 | ☐ |
| `source-tracks/postgresql/wal-and-recovery/Checkpoint.md` | PostgreSQL 的检查点机制笔记（内容还在整理）。 | （没抽出来） | ☐ |
| `source-tracks/postgresql/wal-and-recovery/WalWriter.md` | 预写式日志WAL机制是对数据文件的修改必须是只能发生在这些修改已经记录到日志之后，即先写日志再写数据。 | 预写式日志WAL机制是对数据文件的修改必须是只能发生在这些修改已经记录到日志之后，即先写日志再写数据。 | ☐ |
| `source-tracks/postgresql/replication-ha/PostgreSQL 同步流复制原理和代码浅析-阿里云开发者社区.md` | 数据库ACID里面的D，持久化。 指的是对于用户来说提交的事务，数据是可靠的，即使数据库crash了，在硬件完好的情况下，也能恢复回来。 PostgreSQL是怎么做到的呢，看一幅图，画得比较丑，凑合看吧。 假设一个事务，对数据库做了一些操作，并且产生了一些脏数据，首先这些脏数据会在数据库的sha… | 数据库ACID里面的D，持久化。 指的是对于用户来说提交的事务，数据是可靠的，即使数据库crash了，在硬件完好的情况下，也能恢复回来。 PostgreSQL是怎么做到的呢，看一幅图，画得比较丑，凑合看吧。 假设一个事务，对数据库做了一些操作，并且产生了一些脏数据，首先这些脏数据会在数据库的sha… | ☐ |
| `source-tracks/postgresql/replication-ha/PostgreSQL复制槽实操.md` | 看下官网的解释，复制槽提供了一种办法确保主库不会“删除”还未发送到备库的WAL日志，也不会删除备库需要的多版本，即使备库掉线。 | 看下官网的解释，复制槽提供了一种办法确保主库不会“删除”还未发送到备库的WAL日志，也不会删除备库需要的多版本，即使备库掉线。 | ☐ |
| `source-tracks/postgresql/replication-ha/PostgreSQL数据库复制——后台一等公民进程WalReceiver&startup交互_postgressql walreceive线程_肥叔菌的博客-CSDN博客.md` | walsender进程是用来发送WAL日志记录的，执行顺序如下： | walsender进程是用来发送WAL日志记录的，执行顺序如下： | ☐ |
| `source-tracks/postgresql/replication-ha/PostgreSQL的后台进程walsender分析 - 关系型数据库 - 亿速云.md` | 这篇文章主要介绍“PostgreSQL的后台进程walsender分析”，在日常操作中，相信很多人在PostgreSQL的后台进程walsender分析问题上存在疑惑，小编查阅了各式资料，整理出简单好用的操作方法，希望对大家解答”PostgreSQL的后台进程walsender分析”的疑惑有所帮助… | 这篇文章主要介绍“PostgreSQL的后台进程walsender分析”，在日常操作中，相信很多人在PostgreSQL的后台进程walsender分析问题上存在疑惑，小编查阅了各式资料，整理出简单好用的操作方法，希望对大家解答”PostgreSQL的后台进程walsender分析”的疑惑有所帮助… | ☐ |
| `source-tracks/postgresql/replication-ha/docker搭建Postgresql主备集群.md` | docker-compose.yaml配置文件如下： | docker-compose.yaml配置文件如下： | ☐ |
| `source-tracks/postgresql/replication-ha/pg_logic_decode.md` | pg_logical_decode 笔记：逻辑解码的接口与实现（内容还在整理）。 | （没抽出来） | ☐ |
| `source-tracks/postgresql/replication-ha/pg_replication_keepalive.md` | 在当前流复制过程中，当walreceiver进程在收到大量数据报文时会出现walsender因keepalive心跳报文超时而导致流复制断开。 | 在当前流复制过程中，当walreceiver进程在收到大量数据报文时会出现walsender因keepalive心跳报文超时而导致流复制断开。 | ☐ |
| `source-tracks/postgresql/replication-ha/pg_slot.md` | pg_slot 笔记：复制槽的类型与生命周期（内容还在整理）。 | （没抽出来） | ☐ |
| `source-tracks/postgresql/replication-ha/pg_walreceiver.md` | wal_receiver整体流程由三层循环组成，第一层循环使用launch机制，第二层和第三层则使用for(;;)实现。 | wal_receiver整体流程由三层循环组成，第一层循环使用launch机制，第二层和第三层则使用for(;;)实现。 | ☐ |
| `source-tracks/postgresql/replication-ha/pg_walsender.md` | walsender分析分为两部分， | walsender分析分为两部分， | ☐ |
| `source-tracks/postgresql/replication-ha/postgresql startup处理 - postgresql内核分析 - SegmentFault 思否.md` | 本文主要介绍postgresql 的startup处理流程。startup发生在一个client连接server端时，server与client建立连接，并创建对应的backend process。后续就可以进行正常的消息交互了。 | 本文主要介绍postgresql 的startup处理流程。startup发生在一个client连接server端时，server与client建立连接，并创建对应的backend process。后续就可以进行正常的消息交互了。 | ☐ |
| `source-tracks/postgresql/replication-ha/postgresql流复制同异步分析.md` | postgresql流复制主要是四个进程的交互。 | postgresql流复制主要是四个进程的交互。 | ☐ |
| `source-tracks/postgresql/replication-ha/详解完整恢复及基于时间点的恢复.md` | 使用pause的目的是恢复到最想要的位置。当确定已恢复到最想要的位置，可以使用pg_wal_replay_resume()结束暂停的状态，这会让恢复终结。如果恢复的位置不是想要的，那么关闭服务器，重新设置恢复目标，然后启动DB继续恢复。 | 使用pause的目的是恢复到最想要的位置。当确定已恢复到最想要的位置，可以使用pg_wal_replay_resume()结束暂停的状态，这会让恢复终结。如果恢复的位置不是想要的，那么关闭服务器，重新设置恢复目标，然后启动DB继续恢复。 | ☐ |
| `source-tracks/postgresql/replication-ha/Postgresql存储、索引及系统优化、主备切换/index.md` | 本文讲三件事：数据在磁盘上长什么样（存储结构）、索引怎么选、系统层面怎么调，最后落到主备集群怎么搭、怎么切。 | 本文讲三件事：数据在磁盘上长什么样（存储结构）、索引怎么选、系统层面怎么调，最后落到主备集群怎么搭、怎么切。 | ☐ |
| `source-tracks/postgresql/replication-ha/repmgr_cluster.md` | 检查pg是否安装，主要看pg_config在不在$PATH下面。 | 检查pg是否安装，主要看pg_config在不在$PATH下面。 | ☐ |
| `source-tracks/postgresql/replication-ha/pgsql_repmgr/index.md` | repmgr用于管理 PostgreSQL 服务器集群内的复制和故障转移。repmgr 支持并增强了 PostgreSQL 的内置流复制，它提供了一个单一的读/写主服务器和一个或多个只读备用服务器。 | repmgr用于管理 PostgreSQL 服务器集群内的复制和故障转移。repmgr 支持并增强了 PostgreSQL 的内置流复制，它提供了一个单一的读/写主服务器和一个或多个只读备用服务器。 | ☐ |
| `source-tracks/postgresql/index-and-query/stats.md` | PostgreSQL 统计信息相关的参数与视图：stats_temp_directory、pg_stat_activity、pg_stat_replication、pg_stat_wal_receiver 等。 | （没抽出来） | ☐ |
| `source-tracks/postgresql/storage-engine/PosgreSQL FSM文件解析 – 蛋挞.md` | 由于PostgreSQL使用的MVCC机制，导致对同一张表的不断更新会产生大量空闲空间（free space），在插入tuple之前优先现在之前的空闲空间是个较好的选择。 | 由于PostgreSQL使用的MVCC机制，导致对同一张表的不断更新会产生大量空闲空间（free space），在插入tuple之前优先现在之前的空闲空间是个较好的选择。 | ☐ |
| `source-tracks/postgresql/wal-and-recovery/pg_checksum.md` | pg在将数据写入磁盘时才会进行checksum的计算写入。 | pg在将数据写入磁盘时才会进行checksum的计算写入。 | ☐ |
| `source-tracks/postgresql/storage-engine/pgsql_storage.md` | 包括共享内存、本地内存、内存上下文、缓冲区的管理。 | 包括共享内存、本地内存、内存上下文、缓冲区的管理。 | ☐ |
| `source-tracks/postgresql/storage-engine/pg共享内存.md` | PostgreSQL 共享内存：PGShmemHeader 的结构，以及共享内存段的创建与切分。 | （没抽出来） | ☐ |
| `source-tracks/postgresql/wal-and-recovery/xlog.md` | xlog 笔记：XLogCtlData 全局变量，以及 XLogwrtRqst/XLogwrtResult 这组写入与刷新的状态结构。 | （没抽出来） | ☐ |
| `source-tracks/postgresql/storage-engine/干货  PostgreSQL数据表文件底层结构布局分析 - 知乎.md` | PostgreSQL提供了可靠、稳定、有序的数据存储、检索管理。即使在不知道其背后运行原理的情况下，也没有多大关系，因为我们只需要按部就班地执行建库、建表然后插入数据结构这几个流程，就可以如愿以偿地实现将我们的数据持久化于PostgreSQL数据库中。于是我们不得不好奇，这些数据最终落盘于磁盘上的… | PostgreSQL提供了可靠、稳定、有序的数据存储、检索管理。即使在不知道其背后运行原理的情况下，也没有多大关系，因为我们只需要按部就班地执行建库、建表然后插入数据结构这几个流程，就可以如愿以偿地实现将我们的数据持久化于PostgreSQL数据库中。于是我们不得不好奇，这些数据最终落盘于磁盘上的… | ☐ |
| `source-tracks/postgresql/storage-engine/file/pgsql_page.md` | 文件是数据库的持久化存储，当然我们已经知道数据库的relation以文件的形式存在在磁盘上，无论是xxx文件还是xxx_fsm,还是xxx_vm，这是文件的概念。 当relation的xxx的文件特别大，超过1G的时候，同一个relation还会分文件存储，出现xxx.1，xxx.2这种文件。 所… | 文件是数据库的持久化存储，当然我们已经知道数据库的relation以文件的形式存在在磁盘上，无论是xxx文件还是xxx_fsm,还是xxx_vm，这是文件的概念。 当relation的xxx的文件特别大，超过1G的时候，同一个relation还会分文件存储，出现xxx.1，xxx.2这种文件。 所… | ☐ |
| `source-tracks/postgresql/wal-and-recovery/full_page_writes/index.md` | 数据库保证数据库完整性（解决块折断问题）当前主要有如下三种方式： | 数据库保证数据库完整性（解决块折断问题）当前主要有如下三种方式： | ☐ |
| `source-tracks/postgresql/storage-engine/mm/pg_page.md` | pg_page 笔记：数据页的结构（内容还在整理）。 | （没抽出来） | ☐ |
| `source-tracks/postgresql/storage-engine/mm/pgsql内存管理.md` | page是一段内存的指针，pageheaderData是page内存最前面的数据,pageheader是指向pageheaderData的指针。 | page是一段内存的指针，pageheaderData是page内存最前面的数据,pageheader是指向pageheaderData的指针。 | ☐ |
| `programmer_self_cultivation/linux生成coredump.md` | 可以看到本机未开启core dump。执行如下命令开启，并且不限制core文件大小。 | 可以看到本机未开启core dump。执行如下命令开启，并且不限制core文件大小。 | ☐ |
| `protocol/fib表.md` | fib（forward info base）转发表。 | fib（forward info base）转发表。 | ☐ |
| `protocol/ip分片.md` | IP 分片：IPv4 报文结构里标识、标志、片偏移这三个字段怎么协同完成分片与重组。 | （没抽出来） | ☐ |
| `protocol/protobuf实现rpc.md` | Protocol Buffers (protobuf) 是Google开发的一种高效的数据序列化格式，常被用于RPC（远程过程调用）系统中。 | Protocol Buffers (protobuf) 是Google开发的一种高效的数据序列化格式，常被用于RPC（远程过程调用）系统中。 | ☐ |
| `protocol/抓包进阶.md` | 当单个文件报文个数过多时，打开和查询报文缓慢。可以使用wireshark相关工具对其进行拆分。 | 当单个文件报文个数过多时，打开和查询报文缓慢。可以使用wireshark相关工具对其进行拆分。 | ☐ |
| `protocol/nginx/nginx基本原理.md` | nginx由内核和模块组成，nginx接收到请求时，通过查找配置文件将此次请求映射到一个location block。 | nginx由内核和模块组成，nginx接收到请求时，通过查找配置文件将此次请求映射到一个location block。 | ☐ |
| `protocol/otel/opentelemetry详解.md` | OpenTelemetry（简称 OTel） 是一个开源的可观测性（Observability）标准与工具集，用于统一采集、传输和导出应用的 Trace（链路追踪）、Metric（指标）、Log（日志） 数据。 | OpenTelemetry（简称 OTel） 是一个开源的可观测性（Observability）标准与工具集，用于统一采集、传输和导出应用的 Trace（链路追踪）、Metric（指标）、Log（日志） 数据。 | ☐ |
| `protocol/otel/postgresql可视化观测平台.md` | 使用 OpenTelemetry 实现 Trace + Metrics + Logs → Tempo + Prometheus + Loki → Grafana的全链路可观测平台。 | 使用 OpenTelemetry 实现 Trace + Metrics + Logs → Tempo + Prometheus + Loki → Grafana的全链路可观测平台。 | ☐ |
| `protocol/otel/rust使用opel将trace数据导入tempo.md` | 修改Cargo.toml,将其内容修改如下： | 修改Cargo.toml,将其内容修改如下： | ☐ |
| `protocol/tcp/tcp socket必知必会.md` | TCP socket 必知必会：阻塞与非阻塞、串行与并行、select/poll/epoll，以及 SO_REUSEADDR 和 SO_LINGER。 | （没抽出来） | ☐ |
| `protocol/tcp/tcp重建链.md` | 在tcp链路中，当网络异常时，缩短tcp超时时间一般有如下方法： | 在tcp链路中，当网络异常时，缩短tcp超时时间一般有如下方法： | ☐ |
| `protocol/tcp/tcp的user_timeout与keepalive的关系与生效机制/index.md` | 当tcp流中有数据交互时，tcp流不会进入keepalive，此时的超时主要受tcp_user_timeout影响。数据包被发送后未接收到ACK确认的达到tcp_user_timeout时会断开连接。tcp_user_timeout以毫秒为单位，例如设置为10000时，代表如果发送出去的数据包在十… | 当tcp流中有数据交互时，tcp流不会进入keepalive，此时的超时主要受tcp_user_timeout影响。数据包被发送后未接收到ACK确认的达到tcp_user_timeout时会断开连接。tcp_user_timeout以毫秒为单位，例如设置为10000时，代表如果发送出去的数据包在十… | ☐ |
| `stock/A股股票筛选规则.md` | 选股不是单条规则，而是由粗到细的漏斗，建议按以下顺序逐层过滤： | 选股不是单条规则，而是由粗到细的漏斗，建议按以下顺序逐层过滤： | ☐ |
| `storage/nfs详解.md` | NFS是Network File System的缩写，即网络文件系统，是一种使用于分散式文件系统的协定。功能是通过网络让不同的机器、不同的操作系统能够彼此分享个别的数据，让应用程序在客户端通过网络访问位于服务器磁盘中的数据，是在类Unix系统间实现磁盘文件共享的一种方法。 | NFS是Network File System的缩写，即网络文件系统，是一种使用于分散式文件系统的协定。功能是通过网络让不同的机器、不同的操作系统能够彼此分享个别的数据，让应用程序在客户端通过网络访问位于服务器磁盘中的数据，是在类Unix系统间实现磁盘文件共享的一种方法。 | ☐ |
| `storage/samba服务深度定制.md` | 在 Windows 7 中，您可以通过修改注册表来指定 Samba 服务器的端口。 | 在 Windows 7 中，您可以通过修改注册表来指定 Samba 服务器的端口。 | ☐ |
| `storage/sshfs-win精讲.md` | sshfs-win 精讲笔记（内容还在整理）。 | （没抽出来） | ☐ |
| `storage/win10实现非标（非445）端口访问samba服务_smb服务能使用其他端口吗-CSDN博客.md` | 在 Windows 10 上访问使用非标准端口的 Samba 服务：为什么默认的 445 端口用不了，以及该怎么配置。 | 糖果墙 于 2023-11-14 01:58:11 发布 | ☐ |
| `storage/windows的139、445端口到底在做什么.md` | NBT 协议（NetBIOS over TCP/IP）是一种用于在 TCP/IP 网络上实现 NetBIOS 服务的协议。 NBT使用137（UDP）、138（UDP）和139（TCP）来实现基于TCP/IP的NETBIOS网际互联。 而139端口的作用就是获得NETBIOS/SMB服务（即Net… | NBT 协议（NetBIOS over TCP/IP）是一种用于在 TCP/IP 网络上实现 NetBIOS 服务的协议。 NBT使用137（UDP）、138（UDP）和139（TCP）来实现基于TCP/IP的NETBIOS网际互联。 而139端口的作用就是获得NETBIOS/SMB服务（即Net… | ☐ |
| `engineering/web-and-frontend/15 个提高 Google 搜索效率的小技巧 - 少数派.md` | 为了得到更加「多元化」的搜索结果，虽然 Google 目前访问起来并不是那么方便，但是仍然有很多人把它作为常用搜索引擎在使用。 | 为了得到更加「多元化」的搜索结果，虽然 Google 目前访问起来并不是那么方便，但是仍然有很多人把它作为常用搜索引擎在使用。 | ☐ |
| `engineering/containers/Jellyfin+Kodi打造个人媒体中心.md` | 「一台7×24小时运行的电脑可以用来做什么？」系列第二篇。作为一个数字收集癖和整理癖患者，从十几年前在VeryCD上用迅雷慢慢下载TLF组的奥斯卡全集，几KB的速度下几周，到现在对比不同的压制组作品的质量，千兆的网络压得磁盘跟不上下载速度，硬盘容量存不下想要收藏的电影。回望过去，观看的速度永远跟不… | 「一台7×24小时运行的电脑可以用来做什么？」系列第二篇。作为一个数字收集癖和整理癖患者，从十几年前在VeryCD上用迅雷慢慢下载TLF组的奥斯卡全集，几KB的速度下几周，到现在对比不同的压制组作品的质量，千兆的网络压得磁盘跟不上下载速度，硬盘容量存不下想要收藏的电影。回望过去，观看的速度永远跟不… | ☐ |
| `engineering/engineering-practice/Shell脚本的简单排错法及调试程序bashdb.md` | 与众多脚本语言一样，Shell 脚本在执行时出错是很常见的，最简单的原因无外乎脚本在编写的过程中出现了语法错误或者不小心输错了命令等。找出脚本中的错误是很重要的能力。比如，我经常不小心会把 echo 命令写成了 ehco，那么执行就会出现下面这种情况： | 与众多脚本语言一样，Shell 脚本在执行时出错是很常见的，最简单的原因无外乎脚本在编写的过程中出现了语法错误或者不小心输错了命令等。找出脚本中的错误是很重要的能力。比如，我经常不小心会把 echo 命令写成了 ehco，那么执行就会出现下面这种情况： | ☐ |
| `engineering/engineering-practice/bashdb安装及调试shell脚本.md` | 解压安装 bashdb是在linux环境下使用的，将资源下载下来后，解压上传到linux系统，再执行以下指令完成安装。 | 解压安装 bashdb是在linux环境下使用的，将资源下载下来后，解压上传到linux系统，再执行以下指令完成安装。 | ☐ |
| `engineering/web-and-frontend/clash-meta-mihomo-install-guide.md` | Clash 是一个基于 Go 实现的代理客户端，凭借规则分流、YAML 配置、TUN 模式、relay（链式代理）等特性，长期是代理工具的事实标准。原始 Clash 项目自 2023 年作者删库后，社区分叉出三个主流分支： | Clash 是一个基于 Go 实现的代理客户端，凭借规则分流、YAML 配置、TUN 模式、relay（链式代理）等特性，长期是代理工具的事实标准。原始 Clash 项目自 2023 年作者删库后，社区分叉出三个主流分支： | ☐ |
| `engineering/web-and-frontend/clash-meta-user-guide.md` | 简单说：Clash 是一款帮你\"科学上网\"的工具。它本身不带线路，你只需要把别人给你的\"订阅链接\"（一串网址）填进去，它就会自动帮你连接好服务器，然后你打开浏览器就能上 Google、Github、YouTube 了。 | 简单说：Clash 是一款帮你"科学上网"的工具。它本身不带线路，你只需要把别人给你的"订阅链接"（一串网址）填进去，它就会自动帮你连接好服务器，然后你打开浏览器就能上 Google、Github、YouTube 了。 | ☐ |
| `engineering/containers/code-server.md` | code-server是C/S架构，一般将服务端部署在linux机器上，然后我们就可以在windows端通过浏览器来访问linux机器上的代码。 | code-server是C/S架构，一般将服务端部署在linux机器上，然后我们就可以在windows端通过浏览器来访问linux机器上的代码。 | ☐ |
| `engineering/containers/codeserver_docker.md` | dockerfile如下： | dockerfile如下： | ☐ |
| `engineering/engineering-practice/cunit单元测试使用.md` | cunit安装测试注册表，测试套，测试用例三个层级来管理单元测试。一般来说，一个项目对应一个测试注册表，一个测试套对应一个c文件，一个测试用例对应一个测试函数。当然一个c函数可能会有多个测试用例。 | cunit安装测试注册表，测试套，测试用例三个层级来管理单元测试。一般来说，一个项目对应一个测试注册表，一个测试套对应一个c文件，一个测试用例对应一个测试函数。当然一个c函数可能会有多个测试用例。 | ☐ |
| `engineering/engineering-practice/doxygen使用指南.md` | 官网下载二进制或者直接用yum或apt工具下载。 | 官网下载二进制或者直接用yum或apt工具下载。 | ☐ |
| `engineering/web-and-frontend/leanote使用教程.md` | leanote的特点就是简约、免费、开源、支持 Markdown 语法，支持程序代码高亮、笔记历史记录、支持笔记分享协作、将笔记发布成博客等功能。 | leanote的特点就是简约、免费、开源、支持 Markdown 语法，支持程序代码高亮、笔记历史记录、支持笔记分享协作、将笔记发布成博客等功能。 | ☐ |
| `engineering/engineering-practice/nc.md` | NC（netcat）被称为网络工具中的瑞士军刀，体积小巧，但功能强大。 | NC（netcat）被称为网络工具中的瑞士军刀，体积小巧，但功能强大。 | ☐ |
| `engineering/engineering-practice/shell常用脚本.md` | shell 常用脚本合集：计算程序运行时间（秒与毫秒两种）、循环执行等日常写法。 | （没抽出来） | ☐ |
| `engineering/engineering-practice/shell脚本进阶.md` | 可以看到成功调用了caller中main函数，同时由于先导入caller.sh文件，后再声明var1变量，最终打印出var1变量值为call。 | 可以看到成功调用了caller中main函数，同时由于先导入caller.sh文件，后再声明var1变量，最终打印出var1变量值为call。 | ☐ |
| `engineering/engineering-practice/vim + ctags + cscope = 强大的IDE_ctags cscope.md` | vim 的最大痛点在于它就是文本编辑器，难以实现函数/变量的跳转。但有了 ctags 和 cscope 这两个插件，它就能实现非常方便的函数/变量跳转以及查找功能。 | vim 的最大痛点在于它就是文本编辑器，难以实现函数/变量的跳转。但有了 ctags 和 cscope 这两个插件，它就能实现非常方便的函数/变量跳转以及查找功能。 | ☐ |
| `engineering/web-and-frontend/一文教你选择局域网文件服务器.md` | apache是linux下常用的web服务器，可以使用yum、apt等工具直接安装，其一般用于生产环境或者大规模场景。 | apache是linux下常用的web服务器，可以使用yum、apt等工具直接安装，其一般用于生产环境或者大规模场景。 | ☐ |
| `engineering/engineering-practice/不得不会的代码注释工具——doxygen.md` | 官网下载二进制或者直接用yum或apt工具下载。 | 官网下载二进制或者直接用yum或apt工具下载。 | ☐ |
| `engineering/engineering-practice/你一定要知道的黑客小技巧.md` | 几个常用排查手段：用 nmap 扫端口、用 nc 测试 tcp/udp 端口是否在监听，以及常见服务端口与连接方式。 | （没抽出来） | ☐ |
| `engineering/engineering-practice/如何调试bash脚本.md` | 你可以让bash打印出你脚本执行的过程中的所有语句。这很简单，只需要使用bash的-x选项就可以做到，下面让我们来看一下。 | 你可以让bash打印出你脚本执行的过程中的所有语句。这很简单，只需要使用bash的-x选项就可以做到，下面让我们来看一下。 | ☐ |
| `engineering/containers/那些你不得不会的提高工作效率的软件神器.md` | vscode服务器版本，可以在浏览器中开发调试代码，尤其适用于windows端开发linux服务器程序。 | vscode服务器版本，可以在浏览器中开发调试代码，尤其适用于windows端开发linux服务器程序。 | ☐ |
| `video_work/video.md` | 程序员，码农，数据库内核开发，分布式存储开发，用户态协议栈开发。 | 程序员，码农，数据库内核开发，分布式存储开发，用户态协议栈开发。 | ☐ |
| `vpp/cdu_nxp2160_ptp1588v2实现方案.md` | ptp1588v2是一套软件协议标准，借助于软硬件时间戳来进行时间同步。因而其需要两方面的支持： | ptp1588v2是一套软件协议标准，借助于软硬件时间戳来进行时间同步。因而其需要两方面的支持： | ☐ |
| `vpp/fastgtpu配置及cli说明文档.md` | vpp加载时会读取startup.conf的配置，fastgtpu的配置如下： | vpp加载时会读取startup.conf的配置，fastgtpu的配置如下： | ☐ |
| `vpp/fastup发包测试说明文档.md` | fastgtpu作为vpp的一个插件，只能被动收包，无法主动发包，需对其进行发包适配。 | fastgtpu作为vpp的一个插件，只能被动收包，无法主动发包，需对其进行发包适配。 | ☐ |
| `vpp/fastup插件加载.md` | fastgtpu 插件的加载与初始化：VLIB 初始化函数、线程创建、udp 端口注册、发包队列与收包回调的调用链。 | （没抽出来） | ☐ |
| `vpp/fastup适配ptp方案.md` | vpp主要在5G小基站侧基于dpdk用于收发包处理。而中国移动对基站侧的ptp协议实现要求如下： | vpp主要在5G小基站侧基于dpdk用于收发包处理。而中国移动对基站侧的ptp协议实现要求如下： | ☐ |
| `vpp/vpp buffer接口.md` | VPP 的 buffer 接口：vlib_buffer_t 的结构，为什么用 union 以及 cacheline 对齐是怎么回事。 | （没抽出来） | ☐ |
| `vpp/vpp vector指北.md` | VPP 的 vector 是什么：本质上是动态可变大小的数组，以及它在数据面编程里怎么用。 | 版权声明：本文为CSDN博主「成王君」的原创文章，遵循CC 4.0 BY-SA版权协议，转载请附上原文出处链接及本声明。 原文链接：https://blog.csdn.net/weixin_45429253/article/details/97020110 | ☐ |
| `vpp/vpp主要数据结构.md` | vpp最顶层结构，其中包含了vpp执行的绝大部分信息，后续注册加载都是填充该数据结构。执行都需要从该数据结构中获取相关信息。 | vpp最顶层结构，其中包含了vpp执行的绝大部分信息，后续注册加载都是填充该数据结构。执行都需要从该数据结构中获取相关信息。 | ☐ |
| `vpp/vpp代码流程图.md` | 常规程序都是从main函数开始执行，main函数执行完后程序退出。但vpp利用gcc的 \\__attribute__((constructor))特性，使很多函数都在main函数之前执行。主要是插件的配置、注册等操作。当然这些配置和注册操作只是告诉vpp有哪些插件和配置，具体的注册加载执行还需要… | 常规程序都是从main函数开始执行，main函数执行完后程序退出。但vpp利用gcc的 \__attribute__((constructor))特性，使很多函数都在main函数之前执行。主要是插件的配置、注册等操作。当然这些配置和注册操作只是告诉vpp有哪些插件和配置，具体的注册加载执行还需要… | ☐ |
| `vpp/vpp使用说明文档.md` | 先将vpp_arm64.tar.gz复制到目标机器上进行解压，解压后的目录结构如下： | 先将vpp_arm64.tar.gz复制到目标机器上进行解压，解压后的目录结构如下： | ☐ |
| `vpp/vpp多网口转发.md` | vpp接管两个网口，当前需实现功能从网口1进来的流量由网口2发送出去。 | vpp接管两个网口，当前需实现功能从网口1进来的流量由网口2发送出去。 | ☐ |
| `vpp/vpp开发指南.md` | vpp二次开发一般都是基于vpp框架进行插件开发。具体友包含以下几个方面： | vpp二次开发一般都是基于vpp框架进行插件开发。具体友包含以下几个方面： | ☐ |
| `vpp/vpp抓包.md` | vpp支持抓包，对报文抓取后保存到文件中，并通过wireshark分析报文。 | vpp支持抓包，对报文抓取后保存到文件中，并通过wireshark分析报文。 | ☐ |
| `vpp/vpp日志系统.md` | 在dpdk插件中可以使用vpp封装的dpdk日志打印接口： | 在dpdk插件中可以使用vpp封装的dpdk日志打印接口： | ☐ |
| `vpp/vpp调试指北.md` | 常用程序调试有如下几种方式： | 常用程序调试有如下几种方式： | ☐ |
| `vpp/fastup-kni设计实现说明文档/index.md` | 当前5G小基站CDU控制面和数据面需要使用两个网口与核心网进行通信。但对于CDU而言，控制面数据量较小，且属于突发性流量；而数据面数据量较大，为持续性流量。相对于数据面来说，控制面流量几乎可以忽略不计。在当前设计中，控制面却需要占用一张网卡，这带来了巨大的资源消耗和维护成本。 | 当前5G小基站CDU控制面和数据面需要使用两个网口与核心网进行通信。但对于CDU而言，控制面数据量较小，且属于突发性流量；而数据面数据量较大，为持续性流量。相对于数据面来说，控制面流量几乎可以忽略不计。在当前设计中，控制面却需要占用一张网卡，这带来了巨大的资源消耗和维护成本。 | ☐ |
| `vpp/fatsup-cpu间转发测试报告/index.md` | cpub对外网口1接入数据包，经mac层转发到cpub对内网口2，经mac层转发到cpua对内网口1进行业务逻辑处理。在cpub上未进行业务处理，在cpub上报文仅到达mac层。 | cpub对外网口1接入数据包，经mac层转发到cpub对内网口2，经mac层转发到cpua对内网口1进行业务逻辑处理。在cpub上未进行业务处理，在cpub上报文仅到达mac层。 | ☐ |
| `vpp/vpp-ip分片测试验证/index.md` | fastup后续需考虑大包，会涉及到ip分片，需要分析验证fastup是否支持分片报文重组，以及大包分片发送。 | fastup后续需考虑大包，会涉及到ip分片，需要分析验证fastup是否支持分片报文重组，以及大包分片发送。 | ☐ |
| `engineering/web-and-frontend/5种回到顶部的写法从实现到增强 - 小火柴的蓝色理想 - 博客园.md` | 本文先详细介绍回到顶部的5种写法，然后对其实现功能增加，最后得到最终实现 | 本文先详细介绍回到顶部的5种写法，然后对其实现功能增加，最后得到最终实现 | ☐ |
| `engineering/web-and-frontend/CORS相关问题.md` | CORS 是什么、为什么会报错，以及跨域请求该怎么处理。 | （没抽出来） | ☐ |
| `engineering/web-and-frontend/cargo构建.md` | cargo 构建技巧：把 crates.io 换成国内镜像源，以及 rustup 升级。 | （没抽出来） | ☐ |
| `engineering/web-and-frontend/gitbook教程.md` | 即将graceful-fs更新到最新。请参考Stack Overflow. | 即将graceful-fs更新到最新。请参考Stack Overflow. | ☐ |
| `engineering/web-and-frontend/html简单教程.md` | 以下是一个简单的HTML登录页面的代码，你可以根据自己的需要进行修改： | 以下是一个简单的HTML登录页面的代码，你可以根据自己的需要进行修改： | ☐ |
| `engineering/web-and-frontend/oh-my-code.md` | 选择Postgresql作为我们的数据库环境，然后使用如下配置文件启动容器： | 选择Postgresql作为我们的数据库环境，然后使用如下配置文件启动容器： | ☐ |
| `engineering/web-and-frontend/python环境搭建.md` | python 环境搭建：装 anaconda、用 conda 建各版本环境，以及 django 项目的创建与运行。 | （没抽出来） | ☐ |
| `engineering/web-and-frontend/react app教程.md` | 安装chrome dev tools插件，然后npm start，再按f5或者运行中开始调试。 | 安装chrome dev tools插件，然后npm start，再按f5或者运行中开始调试。 | ☐ |
| `engineering/web-and-frontend/vue后端api开发.md` | 前端界面写好后，一般需要开发后端进程，提供相关的接口给前端展示。 一般前端用js之类的语言编写，后端采用restful api提供，实现的话可以采用java、go、python等语言实现。 | 前端界面写好后，一般需要开发后端进程，提供相关的接口给前端展示。 一般前端用js之类的语言编写，后端采用restful api提供，实现的话可以采用java、go、python等语言实现。 | ☐ |
| `engineering/web-and-frontend/vue开发环境搭建.md` | 下载node.js安装包安装。 | 下载node.js安装包安装。 | ☐ |
| `engineering/web-and-frontend/vue项目开发流程.md` | 修改vite.config.js,修改如下所示，添加server的host和port。 | 修改vite.config.js,修改如下所示，添加server的host和port。 | ☐ |
| `engineering/web-and-frontend/从登陆注册开始.md` | 要写一个网页界面，一般都是从登陆注册开始的。 | 要写一个网页界面，一般都是从登陆注册开始的。 | ☐ |
| `engineering/web-and-frontend/搭建npm离线仓库.md` | 要在离线环境下使用 Docker 和 Verdaccio 搭建私有的 npm 镜像仓库，你可以按照以下步骤进行操作： | 要在离线环境下使用 Docker 和 Verdaccio 搭建私有的 npm 镜像仓库，你可以按照以下步骤进行操作： | ☐ |
| `engineering/web-and-frontend/tauri将docusruaus网站打包成桌面应用.md` | tauri可以将vue、react等打包成桌面应用 | tauri可以将vue、react等打包成桌面应用 | ☐ |
