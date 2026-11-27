# 设计：把 `docs/` 的物理目录重排成学习路径的镜像

日期：2026-11-26
状态：待批准
作者：growdu × Claude

---

## 一、目标与非目标

### 目标

1. **`docs/` 的物理目录树 = 学习路径的赛道 × 阶段树。** 目录名自带学习顺序，
   新文章落到哪个阶段，看目录就知道，不用回头查 `data/learning-path.json`。
2. **`data/learning-path.json` 的规则退化成一条 `path_prefix` 对一个阶段。**
   现在 `dataplane` 那条赛道要逐个文件名列正则（`^dpdk/(day1|dpdk常用接口指北|…)`），
   搬完可以全部删掉。
3. **旧 URL 继续可用**（重定向表），**旧日期不跳**（日期固化表）。

### 非目标

- 不改文章正文一个字。
- 不改文章 front matter 里的 `title` / `description` / `tags`。
- 不重排文章在阶段内部的顺序（阶段内仍按「编号系列在前、其余按时间」）。
- 不合并任何两篇文章（那是审校台账的事，不是搬家的事）。
- 不做双轨：旧的顶层目录不再保留副本。

---

## 二、事实基线（2026-11-26 实测）

| 事实 | 数值 | 怎么测的 |
| --- | --- | --- |
| `docs/` 顶层目录 | 34 个 | `find docs -maxdepth 1 -type d` |
| 站内文章 | **590 篇**（586 篇 `.md` + 3 篇 `.html` + 1 篇未入库的 WIP） | `git ls-files docs` = 589，加上工作区里那篇 WIP |
| 视频内容单元 | 6 个（不在 `docs/`，在 `aiv/pipeline/Makefile` 登记） | `tools/build-learning-path.py` 的 `video_corpus()` |
| 学习路径语料 | 596 篇，**全部归类成功，兜底 0 篇** | `tools/build-learning-path.py` 的 `classify()` |
| 赛道 / 阶段 | 10 条赛道 / 42 个阶段 | `data/learning-path.json` |
| 硬编码 docs 路径 | 代码与配置 243 处、散文 1940 处 | 全仓 grep `docs/`、`source-tracks/` |
| 已经在 `source-tracks/` 下的文章 | 270 篇（另有 22 个 `_index.md`） | `git ls-files docs/source-tracks` |
| 资源文件（图片等） | 1085 个 | `git ls-files docs`，去掉 `.md` / `.html` |
| 现有重定向条目 | 320 条（带日期段的 1 条） | `data/redirects.json` |
| 现有日期固化条目 | 579 条 | `data/date-overrides.json` |
| `learning-path.json` 里的 `path_regex` | 29 条（阶段 26 + 赛道 3） | 逐条统计 |
| `review/` 台账文件 | 29 个（其中 20 份是逐篇审校记录） | `git ls-files review` |

**那篇 WIP 文章**：`docs/source-tracks/linux-kernel/process-memory/learning-path/
05-调度器-EEVDF负载均衡与上下文切换.md` 还在工作区，没入库。
它现在就让 `tools/build-learning-path.py --check` 报「语料对不上」
（源码树里有、`source/_posts/` 里没有）。搬之前要把它 `git add` 进来 ——
`git mv` 不动没入库的文件。

**结论**：学习路径的**语义**已经是成品，缺的是**物理目录**和**规则表**的对齐。
所以这次工作的本质是「把规则表翻译成目录树」，不是重新策展。

---

## 三、目标目录树

```
docs/
└── source-tracks/                      ← 唯一顶层目录
    ├── postgresql/                    赛道：PostgreSQL 源码内核
    │   ├── L1-getting-started/         起步与全景
    │   ├── L2-storage-engine/          存储引擎：页、文件与内存
    │   ├── L3-index-and-query/         索引与查询管线
    │   ├── L4-transaction-mvcc/        事务、MVCC 与并发
    │   ├── L5-wal-and-recovery/        WAL、checkpoint 与恢复
    │   ├── L6-replication-ha/          复制与高可用
    │   ├── L7-logical-replication/     逻辑复制与流式
    │   └── L8-extensions-perf/         扩展、性能与生态
    ├── distributed/                   赛道：分布式与集群
    │   ├── L1-foundations/              分布式基础
    │   ├── L2-consensus/                一致性协议
    │   ├── L3-ha-and-dr/                高可用方案与选型
    │   └── L4-field-notes/              实战与故障现场
    ├── ceph/                          赛道：Ceph 源码
    │   ├── L1-getting-started/          起步与全景
    │   └── L2-architecture/             架构与数据路径
    ├── linux-kernel/                  赛道：Linux 源码
    │   ├── L1-getting-started/          起步与全景
    │   ├── L2-architecture/             架构与数据路径
    │   └── L3-process-memory/           进程与内存
    ├── linux/                         赛道：Linux 与网络
    │   ├── L1-daily-ops/                Linux 入门与日常操作
    │   ├── L2-memory-and-linking/       内存与动态链接
    │   ├── L3-kernel-internals/         内核机制与驱动
    │   ├── L4-networking/               网络协议与抓包
    │   └── L5-filesystem/               存储与文件系统
    ├── dataplane/                     赛道：数据面：DPDK · VPP
    │   ├── L1-environment/              环境与入门
    │   ├── L2-architecture/             架构与核心数据结构
    │   ├── L3-plugin-dev/               插件与业务开发
    │   └── L4-testing/                  测试、验证与性能
    ├── ai-tools/                      赛道：AI 与工具
    │   ├── L1-concepts/                 AI 是什么、怎么工作的
    │   ├── L2-toolbox/                  AI 工具箱
    │   ├── L3-leverage/                 把 AI 变成杠杆
    │   └── L4-video-platform/           AI 视频平台设计
    ├── engineering/                   赛道：工程与语言
    │   ├── L1-basics/                   计算机基础与语言入门
    │   ├── L2-tooling/                  工程化：编译、测试、调试
    │   ├── L3-container/                容器与环境
    │   └── L4-web/                      Web、前端与搜索
    ├── life/                          赛道：人生与成长
    │   ├── L1-learning-method/          学习方法与自我认知
    │   ├── L2-exam-prep/                学业与备考
    │   ├── L3-economy/                  经济周期与自我经营
    │   └── L4-hometown/                 家乡与私人记录
    ├── blogging/                      赛道：博客与自媒体
    │   ├── L1-setup/                    把站搭起来
    │   ├── L2-content/                  内容与排版
    │   ├── L3-distribution/             传播与变现
    │   └── L4-video-pipeline/           视频生产线
    └── platform-meta/                 赛道：平台元数据（讲这个站自己怎么造）
        ├── L1-platform-overview/        平台总览
        ├── L2-content-model/            内容模型
        ├── L3-build-pipeline/           构建流水线
        ├── L4-info-architecture/        信息架构
        ├── L5-multiplatform/            多平台分发
        └── L6-video-line/               视频生产线
```

**11 条赛道 / 48 个阶段。** 赛道目录名 = 赛道 id = 阶段 id 的前缀，三层名字一处到底。

