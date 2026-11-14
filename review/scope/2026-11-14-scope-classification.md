# 全树范围分类：哪些不是面向读者的技术文章

- 日期：2026-11-14
- 依据：`tools/review-check.py` 对 `docs/` 全树（621 篇）跑出的信号，加逐篇读原文的判断
- 目的：把审校范围从「四支柱 282 篇」扩到全树之前，先把**不面向读者的技术文章**筛掉，
  免得把站点目录页、内部工作文档、命令速查表也按技术深度五要素去审。

## 四个桶

| 桶 | 含义 | 篇数 | 技术深度五要素 |
| --- | --- | --- | --- |
| 1 非内容 | 根本不面向读者：站点目录页、代码仓库说明、内部工作文档、外链指北、只有标题的未成稿 | 99 | 不审 |
| 2 速查/清单/操作类 | 面向读者，但形态是命令表、步骤、清单，没有成篇解释 | 49 | 不适用 |
| 3 非技术内容 | 面向读者，但写的是生活、备考、内部规范 | 47 | 不适用 |
| 4 技术文章 | 面向读者的技术解释 | 426 | **审** |

**审校工作面 = 426 篇**（桶 4）。桶 2、3 面向读者但不是技术文章，
可选做表达与结构审，不套五要素；桶 1 不审。

## 判据

机械层（可复跑）：

- 目录页：文件名为 `_index.md`
- 代码仓库说明：路径在 `docs/code/` 下
- 只有标题的未成稿：散文字符数为 0、无表格、无代码块、总字符 < 150
  （散文字符数 = 排开标题、代码块、表格、列表后的正文长度，引用块计入）

人工层（逐篇读过原文，一次判断写死）：

- 内部工作文档：开发交付计划、验证步骤、测试进度表、内部规范、个人数据记录
- 外链指北：正文只有 `# reference` 链接列表
- 速查/清单/操作类：有内容但形态是命令表、步骤、清单，没有机制解释
- 非技术内容：`docs/life/`、`docs/stock/`、`docs/ai/` 科普系列、`docs/chatgpt/`

复跑方式：

```bash
python3 tools/review-check.py docs --json --out /tmp/all_docs.json
```

## 逐支柱分布

| 支柱 | 总数 | 非内容 | 速查操作 | 非技术 | 技术文章 | warn | DEP-00 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| db | 102 | 11 | 2 | 0 | 89 | 44 | 11 |
| database | 61 | 1 | 0 | 0 | 60 | 28 | 0 |
| cluster | 64 | 8 | 0 | 0 | 56 | 62 | 31 |
| pgsql | 55 | 5 | 6 | 0 | 44 | 42 | 20 |
| linux | 39 | 5 | 7 | 0 | 27 | 21 | 16 |
| dpdk | 27 | 3 | 7 | 0 | 17 | 15 | 9 |
| ai | 30 | 1 | 0 | 13 | 16 | 36 | 4 |
| tools | 21 | 1 | 4 | 0 | 16 | 17 | 9 |
| vpp | 19 | 1 | 2 | 0 | 16 | 13 | 9 |
| protocol | 12 | 2 | 0 | 0 | 10 | 9 | 7 |
| docker | 12 | 1 | 2 | 0 | 9 | 5 | 2 |
| language | 17 | 3 | 5 | 0 | 9 | 11 | 11 |
| vue | 14 | 1 | 4 | 0 | 9 | 9 | 4 |
| blog | 10 | 2 | 0 | 0 | 8 | 3 | 2 |
| page | 13 | 3 | 2 | 0 | 8 | 13 | 11 |
| base | 14 | 3 | 4 | 0 | 7 | 16 | 10 |
| network | 10 | 3 | 0 | 0 | 7 | 13 | 5 |
| es | 5 | 1 | 0 | 0 | 4 | 6 | 1 |
| storage | 6 | 2 | 0 | 0 | 4 | 4 | 2 |
| edit | 5 | 1 | 1 | 0 | 3 | 5 | 4 |
| openguass | 5 | 1 | 1 | 0 | 3 | 3 | 3 |
| alg | 2 | 1 | 0 | 0 | 1 | 3 | 1 |
| computer_communication | 2 | 1 | 0 | 0 | 1 | 2 | 2 |
| programmer_self_cultivation | 2 | 1 | 0 | 0 | 1 | 1 | 1 |
| web | 2 | 1 | 0 | 0 | 1 | 2 | 2 |
| chatgpt | 3 | 1 | 0 | 2 | 0 | 3 | 3 |
| code | 12 | 12 | 0 | 0 | 0 | 12 | 12 |
| environment | 1 | 1 | 0 | 0 | 0 | 1 | 1 |
| faq | 2 | 1 | 1 | 0 | 0 | 2 | 2 |
| go_web | 2 | 1 | 1 | 0 | 0 | 2 | 2 |
| life | 42 | 11 | 0 | 31 | 0 | 22 | 6 |
| mail | 1 | 1 | 0 | 0 | 0 | 1 | 1 |
| opc | 2 | 2 | 0 | 0 | 0 | 1 | 1 |
| pcap | 1 | 1 | 0 | 0 | 0 | 1 | 1 |
| src | 1 | 1 | 0 | 0 | 0 | 1 | 1 |
| stock | 2 | 1 | 0 | 1 | 0 | 2 | 1 |
| video_work | 2 | 2 | 0 | 0 | 0 | 2 | 2 |
| wiki | 1 | 1 | 0 | 0 | 0 | 1 | 1 |
| **合计** | **621** | **99** | **49** | **47** | **426** | **434** | **211** |

