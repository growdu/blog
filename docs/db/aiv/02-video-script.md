# 短视频分镜脚本（30 秒 · Minimax Hub 版）

> 总时长 ≤ 30 秒，口播约 27 秒（落版 3 秒）。
> 比例：竖版 9:16（抖音 / 视频号 / 小红书）/ 横版 16:9（B 站 / 公众号）。
> 生成工具：**Minimax Hub**（minimax，单镜头 4–6 秒生成 + 字幕叠加）。
> 风格：深色科技底 + 青 / 橙 accent，字体与海报一致。
> 主钩子：**海量数据库内核原生支持 DDL 同步，DDL 沿用 DML 同步机制。**

---

## 主讲人形象（Minimax Hub 定妆照 prompt）

> **角色**：海量数据库大象（Mass Elephant），品牌吉祥物兼本次视频主讲人。
> **形象**：圆润卡通大象，皮肤青蓝色（与海报主色 #4FD1C5 同色系），戴黑色半框眼镜，穿深蓝色 polo 衫胸口印有「海量」二字。眼神亲切、表情自信、姿态稳定。
> **站位**：画面中央或偏一侧，不遮挡主文案。
> **动作库**：指向屏幕元素、点头、挥手、转身、缓推时身体比例不变形。
> **Minimax prompt（英文版）**：
> `A friendly cartoon elephant mascot, cyan-blue skin, black half-frame glasses, navy polo shirt with "Mass" logo on chest, standing confidently in front of a dark tech background, soft rim light, 3D Pixar style, clean silhouette, no extra props.`
> **Minimax prompt（中文版）**：
> `一只圆润可爱的卡通大象，皮肤青蓝色，戴黑色半框眼镜，穿深蓝色 polo 衫胸口印"海量"二字，深色科技背景前自信站立，柔光轮廓光，皮克斯 3D 风格，干净剪影。`

---

## 总体结构（30s）

| 时间 | 段落 | 大象位置 | 文字图层 | 镜头 |
| --- | --- | --- | --- | --- |
| 0–5s | 钩子 | 居中站立 | 双行主钩子 | 缓推 zoom in |
| 5–9s | 痛点 | 右侧站立 | 对比分屏：左发布端 / 右订阅端 + 红叉 | 切到分屏左移 |
| 9–15s | 现状 | 居中偏左 → 指向右 | 模糊数据库图标群 + 红叉「DDL 同步」 | 跟随手指 pan right |
| 15–21s | 能力 | 居中 | 大字「DDL 沿 DML 自动同步」+ 副字 | 稳定 |
| 21–27s | 价值 | 居中偏右 | 三场景图标依次亮起 | 稳定 |
| 27–30s | 落版 | 居中 | 主钩子 | 静止 |

---

## 分镜详表

### 0–5s · 钩子

- **画面**：黑屏 → 大象卡通从画面中心淡入 → 身后浮现双行大字「**海量数据库内核原生支持 DDL 同步**」+「**DDL 沿用 DML 同步机制**」，逐行高亮。
- **口播**：「海量数据库内核原生支持 DDL 同步，沿用 DML 同步机制。」
- **镜头**：缓推（zoom in），大象比例不变。
- **字幕**：主钩子双行，第二行青色 #4FD1C5。
- **Minimax prompt**：
  `Cartoon cyan-blue elephant mascot in navy polo with "Mass" logo stands center frame, two lines of bold Chinese text appear behind it line by line, dark tech background, slow zoom in, 3D Pixar style.`

### 5–9s · 痛点

- **画面**：大象站在画面右侧，左手抬起指向左侧 → 左侧出现对比分屏：左半发布端表结构（带绿色 ✓），右半订阅端表结构（灰色 + 红色 ✗「同步缺失」）。
- **口播**：「DDL 已提交，订阅端表结构还是老的。」
- **镜头**：大象稳定，镜头跟随手指方向轻微左移。
- **字幕**：上方红字「DDL 同步缺失」，下方分屏标签「发布端」/「订阅端」。
- **Minimax prompt**：
  `Cartoon cyan-blue elephant mascot standing on right side, points left toward a split-screen comparison: left panel shows a green checkmark on a table schema, right panel shows a red X over a faded table schema, dark background, 3D Pixar style.`

### 9–15s · 现状