### 三点说明

1. **`platform-meta` 从「寄居在 blogging 下」变成独立赛道。**
   之前它挂在 blogging 的四个阶段里（2 / 2 / 1 / 1 篇），是权宜之计
   （`data/learning-path.json` 的 `note` 里写着「等赛道树整体重排时再决定」）。
   现在就是那个时刻：它自己已经有 6 个系列（`platform-overview` / `content-model` /
   `build-pipeline` / `info-architecture` / `multiplatform` / `video-line`），
   每个系列一篇正文，天然是 6 个阶段。
   **代价**：这 6 个阶段每段只有 1 篇文章 —— 它是「参考手册」而不是「学习路径」。
   接受这一点；将来要合并成 3 段，只是改 JSON 加一次目录合并。

2. **赛道 id 改名两处**：`db-internals` → `postgresql`、`linux-network` → `linux`。
   理由：目录名 = 赛道 id。改 id 比改目录便宜 —— 改 id 只动 `/learning/<id>/` 一个页面，
   改目录要连带改 `data/redirects.json` 里那一批键。

3. **阶段目录带 `L1-` 前缀。**
   现在 `postgresql/` 下的目录按字母序排（`extensions-perf` 在 `getting-started` 前面），
   物理顺序 ≠ 学习顺序，正是信息架构那篇里说的那个坑。编号写进目录名，
   目录一排开就是学习顺序。

---

## 四、落点规则

### 4.1 一条规则

> **一篇文章落到 `source-tracks/<赛道>/<阶段>/` 下，原顶层目录名这一层去掉，
> 顶层目录下面的结构原样保留。**
>
> **再去掉一层（可选）**：顶层目录下的「一级子目录」如果
> ①整体落进同一个阶段、②不是 bundle（目录里没有 `index.md`）、
> ③扁平化之后不与同阶段任何其他内容重名 —— 那就把这个子目录名也去掉。

举例：

| 原路径 | 新路径 | 说明 |
| --- | --- | --- |
| `docs/dpdk/day1.md` | `docs/source-tracks/dataplane/L1-environment/day1.md` | 顶层散文件，平铺 |
| `docs/dpdk/l3fwd/index.md` | `docs/source-tracks/dataplane/L1-environment/l3fwd/index.md` | bundle，目录名必须留 |
| `docs/distributed/foundations/分布式一致性协议.md` | `docs/source-tracks/distributed/L1-foundations/分布式一致性协议.md` | `foundations` 整体落在 L1，去掉一层 |
| `docs/source-tracks/postgresql/storage-engine/mm/pg_page.md` | `docs/source-tracks/postgresql/L2-storage-engine/mm/pg_page.md` | 系列目录就是阶段目录，不动 |

三个条件缺一不可：
- 条件 ① 保证「一个来源目录只服务于一个阶段」，扁平后语义不乱；
- 条件 ② 保证不会把两个 `index.md` 摞到一起（bundle 的目录名是它的地址）；
- 条件 ③ 是**冲突守卫**。

**已经在 `source-tracks/` 下的文章走另一条路**：它们下面有两层 ——
赛道目录和系列目录。系列目录**本身就是阶段目录**（阶段与系列已经 1:1），
所以不适用扁平规则：赛道目录保留，系列目录换成带编号的阶段目录。
`source-tracks/postgresql/storage-engine/mm/pg_page.md`
→ `source-tracks/postgresql/L2-storage-engine/mm/pg_page.md`。

### 4.2 零冲突，已验证

按 §4.1 的规则对全部 590 篇 + 6 个视频单元算落点，
**同一阶段内没有任何两个来源落在同一个路径**（脚本逐篇比对，冲突数 = 0）。

守卫实际挡下了 8 个目录：

| 目录 | 为什么不能扁平 |
| --- | --- |
| `code/assemble-work/`、`code/c-sharp-work/`、`code/c-work/`、`code/gui-work/`、`code/html-work/`、`code/JavaScript-work/`、`code/java-work/`、`code/shell-work/` | 每个里面都只有一个 `readme.md`，扁平后 8 个 `readme.md` 撞在同一个路径上 |

**深度分布**（`tools/build-tree-migration.py` 算出来的，不是估的）：
373 篇落在「赛道/阶段/文件」三层，209 篇落在四层，7 篇落在五层，1 篇落在六层。
多出来的那几层**不是白带的**：

- 四层 = bundle 目录。目录里有 `index.md` 的，它的名字就是它的地址 ——
  扁平掉就成了两个 `index.md` 摞在一起（§4.1 条件 ②）；
- 五层、六层 = bundle 目录下面本来就有子目录
  （`code/c-work/simple-editor/`、`life/aiv/brand/scripts/`），
  「顶层目录下面的结构原样保留」这条规则要求它们留着。

**落点逐赛道核对**（搬完之后用这个表验收）：

| 赛道 | 各阶段篇数 | 合计 |
| --- | --- | --- |
| `postgresql` | L1 27 · L2 16 · L3 14 · L4 9 · L5 13 · L6 21 · L7 79 · L8 30 | 209 |
| `engineering` | L1 31 · L2 28 · L3 15 · L4 35 | 109 |
| `linux` | L1 13 · L2 10 · L3 14 · L4 22 · L5 6 | 65 |
| `distributed` | L1 7 · L2 28 · L3 18 · L4 11 | 64 |
| `dataplane` | L1 19 · L2 7 · L3 10 · L4 8 | 44 |
| `ai-tools` | L1 19 · L2 5 · L3 2 · L4 5 | 31 |
| `life` | L1 6 · L2 12 · L3 7 · L4 2 | 27 |
| `blogging` | L1 4 · L2 3 · L3 3 · L4 10 | 20 |
| `ceph` | L1 2 · L2 7 | 9 |
| `linux-kernel` | L1 1 · L2 2 · L3 3 | 6 |
| `platform-meta` | L1 1 · L2 1 · L3 1 · L4 1 · L5 1 · L6 1 | 6 |
| **合计** | | **590** |

这一步必须先跑：一旦有冲突而没守卫，就会**丢文章**（`git mv` 到同一个目标，
后者直接被跳过）。

### 4.3 五个特例

| 特例 | 处理 | 理由 |
| --- | --- | --- |
| `docs/source-tracks/postgresql/` 下 8 个系列目录 | 只加 `L#-` 前缀，内容不动 | 阶段与目录已经 1:1，只差编号 |
| `docs/source-tracks/linux/` 下 5 个系列目录 | 同上 | 同上 |
| `docs/pcap/`（5 个抓包文件） | 归到 `linux/L4-networking/pcap/` | 都是网络协议阶段的素材，跟着那批文章走 |
| `docs/src/`（C 测试代码，无任何文章引用） | 移出 `docs/` 到 `internal/` | docusaurus 时代的遗留，谁也不引用 |
| **顶层目录里的散落资源** | 逐个定去留（删 / 跟目录走 / 归到指定阶段） | 见下 |

