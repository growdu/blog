# 全树范围分类：哪些不是面向读者的技术文章

- 日期：2026-11-14（2026-11-26 按新目录树更新；2026-11-27 加了成长路线那篇）
- 依据：`tools/review-check.py` 对 `docs/` 全树（649 篇）跑出的信号，加逐篇读原文的判断
- 目的：把审校范围从「四支柱 282 篇」扩到全树之前，先把**不面向读者的技术文章**筛掉，
  免得把站点目录页、内部工作文档、命令速查表也按技术深度五要素去审。

## 五个桶

| 桶 | 含义 | 篇数 | 技术深度五要素 |
| --- | --- | --- | --- |
| 1 非内容 | 根本不面向读者：站点目录页、代码仓库说明、内部工作文档、外链指北、只有标题的未成稿 | 105 | 不审 |
| 2 速查/清单/操作类 | 面向读者，但形态是命令表、步骤、清单，没有成篇解释 | 49 | 不适用 |
| 3 非技术内容 | 面向读者，但写的是生活、备考、内部规范 | 38 | 不适用 |
| 4 转载内容 | 标了来源、署名他人的转载稿 | 17 | 不按原创稿审改 |
| 5 技术文章 | 面向读者的技术解释 | 440 | **审** |

**审校工作面 = 440 篇**（桶 5）。桶 2、3 面向读者但不是技术文章，
可选做表达与结构审，不套五要素；桶 1 不审；桶 4 是转载稿，
怎么处理（保留标注 / 删除 / 重写）是站长的决定。

## 判据

机械层（可复跑）：

- 目录页：文件名为 `_index.md`
- 代码仓库说明：文件名是 `readme.md`，且所在的目录是一个代码工程目录（`*work/`）
- 转载稿：正文顶部有 `> 来源:` 标记
- 只有标题的未成稿：排开标题、代码块、表格之后的正文不超过 10 个字符

人工层（逐篇读过原文，一次判断写死）：

- 内部工作文档：开发交付计划、验证步骤、测试进度表、内部规范、个人数据记录
- 外链指北：正文只有 `# reference` 链接列表
- 速查/清单/操作类：有内容但形态是命令表、步骤、清单，没有机制解释
- 非技术内容：`life/` 赛道、`stock/`、`ai-tools/` 科普系列、`chatgpt/`
- 转载内容：正文顶部有 `> 来源:` 标记，署名他人

复跑方式：

```bash
python3 tools/review-check.py docs --json --out /tmp/all_docs.json
```

## 逐赛道分布

目录重排之后，`docs/` 下只有一条赛道树：内容库 → 赛道 → 阶段。
「支柱」这个说法没了 —— 支柱是当初的四根柱子，现在是十一条赛道。

| 赛道 | 总数 | 非内容 | 速查操作 | 非技术 | 转载 | 技术文章 | warn | DEP-00 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 内容库首页 | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 1 |
| ai-tools | 36 | 5 | 0 | 6 | 17 | 8 | 28 | 10 |
| blogging | 25 | 9 | 0 | 7 | 0 | 9 | 13 | 5 |
| ceph | 12 | 3 | 0 | 0 | 0 | 9 | 7 | 1 |
| dataplane | 49 | 7 | 9 | 0 | 0 | 33 | 25 | 20 |
| distributed | 69 | 12 | 1 | 0 | 0 | 56 | 47 | 31 |
| engineering | 114 | 23 | 24 | 0 | 0 | 67 | 80 | 61 |
| life | 31 | 6 | 0 | 25 | 0 | 0 | 16 | 5 |
| linux | 71 | 14 | 7 | 0 | 0 | 50 | 43 | 32 |
| linux-kernel | 10 | 4 | 0 | 0 | 0 | 6 | 8 | 3 |
| platform-meta | 15 | 7 | 0 | 0 | 0 | 8 | 7 | 7 |
| postgresql | 216 | 14 | 8 | 0 | 0 | 194 | 140 | 30 |
| **合计** | **649** | **105** | **49** | **38** | **17** | **440** | **415** | **206** |

## 排除清单

下面四桶逐篇列出。契约测试守着两件事：清单里的路径不许悬空；审校记录的原文不许落在清单里。

### 桶 1 非内容（105 篇）


#### 站点目录页（60 篇）

