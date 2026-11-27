---
description: "Ceph 是分布式存储里少见的一个全样本：三种存储形态跑在同一套 RADOS 上，无中心的元数据管理、一套 CRUSH 放置算法、一套自己实现的网络栈，全摊在同一棵代码树里。这篇是这条源码线的总入口：一张全景图、一份代码地图、一条 12 章的路线，以及该怎么在 30 万行 C++ 里读出一条链路。"
---

# Ceph 源码学习之路：一张全景图 + 12 章路线

| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 初稿：给出 Ceph 的角色全景、`src/` 代码地图、12 章阅读路线，以及编译、GDB、ctags/cscope 的上手方法。 | 2026-11-25 |

> 本文是「Ceph 源码主线」的总入口。同系列后续：
>
> - [01 整体架构与一次写请求的完整链路](../L2-architecture/learning-path/01-整体架构与一次写请求的完整链路.md)
> - [02 环境、编译与代码地图](./learning-path/02-环境编译与代码地图.md)
> - [03 MON：集群状态是怎么产生和分发的](../L2-architecture/learning-path/03-MON集群状态的产生与分发.md)
> - [04 PG 状态机：从 peering 到 active](../L2-architecture/learning-path/04-PG状态机与恢复.md)
> - [05 CRUSH：数据怎么落到这些盘上](../L2-architecture/learning-path/05-CRUSH数据放置.md)
> - [06 BlueStore：对象怎么变成 extent](../L2-architecture/learning-path/06-BlueStore对象与extent.md)
> - [07 事务与 journal：一次写什么时候算「落盘」](../L2-architecture/learning-path/07-事务与journal写什么时候算落盘.md)
> - [08 RADOS 对象语义：omap、快照、xattr、watch/notify](../L2-architecture/learning-path/08-RADOS对象语义.md)

## 为什么先读 Ceph

分布式存储的论文和书里讲的是**模型**（一致性、放置、复制、恢复），
而 Ceph 是少数把这些模型**整套实现出来**、并且**代码全部公开**的系统：

- **无中心的元数据管理**：没有 leader，也没有配置中心；MON 只是一个「多个副本 + Paxos 表决」的元数据服务。
- **自己实现的数据放置算法**：CRUSH 把「对象 → PG → OSD」的映射算出来，不靠中心目录。
- **自己实现的网络栈**：从 asio 迁移到 seastar 的 Messenger，两套实现同时在树里。
- **三种存储形态共用一套底座**：对象存储（RADOS）、块存储（RBD）、文件存储（CephFS）都建在 RADOS 上。
- **存储引擎自己写**：BlueStore 直接管裸设备和文件，自己实现 allocator、事务和落盘链路。

所以读 Ceph 的收益不是「学会用 Ceph」，而是：**把分布式存储的每个概念，
对到一份能跑、能 GDB、能改的真实实现上**。

## 0. 先建立三个概念

读源码之前，这三个词必须先立住 —— Ceph 后面所有的命名都从它们派生。

### 0.1 RADOS：对象 / 池 / PG

Ceph 的数据模型是三层：

| 层 | 是什么 | 谁管 |
| --- | --- | --- |
| **对象（object）** | 一段数据 + 一份 xattr/omap 元数据 | 客户端 |
| **池（pool）** | 一组对象的命名空间 + 副本数 + 故障域规则 | 管理员（`ceph osd pool create`） |
| **PG（placement group）** | 池里的对象按 hash 切成的逻辑分片 | 系统自动 |

对象写进池里时，客户端先算出 **PG id**（`hash(object) % pg_num`），
再由 PG id 算出 **OSD 列表**（acting set）。**副本是以 PG 为单位复制的**，
不是以对象为单位 —— 这是 Ceph 一切设计的地基。

### 0.2 五个角色

