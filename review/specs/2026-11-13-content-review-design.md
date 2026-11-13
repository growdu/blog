# 设计：博客内容审校（Content Review）落地机制

- 日期：2026-11-13
- 范围：`docs/` 数据库内核支柱（`database` / `db` / `pgsql` / `cluster`，共 282 篇）
- 规范来源：`review/README.md`（唯一权威，本文只描述「怎么落地」，不改写规范本身）
- 状态：已批准

---

## 1. 背景与目标

`review/README.md` 定义了一套严谨的内容审校规范：7 条审校原则、5 项技术深度要素、
AI 味信号清单、6 步审校流程、记录模板与边界。它目前只是一份**流程文档**，
没有任何可执行的机制：

- 282 篇目标文章，没有任何进度可查；
- 规范里最容易漏的一类检查（AI 味信号、证据密度）纯靠人眼数，不可复现、不可回归；
- 「小步可审」没有落地为「一篇一记录、一篇一确认」的强制约定。

**目标**：让规范变成两件可执行的东西——

1. 一个**确定性检查器**，只出信号、不下结论，把机械指标从「靠人读」变成「可复现」；
2. 一套**记录契约与进度表**，把「每篇一篇记录、状态可查、确认后才改正文」变成机器可校验的约定。

**非目标（本轮明确不做）**：

- 不引入 LLM API 调用（无凭据基础设施、成本不可控、模型不可复现）；
- 不给检查器新增 CI 工作流（部署队列已有负担；CI 只跑契约测试）；
- 不自动改写正文（两阶段，确认后才落地）；
- 不审校四支柱以外的 339 篇文章。

---

## 2. 仓库约束（决定了三处设计选择）

| 约束 | 事实 | 对设计的影响 |
|---|---|---|
| `docs/` 会被发布 | `tools/sync-hexo.py` 把 `docs/**` 转成 `source/_posts`；排除目录仅 `tests/test/fixtures/plans/pipeline/build/out/_staging/frames` | 审校记录与 spec **一律不放 `docs/` 下**，否则变成线上文章。记录放仓库根 `review/`（`sync-hexo.py` 只扫 `docs/`） |
| 根级 `tests/` 已在 CI | `.github/workflows/site-guard.yml` 跑 `python3 -m pytest tests/ -q` | 契约测试放根 `tests/`，**零 CI 成本**接入，不再新增工作流 |
| 文章形态 | 无 YAML front matter；结构为 `H1` + 「编写人/编写内容/编写时间」表格 + 正文 | 解析器按「H1 + 表格」识别元信息；审校记录同样**不加 front matter**，机器可读信息从 README 模板既有行解析 |

---

## 3. 总体架构

```
docs/<支柱>/<slug>/index.md ──[tools/review-check.py]──► 信号报告(JSON)
                                                        │
                                                        ▼
                                          Agent 判断（README 六步流程）
                                                        │
                                                        ▼
                                          review/<支柱>/<slug>.md   ← 阶段 A 产物
                                                        │
                                                   [你确认]
                                                        │
                                                        ▼
                                          docs/ 正文改动（commit: docs(review): <slug>）← 阶段 B
```

### 3.1 为什么分两层，不做成「一个审校器出完整草稿」

README 原则 1「先保真，再润色」要求判断必须带上下文；原则 3「让抽象话落地」要求
判断落到具体对象与条件。机械启发式（连接词密度、重复句）适合机器，
但「是不是空泛评价」「技术深度够不够」需要人/Agent 判断。

**工具只出信号、判断留给 Agent**，工具的启发式因此不会变成「内容的标准」——
这一点比省下的那点时间重要得多。

已排除的替代方案：

- *单一 LLM 审校器直出完整草稿*：仓库无 LLM 凭据与模型基础设施；README 原则 5 要求
  「小步可审」，全自动草稿会一次性制造 282 篇待确认噪声，与「小步」背道而驰。
- *纯人工流程 + 最小脚手架*：AI 味信号、证据密度靠人肉数，不可复现、必然漏。

### 3.2 进度表只维护一份