- `docs/source-tracks/_index.md`
- `docs/source-tracks/ai-tools/L1-concepts/_index.md`
- `docs/source-tracks/ai-tools/L2-toolbox/_index.md`
- `docs/source-tracks/ai-tools/L3-leverage/_index.md`
- `docs/source-tracks/ai-tools/L4-video-platform/_index.md`
- `docs/source-tracks/ai-tools/_index.md`
- `docs/source-tracks/blogging/L1-setup/_index.md`
- `docs/source-tracks/blogging/L2-content/_index.md`
- `docs/source-tracks/blogging/L3-distribution/_index.md`
- `docs/source-tracks/blogging/L4-video-pipeline/_index.md`
- `docs/source-tracks/blogging/_index.md`
- `docs/source-tracks/ceph/L1-getting-started/_index.md`
- `docs/source-tracks/ceph/L2-architecture/_index.md`
- `docs/source-tracks/ceph/_index.md`
- `docs/source-tracks/dataplane/L1-environment/_index.md`
- `docs/source-tracks/dataplane/L2-architecture/_index.md`
- `docs/source-tracks/dataplane/L3-plugin-dev/_index.md`
- `docs/source-tracks/dataplane/L4-testing/_index.md`
- `docs/source-tracks/dataplane/_index.md`
- `docs/source-tracks/distributed/L1-foundations/_index.md`
- `docs/source-tracks/distributed/L2-consensus/_index.md`
- `docs/source-tracks/distributed/L3-ha-and-dr/_index.md`
- `docs/source-tracks/distributed/L4-field-notes/_index.md`
- `docs/source-tracks/distributed/_index.md`
- `docs/source-tracks/engineering/L1-basics/_index.md`
- `docs/source-tracks/engineering/L2-tooling/_index.md`
- `docs/source-tracks/engineering/L3-container/_index.md`
- `docs/source-tracks/engineering/L4-web/_index.md`
- `docs/source-tracks/engineering/_index.md`
- `docs/source-tracks/life/L1-learning-method/_index.md`
- `docs/source-tracks/life/L2-exam-prep/_index.md`
- `docs/source-tracks/life/L3-economy/_index.md`
- `docs/source-tracks/life/L4-hometown/_index.md`
- `docs/source-tracks/life/_index.md`
- `docs/source-tracks/linux-kernel/L1-getting-started/_index.md`
- `docs/source-tracks/linux-kernel/L2-architecture/_index.md`
- `docs/source-tracks/linux-kernel/L3-process-memory/_index.md`
- `docs/source-tracks/linux-kernel/_index.md`
- `docs/source-tracks/linux/L1-daily-ops/_index.md`
- `docs/source-tracks/linux/L2-memory-and-linking/_index.md`
- `docs/source-tracks/linux/L3-kernel-internals/_index.md`
- `docs/source-tracks/linux/L4-networking/_index.md`
- `docs/source-tracks/linux/L5-filesystem/_index.md`
- `docs/source-tracks/linux/_index.md`
- `docs/source-tracks/platform-meta/L1-platform-overview/_index.md`
- `docs/source-tracks/platform-meta/L2-content-model/_index.md`
- `docs/source-tracks/platform-meta/L3-build-pipeline/_index.md`
- `docs/source-tracks/platform-meta/L4-info-architecture/_index.md`
- `docs/source-tracks/platform-meta/L5-multiplatform/_index.md`
- `docs/source-tracks/platform-meta/L6-video-line/_index.md`
- `docs/source-tracks/platform-meta/_index.md`
- `docs/source-tracks/postgresql/L1-getting-started/_index.md`
- `docs/source-tracks/postgresql/L2-storage-engine/_index.md`
- `docs/source-tracks/postgresql/L3-index-and-query/_index.md`
- `docs/source-tracks/postgresql/L4-transaction-mvcc/_index.md`
- `docs/source-tracks/postgresql/L5-wal-and-recovery/_index.md`
- `docs/source-tracks/postgresql/L6-replication-ha/_index.md`
- `docs/source-tracks/postgresql/L7-logical-replication/_index.md`
- `docs/source-tracks/postgresql/L8-extensions-perf/_index.md`
- `docs/source-tracks/postgresql/_index.md`

#### 只有标题的未成稿（24 篇）