**资源（图片等）怎么落位。** 图片的引用是按「文章所在目录相对」解析的，
所以资源必须跟着**引用它的那篇文章**走。实测 `docs/` 下有 **1084 个非文章文件**
（图片、源码附件、抓包文件、字节码、编辑器配置），其中 **139 个**被文章引用
（`![...](...)` 与 `<img src=...>` 两种写法都算）。

| 事实 | 数字 |
| --- | --- |
| 被引用的资源 | 139 |
| **同时被两个阶段的文章引用** | **0** |
| 有主（所在目录里有文章，能跟着走）的资源 | 1037 |
| 无主（所在目录里没有文章）的资源 | 47 |

**0 个跨阶段 —— 早期稿子里的「3 个跨阶段共用图片」是错的。**
`dpdk/vpp_image/15min*.png` 这三个文件确实存在，但引用它们的文章
（`dpdk/nxp测试报告/`、`dpdk/fastup测试报告/`）各有**自己的** `vpp_image/` 副本，
两批文章也落在同一个阶段里。早期结论是路径解析算错了（用的是漏绑 `sl` 的那份落点表）。

**结论：资源不需要复制，只需要搬。** 这让搬运表的复杂度降了一档 ——
没有「一份资源两个去处」的情况，`asset_map` 是一张一对一的全表。

47 个无主资源分四类，逐个定去留：

| 类 | 数量 | 去向 | 理由 |
| --- | --- | --- | --- |
| `docs/alg/alg_img/*.webp` | 19 | **删** | 与 `docs/alg/B-树如何使查询更快/alg_img/` 里的同名文件**逐字节相同**（md5 一致），文章引用的是后者；这个目录是没人收的旧拷贝 |
| `docs/code/**`（没有 `readme.md` 的工程目录：`flex_bison_test/`、`python-work/`） | 17 | 跟 `code/` 走 → `engineering/L2-tooling/` | 它们是 `code/` 那条线的素材，只是没有配套文章 |
| `docs/pcap/*.pcap` | 5 | → `linux/L4-networking/pcap/` | 网络协议阶段的素材 |
| `docs/src/test/**` | 5 | 移出 `docs/` → `internal/` | 见上 |
| `docs/environment/vfox使用指南` | 1 | **删** | 0 字节的空文件 |
| `docs/report_restructured.pptx` | 1 | 移出 `docs/` → `internal/` | 一次重排的交付物，不是文章 |

这条要落到 `tools/migrate-tree.py` 上：现有的 `asset_moves()` 只会跟着
**目录**搬资源，一旦一个顶层目录被拆到多个阶段就会漏；
而且它只认「文章旁边的同级文件」，认不出文章目录里的子目录。
本次给迁移表加一段 `asset_map`（旧路径 → 新路径，逐文件），
`asset_moves()` 先读它，读不到再退回原来的两条规则。

### 4.4 34 个顶层目录逐条去向

「篇数」是落到该阶段的文章数；一个顶层目录拆到几个阶段，就写几行。

| 原顶层目录 | 落到 | 篇数 |
| --- | --- | --- |
| `ai/` | `ai-tools/L1-concepts` 17 · `L2-toolbox` 5 · `L3-leverage` 2 · `L4-video-platform` 5 | 29 |
| `alg/` | `engineering/L1-basics` | 1 |
| `base/` | `engineering/L1-basics` | 13 |
| `blog/` | `blogging/L1-setup` 4 · `L2-content` 3 · `L3-distribution` 2 | 9 |
| `chatgpt/` | `ai-tools/L1-concepts` | 2 |
| `code/` | `engineering/L2-tooling` | 11 |
| `computer_communication/` | `linux/L1-daily-ops` | 1 |
| `distributed/` | `distributed/L1-foundations` 7 · `L2-consensus` 28 · `L3-ha-and-dr` 18 · `L4-field-notes` 11 | 64 |
| `docker/` | `engineering/L3-container` | 11 |
| `dpdk/` | `dataplane/L1-environment` 15 · `L2-architecture` 2 · `L3-plugin-dev` 5 · `L4-testing` 4 | 26 |
| `edit/` | `engineering/L2-tooling` | 4 |
| `es/` | `engineering/L4-web` | 4 |
| `faq/` | `engineering/L2-tooling` | 1 |
| `go_web/` | `engineering/L4-web` | 1 |
| `language/` | `engineering/L1-basics` | 16 |
| `life/` | `life/L1-learning-method` 6 · `L2-exam-prep` 12 · `L3-economy` 6 · `L4-hometown` 2 · `blogging/L3-distribution` 1 · `L4-video-pipeline` 9 | 36 |
| `opc/` | `engineering/L2-tooling` | 1 |
| `page/` | `engineering/L1-basics` 1 · `L4-web` 11 | 12 |
| `platform-meta/` | `platform-meta/L1-platform-overview` … `L6-video-line`（每段 1 篇） | 6 |
| `programmer_self_cultivation/` | `linux/L2-memory-and-linking` | 1 |
| `protocol/` | `linux/L4-networking` | 11 |
| `source-tracks/` | `postgresql/L1…L8` 209 · `ceph/L1…L2` 9 · `linux-kernel/L1…L3` 6 · `linux/L1…L5` 47 | 271 |
| `stock/` | `life/L3-economy` | 1 |
| `storage/` | `linux/L5-filesystem` | 5 |
| `tools/` | `engineering/L2-tooling` 11 · `L3-container` 4 · `L4-web` 5 | 20 |
| `video_work/` | `blogging/L4-video-pipeline` | 1 |
| `vpp/` | `dataplane/L1-environment` 4 · `L2-architecture` 5 · `L3-plugin-dev` 5 · `L4-testing` 4 | 18 |
| `vue/` | `engineering/L4-web` | 13 |
| `web/` | `engineering/L4-web` | 1 |
| `mail/`、`wiki/` | —— 零文章，删除 | 0 |
| `environment/`、`pcap/`、`src/` | —— 资源归位 / 移出 / 删空文件 | 0 |

合计 590 篇（另有 6 个视频内容单元不在 `docs/` 里，规则用 `path_exact` 单列）。

---

## 五、`data/learning-path.json` 的重写

规则表从「10 条赛道 + 42 个阶段 + 29 条正则 + 26 条 `path_exact`」变成
「11 条赛道 + 48 个阶段 + 48 条 `path_prefix` + 6 条 `path_exact`」，例如：

```json
{
  "id": "postgresql",
  "title": "PostgreSQL 源码内核",
  "track_match": [{ "path_prefix": "source-tracks/postgresql/" }],
  "stages": [
    {
      "id": "L1",
      "title": "起步与全景",
      "match": [{ "path_prefix": "source-tracks/postgresql/L1-getting-started/" }]
    },
    ...
  ]
}
```

**每条规则 = 一个阶段目录。** 以后加一篇文章只需要放进对应的阶段目录，
规则一个字都不用改 —— 这是这次搬家真正买到的东西。