`review/INDEX.md`，一行一篇：slug、支柱、状态、信号数、待确认项、批次。
**不另设队列文件**——两处维护必然不一致，而契约测试会因此变成噪声源。
队列顺序直接由 INDEX 的行序表达。

---

## 4. 检查器：`tools/review-check.py`

### 4.1 契约

- 纯标准库，无第三方依赖（与 `tools/check-markdown.py`、`tools/check-built-links.py` 一致）；
- 脚本头部 docstring 写清「为什么存在」（沿用仓库既有风格）；
- 只读、不修改任何被检文件；不写仓库内文件（报告默认走 stdout 或 `--out` 指定路径）。

### 4.2 CLI

```bash
# 单篇，人读摘要
python3 tools/review-check.py docs/database/postgresql-mvcc/index.md

# 单篇，JSON
python3 tools/review-check.py docs/database/postgresql-mvcc/index.md --json

# 批量（四支柱），JSON 落盘
python3 tools/review-check.py docs/database docs/db docs/pgsql docs/cluster \
    --json --out /tmp/db-signals.json
```

- 位置参数：文件或目录（目录递归）。
- `--json`：输出 JSON；默认输出人读 Markdown 摘要。
- `--out PATH`：写入文件（默认 stdout）。
- 退出码：`0` 正常；`1` 参数或 IO 错误。**信号本身不导致非零退出**——
  信号是提示，不是门禁（否则一篇老文章的历史问题会永久卡住流水线）。

### 4.3 规则集

每条规则有**稳定编号**，供审校记录引用与单元测试断言。编号一经发布不再变更。

#### AI 味信号（对应 README「常见 AI 味信号」）

| 编号 | 判据 | 严重级 |
|---|---|---|
| `AIF-01` | 连接词密度 > 2 次/千字。词表：首先、其次、最后、此外、值得注意的是、总而言之、综上所述、总的来说、事实上 | warn |
| `AIF-02` | 空泛评价词命中且**所在段落无证据支撑**（段落内无代码块/表格/数字）。词表：高效、全面、显著、至关重要、强大、极大、非常好、行业领先、完美 | warn |
| `AIF-03` | 正文单段 > 200 字，且段内无代码块、表格、列表 | warn |
| `AIF-04` | 结尾 3 段出现泛化收尾语：希望本文、本文到此结束、以上就是、让我们一起、随着…的发展 | warn |
| `AIF-05` | 近似重复句：长度 ≥ 12 字的句子，两两相似度 ≥ 0.85（分桶比较，避免 O(n²)） | warn |

#### 技术深度（对应 README「技术深度检查」五要素的机械代理）

| 编号 | 要素 | 机械代理判据 | 严重级 |
|---|---|---|---|
| `DEP-01` | 问题边界 | 版本号（`PostgreSQL 17.2` / `v1.2.3`）、关键词：环境、前提、规模、边界 | info |
| `DEP-02` | 机制解释 | 源码路径（`src/backend/**.c`）、C 风格标识符调用（`xxx_yyy(`）、关键词：调用链、状态机、流程、实现 | info |
| `DEP-03` | 可复现证据 | 代码块内含 SQL / shell / 日志特征（`SELECT`、`CREATE`、`psql`、`docker`、`gdb`、`strace`、`perf`、`grep`…） | info |
| `DEP-04` | 工程取舍 | 关键词：相比、相比之下、替代、取舍、权衡、代价、适用场景 | info |
| `DEP-05` | 踩坑与校验 | 关键词：坑、注意、误区、验证、校验、复现、监控、陷阱、别用 | info |
| `DEP-00` | 综合判定 | 命中的要素 **< 2** 项 → 「技术深度不足」 | warn |

要素命中数只做**计数与定位**，是否达标由 Agent 结合上下文判断；
`DEP-00` 是提示，不是判决。

#### 结构与产物

| 编号 | 判据 | 严重级 |
|---|---|---|
| `STR-01` | `## ` 二级章节数 < 3 | info |
| `STR-02` | 开头 3 段无问题定位句（含「本文回答 / 本文要解决 / 为什么」或疑问句） | info |
| `STR-03` | 结尾 5 段无可带走产物（清单、检查表、下一步、下一篇、延伸阅读、系列） | info |
| `STR-04` | 相对链接目标文件不存在（`](./x.md)` / `](./x/)`） | warn |
| `STR-05` | 术语大小写不一致（`Postgresql` 这类错误变体） | info |