| 角色 | 干什么 | 源码入口 |
| --- | --- | --- |
| **MON**（monitor） | 保存并分发集群状态：OSDMap、PGMap、pool 拓扑；本身用 Paxos 表决 | `src/ceph_mon.cc` → `src/mon/Monitor.cc` |
| **OSD**（object storage daemon） | 真正存数据的服务：管 PG、接客户端写、跑复制和恢复 | `src/ceph_osd.cc` → `src/osd/OSD.cc` |
| **MGR**（manager） | 集群运维与观测：dashboard、orchestrator、balancer | `src/ceph_mgr.cc` → `src/mgr/` |
| **MDS**（metadata server） | CephFS 的元数据：目录树、权限、多活 | `src/ceph_mds.cc` → `src/mds/MDSRank.cc` |
| **RGW**（RADOS gateway） | 对象存储网关：S3 / Swift 协议 | `src/rgw/rgw_main.cc` → `src/rgw/` |

> 另外还有一个「伪装成客户端」的角色：**MDS 自己也通过 librados 读写元数据**，
> 所以元数据和普通数据走的是同一条 RADOS 链路，只是池不同。

### 0.3 数据面 / 控制面

Ceph 有一条很清晰的分工（读代码时始终带着这张图）：

- **控制面**：MON 里的 OSDMap + PGMap → 决定「谁该存哪个 PG」「PG 现在该是什么状态」。
- **数据面**：OSD 之间直接互传数据，**不经过 MON**；MON 只在状态变化时被动通知。
- **客户端面**：librados 通过 `Objecter` 直接找 OSD 说话，只在需要新的 OSDMap 时才问 MON。

**「MON 不在数据路径上」**是 Ceph 与 GFS/HDFS 最大的架构差异之一，
也是它没有中心瓶颈的原因。

## 1. 代码地图

`src/` 下面按「子系统」分目录。读 Ceph 之前先把这张地图刻进脑子：

```
src/
├── common/          # 所有守护进程共用：配置系统、日志、Timer、Context、并发原语
├── log/             # 日志实现（Log 类）
├── global/          # 进程级全局初始化（global_init / fork / 信号）
├── messages/        # 每一种协议消息一个类（179 个 M*.h，如 MOSDOp.h、MMonGetMap.h）
├── msg/             # 网络层抽象：Messenger / Message / Connection / Dispatcher + asio 实现
├── osdc/            # 客户端侧：Objecter（op 路由 + osdmap 缓存）、Journaler、Filer、Striper
├── librados/        # RADOS 客户端库（librados_c.cc + librados_cxx.cc）
├── librbd/          # 块设备客户端库
├── neorados/        # 新一代面向对象客户端库（实验性）
├── mon/             # MON：Monitor / OSDMonitor / MonMap / Paxos / MgrMonitor
├── osd/             # OSD：OSD / PG / PrimaryLogPG / PeeringState / 恢复
├── os/              # 服务端存储抽象：ObjectStore / Transaction / BlueStore
│   └── bluestore/   # BlueStore 存储引擎（allocator + 事务 + RocksDB/BlueFS）
├── blk/             # 裸块设备抽象层（BlueStore 底下那一层）
├── crush/           # CRUSH 放置算法
├── mds/             # CephFS 元数据服务
├── rgw/             # 对象存储网关
├── client/          # 内核客户端库（librados 之上的 POSIX/FUSE 接口）
├── mgr/             # 管理服务（dashboard / orchestrator / balancer）
├── objclass/        # 对象类框架（加载、接口、执行环境）
├── cls/             # 对象类的具体实现（rbd / cephfs / rgw / lock / cas / ...）
├── erasure-code/    # 纠删码
├── crimson/         # 新的 seastar 版 OSD（实验性，net/ 下还有一套 seastar Messenger）
├── tools/           # ceph 客户端工具
├── cephadm/         # 集群部署与管理脚本
└── include/         # 对外头文件（rados/librados.h、rados/librados.hpp 等）
```

**读哪几个目录能读懂 Ceph**（按重要性）：

