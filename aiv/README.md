# aiv — 品牌系列视频的生产线

把写好的技术文章，变成一条能持续产出、还能被复现的成片流水线。

技术图示一律由代码绘制（cairo + ffmpeg），不交给模型生成；
形象是 3D 静帧 + 位移/缩放/淡入，文字用真实字体在 cairo 阶段渲染。
**入库的是事实**（规范、契约、台账、代码），**产物不入库**（成片、片段、时间轴、发布包留本机）。
**出片必需的输入也入库**（旁白、曲库、形象素材、品牌片）——没有它们就出不了片，
不入库就等于每次换机器都要重新搬一遍。见[上机指南.md](上机指南.md)。

## 目录

| 目录 | 内容 |
| --- | --- |
| `pipeline/` | 出片流水线：`pyv/` 渲染引擎 + `tests/` + `Makefile` |
| `contracts/` | 视觉分镜契约：一期视频的段落划分与画面文案 |
| `publish/` | 发布元数据：每期各平台的标题、简介、话题与分区（`pyv publish check` 体检） |
| `review/` | 视频审校：文本层 `VT-*` 与成片层 `VV-*` 的规则、一期一条记录、抽帧清单 |
| `character/` | 3D 小象形象：生成、加眼镜、铭牌盖章（`scripts/`） |
| `brand/` | 品牌片头/片尾：渲染与配乐（`scripts/`） |
| `voice/` | 旁白音色与合成（`scripts/`） |
| `music/` | 背景音乐曲库：授权台账 + 曲库文件（授权 CC0-1.0，都入库） |

## 规范

| 文档 | 内容 |
| --- | --- |
| [人格规范.md](人格规范.md) | 小象是谁、怎么想、怎么讲；9 条可机检规则 |
| [形象与音色规范.md](形象与音色规范.md) | 角色设定、铭牌文字的确定性、旁白音色定稿 |
| [背景音乐规范.md](背景音乐规范.md) | 选曲白名单、风格标准、技术规格、混音与 ducking 规则 |
| [选题库.md](选题库.md) | 每期的题目、口播骨架、画面契约草案与数字出处（选题的唯一事实来源） |
| [上机指南.md](上机指南.md) | 换机器怎么装依赖、字体差异、常见故障 |
| [review/README.md](review/README.md) | 视频审校规范：两层规则、抽帧方法、一期一条记录 |

模块自己的说明在 [character/README.md](character/README.md)、
[brand/README.md](brand/README.md)、[voice/README.md](voice/README.md)、
[music/README.md](music/README.md)。

## 选题库

[选题库.md](选题库.md) 是**选题这件事的唯一事实来源**：每一期一条，
含题目、主钩子、关联文档、适配理由、口播骨架、画面契约草案与数字出处。
第一季的主线是「机制族」——同一个机制往下挖；EP06 起进入第二季「内核机制」
（行锁、MVCC 这些内核里的数据结构）。

它同样可机检（`pipeline/pyv/topics.py`，8 条规则）：

```bash
cd aiv/pipeline
make topics       # python -m pyv.cli topics check
```

守的是四件事：**结构完整**（必备字段与三段小节都在）、
**关联文档真实存在**（被删了就该红）、**口径不跑偏**（标题与钩子不命中
《人格规范》的禁词表，且整期落在能力域内）、**数字有出处**（实测类数字
必须带作者本人归因）。句数与字数按系列硬指标（10 句、230~280 字）卡住。

选题库里的口播骨架是**草案**，出片前要按实际旁白重新定标语速。

### 进度

| 期 | 主题 | 状态 | 成片规格 |
| --- | --- | --- | --- |
| EP01 | openGauss 的并行逻辑解码 | 已出片 | 正文 32.436 秒 |
| EP02 | 一个 64 位计数器，决定所有事务的提交顺序 | 已出片 | 正文 35.316 秒 |
| EP03 | WAL 里的顺序，不等于事务的顺序 | 已出片 | 正文 34.596 秒 |
| EP04 | 并行接收之后，谁先应用 | 已出片 | 正文 35.424 秒 |
| EP05 | 为什么 DDL 同步不能直接把 SQL 文本发过去 | 已出片 | 正文 34.128 秒 |
| EP06 | 两个事务改同一行，谁先谁后（第二季入口） | 已出片 | 正文 35.208 秒 |

六期的成片都是 1920×1080 / 24fps / H.264 yuv420p / AAC 48kHz 立体声，
外加 2.833 秒品牌片头与片尾（EP01 共 38.125 秒，EP02 共 41.000 秒，
EP03 共 40.262 秒，EP04 共 41.090 秒，EP05 共 39.833 秒，EP06 共 40.875 秒）。
成片是产物、不入库，上面的时长是实测值，记在 [index.md](index.md) 与本表里。