现在规则表里 `path_regex` 有 **29 条**（阶段匹配 26 条 + 赛道匹配 3 条），
`path_exact` 有 **26 条**（6 条给视频单元，20 条给 `tools/` 下的单篇文件）。
搬完之后：正则 **0 条**，`path_exact` 只剩 **6 条**（视频单元不在 `docs/` 里，
没法用目录前缀表示）；那 20 条 `tools/` 单篇规则随着文件落进阶段目录，
自然被阶段目录的 `path_prefix` 覆盖。

### 5.1 视频内容单元

6 个视频单元不在 `docs/` 里，规则用 `path_exact` 单独列（如 `video/row-lock`），
它们的阶段归属（L4 / L5 / L7）不变。

### 5.2 规则表里每条赛道还带一段人写的元信息

`data/learning-path.json` 的每条赛道除了 `id` / `title` / `match`，还有
`icon` / `summary` / `audience` / `goal`，每个阶段还有一句 `goal`。
这些是**人写的**，脚本不生成，搬家时必须**原样带过去**，不能丢：

- 现有 10 条赛道的 `summary` / `audience` / `goal` / 每个阶段的 `goal` —— 原文照抄；
- `platform-meta` 是新赛道，要新写：`icon`（一个 `fas fa-*` 图标名）、
  `summary` / `audience` / `goal`，以及 6 个阶段各自的 `goal`；
- 两个改名的赛道：`db-internals` → `postgresql`、`linux-network` → `linux`，
  `title` 跟着改成「PostgreSQL 源码内核」（原「数据库内核」）；
  `linux-network` 的 `title`「Linux 与网络」**不变**，`summary` / `audience` / `goal` 原文照抄；
- `postgresql` 的 L7 标题「逻辑复制与流式（站内最厚的一块）」里的括号注解
  拆成独立的 `note` 字段，标题本身缩回「逻辑复制与流式」——
  注解是给读者看的，不能进分类链（§7.3）。

### 5.3 守卫

`tests/test_learning_path.py` 现有 **21 条测试**全部保留，另加三条新的：

1. **每个阶段目录必须有且只有一条 `path_prefix` 规则**（防止有人手写一条正则绕过目录）。
2. **每个 `path_prefix` 必须对应一个真实存在的目录**（防止规则指向空目录）。
3. **`fallback_stage` 仍然吸收 0 篇**（原有守卫）。

### 5.4 迁移表怎么造

**决定：复用 `tools/migrate-tree.py` + `data/tree-migration.json`，
不另写新脚本。** 这套机器上一轮已经跑过一次（PostgreSQL 那次 208 篇），
管道顺序、幂等、`git mv` 的边界情况都踩过了。重写一遍只会把踩过的坑再踩一次。

`data/tree-migration.json` 这次要重写的四段：

| 段 | 现在 | 这次 |
| --- | --- | --- |
| `dir_map` | 35 条 | **0 条** —— 顶层目录会拆到多个阶段，目录级规则表达不了，全部逐篇写进 `file_map` |
| `file_map` | 186 条 | **590 条**（逐篇落点，含 3 篇 `.html`） |
| `asset_map` | （没有这一段） | **961 条**（资源的逐文件落点；新增段） |
| `out_map` | 2 条 | **102 条**：解包的 pptx 成品（96 个 OOXML 文件）、`docs/src/test/**`（5 个）、`docs/report_restructured.pptx`（1 个）→ 全部进 `internal/` |
| `drop_files` | （没有这一段） | **22 条**（删掉的东西：`docs/alg/alg_img/` 的 18 个重复 webp、`docs/environment/vfox使用指南`、`docs/source-tracks/postgresql/.claude/settings.json`、2 个 `__pycache__` 里的 .pyc；新增段） |
| `drop_index` | 13 条 | 现在 `docs/` 下的**全部** `_index.md`（75 条） |
| `index_map` | （没有这一段） | **42 条** —— 跟着目录搬走的旧目录页（系列目录 → 阶段目录、赛道目录 → 赛道目录） |
| `index_archive` | （没有这一段） | **28 条** —— 搬不走的旧目录页，存进 `internal/legacy-index/<原路径>` |
| `index_keep` | （没有这一段） | **5 条** —— 原地不动的：`source-tracks/_index.md` 与四个已经在赛道目录上的赛道页 |
| `projects` | 3 块 | **11 块**（每条赛道一块） |
| `ref_rewrites` | 16 条（其中 2 条指向已删除的文件） | 按新 grep 重建（§8.1），**2376 条** |
| `category_redirects` | 13 条 | 重算（新分类链的名字），**67 条** |

`file_map` 的 590 条直接由 §4.2 那个落点脚本生成 ——
**同一个脚本既算落点、又生成搬运表**，不留「文档里的表」和「脚本算的表」两份。

#### 旧目录页的三种去向

`_index.md` 现在是**不发布**的目录页（分类页 2026-11-19 已退休），
它只当分类链的载体（`cascade.categories`）。
可它里面有人手写的东西 —— PostgreSQL 那张「数据库总览」的 mindmap 总图、
人生那条「路径 A / B / C」的阅读路线。**删了就没了**；
留在 `docs/` 里又变成一份没人维护的旧结构说明。折中是分三种去向：

| 去向 | 落点规则 | 条数 |
| --- | --- | --- |
| `index_map`（跟着搬） | ① 赛道目录 → 新的赛道目录；② 系列目录 → 新的阶段目录；③ 其余目录 → 它底下文章的落点（**只认赛道目录和阶段目录** —— 阶段目录下面再放一份 `_index.md`，分类链就变成四级，文章归不进赛道） | 42 |
| `index_archive`（归档） | 落点找不到一个共同的祖先，或者落在阶段目录下面 —— 存进 `internal/legacy-index/<原路径>`。**不删**：那些手写的东西还在，只是不再挂在 `docs/` 里 | 28 |
| `index_keep`（原地不动） | 已经落在新结构里的那几份：`source-tracks/_index.md` 与四个赛道目录页。由 `write_index_files()` 在原地合并 | 5 |

**一个新目录只放得下一份目录页**：文章多的那个赢，
系列目录优先于内容目录（它就是这一段的主页）—— 其余的归档。

这个脚本落在仓库里：`tools/build-tree-migration.py`。
它是**一次性的**（跑完就固化在 `data/tree-migration.json` 里），
但留在仓库里有个好处：以后再搬一次目录，落点是算出来的，不是手抄的。
它必须可重跑 —— 同样的输入产出同样的表。

### 5.5 `migrate-tree.py` 要改哪几处