- `docs/source-tracks/engineering/L1-basics/download.md`
- `docs/source-tracks/distributed/L3-ha-and-dr/Patroni详解.md`
- `docs/source-tracks/distributed/L2-consensus/corosy-qdevice源码阅读.md`
- `docs/source-tracks/distributed/L3-ha-and-dr/业界高可用解决方案.md`
- `docs/source-tracks/distributed/L4-field-notes/repmgr网络割裂问题.md`
- `docs/source-tracks/distributed/L3-ha-and-dr/主流分布式高可用方案.md`
- `docs/source-tracks/distributed/L1-foundations/分布式存储需要解决的问题.md`
- `docs/source-tracks/distributed/L1-foundations/分布式系统设计必知必会.md`
- `docs/source-tracks/postgresql/L7-logical-replication/ai_coding/逻辑复制支持ddl ai配置流程.md`
- `docs/source-tracks/dataplane/L3-plugin-dev/vpp插件开发.md`
- `docs/source-tracks/engineering/L1-basics/pytest/pytest进阶.md`
- `docs/source-tracks/engineering/L1-basics/rust设计原则.md`
- `docs/source-tracks/linux/L3-kernel-internals/linux数据预取.md`
- `docs/source-tracks/linux/L1-daily-ops/shell使用.md`
- `docs/source-tracks/linux/L4-networking/C语言网络编程库选择.md`
- `docs/source-tracks/linux/L4-networking/mtu路径发现pmtu详解.md`
- `docs/source-tracks/engineering/L4-web/gui.md`
- `docs/source-tracks/engineering/L4-web/read-pdfbox-source-code.md`
- `docs/source-tracks/postgresql/L5-wal-and-recovery/Checkpoint.md`
- `docs/source-tracks/postgresql/L6-replication-ha/pg_logic_decode.md`
- `docs/source-tracks/postgresql/L6-replication-ha/pg_slot.md`
- `docs/source-tracks/postgresql/L2-storage-engine/mm/pg_page.md`
- `docs/source-tracks/linux/L4-networking/tcp socket必知必会.md`
- `docs/source-tracks/linux/L5-filesystem/sshfs-win精讲.md`

#### 代码仓库说明（11 篇）

- `docs/source-tracks/engineering/L2-tooling/JavaScript-work/readme.md`
- `docs/source-tracks/engineering/L2-tooling/assemble-work/readme.md`
- `docs/source-tracks/engineering/L2-tooling/c-sharp-work/readme.md`
- `docs/source-tracks/engineering/L2-tooling/c-work/readme.md`
- `docs/source-tracks/engineering/L2-tooling/c-work/simple-editor/preview.md`
- `docs/source-tracks/engineering/L2-tooling/c-work/ticket/readme.md`
- `docs/source-tracks/engineering/L2-tooling/gui-work/readme.md`
- `docs/source-tracks/engineering/L2-tooling/html-work/readme.md`
- `docs/source-tracks/engineering/L2-tooling/java-work/readme.md`
- `docs/source-tracks/engineering/L2-tooling/shell-work/readme.md`
- `docs/source-tracks/engineering/L2-tooling/shell-work/vim/readme.md`

#### 内部工作文档与记录（8 篇）

- `docs/source-tracks/engineering/L1-basics/normal.md`
- `docs/source-tracks/dataplane/L4-testing/fastup测试优化完成情况.md`
- `docs/source-tracks/blogging/L4-video-pipeline/aiv/人格规范.md`
- `docs/source-tracks/blogging/L4-video-pipeline/aiv/形象与音色规范.md`
- `docs/source-tracks/blogging/L4-video-pipeline/aiv/背景音乐规范.md`
- `docs/source-tracks/life/L3-economy/zhuangxiu.md`
- `docs/source-tracks/engineering/L2-tooling/opc.md`
- `docs/source-tracks/blogging/L4-video-pipeline/video.md`

#### 只有外链的指北页（2 篇）

- `docs/source-tracks/linux/L3-kernel-internals/linux内核指北.md`
- `docs/source-tracks/linux/L3-kernel-internals/uboot指北.md`

### 桶 2 速查/清单/操作类（49 篇）