## 本期内容进契约，版式常量留代码

一条视频的**画面文案与数字**（标题、副标题、标签、核数、顺序号、性能倍数……）
全部写在 `contracts/*.json` 的视觉分镜契约里，不写在场景代码里。

| | 放哪 | 谁定 |
| --- | --- | --- |
| 文案、数字、标签、枚举 | `contracts/<期>.json` | 每一期 |
| 位置、尺寸、配色、动效 | `pipeline/pyv/scenes/*.py` | 模板 |

这么分是为了让「换一期」不再等于「改一遍代码」：新一期只写契约，
场景渲染器一行都不用动。两条硬规矩：

- **参数缺失当场报错**。契约少给一个参数，渲染前就抛 `MissingParam`，
  绝不悄悄退回硬编码的旧文案——那会让契约与画面的不一致变得无声无息。
- **文案不许回流到代码**。`pipeline/tests/test_contract.py` 会解析场景源码，
  只要契约里的文案还以字符串字面量的形式出现在场景里，测试就红。

契约里还规定「哪几句旁白配哪张图」，句子必须**恰好被覆盖一次**：
漏了、重了都会在 `align` 之前就报错。

## 跑一遍

```bash
cd aiv/pipeline
python3 scripts/install_font.py   # 装内置字体（两台机器用同一份，跨机版式一致）
make doctor      # 环境自检：这台机器缺什么、怎么补（换机器先跑这个）
make test        # 全量测试
make persona     # 按《人格规范》检查口播稿
make topics      # 按《选题库》的规则检查选题
make bgm         # 按《背景音乐规范》检查曲库台账
make mix-verify  # 成片级混音验收（规范 §5.7）
make pronunciation  # 多音字读音验收（要联网合成探针）
make probe       # ffprobe 看成片的时长、编码与像素格式
```

出片链路（`align → validate → brand → render → compose`）需要旁白音频
（`narration_<期号>.mp3`，**已入库**）与视觉分镜契约（`contracts/<期号>.json`，
已入库）——契约决定**画面上写什么**，旁白决定**什么时候出现**。
时间轴 `storyboard_<期号>.json` 由 `align` 从旁白算出来，是产物，不入库。

### 出片之后：验收、体检与审校

出片不是终点。成片要过两道体检，再进审校：

| 环节 | 命令 | 查什么 |
| --- | --- | --- |
| 成片验收 | `make EP=<期号> mix-verify` | 稳态 duck 深度、旁白/BGM 电平差、真峰值（规范 §5.7） |
| 发布体检 | `python3 -m pyv.cli publish check --episode <期号>` | 发布元数据 + 成片技术门槛（每个平台各判一遍） |
| 文本层审校 | `make review-text EP=<期号>` | `VT-*`：口播腔调、数字出处、口播与字幕是否一致 |
| 成片层审校 | `make review-video EP=<期号>` | `VV-*`：漏画、字幕没烧上、旁白静音、时长与时间轴对不上 |
| 抽帧看画面 | `make review-frames EP=<期号>` | 每段两帧 + 关键帧，出一份「这一帧该有什么文案」的对照清单 |

审校的两层、阈值与边界见 [review/README.md](review/README.md)。

### 抖音那一档：无品牌导流版与竖版

抖音禁「过度营销信息」与站外引流，所以另出两档：

```bash
make EP=<期号> nobrand            # 去品牌片头/片尾
make EP=<期号> nobrand NOBADGE=1  # 再去掉胸口铭牌（铭牌也是品牌标识）
make EP=<期号> vertical           # 9:16 竖版
```

三件事要记住：

- **片段目录与成片都另起一份**（`build/<期号>__nobrand/`、`out/<期号>__nobrand.mp4`），
  不跟带品牌的版本共用——共用会让增量渲染把带品牌片的片段当成可复用的。
- **竖版本来就不套品牌片**：品牌片素材是横版的，贴到竖版画布上会被拉变形，
  `pyv.cli brand` 会直接拒绝。
- **铭牌默认保留**：铭牌占比极小，先按保留投一条看审核结果再定。

### 换一台机器

macOS 与 Linux 都能跑。一台干净的 Linux 机器上：

```bash
sudo bash aiv/pipeline/scripts/bootstrap_linux.sh   # 装依赖
cd aiv/pipeline && make doctor                       # 自检
```

唯一的差异是**字体**：macOS 用 `PingFang SC`，Linux 用开源的 `Noto Sans CJK SC`
（PingFang 是 Apple 授权字体，不能随仓库分发），所以同一段文字的**像素不同**，
文案与版式规则一致。详见[上机指南.md](上机指南.md)。

### 版式在两台机器上长得一样