| 函数 | 要改什么 |
| --- | --- |
| `asset_moves()` | 先读迁移表新增的 `asset_map` 段（逐文件落点），读不到再退回原来的两条规则 |
| `write_index_files()` | `projects` 扩到 11 块；名字从 `data/learning-path.json` 读；顶层改名「内容库」（§7） |
| `index_actions()` | 新增：旧目录页的去向（`move` / `archive` / `keep`）。原先 `drop_index` 里的每一份都是 `git rm` —— 那会把 PostgreSQL 那张「数据库总览」的总图一起删掉 |
| `_merge_index()` | 新增：目录页合并。**front matter 用新的**（`cascade.categories` 是分类链的输入，旧的那份带着旧阶段名，留着就是两份真相），**手写正文留着**（总图、人生的阅读路线），**「本系列文章」那一节用新的**。老目录页**没有 `---` 分隔线**（`sync-hexo.py` 用正则读 `cascade`，不挑写法），拆分 front matter 时要认这两种 |
| `build_redirects()` | 加链式归并（§6.1.1） |
| `rewrite_learning_links()` | 新增：正文里写死的旧赛道地址（`/learning/db-internals/`）改成新赛道地址 —— 真相在 `data/learning-path.json` 的 `aliases` 里 |
| `rewrite_refs()` | 不改逻辑，改 `ref_rewrites` 清单（§8.1） |
| `do_move()` | 不改逻辑，但要处理那篇未入库的 WIP（`git mv` 不动没入库的文件） |
| `main()` | 加 `drop_files` 段的执行（删文件） |

`data/migration-moves.json`（上一轮的解析清单，67 KB）先归档改名，
让脚本从头推（§6.4）。

---

## 六、URL 兼容：重定向 + 日期固化

### 6.1 重定向

`data/redirects.json` 现有 **320 条**，这次新增约 590 条（旧路径 → 新路径）。
生成方式沿用 `tools/migrate-tree.py` 的 `build_redirects()`：由搬运表推出，
带日期段的旧键（上一轮手工补的那 **1 条**）原样保留。

旧地址形如
`/2025/05/17/distributed/foundations/分布式一致性协议/`
→ 新地址
`/2025/05/17/source-tracks/distributed/L1-foundations/分布式一致性协议/`。

### 6.1.1 老重定向要「链式归并」，不能只加不改

**现有 320 条重定向的目标，全部是这次要搬的路径。**
上一轮它们是 `cluster/x` → `distributed/consensus/x`；
这一轮 `distributed/consensus/x` 又搬到了 `source-tracks/distributed/L2-consensus/x`。

`build_redirects()` 只从「本轮的旧路径 → 新路径」推出条目，
**它不知道上一轮那张表的去向**。所以照它跑完，`cluster/x` 还会指向
`distributed/consensus/x` —— 一个**这一轮之后就不存在**的中间地址。
老 URL 会跳到一个死路上。

**做法**：搬运表生成之后、写重定向表之前，先把旧表按新表**归并一遍**：

```
新表[旧键] = 新表.get(旧表[旧键], 旧表[旧键])
```

即：旧键的目标如果也在本轮被搬了，就把它的目标改成**最终新路径**，
不留在中间路径上。320 条全部要过这一遍。

**验收**：重定向表里不允许出现任何「目标不是当前 `docs/` 里的文章」的条目
（`source/` 里的视频、`/learning/` 页面除外）—— 写一条测试钉住。

### 6.2 日期固化

`data/date-overrides.json` 按**新路径**存日期（现 **579 条**，这次约 590 条）。
理由见 `tools/migrate-tree.py` 的文件头：`sync-hexo.py` 的 `git_date()` 走
`git log --all --reverse -- <路径>`，路径一变，最早的提交就是「搬运」那一次，
全站日期一起跳到搬运日。**搬家前先把日期按新路径固化。**

### 6.3 站内相对链接

`tools/migrate-tree.py` 的 `rewrite_relative_links()` 处理两类：

- 被搬文件内部的相对链接（按新位置重算）；
- 留在原地的文件里指向被搬文章的链接。

搬完跑 `tools/check-internal-links.py`：**产物侧站内 href 零死链**，
母稿侧相对链接解析失败数**不得高于搬家前的基线**（当前基线 5 条，逐条核对过是误报）。

### 6.4 上一轮的运行产物要先归档

`data/migration-moves.json` 是 `tools/migrate-tree.py` 上一轮跑出来的
**解析清单**（67 KB，208 条）。这次跑之前要把它归档（改名留档），
让脚本从头推：

- 留着它 → `load_resolved()` 会把上一轮的 208 条旧搬迁合进本轮的表，
  于是 `build_redirects()` 会为 `cluster/x` 再生成一条指向
  `distributed/consensus/x` 的条目 —— 正是 §6.1.1 要避免的中间地址；
- `data/redirects.json` 和 `data/date-overrides.json` 是**源**，
  不是运行产物，要留在原地被本轮更新。

---

## 七、分类链与目录页重建

分类页 2026-11-19 已整套退休，但**分类链还在算**，它现在是**检索维度**
（搜索索引读它）。所以：

1. 每个赛道目录、每个阶段目录都要有 `_index.md`，带 `title:` 和 `cascade.categories:`；
2. `tools/migrate-tree.py` 的 `write_index_files()` 已经能按 `projects` 表
   生成这套目录页（含「本系列文章」清单）—— 本次把 `projects` 表从 3 块扩到 11 块，
   `series` 的 slug 用 `L1-xxx` 这种带编号的名字，顺序即学习顺序；
3. 链条仍然是三级：**顶层 → 赛道 → 阶段**（中文名不带 `L#`）。

链条怎么拼（`tools/sync-hexo.py` 的 `resolve_post_categories()` 读的是这个）：
`primary` = **顶层目录**的 `_index.md` 标题，然后从浅到深把每一级祖先的
`cascade.categories` 追加上去（去重）。所以每个 `_index.md` 的
`cascade.categories` 只写**自己那一级的中文名**就够，链条自动长出来。

### 7.1 中文名的唯一来源：`data/learning-path.json`

**决定（我的判断，可以推翻）：分类链的三级名字全部取自
`data/learning-path.json` 的 `title` 字段**，不再另立一张名字表。

理由：赛道名和阶段名在规则表里已经写好了一份（11 + 48 条），
学习路径页显示的就是它。再手写一份中文名，两份必然漂移 ——
这正是 `docs/platform-meta/info-architecture/category-restructure-and-learning-path.md`
里说的「一个站有两个真相」。脚本从 JSON 读名字，`_index.md` 的 `title`
与规则表永远一致。

落点：`tools/migrate-tree.py` 里写死的 `TOP_DISPLAY_NAMES` /
`PROJECT_DISPLAY_NAMES` 两个字典删掉，改成读 `data/learning-path.json`。

### 7.2 顶层中文名要改：「源码主线」→「内容库」

`docs/source-tracks/` 这次装的是**全部**内容 —— 不只是 PostgreSQL / Linux /
Ceph，还有 AI、人生、博客、平台元数据。顶层分类还叫「源码主线」就名不副实了
（今天它只覆盖 270 篇，搬完是 590 篇全覆盖）。

**决定：顶层 `_index.md` 的 `title:` 改成「内容库」。**

目录名 `source-tracks/` **不动**（URL 段保持不变，中文名只影响分类链，
而分类页已退休、不产生任何页面，只进搜索索引）。改目录名要连带重写
`data/redirects.json` 的键和 243 处代码与配置里的硬编码路径，
收益只有「名字更准」，不值当。