- `docs/source-tracks/engineering/L1-basics/git.md`
- `docs/source-tracks/engineering/L1-basics/google.md`
- `docs/source-tracks/engineering/L1-basics/other.md`
- `docs/source-tracks/engineering/L1-basics/vim.md`
- `docs/source-tracks/postgresql/L8-extensions-perf/macos安装mysql.md`
- `docs/source-tracks/postgresql/L1-getting-started/使用meson编译pg.md`
- `docs/source-tracks/engineering/L3-container/docker compose管理容器.md`
- `docs/source-tracks/engineering/L3-container/docker搭建个人镜像仓库.md`
- `docs/source-tracks/dataplane/L4-testing/fastup模拟UE测试.md`
- `docs/source-tracks/dataplane/L1-environment/pktgen.md`
- `docs/source-tracks/dataplane/L1-environment/pktgen编译使用.md`
- `docs/source-tracks/dataplane/L1-environment/ptpclient.md`
- `docs/source-tracks/dataplane/L3-plugin-dev/vpp使用.md`
- `docs/source-tracks/dataplane/L1-environment/交叉编译.md`
- `docs/source-tracks/dataplane/L1-environment/抓包.md`
- `docs/source-tracks/engineering/L2-tooling/texlive安装.md`
- `docs/source-tracks/engineering/L2-tooling/faq汇总.md`
- `docs/source-tracks/engineering/L4-web/go_web.md`
- `docs/source-tracks/engineering/L1-basics/cmake使用指南.md`
- `docs/source-tracks/engineering/L1-basics/pytest自动化测试.md`
- `docs/source-tracks/engineering/L1-basics/python跨平台下载离线安装包.md`
- `docs/source-tracks/engineering/L1-basics/使用mdbook编译html和pdf.md`
- `docs/source-tracks/engineering/L1-basics/搭建内网rust仓库.md`
- `docs/source-tracks/linux/L2-memory-and-linking/ebpf/oltp.md`
- `docs/source-tracks/linux/L1-daily-ops/git指北.md`
- `docs/source-tracks/linux/L1-daily-ops/git高级指北.md`
- `docs/source-tracks/linux/L1-daily-ops/linux常用高级命令.md`
- `docs/source-tracks/linux/L4-networking/抓包指北.md`
- `docs/source-tracks/linux/L1-daily-ops/本地git仓库.md`
- `docs/source-tracks/linux/L1-daily-ops/解决SSH连接Linux超时自动断开.md`
- `docs/source-tracks/distributed/L2-consensus/openguass升级机制.md`
- `docs/source-tracks/engineering/L4-web/python.md`
- `docs/source-tracks/engineering/L4-web/ssh.md`
- `docs/source-tracks/postgresql/L1-getting-started/code-server调试postgresql.md`
- `docs/source-tracks/postgresql/L1-getting-started/initdb.md`
- `docs/source-tracks/postgresql/L1-getting-started/pg_ctl.md`
- `docs/source-tracks/postgresql/L1-getting-started/pg_complie_and_run.md`
- `docs/source-tracks/postgresql/L1-getting-started/postgresql源码编译.md`
- `docs/source-tracks/postgresql/L6-replication-ha/repmgr_cluster.md`
- `docs/source-tracks/engineering/L3-container/codeserver_docker.md`
- `docs/source-tracks/engineering/L2-tooling/doxygen使用指南.md`
- `docs/source-tracks/engineering/L2-tooling/shell常用脚本.md`
- `docs/source-tracks/engineering/L2-tooling/你一定要知道的黑客小技巧.md`
- `docs/source-tracks/dataplane/L3-plugin-dev/fastgtpu配置及cli说明文档.md`
- `docs/source-tracks/dataplane/L1-environment/vpp调试指北.md`
- `docs/source-tracks/engineering/L4-web/cargo构建.md`
- `docs/source-tracks/engineering/L4-web/python环境搭建.md`
- `docs/source-tracks/engineering/L4-web/react app教程.md`
- `docs/source-tracks/engineering/L4-web/vue开发环境搭建.md`

### 桶 3 非技术内容（38 篇）