「像素不同」这件事后来收窄了。做法是让两台机器用**同一个字体文件**，
再把字体之外的变量按住：

| 做法 | 在哪 | 为什么 |
| --- | --- | --- |
| 内置字体子集入库 | `pipeline/assets/fonts/` | 两台机器装同一份 `AIV Sans CJK SC`（Regular + Bold），不是各装各的系统字体 |
| 关掉 hinting | `pyv/fingerprint.py` 的前置条件 | Linux 的 FreeType 默认开 autohinter，轮廓点吸附像素网格——实测一行字的步进能差 **68px**，字号跟着差 3.2px |
| 粗体用真 Bold 字形 | `assets/fonts/AIVSansCJKSC-Bold.otf` | 只装常规字重时 cairo 会**合成**粗体，CoreText 合成一套、FreeType 合成另一套，轮廓包围盒差 3.14px |
| 布局指纹守卫 | `pyv/fingerprint.py` + `tests/test_layout_fingerprint.py` | 记落笔坐标、字号、步进宽度、轮廓包围盒——这四类是**字体的性质**，跨机可比 |
| 逐像素基准 | `scripts/capture_scene_baseline.py` + `tests/test_contract.py` | 覆盖全部 36 个视觉段（6 期 × 6 段），守的是「文案搬进契约不该动到画面」 |

**逐像素基准跨机不可比**：cairo 在 macOS 走 CoreText、在 Linux 走 FreeType，
栅格化不同，像素必然不同。所以跨机靠**指纹**（实测最大差：坐标 0.000、字号 0.027、
步进 0.812、包围盒 0.711），逐像素基准只在同平台内比；Linux CI 上那条守卫会
**跳过并说明原因**，不是红，也不是假装绿。

## 换一期

流水线按期号（`EP`）切：

```bash
cd aiv/pipeline
make EP=csn-total-ordering align      # 按这一期的旁白对齐出时间轴
make EP=csn-total-ordering all         # validate → brand → render → compose
```

`EP` 决定这一期的契约、旁白、时间轴、片段目录与成片的文件名；
**口播稿按主题命名**（`字幕-并行解码.md`、`字幕-CSN全序.md`），
在 Makefile 里按 `EP` 显式登记——换期时忘了换稿会当场报错，
而不是静悄悄地拿上一期的稿子出片。

片段目录也按期分开（`build/<期号>/`）：各期的段 id 会重名（`s01`…），
共用一个目录会互相覆盖。

| 入库 | 不入库（留本机） |
| --- | --- |
| `contracts/<期号>.json` 视觉分镜契约 | `storyboard_<期号>.json` 时间轴 |
| `字幕-<主题>.md` 口播稿与字幕表 | `build/<期号>/*.mp4` 片段 |
| `pipeline/pyv/scenes/*.py` 场景代码 | `out/<期号>.mp4` 成片 |
| `narration_<期号>.mp3` 旁白（**出片必需**） | 发布包 |
| `music/tracks/*.wav` 曲库（**出片必需**） | `review/frames/<期号>/*.png` 抽出来的帧 |
| `character/growdu_character_2k_nobg.png` 立绘（**出片必需**） | |
| `brand/clips/*.mp4`、`brand/audio/*_mix.wav` 品牌片与音轨 | |
| `pipeline/assets/fonts/*.otf` 内置字体子集（**跨机版式一致要用**） | |
| `publish/<期号>.json` 发布元数据 | |
| `review/frames/<期号>/frames.md` 抽帧清单 | |

抽帧的**帧不入库、清单入库**：帧是产物，跟着本机的成片走；清单是
「这一期抽了哪些帧、每帧该有什么文案」的对照表——审核记录里的判断要能对着它复核。
（`.gitignore` 里这一条的放行顺序要紧：先放行目录，再拦内容，最后放行清单。）

## 审校（review）

`review/` 存放对这条线的**审校任务与记录**，一期一条，规范在
[review/README.md](review/README.md)。目标不是把片子做得更华丽，
而是让它像一位有经验的工程师在清楚地讲一件事：具体、自然、有判断。

两层分开：

| 层 | 编号 | 审什么 |
| --- | --- | --- |
| 文本层 | `VT-01`~`VT-07` | 要讲什么：口播腔调、泛化收尾、近似重复句、数字出处、口播与字幕是否一致、字幕表格式 |
| 成片层 | `VV-01`~`VV-07` | 做出来是什么样：漏画、字幕没烧上、旁白静音、时长对不上、关键帧间隔、混音电平、平台技术门槛 |

```bash
cd aiv/pipeline
make review-text   EP=<期号>   # 文本层
make review-video  EP=<期号>   # 成片层（需要本机有 out/<期号>.mp4）
make review-frames EP=<期号>   # 抽帧 + 清单（帧不入库，清单入库）
```