### 7.3 分类链会变哪些名字（逐条列出来）

赛道级 11 个名字（左边是现在链上的，右边是搬完的）：

| 赛道 | 现在链上的名字 | 搬完 |
| --- | --- | --- |
| `postgresql` | PostgreSQL | PostgreSQL 源码内核 |
| `distributed` | 分布式与架构 | 分布式与集群 |
| `ceph` | Ceph | Ceph 源码 |
| `linux-kernel` | Linux 源码 | Linux 源码（不变） |
| `linux` | Linux | Linux 与网络 |
| `dataplane` | —（散在 `dpdk/`、`vpp/` 下，没有统一赛道名） | 数据面：DPDK · VPP |
| `ai-tools` | —（散在 `ai/`、`chatgpt/`） | AI 与工具 |
| `engineering` | —（散在 `code/`、`docker/`、`vue/`…） | 工程与语言 |
| `life` | 人生 | 人生与成长 |
| `blogging` | —（散在 `blog/`） | 博客与自媒体 |
| `platform-meta` | 平台元数据 | 平台元数据（不变） |

阶段级 48 个名字里，**42 个沿用现有 `_index.md` 的名字**，
**6 个改**（PostgreSQL 4 个、分布式 1 个、Linux 1 个）。
新赛道（`dataplane` / `ai-tools` / `engineering` / `life` / `blogging`）
的 20 个阶段本来就是新赛道、新阶段，名字直接用规则表里已有的那套。
`platform-meta` 的 6 个阶段沿用现有名字：
平台总览 / 内容模型 / 构建流水线 / 信息架构 / 多平台分发 / 视频生产线。

改动最明显的是 PostgreSQL 的 4 个：

| 阶段 | 现在 | 搬完 |
| --- | --- | --- |
| L2 | 存储引擎 | 存储引擎：页、文件与内存 |
| L3 | 索引与查询 | 索引与查询管线 |
| L4 | 事务与并发 | 事务、MVCC 与并发 |
| L5 | WAL 与恢复 | WAL、checkpoint 与恢复 |

另外两处：`distributed` 的 L3「高可用与容灾」→「高可用方案与选型」，
`linux` 的 L1「日常操作与工具」→「Linux 入门与日常操作」。

`postgresql` 的 L7 标题是「逻辑复制与流式（站内最厚的一块）」——
括号里是给读者看的注解，**不进分类链**，链上叫「逻辑复制与流式」。
规则表里把注解拆成独立的 `note` 字段。

**代价**：搜索索引里的 6 个分类名会变。
分类页已退休，**没有任何页面依赖这些名字**，唯一的消费者是搜索索引，
所以这是「换个说法」而不是「丢了一类」。

### 7.4 `write_index_files()` 要改三处

1. **赛道名和阶段名不再写死**：`PROJECT_DISPLAY_NAMES` 那个字典删掉，
   名字从 `data/learning-path.json` 读（§7.1）；
2. **顶层名改成「内容库」**：顶层目录名 `source-tracks` 不是赛道 id，
   在规则表里没有对应项，所以顶层名留在代码里当常量
   （`TOP_DISPLAY_NAMES = {"source-tracks": "内容库"}`）。
   同时描述文案「源码主线：按「一条主线走到底」的顺序组织的内容。」
   也要改 —— 现在装的是 11 条赛道，不是一条主线；
3. `kind = "源码主线" if target_root.startswith("source-tracks/") else "专题"`
   这行的两个字也要改成「内容库」。

`projects` 表从 3 块扩到 11 块，每块 `target_root` 是
`source-tracks/<赛道id>`，`series` 的 slug 是 48 个阶段目录名，
`series_meta` 是各阶段的一句中文描述。

---

## 八、站点外部的硬编码路径

全仓 243 处硬编码 `docs/` 路径，另有 1940 处 `docs/` / `source-tracks/`
出现在 `.md` 正文里。两类处理方式**完全不同**：

| 类别 | 数量 | 怎么处理 |
| --- | --- | --- |
| **代码与配置**（`.py` / `.js` / `.json` / `.yml` / `.sh`） | 243 处 | **必须改对**，否则构建期、测试期直接报错 |
| **散文里的路径提及**（`.md` 正文） | 1940 处 | **绝大多数不改** —— 那是文章在讲历史结构，改了反而篡改原意 |

**决定：批量改写只覆盖代码与配置，散文不动。**
散文里的路径提及分三类：① 描述旧结构的叙述（保留，那是历史快照）；
② 指向站内文章的**相对链接**（由 `rewrite_relative_links()` 处理）；
③ 指向 `/learning/` 页面的**绝对地址**（手工改，见 §8.3）。

搬运表里的 `ref_rewrites` 段落描述代码与配置里要改的位置，
`rewrite_refs()` 按五种形态改写：

| 形态 | 含义 | 例 |
| --- | --- | --- |
| `docs` | 母稿路径，含扩展名 | `docs/distributed/foundations/x.md` |
| `flat` | 产物里的拍平路径 | `distributed/foundations/x.md` |
| `postid` | 产物路径去掉 `.md` | `distributed/foundations/x` |
| `permalink` | 站内绝对地址（带日期段） | `/2023/09/14/source-tracks/postgresql/...` |
| `cid` | 内容单元 id | `db/postgresql/foo` |

**逐个核对，不批量替换** —— 上一轮的经验是批量替换会误伤
（`tools/migrate-tree.py:394` 那条注释就是踩过的坑）。

### 8.1 `ref_rewrites` 要按新 grep 重建

现有 16 条 `ref_rewrites` **已经过期**：里面 `data/featured.json`、
`tools/templates/database.md` 两个文件**早就不存在了**
（`data/featured.json` 已删，`tools/templates/` 目录已删）。
留着的后果是 `rewrite_refs()` 找不到文件，行为未定义。

本次按最新 grep 重建，命中数（`grep -c "docs/\|source-tracks/"`）：

| 文件 | 处数 | 形态 | 备注 |
| --- | --- | --- | --- |
| `tools/add-tags.py` | 104 | `flat` | 一张「文章路径 → 标签」的硬编码表，全部要跟着阶段目录改名 |
| `tools/sync-hexo.py` | 53 | `docs` | 工具自身的路径常量 |
| `publish/tests/test_episode.py` | 32 | `docs` / `cid` | 测试用例里的样本路径 |
| `tests/test_review_records.py` | 18 | `docs` | 审校台账的路径校验 |
| `tests/test_review_articles.py` | 18 | `docs` | 同上 |
| `tests/test_episode_block.py` | 12 | `docs` / `permalink` / `cid` | |
| `tests/test_review_check.py` | 11 | `docs` | |
| `publish/publishkit/episode.py` | 10 | `docs` | 内容单元的路径解析 |
| `tools/build-learning-path.py` | 10 | — | 见 §8.2 |
| `tools/review-check.py` | 8 | `docs` | |
| `tests/test_podcast_spec.py` | 8 | `docs` | |
| `publish/tests/test_sync_exclusions.py` | 8 | `docs` | |
| 其余 20 多个文件 | 各 1–10 | 混合 | `weixin/wechat/cli.py`、`publish/publishkit/contract.py`、`aiv/scripts/sync_publish_docs.py`、`tools/draft-descriptions.py`、`tools/capture-dates.py` 等 |