## 排除清单

下面三桶逐篇列出。**桶 4 = `docs/` 全集减去这份清单**，不单独列。
契约测试守着两件事：清单里的路径不许悬空；审校记录的原文不许落在清单里。

### 桶 1 非内容（99 篇）

#### 站点目录页（52 篇）

- `docs/ai/_index.md`
- `docs/alg/_index.md`
- `docs/base/_index.md`
- `docs/blog/_index.md`
- `docs/blog/mermaid/_index.md`
- `docs/chatgpt/_index.md`
- `docs/cluster/_index.md`
- `docs/code/_index.md`
- `docs/computer_communication/_index.md`
- `docs/database/_index.md`
- `docs/db/_index.md`
- `docs/db/benchmarksql/_index.md`
- `docs/db/linux-shared-memory/_index.md`
- `docs/db/logical_decode/_index.md`
- `docs/db/opengauss-csn-total-ordering/_index.md`
- `docs/db/opengauss-parallel-decoding-design/_index.md`
- `docs/db/postgresql/_index.md`
- `docs/db/postgresql/learning-path/_index.md`
- `docs/docker/_index.md`
- `docs/dpdk/_index.md`
- `docs/edit/_index.md`
- `docs/environment/_index.md`
- `docs/es/_index.md`
- `docs/faq/_index.md`
- `docs/go_web/_index.md`
- `docs/language/_index.md`
- `docs/life/_index.md`
- `docs/life/blog-to-wechat/_index.md`
- `docs/life/daxue/_index.md`
- `docs/life/gaokao/_index.md`
- `docs/life/hometown/_index.md`
- `docs/life/road/_index.md`
- `docs/life/shehui/_index.md`
- `docs/linux/_index.md`
- `docs/mail/_index.md`
- `docs/network/_index.md`
- `docs/opc/_index.md`
- `docs/openguass/_index.md`
- `docs/page/_index.md`
- `docs/pcap/_index.md`
- `docs/pgsql/_index.md`
- `docs/programmer_self_cultivation/_index.md`
- `docs/protocol/_index.md`
- `docs/src/_index.md`
- `docs/stock/_index.md`
- `docs/storage/_index.md`
- `docs/tools/_index.md`
- `docs/video_work/_index.md`
- `docs/vpp/_index.md`
- `docs/vue/_index.md`
- `docs/web/_index.md`
- `docs/wiki/_index.md`

#### 只有标题的未成稿（24 篇）