三条规矩：

- **信号不是门禁**：命中信号不会让命令失败——一期历史问题不该永久卡住流水线。
- **信号为 0 不等于这期没问题**：机械信号干净的一期照样可能需要改；
  信号是「值得看一眼的地方」，不是「问题清单」。
- **改稿会改到画面**：口播改了，契约的句子覆盖关系可能变，`align` 要重算时间轴、
  片段要重渲。只审文本不审成片，等于审了一份没出片的稿子。

一期一条记录在 `review/episodes/<期号>.md`，进度在 `review/INDEX.md`（只维护一份）。
`review/` 只记录审核过程与结论，**不是对外发布内容**，不进 `docs/`，
也不进发布白名单（与文档侧的根 `review/` 同一条纪律）。

## 发布到博客的那一份

`aiv/` 在仓库根，不在 `docs/` 下面，而 `sync-hexo.py` 只扫 `docs/`——
所以上面那些**文档**在 `docs/source-tracks/blogging/L4-video-pipeline/aiv/` 另存一份，博客上发的就是那一份。

改完 `aiv/` 里的文档后跑：

```bash
python3 aiv/scripts/sync_publish_docs.py
```

`pipeline/tests/test_publish_copy.py` 盯着两份是否一致：漂了会红，
线上内容不会悄悄落后于仓库里的规范。

发布目录里**只有**这些文档。`pipeline/` 下的内部设计、实施计划与测试夹具
留在仓库里，不进博客——测试夹具尤其不能发，其中一份是故意写坏的样本。

### 站内相对链接是怎么变成绝对路径的

博客里大量用 `../xxx/index.html` 这种写法，但站点的真实 URL 带日期
（`/2026/11/11/life/gaokao/yunnan-policy/`）。**Hexo 在构建时会重写**：
目标页存在时，相对链接被改成带日期的绝对路径。

**目标页不存在时，链接就原样留下**，于是 404。实测：
`../aiv/背景音乐规范.md` 被正确重写成了 `/blog/2026/11/11/life/aiv/背景音乐规范/`，
而 `../aiv/index.html` 因为专题页不存在，保持字面量、点了就是 404。

所以补一个缺失的页面时**不用去改引用它的那些链接**——把页面写出来，
链接会自己恢复。反过来，看到「相对链接 404」要先查目标页在不在，
而不是去改链接文本。

### AIV 专题页

专题页「AIV 视频生产线：九个环节、唯一契约与入库边界」
（正本 `index.md`，发布副本 `docs/source-tracks/blogging/L4-video-pipeline/aiv/index.md`）讲的是这条线本身：
九个环节、唯一契约、入库边界，以及「片尾接回片头」的配乐闭环。

它在目录迁移提交 `0b9cb9a` 里被删过，仓库里有 **8 处链接**指向它、当时全 404。
旧页在 git 历史里（`0b9cb9a^:docs/life/aiv/index.md`，213 行），但**不能直接恢复**：
里面写的是「成片线归雇主、我们支持了 X」的公司口径，与现在的第三方开发者口径冲突；
还引用已作废的 `pa_decode_v2.mp3`、把 `storyboard.json` 说成唯一契约
（现在契约是 `contracts/*.json`，storyboard 是产物）。所以按现状重写了。

重写后链接自己就恢复了——引用它的页面一个字都没改：

| 位置 | 处数 |
| --- | --- |
| `docs/source-tracks/life/_index.md` | 2 |
| `docs/source-tracks/blogging/L3-distribution/blog-to-wechat/index.md` | 3 |
| `docs/source-tracks/life/L3-economy/media-account/index.md` | 2 |
| `docs/source-tracks/postgresql/_index.md` | 1（路径另错了一层，一并改成 `../../life/aiv/index.html`） |

落地方式：正本 `index.md` + 发布副本 `docs/source-tracks/blogging/L4-video-pipeline/aiv/index.md`，
并把 `index.md` 加进 `aiv/scripts/sync_publish_docs.py` 的 `PUBLISH_DOCS`，
这样副本漂移继续被 `test_publish_copy.py` 抓住。

### 一个容易踩的坑：正文里的方括号

`sync-hexo.py` 重写站内相对链接用的是一条「左方括号 + 文字 + 右方括号 +
左圆括号 + 地址 + 右圆括号」的匹配，它**不认代码块**。
正文里任何不成对的左方括号（比如区间写法里的半开区间记号）
都会让它一路吃到后面某个链接的右圆括号，把中间整段包成一个链接——
markdown 源码看着没变，渲染出来却是上千字的巨型蓝色链接。

所以发布文档里**不要用 ASCII 方括号**写区间。`tests/test_publish_copy.py`
有一条测试盯住发布目录里的跨段误匹配，踩到了会红。