1. `src/osd/` —— 核心，占了 Ceph 一多半的复杂度。PG、复制、恢复都在这。
2. `src/os/bluestore/` —— 存储引擎。数据最后怎么变成盘上的 extent，答案在这。
3. `src/mon/` —— 集群状态怎么来的。
4. `src/librados/` + `src/osdc/` —— 客户端怎么把一次写变成一条消息。
5. `src/msg/` + `src/messages/` —— 消息怎么在机器之间跑。
6. `src/crush/` —— 数据怎么落到这些盘上。

其余目录可以按需再读。

**先看一眼规模，知道自己面对什么**（2026-11-25，`main` 分支实测行数）：

| 文件 | 行数 | 说明 |
| --- | ---: | --- |
| `src/mon/OSDMonitor.cc` | 20,283 | 全仓最大单文件：OSDMap 的产生与分歧处理 |
| `src/client/Client.cc` | 19,922 | 内核客户端的元数据逻辑 |
| `src/osd/PrimaryLogPG.cc` | 18,583 | PG 日志与恢复主路径 |
| `src/os/bluestore/BlueStore.cc` | 18,266 | 存储引擎 |
| `src/mds/MDCache.cc` | 15,649 | CephFS 的 dentry/inode 缓存 |
| `src/osd/OSD.cc` | 11,967 | OSD 主体 |

> 顺带一提：v22 起 **FileStore 已被移除**，`ObjectStore::create()` 只认
> `bluestore` 和 `memstore`（`src/os/ObjectStore.cc`）。老文章里讲 FileStore
> 的部分，只能当历史看。

## 2. 12 章路线

每一章都回答一个具体问题。**读完每一章，你都能回答它标题里的那个问题**，
这就是这条线的判断标准。

| # | 章节 | 回答什么问题 | 放在哪一站 |
| --- | --- | --- | --- |
| 01 | 整体架构与一次写请求的完整链路 | 一次写从 librados 到盘上再回到客户端，经过了哪些函数？ | 架构与数据路径 |
| 02 | 环境、编译与代码地图 | 怎么把 Ceph 编译起来、跑起来、GDB 跟住一条链路？ | 起步与全景 |
| 03 | MON：集群状态是怎么产生和分发的 | OSDMap / PGMap 从哪儿来，怎么在 MON 之间表决、怎么发给 OSD？ | 架构与数据路径 |
| 04 | PG 状态机：从 peering 到 active | PG 的每个状态意味着什么，恢复是怎么一步步推进的？ | 架构与数据路径 |
| 05 | CRUSH：数据怎么落到这些盘上 | 一个 PG 怎么变成一组 OSD，权重和故障域怎么参与计算？ | 架构与数据路径 |
| 06 | BlueStore：对象怎么变成 extent | 对象在盘上长什么样，allocator 怎么分配空间？ | 架构与数据路径 |
| 07 | 事务与 journal：一次写什么时候算「落盘」 | 写、事务、WAL、fsync 的顺序是什么？ack 在哪一刻返回？ | 架构与数据路径 |
| 08 | RADOS 对象语义 | omap、快照、xattr、watch/notify 分别由谁实现？ | 对象语义与客户端 |
| 09 | Messenger：消息怎么在机器之间跑 | 一条消息从 send 到对端 handler 经过哪些层？ | 对象语义与客户端 |
| 10 | librados：客户端库那一侧 | 客户端 API 怎么变成 PG 定位和 OSD 操作？ | 对象语义与客户端 |
| 11 | CephFS 与 RGW | 文件存储和对象存储分别在 RADOS 之上加了什么？ | 上层应用 |
| 12 | objclass / cls 与新架构 | 怎么给对象加行为？seastar、crimson、blk 这些新方向在替换什么？ | 上层应用 |