- **画面**：大象居中偏左 → 身后右侧浮现多个模糊灰色数据库图标（轮廓相似、不显示具体厂商名）→ 图标逐一被红色 ✗ 划掉 → 大字「**DDL 同步 ❌**」+ 副字「**DDL 同步只能借助第三方工具或手动**」。
- **口播**：「大多数关系型数据库的逻辑复制只同步 DML,DDL 还得手动。」
- **镜头**：大象稳定，背景图标逐个淡出，镜头轻微 pan right。
- **字幕**：大字红色高亮「DDL 同步 ❌」，副字橙色。
- **Minimax prompt**：
  `Cartoon cyan-blue elephant mascot standing center-left, behind it on the right side multiple blurred gray database cylinder icons appear in a row, each gets crossed out by a red X one by one, big red text "DDL Sync ❌", orange subtitle below, dark tech background, 3D Pixar style.`

### 15–21s · 能力

- **画面**：大象居中站立 → 身后从左到右贯穿一条青色发光数据流线 → 流线穿过时高亮「DML 复制通道」 → 大字「**海量数据库 DDL 沿 DML 自动同步**」+ 副字①「**事务一提交就在订阅端同步执行 · 自动捕获 · 自动同步 · 自动回放**」+ 副字②「**沿用现有复制接口 · 同步语义一致 · 不用额外改造**」。
- **口播**：「海量数据库 DDL 沿 DML 自动同步，事务一提交就在订阅端同步执行。」
- **镜头**：稳定居中，流线自左向右滑动。
- **字幕**：大字青色，副字青色小字。
- **Minimax prompt**：
  `Cartoon cyan-blue elephant mascot standing center frame, a glowing cyan data stream flows from left to right behind it, the stream highlights a channel labeled "DML", large cyan text "DDL auto-sync along DML", two lines of smaller cyan subtitle text below, dark tech background, 3D Pixar style.`

### 21–27s · 价值

- **画面**：大象居中偏右站立 → 画面左侧依次亮起三个场景图标：盾牌（金融）/ 徽章（政务）/ 信号塔（电信）→ 大字「**强监管场景都适用**」+ 副字「**业务不中断 · 跨库容灾 · 实时同步**」。
- **口播**：「海量数据库满足金融、政务、电信强监管要求，业务不中断。」
- **镜头**：稳定居中，图标依次淡入。
- **字幕**：大字青色，副字青色小字。
- **Minimax prompt**：
  `Cartoon cyan-blue elephant mascot standing center-right, on the left side three icons light up in sequence: a shield, a government badge, and a telecom tower, large cyan text "All regulated industries", smaller cyan subtitle "zero downtime · cross-DB DR · real-time sync", dark tech background, 3D Pixar style.`

### 27–30s · 落版

- **画面**：黑屏 → 大象卡通居中 + 海量数据库 Logo + 主钩子双行大字。
- **口播**：（静帧，无口播）
- **镜头**：缓推 → 静止 3 秒。
- **字幕**：主钩子双行，第二行青色。
- **Minimax prompt**：
  `Cartoon cyan-blue elephant mascot standing center frame with "Mass" database logo above, two lines of bold Chinese tagline text appear behind, dark background, gentle zoom then hold, 3D Pixar style.`

---

## 口播稿（完整版，100 字中文 + 7 英文词 ≈ 27 秒口播 + 3 秒落版）

> 海量数据库内核原生支持 DDL 同步，沿用 DML 同步机制。DDL 已提交，订阅端表结构还是老的。大多数关系型数据库的逻辑复制只同步 DML,DDL 还得手动。海量数据库 DDL 沿 DML 自动同步，事务一提交就在订阅端同步执行。海量数据库满足金融、政务、电信强监管要求，业务不中断。

---

## Minimax Hub 生成步骤（操作指引）

1. **生成定妆照**：用「主讲人形象」一节中的 prompt 生成大象形象，挑选最稳的一版作为角色锚图。
2. **按 6 个分镜分别生成**：每个分镜用对应 prompt + 角色锚图（reference image），时长 4–6 秒。
3. **叠加字幕**：Minimax Hub 支持中文字幕图层，按各分镜的「字幕」要求叠加文案。
4. **拼接 + 落版**：6 段按时间顺序拼接，最后一段 27–30s 为静态落版 3 秒。
5. **导出**：竖版 9:16（抖音 / 视频号 / 小红书）或横版 16:9（B 站 / 公众号）。

---

## 制作说明

- **节奏**：配音员标准播报速度约 4 字/秒，本口播约 27 秒；加 3 秒落版 + 视觉留白 ≈ 30 秒。
- **字幕**：中文 ≤ 14 字 / 行；主钩子双行展示。
- **不要做的事**：
  - 不分多期，单期完整版。
  - 落版不超过 3 秒。
  - 不出现具体数据库名（任何关系型 / NoSQL 厂商名一律避免）。
  - 不出现函数名 / 类名 / 源码符号。
  - 表达克制，不堆砌形容词。