- `docs/base/use-tools/download.md`
- `docs/cluster/Patroni详解.md`
- `docs/cluster/corosync/corosy-qdevice源码阅读.md`
- `docs/cluster/ha/业界高可用解决方案.md`
- `docs/cluster/repmgr网络割裂问题.md`
- `docs/cluster/主流分布式高可用方案.md`
- `docs/cluster/分布式存储需要解决的问题.md`
- `docs/cluster/分布式系统设计必知必会.md`
- `docs/db/logical_decode/ai_coding/逻辑复制支持ddl ai配置流程.md`
- `docs/dpdk/vpp插件开发.md`
- `docs/language/python/pytest/pytest进阶.md`
- `docs/language/rust/rust设计原则.md`
- `docs/linux/linux数据预取.md`
- `docs/linux/shell使用.md`
- `docs/network/C语言网络编程库选择.md`
- `docs/network/mtu路径发现pmtu详解.md`
- `docs/page/gui.md`
- `docs/page/read-pdfbox-source-code.md`
- `docs/pgsql/process/Checkpoint.md`
- `docs/pgsql/replication/pg_logic_decode.md`
- `docs/pgsql/replication/pg_slot.md`
- `docs/pgsql/storage/mm/pg_page.md`
- `docs/protocol/tcp/tcp socket必知必会.md`
- `docs/storage/sshfs-win精讲.md`

#### 代码仓库说明（11 篇）

- `docs/code/JavaScript-work/readme.md`
- `docs/code/assemble-work/readme.md`
- `docs/code/c-sharp-work/readme.md`
- `docs/code/c-work/readme.md`
- `docs/code/c-work/simple-editor/preview.md`
- `docs/code/c-work/ticket/readme.md`
- `docs/code/gui-work/readme.md`
- `docs/code/html-work/readme.md`
- `docs/code/java-work/readme.md`
- `docs/code/shell-work/readme.md`
- `docs/code/shell-work/vim/readme.md`

#### 内部工作文档与记录（10 篇）

- `docs/base/normal.md`
- `docs/db/logical_decode/逻辑复制支持DDL开发交付计划.md`
- `docs/db/logical_decode/逻辑复制验证步骤.md`
- `docs/dpdk/fastup测试优化完成情况.md`
- `docs/life/aiv/人格规范.md`
- `docs/life/aiv/形象与音色规范.md`
- `docs/life/aiv/背景音乐规范.md`
- `docs/life/shehui/zhuangxiu.md`
- `docs/opc/opc.md`
- `docs/video_work/video.md`

#### 只有外链的指北页（2 篇）

- `docs/linux/linux内核指北.md`
- `docs/linux/uboot指北.md`

### 桶 2 速查/清单/操作类（49 篇）

- `docs/base/use-tools/git.md`
- `docs/base/use-tools/google.md`
- `docs/base/use-tools/other.md`
- `docs/base/use-tools/vim.md`
- `docs/db/mysql/macos安装mysql.md`
- `docs/db/postgresql/使用meson编译pg.md`
- `docs/docker/docker compose管理容器.md`
- `docs/docker/docker搭建个人镜像仓库.md`
- `docs/dpdk/fastup模拟UE测试.md`
- `docs/dpdk/pktgen.md`
- `docs/dpdk/pktgen编译使用.md`
- `docs/dpdk/ptpclient.md`
- `docs/dpdk/vpp使用.md`
- `docs/dpdk/交叉编译.md`
- `docs/dpdk/抓包.md`
- `docs/edit/texlive安装.md`
- `docs/faq/faq汇总.md`
- `docs/go_web/go_web.md`
- `docs/language/cmake使用指南.md`
- `docs/language/python/pytest自动化测试.md`
- `docs/language/python/python跨平台下载离线安装包.md`
- `docs/language/rust/使用mdbook编译html和pdf.md`
- `docs/language/rust/搭建内网rust仓库.md`
- `docs/linux/ebpf/oltp.md`
- `docs/linux/git指北.md`
- `docs/linux/git高级指北.md`
- `docs/linux/linux常用高级命令.md`
- `docs/linux/抓包指北.md`
- `docs/linux/本地git仓库.md`
- `docs/linux/解决SSH连接Linux超时自动断开.md`
- `docs/openguass/openguass升级机制.md`
- `docs/page/python.md`
- `docs/page/ssh.md`
- `docs/pgsql/debug/code-server调试postgresql.md`
- `docs/pgsql/pg_command/initdb.md`
- `docs/pgsql/pg_command/pg_ctl.md`
- `docs/pgsql/pg_complie_and_run.md`
- `docs/pgsql/postgresql源码编译.md`
- `docs/pgsql/repmgr/repmgr_cluster.md`
- `docs/tools/codeserver_docker.md`
- `docs/tools/doxygen使用指南.md`
- `docs/tools/shell常用脚本.md`
- `docs/tools/你一定要知道的黑客小技巧.md`
- `docs/vpp/fastgtpu配置及cli说明文档.md`
- `docs/vpp/vpp调试指北.md`
- `docs/vue/cargo构建.md`
- `docs/vue/python环境搭建.md`
- `docs/vue/react app教程.md`
- `docs/vue/vue开发环境搭建.md`