> 「起步与全景」「架构与数据路径」这两站已经建好；后面几站等写到那一章时，
> 再去 `data/learning-path.json` 里开。**每写完一章，都要给它所在的站加一条规则** ——
> 站不能是空的，那是 CI 会拦的事（见仓库里的 `tests/test_learning_path.py`）。
>
> **进度**：01、02、03、04、05、06、07、08 已写完（[01](../L2-architecture/learning-path/01-整体架构与一次写请求的完整链路.md)、
> [02](./learning-path/02-环境编译与代码地图.md)、
> [03](../L2-architecture/learning-path/03-MON集群状态的产生与分发.md)、
> [04](../L2-architecture/learning-path/04-PG状态机与恢复.md)、
> [05](../L2-architecture/learning-path/05-CRUSH数据放置.md)、
> [06](../L2-architecture/learning-path/06-BlueStore对象与extent.md)、
> [07](../L2-architecture/learning-path/07-事务与journal写什么时候算落盘.md)、
> [08](../L2-architecture/learning-path/08-RADOS对象语义.md)），09 起陆续补上。

## 3. 怎么在 Ceph 这棵树上读代码

Ceph 的代码量在 30 万行 C++ 量级（不含测试和第三方库），**靠通读是读不完的**。
下面这套工具链和姿势是这套路线图配套的。

### 3.1 编译一棵带符号的树

```bash
cd /work/cwork/ceph
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Debug \
         -DCMAKE_CXX_FLAGS="-O0 -g3" \
         -DWITH_TESTS=OFF
make -j$(nproc)
```

- Ceph 用 CMake（不是 autotools）。`Debug` + `-O0 -g3` 是为了能单步。
- 只编译你关心的目标会快很多：`make ceph-osd -j$(nproc)`。
- 想跑单元测试就开 `-DWITH_TESTS=ON`，`ctest` 能跑 `src/osd/` 等目录下的单测。

### 3.2 起一个本地集群

Ceph 自带 `vstart`（`src/vstart.sh`），它用本地目录当 OSD，不需要 root 权限，
是读源码时最省事的实验台。**它必须在 build 目录里跑**（脚本靠 `CMakeCache.txt`
找编译产物）：

```bash
cd /work/cwork/ceph/build
make -j$(nproc) vstart                       # 把 vstart 依赖的二进制都编出来

MON=1 OSD=3 MDS=0 MGR=1 ../src/vstart.sh -n -d
```

- 集群规模用**环境变量**指定：`MON=`、`OSD=`、`MDS=`、`MGR=`、`RGW=`。
- `-n` = 新建（清掉旧数据重来），`-d` = debug（前台跑，日志直接打终端）。
- 常用开关：`--msgr1` / `--msgr2` 强制协议版本，`--memstore` 用内存后端，
  `--crimson` 换成实验性的 seastar 版 OSD，`-X` 关掉 CephX。
- 生成的配置在 `build/data/` 下面，配置项跟真实集群一模一样，可以直接读。
- 拆集群：`../src/vstart.sh --stop`（或直接 `pkill ceph-osd`）。

> 跑起来之后先做两件事：`ceph -s` 看集群状态，`rados -p rbd put obj1 /etc/hostname`
> 写一个对象 —— 有了这两次操作，后面的 GDB 断点才有东西可跟。

### 3.3 定位代码：ctags / cscope / ripgrep

```bash
cd /work/cwork/ceph/src

# 1. ctags：生成符号索引，vim 里 :tag 跳定义
ctags -R --fields=+l .

# 2. cscope：查「谁调用了它」「它调用了谁」
cscope -R .

# 3. ripgrep：查文本最快，适合找「哪里用了这个字段」
rg -n 'class Objecter' src/osdc/Objecter.h
rg -n 'do_op\b' src/osd/PrimaryLogPG.cc
```

**Ceph 的命名习惯**（决定了 grep 的效率）：

- 类名 `PascalCase`（`OSD`、`BlueStore`、`PG`、`Objecter`）。
- 方法名 `snake_case`（`handle_op`、`do_transactions`、`_op`）。
- 私有成员带 `_` 前缀（`_osdmap`、`_op_queue`）。
- 头文件里类的前向声明在文件顶部成片出现 —— 想看一个类的全部接口，
  先 `rg -n "class BlueStore" src/osd/BlueStore.h`，再看同文件的其他声明。