`data/` 下的四个 JSON（`migration-moves.json` 413、`date-overrides.json` 260、
`redirects.json` 255、`tree-migration.json` 188）**不手工改**：
前三个由脚本生成，第四个是搬运表本身。

**验收**：搬完之后重新 grep 一次全仓，
`docs/<旧路径>` 形式的硬编码**命中数必须为 0**（散文除外，见上）。
写一条测试钉住。

### 8.2 `tools/build-learning-path.py` 里有一处写死的赛道地址

`tools/build-learning-path.py`（生成学习路径首页那段）里写着：

```python
"已经在写数据库内核 | 直接进 [数据库内核](%s) 的 **L7** |" % _rooted_path("/learning/db-internals/"),
```

赛道 id 改名之后这行会指向死链。它要改成**从规则表里按 id 查**，
不能再写死字符串：

```python
pg = next(t for t in tracks if t["id"] == "postgresql")
... _rooted_path("/learning/%s/" % pg["id"])
```

已经改掉了，落在 `_deep_dive_cell()` 里：赛道 id、赛道名、阶段 id、
阶段名全部从 `data/learning-path.json` 读，写死一处就漂一处。

### 8.3 站内绝对地址 `/learning/<赛道id>/` 要手工改

改赛道 id 会改掉两条赛道的 `/learning/` 页面地址（`db-internals` → `postgresql`、
`linux-network` → `linux`）。`docs/` 里有 **25 条**提到 `/learning/` 的绝对地址，
自动改写**不会碰它们**（改写器只处理相对链接）。逐条分类：

| 现在的地址 | 条数 | 状态 | 怎么处理 |
| --- | --- | --- | --- |
| `/learning/db-internals/` | 11 | 活 | 改成 `/learning/postgresql/` |
| `/learning/linux-network/` | 1 | 活 | 改成 `/learning/linux/` |
| `/learning/posgresql-fsm/` | 1 | 死（这条赛道从来不存在） | 改成 `/learning/postgresql/` |
| `/learning/distributed/` | 2 | 活 | 不变 |
| `/learning/db-internals/<中文专题>/`（percent-encoded） | 5 | 死（分类页 2026-11-19 已退休） | 顺手改成 `/learning/postgresql/` |
| 占位文字（`/learning/...`、`/learning/<赛道>/`、`/learning/`） | 5 | 不是链接 | 不动 |

分布：`docs/source-tracks/postgresql/_index.md` 16 条、
`docs/source-tracks/postgresql/extensions-perf/postgresql-community-gems/index.md` 3 条、
`docs/blog/` 5 条、`docs/source-tracks/postgresql/replication-ha/…/index.md` 1 条。

同时给这两个旧地址各加一条重定向（`data/redirects.json` 手加，
`build_redirects()` 不会自动生成 —— 它只从 `docs/` 里的文章推出）。

**注意：`data/redirects.json` 撑不起这件事。**
`sync-hexo.py` 的 `_redirect_target_file()` 只认「能在 `docs/` 里找到源文件」的目标，
`/learning/postgresql/` 不是一篇文章 —— 直接往重定向表里加会得到
`WARNING redirect target missing`，重定向页不生成。
所以别名页要由 `tools/build-learning-path.py` 一起写出来：
赛道加一个 `aliases: ["db-internals"]` 字段，生成器在
`source/learning/db-internals/index.md` 额外写一页跳转（meta refresh + canonical），
指到新赛道页。

---

## 九、清理清单

搬的过程中一并处理（都不进新树）：

| 东西 | 位置 | 处理 |
| --- | --- | --- |
| 解包的 pptx 成品 | `docs/source-tracks/postgresql/logical-replication/sqlserver/unpacked/`（**96 个文件**，含 `ppt/slides/` 等 OOXML） | 移出 `docs/` 到 `internal/` |
| Python 字节码 | `docs/code/python-work/pytest/__pycache__/`、`docs/code/python-work/yaml_test/__pycache__/` | 删除（加进 `.gitignore`） |
| 编辑器配置 | `docs/source-tracks/postgresql/.claude/` | 删除（加进 `.gitignore`） |
| 空文件 | `docs/environment/vfox使用指南`（0 字节，内容与 `docs/computer_communication/现代信息查询与检索技巧.md` 重复） | 删除 |
| 零文章分类 | `docs/mail/`、`docs/wiki/` | 删除（各自只有一句「本分类下的文章。」的 `_index.md`） |
| 无人引用的 C 测试代码 | `docs/src/test/`（`test_misc` / `test_module`） | 移到 `internal/` |
| 顶层交付物 | `docs/report_restructured.pptx` | 移到 `internal/` |

### 9.1 两篇讲「结构本身」的文章要同步

`docs/platform-meta/info-architecture/category-restructure-and-learning-path.md` 里写满了
旧结构的数字（39 个顶层目录 → 37 个、分类名 46 → 59、「现在是 37 个顶层目录、59 个分类名」）。
搬完这些数字全变了，而且这篇文章本身就是 `platform-meta` 赛道的一篇 ——
它会被搬到 `source-tracks/platform-meta/L4-info-architecture/`。

两种处理：

1. **加一节「2026-11-26 后续」**，像那篇 2026-11-19 的后续注记一样，
   说明分类树退休之后又发生了什么（本文即那篇的后续）；
2. 正文里的旧数字**保留不改** —— 它们标注了测量日期，是历史快照，不是错。

`docs/platform-meta/info-architecture/_index.md` 里那句
「下一篇会讲剩下的子树怎么逐块搬」也要改成指向本次搬家。

### 9.2 新增一篇讲这次搬家的文章

按仓库的惯例（`docs/platform-meta/` 每个系列都有成稿），
`platform-meta/L4-info-architecture/` 下应该有一篇
「把 `docs/` 的目录重排成学习路径的镜像」——
就是这份设计文档的对外版本：为什么搬、搬成什么样、代价是什么、
以及「规则表里一条正则都不剩」这个验收标志。

**这篇要等你确认设计之后才写** —— 它是对外的说法，跟设计文档不是一回事。

---

## 十、`review/` 台账同步

`review/` 下 29 个文件，其中 **20 份是逐篇审校记录**（每份开头一行
「原文：docs/<路径>」）。搬家后这些路径会失效，必须同步改。

### 10.1 记录文件本身要搬家

`tests/test_review_records.py` 钉死一条：**记录必须放在原文所属的一级目录下**
（`review/<pillar>/` 的 `<pillar>` 必须是 `docs/` 下的一级目录名）。
搬完之后 `docs/` 只剩 `source-tracks/` 一个一级目录，
所以**所有记录都要落到 `review/source-tracks/` 下**，
而且目录要镜像文章的路径 —— `review/source-tracks/<赛道>/<阶段>/...`。