### 桶 3 非技术内容（47 篇）

- `docs/ai/01-ai常用工具和开发框架.md`
- `docs/ai/01_开场白目录.md`
- `docs/ai/02_AI到底聪明在哪从手机人脸识别说起.md`
- `docs/ai/03_AI怎么读懂文字国王减去男人等于什么.md`
- `docs/ai/04_AI是怎么突然变厉害的2012所有人以为他们作弊了.md`
- `docs/ai/05_神经网络到底是什么6000万个旋钮的真相.md`
- `docs/ai/06_AI是怎么学会的从做错一道题说起.md`
- `docs/ai/07_ChatGPT为什么能对话一篇引用17万次的论文.md`
- `docs/ai/08_AI为什么会撒谎一个律师被ChatGPT骗了.md`
- `docs/ai/09_ChatGPT回答你的三秒钟里发生了什么.md`
- `docs/ai/19_AI是你的杠杆普通人也能用的AI实战教程.md`
- `docs/ai/claude/claude配置.md`
- `docs/ai/claude安装教程/index.md`
- `docs/chatgpt/chatgpt使用.md`
- `docs/chatgpt/newbing使用教程/index.md`
- `docs/life/aiv/brand/README.md`
- `docs/life/aiv/brand/scripts/README.md`
- `docs/life/aiv/character/README.md`
- `docs/life/aiv/index.md`
- `docs/life/aiv/music/README.md`
- `docs/life/aiv/voice/README.md`
- `docs/life/blog-to-wechat/index.md`
- `docs/life/daxue/电子科技大学-计算机-自考-复习计划/index.md`
- `docs/life/daxue/腾冲事业编-公务员备考计划/index.md`
- `docs/life/doctor_test/寻康杯备战方案.md`
- `docs/life/doctor_test/寻康杯实战操作手册.md`
- `docs/life/gaokao/biology-methods/index.md`
- `docs/life/gaokao/chemistry-methods/index.md`
- `docs/life/gaokao/english-roots/index.md`
- `docs/life/gaokao/geography-methods/index.md`
- `docs/life/gaokao/math-methods/index.md`
- `docs/life/gaokao/math-paper2/index.md`
- `docs/life/gaokao/physics-methods/index.md`
- `docs/life/gaokao/politics-methods/index.md`
- `docs/life/gaokao/yunnan-apply/index.md`
- `docs/life/gaokao/yunnan-policy/index.md`
- `docs/life/hometown/家中对联.md`
- `docs/life/road/00-intro.md`
- `docs/life/road/01-how_to_learn_program.md`
- `docs/life/road/02-elevate_thinking.md`
- `docs/life/road/左耳朵耗子的话——关于技术的一些思考.md`
- `docs/life/shehui/area.md`
- `docs/life/shehui/economic-downturn-deep-dive/index.md`
- `docs/life/shehui/economic-downturn-strategy/index.md`
- `docs/life/shehui/media-account/index.md`
- `docs/life/shehui/self-host/index.md`
- `docs/stock/A股股票筛选规则.md`