### 3.4 GDB：跟一条写请求

这是这套路线里最有用的一招。**先跑起来，再打断点**：

```bash
# 终端 1：起集群（必须在 build 目录里跑）
cd /work/cwork/ceph/build
MON=1 OSD=3 MDS=0 MGR=1 ../src/vstart.sh -n -d

# 终端 2：写一个对象
rados -p rbd put obj1 /etc/hostname

# 终端 2：GDB 挂到某个 OSD 上
gdb -p $(pgrep -f ceph-osd | head -1)
```

推荐的断点顺序（从客户端到盘上）：

| 断点 | 位置 | 看什么 |
| --- | --- | --- |
| `librados::IoCtxImpl::operate` | `src/librados/IoCtxImpl.cc` | 客户端 API 入口 |
| `Objecter::_calc_target` | `src/osdc/Objecter.cc` | PG id 和 acting set 算出来了 |
| `Objecter::_send_op` | `src/osdc/Objecter.cc` | 操作怎么被发出去 |
| `OSD::ms_fast_dispatch` | `src/osd/OSD.cc` | OSD 收到消息 |
| `PrimaryLogPG::do_op_impl` | `src/osd/PrimaryLogPG.cc` | 落到哪个 PG、哪个副本 |
| `BlueStore::_do_write` | `src/os/bluestore/BlueStore.cc` | 真的写盘 |

抓一段调用栈：

```
(gdb) set pagination off
(gdb) b PrimaryLogPG::do_op_impl
(gdb) c
(gdb) bt
```

> GDB 挂到正在运行的进程需要 `ptrace` 权限；容器里可能要
> `--cap-add=SYS_PTRACE`，或者给内核加 `kernel.yama.ptrace_scope=0`。

### 3.5 读代码的三条纪律

1. **先看类的声明再看实现**。Ceph 的头文件里通常已经把接口、成员、
   注释都写全了（注释质量相当高，很多地方直接引用了对应的邮件列表讨论）。
2. **先找「入口」再找「细节」**。任何一条链路，都有一个「收到消息」或
   「发起调用」的地方；从那里往两头读，比从文件头顺读快十倍。
   v22 起**每种消息一个类**（`src/messages/` 下的 `MOSDOp.h`、`MMonGetMap.h`
   ……共 179 个），找消息类型先从这里下手，而不是去翻 `msg_types.h`。
3. **拿不准就查 `doc/`**。`src/doc/` 下有开发者文档（`dev/development.md`、
   `dev/cephfs.rst` 等），还有 `src/common/options/*.yaml.in` 里的配置项
   说明 —— 配置项的语义在那里比代码里清楚（v22 起配置项定义在这批 YAML 里，
   由 `src/common/options/validate-options.py` 生成 C++ 代码）。

## 4. 这条线的验收标准

走完 12 章，你应该能不看代码回答这几个问题：

1. 一次 `rados put` 到对象真正落在盘上，中间经过哪几个进程、哪几条消息？
2. Ceph 的「提交」发生在哪一刻？客户端拿到 ack 时，数据在哪些副本上？
3. PG 从 `active` 变成 `degraded` 再回到 `active`，中间做了什么？
4. CRUSH 算出的 acting set 和 up set 有什么区别？为什么需要两个？
5. MDS 崩溃后，CephFS 的元数据是怎么恢复的？
6. seastar 版 Messenger 和 crimson 版 OSD 想替换掉现在的什么？

## 5. 版本与参考

- 本文基于 Ceph `main` 分支（`v22.0.0`，代号 **vampire**，dev 版本）。
  Ceph 每年一个大版本，目录结构会动 —— 引用文件时请以你手上那棵树的
  `git describe` 为准。