现在 `review/base/`（1 份）、`review/distributed/`（12 份）下的 13 份记录要搬，
`review/source-tracks/` 下的 7 份要加 `L#-` 那一层。

| 现在 | 搬完 |
| --- | --- |
| `review/base/file.md` | `review/source-tracks/engineering/L1-basics/file.md` |
| `review/distributed/foundations/分布式一致性协议.md` | `review/source-tracks/distributed/L1-foundations/分布式一致性协议.md` |
| `review/source-tracks/postgresql/transaction-mvcc/postgresql-mvcc.md` | `review/source-tracks/postgresql/L4-transaction-mvcc/postgresql-mvcc.md` |

### 10.2 记录里的「原文」路径要改

每份记录开头那行 `- 原文：docs/<路径>` 要改成新路径。
`tests/test_review_records.py` 的 `test_record_source_file_exists()`
会检查这个路径**真实存在** —— 忘了改就是孤儿记录，测试直接红。

### 10.3 索引与统计要重算

- `review/INDEX.md`：表格里的「记录」列（路径）要跟着改，
  测试要求索引与磁盘上的记录**一一对应**；
  里面的统计数字（661 / 437 / 224 / 639）按新树重算；
- `review/scope/2026-11-14-scope-classification.md`（338 行，逐篇列了路径与计数）
  里的路径要改，**计数要重算**（上一篇提到上次改一次计数漂移了一次）。
  重算的办法：拿 `tools/review-check.py` 对新树跑一遍信号，
  按「桶 1–6」的分类重新统计，**逐篇比对旧表**，
  确认哪些文章因为换目录而改变了归类（换目录不该改变「这是不是技术文章」
  这个判断，只会让它所在的支柱名变了）。

### 10.4 历史计划与设计文档不改

`review/plans/`（6 份）、`review/specs/`（2 份）、`review/README.md`
里的路径是**历史快照**，改了就是篡改历史 —— 一律不动。
它们引用的文章路径搬完会变成死链，这是可接受的：
审校记录不是给人顺着链接逛的，是给作者和审校者查的。

唯一例外：`review/README.md` 里的模板示例
`- 原文：docs/…/文章.md` 是**占位写法**，本身就不指向真实文章，不用改。

---

## 十一、回归与验收

搬完必须全绿（命令沿用 `tools/migrate-tree.py` 文件头里的清单）：

```bash
python3 tools/capture-dates.py --check data/date-overrides.json   # 日期逐篇一致
python3 tools/check-internal-links.py                              # 站内链接
python3 tools/check-markdown.py                                    # Markdown 规范
python3 tools/check-mermaid.py                                     # Mermaid 图
python3 tools/build-learning-path.py --check                       # 596 篇全归类、兜底 0
python3 tools/review-check.py                                      # 审校信号
python3 -m pytest tests/ -q                                       # 全量测试
npx hexo generate                                                  # 产物构建
```

**验收标准（数字，不是感觉）**：

| 项 | 搬家前 | 搬家后必须 |
| --- | --- | --- |
| 学习路径归类 | 596 / 596，兜底 0 | 同左 |
| 阶段号与赛道归属 | 逐篇不变 | **590 篇里 589 篇逐篇不变**；唯一变化是 `platform-meta` 的 6 篇从 blogging 的 4 个阶段里独立出来（§3 说明 1） |
| 产物侧站内死链 | 0 | 0 |
| 母稿侧相对链接解析失败 | 5 | ≤ 5（且不多于基线） |
| `docs/` 顶层目录 | 34 | 1（`source-tracks/`） |
| 赛道 / 阶段 | 10 / 42 | 11 / 48 |
| `learning-path.json` 里的 `path_regex` 条数 | 29 | 0 |
| `learning-path.json` 里的 `path_exact` 条数 | 26 | 6（只剩视频单元） |
| 重定向条目 | 320 | ≥ 910（320 + 590，且每条目标都存在） |
| 代码与配置里硬编码的旧 `docs/` 路径 | 243 处 | **0** |
| 落点冲突 | — | 0（§4.2 的脚本必须复算通过） |
| 资源丢失 | 1083 | 961（搬到新树）+ 102（移出 `docs/` 进 `internal/`）+ 20（删掉：18 个重复 webp、1 个空文件、1 个编辑器配置；另 2 个 `.pyc` 早已不在树上） |

最后一条 `path_regex` 是这次搬家真正的验收标志：**规则表里一条正则都不剩。**

**新增守卫测试**（写进 `tests/test_learning_path.py` 或新文件）：

1. 每条重定向的目标都必须能在 `docs/` 里找到文章（§6.1.1 的链式归并）；
2. 每个阶段目录恰好一条 `path_prefix` 规则，且目录真实存在（§5.3）；
3. `fallback_stage` 吸收 0 篇（原有守卫）；
4. 分类链是三级、且每篇文章的 `categories` 长度与链条长度一致（§7）；
5. `review/` 里每份记录的「原文」路径存在，且记录在原文的一级目录下（§10）。

---

## 十二、不做的事 / 已知代价

- **不删除任何旧 URL** —— 靠重定向表接住。
- **不重排文章在阶段内部的顺序** —— 阶段内仍按「编号系列在前、其余按时间」。
- **不改文章正文与 front matter** —— 搬家是目录工程，不是内容工程。
  （例外：那 25 处 `/learning/` 绝对地址要改，见 §8.3；它们是链接，不是内容。）
- **不合并重复文章** —— 有重复的（`corosync-down…` 两版等）由审校流程处理。
- **不留旧目录副本** —— 双轨会让「文章在哪」有两个答案。
- **不改散文里的历史路径描述** —— 那是历史快照（§8）。
- **代价**：590 篇的 URL 全变（重定向接住），`/learning/db-internals/` →
  `/learning/postgresql/`、`/learning/linux-network/` → `/learning/linux/` 两处换名。
- **代价**：物理目录从「按学科和工具切」变成「按教学轴切」，
  找「所有 Docker 文章」得走 `source-tracks/engineering/L3-container/` ——
  检索靠分类链和搜索，不靠目录。
- **代价**：6 个分类名要换（§7.3），搜索索引里的分类维度变一次。
- **代价**：顶层目录名还叫 `source-tracks/`，但里面装的不只是源码主线了。
  改目录名要连带重写 `data/redirects.json` 的键和 243 处硬编码路径，
  收益只有「名字更准」，这次不做（§7.2）。

---

## 相关文档

- [分类不是导航，学习路径才是](../../docs/platform-meta/info-architecture/category-restructure-and-learning-path.md)
  — 为什么要把「分类」和「学习路径」分开，这篇是它的续集
- [学习路径：把 577 篇文章排成一条能读下去的路](../plans/2026-11-17-学习路径.md)
  — 上一轮的规则表设计，本次是它的物理落地
- [内容分类与结构重构](../plans/2026-11-17-内容分类与结构重构.md)
  — 上一轮的目录搬迁，本次是它的续集