#### 元信息

| 编号 | 判据 | 严重级 |
|---|---|---|
| `MET-01` | 缺少「编写人 / 编写时间」信息表 | info |
| `MET-02` | 缺少 H1 标题 | info |

### 4.4 输出格式

```json
{
  "source": "docs/database/postgresql-mvcc/index.md",
  "pillar": "database",
  "slug": "postgresql-mvcc",
  "title": "PostgreSQL MVCC：一条数据是如何拥有\"分身术\"的",
  "stats": {"chars": 18422, "paragraphs": 96, "h2": 14, "code_blocks": 8,
            "images": 6, "links": 11, "tables": 3},
  "depth": {"DEP-01": 2, "DEP-02": 6, "DEP-03": 5, "DEP-04": 3, "DEP-05": 4},
  "depth_ok": true,
  "signals": [
    {"rule": "AIF-01", "severity": "warn", "line": 42,
     "excerpt": "首先我们来看…", "detail": "连接词密度 3.4/千字（阈值 2）"}
  ]
}
```

字段约定：`line` 为 1 基行号；`excerpt` 截断到 120 字符；
`pillar`/`slug` 由路径推导（`docs/<pillar>/<slug>/index.md` → pillar=`<pillar>`、slug=`<slug>`；
`docs/<pillar>/<slug>.md` → slug=`<slug>`）。

---

## 5. 审校记录

### 5.1 路径映射

| 原文 | 记录 |
|---|---|
| `docs/database/postgresql-mvcc/index.md` | `review/database/postgresql-mvcc.md` |
| `docs/database/pg-dont-do-this.md` | `review/database/pg-dont-do-this.md` |
| `docs/db/postgresql/xxx.md` | `review/db/postgresql/xxx.md`（层级原样保留） |

规则：`<支柱>/<相对路径去后缀>.md`。四支柱中仅 `_index` 跨支柱重名，
按此映射天然不冲突。

### 5.2 记录内容

**严格使用 `review/README.md` 的模板**，不新增 YAML front matter、不改小节名。
机器可读信息从模板既有行解析：

- `- 原文：` → 源文件路径
- `- 范围：` → 全文 / 第 N 节
- `- 审校状态：` → 状态机取值

「优先修改」条目里的**位置**填行号/章节，**问题**填规则编号 + 一句话描述，
**建议**给可直接采用的改法，**原因**说明为什么这么改（对应 README 原则 7）。

### 5.3 状态机

```
待审 → 审校中 → 建议中 → 已确认 → 已合入
```

- `待审`：在 INDEX 里排队，未开始
- `审校中`：Agent 正在处理
- `建议中`：记录已产出，等你确认（**阶段 A 的正常终点**）
- `已确认`：你确认了建议，正文改动待落地
- `已合入`：正文已改并提交（**阶段 B 的终点**）

非法跳转（如 `待审` → `已合入`）由契约测试拦截。

### 5.4 INDEX 列

| 列 | 说明 |
|---|---|
| 记录 | 指向 `review/<支柱>/<slug>.md` 的相对链接 |
| 支柱 | database / db / pgsql / cluster |
| 状态 | 状态机取值 |
| 信号 | warn 级信号数（info 级不进表） |
| 待确认 | 「事实待核」未清空条目数 |
| 批次 | 试点 / 1 / 2… |

---

## 6. 两阶段写入协议

### 阶段 A（审校）

1. Agent 跑检查器，拿到信号；
2. 按 README 六步流程判断，出记录 → `review/<支柱>/<slug>.md`，状态 `建议中`；
3. **不碰 `docs/`**；
4. 提交：`docs(review): 记录 <slug>`。

### 阶段 B（合入）