- 官方文档：<https://docs.ceph.com/en/latest/>
- 开发者文档（代码树里也有）：`src/doc/dev/`
- 邮件列表与设计讨论：<https://lists.ceph.com/>
- 源码树：`/work/cwork/ceph`（本系列所有行号都基于它）

### v22 里有几个「老文章会踩空」的地方

读 Ceph 的中文材料大多写的是 v16/v17（Pacific/Quincy）那一代，v22 有几处
结构性变化，引用文件时要当心：

| 老文章里通常这么写 | v22 实际是 |
| --- | --- |
| `src/osd/BlueStore.cc` | `src/os/bluestore/BlueStore.cc`（存储引擎搬到了 `src/os/` 下） |
| `src/osdc/ObjectStore.h` | `src/os/ObjectStore.h`（`src/osdc/` 现在是客户端侧的 `Objecter`/`Filer`/`Striper`） |
| `OSD::handle_op` | `OSD::ms_fast_dispatch` → `enqueue_op` → `dequeue_op`（`src/osd/OSD.cc`） |
| `PG::handle_op` / `PG::queue_op` | `PrimaryLogPG::do_request` / `do_op` / `do_op_impl`（`src/osd/PrimaryLogPG.cc`） |
| `PGStateMachine.h` | **不存在**。PG 状态机是 `src/osd/PeeringState.h` 里的 boost::statechart（实现另有 `src/osd/PeeringState.cc`，9,615 行） |
| `PrimaryLogPG::do_peer` / `PG::queue_all_peers` 等 peering 函数 | **整体搬到 `src/osd/PeeringState.{h,cc}`**；`PrimaryLogPG.cc` 只剩数据面 |
| `src/osd/MissingSet.h` | **不存在**。改成 `src/osd/MissingLoc.h` + `osd_types.h` 里的 `pg_missing_set` |
| OSD 用 `Journaler` 存 PG log、重启回放 | **不再如此**。PG log 是 collection 里的 omap 对象，和 op 同事务落盘 |
| `MOSDMapIncremental` 消息类 | **不存在**。全量与增量同在 `MOSDMap` 的 `maps` / `incremental_maps` 两个字段 |
| CRUSH 在 `src/osd/` 下，`src/osd/CRUSHWrapper.{h,cc}` | **不存在**。独立目录 `src/crush/`，类名是 `CrushWrapper`（`src/crush/CrushWrapper.{h,cc}`） |
| CRUSH 算法在 `src/crush/crush.c` | **半错**。`crush.c` 只有 137 行析构；算法在 `src/crush/mapper.c`（2,053 行） |
| `OSDMap` 里有 `pg_up` / `pg_acting`（`pg_osd_item_t`） | **不存在**。v22 按需计算（`OSDMap::_pg_to_up_acting_osds`，`src/osd/OSDMap.cc:3500`），常驻的只有 `pg_temp` / `pg_upmap` |
| `src/mon/PGMonitor.{h,cc}` | 2017 年已删除；PG 统计改由 OSD 直接报给 mgr |
| `class MDS` | `class MDSRank`（`src/mds/MDSRank.h`） |
| `src/msg/message.h` 里的 `Framed` 基类 | `src/msg/Message.h` 的 `Message`，靠 `encode_payload()`/`decode_payload()` 虚函数 |
| `MSG_OSD_WRITE` 之类枚举 | 每种消息一个类，放在 `src/messages/`（`MOSDOp.h` 等，179 个）；老常量在 `src/include/ceph_fs.h` 里叫 `CEPH_MSG_*` |
| `src/msg/seastar/` | **不存在**。seastar 版 Messenger 只在 `src/crimson/net/`，`src/msg/` 只有 asio 版 |
| BlueStore 有 journal | **没有**。`needs_journal()` / `wants_journal()` / `allows_journal()` 全返回 false（`src/os/bluestore/BlueStore.h:1652-1654`）。元数据靠 RocksDB 的 WAL（落在 BlueFS 的 metadata log 里），用户数据直接写 bdev |
| BlueStore 的数据存在 RocksDB 里 | **只存元数据**。用户数据由 `bdev->aio_write()` 直接写设备（`src/os/bluestore/BlueStore.cc:14035`） |
| OSD 有 op journal（`osd_journal` / journal 盘），op 先落 journal 再落盘 | **整个没了**。FileStore 已删（`src/os/ObjectStore.cc:51-53`），`osd_journal` 配置项不存在 |
| `ceph daemon osd.N flush_journal` 能强制刷 journal | **命令还在，但是空转**。`ObjectStore::flush_journal()` 默认 `-EOPNOTSUPP`（`src/os/ObjectStore.h:787`），BlueStore 未覆盖，OSD 还不看返回值 |
| 写顺序是「先写 journal，再写 data」 | **反了**。BlueStore 是**数据 aio 先完成，元数据后提交**（`src/os/bluestore/BlueStore.cc:11136-11161`），提交前还要 `bdev->flush()`（`:11881`） |
| `on_commit` 回调 = 改动可读 | **`on_commit` = 已持久化**。可读是 `on_applied` / `on_applied_sync`（契约见 `src/os/Transaction.h:26-59`） |
| 每个事务一次 fsync | **一批事务共用一次 fsync**。`_kv_sync_thread` 用一个额外的 `synct` 事务逼出 fsync（`src/os/bluestore/BlueStore.cc:11895` / `:11959`） |
| `BlueStore::Object` / `ObjectHandle` / `onode_t` | **都不存在**。v22 是 `bluestore::Onode`（`BlueStore_objects.h:887`）、`bluestore_onode_t`（`bluestore_types.h:1293`）；`ObjectHandle` 几乎从树上消失了 |
| extent map 用 `interval_set` | **是 `boost::intrusive::set<Extent>`**（`src/os/bluestore/BlueStore_objects.h:119`） |
| allocator 接口是 `alloc()` / `free()` | **是 `allocate()` / `release()`**（`src/os/bluestore/Allocator.h:54` / `:65`）；v22 有可插拔家族，默认 `hybrid` |
| `bluestore_allocator = fastbitmap` | **没有这个 type**。位图分配器的类名是 `BitmapAllocator`，配置项写 `bitmap` |
| FileStore | **已移除**，`ObjectStore::create()` 只认 `bluestore` 和 `memstore` |
| `src/common/ceph_strings.cc` 定义配置项 | 配置项在 `src/common/options/*.yaml.in`，生成到 `src/common/options.cc` |
| `md_config_t` 在 `ceph_context.h` | 在 `src/common/config.h`；`CephContext` 持有的是门面 `ConfigProxy` |
| 存储层支持快照（`ObjectStore::snapshot()`） | **死接口**，永远 `-EOPNOTSUPP`，没有任何实现覆盖它（`src/os/ObjectStore.h:791`） |
| RADOS 快照 = 拷一份数据 | **不拷**。创建快照只改映射，第一次写才懒克隆（`src/osd/PrimaryLogPG.cc:9231`） |
| omap 存在对象的元数据里 | **独立的 KV key**，一条 entry 一个（`src/os/bluestore/BlueStore.cc:15043`） |
| omap 只有一个前缀 | **四个**：`M` / `m` / `p` / `P`，对应三种布局（`src/os/bluestore/BlueStore.cc:139-142`） |
| 集合也有 xattr | **v22 没有这个接口**，BlueStore 回 `-EOPNOTSUPP`（`src/os/bluestore/BlueStore.cc:12702`） |
| watch 是纯内存状态 | **一半落盘**：名单在 `object_info_t::watchers` 里，随 `OI_ATTR` xattr 落盘 |

> 完整的对照表在 [01 整体架构与一次写请求的完整链路](../L2-architecture/learning-path/01-整体架构与一次写请求的完整链路.md) 的最后一节。