- `docs/source-tracks/ai-tools/L2-toolbox/01-ai常用工具和开发框架.md`
- `docs/source-tracks/ai-tools/L3-leverage/19_AI是你的杠杆普通人也能用的AI实战教程.md`
- `docs/source-tracks/ai-tools/L2-toolbox/claude配置.md`
- `docs/source-tracks/ai-tools/L2-toolbox/claude安装教程/index.md`
- `docs/source-tracks/ai-tools/L1-concepts/chatgpt使用.md`
- `docs/source-tracks/ai-tools/L1-concepts/newbing使用教程/index.md`
- `docs/source-tracks/blogging/L4-video-pipeline/aiv/brand/README.md`
- `docs/source-tracks/blogging/L4-video-pipeline/aiv/brand/scripts/README.md`
- `docs/source-tracks/blogging/L4-video-pipeline/aiv/character/README.md`
- `docs/source-tracks/blogging/L4-video-pipeline/aiv/index.md`
- `docs/source-tracks/blogging/L4-video-pipeline/aiv/music/README.md`
- `docs/source-tracks/blogging/L4-video-pipeline/aiv/voice/README.md`
- `docs/source-tracks/blogging/L3-distribution/blog-to-wechat/index.md`
- `docs/source-tracks/life/L2-exam-prep/电子科技大学-计算机-自考-复习计划/index.md`
- `docs/source-tracks/life/L2-exam-prep/腾冲事业编-公务员备考计划/index.md`
- `docs/source-tracks/life/L1-learning-method/寻康杯备战方案.md`
- `docs/source-tracks/life/L1-learning-method/寻康杯实战操作手册.md`
- `docs/source-tracks/life/L2-exam-prep/biology-methods/index.md`
- `docs/source-tracks/life/L2-exam-prep/chemistry-methods/index.md`
- `docs/source-tracks/life/L2-exam-prep/english-roots/index.md`
- `docs/source-tracks/life/L2-exam-prep/geography-methods/index.md`
- `docs/source-tracks/life/L2-exam-prep/math-methods/index.md`
- `docs/source-tracks/life/L2-exam-prep/math-paper2/index.md`
- `docs/source-tracks/life/L2-exam-prep/physics-methods/index.md`
- `docs/source-tracks/life/L2-exam-prep/politics-methods/index.md`
- `docs/source-tracks/life/L2-exam-prep/yunnan-apply/index.md`
- `docs/source-tracks/life/L2-exam-prep/yunnan-policy/index.md`
- `docs/source-tracks/life/L4-hometown/家中对联.md`
- `docs/source-tracks/life/L1-learning-method/00-intro.md`
- `docs/source-tracks/life/L1-learning-method/01-how_to_learn_program.md`
- `docs/source-tracks/life/L1-learning-method/02-elevate_thinking.md`
- `docs/source-tracks/life/L1-learning-method/左耳朵耗子的话——关于技术的一些思考.md`
- `docs/source-tracks/life/L3-economy/area.md`
- `docs/source-tracks/life/L3-economy/economic-downturn-deep-dive/index.md`
- `docs/source-tracks/life/L3-economy/economic-downturn-strategy/index.md`
- `docs/source-tracks/life/L3-economy/media-account/index.md`
- `docs/source-tracks/life/L3-economy/self-host/index.md`
- `docs/source-tracks/life/L3-economy/A股股票筛选规则.md`

### 桶 4 转载内容（17 篇）

- `docs/source-tracks/ai-tools/L1-concepts/01_开场白目录.md`
- `docs/source-tracks/ai-tools/L1-concepts/02_AI到底聪明在哪从手机人脸识别说起.md`
- `docs/source-tracks/ai-tools/L1-concepts/03_AI怎么读懂文字国王减去男人等于什么.md`
- `docs/source-tracks/ai-tools/L1-concepts/04_AI是怎么突然变厉害的2012所有人以为他们作弊了.md`
- `docs/source-tracks/ai-tools/L1-concepts/05_神经网络到底是什么6000万个旋钮的真相.md`
- `docs/source-tracks/ai-tools/L1-concepts/06_AI是怎么学会的从做错一道题说起.md`
- `docs/source-tracks/ai-tools/L1-concepts/07_ChatGPT为什么能对话一篇引用17万次的论文.md`
- `docs/source-tracks/ai-tools/L1-concepts/08_AI为什么会撒谎一个律师被ChatGPT骗了.md`
- `docs/source-tracks/ai-tools/L1-concepts/09_ChatGPT回答你的三秒钟里发生了什么.md`
- `docs/source-tracks/ai-tools/L1-concepts/10_AI 到底有多聪明一份让 AI 研究者也困惑的成绩单.md`
- `docs/source-tracks/ai-tools/L1-concepts/11_AI 能创造吗从一团噪声到一幅画.md`
- `docs/source-tracks/ai-tools/L1-concepts/12_为什么 AI 能赢世界冠军却开不好车一条藏在所有 AI 背后的分界线.md`
- `docs/source-tracks/ai-tools/L1-concepts/13_这个框架会过时吗AI 的天花板和你的判断力.md`
- `docs/source-tracks/ai-tools/L1-concepts/14_怎么让AI听懂你的话同一个AI为什么他用得比你好10倍.md`
- `docs/source-tracks/ai-tools/L1-concepts/15_怎么跟AI协作不翻车AI说的话你该信几分.md`
- `docs/source-tracks/ai-tools/L1-concepts/16_AI 写代码有多厉害快了 55但错多了 75.md`
- `docs/source-tracks/ai-tools/L1-concepts/17_AI会取代我们吗它不懂孤独是什么意思.md`