1. 你确认建议 → 记录状态 `已确认`；
2. 按记录改动 `docs/` 正文，**只改记录里点名的位置**，不顺手扩写；
3. 状态 `已合入` → 跑全量测试 → 提交：`docs(review): <slug>`（正文改动）；
4. 契约测试用 `git log` 反查「标了已合入，是否真有对应提交且该提交动了源文件」。

**commit message 约定**（两个前缀互斥，契约测试靠它区分阶段）：

| 阶段 | message | 含义 |
|---|---|---|
| A | `docs(review): 记录 <slug>` | 只产出审校记录，正文未动 |
| B | `docs(review): <slug>` | 正文已按确认后的记录改动并合入 |

契约测试第 5 条只认**精确等于** `docs(review): <slug>` 的提交，
因此阶段 A 的提交无法冒充阶段 B。

---

## 7. 契约测试（根 `tests/`，随 `site-guard.yml` 自动进 CI）

`tests/test_review_records.py`：

1. **路径合法**：记录位于 `review/<支柱>/` 下，支柱 ∈ 首轮白名单 {database, db, pgsql, cluster}；
2. **模板完整**：README 模板的全部小节标题齐备；
3. **原文存在**：记录里引用的源文件真实存在；
4. **索引一致**：`review/INDEX.md` 与记录目录双向一致（无孤儿记录、无缺行）；
5. **状态合法**：取值在状态机内；`已合入` 必须存在 `docs(review): <slug>` 提交，且该提交改动了源文件；
6. **事实待核闭环**：状态为 `已合入` 的记录，其「事实待核」小节必须为空或逐条标记核实；
7. **防泄露**：`docs/` 下不得出现 `review/` 目录或审校记录文件（会被发布成线上文章）。

`tests/test_review_check.py`：

- **单元**：每条规则一个正例与一个反例（内联最小文本）；
- **集成**：对 `docs/database` 真实文章跑批量，检查不崩、JSON 结构完整、支柱/slug 推导正确。

---

## 8. 分批与提交序列

每个 commit **自包含**：在「只含该 commit 内容的干净检出」上独立跑通全部测试，
不引用后续 commit 才引入的文件。

| 批次 | 内容 | 提交 |
|---|---|---|
| 0 | spec（本文） | `docs(review): 内容审校落地方案（设计）` |
| 1 | 检查器 + 单元/集成测试 | `feat(review): 审校信号检查器` |
| 2 | 契约测试 + INDEX 骨架 + 队列排序 | `feat(review): 审校记录契约与进度索引` |
| 3 | 试点审校 5 篇（database / db / pgsql / cluster / logical-replication 各 1） | **每篇一个** `docs(review): 记录 <slug>` |
| 4 | 支柱放量（按系列分批，每批 10~15 篇） | **每篇一个** `docs(review): 记录 <slug>` |

阶段 B（正文合入）同样是**每篇一个** `docs(review): <slug>`。

**先跑试点再放量**：流程没跑通就推 282 篇，返工成本是全文级的。

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 机械启发式误报（尤其 AIF-02、AIF-05） | 全部信号是 `warn`/`info`，不门禁；判据在测试里以反例锁定；Agent 判断优先于信号 |
| 信号退化成「打分刷 KPI」 | 规则只出事实计数，不出分；README 原则 6/7 要求的判断由 Agent 承担 |
| 记录与正文漂移（记了已合入但正文没改） | 契约测试第 5 条用 `git log` 反查 |
| 审校内容泄露到站点 | 记录与 spec 放仓库根 `review/`；契约测试第 7 条守住 `docs/` 纯净 |
| 282 篇进度失控 | 单一 INDEX 作进度真相源；分批放量，每批可中断 |
| 审校把「技术准确」改坏 | 阶段 A/B 分离，改动必须经确认；事实存疑一律进「事实待核」而非补全 |

---

## 10. 验收标准

- `python3 -m pytest tests/ -q` 全绿；
- `python3 tools/review-check.py docs/database docs/db docs/pgsql docs/cluster --json`
  能跑完 282 篇，输出结构完整、无异常；
- 试点 5 篇审校记录齐备，INDEX 与之一致，状态机合法；
- `docs/` 未被本轮流程改动（阶段 A 的边界），无任何审校内容进入站点。
